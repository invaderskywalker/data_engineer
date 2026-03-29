
###### super agent --> core --> runtime_policy.py

from .rules import *

class AgentRuntimePolicy:
    """
    Lightweight, read-only policy.
    No intelligence. No execution.
    Just prompt framing + metadata access.
    """

    def __init__(self, agent_config: dict):
        self.cfg = agent_config

    # -----------------------------
    # Identity (prompt only)
    # -----------------------------

    @property
    def agent_name(self) -> str:
        return self.cfg.get("agent_name", "agent")

    @property
    def agent_role(self) -> str:
        return self.cfg.get("agent_role", "")

    @property
    def mission(self) -> str:
        return self.cfg.get("mission", "")
    
    @property
    def thinking_style(self) -> str:
        return self.cfg.get("thinking_style", "")

    @property
    def mode(self) -> str:
        return self.cfg.get("mode", "")

    @property
    def version(self) -> str:
        return self.cfg.get("version", "v1")
    
    @property
    def capabilities(self):
        return self.cfg.get("capabilities")

    # -----------------------------
    # Prompt helper
    # -----------------------------

    # @property
    # def decision_process_prompt(self) -> str:
    #     base = f"""
    #         You are {self.agent_name}.

    #         Role:
    #         {self.agent_role}

    #         Mission:
    #         {self.mission}

    #         How you should think:
    #             - Start with a rough idea, not a perfect plan
    #             - Learn by executing and observing real data
    #             - Decide criteria only after seeing reality
    #             - Prefer correctness over speed

    #         Planning principles:
    #             - If the plan feels unclear, make that uncertainty explicit instead of guessing
    #             - It is acceptable to discover that the original approach was wrong
    #             - Only think about actions that are actually available to you

    #         CRITICAL EXECUTION RULE:
    #             - If an action is listed in Available Actions, you ARE allowed to execute it
    #             - You must NOT assume hidden restrictions or missing pipelines
    #             - Do NOT ask whether an action is possible — its presence means it is permitted
                
    #         You must obey the AGENT BEHAVIOR CONTRACT.
            
    #         Epistemic reminder:
    #             - You do NOT retain data across runs
    #             - Explicit re-acquisition is required for continuity

    #         """

    #     return base.strip()


    
    @property
    def rough_plan_schema(self):
        if self.mode == "deep_research":
            return DEEP_SEARCH_ROUGH_PLAN_SCHEMA
        return ROUGH_PLAN_SCHEMA
    
    @property
    def behavior_contract(self) -> str:
        return self.cfg.get("behavior_contract", "") or ""
    
    # @property
    # def execution_step_schema(self):
    #     if self.mode == "deep_research":
    #         return DEEP_RESEARCH_EXECUTION_STEP_SCHEMA
    #     return EXECUTION_STEP_SCHEMA
    
    
    @property
    def execution_step_schema(self):
        # No longer decides based on policy.mode
        # base schema only — SuperAgent picks the right one
        return EXECUTION_STEP_SCHEMA

    @property
    def deep_research_execution_step_schema(self):
        return DEEP_RESEARCH_EXECUTION_STEP_SCHEMA
    

        
