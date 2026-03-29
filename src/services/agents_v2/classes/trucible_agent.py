

# src/trmeric_services/agents_v2/classes/trucible_agent.py
from typing import Generator
from src.api.logging.AppLogger import appLogger, debugLogger
from ..core import BaseAgent

class TrucibleAgent(BaseAgent):
    """Trucible agent for enterprise context building and business intelligence."""
    
    def __init__(self, tenant_id: int, user_id: int, **kwargs):
        super().__init__(tenant_id, user_id, **kwargs)
        

    def process_combined_query(self, query: str) -> Generator[str, None, None]:
        """Process a combined query and yield response chunks."""
        appLogger.info({
            "function": "TrucibleAgent_process_combined_query", 
            "query": query, 
            "tenant_id": self.tenant_id
        })
        for chunk in super().process_combined_query(query):
            yield chunk

    