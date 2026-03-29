from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.agents.functions.onboarding.utils.enhance import CreationEnhancer
from src.trmeric_services.journal.Activity import activity, record
import requests
import os
import re
import json
from datetime import datetime


class AutomousProjectAgent:
    def __init__(self):
        self.projectService = ProjectService()
        self.create_project_url = os.getenv(
            "DJANGO_BACKEND_URL") + "api/projects/tango/create"

    def format_json_for_request(self, input_json, userId, tenantId):
        team_info = input_json.get("team", [])

        if team_info == []:
            team_info = [{"name": "", "pm_id": str(userId), "milestones": []}]
        else:
            for team_info_part in team_info:
                team_info_part["pm_id"] = userId

        start_date = input_json.get("start_date", None)
        end_date = input_json.get("end_date", None)

        def validate_date(date_str):
            # Regex to match "YYYY-MM-DD" format
            pattern = r"^\d{4}-\d{2}-\d{2}$"
            if isinstance(date_str, str) and re.match(pattern, date_str):
                return date_str
            pattern2 = r"^\d{2}-\d{2}-\d{2}$"
            if isinstance(date_str, str) and re.match(pattern2, date_str):
                # Convert YY-MM-DD to YYYY-MM-DD
                year, month, day = date_str.split('-')
                return f"20{year}-{month}-{day}"
            # If the date string does not match either format, return None
            return None

        # Validate start_date and end_date
        start_date = validate_date(input_json.get("start_date", None))
        end_date = validate_date(input_json.get("end_date", None))

        tech_stack = input_json.get("technology_stack", None)
        if tech_stack == []:
            tech_stack = None
            
        if isinstance(input_json.get("scope"), list):
            input_json["scope"] = ", ".join(input_json["scope"])

        input_json["start_date"] = start_date
        input_json["end_date"] = end_date
        input_json["team"] = team_info
        input_json["user_id"] = userId
        input_json["tenant_id"] = tenantId
        input_json["technology_stack"] = tech_stack

        return input_json

    def format_json_for_request_source(self, input_json, userId, tenantId):
        team_info = input_json.get("team", [])

        if team_info == []:
            team_info = [{"name": "", "milestones": []}]

        start_date = input_json.get("start_date", None)
        end_date = input_json.get("end_date", None)

        def validate_date(date_str):
            # Regex to match "YY-MM-DD" format
            pattern = r"^\d{2}-\d{2}-\d{2}$"
            if isinstance(date_str, str) and re.match(pattern, date_str):
                return date_str
            return None

        # Validate start_date and end_date
        start_date = validate_date(input_json.get("start_date", None))
        end_date = validate_date(input_json.get("end_date", None))

        tech_stack = input_json.get("technology_stack", None)
        if tech_stack == []:
            tech_stack = None

        input_json["start_date"] = start_date
        input_json["end_date"] = end_date
        input_json["team"] = team_info
        input_json["technology_stack"] = tech_stack

        return input_json

    @activity("onboarding::project::enhance_project")
    def enhance_project(self, llm, input_json, user_id, tenant_id):
        record("input_data", input_json)
        record("description", "Takes the Tango JSON created for a user from their sources, and enhances it using Tango and web information.")
        input_json, input_json_source = CreationEnhancer(llm=llm, input_data=input_json, enhance_type="project", tenant_id=tenant_id, user_id=user_id).enhance()
        record("output_data", input_json_source)
        return input_json, input_json_source

    def create_project(self, tenant_id, user_id, input_json, llm):
        headers = {
            'Content-Type': 'application/json'
        }

        input_json, input_json_source = self.enhance_project(llm, input_json, user_id, tenant_id)

        print("debug --new enhance input_json--- ", input_json)
        request_data = self.format_json_for_request(
            input_json=input_json, userId=user_id, tenantId=tenant_id)

        request_data_source = self.format_json_for_request_source(
            input_json=input_json_source, userId=user_id, tenantId=tenant_id)

        print("debug --- ", request_data)
        response = requests.post(
            self.create_project_url, headers=headers, json=request_data)
        # Print the response (status code and content)
        print("Status Code:", response.status_code)
        print("Response Content:", response.text)

        # print(request_data_source)

        ret_val = f"""
            Success or failure of this method
            Please analyse from this Response status: {response.status_code}
            and Response Text:  {response.text}
            
            If there is an error in creating the Project then respond with a meaningful response to the user
            
            Highlight the Project title
        """

        if response.status_code != 201:
            request_data_source = None

        return (request_data_source, ret_val)

    def only_request_creation(self, request_data, userId, tenantId):
        headers = {
            'Content-Type': 'application/json'
        }
        team_info = request_data.get("team", [])
        if team_info == []:
            team_info = [{"name": "", "pm_id": str(userId), "milestones": []}]
        else:
            for team_info_part in team_info:
                team_info_part["pm_id"] = userId
                team_info_part["milestones"] = []

        # Map key_results → kpis for API compatibility
        if "key_results" in request_data:
            request_data["kpis"] = [
                {
                    "name": kr["key_result"],
                    "baseline_value": kr["baseline_value"]
                } for kr in request_data["key_results"]
            ]
        else:
            request_data["kpi"] = request_data.get("kpis", [])

        # Add user and tenant info
        request_data["user_id"] = userId
        request_data["tenant_id"] = tenantId

        # ✅ Auto-fill start_date and end_date with today's date if missing or empty
        today = datetime.now().strftime("%Y-%m-%d")
        if not request_data.get("start_date"):
            request_data["start_date"] = today
        if not request_data.get("end_date"):
            request_data["end_date"] = today

        # Ensure KPI key is consistent
        request_data["kpi"] = request_data.get("kpis")

        print("request --- data for create project --- ", request_data)

        try:
            response = requests.post(
                self.create_project_url,
                headers=headers,
                json=request_data
            )
            print("Status Code:", response.status_code)

            response_data = response.json()
            print("Response JSON:", response_data)

            if response_data.get("status") == "success" and response_data.get("data"):
                project_data = response_data["data"][0]
                return {
                    "message": "success",
                    "project_id": project_data.get("id"),
                    "data": request_data
                }
            else:
                print("Error: API response indicates failure or no data")
                return None

        except json.JSONDecodeError:
            print("Error: Response is not valid JSON")
            return None
        except Exception as e:
            print(f"Error processing response: {e}")
            return None
