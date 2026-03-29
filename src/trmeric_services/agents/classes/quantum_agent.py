from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import ProjectsDao,TangoDao
from src.trmeric_services.provider.quantum.QuantumService import QUANTUM_ONBOARD
from src.trmeric_services.provider.quantum.actions import QUANTUM_PROCESS_DOCS


class QuantumAgent(BaseAgent):
    name= "quantum_agent"
    description= """
        This is a Quantum Agent whose main purpose is to prepare the blueprint for the Onboarding process of Providers
        in Trmeric platform. It will guide the user through the process to ensure all the necessary information is collected
        and the onboarding is completed successfully. 
        The agent will also provide assistance in case of any issues or questions during the onboarding process.

    """
    
    functions= [
        QUANTUM_ONBOARD
    ]
    
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions()
        
    def action_function_getter(self,action):
        """
        Returns the action function for the given action name.
        """
        print("--deubg action function getter in quantum agent", action)
        if action in self.action_map:
            return self.action_map[action]
        else:
            raise ValueError(f"Action {action} not found in QuantumAgent.")
        
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in QuantumAgent-----",agent_function.name)
        # self.action_map[action_name] = agent_function
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }


    def action_functions(self):
        self.register_action_functions(action_name="process_uploaded_doc", agent_function=QUANTUM_PROCESS_DOCS)
        
        
  