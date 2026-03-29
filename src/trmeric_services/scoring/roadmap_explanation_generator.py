"""
Roadmap scoring explanation generator.
Parallel to explanation_generator.py (project scoring).

IMPORTANT: This component does dual work in a SINGLE LLM call:
1. Produces LLM quality subscores (0-100) for each of the 5 dimensions —
   these are blended with presence scores in the engine.
2. Produces human-readable explanations, strengths, and gaps.

This avoids 5 separate LLM calls. The engine calls evaluate_and_explain()
once and uses the returned dict for both blending and final output.
"""

from typing import Dict, Any, Optional
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from .roadmap_models import RoadmapContext
import traceback
import json


class RoadmapScoringExplanationGenerator:
    """
    Single LLM call that produces both quality subscores and narrative explanation
    for a roadmap's data quality score.
    """

    def __init__(self):
        self.llm = ChatGPTClient()

    @staticmethod
    def _build_system_prompt() -> str:
        return """
You are an expert roadmap analyst evaluating how thoroughly a roadmap has been planned and defined.
Your task is to assess the QUALITY and SPECIFICITY of the planning content — not whether the roadmap
is a good idea, but whether the plan itself is well-formed, measurable, and actionable.

SCORING METHODOLOGY:
- strategic_clarity_quality: Are the title, description, and objectives clear, specific, and outcome-oriented?
  (not just labels or one-liners, but substantive direction-setting text)
- okr_quality: Are the KPIs/key results measurable with clear baselines? Could someone hold this roadmap
  accountable to these metrics? Vague KPIs like "improve performance" score low.
- scope_quality: Are scope items specific deliverables? Are constraints named with enough detail
  to actually constrain planning? Generic entries like "Cost" alone score low.
- financial_quality: Do cash inflow justifications explain WHY the savings/revenue will materialize?
  Is the financial case grounded or just placeholder numbers? If no inflows exist, score is 0.
- solution_quality: Does the solution text describe a CONCRETE approach (specific technologies,
  methods, or architectural decisions), or is it vague intent ("we will improve X")?

CRITICAL INSTRUCTIONS — same as project analyst:
1. SPEAK WITH AUTHORITY. You have the data. State facts directly.
   ❌ "suggests potential issues" → ✅ "lacks specificity because..."
   ❌ "might benefit from" → ✅ "requires [specific field] to be actionable"

2. CITE WHAT YOU SEE. Reference actual content from the fields provided.
   ✅ "The objectives field contains only 'increase revenue' with no target, timeline, or measure"
   ✅ "3 KPIs are defined but none have baseline_value, making tracking impossible"

3. STATE GAPS PRECISELY — name the missing field and its impact on the score.

4. CALIBRATE SCORES HONESTLY:
   - 80-100: Genuinely thorough, specific, measurable content
   - 60-79: Present and reasonable but could be more specific
   - 40-59: Exists but thin, generic, or incomplete
   - 20-39: Minimal content, barely usable
   - 0-19: Missing or single-word placeholder

5. FACTOR IN ROADMAP STATE when evaluating:
   - Intake/Draft: Expect strategic clarity and initial OKRs. Don't penalize missing solution
     or financials as harshly — they're expected to be incomplete.
   - Elaboration/Solutioning: Solution approach should be emerging. Score solution_quality
     more critically. Scope should be partially defined.
   - Approved/Execution: ALL dimensions should be well-defined. Score strictly — missing
     solution or financials at this stage is a real planning failure.

Output JSON in this exact format:
{
    "strategic_clarity_quality": <0-100>,
    "okr_quality": <0-100>,
    "scope_quality": <0-100>,
    "financial_quality": <0-100>,
    "solution_quality": <0-100>,
    "dimension_explanations": {
        "strategic_clarity": "<1-2 authoritative sentences citing specific content>",
        "okr_quality": "<1-2 sentences>",
        "scope_and_constraints": "<1-2 sentences>",
        "resource_financial_planning": "<1-2 sentences>",
        "solution_readiness": "<1-2 sentences>"
    },
    "explanation": "<2-3 paragraph authoritative overview of the roadmap's planning quality>",
    "key_strengths": ["<strength with specific evidence>"],
    "key_gaps": ["<gap with specific missing field or weak content>"],
    "data_quality_note": "<what data is present vs missing and how it affects confidence>"
}
"""

    def evaluate_and_explain(self, context: RoadmapContext) -> Dict[str, Any]:
        """
        Single LLM call that returns:
        - Quality subscores (0-100) for all 5 dimensions
        - Human-readable explanations per dimension
        - Overall explanation, strengths, gaps, data quality note

        Args:
            context: RoadmapContext with all roadmap data

        Returns:
            Dict matching the output JSON schema above, or a fallback dict on failure.
        """
        try:
            user_message = self._build_user_message(context)

            chat_completion = ChatCompletion(
                system=self._build_system_prompt(),
                prev=[],
                user=user_message,
            )

            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2),
                "roadmap_scoring::evaluate_and_explain",
            )

            result = extract_json_after_llm(response)
            if result:
                appLogger.info({
                    "event": "roadmap_scoring_llm_success",
                    "roadmap_id": context.roadmap_id,
                })
                return result

            appLogger.warning({
                "event": "roadmap_scoring_llm_parse_failed",
                "roadmap_id": context.roadmap_id,
            })
            return self._fallback_result()

        except Exception as e:
            appLogger.error({
                "event": "roadmap_scoring_llm_error",
                "roadmap_id": context.roadmap_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            return self._fallback_result()

    def _build_user_message(self, context: RoadmapContext) -> str:
        """Construct the user message with all roadmap content for the LLM."""

        # Format KPIs
        kpis = [k for k in context.roadmap_key_results if k]
        if kpis:
            kpi_lines = "\n".join(
                f"  - {k.get('key_result_title', '(no name)')}"
                f" [baseline: {k.get('baseline_value', 'not set')}]"
                for k in kpis
            )
        else:
            kpi_lines = "  (none defined)"

        # Format scope items
        scope_items = [s for s in context.roadmap_scope if s and str(s).strip()]
        scope_lines = (
            "\n".join(f"  - {s}" for s in scope_items)
            if scope_items else "  (none defined)"
        )

        # Format constraints
        constraints = [c for c in context.roadmap_constraints if c]
        constraint_lines = (
            "\n".join(
                f"  - [{c.get('constraint_type', 'Unknown')}] {c.get('constraint_title', '(no name)')}"
                for c in constraints
            )
            if constraints else "  (none defined)"
        )

        # Format team
        team = [t for t in context.team_data if t]
        if team:
            team_lines = "\n".join(
                f"  - {t.get('team_name', '?')} | {t.get('labour_type', '?')} "
                f"| {t.get('team_unit_size', '?')} units | {t.get('team_efforts', '?')}"
                for t in team
            )
        else:
            team_lines = "  (no team estimates)"

        # Format cash inflows
        all_inflows = []
        for inflow in (context.savings_cash_inflows or []):
            if inflow:
                all_inflows.append(f"  [SAVINGS] Period {inflow.get('time_period','?')}: "
                                   f"${inflow.get('cash_inflow','?'):,.0f} — "
                                   f"{inflow.get('justification_text','no justification')[:200]}"
                                   if isinstance(inflow.get('cash_inflow'), (int, float))
                                   else f"  [SAVINGS] {inflow}")
        for inflow in (context.revenue_cash_inflows or []):
            if inflow:
                all_inflows.append(f"  [REVENUE] Period {inflow.get('time_period','?')}: "
                                   f"${inflow.get('cash_inflow','?'):,.0f} — "
                                   f"{inflow.get('justification_text','no justification')[:200]}"
                                   if isinstance(inflow.get('cash_inflow'), (int, float))
                                   else f"  [REVENUE] {inflow}")

        inflow_lines = "\n".join(all_inflows) if all_inflows else "  (no cash inflows defined)"

        return f"""
ROADMAP: {context.roadmap_title or '(no title)'}
State: {context.roadmap_state or 'Unknown'}
Type: {context.roadmap_type or 'Unknown'}
Priority: {context.roadmap_priority or 'Unknown'}
Category: {context.roadmap_category or 'Unknown'}
Portfolio(s): {', '.join(str(p) for p in context.roadmap_portfolios if p) or 'None assigned'}
Org Strategy Alignment: {context.roadmap_org_strategy_alignment or 'Not set'}

── DESCRIPTION ──
{context.roadmap_description or '(not provided)'}

── OBJECTIVES ──
{context.roadmap_objectives or '(not provided)'}

── SOLUTION / APPROACH ──
{context.roadmap_solution or '(not provided)'}

── KPIs / KEY RESULTS ({len(kpis)}) ──
{kpi_lines}

── SCOPE ITEMS ({len(scope_items)}) ──
{scope_lines}

── CONSTRAINTS ({len(constraints)}) ──
{constraint_lines}

── TEAM ESTIMATES ({len(team)}) ──
{team_lines}

── FINANCIAL ──
Budget: {f'${float(context.roadmap_budget):,.0f}' if context.roadmap_budget else 'Not set'}
Total Capital Cost: {f'${float(context.roadmap_total_capital_cost):,.0f}' if context.roadmap_total_capital_cost else 'Not set'}
Timeline: {context.roadmap_start_date or 'no start'} → {context.roadmap_end_date or 'no end'}

── CASH INFLOWS ({len(all_inflows)}) ──
{inflow_lines}

Evaluate the planning quality of this roadmap across all 5 dimensions and return the JSON schema.
"""

    @staticmethod
    def _fallback_result() -> Dict[str, Any]:
        """Return zeroed-out quality scores when LLM call fails."""
        return {
            "strategic_clarity_quality": 0,
            "okr_quality": 0,
            "scope_quality": 0,
            "financial_quality": 0,
            "solution_quality": 0,
            "dimension_explanations": {
                "strategic_clarity": "LLM evaluation unavailable.",
                "okr_quality": "LLM evaluation unavailable.",
                "scope_and_constraints": "LLM evaluation unavailable.",
                "resource_financial_planning": "LLM evaluation unavailable.",
                "solution_readiness": "LLM evaluation unavailable.",
            },
            "explanation": "LLM evaluation could not be completed. Scores reflect presence checks only.",
            "key_strengths": [],
            "key_gaps": ["LLM evaluation failed — manual review required"],
            "data_quality_note": "Quality subscores unavailable; blended scores default to presence scores only.",
        }
