"""
Roadmap quality signal analysis.
Parallel to signals.py (project scoring).

Derives PlanningDepthPattern and FinancialRationalePattern from
the presence scores already calculated — no new data fetching or LLM calls.
"""

from .roadmap_models import (
    RoadmapContext,
    RoadmapQualitySignals,
    RoadmapPlanningSignal,
    RoadmapFinancialSignal,
    PlanningDepthPattern,
    FinancialRationalePattern,
)


class RoadmapSignalAnalysis:
    """Extract quality signals from roadmap context and presence scores."""

    @staticmethod
    def analyze(
        context: RoadmapContext,
        presence_scores: dict,  # {"strategic": int, "okr": int, "scope": int, "resource": int, "solution": int}
    ) -> RoadmapQualitySignals:
        """
        Derive both signals from the already-computed presence scores.

        Args:
            context: RoadmapContext
            presence_scores: dict with keys matching dimension names

        Returns:
            RoadmapQualitySignals
        """
        planning_signal = RoadmapSignalAnalysis._analyze_planning_depth(presence_scores)
        financial_signal = RoadmapSignalAnalysis._analyze_financial_rationale(context)
        return RoadmapQualitySignals(
            planning_depth=planning_signal,
            financial_rationale=financial_signal,
        )

    @staticmethod
    def _analyze_planning_depth(presence_scores: dict) -> RoadmapPlanningSignal:
        """
        Classify overall planning depth based on how many dimensions
        have a high presence score.

        Thresholds:
        - COMPREHENSIVE    : ≥4 of 5 dimensions ≥ 70
        - SOLID_FOUNDATION : ≥3 of 5 dimensions ≥ 60
        - PARTIAL_PLAN     : ≥2 of 5 dimensions ≥ 40
        - SKELETON         : fewer than 2 dimensions ≥ 40
        """
        scores = [
            presence_scores.get("strategic", 0),
            presence_scores.get("okr", 0),
            presence_scores.get("scope", 0),
            presence_scores.get("resource", 0),
            presence_scores.get("solution", 0),
        ]

        above_70 = sum(1 for s in scores if s >= 70)
        above_60 = sum(1 for s in scores if s >= 60)
        above_40 = sum(1 for s in scores if s >= 40)

        if above_70 >= 4:
            pattern = PlanningDepthPattern.COMPREHENSIVE
            confidence_impact = 5
            description = (
                f"Comprehensive plan: {above_70}/5 dimensions well populated (≥70 presence)"
            )
        elif above_60 >= 3:
            pattern = PlanningDepthPattern.SOLID_FOUNDATION
            confidence_impact = 2
            description = (
                f"Solid foundation: {above_60}/5 dimensions adequately defined (≥60 presence)"
            )
        elif above_40 >= 2:
            pattern = PlanningDepthPattern.PARTIAL_PLAN
            confidence_impact = -2
            description = (
                f"Partial plan: only {above_40}/5 dimensions have meaningful content (≥40 presence)"
            )
        else:
            pattern = PlanningDepthPattern.SKELETON
            confidence_impact = -5
            description = (
                f"Skeleton: fewer than 2 dimensions have meaningful content; "
                f"roadmap needs substantial definition"
            )

        return RoadmapPlanningSignal(
            pattern=pattern,
            dimensions_above_threshold=above_60,
            description=description,
            confidence_impact=confidence_impact,
        )

    @staticmethod
    def _analyze_financial_rationale(context: RoadmapContext) -> RoadmapFinancialSignal:
        """
        Classify financial rationale completeness.

        WELL_JUSTIFIED    : budget + cost + cash_inflow + justification_text all present
        PARTIALLY_JUSTIFIED: some financial data present
        BUDGET_ONLY       : budget/cost set but no ROI case (no inflows)
        NO_FINANCIAL_DATA : nothing set
        """
        has_budget = bool(
            context.roadmap_budget and float(context.roadmap_budget) > 0
        )
        has_cost = bool(
            context.roadmap_total_capital_cost
            and float(context.roadmap_total_capital_cost) > 0
        )
        all_inflows = (context.savings_cash_inflows or []) + (context.revenue_cash_inflows or [])
        all_inflows = [i for i in all_inflows if i]
        has_inflows = bool(all_inflows)

        has_justification = any(
            i.get("justification_text") and str(i["justification_text"]).strip()
            for i in all_inflows
        )

        financial_signals = sum([has_budget, has_cost, has_inflows, has_justification])

        if financial_signals >= 3 and has_inflows:
            pattern = FinancialRationalePattern.WELL_JUSTIFIED
            description = (
                "Well-justified: budget, cost estimate, cash inflows"
                + (", and justification text" if has_justification else "")
                + " all present"
            )
        elif has_budget or has_cost:
            if has_inflows:
                pattern = FinancialRationalePattern.PARTIALLY_JUSTIFIED
                description = "Partially justified: financial figures and cash inflows present but incomplete"
            else:
                pattern = FinancialRationalePattern.BUDGET_ONLY
                description = (
                    "Budget/cost set but no ROI case: "
                    "cash inflows and financial justification are missing"
                )
        elif has_inflows:
            pattern = FinancialRationalePattern.PARTIALLY_JUSTIFIED
            description = "Cash inflows defined but no budget or cost estimate"
        else:
            pattern = FinancialRationalePattern.NO_FINANCIAL_DATA
            description = "No financial data: budget, cost, and cash inflows are all missing"

        return RoadmapFinancialSignal(
            pattern=pattern,
            has_budget=has_budget,
            has_cost_estimate=has_cost,
            has_cash_inflows=has_inflows,
            has_justification=has_justification,
            description=description,
        )
