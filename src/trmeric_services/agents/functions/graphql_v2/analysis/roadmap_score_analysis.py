"""
Roadmap Score Analysis Engine

Analyzes top/bottom performing roadmaps based on data-quality scoring.
Parallel to score_analysis.py but for roadmap planning completeness.

Takes n highest or lowest scoring roadmaps and uses LLM to identify:
- Common patterns in planning thoroughness
- Contributing factors to good or poor plan quality
- Recommendations for improving roadmap data completeness

Works within a single tenant scope using RoadmapScore vertices in TigerGraph.
"""

from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, asdict
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient, ModelOptions
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import RoadmapDao
from ..infrastructure import GraphConnector, GraphConnectorConfig
import json
import traceback


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class RoadmapScoreAnalysisRequest:
    """Request parameters for roadmap score analysis."""
    tenant_id: int
    rank_type: Literal["highest", "lowest"]
    n: int = 5
    score_dimension: Optional[str] = None  # e.g. "strategic_clarity", "okr_quality", etc.


@dataclass
class PlanningPattern:
    """A pattern found across analyzed roadmaps."""
    pattern_name: str
    description: str
    frequency: str  # e.g. "4/5 roadmaps"
    related_dimensions: List[str]


@dataclass
class PlanningFactor:
    """A factor that contributed to roadmap quality."""
    factor: str
    description: str
    evidence: List[str]  # Roadmap titles exhibiting this factor
    impact: str  # "positive" or "negative"
    confidence: str  # "high", "medium", "low"


@dataclass
class PlanningRecommendation:
    """Actionable recommendation for improving roadmap quality."""
    recommendation: str
    rationale: str
    priority: str  # "high", "medium", "low"
    applicable_to: str  # "all roadmaps", "similar scope", etc.


@dataclass
class RoadmapScoreAnalysisResult:
    """Result of roadmap score analysis."""
    analysis_type: str  # "best_planned" or "least_planned"
    tenant_id: int
    roadmaps_analyzed: List[Dict[str, Any]]
    score_summary: Dict[str, Any]
    planning_patterns: List[PlanningPattern]
    contributing_factors: List[PlanningFactor]
    key_differentiators: List[str]
    recommendations: List[PlanningRecommendation]
    analysis_confidence: str
    llm_reasoning: str


# ============================================================================
# GRAPH RETRIEVAL
# ============================================================================

