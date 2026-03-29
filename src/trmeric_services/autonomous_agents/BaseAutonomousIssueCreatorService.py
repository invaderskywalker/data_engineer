
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
import os


class BaseAutonomousIssueCreatorService:
    def __init__(self, tenant_id, user_id):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions( #not in use
            model="gpt-4-turbo",
            max_tokens=4096,
            temperature=0
        )
        self.modelOptionsFast = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0
        )
        self.logInfo = {
            "tenant_id": tenant_id,
            "user_id": user_id
        }
        self.user_id = user_id
        self.basePath = f"all_data_creation/jira_issues_create_data/"
        self.milestones_and_tasks_breakdown_file_path = f"{self.basePath}milestones_and_tasks_breakdown_{self.user_id}.json"
        self.updated_milestones_and_tasks_breakdown_file_path = f"{self.basePath}updated_milestones_and_tasks_breakdown_file_path{self.user_id}.json"
        self.jira_issues_file_path = f"{self.basePath}jira_issues_{self.user_id}.json"
        self.jira_epics_file_path = f"{self.basePath}epics_{self.user_id}.json"

        self.create_nested_folders()

    def create_nested_folders(self):
        os.makedirs(self.basePath, exist_ok=True)
