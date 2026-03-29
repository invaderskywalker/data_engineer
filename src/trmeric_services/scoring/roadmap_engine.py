"""
Roadmap Scoring Engine — orchestrates all calculations.
Parallel to engine.py (project scoring).

Entry point:
    engine = RoadmapScoringEngine()
    score = engine.score_roadmap(roadmap_id=42, tenant_id=648)
    json_result = score.to_dict()
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import traceback

from src.trmeric_database.dao.roadmap import RoadmapDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_utils.constants.base import roadmap_state_mapping, roadmap_type_mapping

from .roadmap_models import (
    RoadmapContext,
    RoadmapDimensionScores,
    RoadmapScore,
)
from .roadmap_calculations import RoadmapDimensionCalculations
from .roadmap_confidence import RoadmapConfidenceCalculation
from .roadmap_signals import RoadmapSignalAnalysis
from .roadmap_explanation_generator import RoadmapScoringExplanationGenerator


class RoadmapScoringEngine:
    """
    Main roadmap scoring engine.
    Fetches roadmap data, computes presence scores, calls LLM once,
    blends scores, and returns a complete RoadmapScore.
    """

    def __init__(self):
        self.explanation_gen = RoadmapScoringExplanationGenerator()

    def score_roadmap(self, roadmap_id: int, tenant_id: int) -> RoadmapScore:
        """
        Score a single roadmap.

        Args:
            roadmap_id: ID of the roadmap to score
            tenant_id: Tenant context

        Returns:
            RoadmapScore with all dimension scores, confidence, signals, and explanation

        Raises:
            ValueError: If the roadmap cannot be found
        """
        appLogger.info({
            "event": "roadmap_scoring_start",
            "roadmap_id": roadmap_id,
            "tenant_id": tenant_id,
        })

        # 1. Fetch all roadmap data via the business plan DAO method
        #    (the only existing single-call that includes cash inflows + total_capital_cost)
        context = self._fetch_roadmap_context(roadmap_id, tenant_id)

        # 2. Compute presence scores (pure Python, no I/O)
        strategic_presence, _ = RoadmapDimensionCalculations.calculate_strategic_clarity(context)
        okr_presence, _ = RoadmapDimensionCalculations.calculate_okr_quality(context)
        scope_presence, _ = RoadmapDimensionCalculations.calculate_scope_and_constraints(context)
        resource_presence, _ = RoadmapDimensionCalculations.calculate_resource_financial_planning(context)
        solution_presence, _ = RoadmapDimensionCalculations.calculate_solution_readiness(context)

        presence_scores = {
            "strategic": strategic_presence,
            "okr": okr_presence,
            "scope": scope_presence,
            "resource": resource_presence,
            "solution": solution_presence,
        }

        appLogger.info({
            "event": "roadmap_scoring_presence_done",
            "roadmap_id": roadmap_id,
            "presence_scores": presence_scores,
        })

        # 3. Signals (pure Python — uses presence scores)
        signals = RoadmapSignalAnalysis.analyze(context, presence_scores)

        # 4. Confidence (pure Python — folds signal impacts into overall)
        signal_impact = 0
        if signals.planning_depth:
            signal_impact += signals.planning_depth.confidence_impact
        confidence = RoadmapConfidenceCalculation.calculate(context, signal_impact=signal_impact)

        # 5. Single LLM call — quality subscores + explanation
        llm_result = self.explanation_gen.evaluate_and_explain(context)

        appLogger.info({
            "event": "roadmap_scoring_llm_done",
            "roadmap_id": roadmap_id,
            "llm_quality_scores": {
                "strategic_clarity_quality": llm_result.get("strategic_clarity_quality", 0),
                "okr_quality": llm_result.get("okr_quality", 0),
                "scope_quality": llm_result.get("scope_quality", 0),
                "financial_quality": llm_result.get("financial_quality", 0),
                "solution_quality": llm_result.get("solution_quality", 0),
            },
        })

        # 6. Blend presence scores with LLM quality subscores
        #    Rule weight = how much to trust the binary presence check
        #    LLM weight  = how much to trust the LLM's qualitative assessment
        strategic_final = self._blend(
            presence=strategic_presence,
            llm_quality=llm_result.get("strategic_clarity_quality", 0),
            rule_weight=0.50,  # presence is reliable (clear fields)
        )
        okr_final = self._blend(
            presence=okr_presence,
            llm_quality=llm_result.get("okr_quality", 0),
            rule_weight=0.40,  # LLM better at judging KPI quality
        )
        scope_final = self._blend(
            presence=scope_presence,
            llm_quality=llm_result.get("scope_quality", 0),
            rule_weight=0.45,  # balanced — scope items binary but quality matters
        )
        resource_final = self._blend(
            presence=resource_presence,
            llm_quality=llm_result.get("financial_quality", 0),
            rule_weight=0.55,  # financial data is binary, presence reliable
        )
        solution_final = self._blend(
            presence=solution_presence,
            llm_quality=llm_result.get("solution_quality", 0),
            rule_weight=0.30,  # presence unreliable without text, lean on LLM
        )

        core_score = RoadmapDimensionCalculations.aggregate_core_score(
            strategic_clarity=strategic_final,
            okr_quality=okr_final,
            scope_and_constraints=scope_final,
            resource_financial=resource_final,
            solution_readiness=solution_final,
            roadmap_state=context.roadmap_state,
        )

        # 7. Extract dimension explanations from LLM result
        dim_explanations = llm_result.get("dimension_explanations", {})

        dimensions = RoadmapDimensionScores(
            # Final blended scores
            strategic_clarity=strategic_final,
            okr_quality=okr_final,
            scope_and_constraints=scope_final,
            resource_financial_planning=resource_final,
            solution_readiness=solution_final,
            core_score=core_score,
            # Presence subscores
            strategic_clarity_presence=strategic_presence,
            okr_quality_presence=okr_presence,
            scope_and_constraints_presence=scope_presence,
            resource_financial_presence=resource_presence,
            solution_readiness_presence=solution_presence,
            # LLM quality subscores
            strategic_clarity_quality=llm_result.get("strategic_clarity_quality", 0),
            okr_quality_score=llm_result.get("okr_quality", 0),
            scope_quality=llm_result.get("scope_quality", 0),
            financial_quality=llm_result.get("financial_quality", 0),
            solution_quality=llm_result.get("solution_quality", 0),
            # Explanations
            strategic_clarity_explanation=dim_explanations.get("strategic_clarity", ""),
            okr_quality_explanation=dim_explanations.get("okr_quality", ""),
            scope_and_constraints_explanation=dim_explanations.get("scope_and_constraints", ""),
            resource_financial_explanation=dim_explanations.get("resource_financial_planning", ""),
            solution_readiness_explanation=dim_explanations.get("solution_readiness", ""),
        )

        # 8. Build LLM explanation payload (same structure as ProjectScore.llm_explanation)
        llm_explanation = {
            "explanation": llm_result.get("explanation", ""),
            "key_strengths": llm_result.get("key_strengths", []),
            "key_gaps": llm_result.get("key_gaps", []),
            "data_quality_note": llm_result.get("data_quality_note", ""),
        }

        # 9. Assemble final result
        result = RoadmapScore(
            roadmap_id=context.roadmap_id,
            roadmap_title=context.roadmap_title,
            roadmap_state=context.roadmap_state or "Unknown",
            roadmap_type=context.roadmap_type,
            core_score=core_score,
            dimensions=dimensions,
            confidence=confidence,
            signals=signals,
            llm_explanation=llm_explanation,
            calculated_at=datetime.now(),
            data_completeness_pct=self._calculate_data_completeness(context),
        )

        appLogger.info({
            "event": "roadmap_scoring_complete",
            "roadmap_id": roadmap_id,
            "core_score": core_score,
            "confidence": confidence.overall,
            "planning_signal": signals.planning_depth.pattern.value if signals.planning_depth else None,
        })

        return result

    # -------------------------------------------------------------------------
    # Data fetching
    # -------------------------------------------------------------------------

    def _fetch_roadmap_context(self, roadmap_id: int, tenant_id: int) -> RoadmapContext:
        """
        Fetch all roadmap data using fetchRoadmapDataForBusinessPlan.
        Parses JSON_AGG TEXT fields into Python lists/dicts.

        Raises:
            ValueError if roadmap is not found.
        """
        try:
            results = RoadmapDao.fetchRoadmapDataForBusinessPlan(roadmap_id)
        except Exception as e:
            raise ValueError(
                f"Error fetching roadmap {roadmap_id}: {str(e)}\n{traceback.format_exc()}"
            )

        if not results or len(results) == 0:
            raise ValueError(f"Roadmap {roadmap_id} not found")

        raw = results[0]

        # Fetch supplemental fields not included in fetchRoadmapDataForBusinessPlan
        supp = {}
        try:
            supp_results = RoadmapDao.fetchRoadmapScoreFields(roadmap_id)
            if supp_results:
                supp = supp_results[0]
        except Exception as e:
            appLogger.warning({
                "event": "roadmap_score_fields_fetch_failed",
                "roadmap_id": roadmap_id,
                "error": str(e),
            })

        # Decode integer enums to human-readable strings
        _state_int = supp.get("current_state")
        decoded_state = roadmap_state_mapping(_state_int) if _state_int is not None else None

        _type_int = supp.get("type")
        try:
            decoded_type = roadmap_type_mapping(_type_int) if _type_int is not None else None
        except (ValueError, KeyError):
            decoded_type = None

        _priority_int = supp.get("priority")
        _priority_map = {1: "High", 2: "Medium", 3: "Low"}
        decoded_priority = _priority_map.get(_priority_int) if _priority_int is not None else None

        return RoadmapContext(
            roadmap_id=roadmap_id,
            tenant_id=tenant_id,
            roadmap_title=raw.get("roadmap_title") or "",
            roadmap_description=raw.get("roadmap_description"),
            roadmap_objectives=raw.get("roadmap_objectives"),
            roadmap_solution=supp.get("solution"),
            roadmap_category=raw.get("roadmap_category"),
            roadmap_org_strategy_alignment=raw.get("roadmap_org_strategy_alignment"),
            roadmap_type=decoded_type,
            roadmap_state=decoded_state,
            roadmap_priority=decoded_priority,
            roadmap_start_date=supp.get("start_date"),
            roadmap_end_date=supp.get("end_date"),
            roadmap_budget=self._to_float(raw.get("roadmap_budget")),
            roadmap_total_capital_cost=self._to_float(raw.get("roadmap_total_capital_cost")),
            roadmap_constraints=self._parse_json_agg(raw.get("roadmap_constraints")),
            roadmap_portfolios=self._parse_string_agg(raw.get("roadmap_portfolios")),
            roadmap_key_results=self._parse_json_agg(raw.get("roadmap_key_results")),
            roadmap_scope=self._parse_string_agg(raw.get("roadmap_scope")),
            team_data=self._parse_json_agg(raw.get("team_data")),
            savings_cash_inflows=self._parse_json_agg(
                raw.get("operational_efficiency_gains_savings_cash_inflow")
            ),
            revenue_cash_inflows=self._parse_json_agg(
                raw.get("revenue_uplift_cash_inflow_data")
            ),
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _blend(presence: int, llm_quality: int, rule_weight: float) -> int:
        """Blend a presence score with an LLM quality score."""
        llm_weight = 1.0 - rule_weight
        blended = (presence * rule_weight) + (llm_quality * llm_weight)
        return int(min(100, max(0, blended)))

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """Safely convert a value to float, returning None if not possible."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_json_agg(value: Any) -> List[Dict[str, Any]]:
        """
        Parse a JSON_AGG TEXT column from PostgreSQL.

        The column is produced by JSON_AGG(DISTINCT JSON_BUILD_OBJECT(...)::TEXT),
        which returns a Python list of strings. Each string is a JSON object.
        Handles None, null elements, and already-parsed dicts defensively.
        """
        if not value:
            return []
        if isinstance(value, list):
            result = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, str):
                    item = item.strip()
                    if item and item.lower() != "null":
                        try:
                            parsed = json.loads(item)
                            if isinstance(parsed, dict):
                                result.append(parsed)
                        except (json.JSONDecodeError, ValueError):
                            pass
            return result
        return []

    @staticmethod
    def _parse_string_agg(value: Any) -> List[str]:
        """
        Parse a JSON_AGG DISTINCT column of plain strings (e.g. portfolio titles, scope names).
        Returns a list of non-null, non-empty strings.
        """
        if not value:
            return []
        if isinstance(value, list):
            return [
                str(item) for item in value
                if item is not None and str(item).strip() and str(item).lower() != "null"
            ]
        return []

    @staticmethod
    def _calculate_data_completeness(context: RoadmapContext) -> int:
        """
        Overall data completeness percentage for the roadmap (0-100).
        10 data points, weighted by importance:
          description(12), objectives(12), solution(12), KPIs(10), scope(8),
          constraints(8), team(10), cash_inflows(10), budget(8), timeline(10)
        """
        score = 0

        # Core text fields (36 pts)
        desc = (context.roadmap_description or "").strip()
        if len(desc) > 50:
            score += 12
        elif desc:
            score += 6

        obj = (context.roadmap_objectives or "").strip()
        if len(obj) > 50:
            score += 12
        elif obj:
            score += 6

        sol = (context.roadmap_solution or "").strip()
        if len(sol) > 50:
            score += 12
        elif sol:
            score += 6

        # Structured data (64 pts)
        kpis = [k for k in context.roadmap_key_results if k]
        if len(kpis) >= 3:
            score += 10
        elif kpis:
            score += 5

        scope_items = [s for s in context.roadmap_scope if s and str(s).strip()]
        if scope_items:
            score += 8

        constraints = [c for c in context.roadmap_constraints if c]
        if constraints:
            score += 8

        team = [t for t in context.team_data if t]
        if team:
            score += 10

        all_inflows = (context.savings_cash_inflows or []) + (context.revenue_cash_inflows or [])
        if any(i for i in all_inflows if i):
            score += 10

        if context.roadmap_budget and float(context.roadmap_budget) > 0:
            score += 8

        if context.roadmap_start_date and context.roadmap_end_date:
            score += 10
        elif context.roadmap_start_date or context.roadmap_end_date:
            score += 5

        return min(100, score)
