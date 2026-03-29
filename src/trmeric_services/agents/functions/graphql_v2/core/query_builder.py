"""
Query Builder - Constructs GSQL Queries

This module handles the generation of GSQL queries from QueryPlans,
including privacy filtering and batch processing.
"""

from typing import List, Dict, Any
from ..models.query_plan import QueryPlan
from ..models.graph_schema import GraphSchema
from ..models.privacy_models import PrivacyScope
from src.trmeric_api.logging.AppLogger import appLogger


class QueryBuilder:
    """
    Builds GSQL interpreted queries from QueryPlans.
    
    Handles:
    - Dynamic query generation based on plan
    - Privacy-aware filtering
    - Batch processing
    - Filter query generation
    """
    
    def __init__(self, schema: GraphSchema, graphname: str = "TrmericGraph"):
        """
        Initialize query builder.
        
        Args:
            schema: Graph schema for the entity type
            graphname: Name of the TigerGraph graph
        """
        self.schema = schema
        self.graphname = graphname
    
    def build_entity_query(self, plan: QueryPlan) -> str:
        """
        Build main entity query from plan.
        
        Args:
            plan: Query plan
            
        Returns:
            GSQL interpreted query string
        """
        if not plan.entity_ids:
            raise ValueError("No entity IDs provided in query plan")
        
        query_lines = [f"USE GRAPH {self.graphname}"]
        query_lines.append(f"INTERPRET QUERY () FOR GRAPH {self.graphname} {{")
        query_lines.append("")
        
        # Select all entities first
        entity_var_prefix = plan.entity_type.lower()[:4]  # e.g., "proj" for Project
        
        for entity_id in plan.entity_ids:
            var_name = f"{entity_var_prefix}_{entity_id}"
            query_lines.append(
                f"  {var_name} = SELECT e FROM {plan.entity_type}:e "
                f'WHERE e.id == "{entity_id}";'
            )
        
        query_lines.append("")
        
        # Print entity attributes if requested
        if plan.entity_type in plan.vertices_to_query:
            for entity_id in plan.entity_ids:
                var_name = f"{entity_var_prefix}_{entity_id}"
                attrs = plan.attributes_to_query.get(plan.entity_type, [])
                
                if attrs:
                    attr_list = ", ".join(f"{var_name}.{attr}" for attr in attrs)
                    query_lines.append(f"  PRINT {var_name}[{attr_list}];")
                else:
                    query_lines.append(f"  PRINT {var_name};")
        
        query_lines.append("")
        
        # Traverse edges and print connected vertices
        for entity_id in plan.entity_ids:
            source_var = f"{entity_var_prefix}_{entity_id}"
            
            for edge_name in plan.edges_to_query:
                edge_def = self.schema.get_edge(edge_name)
                if not edge_def or edge_def["from"] != plan.entity_type:
                    continue
                
                target_vertex = edge_def["to"]
                target_var = f"{target_vertex.lower()}_{entity_id}"
                
                query_lines.append(
                    f"  {target_var} = SELECT v FROM {source_var} "
                    f"-({edge_name})-> {target_vertex}:v;"
                )
                
                # Print target vertex attributes if requested
                if target_vertex in plan.vertices_to_query:
                    attrs = plan.attributes_to_query.get(target_vertex, [])
                    
                    if attrs:
                        attr_list = ", ".join(f"{target_var}.{attr}" for attr in attrs)
                        query_lines.append(f"  PRINT {target_var}[{attr_list}];")
                    else:
                        query_lines.append(f"  PRINT {target_var};")
            
            query_lines.append("")
        
        query_lines.append("}")
        
        return "\n".join(query_lines)
    
    def build_filter_query(self, plan: QueryPlan) -> str:
        """
        Build filter query to get entity IDs matching criteria.
        
        Args:
            plan: Query plan with filters
            
        Returns:
            GSQL filter query string
        """
        if not plan.filters:
            raise ValueError("No filters provided in query plan")
        
        # Map vertex types to their edges from the main entity
        vertex_edge_map = {
            edge_def["to"]: edge_name
            for edge_name, edge_def in self.schema.edges.items()
            if edge_def["from"] == plan.entity_type
        }
        
        query_lines = [f"USE GRAPH {self.graphname}"]
        query_lines.append(f"INTERPRET QUERY () FOR GRAPH {self.graphname} {{")
        
        # Build FROM clauses and WHERE conditions
        from_clauses = []
        where_conditions = []
        alias_counter = 0
        
        for vertex_type, filter_attrs in plan.filters.items():
            edge_name = vertex_edge_map.get(vertex_type)
            if not edge_name:
                continue
            
            alias = f"v{alias_counter}"
            alias_counter += 1
            
            from_clause = (
                f"{plan.entity_type}:e -({edge_name})-> {vertex_type}:{alias}"
            )
            from_clauses.append(from_clause)
            
            # Build WHERE conditions for this vertex
            for attr, value in filter_attrs.items():
                if isinstance(value, str):
                    where_conditions.append(f'{alias}.{attr} == "{value}"')
                else:
                    where_conditions.append(f'{alias}.{attr} == {value}')
        
        # Construct query
        query_lines.append(f"  filtered_entities = SELECT e FROM {', '.join(from_clauses)}")
        
        if where_conditions:
            query_lines.append(f"    WHERE {' AND '.join(where_conditions)};")
        else:
            query_lines.append(";")
        
        query_lines.append("  PRINT filtered_entities[filtered_entities.id, filtered_entities.title];")
        query_lines.append("}")
        
        return "\n".join(query_lines)
    
    def build_batched_queries(
        self, 
        plan: QueryPlan,
        batch_size: int = 5
    ) -> List[str]:
        """
        Build multiple queries for batch processing.
        
        Args:
            plan: Query plan
            batch_size: Number of entities per batch
            
        Returns:
            List of GSQL query strings
        """
        # If no entity IDs, build a query to fetch all entities of the type
        if not plan.entity_ids:
            query = self._build_get_all_query(plan)
            return [query] if query else []
        
        queries = []
        
        for i in range(0, len(plan.entity_ids), batch_size):
            batch_ids = plan.entity_ids[i:i + batch_size]
            
            # Create batch-specific plan
            batch_plan = QueryPlan(
                vertices_to_query=plan.vertices_to_query,
                edges_to_query=plan.edges_to_query,
                entity_ids=batch_ids,
                attributes_to_query=plan.attributes_to_query,
                filters=plan.filters,
                privacy_scope=plan.privacy_scope,
                entity_type=plan.entity_type
            )
            
            query = self.build_entity_query(batch_plan)
            queries.append(query)
        
        appLogger.info({
            "function": "QueryBuilder_build_batched_queries",
            "total_entities": len(plan.entity_ids),
            "batch_size": batch_size,
            "num_batches": len(queries)
        })
        
        return queries
    
    def _build_get_all_query(self, plan: QueryPlan) -> str:
        """
        Build a query to fetch all entities of a given type.
        
        Args:
            plan: Query plan with entity type
            
        Returns:
            GSQL interpreted query string
        """
        query_lines = [f"USE GRAPH {self.graphname}"]
        query_lines.append(f"INTERPRET QUERY () FOR GRAPH {self.graphname} {{")
        query_lines.append("")
        
        entity_var = "entities"
        entity_type = plan.entity_type
        
        # Get all entities of the type
        query_lines.append(
            f"  {entity_var} = SELECT e FROM {entity_type}:e;"
        )
        query_lines.append("")
        
        # Print entity data
        query_lines.append(f"  PRINT {entity_var};")
        query_lines.append("")
        query_lines.append("}")
        
        query = "\n".join(query_lines)
        
        appLogger.info({
            "function": "QueryBuilder_build_get_all_query",
            "entity_type": entity_type,
            "graphname": self.graphname
        })
        
        return query
