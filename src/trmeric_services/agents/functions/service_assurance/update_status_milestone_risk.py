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
from src.trmeric_services.agents.functions.common import send_latest_project_status_for_user
from src.trmeric_services.agents.precache import ServiceAssurancePrecache





import concurrent.futures


service_assurance_service = ServiceAssuranceApis()


def update_milestone(tenantID, project_id, milestone_updates):
    """Updates all milestones for a project."""
    for milestone_update in milestone_updates:
        milestone_id = milestone_update.get("milestone_id")
        new_target_date = milestone_update.get("new_target_date")

        if not milestone_id or not new_target_date:
            print(f"Skipping invalid milestone update: {milestone_update}")
            continue

        update_query = """
            UPDATE workflow_projectmilestone
            SET target_date = %s
            WHERE id = %s AND project_id = %s;
        """
        
        try:
            db_instance.executeSQLQuery(update_query, (new_target_date, milestone_id, project_id))
            print(f"Milestone {milestone_id} updated successfully to {new_target_date}")
        except Exception as e:
            print(f"Milestone update error: {e}")


def process_risk_update(tenantID, userID, project_id, item):
    print("process_risk_update --------", tenantID, userID, project_id, item)
    priority = item.get("priority", 2)  # Default to Medium if missing
    request_json = {
        "user_id": userID,
        "tenant_id": tenantID,
        "risk_list": [{
            "id": 0,
            "description": item["description"],
            "impact": item["impact"],
            "mitigation": item["mitigation"],
            "priority": priority,
            "due_date": item["due_date"]
        }]
    }
    try:
        response = service_assurance_service.create_risk(project_id, request_json)
        if response.status_code != 201:
            print(f"Risk update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Risk update error: {e}")
        return None


def process_risk_update_v2(tenantID, userID, project_id, data):
    # print("process_risk_update --------", tenantID, userID, project_id, item)
    items = []
    for d in data:
        priority = d.get("priority", 2)  # Default to Medium if missing
        items.append({
            "id": 0,
            "description": d["description"],
            "impact": d["impact"],
            "mitigation": d["mitigation"],
            "priority": priority,
            "due_date": d["due_date"]
        })
    
    request_json = {
        "user_id": userID,
        "tenant_id": tenantID,
        "risk_list": items
    }
    # request_json = {
    #     "user_id": userID,
    #     "tenant_id": tenantID,
    #     "risk_list": [{
    #         "id": 0,
    #         "description": item["description"],
    #         "impact": item["impact"],
    #         "mitigation": item["mitigation"],
    #         "priority": priority,
    #         "due_date": item["due_date"]
    #     }]
    # }
    try:
        response = service_assurance_service.create_risk(project_id, request_json)
        if response.status_code != 201:
            print(f"Risk update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Risk update error: {e}")
        return None


def process_status_update(tenantID, userID, project_id, update_type, update_value, comment):
    print("process_status_update --------", tenantID, userID, project_id, update_type, update_value, comment)
    if not comment:
        print("Skipping status update: No comment provided")
        return None

    _type = PROJECT_STATUS_TYPE_TO_CODE.get(update_type, "unknown")
    _value = PROJECT_STATUS_VALUE_TO_CODE.get(update_value, "unknown")

    request_json = {
        "tenant_id": tenantID,
        "user_id": userID,
        "type": _type,
        "value": _value,
        "comments": comment,
        "actual_percentage": 0
    }
    try:
        response = service_assurance_service.update_status(project_id, request_json)
        if response.status_code != 201:
            print(f"Status update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Status update error: {e}")
        return None


def save_all_updates(tenantID, userID, project_id, risk_updates, status_updates, milestone_updates):
    """Runs all risk, status, and milestone updates in parallel."""
    futures = []
    results = {"risks": [], "statuses": [], "milestones": []}
    futures = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(process_risk_update_v2, tenantID, userID, project_id, risk_updates)
        futures[future] = f"Risk Updated"

        for status in status_updates:
            future = executor.submit(
                process_status_update,
                tenantID, userID, project_id,
                status["update_type"],
                status["update_value"],
                status["comment"]
            )
            futures[future] = f"Status Update: {status}"
            
        if milestone_updates:
            update_milestone(tenantID, project_id, milestone_updates)
            results["milestones"].append("Milestones updated successfully")

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            print("output from future--------", result)
            print(f"Completed: {futures[future]} - Result: {result}")

    return results

def format_response(output):
    del output["user_satisfied_for_update"]
    del output["your_thought"]
    return output


