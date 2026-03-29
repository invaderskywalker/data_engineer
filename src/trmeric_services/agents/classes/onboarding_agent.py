from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.onboarding.profile import PROFILE_CREATION_FUNC, PROFILE_CREATION_CANCEL
from src.trmeric_services.agents.functions.onboarding.roadmap import ROADMAP_CREATION_FUNC, ROADMAP_CREATION_CANCEL
from src.trmeric_services.agents.functions.onboarding.project import PROJECT_CREATION_FUNC, PROJECT_CREATION_CANCEL

from src.trmeric_services.agents.functions.onboarding.capacity.capacity import CAPACITY_CREATION_FUNC, CAPACITY_CREATION_CANCEL,PROVIDER_CAPACITY_CREATION_FUNC,FINISH_CAPACITY_CREATION_FUNC,CAPACITY_FILE_UPLOAD
from src.trmeric_services.agents.functions.onboarding.transition import TRANSITION_CREATION_FUNC, GENERAL_CREATION_FUNC

class OnboardingAgent(BaseAgent):
    name= "onboarding_agent"
    description= """
            The onboarding agent is to be used when a tenant is onboarded to the platform for the first time. The onboarding agents works in creation for three categories. 
            We can create the company profile, roadmaps, and projects based off user provided documents and documents from integrations.
    """
    functions= [
        PROFILE_CREATION_FUNC,
        ROADMAP_CREATION_FUNC,
        PROJECT_CREATION_FUNC,
        CAPACITY_CREATION_FUNC,
        PROVIDER_CAPACITY_CREATION_FUNC,
        FINISH_CAPACITY_CREATION_FUNC,
        PROFILE_CREATION_CANCEL,
        ROADMAP_CREATION_CANCEL,
        PROJECT_CREATION_CANCEL,
        CAPACITY_CREATION_CANCEL,
        TRANSITION_CREATION_FUNC,
        GENERAL_CREATION_FUNC
    ]
        
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions()
        

    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    
    def fetch_data_for_blueprint_creation(self):
        return f"""
            You are an agent which will understand the user request and execute the tasks.
            
            Remember that the onboarding agent can only exist in three states. It is either creating a company profile, a roadmap, or a project.
            
            Always start the chat by asking the user what they would like to create. 
        """
        
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
        print("--deubg Agent function in OnboardingAgent-----",agent_function.name)
        # self.action_map[action_name] = agent_function
        
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }        
        
    def action_functions(self):
        self.register_action_functions(action_name="specific_capacity_creation", agent_function=CAPACITY_FILE_UPLOAD)
        

  