# src/trmeric_services/phoenix/nodes/knowledge.py
from src.trmeric_utils.knowledge.KnowledgeAgent import KnowledgeAgent
from src.trmeric_services.agents.core import BaseAgent

class KnowledgeNode:
    def __init__(self, network_data={}):
        self.network_data = network_data
        self.log_info = network_data.get("log_info", {})
        self.socketio = network_data.get("socketio")
        self.client_id = network_data.get("client_id")
        self.knowledge_agent = KnowledgeAgent()

    def run(self, intent=None):
        """Fetches insights from tango_knowledge using KnowledgeAgent based on intent."""
        if not intent or "params" not in intent:
            return {"error": "No intent or params provided", "source": "Trmeric knowledge"}

        params = intent.get("params", {})
        project_ids = params.get("project_ids", [])
        project_type = params.get("project_type")
        outcome = params.get("outcome", [])

        try:
            result_string = ""
            if project_ids:
                cateogries = self.knowledge_agent.fetchProjectCategoriesForProjects(project_ids)
                insights = self.knowledge_agent.fetchKnowledgeForProjects(project_ids, outcome)
                for c in cateogries:
                    result_string += f"""
                        For project with name: {c.get("project_title")}
                        Project Type: {c.get("project_type")}.
                    """
                for row in insights:
                    result_string += f"""
                        For the project type: {row["project_type"]} 
                        where outcome is {row["outcome"]}
                        which shows that
                        to achieve {row["outcome"]}
                        execute like ::::: 
                        {row["insight"]}
                        --------
                    """
                    
            return {"data": result_string, "source": "Trmeric knowledge"}
                    
            
                    
                    
                    
            # elif project_type:
            #     insights = self.knowledge_agent.fetchKnowledgeForProjectCategories([project_type], outcome)
            # else:
            #     return {"error": "No data fetched from Trmeric Source", "source": "Trmeric knowledge"}

            # if not insights:
            #     return {"data": [], "source": "Trmeric knowledge", "message": "No relevant insights found"}

            # formatted_insights = [
            #     {
            #         "project_type": row["project_type"],
            #         "outcome": row["outcome"],
            #         "insight": row["insight"],
            #         "created_at": row["created_at"],
            #         "updated_at": row["updated_at"]
            #     } for row in insights
            # ]
            return {"data": formatted_insights, "source": "Trmeric knowledge"}

        except Exception as e:
            return {"error": f"Knowledge fetch failed: {str(e)}", "source": "Trmeric knowledge"}