def update_status_milestone_risk(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    project_id=None,
    project_name=None,
    sessionID=None,
    logInfo=None,
    update_looks_good_to_user=False,
    **kwargs
):
    print("debug -- update_status_milestone_risk ", tenantID, userID, update_looks_good_to_user, project_id, project_name,  last_user_message)
    
        
    if project_id and project_name:
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="update_status_milestone_risk_project_id_name", 
            value=json.dumps({
                "project_id": project_id,
                "project_name": project_name
            }),
            session_id=sessionID
        )
    
    project_and_key_id_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id=sessionID, user_id=userID, key="update_status_milestone_risk_project_id_name")
    project_and_key_id_data = json.loads(project_and_key_id_data[0]['value'])
    project_id_in_conv = project_and_key_id_data["project_id"]
    project_name_in_conv = project_and_key_id_data["project_name"]
        
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key=f"update_status_milestone_risk_conv_{project_id_in_conv}", 
            value=last_user_message, 
            session_id=sessionID
        )
    
    
    conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id=sessionID, user_id=userID, key=f"update_status_milestone_risk_conv_{project_id_in_conv}")
    print("--- conv ", len(conv))
    
    
    
    project_data = ProjectsDao.fetch_project_details_for_service_assurance(project_id)
    prompt = create_combined_update_prompt(project_info=project_data, user_update_statement=last_user_message, conv=conv)
    
    timelineData = [
        "Fetching related info",
        "Creating Status Data",
        "Creating Risk Data",
        "Creating Milestone Data"
    ]
    if ( len(conv) > 1):
        timelineData = [
            "Fetching related info",
            "Updating Status Data",
            "Updating Risk Data",
            "Updating Milestone Data",
            "Saving Status Data",
            "Saving Risk Data",
            "Saving Milestone Data",
        ]
        
    
    def emit_timeline_data():
        print("running this... emit_timeline_data")
        if (socketio and client_id):
            socketio.emit("service_assurance_agent", 
                {
                    "event": "show_timeline",
                }, 
                room=client_id
            )
            time.sleep(1)
            for val in timelineData:
                print("sending ------- timeline ---- ", val)
                socketio.emit("service_assurance_agent", 
                    {
                        "event": "timeline", "data": {"text": val, "key": val, "is_completed": False}
                    }, 
                    room=client_id
                )
                time.sleep(1)
                socketio.emit("service_assurance_agent", 
                    {
                        "event": "timeline", "data": {"text": val, "key": val, "is_completed": True}
                    }, 
                    room=client_id
                )


    timeline_thread = threading.Thread(target=emit_timeline_data)
    timeline_thread.start()
    # timeline_thread.join()
    
                
    response = llm.run(prompt, model_opts , 'agent::service_assurance::update_status_milestone_risk', logInfo)
    print("service_assurance::update_status_milestone_risk 1 ========", response)
    response = extract_json_after_llm(response)
    
    
    TangoDao.insertTangoState(
        tenant_id=tenantID, 
        user_id=userID,
        key=f"update_status_milestone_risk_conv_{project_id_in_conv}", 
        value=str(response), 
        session_id=sessionID
    )
    
    # if response.get("user_satisfied_for_update") == "true":
    if ( len(conv) > 1):
        status_updates = response.get("status_updates", [])
        risk_updates = response.get("risk_updates", [])
        milestone_updates = response.get("milestone_updates", [])
    
        results = save_all_updates(
            tenantID=tenantID, 
            userID=userID, 
            project_id=project_id_in_conv, 
            risk_updates=risk_updates, 
            status_updates=status_updates,
            milestone_updates=milestone_updates
        )
        response = format_response(response)
        socketio.emit("service_assurance_agent", 
                {
                    "event": "stop_show_timeline",
                }, 
                room=client_id
            )
        socketio.emit(
            "service_assurance_agent", 
            {
                "event": "update_done",
                "project_id": project_id_in_conv,
            },
            room=client_id
        )
        
        
        send_latest_project_status_for_user(tenantID, userID, socketio=socketio, client_id=client_id)
        def start():
            ServiceAssurancePrecache(tenant_id=tenantID, user_id=userID)
        
        thread = threading.Thread(target=start)
        thread.start()
        
        return "✅ Updates Created"
    else:
        response = format_response(response)
        
        socketio.emit("service_assurance_agent", 
                {
                    "event": "stop_show_timeline",
                }, 
                room=client_id
            )
        
        socketio.emit(
            "service_assurance_agent", 
            {
                "event": "review_data",
                "data": response
            },
            room=client_id
        )
        
        send_latest_project_status_for_user(tenantID, userID, socketio=socketio, client_id=client_id)
        # socketio.emit("service_assurance_show", response, room=client_id)
        return "✅ UI updated with review data"



ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int",
        "required": 'true',
        "description": """Project Id that user wants to update status""",
    },
    {
        "name": "project_name",
        "type": "string",
        "required": 'true',
        "description": """Project Name that user wants to update status""",
    },
    {
        "name": "update_looks_good_to_user",
        "type": "bool",
        "required": 'true',
        "description": """If the user says that the update looks good""",
    }
]

UPDATE_STATUS_MILESTONE_RISK = AgentFunction(
    name="update_status_milestone_risk",
    description="""
        This function is nicely tailored to create creation/updation of project status,  project risk and milestones
        from a comment given by the user.
        
        Then this function will wait for user confirmation 
        regarding the understanding of the update
        and then will create/update.
        
    """,
    args=ARGUMENTS,
    return_description='',
    function=update_status_milestone_risk,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)
