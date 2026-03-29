class ModelOutputFormat:
    """
    This model is used to define an output format for the model.
    
    In a lot of our use-cases, we prompt the model to provide its response in a very modular format.
    Instead of creating separate parsers for each of them. It's best that we create this abstraction
    to handle all of them. 
    """
    def __init__(self, format: str, cot: bool, outputs: list = None):
        """
        Initializes the ModelOutputFormat object.
        
        Args:
            format (str): The format of the output can be one of the following options:
                - code: For this format, the model will return a coding style output.
                - text: For this model, the model will return text and text only.
                - json: For this model, the model will return a json output.
            cot (bool): Whether the output utilizes chain of thought or not
            outputs (list): A list with objects that define the output format in json format. Each object should 
            contain the following fields: name, type, and description.
        """
        self.format = format
        self.cot = self.cot
        self.outputs = outputs
    
    def displayModelFormatInstructions(self):
        pass
      
    def parseModelOutput(self, model_output: str):
        pass
        