def get_roadmap_scores_from_graph(
    graph_connector: GraphConnector,
    tenant_id: int,
    rank_type: Literal["highest", "lowest"],
    n: int,
    score_dimension: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve roadmap scores from TigerGraph, ranked by score.

    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: Tenant ID to filter scores
        rank_type: "highest" or "lowest"
        n: Number of roadmaps to retrieve
        score_dimension: Optional dimension to rank by (e.g. "strategic_clarity")

    Returns:
        List of roadmap score data ordered by score
    """
    try:
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_roadmap_scores_from_graph",
                "error": "Failed to connect to graph"
            })
            return []

        all_scores = graph_connector._connection.getVertices("RoadmapScore", limit=100)

        if not all_scores:
            return []

        tenant_scores = []
        for score_vertex in all_scores:
            if isinstance(score_vertex, dict):
                attrs = score_vertex.get("attributes", {})
                vertex_tenant_id = attrs.get("tenant_id")
                if str(vertex_tenant_id) == str(tenant_id):
                    if score_dimension:
                        rank_score = attrs.get(f"{score_dimension}_score", attrs.get("core_score", 0))
                    else:
                        rank_score = attrs.get("core_score", 0)

                    tenant_scores.append({
                        "score_id": score_vertex.get("v_id", ""),
                        "roadmap_id": attrs.get("roadmap_id"),
                        "roadmap_title": attrs.get("roadmap_title", ""),
                        "roadmap_state": attrs.get("roadmap_state", ""),
                        "core_score": attrs.get("core_score", 0),
                        # Dimension scores
                        "strategic_clarity_score": attrs.get("strategic_clarity_score", 0),
                        "okr_quality_score": attrs.get("okr_quality_score", 0),
                        "scope_and_constraints_score": attrs.get("scope_and_constraints_score", 0),
                        "resource_financial_score": attrs.get("resource_financial_score", 0),
                        "solution_readiness_score": attrs.get("solution_readiness_score", 0),
                        # Dimension explanations
                        "strategic_clarity_explanation": attrs.get("strategic_clarity_explanation", ""),
                        "okr_quality_explanation": attrs.get("okr_quality_explanation", ""),
                        "scope_and_constraints_explanation": attrs.get("scope_and_constraints_explanation", ""),
                        "resource_financial_explanation": attrs.get("resource_financial_explanation", ""),
                        "solution_readiness_explanation": attrs.get("solution_readiness_explanation", ""),
                        "llm_explanation": attrs.get("llm_explanation", ""),
                        # Confidence
                        "confidence_overall": attrs.get("confidence_overall", 0),
                        "confidence_interpretation": attrs.get("confidence_interpretation", ""),
                        # Signals
                        "planning_depth_pattern": attrs.get("planning_depth_pattern", ""),
                        "planning_depth_description": attrs.get("planning_depth_description", ""),
                        "financial_rationale_pattern": attrs.get("financial_rationale_pattern", ""),
                        "financial_rationale_description": attrs.get("financial_rationale_description", ""),
                        "rank_score": rank_score
                    })

        if rank_type == "highest":
            tenant_scores.sort(key=lambda x: x["rank_score"], reverse=True)
        else:
            tenant_scores.sort(key=lambda x: x["rank_score"])

        return tenant_scores[:n]

    except Exception as e:
        appLogger.error({
            "event": "get_roadmap_scores_from_graph",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


# ============================================================================
# ROADMAP DETAIL FETCHING
# ============================================================================

def fetch_roadmap_details(roadmap_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch detailed roadmap data for analysis.

    Args:
        roadmap_ids: List of roadmap IDs to fetch

    Returns:
        List of roadmap detail dictionaries
    """
    if not roadmap_ids:
        return []

    enriched_roadmaps = []
    for roadmap_id in roadmap_ids:
        try:
            data = RoadmapDao.fetchRoadmapDataForBusinessPlan(roadmap_id)
            if data:
                enriched_roadmaps.append({
                    "roadmap_id": roadmap_id,
                    "title": data.get("title", ""),
                    "description": (data.get("description") or "")[:500],
                    "objectives": (data.get("objectives") or "")[:500],
                    "solution": (data.get("solution") or "")[:500],
                    "category": data.get("category", ""),
                    "org_strategy_alignment": data.get("org_strategy_align", ""),
                    "type": data.get("type", ""),
                    "budget": data.get("budget"),
                    "total_capital_cost": data.get("total_capital_cost"),
                    "start_date": str(data.get("start_date", "")) if data.get("start_date") else None,
                    "end_date": str(data.get("end_date", "")) if data.get("end_date") else None,
                    "kpis": data.get("kpis", []),
                    "constraints": data.get("constraints", []),
                    "scopes": data.get("scopes", []),
                    "cash_inflows": data.get("annual_cash_inflows", []),
                    "portfolios": data.get("portfolios", []),
                    "teams": data.get("teams", []),
                })
        except Exception as e:
            appLogger.error({
                "event": "fetch_roadmap_details",
                "roadmap_id": roadmap_id,
                "error": str(e)
            })

    return enriched_roadmaps


# ============================================================================
# LLM PROMPT
# ============================================================================

def _build_roadmap_analysis_prompt(
    rank_type: Literal["highest", "lowest"],
    roadmaps_with_scores: List[Dict[str, Any]],
    roadmap_details: List[Dict[str, Any]]
) -> str:
    """Build the LLM prompt for roadmap score analysis."""

    quality_label = "best-planned" if rank_type == "highest" else "least-complete"
    analysis_focus = "planning strengths" if rank_type == "highest" else "planning gaps"

    roadmaps_data = []
    details_by_id = {r["roadmap_id"]: r for r in roadmap_details}

    for score in roadmaps_with_scores:
        rid = score["roadmap_id"]
        detail = details_by_id.get(rid, {})

        roadmaps_data.append({
            "roadmap_id": rid,
            "title": score.get("roadmap_title", detail.get("title", "Unknown")),
            "scores": {
                "overall": score.get("core_score", 0),
                "strategic_clarity": score.get("strategic_clarity_score", 0),
                "okr_quality": score.get("okr_quality_score", 0),
                "scope_and_constraints": score.get("scope_and_constraints_score", 0),
                "resource_financial": score.get("resource_financial_score", 0),
                "solution_readiness": score.get("solution_readiness_score", 0),
            },
            "score_explanations": {
                "strategic_clarity": score.get("strategic_clarity_explanation", ""),
                "okr_quality": score.get("okr_quality_explanation", ""),
                "scope_and_constraints": score.get("scope_and_constraints_explanation", ""),
                "resource_financial": score.get("resource_financial_explanation", ""),
                "solution_readiness": score.get("solution_readiness_explanation", ""),
                "overall_analysis": score.get("llm_explanation", ""),
            },
            "confidence": {
                "overall": score.get("confidence_overall", 0),
                "interpretation": score.get("confidence_interpretation", ""),
            },
            "signals": {
                "planning_depth": score.get("planning_depth_pattern", ""),
                "planning_depth_description": score.get("planning_depth_description", ""),
                "financial_rationale": score.get("financial_rationale_pattern", ""),
                "financial_rationale_description": score.get("financial_rationale_description", ""),
            },
            "roadmap_attributes": {
                "description": detail.get("description", ""),
                "objectives": detail.get("objectives", ""),
                "solution": detail.get("solution", ""),
                "category": detail.get("category", ""),
                "org_strategy_alignment": detail.get("org_strategy_alignment", ""),
                "type": detail.get("type", ""),
                "budget": detail.get("budget"),
                "total_capital_cost": detail.get("total_capital_cost"),
                "start_date": detail.get("start_date"),
                "end_date": detail.get("end_date"),
            },
            "kpi_count": len(detail.get("kpis", [])),
            "constraint_count": len(detail.get("constraints", [])),
            "scope_count": len(detail.get("scopes", [])),
            "has_cash_inflows": len(detail.get("cash_inflows", [])) > 0,
            "portfolio_count": len(detail.get("portfolios", [])),
            "team_count": len(detail.get("teams", [])),
        })

    roadmaps_json = json.dumps(roadmaps_data, indent=2, default=str)

    return f"""You are an expert portfolio management analyst specializing in roadmap planning quality assessment.
Analyze these {len(roadmaps_with_scores)} {quality_label} roadmaps to identify {analysis_focus}.

Note: These are PLANNING QUALITY scores, not execution metrics. They measure how completely and
thoroughly the roadmap plan has been defined (data quality), not project delivery performance.

═══════════════════════════════════════════════════════════════════
ROADMAP DATA FOR ANALYSIS
═══════════════════════════════════════════════════════════════════

{roadmaps_json}

═══════════════════════════════════════════════════════════════════
ANALYSIS TASK
═══════════════════════════════════════════════════════════════════

Analyze these {quality_label} roadmaps (ranked by overall data quality score) and identify:

1. **Common Planning Patterns**: What planning approaches or documentation patterns appear across multiple roadmaps?
   - Levels of detail in strategic objectives, KPIs, scope, constraints
   - Financial justification thoroughness (budget, ROI, cash inflows)
   - Quality of solution descriptions and alignment with strategy

2. **Contributing Factors**: What factors contributed to {"thorough planning" if rank_type == "highest" else "incomplete planning"}?
   - Which dimensions are consistently {"strong" if rank_type == "highest" else "weak"}?
   - What data fields drive the scores up or down?

3. **Key Differentiators**: What planning practices set these roadmaps apart?

4. **Recommendations**: What should roadmap authors do to {"maintain" if rank_type == "highest" else "improve"} planning quality?

Respond in JSON:
{{
    "score_summary": {{
        "average_score": <number>,
        "score_range": "<min> - <max>",
        "strongest_dimension": "<dimension>",
        "weakest_dimension": "<dimension>"
    }},
    "planning_patterns": [
        {{
            "pattern_name": "<short name>",
            "description": "<detailed description>",
            "frequency": "<X/Y roadmaps>",
            "related_dimensions": ["<dim1>", "<dim2>"]
        }}
    ],
    "contributing_factors": [
        {{
            "factor": "<factor name>",
            "description": "<how this factor contributes>",
            "evidence": ["<roadmap title 1>", "<roadmap title 2>"],
            "impact": "{"positive" if rank_type == "highest" else "negative"}",
            "confidence": "<high/medium/low>"
        }}
    ],
    "key_differentiators": ["<differentiator 1>", "<differentiator 2>"],
    "recommendations": [
        {{
            "recommendation": "<actionable recommendation>",
            "rationale": "<why this helps>",
            "priority": "<high/medium/low>",
            "applicable_to": "<scope>"
        }}
    ],
    "analysis_confidence": "<high/medium/low>",
    "reasoning": "<2-3 sentences on approach and key findings>"
}}"""


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_roadmap_scores(
    request: RoadmapScoreAnalysisRequest,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> RoadmapScoreAnalysisResult:
    """
    Analyze top or bottom roadmaps by planning quality to identify patterns.

    Args:
        request: Analysis parameters
        llm_client: Optional LLM client
        graph_connector: Optional graph connector

    Returns:
        RoadmapScoreAnalysisResult with patterns, factors, and recommendations
    """
    appLogger.info({
        "event": "analyze_roadmap_scores_start",
        "tenant_id": request.tenant_id,
        "rank_type": request.rank_type,
        "n": request.n,
        "score_dimension": request.score_dimension
    })

    if graph_connector is None:
        config = GraphConnectorConfig.from_env()
        graph_connector = GraphConnector(config)

    if llm_client is None:
        llm_client = ChatGPTClient()

    try:
        # Step 1: Get roadmap scores from graph
        roadmap_scores = get_roadmap_scores_from_graph(
            graph_connector=graph_connector,
            tenant_id=request.tenant_id,
            rank_type=request.rank_type,
            n=request.n,
            score_dimension=request.score_dimension
        )

        if not roadmap_scores:
            appLogger.warning({
                "event": "analyze_roadmap_scores",
                "warning": "No roadmap scores found for tenant",
                "tenant_id": request.tenant_id
            })
            return _empty_roadmap_result(request)

        # Step 2: Fetch detailed roadmap data
        roadmap_ids = [s["roadmap_id"] for s in roadmap_scores if s.get("roadmap_id")]
        roadmap_details = fetch_roadmap_details(roadmap_ids)

        # Step 3: Build and execute LLM analysis
        prompt = _build_roadmap_analysis_prompt(
            rank_type=request.rank_type,
            roadmaps_with_scores=roadmap_scores,
            roadmap_details=roadmap_details
        )

        chat_completion = ChatCompletion(
            system="You are an expert portfolio management analyst specializing in roadmap planning quality assessment and data completeness evaluation.",
            prev=[],
            user=prompt
        )

        response = llm_client.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.2),
            "roadmap_score_analysis::analyze_roadmaps"
        )

        analysis_data = extract_json_after_llm(response)

        if not analysis_data:
            appLogger.error({
                "event": "analyze_roadmap_scores",
                "error": "Failed to parse LLM response"
            })
            return _empty_roadmap_result(request)

        # Step 4: Build result
        result = RoadmapScoreAnalysisResult(
            analysis_type="best_planned" if request.rank_type == "highest" else "least_planned",
            tenant_id=request.tenant_id,
            roadmaps_analyzed=[
                {
                    "roadmap_id": s["roadmap_id"],
                    "title": s["roadmap_title"],
                    "score": s["core_score"]
                }
                for s in roadmap_scores
            ],
            score_summary=analysis_data.get("score_summary", {}),
            planning_patterns=[
                PlanningPattern(
                    pattern_name=p.get("pattern_name", ""),
                    description=p.get("description", ""),
                    frequency=p.get("frequency", ""),
                    related_dimensions=p.get("related_dimensions", [])
                )
                for p in analysis_data.get("planning_patterns", [])
            ],
            contributing_factors=[
                PlanningFactor(
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
                PlanningRecommendation(
                    recommendation=r.get("recommendation", ""),
                    rationale=r.get("rationale", ""),
                    priority=r.get("priority", "medium"),
                    applicable_to=r.get("applicable_to", "all roadmaps")
                )
                for r in analysis_data.get("recommendations", [])
            ],
            analysis_confidence=analysis_data.get("analysis_confidence", "medium"),
            llm_reasoning=analysis_data.get("reasoning", "")
        )

        appLogger.info({
            "event": "analyze_roadmap_scores_complete",
            "tenant_id": request.tenant_id,
            "roadmaps_analyzed": len(roadmap_scores),
            "patterns_found": len(result.planning_patterns),
            "factors_found": len(result.contributing_factors),
            "recommendations_count": len(result.recommendations)
        })

        return result

    except Exception as e:
        appLogger.error({
            "event": "analyze_roadmap_scores_error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return _empty_roadmap_result(request)


# ============================================================================
# HELPERS
# ============================================================================

def _empty_roadmap_result(request: RoadmapScoreAnalysisRequest) -> RoadmapScoreAnalysisResult:
    """Return an empty result when analysis cannot be performed."""
    return RoadmapScoreAnalysisResult(
        analysis_type="best_planned" if request.rank_type == "highest" else "least_planned",
        tenant_id=request.tenant_id,
        roadmaps_analyzed=[],
        score_summary={},
        planning_patterns=[],
        contributing_factors=[],
        key_differentiators=[],
        recommendations=[],
        analysis_confidence="low",
        llm_reasoning="Insufficient data to perform analysis."
    )


def to_dict(result: RoadmapScoreAnalysisResult) -> Dict[str, Any]:
    """Convert RoadmapScoreAnalysisResult to a dictionary for JSON serialization."""
    return {
        "analysis_type": result.analysis_type,
        "tenant_id": result.tenant_id,
        "roadmaps_analyzed": result.roadmaps_analyzed,
        "score_summary": result.score_summary,
        "planning_patterns": [asdict(p) for p in result.planning_patterns],
        "contributing_factors": [asdict(f) for f in result.contributing_factors],
        "key_differentiators": result.key_differentiators,
        "recommendations": [asdict(r) for r in result.recommendations],
        "analysis_confidence": result.analysis_confidence,
        "llm_reasoning": result.llm_reasoning
    }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def analyze_best_planned(
    tenant_id: int,
    n: int = 5,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> RoadmapScoreAnalysisResult:
    """Analyze top n best-planned roadmaps for a tenant."""
    return analyze_roadmap_scores(
        RoadmapScoreAnalysisRequest(tenant_id=tenant_id, rank_type="highest", n=n),
        llm_client=llm_client,
        graph_connector=graph_connector
    )


def analyze_least_planned(
    tenant_id: int,
    n: int = 5,
    llm_client: Optional[ChatGPTClient] = None,
    graph_connector: Optional[GraphConnector] = None
) -> RoadmapScoreAnalysisResult:
    """Analyze bottom n least-complete roadmaps for a tenant."""
    return analyze_roadmap_scores(
        RoadmapScoreAnalysisRequest(tenant_id=tenant_id, rank_type="lowest", n=n),
        llm_client=llm_client,
        graph_connector=graph_connector
    )
