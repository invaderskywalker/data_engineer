from src.trmeric_services.agents.core import BaseAgent

from src.trmeric_services.agents.functions.roadmap_agent import ROADMAP_AGENT, UPDATE_ROADMAP_DATES, UPDATE_ROADMAP_RANKS, UPDATE_ROADMAP_PORTFOLIO_RANKS, ROADMAP_SCHEDULE_REVIEW
from src.trmeric_services.agents.functions.solution_agent.agent import CREATE_ROADMAP_SOLUTION, CREATE_SOLUTION_FROM_TEMPLATE

class RoadmapAgent(BaseAgent):
    name= "roadmap_agent"
    description= """
        
    """
    
    functions= [
        ROADMAP_AGENT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        self.action_map = {}
        self.action_functions()
        
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        return ""
    

    def fetch_data_for_blueprint_creation(self):
        return ""


    def action_function_getter(self, action):
        print("--deubg action function getter in ideation_agent", action)
        if action in self.action_map:
            return self.action_map[action]
        
        return None
    
    
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in RoadmapAgent-----",agent_function.name)
        self.action_map[action_name] = {"name": agent_function.name,"function": agent_function.function}

    def action_functions(self):
        #Including solution agent functions for roadmap
        self.register_action_functions(action_name="create_solution", agent_function=CREATE_ROADMAP_SOLUTION)

        self.register_action_functions(action_name="update_rank", agent_function=UPDATE_ROADMAP_RANKS)
        self.register_action_functions(action_name="update_timeline", agent_function=UPDATE_ROADMAP_DATES)
        self.register_action_functions(action_name="update_portfolio_rank", agent_function=UPDATE_ROADMAP_PORTFOLIO_RANKS)

        self.register_action_functions(action_name="create", agent_function=CREATE_SOLUTION_FROM_TEMPLATE)
        self.register_action_functions(action_name="roadmap_schedule_review", agent_function=ROADMAP_SCHEDULE_REVIEW)

        


    
