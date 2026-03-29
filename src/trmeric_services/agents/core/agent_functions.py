
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes

class AgentFunction:
    def __init__(
        self,
        name: str,
        description: str,
        args: list,
        return_description: str,
        function: callable,
        type_of_func=AgentFnTypes.DATA_GETTER.name, ## it can also be action-taker
        return_type = AgentReturnTypes.RETURN.name
    ):
        self.name = name
        self.description = description
        self.args = args
        self.return_description = return_description
        self.function = function 
        self.type_of_func = type_of_func       
        self.return_type = return_type
        
    def format_function(self):
        """
        Returns a string representation of the function that can be shown to the model
        """
        new_line = "\n\n"
        
        if self.args:
            formatted_args = ", ".join([f"{arg['name']}: {arg['type']}" for arg in self.args])
            formatted_args_doc = new_line.join(
                [
                    f" - {arg['name']}: {arg['description']}. "
                    f"{'This parameter is ' + ('necessary' if arg.get('required') == 'true' else 'not necessary') if 'required' in arg else 'not necessary'}"
                    f"{' The options to choose from for this parameter are: ' + ', '.join(arg['options']) if 'options' in arg else ''}"
                    f"{('Use placeholder like <previous_step_agent.previous_step_function_output>' if arg.get('use_placeholder') == 'true' else '') if 'use_placeholder' in arg else ''}"
                    for arg in self.args
                ]
            )
            
        else:
            formatted_args_doc = "No args"
            formatted_args = ""
        
        formatted = f'''
            def {self.name}({formatted_args}):
            """{self.description}

            Understand the arguments format and stick to it when generating blueprint
            Args:
                {formatted_args_doc}

            Returns:
                {self.return_description}
                
            """
        '''
        return formatted
    
    
    def set_agent_function(self):
        """
        Sets the agent function details.
        """
        return self
