from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import TangoDao, ProjectsDao
import json
from uuid import UUID
import datetime
import traceback
from src.trmeric_services.agents.functions.common import send_latest_project_status_for_user
from src.trmeric_services.agents.precache.service_assurance import ServiceAssurancePrecache

def update_status_basic_data(
    tenantID: int,
    userID: int,
    # project_id,
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    **kwargs
):
    _data = kwargs.get("data", {})
    project_id = _data.get("project_id")

    try:
    
        print("debug -- update_status_basic_data ", tenantID, userID, socketio, client_id)
        data = ServiceAssurancePrecache(tenant_id=tenantID, user_id=userID, init=False, force=False).initializeDataV2(project_id)
        if socketio:
            socketio.emit(
                "service_assurance_agent", 
                {
                    "data": data, 
                    "event": "basic_status_update_data"
                }, 
                room=client_id
            )
            send_latest_project_status_for_user(tenantID, userID, socketio=socketio, client_id=client_id)
            socketio.emit("agent_chat_user", "<end>", room=client_id)
            socketio.emit("agent_chat_user", "<<end>>", room=client_id)
            # project_statuses = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)        
            # socketio.emit(
            #     "service_assurance_agent", 
            #     {
            #         "event": "refresh_status",
            #         "data": arr
            #     },
            #     room=client_id
            # )
    except Exception as e:
        print("--debug error in update_status_basic_data-------", str(e), traceback.format_exc())



UPDATE_STATUS_BASIC_DATA = AgentFunction(
    name="update_status_basic_data",
    description="",
    args=[],
    return_description='',
    function=update_status_basic_data,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)