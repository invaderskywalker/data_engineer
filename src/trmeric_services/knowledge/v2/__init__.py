


from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao
import traceback
from src.trmeric_database.Database import db_instance
from .prompts import *
from datetime import datetime


class KnowledgeV2:
    def __init__(self, tenant_id):
        self.log_info = None
        self.tenant_id = tenant_id
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=8000,
            temperature=0.4
        )
        
    def create(self):
        print("KnowledgeV2 create start")
        projects_data = ProjectsDao.fetchProjectsDetailsForTenantGroupedByPortfolio(tenant_id=self.tenant_id)
        print("KnowledgeV2 data fetched for tenant ", self.tenant_id)
        for pd in projects_data:
            portfolio_id = pd.get("portfolio_id")
            print("creating knowledge for data: ",portfolio_id,  pd)
            response = self.llm.run(
                compress_knowledge_layer(portfolio_data=pd),
                options=self.modelOptions,
                function_name=f"knowledge::v2::portfolio_knowledge_creator_{portfolio_id}",
                logInDb=self.log_info
            )
            print("portfolio_knowledge_creator_ response", response)
            insert_knowledge = """
                INSERT INTO tango_portfolioknowledge (portfolio_id, tenant_id, knowledge, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s);
            """
            params = (portfolio_id, self.tenant_id, response, datetime.now(), datetime.now())
            db_instance.executeSQLQuery(insert_knowledge, params)
            
            