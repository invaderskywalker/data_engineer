from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.project_creation import PROJECT_CREATION_AGENT
from src.trmeric_services.project.projectService import ProjectService, UPDATE_PROJECT_CANVAS, CREATE_PROJECT_SCOPE,TANGO_ASSIST_PROJECT,QNA_CHAT_PREFILL_PROJECT

class ProjectCreationAgent(BaseAgent):
    name= "project_creation_agent"
    description= ""
    
    functions= [
        PROJECT_CREATION_AGENT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
        self.project_service = ProjectService()
        self.action_map = {}
        self.action_functions()
        
        # self.functions = [
        #     UPDATE_PROJECT_CANVAS.__class__(
        #         name=UPDATE_PROJECT_CANVAS.name,
        #         description=UPDATE_PROJECT_CANVAS.description,
        #         args=UPDATE_PROJECT_CANVAS.args,
        #         return_description=UPDATE_PROJECT_CANVAS.return_description,
        #         function=self.project_service.updateProjectCanvas,
        #         type_of_func=UPDATE_PROJECT_CANVAS.type_of_func
        #     ),
        #     CREATE_PROJECT_SCOPE.__class__(
        #         name=CREATE_PROJECT_SCOPE.name,
        #         description=CREATE_PROJECT_SCOPE.description,
        #         args=CREATE_PROJECT_SCOPE.args,
        #         return_description=CREATE_PROJECT_SCOPE.return_description,
        #         function=self.project_service.fetchScopeFromIntegration,
        #         type_of_func=CREATE_PROJECT_SCOPE.type_of_func
        #     )
        # ]
        # self.action_map = {
        #     "update_project_canvas": {"name": self.functions[0].name, "function": self.functions[0].function},
        #     "fetch_scope_driveintegration":{"name": self.functions[1].name, "function": self.functions[1].function}
        # }
        
        
    def action_function_getter(self, action):
        """
        Returns the action function for the given action name.
        """
        print("--deubg action function getter in project creation agent", action)
        if action in self.action_map:
            return self.action_map[action]
        
        return None
    
    
    def register_action_functions(self,action_name, agent_function):
        """
        Args: agent_function (AgentFunction): The agent function to register.
        """
        print("--deubg Agent function in ProjectCreationAgent-----",agent_function.name)
        self.action_map[action_name] = {
            "name": agent_function.name,
            "function": agent_function.function.__get__(self.project_service, ProjectService)
        }


    def action_functions(self):
        self.register_action_functions(action_name="create_project", agent_function=QNA_CHAT_PREFILL_PROJECT)
        self.register_action_functions(action_name="tango_assist_project", agent_function=TANGO_ASSIST_PROJECT)
        self.register_action_functions(action_name="update_project_canvas", agent_function=UPDATE_PROJECT_CANVAS)
        self.register_action_functions(action_name="fetch_scope_driveintegration", agent_function=CREATE_PROJECT_SCOPE)

    
    


