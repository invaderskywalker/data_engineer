from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import *
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import ProjectsDao, TangoDao
import json
from src.trmeric_database.Database import db_instance
import threading
import time
from src.trmeric_services.agents.functions.common import send_latest_project_status_for_user
from src.trmeric_services.agents.precache import ServiceAssurancePrecache
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient


import concurrent.futures


service_assurance_service = ServiceAssuranceApis()


def insert_milestone(tenantID, project_id, milestone_update):
    """Inserts a new milestone for a project."""
    valid_status_values = {1, 2, 3}  # 1: Not Started, 2: In Progress, 3: Completed

    milestone_id = milestone_update.get("milestone_id")
    milestone_name = milestone_update.get("milestone_name")
    new_target_date = milestone_update.get("new_target_date") or milestone_update.get("original_date")  # Fallback to original_date
    new_actual_date = milestone_update.get("actual_date")
    new_comments = milestone_update.get("comments")
    new_status_value = milestone_update.get("status_value")
    milestone_type = milestone_update.get("milestone_type") or 2
    
    
    # 🔥 Normalize empty strings → None
    if new_target_date == "":
        new_target_date = None
    if new_actual_date == "":
        new_actual_date = None

    # Validate required fields for a new milestone
    if milestone_id != "0":
        print(f"Skipping insert for milestone {milestone_id}: Not a new milestone (milestone_id must be '0')")
        return
    if not milestone_name:
        print(f"Skipping insert for new milestone: Missing milestone_name")
        return
    if new_status_value != 3 and not new_target_date:
        print(f"Skipping insert for new milestone: Missing new_target_date")
        return
    if new_status_value is None or new_status_value not in valid_status_values:
        print(f"Skipping insert for new milestone: Invalid status_value {new_status_value}")
        return
    if new_status_value == 3 and not new_actual_date:
        print(f"Skipping insert for new milestone: Missing actual_date for completed milestone")
        return
    # Validate actual_date is not in the future for completed milestones
    from datetime import datetime
    current_date = datetime.now().date().isoformat()
    if new_status_value == 3 and new_actual_date and new_actual_date > current_date:
        print(f"Skipping insert for new milestone: actual_date {new_actual_date} cannot be in the future")
        return

    # Fetch team_id from workflow_projectteam
    team_id = None
    try:
        team_query = f"""
            SELECT id FROM public.workflow_projectteam WHERE project_id = {project_id}
        """
        result = db_instance.retrieveSQLQueryOld(team_query)
        if result and len(result) > 0:
            team_id = result[0].get("id")
        else:
            print(f"No team_id found for project_id {project_id}. Proceeding with team_id as NULL.")
    except Exception as e:
        print(f"Error fetching team_id for project_id {project_id}: {e}. Proceeding with team_id as NULL.")

    # Build the INSERT query
    columns = ["project_id", "name", "target_date"]
    values = ["%s", "%s", "%s"]
    params = [project_id, milestone_name, new_target_date]

    if new_actual_date is not None:
        columns.append("actual_date")
        values.append("%s")
        params.append(new_actual_date)
    if new_comments is not None:
        columns.append("comments")
        values.append("%s")
        params.append(new_comments)
    if new_status_value is not None:
        columns.append("status_value")
        values.append("%s")
        params.append(new_status_value)
    if team_id is not None:
        columns.append("team_id")
        values.append("%s")
        params.append(team_id)
    
    columns.append("type")
    values.append("%s")
    params.append(milestone_type)

    insert_query = f"""
        INSERT INTO workflow_projectmilestone ({', '.join(columns)})
        VALUES ({', '.join(values)})
    """

    try:
        db_instance.executeSQLQuery(insert_query, params)
        print(f"New milestone '{milestone_name}' inserted successfully for project {project_id}")
    except Exception as e:
        print(f"Error inserting new milestone '{milestone_name}': {e}")
        

