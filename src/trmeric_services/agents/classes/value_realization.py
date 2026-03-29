from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.value_realization import VALUE_REALIZATION

class ValueRealization(BaseAgent):
    name= "value_realization_agent"
    description= """
        The Value realization agent will be used when a project has been completed in the platform and the user wants to 
        track the progress of the delivered projects in terms of meeting the key results.
        
        The value realization agent works in creation of learning fabric of the organization.
        We can input the key learnings, challenges, ideas on what can be done better to fetch the insights.
    """
    
    functions= [
        VALUE_REALIZATION
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        # tenant_id = self.log_info.get("tenant_id")
        # user_id = self.log_info.get("user_id")

        # print("--debug in ValueRealization tenant , user id", tenant_id, user_id)
        # self.eligible_projects = ProjectsDao.FetchEligibleProjectsForVRAgent(tenant_id,user_id)
        # print("--debug vr agent eligible_projects :", self.eligible_projects)
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        return ""
  