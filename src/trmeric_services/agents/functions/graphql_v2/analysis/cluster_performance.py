"""
Cluster-Performance Analysis Engine

Integrates cluster/pattern data with project scoring to answer:
- Which clusters/patterns produce the best performing projects?
- What's the average performance of projects in a specific cluster?
- For a given project, what's its cluster AND its score together?

Combines data from:
- ProjectPattern vertices (cluster membership)
- ProjectScore vertices (performance scores)
- Project details from database
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ProjectsDao
from ..infrastructure import GraphConnector, GraphConnectorConfig
import traceback


@dataclass
class ClusterPerformanceSummary:
    """Performance summary for a cluster/pattern."""
    pattern_id: str
    pattern_name: str
    pattern_description: str
    project_count: int
    projects_with_scores: int
    avg_score: float
    min_score: int
    max_score: int
    score_distribution: Dict[str, int]  # e.g., {"excellent": 2, "good": 3, "needs_attention": 1}
    top_performer: Optional[Dict[str, Any]]
    bottom_performer: Optional[Dict[str, Any]]
    projects: List[Dict[str, Any]]  # List of projects with their scores


def _build_graph_connector(tenant_id: int) -> Optional[GraphConnector]:
    """Build graph connector using environment-aware naming."""
    env = os.getenv("ENVIRONMENT", "dev")
    graphname = f"g_{env}_{tenant_id}"
    
    try:
        config = GraphConnectorConfig.from_env(graphname)
        connector = GraphConnector(config)
        if connector.ensure_connected():
            return connector
        return None
    except Exception as e:
        appLogger.error({
            "event": "cluster_performance_graph_connect_error",
            "tenant_id": tenant_id,
            "error": str(e)
        })
        return None


def _get_all_project_scores(connector: GraphConnector, tenant_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Fetch all ProjectScore vertices and return as dict keyed by project_id.
    """
    try:
        all_scores = connector._connection.getVertices("ProjectScore", limit=500)
        if not all_scores:
            return {}
        
        scores_by_project = {}
        for score_vertex in all_scores:
            if isinstance(score_vertex, dict):
                attrs = score_vertex.get("attributes", {})
                vertex_tenant_id = attrs.get("tenant_id")
                if str(vertex_tenant_id) == str(tenant_id):
                    project_id = str(attrs.get("project_id", ""))
                    if project_id:
                        scores_by_project[project_id] = {
                            "score_id": score_vertex.get("v_id", ""),
                            "project_id": project_id,
                            "project_title": attrs.get("project_title", ""),
                            "core_score": attrs.get("core_score", 0),
                            "on_time_score": attrs.get("on_time_score", 0),
                            "on_scope_score": attrs.get("on_scope_score", 0),
                            "on_budget_score": attrs.get("on_budget_score", 0),
                            "risk_management_score": attrs.get("risk_management_score", 0),
                            "team_health_score": attrs.get("team_health_score", 0),
                            "llm_explanation": attrs.get("llm_explanation", ""),
                            "confidence_overall": attrs.get("confidence_overall", 0),
                        }
        return scores_by_project
    except Exception as e:
        appLogger.error({
            "event": "_get_all_project_scores_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {}


def _get_all_project_patterns(connector: GraphConnector, tenant_id: int) -> List[Dict[str, Any]]:
    """
    Fetch all ProjectPattern vertices for the tenant (workflow scope only).
    """
    try:
        all_patterns = connector.get_vertices("ProjectPattern", tenant_id=tenant_id)
        if not all_patterns:
            return []
        
        # Filter to workflow scope (the actual clusters, not portfolio/customer aggregations)
        workflow_patterns = [
            p for p in all_patterns
            if p.get("attributes", {}).get("scope") == "workflow"
        ]
        return workflow_patterns
    except Exception as e:
        appLogger.error({
            "event": "_get_all_project_patterns_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def _categorize_score(score: int) -> str:
    """Categorize a score into performance bands."""
    if score >= 80:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 60:
        return "fair"
    else:
        return "needs_attention"


def get_cluster_performance_summary(
    tenant_id: int,
    pattern_id: str,
    connector: Optional[GraphConnector] = None
) -> Dict[str, Any]:
    """
    Get performance summary for a specific cluster/pattern.
    
    Args:
        tenant_id: Tenant ID
        pattern_id: The pattern vertex ID (e.g., "ProjectPattern_12345")
        connector: Optional existing graph connector
        
    Returns:
        Performance summary including avg score, score distribution, top/bottom performers
    """
    try:
        if connector is None:
            connector = _build_graph_connector(tenant_id)
        if connector is None:
            return {"error": "graph_connection_failed"}
        
        # Get the specific pattern
        patterns = _get_all_project_patterns(connector, tenant_id)
        target_pattern = None
        for p in patterns:
            if p.get("v_id") == pattern_id:
                target_pattern = p
                break
        
        if not target_pattern:
            return {"error": "pattern_not_found", "pattern_id": pattern_id}
        
        attrs = target_pattern.get("attributes", {})
        project_ids = attrs.get("project_ids", []) or []
        project_ids_str = [str(pid) for pid in project_ids]
        
        if not project_ids_str:
            return {
                "pattern_id": pattern_id,
                "pattern_name": attrs.get("name", ""),
                "pattern_description": attrs.get("description", ""),
                "project_count": 0,
                "projects_with_scores": 0,
                "avg_score": 0,
                "message": "No projects in this cluster"
            }
        
        # Get all scores
        scores_by_project = _get_all_project_scores(connector, tenant_id)
        
        # Match cluster projects with their scores
        projects_with_scores = []
        for pid in project_ids_str:
            score_data = scores_by_project.get(pid)
            if score_data:
                projects_with_scores.append(score_data)
        
        if not projects_with_scores:
            return {
                "pattern_id": pattern_id,
                "pattern_name": attrs.get("name", ""),
                "pattern_description": attrs.get("description", ""),
                "project_count": len(project_ids_str),
                "projects_with_scores": 0,
                "avg_score": 0,
                "message": "No score data available for projects in this cluster"
            }
        
        # Calculate statistics
        core_scores = [p["core_score"] for p in projects_with_scores]
        avg_score = round(sum(core_scores) / len(core_scores), 1)
        
        # Score distribution
        distribution = {"excellent": 0, "good": 0, "fair": 0, "needs_attention": 0}
        for score in core_scores:
            category = _categorize_score(score)
            distribution[category] += 1
        
        # Sort by score
        sorted_projects = sorted(projects_with_scores, key=lambda x: x["core_score"], reverse=True)
        
        return {
            "pattern_id": pattern_id,
            "pattern_name": attrs.get("name", ""),
            "pattern_description": attrs.get("description", ""),
            "pattern_category": attrs.get("category", ""),
            "project_count": len(project_ids_str),
            "projects_with_scores": len(projects_with_scores),
            "avg_score": avg_score,
            "min_score": min(core_scores),
            "max_score": max(core_scores),
            "score_distribution": distribution,
            "top_performer": sorted_projects[0] if sorted_projects else None,
            "bottom_performer": sorted_projects[-1] if sorted_projects else None,
            "all_projects": sorted_projects
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_cluster_performance_summary_error",
            "pattern_id": pattern_id,
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "cluster_performance_lookup_failed", "detail": str(e)}


def rank_clusters_by_performance(
    tenant_id: int,
    connector: Optional[GraphConnector] = None
) -> Dict[str, Any]:
    """
    Rank all clusters by their average project performance.
    
    Returns clusters sorted from best to worst performing, with stats.
    """
    try:
        if connector is None:
            connector = _build_graph_connector(tenant_id)
        if connector is None:
            return {"error": "graph_connection_failed"}
        
        # Get all patterns and scores
        patterns = _get_all_project_patterns(connector, tenant_id)
        scores_by_project = _get_all_project_scores(connector, tenant_id)
        
        if not patterns:
            return {"error": "no_patterns_found", "tenant_id": tenant_id}
        
        if not scores_by_project:
            return {"error": "no_scores_found", "tenant_id": tenant_id}
        
        # Calculate performance for each cluster
        cluster_performances = []
        
        for pattern in patterns:
            attrs = pattern.get("attributes", {})
            pattern_id = pattern.get("v_id", "")
            project_ids = attrs.get("project_ids", []) or []
            project_ids_str = [str(pid) for pid in project_ids]
            
            # Get scores for cluster projects
            cluster_scores = []
            for pid in project_ids_str:
                score_data = scores_by_project.get(pid)
                if score_data:
                    cluster_scores.append(score_data["core_score"])
            
            if cluster_scores:
                avg_score = round(sum(cluster_scores) / len(cluster_scores), 1)
                cluster_performances.append({
                    "pattern_id": pattern_id,
                    "pattern_name": attrs.get("name", "Unknown"),
                    "pattern_description": attrs.get("description", ""),
                    "pattern_category": attrs.get("category", ""),
                    "project_count": len(project_ids_str),
                    "projects_with_scores": len(cluster_scores),
                    "avg_score": avg_score,
                    "min_score": min(cluster_scores),
                    "max_score": max(cluster_scores),
                    "score_spread": max(cluster_scores) - min(cluster_scores),
                    "performance_tier": _categorize_score(int(avg_score))
                })
        
        if not cluster_performances:
            return {
                "error": "no_clusters_with_scores",
                "message": "Found patterns but none have projects with scores"
            }
        
        # Sort by average score (best first)
        cluster_performances.sort(key=lambda x: x["avg_score"], reverse=True)
        
        # Add rank
        for i, cluster in enumerate(cluster_performances):
            cluster["rank"] = i + 1
        
        # Calculate overall stats
        all_avg_scores = [c["avg_score"] for c in cluster_performances]
        
        return {
            "total_clusters": len(cluster_performances),
            "overall_avg_score": round(sum(all_avg_scores) / len(all_avg_scores), 1),
            "best_performing_cluster": cluster_performances[0] if cluster_performances else None,
            "worst_performing_cluster": cluster_performances[-1] if cluster_performances else None,
            "clusters_ranked": cluster_performances,
            "performance_tiers": {
                "excellent": len([c for c in cluster_performances if c["performance_tier"] == "excellent"]),
                "good": len([c for c in cluster_performances if c["performance_tier"] == "good"]),
                "fair": len([c for c in cluster_performances if c["performance_tier"] == "fair"]),
                "needs_attention": len([c for c in cluster_performances if c["performance_tier"] == "needs_attention"]),
            }
        }
        
    except Exception as e:
        appLogger.error({
            "event": "rank_clusters_by_performance_error",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "cluster_ranking_failed", "detail": str(e)}


def get_project_cluster_and_performance(
    tenant_id: int,
    project_id: str,
    connector: Optional[GraphConnector] = None
) -> Dict[str, Any]:
    """
    Get combined cluster membership AND performance score for a single project.
    
    Answers: "What type of project is this, and how is it performing?"
    """
    try:
        if connector is None:
            connector = _build_graph_connector(tenant_id)
        if connector is None:
            return {"error": "graph_connection_failed"}
        
        project_id_str = str(project_id)
        
        # Get score for this project
        scores_by_project = _get_all_project_scores(connector, tenant_id)
        project_score = scores_by_project.get(project_id_str)
        
        # Find which cluster(s) this project belongs to
        patterns = _get_all_project_patterns(connector, tenant_id)
        matching_clusters = []
        
        for pattern in patterns:
            attrs = pattern.get("attributes", {})
            project_ids = attrs.get("project_ids", []) or []
            project_ids_str = [str(pid) for pid in project_ids]
            
            if project_id_str in project_ids_str:
                # Get cluster performance stats for context
                cluster_scores = []
                for pid in project_ids_str:
                    score_data = scores_by_project.get(pid)
                    if score_data:
                        cluster_scores.append(score_data["core_score"])
                
                cluster_avg = round(sum(cluster_scores) / len(cluster_scores), 1) if cluster_scores else 0
                
                matching_clusters.append({
                    "pattern_id": pattern.get("v_id", ""),
                    "pattern_name": attrs.get("name", ""),
                    "pattern_description": attrs.get("description", ""),
                    "pattern_category": attrs.get("category", ""),
                    "cluster_size": len(project_ids_str),
                    "cluster_avg_score": cluster_avg,
                    "cluster_projects_with_scores": len(cluster_scores)
                })
        
        # Get project details from database
        try:
            project_details = ProjectsDao.fetchInfoForListOfProjects([int(project_id)])
            project_info = project_details[0] if project_details else {}
        except:
            project_info = {}
        
        result = {
            "project_id": project_id_str,
            "project_title": project_score.get("project_title", "") if project_score else project_info.get("project_title", "Unknown"),
        }
        
        # Add score info
        if project_score:
            result["has_score"] = True
            result["score"] = {
                "core_score": project_score["core_score"],
                "on_time_score": project_score["on_time_score"],
                "on_scope_score": project_score["on_scope_score"],
                "on_budget_score": project_score["on_budget_score"],
                "risk_management_score": project_score["risk_management_score"],
                "team_health_score": project_score["team_health_score"],
                "performance_tier": _categorize_score(project_score["core_score"]),
                "llm_explanation": project_score.get("llm_explanation", "")
            }
        else:
            result["has_score"] = False
            result["score"] = None
        
        # Add cluster info
        if matching_clusters:
            result["has_cluster"] = True
            result["clusters"] = matching_clusters
            
            # Compare to cluster average
            if project_score and matching_clusters:
                primary_cluster = matching_clusters[0]
                if primary_cluster["cluster_avg_score"] > 0:
                    diff = project_score["core_score"] - primary_cluster["cluster_avg_score"]
                    result["vs_cluster_avg"] = {
                        "difference": round(diff, 1),
                        "comparison": "above_average" if diff > 0 else "below_average" if diff < 0 else "at_average",
                        "cluster_name": primary_cluster["pattern_name"]
                    }
        else:
            result["has_cluster"] = False
            result["clusters"] = []
        
        # Add project details
        if project_info:
            result["project_details"] = {
                "project_type": project_info.get("project_type", ""),
                "start_date": str(project_info.get("start_date", "")) if project_info.get("start_date") else None,
                "end_date": str(project_info.get("end_date", "")) if project_info.get("end_date") else None,
                "project_manager": project_info.get("project_manager_name", ""),
                "delivery_status": project_info.get("delivery_status", ""),
            }
        
        return result
        
    except Exception as e:
        appLogger.error({
            "event": "get_project_cluster_and_performance_error",
            "project_id": project_id,
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"error": "project_lookup_failed", "detail": str(e)}
