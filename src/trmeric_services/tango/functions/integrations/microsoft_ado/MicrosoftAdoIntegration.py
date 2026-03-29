from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_api.types.TabularData import TabularData
from src.trmeric_services.tango.functions.Types import ApiMetadata, TangoFunction
from src.trmeric_integrations.MicrosoftAdo.Api import AzureDevOpsAPI
from src.trmeric_services.tango.functions.integrations.microsoft_ado.GetADOData import GET_ADO_PROJECT_DATA


class MicrosoftAdoIntegration(TangoIntegration):
    """
    This is a class to represent the integration of ADO.
    """

    def __init__(self, userID: int, tenantID: int, metadata: ApiMetadata = None):
        super().__init__("ado", [GET_ADO_PROJECT_DATA], userID, tenantID, True)
        self.api = AzureDevOpsAPI(userID, tenantID, metadata)
        self.availableProjects = []
        
    def initializeIntegration(self):
        """
        Initializes the integration with ADO.
        """
        projects = self.api.get_all_projects()['value']
        description = "These are the IDs and names of the projects that the user has access to in Azure DevOps. Access only includes the ability to query the projects."
        
        if projects is not None:
            data = TabularData(['id', 'name'])
            for project in projects:
                data.addRow([project['id'], project['name']])
                self.availableProjects.append(project['id'])
            
            integrationData = TangoIntegrationData(data, description)
            self.addIntegrationData(integrationData)

