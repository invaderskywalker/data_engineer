from src.trmeric_database.dao import ProjectsDaoV2
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_services.project.Prompts import createOrgStrategiesPrompt
from src.trmeric_utils.json_parser import extract_json_after_llm
import json


class JobOrgStrategyCreator:
    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=1000,
            temperature=0.1
        )
        

    def process_projects(self):
        projects_to_update = ProjectsDaoV2.fetch_all_child_projects(
            tenant_id=self.tenant_id, 
            include_archived=True
        )
        print("projects_to_update ", projects_to_update)
        projects_data = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
            project_ids=projects_to_update, 
            projection_attrs=["id", "title", "description", "objectives"]
        )
        default_list = ["1-Financial Targets", "2-Nextgen Technology", "3-People Product & Planet"]
        for data in projects_data:
            prompt = createOrgStrategiesPrompt(data, default_list)
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "process_projects::create::org_strategies",
                logInDb=self.logInfo
            )
            json_org_strategies = extract_json_after_llm(response)
            print("debug --- org_strategies ", json.dumps(json_org_strategies, indent=2) )
            
            strategies = json_org_strategies.get("suitable_org_strategies", [])
            strategy_string = ", ".join(strategies)
            ProjectsDaoV2.update_org_strategy(data["id"], strategy_string)
    
            # break
            ## write the code to update after this whole thing
            
        
        
        
        
        
