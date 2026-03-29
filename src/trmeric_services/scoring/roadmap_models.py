"""
Data models for roadmap data quality scoring system.
Parallel to models.py (project scoring) but measures planning completeness
rather than execution fidelity.

A roadmap has no milestones, risks, or status updates — it is a plan.
All scoring is based on how thoroughly the plan is defined.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# SIGNAL ENUMS
# ============================================================================

class PlanningDepthPattern(str, Enum):
    """How thoroughly the roadmap planning fields are filled."""
    COMPREHENSIVE = "COMPREHENSIVE"        # Presence score ≥80 across ≥4 of 5 dimensions
    SOLID_FOUNDATION = "SOLID_FOUNDATION"  # Presence score ≥60 in ≥3 dimensions
    PARTIAL_PLAN = "PARTIAL_PLAN"          # Presence score ≥40 in fewer than 3 dimensions
    SKELETON = "SKELETON"                  # Mostly empty; only basic fields present


class FinancialRationalePattern(str, Enum):
    """Whether financial justification has been thought through."""
    WELL_JUSTIFIED = "WELL_JUSTIFIED"              # budget + cost + cash_inflow + justification_text
    PARTIALLY_JUSTIFIED = "PARTIALLY_JUSTIFIED"    # Some financial data present
    BUDGET_ONLY = "BUDGET_ONLY"                    # Budget/cost set but no ROI case
    NO_FINANCIAL_DATA = "NO_FINANCIAL_DATA"        # Nothing set


# ============================================================================
# INPUT / CONTEXT
# ============================================================================

@dataclass
class RoadmapContext:
    """
    All fetched data for a roadmap.
    Populated from RoadmapDao.fetchRoadmapDataForBusinessPlan().

    Fields map directly to the columns returned by that query.
    """
    # Core project / identity
    roadmap_id: int
    tenant_id: int
    roadmap_title: str                    # rr.title
    roadmap_description: Optional[str]    # rr.description
    roadmap_objectives: Optional[str]     # rr.objectives
    roadmap_solution: Optional[str]       # rr.solution
    roadmap_category: Optional[str]       # rr.category
    roadmap_org_strategy_alignment: Optional[str]  # rr.org_strategy_align
    roadmap_type: Optional[str]           # rr.type (decoded to string e.g. "Program")
    roadmap_state: Optional[str]          # rr.current_state (decoded to string e.g. "Intake")
    roadmap_priority: Optional[str]       # rr.priority (decoded to "High"/"Medium"/"Low")

    # Timeline
    roadmap_start_date: Optional[Any]     # rr.start_date
    roadmap_end_date: Optional[Any]       # rr.end_date

    # Financial
    roadmap_budget: Optional[float]       # rr.budget
    roadmap_total_capital_cost: Optional[float]  # rr.total_capital_cost

    # Related collections (parsed from JSON_AGGs by the engine)
    roadmap_constraints: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"constraint_title": str, "constraint_type": str}

    roadmap_portfolios: List[str] = field(default_factory=list)
    # List of portfolio title strings

    roadmap_key_results: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"key_result_title": str, "baseline_value": str|float|None}

    roadmap_scope: List[str] = field(default_factory=list)
    # List of scope item name strings

    team_data: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"team_name": str, "team_unit_size": int, "labour_type": str,
    #        "labour_estimate_value": str, "team_efforts": str}

    # Cash inflows split by type (from fetchRoadmapDataForBusinessPlan)
    savings_cash_inflows: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"cash_inflow": float, "time_period": int, "category": str, "justification_text": str}

    revenue_cash_inflows: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"cash_inflow": float, "time_period": int, "category": str, "justification_text": str}


# ============================================================================
# SCORE COMPONENTS
# ============================================================================

@dataclass
class RoadmapDimensionScores:
    """
    Per-dimension scores (0-100) for the roadmap.

    Each dimension has:
    - A presence_score: purely rule-based (fields present/populated)
    - A final blended score: (presence * rule_weight) + (llm_quality * llm_weight)
    - An explanation: authoritative text from the LLM call
    """
    # Final blended scores
    strategic_clarity: int
    okr_quality: int
    scope_and_constraints: int
    resource_financial_planning: int
    solution_readiness: int
    core_score: int  # Weighted aggregate

    # Per-dimension presence scores (rule-based, before LLM blend)
    strategic_clarity_presence: int = 0
    okr_quality_presence: int = 0
    scope_and_constraints_presence: int = 0
    resource_financial_presence: int = 0
    solution_readiness_presence: int = 0

    # LLM quality subscores (0-100, from single LLM call)
    strategic_clarity_quality: int = 0
    okr_quality_score: int = 0
    scope_quality: int = 0
    financial_quality: int = 0
    solution_quality: int = 0

    # Explanations (from LLM)
    strategic_clarity_explanation: str = ""
    okr_quality_explanation: str = ""
    scope_and_constraints_explanation: str = ""
    resource_financial_explanation: str = ""
    solution_readiness_explanation: str = ""


@dataclass
class RoadmapConfidenceBreakdown:
    """
    How much to trust the score — reflects data completeness.

    Floor is 30 (not 55 like projects) since early-stage roadmaps
    are legitimately incomplete.
    """
    core_fields: int        # title/description/objectives/category/type fill rate
    okr_completeness: int   # KPI count + baseline_value fill rate
    scope_coverage: int     # scope items + constraints present
    financial_data: int     # budget + team + cash_inflow presence
    alignment_signal: int   # org_strategy_align + portfolio assigned
    overall: int            # Final 0-100
    interpretation: str     # "High" / "Good" / "Moderate" / "Early-stage"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoadmapPlanningSignal:
    """Planning depth signal derived from presence checks."""
    pattern: PlanningDepthPattern
    dimensions_above_threshold: int  # How many of 5 dimensions have presence ≥ 60
    description: str
    confidence_impact: int  # -5 to +5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "dimensions_above_threshold": self.dimensions_above_threshold,
            "description": self.description,
            "confidence_impact": self.confidence_impact
        }


@dataclass
class RoadmapFinancialSignal:
    """Financial rationale signal derived from presence checks."""
    pattern: FinancialRationalePattern
    has_budget: bool
    has_cost_estimate: bool
    has_cash_inflows: bool
    has_justification: bool
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "has_budget": self.has_budget,
            "has_cost_estimate": self.has_cost_estimate,
            "has_cash_inflows": self.has_cash_inflows,
            "has_justification": self.has_justification,
            "description": self.description
        }


@dataclass
class RoadmapQualitySignals:
    """Container for both signal types."""
    planning_depth: Optional[RoadmapPlanningSignal] = None
    financial_rationale: Optional[RoadmapFinancialSignal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "planning_depth": self.planning_depth.to_dict() if self.planning_depth else None,
            "financial_rationale": self.financial_rationale.to_dict() if self.financial_rationale else None
        }


# ============================================================================
# FINAL RESULT
# ============================================================================

@dataclass
class RoadmapScore:
    """
    Final scoring output for a roadmap.
    Parallel to ProjectScore in models.py.
    """
    # Identifiers
    roadmap_id: int
    roadmap_title: str
    roadmap_state: str   # "Intake", "Draft", "Approved", etc.

    # Core score
    core_score: int  # 0-100
    dimensions: RoadmapDimensionScores

    # Data quality & confidence
    confidence: RoadmapConfidenceBreakdown
    signals: RoadmapQualitySignals

    # LLM-generated explanation (from the single combined call)
    llm_explanation: Optional[Dict[str, Any]] = None
    # Keys: explanation, key_strengths, key_gaps, data_quality_note

    # Metadata
    roadmap_type: Optional[str] = None  # "Project", "Program", "Enhancement", etc.
    calculated_at: datetime = field(default_factory=datetime.now)
    data_completeness_pct: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "roadmap_id": self.roadmap_id,
            "roadmap_title": self.roadmap_title,
            "roadmap_state": self.roadmap_state,
            "roadmap_type": self.roadmap_type,
            "core_score": self.core_score,
            "dimensions": {
                # Final blended scores
                "strategic_clarity": self.dimensions.strategic_clarity,
                "okr_quality": self.dimensions.okr_quality,
                "scope_and_constraints": self.dimensions.scope_and_constraints,
                "resource_financial_planning": self.dimensions.resource_financial_planning,
                "solution_readiness": self.dimensions.solution_readiness,
                "core_score": self.dimensions.core_score,
                # Presence subscores
                "strategic_clarity_presence": self.dimensions.strategic_clarity_presence,
                "okr_quality_presence": self.dimensions.okr_quality_presence,
                "scope_and_constraints_presence": self.dimensions.scope_and_constraints_presence,
                "resource_financial_presence": self.dimensions.resource_financial_presence,
                "solution_readiness_presence": self.dimensions.solution_readiness_presence,
                # LLM quality subscores
                "strategic_clarity_quality": self.dimensions.strategic_clarity_quality,
                "okr_quality_score": self.dimensions.okr_quality_score,
                "scope_quality": self.dimensions.scope_quality,
                "financial_quality": self.dimensions.financial_quality,
                "solution_quality": self.dimensions.solution_quality,
                # Explanations
                "strategic_clarity_explanation": self.dimensions.strategic_clarity_explanation,
                "okr_quality_explanation": self.dimensions.okr_quality_explanation,
                "scope_and_constraints_explanation": self.dimensions.scope_and_constraints_explanation,
                "resource_financial_explanation": self.dimensions.resource_financial_explanation,
                "solution_readiness_explanation": self.dimensions.solution_readiness_explanation,
            },
            "confidence": self.confidence.to_dict(),
            "signals": self.signals.to_dict(),
            "llm_explanation": self.llm_explanation,
            "calculated_at": self.calculated_at.isoformat(),
            "data_completeness_pct": self.data_completeness_pct,
        }

    def get_full_explanation(self) -> str:
        parts = [
            f"ROADMAP SCORE BREAKDOWN: {self.core_score}/100",
            "",
            "DIMENSION SCORES:",
            f"• Strategic Clarity ({self.dimensions.strategic_clarity}/100): {self.dimensions.strategic_clarity_explanation}",
            f"• OKR Quality ({self.dimensions.okr_quality}/100): {self.dimensions.okr_quality_explanation}",
            f"• Scope & Constraints ({self.dimensions.scope_and_constraints}/100): {self.dimensions.scope_and_constraints_explanation}",
            f"• Resource & Financial Planning ({self.dimensions.resource_financial_planning}/100): {self.dimensions.resource_financial_explanation}",
            f"• Solution Readiness ({self.dimensions.solution_readiness}/100): {self.dimensions.solution_readiness_explanation}",
        ]
        return "\n".join(parts)
