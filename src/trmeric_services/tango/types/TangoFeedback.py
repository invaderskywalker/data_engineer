from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question

class ReturnQuestion:
    def __init__(self, question:str):
        self.question = ask_clarifying_question(question)
        
class TangoFeedback:
    '''
    This class will have three items. The first will be the value of the class. The second will be the feedback provided by the user and the third is user confirmation.
    '''
    
    def __init__(self, name:str, value: str = None, feedback: bool = False, feedback_val:str = None, confirmation: bool = False):
        self.name = name
        self.value = value
        self.feedback = feedback
        self.feedback_val = feedback_val
        self.confirmation = confirmation
        
    def handle(self):
        print(f"Handling feedback for {self.name}")
        if self.feedback_val: self.confirmation = False
        if self.confirmation:
            return True
        elif not self.feedback:
            return ReturnQuestion(f"Here's what I'm thinking for {self.name}: {self.value}. Do you have any feedback or would you like for me to proceed?")
        elif self.feedback:
            self.value = self.feedback_val
            return ReturnQuestion(f"Thanks for the help. Here's an updated version for {self.name}: {self.value}. Do you have any further feedback or would you like for me to proceed?")
            