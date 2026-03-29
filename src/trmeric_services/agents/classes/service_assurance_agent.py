from src.trmeric_services.agents.core import BaseAgent
# from src.trmeric_services.agents.functions.common import PROJECT_ANALYST
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.service_assurance import *

class ServiceAssuranceAgent(BaseAgent):
    name= "service_assurance_agent"
    description= """
        The servie assurance agent will help to decide if the project execution is going well
        see from our projects data we can capture if milestones are completed on time,
        they are delayed, why they afe delayed. why projects are going over budget etc all 
        related to project execution.
        
        And it has the power of the funtionalities update project status ui and update status milestone risk..
        
        So, after showing the ui.. updates can be done
    """
    
    functions= [
        # PROJECT_ANALYST,
        # UPDATE_PROJECT_STATUS,
        UPDATE_PROJECT_STATUS_UI,
        UPDATE_STATUS_MILESTONE_RISK,
        # SERVICE_ASSURANCE_ANALYST,
        UPDATE_OR_CREATE_ACTION
        # SERVICE_ASSURANCE_INSIGHT,
        # UPDATE_OR_CREATE_RISK,
        # UPDATE_OR_CREATE_ACTION
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.action_map = {}
        self.agent_actions = self.action_functions()
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        return ""
    
    
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
        print("--deubg Agent function in ServiceAssuranceAgent-----",agent_function.name)
        # self.action_map[action_name] = agent_function
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function
        }
        
        # print(f"Action functions registered:{agent_function.name} in ServiceAssuranceAgent: \n\n{self.action_map}")
        
        
    def action_functions(self):
        self.register_action_functions(action_name="create_service_assurance_report", agent_function=CREATE_SERVICE_ASSURNACE_REPORT)
        self.register_action_functions(action_name="create_project_review_screen",agent_function= CREATE_PROJECT_REVIEW_REPORT)
        self.register_action_functions(action_name="fetch_status_update_basic_data",agent_function= UPDATE_STATUS_BASIC_DATA)
        self.register_action_functions(action_name="update_status_step1",agent_function= UPDATE_STATUS_MILESTONE_RISK_V2)
        self.register_action_functions(action_name="update_status_step2",agent_function= UPDATE_STATUS_MILESTONE_RISK_V2)



  