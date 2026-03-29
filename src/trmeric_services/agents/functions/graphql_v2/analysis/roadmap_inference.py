"""
Roadmap Inference Engine

LLM-based roadmap pattern matching and generation advice.
Takes minimal roadmap information (name, description) and:
1. Retrieves roadmap patterns from TigerGraph database
2. Uses LLM to match against patterns
3. Generates advice based on matching patterns

Uses RoadmapPattern vertices from TigerGraph as comparison basis.
Standalone function that can be used for roadmap generation support.
"""

from typing import Dict, List, Any, Optional
import os
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient, ModelOptions
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from ..infrastructure import GraphConnector, GraphConnectorConfig
from src.trmeric_database.dao.roadmap import RoadmapDao
import json
import traceback




def format_guidance_for_canvas_stages(inference_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Format the inference result into stage-specific guidance dictionaries
    optimized for each roadmap canvas creation stage (basic, okr, cpc).
    
    This function extracts and formats the most relevant information from
    the inference result for each specific stage, making it easy to consume
    in the prompt templates.
    
    Args:
        inference_result: Full result from infer_roadmap()
        
    Returns:
        Dictionary with keys 'basic', 'okr', 'cpc', each containing
        stage-specific guidance formatted for prompt injection
    """
    # Extract components from inference result
    matched_pattern = inference_result.get("matched_pattern", {})
    dim_guidance = inference_result.get("dimension_guidance", {})
    sol_guidance = inference_result.get("solution_guidance", "")
    pattern_ref = inference_result.get("pattern_reference", {})
    template_examples = inference_result.get("template_examples", [])
    state_narrative = inference_result.get("state_transition_narrative", "")
    
    # Build similar roadmaps reference string
    roadmap_names = pattern_ref.get("roadmap_names", [])
    similar_roadmaps_str = ", ".join(roadmap_names[:5]) if roadmap_names else ""
    roadmap_count = pattern_ref.get("roadmap_count", 0)
    
    # ============ BASIC STAGE GUIDANCE ============
    # Needs: name/description inspiration, type, priority, timeline, business_value, budget
    basic_guidance = {
        "has_guidance": bool(matched_pattern),
        "similar_roadmaps": similar_roadmaps_str,
        "roadmap_count": roadmap_count,
        "solution_narrative": sol_guidance if sol_guidance else "",
        # Timeline guidance
        "timeline_guidance": dim_guidance.get("timeline", ""),
        "typical_state_flow": " -> ".join(matched_pattern.get("typical_state_flow", [])),
        "avg_days_per_stage": matched_pattern.get("avg_days_per_stage", ""),
        "state_transition_narrative": state_narrative if state_narrative else "",
        # Type and priority patterns
        "common_priorities": matched_pattern.get("common_priorities", []),
        "solution_themes": matched_pattern.get("solution_themes", []),
        # Business value patterns
        "business_value_guidance": dim_guidance.get("business_value", ""),
        "budget_band": matched_pattern.get("budget_band", ""),
        "expected_outcomes_summary": matched_pattern.get("expected_outcomes_summary", ""),
        # Template examples for inspiration
        "template_examples": [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "roadmap_type": t.get("roadmap_type", ""),
                "priority": t.get("priority", "")
            }
            for t in template_examples[:2]
        ] if template_examples else []
    }
    
    # ============ OKR STAGE GUIDANCE ============
    # Needs: objectives, key_results, org_strategy_align
    okr_guidance = {
        "has_guidance": bool(matched_pattern),
        "similar_roadmaps": similar_roadmaps_str,
        "roadmap_count": roadmap_count,
        # Objectives guidance
        "objectives_guidance": dim_guidance.get("objectives", ""),
        "solution_approaches": matched_pattern.get("solution_approaches", []),
        "solution_success_criteria": matched_pattern.get("solution_success_criteria", []),
        "strategic_focus": matched_pattern.get("strategic_focus", ""),
        # Key results guidance
        "key_kpis": matched_pattern.get("key_kpis", []),
        "key_milestones": matched_pattern.get("key_milestones", []),
        # Template objectives for inspiration
        "template_objectives": [
            {
                "objectives": t.get("objectives", ""),
                "strategic_goal": t.get("strategic_goal", ""),
                "org_strategy_align": t.get("org_strategy_align", "")
            }
            for t in template_examples[:2]
        ] if template_examples else []
    }
    
    # ============ CPC STAGE GUIDANCE ============
    # Needs: constraints, portfolio, roadmap_category
    cpc_guidance = {
        "has_guidance": bool(matched_pattern),
        "similar_roadmaps": similar_roadmaps_str,
        "roadmap_count": roadmap_count,
        # Constraints guidance
        "constraints_guidance": dim_guidance.get("constraints", ""),
        "pattern_constraints": matched_pattern.get("constraints", []),
        "implementation_complexity": matched_pattern.get("implementation_complexity", ""),
        # Portfolio guidance
        "portfolio_guidance": dim_guidance.get("portfolio", ""),
        "common_scopes": matched_pattern.get("common_scopes", []),
        # Category guidance  
        "category_guidance": dim_guidance.get("category", ""),
        # Team/resource patterns
        "team_allocations": matched_pattern.get("team_allocations", []),
        "resource_distribution": matched_pattern.get("resource_distribution", {}),
        # Template categories for reference
        "template_categories": [
            {
                "category": t.get("category", ""),
                "tags": t.get("tags", "")
            }
            for t in template_examples[:2]
        ] if template_examples else []
    }
    
    guidance_dict = {
        "basic": basic_guidance,
        "okr": okr_guidance,
        "cpc": cpc_guidance
    }
    
    return guidance_dict


def format_basic_stage_prompt_section(guidance: Dict[str, Any]) -> str:
    """Format the basic stage guidance into a prompt-ready string."""
    if not guidance.get("has_guidance"):
        return ""
    
    sections = []
    sections.append("### Strategic Guidance from Historical Patterns:")
    
    if guidance.get("similar_roadmaps"):
        sections.append(f"**Similar Roadmaps ({guidance.get('roadmap_count', 0)} total)**: {guidance['similar_roadmaps']}")
    
    if guidance.get("solution_narrative"):
        sections.append(f"\n**Solution Context**:\n{guidance['solution_narrative']}")
    
    # Timeline section
    timeline_parts = []
    if guidance.get("typical_state_flow"):
        timeline_parts.append(f"- Typical Flow: {guidance['typical_state_flow']}")
    if guidance.get("avg_days_per_stage"):
        timeline_parts.append(f"- Stage Durations: {guidance['avg_days_per_stage']}")
    if guidance.get("timeline_guidance"):
        timeline_parts.append(f"- Timeline Insight: {guidance['timeline_guidance']}")
    if timeline_parts:
        sections.append("\n**Timeline Patterns**:\n" + "\n".join(timeline_parts))
    
    # Priority and type patterns
    if guidance.get("common_priorities"):
        sections.append(f"\n**Common Priorities**: {', '.join(guidance['common_priorities'][:5])}")
    if guidance.get("solution_themes"):
        sections.append(f"**Solution Themes**: {', '.join(guidance['solution_themes'][:5])}")
    
    # Business value section
    bv_parts = []
    if guidance.get("budget_band"):
        bv_parts.append(f"- Budget Band: {guidance['budget_band']}")
    if guidance.get("expected_outcomes_summary"):
        bv_parts.append(f"- Expected Outcomes: {guidance['expected_outcomes_summary']}")
    if guidance.get("business_value_guidance"):
        bv_parts.append(f"- Business Value Pattern: {guidance['business_value_guidance']}")
    if bv_parts:
        sections.append("\n**Business Value Patterns**:\n" + "\n".join(bv_parts))
    
    # Template examples
    if guidance.get("template_examples"):
        examples = []
        for t in guidance["template_examples"]:
            if t.get("name"):
                examples.append(f"- {t['name']}: {t.get('description', '')}")
        if examples:
            sections.append("\n**Reference Templates**:\n" + "\n".join(examples))
    
    return "\n".join(sections)


def format_okr_stage_prompt_section(guidance: Dict[str, Any]) -> str:
    """Format the OKR stage guidance into a prompt-ready string."""
    if not guidance.get("has_guidance"):
        return ""
    
    sections = []
    sections.append("### Strategic Guidance from Historical Patterns:")
    
    if guidance.get("similar_roadmaps"):
        sections.append(f"**Similar Roadmaps ({guidance.get('roadmap_count', 0)} total)**: {guidance['similar_roadmaps']}")
    
    # Objectives section
    obj_parts = []
    if guidance.get("objectives_guidance"):
        obj_parts.append(f"- Objectives Pattern: {guidance['objectives_guidance']}")
    if guidance.get("solution_approaches"):
        obj_parts.append(f"- Proven Approaches: {', '.join(guidance['solution_approaches'][:5])}")
    if guidance.get("strategic_focus"):
        obj_parts.append(f"- Strategic Focus: {guidance['strategic_focus']}")
    if obj_parts:
        sections.append("\n**Objectives Guidance**:\n" + "\n".join(obj_parts))
    
    # Key results section
    kr_parts = []
    if guidance.get("key_kpis"):
        kr_parts.append(f"- Key KPIs from Similar Roadmaps: {', '.join(guidance['key_kpis'][:5])}")
    if guidance.get("key_milestones"):
        kr_parts.append(f"- Common Milestones: {', '.join(guidance['key_milestones'][:5])}")
    if guidance.get("solution_success_criteria"):
        kr_parts.append(f"- Success Criteria: {', '.join(guidance['solution_success_criteria'][:5])}")
    if kr_parts:
        sections.append("\n**Key Results Guidance**:\n" + "\n".join(kr_parts))
    
    # Template objectives
    if guidance.get("template_objectives"):
        examples = []
        for t in guidance["template_objectives"]:
            if t.get("objectives"):
                examples.append(f"- Objectives: {t['objectives']}")
            if t.get("strategic_goal"):
                examples.append(f"  Strategic Goal: {t['strategic_goal']}")
        if examples:
            sections.append("\n**Reference Template OKRs**:\n" + "\n".join(examples))
    
    return "\n".join(sections)


def format_cpc_stage_prompt_section(guidance: Dict[str, Any]) -> str:
    """Format the CPC stage guidance into a prompt-ready string."""
    if not guidance.get("has_guidance"):
        return ""
    
    sections = []
    sections.append("### Strategic Guidance from Historical Patterns:")
    
    if guidance.get("similar_roadmaps"):
        sections.append(f"**Similar Roadmaps ({guidance.get('roadmap_count', 0)} total)**: {guidance['similar_roadmaps']}")
    
    # Constraints section
    const_parts = []
    if guidance.get("constraints_guidance"):
        const_parts.append(f"- Constraints Pattern: {guidance['constraints_guidance']}")
    if guidance.get("pattern_constraints"):
        const_parts.append(f"- Common Constraints: {', '.join(guidance['pattern_constraints'][:5])}")
    if guidance.get("implementation_complexity"):
        const_parts.append(f"- Implementation Complexity: {guidance['implementation_complexity']}")
    if const_parts:
        sections.append("\n**Constraints Guidance**:\n" + "\n".join(const_parts))
    
    # Portfolio section
    port_parts = []
    if guidance.get("portfolio_guidance"):
        port_parts.append(f"- Portfolio Pattern: {guidance['portfolio_guidance']}")
    if guidance.get("common_scopes"):
        port_parts.append(f"- Common Scopes: {', '.join(guidance['common_scopes'][:5])}")
    if port_parts:
        sections.append("\n**Portfolio Guidance**:\n" + "\n".join(port_parts))
    
    # Category section
    cat_parts = []
    if guidance.get("category_guidance"):
        cat_parts.append(f"- Category Pattern: {guidance['category_guidance']}")
    if cat_parts:
        sections.append("\n**Category Guidance**:\n" + "\n".join(cat_parts))
    
    # Team/resource section
    team_parts = []
    if guidance.get("team_allocations"):
        allocations = guidance['team_allocations']
        if allocations and isinstance(allocations[0], dict):
            # Handle list of dictionaries: [{"role": "...", "allocation": "..."}]
            alloc_strs = [f"{a.get('role', 'Unknown')}: {a.get('allocation', 'N/A')}" for a in allocations[:5]]
            team_parts.append(f"- Team Allocations: {', '.join(alloc_strs)}")
        elif allocations and isinstance(allocations[0], str):
            # Handle list of strings
            team_parts.append(f"- Team Allocations: {', '.join(allocations[:5])}")
    if guidance.get("resource_distribution"):
        res_dist = guidance['resource_distribution']
        if isinstance(res_dist, dict) and res_dist:
            team_parts.append(f"- Resource Distribution: {json.dumps(res_dist)}")
    if team_parts:
        sections.append("\n**Team & Resource Patterns**:\n" + "\n".join(team_parts))
    
    return "\n".join(sections)


def get_roadmap_patterns_from_graph(
    graph_connector: GraphConnector,
    tenant_id: int,
    limit: int = 10,
    scope_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve roadmap patterns from TigerGraph database.
    
    Queries the RoadmapPattern vertices that contain pattern attributes
    (solution themes, approaches, KPIs, milestones, etc.) for roadmap generation.
    
    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: REQUIRED tenant ID for filtering
        limit: Maximum number of patterns to retrieve
        scope_filter: Optional filter for pattern scope (workflow, portfolio, customer)
        
    Returns:
        List of roadmap patterns from the database (filtered by tenant_id)
    """
    if not tenant_id:
        raise ValueError("tenant_id is REQUIRED for get_roadmap_patterns_from_graph")
    
    try:
        # Ensure we're connected
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_roadmap_patterns_from_graph",
                "error": "Failed to connect to graph",
                "tenant_id": tenant_id
            })
            return []
        
        # Use GraphConnector's connection to fetch RoadmapPattern vertices (filtered by tenant_id)
        patterns = graph_connector.get_vertices("RoadmapPattern", tenant_id=tenant_id, limit=limit)
        
        appLogger.info({
            "event": "get_roadmap_patterns_from_graph",
            "query": "fetch_patterns",
            "vertex_type": "RoadmapPattern",
            "tenant_id": tenant_id,
            "limit": limit,
            "status": "executed",
            "patterns_retrieved": len(patterns) if patterns else 0
        })
        
        # Convert TigerGraph vertex format to dict format
        patterns_list = []
        if isinstance(patterns, dict):
            # getVertices returns a dict with vertex_id as key
            for vertex_id, pattern_vertex in patterns.items():
                if isinstance(pattern_vertex, dict):
                    # Extract key attributes for roadmap matching
                    attributes = pattern_vertex.get("attributes", {})
                    
                    # Filter by scope if specified
                    pattern_scope = attributes.get("scope", "")
                    if scope_filter and pattern_scope != scope_filter:
                        continue
                    
                    pattern_dict = {
                        "id": vertex_id,
                        "name": attributes.get("name", ""),
                        "description": attributes.get("description", ""),
                        "explanation": attributes.get("explanation", ""),
                        "category": attributes.get("category", ""),
                        "scope": pattern_scope,
                        "confidence_score": attributes.get("confidence_score", 0.0),
                        "support_score": attributes.get("support_score", 0.0),
                        "created_at": attributes.get("created_at", ""),
                        "summary_period": attributes.get("summary_period", ""),
                        # Roadmap-specific pattern fields
                        "roadmap_ids": attributes.get("roadmap_ids", []),
                        "common_scopes": attributes.get("common_scopes", []),
                        "common_priorities": attributes.get("common_priorities", []),
                        "common_statuses": attributes.get("common_statuses", []),
                        "solution_themes": attributes.get("solution_themes", []),
                        "solution_approaches": attributes.get("solution_approaches", []),
                        "solution_success_criteria": attributes.get("solution_success_criteria", []),
                        "solution_narrative": attributes.get("solution_narrative", ""),
                        "key_milestones": attributes.get("key_milestones", []),
                        "key_kpis": attributes.get("key_kpis", []),
                        "constraints": attributes.get("constraints", []),
                        "team_allocations": attributes.get("team_allocations", []),
                        "resource_distribution": attributes.get("resource_distribution", {}),
                        "expected_outcomes_summary": attributes.get("expected_outcomes_summary", ""),
                        "strategic_focus": attributes.get("strategic_focus", ""),
                        "maturity_level": attributes.get("maturity_level", ""),
                        "implementation_complexity": attributes.get("implementation_complexity", ""),
                        "governance_model": attributes.get("governance_model", ""),
                        "avg_milestone_velocity": attributes.get("avg_milestone_velocity", 0.0),
                        "budget_band": attributes.get("budget_band", ""),
                        # Timeline / state transition insights
                        "state_transition_history": attributes.get("state_transition_history", []),
                        "typical_state_flow": attributes.get("typical_state_flow", []),
                        "stage_duration_insights": attributes.get("stage_duration_insights", []),
                        "avg_days_per_stage": attributes.get("avg_days_per_stage", "")
                    }
                    patterns_list.append(pattern_dict)
        elif isinstance(patterns, list):
            # Handle case where it returns a list
            for pattern_vertex in patterns:
                if isinstance(pattern_vertex, dict):
                    attributes = pattern_vertex.get("attributes", {})
                    
                    pattern_scope = attributes.get("scope", "")
                    if scope_filter and pattern_scope != scope_filter:
                        continue
                    
                    pattern_dict = {
                        "id": pattern_vertex.get("v_id", pattern_vertex.get("id", "unknown")),
                        "name": attributes.get("name", ""),
                        "description": attributes.get("description", ""),
                        "explanation": attributes.get("explanation", ""),
                        "category": attributes.get("category", ""),
                        "scope": pattern_scope,
                        "confidence_score": attributes.get("confidence_score", 0.0),
                        "support_score": attributes.get("support_score", 0.0),
                        "created_at": attributes.get("created_at", ""),
                        "summary_period": attributes.get("summary_period", ""),
                        "roadmap_ids": attributes.get("roadmap_ids", []),
                        "common_scopes": attributes.get("common_scopes", []),
                        "common_priorities": attributes.get("common_priorities", []),
                        "common_statuses": attributes.get("common_statuses", []),
                        "solution_themes": attributes.get("solution_themes", []),
                        "solution_approaches": attributes.get("solution_approaches", []),
                        "solution_success_criteria": attributes.get("solution_success_criteria", []),
                        "solution_narrative": attributes.get("solution_narrative", ""),
                        "key_milestones": attributes.get("key_milestones", []),
                        "key_kpis": attributes.get("key_kpis", []),
                        "constraints": attributes.get("constraints", []),
                        "team_allocations": attributes.get("team_allocations", []),
                        "resource_distribution": attributes.get("resource_distribution", {}),
                        "expected_outcomes_summary": attributes.get("expected_outcomes_summary", ""),
                        "strategic_focus": attributes.get("strategic_focus", ""),
                        "maturity_level": attributes.get("maturity_level", ""),
                        "implementation_complexity": attributes.get("implementation_complexity", ""),
                        "governance_model": attributes.get("governance_model", ""),
                        "avg_milestone_velocity": attributes.get("avg_milestone_velocity", 0.0),
                        "budget_band": attributes.get("budget_band", ""),
                        # Timeline / state transition insights
                        "state_transition_history": attributes.get("state_transition_history", []),
                        "typical_state_flow": attributes.get("typical_state_flow", []),
                        "stage_duration_insights": attributes.get("stage_duration_insights", []),
                        "avg_days_per_stage": attributes.get("avg_days_per_stage", "")
                    }
                    patterns_list.append(pattern_dict)
        
        appLogger.info({
            "event": "get_roadmap_patterns_from_graph",
            "patterns_retrieved": len(patterns_list),
            "scope_filter": scope_filter
        })
        
        return patterns_list
        
    except Exception as e:
        appLogger.error({
            "event": "get_roadmap_patterns_from_graph",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def aggregate_execution_metrics(scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate execution metrics from a list of ProjectScore vertices.

    Args:
        scores: List of ProjectScore vertex dictionaries with attributes

    Returns:
        Dictionary with aggregated execution statistics:
        - avg_core_score, avg_on_time_score, etc.
        - execution_count
        - score_variance
        - top_performer (boolean)
        - score_breakdown by dimension
    """
    if not scores:
        return {"execution_count": 0}

    try:
        # Extract score values from vertices
        core_scores = []
        on_time_scores = []
        on_scope_scores = []
        on_budget_scores = []
        risk_scores = []
        team_health_scores = []

        for score_vertex in scores:
            if not isinstance(score_vertex, dict):
                continue

            attrs = score_vertex.get("attributes", {})

            # Use .get() with default 0 for all score fields
            core_score = attrs.get("core_score", 0)
            if core_score is not None:
                core_scores.append(core_score)

            on_time = attrs.get("on_time_score", 0)
            if on_time is not None:
                on_time_scores.append(on_time)

            on_scope = attrs.get("on_scope_score", 0)
            if on_scope is not None:
                on_scope_scores.append(on_scope)

            on_budget = attrs.get("on_budget_score", 0)
            if on_budget is not None:
                on_budget_scores.append(on_budget)

            risk = attrs.get("risk_mgmt_score", 0)
            if risk is not None:
                risk_scores.append(risk)

            team = attrs.get("team_health_score", 0)
            if team is not None:
                team_health_scores.append(team)

        # Calculate averages
        execution_count = len(core_scores) if core_scores else 0

        if execution_count == 0:
            return {"execution_count": 0}

        avg_core = sum(core_scores) / len(core_scores) if core_scores else 0
        avg_on_time = sum(on_time_scores) / len(on_time_scores) if on_time_scores else 0
        avg_on_scope = sum(on_scope_scores) / len(on_scope_scores) if on_scope_scores else 0
        avg_on_budget = sum(on_budget_scores) / len(on_budget_scores) if on_budget_scores else 0
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        avg_team = sum(team_health_scores) / len(team_health_scores) if team_health_scores else 0

        # Calculate variance for consistency measure
        if core_scores and len(core_scores) > 1:
            mean_score = avg_core
            variance = sum((x - mean_score) ** 2 for x in core_scores) / len(core_scores)
            score_variance = variance ** 0.5  # Standard deviation
        else:
            score_variance = 0.0

        # Determine if top performer (avg > 75)
        top_performer = avg_core > 75

        # NEW: Calculate data quality indicators
        dimensions_with_data = sum([
            1 if avg_on_time > 0 else 0,
            1 if avg_on_scope > 0 else 0,
            1 if avg_on_budget > 0 else 0,
            1 if avg_risk > 0 else 0,
            1 if avg_team > 0 else 0
        ])
        
        total_dimensions = 5
        
        # Determine confidence level
        if execution_count >= 5:
            confidence_level = "high"
        elif execution_count >= 3:
            confidence_level = "medium"
        elif execution_count >= 1:
            confidence_level = "low"
        else:
            confidence_level = "none"
        
        # Calculate overall data quality score
        execution_factor = min(execution_count / 5.0, 1.0)  # Max at 5 executions
        dimension_coverage = dimensions_with_data / total_dimensions
        variance_factor = 1.0 if execution_count > 1 and score_variance > 0 else 0.5
        
        quality_score = (
            0.5 * execution_factor +  # 50% weight on execution count
            0.3 * dimension_coverage +  # 30% weight on dimension coverage
            0.2 * variance_factor  # 20% weight on having variance data
        )

        result = {
            "execution_count": execution_count,
            "avg_core_score": round(avg_core, 1),
            "avg_on_time_score": round(avg_on_time, 1),
            "avg_on_scope_score": round(avg_on_scope, 1),
            "avg_on_budget_score": round(avg_on_budget, 1),
            "avg_risk_score": round(avg_risk, 1),
            "avg_team_health_score": round(avg_team, 1),
            "score_variance": round(score_variance, 1),
            "top_performer": top_performer,
            "score_breakdown": {
                "on_time": round(avg_on_time, 1),
                "on_scope": round(avg_on_scope, 1),
                "on_budget": round(avg_on_budget, 1),
                "risk_management": round(avg_risk, 1),
                "team_health": round(avg_team, 1)
            },
            # NEW: Data quality metadata
            "data_quality": {
                "confidence_level": confidence_level,
                "dimensions_with_data": dimensions_with_data,
                "total_dimensions": total_dimensions,
                "dimension_coverage": round(dimension_coverage, 2),
                "quality_score": round(quality_score, 2),
                "has_variance": score_variance > 0
            }
        }

        appLogger.info({
            "event": "aggregate_execution_metrics",
            "execution_count": execution_count,
            "avg_core_score": result["avg_core_score"],
            "top_performer": top_performer,
            "confidence_level": confidence_level,
            "quality_score": quality_score
        })

        return result

    except Exception as e:
        appLogger.error({
            "event": "aggregate_execution_metrics",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {"execution_count": 0}


def get_roadmap_patterns_with_execution_scores(
    graph_connector: GraphConnector,
    tenant_id: int,
    limit: int = 10,
    scope_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve roadmap patterns from TigerGraph with aggregated execution scores.

    For each RoadmapPattern, traverses hasProjectExecution edges to fetch
    associated ProjectScore vertices and aggregates execution metrics.

    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID for filtering
        limit: Maximum number of patterns to retrieve
        scope_filter: Optional filter for pattern scope

    Returns:
        List of roadmap patterns enriched with execution_data field containing:
        - avg_core_score, avg_on_time_score, etc.
        - execution_count
        - score_variance
        - top_performer boolean
    """
    try:
        # Get base patterns using existing function
        patterns = get_roadmap_patterns_from_graph(
            graph_connector, tenant_id, limit, scope_filter
        )

        appLogger.info({
            "event": "get_roadmap_patterns_with_execution_scores",
            "tenant_id": tenant_id,
            "base_patterns_retrieved": len(patterns)
        })

        # For each pattern, traverse hasProjectExecution edges
        for pattern in patterns:
            try:
                pattern_id = pattern.get("id")

                # Traverse hasProjectExecution edge from RoadmapPattern to ProjectScore
                edges = graph_connector.get_edges(
                    source_vertex_type="RoadmapPattern",
                    source_vertex_id=pattern_id,
                    edge_type="hasProjectExecution",
                    tenant_id=tenant_id
                )

                appLogger.info({
                    "event": "traverse_hasProjectExecution",
                    "pattern_id": pattern_id,
                    "edges_found": len(edges) if edges else 0
                })

                # Extract target ProjectScore vertex IDs (batch operation)
                score_ids = []
                if edges:
                    for edge in edges:
                        if isinstance(edge, dict):
                            target_id = edge.get("to_id") or edge.get("t_id")
                            if target_id:
                                score_ids.append(target_id)

                if score_ids:
                    # Batch fetch all ProjectScore vertices
                    scores = graph_connector.get_vertices_by_id(
                        "ProjectScore",
                        tenant_id=tenant_id,
                        vertex_ids=score_ids
                    )

                    # Aggregate execution metrics
                    pattern["execution_data"] = aggregate_execution_metrics(scores)

                    appLogger.info({
                        "event": "aggregated_execution_metrics",
                        "pattern_id": pattern_id,
                        "scores_aggregated": len(scores) if scores else 0,
                        "avg_core_score": pattern["execution_data"].get("avg_core_score", 0)
                    })
                else:
                    # No execution scores for this pattern
                    pattern["execution_data"] = {"execution_count": 0}

                    appLogger.info({
                        "event": "no_execution_data",
                        "pattern_id": pattern_id
                    })

            except Exception as e:
                # Log error but continue processing other patterns
                appLogger.error({
                    "event": "get_execution_scores_for_pattern",
                    "pattern_id": pattern.get("id"),
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                # Set empty execution data on error
                pattern["execution_data"] = {"execution_count": 0}

        # Log summary
        patterns_with_execution = sum(
            1 for p in patterns
            if p.get("execution_data", {}).get("execution_count", 0) > 0
        )

        appLogger.info({
            "event": "get_roadmap_patterns_with_execution_scores",
            "tenant_id": tenant_id,
            "patterns_retrieved": len(patterns),
            "patterns_with_execution_data": patterns_with_execution
        })

        return patterns

    except Exception as e:
        appLogger.error({
            "event": "get_roadmap_patterns_with_execution_scores",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        # Return empty list on complete failure
        return []


def get_top_scored_projects_with_roadmaps(
    graph_connector: GraphConnector,
    tenant_id: int,
    min_core_score: float = 75.0
) -> List[Dict[str, Any]]:
    """
    Retrieve high-scoring ProjectScore vertices that have associated roadmap_ids.

    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID for filtering
        min_core_score: Minimum core score threshold (default 75.0)

    Returns:
        List of ProjectScore vertices with score >= min_core_score and roadmap_id populated
    """
    try:
        # Get all ProjectScore vertices for tenant
        all_scores = graph_connector.get_vertices(
            "ProjectScore",
            tenant_id=tenant_id,
            limit=1000  # Reasonable limit for cluster analysis
        )

        appLogger.info({
            "event": "get_top_scored_projects_with_roadmaps",
            "tenant_id": tenant_id,
            "total_scores_retrieved": len(all_scores) if all_scores else 0
        })

        if not all_scores:
            return []

        # Filter for high-scoring projects with roadmap_id
        top_scored = []

        # Handle both dict and list formats from GraphConnector
        scores_list = []
        if isinstance(all_scores, dict):
            scores_list = list(all_scores.values())
        elif isinstance(all_scores, list):
            scores_list = all_scores

        for score_vertex in scores_list:
            if not isinstance(score_vertex, dict):
                continue

            attrs = score_vertex.get("attributes", {})

            core_score = attrs.get("core_score", 0)
            roadmap_id = attrs.get("roadmap_id")

            # Include if core_score >= threshold AND has roadmap_id
            if core_score >= min_core_score and roadmap_id:
                top_scored.append({
                    "id": score_vertex.get("v_id") or score_vertex.get("id"),
                    "project_id": attrs.get("project_id"),
                    "roadmap_id": roadmap_id,
                    "core_score": core_score,
                    "on_time_score": attrs.get("on_time_score", 0),
                    "on_scope_score": attrs.get("on_scope_score", 0),
                    "on_budget_score": attrs.get("on_budget_score", 0),
                    "project_title": attrs.get("project_title", "")
                })

        appLogger.info({
            "event": "get_top_scored_projects_with_roadmaps",
            "tenant_id": tenant_id,
            "min_core_score": min_core_score,
            "top_scored_projects_found": len(top_scored)
        })

        return top_scored

    except Exception as e:
        appLogger.error({
            "event": "get_top_scored_projects_with_roadmaps",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def extract_patterns_for_roadmaps(
    graph_connector: GraphConnector,
    tenant_id: int,
    roadmap_ids: List[int]
) -> List[Dict[str, Any]]:
    """
    Find RoadmapPattern vertices that contain any of the specified roadmap_ids.

    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID for filtering
        roadmap_ids: List of roadmap IDs to search for in patterns

    Returns:
        List of RoadmapPattern vertices that include the roadmap_ids
    """
    try:
        if not roadmap_ids:
            return []

        # Convert to strings for comparison (roadmap_ids attribute is list of strings)
        roadmap_ids_str = [str(rid) for rid in roadmap_ids]

        # Get all RoadmapPattern vertices for tenant
        all_patterns = graph_connector.get_vertices(
            "RoadmapPattern",
            tenant_id=tenant_id,
            limit=500
        )

        appLogger.info({
            "event": "extract_patterns_for_roadmaps",
            "tenant_id": tenant_id,
            "roadmap_ids_to_find": len(roadmap_ids),
            "patterns_retrieved": len(all_patterns) if all_patterns else 0
        })

        if not all_patterns:
            return []

        matching_patterns = []

        # Handle both dict and list formats
        patterns_list = []
        if isinstance(all_patterns, dict):
            patterns_list = list(all_patterns.values())
        elif isinstance(all_patterns, list):
            patterns_list = all_patterns

        for pattern_vertex in patterns_list:
            if not isinstance(pattern_vertex, dict):
                continue

            attrs = pattern_vertex.get("attributes", {})
            pattern_roadmap_ids = attrs.get("roadmap_ids", [])

            # Check if any of our target roadmaps are in this pattern
            if pattern_roadmap_ids:
                # Convert to strings for comparison
                pattern_roadmap_ids_str = [str(r) for r in pattern_roadmap_ids]

                # Check for intersection
                if any(rid in pattern_roadmap_ids_str for rid in roadmap_ids_str):
                    # Extract key pattern attributes for LLM analysis
                    matching_patterns.append({
                        "id": pattern_vertex.get("v_id") or pattern_vertex.get("id"),
                        "name": attrs.get("name", ""),
                        "description": attrs.get("description", ""),
                        "explanation": attrs.get("explanation", ""),
                        "roadmap_ids": pattern_roadmap_ids,
                        "solution_themes": attrs.get("solution_themes", []),
                        "solution_approaches": attrs.get("solution_approaches", []),
                        "solution_narrative": attrs.get("solution_narrative", ""),
                        "key_milestones": attrs.get("key_milestones", []),
                        "key_kpis": attrs.get("key_kpis", []),
                        "constraints": attrs.get("constraints", []),
                        "team_allocations": attrs.get("team_allocations", []),
                        "strategic_focus": attrs.get("strategic_focus", ""),
                        "implementation_complexity": attrs.get("implementation_complexity", ""),
                        "typical_state_flow": attrs.get("typical_state_flow", []),
                        "avg_days_per_stage": attrs.get("avg_days_per_stage", "")
                    })

        appLogger.info({
            "event": "extract_patterns_for_roadmaps",
            "tenant_id": tenant_id,
            "matching_patterns_found": len(matching_patterns)
        })

        return matching_patterns

    except Exception as e:
        appLogger.error({
            "event": "extract_patterns_for_roadmaps",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def analyze_roadmap_cluster_performance(
    graph_connector: GraphConnector,
    tenant_id: int,
    llm: Optional[ChatGPTClient] = None
) -> Dict[str, Any]:
    """
    Analyze which roadmap attributes correlate with successful project execution.

    Uses LLM to identify patterns in top-performing projects and their originating
    roadmaps. Looks across ALL tenant roadmaps (not pattern-specific) to derive
    insights about what makes roadmaps successful.

    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID for filtering
        llm: Optional LLM client (creates one if not provided)

    Returns:
        Structured analysis with:
        - top_performing_patterns: Pattern IDs with high execution scores
        - success_factors: Attributes correlating with success
        - recommendations: LLM-generated guidance
        - evidence: Specific citations with scores
    """
    try:
        if llm is None:
            llm = ChatGPTClient()

        appLogger.info({
            "event": "analyze_roadmap_cluster_performance",
            "tenant_id": tenant_id,
            "step": "start"
        })

        # Step 1: Find high-scoring projects with roadmaps
        high_scoring_projects = get_top_scored_projects_with_roadmaps(
            graph_connector, tenant_id, min_core_score=75.0
        )

        if not high_scoring_projects or len(high_scoring_projects) < 3:
            appLogger.warning({
                "event": "analyze_roadmap_cluster_performance",
                "tenant_id": tenant_id,
                "warning": "insufficient_high_scoring_projects",
                "projects_found": len(high_scoring_projects) if high_scoring_projects else 0
            })
            return {
                "top_performing_patterns": [],
                "success_factors": [],
                "recommendations": "Insufficient execution data for cluster analysis (need at least 3 high-scoring projects with roadmaps)",
                "evidence": []
            }

        # Step 2: Extract roadmap IDs from high-scoring projects
        roadmap_ids = list(set([p["roadmap_id"] for p in high_scoring_projects]))

        appLogger.info({
            "event": "analyze_roadmap_cluster_performance",
            "tenant_id": tenant_id,
            "step": "extracted_roadmap_ids",
            "unique_roadmaps": len(roadmap_ids),
            "high_scoring_projects": len(high_scoring_projects)
        })

        # Step 3: Get RoadmapPattern vertices containing those roadmap_ids
        roadmap_patterns = extract_patterns_for_roadmaps(
            graph_connector, tenant_id, roadmap_ids
        )

        if not roadmap_patterns:
            appLogger.warning({
                "event": "analyze_roadmap_cluster_performance",
                "tenant_id": tenant_id,
                "warning": "no_patterns_found_for_roadmaps",
                "roadmap_ids_searched": len(roadmap_ids)
            })
            return {
                "top_performing_patterns": [],
                "success_factors": [],
                "recommendations": "No roadmap patterns found for high-scoring projects",
                "evidence": []
            }

        # Step 4: Prepare data for LLM analysis
        # Format patterns with their execution context
        patterns_for_llm = []
        for pattern in roadmap_patterns:
            # Count how many of our high-scoring projects came from this pattern
            pattern_roadmap_ids_str = [str(r) for r in pattern.get("roadmap_ids", [])]
            matching_projects = [
                p for p in high_scoring_projects
                if str(p["roadmap_id"]) in pattern_roadmap_ids_str
            ]

            if matching_projects:
                avg_score = sum(p["core_score"] for p in matching_projects) / len(matching_projects)
                patterns_for_llm.append({
                    "pattern_id": pattern.get("id"),
                    "pattern_name": pattern.get("name", ""),
                    "pattern_description": pattern.get("description", "")[:200],
                    "solution_themes": pattern.get("solution_themes", []),
                    "solution_approaches": pattern.get("solution_approaches", []),
                    "key_milestones": pattern.get("key_milestones", []),
                    "key_kpis": pattern.get("key_kpis", []),
                    "constraints": pattern.get("constraints", []),
                    "strategic_focus": pattern.get("strategic_focus", ""),
                    "implementation_complexity": pattern.get("implementation_complexity", ""),
                    "typical_state_flow": pattern.get("typical_state_flow", []),
                    "matching_projects_count": len(matching_projects),
                    "avg_execution_score": round(avg_score, 1),
                    "projects": [
                        {
                            "title": p.get("project_title", ""),
                            "core_score": p["core_score"],
                            "on_time": p["on_time_score"],
                            "on_scope": p["on_scope_score"],
                            "on_budget": p["on_budget_score"]
                        }
                        for p in matching_projects[:3]  # Limit to 3 projects per pattern
                    ]
                })

        patterns_json = json.dumps(patterns_for_llm, indent=2)

        # Step 5: LLM analysis
        system_prompt = """You are analyzing roadmap execution patterns to identify success factors.

You have been given data about roadmap patterns whose executions scored highly (core_score >= 75).
Your task is to identify which roadmap attributes correlate with successful project execution.

Focus on:
- solution_themes: What problem areas led to success?
- solution_approaches: What implementation strategies worked?
- key_milestones: What milestone patterns correlated with success?
- key_kpis: What metrics were tracked in successful roadmaps?
- constraints: What constraints were acknowledged upfront?
- strategic_focus: What strategic alignments mattered?
- typical_state_flow: Did certain state progressions lead to better outcomes?
- implementation_complexity: Did complexity levels affect success?

DO NOT invent patterns not present in the data. Only cite attributes actually found in the patterns.
Ground all insights in the execution scores provided."""

        user_prompt = f"""Analyze these roadmap patterns and their execution outcomes:

{patterns_json}

All of these patterns led to projects that scored >= 75/100 on execution metrics.

Return a JSON structure:
{{
    "top_performing_patterns": ["pattern_id_1", "pattern_id_2", ...],
    "success_factors": [
        "Factor 1: Explanation grounded in data",
        "Factor 2: Explanation grounded in data"
    ],
    "recommendations": "Narrative guidance for roadmap planning based on what worked. 2-3 paragraphs citing specific patterns and their execution scores.",
    "evidence": [
        {{
            "pattern_id": "...",
            "pattern_name": "...",
            "avg_score": 85.5,
            "execution_count": 3,
            "key_attributes": ["attr1", "attr2"]
        }}
    ]
}}

Ensure all success_factors cite specific pattern attributes from the data.
"""

        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )

        response = llm.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.2),
            'roadmap_inference::cluster_performance'
        )

        result = extract_json_after_llm(response)

        appLogger.info({
            "event": "analyze_roadmap_cluster_performance",
            "tenant_id": tenant_id,
            "step": "complete",
            "patterns_analyzed": len(patterns_for_llm),
            "success_factors_identified": len(result.get("success_factors", []))
        })

        return result

    except Exception as e:
        appLogger.error({
            "event": "analyze_roadmap_cluster_performance",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        # Return empty result structure on failure
        return {
            "top_performing_patterns": [],
            "success_factors": [],
            "recommendations": f"Error during cluster performance analysis: {str(e)}",
            "evidence": [],
            "error": str(e)
        }


def match_patterns(
    roadmap_data: Dict[str, Any],
    patterns: List[Dict[str, Any]],
    llm: Optional[ChatGPTClient] = None
) -> Dict[str, Any]:
    """
    Use LLM to identify the top 2 most similar patterns to ensure we always
    provide knowledge value. Returns top 2 patterns unless the best pattern
    has 3+ roadmap entities, in which case we use only that pattern.
    
    Args:
        roadmap_data: Minimal roadmap data (name, description, category, etc.)
        patterns: List of RoadmapPattern vertices from TigerGraph to match against
        llm: Optional LLM client (creates one if not provided)
        
    Returns:
        Dict with top 2 patterns, confidence scores, and explanations
    """
    if not patterns:
        return {
            "matched_patterns": [],
            "match_count": 0,
            "message": "No patterns available for matching"
        }
    
    if llm is None:
        llm = ChatGPTClient()
    
    try:
        # Format patterns for LLM analysis with indexes 
        patterns_with_index = []
        for idx, p in enumerate(patterns): 
            patterns_with_index.append({
                "index": idx,
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "explanation": p.get("explanation", ""),
                "category": p.get("category", ""),
                "scope": p.get("scope", ""),
                "confidence_score": p.get("confidence_score", 0.0),
                "support_score": p.get("support_score", 0.0),
                "roadmap_count": len(p.get("roadmap_ids", [])),
                "solution_themes": p.get("solution_themes", []),
                "solution_approaches": p.get("solution_approaches", []),
                "solution_narrative": p.get("solution_narrative", "")[:600],
                "key_kpis": p.get("key_kpis", []),
                "key_milestones": p.get("key_milestones", []),
                "common_scopes": p.get("common_scopes", []),
                "strategic_focus": p.get("strategic_focus", ""),
                "maturity_level": p.get("maturity_level", ""),
                "implementation_complexity": p.get("implementation_complexity", "")
            })
        
        patterns_str = json.dumps(patterns_with_index, indent=2)
        
        # Calculate dynamic index range
        num_patterns = len(patterns_with_index)
        max_index = num_patterns - 1
        index_range = f"0-{max_index}" if num_patterns > 1 else "0"
        
        # Create index-to-name mapping for clarity
        index_mapping = "\n".join([f"  Index {p['index']}: {p['name']}" for p in patterns_with_index])
        
        roadmap_str = json.dumps({
            "name": roadmap_data.get("name", ""),
            "description": roadmap_data.get("description", ""),
            "category": roadmap_data.get("category", ""),
            "roadmap_type": roadmap_data.get("roadmap_type", ""),
            "objectives": roadmap_data.get("objectives", "")
        })
        
        system_prompt = f"""
        You are an expert roadmap analyst. Your task is to identify the TOP 2 most similar 
        patterns to ensure we always provide knowledge value from our pattern database.
        
        SPECIAL RULE: If the best matching pattern has 3+ roadmaps (roadmap_count >= 3), 
        then return ONLY that pattern. Otherwise, always return the top 2 patterns.
        
        These patterns are RoadmapPattern vertices that aggregate learnings from multiple 
        successful roadmaps. Consider:
        - Semantic similarity in description and solution narrative
        - Matching category and strategic focus  
        - Relevance of solution themes and approaches
        - Alignment with KPIs and milestones
        - Pattern confidence and support scores (higher is better)
        - Number of roadmaps (roadmap_count - more is generally better)
        
        AVAILABLE PATTERNS: {num_patterns} patterns (indices {index_range})
        {index_mapping}
        
        For each selected pattern, provide:
        - Confidence score (0.0-1.0)
        - Detailed explanation of why it matches
        - Key similarity factors
        
        Return JSON with:
        - primary_pattern: {{index, confidence_score, explanation, similarity_factors}}
        - secondary_pattern: {{index, confidence_score, explanation, similarity_factors}} OR null
        - match_strategy: "single_rich_pattern" (if primary has 3+ roadmaps) or "dual_pattern"
        - overall_confidence: Overall confidence in pattern matching quality
        """
        
        user_prompt = f"""
        Find the best pattern matches for this roadmap:
        
        INPUT ROADMAP:
        {roadmap_str}
        
        AVAILABLE PATTERNS ({num_patterns} total):
        {patterns_str}
        
        REMEMBER: 
        - If best match has roadmap_count >= 3, return only that pattern
        - Otherwise, return top 2 patterns with explanations
        - Always provide knowledge value through pattern matching
        - Valid index range: {index_range}
        
        Return as JSON:
        {{
            "primary_pattern": {{
                "index": <integer in range {index_range}>,
                "confidence_score": 0.0-1.0,
                "explanation": "detailed explanation of match",
                "similarity_factors": ["factor1", "factor2", ...]
            }},
            "secondary_pattern": {{
                "index": <integer in range {index_range}>,
                "confidence_score": 0.0-1.0,
                "explanation": "detailed explanation of match", 
                "similarity_factors": ["factor1", "factor2", ...]
            }} OR null,
            "match_strategy": "single_rich_pattern" or "dual_pattern",
            "overall_confidence": 0.0-1.0
        }}
        """
        
        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )
        
        response = llm.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.1),
            'roadmap_inference::match_patterns'
        )
        
        result = extract_json_after_llm(response)
        
        if isinstance(result, str):
            appLogger.error({
                "event": "match_patterns",
                "error": "LLM returned unparseable JSON",
                "raw_response": result[:500]
            })
            return {
                "matched_patterns": [],
                "match_count": 0,
                "message": "Error parsing LLM response"
            }
        
        # Extract matched patterns
        matched_patterns = []
        primary = result.get("primary_pattern")
        secondary = result.get("secondary_pattern")
        
        if primary and isinstance(primary.get("index"), int):
            idx = primary["index"]
            if 0 <= idx < len(patterns):
                matched_patterns.append({
                    "pattern": patterns[idx],
                    "confidence_score": primary.get("confidence_score", 0.0),
                    "explanation": primary.get("explanation", ""),
                    "similarity_factors": primary.get("similarity_factors", []),
                    "rank": 1
                })
        
        if secondary and isinstance(secondary.get("index"), int):
            idx = secondary["index"]
            if 0 <= idx < len(patterns):
                matched_patterns.append({
                    "pattern": patterns[idx],
                    "confidence_score": secondary.get("confidence_score", 0.0),
                    "explanation": secondary.get("explanation", ""),
                    "similarity_factors": secondary.get("similarity_factors", []),
                    "rank": 2
                })
        
        appLogger.info({
            "event": "match_patterns",
            "match_strategy": result.get("match_strategy"),
            "patterns_matched": len(matched_patterns),
            "overall_confidence": result.get("overall_confidence", 0.0)
        })
        
        return {
            "matched_patterns": matched_patterns,
            "match_count": len(matched_patterns),
            "match_strategy": result.get("match_strategy", "dual_pattern"),
            "overall_confidence": result.get("overall_confidence", 0.0)
        }
        
    except Exception as e:
        appLogger.error({
            "event": "match_patterns",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "matched_pattern_index": None,
            "confidence_score": 0.0,
            "reasoning": f"Error during pattern matching: {str(e)}",
            "similarity_factors": []
        }


def filter_execution_dimensions(execution_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter execution dimensions to only include those with actual data.
    Returns a dict with valid dimensions and their contextual descriptions.
    
    Args:
        execution_data: Full execution data dict with all dimensions
        
    Returns:
        Filtered dict with only meaningful dimensions
    """
    filtered = {}
    confidence_level = execution_data.get("data_quality", {}).get("confidence_level", "none")
    execution_count = execution_data.get("execution_count", 0)
    
    # Always include core metrics if exists
    if execution_count > 0:
        filtered["execution_count"] = execution_count
        filtered["avg_core_score"] = execution_data.get("avg_core_score", 0)
        filtered["confidence_level"] = confidence_level
    
    # Filter dimension scores - only include if > 0 (actual data)
    dimensions = {
        "on_time": execution_data.get("avg_on_time_score", 0),
        "on_scope": execution_data.get("avg_on_scope_score", 0),
        "on_budget": execution_data.get("avg_on_budget_score", 0),
        "risk_mgmt": execution_data.get("avg_risk_score", 0),
        "team_health": execution_data.get("avg_team_health_score", 0)
    }
    
    filtered["dimensions"] = {}
    filtered["missing_dimensions"] = []
    
    for dim_name, dim_value in dimensions.items():
        if dim_value > 0:
            filtered["dimensions"][dim_name] = {
                "score": dim_value,
                "has_data": True
            }
        else:
            filtered["missing_dimensions"].append(dim_name)
    
    filtered["data_quality"] = execution_data.get("data_quality", {})
    
    return filtered


def build_execution_context_for_llm(execution_data: Dict[str, Any], roadmap_names: List[str]) -> str:
    """
    Build natural language execution context for LLM prompt based on data quality.
    
    Args:
        execution_data: Execution metrics with data quality indicators
        roadmap_names: List of roadmap names for context
        
    Returns:
        Natural language description of execution insights
    """
    if not execution_data or execution_data.get("execution_count", 0) == 0:
        return ""
    
    filtered = filter_execution_dimensions(execution_data)
    confidence = filtered.get("confidence_level", "none")
    exec_count = filtered.get("execution_count", 0)
    core_score = filtered.get("avg_core_score", 0)
    dimensions = filtered.get("dimensions", {})
    missing = filtered.get("missing_dimensions", [])
    quality_score = filtered.get("data_quality", {}).get("quality_score", 0)
    
    # Build confidence-appropriate narrative
    parts = []
    
    # Opening based on confidence level
    if confidence == "high":
        parts.append(
            f"STRONG EXECUTION EVIDENCE ({exec_count} implementations):\n"
            f"Consistent track record averaging {core_score}/100 across multiple executions."
        )
    elif confidence == "medium":
        parts.append(
            f"MODERATE EXECUTION DATA ({exec_count} implementations):\n"
            f"Emerging pattern showing average performance of {core_score}/100."
        )
    elif confidence == "low":
        parts.append(
            f"LIMITED EXECUTION SNAPSHOT ({exec_count} execution{'s' if exec_count > 1 else ''}):\n"
            f"Preliminary indicator suggests performance around {core_score}/100."
        )
    
    # Add dimension breakdown (only for valid dimensions)
    if dimensions:
        parts.append("\nPerformance by dimension:")
        
        # Group by strength
        strong = {k: v for k, v in dimensions.items() if v['score'] >= 70}
        moderate = {k: v for k, v in dimensions.items() if 50 <= v['score'] < 70}
        weak = {k: v for k, v in dimensions.items() if v['score'] < 50}
        
        if strong:
            parts.append(f"  ✓ Strong areas: " + ", ".join([f"{k} ({v['score']}/100)" for k, v in strong.items()]))
        if moderate:
            parts.append(f"  ≈ Moderate areas: " + ", ".join([f"{k} ({v['score']}/100)" for k, v in moderate.items()]))
        if weak:
            parts.append(f"  ⚠ Weak areas: " + ", ".join([f"{k} ({v['score']}/100)" for k, v in weak.items()]))
    
    # Note missing data
    if missing:
        parts.append(f"\n⚠ No data tracked for: {', '.join(missing)}")
    
    # Usage guidance based on confidence
    parts.append("\nHow to use this data:")
    if confidence == "high":
        parts.append(
            "  - Use these metrics confidently to validate recommendations\n"
            "  - Strong performers (>70) indicate proven practices to replicate\n"
            "  - Weak areas (<50) require mitigation strategies"
        )
    elif confidence == "medium":
        parts.append(
            "  - Use directionally, noting the limited sample size\n"
            "  - Treat as emerging patterns rather than definitive evidence\n"
            "  - Strong/weak signals suggest areas of focus"
        )
    elif confidence == "low":
        parts.append(
            "  - Treat as anecdotal evidence only\n"
            "  - Focus on qualitative insights, not quantitative benchmarks\n"
            "  - Use cautious language: 'indicates', 'suggests', 'preliminary data shows'\n"
            f"  - Always note: 'based on {exec_count} execution' in your recommendations"
        )
    
    return "\n".join(parts)


def generate_advice(
    roadmap_data: Dict[str, Any],
    matched_patterns: List[Dict[str, Any]],
    llm: Optional[ChatGPTClient] = None,
    tenant_id: int = None,
    cluster_performance: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate solution-focused advice based on matched pattern from knowledge graph.

    Analyzes how similar roadmaps solved their problems and adapts the approach
    to the current roadmap context. Optionally includes execution insights when
    available.

    Args:
        roadmap_data: The input roadmap data
        matched_pattern: The matched RoadmapPattern vertex from TigerGraph
        confidence_score: Confidence in the pattern match
        llm: Optional LLM client (creates one if not provided)
        tenant_id: Tenant ID for database queries
        cluster_performance: Optional cluster performance analysis data
        confidence_score: Confidence in the pattern match
        llm: Optional LLM client (creates one if not provided)
        tenant_id: Tenant ID for fetching roadmap names
        roadmap_id_to_name_mapping: Dict mapping roadmap IDs to names for consistent citation
        
    Returns:
        Synthesized solution-focused advice from multiple patterns
    """
    if llm is None:
        llm = ChatGPTClient(tenant_id=tenant_id)
    
    try:
        if not matched_patterns:
            return {
                "status": "no_patterns",
                "message": "No patterns available for advice generation.",
                "solution_guidance": None
            }

        # Use the highest-ranked match as primary context while preserving
        # references from all matched patterns for citations.
        primary_match = matched_patterns[0]
        matched_pattern = primary_match.get("pattern", {}) or {}
        confidence_score = primary_match.get("confidence_score", 0.0)

        if not matched_pattern:
            return {
                "status": "no_patterns",
                "message": "Matched patterns are missing pattern payloads.",
                "solution_guidance": None
            }

        # Build a single roadmap-id -> title mapping across all matched patterns.
        roadmap_id_to_name_mapping = {}
        unique_roadmap_ids = set()
        for match in matched_patterns:
            pattern = match.get("pattern", {}) or {}
            for rid in pattern.get("roadmap_ids", []):
                try:
                    unique_roadmap_ids.add(int(rid))
                except (TypeError, ValueError):
                    continue

        if unique_roadmap_ids:
            try:
                all_roadmaps = RoadmapDao.FetchRoadmapNamesWithIDS(tenant_id, list(unique_roadmap_ids))
                for roadmap in all_roadmaps or []:
                    rid = int(roadmap.get("id", 0))
                    roadmap_id_to_name_mapping[rid] = roadmap.get("title", f"Roadmap {rid}")
            except Exception as e:
                appLogger.warning({
                    "event": "fetch_roadmap_names",
                    "error": str(e),
                    "roadmap_ids": list(unique_roadmap_ids),
                    "tenant_id": tenant_id
                })

        pattern_contexts = []
        for rank, match in enumerate(matched_patterns, start=1):
            pattern = match.get("pattern", {}) or {}
            pattern_roadmap_ids = pattern.get("roadmap_ids", [])
            names = []
            for rid in pattern_roadmap_ids[:5]:
                try:
                    rid_int = int(rid)
                    names.append(roadmap_id_to_name_mapping.get(rid_int, f"Roadmap {rid_int}"))
                except (TypeError, ValueError):
                    names.append(f"Roadmap {rid}")

            pattern_contexts.append({
                "pattern_id": pattern.get("id"),
                "pattern_name": pattern.get("name", ""),
                "rank": rank,
                "confidence_score": match.get("confidence_score", 0.0),
                "match_explanation": match.get("explanation", ""),
                "roadmap_count": len(pattern_roadmap_ids),
                "roadmap_names": names,
            })

        total_roadmap_count = sum(ctx["roadmap_count"] for ctx in pattern_contexts)
        
        # Extract roadmap IDs from pattern
        roadmap_ids = matched_pattern.get("roadmap_ids", [])
        roadmap_count = len(roadmap_ids)
        roadmap_names = pattern_contexts[0]["roadmap_names"] if pattern_contexts else [f"Roadmap {rid}" for rid in roadmap_ids[:5]]
        
        pattern_context = {
            "pattern_name": matched_pattern.get("name", ""),
            "roadmap_count": roadmap_count,
            "roadmap_names": roadmap_names,
            "solution_themes": matched_pattern.get("solution_themes", []),
            "solution_approaches": matched_pattern.get("solution_approaches", []),
            "solution_narrative": matched_pattern.get("solution_narrative", ""),
            "solution_success_criteria": matched_pattern.get("solution_success_criteria", []),
            "key_milestones": matched_pattern.get("key_milestones", []),
            "constraints": matched_pattern.get("constraints", []),
            "strategic_focus": matched_pattern.get("strategic_focus", ""),
            "implementation_complexity": matched_pattern.get("implementation_complexity", ""),
            "expected_outcomes_summary": matched_pattern.get("expected_outcomes_summary", ""),
            # State transition / timeline data
            "state_transition_history": matched_pattern.get("state_transition_history", []),
            "typical_state_flow": matched_pattern.get("typical_state_flow", []),
            "stage_duration_insights": matched_pattern.get("stage_duration_insights", []),
            "avg_days_per_stage": matched_pattern.get("avg_days_per_stage", "")
        }

        # Check if execution data exists and add to pattern context
        execution_data = matched_pattern.get("execution_data", {})
        has_execution_data = execution_data.get("execution_count", 0) > 0
        
        # NEW: Get data quality indicators
        data_quality = execution_data.get("data_quality", {}) if has_execution_data else {}
        confidence_level = data_quality.get("confidence_level", "none")
        quality_score = data_quality.get("quality_score", 0)

        appLogger.info({
            "event": "generate_advice",
            "pattern_id": matched_pattern.get("id"),
            "has_execution_data": has_execution_data,
            "execution_count": execution_data.get("execution_count", 0),
            "avg_core_score": execution_data.get("avg_core_score", 0) if has_execution_data else None,
            "confidence_level": confidence_level,
            "quality_score": quality_score
        })

        # Add execution insights to pattern_context if available (filtered by quality)
        if has_execution_data:
            filtered_exec_data = filter_execution_dimensions(execution_data)
            pattern_context["execution_insights"] = {
                "avg_core_score": execution_data.get("avg_core_score"),
                "execution_count": execution_data.get("execution_count"),
                "confidence_level": confidence_level,
                "score_breakdown": execution_data.get("score_breakdown", {}),
                "valid_dimensions": filtered_exec_data.get("dimensions", {}),
                "missing_dimensions": filtered_exec_data.get("missing_dimensions", []),
                "top_performer": execution_data.get("top_performer", False),
                "score_variance": execution_data.get("score_variance", 0),
                "data_quality": data_quality
            }
            appLogger.info({
                "event": "generate_advice",
                "message": "Including execution insights in advice generation",
                "pattern_id": matched_pattern.get("id"),
                "avg_core_score": execution_data.get("avg_core_score"),
                "confidence_level": confidence_level,
                "dimensions_with_data": data_quality.get("dimensions_with_data", 0)
            })
        else:
            appLogger.info({
                "event": "generate_advice",
                "message": "No execution data available for pattern",
                "pattern_id": matched_pattern.get("id")
            })

        pattern_str = json.dumps(pattern_context, indent=2)
        
        roadmap_str = json.dumps({
            "name": roadmap_data.get("name", ""),
            "description": roadmap_data.get("description", ""),
            "objectives": roadmap_data.get("objectives", "")
        })
        
        system_prompt = f"""
        You are a solutions architect analyzing past roadmap execution patterns to inform a new roadmap.

        You have access to detailed pattern data from {roadmap_count} similar roadmap(s): {', '.join(roadmap_names)}.

        CRITICAL: This pattern includes historical state transition data showing how similar roadmaps progressed through
        execution phases (typical state flows, stage durations, approval timelines). Use this timeline data to provide
        realistic execution guidance with specific milestone recommendations based on historical patterns.
        """

        # Add quality-aware execution context to system prompt if execution data exists
        if has_execution_data:
            execution_context = build_execution_context_for_llm(execution_data, roadmap_names)
            system_prompt += f"\n\n{execution_context}"

        system_prompt += """

        Your task is to provide COMPREHENSIVE, solution-focused guidance across multiple dimensions.
        For each dimension, you will:
        1. Reference SPECIFIC roadmaps by name with actual data points
        2. Describe concrete solutions, approaches, and implementations
        3. Cite success criteria and expected outcomes
        4. Connect past learnings to current roadmap context
        5. Recommend realistic timelines based on state transition patterns and stage durations

        CRITICAL: Provide multiple paragraphs of rich solution guidance (not just bullets),
        then follow with dimension-specific guidance.
        """
        
        user_prompt = f"""
        Synthesize insights from {len(matched_patterns)} matched pattern(s) for this roadmap:
        
        NEW ROADMAP:
        {roadmap_str}
        
        PATTERN FROM PREVIOUS ROADMAPS (INCLUDING STATE TRANSITION DATA):
        {pattern_str}
        
        ADDITIONAL STATE TRANSITION CONTEXT:
        This pattern shows the following typical state flow: {', '.join(matched_pattern.get('typical_state_flow', []))}
        Average stage durations: {matched_pattern.get('avg_days_per_stage', 'N/A')}
        
        For the comprehensive solution guidance, write 3-5 substantive paragraphs that:
        - {"Start naturally: 'Based on " + str(execution_data.get('execution_count', 0)) + " previous implementation(s) of this pattern, which achieved an average score of " + str(round(execution_data.get('avg_core_score', 0), 1)) + "/100, along with insights from " + ', '.join(roadmap_names) + "...' Then explain what these scores reveal about the pattern's strengths and challenges." if has_execution_data else "Start with 'Based on " + ', '.join(roadmap_names) + ", the most effective approach...'"}
        - Include specific solution themes, approaches, and implementations
        - Reference actual constraints that were overcome
        - {"Weave in execution insights naturally: If on-time was low (" + str(round(execution_data.get('avg_on_time_score', 0), 1)) + "/100), explain timeline risks and mitigation. If budget was strong (" + str(round(execution_data.get('avg_on_budget_score', 0), 1)) + "/100), note cost-control practices that worked." if has_execution_data else ""}
        - Describe expected outcomes with concrete metrics based on historical performance
        - Connect to the new roadmap's objectives
        - Use historical state transitions to recommend realistic milestone timelines
        
        Then provide dimension-specific guidance as before.
        
        For each dimension below, write 2-3 concise Markdown bullet points. Each bullet must:
        - Start with a **bold header** naming specific roadmap(s) ONLY if citing actual pattern data
        - ONLY cite data that appears in the pattern (constraints, objectives themes, portfolio alignments, categories, etc.)
        - DO NOT attribute inferred values (like total duration, KPI targets, or estimated metrics) to roadmaps
        - Mark inferred/estimated values with ⚠️ [inferred] or ⚠️ [estimated]
        - Be explicit: "From pattern data:" vs "Inference based on scope:"
        
        Dimensions to address:
        
        1. **Timeline Guidance**: Typical state progression and stage durations from historical patterns (cite specific durations from {matched_pattern.get('avg_days_per_stage', 'pattern data')}). DO NOT cite total project duration - that's inferred. Format: "[Roadmap A, B]: Intake → Solutioning (5d, from pattern) → Approved"
        2. **Objectives Guidance**: Reference actual objective themes from the pattern ONLY (e.g., "Compliance, Performance" if those appear in roadmaps). Do NOT invent objectives.
        3. **Constraints Guidance**: Reference constraints actually mentioned in pattern data. Do NOT infer constraints not in the pattern.
        4. **Portfolio Guidance**: Portfolio alignments if present in pattern. Do NOT speculate.
        5. **Category Guidance**: Categories/tags if present in pattern. Do NOT add categories.
        6. **Business Value Guidance**: Only KPIs/targets explicitly in pattern. Do NOT infer business value targets.
        
        Return as JSON:
        {{
            "solution_guidance": "{"3-5 paragraphs naturally integrating execution insights (" + str(execution_data.get('execution_count', 0)) + " executions averaging " + str(round(execution_data.get('avg_core_score', 0), 1)) + "/100). Explain what worked, what struggled, and actionable recommendations based on the performance data." if has_execution_data else "3-5 paragraphs of rich, detailed solution guidance starting with 'Based on...'."} For inferred values, be clear: 'These roadmaps suggest X, and based on similar projects, we estimate Y'",
            "timeline_guidance": "Markdown bullets citing specific stage durations from pattern ONLY (e.g., 'Solutioning=5d'). DO NOT cite total project duration - explain how phase data can guide estimation. {"If on-time score was low (" + str(round(execution_data.get('avg_on_time_score', 0), 1)) + "/100), explain timeline risks and mitigation strategies." if has_execution_data and execution_data.get('avg_on_time_score', 0) < 60 else ""} Format: '**[Roadmap A, B]**: Intake → Solutioning (5d from pattern) → Approved. Estimated total: 4-6 months based on scope.' Mark estimates with ⚠️ [estimated]",
            "objectives_guidance": "Markdown bullets ONLY citing objective themes actually present in the referenced roadmaps. {"Optionally mention scope performance (" + str(round(execution_data.get('avg_on_scope_score', 0), 1)) + "/100) if it provides insight." if has_execution_data and execution_data.get('avg_on_scope_score', 0) > 0 else ""} If pattern lacks objective data, state: 'Pattern data insufficient for objectives guidance.'",
            "constraints_guidance": "Markdown bullets citing specific constraints from pattern data. {"If risk score (" + str(round(execution_data.get('avg_risk_score', 0), 1)) + "/100) is relevant, discuss how constraints were handled." if has_execution_data and execution_data.get('avg_risk_score', 0) > 0 else ""} Do not infer constraints. If pattern lacks constraint data, state: 'Pattern data shows no documented constraints.'",
            "portfolio_guidance": "Markdown bullets citing portfolio alignments from pattern. If not in pattern, state: 'Pattern data does not specify portfolio alignments.'",
            "category_guidance": "Markdown bullets citing categories from pattern. If not in pattern, state: 'Pattern data does not list specific categories.'",
            "business_value_guidance": "Markdown bullets citing only KPIs/targets explicitly in pattern. {"Given average execution score of " + str(round(execution_data.get('avg_core_score', 0), 1)) + "/100, set realistic ROI expectations." if has_execution_data and execution_data.get('avg_core_score', 0) > 0 else ""} DO NOT infer business value. If pattern lacks data, state: 'Pattern data does not quantify business value.'"
        }}
        """
        
        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )
        
        response = llm.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=2500, temperature=0.3),
            'roadmap_inference::generate_advice'
        )
        
        advice = extract_json_after_llm(response)
        
        appLogger.info({
            "event": "generate_advice",
            "roadmap_name": roadmap_data.get("name"),
            "patterns_used": len(matched_patterns),
            "total_roadmap_count": total_roadmap_count,
            "advice_generated": True
        })
        
        return {
            "status": "success",
            "patterns_used": len(matched_patterns),
            "pattern_references": [{
                "pattern_id": ctx["pattern_id"],
                "pattern_name": ctx["pattern_name"],
                "rank": ctx["rank"],
                "confidence_score": ctx["confidence_score"],
                "match_explanation": ctx["match_explanation"],
                "roadmap_count": ctx["roadmap_count"],
                "roadmap_names": ctx["roadmap_names"]
            } for ctx in pattern_contexts],
            "solution_guidance": advice.get("solution_guidance", ""),
            "dimension_guidance": {
                "timeline": advice.get("timeline_guidance", ""),
                "objectives": advice.get("objectives_guidance", ""),
                "constraints": advice.get("constraints_guidance", ""),
                "portfolio": advice.get("portfolio_guidance", ""),
                "category": advice.get("category_guidance", ""),
                "business_value": advice.get("business_value_guidance", "")
            },
            "pattern_synthesis_summary": advice.get("pattern_synthesis_summary", "")
        }
        
    except Exception as e:
        appLogger.error({
            "event": "generate_advice",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "status": "error",
            "error": str(e),
            "solution_guidance": None
        }


def format_state_transition_narrative(
    pattern: Dict[str, Any]
) -> Optional[str]:
    """
    Format all 4 state transition fields from a pattern into a comprehensive,
    human-readable narrative string.
    
    Combines:
    - state_transition_history: Individual roadmap transitions with dates/approvals
    - typical_state_flow: Common state progressions observed in pattern
    - stage_duration_insights: Average days spent in each stage
    - avg_days_per_stage: Compact format with aggregated duration data
    
    Example output:
    "Based on 2 roadmaps, typical execution follows: Intake -> Solutioning -> Approved.
    Most roadmaps spend avg 5 days in Solutioning stage. Historical transitions include:
    [Malaysia E-Invoicing]: On 2025-11-18, moved from Intake to Solutioning (0 days).
    [Denmark Entity]: On 2025-11-18, moved from Intake to Solutioning (5 days in Solutioning).
    [Denmark Entity]: On 2025-11-24, moved to Approved. Timeline recommendation:
    Plan for 5 days in Solutioning phase based on historical patterns."
    
    Args:
        pattern: RoadmapPattern vertex dict from TigerGraph
        
    Returns:
        Formatted narrative string if timeline data exists, None otherwise
    """
    try:
        state_transition_history = pattern.get("state_transition_history", [])
        typical_state_flow = pattern.get("typical_state_flow", [])
        stage_duration_insights = pattern.get("stage_duration_insights", [])
        avg_days_per_stage = pattern.get("avg_days_per_stage", "")
        
        # Check if any timeline data exists
        has_timeline_data = (
            (state_transition_history and len(state_transition_history) > 0) or
            (typical_state_flow and len(typical_state_flow) > 0) or
            (stage_duration_insights and len(stage_duration_insights) > 0) or
            (avg_days_per_stage and avg_days_per_stage.strip())
        )
        
        if not has_timeline_data:
            return None
        
        # Build the narrative
        lines = []
        
        # 1. Common state flow section
        if typical_state_flow and len(typical_state_flow) > 0:
            flow_str = " -> ".join(typical_state_flow)
            roadmap_count = len(pattern.get("roadmap_ids", []))
            lines.append(
                f"Typical execution flow (from {roadmap_count} roadmaps): {flow_str}."
            )
        
        # 2. Stage duration insights section
        if stage_duration_insights and len(stage_duration_insights) > 0:
            insights_str = ", ".join(stage_duration_insights)
            lines.append(f"Stage duration patterns: {insights_str}.")
        
        # 3. Compact average days section
        if avg_days_per_stage and avg_days_per_stage.strip():
            lines.append(f"Aggregated stage durations: {avg_days_per_stage}.")
        
        # 4. State transition history section
        if state_transition_history and len(state_transition_history) > 0:
            lines.append("Historical state transitions:")
            for idx, transition in enumerate(state_transition_history[:10], 1):  # Limit to 10 entries
                # transition format: "[Roadmap Name]: On DATE, moved from STATE to STATE, STATUS. (DURATION)"
                lines.append(f"  {idx}. {transition}")
        
        narrative = "\n".join(lines)
        
        appLogger.info({
            "event": "format_state_transition_narrative",
            "pattern_id": pattern.get("id"),
            "has_narrative": True,
            "narrative_length": len(narrative),
            "transition_count": len(state_transition_history),
            "flow_count": len(typical_state_flow)
        })
        
        return narrative
        
    except Exception as e:
        appLogger.error({
            "event": "format_state_transition_narrative",
            "pattern_id": pattern.get("id"),
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return None


def extract_state_transition_insights(
    pattern: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Extract and validate state transition insights from a RoadmapPattern vertex.
    
    Checks if the pattern contains populated state transition data and extracts:
    - state_transition_history: Full timeline entries with roadmap attribution
    - typical_state_flow: Common state progressions (e.g., "Intake -> Solutioning")
    - stage_duration_insights: Average days per stage (e.g., "Solutioning: avg 5 days")
    - avg_days_per_stage: Compact format (e.g., "Solutioning=5d")
    
    State Values Reference:
    - 0: Intake
    - 1: Approved
    - 2: Execution
    - 3: Archived
    - 4: Elaboration
    - 5: Solutioning
    - 6: Prioritize
    - 99: Hold
    - 100: Rejected
    - 999: Cancelled
    - 200: Draft
    
    Args:
        pattern: RoadmapPattern vertex dict from TigerGraph
        
    Returns:
        Dict with extracted state transition insights if available, None if empty
    """
    try:
        # Check if pattern has state transition data
        state_transition_history = pattern.get("state_transition_history", [])
        typical_state_flow = pattern.get("typical_state_flow", [])
        stage_duration_insights = pattern.get("stage_duration_insights", [])
        avg_days_per_stage = pattern.get("avg_days_per_stage", "")
        
        # Validate: at least one field should have data
        has_timeline_data = (
            (state_transition_history and len(state_transition_history) > 0) or
            (typical_state_flow and len(typical_state_flow) > 0) or
            (stage_duration_insights and len(stage_duration_insights) > 0) or
            (avg_days_per_stage and avg_days_per_stage.strip())
        )
        
        if not has_timeline_data:
            # No state transition data in this pattern
            appLogger.info({
                "event": "extract_state_transition_insights",
                "pattern_id": pattern.get("id"),
                "has_timeline_data": False,
                "reason": "all_timeline_fields_empty"
            })
            return None
        
        # Extract and structure the insights
        insights = {
            "has_timeline_data": True,
            "state_transition_history": state_transition_history,
            "typical_state_flow": typical_state_flow,
            "stage_duration_insights": stage_duration_insights,
            "avg_days_per_stage": avg_days_per_stage,
            "summary": {
                "num_transitions": len(state_transition_history),
                "common_flows": len(typical_state_flow),
                "stage_metrics": len(stage_duration_insights),
                "has_avg_days": bool(avg_days_per_stage)
            }
        }
        
        # Log successful extraction
        appLogger.info({
            "event": "extract_state_transition_insights",
            "pattern_id": pattern.get("id"),
            "has_timeline_data": True,
            "num_transitions": len(state_transition_history),
            "common_flows": len(typical_state_flow)
        })
        
        return insights
        
    except Exception as e:
        appLogger.error({
            "event": "extract_state_transition_insights",
            "pattern_id": pattern.get("id"),
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return None


def get_templates_for_roadmap_pattern(
    graph_connector: GraphConnector,
    pattern_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieve RoadmapTemplate vertices connected to a pattern via the
    supportedByRoadmapTemplate edge in TigerGraph.
    
    This uses the graph edge relationship rather than a template_id attribute,
    as defined in trmeric_schema.py:
    - supportedByRoadmapTemplate: FROM RoadmapPattern TO RoadmapTemplate
    
    Args:
        graph_connector: Connected GraphConnector instance
        pattern_id: The ID of the RoadmapPattern vertex
        
    Returns:
        List of roadmap templates connected to this pattern
    """
    if not pattern_id:
        return []
    
    try:
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_templates_for_roadmap_pattern",
                "error": "Failed to connect to graph"
            })
            return []
        
        # Use getEdges to traverse the supportedByRoadmapTemplate edge
        # from the pattern to find connected templates
        edges = graph_connector.get_edges(
            sourceVertexType="RoadmapPattern",
            sourceVertexId=pattern_id,
            edgeType="supportedByRoadmapTemplate"
        )
        
        appLogger.info({
            "event": "get_templates_for_roadmap_pattern",
            "pattern_id": pattern_id,
            "edge_type": "supportedByRoadmapTemplate",
            "edges_found": len(edges) if edges else 0
        })
        
        if not edges:
            return []
        
        templates_list = []
        
        # Extract target template IDs from edges and fetch full template data
        for edge in edges:
            if isinstance(edge, dict):
                # Get the target vertex ID (the template)
                target_id = edge.get("to_id") or edge.get("t_id")
                if target_id:
                    # Fetch the full template vertex
                    try:
                        template_vertex = graph_connector.get_vertices_by_id(
                            "RoadmapTemplate",
                            [target_id]
                        )
                        
                        if template_vertex and isinstance(template_vertex, list) and len(template_vertex) > 0:
                            tv = template_vertex[0]
                            if isinstance(tv, dict):
                                attributes = tv.get("attributes", {})
                                templates_list.append({
                                    "id": target_id,
                                    "name": attributes.get("name", ""),
                                    "title": attributes.get("title", ""),
                                    "roadmap_type": attributes.get("roadmap_type", ""),
                                    "description": attributes.get("description", ""),
                                    "objectives": attributes.get("objectives", ""),
                                    "solution": attributes.get("solution", ""),
                                    "strategic_goal": attributes.get("strategic_goal", ""),
                                    "category": attributes.get("category", ""),
                                    "org_strategy_align": attributes.get("org_strategy_align", ""),
                                    "current_state": attributes.get("current_state", ""),
                                    "visibility": attributes.get("visibility", ""),
                                    "version": attributes.get("version", ""),
                                    "timeline": {
                                        "start_date": attributes.get("start_date", ""),
                                        "end_date": attributes.get("end_date", ""),
                                        "time_horizon": attributes.get("time_horizon", ""),
                                        "review_cycle": attributes.get("review_cycle", "")
                                    },
                                    "budget": attributes.get("budget", 0),
                                    "status": attributes.get("status", ""),
                                    "priority": attributes.get("priority", ""),
                                    "tags": attributes.get("tags", ""),
                                    "template_source": attributes.get("template_source", ""),
                                    "adoption_count": attributes.get("adoption_count", 0),
                                    "validity_score": attributes.get("validity_score", 0),
                                    "created_at": attributes.get("created_at", ""),
                                    "updated_at": attributes.get("updated_at", "")
                                })
                    except Exception as e:
                        appLogger.warning({
                            "event": "get_templates_for_roadmap_pattern",
                            "template_id": target_id,
                            "error": str(e)
                        })
                        continue
        
        appLogger.info({
            "event": "get_templates_for_roadmap_pattern",
            "pattern_id": pattern_id,
            "templates_retrieved": len(templates_list)
        })
        
        return templates_list
        
    except Exception as e:
        appLogger.error({
            "event": "get_templates_for_roadmap_pattern",
            "pattern_id": pattern_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def infer_roadmap(
    tenant_id,
    roadmap_data: Dict[str, Any],
    graph_connector: Optional[GraphConnector] = None,
    llm: Optional[ChatGPTClient] = None,
    scope_filter: Optional[str] = None,
    include_templates: bool = True,
    graphname: str = "",
    use_execution_insights: bool = True
) -> Dict[str, Any]:
    """
    Complete roadmap inference pipeline - STANDALONE FUNCTION.

    Takes minimal roadmap data and returns generation advice based on pattern matching
    from the TigerGraph knowledge base. Matches against RoadmapPattern vertices that
    aggregate learnings from multiple successful roadmaps.

    Args:
        roadmap_data: Minimal roadmap data {
            "name": "Roadmap Name",
            "description": "Roadmap description",
            "category": "optional category",
            "objectives": "optional objectives",
            "roadmap_type": "optional type"
        }
        graph_connector: Optional GraphConnector instance (creates one if not provided)
        llm: Optional LLM client (creates one if not provided)
        scope_filter: Optional filter for pattern scope (workflow, portfolio, customer)
        include_templates: If True, fetch and include template examples from similar roadmaps
        graphname: Graph name to use (required if graph_connector not provided)
        use_execution_insights: If True (default), include execution scoring data in inference

    Returns:
        Complete inference result with matched pattern and derived advice
    """
    if llm is None:
        llm = ChatGPTClient()

    tenant_id = int(tenant_id)
    
    # Initialize logging
    if graph_connector is None:
        try:
            if not graphname:
                raise ValueError("graphname is required when graph_connector is not provided")
            graph_config = GraphConnectorConfig.from_env(graphname)
            graph_connector = GraphConnector(graph_config)
            graph_connector.connect()
        except Exception as e:
            appLogger.error({
                "event": "infer_roadmap",
                "error": "Failed to initialize graph connector",
                "details": str(e)
            })
            return {
                "inference_status": "error",
                "error": "Failed to connect to knowledge graph"
            }
    
    try:
        appLogger.info({
            "event": "infer_roadmap_start",
            "roadmap_name": roadmap_data.get("name"),
            "scope_filter": scope_filter,
            "use_execution_insights": use_execution_insights
        })

        # Step 0.5: Cluster performance analysis (if execution insights enabled)
        cluster_performance = None
        if use_execution_insights:
            try:
                cluster_performance = analyze_roadmap_cluster_performance(
                    graph_connector, tenant_id, llm
                )
                appLogger.info({
                    "event": "infer_roadmap",
                    "step": "cluster_performance",
                    "success": True,
                    "top_patterns_found": len(cluster_performance.get("top_performing_patterns", []))
                })
            except Exception as e:
                appLogger.warning({
                    "event": "infer_roadmap",
                    "step": "cluster_performance",
                    "error": str(e),
                    "message": "Failed to retrieve cluster performance, continuing without it"
                })
                cluster_performance = None

        # Step 1: Get roadmap patterns from TigerGraph (with execution data if enabled)
        if use_execution_insights:
            try:
                patterns = get_roadmap_patterns_with_execution_scores(
                    graph_connector, tenant_id, limit=20, scope_filter=scope_filter
                )
                patterns_with_execution = sum(
                    1 for p in patterns
                    if p.get("execution_data", {}).get("execution_count", 0) > 0
                )
                appLogger.info({
                    "event": "infer_roadmap",
                    "step": "get_patterns_with_execution",
                    "patterns_retrieved": len(patterns),
                    "patterns_with_execution_data": patterns_with_execution
                })
            except Exception as e:
                appLogger.warning({
                    "event": "infer_roadmap",
                    "step": "get_patterns_with_execution",
                    "error": str(e),
                    "message": "Failed to retrieve execution data, falling back to standard patterns"
                })
                # Fall back to standard pattern retrieval
                patterns = get_roadmap_patterns_from_graph(
                    graph_connector, tenant_id, limit=20, scope_filter=scope_filter
                )
        else:
            patterns = get_roadmap_patterns_from_graph(
                graph_connector, tenant_id, limit=20, scope_filter=scope_filter
            )
        
        if not patterns:
            appLogger.warning({
                "event": "infer_roadmap",
                "message": "No patterns found in knowledge graph",
                "scope_filter": scope_filter,
                "graphname": graphname
            })
            return {
                "inference_status": "no_patterns",
                "message": "No roadmap patterns available in knowledge graph for comparison",
                "scope_filter": scope_filter,
                "roadmap_data_description": roadmap_data.get("description", "")[:100]
            }
        
        # Step 2: Match roadmap against patterns - now returns top 2 patterns
        match_result = match_patterns(roadmap_data, patterns, llm)
        
        matched_patterns_data = match_result.get("matched_patterns", [])
        match_strategy = match_result.get("match_strategy", "dual_pattern")
        overall_confidence = match_result.get("overall_confidence", 0.0)
        
        if not matched_patterns_data:
            appLogger.warning({
                "event": "infer_roadmap",
                "message": "No patterns matched",
                "scope_filter": scope_filter
            })
            return {
                "inference_status": "no_patterns",
                "message": "No suitable pattern matches found in knowledge graph",
                "match_strategy": match_strategy,
                "overall_confidence": overall_confidence
            }
        
        # Build roadmap ID to name mapping BEFORE generating advice
        # Only fetch names for roadmap IDs that are referenced in the matched patterns
        roadmap_id_to_name_mapping = {}
        try:
            # Collect unique roadmap IDs from matched patterns
            unique_roadmap_ids = set()
            for pattern in [mp["pattern"] for mp in matched_patterns_data]:
                roadmap_ids = pattern.get("roadmap_ids", [])
                # roadmap_ids is a LIST<STRING> attribute from RoadmapPattern vertex
                # Convert to int for consistent mapping key type
                for rid in roadmap_ids:
                    try:
                        unique_roadmap_ids.add(int(rid))
                    except (ValueError, TypeError):
                        appLogger.warning(f"Invalid roadmap ID format: {rid}")
            
            if unique_roadmap_ids:
                # Fetch names for all unique roadmap IDs
                roadmap_ids_list = list(unique_roadmap_ids)
                all_roadmaps = RoadmapDao.FetchRoadmapNamesWithIDS(tenant_id, roadmap_ids_list)
                if all_roadmaps:
                    for roadmap in all_roadmaps:
                        roadmap_id = int(roadmap.get('id', 0))
                        roadmap_title = roadmap.get('title', f'Roadmap {roadmap_id}')
                        roadmap_id_to_name_mapping[roadmap_id] = roadmap_title
            appLogger.info({
                "event": "infer_roadmap",
                "step": "build_roadmap_name_mapping",
                "mapped_count": len(roadmap_id_to_name_mapping)
            })
        except Exception as e:
            appLogger.warning({
                "event": "infer_roadmap",
                "step": "build_roadmap_name_mapping",
                "error": str(e)
            })
        
        # Step 4: Generate advice by applying pattern to current context
        # Extract tenant_id from roadmap_data if available, otherwise use current tenant
        tenant_id = roadmap_data.get("tenant_id", tenant_id)
        advice_result = generate_advice(
            roadmap_data,
            matched_patterns_data,
            llm,
            tenant_id=tenant_id,
            cluster_performance=cluster_performance
        )
        
        # Check if we have valid advice
        if advice_result.get("status") == "low_confidence":
            return {
                "inference_status": advice_result.get("status"),
                "message": advice_result.get("message", "Error generating advice"),
                "patterns_matched": len(matched_patterns_data),
                "match_strategy": match_strategy
            }
        
        # Step 4: Extract enhanced pattern references and state transition data
        primary_pattern = matched_patterns_data[0]["pattern"] if matched_patterns_data else None
        pattern_refs = advice_result.get("pattern_references", [])
        
        # Collect all roadmap names and IDs from all patterns
        all_roadmap_names = []
        all_roadmap_ids = []
        total_roadmap_count = 0
        
        for ref in pattern_refs:
            all_roadmap_names.extend(ref["roadmap_names"])
            total_roadmap_count += ref["roadmap_count"]
            # Note: roadmap_ids would need to be added to pattern_references if needed
        
        # Extract state transition insights from primary pattern
        state_transition_insights = None
        state_transition_narrative = None
        if primary_pattern:
            state_transition_insights = extract_state_transition_insights(primary_pattern)
            state_transition_narrative = format_state_transition_narrative(primary_pattern)
        
        # Step 5: Fetch templates from primary pattern
        template_examples = []
        if include_templates and primary_pattern:
            template_examples = get_templates_for_roadmap_pattern(
                graph_connector, 
                primary_pattern.get("id")
            )
        
        # Build enhanced result with multi-pattern support
        result = {
            "inference_status": "success",
            "match_strategy": match_strategy,
            "patterns_used": len(matched_patterns_data),
            "overall_confidence": overall_confidence,
            "roadmap": {
                "name": roadmap_data.get("name"),
                "description": roadmap_data.get("description", "")[:200]
            },
            # Enhanced pattern matching info
            "pattern_match": {
                "strategy": match_strategy,
                "patterns_matched": len(matched_patterns_data),
                "total_roadmap_count": total_roadmap_count,
                "primary_pattern": {
                    "pattern_id": pattern_refs[0]["pattern_id"] if pattern_refs else None,
                    "pattern_name": pattern_refs[0]["pattern_name"] if pattern_refs else None,
                    "confidence": pattern_refs[0]["confidence_score"] if pattern_refs else 0.0,
                    "explanation": pattern_refs[0]["match_explanation"] if pattern_refs else "",
                    "roadmap_count": pattern_refs[0]["roadmap_count"] if pattern_refs else 0,
                    "roadmap_names": pattern_refs[0]["roadmap_names"] if pattern_refs else []
                },
                "secondary_pattern": {
                    "pattern_id": pattern_refs[1]["pattern_id"] if len(pattern_refs) > 1 else None,
                    "pattern_name": pattern_refs[1]["pattern_name"] if len(pattern_refs) > 1 else None,
                    "confidence": pattern_refs[1]["confidence_score"] if len(pattern_refs) > 1 else None,
                    "explanation": pattern_refs[1]["match_explanation"] if len(pattern_refs) > 1 else None,
                    "roadmap_count": pattern_refs[1]["roadmap_count"] if len(pattern_refs) > 1 else None,
                    "roadmap_names": pattern_refs[1]["roadmap_names"] if len(pattern_refs) > 1 else None
                } if len(pattern_refs) > 1 else None
            },
            # Legacy format for backwards compatibility
            "pattern_reference": {
                "pattern_id": pattern_refs[0]["pattern_id"] if pattern_refs else None,
                "pattern_name": pattern_refs[0]["pattern_name"] if pattern_refs else None,
                "roadmap_count": total_roadmap_count,
                "roadmap_names": all_roadmap_names[:10],  # Limit for legacy compatibility
                "roadmap_ids": all_roadmap_ids[:10] if all_roadmap_ids else []
            },
            # Enhanced pattern data for formatting functions
            "matched_pattern": primary_pattern if primary_pattern else {},
            "all_matched_patterns": [mp["pattern"] for mp in matched_patterns_data],
            "pattern_details": pattern_refs,
            # State transition data from primary pattern
            "state_transition_insights": state_transition_insights,
            "state_transition_narrative": state_transition_narrative,
            # Synthesized guidance
            "solution_guidance": advice_result.get("solution_guidance", ""),
            "dimension_guidance": advice_result.get("dimension_guidance", {}),
            "pattern_synthesis_summary": advice_result.get("pattern_synthesis_summary", ""),
            "template_examples": template_examples,
            "roadmap_id_to_name_mapping": roadmap_id_to_name_mapping
        }

        # Add execution insights to result if enabled
        if use_execution_insights:
            result["execution_insights"] = {
                "enabled": True,
                "cluster_performance": cluster_performance,
                "pattern_execution_data": primary_pattern.get("execution_data") if primary_pattern else None
            }
            appLogger.info({
                "event": "infer_roadmap",
                "step": "execution_insights_added",
                "has_cluster_performance": cluster_performance is not None,
                "has_pattern_execution_data": primary_pattern.get("execution_data", {}).get("execution_count", 0) > 0 if primary_pattern else False
            })
        else:
            result["execution_insights"] = {"enabled": False}

        appLogger.info({
            "event": "infer_roadmap_complete",
            "roadmap_name": roadmap_data.get("name"),
            "primary_pattern_id": pattern_refs[0]["pattern_id"] if pattern_refs else None,
            "pattern_roadmap_count": total_roadmap_count,
            "overall_confidence": overall_confidence,
            "templates_included": len(template_examples),
            "patterns_used": len(matched_patterns_data)
        })
        
        return result
    except Exception as e:
        appLogger.error({
            "event": "infer_roadmap",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "inference_status": "error",
            "error": str(e)
        }

def format_pattern_info_markdown(inference_result: Dict[str, Any]) -> str:
    """
    Format the inference result into a user-friendly markdown string
    for display in the frontend. Uses LLM to create narrative intro.
    
    Args:
        inference_result: Full result from infer_roadmap()
        
    Returns:
        Formatted markdown string with pattern information
    """
    if not inference_result or inference_result.get("inference_status") != "success":
        return ""
    
    pattern_match = inference_result.get("pattern_match", {})
    pattern_details = inference_result.get("pattern_details", [])
    overall_confidence = inference_result.get("overall_confidence", 0.0)
    solution_guidance = inference_result.get("solution_guidance", "")
    synthesis_summary = inference_result.get("pattern_synthesis_summary", "")
    
    # Start building markdown
    markdown_parts = []
    
    # Header
    markdown_parts.append("## 🎯 Insights from Your Organization's Experience\n")
    
    # Strategy and overall info
    strategy = pattern_match.get("strategy", "")
    patterns_matched = pattern_match.get("patterns_matched", 0)
    total_roadmaps = pattern_match.get("total_roadmap_count", 0)
    
    # Use LLM to generate narrative introduction
    try:
        llm = ChatGPTClient()
        
        # Collect pattern information for context
        pattern_info_for_llm = []
        for detail in pattern_details:
            pattern_info_for_llm.append({
                "name": detail.get("pattern_name", ""),
                "confidence": detail.get("confidence_score", 0.0),
                "roadmap_count": detail.get("roadmap_count", 0),
                "roadmap_names": detail.get("roadmap_names", [])[:3]
            })
        
        intro_prompt = f"""
        Write a 2-3 sentence narrative introduction for a pattern analysis report.
        
        Context:
        - Strategy: {strategy}
        - Patterns matched: {patterns_matched}
        - Total historical roadmaps: {total_roadmaps}
        - Overall confidence: {overall_confidence:.0%}
        - Patterns: {json.dumps(pattern_info_for_llm)}
        
        Style: User-friendly, conversational, emphasizing value. Avoid technical jargon.
        Focus on what this means for the user, not technical details.
        
        Return ONLY the introduction text, no JSON, no formatting.
        """
        
        chat_completion = ChatCompletion(
            system="You are a business communication expert writing for executives and project managers.",
            prev=[],
            user=intro_prompt
        )
        
        intro = llm.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=200, temperature=0.7),
            'roadmap_inference::format_intro'
        ).strip()
        
        markdown_parts.append(intro + "\n")
        
    except Exception as e:
        # Fallback to template if LLM fails
        appLogger.warning({"event": "format_intro_llm_failed", "error": str(e)})
        if strategy == "single_rich_pattern":
            intro = f"We found a strong pattern in your organization's history that closely matches this initiative. Drawing from **{total_roadmaps} similar roadmaps**, we've identified insights that can guide your planning with **{overall_confidence:.0%} confidence**."
        elif strategy == "dual_pattern":
            intro = f"Your organization has experience with initiatives like this one. We've identified **{patterns_matched} complementary patterns** across **{total_roadmaps} historical roadmaps** that together provide comprehensive guidance with **{overall_confidence:.0%} confidence**."
        else:
            intro = f"We've analyzed **{total_roadmaps} roadmaps** from your organization's history and identified **{patterns_matched} relevant patterns** that can inform your approach with **{overall_confidence:.0%} confidence**."
        
        markdown_parts.append(intro + "\n")
    
    # Primary pattern details - narrative style
    if pattern_details and len(pattern_details) > 0:
        primary = pattern_details[0]
        pattern_name = primary.get('pattern_name', 'N/A')
        confidence_score = primary.get('confidence_score', 0.0)
        roadmap_count = primary.get('roadmap_count', 0)
        
        markdown_parts.append(f"## 📊 Learning from the '{pattern_name}'\n")
        markdown_parts.append(f"This pattern emerged from **{roadmap_count} successful initiatives** in your organization, giving us **{confidence_score:.0%} confidence** in its applicability to your current roadmap.\n")
        
        roadmap_names = primary.get("roadmap_names", [])
        if roadmap_names:
            markdown_parts.append("**Similar initiatives that informed this analysis:**\n")
            for idx, name in enumerate(roadmap_names[:5], 1):  # Show top 5
                markdown_parts.append(f"{idx}. {name}")
            
            if len(roadmap_names) > 5:
                markdown_parts.append(f"\n*...along with {len(roadmap_names) - 5} other related projects*\n")
            else:
                markdown_parts.append("")
    
    # Secondary pattern (if dual pattern strategy) - narrative style
    if len(pattern_details) > 1:
        secondary = pattern_details[1]
        pattern_name = secondary.get('pattern_name', 'N/A')
        confidence_score = secondary.get('confidence_score', 0.0)
        roadmap_count = secondary.get('roadmap_count', 0)
        
        markdown_parts.append(f"## 🔗 Complementary Insights from '{pattern_name}'\n")
        markdown_parts.append(f"We also identified valuable lessons from **{roadmap_count} projects** following this pattern, which adds depth to our guidance with **{confidence_score:.0%} confidence**.\n")
        
        roadmap_names = secondary.get("roadmap_names", [])
        if roadmap_names:
            markdown_parts.append("**Additional reference projects:**\n")
            for idx, name in enumerate(roadmap_names[:3], 1):  # Show top 3 for secondary
                markdown_parts.append(f"{idx}. {name}")
            
            if len(roadmap_names) > 3:
                markdown_parts.append(f"\n*...and {len(roadmap_names) - 3} more*\n")
            else:
                markdown_parts.append("")
    
    # Pattern synthesis - more narrative
    if synthesis_summary:
        markdown_parts.append(f"## 💡 What This Means for Your Roadmap\n")
        markdown_parts.append(f"{synthesis_summary}\n")
    
    # Solution guidance
    if solution_guidance:
        markdown_parts.append(f"## 🎯 Practical Guidance Based on Past Success\n")
        markdown_parts.append(f"{solution_guidance}\n")
    
    # Value proposition - more conversational
    markdown_parts.append(f"## ✨ Why This Matters\n")
    markdown_parts.append(f"Rather than starting from scratch, you're building on the collective wisdom of **{total_roadmaps} roadmaps** your organization has already executed. This means you can:")
    markdown_parts.append(f"\n- Leverage proven timelines and realistic milestones from projects that actually happened")
    markdown_parts.append(f"- Set objectives and success metrics that have been validated in your specific organizational context")
    markdown_parts.append(f"- Anticipate constraints and challenges that others encountered—and learn from their solutions")
    markdown_parts.append(f"- Allocate resources based on patterns that led to successful outcomes")
    markdown_parts.append(f"- Align with portfolios in ways that have worked well historically\n")
    markdown_parts.append(f"*This isn't guesswork or generic best practices—it's your organization's real experience guiding your next initiative.*")
    
    return "\n".join(markdown_parts)