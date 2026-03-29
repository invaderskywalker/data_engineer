



from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.constants import PROJECT_TYPES
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao
import traceback
from src.trmeric_database.Database import db_instance
from .prompts import *
from datetime import datetime



class KnowledgeV1:
    def __init__(self, 
                #  tenant_id, user_id
                 ):
        # self.tenant_id = tenant_id
        # self.user_id = user_id
        # self.log_info = {
        #     "tenant_id": tenant_id,
        #     "user_id": user_id
        # }
        self.log_info = None
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=8000,
            temperature=0.4
        )

    
    def create(self, project_id):
        print("KnowledgeV1 create 1", project_id)
        ## step1
        # project_basic_data = ProjectsDao.fetchBasicInfoForKnwoeldgeLayer(project_id=project_id)
        
        
        
        
        project_details = ProjectsDao.fetch_project_details_for_knowledge_layer(project_id=project_id)[0]
        project_statuses = ProjectsDao.fetchProjectStatuses(project_id=project_id)
        project_details["status"]= project_statuses
        project_details["status_summary"] = ProjectsDao.fetchProjectStatusSummary(project_id=project_id)
        project_details["team_data"] = ProjectsDao.fetchProjectTeamDetailsV2(project_id=project_id)
        
        
        classify_response = self.llm.run(
            category_decider_prompt(project_data=project_details),
            options=self.modelOptions,
            function_name="knowledge::v1::category_decider",
            logInDb=self.log_info
        )
        print("category_decider_prompt response", classify_response)
        classification_result = extract_json_after_llm(classify_response)
        # print("category_decider_prompt response", classification_result)
        classification_result = classification_result.get("categories", "") or ""
        
        # print("KnowledgeV1 create classification_result", classification_result)
        # return
        
        ## step2
        project_retro_details = ProjectsDao.getRetroAnalysisForProject(project_id=project_id)
        outcome_response = self.llm.run(
            outcome_decider_prompt(
                project_data=project_details, 
                project_retro=project_retro_details
            ),
            options=self.modelOptions,
            function_name="knowledge::v1::outcome_decider",
            logInDb=self.log_info
        )
        outcome_response = extract_json_after_llm(outcome_response)
        outcome_class = outcome_response.get("outcome", "") or ""
        outcome_details = outcome_response.get("detailed_analysis", "") or ""
        
        
        print("KnowledgeV1 create project_retro_details", outcome_response)
        print("retro and project details ", project_details, project_retro_details)
        # return
        
        for category in classification_result:
            existing_insight = KnowledgeDao.fetchKnowledgeV1DataForProjectTypeAndOutcome(project_type=category, outcome=outcome_class)
            
            ### step3
            
            
            outcome_response = self.llm.run(
                knowledge_insight_creator_prompt(
                    project_detailed_data=project_details, 
                    project_type=category,
                    project_retro=project_retro_details,
                    project_outcome=outcome_class,
                    outcome_details=outcome_details,
                    existing_insight=existing_insight
                ),
                options=self.modelOptions,
                function_name="knowledge::v1::knowledge_insight",
                logInDb=self.log_info
            )
            
            print("KnowledgeV1 create outcome_response", outcome_response)
            
            ## save all
            
            # Save to tango_projectanalysis
            insert_project_analysis_query = """
                INSERT INTO tango_projectanalysis (project_id, project_type, outcome, details, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            params = (project_id, category, outcome_class, outcome_details, datetime.now(), datetime.now())
            db_instance.executeSQLQuery(insert_project_analysis_query, params)
            
            upsert_knowledge_query = """
                INSERT INTO tango_knowledge (project_type, outcome, insight, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (project_type, outcome)
                DO UPDATE SET
                    insight = EXCLUDED.insight,
                    updated_at = EXCLUDED.updated_at;
            """
            params = (category, outcome_class, outcome_response, datetime.now(), datetime.now())
            db_instance.executeSQLQuery(upsert_knowledge_query, params)
        return ""
        

        
        
        
        
        
        
        