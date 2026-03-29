"""
Data models for project scoring system.
All input/output structures with strong typing.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProjectStatusEnum(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class SignalPattern(str, Enum):
    """Milestone patterns"""
    CONSISTENT = "CONSISTENT"
    MINOR_DRIFT = "MINOR_DRIFT"
    SLIPPING = "SLIPPING"
    CASCADE_FAILURE = "CASCADE_FAILURE"


class ComplicationPattern(str, Enum):
    """Status comment patterns"""
    FREQUENT_COMPLICATIONS = "FREQUENT_COMPLICATIONS"
    OCCASIONAL_CHALLENGES = "OCCASIONAL_CHALLENGES"
    WELL_MANAGED_ISSUES = "WELL_MANAGED_ISSUES"
    NO_CLEAR_PATTERN = "NO_CLEAR_PATTERN"


# ============================================================================
# INPUT STRUCTURES
# ============================================================================

@dataclass
class ProjectScoringRequest:
    """Simple input to the scoring engine"""
    project_id: int
    tenant_id: int


# ============================================================================
# PROJECT CONTEXT (Internal - passed to all calculators)
# ============================================================================

@dataclass
class ProjectContext:
    """
    All fetched data for a project.
    This object is passed to all calculator methods.
    
    NOTE: workflow_project table does NOT have:
    - planned_budget, actual_budget (spend tracked via milestones)
    - baseline_scope, current_scope (scope tracked via status field)
    """
    # Core project
    project_id: int
    project_title: str
    project_status: str  # "active", "completed", "archived"
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    planned_end_date: Optional[datetime]
    
    # Status tracking (always present)
    scope_status: int  # 1=on_track, 2=at_risk, 3=compromised
    delivery_status: int  # 1=on_track, 2=at_risk, 3=compromised
    spend_status: int  # 1=on_track, 2=at_risk, 3=compromised
    status_updates_count: int  # Total status updates
    
    # Milestones data (spend tracked here, not on project)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    # Each milestone: {
    #   "id": int,
    #   "type": int,  # 1=scope, 2=schedule, 3=spend
    #   "target_date": datetime,
    #   "actual_date": datetime | None,
    #   "milestone_name": str,
    #   "planned_spend": float,
    #   "actual_spend": float,
    #   "comments": str | None
    # }
    
    # Risks data
    risks: List[Dict[str, Any]] = field(default_factory=list)
    # Each risk: {
    #   "id": int,
    #   "description": str,
    #   "impact": str,  # "High", "Medium", "Low"
    #   "status": str,  # "Active", "Closed", "Mitigated", etc.
    #   "priority": int,
    #   "mitigation": str
    # }
    
    # Team data
    team_members: List[Dict[str, Any]] = field(default_factory=list)
    # Each member: {
    #   "name": str,
    #   "role": str,
    #   "utilization": int,  # 0-100
    #   "is_external": bool
    # }
    
    # Status updates for comment analysis
    status_comments: List[str] = field(default_factory=list)
    # Recent status update comments
    
    # Completed project data (optional)
    retro_data: Optional[Dict[str, Any]] = None
    # {
    #   "retrospective_summary": str,
    #   "things_to_keep_doing": str,
    #   "areas_for_improvement": str,
    # }
    
    value_realization_data: Optional[Dict[str, Any]] = None
    # {
    #   "kpis": [
    #     {
    #       "title": str,
    #       "baseline_value": float,
    #       "target_value": float,
    #       "actual_value": float
    #     }
    #   ]
    # }


# ============================================================================
# SCORE COMPONENT STRUCTURES
# ============================================================================

@dataclass
class DimensionScores:
    """Individual dimension scores (0-100)"""
    on_time: int
    on_scope: int
    on_budget: int
    risk_management: int
    team_health: int
    core_score: int  # Weighted average
    
    # Explanations for transparency
    on_time_explanation: str = ""
    on_scope_explanation: str = ""
    on_budget_explanation: str = ""
    risk_management_explanation: str = ""
    team_health_explanation: str = ""


@dataclass
class ConfidenceComponent:
    """Individual confidence component"""
    name: str
    value: int  # 0-100
    weight: float  # 0-1
    description: str


@dataclass
class ConfidenceBreakdown:
    """Data quality/completeness scores"""
    status_fields: int  # Usually 100
    milestones: int  # % of milestones with dates
    comments: int  # % of status updates with comments
    risks: int  # Presence of risk data
    team_data: int  # Team completeness
    retro_bonus: int  # +5 if completed project has retro
    overall: int  # Final confidence 0-100
    interpretation: str  # "High", "Good", "Moderate", "Low"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MilestoneSignal:
    """Milestone pattern analysis"""
    pattern: SignalPattern
    on_time_ratio: float  # 0-1
    avg_delay_days: int
    max_delay_days: int
    completed_count: int
    confidence_impact: int  # -5 to +3
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "on_time_ratio": self.on_time_ratio,
            "avg_delay_days": self.avg_delay_days,
            "max_delay_days": self.max_delay_days,
            "completed_count": self.completed_count,
            "confidence_impact": self.confidence_impact,
            "description": self.description
        }


@dataclass
class ComplicationSignal:
    """Status comment pattern analysis"""
    pattern: ComplicationPattern
    blocker_count: int
    resolution_rate: float  # 0-1 of blockers resolved
    total_complications: int
    confidence_impact: int  # -2 to +2
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "blocker_count": self.blocker_count,
            "resolution_rate": self.resolution_rate,
            "total_complications": self.total_complications,
            "confidence_impact": self.confidence_impact,
            "description": self.description
        }


@dataclass
class QualitySignals:
    """Quality signals that contextualize the core score"""
    milestone_health: Optional[MilestoneSignal] = None
    status_complications: Optional[ComplicationSignal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_health": self.milestone_health.to_dict() if self.milestone_health else None,
            "status_complications": self.status_complications.to_dict() if self.status_complications else None
        }


@dataclass
class MaturityScore:
    """Post-completion maturity assessment (Tier 3)"""
    retrospective_score: int  # 0-100
    value_realization_score: int  # 0-100
    overall_maturity: int  # 0-100 (60% retro, 40% value)
    label: str  # "Excellent", "Good", "Partial", "Limited"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# FINAL RESULT STRUCTURE
# ============================================================================

@dataclass
class ProjectScore:
    """
    Final scoring output for a project.
    This is what gets returned as JSON.
    """
    # Identifiers
    project_id: int
    project_title: str
    project_status: str  # "active", "completed", "archived"
    
    # TIER 1: Core Execution Score
    core_score: int  # 0-100 (main number)
    dimensions: DimensionScores
    
    # TIER 2: Quality Signals & Confidence
    confidence: ConfidenceBreakdown
    signals: QualitySignals
    
    # TIER 3: Maturity (only if completed)
    maturity: Optional[MaturityScore] = None
    
    # TIER 4: LLM-Generated Explanation
    llm_explanation: Optional[Dict[str, Any]] = None
    
    # Metadata
    calculated_at: datetime = field(default_factory=datetime.now)
    data_completeness_pct: int = 100  # How much data was available
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "project_id": self.project_id,
            "project_title": self.project_title,
            "project_status": self.project_status,
            "core_score": self.core_score,
            "dimensions": asdict(self.dimensions),
            "confidence": self.confidence.to_dict(),
            "signals": self.signals.to_dict(),
            "calculated_at": self.calculated_at.isoformat(),
            "data_completeness_pct": self.data_completeness_pct,
        }
        
        if self.llm_explanation:
            result["llm_explanation"] = self.llm_explanation
        
        if self.maturity:
            result["maturity"] = self.maturity.to_dict()
        
        return result
    
    def get_full_explanation(self) -> str:
        """Generate human-readable explanation of the score"""
        parts = [
            f"PROJECT SCORE BREAKDOWN: {self.core_score}/100",
            "",
            "DIMENSION SCORES:",
            f"• On-Time ({self.dimensions.on_time}/100): {self.dimensions.on_time_explanation}",
            f"• On-Scope ({self.dimensions.on_scope}/100): {self.dimensions.on_scope_explanation}",
            f"• On-Budget ({self.dimensions.on_budget}/100): {self.dimensions.on_budget_explanation}",
            f"• Risk Management ({self.dimensions.risk_management}/100): {self.dimensions.risk_management_explanation}",
            f"• Team Health ({self.dimensions.team_health}/100): {self.dimensions.team_health_explanation}",
        ]
        
        if self.maturity:
            parts.extend([
                "",
                f"MATURITY ASSESSMENT ({self.maturity.label}):",
                f"• Retrospective: {self.maturity.retrospective_score}/100",
                f"• Value Realization: {self.maturity.value_realization_score}/100",
            ])
        
        return "\n".join(parts)
