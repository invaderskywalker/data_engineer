"""
Lightweight knowledge lookups for cluster/pattern membership.

Exposes functions:
- get_project_cluster_info(project_id, tenant_id) - Get cluster info for a specific project
- get_roadmap_cluster_info(roadmap_id, tenant_id) - Get cluster info for a specific roadmap
- get_all_project_clusters(tenant_id) - Get all project patterns/clusters with resolved names
- get_all_roadmap_clusters(tenant_id) - Get all roadmap patterns/clusters with resolved names
- get_cluster_by_id(pattern_id, tenant_id) - Get detailed info for a specific pattern by vertex ID

All functions:
- Build graph connection using environment-aware graphname
- Return pattern metadata + cluster membership
- Handle errors gracefully

These functions deliberately avoid LLM flow; they are deterministic graph lookups.
"""

import os
from typing import Any, Dict, List, Optional

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.agents.functions.graphql_v2.infrastructure import (
    GraphConnector,
    GraphConnectorConfig,
)
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_database.dao.roadmap import RoadmapDao

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_graph_connector(tenant_id: int) -> Optional[GraphConnector]:
    """
    Create a GraphConnector using environment-aware graphname conventions.

    Environment mapping (matches existing usages in inference code):
    - ENVIRONMENT in {dev, qa, prod} → graphname = f"g_{env}_{tenant_id}"
    - Otherwise → returns None (no knowledge graph expected)
    """
    env = os.getenv("ENVIRONMENT", None)
    if env and env in {"dev", "qa", "prod"}:
        graphname = f"g_{env}_{tenant_id}"
    else:
        return None

    try:
        config = GraphConnectorConfig.from_env(graphname)
        connector = GraphConnector(config)
        if connector.ensure_connected():
            return connector
        appLogger.warning({
            "event": "cluster_lookup_graph_connect_fail",
            "tenant_id": tenant_id,
            "graphname": graphname,
        })
        return None
    except Exception as e:  # pragma: no cover - defensive
        appLogger.error({
            "event": "cluster_lookup_graph_connect_error",
            "tenant_id": tenant_id,
            "graphname": graphname,
            "error": str(e),
        })
        return None


def _find_all_patterns_by_membership(
    connector: GraphConnector,
    vertex_type: str,
    member_attr: str,
    entity_id: str,
    tenant_id: int,
    scope_filter: str = "workflow",
) -> List[Dict[str, Any]]:
    """
    Fetch pattern vertices for the tenant and return ALL patterns that contain
    the given entity_id inside the member_attr list.

    Only returns patterns with the specified scope (default: "workflow").
    Scope values:
    - "workflow": Cluster-level patterns (most granular, what we typically want)
    - "portfolio": Portfolio-level aggregation patterns
    - "customer": Customer-level aggregation patterns

    Returns a list of matching patterns (may be empty, single, or multiple).
    """
    # Normalize entity_id to string for comparison
    entity_id_str = str(entity_id)
    patterns: List[Dict[str, Any]] = connector.get_vertices(vertex_type, tenant_id=tenant_id)
    print(f"_find_all_patterns_by_membership: checking {len(patterns or [])} patterns for entity_id={entity_id_str} (scope_filter={scope_filter})")
    
    # Filter by scope first
    if scope_filter:
        patterns = [
            p for p in (patterns or [])
            if p.get("attributes", {}).get("scope", "") == scope_filter
        ]
        print(f"_find_all_patterns_by_membership: {len(patterns)} patterns after scope filter (scope={scope_filter})")
    
    # Debug: show all member IDs in filtered patterns
    all_member_ids = set()
    for p in patterns or []:
        attrs = p.get("attributes", {})
        members = attrs.get(member_attr, []) or []
        all_member_ids.update([str(m) for m in members])
    print(f"_find_all_patterns_by_membership: all {member_attr} in patterns: {sorted(all_member_ids)}")
    
    matching_patterns = []
    for p in patterns or []:
        attrs = p.get("attributes", {})
        members = attrs.get(member_attr, []) or []
        # Normalize members to strings for comparison
        members_str = [str(m) for m in members]
        if entity_id_str in members_str:
            print(f"_find_all_patterns_by_membership: found match in pattern {p.get('v_id')} (scope={attrs.get('scope', '')})")
            matching_patterns.append(p)
    
    print(f"_find_all_patterns_by_membership: total matches={len(matching_patterns)} for entity_id={entity_id_str}")
    return matching_patterns


