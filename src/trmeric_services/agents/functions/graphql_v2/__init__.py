"""
GraphQL V2 - Next Generation Graph Query & Analysis System

This module provides a clean, extensible architecture for:
- Natural language querying of TigerGraph data (Query Agents)
- ML-based project clustering and pattern generation (Analysis Pipeline)
- Privacy-aware data access (PUBLIC/PRIVATE scopes)
- Complete data loading workflow (PostgreSQL → TigerGraph)

Main Entry Points:
- MasterAnalyst: Primary orchestrator for queries and analysis
- view_knowledge_graph_analysis: Backward-compatible function
- AnalysisPipeline: Direct access to analysis workflow
"""

# Core query agents
from .core import BaseAgent, PrivacyLayer, QueryBuilder
from .agents import ProjectAgent, RoadmapAgent

# Models
from .models import QueryPlan, PrivacyScope, GraphSchema, SchemaEntity

# Infrastructure
from .infrastructure import GraphConnector, GraphConnectorConfig, AgentConfig
from src.trmeric_ml.llm.Client import LLMClient

# Data loading
from .data_loading import PostgresConnector, PostgresConfig, ProjectQueries, RoadmapQueries, DataSanitizer

# Graph loaders
from .loaders import VertexLoader, EdgeLoader, BatchGraphLoader

# Analysis
from .analysis import ProjectClusterEngine, RoadmapClusterEngine, ProjectPatternGenerator, RoadmapPatternGenerator, TemplateGenerator

# Pipeline
from .pipeline import AnalysisPipeline

# Master orchestrator
from .master_analyst import MasterAnalyst, view_knowledge_graph_analysis

__version__ = "2.0.0"

__all__ = [
    # Master Entry Points
    "MasterAnalyst",
    "view_knowledge_graph_analysis",
    
    # Core Query Components
    "BaseAgent",
    "SchemaRegistry",
    "PrivacyLayer",
    "QueryBuilder",
    
    # Agents
    "ProjectAgent",
    "RoadmapAgent",
    
    # Models
    "QueryPlan",
    "PrivacyScope",
    "GraphSchema",
    "SchemaEntity",
    
    # Infrastructure
    "GraphConnector",
    "LLMClient",
    "GraphConnectorConfig",
    "AgentConfig",
    
    # Data Loading
    "PostgresConnector",
    "PostgresConfig",
    "ProjectQueries",
    "RoadmapQueries",
    "DataSanitizer",
    
    # Graph Loaders
    "VertexLoader",
    "EdgeLoader",
    "BatchGraphLoader",
    
    # Analysis
    "ProjectClusterEngine",
    "RoadmapClusterEngine",
    "ProjectPatternGenerator",
    "RoadmapPatternGenerator",
    "TemplateGenerator",
    "AnalysisPipeline",
]
