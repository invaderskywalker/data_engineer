from src.services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.services.tango.functions.Types import ApiMetadata


class TangoIntegration:
    """
    For each integration, we have a set of IDs that are required to run the functions. This class will store the IDs for each integration.
    
    It will also explain the context behind the formatting of the IDs and how to use them along with any special instructions.
    """
    def __init__(self, name: str, functions: list, userID: int, tenantID: int, metadata: ApiMetadata, enabled = False):
        self.name = name
        self.functions = functions
        self.enabled = enabled
        self.userID = userID
        self.tenantID = tenantID
        self.integrationData = []
        self.api = None
        
    def addIntegrationData(self, data: TangoIntegrationData):
        """
        Adds integration data to the integration.
        """
        self.integrationData.append(data)
        
    def initializeIntegration(self):
        """
        Initializes the integration with all the relevant informatioon and data.
        """
        
    def formatIntegration(self):
        """
        Returns a string representation of the integration that can be shown to the model.
        """
        description = f"Another integration that you can use is the {self.name} integration. This integration has the following functions that you can use:"
        for function in self.functions:
            description += f"\n\n{function.format_function()}"
        description += f"Here are the IDs and their corresponding information that you can use to access the {self.name} integration. The description of the data is as follows:"
        for data in self.integrationData:
            try:
                if data.data:
                    description += f"\n\n{data.description}\n{data.data.formatData()}"
            except:
                description += f"\n\n{data.description}\n{str(data.data)}"
        return description
    
    