def _extract_project_pattern_data(pattern_vertex: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pattern metadata from a ProjectPattern vertex."""
    attrs = pattern_vertex.get("attributes", {})
    pattern_id = pattern_vertex.get("v_id")
    return {
        "id": pattern_id,
        "name": attrs.get("name", ""),
        "description": attrs.get("description", ""),
        "explanation": attrs.get("explanation", ""),
        "category": attrs.get("category", ""),
        "scope": attrs.get("scope", ""),
        "confidence_score": attrs.get("confidence_score", 0.0),
        "support_score": attrs.get("support_score", 0.0),
        "avg_project_duration": attrs.get("avg_project_duration", 0),
        "budget_band": attrs.get("budget_band", ""),
        "key_technologies": attrs.get("key_technologies", []),
        "team_composition": attrs.get("team_composition", []),
        "dev_methodology_dist": attrs.get("dev_methodology_dist", []),
        "work_type_distribution": attrs.get("work_type_distribution", []),
        "key_kpis": attrs.get("key_kpis", []),
        "key_milestones": attrs.get("key_milestones", []),
        "constraints": attrs.get("constraints", []),
        "delivery_themes": attrs.get("delivery_themes", []),
        "delivery_approaches": attrs.get("delivery_approaches", []),
        "delivery_success_criteria": attrs.get("delivery_success_criteria", []),
        "delivery_narrative": attrs.get("delivery_narrative", ""),
        "strategic_focus": attrs.get("strategic_focus", ""),
        "maturity_level": attrs.get("maturity_level", ""),
        "implementation_complexity": attrs.get("implementation_complexity", ""),
        "governance_model": attrs.get("governance_model", ""),
        "milestone_adherence_score": attrs.get("milestone_adherence_score", 0.0),
        "delivery_success_score": attrs.get("delivery_success_score", 0.0),
    }


def _extract_roadmap_pattern_data(pattern_vertex: Dict[str, Any]) -> Dict[str, Any]:
    """Extract pattern metadata from a RoadmapPattern vertex."""
    attrs = pattern_vertex.get("attributes", {})
    pattern_id = pattern_vertex.get("v_id")
    return {
        "id": pattern_id,
        "name": attrs.get("name", ""),
        "description": attrs.get("description", ""),
        "category": attrs.get("category", ""),
        "scope": attrs.get("scope", ""),
        "confidence_score": attrs.get("confidence_score", 0.0),
        "support_score": attrs.get("support_score", 0.0),
        "typical_state_flow": attrs.get("typical_state_flow", []),
        "avg_days_per_stage": attrs.get("avg_days_per_stage", ""),
        "state_transition_narrative": attrs.get("state_transition_narrative", ""),
        "solution_themes": attrs.get("solution_themes", []),
        "solution_approaches": attrs.get("solution_approaches", []),
        "solution_success_criteria": attrs.get("solution_success_criteria", []),
        "common_priorities": attrs.get("common_priorities", []),
        "common_scopes": attrs.get("common_scopes", []),
        "budget_band": attrs.get("budget_band", ""),
        "expected_outcomes_summary": attrs.get("expected_outcomes_summary", ""),
        "team_allocations": attrs.get("team_allocations", []),
        "resource_distribution": attrs.get("resource_distribution", {}),
        "strategic_focus": attrs.get("strategic_focus", ""),
        "implementation_complexity": attrs.get("implementation_complexity", ""),
    }


def _shape_project_response(matching_patterns: List[Dict[str, Any]], project_id: str) -> Dict[str, Any]:
    """
    Shape response for project cluster lookup.
    Handles both single and multiple cluster membership.
    """
    project_id_str = str(project_id)
    
    if len(matching_patterns) == 1:
        # Single cluster membership
        pattern = matching_patterns[0]
        attrs = pattern.get("attributes", {})
        pattern_id = pattern.get("v_id")
        project_ids = attrs.get("project_ids", []) or []
        project_ids_str = [str(p) for p in project_ids]
        
        return {
            "membership": "single",
            "pattern": _extract_project_pattern_data(pattern),
            "cluster": {
                "cluster_id": pattern_id,
                "project_ids": project_ids,
                "project_count": len(project_ids),
            },
            "current_project": {
                "id": project_id,
                "position_in_cluster": project_ids_str.index(project_id_str) if project_id_str in project_ids_str else -1,
                "cluster_size": len(project_ids),
            },
        }
    else:
        # Multiple cluster membership
        patterns_data = []
        all_sibling_ids = set()
        
        for pattern in matching_patterns:
            attrs = pattern.get("attributes", {})
            pattern_id = pattern.get("v_id")
            project_ids = attrs.get("project_ids", []) or []
            project_ids_str = [str(p) for p in project_ids]
            
            # Collect all sibling project IDs (excluding current project)
            all_sibling_ids.update(project_ids_str)
            
            patterns_data.append({
                "pattern": _extract_project_pattern_data(pattern),
                "cluster": {
                    "cluster_id": pattern_id,
                    "project_ids": project_ids,
                    "project_count": len(project_ids),
                },
                "position_in_cluster": project_ids_str.index(project_id_str) if project_id_str in project_ids_str else -1,
            })
        
        # Remove the current project from sibling count
        all_sibling_ids.discard(project_id_str)
        
        return {
            "membership": "multiple",
            "cluster_count": len(matching_patterns),
            "patterns": patterns_data,
            "current_project": {
                "id": project_id,
                "cluster_count": len(matching_patterns),
                "total_sibling_projects": len(all_sibling_ids),
                "all_sibling_project_ids": sorted(all_sibling_ids),
            },
        }


def _shape_roadmap_response(matching_patterns: List[Dict[str, Any]], roadmap_id: str) -> Dict[str, Any]:
    """
    Shape response for roadmap cluster lookup.
    Handles both single and multiple cluster membership.
    """
    roadmap_id_str = str(roadmap_id)
    
    if len(matching_patterns) == 1:
        # Single cluster membership
        pattern = matching_patterns[0]
        attrs = pattern.get("attributes", {})
        pattern_id = pattern.get("v_id")
        roadmap_ids = attrs.get("roadmap_ids", []) or []
        roadmap_ids_str = [str(r) for r in roadmap_ids]
        
        return {
            "membership": "single",
            "pattern": _extract_roadmap_pattern_data(pattern),
            "cluster": {
                "cluster_id": pattern_id,
                "roadmap_ids": roadmap_ids,
                "roadmap_count": len(roadmap_ids),
            },
            "current_roadmap": {
                "id": roadmap_id,
                "position_in_cluster": roadmap_ids_str.index(roadmap_id_str) if roadmap_id_str in roadmap_ids_str else -1,
                "cluster_size": len(roadmap_ids),
            },
        }
    else:
        # Multiple cluster membership
        patterns_data = []
        all_sibling_ids = set()
        
        for pattern in matching_patterns:
            attrs = pattern.get("attributes", {})
            pattern_id = pattern.get("v_id")
            roadmap_ids = attrs.get("roadmap_ids", []) or []
            roadmap_ids_str = [str(r) for r in roadmap_ids]
            
            # Collect all sibling roadmap IDs (excluding current roadmap)
            all_sibling_ids.update(roadmap_ids_str)
            
            patterns_data.append({
                "pattern": _extract_roadmap_pattern_data(pattern),
                "cluster": {
                    "cluster_id": pattern_id,
                    "roadmap_ids": roadmap_ids,
                    "roadmap_count": len(roadmap_ids),
                },
                "position_in_cluster": roadmap_ids_str.index(roadmap_id_str) if roadmap_id_str in roadmap_ids_str else -1,
            })
        
        # Remove the current roadmap from sibling count
        all_sibling_ids.discard(roadmap_id_str)
        
        return {
            "membership": "multiple",
            "cluster_count": len(matching_patterns),
            "patterns": patterns_data,
            "current_roadmap": {
                "id": roadmap_id,
                "cluster_count": len(matching_patterns),
                "total_sibling_roadmaps": len(all_sibling_ids),
                "all_sibling_roadmap_ids": sorted(all_sibling_ids),
            },
        }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_project_cluster_info(project_id: str, tenant_id: int, scope: str = "workflow") -> Dict[str, Any]:
    """
    Locate ALL ProjectPatterns that contain the given project_id.

    Args:
        project_id: The project ID to look up
        tenant_id: The tenant ID for graph filtering
        scope: Pattern scope filter - "workflow" (default), "portfolio", or "customer"
               Only "workflow" scope patterns represent actual project clusters.

    Returns:
    - If single cluster: pattern metadata, cluster membership, current project position
    - If multiple clusters: list of all patterns with their clusters, aggregated sibling info
    - If not found: error response
    """
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        return {"error": "graph_not_available", "tenant_id": tenant_id, "project_id": project_id}

    try:
        matching_patterns = _find_all_patterns_by_membership(
            connector=connector,
            vertex_type="ProjectPattern",
            member_attr="project_ids",
            entity_id=project_id,
            tenant_id=tenant_id,
            scope_filter=scope,
        )
        if not matching_patterns:
            return {"error": "not_found", "project_id": project_id, "tenant_id": tenant_id, "scope": scope}
        return _shape_project_response(matching_patterns, project_id)
    except Exception as e:  # pragma: no cover - defensive
        appLogger.error({
            "event": "get_project_cluster_info_error",
            "project_id": project_id,
            "tenant_id": tenant_id,
            "scope": scope,
            "error": str(e),
        })
        return {"error": "unexpected_error", "project_id": project_id, "tenant_id": tenant_id, "detail": str(e)}


def get_roadmap_cluster_info(roadmap_id: str, tenant_id: int, scope: str = "workflow") -> Dict[str, Any]:
    """
    Locate ALL RoadmapPatterns that contain the given roadmap_id.

    Args:
        roadmap_id: The roadmap ID to look up
        tenant_id: The tenant ID for graph filtering
        scope: Pattern scope filter - "workflow" (default), "portfolio", or "customer"
               Only "workflow" scope patterns represent actual roadmap clusters.

    Returns:
    - If single cluster: pattern metadata, cluster membership, current roadmap position
    - If multiple clusters: list of all patterns with their clusters, aggregated sibling info
    - If not found: error response
    """
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        return {"error": "graph_not_available", "tenant_id": tenant_id, "roadmap_id": roadmap_id}

    try:
        matching_patterns = _find_all_patterns_by_membership(
            connector=connector,
            vertex_type="RoadmapPattern",
            member_attr="roadmap_ids",
            entity_id=roadmap_id,
            tenant_id=tenant_id,
            scope_filter=scope,
        )
        if not matching_patterns:
            return {"error": "not_found", "roadmap_id": roadmap_id, "tenant_id": tenant_id, "scope": scope}
        return _shape_roadmap_response(matching_patterns, roadmap_id)
    except Exception as e:  # pragma: no cover - defensive
        appLogger.error({
            "event": "get_roadmap_cluster_info_error",
            "roadmap_id": roadmap_id,
            "tenant_id": tenant_id,
            "scope": scope,
            "error": str(e),
        })
        return {"error": "unexpected_error", "roadmap_id": roadmap_id, "tenant_id": tenant_id, "detail": str(e)}


# ---------------------------------------------------------------------------
# Entity name resolution helpers
# ---------------------------------------------------------------------------


def _resolve_project_names(project_ids: List[str], tenant_id: int) -> Dict[str, str]:
    """
    Resolve project IDs to project titles using the PSQL database.
    Returns a dict mapping project_id (str) -> project_title.
    """
    if not project_ids:
        return {}
    
    try:
        # Convert to int for the DAO
        int_ids = [int(pid) for pid in project_ids if pid]
        results = ProjectsDao.FetchProjectNamesForIds(int_ids)
        
        # Build mapping
        name_map = {}
        for row in results or []:
            pid = str(row.get("project_id", ""))
            title = row.get("project_title", f"Project {pid}")
            name_map[pid] = title
        
        return name_map
    except Exception as e:
        appLogger.warning({
            "event": "resolve_project_names_error",
            "tenant_id": tenant_id,
            "project_ids_count": len(project_ids),
            "error": str(e),
        })
        # Return empty dict on failure - caller will use IDs as fallback
        return {}


def _resolve_roadmap_names(roadmap_ids: List[str], tenant_id: int) -> Dict[str, str]:
    """
    Resolve roadmap IDs to roadmap titles using the PSQL database.
    Returns a dict mapping roadmap_id (str) -> roadmap_title.
    """
    if not roadmap_ids:
        return {}
    
    try:
        # Use the existing DAO method
        results = RoadmapDao.FetchRoadmapNamesWithIDS(tenant_id, roadmap_ids)
        
        # Build mapping
        name_map = {}
        for row in results or []:
            rid = str(row.get("id", ""))
            title = row.get("title", f"Roadmap {rid}")
            name_map[rid] = title
        
        return name_map
    except Exception as e:
        appLogger.warning({
            "event": "resolve_roadmap_names_error",
            "tenant_id": tenant_id,
            "roadmap_ids_count": len(roadmap_ids),
            "error": str(e),
        })
        # Return empty dict on failure - caller will use IDs as fallback
        return {}


# ---------------------------------------------------------------------------
# Get all clusters functions
# ---------------------------------------------------------------------------


def get_all_project_clusters(tenant_id: int, scope: str = "workflow") -> Dict[str, Any]:
    """
    Retrieve ALL project patterns/clusters for the tenant.

    Args:
        tenant_id: The tenant ID for graph filtering
        scope: Pattern scope filter - "workflow" (default) for cluster-level patterns

    Returns:
        {
            "clusters": [
                {
                    "pattern_id": "ProjectPattern_12345",
                    "name": "Asset Management and Compliance Integration Pattern",
                    "description": "...",
                    "category": "...",
                    "scope": "workflow",
                    "confidence_score": 0.85,
                    "support_score": 0.72,
                    "project_count": 5,
                    "project_ids": ["4928", "5001", ...],
                    "projects": [
                        {"id": "4928", "title": "Digital Transformation Initiative"},
                        {"id": "5001", "title": "Cloud Migration Project"},
                        ...
                    ],
                    "key_technologies": [...],
                    "key_kpis": [...],
                    "budget_band": "...",
                    "avg_project_duration": ...,
                    "delivery_themes": [...],
                    "strategic_focus": "..."
                },
                ...
            ],
            "total_clusters": 18,
            "total_projects_in_clusters": 45,
            "tenant_id": "776"
        }
    """
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        return {"error": "graph_not_available", "tenant_id": tenant_id}

    try:
        # Get all ProjectPattern vertices for the tenant
        all_patterns = connector.get_vertices("ProjectPattern", tenant_id=tenant_id)
        
        # Filter by scope
        patterns = [
            p for p in (all_patterns or [])
            if p.get("attributes", {}).get("scope", "") == scope
        ]
        
        if not patterns:
            return {
                "clusters": [],
                "total_clusters": 0,
                "total_projects_in_clusters": 0,
                "tenant_id": str(tenant_id),
                "scope": scope,
            }
        
        # Collect all unique project IDs across all patterns
        all_project_ids = set()
        for p in patterns:
            attrs = p.get("attributes", {})
            project_ids = attrs.get("project_ids", []) or []
            all_project_ids.update([str(pid) for pid in project_ids])
        
        # Resolve project names in one batch
        project_names = _resolve_project_names(list(all_project_ids), tenant_id)
        
        # Build cluster summaries
        clusters = []
        for p in patterns:
            attrs = p.get("attributes", {})
            pattern_id = p.get("v_id")
            project_ids = attrs.get("project_ids", []) or []
            project_ids_str = [str(pid) for pid in project_ids]
            
            # Build projects list with resolved names
            projects = [
                {
                    "id": pid,
                    "title": project_names.get(pid, f"Project {pid}")
                }
                for pid in project_ids_str
            ]
            
            clusters.append({
                "pattern_id": pattern_id,
                "name": attrs.get("name", ""),
                "description": attrs.get("description", ""),
                "category": attrs.get("category", ""),
                "scope": attrs.get("scope", ""),
                "confidence_score": attrs.get("confidence_score", 0.0),
                "support_score": attrs.get("support_score", 0.0),
                "project_count": len(project_ids),
                "project_ids": project_ids_str,
                "projects": projects,
                "key_technologies": attrs.get("key_technologies", []),
                "key_kpis": attrs.get("key_kpis", []),
                "budget_band": attrs.get("budget_band", ""),
                "avg_project_duration": attrs.get("avg_project_duration", 0),
                "delivery_themes": attrs.get("delivery_themes", []),
                "strategic_focus": attrs.get("strategic_focus", ""),
                "maturity_level": attrs.get("maturity_level", ""),
                "implementation_complexity": attrs.get("implementation_complexity", ""),
            })
        
        return {
            "clusters": clusters,
            "total_clusters": len(clusters),
            "total_projects_in_clusters": len(all_project_ids),
            "tenant_id": str(tenant_id),
            "scope": scope,
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_all_project_clusters_error",
            "tenant_id": tenant_id,
            "scope": scope,
            "error": str(e),
        })
        return {"error": "unexpected_error", "tenant_id": tenant_id, "detail": str(e)}


def get_all_roadmap_clusters(tenant_id: int, scope: str = "workflow") -> Dict[str, Any]:
    """
    Retrieve ALL roadmap patterns/clusters for the tenant.

    Args:
        tenant_id: The tenant ID for graph filtering
        scope: Pattern scope filter - "workflow" (default) for cluster-level patterns

    Returns:
        {
            "clusters": [
                {
                    "pattern_id": "RoadmapPattern_67890",
                    "name": "Strategic Initiative Planning Pattern",
                    "description": "...",
                    "category": "...",
                    "scope": "workflow",
                    "confidence_score": 0.85,
                    "support_score": 0.72,
                    "roadmap_count": 5,
                    "roadmap_ids": ["101", "205", ...],
                    "roadmaps": [
                        {"id": "101", "title": "2024 Product Roadmap"},
                        {"id": "205", "title": "Infrastructure Modernization"},
                        ...
                    ],
                    "solution_themes": [...],
                    "common_priorities": [...],
                    "budget_band": "...",
                    "strategic_focus": "..."
                },
                ...
            ],
            "total_clusters": 12,
            "total_roadmaps_in_clusters": 38,
            "tenant_id": "776"
        }
    """
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        return {"error": "graph_not_available", "tenant_id": tenant_id}

    try:
        # Get all RoadmapPattern vertices for the tenant
        all_patterns = connector.get_vertices("RoadmapPattern", tenant_id=tenant_id)
        
        # Filter by scope
        patterns = [
            p for p in (all_patterns or [])
            if p.get("attributes", {}).get("scope", "") == scope
        ]
        
        if not patterns:
            return {
                "clusters": [],
                "total_clusters": 0,
                "total_roadmaps_in_clusters": 0,
                "tenant_id": str(tenant_id),
                "scope": scope,
            }
        
        # Collect all unique roadmap IDs across all patterns
        all_roadmap_ids = set()
        for p in patterns:
            attrs = p.get("attributes", {})
            roadmap_ids = attrs.get("roadmap_ids", []) or []
            all_roadmap_ids.update([str(rid) for rid in roadmap_ids])
        
        # Resolve roadmap names in one batch
        roadmap_names = _resolve_roadmap_names(list(all_roadmap_ids), tenant_id)
        
        # Build cluster summaries
        clusters = []
        for p in patterns:
            attrs = p.get("attributes", {})
            pattern_id = p.get("v_id")
            roadmap_ids = attrs.get("roadmap_ids", []) or []
            roadmap_ids_str = [str(rid) for rid in roadmap_ids]
            
            # Build roadmaps list with resolved names
            roadmaps = [
                {
                    "id": rid,
                    "title": roadmap_names.get(rid, f"Roadmap {rid}")
                }
                for rid in roadmap_ids_str
            ]
            
            clusters.append({
                "pattern_id": pattern_id,
                "name": attrs.get("name", ""),
                "description": attrs.get("description", ""),
                "category": attrs.get("category", ""),
                "scope": attrs.get("scope", ""),
                "confidence_score": attrs.get("confidence_score", 0.0),
                "support_score": attrs.get("support_score", 0.0),
                "roadmap_count": len(roadmap_ids),
                "roadmap_ids": roadmap_ids_str,
                "roadmaps": roadmaps,
                "solution_themes": attrs.get("solution_themes", []),
                "solution_approaches": attrs.get("solution_approaches", []),
                "common_priorities": attrs.get("common_priorities", []),
                "common_scopes": attrs.get("common_scopes", []),
                "budget_band": attrs.get("budget_band", ""),
                "strategic_focus": attrs.get("strategic_focus", ""),
                "implementation_complexity": attrs.get("implementation_complexity", ""),
                "typical_state_flow": attrs.get("typical_state_flow", []),
                "avg_days_per_stage": attrs.get("avg_days_per_stage", ""),
            })
        
        return {
            "clusters": clusters,
            "total_clusters": len(clusters),
            "total_roadmaps_in_clusters": len(all_roadmap_ids),
            "tenant_id": str(tenant_id),
            "scope": scope,
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_all_roadmap_clusters_error",
            "tenant_id": tenant_id,
            "scope": scope,
            "error": str(e),
        })
        return {"error": "unexpected_error", "tenant_id": tenant_id, "detail": str(e)}


def get_cluster_by_id(pattern_id: str, tenant_id: int, entity_type: str = "project") -> Dict[str, Any]:
    """
    Retrieve detailed information for a specific pattern/cluster by its vertex ID.

    Args:
        pattern_id: The pattern vertex ID (e.g., "ProjectPattern_12345" or "RoadmapPattern_67890")
        tenant_id: The tenant ID for graph filtering
        entity_type: "project" or "roadmap" - determines which pattern type to look up

    Returns:
        Full pattern details including:
        - Pattern metadata (name, description, category, scores, etc.)
        - Member entity IDs with resolved names
        - All pattern-specific attributes
    """
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        return {"error": "graph_not_available", "tenant_id": tenant_id, "pattern_id": pattern_id}

    try:
        vertex_type = "ProjectPattern" if entity_type == "project" else "RoadmapPattern"
        member_attr = "project_ids" if entity_type == "project" else "roadmap_ids"
        
        # Get all patterns and find the specific one by ID
        all_patterns = connector.get_vertices(vertex_type, tenant_id=tenant_id)
        
        # Find the specific pattern
        target_pattern = None
        for p in (all_patterns or []):
            if p.get("v_id") == pattern_id:
                target_pattern = p
                break
        
        if not target_pattern:
            return {
                "error": "not_found",
                "pattern_id": pattern_id,
                "tenant_id": tenant_id,
                "entity_type": entity_type,
            }
        
        attrs = target_pattern.get("attributes", {})
        
        # Get member IDs and resolve names
        member_ids = attrs.get(member_attr, []) or []
        member_ids_str = [str(mid) for mid in member_ids]
        
        if entity_type == "project":
            names_map = _resolve_project_names(member_ids_str, tenant_id)
            members = [
                {"id": mid, "title": names_map.get(mid, f"Project {mid}")}
                for mid in member_ids_str
            ]
            
            return {
                "pattern_id": pattern_id,
                "entity_type": entity_type,
                "pattern": _extract_project_pattern_data(target_pattern),
                "cluster": {
                    "member_count": len(member_ids),
                    "member_ids": member_ids_str,
                    "members": members,
                },
                "tenant_id": str(tenant_id),
            }
        else:
            names_map = _resolve_roadmap_names(member_ids_str, tenant_id)
            members = [
                {"id": mid, "title": names_map.get(mid, f"Roadmap {mid}")}
                for mid in member_ids_str
            ]
            
            return {
                "pattern_id": pattern_id,
                "entity_type": entity_type,
                "pattern": _extract_roadmap_pattern_data(target_pattern),
                "cluster": {
                    "member_count": len(member_ids),
                    "member_ids": member_ids_str,
                    "members": members,
                },
                "tenant_id": str(tenant_id),
            }
        
    except Exception as e:
        appLogger.error({
            "event": "get_cluster_by_id_error",
            "pattern_id": pattern_id,
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "error": str(e),
        })
        return {"error": "unexpected_error", "pattern_id": pattern_id, "tenant_id": tenant_id, "detail": str(e)}


def resolve_pattern_id(user_query: str, tenant_id: int, entity_type: str = "project") -> Optional[str]:
    """
    Resolve a user-friendly pattern name/description to the actual pattern vertex ID in the graph.
    
    This enables users to reference patterns by name (e.g., "Audit Process Transformation Pattern")
    instead of requiring the internal pattern_id (e.g., "pattern_0_1353").
    
    Args:
        user_query: User's natural language reference to a pattern (name, description, or partial match)
        tenant_id: The tenant ID for graph filtering
        entity_type: "project" or "roadmap" to determine which pattern type to search
    
    Returns:
        The resolved pattern_id (vertex ID) if a confident match is found, None otherwise.
    
    Examples:
        >>> resolve_pattern_id("Audit Process Transformation", 776, "project")
        "pattern_0_1353"
        
        >>> resolve_pattern_id("the audit pattern", 776, "project") 
        "pattern_0_1353"
        
        >>> resolve_pattern_id("pattern about cloud migration", 776, "project")
        "pattern_1_4928"
    """
    from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
    from src.trmeric_ml.llm.Types import ModelOptions
    
    appLogger.info({
        "event": "resolve_pattern_id_start",
        "user_query": user_query,
        "tenant_id": tenant_id,
        "entity_type": entity_type
    })
    
    connector = _build_graph_connector(tenant_id)
    if connector is None:
        appLogger.warning({
            "event": "resolve_pattern_id_no_graph",
            "tenant_id": tenant_id
        })
        return None
    
    try:
        # Get all patterns for the entity type
        vertex_type = "ProjectPattern" if entity_type == "project" else "RoadmapPattern"
        all_patterns = connector.get_vertices(vertex_type, tenant_id=tenant_id)
        
        if not all_patterns:
            appLogger.warning({
                "event": "resolve_pattern_id_no_patterns",
                "tenant_id": tenant_id,
                "entity_type": entity_type
            })
            return None
        
        # Filter to workflow scope only (actual clusters, not aggregations)
        workflow_patterns = [
            p for p in all_patterns
            if p.get("attributes", {}).get("scope") == "workflow"
        ]
        
        if not workflow_patterns:
            appLogger.warning({
                "event": "resolve_pattern_id_no_workflow_patterns",
                "tenant_id": tenant_id,
                "entity_type": entity_type,
                "total_patterns": len(all_patterns)
            })
            return None
        
        # Build pattern candidates for LLM matching
        pattern_candidates = []
        for p in workflow_patterns:
            attrs = p.get("attributes", {})
            pattern_candidates.append({
                "id": p.get("v_id"),
                "name": attrs.get("name", ""),
                "description": attrs.get("description", ""),
                "category": attrs.get("category", ""),
                "explanation": attrs.get("explanation", "")[:200] if attrs.get("explanation") else ""  # Truncate for token efficiency
            })
        
        # Use LLM to match user query to pattern
        resolution_prompt = f"""You are a pattern matching assistant. The user is trying to reference a specific pattern/cluster by name or description.

USER QUERY: "{user_query}"

AVAILABLE PATTERNS:
{chr(10).join([f'{i+1}. ID: {p["id"]} | Name: {p["name"]} | Category: {p["category"]} | Description: {p["description"][:150]}...' for i, p in enumerate(pattern_candidates)])}

TASK: Determine which pattern ID the user is most likely referring to.

MATCHING RULES:
- Exact name match has highest priority
- Partial name match (e.g., "audit" matching "Audit Process Transformation") is strong signal
- Category match is secondary signal
- Description keyword match is tertiary signal
- If user says "pattern A" or "first pattern", match by position in their recent context (often the first one shown)

RESPOND WITH ONLY THE PATTERN ID if you have >70% confidence, or "NONE" if ambiguous/not confident.

Examples:
- "Audit Process Transformation" → pattern_0_1353
- "the audit pattern" → pattern_0_1353
- "pattern about cloud" → pattern_1_4928
- "first one" → (first pattern_id from list)
- "xyz random" → NONE

PATTERN ID:"""
        
        llm = ChatGPTClient()
        model_options = ModelOptions(model="gpt-4o-mini", temperature=0.0, max_tokens=50)
        
        response = llm.run(
            prompt=resolution_prompt,
            modelOptions=model_options,
            function_caller="resolve_pattern_id",
            logInDb={"tenant_id": str(tenant_id), "entity_type": entity_type}
        )
        
        resolved_id = response.strip()
        
        # Validate that returned ID exists in our candidates
        valid_ids = [p["id"] for p in pattern_candidates]
        if resolved_id in valid_ids:
            appLogger.info({
                "event": "resolve_pattern_id_success",
                "user_query": user_query,
                "resolved_id": resolved_id,
                "tenant_id": tenant_id
            })
            return resolved_id
        elif resolved_id == "NONE":
            appLogger.warning({
                "event": "resolve_pattern_id_no_match",
                "user_query": user_query,
                "tenant_id": tenant_id,
                "llm_response": resolved_id
            })
            return None
        else:
            appLogger.warning({
                "event": "resolve_pattern_id_invalid_response",
                "user_query": user_query,
                "tenant_id": tenant_id,
                "llm_response": resolved_id,
                "valid_ids_count": len(valid_ids)
            })
            return None
            
    except Exception as e:
        appLogger.error({
            "event": "resolve_pattern_id_error",
            "user_query": user_query,
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "error": str(e)
        })
        return None
