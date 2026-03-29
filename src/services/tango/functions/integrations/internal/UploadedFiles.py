from src.api.types.TabularData import TabularData
from src.database.Database import TrmericDatabase
from src.trmeric_services.tango.functions.integrations.internal.ActionsFunction import VIEW_ACTIONS
from src.trmeric_services.tango.functions.integrations.internal.GetGeneralProjectsFunction import VIEW_PROJECTS
from src.trmeric_services.tango.functions.integrations.internal.IdeaPadFunction import VIEW_IDEAS
from src.trmeric_services.tango.functions.integrations.internal.RoadmapsFunction import VIEW_ROADMAPS
from src.trmeric_services.tango.functions.integrations.internal.GetPortfoliosFunction import VIEW_PORTFOLIOS
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetPortfoliosSnapshot import VIEW_PORTFOLIOS_SNAPSHOT
from src.trmeric_services.tango.functions.integrations.internal.prompts.InitializeQueries import availablePortfoliosQuery, eligibleProjectsQuery, projectsPerPortfolioQuery
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData

from src.database.Database import db_instance
from src.trmeric_services.tango.functions.integrations.internal.CompareProjectsFunction import (
    COMPARE_BY_PROJECTS)
from src.trmeric_services.tango.functions.integrations.internal.OffersFunction import VIEW_OFFERS
from src.trmeric_services.tango.functions.integrations.internal.ProjectRisksFunction import VIEW_PROJECT_RISKS
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetRoadmapItems import VIEW_ROADMAP_ITEMS
from src.trmeric_services.tango.functions.integrations.internal.AutonomousCreateJiraIssues import AUTONOMOUS_CREATE_JIRA_ISSUES
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import GET_JIRA_DATA, LIST_JIRA_PROJECT_MAPPINGS, LIST_ADO_PROJECT_MAPPINGS, GET_ADO_DATA,GET_SMART_SHEET_DATA, GET_GITHUB_DATA
from src.trmeric_services.tango.functions.integrations.internal.GetFileDetailsFunction import GET_FILE_DETAILS
# from src.trmeric_services.tango.functions.integrations.internal.OnboardingFunction import ONBOARD_PROCESS

from src.database.dao.file import FileDao
import time

class UploadedFiles(TangoIntegration):
    """
    This is the class for the fundamental Trmeric integration, of which all users have access to.

    This essentially allows the user to view projects, roadmaps, actions, etc. within the Trmeric database.
    """

    def __init__(self, userID: int, tenantID: int, metadata: dict,sessionID: str = None):

        functions = [
            
        ]

        self.sessionID = sessionID
        self.fileMapping = {}
        super().__init__("uploaded_files", functions, userID, tenantID, True)
        self.eligibleProjects = []

    def fetchCurrentSessionUploadedFiles(self, file_type = 'TANGO', retries = 0):
        """
            Fetch files uploaded in the current session and store a mapping of s3_key to original filename.
            If we get an empty dict, retry after 1 second, up to the specified number of retries.
        """
        print("--debug fetchCurrentSessionUploadedFiles session_id: ", self.sessionID)
        response = FileDao.s3ToOriginalFileMapping(
            sessionID = self.sessionID,
            userID = self.userID,
            file_type = file_type
        )
        
        # If response is empty and we have retries left, wait and try again
        max_retries = 3 if retries < 0 else retries
        current_retry = 0
        
        while not response and current_retry <= max_retries:
            time.sleep(3)  # Wait 1 second before retrying
            current_retry += 1
            print(f"Retry {current_retry}/{max_retries} for fetching uploaded files")
            
            response = FileDao.s3ToOriginalFileMapping(
            sessionID = self.sessionID,
            userID = self.userID,
            file_type = file_type
            )
        
        description = """In the current Tango chat session, user has uploaded documents. 
            You are provided with the mapping of the documents' filename with their respective s3_keys 
            in the fileMapping. Using s3_key we can fetch the file content of the uploaded document.
        """
        integrationData = TangoIntegrationData(response, description)
        self.addIntegrationData(integrationData)
        return response  