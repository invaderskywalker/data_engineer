from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_services.agents.functions.spend.spend import SPEND_CANCEL, SPEND_FUNC
from src.trmeric_services.agents.functions.spend.edit_spend import SPEND_EDIT
from src.trmeric_database.dao import TangoDao

class SpendAgent(BaseAgent):
    name = "spend_agent"
    description = """
        The spend agent is to be used when a user wishes to evaluate their spend 
        and receive detailed insights on their spend and where to save money.
    """
    functions = [SPEND_FUNC]  # Initialize functions in the constructor
    
    def __init__(self, log_info=None):
        super().__init__(log_info)  # Call the parent constructor first


    def refresh_functions(self, sessionID):
        states = TangoDao.fetchTangoStatesForSessionId(sessionID)
        for state in states:
            if state['key'] == 'SPEND_EVALUATION_FINISHED':
                # Avoid duplicating functions
                # if SPEND_ROADMAP not in self.functions:
                #     self.functions.append(SPEND_ROADMAP)
                if SPEND_EDIT not in self.functions:
                    self.functions.append(SPEND_EDIT)
        return self
    
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        data = self.fetch_data_for_blueprint_creation()
        return self._create_next_step(data, steps_executed_already, agents_prompt, conv)
    
    def fetch_data_for_blueprint_creation(self):
        return """
            You are an agent which will understand the user request and execute the tasks.
        """