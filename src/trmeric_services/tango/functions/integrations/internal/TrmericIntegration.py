from src.trmeric_api.types.TabularData import TabularData
from src.trmeric_database.Database import TrmericDatabase
from src.trmeric_services.tango.functions.integrations.internal.ActionsFunction import VIEW_ACTIONS
from src.trmeric_services.tango.functions.integrations.internal.GetGeneralProjectsFunction import VIEW_PROJECTS
from src.trmeric_services.tango.functions.integrations.internal.IdeaPadFunction import VIEW_IDEAS
from src.trmeric_services.tango.functions.integrations.internal.RoadmapsFunction import VIEW_ROADMAPS
from src.trmeric_services.tango.functions.integrations.internal.GetPortfoliosFunction import VIEW_PORTFOLIOS
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetPortfoliosSnapshot import VIEW_PORTFOLIOS_SNAPSHOT
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewPerformanceSnapshot import VIEW_PERFORMANCE_SNAPSHOT_LAST_QUARTER

from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewValueSnapshot import VIEW_VALUE_SNAPSHOT_LAST_QUARTER

from src.trmeric_services.tango.functions.integrations.internal.prompts.GetOrPlanITTechStrategy import GET_OR_PLAN_IT_TECH_STRATEGY
from src.trmeric_services.tango.functions.integrations.internal.prompts.InitializeQueries import availablePortfoliosQuery, eligibleProjectsQuery, projectsPerPortfolioQuery
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData

from src.trmeric_database.Database import db_instance
from src.trmeric_services.tango.functions.integrations.internal.CompareProjectsFunction import (
    COMPARE_BY_PROJECTS)
from src.trmeric_services.tango.functions.integrations.internal.OffersFunction import VIEW_OFFERS
from src.trmeric_services.tango.functions.integrations.internal.ProjectRisksFunction import VIEW_PROJECT_RISKS
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetRoadmapItems import VIEW_ROADMAP_ITEMS
from src.trmeric_services.tango.functions.integrations.internal.AutonomousCreateJiraIssues import AUTONOMOUS_CREATE_JIRA_ISSUES
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import GET_JIRA_DATA, LIST_JIRA_PROJECT_MAPPINGS, LIST_ADO_PROJECT_MAPPINGS, GET_ADO_DATA,GET_SMART_SHEET_DATA, GET_GITHUB_DATA
from src.trmeric_services.tango.functions.integrations.internal.GetFileDetailsFunction import GET_FILE_DETAILS
# from src.trmeric_services.tango.functions.integrations.internal.OnboardingFunction import ONBOARD_PROCESS
from src.trmeric_services.tango.functions.integrations.internal.features import VIEW_RETRO_PROJECTS, VIEW_VALUE_REALIZATIONS

from src.trmeric_services.tango.functions.integrations.internal.providers import FETCH_PROVIDER_DATA
from src.trmeric_services.tango.functions.integrations.internal.resource import FETCH_CAPACITY_DATA
from src.trmeric_services.tango.functions.integrations.internal.ProgramsFunction import VIEW_PROGRAMS

from src.trmeric_database.dao.file import FileDao
from src.trmeric_database.dao import ProjectsDao, TenantDao

