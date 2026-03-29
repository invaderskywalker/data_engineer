from src.trmeric_services.agents.core import BaseAgent
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_services.agents.functions.graphql import VIEW_KNOWLEDGE_GRAPH_ANALYSIS
from src.trmeric_services.agents.functions.project_creation import PROJECT_CREATION_AGENT

class KnowledgeAgent(BaseAgent):
    name= "knowledge_agent"
    description= ""
    
    functions= [
        VIEW_KNOWLEDGE_GRAPH_ANALYSIS,
        # PROJECT_CREATION_AGENT
    ]
    
    def __init__(self, log_info = None):
        super().__init__(log_info)
        
    
