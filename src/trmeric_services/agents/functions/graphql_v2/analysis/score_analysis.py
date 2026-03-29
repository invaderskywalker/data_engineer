"""
Score Analysis Engine

Analyzes top/bottom performing projects based on scoring data.
Takes n highest or lowest scoring projects and uses LLM to identify:
- Common patterns contributing to success or failure
- Similarities in project attributes, approaches, and execution
- Recommendations based on analysis

Works within a single tenant scope, analyzing actual project data.
"""

from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, asdict
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient, ModelOptions
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ProjectsDao
from ..infrastructure import GraphConnector, GraphConnectorConfig
import json
import traceback


@dataclass
class ScoreAnalysisRequest:
    """Request parameters for score analysis."""
    tenant_id: int
    rank_type: Literal["highest", "lowest"]  # Analyze top or bottom performers
    n: int = 5  # Number of projects to analyze
    score_dimension: Optional[str] = None  # Optional: filter by dimension (on_time, on_scope, etc.)


@dataclass 
class ContributingFactor:
    """A factor that contributed to project performance."""
    factor: str
    description: str
    evidence: List[str]  # Project names/IDs that exhibit this factor
    impact: str  # "positive" or "negative"
    confidence: str  # "high", "medium", "low"


@dataclass
class CommonPattern:
    """A pattern found across analyzed projects."""
    pattern_name: str
    description: str
    frequency: str  # e.g., "4/5 projects"
    related_attributes: List[str]


@dataclass
class Recommendation:
    """Actionable recommendation based on analysis."""
    recommendation: str
    rationale: str
    priority: str  # "high", "medium", "low"
    applicable_to: str  # "all projects", "similar scope", etc.


@dataclass
class ScoreAnalysisResult:
    """Result of score analysis."""
    analysis_type: str  # "top_performers" or "bottom_performers"
    tenant_id: int
    projects_analyzed: List[Dict[str, Any]]
    score_summary: Dict[str, Any]
    common_patterns: List[CommonPattern]
    contributing_factors: List[ContributingFactor]
    key_differentiators: List[str]
    recommendations: List[Recommendation]
    analysis_confidence: str
    llm_reasoning: str


