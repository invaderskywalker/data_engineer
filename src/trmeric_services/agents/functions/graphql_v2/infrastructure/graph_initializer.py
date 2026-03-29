"""
Graph Schema Initializer

Utility for initializing a TigerGraph with the consolidated TrmericGraph schema.
Handles schema creation, graph creation, and graph management.

Usage:
    initializer = GraphSchemaInitializer()
"""

import logging
from typing import Optional, Dict, Any
import pyTigerGraph as tg
from src.trmeric_api.logging.AppLogger import appLogger
from .config import GraphConnectorConfig
from .graph_connector import GraphConnector
from .trmeric_schema import (
    get_schema_creation_script,
    get_graph_creation_script,
    get_schema_summary,
)


class GraphSchemaInitializer:
    """Initialize and manage TigerGraph schemas"""
    
    def __init__(self, config: Optional[GraphConnectorConfig] = None, graphname: str = ""):
        """
        Initialize schema initializer with TigerGraph configuration
        
        Args:
            config: GraphConnectorConfig instance. If None, loads from environment via GraphConnectorConfig.from_env()
            graphname: TigerGraph graph name to use (required, cannot be empty)
        """
        if not graphname:
            raise ValueError("graphname is required and cannot be empty")
        if config is None:
            config = GraphConnectorConfig.from_env(graphname)
        
        self.config = config
        self.graphname = graphname
    
    def get_connector(self, graphname: str = "TrmericGraph") -> GraphConnector:
        """
        Get GraphConnector instance for the specified graph.
        
        Args:
            graphname: Name of graph to connect to
            
        Returns:
            Connected GraphConnector instance
            
        Raises:
            RuntimeError: If connection fails
        """
        try:
            # Create config for specified graphname
            config = GraphConnectorConfig.from_env(graphname)
            # Create and connect the connector
            connector = GraphConnector(config)
            if not connector.connect():
                raise RuntimeError(f"Failed to connect to graph: {graphname}")
            appLogger.info(f"✓ Connected to graph: {graphname}")
            return connector
        except Exception as e:
            appLogger.error(f"Connection error: {e}")
            raise
    
    def create_schema_types(self) -> bool:
        """Create all vertex and edge types in the database (global, run once)."""
        try:
            connector = self.get_connector(self.graphname)
            appLogger.info("Creating schema types (global)...")

            schema_script = get_schema_creation_script()
            result = connector.execute_gsql(f"USE GLOBAL\n{schema_script}")
            
            appLogger.info("✓ Schema types created successfully")
            appLogger.debug(f"Result: {result}")
            connector.close()
            return True
        except Exception as e:
            appLogger.error(f"Schema creation error: {e}")
            return False

    def create_graph_plain(self, graphname: str = "TrmericGraph") -> bool:
        """
        Create a new TigerGraph assuming Schemas already exist
        Args:
            graphname: Name of graph to create
        Returns:
            True if successful, False otherwise
        """        
        try:
            appLogger.info(f"Creating graph '{graphname}'...")
            connector = self.get_connector(graphname)
            
            graph_script = get_graph_creation_script(graphname)
            result = connector.execute_gsql(f"USE GLOBAL\n{graph_script}")
            
            appLogger.info(f"✓ Graph '{graphname}' created successfully")
            appLogger.debug(f"Result: {result}")
            connector.close()
            return True
        except Exception as e:
            appLogger.error(f"Graph creation error: {e}")
            return False
    
    def create_graph(self, graphname: str = "TrmericGraph") -> bool:
        """Create a new TigerGraph using pre-existing global schema types."""
        try:
            appLogger.info(f"Creating graph '{graphname}' using existing schema types...")
            connector = self.get_connector(graphname)

            graph_script = get_graph_creation_script(graphname)
            result = connector.execute_gsql(f"USE GLOBAL\n{graph_script}")
            
            appLogger.info(f"✓ Graph '{graphname}' created successfully")
            appLogger.debug(f"Result: {result}")
            connector.close()
            return True
        except Exception as e:
            appLogger.error(f"Graph creation error: {e}")
            return False
    
    def drop_graph(self, graphname: str = "TrmericGraph") -> bool:
        """
        Drop a graph
        
        Args:
            graphname: Name of graph to drop
            
        Returns:
            True if successful, False otherwise
        """
        try:
            connector = self.get_connector(graphname)
            appLogger.warning(f"Dropping graph '{graphname}'...")
            
            result = connector.execute_gsql(f"USE GLOBAL\nDROP GRAPH {graphname}")
            appLogger.info(f"✓ Graph '{graphname}' dropped successfully")
            connector.close()
            return True
        except Exception as e:
            appLogger.error(f"Drop graph error: {e}")
            return False
    
    def recreate_graph_plain(self, graphname: str = "TrmericGraph") -> bool:
        """
        Drop and recreate a graph assuming Schemas already exist
        
        Args:
            graphname: Name of graph to recreate
            
        Returns:
            True if successful, False otherwise
        """
        appLogger.info(f"Recreating graph '{graphname}'...")
        
        # Drop existing graph
        try:
            self.drop_graph(graphname)
        except:
            appLogger.info(f"Graph '{graphname}' did not exist or already dropped")
        
        # Create new graph
        return self.create_graph_plain(graphname)

    def recreate_graph(self, graphname: str = "TrmericGraph") -> bool:
        """
        Drop and recreate a graph
        
        Args:
            graphname: Name of graph to recreate
            
        Returns:
            True if successful, False otherwise
        """
        appLogger.info(f"Recreating graph '{graphname}'...")
        
        # Drop existing graph
        try:
            self.drop_graph(graphname)
        except:
            appLogger.info(f"Graph '{graphname}' did not exist or already dropped")
        
        # Create new graph
        return self.create_graph(graphname)
    
    def get_graph_stats(self, graphname: str = "TrmericGraph") -> Dict[str, Any]:
        """
        Get statistics about a graph
        
        Args:
            graphname: Name of graph
            
        Returns:
            Dictionary with vertex and edge counts
        """
        try:
            connector = self.get_connector(graphname)
            
            stats = {"vertices": {}, "edges": {}}
            
            # Get vertex counts
            try:
                vertex_types = connector.get_vertex_types()
                for vtype in vertex_types:
                    try:
                        count = connector.get_vertex_count(vtype)
                        stats["vertices"][vtype] = count
                    except Exception as e:
                        stats["vertices"][vtype] = "error"
            except Exception:
                appLogger.warning("Could not fetch vertex types/counts")
            
            # Get edge counts
            try:
                edge_types = connector.get_edge_types()
                for etype in edge_types:
                    try:
                        count = connector.get_edge_count(etype)
                        stats["edges"][etype] = count
                    except Exception as e:
                        stats["edges"][etype] = "error"
            except Exception:
                appLogger.warning("Could not fetch edge types/counts")
            
            connector.close()
            return stats
        except Exception as e:
            appLogger.error(f"Error getting stats: {e}")
            return {}
    
    def print_schema_info(self):
        """Print schema information"""
        info = get_schema_summary()
        
        print("\n" + "=" * 80)
        print("TrmericGraph Consolidated Schema")
        print("=" * 80)
        print(f"\nTotal Vertex Types: {info['total_vertices']}")
        print(f"Total Edge Types: {info['total_edges']}")
        
        print(f"\n✓ Project Entities ({len(info['project_vertices'])} vertices):")
        for vtype in info['project_vertices']:
            print(f"  • {vtype}")
        
        print(f"\n✓ Roadmap Entities ({len(info['roadmap_vertices'])} vertices):")
        for vtype in info['roadmap_vertices']:
            print(f"  • {vtype}")
        
        print(f"\n✓ Pattern & Analysis Entities ({len(info['pattern_vertices'])} vertices):")
        for vtype in info['pattern_vertices']:
            print(f"  • {vtype}")
        
        print(f"\n✓ Cross-Cutting Entities ({len(info['cross_cutting_vertices'])} vertices):")
        for vtype in info['cross_cutting_vertices']:
            print(f"  • {vtype}")
        
        print("\n" + "=" * 80)
    
    def print_graph_stats(self, graphname: str = "TrmericGraph"):
        """Print graph statistics"""
        stats = self.get_graph_stats(graphname)
        
        if not stats["vertices"] and not stats["edges"]:
            print(f"No stats available for graph '{graphname}'")
            return
        
        print("\n" + "=" * 80)
        print(f"Graph Statistics: {graphname}")
        print("=" * 80)
        
        total_vertices = sum(v for v in stats["vertices"].values() if isinstance(v, int))
        print(f"\nVertices ({total_vertices} total):")
        for vtype, count in sorted(stats["vertices"].items()):
            if isinstance(count, int):
                print(f"  • {vtype}: {count}")
            else:
                print(f"  • {vtype}: {count}")
        
        total_edges = sum(e for e in stats["edges"].values() if isinstance(e, int))
        print(f"\nEdges ({total_edges} total):")
        for etype, count in sorted(stats["edges"].items()):
            if isinstance(count, int):
                print(f"  • {etype}: {count}")
            else:
                print(f"  • {etype}: {count}")
        
        print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys
    
    # CLI for testing
    initializer = GraphSchemaInitializer()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        graph_name = sys.argv[2] if len(sys.argv) > 2 else "TrmericGraph"
        
        if cmd == "schema":
            initializer.print_schema_info()
        elif cmd == "create":
            success = initializer.create_graph(graph_name)
            sys.exit(0 if success else 1)
        elif cmd == "drop":
            success = initializer.drop_graph(graph_name)
            sys.exit(0 if success else 1)
        elif cmd == "recreate":
            success = initializer.recreate_graph(graph_name)
            sys.exit(0 if success else 1)
        elif cmd == "stats":
            initializer.print_graph_stats(graph_name)
        else:
            print(f"Usage: python {sys.argv[0]} [schema|create|drop|recreate|stats] [graph_name]")
    else:
        initializer.print_schema_info()
