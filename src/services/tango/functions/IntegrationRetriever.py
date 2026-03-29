

from src.trmeric_services.tango.functions.Types import TrmericIntegration
from src.trmeric_services.tango.functions.integrations.general import GeneralIntegration
from src.trmeric_services.tango.functions.integrations.jira import JiraIntegration
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_services.tango.functions.integrations.slack.SlackIntegration import SlackIntegration
from src.trmeric_services.tango.functions.integrations.office.OfficeIntegration import OfficeIntegration
from src.trmeric_services.tango.functions.integrations.drive.DriveIntegration import DriveIntegration


class IntegrationRetriever:
    
    def __init__(self, integrations: list[TangoIntegration]):
        self.integrations = integrations

    def getIntegration(self, name: str) -> TangoIntegration:
        """
        Gets the integration with the given name.
        """
        if name == "jira":
            return self.getJiraIntegration()
        elif name == "trmeric":
            return self.getTrmericIntegration()
        elif name == "general":
            return self.getGeneralIntegration()
        elif name == "ado":
            return self.getADOIntegration()
        elif name == 'slack':
            return self.getSlackIntegration()
        elif name == 'office':
            return self.getOfficeIntegration()
        elif name == 'drive':
            return self.getDriveIntegration()
        
    def getDriveIntegration(self) -> DriveIntegration:
        """
        Gets the Drive integration.
        """
        for integration in self.integrations:
            if integration.name == "drive":
                return integration
    
    def getJiraIntegration(self) -> JiraIntegration:
        """
        Gets the Jira integration.
        """
        for integration in self.integrations:
            if integration.name == "jira":
                return integration
    
    def getSlackIntegration(self) -> SlackIntegration:
        """
        Gets the Slack integration.
        """
        for integration in self.integrations:
            if integration.name == "slack":
                return integration
        
    def getOfficeIntegration(self) -> OfficeIntegration:
        """
        Gets the Office integration.
        """
        for integration in self.integrations:
            if integration.name == "office":
                return integration
            
    def getTrmericIntegration(self) -> TrmericIntegration:
        """
        Gets the Trmeric integration.
        """
        for integration in self.integrations:
            if integration.name == "trmeric":
                return integration
    
    def getGeneralIntegration(self) -> GeneralIntegration:
        """
        Gets the General integration.
        """
        for integration in self.integrations:
            if integration.name == "general":
                return integration
            
    def getADOIntegration(self) -> JiraIntegration:
        """
        Gets the ADO integration.
        """
        for integration in self.integrations:
            if integration.name == "ado":
                return integration
    