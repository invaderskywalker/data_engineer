from src.trmeric_services.agents.core import BaseAgent
# from src.trmeric_services.agents.functions.common import PROJECT_ANALYST
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.roadmap_analyst import VIEW_ROADMAP, VIEW_PROJECTS, VIEW_COMBINED_ANALYSIS

class RoadmapAnalyst(BaseAgent):
    name= "analyst"
    description= """
        Analyst whose work is to do deep research and analysis on 
        Roadmap (future projects) and Project (ongoing projects/initiatives).
        
        Alwys trigger VIEW_COMBINED_ANALYSIS agent.
    """
    
    functions= [
        # VIEW_ROADMAP,
        # VIEW_PROJECTS,
        VIEW_COMBINED_ANALYSIS
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        return ""
    
