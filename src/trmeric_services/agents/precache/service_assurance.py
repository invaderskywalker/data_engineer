from src.trmeric_database.dao import ProjectsDao, TangoDao
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from .s_a_prompt import *
from src.trmeric_utils.json_parser import *
from .caching_users import CachingUsers
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data, get_smartsheet_data
from src.trmeric_api.logging.AppLogger import appLogger

from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.integration.IntegrationService import IntegrationService

import os


from datetime import date, datetime

def _parse_date(d):
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d).date()
        except Exception:
            return None
    return None


def compute_project_timeline_metrics(start_date, end_date):
    today = date.today()

    start_date = _parse_date(start_date)
    end_date = _parse_date(end_date)

    if not start_date or not end_date:
        return {
            "timeline_valid": False
        }

    total_duration_days = (end_date - start_date).days
    days_elapsed = (today - start_date).days
    days_remaining = (end_date - today).days

    return {
        "timeline_valid": True,
        "total_duration_days": total_duration_days,
        "days_elapsed": max(days_elapsed, 0),
        "days_remaining": days_remaining,
        "days_overdue": abs(days_remaining) if days_remaining < 0 else 0,
        "is_past_end_date": days_remaining < 0,
        "progress_time_percent": round(
            (days_elapsed / total_duration_days) * 100, 2
        ) if total_duration_days > 0 else None
    }