def update_milestone(tenantID, project_id, milestone_updates,sender=None):
    """Updates all milestones for a project, or inserts new milestones if milestone_id is '0'."""
    valid_status_values = {1, 2, 3}  # 1: Not Started, 2: In Progress, 3: Completed

    for milestone_update in milestone_updates:
        milestone_id = milestone_update.get("milestone_id")

        # Handle new milestones (milestone_id == "0")
        if milestone_id == "0":
            insert_milestone(tenantID, project_id, milestone_update)
            continue

        new_target_date = milestone_update.get("new_target_date")
        new_actual_date = milestone_update.get("actual_date")
        new_comments = milestone_update.get("comments")
        new_status_value = milestone_update.get("status_value")

        # Validate required fields and status_value
        if not milestone_id:
            print(
                f"Skipping invalid milestone update (missing milestone_id): {milestone_update}")
            continue
        if new_status_value is not None and new_status_value not in valid_status_values:
            print(
                f"Skipping invalid status_value {new_status_value} for milestone {milestone_id}")
            continue

        # Convert empty strings to None for date fields
        if new_target_date == "":
            new_target_date = None
        if new_actual_date == "":
            new_actual_date = None

        # Build the SET clause dynamically based on provided fields
        set_clauses = []
        params = []
        if new_target_date is not None:
            set_clauses.append("target_date = %s")
            params.append(new_target_date)
        if new_actual_date is not None:
            set_clauses.append("actual_date = %s")
            params.append(new_actual_date)
        if new_comments is not None:
            set_clauses.append("comments = %s")
            params.append(new_comments)
        if new_status_value is not None:
            set_clauses.append("status_value = %s")
            params.append(new_status_value)

        if not set_clauses:
            print(f"No valid fields to update for milestone {milestone_id}")
            continue

        # Construct the query
        update_query = f"""
            UPDATE workflow_projectmilestone
            SET {', '.join(set_clauses)}
            WHERE id = %s AND project_id = %s;
        """
        params.extend([milestone_id, project_id])

        try:
            db_instance.executeSQLQuery(update_query, params)
            print(f"Milestone {milestone_id} updated successfully")
        except Exception as e:
            print(f"Milestone update error for {milestone_id}: {e}")
            sender.sendError(key=f"Error updating milestone {milestone_id}: {e}",function = "update_milestone")




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
        response = service_assurance_service.create_risk(
            project_id, request_json)
        if response.status_code != 201:
            print(
                f"Risk update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Risk update error: {e}")
        return None


def process_risk_update_v2(tenantID, userID, project_id, data,sender=None):
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
            sender.sendError(key=f"Risk update failed: {response.text} ",function = "process_risk_update_v2")
        return response
    except Exception as e:
        print(f"Risk update error: {e}")
        return None


def process_status_update(tenantID, userID, project_id, update_type, update_value, comment,sender=None):
    print("process_status_update --------", tenantID, userID,
          project_id, update_type, update_value, comment)
    if not comment:
        print("Skipping status update: No comment provided")
        sender.sendError(key=f"Skipping: No comment provided",function = "process_status_update")
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
            sender.sendError(key=f"Status update failed: {response.text}",function = "process_status_update")
        return response
    except Exception as e:
        print(f"Status update error: {e}")
        return None


