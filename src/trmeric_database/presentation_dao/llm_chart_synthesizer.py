# src/trmeric_database/presentation_dao/llm_chart_synthesizer.py
#
# LLM Chart Synthesizer — THE JUDGE.
#
# Receives DAO results as-is (no flattening, no transformation).
# Surfaces _global_summary prominently when present — it contains
# pre-aggregated values that are ideal for charts.
# The LLM reads the real structure and judges what to show.
#
# Output schema EXACTLY matches ChartExecutor.execute() so it plugs
# directly into ChartExportService.export_to_json() with zero changes.

import json
import traceback
from typing import Any, Dict, List, Optional

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT SCHEMA REFERENCE
# ─────────────────────────────────────────────────────────────────────────────

CHART_SCHEMA_EXAMPLE = {
    "thought_process": "<overall reasoning: what data exists, what matters, what to show>",
    "charts": [
        {
            "chart_id": "chart_001",
            "thought_process": "<per-chart reasoning: why this type, which fields, what insight>",
            "type": "column",
            "stacking": None,
            "title": "Human-readable title (4-8 words)",
            "xAxis": {"categories": ["Category A", "Category B", "Category C"]},
            "series": [{"name": "Series name", "data": [10, 25, 15]}]
        },
        {
            "chart_id": "chart_002",
            "thought_process": "<reasoning>",
            "type": "pie",
            "stacking": None,
            "title": "Pie chart example",
            "xAxis": {"categories": []},
            "series": [
                {
                    "name": "Distribution",
                    "data": [
                        {"name": "Slice A", "y": 40},
                        {"name": "Slice B", "y": 35},
                        {"name": "Slice C", "y": 25}
                    ]
                }
            ]
        }
    ]
}

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — built as a plain string (NOT an f-string at module level)
# so we never accidentally bake in runtime state or corrupt braces.
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_JSON = json.dumps(CHART_SCHEMA_EXAMPLE, indent=2)

