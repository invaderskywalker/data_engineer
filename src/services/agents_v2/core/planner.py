from typing import Dict
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.api.logging.AppLogger import appLogger
from src.database.dao import TenantDao
import re
import traceback
from datetime import datetime
from .data_getters import DataGetters


class Planner:
    """Generates a JSON plan for query processing based on configuration and intent."""
    def __init__(self, config: Dict, llm, log_info: Dict, getters: DataGetters, actors=None):
        self.config = config
        self.llm = llm
        self.log_info = log_info
        self.data_getters = getters

    def _construct_planning_prompt(self):
        pass
    
    
    def plan_combined_analysis(self, query: str) -> Dict:
        """Generates a JSON plan for query processing."""
        appLogger.info({"function": "plan_combined_analysis_start", "tenant_id": self.log_info["tenant_id"], "user_id": self.log_info["user_id"], "query": query})
        
        if not self.llm:
            raise ValueError("LLM instance is required for planning analysis")

        prompt_template = self.config["prompts"][response_type]["template"]        
        
        # Build context
        current_date = datetime.now().date().isoformat()
        conv = self.context_builder.base_agent.conversation.format_conversation() if self.context_builder.base_agent else "No prior conversation."
        tenant_type = TenantDao.checkCustomerType(self.context_builder.tenant_id)
        context = self.context_builder.build_context()

        # Prepare prompt
        system_prompt = prompt_template.format(
            query=query,
            context=context,
            current_date=current_date,
            conversation=conv,
            tenant_type=tenant_type,
            available_data_sources=list(self.context_builder.data_sources.keys()),
            available_actions=list(self.context_builder.actions.keys())
        )

        # Initialize plan
        plan = {
            "response_type": response_type,
            "agents_to_trigger": [],
            "data_sources_to_trigger": intent.get("data_sources", []),
            "actions_to_trigger": intent.get("actions", []),
            "data_source_params": {},
            "action_params": {},
            "combination_logic": "Synthesize data based on query intent and context",
            "planning_rationale": f"Selected {response_type} based on intent: {intent['name']} (keywords: {intent['keywords']})",
            "clarification_needed": False,
            "clarification_message": None
        }

        # Handle specific intents
        if intent["name"] == "bug_enhancement":
            bug_type = re.search(r"(bug|enhancement)", query, re.IGNORECASE)
            plan["data_source_params"]["get_bug_enhancement_data"] = {
                "bug_type": bug_type.group(1) if bug_type else None,
                "status": None,
                "project_id": int(project_id.group(1)) if project_id else None
            }
            plan["action_params"]["log_bug_or_enhancement"] = {
                "bug_type": bug_type.group(1) if bug_type else None,
                "description": query,
                "project_id": int(project_id.group(1)) if project_id else None
            }

        if "snapshot" in query.lower():
            snapshot_type = next((s for s in ["portfolio_snapshot", "performance_snapshot_last_quarter", "value_snapshot_last_quarter", "risk_snapshot"] if s in query.lower()), None)
            if snapshot_type:
                plan["data_sources_to_trigger"].append("get_snapshots")
                plan["data_source_params"]["get_snapshots"] = {
                    "snapshot_type": snapshot_type,
                    "last_quarter_start": None,
                    "last_quarter_end": None,
                    "portfolio_id": portfolio_ids[0] if len(portfolio_ids) == 1 else None,
                    "kwargs": {"portfolio_ids": portfolio_ids} if portfolio_ids else {}
                }

        if roadmap_id:
            plan["agents_to_trigger"].append("roadmap")
            plan["roadmap_query"] = f"Analyze roadmap ID {roadmap_id.group(1)}"

        if project_id:
            plan["agents_to_trigger"].append("project")
            plan["project_query"] = f"Analyze project ID {project_id.group(1)}"

        # Context validation
        if not self.context_builder.has_designation():
            plan["actions_to_trigger"].append("set_user_designation")
            plan["action_params"]["set_user_designation"] = {"designation": None}
            plan["clarification_needed"] = True
            plan["clarification_message"] = "Please provide your designation."

        try:
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user=f"Plan response for: '{query}'. JSON output is mandatory.")
            response = self.llm.run(chat_completion, ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.3), 'trucible::plan', logInDb=self.log_info)
            plan = extract_json_after_llm(response)
            appLogger.info({"function": "plan_combined_analysis_success", "tenant_id": self.log_info["tenant_id"], "query": query, "plan": plan})
            return plan
        except Exception as e:
            appLogger.error({"function": "plan_combined_analysis_error", "error": str(e), "traceback": traceback.format_exc()})
            raise
        
        