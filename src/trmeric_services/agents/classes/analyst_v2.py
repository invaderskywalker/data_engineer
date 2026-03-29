from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.analyst import VIEW_GENERAL_COMBINED_ANALYSIS

class Analyst(BaseAgent):
    name= "analyst_v2"
    description= """
        Analyst whose work is to do deep research and analysis on 
        Roadmap (future projects) and Project (ongoing projects/initiatives).

    """
    
    functions= [
        VIEW_GENERAL_COMBINED_ANALYSIS
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        return ""
    
