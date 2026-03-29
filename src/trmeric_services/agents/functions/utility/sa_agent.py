from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
from src.trmeric_database.Database import db_instance
import threading
import time
import concurrent.futures


service_assurance_service = ServiceAssuranceApis()


def insert_milestone(tenantID, project_id, milestone_update):
    """Inserts a new milestone for a project."""
    valid_status_values = {
        1, 2, 3}  # 1: Not Started, 2: In Progress, 3: Completed

    milestone_id = milestone_update.get("milestone_id")
    milestone_name = milestone_update.get("milestone_name")
    new_target_date = milestone_update.get("new_target_date")
    new_actual_date = milestone_update.get("actual_date")
    new_comments = milestone_update.get("comments")
    new_status_value = milestone_update.get("status_value")

    # Validate required fields for a new milestone
    if milestone_id != "0":
        print(
            f"Skipping insert for milestone {milestone_id}: Not a new milestone (milestone_id must be '0')")
        return
    if not milestone_name:
        print(f"Skipping insert for new milestone: Missing milestone_name")
        return
    if not new_target_date:
        print(f"Skipping insert for new milestone: Missing new_target_date")
        return
    if new_status_value is not None and new_status_value not in valid_status_values:
        print(
            f"Skipping insert for new milestone: Invalid status_value {new_status_value}")
        return

    # Convert empty strings to None for date fields
    if new_target_date == "":
        new_target_date = None
    if new_actual_date == "":
        new_actual_date = None

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
    if tenantID is not None:
        columns.append("tenant_id")
        values.append("%s")
        params.append(tenantID)

    insert_query = f"""
        INSERT INTO workflow_projectmilestone ({', '.join(columns)})
        VALUES ({', '.join(values)})
    """

    try:
        db_instance.executeSQLQuery(insert_query, params)
        print(
            f"New milestone '{milestone_name}' inserted successfully for project {project_id}")
    except Exception as e:
        print(f"Error inserting new milestone '{milestone_name}': {e}")


def update_milestone(tenantID, project_id, milestone_updates):
    """Updates all milestones for a project, or inserts new milestones if milestone_id is '0'."""
    valid_status_values = {
        1, 2, 3}  # 1: Not Started, 2: In Progress, 3: Completed

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
        response = service_assurance_service.create_risk(
            project_id, request_json)
        if response.status_code != 201:
            print(
                f"Risk update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Risk update error: {e}")
        return None


def process_status_update(tenantID, userID, project_id, update_type, update_value, comment):
    print("process_status_update --------", tenantID, userID,
          project_id, update_type, update_value, comment)
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
        response = service_assurance_service.update_status(
            project_id, request_json)
        if response.status_code != 201:
            print(
                f"Status update failed: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Status update error: {e}")
        return None

