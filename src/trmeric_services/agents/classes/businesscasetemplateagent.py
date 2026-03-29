from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.businesscase_agent import BusinessTemplateAgent,CREATE_BUSINESSCASE_FROM_TEMPLATE,RETRIGGER_FINANCIAL

class BusinessCaseTemplateAgent(BaseAgent):
    name= "business_template_agent"
    description= ""
    
    functions= [
        BusinessTemplateAgent
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions()
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        return ""

    def fetch_data_for_blueprint_creation(self):
        return ""
    
    
    def action_function_getter(self, action):
        """
        Returns the action function for the given action name.
        """
        print("--deubg action function getter in project creation agent", action)
        if action in self.action_map:
            return self.action_map[action]
        
        return None
    
    def register_action_functions(self, action_name, agent_function):
        # self.action_map[action_name] = agent_function
        
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }
    
    def action_functions(self):
        self.register_action_functions(action_name="create_from_template", agent_function=CREATE_BUSINESSCASE_FROM_TEMPLATE)
        self.register_action_functions(action_name="retrigger_business_case",agent_function= RETRIGGER_FINANCIAL)
    
  