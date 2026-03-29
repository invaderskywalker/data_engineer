from src.trmeric_api.types import TabularData


class TangoIntegrationData:
    """
    For each integration, we have a set of data points that are required to run the functions. This includes any IDs that the agent needs to query the database / API for the specific user. This class will store those data points along with descriptions of the data for the model to better understand it. 
    """
    def __init__(self, data: TabularData, description: str):
        self.data = data
        self.description = description
        

