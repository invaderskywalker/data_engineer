"""
Project Agent - Handles Project-Specific Graph Queries

This agent extends BaseAgent to provide project-specific functionality.
Most of the heavy lifting is done by BaseAgent; this class just provides
the project-specific configuration.
"""

from typing import Dict, List, Any
from ..core.base_agent import BaseAgent
from ..prompts import ProjectPrompts, BasePrompts
from ..utils import clean_project_response
from ..models.graph_schema import GraphSchema
from ..infrastructure import PROJECT_TEMPLATE_SCHEMA


class ProjectAgent(BaseAgent):
    """
    Agent for querying project data from the graph.
    
    Extends BaseAgent with project-specific:
    - Entity type definition
    - Planning prompts
    - Response cleaning
    """
    
    def get_entity_type(self) -> str:
        """Return 'ProjectTemplate' as the entity type"""
        return "ProjectTemplate"
    
    def get_schema(self) -> GraphSchema:
        """
        Return the GraphSchema for projects.
        
        Returns:
            PROJECT_TEMPLATE_SCHEMA GraphSchema object
        """
        return PROJECT_TEMPLATE_SCHEMA
    
    def get_planning_prompt(self, query: str) -> str:
        """
        Generate project-specific planning prompt.
        
        Args:
            query: User's natural language query
            
        Returns:
            Planning prompt with project-specific hints
        """
        # Get base planning prompt
        base_prompt = BasePrompts.get_planning_prompt(
            entity_type=self.entity_type,
            query=query,
            schema=self.schema.to_dict(self.privacy_scope),
            user_context=self.user_context,
            eligible_entity_ids=self.eligible_entity_ids
        )
        
        # Add project-specific mapping hints
        project_hints = ProjectPrompts.get_entity_mapping_hints()
        
        # Combine
        full_prompt = f"{base_prompt}\n\n{project_hints}"
        
        return full_prompt
    
    def clean_response(self, raw_results: List[Dict]) -> Dict[str, Any]:
        """
        Clean project query results.
        
        Args:
            raw_results: Raw GSQL results
            
        Returns:
            Cleaned project data grouped by project ID
        """
        return clean_project_response(raw_results)
