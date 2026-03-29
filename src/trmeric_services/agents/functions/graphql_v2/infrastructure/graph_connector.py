"""
Graph Connector - Abstraction over TigerGraph

This module provides a clean abstraction over TigerGraph interactions,
making it easier to test, mock, and potentially swap graph databases.
"""

from typing import Dict, Any, Optional
from pyTigerGraph import TigerGraphConnection
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from .config import GraphConnectorConfig


class GraphConnector:
    """
    Abstraction layer for TigerGraph interactions.
    
    Benefits:
    - Easier to test (can mock this class)
    - Centralized error handling
    - Connection pooling/retry logic in one place
    - Easier to swap graph databases in future
    """
    
    def __init__(self, config: GraphConnectorConfig):
        """
        Initialize graph connector with configuration.
        
        Args:
            config: Graph connection configuration
        """
        self.config = config
        self._connection: Optional[TigerGraphConnection] = None
        self._token: Optional[str] = None
        
    
    def connect(self) -> bool:
        """
        Establish connection to TigerGraph.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Initial connection
            self._connection = TigerGraphConnection(
                host=self.config.host,
                username=self.config.username,
                password=self.config.password,
                restppPort=self.config.restpp_port,
                graphname=self.config.graphname
            )
            
            # Try to get authentication token; if graph does not exist yet, proceed without token
            try:
                token_result = self._connection.getToken(self.config.secret)
                self._token = token_result[0] if token_result else None
            except Exception as token_err:
                appLogger.warning({
                    "function": "GraphConnector_connect",
                    "status": "token_skip",
                    "graphname": self.config.graphname,
                    "error": str(token_err)
                })
                self._token = None

            # If token acquired, reconnect with token for authenticated access
            if self._token:
                self._connection = TigerGraphConnection(
                    host=self.config.host,
                    username=self.config.username,
                    password=self.config.password,
                    restppPort=self.config.restpp_port,
                    graphname=self.config.graphname,
                    apiToken=self._token
                )
                # Set graph context when graph exists
                try:
                    result = self._connection.gsql(f"USE GRAPH {self.config.graphname}")
                except Exception:
                    # Ignore if graph not yet created; caller may run USE GLOBAL
                    result = None
            else:
                result = None
            
            appLogger.info({
                "function": "GraphConnector_connect",
                "status": "success",
                "graphname": self.config.graphname
            })
            
            
            return True
            
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_connect",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return False
    
    def execute_gsql(self, query: str) -> str:
        """
        Execute a GSQL query.
        
        Args:
            query: GSQL query string
            
        Returns:
            Query result as string
            
        Raises:
            Exception: If connection not established or query fails
        """
        if not self._connection:
            raise RuntimeError("Graph connection not established. Call connect() first.")
        
        try:
            result = self._connection.gsql(query)
            return result
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_execute_gsql",
                "error": str(e),
                "query": query[:200],  # Log first 200 chars
                "traceback": traceback.format_exc()
            })
            raise
    
    def execute_interpreted_query(self, query: str) -> str:
        """
        Execute an interpreted GSQL query (with USE GRAPH prefix).
        
        Args:
            query: GSQL interpreted query
            
        Returns:
            Query result as string
        """
        full_query = f"USE GRAPH {self.config.graphname}\n{query}"
        return self.execute_gsql(full_query)
    
    def upsert_vertices(self, vertex_type: str, vertices: list) -> Dict[str, Any]:
        """
        Upsert vertices into the graph.
        
        Args:
            vertex_type: Type of vertex (e.g., "Project")
            vertices: List of (vertex_id, attributes_dict) tuples
            
        Returns:
            Result dictionary from TigerGraph
        """
        # Ensure connection is still valid
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        
        try:
            # CRITICAL: Explicitly set graph context before upsert to ensure tenant isolation
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            
            result = self._connection.upsertVertices(
                vertexType=vertex_type,
                vertices=vertices
            )
            return result
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_upsert_vertices",
                "vertex_type": vertex_type,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    def upsert_edges(
        self, 
        source_vertex_type: str,
        edge_type: str,
        target_vertex_type: str,
        edges: list
    ) -> Dict[str, Any]:
        """
        Upsert edges into the graph.
        
        Args:
            source_vertex_type: Source vertex type
            edge_type: Type of edge
            target_vertex_type: Target vertex type
            edges: List of (source_id, target_id, attributes_dict) tuples
            
        Returns:
            Result dictionary from TigerGraph
        """
        # Ensure connection is still valid
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        
        try:
            # CRITICAL: Explicitly set graph context before upsert to ensure tenant isolation
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            
            result = self._connection.upsertEdges(
                sourceVertexType=source_vertex_type,
                edgeType=edge_type,
                targetVertexType=target_vertex_type,
                edges=edges
            )
            return result
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_upsert_edges",
                "edge_type": edge_type,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    def ensure_connected(self) -> bool:
        """
        Ensure connection is established and valid.
        Reconnects if connection was lost.
        
        Returns:
            True if connected, False otherwise
        """
        if not self._connection:
            return self.connect()
        
        try:
            # Try a simple query to verify connection is still valid
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            return True
        except Exception as e:
            appLogger.warning({
                "function": "GraphConnector_ensure_connected",
                "status": "connection_lost",
                "error": str(e)
            })
            # Try to reconnect
            return self.connect()
    
    def close(self):
        """Close the connection"""
        # TigerGraph connections don't need explicit closing
        self._connection = None
        self._token = None
    
    def get_vertices(self, vertex_type: str, tenant_id: int, limit: int = 1000, **kwargs) -> list:
        """
        Get vertices from the graph with proper tenant isolation.
        
        Args:
            vertex_type: Type of vertex to retrieve
            tenant_id: REQUIRED tenant ID for filtering (must match graph context)
            limit: Maximum number of vertices to return
            **kwargs: Additional arguments for getVertices
            
        Returns:
            List of vertices filtered by tenant_id
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_vertices to ensure tenant isolation")
        
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        
        try:
            # CRITICAL: Set graph context before read to ensure tenant isolation
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            
            # Get vertices and filter by tenant_id for defense-in-depth
            all_vertices = self._connection.getVertices(vertex_type, limit=limit, **kwargs)
            
            # Filter to only include vertices with matching tenant_id
            # Convert both sides to int for comparison to handle string tenant_ids
            tenant_id_int = int(tenant_id) if isinstance(tenant_id, str) else tenant_id
            filtered = [v for v in all_vertices if v.get("attributes", {}).get("tenant_id") == tenant_id_int]
            
            if len(filtered) != len(all_vertices):
                appLogger.warning({
                    "function": "GraphConnector_get_vertices",
                    "vertex_type": vertex_type,
                    "tenant_id": tenant_id,
                    "total_vertices": len(all_vertices),
                    "filtered_vertices": len(filtered),
                    "message": "Filtered out vertices with mismatched tenant_id"
                })
            
            return filtered
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_vertices",
                "vertex_type": vertex_type,
                "tenant_id": tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    def get_vertices_by_id(self, vertex_type: str, tenant_id: int, vertex_ids: list) -> list:
        """
        Get specific vertices by ID with proper tenant isolation.
        
        Args:
            vertex_type: Type of vertex
            tenant_id: REQUIRED tenant ID for filtering (must match graph context)
            vertex_ids: List of vertex IDs
            
        Returns:
            List of vertices filtered by tenant_id
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_vertices_by_id to ensure tenant isolation")
        
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        
        try:
            # CRITICAL: Set graph context before read to ensure tenant isolation
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            
            # Get vertices by ID and filter by tenant_id for defense-in-depth
            all_vertices = self._connection.getVerticesById(vertex_type, vertex_ids)
            
            # Filter to only include vertices with matching tenant_id
            # Convert both sides to int for comparison to handle string tenant_ids
            tenant_id_int = int(tenant_id) if isinstance(tenant_id, str) else tenant_id
            filtered = [v for v in all_vertices if v.get("attributes", {}).get("tenant_id") == tenant_id_int]
            
            if len(filtered) != len(all_vertices):
                appLogger.warning({
                    "function": "GraphConnector_get_vertices_by_id",
                    "vertex_type": vertex_type,
                    "tenant_id": tenant_id,
                    "requested_ids": len(vertex_ids),
                    "total_vertices": len(all_vertices),
                    "filtered_vertices": len(filtered),
                    "message": "Filtered out vertices with mismatched tenant_id"
                })
            
            return filtered
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_vertices_by_id",
                "vertex_type": vertex_type,
                "tenant_id": tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    def get_edges(self, source_vertex_type: str, source_vertex_id: str, edge_type: str, tenant_id: int, **kwargs) -> list:
        """
        Get edges from the graph with proper tenant isolation.
        
        Args:
            source_vertex_type: Source vertex type
            source_vertex_id: Source vertex ID
            edge_type: Edge type
            tenant_id: REQUIRED tenant ID for filtering (must match graph context)
            **kwargs: Additional arguments for getEdges
            
        Returns:
            List of edges (filtered by source vertex tenant_id)
        """
        if not tenant_id:
            raise ValueError("tenant_id is REQUIRED for get_edges to ensure tenant isolation")
        
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        
        try:
            # CRITICAL: Set graph context before read to ensure tenant isolation
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            
            # First verify source vertex has correct tenant_id
            source_vertices = self._connection.getVerticesById(source_vertex_type, [source_vertex_id])
            if source_vertices:
                source_tenant_id = source_vertices[0].get("attributes", {}).get("tenant_id")
                if source_tenant_id != tenant_id:
                    appLogger.warning({
                        "function": "GraphConnector_get_edges",
                        "message": "Source vertex tenant_id mismatch",
                        "expected_tenant_id": tenant_id,
                        "actual_tenant_id": source_tenant_id,
                        "source_vertex_id": source_vertex_id
                    })
                    return []  # Don't return edges from wrong tenant
            
            return self._connection.getEdges(source_vertex_type, source_vertex_id, edge_type, **kwargs)
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_edges",
                "edge_type": edge_type,
                "tenant_id": tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise

    def get_vertex_types(self) -> list:
        """Return list of vertex types for current graph context."""
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        try:
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            return self._connection.getVertexTypes()
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_vertex_types",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise

    def get_vertex_count(self, vertex_type: str) -> int:
        """Return count of vertices for a given type in current graph context."""
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        try:
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            return self._connection.getVertexCount(vertex_type)
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_vertex_count",
                "vertex_type": vertex_type,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise

    def get_edge_types(self) -> list:
        """Return list of edge types for current graph context."""
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        try:
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            return self._connection.getEdgeTypes()
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_edge_types",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise

    def get_edge_count(self, edge_type: str) -> int:
        """Return count of edges for a given type in current graph context."""
        if not self.ensure_connected():
            raise RuntimeError("Failed to establish graph connection.")
        try:
            self._connection.gsql(f"USE GRAPH {self.config.graphname}")
            return self._connection.getEdgeCount(edge_type)
        except Exception as e:
            appLogger.error({
                "function": "GraphConnector_get_edge_count",
                "edge_type": edge_type,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
