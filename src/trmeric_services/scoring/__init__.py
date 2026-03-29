"""
Scoring Service
Provides comprehensive evaluation (0-100) with confidence metrics.

Project scoring measures execution fidelity (on-time, on-scope, on-budget, etc.).
Roadmap scoring measures planning completeness / data quality.

Public API:
    from src.trmeric_services.scoring import ProjectScoringEngine, RoadmapScoringEngine

    # Projects
    engine = ProjectScoringEngine(projects_dao)
    score = engine.score_project(project_id=42, tenant_id=648)
    json_result = score.to_dict()

    # Roadmaps
    engine = RoadmapScoringEngine()
    score = engine.score_roadmap(roadmap_id=99, tenant_id=648)
    json_result = score.to_dict()
"""

from .engine import ProjectScoringEngine
from .models import (
    ProjectScore,
    ProjectContext,
    DimensionScores,
    ConfidenceBreakdown,
    QualitySignals,
    MaturityScore,
    MilestoneSignal,
    ComplicationSignal,
)
from .retrospective_analyzer import RetrospectiveAnalyzer

from .roadmap_engine import RoadmapScoringEngine
from .roadmap_models import (
    RoadmapScore,
    RoadmapContext,
    RoadmapDimensionScores,
    RoadmapConfidenceBreakdown,
    RoadmapQualitySignals,
    PlanningDepthPattern,
    FinancialRationalePattern,
)

__all__ = [
    # Project scoring
    "ProjectScoringEngine",
    "ProjectScore",
    "ProjectContext",
    "DimensionScores",
    "ConfidenceBreakdown",
    "QualitySignals",
    "MaturityScore",
    "MilestoneSignal",
    "ComplicationSignal",
    "RetrospectiveAnalyzer",
    # Roadmap scoring
    "RoadmapScoringEngine",
    "RoadmapScore",
    "RoadmapContext",
    "RoadmapDimensionScores",
    "RoadmapConfidenceBreakdown",
    "RoadmapQualitySignals",
    "PlanningDepthPattern",
    "FinancialRationalePattern",
]

