from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.portfolio import  PORTFOLIO_REVIEW, QNA_CHAT_PREFILL_PORTFOLIO, PORTFOLIO_PROFILE
from src.trmeric_database.dao import PortfolioDao

class PortfolioManagementAgent(BaseAgent):
    name= "portfolio_agent"
    description= """
        The Portfolio Management Agent handles all tasks related to managing 
        and analyzing portfolios or reviewing portfolios
    """
    
    functions= [
        # PORTFOLIO_INSIGHTS,
        # CREATE_PORTFOLIO
        # PORTFOLIO_ANALYST
        PORTFOLIO_REVIEW
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        self.action_map = {}
        self.action_functions()
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    

    def fetch_data_for_blueprint_creation(self):
        portfolios_and_project = PortfolioDao.fetchPortfolioDetailsForApplicableProjectsForUser(tenant_id=self.log_info.get("tenant_id"), projects_list=self.eligible_projects)
        return f"""
            portfolio and project data: {portfolios_and_project}
        """
        
    def generate_response_prompt(self, analysis_results):
        prompt = ""
        return prompt


    def action_function_getter(self, action):

        """Returns the action function for the given action name."""
        print("--deubg action function getter in ideation_agent", action)
        if action in self.action_map:
            return self.action_map[action]
        
        return None
    
    
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in portfolioAgent-----",agent_function.name)
        self.action_map[action_name] = {"name": agent_function.name,"function": agent_function.function}

    def action_functions(self):

        self.register_action_functions(action_name="create_portfolio", agent_function=QNA_CHAT_PREFILL_PORTFOLIO)
        self.register_action_functions(action_name="create_portfolio_profile", agent_function=PORTFOLIO_PROFILE)




  