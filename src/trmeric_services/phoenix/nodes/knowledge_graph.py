


# src/trmeric_services/phoenix/nodes/knowledge_graph.py

# from src.trmeric_services.agents.functions.graphql.master import MasterAnalyst
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import traceback
import json

class KnowledgeGraphNode:
    def __init__(self, network_data={}, base_agent=None):
        self.network_data = network_data
        self.socketio = network_data.get("socketio")
        self.client_id = network_data.get("client_id")
        self.log_info = network_data.get("log_info", {})
        self.base_agent = base_agent
        self.tenant_id = self.log_info.get("tenant_id")
        self.customer_id = f"customer_{self.tenant_id}"
        self.user_id = self.log_info.get("user_id")
        self.session_id = self.log_info.get("session_id")
        # self.master_analyst = MasterAnalyst(
        #     tenant_id=self.tenant_id,
        #     user_id=self.user_id,
        #     socketio=self.socketio,
        #     llm=base_agent.llm,
        #     client_id=self.client_id,
        #     session_id=self.session_id,
        #     base_agent=base_agent,
        #     eligibleProjects=[],
        # )
        self.master_analyst = None
        debugLogger.info({"function": "KnowledgeGraphNode_init", "tenant_id": self.tenant_id, "user_id": self.user_id})
        

    def runOld(self, intent: dict) -> str:
        """Execute a knowledge graph query based on intent."""
        # debugLogger.info(f"Run knowledge graph ----- {intent}")
        query = f"Customer id is exactly ----- {self.customer_id} ::: " + intent.get("query", "")
        debugLogger.info(f"Run knowledge graph ----- {query}")
        try:
            # self.socketio.emit("custom_agent_v1_ui", 
            #     {"event": "timeline", "data": {"text": "Knowledge Graph Query", "key": "Knowledge Graph Query", "is_completed": False}},
            #     room=self.client_id
            # )
            # Use MasterAnalyst to generate and execute GSQL queries
            # debugLogger.info(f"debug 1")
            # result = self.master_analyst.process_query_for_data(query)
            # debugLogger.info(f"debug 2 {result}")
            # # self.socketio.emit("custom_agent_v1_ui", 
            # #     {"event": "timeline", "data": {"text": "Knowledge Graph Query", "key": "Knowledge Graph Query", "is_completed": True}},
            # #     room=self.client_id
            # # )
            result = ""
            return result
        
        except Exception as e:
            appLogger.error({
                "function": "KnowledgeGraphNode_run",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return ""
        
        
    def run(self, intent: dict) -> str:
        """Execute a knowledge graph query based on intent for planning"""
        # debugLogger.info(f"Run knowledge graph ----- {intent}")
        print("knowledge graph node run ", intent)
        result = {}
        try:
            query = f"""
                Current Customer id is exactly ----- {self.customer_id}
                Now our aim should be to find all templates for this customer 
                and find the most relevant one and also the relevant portfolio pattern..
                
                idea of user when creating plan for next solution::: {intent.get("query", "")}
            """
            debugLogger.info(f"Run knowledge graph ----- {query}")
            result1 = self.master_analyst.process_query_for_data(query)
            result["customer_context_of_solutions_and_portfolio_patterns"] = result1
            
            
            query = f"""
                Current Customer id is exactly ----- {self.customer_id}
                Now our aim should be to find the industry of this customer and 
                fetch all templates of all customers in that iindustry and find the most matching one..
                idea of user when creating plan for next solution::: {intent.get("query", "")}
            """
            debugLogger.info(f"Run knowledge graph ----- {query}")
            result1 = self.master_analyst.process_query_for_data(query)
            result["templates_of_peers_in_same_industry"] = result1
            
            return json.dumps(result, indent=2)
        except Exception as e:
            appLogger.error({
                "function": "KnowledgeGraphNode_run",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return ""
        

        