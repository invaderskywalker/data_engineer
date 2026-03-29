from src.trmeric_services.agents.core import BaseAgent
# from src.trmeric_services.agents.functions.common import PROJECT_ANALYST
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.onbaording_v2 import FETCH_STATES_V3,ONBOARDING_CONTROLLER,ONBOARDING_CONTROLLER_V3,SAVE_PROGRESS,DISCARD_PROGRESS,FETCH_STATES



class OnboardingV2(BaseAgent):
    name= "onboarding_v2"
    description= ""
    
    functions= [
       
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions()
        
        # self.functions = [
        #         ONBOARDING_CONTROLLER,
        #         ONBOARDING_CONTROLLER_V3,
        #         FETCH_STATES_V3,
        #         FETCH_STATES,
        #         DISCARD_PROGRESS,
        #         SAVE_PROGRESS
        #     ]
        # self.action_map = {
        #     "chat_onboarding_v2":{"name": self.functions[0].name, "function": self.functions[0].function},
        #     "chat_onboarding_v3":{"name": self.functions[1].name, "function": self.functions[1].function},
        #     "fetch_states_v3":{"name": self.functions[2].name, "function": self.functions[2].function},
        #     "chat_onboarding_v3":{"name": self.functions[0].name, "function": self.functions[0].function},
        #     "initiate_onboarding_v2":{"name": self.functions[0].name, "function": self.functions[0].function},
        #     "fetch_states":{"name": self.functions[3].name, "function": self.functions[3].function},
        #     "discard_progress":{"name": self.functions[4].name, "function": self.functions[4].function},
        #     "save_progress":{"name": self.functions[5].name, "function": self.functions[5].function}
        # }
            
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

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
    
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in OnboardingAgentV2-----",agent_function.name)
        # self.action_map[action_name] = agent_function
        
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }


    def action_functions(self):
        self.register_action_functions(action_name="chat_onboarding_v2", agent_function=ONBOARDING_CONTROLLER)
        self.register_action_functions(action_name="chat_onboarding_v3", agent_function=ONBOARDING_CONTROLLER_V3)
        self.register_action_functions(action_name="fetch_states_v3", agent_function=FETCH_STATES_V3)
        self.register_action_functions(action_name="fetch_states", agent_function=FETCH_STATES)
        self.register_action_functions(action_name="discard_progress", agent_function=DISCARD_PROGRESS)
        self.register_action_functions(action_name="save_progress", agent_function=SAVE_PROGRESS)
        self.register_action_functions(action_name="initiate_onboarding_v2", agent_function=ONBOARDING_CONTROLLER)
        