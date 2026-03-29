from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_services.insight.Prompts import *
from src.trmeric_database.dao.insight import InsightDao
from src.trmeric_database.dao.portfolios import PortfolioDao
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_api.logging.AppLogger import appLogger
import traceback

class ProjectsSpaceInsightCreator:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model='gpt-4o',
            max_tokens=1000,
            temperature=0
        )

    def createInsightForProject(self, data):
        prompt = get_project_update_insight_creation(data)
        response = self.llm.run(prompt, self.modelOptions, None)
        return response

    def createInsightForPortfolio(self, data):
        prompt = get_portfolio_update_insight_creation(data)
        response = self.llm.run(prompt, self.modelOptions, None)
        return response

    def createInsightForProvider(self, data):
        prompt = get_provider_update_insight_creation(data)
        response = self.llm.run(prompt, self.modelOptions, None)
        return response
    
    def createInsightForProgram(self, data):
        prompt = get_program_update_insight_creation(data)
        response = self.llm.run(prompt, self.modelOptions, None)
        return response

    def process_update(self, project_id):
        appLogger.info({
            "function": "process_update",
            "project_id": project_id
        })
        try:
            data = ProjectsDao.FetchLatestProjectStatusUpdate(
                project_id=project_id)[0]
            
            # print("debug process_update 1 ", data)
            
            project_total_data = ProjectsDao.FetchProjectDetails(project_id=project_id)[0]

            projectInsight = self.createInsightForProject(
                data=data)
            
            # print("debug process_update 2 ", projectInsight)

            InsightDao.insertInsight(
                project_id=project_id,
                _type=1,  # project
                insight_string=projectInsight,
                meta_id=project_id
            )

            print("project insight done ")
            try:

                project_ids = PortfolioDao.fetchProjectIdsForPortfolio(
                    portfolio_id=data["portfolio_id"])
                portfolio_projects_status_update = []

                for proj_id in project_ids:
                    project_status_update = ProjectsDao.FetchLatestProjectStatusUpdate(
                        project_id=proj_id["project_id"])
                    if (len(project_status_update) > 0):
                        portfolio_projects_status_update.append(project_status_update)

                if (len(portfolio_projects_status_update) > 0):
                    portfolioInsight = self.createInsightForPortfolio(
                        portfolio_projects_status_update)

                    InsightDao.insertInsight(
                        project_id=project_id,
                        _type=2,  # project
                        insight_string=portfolioInsight,
                        meta_id=data["portfolio_id"]
                    )

                print("portfolio insight done")
            except Exception as e:
                print("portfolio insight failed ", e)
                
            try:
                provider_ids = ProjectsDao.FetchProviderIdsForProjects(project_id)

                for p_id in provider_ids:
                    projectIdsOfProvider = ProjectsDao.FetchProjectIdsIdsForProvider(
                        p_id["provider_id"])
                    projectStatusUpdatesForProvider = []
                    for proj in projectIdsOfProvider:
                        status_update = ProjectsDao.FetchLatestProjectStatusUpdate(
                            project_id=proj["project_id"])
                        if (len(status_update) > 0):
                            projectStatusUpdatesForProvider.append(
                                status_update)

                    if (len(projectStatusUpdatesForProvider) > 0):
                        providerInsight = self.createInsightForProvider(
                            projectStatusUpdatesForProvider)

                        InsightDao.insertInsight(
                            project_id=project_id,
                            _type=3,  # project
                            insight_string=providerInsight,
                            meta_id=p_id["provider_id"]
                        )
                 
                print("provider insight done")       
            except Exception as e:
                print("provider insight failed --- ", e)  
            
            
            
            ##### do it for program if program exists
            program_id_exists = project_total_data.get("program_id", None) or None
            print("program insight creating ", program_id_exists)
            if not program_id_exists:
                return
            program_id = project_total_data.get("program_id")
            tenant_id = project_total_data.get("tenant_id_id")
            print("program insight creating 1 ", program_id,tenant_id )
            ## fetch all projects for this project program and this tenant
            projects = ProjectsDao.fetchAllProjectsForProgram(program_id, tenant_id)
            updates = []
            for proj in projects:
                status_update = ProjectsDao.FetchLatestProjectStatusUpdate(
                    project_id=proj["id"]
                )
                if (len(status_update) > 0):
                    updates.append(status_update)
                    
            if len(updates) > 0:
                program_insight = self.createInsightForProgram(data=updates)
                InsightDao.insertInsight(
                    project_id=project_id,
                    _type=4, ## program
                    insight_string=program_insight,
                    meta_id=program_id
                )
        except Exception as e:
            appLogger.error({
                "function": "process_update",
                "project_id": project_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
                
                
            
            
        
        
