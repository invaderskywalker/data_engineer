"""
Knowledge Graph Analysis Functions

All 5 analyst functions for cluster and performance analysis.
Main docstrings are in actions.py (user-facing). These are implementation only.
"""

import os
from typing import Dict, List, Any, Optional, Literal
import traceback

from src.trmeric_api.logging.AppLogger import appLogger
from ..infrastructure import GraphConnector, GraphConnectorConfig
from .cluster_performance import (
    get_cluster_performance_summary,
    rank_clusters_by_performance,
    get_project_cluster_and_performance,
    _build_graph_connector,
    _get_all_project_scores,
)
from .score_analysis import get_project_scores_from_graph, fetch_project_details
from ..knowledge.cluster_lookup import (
    get_project_cluster_info,
    get_roadmap_cluster_info,
    get_all_project_clusters,
    get_all_roadmap_clusters,
    get_cluster_by_id,
    resolve_pattern_id,
)


# =============================================================================
# CONSOLIDATED PARAMETER-DRIVEN FUNCTIONS (2)
# =============================================================================

def fetch_cluster_info(
    tenant_id: int,
    entity_id: Optional[str] = None,
    pattern_id: Optional[str] = None,
    list_all: bool = False,
    entity_type: str = "project"
) -> Dict[str, Any]:
    """Smart cluster info retrieval with parameter routing. See actions.py for docs."""
    try:
        modes_specified = sum([list_all, bool(entity_id), bool(pattern_id)])
        if modes_specified == 0:
            return {"error": "specify_list_all_entity_id_or_pattern_id"}
        if modes_specified > 1:
            return {"error": "specify_only_one_mode"}
        
        if list_all:
            appLogger.info({
                "event": "fetch_cluster_info_list_all",
                "tenant_id": tenant_id,
                "entity_type": entity_type
            })
            if entity_type == "project":
                return get_all_project_clusters(tenant_id=tenant_id)
            else:  # roadmap
                return get_all_roadmap_clusters(tenant_id=tenant_id)
        
        elif pattern_id:
            # PATTERN RESOLUTION: Try to resolve pattern_id if it looks like a name instead of an ID
            # Pattern IDs typically look like "pattern_0_1353", "pattern_1_4928", etc.
            # If pattern_id doesn't start with "pattern_", assume it's a user-friendly name and resolve it
            resolved_id = pattern_id
            if not pattern_id.startswith("pattern_"):
                appLogger.info({
                    "event": "fetch_cluster_info_resolving_pattern_name",
                    "tenant_id": tenant_id,
                    "user_input": pattern_id,
                    "entity_type": entity_type
                })
                resolved_id = resolve_pattern_id(
                    user_query=pattern_id,
                    tenant_id=tenant_id,
                    entity_type=entity_type
                )
                if resolved_id is None:
                    appLogger.warning({
                        "event": "fetch_cluster_info_pattern_resolution_failed",
                        "tenant_id": tenant_id,
                        "user_input": pattern_id,
                        "entity_type": entity_type
                    })
                    return {
                        "error": "pattern_not_found",
                        "message": f"Could not find a pattern matching '{pattern_id}'. Please check the pattern name or use list_all=True to see all available patterns.",
                        "user_input": pattern_id
                    }
                appLogger.info({
                    "event": "fetch_cluster_info_pattern_resolved",
                    "tenant_id": tenant_id,
                    "user_input": pattern_id,
                    "resolved_id": resolved_id
                })
            
            appLogger.info({
                "event": "fetch_cluster_info_details",
                "tenant_id": tenant_id,
                "pattern_id": resolved_id,
                "original_input": pattern_id if resolved_id != pattern_id else None,
                "entity_type": entity_type
            })
            return get_cluster_by_id(pattern_id=resolved_id, tenant_id=tenant_id, entity_type=entity_type)
        
        elif entity_id:
            appLogger.info({
                "event": "fetch_cluster_info_entity",
                "tenant_id": tenant_id,
                "entity_id": entity_id,
                "entity_type": entity_type
            })
            if entity_type == "project":
                return get_project_cluster_info(project_id=entity_id, tenant_id=tenant_id)
            else:  # roadmap
                return get_roadmap_cluster_info(roadmap_id=entity_id, tenant_id=tenant_id)
    
    except Exception as e:
        appLogger.error({
            "event": "fetch_cluster_info_error",
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "pattern_id": pattern_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "cluster_info_lookup_failed", "detail": str(e)}


def fetch_performance_analysis(
    tenant_id: int,
    analysis_type: Literal["performers", "cluster", "rankings", "project"] = "performers",
    target_id: Optional[str] = None,
    mode: Literal["top", "bottom", "both"] = "both",
    n: int = 5,
    with_insights: bool = False
) -> Dict[str, Any]:
    """Smart performance analysis with parameter routing. See actions.py for docs."""
    try:
        if analysis_type == "performers":
            appLogger.info({
                "event": "fetch_performance_analysis_performers",
                "tenant_id": tenant_id,
                "mode": mode,
                "n": n,
                "with_insights": with_insights
            })
            
            # Build connector for graph access
            connector = _build_graph_connector(tenant_id=tenant_id)
            if not connector:
                return {"error": "graph_connection_failed"}
            
            performers_data = {}
            # Fetch both top and bottom performers based on mode
            if mode in ["top", "both"]:
                top_performers = get_project_scores_from_graph(
                    graph_connector=connector,
                    tenant_id=tenant_id,
                    rank_type="highest",
                    n=n
                )
                performers_data["top_performers"] = top_performers if top_performers else []
            
            if mode in ["bottom", "both"]:
                bottom_performers = get_project_scores_from_graph(
                    graph_connector=connector,
                    tenant_id=tenant_id,
                    rank_type="lowest",
                    n=n
                )
                performers_data["bottom_performers"] = bottom_performers if bottom_performers else []
            
            if with_insights and isinstance(performers_data, dict):
                # Get cluster rankings once instead of per-project lookups
                cluster_data = rank_clusters_by_performance(tenant_id=tenant_id, connector=connector)
                cluster_list = cluster_data.get("clusters_ranked", []) if isinstance(cluster_data, dict) else []
                
                pattern_insights = {
                    "top_patterns": {}, 
                    "bottom_patterns": {}, 
                    "key_observations": "",
                    "cluster_context": cluster_list[:3] if cluster_list else []
                }
                
                performers_data["pattern_insights"] = pattern_insights
            
            return performers_data
        
        elif analysis_type == "cluster":
            if not target_id:
                return {"error": "target_id_required_for_cluster_analysis"}
            
            appLogger.info({
                "event": "fetch_performance_analysis_cluster",
                "tenant_id": tenant_id,
                "target_id": target_id
            })
            return get_cluster_performance_summary(pattern_id=target_id, tenant_id=tenant_id)
        
        elif analysis_type == "rankings":
            appLogger.info({
                "event": "fetch_performance_analysis_rankings",
                "tenant_id": tenant_id
            })
            return rank_clusters_by_performance(tenant_id=tenant_id)
        
        elif analysis_type == "project":
            if not target_id:
                return {"error": "target_id_required_for_project_analysis"}
            
            appLogger.info({
                "event": "fetch_performance_analysis_project",
                "tenant_id": tenant_id,
                "target_id": target_id
            })
            return get_project_cluster_and_performance(tenant_id=tenant_id, project_id=target_id)
        
        else:
            return {"error": "invalid_analysis_type", "valid_types": ["performers", "cluster", "rankings", "project"]}
    
    except Exception as e:
        appLogger.error({
            "event": "fetch_performance_analysis_error",
            "tenant_id": tenant_id,
            "analysis_type": analysis_type,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "performance_analysis_failed", "detail": str(e)}


# =============================================================================
# COMPOUND EXECUTIVE FUNCTIONS (3)
# =============================================================================

def fetch_performance_landscape(
    tenant_id: int,
    top_n: int = 3,
    bottom_n: int = 3
) -> Dict[str, Any]:
    """Portfolio overview: rankings + performers + insights. See actions.py for docs."""
    try:
        appLogger.info({
            "event": "fetch_performance_landscape_start",
            "tenant_id": tenant_id,
            "top_n": top_n,
            "bottom_n": bottom_n
        })
        
        # 1. Build connector
        connector = _build_graph_connector(tenant_id=tenant_id)
        if not connector:
            return {"error": "graph_connection_failed"}
        
        # 2. Get all project scores
        all_scores_list = get_project_scores_from_graph(
            graph_connector=connector,
            tenant_id=tenant_id,
            rank_type="highest",
            n=1000  # Fetch all scores for this portfolio
        )
        
        # 3. Get cluster rankings
        cluster_rankings = rank_clusters_by_performance(tenant_id=tenant_id, connector=connector)
        
        # Check for errors in cluster rankings
        if isinstance(cluster_rankings, dict) and "error" in cluster_rankings:
            appLogger.warning({
                "event": "fetch_performance_landscape_cluster_error",
                "tenant_id": tenant_id,
                "error": cluster_rankings.get("error")
            })
            # Continue with what we have, just no cluster data
            cluster_list = []
        else:
            cluster_list = cluster_rankings.get("clusters_ranked", []) if isinstance(cluster_rankings, dict) else cluster_rankings
        
        if not all_scores_list:
            return {
                "cluster_rankings": cluster_list,
                "top_performers": [],
                "bottom_performers": [],
                "insights": "No score data available"
            }
        
        # Convert list to scores
        all_scores = all_scores_list
        
        # 3. Sort and slice top/bottom (use core_score as the primary score)
        sorted_scores = sorted(all_scores, key=lambda x: x.get("core_score", 0), reverse=True)
        top_performers = sorted_scores[:top_n] if len(sorted_scores) >= top_n else sorted_scores
        # For bottom performers, we need to reverse since we want lowest scores
        bottom_performers = sorted(sorted_scores[-bottom_n:], key=lambda x: x.get("core_score", 0)) if len(sorted_scores) >= bottom_n else sorted(sorted_scores, key=lambda x: x.get("core_score", 0))
        
        # 4. Generate insights (cluster info already available in cluster_rankings)
        insights = {
            "total_projects": len(all_scores),
            "total_clusters": len(cluster_list),
            "top_cluster": cluster_list[0].get("pattern_name") if cluster_list and len(cluster_list) > 0 else None,
            "bottom_cluster": cluster_list[-1].get("pattern_name") if cluster_list and len(cluster_list) > 0 else None,
            "average_score": sum(p.get("core_score", 0) for p in all_scores) / len(all_scores) if all_scores else 0
        }
        
        appLogger.info({
            "event": "fetch_performance_landscape_success",
            "tenant_id": tenant_id,
            "total_clusters": insights["total_clusters"]
        })
        
        return {
            "cluster_rankings": cluster_list,
            "top_performers": top_performers,
            "bottom_performers": bottom_performers,
            "insights": insights
        }
    
    except Exception as e:
        appLogger.error({
            "event": "fetch_performance_landscape_error",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "performance_landscape_failed", "detail": str(e)}


def analyze_project_in_context(
    tenant_id: int,
    project_id: str
) -> Dict[str, Any]:
    """Project deep-dive: score + cluster + peers. See actions.py for docs."""
    try:
        appLogger.info({
            "event": "analyze_project_in_context_start",
            "tenant_id": tenant_id,
            "project_id": project_id
        })
        
        # Get comprehensive project + cluster + performance data
        result = get_project_cluster_and_performance(tenant_id=tenant_id, project_id=project_id)
        
        if not result or "error" in result:
            return result
        
        # Add project details if available
        try:
            # fetch_project_details expects a list of project IDs
            project_id_int = int(project_id) if isinstance(project_id, str) else project_id
            project_details_list = fetch_project_details(tenant_id=tenant_id, project_ids=[project_id_int])
            if project_details_list and len(project_details_list) > 0:
                result["project_details"] = project_details_list[0]
        except:
            pass
        
        # Generate contextual insights
        if result.get("has_score") and result.get("has_cluster"):
            # Get cluster average from first cluster (primary cluster)
            clusters = result.get("clusters", [])
            cluster_avg = clusters[0].get("cluster_avg_score", 0) if clusters else 0
            
            score_data = result.get("score", {})
            project_score = score_data.get("core_score", 0) if isinstance(score_data, dict) else 0
            
            # Only generate recommendation if cluster_avg is non-zero to avoid division by zero
            if cluster_avg > 0:
                if project_score > cluster_avg:
                    result["recommendation"] = f"Project performing {((project_score - cluster_avg) / cluster_avg * 100):.1f}% above cluster average"
                else:
                    result["recommendation"] = f"Project performing {((cluster_avg - project_score) / cluster_avg * 100):.1f}% below cluster average"
        
        appLogger.info({
            "event": "analyze_project_in_context_success",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "has_score": result.get("has_score"),
            "has_cluster": result.get("has_cluster")
        })
        
        return result
    
    except Exception as e:
        appLogger.error({
            "event": "analyze_project_in_context_error",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "project_context_analysis_failed", "detail": str(e)}


def find_success_patterns(
    tenant_id: int,
    top_n: int = 3
) -> Dict[str, Any]:
    """Strategic analysis: what patterns drive success. See actions.py for docs."""
    try:
        appLogger.info({
            "event": "find_success_patterns_start",
            "tenant_id": tenant_id,
            "top_n": top_n
        })
        
        # 1. Build connector
        connector = _build_graph_connector(tenant_id=tenant_id)
        if not connector:
            return {"error": "graph_connection_failed"}
        
        # 2. Get cluster rankings
        cluster_rankings_result = rank_clusters_by_performance(tenant_id=tenant_id, connector=connector)
        cluster_rankings = cluster_rankings_result.get("clusters_ranked", []) if isinstance(cluster_rankings_result, dict) else []
        
        if not cluster_rankings or len(cluster_rankings) == 0:
            return {
                "success_patterns": [],
                "anti_patterns": [],
                "insights": "No cluster data available"
            }
        
        # 2. Get top N clusters
        top_clusters = cluster_rankings[:top_n]
        bottom_clusters = cluster_rankings[-top_n:] if len(cluster_rankings) >= top_n else []
        
        # 3. Enrich with details
        success_patterns = []
        for cluster in top_clusters:
            pattern_id = cluster.get("pattern_id")
            try:
                details = get_cluster_performance_summary(pattern_id=pattern_id, tenant_id=tenant_id)
                if details:
                    success_patterns.append({
                        "pattern_name": cluster.get("pattern_name"),
                        "average_score": cluster.get("avg_score"),  # Note: rank_clusters_by_performance returns "avg_score"
                        "member_count": cluster.get("project_count"),  # Note: cluster field is "project_count" not "member_count"
                        "details": details
                    })
            except:
                success_patterns.append(cluster)
        
        anti_patterns = []
        for cluster in bottom_clusters:
            pattern_id = cluster.get("pattern_id")
            try:
                details = get_cluster_performance_summary(pattern_id=pattern_id, tenant_id=tenant_id)
                if details:
                    anti_patterns.append({
                        "pattern_name": cluster.get("pattern_name"),
                        "average_score": cluster.get("avg_score"),  # Note: rank_clusters_by_performance returns "avg_score"
                        "member_count": cluster.get("project_count"),  # Note: cluster field is "project_count" not "member_count"
                        "details": details
                    })
            except:
                anti_patterns.append(cluster)
        
        # 4. Generate strategic insights
        insights = {
            "total_patterns_analyzed": len(cluster_rankings),
            "best_pattern": success_patterns[0].get("pattern_name") if success_patterns else None,
            "worst_pattern": anti_patterns[-1].get("pattern_name") if anti_patterns else None,
            "score_gap": (
                (success_patterns[0].get("average_score") or 0) - (anti_patterns[-1].get("average_score") or 0)
                if success_patterns and anti_patterns else 0
            )
        }
        
        appLogger.info({
            "event": "find_success_patterns_success",
            "tenant_id": tenant_id,
            "patterns_found": len(success_patterns)
        })
        
        return {
            "success_patterns": success_patterns,
            "anti_patterns": anti_patterns,
            "insights": insights,
            "recommendation": f"Focus on '{insights['best_pattern']}' patterns for best results" if insights.get("best_pattern") else "Insufficient data for recommendations"
        }
    
    except Exception as e:
        appLogger.error({
            "event": "find_success_patterns_error",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "success_pattern_analysis_failed", "detail": str(e)}
