# src/trmeric_services/agents/notify/service_assurnace_agent_analysis.py
import datetime
from ..base import BaseNotifyAgent
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.notify.prompts.service_assurance_agent import *
from src.trmeric_database.dao import ProjectsDao, TangoDao, IntegrationDao, UsersDao, ProjectsDaoV2
from src.trmeric_services.agents.notify.constants import * 
from src.trmeric_utils.html_formatter import *
from src.trmeric_utils.api import ApiUtils
import html



class ServiceAssuranceNotificationAnalyst(BaseNotifyAgent):
    def __init__(self, tenant_id, user_id):
        super().__init__("ServiceAssuranceNotificationAnalyst", tenant_id, user_id)
    
    # def create_analysis(self, project_data):
    #     """
    #     Generates a service assurance report by analyzing project data and fetching web insights.

    #     Args:
    #         project_data (dict): Structured project data with stage information.
    #         self.logInfo (bool): Whether to log the LLM input in the database (default: False).

    #     Returns:
    #         str: Markdown report.
    #     """
    #     # Step 1: Decide web queries
    #     query_prompt = create_web_query_prompt(project_data)
    #     print("query prompt ", query_prompt.formatAsString())
    #     query_response = self.llm.run(
    #         query_prompt,
    #         options=self.modelOptions,
    #         function_name="ServiceAssuranceNotificationAnalyst::generateIdeas",
    #         logInDb=self.logInfo
    #     )
    #     print("query prompt response ", query_response)
    #     web_queries = extract_json_after_llm(query_response)  # Expecting a list of queries
    #     print("query prompt response 2 ", web_queries)
    #     # Step 2: Fetch web data
    #     # project_type = "SAP migration" if "sap" in project_data["name"].lower() else project_data["name"].split()[0].lower()
    #     project_type = project_data["name"].lower()
    #     project_insights = self.websearch_agent.get_project_insights(project_type)
    #     industry_trends = self.websearch_agent.get_industry_trends(project_type)
    #     extra_results = [self.websearch_agent.query_search_engine(query) for query in web_queries]

    #     # Add web insights to project_data
    #     project_data["web_insights"] = {
    #         "best_practices": project_insights["insights"],
    #         "trends": industry_trends["trends"],
    #         "extra": [result["snippet"] for sublist in extra_results for result in sublist]
    #     }
        
    #     # print("project data ", project_data)

    #     # Step 3: Generate the report
    #     report_prompt = create_service_assurance_prompt(project_data, web_queries)
    #     print("report_prompt ", report_prompt.formatAsString())
    #     report_response = self.llm.run(
    #         report_prompt,
    #         options=self.modelOptions,
    #         function_name="ServiceAssuranceNotificationAnalyst::analysis",
    #         logInDb=self.logInfo
    #     )
    #     print("report_prompt  response", report_response)
    #     return report_response
    
    def create_end_date_analysis(self, projects_by_pms):
        for item in projects_by_pms:
            print("debug ---- ", item)
            project_manager_id = item["project_manager_id"]
            pm_info = UsersDao.fetchUserInfoWithId(user_id=project_manager_id)
            print("debug ---- ", pm_info)
            project_ids = item["project_ids"]
            data = ProjectsDao.findProjectMilestonesAndRisk(project_ids)
            
            prompt = create_notification_prompt_for_end_date_close(project_data=data)
            print("prompt ---- ", prompt.formatAsString())
            response = self.llm.run(
                prompt,
                options=self.modelOptions,
                function_name="ServiceAssuranceNotificationAnalyst::classifyProject",
                logInDb=self.logInfo
            )
            clean_res = clean_html(html_content=response)
            print("response --- ", clean_res)
            ## trigger mail
            ApiUtils().send_notification_mail_api(email_content=clean_res, receiver_email=pm_info.get("email"))
            
            
        
    
    def create_analysis_v2(self, project_id):
        project_basic_data = ProjectsDao.fetchBasicInfoForServiceAssuranceNotifyAgent(project_id)
        classify_prompt = create_classification_prompt(project_basic_data)
        classify_response = self.llm.run(
            classify_prompt,
            options=self.modelOptions,
            function_name="ServiceAssuranceNotificationAnalyst::classifyProject",
            logInDb=self.logInfo
        )
        classification_result = extract_json_after_llm(classify_response)
        project_type = classification_result.get("project_type", "unknown")
        print("debug -- ", classify_response)
        
        
        
        # web_search_queries = CATEGORY_WEB_SEARCH_MAPPING[project_type]
        project_details = ProjectsDao.fetch_project_details_for_service_assurance(
            project_id=project_id
        )[0]
        project_statuses = ProjectsDao.fetchProjectStatuses(project_id)
        project_details["status"]= project_statuses
        
        web_search_prompt = create_web_source_finder(project_data=project_details, project_type=project_type)
        web_search_response = self.llm.run(
            web_search_prompt,
            options=self.modelOptions,
            function_name="ServiceAssuranceNotificationAnalyst::web_search",
            logInDb=self.logInfo
        )
        print("web_search_response", web_search_response)
        web_search_response = extract_json_after_llm(web_search_response)
        web_search_queries = web_search_response.get("relevant_sources", []) or []
        web_search_queries = web_search_queries[:2]
        search_results = [self.websearch_agent.query_search_engine(query, skip_source=True) for query in web_search_queries]
        
        # print("-------", search_results)
        # return
        
        
        
        prompt = create_insight_and_action_prompt(
            project_data=project_details, 
            web_queries=web_search_queries,
            web_insights_data=search_results,
            project_type=project_type
        )
        print("debug prompt -- ", prompt.formatAsString())
        
        response = self.llm.run(
            prompt,
            options=self.modelOptions,
            function_name="ServiceAssuranceNotificationAnalyst::analysis",
            logInDb=self.logInfo
        )
        print("debug prompt -- response")
        print(response)
        clean_res = clean_html(html_content=response)
        TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key=f"S_A_ANALYSIS_{project_id}", value=clean_res, session_id="")
        
        # InsightDao.save_daily_summary(tenant_id=self.tenant_id, header="Service Assurance Agent Analysis", label=clean_res, _type='Service Assurance Agent Analysis')
        
        
        
    def send_execution_update(self):
        project_ids = ProjectsDao.FetchAvailableProject(
            tenant_id=self.tenant_id, 
            user_id=self.user_id
        )
        print("project ids ", project_ids)
        user_info = UsersDao.fetchUserInfoWithId(user_id=self.user_id)
        data = []
        status_summary = {
            "red": 0,
            "green": 0,
            "amber": 0,
            "grey": 0
        }
        for pid in project_ids:
            project_data = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                project_ids=[pid],
                projection_attrs=["title", "start_date", "end_date"],
                tenant_id=self.tenant_id,
                include_archived=False,
                include_parent=False
            )
            
            status_data = ProjectsDao.fetchProjectLatestStatusUpdateV2(project_id=pid)
            ## if the statuses are unknown all. then we reject it
            scope = status_data.get("scope")
            delivery = status_data.get("delivery")
            spend = status_data.get("spend")
            # status_summary
            all_grey = False
            if scope == "unknown" and delivery == "unknown" and spend == "unknown":
                status_summary["grey"] += 1
                all_grey = True
            elif scope == "red" or delivery == "red" or spend == "red":
                status_summary["red"] += 1
            elif scope == "amber" or delivery == "amber" or spend == "amber":
                status_summary["amber"] += 1
            else:
                status_summary["green"] += 1
                
            if all_grey:
                continue
            
            integration_info = IntegrationDao.getIntegrationLatestUpdatedDataForIntegrationOfProjectId(project_id=pid)
            data.append({
                "project_id": pid,
                "project_title": project_data[0]["title"],
                "project_start_date": project_data[0]["start_date"],
                "project_end_date": project_data[0]["end_date"],
                "latest_status_update_data": status_data,
                "integration_info": integration_info
            })
            
        print("data -- ", data)
        print("--")
            

        prompt = weekly_projects_review(
            projects_data=data
        )
        
        response = self.llm.run(
            prompt,
            options=self.modelOptions,
            function_name="ServiceAssuranceNotificationAnalyst::weekly::review",
            logInDb=self.logInfo
        )
        print("debug prompt -- response")
        print(response)
        
        response_json = extract_json_after_llm(response)
        project_rows = response_json.get("projects")
        table_rows = ""
        
        
        def generate_header_name(key):
            """Convert a JSON key to a human-readable table header name."""
            # Handle snake_case (e.g., project_title → Project Title)
            
            def format_word(word: str) -> str:
                # Keep "and" lowercase, otherwise capitalize
                return word if word.lower() == "and" else word.capitalize()
    
            if '_' in key:
                return ' '.join(format_word(word) for word in key.split('_'))
            
            # Handle camelCase or other formats (e.g., lastUpdated → Last Updated)
            # Insert space before capital letters, then capitalize words
            key_with_spaces = re.sub(r'(?<!^)([A-Z])', r' \1', key)
            return ' '.join(format_word(word) for word in key_with_spaces.split())

        # Generate table headers dynamically
        table_headers = ""
        if project_rows:  # Check if there’s at least one project
            first_project = project_rows[0]
            header_cells = "".join(
                '<th style="padding: 10px; text-align: left; font-weight: bold; '
                'color: #ffffff; border: 1px solid #e0e0e0;">{}</th>'.format(
                    generate_header_name(key)
                )
                for key in first_project.keys()
            )
            table_headers = f'<tr style="background-color: #f4af3d;">{header_cells}</tr>'

        # Generate table rows with alternating colors
        table_rows = ""
        for index, project in enumerate(project_rows):
            status_color = {
                "Red": "#ff0000",
                "Yellow": "#ff9900",
                "Green": "#008000",
                "Unknown": "#333333"
            }.get(project["status"], "#333333")
            row_bg = "#fafafa" if index % 2 == 0 else "#ffffff"
            table_rows += (
                f'<tr style="background-color: {row_bg};">'
                f'<td style="padding: 10px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif; font-size: 14px; color: #333333;">{html.escape(project["project_title"])}</td>'
                f'<td style="padding: 10px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif; font-size: 14px; color: {status_color};">{html.escape(project["status"])}</td>'
                f'<td style="padding: 10px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif; font-size: 14px; color: #333333;">{html.escape(project["last_updated"])}</td>'
                f'<td style="padding: 10px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif; font-size: 14px; color: #333333;">{html.escape(project["integration_and_last_sync"])}</td>'
                f'<td style="padding: 10px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif; font-size: 14px; color: #333333;">{html.escape(project["status_reason"])}</td>'
                f'</tr>'
            )

        print("--")
        print(table_headers)
        print(table_rows)
        print("--")


        ApiUtils().send_notification_mail_api(
            email_content='',
            email_data={
                "PROJECT_TABLE_HEADERS": table_headers,
                "PROJECT_TABLE_ROWS": table_rows,
                "project_total_status_green": status_summary.get("green") or 0,
                "project_total_status_amber": status_summary.get("amber") or 0,
                "project_total_status_red": status_summary.get("red") or 0,
                "project_total_status_unknown": status_summary.get("grey") or 0,
            }, 
            receiver_email=user_info.get("email"),
            template_key='TANGO-WEEKLY-REVIEW'
        )
        
            
            
        