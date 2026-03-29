
from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_integrations.Jira.Api import JiraAPI
from src.trmeric_api.types.TabularData import TabularData
from src.trmeric_services.tango.functions.Types import ApiMetadata
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import list_jira_projects, get_jira_data
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
import traceback



class JiraIntegration(TangoIntegration):
    """
    This is a class to represent the integration of Jira.
    """

    def __init__(self, userID: int, tenantID: int, metadata: ApiMetadata):
        super().__init__("jira", [], userID, tenantID, True)
        try:
            self.api = JiraAPI(userID, tenantID, metadata)
        except Exception as e:
            print("error in initializing JiraAPI ", e)

    def initializeIntegration(self):
        """
        Initializes the integration with Jira.
        """
        appLogger.info({
            "function": "initializeIntegration_start",
        })
        try:
        
            integrations_with_projects = list_jira_projects(tenantID=self.tenantID, userID=self.userID)
            tabularData = TabularData(["trmeric_projects_to_jira_project_mappings"])
            tabularData.addRow([integrations_with_projects])
            integrationData = TangoIntegrationData(tabularData, "Trmeric Projects mapped with jira projects/initiative/epic")
            self.addIntegrationData(integrationData)
            
            appLogger.info({
                "function": "initializeIntegration_integrations_with_projects",
                "text": integrations_with_projects
            })
            try:
            
                summary_analysis_of_projects = TangoDao.fetchTangoIntegrationKeyAnalysisDataForTenant(tenant_id=self.tenantID)
                tabularData = TabularData(["keys_of_jira_project_names_for_summary"])
                tabularData.addRow([str(summary_analysis_of_projects)])
                integrationData = TangoIntegrationData(tabularData, 
                                                    """
                                                    We already have stored summarized analysis 
                                                    for sprints of these jira projects for this user.
                                                    **Very important** - use exact names from this list for the argument 
                                                    summary_analysis_of_which_jira_projects for the function get_jira_data
                                                    """)
                self.addIntegrationData(integrationData)
                
    
            except Exception as e:
                appLogger.error({
                    "function": "initializeIntegration_error",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }) 
                
            appLogger.info({
                "function": "initializeIntegration_summary_analysis_of_projects",
                # "text": str(summary_analysis_of_projects)
            }) 
            
        except Exception as e:
            appLogger.error({
                "function": "initializeIntegration_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        appLogger.info({
            "function": "initializeIntegration_end",
        })
        
        
        # projects = self.api.retrieveAllProjects()

        # description = "These are the IDs and names of the projects that the user has access to in Jira. Access only includes the ability to query the projects."
  
        # integrationData = TangoIntegrationData(projects, description)
        # self.addIntegrationData(integrationData)
        
    def initializeIntegrationAgent(self):
        projects = self.api.retrieveAllProjects()
        description = "These are the IDs and names of the projects that the user has access to in Jira. Access only includes the ability to query the projects."
        integrationData = TangoIntegrationData(projects, description)
        self.addIntegrationData(integrationData)
