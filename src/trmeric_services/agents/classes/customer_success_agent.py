from src.trmeric_services.agents.core import BaseAgent
# from src.trmeric_services.agents.functions.common import PROJECT_ANALYST
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.customer_success import MANAGE_BUG_ENHANCEMENT

class CustomerSuccessAgent(BaseAgent):
    name= "customer_success_agent"
    description= """
        
    """
    
    functions= [
        MANAGE_BUG_ENHANCEMENT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        return ""
  