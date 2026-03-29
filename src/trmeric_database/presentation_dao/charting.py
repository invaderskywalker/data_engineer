# src/trmeric_database/presentation_dao/charting.py

from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.helper.common import MyJSON
from src.trmeric_utils.helper.decorators import log_function_io_and_time
import json
import tempfile
from typing import Dict, Any
from src.trmeric_utils.helper.event_bus import Event, event_bus


class ChartInterpreter:
    """
    Converts analytical truth into a CHART PLAN.

    - NO computation
    - NO aggregation
    - NO inference
    - ONLY decides visual projection
    """

    def __init__(self, tenant_id, user_id, session_id):
        self.llm = ChatGPTClient(user_id, tenant_id)
        self.model_opts = ModelOptions(
            model="gpt-4.1",
            temperature=0.1,
            max_tokens=3000,
        )
        self.session_id = session_id

    def interpret(self, *, evidence_snapshot: dict) -> dict:
        system_prompt = f"""
        You are a Chart Planning Engine.

        You receive a PREVIEW of FINAL analytical truth.
        All computation, aggregation, and derivation are already done elsewhere.

        Your responsibility is to DESIGN charts that help a human
        understand the data quickly and clearly.

        You ONLY decide:
        - whether a chart should exist
        - which chart type to use
        - which fields map to axes, series, groupings, or filters

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        CORE RULES (NON-NEGOTIABLE)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1. You MUST NOT compute or aggregate anything.
        2. You MUST NOT infer or derive new metrics.
        3. You MUST NOT invent fields or values.
        4. You ONLY describe visual projection of existing truth.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        DATA SEMANTICS
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ENTITY-LEVEL DATA:
        - One row per entity
        - Suitable for: comparison, ranking, trend

        EXPANDED-LEVEL DATA:
        - One row per sub-entity (e.g. one row per month+type combination)
        - Suitable for: distribution, relationship, composition

        ❌ NEVER mix entity-level and expanded-level data in a single chart.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        CHART SELECTION PHILOSOPHY
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Your goal is NOT to visualize everything.
        Your goal is to visualize what matters MOST.

        Prefer:
        - clarity over completeness
        - insight over decoration
        - fewer charts over many charts

        Guidelines:
        - 1–3 charts per request is ideal
        - Create a chart ONLY if it adds immediate understanding
        - If unsure, DO NOT create the chart

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        INTENT → CHART TYPE GUIDELINES
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        comparison:
        - Goal: compare values across categories
        - Use: bar | column

        ranking:
        - Goal: highlight top or bottom entities
        - Use: bar (sorted descending)
        - Apply limit (Top 5 or Top 10)

        trend:
        - Goal: show change over time or sequence
        - Use: line | area
        - x-axis MUST represent time, sprint, or ordered sequence
        - Use area for cumulative or growth emphasis

        distribution:
        - Goal: show spread or frequency
        - Use: column
        - ONLY for expanded-level data

        composition:
        - Goal: show contribution to a whole
        - Use: stacked_column | pie
        - pie ONLY if <= 6 unique categories
        - stacked_column when comparing composition across time or entities
        - Parts must clearly sum to a meaningful whole

        relationship:
        - Goal: show correlation or interaction
        - Use: scatter | bubble
        - scatter: x and y must be numeric
        - bubble: x, y, z must be numeric (z = magnitude)

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        SUPPORTED CHART TYPES
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        You may ONLY use:
        - line
        - area
        - column
        - bar
        - stacked_column
        - pie
        - scatter
        - bubble

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        DATA STRUCTURE CONTRACT PER CHART TYPE
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Every chart type has a strict data contract.
        You MUST follow the correct contract for every chart you plan.

        ──────────────────────────────────────
        LINE / AREA
        ──────────────────────────────────────
        USE WHEN: showing trend over time or an ordered sequence.

        Single series:
        "chart_type": "line"
        "x": time or ordered field
        "y": numeric measure
        "group_by": null
        "filter": null

        Multi-series (split by dimension):
        "chart_type": "line"
        "x": time or ordered field
        "y": numeric measure
        "group_by": categorical field   -> one line per unique value
        "filter": null or {{ "field": "...", "value": "..." }}

        RULES:
        - x MUST be a time or sequence field
        - If x values repeat AND a categorical split dimension exists -> MUST set group_by

        ──────────────────────────────────────
        COLUMN / BAR
        ──────────────────────────────────────
        USE WHEN: comparing values across categories.

        Single series:
        "chart_type": "column"
        "x": categorical field
        "y": numeric measure
        "group_by": null

        Grouped (side-by-side per category):
        "chart_type": "column"
        "x": categorical field
        "y": numeric measure
        "group_by": secondary categorical field

        RULES:
        - If x values repeat in the data -> you MUST set group_by

        ──────────────────────────────────────
        STACKED_COLUMN
        ──────────────────────────────────────
        USE WHEN: showing composition/parts-of-whole compared across categories or time.

        WARNING: ALWAYS requires group_by. Without it the chart is INVALID. Do not generate it.

        "chart_type": "stacked_column"
        "x": category or time field
        "y": numeric measure (what gets stacked)
        "group_by": categorical field defining each stack layer (MANDATORY)
        "filter": {{ "field": "dot.path", "value": "exact_value" }} | null

        RULES:
        - Data MUST have one row per (x_value, group_by_value) combination AFTER filtering
        - group_by is the field that splits rows into stack segments
        - stacked_column without group_by -> INVALID, remove or downgrade to column

        ──────────────────────────────────────
        WHEN TO USE filter vs group_by
        ──────────────────────────────────────

        The data may have MULTIPLE categorical dimensions.
        Decide: should a dimension be a FILTER or a GROUP_BY?

        group_by = dimension you want as SEPARATE SERIES (stacks, lines, bar groups)
        filter   = dimension you want to RESTRICT to one specific value

        REAL EXAMPLE — Data has: status_month, type (schedule/scope/spend),
                    dominant_status (on_track/at_risk/compromised), count

        Option A — All types combined, stacked by dominant_status:
        x = status_month
        group_by = dominant_status
        filter = null
        -> ALL types summed, stacked by on_track/at_risk/compromised  [PREFERRED - 1 chart]

        Option B — Only "schedule" rows, stacked by dominant_status:
        x = status_month
        group_by = dominant_status
        filter = {{ "field": "type", "value": "schedule" }}
        -> ONLY schedule rows, stacked by on_track/at_risk/compromised

        Option C — All statuses combined, stacked by type:
        x = status_month
        group_by = type
        filter = null
        -> ALL statuses summed, stacked by schedule/scope/spend  [PREFERRED - 1 chart]

        DECISION RULE — ALWAYS prefer fewer charts:
        - If one chart with group_by captures the full picture -> USE THAT.
        - Only create per-filter charts if the combined view is unreadable (> 5 series)
        OR the intent specifically isolates one dimension.
        - NEVER create multiple charts that are structurally identical but filtered to
        different values. Combine them into one chart using group_by instead.

        ──────────────────────────────────────
        PIE
        ──────────────────────────────────────
        "chart_type": "pie"
        "x": category label field (slice name)
        "y": numeric value field (slice size)
        "group_by": null   <- ALWAYS null for pie
        "filter": {{ "field": "...", "value": "..." }} | null

        RULES:
        - group_by MUST be null
        - NEVER use pie if there are more than 6 unique x values

        ──────────────────────────────────────
        SCATTER
        ──────────────────────────────────────
        "chart_type": "scatter"
        "x": numeric field
        "y": numeric field
        "z": null
        "group_by": null or optional categorical
        "filter": null

        RULES: x and y MUST be numeric fields

        ──────────────────────────────────────
        BUBBLE
        ──────────────────────────────────────
        "chart_type": "bubble"
        "x": numeric field
        "y": numeric field
        "z": numeric field (controls bubble size, REQUIRED)
        "group_by": null or optional
        "filter": null

        RULES: x, y, z ALL must be numeric fields

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        GROUP_BY DETECTION RULE (CRITICAL)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Before finalizing any chart:

        STEP 1: Examine the data rows at data_source (after any filter is applied).
        STEP 2: Check whether the x field value repeats across rows.
                Example: "status_month" = "2025-10-01" appears 3 times -> x repeats.
        STEP 3: If x repeats AND a categorical dimension exists that explains the split:
                -> Set group_by = that EXACT categorical field name from the data
                -> group_by MUST be a real field name — never a concatenation or derivation
                -> Without group_by, executor collapses all rows into one flat series
                    and the chart will be WRONG.
        STEP 4: If the split requires TWO dimensions (e.g. type + dominant_status):
                -> Create TWO separate charts, each using ONE of those fields as group_by
                -> Do NOT invent a combined field name
        STEP 5: If x does NOT repeat -> group_by = null is fine.

        For stacked_column: group_by is ALWAYS required. No exceptions.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        DUPLICATE CHART DETECTION (CRITICAL)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Before generating multiple charts, ask:
        "Would these charts show IDENTICAL structure, just filtered to different values?"

        If YES -> combine into ONE chart using group_by instead of filter.

        WRONG (3 identical charts):
        Chart 1: stacked_column, filter type=schedule, group_by=dominant_status
        Chart 2: stacked_column, filter type=scope,    group_by=dominant_status
        Chart 3: stacked_column, filter type=spend,    group_by=dominant_status

        CORRECT (1 clear chart):
        Chart 1: stacked_column, group_by=type, filter=null
        -> x=month, stacks=schedule/scope/spend

        Only use per-filter charts when:
        - Combined chart would have > 5 series (unreadable)
        - Intent specifically requires isolating one dimension
        - Different filter values have fundamentally different scales


        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        FIELD NAMES MUST EXIST VERBATIM (CRITICAL)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Every field you reference in x, y, z, group_by, filter.field
        MUST be a real field name that exists verbatim in the data rows.

        ❌ FORBIDDEN — inventing combined/derived field names:
            group_by = "type_dominant_status"       <- does not exist
            group_by = "type_and_status"            <- does not exist
            group_by = "status_type_combined"       <- does not exist
            x = "month_label"                       <- does not exist

        ✅ CORRECT — use only fields visible in the snapshot rows:
            group_by = "dominant_status"            <- real field
            group_by = "type"                       <- real field
            x = "status_month"                      <- real field
            y = "status_update_count"               <- real field

        RULE: If the data has two dimensions you want to split by (e.g. type AND
        dominant_status), you MUST pick ONE as group_by and either:
        - ignore the other (if the combined chart is still meaningful), OR
        - use filter to restrict to a specific value of the other dimension.

        You CANNOT combine two fields into one group_by. The executor has no
        ability to create derived fields — it resolves paths as-is.

        PRACTICAL EXAMPLE for status data with: type, dominant_status, status_month

        WRONG:
        group_by = "type_dominant_status"    <- invented, executor returns None for every row

        CORRECT OPTION A (group by status, ignore type):
        x = "status_month"
        group_by = "dominant_status"
        filter = null
        -> 3 series: on_track / at_risk / compromised (all types summed)

        CORRECT OPTION B (group by type, ignore status):
        x = "status_month"
        group_by = "type"
        filter = null
        -> 3 series: schedule / scope / spend (all statuses summed)

        CORRECT OPTION C (group by status, filter to one type):
        x = "status_month"
        group_by = "dominant_status"
        filter = {{ "field": "type", "value": "schedule" }}
        -> 3 series for schedule only

        For a request asking for BOTH type and status breakdown:
        -> Create 2 charts using OPTIONS A and B above (one per dimension)
        -> This is the ONLY valid way to show both dimensions simultaneously

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PATH RULES (CRITICAL — ARRAY HANDLING)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        NEVER use numeric indexing (.0, .1, [0], etc.)
        ALWAYS use direct field paths.
        data_source MUST point to the array level, not the parent.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        TITLE QUALITY
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Chart titles must:
        - Be human-readable and describe the insight
        - Be concise (4-8 words)
        - Avoid raw field names or technical prefixes

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        OUTPUT FORMAT (STRICT JSON)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        {{
            "rationale": ["Brief professional explanation of chart choices"],
            "rationale_for_user_visiblity": ["very few phrases. very compact"],
            "charts": [
                {{
                    "chart_id": "string",
                    "intent": "comparison | ranking | trend | distribution | composition | relationship",
                    "chart_type": "line | area | column | bar | stacked_column | pie | scatter | bubble",
                    "data_source": "dot.path",
                    "x": "dot.path",
                    "y": "dot.path",
                    "z": "dot.path | null",
                    "group_by": "dot.path | null",
                    "filter": {{ "field": "dot.path", "value": "exact_string_or_number" }},
                    "title": "string",
                    "sort": "asc | desc | null",
                    "limit": "number | null"
                }}
            ]
        }}

        Note: "filter" must be either a JSON object with "field" and "value" keys, or null.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        EVIDENCE SNAPSHOT (READ-ONLY)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        {MyJSON.dumps(evidence_snapshot)}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        MANDATORY FINAL VALIDATION CHECKLIST
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Before returning JSON, verify EVERY chart:

        [ ] Chart adds clear value within 5 seconds of viewing
        [ ] Chart type matches analytical intent
        [ ] No computation or aggregation is implied
        [ ] stacked_column -> group_by is set (not null). If missing -> REMOVE.
        [ ] x values repeat in data (after filter) -> group_by is set. If missing -> fix or remove.
        [ ] Multiple charts differ only by filter value -> COMBINE into one with group_by.
        [ ] pie -> group_by is null AND unique x values <= 6
        [ ] bubble -> x, y, z are ALL valid numeric field paths
        [ ] scatter -> x, y are numeric
        [ ] filter.value matches an EXACT value present in the data
        [ ] No numeric indexing in any path (x, y, z, group_by, data_source, filter.field)
        [ ] data_source points to the array level, not the parent

        Return ONLY valid JSON. No explanation outside the JSON.
        """

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user="Generate chart plan. Output JSON only in the given format. Select the correct chart type and structure per the data contracts.",
        )

        llm_output = ""
        printed = set()
        import re

        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_opts,
            "charts::interpreter"
        ):
            llm_output += chunk
            if '"rationale_for_user_visiblity"' in llm_output:
                match = re.search(r'"rationale_for_user_visiblity"\s*:\s*\[([^\]]*)', llm_output, re.DOTALL)
                if match:
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    for t in items:
                        if t not in printed:
                            print(f"🧠 Thought: {t}")
                            event_bus.dispatch("THOUGHT_AI_DAO", {"message": t, "size": len(printed)}, session_id=self.session_id)
                            printed.add(t)

        print("chart interpreter -- ", llm_output)

        return extract_json_after_llm(llm_output)


