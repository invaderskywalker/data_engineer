from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_database.dao.roadmap import RoadmapDao
from src.trmeric_database.dao.insight import InsightDao
from src.trmeric_database.dao.integration import IntegrationDao

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.insight.Prompts import *
from src.trmeric_utils.json_parser import *

class DigestService:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model='gpt-4.1',
            max_tokens=20000,
            temperature=0.1
        )
        
    def createDailyDigest(self, tenant_id, user_id=None):
        print("createDailyDigest -- ", tenant_id, user_id)
        appLogger.info({
            "event": "createDailyDigest",
            "tenant_id": tenant_id
        })
        try:
            createdProjectsYesterday = ProjectsDao.fetchProjectsForTenantCreatedAfterYesterday(tenant_id=tenant_id)
            print("debug --createdProjectsYesterday ", createdProjectsYesterday)
            createdRoadmaps = RoadmapDao.fetchRoadmapsForTenantCreatedAfterYesterday(tenant_id)
            print("debug --createdRoadmaps ", createdRoadmaps)
            projectStatusUpdatesMadeYesterday = ProjectsDao.projectStatusUpdatesMadeYesterday(tenant_id)
            # print("debug --projectStatusUpdatesMadeYesterday ", projectStatusUpdatesMadeYesterday)
            
            # jiraData = IntegrationDao.getJiraDataYesterdayUpdateData(tenant_id)
            # integrationUpdateData = 
            # print("debug --jiraData ", jiraData)
            ## fetch jira latest in progress sprint data
            integration_data = None
            from src.trmeric_services.integration.helpers.jira_on_prem_getter import fetch_filtered_integration_data
            
            _data = IntegrationDao.fetchActiveProjectSourcesForTenant(tenant_id=tenant_id)
            project_ids = [p.get("project_id") for p in _data if p]
            integration_name = "jira"
            is_jira_on_prem = IntegrationDao.is_user_on_prem_jira(user_id)
            from src.trmeric_services.agents.functions.roadmap_analyst import getIntegrationData
            from src.trmeric_services.integration.helpers.jira_on_prem_getter import fetch_filtered_integration_data
            data = getIntegrationData(
                integration_name=integration_name,
                project_ids=project_ids,
                tenantID=tenant_id,
                userID=user_id,
            )
            print("is_jira_on_prem ", is_jira_on_prem)
            if (is_jira_on_prem or int(tenant_id) in [212, 776]) \
                and (integration_name == "jira" or integration_name == "github"):
                # Flatten out the grouped structure
                ndata = []
                for project_id, integrations in data.items():
                    for item in integrations:
                        if "integration_data" in item:
                            int_data = item["integration_data"].get("data")
                            if int_data:
                                ndata.append(int_data)

                query = """
                Fetch feature name and summarized metrics per epic. 
                so that we can combijne them and provide a view
                """
                integration_data = fetch_filtered_integration_data(
                    user_query=query,
                    data_array=ndata,
                    integration_name=integration_name
                )
            
                
            # integration_data = "integration_data"
            prompt = createDailyDigestPrompt(
                roadmap_created_in_last_day=createdRoadmaps, 
                project_created_in_last_day=createdProjectsYesterday, 
                project_status_updates_in_last_day=projectStatusUpdatesMadeYesterday, 
                latest_integration_data_update=integration_data
            )
            response = self.llm.run(prompt, self.modelOptions, "daily_digest_run", {"tenant_id": tenant_id, "user_id": user_id})
            print("resoponse daily digest ", response)
            response_json = extract_json_after_llm(response)
            header = response_json.get('insight_header')
            label = response_json.get('insight_description')
            InsightDao().save_daily_summary(tenant_id, header, label)
            
            appLogger.info({
                "event": "createDailyDigest_complete",
                "tenant_id": tenant_id
            })
            return 
        except Exception as e:
            print("debug ---err digest", e, traceback.format_exc())
        
        
        
        
        
        