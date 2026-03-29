from typing import Dict, Any, List
from src.trmeric_database.dao import IntegrationDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.integration.Jira import Jira
from src.trmeric_services.integration.RefreshTokenService import RefreshTokenService
from src.trmeric_api.logging.AppLogger import appLogger
import json
import threading
import traceback
from datetime import datetime
from src.trmeric_services.agents.functions.roadmap_analyst.actions import Analystactions
import pandas as pd
import re

def clean_text(text):
    """Clean text by replacing problematic characters."""
    if isinstance(text, str):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Replace non-ASCII characters
        text = text.replace('¬†', ' ').replace('‚Äã', '')  # Replace specific artifacts
        return text.strip()
    return text

class RoadmapCreator:
    def __init__(self, tenant_id: str, user_id: str, input_file_path: str = "issues.json"):
        """
        Initialize RoadmapCreator with tenant_id, user_id, and input file path.
        
        Args:
            tenant_id (str): Tenant identifier.
            user_id (str): User identifier.
            input_file_path (str, optional): Path to the JSON file containing issues. Defaults to "issues.json".
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.input_file_path = input_file_path
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        
        # # Initialize Jira instance with refreshed access token
        # token = RefreshTokenService().refreshIntegrationAccessToken(tenant_id, user_id, "jira")
        # self.jira_instance = Jira(
        #     project_id="",
        #     accessToken=token["access_token"],
        #     metadata={},
        #     tenant_id=tenant_id,
        #     user_id=user_id
        # )
        
        try:
            token = RefreshTokenService().refreshIntegrationAccessToken(tenant_id, user_id, "jira")
        except Exception as e:
            print("error ", e)
            token = {"access_token": ""}
            
        accessToken = token.get("access_token") or "" if token else ""
        # module = metadata.get("module") or None
        try:
            self.jira_instance = Jira(
                project_id="", 
                accessToken=accessToken, 
                metadata={}, 
                tenant_id=tenant_id, 
                user_id=user_id
            )
        except Exception as e:
            print("error in initiating jira instance", e)
            self.jira_instance = None
            
        self.csv_file_path = "roadmap_sheet.csv"
        
            

    def process_issues_for_roadmaps(self, mode="jira") -> List[Dict[str, Any]]:
        if (mode == "sheet"):
            return self.process_sheet_for_roadmap_creation()
        results = []

        # Step 1: Read the JSON file
        try:
            with open(self.input_file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            appLogger.error({
                "function": "process_issues_for_roadmaps",
                **self.logInfo,
                "error": f"Input file {self.input_file_path} not found"
            })
            return [{"error": f"Input file {self.input_file_path} not found"}]
        except json.JSONDecodeError as e:
            appLogger.error({
                "function": "process_issues_for_roadmaps",
                **self.logInfo,
                "error": f"Invalid JSON in {self.input_file_path}: {str(e)}"
            })
            return [{"error": f"Invalid JSON in {self.input_file_path}: {str(e)}"}]

        # Step 2: Extract issues (assuming issues are under a key like "DSE")
        issues = next(iter(data.values()), [])  # Get the first list of issues (e.g., data["DSE"])
        print("all issues --- length --- ", len(issues))
        # Step 3: Process each issue
        counter = 0
        for issue in issues:
            counter += 1
            # if counter <=7 :
            #     continue
            # if counter > 8:
            #     break
            key = issue.get("key")
            name = issue.get("name", key)
            issue_type = issue.get("issuetype", {}).get("name", "Unknown")
            labels = issue.get("labels", [])

            if not key:
                appLogger.error({
                    "function": "process_issues_for_roadmaps",
                    **self.logInfo,
                    "error": f"Missing key for issue: {issue}"
                })
                results.append({"item_key": key or "unknown", "item_name": name, "error": "Missing key"})
                continue

            try:
                # Step 4: Fetch additional details from Jira
                item_input = {"key": key, "tag": "issue", "name": name}
                jira_issue_data = self.jira_instance.fetch_and_analyze_kanban_item(item_input)
                # jira_issue_data["capabilities"] = labels
                print("jira issue data --- ", json.dumps(jira_issue_data, indent=2))
                actions_class = Analystactions(tenant_id=self.tenant_id, user_id=self.user_id)
                conv_data = f"""
                A jira issue will be used to create a roadmap:
                data: {jira_issue_data}.
                
                Add the {labels} in the roadmap capabilities.
                Force title of roadmap to -- {name}
                
                You have to read this data. and create a roadmap with beautiful description and all attributes beautifully
                """
                roadmap_result = actions_class.create_roadmaps(
                    conv_data, 
                    {
                        "category": labels,
                        "title": name
                    }, 
                    True
                )
                print("roadmap result ", roadmap_result)


            except Exception as e:
                appLogger.error({
                    "function": "process_issues_for_roadmaps",
                    **self.logInfo,
                    "item_key": key,
                    "error": f"Error processing issue {key}: {str(e)}",
                    "traceback": traceback.format_exc()
                })
                results.append({
                    "item_key": key,
                    "item_name": name,
                    "item_type": issue_type,
                    "error": f"Error processing issue: {str(e)}"
                })

        return results



    def process_sheet_for_roadmap_creation(self, session_state: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Process projects from a spreadsheet file (e.g., Excel) row by row.
        
        Args:
            session_state (Dict[str, Any], optional): Session state with additional configuration.
        
        Returns:
            List[Dict[str, Any]]: List of results for each processed row, including success or error details.
        """
        results = []
        session_state = session_state or {}

        # Step 1: Load the CSV file
        try:
            df = pd.read_csv(self.csv_file_path, encoding='utf-8')
        except FileNotFoundError:
            appLogger.error({
                "function": "process_items_from_sheet",
                **self.logInfo,
                "error": f"Input file {self.csv_file_path} not found"
            })
            return [{"error": f"Input file {self.csv_file_path} not found"}]
        except Exception as e:
            appLogger.error({
                "function": "process_items_from_sheet",
                **self.logInfo,
                "error": f"Error reading {self.csv_file_path}: {str(e)}"
            })
            return [{"error": f"Error reading {self.csv_file_path}: {str(e)}"}]


        print(f"Processing {len(df)} rows from sheet")
        
        # Step 2: Process each row
        for index, row in df.iterrows():
            
            issue_key = row.get('Issue key', '') or ''
            summary = row.get('Summary')
            description = row.get('Description', '')
            portfolio = row.get('Termeric Portfolio', '')
            roadmap_name = row.get('Roadmap Name', '') or None

            # Combine summary and issue key for project name
            project_name = f"{roadmap_name} - {issue_key}".strip()
            # if roadmap_name:
            #     project_name = f"{roadmap_name} - {issue_key}".strip()
            # else:
            #     project_name = f"{summary}".strip()
                
            project_description = f"{row}"

            project_description = clean_text(project_description)
            project_name = clean_text(project_name)
            
            actions_class = Analystactions(tenant_id=self.tenant_id, user_id=self.user_id)
            conv_data = f"""
            A sheet row data will be used to create a roadmap:
            data: {project_description}.
            
            Force title of roadmap to -- {project_name}
            
            You have to read this data. 
            and create a roadmap with beautiful description 
            and all attributes beautifully.
            """
            try:
                roadmap_result = actions_class.create_roadmaps(
                    conv_data, 
                    {
                        "title": project_name
                    },
                )
                print("roadmap result ", roadmap_result)
                results.append(f"Name- {project_name} created")

                
            except Exception as e:
                appLogger.error({
                    "function": "process_items_from_sheet",
                    **self.logInfo,
                    "item_key": issue_key,
                    "error": f"Error processing row {index} with key {issue_key}: {str(e)}",
                    "traceback": traceback.format_exc()
                })
                results.append({
                    "item_key": issue_key,
                    "item_name": project_name,
                    "item_type": "sheet_roadmap",
                    "error": f"Error processing row: {str(e)}"
                })

        return results
    