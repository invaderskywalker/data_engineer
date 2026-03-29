from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_database.Database import db_instance
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_database.models import ProjectsKnowledgeModel


class KnowledgeBase:
    def __init__(self):
        self.db_instance = db_instance
        self.llm_service = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0
        )
        
    def save_project_knowledge(self, tenant_id, _type, portfolio_id, knowledge_summary):
        """_summary_

        Args:
            tenant_id (_type_): _description_
            portfolio_id (_type_): _description_
            knowledge_summary (_type_): _description_
        """
        existing_project_knowledge = ProjectsKnowledgeModel.get_or_none(
            tenant_id=tenant_id,
            portfolio_id=portfolio_id,
            type=_type
        )
        print("save_project_knowledge ")

        if existing_project_knowledge:
            existing_project_knowledge.knowledge_summary = knowledge_summary
            existing_project_knowledge.save()
            print("Updated entry ")
        else:
            project_knowledge = ProjectsKnowledgeModel(
                tenant_id=tenant_id,
                portfolio_id=portfolio_id,
                type=_type,
                knowledge_summary=knowledge_summary
            )
            project_knowledge.save(force_insert=True)
            print("Saved entry ")
