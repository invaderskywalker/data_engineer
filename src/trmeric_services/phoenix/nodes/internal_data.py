from src.trmeric_services.phoenix.queries import *
from src.trmeric_database.dao import ProjectsDao


class InternalDataNode:
    def __init__(self, network_data={} , agent_name=""):
        # self.init_query = init_query
        self.network_data = network_data
        self.log_info = self.network_data.get("log_info")
        self.eligible_projects = ProjectsDao.FetchAvailableProject(tenant_id=self.log_info.get("tenant_id"), user_id=self.log_info.get("user_id"))
        self.query_functions = {
            ## projects
            "fetchProjectInfo": fetchProjectInfo,
            "fetchStatusInfo": fetchStatusInfo,
            "fetchMilestoneInfo": fetchMilestoneInfo,
            "fetchRiskInfo": fetchRiskInfo,
            "fetchTeamInfo": fetchTeamInfo,
            
            ## integration
            "getIntegrationData": getIntegrationData,
            
            
            # New roadmap query functions from RoadmapQueries
            "fetchRoadmapInfo": RoadmapQueries.fetchRoadmapInfo,
            "fetchRoadmapConstraints": RoadmapQueries.fetchRoadmapConstraints,
            "fetchRoadmapKeyResults": RoadmapQueries.fetchRoadmapKeyResults,
            "fetchRoadmapOrgStrategyAlign": RoadmapQueries.fetchRoadmapOrgStrategyAlign,
            "fetchRoadmapPortfolioInfo": RoadmapQueries.fetchRoadmapPortfolioInfo,
            
            
            
            
            "fetchPortfolioKnowledge": KnowledgeQueries.fetchPortfolioKnowledge,
        }
        # if (agent_name == "orion_planning"):
        #      self.query_functions = {
        #         "fetchPortfolioKnowledge": KnowledgeQueries.fetchPortfolioKnowledge,
        #         "fetchProjectInfo": fetchProjectInfo,  # Keep some basics for cross-checks
        #         "fetchTeamInfo": fetchTeamInfo
        #     }
        
    
    def run(self, intent=None):
        """Executes the specified query function based on intent."""
 
        query = intent.get("data_query", "")
        function_name = intent.get("function", "")
        params = intent.get("params", {})
        
        params.update({
            'tenantID': self.log_info.get("tenant_id"),
            'userID': self.log_info.get("user_id"),
            'eligibleProjects': self.eligible_projects,
        })
        
        try:
            func = self.query_functions[function_name]
            result = func(**params)
            return {"data": result, "source": function_name}
        except Exception as e:
            print("failure in InternalDataNode", function_name, e)
            return {"error": f"Query execution failed: {e}"}