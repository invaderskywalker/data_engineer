"""
Roadmap Agent - Handles Roadmap-Specific Graph Queries

This agent extends BaseAgent to provide roadmap-specific functionality.
"""

from typing import Dict, List, Any
from ..core.base_agent import BaseAgent
from ..prompts import RoadmapPrompts, BasePrompts
from ..utils import clean_roadmap_response
from ..models.graph_schema import GraphSchema
from ..infrastructure import ROADMAP_TEMPLATE_SCHEMA


class RoadmapAgent(BaseAgent):
    """
    Agent for querying roadmap data from the graph.
    
    Extends BaseAgent with roadmap-specific:
    - Entity type definition
    - Planning prompts
    - Response cleaning
    """
    
    def get_entity_type(self) -> str:
        """Return 'RoadmapTemplate' as the entity type"""
        return "RoadmapTemplate"
    
    def get_schema(self) -> GraphSchema:
        """
        Return the GraphSchema for roadmaps.
        
        Returns:
            ROADMAP_TEMPLATE_SCHEMA GraphSchema object
        """
        return ROADMAP_TEMPLATE_SCHEMA
    
    def get_planning_prompt(self, query: str) -> str:
        """
        Generate roadmap-specific planning prompt.
        
        Args:
            query: User's natural language query
            
        Returns:
            Planning prompt with roadmap-specific hints
        """
        # Get base planning prompt
        base_prompt = BasePrompts.get_planning_prompt(
            entity_type=self.entity_type,
            query=query,
            schema=self.schema.to_dict(self.privacy_scope),
            user_context=self.user_context,
            eligible_entity_ids=self.eligible_entity_ids
        )
        
        # Add roadmap-specific mapping hints
        roadmap_hints = RoadmapPrompts.get_entity_mapping_hints()
        
        # Combine
        full_prompt = f"{base_prompt}\n\n{roadmap_hints}"
        
        return full_prompt
    
    def clean_response(self, raw_results: List[Dict]) -> Dict[str, Any]:
        """
        Clean roadmap query results.
        
        Args:
            raw_results: Raw GSQL results
            
        Returns:
            Cleaned roadmap data grouped by roadmap ID
        """
        return clean_roadmap_response(raw_results)
