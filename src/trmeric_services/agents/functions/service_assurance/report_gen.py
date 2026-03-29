from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import create_combined_update_prompt, create_report_prompt
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import ProjectsDao, TangoDao
import json
import traceback
import time
from src.trmeric_api.logging.AppLogger import appLogger



def format_response(output):
    del output["user_satisfied_for_update"]
    del output["your_thought"]
    return output


def create_service_assurance_report(
    tenantID: int,
    userID: int,
    # eligibleProjects: list[int],
    llm= None,
    model_opts=None,
    logInfo=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    # project_id=None,
    project_name=None,
    sessionID=None,
    **kwargs
    
):
    data = kwargs.get("data", {})
    project_id = data.get("project_id", None)
    try:
        sender = kwargs.get("step_sender")
        print("debug -- create_service_assurance_report ", tenantID, userID, project_id)

        project_data = ProjectsDao.fetch_project_details_for_service_assurance(project_id)
        alreadyGeneratedInsightData = TangoDao.fetchTangoStatesForUserForProjectStatusUpdate(user_id=userID, tenant_id=tenantID)
        project_manager_info = ProjectsDao.FetchProjectManagerInfoForProjects(_project_ids=[project_id])
        project_manager_name = ""
        if project_manager_info:
            if len(project_manager_info) > 0:
                project_manager_name = project_manager_info[0]["first_name"] + " " + project_manager_info[0]["last_name"]
        
        requiredData = None
        for item in alreadyGeneratedInsightData:
            # print("----")
            # print(item)
            # print()
            if item.get("project_id") == project_id or item.get("project_id") == str(project_id):
                requiredData = item
                break
                
        # return
        if requiredData:
            requiredData = requiredData["agent_insight"]
            
        # print("debug --- create_service_assurance_report-", project_data, )
        
        prompt = create_report_prompt(project_info=project_data, alreadyGeneratedInsightData=requiredData)
        # print(prompt.formatAsString())
        # return
        

    
        response = llm.run(prompt, model_opts , 'agent::service_assurance::create_service_assurance_report', logInfo,socketio=socketio, client_id=client_id)
        print("service_assurance::create_service_assurance_report 1 ========", response)
        response = extract_json_after_llm(response,step_sender=sender)
        response["projectDetails"]["projectManager"] = project_manager_name
        response["project_id"] =  project_id
        current_project_status = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
        response["status"] = current_project_status
        
        
        socketio.emit(
            "service_assurance_agent", 
            {
                "event": "create_service_assurance_report",
                "project_id": project_id,
                "data": response
            },
            room=client_id
        )
    except Exception as e:
        sender.sendError(key="Error generating assure report",function = "create_service_assurance_report")
        appLogger.error({"event": "create_service_assurance_report", "error": str(e), "tenant_id": tenantID,"traceback":traceback.format_exc()})
    
    

ARGUMENTS = []

CREATE_SERVICE_ASSURNACE_REPORT = AgentFunction(
    name="create_service_assurance_report",
    description="",
    args=ARGUMENTS,
    return_description='',
    function=create_service_assurance_report,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)