def save_all_updates(tenantID, userID, project_id, risk_updates, status_updates, milestone_updates,sender=None):
    """Runs all risk, status, and milestone updates in parallel."""
    futures = []
    results = {"risks": [], "statuses": [], "milestones": []}
    futures = {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        if risk_updates:
            future = executor.submit(
                process_risk_update_v2, tenantID, userID, project_id, risk_updates)
            futures[future] = "Risk Updated"

        for status in status_updates:
            future = executor.submit(
                process_status_update,
                tenantID, userID, project_id,
                status["update_type"],
                status["update_value"],
                status["comment"],
                sender = sender
            )
            futures[future] = f"Status Update: {status}"

        if milestone_updates:
            update_milestone(tenantID, project_id, milestone_updates,sender=sender)
            results["milestones"].append("Milestones updated successfully")

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            print("output from future--------", result)
            print(f"Completed: {futures[future]} - Result: {result}")
            label = futures[future]

            if "Risk" in label:
                results["risks"].append("Risk created")
            elif "Status" in label:
                msg = ""
                try:
                    if result.status_code == 201:
                        msg = "Successfully updated status"
                    else:
                        msg = f"Status code : {result.status_code}"
                except Exception as e:
                    msg = "Failed to update status"
                    
                results["statuses"].append(msg)

    return results


def format_response(output):
    if "user_satisfied_for_update" in output:
        del output["user_satisfied_for_update"]
    if "your_thought" in output:
        del output["your_thought"]
    return output


def update_status_milestone_risk_v2(
    tenantID: int,
    userID: int,
    # eligibleProjects: list[int],
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    # last_user_message=None,
    # project_id=None,
    # project_name=None,
    sessionID=None,
    logInfo=None,
    # update_looks_good_to_user=False,
    # input_json={},
    **kwargs
):
    
    data = kwargs.get("data", {})
    message = kwargs.get("message", None)
    eligibleProjects = kwargs.get("eligibleProjects", [])
    update_looks_good_to_user = kwargs.get("update_looks_good_to_user", False)
    project_id = data.get("project_id", None)   
    project_name = data.get("project_name", None)
    input_json = data
    
    last_user_message="Message: " + message +"\n\n" + "Data: " + json.dumps(data)
    print("debug -- update_status_milestone_risk_v2 ", tenantID, userID,
          update_looks_good_to_user, project_id, project_name,  last_user_message)
    project_id_in_conv = project_id
    project_name_in_conv = project_name
    sender = kwargs.get("step_sender")
    
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key=f"update_status_milestone_risk_conv_{project_id_in_conv}",
            value=last_user_message,
            session_id=sessionID
        )

    conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
        session_id=sessionID, user_id=userID, key=f"update_status_milestone_risk_conv_{project_id_in_conv}")
    print("--- conv ", len(conv))

    project_data = ProjectsDao.fetch_project_details_for_service_assurance_v2(project_id)
    data = TangoDao.fetchLatestTangoStateForProjectForTenant(tenant_id=tenantID, project_id=project_id)
    
    timelineData = [
        "Fetching related info",
        "Creating Status Data",
        "Creating Risk Data",
        "Creating Milestone Data"
    ]
    if (update_looks_good_to_user):
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
                              "project_id": project_id_in_conv,
                          },
                          room=client_id
                          )
            socketio.sleep(1)
            for val in timelineData:
                print("sending ------- timeline ---- ", val)
                socketio.emit("service_assurance_agent",
                              {
                                  "event": "timeline", "data": {"text": val, "key": val, "is_completed": False, "project_id": project_id_in_conv}
                              },
                              room=client_id
                              )
                socketio.sleep(1)
                socketio.emit("service_assurance_agent",
                              {
                                  "event": "timeline", "data": {"text": val, "key": val, "is_completed": True, "project_id": project_id_in_conv}
                              },
                              room=client_id
                              )

    timeline_thread = threading.Thread(target=emit_timeline_data)
    timeline_thread.start()
    
    

    # TangoDao.insertTangoState(
    #     tenant_id=tenantID,
    #     user_id=userID,
    #     key=f"update_status_milestone_risk_conv_{project_id_in_conv}",
    #     value=str(response),
    #     session_id=sessionID
    # )

    if (update_looks_good_to_user):
        def format_input_data(input_data, project_id):
            """Formats input data into the expected JSON structure without LLM."""
            return {
                "project_id": str(project_id),
                "project_name": input_data.get("project_name", ""),
                "status_updates": input_data.get("user_comment", {}).get("status_updates", []),
                "risk_updates": input_data.get("user_comment", {}).get("risk_updates", []),
                "milestone_updates": input_data.get("user_comment", {}).get("milestone_updates", [])
            }
        
        # with open("sa_update_status_v2.json", 'w') as f:
        #     json.dumps(input_json, f,indent=2)
        
        response = format_input_data(input_json, project_id_in_conv)
        response["project_id"] = project_id_in_conv
        
        
        status_updates = response.get("status_updates", [])
        risk_updates = response.get("risk_updates", [])
        milestone_updates = response.get("milestone_updates", [])

        results = save_all_updates(
            tenantID=tenantID,
            userID=userID,
            project_id=project_id_in_conv,
            risk_updates=risk_updates,
            status_updates=status_updates,
            milestone_updates=milestone_updates,
            sender = sender
        )
        response = format_response(response)
        
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key=f"update_status_milestone_risk_conv_{project_id_in_conv}",
            value=str(response),
            session_id=sessionID
        )
        socketio.emit("service_assurance_agent",
                      {
                          "event": "stop_show_timeline",
                          "project_id": project_id_in_conv,
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

        send_latest_project_status_for_user(
            tenantID, userID, socketio=socketio, client_id=client_id,sender=sender)
        socketio.emit("agent_chat_user", "<end>", room=client_id)
        socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        return "✅ Updates Created"
    else:
        prompt = create_combined_update_prompt_v2(
        project_info=project_data, data=None, user_update_statement=last_user_message, conv=conv)

        # print("prompt --- ", prompt.formatAsString())

        response = llm.run(
            prompt, model_opts, 'agent::service_assurance::update_status_milestone_risk', logInfo,socketio=socketio, client_id=client_id)
        print("service_assurance::update_status_milestone_risk 1 ========", update_looks_good_to_user, response)
        response = extract_json_after_llm(response,step_sender=sender)
        response["project_id"] = project_id_in_conv
    
        response = format_response(response)
        
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key=f"update_status_milestone_risk_conv_{project_id_in_conv}",
            value=str(response),
            session_id=sessionID
        )

        socketio.emit("service_assurance_agent",
                      {
                          "event": "stop_show_timeline",
                          "project_id": project_id_in_conv,
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

        send_latest_project_status_for_user(
            tenantID, userID, socketio=socketio, client_id=client_id,sender=sender)
        socketio.emit("agent_chat_user", "<end>", room=client_id)
        socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        return "✅ UI updated with review data"




UPDATE_STATUS_MILESTONE_RISK_V2 = AgentFunction(
    name="update_status_milestone_risk_v2",
    description="""
        This function is nicely tailored to create creation/updation of project status,  project risk and milestones
        from a comment given by the user.
        
        Then this function will wait for user confirmation 
        regarding the understanding of the update
        and then will create/update.
        
    """,
    args=[],
    return_description='',
    function=update_status_milestone_risk_v2,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)



def create_project_updates(
    tenant_id: int,
    user_id: int,
    project_id: int,
    conversation: str,
    update_type: str,
):
    try:
        logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        print("create_project_updates start ", update_type, project_id, logInfo)
        
        llm = ChatGPTClient()
        modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=4000,
            temperature=0.1
        )
        
        valid_types = ["milestone", "status", "risk"]
        if update_type not in valid_types:
            return {"error": f"Invalid update_type. Must be one of {valid_types}"}

        project_data = ProjectsDao.fetch_project_details_for_service_assurance_v2(project_id)
        if not project_data:
            return {"error": f"No project found for project_id {project_id}"}

        # Select prompt based on update_type
        if update_type == "milestone":
            prompt = create_milestone_update_prompt(project_info=project_data, conversation=conversation)
        elif update_type == "status":
            prompt = create_status_update_prompt(project_info=project_data, conversation=conversation)
        elif update_type == "risk":
            prompt = create_risk_update_prompt(project_info=project_data, conversation=conversation)

        response = llm.run(prompt, modelOptions, f'agent::analyst::suggest_{update_type}', logInfo)
        response = extract_json_after_llm(response)
        response["project_id"] = project_id
        print("---------------")
        print("response -- ", update_type, project_id, response)
        print("--------------")
        
        
        def format_input_data(input_data, project_id):
            """Formats input data into the expected JSON structure without LLM."""
            return {
                "project_id": str(project_id),
                "project_name": input_data.get("project_name", ""),
                "status_updates": input_data.get("status_updates", []) or [],
                "risk_updates": input_data.get("risk_updates", []) or [],
                "milestone_updates": input_data.get("milestone_updates", []) or []
            }

        response = format_input_data(response, project_id)
        status_updates = response.get("status_updates", []) or []
        risk_updates = response.get("risk_updates", []) or []
        milestone_updates = response.get("milestone_updates", []) or []

        results = save_all_updates(
            tenantID=tenant_id,
            userID=user_id,
            project_id=project_id,
            risk_updates=risk_updates,
            status_updates=status_updates,
            milestone_updates=milestone_updates
        )
        print("save_all_updates results ", results)
        return {
            "update_type": update_type,
            "input": response,
            "result": results
        }
    
    except Exception as e:
        print("create_project_updates error ", e)
        raise e