class ChartExecutor:
    """
    Deterministic chart projection engine.
    Produces Highcharts-compatible JSON.

    Supports:
    - Single-series charts (line, area, column, bar, pie, scatter, bubble)
    - Multi-series charts via group_by (stacked_column, grouped column, multi-line)
    - Row-level filtering via filter: { "field": "...", "value": "..." }
    - Automatic stacking flag for stacked_column
    - Bubble charts with x, y, z numeric point data
    - Pie charts with { name, y } point data
    - Deduplication for single-series x-axis
    - Summation when (x, group) pair appears more than once
    """

    STACKED_TYPES = {"stacked_column"}

    HC_TYPE_MAP = {
        "stacked_column": "column",
        "line":    "line",
        "area":    "area",
        "column":  "column",
        "bar":     "bar",
        "pie":     "pie",
        "scatter": "scatter",
        "bubble":  "bubble",
    }

    def execute(self, *, analytical_truth: dict, chart_plan: dict) -> dict:
        output = []

        for chart in chart_plan.get("charts", []):
            try:
                result = self._build_chart(analytical_truth, chart)
                if result:
                    output.append(result)
            except Exception as e:
                print(f"⚠️  ChartExecutor: Failed to build chart '{chart.get('chart_id')}': {e}")

        try:
            with open("chart_data.json", "w") as f:
                MyJSON.dump(output, f)
        except Exception:
            pass

        return {"charts": output}

    # ── Main dispatcher ────────────────────────────────────────────────────

    def _build_chart(self, analytical_truth: dict, chart: dict) -> dict | None:
        chart_type = chart.get("chart_type", "column")
        chart_id   = chart.get("chart_id", "unknown")
        title      = chart.get("title", "")
        group_by   = chart.get("group_by")          # dot-path string or None
        filter_cfg = chart.get("filter")             # { field, value } or None
        hc_type    = self.HC_TYPE_MAP.get(chart_type, chart_type)
        is_stacked = chart_type in self.STACKED_TYPES

        # ── Resolve rows from truth ────────────────────────────────────────
        rows = self._resolve_path(analytical_truth, chart["data_source"]) or []

        # Unwrap accidental double-wrapping [[...]]
        if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], list):
            print(f"ℹ️  Chart '{chart_id}': Auto-unwrapping nested single-item array")
            rows = rows[0]

        if not isinstance(rows, list):
            rows = [rows] if rows else []

        # ── Apply row filter ───────────────────────────────────────────────
        if filter_cfg and isinstance(filter_cfg, dict):
            filter_field = filter_cfg.get("field")
            filter_value = filter_cfg.get("value")
            if filter_field and filter_value is not None:
                before = len(rows)
                rows = [
                    row for row in rows
                    if str(self._resolve_path(row, filter_field)) == str(filter_value)
                ]
                print(f"ℹ️  Chart '{chart_id}': filter '{filter_field}={filter_value}' "
                      f"reduced {before} -> {len(rows)} rows")

        if not rows:
            print(f"⚠️  Chart '{chart_id}': No data rows after filtering. Skipping.")
            return None

        # ── Route to builder ───────────────────────────────────────────────
        if chart_type == "bubble":
            return self._build_bubble(chart, rows, hc_type, title)

        if chart_type == "pie":
            return self._build_pie(chart, rows, hc_type, title)

        if group_by:
            return self._build_multi_series(chart, rows, hc_type, title, is_stacked, group_by)

        return self._build_single_series(chart, rows, hc_type, title, is_stacked)

    # ── Builders ───────────────────────────────────────────────────────────

    def _build_single_series(self, chart, rows, hc_type, title, is_stacked):
        """
        Single flat series.
        Deduplicates x values (first-occurrence wins).
        """
        x_vals = []
        y_vals = []
        seen_x: set = set()

        for row in rows:
            x = self._resolve_path(row, chart["x"])
            y = self._resolve_path(row, chart["y"])
            x_str = str(x) if x is not None else "Unknown"

            if x_str not in seen_x:
                x_vals.append(x_str)
                y_vals.append(y)
                seen_x.add(x_str)

        # Sort by x — default asc (important for time-series axes)
        sort = chart.get("sort", "asc")
        if sort in ("asc", "desc"):
            paired = sorted(zip(x_vals, y_vals), key=lambda p: p[0], reverse=(sort == "desc"))
            x_vals, y_vals = [p[0] for p in paired], [p[1] for p in paired]

        return {
            "chart_id": chart["chart_id"],
            "type": hc_type,
            "stacking": "normal" if is_stacked else None,
            "title": title,
            "xAxis": {"categories": x_vals},
            "series": [{"name": title, "data": y_vals}],
        }

    def _build_multi_series(self, chart, rows, hc_type, title, is_stacked, group_by):
        """
        Pivot rows into multiple named series using group_by.

        - Preserves x-axis category order (first appearance).
        - Fills missing (x, group) pairs with 0.
        - SUMS values if the same (x, group) pair appears more than once.
          This handles cases where the data hasn't been fully pre-aggregated.
        """
        categories_ordered: list[str] = []
        seen_cats: set = set()
        # { group_value: { x_value: accumulated_y } }
        grouped: dict[str, dict[str, float]] = {}

        for row in rows:
            x = self._resolve_path(row, chart["x"])
            y = self._resolve_path(row, chart["y"])
            g = self._resolve_path(row, group_by)

            x_str = str(x) if x is not None else "Unknown"
            g_str = str(g) if g is not None else "Other"

            if x_str not in seen_cats:
                categories_ordered.append(x_str)
                seen_cats.add(x_str)

            if g_str not in grouped:
                grouped[g_str] = {}

            # Sum if the same (x, group) pair appears multiple times
            prev = grouped[g_str].get(x_str, 0)
            grouped[g_str][x_str] = prev + (y if isinstance(y, (int, float)) else 0)

        # Sort categories — default asc (important for time-series x-axes)
        sort = chart.get("sort", "asc")
        if sort == "desc":
            categories_ordered = sorted(categories_ordered, reverse=True)
        elif sort != "none":
            categories_ordered = sorted(categories_ordered)  # asc is default

        series = [
            {
                "name": g_val,
                "data": [value_map.get(cat, 0) for cat in categories_ordered],
            }
            for g_val, value_map in grouped.items()
        ]

        return {
            "chart_id": chart["chart_id"],
            "type": hc_type,
            "stacking": "normal" if is_stacked else None,
            "title": title,
            "xAxis": {"categories": categories_ordered},
            "series": series,
        }

    def _build_pie(self, chart, rows, hc_type, title):
        """
        Pie chart: each row becomes a {{ name, y }} point.
        """
        points = [
            {
                "name": str(self._resolve_path(row, chart["x"]) or "Unknown"),
                "y": v if isinstance((v := self._resolve_path(row, chart["y"])), (int, float)) else 0,
            }
            for row in rows
        ]

        return {
            "chart_id": chart["chart_id"],
            "type": hc_type,
            "stacking": None,
            "title": title,
            "xAxis": {"categories": []},
            "series": [{"name": title, "data": points}],
        }

    def _build_bubble(self, chart, rows, hc_type, title):
        """
        Bubble chart: each row becomes a {{ x, y, z }} numeric point.
        """
        z_path = chart.get("z")
        points = []

        for row in rows:
            x = self._resolve_path(row, chart["x"])
            y = self._resolve_path(row, chart["y"])
            z = self._resolve_path(row, z_path) if z_path else None
            points.append({
                "x": x if isinstance(x, (int, float)) else 0,
                "y": y if isinstance(y, (int, float)) else 0,
                "z": z if isinstance(z, (int, float)) else 0,
            })

        return {
            "chart_id": chart["chart_id"],
            "type": hc_type,
            "stacking": None,
            "title": title,
            "xAxis": {"categories": []},
            "series": [{"name": title, "data": points}],
        }

    # ── Path resolver ───────────────────────────────────────────────────────

    def _resolve_path(self, obj, path):
        """
        Resolve a dot-notation path against a nested dict/list structure.

        Behaviour:
        - Navigates dicts by key name.
        - Handles numeric list indices as a defensive fallback (logs a warning).
        - Auto-unwraps single-item lists at the resolved leaf.
        - Returns None if any segment cannot be resolved.
        """
        if not path:
            return None

        path_parts = path.split(".")

        if any(part.isdigit() for part in path_parts):
            print(
                f"⚠️  CHART PLAN VIOLATION: Numeric indexing detected in path '{path}'. "
                f"data_source should point to the array directly."
            )

        cur = obj
        for part in path_parts:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list):
                try:
                    idx = int(part)
                    cur = cur[idx] if 0 <= idx < len(cur) else None
                except (ValueError, TypeError):
                    return None
            else:
                return None

        # Auto-unwrap single-item leaf arrays
        if isinstance(cur, list) and len(cur) == 1:
            return cur[0]

        return cur


class ChartExportService:
    """
    Deterministic chart export layer.
    Exports chart-ready JSON to a temp file.
    NO analytics. NO transformation.
    """

    def export_to_json(self, chart_output: Dict[str, Any]) -> str:
        """Returns local file path of generated JSON file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            json.dump(chart_output, tmp, indent=2)
            return tmp.name
        