class TrmericIntegration(TangoIntegration):
    """
    This is the class for the fundamental Trmeric integration, of which all users have access to.

    This essentially allows the user to view projects, roadmaps, actions, etc. within the Trmeric database.
    """

    def __init__(self, userID: int, tenantID: int, metadata: dict,sessionID: str):

        functions = [
            VIEW_PROJECTS,
            VIEW_ACTIONS,
            # VIEW_RETRO_PROJECTS,
            # VIEW_VALUE_REALIZATIONS,
            VIEW_PORTFOLIOS,
            VIEW_PORTFOLIOS_SNAPSHOT,
            VIEW_PROGRAMS,
            
            VIEW_PERFORMANCE_SNAPSHOT_LAST_QUARTER,
            VIEW_VALUE_SNAPSHOT_LAST_QUARTER,
            
            
            VIEW_ROADMAPS,
            VIEW_IDEAS,
            # COMPARE_BY_PROJECTS,
            VIEW_OFFERS,
            VIEW_PROJECT_RISKS,
            # AUTONOMOUS_CREATE_JIRA_ISSUES,
            GET_FILE_DETAILS,
            # ONBOARD_PROCESS,
            GET_JIRA_DATA,
            GET_GITHUB_DATA,
            GET_SMART_SHEET_DATA,
            LIST_JIRA_PROJECT_MAPPINGS,
            LIST_ADO_PROJECT_MAPPINGS,
            GET_ADO_DATA,
            GET_OR_PLAN_IT_TECH_STRATEGY,
            # VIEW_ROADMAP_ITEMS,
            
            FETCH_CAPACITY_DATA
        ]
        
        if TenantDao.fetchTenantType(tenant_id=tenantID) == "provider":
            functions = [
                VIEW_PROJECTS,
                VIEW_ACTIONS,

                VIEW_PORTFOLIOS,
                VIEW_PORTFOLIOS_SNAPSHOT,
                
                VIEW_PERFORMANCE_SNAPSHOT_LAST_QUARTER,
                VIEW_VALUE_SNAPSHOT_LAST_QUARTER,
                
                
                VIEW_ROADMAPS,
                
                # VIEW_OFFERS,
                VIEW_PROJECT_RISKS,
          
                GET_FILE_DETAILS,
            
                GET_JIRA_DATA,
                GET_GITHUB_DATA,
                GET_SMART_SHEET_DATA,
                LIST_JIRA_PROJECT_MAPPINGS,
                LIST_ADO_PROJECT_MAPPINGS,
                GET_ADO_DATA,
                
                
                ## WILL ADD A FUNCTION FOR PROVIDER DATA FETCHING
                FETCH_PROVIDER_DATA
              
            ]

        self.sessionID = sessionID
        self.fileMapping = {}
        super().__init__("trmeric", functions, userID, tenantID, True)
        self.eligibleProjects = []

    def initializeIntegration(self):
        """
        Initializes the integration with all the relevant informatioon and data.
        """
        accessableProjects = self.retrieveEligibleProjects().getColumn("id")
        # print("debug ----initializeIntegration-- ", accessableProjects)
        portfolios = self.retrieveAvailablePortfolios()
        for portfolio in portfolios.getColumn("portfolio_id"):
            self.retrieveProjectsPerPortfolio(portfolio, accessableProjects)
            
        print("debug ----initializeIntegration222-- ", accessableProjects)
        self.fetchProvidersForProjects(accessableProjects)
        try:
            self.getProjectAndNames(accessableProjects)
        except Exception as e:
            print("error in getProjectAndNames ", e)
        
        self.fetchCurrentSessionUploadedFiles()
        
    def getProjectAndNames(self,accessableProjects):
        # print("debug ----getProjectAndNames-- ", accessableProjects)
        eligible_project_id_and_names = ProjectsDao.fetchProjectsIdAndTItle(project_ids=accessableProjects)
        context_string = f"""
            These are the projects that the user has access to:
            {eligible_project_id_and_names}
        """
        description = "These are the projects and their names"
        integrationData = TangoIntegrationData(context_string, description)
        self.addIntegrationData(integrationData)
        
    def fetchProvidersForProjects(self, project_ids):
        project_ids_str = f"({', '.join(map(str, project_ids))})" 
        query = f"""
            SELECT wp.id as project_id, wp.title as project_name, tp.id as provider_id, tp.company_name FROM public.workflow_projectprovider as wpp
            join tenant_provider as tp on tp.id = wpp.provider_id
            left outer join workflow_project as wp on wp.id=wpp.project_id
            where wp.id in {project_ids_str}
        """
        response = db_instance.retrieveSQLQuery(query)
        description = "These are the providers within the Trmeric database that the user is using to manage projects."
        integrationData = TangoIntegrationData(response, description)
        self.addIntegrationData(integrationData)

    def fetchCurrentSessionUploadedFiles(self, file_type = 'TANGO'):
        """
            Fetch files uploaded in the current session and store a mapping of s3_key to original filename.
        """
        response = FileDao.s3ToOriginalFileMapping(
            sessionID = self.sessionID,
            userID = self.userID,
            file_type = file_type
        )
        # print("--debug sessionID",self.sessionID,"\n")
        # print("--debug currentSession uploaded filemapping",response)

        # self.fileMapping = {v:k for k,v in response.items()}
        description = """In the current Tango chat session, user has uploaded documents. 
            You are provided with the mapping of the documents' filename with their respective s3_keys 
            in the fileMapping. Using s3_key we can fetch the file content of the uploaded document.
        """
        integrationData = TangoIntegrationData(response, description)
        self.addIntegrationData(integrationData)

        # print("--debug uploadfile integrationData", integrationData)
        return response  

    def retrieveAvailablePortfolios(self):
        """
        Retrieves the available portfolios for the user.
        """
        response = db_instance.retrieveSQLQuery(
            availablePortfoliosQuery(self.tenantID))
        description = "These are the portfolios within the Trmeric database that the user has access to along with the IDs to query them."
        integrationData = TangoIntegrationData(response, description)
        self.addIntegrationData(integrationData)
        return response

    def retrieveProjectsPerPortfolio(self, portfolioID, eligibleProjectIDs: list):
        response = db_instance.retrieveSQLQuery(
            projectsPerPortfolioQuery(portfolioID))
        # filter out the projects that the user does not have access to
        response.filterColumns(
            "project_id", lambda project_id: project_id in eligibleProjectIDs)
        description = "These are the projects within the Trmeric database that the user has access to along with the IDs to query them."
        integrationData = TangoIntegrationData(response, description)
        self.addIntegrationData(integrationData)

    def retrieveEligibleProjects(self) -> TabularData:
        """
        Retrieves the eligible projects for the user.
        """
        response = db_instance.retrieveSQLQuery(
            eligibleProjectsQuery(self.userID, self.tenantID))
        self.eligibleProjects = response.getColumn("id")
        return response
