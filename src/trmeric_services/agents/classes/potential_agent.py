from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.potential_agent.potential import Potential,UPLOAD_POTENTIAL_DATA
from src.trmeric_services.agents.functions.potential_agent.analyst import POTENTIAL_ANALYST



class PotentialAgent(BaseAgent):
    name= "potential_agent"
    description= """
        The Potential Agent handles all tasks related to identifying and analyzing potential opportunities
    """
    
    functions= [
        POTENTIAL_ANALYST
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.potential_service = Potential()
        self.action_map = {}
        self.agent_actions = self.action_functions() 
        
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

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
            "function": agent_function.function.__get__(self.potential_service,Potential)
        }
        # print(f"Action functions registered:{agent_function.name} in ResourcePlanningAgent: \n\n{self.action_map}")
        
        
    def action_functions(self):
        pass
        # self.register_action_functions(action_name="upload_data", agent_function=UPLOAD_POTENTIAL_DATA)