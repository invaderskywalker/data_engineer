"""
Roadmap dimension presence-score calculations.
Parallel to calculations.py (project scoring).

Each method is pure Python — no I/O, no LLM.
They compute a rule-based "presence score" (0-100) for each dimension,
which the engine later blends with the LLM quality subscore.
"""

from typing import Tuple
from .roadmap_models import RoadmapContext


class RoadmapDimensionCalculations:
    """Pure presence-based scoring for each roadmap dimension."""

    @staticmethod
    def calculate_strategic_clarity(context: RoadmapContext) -> Tuple[int, str]:
        """
        STRATEGIC CLARITY presence score (0-100).

        Checks whether the core identity fields are populated and
        substantive — not just whether they exist.

        Returns: (presence_score, explanation)
        """
        score = 0
        parts = []

        # Title (always present by schema constraint, but check non-empty)
        if context.roadmap_title and context.roadmap_title.strip():
            score += 15
            parts.append("Title present (+15)")
        else:
            parts.append("Title missing (0)")

        # Description — must be substantive (>50 chars)
        desc = (context.roadmap_description or "").strip()
        if len(desc) > 50:
            score += 25
            parts.append(f"Description present and substantive ({len(desc)} chars, +25)")
        elif desc:
            score += 10
            parts.append(f"Description present but thin ({len(desc)} chars, +10)")
        else:
            parts.append("Description missing (0)")

        # Objectives — most critical field for strategic clarity
        obj = (context.roadmap_objectives or "").strip()
        if len(obj) > 50:
            score += 30
            parts.append(f"Objectives defined ({len(obj)} chars, +30)")
        elif obj:
            score += 10
            parts.append(f"Objectives present but thin ({len(obj)} chars, +10)")
        else:
            parts.append("Objectives missing (0)")

        # Org strategy alignment
        if context.roadmap_org_strategy_alignment:
            score += 20
            parts.append("Org strategy alignment set (+20)")
        else:
            parts.append("Org strategy alignment not set (0)")

        # Category
        if context.roadmap_category:
            score += 10
            parts.append("Category set (+10)")
        else:
            parts.append("Category not set (0)")

        final = min(100, score)
        parts.append(f"Presence score: {final}/100")
        return final, "; ".join(parts)

    @staticmethod
    def calculate_okr_quality(context: RoadmapContext) -> Tuple[int, str]:
        """
        OKR QUALITY presence score (0-100).

        Checks KPI count and baseline_value completeness.

        Returns: (presence_score, explanation)
        """
        kpis = [k for k in context.roadmap_key_results if k]
        score = 0
        parts = []

        if not kpis:
            parts.append("No KPIs / key results defined (0)")
            return 0, "; ".join(parts)

        kpi_count = len(kpis)
        parts.append(f"{kpi_count} KPI(s) defined")

        # KPI count — graded (was: flat +40 for any KPIs)
        if kpi_count >= 3:
            score += 45
            parts.append(f"3+ KPIs defined (+45)")
        elif kpi_count == 2:
            score += 35
            parts.append(f"2 KPIs defined (+35)")
        else:
            score += 25
            parts.append(f"1 KPI defined (+25)")

        # Baseline values filled
        with_baseline = sum(
            1 for k in kpis
            if k.get("baseline_value") not in (None, "", "None", 0)
        )
        if kpi_count > 0:
            baseline_rate = with_baseline / kpi_count
            baseline_bonus = int(baseline_rate * 40)
            score += baseline_bonus
            parts.append(
                f"{with_baseline}/{kpi_count} KPIs have baseline_value "
                f"({baseline_rate:.0%}, +{baseline_bonus})"
            )

        # Org strategy alignment as okr anchor
        if context.roadmap_org_strategy_alignment:
            score += 10
            parts.append("Org strategy alignment present (+10)")

        final = min(100, score)
        parts.append(f"Presence score: {final}/100")
        return final, "; ".join(parts)

    @staticmethod
    def calculate_scope_and_constraints(context: RoadmapContext) -> Tuple[int, str]:
        """
        SCOPE & CONSTRAINTS presence score (0-100).

        Checks number of scope items and diversity of constraint types.

        Returns: (presence_score, explanation)
        """
        scope_items = [s for s in context.roadmap_scope if s and str(s).strip()]
        constraints = [c for c in context.roadmap_constraints if c]
        score = 0
        parts = []

        # Scope items
        scope_count = len(scope_items)
        if scope_count >= 3:
            score += 50
            parts.append(f"{scope_count} scope items defined (+50)")
        elif scope_count >= 1:
            score += 30
            parts.append(f"{scope_count} scope item(s) defined (+30)")
        else:
            parts.append("No scope items defined (0)")

        # Constraints
        constraint_count = len(constraints)
        if constraint_count >= 1:
            score += 30
            parts.append(f"{constraint_count} constraint(s) defined (+30)")

            # Bonus for type diversity
            constraint_types = set(
                c.get("constraint_type", "Unknown")
                for c in constraints
                if c.get("constraint_type") not in (None, "Unknown")
            )
            if len(constraint_types) >= 2:
                score += 20
                parts.append(
                    f"Constraints cover {len(constraint_types)} types "
                    f"({', '.join(sorted(constraint_types))}, +20)"
                )
            else:
                parts.append(f"Constraints cover only 1 type (no diversity bonus)")
        else:
            parts.append("No constraints defined (0)")

        final = min(100, score)
        parts.append(f"Presence score: {final}/100")
        return final, "; ".join(parts)

    @staticmethod
    def calculate_resource_financial_planning(context: RoadmapContext) -> Tuple[int, str]:
        """
        RESOURCE & FINANCIAL PLANNING presence score (0-100).

        Checks budget, team estimates, cash inflows, and timeline.

        Returns: (presence_score, explanation)
        """
        score = 0
        parts = []

        # Budget
        budget = context.roadmap_budget
        if budget and float(budget) > 0:
            score += 25
            parts.append(f"Budget set (${float(budget):,.0f}, +25)")
        else:
            parts.append("Budget not set (0)")

        # Team estimates
        team = [t for t in context.team_data if t]
        if team:
            score += 25
            parts.append(f"{len(team)} team estimate row(s) defined (+25)")
        else:
            parts.append("No team estimates defined (0)")

        # Cash inflows (savings OR revenue)
        all_inflows = (context.savings_cash_inflows or []) + (context.revenue_cash_inflows or [])
        all_inflows = [i for i in all_inflows if i]
        if all_inflows:
            savings_count = len([i for i in context.savings_cash_inflows if i])
            revenue_count = len([i for i in context.revenue_cash_inflows if i])
            score += 25
            parts.append(
                f"Cash inflows defined ({savings_count} savings, {revenue_count} revenue, +25)"
            )
        else:
            parts.append("No cash inflows defined (0)")

        # Total capital cost
        tcc = context.roadmap_total_capital_cost
        if tcc and float(tcc) > 0:
            score += 15
            parts.append(f"Total capital cost set (${float(tcc):,.0f}, +15)")
        else:
            parts.append("Total capital cost not set (0)")

        # Timeline (both dates)
        if context.roadmap_start_date and context.roadmap_end_date:
            score += 10
            parts.append("Start and end dates both set (+10)")
        elif context.roadmap_start_date or context.roadmap_end_date:
            score += 5
            parts.append("Only one date set (+5)")
        else:
            parts.append("No timeline dates set (0)")

        final = min(100, score)
        parts.append(f"Presence score: {final}/100")
        return final, "; ".join(parts)

    @staticmethod
    def calculate_solution_readiness(context: RoadmapContext) -> Tuple[int, str]:
        """
        SOLUTION READINESS presence score (0-100).

        Solution text is the dominant signal — it IS the dimension.
        Metadata (type, priority, portfolio) provides supporting context only.

        Returns: (presence_score, explanation)
        """
        score = 0
        parts = []

        # Solution text — the dominant field (up to 60 pts)
        solution = (context.roadmap_solution or "").strip()
        if len(solution) > 200:
            score += 60
            parts.append(f"Solution well-defined ({len(solution)} chars, +60)")
        elif len(solution) > 100:
            score += 50
            parts.append(f"Solution defined and substantive ({len(solution)} chars, +50)")
        elif len(solution) > 50:
            score += 35
            parts.append(f"Solution defined but brief ({len(solution)} chars, +35)")
        elif solution:
            score += 20
            parts.append(f"Solution present but very thin ({len(solution)} chars, +20)")
        else:
            parts.append("Solution not defined (0)")

        # Roadmap type set (+15)
        if context.roadmap_type and context.roadmap_type not in ("Unknown", ""):
            score += 15
            parts.append(f"Roadmap type set ({context.roadmap_type}, +15)")
        else:
            parts.append("Roadmap type not set (0)")

        # Priority explicitly set (+10)
        if context.roadmap_priority and context.roadmap_priority not in ("Unknown", ""):
            score += 10
            parts.append(f"Priority set ({context.roadmap_priority}, +10)")
        else:
            parts.append("Priority not set (0)")

        # Portfolio assigned (+10)
        portfolios = [p for p in context.roadmap_portfolios if p and str(p).strip()]
        if portfolios:
            score += 10
            parts.append(f"Assigned to portfolio ({', '.join(str(p) for p in portfolios[:2])}, +10)")
        else:
            parts.append("Not assigned to any portfolio (0)")

        # State explicitly set (not Unknown/None) — indicates lifecycle management (+5)
        if context.roadmap_state and context.roadmap_state not in ("Unknown", ""):
            score += 5
            parts.append(f"State set ({context.roadmap_state}, +5)")
        else:
            parts.append("State not set (0)")

        final = min(100, score)
        parts.append(f"Presence score: {final}/100")
        return final, "; ".join(parts)

    @staticmethod
    def aggregate_core_score(
        strategic_clarity: int,
        okr_quality: int,
        scope_and_constraints: int,
        resource_financial: int,
        solution_readiness: int,
        roadmap_state: str = None,
    ) -> int:
        """
        Weighted aggregate of all 5 blended dimension scores.

        Uses state-aware weight profiles:
        - Early stages (Intake/Draft): emphasize strategic + OKR, reduce solution expectation
        - Solutioning/Prioritize: balance all dimensions, emphasize solution
        - Execution/Approved: all dimensions equally critical
        - Default/Unknown: standard balanced weights

        Returns: int (0-100)
        """
        # State weight profiles: {strategic, okr, scope, resource, solution}
        _PROFILES = {
            "early":    (0.30, 0.25, 0.20, 0.15, 0.10),
            "planning": (0.22, 0.20, 0.20, 0.18, 0.20),
            "active":   (0.20, 0.20, 0.20, 0.20, 0.20),
            "default":  (0.25, 0.20, 0.20, 0.20, 0.15),
        }

        _STATE_MAP = {
            "Intake": "early", "Draft": "early",
            "Elaboration": "planning", "Solutioning": "planning", "Prioritize": "planning",
            "Approved": "active", "Execution": "active",
            "Hold": "default", "Archived": "default", "Rejected": "default",
            "Cancelled": "default",
        }

        profile_key = _STATE_MAP.get(roadmap_state, "default") if roadmap_state else "default"
        w_sc, w_okr, w_sco, w_rf, w_sr = _PROFILES[profile_key]

        score = (
            (strategic_clarity * w_sc) +
            (okr_quality * w_okr) +
            (scope_and_constraints * w_sco) +
            (resource_financial * w_rf) +
            (solution_readiness * w_sr)
        )
        return int(min(100, max(0, score)))
