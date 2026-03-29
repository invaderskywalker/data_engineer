import re
import json
import traceback
import numpy as np
from datetime import datetime
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.reinforcement import core, engine, feedback
from src.trmeric_database.Redis import RedClient

# Policy Management
class PolicyOptimizer:
    def __init__(self):
        # self.policy_cache = {}
        self.rl = core.ReinforcementLearning()
        self.redis = RedClient()

    def get_optimized_params(self, tenant_id, agent_name, feature_name, current_params,section=None,subsection=None,user_id:int=None):
        if user_id:
            key_set = f"ReinforcementPolicyOptimizer::tenant_id::{tenant_id}::user_id::{user_id}::Agent::{agent_name}::Feature::{feature_name}"
        else:
            key_set = f"ReinforcementPolicyOptimizer::tenant_id::{tenant_id}::Agent::{agent_name}::Feature::{feature_name}"
        return self.redis.execute(
            query = lambda: self.get_optimized_params_utils(tenant_id, agent_name, feature_name, current_params,section=section,subsection=subsection,user_id=user_id),
            key_set = key_set,
            expire = 3600  # Cache for 1 hour
        )

    def get_optimized_params_utils(self, tenant_id, agent_name, feature_name, current_params,section=None,subsection=None,user_id:int=None):
        """
        Returns optimized model parameters and stores delta prompts.
        """
        # cache_key = (tenant_id, feature_name)
        # if cache_key in self.policy_cache:
        #     return self.policy_cache[cache_key]
    
        # Use a single DifferentialRewardEngine instance
        reward_engine = engine.DifferentialRewardEngine(tenant_id, agent_name, feature_name,section=section,subsection=subsection,user_id=user_id)
        reward = reward_engine.calculate_reward()
        print("--debug reward----------------", reward)

        # Generate and store instruction rules
        rules, metadata = reward_engine.analyze_feedback_patterns()

        # print("--debug [PolicyOptimizer] rules generated:", rules, "\nMetadata: ", metadata)
        if rules:
            # delta_prompt = "\n".join([f"RULE: {rule}" for rule in rules])
            delta_prompt = self.build_enhanced_delta_prompt(rules, metadata)
            # print("--deubg [Delta Prompt]-------", delta_prompt, metadata)
            
            self.rl.store_delta_prompt(
                tenant_id=tenant_id,
                feature_name=feature_name,
                agent_name=agent_name,
                user_id=user_id,  
                delta_prompt=delta_prompt,
                metadata=metadata,
                section=section,
                subsection=subsection,
            )

        # Adjust temperature and tokens
        new_temp = self._adjust_temperature(current_params.temperature, reward)
        new_tokens = self._adjust_tokens(current_params.max_tokens, reward)

        optimized_params = ModelOptions(
            model=current_params.model,
            temperature=new_temp,
            max_tokens=new_tokens
        )
        # print("--debug optimized_options--", optimized_params, optimized_params.model, optimized_params.max_tokens, optimized_params.temperature)
        return optimized_params

    def _adjust_temperature(self, base_temp, reward):
        """
        Adjust temperature based on reward (-1 to 1).
        """
        return np.clip(
            base_temp * (0.8 + 0.4 * reward),  # Scaling factor
            0.1,  # Min temp
            0.9   # Max temp
        )

    def _adjust_tokens(self, base_tokens, reward):
        """
        Adjust max_tokens based on reward (-1 to 1), ensuring positive values.
        """
        # Scale tokens: 0.8 (min) to 1.2 (max) based on reward
        scale = 0.8 + 0.4 * (reward + 1) / 2  # Maps reward [-1,1] to [0.8,1.2]
        new_tokens = int(base_tokens * scale)
        return max(1, min(new_tokens, base_tokens))  # Enforce min=1, max=base_tokens

    def _select_prompt_template(self, reward):
        """
        Select prompt template based on reward (unused in current implementation).
        """
        if reward > 0.5:
            return "detailed_template"
        elif reward > -0.5:
            return "standard_template"
        else:
            return "simple_template"



    def build_enhanced_delta_prompt(self,rules, metadata):
        lines = [f"RULE: {r}" for r in rules]
        xg = metadata.get("xgboost_quality", {})
        score = xg.get("score", 5.0)
        percentile = xg.get("percentile", 50)
        drivers = xg.get("top_drivers", [])[:2]

        # Quality level
        if score < 5:
            lines.append(f"CRITICAL: Feedback quality is LOW ({score}/10, bottom {100-percentile:.0f}%)")
        elif score < 7:
            lines.append(f"WARNING: Feedback quality is BELOW AVERAGE ({score}/10)")
        else:
            lines.append(f"NOTE: Feedback quality is AVERAGE or better ({score}/10)")

        # Top driver insight
        if drivers:
            d = drivers[0]
            if "word_count" in d["feature"] and d["impact"] > 0:
                lines.append("HINT: Users prefer SHORT, CLEAR feedback")
            elif "sentiment" in d["feature"] and d["impact"] < 0:
                lines.append("HINT: Avoid negative tone unless necessary")
            elif "vague" in d["feature"]:
                lines.append("HINT: Users complain about VAGUE responses — be specific")

        # Critical patterns
        for p, data in metadata.get("pattern_scores", {}).items():
            if data.get("priority") == "critical":
                name = p.replace("_", " ").title()
                lines.append(f"PRIORITY: Fix {name}")

        if percentile < 30:
            lines.append("URGENT: You are in the BOTTOM 30% of feedback quality")
        elif percentile > 70:
            lines.append("KEEP IT UP: You are in the TOP 30%")

        return "\n".join(lines)
