from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.api.logging.LLMLogger import log_llm_request
from src.api.logging.AppLogger import appLogger

class LLMClient:
    def __init__(self, model_name, user_id=None, tenant_id=None):
        self.model_name = model_name
        self.user_id = user_id
        self.tenant_id = tenant_id

    def run(self, chat: ChatCompletion, options: ModelOptions, function_name=None, logInDb=None) -> str:
        """
        Base implementation with logging support. 
        Should be overridden by subclasses but called via super().
        """
        # Display a large warning if function_name is not provided
        if function_name is None or function_name == "":
            warning_message = """
            #################################################################
            #                          WARNING                               #
            #  LLM run function called without a function name parameter!    #
            #  This will affect logging and monitoring capabilities.         #
            #  Please provide a descriptive function name for all LLM calls. #
            #################################################################
            """
            appLogger.warning(warning_message)
            print(warning_message)
            function_name = "unspecified_function"
            
        # Prioritize instance user_id and tenant_id over logInDb values
        user_id = self.user_id
        tenant_id = self.tenant_id
        
        # Only use logInDb values if instance values are None
        if user_id is None and logInDb:
            user_id = logInDb.get("user_id")
        if tenant_id is None and logInDb:
            tenant_id = logInDb.get("tenant_id")
        
        # Format the chat for logging
        formatted_chat = chat.format()
        system_prompt = formatted_chat.get("system", "")
        user_prompt = formatted_chat.get("user", "")
        combined_prompt = f"System: {system_prompt}\nUser: {user_prompt}"
        
        # Log the request
        timer_id = log_llm_request(
            self.model_name, 
            function_name,
            combined_prompt,
            options,
            user_id,
            tenant_id
        )
        
        # Subclasses should call this method and handle the timer_id
        return timer_id

    def tokenize(self, chat: ChatCompletion, options: ModelOptions) -> list:
        pass
