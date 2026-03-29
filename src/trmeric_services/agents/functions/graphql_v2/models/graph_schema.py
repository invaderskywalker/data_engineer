from dataclasses import dataclass, field
from typing import Dict, List, Set
from .privacy_models import PrivacyConfig, PrivacyScope


@dataclass
class SchemaEntity:
    """Represents a vertex or edge in the graph schema"""
    
    name: str
    attributes: List[str] = field(default_factory=list)
    privacy_config: PrivacyConfig = field(default_factory=PrivacyConfig)
    description: str = ""
    
    def get_allowed_attributes(self, scope: PrivacyScope) -> List[str]:
        """Get attributes allowed for the given privacy scope"""
        allowed_fields = self.privacy_config.get_allowed_fields(scope)
        if not allowed_fields:  # No privacy config, allow all
            return self.attributes
        return [attr for attr in self.attributes if attr in allowed_fields]


@dataclass
class GraphSchema:
    """
    Complete graph schema definition for an entity type.
    
    Single source of truth for what vertices, edges, and attributes
    exist for a given entity (Project, Roadmap, etc.)
    """
    
    entity_type: str
    vertices: Dict[str, SchemaEntity] = field(default_factory=dict)
    edges: Dict[str, Dict[str, str]] = field(default_factory=dict)  # {edge_name: {from: X, to: Y}}
    
    def get_vertex(self, name: str) -> SchemaEntity:
        """Get vertex definition by name"""
        return self.vertices.get(name)
    
    def get_edge(self, name: str) -> Dict[str, str]:
        """Get edge definition by name"""
        return self.edges.get(name)
    
    def to_dict(self, scope: PrivacyScope = PrivacyScope.PRIVATE) -> Dict:
        """
        Convert schema to dictionary format for LLM prompts.
        Filters attributes based on privacy scope.
        """
        return {
            "vertices": {
                name: entity.get_allowed_attributes(scope)
                for name, entity in self.vertices.items()
            },
            "edges": self.edges
        }
