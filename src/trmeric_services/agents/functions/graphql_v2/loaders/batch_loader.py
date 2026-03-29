"""
Batch Graph Loader

High-level interface for loading complete graph structures (vertices + edges).
"""

from typing import Dict, List, Tuple, Any
from collections import defaultdict
import json
from ..infrastructure import GraphConnector, get_edge_type_mapping
from .vertex_loader import VertexLoader
from .edge_loader import EdgeLoader


# Import edge type mapping from consolidated schema
EDGE_TYPE_MAPPING = get_edge_type_mapping()


class BatchGraphLoader:
    """
    High-level loader for complete graph structures.
    Handles loading both vertices and edges with proper ordering.
    """
    
    def __init__(
        self,
        graph_connector: GraphConnector,
        vertex_batch_size: int = 10,
        edge_batch_size: int = 10,
        max_retries: int = 3
    ):
        """
        Args:
            graph_connector: GraphConnector instance
            vertex_batch_size: Batch size for vertex loading
            edge_batch_size: Batch size for edge loading
            max_retries: Maximum retry attempts
        """
        self.graph_connector = graph_connector
        
        self.vertex_loader = VertexLoader(
            graph_connector=self.graph_connector,
            batch_size=vertex_batch_size,
            max_retries=max_retries
        )
        self.edge_loader = EdgeLoader(
            graph_connector=self.graph_connector,
            batch_size=edge_batch_size,
            max_retries=max_retries
        )
        # Track loaded vertex IDs across multiple calls to support multi-stage loading
        self.loaded_vertex_ids = defaultdict(set)
    
    def load_graph_structure(
        self,
        vertices: Dict[str, List[Tuple[str, Dict[str, Any]]]],
        edges: Dict[str, List[Tuple[str, str]]]
    ) -> Dict[str, Any]:
        """
        Load complete graph structure (vertices + edges).
        
        Args:
            vertices: Dictionary mapping vertex_type -> list of (id, attributes) tuples
            edges: Dictionary mapping edge_type -> list of (source_id, target_id) tuples
            
        Returns:
            Dictionary with loading statistics
        """
        print("\n" + "="*80)
        print("BATCH GRAPH LOADER - Starting graph structure load")
        print("="*80)
        
        # Extract tenant_id from first vertex (all vertices in a batch should have same tenant)
        self.current_tenant_id = None
        for vertex_type, vertex_data in vertices.items():
            if vertex_data and len(vertex_data) > 0:
                _, attrs = vertex_data[0]
                self.current_tenant_id = attrs.get("tenant_id")
                break
        
        stats = {
            "vertices": {},
            "edges": {},
            "total_vertices_loaded": 0,
            "total_edges_loaded": 0,
            "total_vertices_failed": 0,
            "total_edges_failed": 0,
            "edges_filtered_out": 0,
        }
        
        # Phase 1: Load all vertices
        print("\n--- PHASE 1: Loading Vertices ---")
        
        for vertex_type, vertex_data in vertices.items():
            print(f"\nLoading {vertex_type} vertices ({len(vertex_data)} items)...")
            result = self.vertex_loader.load_vertices(vertex_type, vertex_data)
            stats["vertices"][vertex_type] = result
            stats["total_vertices_loaded"] += result["loaded"]
            stats["total_vertices_failed"] += result["failed"]
            
            # Track loaded IDs for edge validation
            current_ids = {str(vertex_id) for vertex_id, _ in vertex_data}
            self.loaded_vertex_ids[vertex_type].update(current_ids)
        
        # Phase 1.5: Pre-populate loaded_vertex_ids with existing vertices referenced in edges
        # This handles cases where edges reference vertices loaded in previous operations
        self._prepopulate_edge_target_vertices(edges)
        
        # Phase 2: Load all edges (with filtering to prevent stub vertex creation)
        print("\n--- PHASE 2: Loading Edges (with validation) ---")
        for edge_type, edge_data in edges.items():
            # Get vertex types for this edge
            edge_configs = EDGE_TYPE_MAPPING.get(edge_type)
            if not edge_configs:
                print(f"⚠ Warning: Unknown edge type '{edge_type}', skipping...")
                continue
            
            # Group valid edges by configuration
            # Key: (from_type, to_type), Value: list of (from_id, to_id)
            valid_edges_by_config = defaultdict(list)
            filtered_edges = []
            
            for from_id, to_id in edge_data:
                from_id_str = str(from_id)
                to_id_str = str(to_id)
                
                matched = False
                for config in edge_configs:
                    from_type = config["from"]
                    to_type = config["to"]
                    
                    # Check if both vertices were loaded
                    from_exists = from_id_str in self.loaded_vertex_ids.get(from_type, set())
                    to_exists = to_id_str in self.loaded_vertex_ids.get(to_type, set())
                    
                    if from_exists and to_exists:
                        valid_edges_by_config[(from_type, to_type)].append((from_id, to_id))
                        matched = True
                        break
                
                if not matched:
                    filtered_edges.append((from_id, to_id))
            
            # Report filtering
            if filtered_edges:
                print(f"\n  ⚠ Filtering {len(filtered_edges)} edges for {edge_type}:")
                for from_id, to_id in filtered_edges[:3]:  # Show first 3
                    print(f"    - {from_id} -> {to_id} (no matching source/target types found)")
                if len(filtered_edges) > 3:
                    print(f"    ... and {len(filtered_edges) - 3} more")
                stats["edges_filtered_out"] += len(filtered_edges)
            
            # Load valid edges for each configuration
            total_valid = sum(len(v) for v in valid_edges_by_config.values())
            print(f"\nLoading {edge_type} edges ({total_valid}/{len(edge_data)} valid)...")
            
            if total_valid == 0:
                print(f"  No valid {edge_type} edges to load")
                continue

            for (from_type, to_type), batch_edges in valid_edges_by_config.items():
                print(f"  {from_type} -> {to_type} ({len(batch_edges)} edges)")
                
                result = self.edge_loader.load_edges(
                    edge_type=edge_type,
                    from_vertex_type=from_type,
                    to_vertex_type=to_type,
                    data=batch_edges
                )
                
                if edge_type not in stats["edges"]:
                    stats["edges"][edge_type] = {"loaded": 0, "failed": 0, "total": 0}
                
                stats["edges"][edge_type]["loaded"] += result["loaded"]
                stats["edges"][edge_type]["failed"] += result["failed"]
                stats["edges"][edge_type]["total"] += result["total"]
                
                stats["total_edges_loaded"] += result["loaded"]
                stats["total_edges_failed"] += result["failed"]
        
        # Summary
        print("\n" + "="*80)
        print("BATCH GRAPH LOADER - Summary")
        print("="*80)
        print(f"Vertices Loaded: {stats['total_vertices_loaded']}")
        print(f"Vertices Failed: {stats['total_vertices_failed']}")
        print(f"Edges Loaded: {stats['total_edges_loaded']}")
        print(f"Edges Failed: {stats['total_edges_failed']}")
        print(f"Edges Filtered (to prevent stub vertices): {stats['edges_filtered_out']}")
        print("="*80 + "\n")
        
        return stats
    
    def _prepopulate_edge_target_vertices(self, edges: Dict[str, List[Tuple[str, str]]]):
        """
        Query graph for vertices that will be edge targets but weren't loaded in this batch.
        This ensures edge validation doesn't filter out edges to vertices loaded in previous operations.
        
        Args:
            edges: Dictionary mapping edge_type -> list of (source_id, target_id) tuples
        """
        # Collect all vertex IDs referenced in edges, grouped by inferred type
        vertex_ids_to_check = defaultdict(set)
        
        for edge_type, edge_data in edges.items():
            edge_configs = EDGE_TYPE_MAPPING.get(edge_type, [])
            
            for from_id, to_id in edge_data:
                from_id_str = str(from_id)
                to_id_str = str(to_id)
                
                # For each edge config, track which vertex types we need
                for config in edge_configs:
                    from_type = config["from"]
                    to_type = config["to"]
                    
                    # Only query for vertices NOT already tracked
                    if from_id_str not in self.loaded_vertex_ids.get(from_type, set()):
                        vertex_ids_to_check[from_type].add(from_id_str)
                    if to_id_str not in self.loaded_vertex_ids.get(to_type, set()):
                        vertex_ids_to_check[to_type].add(to_id_str)
        
        if not vertex_ids_to_check:
            return
        
        print("\n--- PHASE 1.5: Checking existing edge target vertices ---")
        
        # Query graph for each vertex type to verify which IDs exist
        for vertex_type, vertex_ids in vertex_ids_to_check.items():
            if not vertex_ids:
                continue
                
            print(f"Checking {len(vertex_ids)} {vertex_type} vertices...")
            
            try:
                # Query vertices by ID to see which exist
                existing = self.graph_connector.get_vertices_by_id(
                    vertex_type=vertex_type,
                    tenant_id=self.current_tenant_id,
                    vertex_ids=list(vertex_ids)
                )
                
                if existing:
                    existing_ids = set()
                    for v in existing:
                        if isinstance(v, dict):
                            vid = v.get("v_id") or v.get("id") or v.get("primary_id")
                            if vid:
                                existing_ids.add(str(vid))
                    
                    self.loaded_vertex_ids[vertex_type].update(existing_ids)
                    print(f"  ✓ Found {len(existing_ids)} existing {vertex_type} vertices")
            except Exception as e:
                # If query fails, assume vertices exist (edge creation will fail if they don't)
                print(f"  ⚠ Could not verify {vertex_type} vertices (will attempt edge creation anyway): {e}")
                self.loaded_vertex_ids[vertex_type].update(vertex_ids)
    
    def load_customer_data(
        self,
        customer_data: List[Dict[str, Any]],
        tenant_id: int = None
    ) -> Dict[str, Any]:
        """
        Load customer, industry, and industry sector data.
        
        Args:
            customer_data: List of customer data dictionaries with structure:
                {
                    "customer": {...},
                    "industry": {...},
                    "industry_sector": {...}
                }
            tenant_id: Tenant ID to stamp on all vertices. Required for correct
                       tenant isolation — every vertex must carry the owning tenant's ID.
        
        Returns:
            Dictionary with loading statistics
        """
        vertices = defaultdict(list)
        edges = defaultdict(list)
        
        for data in customer_data:
            # Customer vertex
            customer = data.get("customer", {})
            if customer:
                vertices["Customer"].append((
                    customer["id"],
                    {
                        "id": customer["id"],
                        "tenant_id": tenant_id or customer.get("tenant_id") or 0,
                        "name": customer.get("name", customer["id"].capitalize()),
                        "company_size": customer.get("company_size", 0),
                        "location": customer.get("location", ""),
                        "revenue": customer.get("revenue", 0),
                        "employees": customer.get("employees", 0),
                        "it_budget": customer.get("it_budget", 0),
                        "created_date": customer.get("created_date", ""),
                    }
                ))
            
            # Industry vertex
            industry = data.get("industry", {})
            if industry:
                # Handle regulatory_requirements as JSON string, comma-separated string, or list
                reg_reqs = industry.get("regulatory_requirements", [])
                if isinstance(reg_reqs, str):
                    # Try parsing as JSON first
                    try:
                        reg_reqs = json.loads(reg_reqs)
                        if not isinstance(reg_reqs, list):
                            reg_reqs = []
                    except (json.JSONDecodeError, ValueError):
                        # Fall back to comma-separated string
                        reg_reqs = reg_reqs.split(",") if reg_reqs else []
                elif not isinstance(reg_reqs, list):
                    reg_reqs = []
                
                # Clean up whitespace from string elements
                reg_reqs = [str(r).strip() for r in reg_reqs if r]
                
                vertices["Industry"].append((
                    industry["id"],
                    {
                        "id": industry["id"],
                        "tenant_id": tenant_id or industry.get("tenant_id") or 0,
                        "name": industry.get("name", "Unknown"),
                        "regulatory_requirements": reg_reqs,
                    }
                ))
            
            # IndustrySector vertex
            industry_sector = data.get("industry_sector", {})
            if industry_sector:
                vertices["IndustrySector"].append((
                    industry_sector["id"],
                    {
                        "id": industry_sector["id"],
                        "tenant_id": tenant_id or industry_sector.get("tenant_id") or 0,
                        "name": industry_sector.get("name", "Unknown"),
                        "description": industry_sector.get("description", ""),
                    }
                ))
            
            # Edges
            if customer and industry:
                edges["belongsToIndustry"].append((customer["id"], industry["id"]))
            if industry and industry_sector:
                edges["belongsToSector"].append((industry["id"], industry_sector["id"]))
        
        return self.load_graph_structure(dict(vertices), dict(edges))
