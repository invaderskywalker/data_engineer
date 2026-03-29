from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.utility import FORMAT_DATA_FOR_GRAPH, UTILITY_AGENT_NUDGE

class UtilityAgent(BaseAgent):
    name= "utility_agent"
    description= """
        The Utility Agent is responsible for doing non primary tasks such as formating data for graph visualization,
        exporting answers in output format - like pdf, ppt.
        
        So basically,
            this won't create data: this wil use the data created 
            from the other agents and this will use that data do do some tasks.
        
    """
    functions= [
        FORMAT_DATA_FOR_GRAPH,
        # UTILITY_AGENT_NUDGE
    ]
        
    def __init__(self, log_info = None):
        super().__init__(log_info)
    

    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    
    # def plan_functions(self, agents_prompt, conv, user_context):
    #     data = self.fetch_data_for_blueprint_creation()
    #     return self._plan_functions(data, agents_prompt, conv, user_context)
    
    
    def fetch_data_for_blueprint_creation(self):
        return f"""
            You are an agent which will understand the user request and
            and execute the tasks.
        """
  