class ServiceAssurancePrecache:
    def __init__(self, tenant_id, user_id, init=True, force=False):
        print("init ServiceAssurancePrecache", tenant_id, user_id)
        appLogger.info({"event": "ServiceAssurancePrecache_init", "user_id": user_id, "tenant_id": tenant_id })

        self.tenant_id = tenant_id
        self.env_check = os.getenv("ENVIRONMENT")
        self.user_id = user_id
        self.data = None
        self.force = force
        self.init = init
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=10000,
            temperature=0.1
        )
        self.env_check = os.getenv("ENVIRONMENT")
        # self.env_check = "qa"
        appLogger.info({"event": "ServiceAssurancePrecache_init_2", "user_id": user_id, "tenant_id": tenant_id, "init": init })

        # if init:
        #     self.initializeData()

    def checkIfShouldPreCache(self, project_id):
        # print("checkIfShouldPreCache debug ---- ",self.user_id )
        if self.env_check == 'dev':
            # if self.user_id == '301':
            # return True
            return False
        else:
            project_statuses = ProjectsDao.fetchProjectStatuses(project_id)
            key = f'SERVICE_ASSURANCE_AGENT_UPDATE_STATUS_DATA_FOR_PROJECT_{project_id}'
            tango_states = TangoDao.fetchTangoStatesTenant(
                tenant_id=self.tenant_id, key=key)
            if (len(tango_states) == 0):
                return True
            if (len(project_statuses) == 0):
                return True
            if project_statuses[0]["created_date"] >= tango_states[0]["created_date"]:
                return True
            return False

    def initializeDataV2(self, project_id,sender=None):
        print("in initializeDataV2 ", project_id)
        appLogger.info({"event": "ServiceAssurancePrecache_initializeData_v2","user_id": self.user_id, "tenant_id": self.tenant_id, "project_id": project_id})

        # create precache data
        try:
            project_details = ProjectsDao.fetch_project_details_for_service_assurance(project_id=project_id)
            # print("project_details", project_details)
            project_statuses = ProjectsDao.fetchProjectStatuses(project_id)
            milestone_data = ProjectsDao.fetchProjectMilestones(project_id)
            project_formatted_data = self.projectFormattedDataV2(
                project_id, 
                project_details, 
                project_statuses, 
                milestone_data
            )

            project_formatted_data["statuses"] = project_statuses

            project_fetch_latest_status = ProjectsDao.fetchProjectLatestStatusUpdate(project_id)
            
            integration_data = IntegrationService().fetchProjectDataforIntegration(tenant_id =self.tenant_id, project_id=project_id )
            new_summary = json.dumps(integration_data, indent=2)
            
            prompt = createDataForUpdateStatusAgent_v2(project_data_with_status=project_formatted_data, integration_data=new_summary)

            # print("debug prompt initializeData ", prompt.formatAsString())
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "ServiceAssurancePrecache",
                logInDb={
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                }
            )
            print("debug prompt output ", response)
            project_json_data = extract_json_after_llm(response,step_sender=sender)
            project_json_data["project_title"] = project_details[0].get("title")
            project_json_data["project_id"] = project_id
            project_json_data["project_start_date"] = project_details[0].get(
                "project_start_date")
            project_json_data["project_end_date"] = project_details[0].get(
                "project_end_date")
            project_json_data["current_status_data"] = project_fetch_latest_status
            self.cacheDataForThisUser(project_id, project_json_data)
            return project_json_data
        except Exception as e:
            print('--debug error in initializeDataV2-------', str(e))
            appLogger.error({'event': 'initializeDataV2', 'error': str(e), 'traceback': traceback.format_exc()})

    def cacheDataForThisUser(self, project_id, project_json_data):
        TangoDao.insertTangoState(
            self.tenant_id,
            self.user_id,
            f"SERVICE_ASSURANCE_AGENT_UPDATE_STATUS_DATA_FOR_PROJECT_{project_id}",
            json.dumps(project_json_data),
            ""
        )

    def projectFormattedData(self, project_id, project_details, project_statuses):
        # print("data ------------ ", project_id, project_details, project_statuses)
        # print()
        formatted_data = {
            "project_id": project_id,
            "title": project_details[0].get("title", "Unknown"),
            "project_description": project_details[0].get("project_description", "Unknown"),
            "project_objectives": project_details[0].get("project_objectives", ""),
            "start_date": project_details[0].get("project_start_date", "Unknown"),
            "end_date": project_details[0].get("project_end_date", "Unknown"),
            # "location": project_details[0].get("project_location", "Unknown"),
            # "type": project_details[0].get("project_type", "Unknown"),
            # "methodology": project_details[0].get("sdlc_method", "Unknown"),
            # "budget": project_details[0].get("project_budget", 0.0),
            "tech_stack": project_details[0].get("tech_stack", "Unknown"),
            "key_results": [kr for kr in project_details[0].get("key_results", []) if kr],
            "milestones": project_details[0].get("milestones", []),
            "statuses": self.cleanAndLimitStatuses(project_statuses, limit=10),
            "actual_spend": self.calculateMilestoneSpend(project_details[0].get("milestones", []), "actual_spend"),
            "planned_spend": self.calculateMilestoneSpend(project_details[0].get("milestones", []), "planned_spend")
        }
        # print("Formatted Data:", formatted_data)
        formatted_data = self.formatProjectAsText(formatted_data)
        # print("Formatted Data V2:", formatted_data)
        return formatted_data

    def projectFormattedDataV2(self, project_id, project_details, project_statuses, milestone_data):
        # print("data ------------ ", project_id, project_details, project_statuses)
        # print()
        timeline_metrics = compute_project_timeline_metrics(
            project_details[0].get("project_start_date"),
            project_details[0].get("project_end_date")
        )
        formatted_data = {
            "project_id": project_id,
            "title": project_details[0].get("title", "Unknown"),
            "project_description": project_details[0].get("project_description", "Unknown"),
            "project_objectives": project_details[0].get("project_objectives", ""),
            "start_date": project_details[0].get("project_start_date", "Unknown"),
            "end_date": project_details[0].get("project_end_date", "Unknown"),
            "timeline_metrics": timeline_metrics,
            # "location": project_details[0].get("project_location", "Unknown"),
            # "type": project_details[0].get("project_type", "Unknown"),
            # "methodology": project_details[0].get("sdlc_method", "Unknown"),
            # "budget": project_details[0].get("project_budget", 0.0),
            "tech_stack": project_details[0].get("tech_stack", "Unknown"),
            "key_results": [kr for kr in project_details[0].get("key_results", []) if kr],
            "milestones": milestone_data,
            "statuses": self.cleanAndLimitStatuses(project_statuses, limit=10),
            "actual_spend": self.calculateMilestoneSpend(project_details[0].get("milestones", []), "actual_spend"),
            "planned_spend": self.calculateMilestoneSpend(project_details[0].get("milestones", []), "planned_spend")
        }
        # print("Formatted Data:", formatted_data)
        # formatted_data = self.formatProjectAsText(formatted_data)
        # print("Formatted Data V2:", formatted_data)
        return formatted_data

    def cleanAndLimitStatuses(self, statuses, limit=10):
        """
        Clean and limit the project statuses to the latest `limit` entries.
        """
        sorted_statuses = sorted(statuses, key=lambda x: x.get(
            "created_date", ""), reverse=True)
        limited_statuses = sorted_statuses[:limit]
        cleaned_statuses = []
        for status in limited_statuses:
            cleaned_status = {
                "type": status.get("type", "Unknown"),
                "value": status.get("value", "Unknown"),
                "comment": status.get("comment", "No comment"),
                "created_date": self.formatDate(status.get("created_date", "Unknown"))
            }
            cleaned_statuses.append(cleaned_status)

        return cleaned_statuses

    def calculateMilestoneSpend(self, milestones, spend_type):
        """
        Calculate the total spend (actual or planned) from milestones.
        """
        return sum(milestone.get(spend_type, 0) for milestone in milestones if milestone.get(spend_type) is not None)

    def formatDate(self, date_str):
        """
        Format the date string into a simpler format (e.g., YYYY-MM-DD).
        """
        try:
            from datetime import datetime
            return datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
        except ValueError:
            return "Unknown"

    def formatProjectAsText(self, formatted_data):
        key_results_text = "\n".join(
            f"- {kr}" for kr in formatted_data["key_results"]) or "None"
        milestones_text = "\n".join(
            f"- {milestone.get('name', 'Unknown')} (Target Date: {milestone.get('target_date', 'None')}, "
            f"Actual Spend: {milestone.get('actual_spend', 'None')}, Planned Spend: {milestone.get('planned_spend', 0)})"
            for milestone in formatted_data["milestones"]
        ) or "None"
        statuses_text = "\n".join(
            f"- {status.get('type', 'Unknown')}: {status.get('value', 'Unknown')} "
            f"({status.get('created_date', 'Unknown')}) - {status.get('comment', 'No comment')}"
            for status in formatted_data["statuses"]
        ) or "None"

        # Combine all the data
        formatted_text = (
            f"Project ID: {formatted_data['project_id']}\n"
            f"Title: {formatted_data['title']}\n"
            f"Description: {formatted_data['project_description']}\n"
            f"Objectives: {formatted_data['project_objectives']}\n"
            f"Start Date: {formatted_data['start_date']}\n"
            f"End Date: {formatted_data['end_date']}\n"
            f"Tech Stack: {formatted_data['tech_stack']}\n\n"
            f"Key Results:\n{key_results_text}\n\n"
            f"Milestones:\n{milestones_text}\n\n"
            f"Statuses:\n{statuses_text}\n\n"
            f"Actual Spend: {formatted_data['actual_spend']}\n"
            f"Planned Spend: {formatted_data['planned_spend']}"
        )
        return formatted_text
