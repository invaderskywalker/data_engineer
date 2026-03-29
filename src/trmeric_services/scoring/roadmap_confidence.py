"""
Roadmap confidence score calculation.
Parallel to confidence.py (project scoring).

Measures how much data is present to back the score.
Floor is 30 (vs 55 for projects) because a roadmap in Intake/Draft
is legitimately incomplete — that is normal, not a data quality failure.
"""

from .roadmap_models import RoadmapContext, RoadmapConfidenceBreakdown


class RoadmapConfidenceCalculation:
    """Calculate data completeness/confidence for a roadmap score."""

    @staticmethod
    def _has_solution_approach(context: RoadmapContext) -> bool:
        """Treat substantive solution text as evidence of implementation readiness."""
        return len((context.roadmap_solution or "").strip()) >= 50

    @staticmethod
    def _has_financial_evidence(context: RoadmapContext) -> bool:
        """Consider any material financial planning signal as evidence, not just budget."""
        budget = context.roadmap_budget
        capital_cost = context.roadmap_total_capital_cost
        team = [t for t in context.team_data if t]
        all_inflows = (context.savings_cash_inflows or []) + (context.revenue_cash_inflows or [])

        return any([
            budget not in (None, "", 0) and float(budget) > 0,
            capital_cost not in (None, "", 0) and float(capital_cost) > 0,
            bool(team),
            any(i for i in all_inflows if i),
        ])

    @staticmethod
    def calculate(context: RoadmapContext, signal_impact: int = 0) -> RoadmapConfidenceBreakdown:
        """
        Calculate overall confidence score (0-100).

        Components & weights:
        1. core_fields       30% — title/description/objectives/category/type
        2. okr_completeness  25% — KPI count + baseline_value fill rate
        3. scope_coverage    20% — scope items + constraints presence
        4. financial_data    15% — budget + team + cash_inflow
        5. alignment_signal  10% — org_strategy_align + portfolio

        Floor: 30 (early-stage roadmap expected to be incomplete)
        Ceiling: 100
        """

        # 1. Core fields (0-100)
        #    5 fields × 20 pts each
        core_score = 0
        if context.roadmap_title and context.roadmap_title.strip():
            core_score += 20
        if (context.roadmap_description or "").strip():
            core_score += 20
        if (context.roadmap_objectives or "").strip():
            core_score += 20
        if context.roadmap_category:
            core_score += 20
        if context.roadmap_type and context.roadmap_type not in ("Unknown", ""):
            core_score += 20

        # 2. OKR completeness (0-100)
        kpis = [k for k in context.roadmap_key_results if k]
        if not kpis:
            okr_score = 0
        elif len(kpis) == 1:
            okr_score = 50
        elif len(kpis) == 2:
            okr_score = 75
        else:
            okr_score = 100

        # Bonus for baseline_value presence (up to +20, capped at 100)
        if kpis:
            with_baseline = sum(
                1 for k in kpis
                if k.get("baseline_value") not in (None, "", "None", 0)
            )
            baseline_bonus = int((with_baseline / len(kpis)) * 20)
            okr_score = min(100, okr_score + baseline_bonus)

        # 3. Scope coverage (0-100)
        scope_items = [s for s in context.roadmap_scope if s and str(s).strip()]
        constraints = [c for c in context.roadmap_constraints if c]
        scope_part = 50 if scope_items else 0
        constraint_part = 50 if constraints else 0
        scope_score = scope_part + constraint_part

        # 4. Financial data (0-100)
        #    3 signals × 33 pts each (rounded)
        financial_score = 0
        budget = context.roadmap_budget
        if budget and float(budget) > 0:
            financial_score += 33
        team = [t for t in context.team_data if t]
        if team:
            financial_score += 33
        all_inflows = (context.savings_cash_inflows or []) + (context.revenue_cash_inflows or [])
        if any(i for i in all_inflows if i):
            financial_score += 34
        financial_score = min(100, financial_score)

        # 5. Alignment signal (0-100)
        alignment_score = 0
        if context.roadmap_org_strategy_alignment:
            alignment_score += 50
        portfolios = [p for p in context.roadmap_portfolios if p and str(p).strip()]
        if portfolios:
            alignment_score += 50

        # Weighted overall + signal adjustment
        overall = (
            (core_score * 0.30) +
            (okr_score * 0.25) +
            (scope_score * 0.20) +
            (financial_score * 0.15) +
            (alignment_score * 0.10)
        ) + signal_impact

        # Cap confidence when critical planning evidence is missing.
        # A roadmap can still be early-stage, but confidence should not read as
        # strong if the score lacks both execution economics and a real solution path.
        has_financial_evidence = RoadmapConfidenceCalculation._has_financial_evidence(context)
        has_solution_approach = RoadmapConfidenceCalculation._has_solution_approach(context)

        confidence_cap = 100
        if not has_financial_evidence and not has_solution_approach:
            confidence_cap = 55
        elif not has_financial_evidence or not has_solution_approach:
            confidence_cap = 70

        # Floor at 30, ceiling at 100, then apply evidence-based confidence cap.
        overall = int(min(confidence_cap, min(100, max(30, overall))))

        # Interpretation
        if overall >= 85:
            interpretation = "High"
        elif overall >= 70:
            interpretation = "Good"
        elif overall >= 55:
            interpretation = "Moderate"
        else:
            interpretation = "Early-stage"

        return RoadmapConfidenceBreakdown(
            core_fields=core_score,
            okr_completeness=okr_score,
            scope_coverage=scope_score,
            financial_data=financial_score,
            alignment_signal=alignment_score,
            overall=overall,
            interpretation=interpretation,
        )
