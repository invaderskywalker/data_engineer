from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_services.agents.prompts.agents import create_combined_update_prompt, create_report_prompt, create_review_project
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import ProjectsDao, TangoDao, CustomerDao
import json
from src.trmeric_database.Database import db_instance
import traceback
import time
import datetime
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data, get_smartsheet_data, get_jira_summary_data
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.integration.IntegrationService import IntegrationService
from .update_status_milestone_risk_v2 import process_status_update


from copy import deepcopy


def create_review_report_for_project(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    project_id=None,
    project_name=None,
    sessionID=None,
    logInfo=None,
    **kwargs,
):
    sender = kwargs.get("step_sender")
    try:
    
        if project_id is None:
            # socketio.emit("service_assurance_agent", {"event": "create_project_review_screen::failure", "error": "Project Id Missing"}, room=client_id)
            sender.sendError(key="Project Id Missing",function = "create_review_report_for_project")
            return

        appLogger.info({"event": "start", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

        current_date = datetime.datetime.now().date()  # Get current date
        previous_date = (current_date - datetime.timedelta(days=7)).isoformat()  # Get n days before
        previous_previous_date = (current_date - datetime.timedelta(days=7)).isoformat()

        project_data = ProjectsDao.fetchProjectDetailsForServiceAssuranceReview(project_id=project_id)
        previous_week_status_updates = ProjectsDao.fetchStatusUpdatesBetweenTimes(project_id=project_id, start_date=previous_date)
        two_weeks_before_status_updates = ProjectsDao.fetchStatusUpdatesBetweenTimes(project_id, start_date=previous_previous_date, end_date=previous_date)
        milestone_data = ProjectsDao.fetchProjectMilestonesV2(project_id=project_id)

        risksData = ProjectsDao.fetchProjectsRisksV2([project_id])
        project_data["risks_data"] = risksData
        current_project_status = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
        project_data["latest_project_status"] = current_project_status

        appLogger.info({"event": "start_1", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})
        # upcoming_milestone_data = ProjectsDao.fetchProjectUpcomingMilestones(project_id=project_id)

        customer_info = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenantID)
        org_info_string = ""
        if len(customer_info) > 0:
            org_info_string += f"""
                This customer Org Info gathered by Trmeric is:
                {customer_info[0].get("org_info")}
            """

        # smartsheet_data = get_smartsheet_data(tenantID, userID, project_id=project_id)
        # jira_data = get_jira_data(tenantID=tenantID, userID=userID, project_id=[project_id], get_all_data=True)
        # smartsheet_data_str = json.dumps(smartsheet_data, indent=2)

        appLogger.info({"event": "start_2", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

        # integration_data = ''
        # if len(jira_data.split()) > 200:
        #     integration_data += f"- **jira_data**: {jira_data }"
        # if len(smartsheet_data_str) > 500:
        #     integration_data += f"\n\n- **smartsheet_data**: {smartsheet_data}"

        integration_data = IntegrationService().fetchProjectDataforIntegration(tenant_id=tenantID, project_id=project_id)
        new_summary = json.dumps(integration_data, indent=2)

        appLogger.info({"event": "start_3", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

        prompt = create_review_project(
            project_info=project_data,
            previous_week_status_updates=previous_week_status_updates,
            p2p_week_status_updates=two_weeks_before_status_updates,
            milestone_data=milestone_data,
            org_info_string=org_info_string,
            jira_data=None,
            smartsheet_data=None,
            integration_data=integration_data,
        )
        print("prompt for service_assurance::create_review_report_for_project 1 ========", prompt.formatAsString())

        # model_opts_1 = ModelOptions(model="gpt-4.1", max_tokens=16000, temperature=0)
        response = llm.run(prompt, model_opts, 'agent::service_assurance::create_review_report_for_project', {"tenant_id": tenantID, "user_id": userID},socketio=socketio, client_id=client_id)
        print("service_assurance::create_review_report_for_project 1 ========", response)
        response = extract_json_after_llm(response,step_sender=sender)

        appLogger.info({"event": "start_4", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})
        socketio.emit("service_assurance_agent", {"event": "create_project_review_screen::data", "project_id": project_id, "data": response}, room=client_id)

    except Exception as e:
        sender.sendError(key="Error generating review report",function = "create_review_report_for_project")
        appLogger.error({"event": "create_review_report_for_project", "error": str(e), "tenant_id": tenantID,"traceback":traceback.format_exc()})



# def evaluate_and_update_schedule_status(tenantID, userID, project_id, milestone_data, project_data):
#     """
#     Evaluates the project schedule and spend status based on milestone target dates, risk status,
#     and spend milestones, then updates the status using process_status_update.

#     Args:
#         tenantID (int): Tenant ID
#         userID (int): User ID
#         project_id (int): Project ID
#         milestone_data (dict): Milestone data containing schedule_milestones and spend_milestones
#         project_data (list): Project data containing risk_table and project_budget

#     Returns:
#         dict: Contains schedule_status ('on_track', 'at_risk', 'compromised') and
#               spend_status ('on_track', 'compromised')
#     """
#     current_date = datetime.datetime.now().date()
#     schedule_status = "on_track"  # Default schedule status
#     spend_status = "on_track"     # Default spend status
#     schedule_comment = ""
#     spend_comment = ""

#     # Fetch risk table
#     risk_table = ProjectsDao.fetchProjectsRisksV2(project_ids=[project_id])

#     # Extract project budget from project_data
#     project_budget = project_data[0].get('project_budget', float('inf')) if project_data else float('inf')

#     print("debug milestone_data---- ", project_budget, milestone_data, risk_table)

#     # --- Schedule Status Evaluation ---
#     milestones = milestone_data.get('schedule_milestones', [])
#     valid_milestones = []
#     invalid_milestones = []

#     # Filter milestones with valid target_date
#     for milestone in milestones:
#         target_date_str = milestone.get('target_date')
#         milestone_name = milestone.get('milestone_name', 'Unknown')
#         if not isinstance(target_date_str, str) or not target_date_str:
#             invalid_milestones.append(milestone_name)
#             print(f"Invalid or missing target_date for milestone '{milestone_name}': {target_date_str}")
#             continue
#         try:
#             # Validate date format
#             datetime.datetime.strptime(target_date_str, '%Y-%m-%d')
#             valid_milestones.append(milestone)
#         except ValueError:
#             invalid_milestones.append(milestone_name)
#             print(f"Invalid target_date format for milestone '{milestone_name}': {target_date_str}")

#     # Sort valid milestones by target_date in ascending order
#     try:
#         valid_milestones = sorted(
#             valid_milestones,
#             key=lambda x: datetime.datetime.strptime(x.get('target_date'), '%Y-%m-%d').date()
#         )
#     except Exception as e:
#         print(f"Error sorting milestones: {e}")
#         invalid_milestones.extend([m.get('milestone_name', 'Unknown') for m in valid_milestones])
#         valid_milestones = []

#     print("debug sorted milestone_data---- ", valid_milestones)

#     overdue_or_late_milestones = []
#     on_track_milestones = []
#     total_milestones = len(milestones)
#     track_latest_schedule_status = ''

#     for milestone in valid_milestones:
#         target_date_str = milestone.get('target_date')
#         actual_completion_date = milestone.get('actual_completion_date', None)
#         milestone_name = milestone.get('milestone_name', 'Unknown')

#         print("looping milestones ... ", track_latest_schedule_status)

#         if not target_date_str:
#             continue  # Skip milestones with no target date

#         try:
#             target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()

#             # Case 1: Overdue (no actual completion and target date passed)
#             if not actual_completion_date and target_date < current_date:
#                 overdue_or_late_milestones.append(milestone_name)
#                 track_latest_schedule_status = 'compromised'
#                 continue

#             # Case 2: Completed milestone
#             if actual_completion_date:
#                 actual_date = datetime.datetime.strptime(actual_completion_date, '%Y-%m-%d').date()
#                 if actual_date > target_date:
#                     # Late completion
#                     track_latest_schedule_status = 'compromised'
#                     overdue_or_late_milestones.append(milestone_name)
#                 elif actual_date <= target_date:
#                     # On time or early completion
#                     track_latest_schedule_status = 'on_track'
#                     on_track_milestones.append(milestone_name)
#         except ValueError:
#             print(f"Error parsing dates for milestone '{milestone_name}'")
#             invalid_milestones.append(milestone_name)

#     print("debug --- ", track_latest_schedule_status)
#     # Determine schedule status
#     if track_latest_schedule_status == 'compromised':
#         schedule_status = "compromised"
#         schedule_comment += f"Schedule is compromised due to {len(overdue_or_late_milestones)}/{total_milestones} overdue or late milestones: {', '.join(overdue_or_late_milestones)}."
#     elif track_latest_schedule_status == 'on_track':
#         schedule_status = "on_track"
#         schedule_comment += f"Schedule is on track with {len(on_track_milestones)}/{total_milestones} milestones completed on time or early: {', '.join(on_track_milestones)}."
#     # else:
#     #     schedule_comment += "No valid milestones to evaluate schedule status."

#     # Check for active risks (only if not compromised)
#     active_risks = [risk for risk in risk_table if risk.get('status', '').lower() == 'active']
#     if active_risks and schedule_status == "on_track":
#         schedule_status = "at_risk"
#         schedule_comment = f"Active risks detected: {len(active_risks)} risk(s) impacting schedule."

#     # --- Spend Status Evaluation ---
#     spend_milestones = milestone_data.get('spend_milestones', [])
#     total_planned_spend = 0.0
#     overspend_milestones = []

#     for milestone in spend_milestones:
#         planned_spend = float(milestone.get('planned_spend', 0.0) or 0.0)
#         actual_spend = float(milestone.get('actual_spend', 0.0) or 0.0)
#         milestone_name = milestone.get('milestone_name', 'Unknown')

#         # Accumulate total planned spend
#         total_planned_spend += planned_spend

#         # Check if actual spend exceeds planned spend
#         if actual_spend > planned_spend:
#             overspend_milestones.append(milestone_name)

#     # Determine spend status
#     if overspend_milestones:
#         spend_status = "compromised"
#         spend_comment += f"Overspending detected in milestone(s): {', '.join(overspend_milestones)}."
#     elif total_planned_spend > project_budget:
#         spend_status = "compromised"
#         spend_comment += f"Total planned spend ({total_planned_spend}) exceeds project budget ({project_budget})."
#     else:
#         spend_status = "on_track"
#         spend_comment += f"Total planned spend ({total_planned_spend}) is within project budget ({project_budget}) and no overspending detected."

#     # --- Update Schedule Status ---
#     if schedule_comment:
#         response = process_status_update(
#             tenantID=tenantID,
#             userID=userID,
#             project_id=project_id,
#             update_type="schedule",
#             update_value=schedule_status,
#             comment=schedule_comment.strip()
#         )
#         if response and response.status_code == 201:
#             appLogger.info({
#                 "event": "schedule_status_updated",
#                 "tenant_id": tenantID,
#                 "user_id": userID,
#                 "project_id": project_id,
#                 "status": schedule_status,
#                 "comment": schedule_comment
#             })
#         else:
#             appLogger.error({
#                 "event": "schedule_status_update_failed",
#                 "tenant_id": tenantID,
#                 "user_id": userID,
#                 "project_id": project_id,
#                 "status": schedule_status,
#                 "comment": schedule_comment
#             })

#     # --- Update Spend Status ---
#     if spend_comment:
#         response = process_status_update(
#             tenantID=tenantID,
#             userID=userID,
#             project_id=project_id,
#             update_type="spend",
#             update_value=spend_status,
#             comment=spend_comment.strip()
#         )
#         if response and response.status_code == 201:
#             appLogger.info({
#                 "event": "spend_status_updated",
#                 "tenant_id": tenantID,
#                 "user_id": userID,
#                 "project_id": project_id,
#                 "status": spend_status,
#                 "comment": spend_comment
#             })
#         else:
#             appLogger.error({
#                 "event": "spend_status_update_failed",
#                 "tenant_id": tenantID,
#                 "user_id": userID,
#                 "project_id": project_id,
#                 "status": spend_status,
#                 "comment": spend_comment
#             })

#     return {
#         "schedule_status": schedule_status,
#         "spend_status": spend_status
#     }


def create_review_report_for_project(
    tenantID: int,
    userID: int,
    # eligibleProjects: list[int],
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    # project_id=None,
    project_name=None,
    sessionID=None,
    logInfo=None,
    **kwargs,
):
    data = kwargs.get("data", {})
    project_id = data.get("project_id", None)
    if project_id is None:
        socketio.emit("service_assurance_agent", {"event": "create_project_review_screen::failure", "error": "Project Id Missing"}, room=client_id)
        return

    appLogger.info({"event": "start", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

    current_date = datetime.datetime.now().date()  # Get current date
    previous_date = (current_date - datetime.timedelta(days=7)).isoformat()  # Get n days before
    previous_previous_date = (current_date - datetime.timedelta(days=7)).isoformat()

    project_data = ProjectsDao.fetchProjectDetailsForServiceAssuranceReview(project_id=project_id)
    previous_week_status_updates = ProjectsDao.fetchStatusUpdatesBetweenTimes(project_id=project_id, start_date=previous_date)
    two_weeks_before_status_updates = ProjectsDao.fetchStatusUpdatesBetweenTimes(project_id, start_date=previous_previous_date, end_date=previous_date)
    milestone_data = ProjectsDao.fetchProjectMilestonesV2(project_id=project_id)

    risksData = ProjectsDao.fetchProjectsRisksV2([project_id])
    project_data["risks_data"] = risksData
    current_project_status = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id)
    project_data["latest_project_status"] = current_project_status

    appLogger.info({"event": "start_1", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})
    # upcoming_milestone_data = ProjectsDao.fetchProjectUpcomingMilestones(project_id=project_id)

    customer_info = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=tenantID)
    org_info_string = ""
    if len(customer_info) > 0:
        org_info_string += f"""
            This customer Org Info gathered by Trmeric is:
            {customer_info[0].get("org_info")}
        """

    # smartsheet_data = get_smartsheet_data(tenantID, userID, project_id=project_id)
    # jira_data = get_jira_data(tenantID=tenantID, userID=userID, project_id=[project_id], get_all_data=True)
    # smartsheet_data_str = json.dumps(smartsheet_data, indent=2)

    appLogger.info({"event": "start_2", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

    # integration_data = ''
    # if len(jira_data.split()) > 200:
    #     integration_data += f"- **jira_data**: {jira_data }"
    # if len(smartsheet_data_str) > 500:
    #     integration_data += f"\n\n- **smartsheet_data**: {smartsheet_data}"

    integration_data = IntegrationService().fetchProjectDataforIntegration(tenant_id=tenantID, project_id=project_id)
    new_summary = json.dumps(integration_data, indent=2)

    appLogger.info({"event": "start_3", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})

    prompt = create_review_project(
        project_info=project_data,
        previous_week_status_updates=previous_week_status_updates,
        p2p_week_status_updates=two_weeks_before_status_updates,
        milestone_data=milestone_data,
        org_info_string=org_info_string,
        jira_data=None,
        smartsheet_data=None,
        integration_data=integration_data,
    )
    print("prompt for service_assurance::create_review_report_for_project 1 ========", prompt.formatAsString())

    model_opts_1 = ModelOptions(model="gpt-4.1", max_tokens=16000, temperature=0)
    response = llm.run(prompt, model_opts_1, 'agent::service_assurance::create_review_report_for_project', {"tenant_id": tenantID, "user_id": userID})
    print("service_assurance::create_review_report_for_project 1 ========", response)
    response = extract_json_after_llm(response)

    appLogger.info({"event": "start_4", "tenant_id": tenantID, "user_id": userID, "function": "create_review_report_for_project"})
    socketio.emit("service_assurance_agent", {"event": "create_project_review_screen::data", "project_id": project_id, "data": response}, room=client_id)



CREATE_PROJECT_REVIEW_REPORT = AgentFunction(
    name="create_review_report_for_project",
    description="",
    args=[],
    return_description='',
    function=create_review_report_for_project,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)