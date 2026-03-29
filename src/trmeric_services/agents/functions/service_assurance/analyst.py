from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction, AgentReturnTypes
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao, TangoDao
import datetime
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data
from src.trmeric_services.agents.precache import ServiceAssurancePrecache
from src.trmeric_services.agents.prompts.agents import create_high_level_analysis_prompt
from src.trmeric_services.tango.types.TangoYield import TangoYield
import time
    
def service_assurance_analyst(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    project_ids=[],
    sessionID=None,
    logInfo=None,
    **kwargs
):
    print("service_assurance_analyst",  project_ids)
    projects_to_process = []
    if len(project_ids) > 0:
        projects_to_process = project_ids
    else:
        projects_to_process = eligibleProjects
        
    print("service_assurance_analyst 2",  projects_to_process)
    service_assurnace_precache = ServiceAssurancePrecache(tenant_id=tenantID, user_id=userID, init=False)
     
    socketio.emit("spend_agent", 
        {
            "event": "show_timeline",
        }, 
        room=client_id
    )
    retrieved_data = ""  
    socketio.emit("spend_agent", 
        {
            "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": False}
        }, 
        room=client_id
    ) 
    for project_id in projects_to_process:
        project_details = ProjectsDao.fetch_project_details_for_service_assurance(
            project_id=project_id
        )
        project_statuses = ProjectsDao.fetchProjectStatuses(project_id)
        project_formatted_data = service_assurnace_precache.projectFormattedData(project_id, project_details, project_statuses)
        
        data = TangoDao.fetchLatestTangoStateForProjectForTenant(tenant_id=tenantID, project_id=project_id)
        retrieved_data += f"""
            --------  --------
            For this project data and project statuses and this projects integration
            <project_data_with_status>
            {project_formatted_data}
            <project_data_with_status>
            
            <service_assurnace_level1_analysis>
            {data}
            <service_assurnace_level1_analysis>
            --------  --------
        """
        
    socketio.emit("spend_agent", 
        {
            "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": True}
        }, 
        room=client_id
    ) 
    
    socketio.emit("spend_agent", 
        {
            "event": "timeline", "data": {"text": "Analysing", "key": "Analysing", "is_completed": False}
        }, 
        room=client_id
    )
    
    prompt = create_high_level_analysis_prompt(data=retrieved_data, user_query=last_user_message)
    print("debug -- prompt", prompt.formatAsString())
    analysis = ""
    for chunk in llm.run(prompt, model_opts , 'agent::service_assurance::analyst', logInfo):
        analysis += chunk
        yield chunk
    
    socketio.emit("spend_agent", 
        {
            "event": "timeline", "data": {"text": "Analysing", "key": "Analysing", "is_completed": True}
        }, 
        room=client_id
    )
    
    
    time.sleep(1)
    
    socketio.emit("spend_agent", 
        {
            "event": "stop_show_timeline",
        }, 
        room=client_id
    )
    
    return "✅ Analysis Done by Service assurance analyst"
    
    # return TangoYield(return_info="", yield_info=f"""
    #     Analysis Done by Service Assurance Agent Analyst: {analysis}
    # """)
    
    # return f"""
    #     For data: {retrieved_data}
    #     Analysis Done: {analysis}
    # """
        
            
    
        
    

RETURN_DESCRIPTION = """
    A detailed list of projects with updates, milestone statuses, and identified risks or successes. 
    Supplemental insights from the knowledge layer and integrations, if applicable.
"""

ARGUMENTS = [
    {
        "name": "project_ids",
        "type": "int[]",
        "required": 'true',
        "description": """Project Ids that user wants analysis on, either all projects or specific project""",
    },
]

SERVICE_ASSURANCE_ANALYST = AgentFunction(
    name="service_assurance_analyst",
    description="""
        This function proactively analyzes a user's projects to identify possible risks, 
        failures, and successes. It checks the project's latest updates, milestones, and 
        associated risks and mitigation strategies and all integration data. 
        
        If a project is outdated (status not updated in 
        the last 7 days) or has missed milestones, 
        the user should be informed.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=service_assurance_analyst,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)
