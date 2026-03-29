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
import re
from src.trmeric_services.agents.functions.common import send_latest_project_status_for_user

def update_project_status_ui(
    tenantID: int,
    userID: int,
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    
    **kwargs
):
    
    print("debug -- update_project_status_ui ", tenantID, userID, socketio, client_id)
    data = TangoDao.fetchTangoStatesForUserForProjectStatusUpdate(user_id=userID, tenant_id=tenantID)
    message = ''
    availableProjects = ProjectsDao.FetchAvailableProject(tenant_id=tenantID, user_id=userID)
    print("availableProjects--", len(data), availableProjects)
    arr = []
    for d in data:
        print("d--", d)
        if d["project_id"] in availableProjects:
            arr.append(d)
    
    def fix_unescaped_quotes(json_string):
        return re.sub(r'(?<!\\)"', r'\\"', json_string)

    if socketio:
        socketio.emit("tango_show_project_status_ui", arr, room=client_id)
        print("data sent ---- ")
        send_latest_project_status_for_user(tenantID, userID, socketio=socketio, client_id=client_id)
        message += "✅ Service Assurance Workplace Initiated"
    else:
        print("missing socket io error ")
        message += "❌ Error occured in initializing service assurance Workplace"
    print("message --- debug ", message)   
    return message
        

    

RETURN_DESCRIPTION = """
This function is responsible to render the UI for projects status update
"""

ARGUMENTS = []

UPDATE_PROJECT_STATUS_UI = AgentFunction(
    name="update_project_status_ui",
    description="""
        This function is brilliantly created to show the update staus UI whenever user wants to update project status
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=update_project_status_ui,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)
