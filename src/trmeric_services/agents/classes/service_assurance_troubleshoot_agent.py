from src.trmeric_services.agents.core import BaseAgent
# from src.trmeric_services.agents.functions.common import PROJECT_ANALYST
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.service_assurance_troubleshoot import SERVICE_ASSURANCE_TROUBLESHOOT

class ServiceAssuranceTroubleShootAgent(BaseAgent):
    name= "service_assurance_troubleshoot_agent"
    description= """
        A part of a bigger service assurance aggent. 
        but this agent focuses on finding solution to problem in customers projects
    """
    
    functions= [
        SERVICE_ASSURANCE_TROUBLESHOOT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        return ""

    def fetch_data_for_blueprint_creation(self):
        return ""
  