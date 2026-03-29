"""
Master Analyst - Main Entry Point for GraphQL V2

Integrates:
1. Query Agents (ProjectAgent, RoadmapAgent) - For natural language queries
2. Analysis Pipeline - For data loading and pattern generation

This module provides backward compatibility with the original system while
using the new V2 architecture.
"""

from typing import Dict, Any, Optional, Set
from .agents import ProjectAgent, RoadmapAgent
from .infrastructure import GraphConnector, GraphConnectorConfig, AgentConfig
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from .models import PrivacyScope
from .pipeline import AnalysisPipeline
from .data_loading import PostgresConfig

class MasterAnalyst:
    """
    Master orchestrator for GraphQL V2 system.
    
    Provides two main capabilities:
    1. Natural language querying of graph data (via agents)
    2. Data loading and pattern generation (via pipeline)
    """
    
    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        socketio=None,
        llm=None,
        client_id=None,
        session_id=None,
        graphname: str = None
    ):
        """
        Initialize Master Analyst.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            socketio: SocketIO instance for streaming responses
            llm: LLM client instance
            client_id: Client identifier for logging
            session_id: Session identifier for logging
            graphname: TigerGraph graph name (REQUIRED - must be tenant-specific like g_dev_648)
        """
        if not graphname:
            raise ValueError("graphname is required and must be a tenant-specific graph (e.g., g_dev_648)")
        
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.socketio = socketio
        # If caller doesn't provide an llm, instantiate a ChatGPTClient using tenant/user
        if llm is None:
            # instantiate default ChatGPT client (legacy pattern)
            self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        else:
            self.llm = llm
        self.client_id = client_id
        self.session_id = session_id
        self.graphname = graphname

        # Initialize infrastructure
        # Ensure graph connector uses the same graphname provided to MasterAnalyst
        graph_config = GraphConnectorConfig.from_env(self.graphname)
        self.graph_connector = GraphConnector(graph_config)
        self.graph_connector.connect()

        # Use the ChatGPTClient directly (no LLMClient wrapper needed)
        self.llm_client = self.llm
        self.agent_config = AgentConfig.from_env()

        # Initialize agents (lazy)
        self._project_agent: Optional[ProjectAgent] = None
        self._roadmap_agent: Optional[RoadmapAgent] = None

        # Initialize pipeline (lazy)
        self._analysis_pipeline: Optional[AnalysisPipeline] = None
    
    @property
    def project_agent(self) -> ProjectAgent:
        """Get or create ProjectAgent instance."""
        if self._project_agent is None:
            self._project_agent = ProjectAgent(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                graph_connector=self.graph_connector,
                llm_client=self.llm_client,
                config=self.agent_config,
                privacy_scope=PrivacyScope.PRIVATE,  # Default to private
                eligible_entity_ids=[],
                user_context=""
            )
        return self._project_agent
    
    @property
    def roadmap_agent(self) -> RoadmapAgent:
        """Get or create RoadmapAgent instance."""
        if self._roadmap_agent is None:
            self._roadmap_agent = RoadmapAgent(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                graph_connector=self.graph_connector,
                llm_client=self.llm_client,
                config=self.agent_config,
                privacy_scope=PrivacyScope.PRIVATE,
                eligible_entity_ids=[],
                user_context=""
            )
        return self._roadmap_agent
    
    @property
    def analysis_pipeline(self) -> AnalysisPipeline:
        """Get or create AnalysisPipeline instance."""
        if self._analysis_pipeline is None:
            # Provide graph_config with correct graphname so pipeline loads to the same graph
            graph_config = GraphConnectorConfig.from_env(self.graphname)
            self._analysis_pipeline = AnalysisPipeline(
                postgres_config=PostgresConfig.from_env(),
                graph_config=graph_config,
                llm_client=self.llm
            )
        return self._analysis_pipeline
    
    def query_projects(
        self,
        query: str,
        eligible_project_ids: list = None,
        user_context: str = "",
        privacy_scope: PrivacyScope = PrivacyScope.PRIVATE
    ) -> Dict[str, Any]:
        """
        Execute natural language query against project data.
        
        Args:
            query: Natural language query (e.g., "Show me projects using React")
            eligible_project_ids: List of project IDs user can access
            user_context: User role and access context
            privacy_scope: PUBLIC or PRIVATE data access
            
        Returns:
            Query results dictionary
        """
        # Update agent configuration
        self.project_agent.eligible_entity_ids = eligible_project_ids or []
        self.project_agent.user_context = user_context
        self.project_agent.privacy_scope = privacy_scope
        
        # Execute query
        return self.project_agent.process_query(query)
    
    def query_roadmaps(
        self,
        query: str,
        eligible_roadmap_ids: list = None,
        user_context: str = "",
        privacy_scope: PrivacyScope = PrivacyScope.PRIVATE
    ) -> Dict[str, Any]:
        """
        Execute natural language query against roadmap data.
        
        Args:
            query: Natural language query
            eligible_roadmap_ids: List of roadmap IDs user can access
            user_context: User role and access context
            privacy_scope: PUBLIC or PRIVATE data access
            
        Returns:
            Query results dictionary
        """
        # Update agent configuration
        self.roadmap_agent.eligible_entity_ids = eligible_roadmap_ids or []
        self.roadmap_agent.user_context = user_context
        self.roadmap_agent.privacy_scope = privacy_scope
        
        # Execute query
        return self.roadmap_agent.process_query(query)
    
    def analyze_and_load_projects(
        self,
        customer_id: str,
        project_ids: Set[int],
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run complete analysis pipeline for projects: fetch → cluster → generate → load.
        
        Args:
            customer_id: Customer identifier
            project_ids: Set of project IDs to analyze
            customer_data: Customer metadata with structure:
                {
                    "customer": {"id": str, "name": str, ...},
                    "industry": {"id": str, "name": str, ...},
                    "industry_sector": {"id": str, "name": str, ...}
                }
        
        Returns:
            Analysis results and loading statistics
        """
        return self.analysis_pipeline.run(
            tenant_id=self.tenant_id,
            customer_id=customer_id,
            entity_ids=project_ids,
            customer_data=customer_data,
            entity_type="Project"
        )
    
    def analyze_and_load_roadmaps(
        self,
        customer_id: str,
        roadmap_ids: Set[int],
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run complete analysis pipeline for roadmaps: fetch → cluster → generate → load.

        Args:
            customer_id: Customer identifier
            roadmap_ids: Set of roadmap IDs to analyze
            customer_data: Customer metadata with structure:
                {
                    "customer": {"id": str, "name": str, ...},
                    "industry": {"id": str, "name": str, ...},
                    "industry_sector": {"id": str, "name": str, ...}
                }

        Returns:
            Analysis results and loading statistics
        """
        return self.analysis_pipeline.run(
            tenant_id=self.tenant_id,
            customer_id=customer_id,
            entity_ids=roadmap_ids,
            customer_data=customer_data,
            entity_type="Roadmap"
        )

    def connect_patterns(self) -> Dict[str, Any]:
        """
        Connect RoadmapPattern vertices to ProjectScore and ProjectPattern vertices.

        Creates bidirectional edges based on roadmap-to-project mappings:
        - RoadmapPattern ↔ ProjectScore (hasProjectExecution / executedByRoadmap)
        - RoadmapPattern ↔ ProjectPattern (hasExecutionInCluster / roadmapExecutedInCluster)

        Returns:
            Statistics about connections created
        """
        return self.analysis_pipeline.connect_roadmap_to_project_patterns(self.tenant_id)

    def close(self):
        """Clean up resources."""
        if self.graph_connector:
            self.graph_connector.close()


def view_knowledge_graph_analysis(
    tenant_id: int,
    user_id: int,
    query: str,
    entity_type: str = "project",
    eligible_entity_ids: list = None,
    user_context: str = "",
    socketio=None,
    llm=None,
    client_id=None,
    session_id=None,
    graphname: str = None
) -> Dict[str, Any]:
    """
    Backward-compatible entry point for knowledge graph queries.
    
    Args:
        tenant_id: Tenant identifier
        user_id: User identifier
        query: Natural language query
        entity_type: "project" or "roadmap"
        eligible_entity_ids: List of entity IDs user can access
        user_context: User role and access context
        socketio: SocketIO instance
        llm: LLM client
        client_id: Client identifier
        session_id: Session identifier
        graphname: TigerGraph graph name (REQUIRED - must be tenant-specific)
        
    Returns:
        Query results
    """
    if not graphname:
        raise ValueError("graphname is required and must be a tenant-specific graph (e.g., g_dev_648)")
    
    analyst = MasterAnalyst(
        tenant_id=tenant_id,
        user_id=user_id,
        socketio=socketio,
        llm=llm,
        client_id=client_id,
        session_id=session_id,
        graphname=graphname
    )
    
    try:
        if entity_type.lower() == "project":
            return analyst.query_projects(
                query=query,
                eligible_project_ids=eligible_entity_ids,
                user_context=user_context
            )
        elif entity_type.lower() == "roadmap":
            return analyst.query_roadmaps(
                query=query,
                eligible_roadmap_ids=eligible_entity_ids,
                user_context=user_context
            )
        else:
            return {"error": f"Unknown entity type: {entity_type}"}
    finally:
        analyst.close()
