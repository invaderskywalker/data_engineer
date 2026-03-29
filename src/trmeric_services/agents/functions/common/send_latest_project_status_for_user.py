from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import create_combined_update_prompt
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import ProjectsDao, TangoDao
import json
from src.trmeric_database.Database import db_instance
import threading
import time


def send_latest_project_status_for_user(
    tenantID: int,
    userID: int,
    socketio=None,
    client_id=None,
    **kwargs
):  
    sender = kwargs.get("steps_sender")
    print("debug -- update_status_milestone_risk ", tenantID, userID)

    availableProjects = ProjectsDao.FetchAvailableProject(
        tenant_id=tenantID, user_id=userID)
    # print("debug -- update_status_milestone_risk ", availableProjects)
    arr = {}
    for project_id in availableProjects:
        project_statuses = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
        # print("debug -- update_status_milestone_risk ", project_statuses)
        # project_statuses = ProjectsDao.fetchProjectStatuses(project_id)
        # arr.append(project_statuses)
        arr[project_id] = project_statuses
        
    if not arr:
        print("--debug error sending status --",arr,tenantID,userID)
        sender.sendError(key="Error in refreshing status",function = "send_latest_project_status_for_user")
        return

    socketio.emit(
        "service_assurance_agent",
        {
            "event": "refresh_status",
            "data": arr
        },
        room=client_id
    )
