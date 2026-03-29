"""
    Creation of Projects Knowledge
"""
from src.trmeric_services.internal.knowledge.base import KnowledgeBase
from src.trmeric_database.dao.portfolios import PortfolioDao
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao
from src.trmeric_services.internal.knowledge.projects.prompt import *
# from .prompt import generate_summary_view_of_projects


class ProjectsKnowledge(KnowledgeBase):
    """_summary_

    Args:
        KnowledgeBase (_type_): _description_
    """
    def __init__(self):
        super().__init__()
        self.table_name = 'project_knowledge'

    def process_projects_in_portfolio(self, item):
        """
        item: {'portfolio_id': 116, 'portfolio_title': 'Trmeric AI', 'project_ids': [1730, 1731, 1728, 1729]}
        """
        projects_data = []
        for project_id in item.get("project_ids", []):
            if project_id is None:
                continue
            data = ProjectsDao.fetch_project_details(
                project_id=project_id
            )
            projects_data.extend(data)
        if len(projects_data) == 0:
            raise Exception("No projects")
        # print("---processProjectsInPortfolio--", projects_data)
        prompt = generate_summary_view_of_projects(
            portfolio_title=item.get("portfolio_title"), projects_data=projects_data)
        response = self.llm_service.run(prompt, self.modelOptions, "ProjectsKnowledge::portfolio", None)
        # print("--process_projects_in_portfolio--", response)
        # print("--process_projects_in_portfolio--")
        return response

    def extract_project_knowledge(self, tenant_id):
        """Fetches roadmap data, processes it with LLM, and saves it as knowledge."""
        print("extract_project_knowledge_start", tenant_id)
        portfolio_project_mapping = PortfolioDao.fetchPortfoliosOfProjectsForTenant(
            tenant_id=tenant_id
        )
        print("extract_project_knowledge_start", portfolio_project_mapping)

        for item in portfolio_project_mapping:
            try:
                response = self.process_projects_in_portfolio(item)
                self.save_project_knowledge(tenant_id, "portfolio", portfolio_id=item.get("portfolio_id"), knowledge_summary=response)
            except Exception as e:
                print("error", e)
                
        ## combined knowledge layer
        try:
            all_portfolio_knowledge = KnowledgeDao.FetchAllPortfolioKnowledgeOfTenant(tenant_id)
            knowledges_by_portfolio = ''
            for kn in all_portfolio_knowledge:
                knowledges_by_portfolio += f"""
                ----------------------------
                    {kn.get("knowledge_summary")}
                """
            prompt = generate_company_knowledge_layer(portfolios_data=knowledges_by_portfolio)
            response = self.llm_service.run(prompt, self.modelOptions, "ProjectsKnowledge::portfolio::combined", None)
            
            print("--process output al portfolios--", response)
            self.save_project_knowledge(tenant_id, "portfolio_combined", portfolio_id=None, knowledge_summary=response)
        except Exception as e:
            print("error ", e)
