from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
import datetime
# from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data

    
def service_assurance_insight(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    project_ids=None,
    capture_projects_info=False,
    capture_portfolio_knowledge=False,
    summary_analysis_of_which_jira_projects=False,
    **kwargs
):
    print("service_assurance_insight --- ", capture_projects_info, summary_analysis_of_which_jira_projects,capture_portfolio_knowledge )
    capture_portfolio_knowledge = False
    eligible_projects = ProjectsDao.FetchAvailableProject(tenant_id=tenantID, user_id=userID)
    final_list = []
    if (project_ids==None or project_ids == []):
        final_list = eligible_projects
    else :
        for p in project_ids:
            final_list.append(p)
            
    print("service_assurance_insight eligible projects ", final_list)
    
    output = ProjectsDao.fetchProjectsWithLastUpdates(project_ids=eligible_projects, tenant_id=tenantID)
    
    currentDate = datetime.datetime.now().date().isoformat()
    data = ""
    if capture_portfolio_knowledge:
        knowledgeData = KnowledgeDao.FetchProjectPortfolioKnowledge(tenant_id=tenantID, portfolio_id=None)
        data += f"""
            Use the learning from this knowledge layer. 
            Do not use it to create response.
            Use it to create analysis and thought process.
            
            The knowledge layer provides organization-wide trends and insights that 
            could help identify patterns across projects. 
            Use it as a supplemental source of information 
            for identifying risks, failures, and potential successes within the current context.
            -----------------
            Knowledge layer data:
            <knowledge_layer>
                {knowledgeData}
            <knowledge_layer>
            ------------------
        """
    # if summary_analysis_of_which_jira_projects:
    #     if (len(summary_analysis_of_which_jira_projects) > 0):
    #         response = get_jira_data(tenantID, userID, summary_analysis_of_which_jira_projects=summary_analysis_of_which_jira_projects)
    #         data += response
    #     # else:
    # if capture_projects_info:
    data += f"""
        Here is the list of project id, title, and latest updates 
        made with date and their milestones and also risk and mitigation strategies: 
        {output}.
    """
    
    return data
        
    

RETURN_DESCRIPTION = """
A detailed list of projects with updates, milestone statuses, and identified risks or successes. 
        Supplemental insights from the knowledge layer and integrations, if applicable.
        """

ARGUMENTS = [
    {
        "name": "project_ids[]",
        "type": "int[]",
        "description": """
            Project Ids that user wants you to look into
        """,
    },
    {
        "name": "capture_projects_info",
        "type": "bool",
        "description": """
            
        """,
        "required": 'true'
    },
    {
        "name": "capture_portfolio_knowledge",
        "type": "bool",
        "description": """
            
        """,
        "required": 'true'
    },
    # {
    #     "name": "capture_portfolio_knowledge",
    #     "type": "bool",
    #     "description": """
    #         Embed 
    #         only when you should use the knowledge layer 
    #         to enhance insights only when user is asking 
    #         about portfolio trend, or trend across portfolio.
    #     """,
    #     "required": 'true'
    # },
    {
        "name": "summary_analysis_of_which_jira_projects",
        "type": "str[]",
        "description": "Very important: Look into the items mentioned keys_of_jira_project_names_for_summary and figure out the values if user wants you answer on integrations",
        "required": 'true'
    },
]

SERVICE_ASSURANCE_INSIGHT = AgentFunction(
    name="service_assurance_insight",
    description="""
        This function proactively analyzes a user's projects to identify possible risks, 
        failures, and successes. It checks the project's latest updates, milestones, and 
        associated risks and mitigation strategies. If a project is outdated (not updated in 
        the last 7 days) or has missed milestones, the user will be informed.

        While leveraging the knowledge layer, this function prioritizes identifying actionable 
        insights like risks and potential failures. The knowledge layer serves as a supplemental 
        source to provide context and identify broader trends but should not dominate the response.
        Focus on providing concrete insights from project-specific data and integrations.

        Use the integrations' knowledge, such as Jira project summaries, to further enhance the 
        analysis and provide comprehensive recommendations.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=service_assurance_insight,
)