SYSTEM_PROMPT = """
You are THE CHART JUDGE for an enterprise analytics platform.

You receive raw analytical data and decide:
  • Is there anything genuinely worth visualising?
  • What insight does the user actually need to see?
  • Which chart type communicates that insight most clearly?
  • Are the data values real enough to support that chart?

You are NOT a formatter. You are a judge. Think first, then build.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT SCHEMA (MATCH EXACTLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

""" + _SCHEMA_JSON + """

FIELD RULES:

chart_id         → unique string e.g. "chart_001"
type             → one of: column | bar | line | area | pie | scatter | bubble
stacking         → "normal" for stacked charts, null otherwise
title            → concise human-readable title (4-8 words)
xAxis.categories → string labels — EMPTY [] for pie / scatter / bubble

series shapes by type:

  column / bar / line / area:
    {"name": "Label", "data": [10, 25, 15]}
    data = plain numbers, positionally aligned to xAxis.categories
    len(data) MUST equal len(xAxis.categories) — if they differ the chart is BROKEN

  pie:
    {"name": "Label", "data": [{"name": "Slice", "y": 42}, ...]}

  scatter / bubble:
    {"name": "Label", "data": [{"x": 320.0, "y": 85, "name": "Point label"}, ...]}
    x and y = REAL numeric field values from the data rows
    name on each point = entity title (shown in tooltip on hover)
    NEVER use row index (0, 1, 2, 3...) as x or y

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA INPUTS — READ THIS FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You will receive the analytical data exactly as produced by the DAO — no
transformation, no flattening. The structure IS the signal. Read it as-is.

The data may contain:

1. _global_summary  ← READ THIS FIRST IF PRESENT
   A top-level key containing pre-aggregated totals, counts, breakdowns,
   and computed metrics. This is the richest source for chart values.
   It may look like:
     {
       "_global_summary": {
         "total_roadmaps": 42,
         "by_status": {"on_track": 18, "at_risk": 14, "compromised": 10},
         "by_category": {"Platform": 12, "Growth": 8, ...},
         "avg_priority": 74.2,
         ...
       }
     }
   → Pre-aggregated breakdowns are ideal for pie, column, bar charts.
   → Use these values directly — they are already correct totals.
   → ALWAYS check _global_summary before looking at entity-level rows.

2. Entity-level rows
   A list of dicts, one per entity (roadmap, project, idea, etc.).
   Each entity has its own fields (title, priority, status, dates, etc.).
   → Use for: ranking, scatter/bubble (one point per entity),
     trend over time (if entities have date fields).
   → Fields vary by domain — inspect the actual keys present.

3. Aggregated sub-lists
   Some results contain pre-grouped sub-arrays (e.g. monthly breakdowns,
   status histories, category counts inside a result object).
   → These are also ready to use directly.

RULE: Read the actual structure first. Use whatever is richest for the
      intended chart. _global_summary is usually the best starting point.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — JUDGE THE DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before touching chart types, ask yourself:

  Q1: Is _global_summary present?
      Yes → read it immediately. List every key and its value type.
            Breakdowns (dicts of label→count/value) are chart-ready.
      No  → proceed to entity rows.

  Q2: How many entity rows are present?
      0 rows and no _global_summary → Return {"charts": []} — nothing to show.
      1-2 rows, no summary          → Only simple charts. No scatter.
      3+ rows OR summary present    → Full chart palette available.

  Q3: What numeric fields exist and do they have real non-zero values?
      List every numeric field across _global_summary AND entity rows.
      For each, note: is it a total? a breakdown? a per-entity value?
      A field where 80%+ of values are zero is NOT suitable for an axis.

  Q4: What categorical fields exist?
      Low cardinality strings (< 20 unique values) → grouping, stacking, pie.
      Already-aggregated dicts in _global_summary → direct chart source.

  Q5: Is there a time/sequence field?
      (date, month, sprint, quarter) → line or area is viable.

  Q6: What does the user actually want to understand?
      Re-read ANALYTICAL GOAL and CHART INTENT.
      If intent names specific fields → honour those fields exactly.
      If intent is vague → choose the most informative available chart.

Write your answers to Q1-Q6 in the top-level "thought_process" field.
This reasoning MUST appear before you commit to any chart.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — SELECT CHART TYPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use chart_intent as primary guide. When absent or vague:

  One numeric + one category label     → column (vertical) or bar (horizontal,
                                          use bar when labels are long text)
  One numeric + time sequence          → line or area
  Part-of-whole, ≤ 6 groups           → pie
  Two numerics per entity              → scatter
  Two numerics + one size dimension    → bubble
  One numeric + stacked groups         → column with stacking="normal"
  Top-N ranking by a score             → horizontal bar, sorted desc

QUALITY GATE FOR SCATTER:
  Count entity rows where BOTH X-field > 0 AND Y-field > 0 = valid_count
  (scatter only applies to entity-level rows, not _global_summary aggregates)
  If valid_count < 3:
    → DO NOT build scatter.
    → Build ranked horizontal bar on Y-field instead.
    → Sort desc, take top 20, label by entity title.
    → Note fallback in thought_process.
  If valid_count ≥ 3:
    → Proceed with scatter.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — BUILD THE CHART DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RULES that MUST hold for every chart:

  R1.  Every value must exist in the data — never invent, estimate, or interpolate.
  R2.  Numeric fields must be int or float in the JSON — never a string.
  R3.  len(series[i].data) MUST equal len(xAxis.categories) for column/bar/line/area.
       Recount before finalising.
  R4.  pie data uses {name, y} objects. y must be a real number.
  R5.  scatter/bubble data uses {x, y, name}. x and y are REAL field values.
  R6.  xAxis.categories MUST be [] for pie, scatter, bubble.
       SCATTER RULE: xAxis must ONLY contain a "title" object and "categories": [].
       NEVER include any other xAxis properties that would force category mode.
  R7.  For stacked charts: stacking = "normal". group_by dimension becomes
       multiple series entries, each with its own name and data array.
  R8.  Cap scatter/bubble at 30 points: sort by Y desc then X desc, take top 30.
  R9.  Cap column/bar categories at 20: sort by value desc, take top 20.
  R10. Skip entities where ALL relevant numeric fields are 0 or null.
  R11. Prefer 1–3 charts. Never add a chart that doesn't add new insight.
  R12. NEVER return {"charts": []} if any numeric field has real non-zero values.
       There is always something worth showing — fall back to a ranked bar.
       Only return {"charts": []} if data is completely empty or entirely zero.

SEMANTIC FIELDS (descriptions, objectives, alignment text):
  → Use ONLY as point labels, titles, or tooltip context.
  → NEVER as x, y, z axis values. They are text — not numbers.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUADRANT CHARTS (2x2) — FULL RECIPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trigger when chart_intent contains: "2x2", "quadrant", "prioritization matrix",
"impact-effort", "impact vs effort", or similar positioning language.

Follow steps A → H in strict order.

──────────────────────────────────────
A — VALIDATE DATA QUALITY
──────────────────────────────────────
  valid_points = rows where X-field > 0 AND Y-field > 0

  If len(valid_points) < 3:
    → DO NOT attempt scatter.
    → Build ranked horizontal bar on Y-field:
        categories = top 20 entity titles sorted by Y desc
        data       = their Y values
        title      = "Top [Entities] by [Y-field label]"
    → thought_process: "X axis had insufficient data (< 3 valid points).
      Fell back to ranked bar chart on [Y-field]."
    → STOP. Do not continue to B–H.

  If len(valid_points) ≥ 3:
    → Continue to B.

──────────────────────────────────────
B — EXTRACT SCATTER POINTS
──────────────────────────────────────
  For each valid_point:
    x    = X-field value   (real number from the data, NOT row index)
    y    = Y-field value   (real number from the data, NOT row index)
    name = entity title field (string, shown in tooltip)

  Sort by Y desc, then X desc. Take top 30.
  Skip any point where both x=0 AND y=0.

──────────────────────────────────────
C — COMPUTE QUADRANT BOUNDARIES
──────────────────────────────────────
  From your extracted points:
    median_x = median of all x values
    median_y = median of all y values
    max_x    = max(x values) * 1.1    ← 10% padding
    max_y    = max(y values) * 1.1
    min_x    = 0
    min_y    = 0

──────────────────────────────────────
D — BUILD SCATTER DATA SERIES
──────────────────────────────────────
  {
    "type": "scatter",
    "name": "Initiatives",
    "data": [
      {"x": <real_x>, "y": <real_y>, "name": "<entity_title>"},
      ...
    ]
  }

──────────────────────────────────────
E — ADD QUADRANT DIVIDER LINES
──────────────────────────────────────
  Vertical divider (splits Low Effort / High Effort):
  {
    "type": "line", "name": "", "dashStyle": "Dash",
    "color": "#cccccc", "enableMouseTracking": false,
    "showInLegend": false, "marker": {"enabled": false},
    "data": [[median_x, min_y], [median_x, max_y]]
  }

  Horizontal divider (splits Low Impact / High Impact):
  {
    "type": "line", "name": "", "dashStyle": "Dash",
    "color": "#cccccc", "enableMouseTracking": false,
    "showInLegend": false, "marker": {"enabled": false},
    "data": [[min_x, median_y], [max_x, median_y]]
  }

──────────────────────────────────────
F — ADD QUADRANT LABEL SERIES
──────────────────────────────────────
  Position labels at the centre of each quadrant:

    top_left_x     = median_x * 0.5
    top_left_y     = median_y + (max_y - median_y) * 0.5
    top_right_x    = median_x + (max_x - median_x) * 0.5
    top_right_y    = top_left_y
    bottom_left_x  = top_left_x
    bottom_left_y  = median_y * 0.5
    bottom_right_x = top_right_x
    bottom_right_y = bottom_left_y

  CRITICAL: Use "name" (NOT "label") on each data point.
  CRITICAL: Use "{point.name}" (NOT "{point.label}") in dataLabels.format.
  Highcharts only recognises {point.name} — {point.label} is silently ignored
  and quadrant labels will be invisible if you use it.

  Label series:
  {
    "type": "scatter",
    "name": "Quadrants",
    "enableMouseTracking": false,
    "showInLegend": false,
    "marker": {"enabled": false},
    "dataLabels": {
      "enabled": true,
      "format": "{point.name}",
      "style": {"color": "#aaaaaa", "fontSize": "11px", "fontWeight": "normal"}
    },
    "data": [
      {"x": top_left_x,     "y": top_left_y,     "name": "Quick Wins"},
      {"x": top_right_x,    "y": top_right_y,    "name": "Strategic Bets"},
      {"x": bottom_left_x,  "y": bottom_left_y,  "name": "Fill-Ins"},
      {"x": bottom_right_x, "y": bottom_right_y, "name": "Avoid"}
    ]
  }

──────────────────────────────────────
G — SEMANTIC ENRICHMENT (optional)
──────────────────────────────────────
  If a categorical field (e.g. current_stage, roadmap_category_str,
  roadmap_org_strategy_alignment_text) has ≤ 6 distinct values AND
  a count-by-category chart would add genuine insight beyond the scatter:
    → Add a second chart (column or pie: count per category).
    → Otherwise skip it. Do not add noise.

──────────────────────────────────────
H — FINAL SERIES ORDER (MANDATORY)
──────────────────────────────────────
  series array for the quadrant chart MUST be exactly:
  [scatter_data_series, vertical_divider, horizontal_divider, quadrant_labels]

  Final quadrant chart structure — copy this exactly, substituting real values:
  {
    "chart_id": "chart_001",
    "thought_process": "<reasoning>",
    "type": "scatter",
    "stacking": null,
    "title": "Initiatives: Impact vs Effort",
    "xAxis": {
      "title": {"text": "Effort (hours)"},
      "categories": []
    },
    "yAxis": {
      "title": {"text": "Impact (priority score)"}
    },
    "series": [
      {
        "type": "scatter",
        "name": "Initiatives",
        "data": [
          {"x": 1280, "y": 99, "name": "AI Platform Launch"},
          {"x": 640,  "y": 72, "name": "Mobile Redesign"}
        ]
      },
      {
        "type": "line",
        "name": "",
        "dashStyle": "Dash",
        "color": "#cccccc",
        "enableMouseTracking": false,
        "showInLegend": false,
        "marker": {"enabled": false},
        "data": [[960, 0], [960, 109]]
      },
      {
        "type": "line",
        "name": "",
        "dashStyle": "Dash",
        "color": "#cccccc",
        "enableMouseTracking": false,
        "showInLegend": false,
        "marker": {"enabled": false},
        "data": [[0, 50], [1408, 50]]
      },
      {
        "type": "scatter",
        "name": "Quadrants",
        "enableMouseTracking": false,
        "showInLegend": false,
        "marker": {"enabled": false},
        "dataLabels": {
          "enabled": true,
          "format": "{point.name}",
          "style": {"color": "#aaaaaa", "fontSize": "11px", "fontWeight": "normal"}
        },
        "data": [
          {"x": 480,  "y": 80, "name": "Quick Wins"},
          {"x": 1280, "y": 80, "name": "Strategic Bets"},
          {"x": 480,  "y": 25, "name": "Fill-Ins"},
          {"x": 1280, "y": 25, "name": "Avoid"}
        ]
      }
    ]
  }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL SELF-CHECK (run before returning)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For every chart in your output, verify:

  [ ] Does this chart add genuine insight in under 5 seconds?
      If no → remove it.
  [ ] column/bar/line/area: len(data) == len(categories)?
      If no → fix or remove.
  [ ] scatter/bubble: every point has real x and y from the data?
      If any point uses row index → replace with real field value or remove.
  [ ] scatter/bubble: xAxis has ONLY "title" and "categories": [] — nothing else?
      If no → remove the extra properties.
  [ ] pie: group_by is null, unique slices ≤ 6?
  [ ] stacked: stacking = "normal" and multiple named series?
  [ ] quadrant: 4 series in order [data, v-line, h-line, labels]?
  [ ] quadrant labels: data points use "name" (NOT "label")?
  [ ] quadrant labels: dataLabels.format is "{point.name}" (NOT "{point.label}")?
  [ ] No invented numbers anywhere?
  [ ] No semantic/text fields used as axis values?

Return ONLY the JSON object. No markdown, no fences, no commentary outside the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
# POST-PROCESSING VALIDATOR — Python catches what the LLM might slip through
# ─────────────────────────────────────────────────────────────────────────────

def _repair_quadrant_labels(series: List[Dict]) -> List[Dict]:
    """
    FIX: Highcharts only knows {point.name}, not {point.label}.
    If the LLM still emits the old pattern, promote label → name
    and fix the format token so quadrant labels actually appear.
    """
    repaired = []
    for s in series:
        if s.get("name") == "Quadrants":
            s = dict(s)
            # Fix dataLabels format token
            if isinstance(s.get("dataLabels"), dict):
                dl = dict(s["dataLabels"])
                if dl.get("format") == "{point.label}":
                    dl["format"] = "{point.name}"
                s["dataLabels"] = dl
            # Promote label → name on each data point
            if isinstance(s.get("data"), list):
                fixed_data = []
                for p in s["data"]:
                    if isinstance(p, dict) and "label" in p and "name" not in p:
                        p = dict(p)
                        p["name"] = p.pop("label")
                    fixed_data.append(p)
                s["data"] = fixed_data
        repaired.append(s)
    return repaired


def _validate_and_repair_charts(charts: List[Dict]) -> List[Dict]:
    """
    Structural validation + lightweight repair pass.

    Drops or repairs charts that would silently render wrong in Highcharts.
    """
    valid: List[Dict] = []

    for c in charts:
        if not isinstance(c, dict):
            continue

        chart_type = c.get("type", "")
        series = c.get("series", [])
        title = c.get("title", c.get("chart_id", "unknown"))

        if not chart_type or not isinstance(series, list) or len(series) == 0:
            appLogger.warning({"event": "chart_dropped", "reason": "no type or series", "title": title})
            continue

        # ── column / bar / line / area: data length must match categories ──
        if chart_type in ("column", "bar", "line", "area"):
            categories = c.get("xAxis", {}).get("categories", [])
            n_cats = len(categories)

            repaired_series = []
            ok = True
            for s in series:
                data = s.get("data", [])
                if len(data) != n_cats:
                    appLogger.warning({
                        "event": "chart_series_length_mismatch",
                        "title": title,
                        "series_name": s.get("name"),
                        "expected": n_cats,
                        "got": len(data),
                    })
                    if len(data) > n_cats:
                        # Trim to match — safer than padding with zeros
                        s = dict(s)
                        s["data"] = data[:n_cats]
                        appLogger.warning({"event": "chart_series_trimmed", "title": title})
                    else:
                        ok = False
                        break
                repaired_series.append(s)

            if not ok:
                appLogger.warning({"event": "chart_dropped", "reason": "series/category length mismatch unfixable", "title": title})
                continue
            c = dict(c)
            c["series"] = repaired_series

        # ── scatter / bubble ──────────────────────────────────────────────────
        if chart_type in ("scatter", "bubble"):
            # FIX 1: Strip any stray keys from xAxis that would force Highcharts
            # into category mode and break numeric scatter axes.
            # Only "title" and "categories": [] are safe for scatter.
            if "xAxis" in c:
                x_axis = c["xAxis"]
                safe_xaxis: Dict[str, Any] = {"categories": []}
                if isinstance(x_axis.get("title"), dict):
                    safe_xaxis["title"] = x_axis["title"]
                elif isinstance(x_axis.get("title"), str):
                    safe_xaxis["title"] = {"text": x_axis["title"]}
                if x_axis != safe_xaxis:
                    appLogger.warning({
                        "event": "scatter_xaxis_sanitised",
                        "title": title,
                        "original_keys": list(x_axis.keys()),
                    })
                c = dict(c)
                c["xAxis"] = safe_xaxis

            # FIX 2: Repair quadrant label series (label → name, format token)
            c = dict(c)
            c["series"] = _repair_quadrant_labels(c["series"])
            series = c["series"]  # refresh local ref after repair

            # FIX 3: Validate data-point series have real x,y (not row indices)
            drop = False
            for s in series:
                if s.get("name") in ("", "Quadrants"):
                    continue  # divider lines and label series — skip
                data = s.get("data", [])
                if not isinstance(data, list) or len(data) == 0:
                    continue
                x_vals = [p.get("x") for p in data if isinstance(p, dict) and "x" in p]
                if x_vals and x_vals == list(range(len(x_vals))):
                    appLogger.warning({
                        "event": "chart_dropped",
                        "reason": "scatter x-axis appears to be row index",
                        "title": title,
                    })
                    drop = True
                    break
            if drop:
                continue

        # ── pie: y values must be numeric ──
        if chart_type == "pie":
            for s in series:
                data = s.get("data", [])
                bad = [p for p in data if not isinstance(p.get("y"), (int, float))]
                if bad:
                    appLogger.warning({"event": "chart_pie_bad_y", "title": title, "bad_count": len(bad)})
                    s["data"] = [p for p in data if isinstance(p.get("y"), (int, float))]

        # ── ensure xAxis exists ──
        if "xAxis" not in c:
            c["xAxis"] = {"categories": []} if chart_type in ("pie", "scatter", "bubble") else {"categories": []}

        # ── ensure stacking key exists ──
        if "stacking" not in c:
            c["stacking"] = None

        valid.append(c)

    return valid


# ─────────────────────────────────────────────────────────────────────────────
# THE JUDGE
# ─────────────────────────────────────────────────────────────────────────────

class LLMChartSynthesizer:
    """
    THE JUDGE.

    Receives raw DAO results (self.results from SuperAgent), extracts clean
    flat rows via Python, then asks the LLM to reason about what to show and
    produce Highcharts-compatible JSON.

    Output schema matches ChartExecutor.execute() — plugs into
    ChartExportService.export_to_json() with zero changes.
    """

    def __init__(self, tenant_id: int, user_id: int, session_id: str):
        self.tenant_id  = tenant_id
        self.user_id    = user_id
        self.session_id = session_id
        self.llm        = ChatGPTClient(user_id, tenant_id)
        self.log_info   = {"tenant_id": tenant_id, "user_id": user_id}
        self.model_opts = ModelOptions(
            model="gpt-4.1",
            max_tokens=20000,
            temperature=0.1,   # lower = more consistent, less hallucination
        )

    # ── Public entry point ────────────────────────────────────────────────────

    def synthesize(
        self,
        results: List[Dict[str, Any]],
        requirement_focus: str,
        chart_intent: str = "",
        conversation: str = "",
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        results           : raw self.results from SuperAgent — sent as-is, no transformation
        requirement_focus : what the user wanted to understand / what to show
        chart_intent      : type + axis hint from execution plan, e.g.
                            "scatter 2x2 quadrant: X=effort_hours, Y=roadmap_priority"
                            "bar: count of projects by portfolio"
                            "line trend: ideas created per month in 2024"
                            Leave empty to let the judge decide.
        conversation      : prior conversation context (optional)

        Returns
        -------
        {"charts": [...]}  or {"charts": []} on failure / no data
        """
        try:
            appLogger.info({
                "event": "llm_chart_synthesizer_start",
                # "result_count": len(results) if isinstance(results, list) else 1,
            })

            # ── Step 2: Serialize data ────────────────────────────────────────
            results_str = json.dumps(results, default=str)

            # ── Step 3: Build user prompt ─────────────────────────────────────
            user_prompt = f"""
ANALYTICAL GOAL:
{requirement_focus}

CHART INTENT:
{chart_intent or "No specific chart type — apply the full judge protocol to choose the most informative chart(s)."}

CONVERSATION CONTEXT:
{conversation or "None"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL ANALYTICAL DATA (complete DAO output — entity rows, sub-lists, all context)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{results_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execute the full judge protocol from the system prompt:

  Phase 1 — Judge the data
            Q1: Is _global_summary present and useful?
            Q2: How many entity rows? Any data at all?
            Q3: Which numeric fields have real non-zero values?
            Q4: Which categorical fields exist?
            Q5: Any time/sequence fields?
            Q6: What does the user actually need to see?
            Write all reasoning in top-level thought_process.

  Phase 2 — Select chart type(s)
            Apply quality gates.
            If 2x2/quadrant intent → apply Steps A–H from QUADRANT CHARTS section.

  Phase 3 — Build chart data
            Use values directly from the data — never invent.
            Apply all R1–R12 rules.

  Final self-check — verify every chart before returning.
  Pay special attention to:
    - scatter xAxis must have ONLY "title" and "categories": []
    - quadrant label points must use "name" not "label"
    - quadrant dataLabels.format must be "{{point.name}}" not "{{point.label}}"

Return ONLY the JSON object. No markdown, no fences, no commentary outside the JSON.
"""

            # ── Step 4: Call the LLM ──────────────────────────────────────────
            chat = ChatCompletion(
                system=SYSTEM_PROMPT,
                prev=[],
                user=user_prompt,
            )

            raw = ""
            for chunk in self.llm.runWithStreaming(
                chat,
                self.model_opts,
                "llm_chart_synthesizer::synthesize",
                logInDb=self.log_info,
            ):
                raw += chunk

            print("llm chart -- ", raw)

            appLogger.info({
                "event": "llm_chart_synthesizer_raw_received",
                "raw_length": len(raw),
                "raw_preview": raw[:300],
            })

            # ── Step 5: Parse ─────────────────────────────────────────────────
            parsed = extract_json_after_llm(raw)
            with open("chart_json.json", "w") as f:
                json.dump(parsed, f, indent=2)

            if isinstance(parsed, list):
                parsed = {"charts": parsed}

            if not isinstance(parsed, dict) or "charts" not in parsed:
                appLogger.warning({
                    "event": "llm_chart_synthesizer_bad_output",
                    "raw_preview": raw[:500],
                })
                return {"charts": []}

            # ── Step 6: Python-side validation + repair ───────────────────────
            valid_charts = _validate_and_repair_charts(parsed.get("charts", []))

            appLogger.info({
                "event": "llm_chart_synthesizer_done",
                "charts_produced": len(valid_charts),
                "thought_process": parsed.get("thought_process", "")[:300],
            })

            return {"charts": valid_charts}

        except Exception as e:
            appLogger.error({
                "event": "llm_chart_synthesizer_failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            return {"charts": []}
        