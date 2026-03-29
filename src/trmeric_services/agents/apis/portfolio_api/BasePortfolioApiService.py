
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
from src.trmeric_database.Redis import RedClient


class BaseAgentService:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0
        )
        
    def fetchProjectsWithAttributesV2(self, portfolio, tenant_id, applicable_projects, id='', start_date=None, end_date=None):
        archived_projects = self.fetchArchivedProjectsWithAttributesV2(portfolio, tenant_id, applicable_projects, start_date=start_date, end_date=end_date)
        ongoing_projects = self.fetchOngonigProjectsWithAttributesV2(portfolio, tenant_id, applicable_projects, start_date=start_date, end_date=end_date)
        future_projects = self.fetchFutureProjectsWithAttributesV2(portfolio, tenant_id, applicable_projects, start_date=start_date, end_date=end_date)
        # print("debug fetchProjectsWithAttributesV2 -- ", id, len(future_projects))
        return {
            "archived_projects": archived_projects,
            "ongoing_projects": ongoing_projects,
            "future_projects": future_projects
        }
        
    def fetchArchivedProjectsWithAttributesV2(self, portfolio, tenant_id, applicable_projects, start_date=None, end_date=None):

        key_components = [
            f"fetchArchivedProjectsWithAttributesV2",
            f"tenant_id:{tenant_id}",
            f"portfolio:{'_'.join((str(x) for x in portfolio))}",
            f"applicable_projects:{'_'.join(str(x) for x in applicable_projects)}"
        ]
        key_set = RedClient.create_key(components=key_components)
        data = RedClient.execute(
            query = lambda: ProjectsDao.fetchProjectsInfoForPortfolioV2(
                portfolio_ids=portfolio, 
                tenant_id=tenant_id,
                applicable_projects=applicable_projects,
                archived=True,
                start_date=start_date, 
                end_date=end_date
            ),
            key_set = key_set
            # key_set = ["archived_projects",tenant_id]
        )

        
        ndata = []
        for d in data:
            # print("debug ... ", d["milestones"])
            miles = []
            milestones = d.get("milestones", []) or []
            # for m in milestones:
            #     miles.append(m)  # m is already a dict from JSONB deserialization
            for m in d["milestones"]:
                # print("debug ..mm. ", d["milestones"])
                # miles.append(json.loads(m))
                if isinstance(m, dict):
                    miles.append(m)
                elif isinstance(m, (str, bytes, bytearray)):
                    miles.append(json.loads(m))
    
                
            d["milestones"] = miles
            if "unique_milestones_text" in d:
                del d["unique_milestones_text"]
            ndata.append(d)
            
        return ndata
    
    def fetchOngonigProjectsWithAttributesV2(self, portfolio, tenant_id, applicable_projects, start_date=None, end_date=None):
        
        # _data = ProjectsDao.fetchProjectsInfoForPortfolioV2(
        #     portfolio_ids=portfolio, 
        #     tenant_id=tenant_id,
        #     applicable_projects=applicable_projects,
        #     archived=False,
        #     start_date=start_date, 
        #     end_date=end_date
        # )
        key_components = [
            f"fetchOngonigProjectsWithAttributesV2",
            f"tenant_id:{tenant_id}",
            f"portfolio:{'_'.join((str(x) for x in portfolio))}",
            f"applicable_projects:{'_'.join(str(x) for x in applicable_projects)}"
        ]
        key_set = RedClient.create_key(components=key_components)
    
        data = RedClient.execute(
            query = lambda: ProjectsDao.fetchProjectsInfoForPortfolioV2(
                portfolio_ids=portfolio, 
                tenant_id=tenant_id,
                applicable_projects=applicable_projects,
                archived=False,
                start_date=start_date, 
                end_date=end_date
            ),
            key_set = key_set
        )

        # print("fetchOngonigProjectsWithAttributesV2 ", time.time() - start_time)
        ndata = []
        for d in data:
            # print("debug ... ", d["milestones"])
            miles = []
            milestones = d.get("milestones", []) or []
            # for m in milestones:
            #     miles.append(m)  # m is already a dict from JSONB deserialization
            for m in d["milestones"]:
                # print("debug ..mm. ", d["milestones"])
                # miles.append(json.loads(m))
                if isinstance(m, dict):
                    miles.append(m)
                elif isinstance(m, (str, bytes, bytearray)):
                    miles.append(json.loads(m))
    
            d["milestones"] = miles
            if "unique_milestones_text" in d:
                del d["unique_milestones_text"]
            # del d["unique_milestones_text"]
            ndata.append(d)
            
        return ndata
    
    def fetchFutureProjectsWithAttributesV2(self, portfolio, tenant_id, applicable_projects, start_date=None, end_date=None):
        # return ProjectsDao.fetchfutureProjectsInfoForPortfolioV2(portfolio_ids=portfolio,applicable_projects=applicable_projects, tenant_id=tenant_id, start_date=start_date, end_date=end_date)
        key_components = [
            f"fetchFutureProjectsWithAttributesV2",
            f"tenant_id:{tenant_id}",
            f"portfolio:{'_'.join((str(x) for x in portfolio))}",
            f"applicable_projects:{'_'.join(str(x) for x in applicable_projects)}"
        ]
        key_set = RedClient.create_key(components=key_components)
        return RedClient.execute(
            query = lambda: ProjectsDao.fetchfutureProjectsInfoForPortfolioV2(portfolio_ids=portfolio,applicable_projects=applicable_projects, tenant_id=tenant_id, start_date=start_date, end_date=end_date),
            key_set = key_set
        )

    
    def runLLM(self, user_id, tenant_id, prompt, category):
        response = self.llm.run(
            prompt, 
            self.modelOptions, 
            f"portfolio_agent::insight::{category}",
            logInDb={
                "tenant_id": tenant_id,
                "user_id": user_id
            }
        )
        return extract_json_after_llm(response)