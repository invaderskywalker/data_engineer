from src.services.tango.functions.integrations.general.GeneralIntegration import GeneralIntegration
from src.services.tango.functions.integrations.internal.TrmericIntegration import TrmericIntegration
from src.services.tango.functions.integrations.jira.JiraIntegration import JiraIntegration
from src.services.tango.functions.integrations.office.OfficeIntegration import OfficeIntegration
from src.services.tango.functions.integrations.drive.DriveIntegration import DriveIntegration
from src.services.tango.functions.integrations.internal.UploadedFiles import UploadedFiles
from src.services.tango.types.TangoIntegration import TangoIntegration
from src.services.tango.functions.integrations.microsoft_ado.MicrosoftAdoIntegration import MicrosoftAdoIntegration
from src.api.types.TabularData import TabularData
import traceback
from src.services.tango.functions.integrations.slack.SlackIntegration import (
    SlackIntegration)




IntegrationMap = {
    'trmeric': TrmericIntegration,
    'general': GeneralIntegration,
    'jira': JiraIntegration,
    'ado_off': MicrosoftAdoIntegration,
    'slack': SlackIntegration,
    'office': OfficeIntegration,
    'drive': DriveIntegration
}

def createIntegrations(availableIntegrations: TabularData, userId: str, tenantId: str,sessionId: str) -> list[TangoIntegration]:
    integrations = []
    # appLogger.info({
    #     "function": "createIntegrations",
    #     "availableIntegrations": str(availableIntegrations.getRows())
    # })
    for integration in availableIntegrations.getRows():
        if integration['integration_type'] in IntegrationMap:
            try:
                selected = IntegrationMap[integration['integration_type']](userId, tenantId, integration['metadata'])
                selected.initializeIntegration()
                integrations.append(selected)
            except Exception as e:
                print('failed: ' + integration['integration_type'])
                traceback.print_exc()
                print(f"Error message: {e}")
                
    trmericIntegration = TrmericIntegration(userId, tenantId, {}, sessionId)
    trmericIntegration.initializeIntegration()
    integrations.append(trmericIntegration)
    generalIntegration = GeneralIntegration(userId, tenantId, {})
    generalIntegration.initializeIntegration()
    integrations.append(generalIntegration)
    
    return integrations




def createIntegrationsAgent(availableIntegrations: TabularData, userId: str, tenantId: str, selectOnlyFew = ['all'], forceJiraOld=False) -> list[TangoIntegration]:
    integrations = []
    for integration in availableIntegrations.getRows():
        if integration['integration_type'] in IntegrationMap:
            try:
                selected = IntegrationMap[integration['integration_type']](userId, tenantId, integration['metadata'])
                if integration['integration_type'] == 'jira' and not forceJiraOld:
                    selected.initializeIntegrationAgent()
                else:
                    selected.initializeIntegration()
                if 'all' in selectOnlyFew or integration['integration_type'] in selectOnlyFew:
                    integrations.append(selected)
            except Exception as e:
                print('failed: ' + integration['integration_type'])
                traceback.print_exc()
                print(f"Error message: {e}")
    if 'all' in selectOnlyFew or 'uploaded' in selectOnlyFew:          
        trmericIntegration = UploadedFiles(userId, tenantId, {})
        integrations.append(trmericIntegration)
                
    return integrations