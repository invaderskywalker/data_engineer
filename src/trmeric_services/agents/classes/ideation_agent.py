from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.idea_pad.IdeaPadService import IdeaPadService,QNA_CHAT_PREFILL_IDEA,CREATE_IDEA_LOGS,CREATE_IDEA_SCOPE, CREATE_DEMAND_INSIGHTS_FROM_IDEA
from src.trmeric_services.agents.functions.ideation_agent import UPDATE_IDEA_RANKS, UPDATE_IDEA_PORTFOLIO_RANKS,IDEA_RANKING_AGENT
# from src.controller.qna import QNA_CHAT_PREFILL
# from functools import partial
# from src.trmeric_services.agents.core.agent_functions import AgentFunction

OTHERS = ["update_rank","update_portfolio_rank"]

class IdeationAgent(BaseAgent):
    name= "ideation_agent"
    description= "This agent is responsible for generating new idea, managing idea rankings, and facilitating ideation processes."
    
    functions= [
        IDEA_RANKING_AGENT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.idea_service = IdeaPadService()
        self.action_map = {}
        self.action_functions()
         
        
    def action_function_getter(self, action):
        """
        Returns the action function for the given action name.
        """
        print("--deubg action function getter in ideation_agent", action)
        if action in self.action_map:
            return self.action_map[action]
        
        return None
    
    
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in IdeationAgent-----",agent_function.name)
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function.__get__(self.idea_service, IdeaPadService) if action_name not in OTHERS else agent_function.function
        }

    def action_functions(self):

        # Create a partial function to bind _type
        # create_idea_function = partial(QNA_CHAT_PREFILL.function, _type=6) # 6 for idea
        # # Register the partial function for create_idea
        # self.register_action_functions(
        #     action_name="create_idea",
        #     agent_function=AgentFunction(
        #         name=QNA_CHAT_PREFILL.name,
        #         description=QNA_CHAT_PREFILL.description,
        #         args=QNA_CHAT_PREFILL.args,
        #         return_description=QNA_CHAT_PREFILL.return_description,
        #         function=create_idea_function,
        #         type_of_func=QNA_CHAT_PREFILL.type_of_func
        #     )
        # )

        self.register_action_functions(action_name="create_idea", agent_function=QNA_CHAT_PREFILL_IDEA)
        self.register_action_functions(action_name="ideation_changelog", agent_function=CREATE_IDEA_LOGS)
        # self.register_action_functions(action_name="create_ideascope", agent_function=CREATE_IDEA_SCOPE)
        self.register_action_functions(action_name="create_demand_insights", agent_function=CREATE_DEMAND_INSIGHTS_FROM_IDEA)
        
        self.register_action_functions(action_name="update_rank", agent_function=UPDATE_IDEA_RANKS)
        self.register_action_functions(action_name="update_portfolio_rank", agent_function=UPDATE_IDEA_PORTFOLIO_RANKS)

    
    


