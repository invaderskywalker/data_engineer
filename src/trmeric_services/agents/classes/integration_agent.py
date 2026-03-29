from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.integration_agent import INTEGRATION_AGENT

from src.trmeric_services.agents.functions.integration_agent.actions import RUN_TENANT_CRON
class IntegrationAgent(BaseAgent):
    name = "integration_agent"
    description = """
        
    """

    functions = [
        INTEGRATION_AGENT
    ]

    def __init__(self, log_info=None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions() 

    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)

    def fetch_data_for_blueprint_creation(self):
        return ""
    
    
    def action_function_getter(self,action):
        """
        Returns the action function for the given action name.
        """
        print("--deubg action function getter in resource planning agent", action)
        if action in self.action_map:
            return self.action_map[action]
        else:
            raise ValueError(f"Action {action} not found in ResourcePlanningAgent.")
        
        
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in ResourcePlanningAgent-----",agent_function.name)
        # self.action_map[action_name] = agent_function
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }
        # print(f"Action functions registered:{agent_function.name} in ResourcePlanningAgent: \n\n{self.action_map}")
        
        
    def action_functions(self):
        self.register_action_functions(action_name="cron_run_for_tenant",agent_function=RUN_TENANT_CRON)