def get_project_scores_from_graph(
    graph_connector: GraphConnector,
    tenant_id: int,
    rank_type: Literal["highest", "lowest"],
    n: int,
    score_dimension: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve project scores from TigerGraph, ranked by score.
    
    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID to filter scores
        rank_type: "highest" or "lowest"
        n: Number of projects to retrieve
        score_dimension: Optional specific dimension to rank by
        
    Returns:
        List of project score data ordered by score
    """
    try:
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_project_scores_from_graph",
                "error": "Failed to connect to graph"
            })
            return []
        
        # Fetch all ProjectScore vertices for this tenant
        # We fetch more than n to ensure we have enough after filtering
        all_scores = graph_connector._connection.getVertices("ProjectScore", limit=100)
        
        if not all_scores:
            return []
        
        # Filter by tenant and extract score data
        tenant_scores = []
        for score_vertex in all_scores:
            if isinstance(score_vertex, dict):
                attrs = score_vertex.get("attributes", {})
                # Handle tenant_id as both string and int for comparison
                vertex_tenant_id = attrs.get("tenant_id")
                if str(vertex_tenant_id) == str(tenant_id):
                    # Determine which score to rank by
                    if score_dimension:
                        rank_score = attrs.get(f"{score_dimension}_score", attrs.get("core_score", 0))
                    else:
                        rank_score = attrs.get("core_score", 0)
                    
                    tenant_scores.append({
                        "score_id": score_vertex.get("v_id", ""),
                        "project_id": attrs.get("project_id"),
                        "project_title": attrs.get("project_title", ""),
                        "project_status": attrs.get("project_status", ""),
                        "core_score": attrs.get("core_score", 0),
                        "on_time_score": attrs.get("on_time_score", 0),
                        "on_scope_score": attrs.get("on_scope_score", 0),
                        "on_budget_score": attrs.get("on_budget_score", 0),
                        "risk_management_score": attrs.get("risk_management_score", 0),
                        "team_health_score": attrs.get("team_health_score", 0),
                        "on_time_explanation": attrs.get("on_time_explanation", ""),
                        "on_scope_explanation": attrs.get("on_scope_explanation", ""),
                        "on_budget_explanation": attrs.get("on_budget_explanation", ""),
                        "risk_management_explanation": attrs.get("risk_management_explanation", ""),
                        "team_health_explanation": attrs.get("team_health_explanation", ""),
                        "llm_explanation": attrs.get("llm_explanation", ""),
                        "confidence_overall": attrs.get("confidence_overall", 0),
                        "confidence_interpretation": attrs.get("confidence_interpretation", ""),
                        "milestone_pattern": attrs.get("milestone_pattern", ""),
                        "milestone_on_time_ratio": attrs.get("milestone_on_time_ratio", 0.0),
                        "complication_pattern": attrs.get("complication_pattern", ""),
                        "rank_score": rank_score
                    })
        
        # Sort by rank_score
        if rank_type == "highest":
            tenant_scores.sort(key=lambda x: x["rank_score"], reverse=True)
        else:
            tenant_scores.sort(key=lambda x: x["rank_score"])
        
        # Return top n
        return tenant_scores[:n]
        
    except Exception as e:
        appLogger.error({
            "event": "get_project_scores_from_graph",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def fetch_project_details(tenant_id: int, project_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch detailed project data using ProjectsDao.
    
    Args:
        tenant_id: Tenant ID
        project_ids: List of project IDs to fetch
        
    Returns:
        List of project detail dictionaries with all relevant data
    """
    if not project_ids:
        return []
    
    try:
        # Fetch basic project info with milestones, KPIs, insights
        projects = ProjectsDao.fetchInfoForListOfProjects(project_ids)
        
        if not projects:
            return []
        
        # Enrich with team data for each project
        enriched_projects = []
        for project in projects:
            pid = project.get("project_id")
            
            # Fetch team details
            team_data = ProjectsDao.fetchProjectTeamDetails(pid)
            
            enriched_projects.append({
                "project_id": pid,
                "project_title": project.get("project_title", ""),
                "start_date": str(project.get("start_date", "")) if project.get("start_date") else None,
                "end_date": str(project.get("end_date", "")) if project.get("end_date") else None,
                "project_type": project.get("project_type", ""),
                "spend_status": project.get("spend_status", ""),
                "scope_status": project.get("scope_status", ""),
                "delivery_status": project.get("delivery_status", ""),
                "project_manager": project.get("project_manager_name", ""),
                "kpis": [k for k in (project.get("kpi_names") or []) if k],
                "milestones": project.get("milestones") or [],
                "insights": [i for i in (project.get("insights") or []) if i],
                "team": team_data.get("team_members", []) if team_data else [],
                "pm_details": team_data.get("pm") if team_data else None
            })
        
        return enriched_projects
            
    except Exception as e:
        appLogger.error({
            "event": "fetch_project_details",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def _build_analysis_prompt(
    rank_type: Literal["highest", "lowest"],
    projects_with_scores: List[Dict[str, Any]],
    project_details: List[Dict[str, Any]]
) -> str:
    """Build the LLM prompt for score analysis."""
    
    performance_label = "top-performing" if rank_type == "highest" else "underperforming"
    analysis_focus = "success factors" if rank_type == "highest" else "areas of concern"
    
    # Merge score data with project details
    projects_data = []
    details_by_id = {p["project_id"]: p for p in project_details}
    
    for score in projects_with_scores:
        pid = score["project_id"]
        detail = details_by_id.get(pid, {})
        
        projects_data.append({
            "project_id": pid,
            "title": score.get("project_title", detail.get("name", "Unknown")),
            "scores": {
                "overall": score.get("core_score", 0),
                "on_time": score.get("on_time_score", 0),
                "on_scope": score.get("on_scope_score", 0),
                "on_budget": score.get("on_budget_score", 0),
                "risk_management": score.get("risk_management_score", 0),
                "team_health": score.get("team_health_score", 0)
            },
            "score_explanations": {
                "on_time": score.get("on_time_explanation", ""),
                "on_scope": score.get("on_scope_explanation", ""),
                "on_budget": score.get("on_budget_explanation", ""),
                "risk_management": score.get("risk_management_explanation", ""),
                "team_health": score.get("team_health_explanation", ""),
                "overall_analysis": score.get("llm_explanation", "")
            },
            "confidence": {
                "overall": score.get("confidence_overall", 0),
                "interpretation": score.get("confidence_interpretation", "")
            },
            "signals": {
                "milestone_pattern": score.get("milestone_pattern", ""),
                "milestone_on_time_ratio": score.get("milestone_on_time_ratio", 0),
                "complication_pattern": score.get("complication_pattern", "")
            },
            "project_attributes": {
                "description": detail.get("description", "")[:500] if detail.get("description") else "",
                "project_type": detail.get("project_type", []),
                "sdlc_method": detail.get("sdlc_method", []),
                "project_category": detail.get("project_category", ""),
                "delivery_status": detail.get("delivery_status", ""),
                "scope_status": detail.get("scope_status", ""),
                "spend_status": detail.get("spend_status", ""),
                "technology_stack": detail.get("technology_stack", ""),
                "start_date": str(detail.get("start_date", "")) if detail.get("start_date") else "",
                "end_date": str(detail.get("end_date", "")) if detail.get("end_date") else ""
            },
            "milestones": [
                {
                    "name": m.get("milestone_name", ""),
                    "type": m.get("type", ""),
                    "status": "completed" if m.get("actual_date") else "pending",
                    "on_time": m.get("actual_date") <= m.get("target_date") if m.get("actual_date") and m.get("target_date") else None
                }
                for m in detail.get("milestones", [])[:10]  # Limit to 10 milestones
            ],
            "team_size": len(detail.get("team", [])),
            "team_roles": list(set(t.get("role", "") for t in detail.get("team", []) if t.get("role"))),
            "technologies": [t.get("name", "") for t in detail.get("technologies", [])],
            "risk_count": len(detail.get("risks", [])),
            "active_risks": [r.get("description", "")[:100] for r in detail.get("risks", []) if r.get("status") == "Active"][:5],
            "kpi_count": len(detail.get("kpis", []))
        })
    
    projects_json = json.dumps(projects_data, indent=2, default=str)
    
    prompt = f"""You are an expert project management analyst. Analyze these {len(projects_with_scores)} {performance_label} projects to identify {analysis_focus} and patterns.

═══════════════════════════════════════════════════════════════════
PROJECT DATA FOR ANALYSIS
═══════════════════════════════════════════════════════════════════

{projects_json}

═══════════════════════════════════════════════════════════════════
ANALYSIS TASK
═══════════════════════════════════════════════════════════════════

Analyze these {performance_label} projects (ranked by overall score) and identify:

1. **Common Patterns**: What attributes, approaches, or characteristics appear across multiple projects?
   - Look at project types, methodologies, technologies, team structures
   - Identify patterns in milestone management, risk handling, status tracking
   - Note any patterns in timeline, scope, or budget management

2. **Contributing Factors**: What specific factors contributed to the {"success" if rank_type == "highest" else "poor performance"} of these projects?
   - Use evidence from the score explanations and project data
   - Distinguish between high-impact and moderate-impact factors
   - Consider both project structure and execution factors

3. **Key Differentiators**: What sets these projects apart from others?
   - What are they doing {"well" if rank_type == "highest" else "poorly"} that others might {"learn from" if rank_type == "highest" else "avoid"}?

4. **Recommendations**: Based on this analysis, what actionable recommendations can be made?
   - For {"replicating success" if rank_type == "highest" else "improving performance"} in other projects
   - Prioritize by potential impact

Respond with a JSON object in this exact format:
{{
    "score_summary": {{
        "average_score": <number>,
        "score_range": "<min> - <max>",
        "strongest_dimension": "<dimension with highest avg>",
        "weakest_dimension": "<dimension with lowest avg>"
    }},
    "common_patterns": [
        {{
            "pattern_name": "<short name>",
            "description": "<detailed description>",
            "frequency": "<X/Y projects>",
            "related_attributes": ["<attr1>", "<attr2>"]
        }}
    ],
    "contributing_factors": [
        {{
            "factor": "<factor name>",
            "description": "<explanation of how this factor contributes>",
            "evidence": ["<project title 1>", "<project title 2>"],
            "impact": "{"positive" if rank_type == "highest" else "negative"}",
            "confidence": "<high/medium/low>"
        }}
    ],
    "key_differentiators": [
        "<differentiator 1>",
        "<differentiator 2>"
    ],
    "recommendations": [
        {{
            "recommendation": "<actionable recommendation>",
            "rationale": "<why this will help>",
            "priority": "<high/medium/low>",
            "applicable_to": "<scope of applicability>"
        }}
    ],
    "analysis_confidence": "<high/medium/low based on data quality>",
    "reasoning": "<2-3 sentences explaining your overall analysis approach and key findings>"
}}"""

    return prompt


def analyze_project_scores(
    request: ScoreAnalysisRequest,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> ScoreAnalysisResult:
    """
    Analyze top or bottom performing projects to identify patterns and contributing factors.
    
    Args:
        request: Analysis parameters (tenant_id, rank_type, n, score_dimension)
        llm_client: Optional LLM client (creates one if not provided)
        graph_connector: Optional graph connector (creates one if not provided)
        
    Returns:
        ScoreAnalysisResult with patterns, factors, and recommendations
    """
    appLogger.info({
        "event": "analyze_project_scores_start",
        "tenant_id": request.tenant_id,
        "rank_type": request.rank_type,
        "n": request.n,
        "score_dimension": request.score_dimension
    })
    
    # Initialize connections if not provided
    if graph_connector is None:
        config = GraphConnectorConfig.from_env()
        graph_connector = GraphConnector(config)
    
    if llm_client is None:
        llm_client = ChatGPTClient()
    
    try:
        # Step 1: Get project scores from graph
        project_scores = get_project_scores_from_graph(
            graph_connector=graph_connector,
            tenant_id=request.tenant_id,
            rank_type=request.rank_type,
            n=request.n,
            score_dimension=request.score_dimension
        )
        
        if not project_scores:
            appLogger.warning({
                "event": "analyze_project_scores",
                "warning": "No project scores found for tenant",
                "tenant_id": request.tenant_id
            })
            return _empty_result(request)
        
        appLogger.info({
            "event": "analyze_project_scores",
            "step": "scores_retrieved",
            "count": len(project_scores)
        })
        
        # Step 2: Fetch detailed project data
        project_ids = [s["project_id"] for s in project_scores if s.get("project_id")]
        project_details = fetch_project_details(request.tenant_id, project_ids)
        
        appLogger.info({
            "event": "analyze_project_scores",
            "step": "details_fetched",
            "count": len(project_details)
        })
        
        # Step 3: Build and execute LLM analysis
        prompt = _build_analysis_prompt(
            rank_type=request.rank_type,
            projects_with_scores=project_scores,
            project_details=project_details
        )
        
        chat_completion = ChatCompletion(
            system="You are an expert project management analyst specializing in identifying success and failure patterns across project portfolios.",
            prev=[],
            user=prompt
        )
        
        response = llm_client.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.2),
            "score_analysis::analyze_projects"
        )
        
        # Parse LLM response
        analysis_data = extract_json_after_llm(response)
        
        if not analysis_data:
            appLogger.error({
                "event": "analyze_project_scores",
                "error": "Failed to parse LLM response"
            })
            return _empty_result(request)
        
        # Step 4: Build result
        result = ScoreAnalysisResult(
            analysis_type="top_performers" if request.rank_type == "highest" else "bottom_performers",
            tenant_id=request.tenant_id,
            projects_analyzed=[
                {
                    "project_id": s["project_id"],
                    "title": s["project_title"],
                    "score": s["core_score"]
                }
                for s in project_scores
            ],
            score_summary=analysis_data.get("score_summary", {}),
            common_patterns=[
                CommonPattern(
                    pattern_name=p.get("pattern_name", ""),
                    description=p.get("description", ""),
                    frequency=p.get("frequency", ""),
                    related_attributes=p.get("related_attributes", [])
                )
                for p in analysis_data.get("common_patterns", [])
            ],
            contributing_factors=[
                ContributingFactor(
                    factor=f.get("factor", ""),
                    description=f.get("description", ""),
                    evidence=f.get("evidence", []),
                    impact=f.get("impact", ""),
                    confidence=f.get("confidence", "medium")
                )
                for f in analysis_data.get("contributing_factors", [])
            ],
            key_differentiators=analysis_data.get("key_differentiators", []),
            recommendations=[
                Recommendation(
                    recommendation=r.get("recommendation", ""),
                    rationale=r.get("rationale", ""),
                    priority=r.get("priority", "medium"),
                    applicable_to=r.get("applicable_to", "all projects")
                )
                for r in analysis_data.get("recommendations", [])
            ],
            analysis_confidence=analysis_data.get("analysis_confidence", "medium"),
            llm_reasoning=analysis_data.get("reasoning", "")
        )
        
        appLogger.info({
            "event": "analyze_project_scores_complete",
            "tenant_id": request.tenant_id,
            "projects_analyzed": len(project_scores),
            "patterns_found": len(result.common_patterns),
            "factors_found": len(result.contributing_factors),
            "recommendations_count": len(result.recommendations)
        })
        
        return result
        
    except Exception as e:
        appLogger.error({
            "event": "analyze_project_scores_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return _empty_result(request)


def _empty_result(request: ScoreAnalysisRequest) -> ScoreAnalysisResult:
    """Return an empty result when analysis cannot be performed."""
    return ScoreAnalysisResult(
        analysis_type="top_performers" if request.rank_type == "highest" else "bottom_performers",
        tenant_id=request.tenant_id,
        projects_analyzed=[],
        score_summary={},
        common_patterns=[],
        contributing_factors=[],
        key_differentiators=[],
        recommendations=[],
        analysis_confidence="low",
        llm_reasoning="Insufficient data to perform analysis."
    )


def to_dict(result: ScoreAnalysisResult) -> Dict[str, Any]:
    """Convert ScoreAnalysisResult to a dictionary for JSON serialization."""
    return {
        "analysis_type": result.analysis_type,
        "tenant_id": result.tenant_id,
        "projects_analyzed": result.projects_analyzed,
        "score_summary": result.score_summary,
        "common_patterns": [asdict(p) for p in result.common_patterns],
        "contributing_factors": [asdict(f) for f in result.contributing_factors],
        "key_differentiators": result.key_differentiators,
        "recommendations": [asdict(r) for r in result.recommendations],
        "analysis_confidence": result.analysis_confidence,
        "llm_reasoning": result.llm_reasoning
    }


# Convenience functions for common use cases
def analyze_top_performers(
    tenant_id: int,
    n: int = 5,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> ScoreAnalysisResult:
    """Analyze top n performing projects for a tenant."""
    return analyze_project_scores(
        ScoreAnalysisRequest(tenant_id=tenant_id, rank_type="highest", n=n),
        llm_client=llm_client,
        graph_connector=graph_connector
    )


def analyze_bottom_performers(
    tenant_id: int,
    n: int = 5,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> ScoreAnalysisResult:
    """Analyze bottom n performing projects for a tenant."""
    return analyze_project_scores(
        ScoreAnalysisRequest(tenant_id=tenant_id, rank_type="lowest", n=n),
        llm_client=llm_client,
        graph_connector=graph_connector
    )
