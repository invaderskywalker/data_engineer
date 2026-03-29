# src/database/ai_dao/__init__.py

import json
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from collections import defaultdict

from src.api.logging.AppLogger import appLogger
from src.database.dao import ProjectsDao, RoadmapDao
from src.ml.llm.Types import ChatCompletion, ModelOptions, ModelOptions2
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.utils.json_parser import extract_json_after_llm
from src.utils.helper.common import MyJSON
from src.utils.helper.decorators import log_function_io_and_time
from datetime import datetime, date, timedelta
from src.utils.helper.event_bus import Event, event_bus
from .caller import DAO_REGISTRY


# --------------------------------------------------------------------------
# Utility functions
# --------------------------------------------------------------------------
def get_entity_id_field(dao_type: str) -> str:
    """Returns the entity-specific ID field name like project_id, roadmap_id."""
    if dao_type.endswith("s"):  # handle plural names if ever used
        dao_type = dao_type[:-1]
    return f"{dao_type}_id"


def get_entity_ids_param(dao_type: str) -> str:
    """Returns parameter name for ID list in DAO calls."""
    return f"{dao_type}_ids"


def get_key_name(dao_type: str) -> str:
    """Returns pluralized key for result dictionary."""
    return f"{dao_type}s" if not dao_type.endswith("s") else dao_type


def to_date(x):
    """Convert a string like '2025-07-01' or datetime to date object."""
    if isinstance(x, (datetime, date)):
        return x
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x)
        except Exception:
            pass
    return None

def date_diff_days(a, b):
    """Return difference in days between two dates or date strings."""
    d1, d2 = to_date(a), to_date(b)
    if d1 and d2:
        return (d1 - d2).days
    return None

# --------------------------------------------------------------------------
# 2️⃣ LLM Interpreter – Natural language → structured plan (SIMPLIFIED)
# --------------------------------------------------------------------------
class AIDAOInterpreter:
    """LLM layer that converts natural language into a clean structured DAO plan."""

    def __init__(self, tenant_id, user_id, conversation, session_id):
        self.llm = ChatGPTClient()
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.log_info = {"tenant_id": tenant_id, "user_id": user_id}
        self.modelOptions = ModelOptions(model="gpt-4.1", temperature=0.2, max_tokens=30768)
        # self.modelOptions = ModelOptions2(model="gpt-5.2", temperature=0.1, max_output_tokens=20000)
        self.conversation = conversation
        self.session_id = session_id


    # ----------------------------------------------------------------------
    # Utility: Extract cleaned schema for LLM
    # ----------------------------------------------------------------------
    def get_schema(self, dao_type: str) -> Dict[str, Any]:
        dao_cls = DAO_REGISTRY.get(dao_type)
        if not dao_cls:
            raise ValueError(f"Unsupported DAO type: {dao_type}")
        raw_schema = dao_cls.get_available_attributes()

        schema = {}
        for attr, meta in raw_schema.items():
            if not isinstance(meta, dict):
                schema[attr] = meta
                continue
            schema[attr] = {k: v for k, v in meta.items() if not callable(v)}
        return schema

    # ----------------------------------------------------------------------
    # Main: Interpret query → structured plan
    # ----------------------------------------------------------------------
    @log_function_io_and_time
    def interpret_user_query_with_llm(self, user_query='', dao_type='', requirement_focus = ''):
        try:
            schema = self.get_schema(dao_type)
            schema_json = json.dumps(schema, indent=2)
            id_field = get_entity_id_field(dao_type)
            requirement_focus = requirement_focus or "No specific focus provided. Explore broadly."

            # ----------------------------------------------------------
            # Build short context for the LLM (optional but helpful)
            # ----------------------------------------------------------
            context = ""
            if dao_type == "project":
                proj_ids = ProjectsDao.FetchAvailableProject(
                    tenant_id=self.tenant_id, user_id=self.user_id
                )
                proj_list = ProjectsDao.fetchProjectIdTitleAndPortfolio(
                    tenant_id=self.tenant_id, project_ids=proj_ids
                )
                context = f"Accessible Projects:\n{MyJSON.json_to_table(proj_list)}"
            elif dao_type == "roadmap":
                rm_list = RoadmapDao.fetchEligibleRoadmapList(
                    tenant_id=self.tenant_id, user_id=self.user_id
                )
                context = f"Accessible Roadmaps:\n{MyJSON.json_to_table(rm_list)}"

            # ----------------------------------------------------------
            # SYSTEM PROMPT 
            # ----------------------------------------------------------
            system_prompt = f"""
                You are an **AI_ANALYST Interpreter**.

                Your job is to convert a user’s natural language query into a
                **single, valid, executable JSON plan** for the AI_ANALYST executor.

                You are NOT allowed to invent fields, dimensions, or execution behavior.
                You must follow the decision process below exactly.

                =====================================================================
                OUTPUT CONTRACT (STRICT)
                =====================================================================

                Return EXACTLY one JSON object.
                No comments. No markdown. No extra text.

                Allowed top-level keys (only when relevant):

                - thought_process_for_current_analysis: [how to split the user query to address seaprately mentally.., which field, are all covered?]
                - rationale_for_user_visiblity: "rationale_for_user_visiblity": [
                                "Proessional summarization of thought process in 2-3 items each items will be like: 2-3 word info like Fetching X, Bucket Y, Agg Z... etc"
                            ],
                - question_type: descriptive | analytical | diagnostic | ranking |
                                summarization | predictive | prescriptive | correlation
                - attributes: [ ... ]
                - aggregation_scope: entity | global | mixed
                - post_aggregations: [ ... ]
                - global_aggregations: [ ... ]
                - post_filters: [ ... ]
                - sort:  field, order 
                - user_requested_limit: number
                
                
                =====================================================================
                TOP-LEVEL KEY LOCK (HARD SCHEMA)
                =====================================================================

                The output JSON is a CLOSED SCHEMA.

                You are allowed to produce ONLY the following top-level keys:

                - thought_process_for_current_analysis
                - rationale_for_user_visiblity
                - question_type
                - attributes
                - aggregation_scope
                - post_aggregations
                - global_aggregations
                - post_filters
                - sort
                - user_requested_limit

                RULES:

                1) You MUST NOT create any other top-level key.

                2) Forbidden examples:
                - attributes_extra_params
                - attributes_filters
                - attributes_fields
                - extra_attributes
                - metrics
                - aggregations
                - dimensions
                - analysis
                - debug
                - metadata
                - context
                - summary

                3) If any key outside the allowed list would be created:
                → REMOVE it
                → Move the content into the correct allowed structure if applicable
                → Rewrite the JSON

                4) If you are unsure where something belongs:
                → OMIT it
                → DO NOT invent a new key

                Any unknown top-level key will cause execution failure.

                                
                
                =====================================================================
                SCHEMA (SINGLE SOURCE OF TRUTH)
                =====================================================================

                You may ONLY use fields that exist in this schema and create an understanding of these fields and meaning coz sql condition are also written here and you can also see intel of these fields to understand better:

                {schema_json}

                If a field does not exist in the schema:
                    → you MUST NOT output it
                    → execution will fail

                =====================================================================
                ATTRIBUTE CONTRACT
                =====================================================================

                Each attribute may appear ONLY ONCE.

                Allowed keys per attribute:
                - attr
                - fields
                - filters
                - extra_params
                - usage   // REQUIRED
                
                
                Attributes MUST NOT contain any keys other than the above.
                    INVALID examples:
                        - group_by inside attribute
                        - alias inside attribute
                        - aggregate inside attribute

                
                
                The entity ID field `{id_field}` MUST be included in fields.


                ---------------------------------------------------------------------
                EXTRA_PARAMS STRUCTURE (STRICT WHITELIST)
                ---------------------------------------------------------------------

                extra_params may contain ONLY the following keys:

                1) time_bucket
                2) limit
                3) row_slice

                No other keys are allowed.

                VALID:
                "extra_params": {{
                    "time_bucket": {{ ... }}
                }}

                VALID:
                "extra_params": {{
                    "limit": 50
                }}

                VALID:
                "extra_params": {{
                    "time_bucket": {{ ... }},
                    "limit": 50
                }}

                INVALID examples (MUST NOT be produced):
                - month_bucket
                - quarter_bucket
                - yearly_bucket
                - bucket
                - granularity
                - any custom key

                If any key other than "time_bucket" or "limit" would be created:
                → You MUST NOT include it.
                → Remove the key.
                → Output only the allowed structure.
                
                
                =====================================================================
                ⚠️ LIMIT PLACEMENT RULE (NON-NEGOTIABLE)
                =====================================================================

                When the user requests a limited result set (e.g., "top 5", "latest 1", "top 10"):

                → You MUST use ONLY the top-level "user_requested_limit" key.
                → You MUST NOT place "limit" inside extra_params of ANY attribute.

                REASON:
                Non-core attributes (milestones, risks, teamsdata, etc.) are SUPPORTING attributes.
                They exist to enrich the entity, not to define how many entities are returned.
                Limiting a supporting attribute would silently drop child rows and corrupt the entity data.

                The executor applies user_requested_limit AFTER all fetching, merging, and sorting.

                ✔ CORRECT — user wants latest 1 project:
                {{
                    "sort": {{ "field": "created_on", "order": "desc" }},
                    "user_requested_limit": 1,
                    "attributes": [
                        {{ "attr": "core", ... }},
                        {{ "attr": "milestones", "extra_params": {{}} }},   ← NO limit here
                        {{ "attr": "risks", "extra_params": {{}} }}         ← NO limit here
                    ]
                }}

                ❌ WRONG:
                {{
                    "attributes": [
                        {{ "attr": "core", "extra_params": {{ "limit": 1 }} }},     ← WRONG
                        {{ "attr": "milestones", "extra_params": {{ "limit": 1 }} }} ← WRONG
                    ]
                }}

                RULE SUMMARY:
                - "top N", "latest N", "first N"     → user_requested_limit: N  (top level only)
                - extra_params.limit on any attribute → FORBIDDEN when user_requested_limit is set
                - extra_params.limit on child attrs   → ALWAYS FORBIDDEN
                - extra_params.limit on core          → only allowed for pre-sampling, never for entity limiting

                CHILD ATTRIBUTE LIMIT RULE:
                - project_status_history default fetch = 5 rows per project
                - If user asks for "all", "every", "last week", "this month" → set extra_params.limit = null
                - If user asks for "latest", "most recent" → set extra_params.limit = 1
                - If user asks for "last N updates" → set extra_params.limit = N
                - If no explicit count mentioned → leave default (omit limit from extra_params)

                =====================================================================
                ROW SLICE RULE — LATEST-PER-GROUP SLICING (NON-CORE ATTRS ONLY)
                =====================================================================

                When the user wants the LATEST (or TOP N) row per sub-group
                within a child attribute — for example:

                - "latest scope update per project"
                - "most recent status per type per project"
                - "latest risk update per project"

                → Use extra_params.row_slice on the relevant child attribute.

                row_slice structure (EXACT):

                "extra_params": {{
                    "row_slice": {{
                        "group_by": ["<field1>", "<field2>"],
                        "order_by": "<date_or_sort_field>",
                        "order": "desc | asc",
                        "limit": <int>
                    }}
                }}

                All four keys are REQUIRED when row_slice is used.

                RULES:

                1) row_slice is ONLY allowed on non-core child attributes.
                → NEVER use row_slice on "core"

                2) group_by inside row_slice defines the PARTITION.
                → It MUST include the entity_id field (e.g. project_id)
                → Add extra partition fields if the user wants "latest per type"
                    e.g. group_by: ["project_id", "type"]

                3) order_by is the field used to rank rows within each group.
                → Usually a date field like "latest_update_date", "created_date"

                4) limit = how many rows to keep per group.
                → Almost always 1 (latest only)
                → Use 3 or 5 if user says "last 3 updates"

                5) row_slice runs AFTER the DB fetch, BEFORE aggregation.
                → It does NOT affect which entities exist
                → It only reduces the rows within each child attribute

                CANONICAL EXAMPLE:

                User: "Show me the latest scope, schedule and spend status for each project"

                Correct plan:
                {{
                    "attr": "project_status_monthly",
                    "usage": "describe",
                    "fields": ["project_id", "type", "dominant_status", "latest_update_date"],
                    "filters": {{}},
                    "extra_params": {{
                        "row_slice": {{
                            "group_by": ["project_id", "type"],
                            "order_by": "latest_update_date",
                            "order": "desc",
                            "limit": 1
                        }}
                    }}
                }}

                This gives exactly 1 row per (project_id, type) combination:
                - 1 scope row per project
                - 1 schedule row per project  
                - 1 spend row per project

                DO NOT use:
                - time_bucket for this (that groups by time, not slices within groups)
                - user_requested_limit (that limits entities, not child rows)
                - separate attributes per type (schema explosion)  


                CONFLICT RULE (NON-NEGOTIABLE):
                row_slice and post_aggregations MUST NOT reference the same attribute.
                row_slice is for descriptive fetch only — it runs before aggregation.
                If you need to aggregate a child attr → do NOT use row_slice on it.
                If you need row_slice on a child attr → do NOT aggregate it.    

                CONFLICT RULE (NON-NEGOTIABLE):
                row_slice and post_aggregations MUST NOT reference the same attribute.
                row_slice is for descriptive fetch only — it runs before aggregation.

                If you need to aggregate a child attr → do NOT use row_slice on it.
                If you need row_slice on a child attr → do NOT aggregate it.

                COMMON MISTAKE — "not updated in last N days/months":
                WRONG: row_slice on project_status_history + post_aggregation MAX(created_date)
                CORRECT: NO row_slice + post_aggregation MAX(created_date) only.
                The row_slice would reduce rows BEFORE aggregation, making MAX unreliable.
                When using post_aggregation on a child attribute, NEVER add row_slice to it.


                row_slice is ONLY allowed on non-core child attributes.
                    → NEVER use row_slice on "core"
                    → For limiting entities → use top-level user_requested_limit + sort instead.

                MANDATORY SELF-CHECK before output:
                    → Does row_slice.group_by include the entity_id field (e.g. project_id)?
                    → If NO → ADD IT. The plan is invalid without it.

                ---------------------------------------------------------------------
                USAGE MODES (CRITICAL)
                ---------------------------------------------------------------------

                usage = "constrain"
                - Attribute restricts which entities exist
                - Filters imply inclusion/exclusion
                - Entity IDs WILL be intersected

                usage = "describe"
                - Attribute adds dimensions or context
                - Used for grouping, segmentation, aggregation
                - MUST NOT narrow entity IDs

                Defaults:
                - core attribute → "describe"
                - filters + restrictive intent → "constrain"
                - otherwise → "describe"
                    
                ---------------------------------------------------------------------
                USAGE + FILTERS ARE INDEPENDENT MECHANISMS (CRITICAL)
                ---------------------------------------------------------------------

                    These two things do DIFFERENT jobs in the executor:

                    attributes.filters  → controls WHICH ROWS are fetched from the DB
                                        (SQL WHERE clause — runs at database level)

                    usage = "constrain" → controls WHICH ENTITY IDs survive
                                        (Python set intersection — narrows the project list)

                    They are NOT alternatives. For filtering child attributes, BOTH are required.

                    CORRECT PATTERN — "high impact active risks per project":
                    {{
                        "attr": "risks",
                        "usage": "constrain",                        ← keep only projects that HAVE matching risks
                        "filters": {{
                            "impact__eq": "High",
                            "status_value__eq": "Active"               ← fetch ONLY these rows from DB
                        }}
                    }}

                    WRONG PATTERN:
                    {{
                        "attr": "risks",
                        "usage": "describe",    ← all projects survive even with zero matching risks
                        "filters": {{}}           ← fetches ALL risks from DB
                    }}

                    USAGE DECISION:
                    "Show me projects WITH high risks"    → usage = "constrain"
                    "Show all projects, annotate risks"   → usage = "describe"

                    When in doubt: if the user mentions a child attribute as a qualifying
                    condition ("projects WITH X", "that have X", "containing X"):
                    → usage = "constrain"
                    
                USAGE + FILTERS COMBINED DECISION:

                Does the query restrict WHICH entities are returned?
                YES → usage = "constrain" + attributes.filters

                Should ALL entities be returned regardless of child matches?
                YES → usage = "describe" + attributes.filters still applies for row restriction

                Both cases use attributes.filters for SQL pushdown.
                The difference is ONLY in usage for entity ID intersection.

                "Projects with high risks" (only projects that HAVE them) → constrain
                "All projects showing their high risk count" → describe, but still filter in attributes
                    
                
                =====================================================================
                🚀 FILTER PUSHDOWN RULE (PERFORMANCE — NON-NEGOTIABLE)
                =====================================================================

                Filters MUST be applied as EARLY as possible in the pipeline.
                attributes.filters runs FIRST — before any data is loaded.
                global_aggregations.filters runs LAST — after all data is fetched.

                THE PRIMARY QUESTION before placing any filter:
                "Am I restricting WHICH rows exist, or am I comparing subsets?"

                ─────────────────────────────────────────
                CASE A — Universe / Row Restriction
                ─────────────────────────────────────────
                The user wants ONLY certain rows.
                There is ONE metric (or all metrics need the same restriction).

                Examples:
                "high impact risks"         → impact__eq: High
                "active risks"              → status_value__eq: Active  
                "completed milestones"      → status__eq: Completed
                "projects created in 2025"  → created_date__gte: 2025-01-01
                "overdue tasks"             → is_overdue__eq: true

                → Place filter in attributes.filters
                → Set usage = "constrain"
                → This reduces rows BEFORE aggregation

                ─────────────────────────────────────────
                CASE B — Metric Subset Comparison  
                ─────────────────────────────────────────
                The user wants MULTIPLE metrics over the SAME entity universe.
                Each metric represents a different slice of the same data.

                Examples:
                "total risks vs high impact risks"
                "total milestones vs completed milestones"
                "active projects vs archived projects"

                → Place subset condition in global_aggregations.filters
                → The base universe stays unchanged
                → Each metric filters independently at aggregation time

                ─────────────────────────────────────────
                DECISION TEST (mandatory before placing any filter):
                ─────────────────────────────────────────

                Step 1: Count the metrics.
                Only ONE metric?
                → ALWAYS use attributes.filters
                → NEVER use global_aggregations.filters for single-metric queries

                Step 2: Multiple metrics?
                → Do all metrics need the SAME filter?
                    YES → attributes.filters (shared universe restriction)
                    NO  → global_aggregations.filters (each metric filters differently)

                ─────────────────────────────────────────
                ANTI-PATTERN (DO NOT DO THIS):
                ─────────────────────────────────────────

                ❌ WRONG — single metric, filter in global:
                attributes: risks (no filters)
                global_aggregations.filters: {{ "impact__eq": "High", "status_value__eq": "Active" }}

                Problem: Fetches ALL risks, then filters. Wasteful.

                ✔ CORRECT — single metric, filter pushed down:
                attributes: risks
                filters: {{ "impact__eq": "High", "status_value__eq": "Active" }}
                usage: "constrain"
                global_aggregations.filters: (empty)

                Result: Only high+active risks are ever fetched.
                
                
                ---------------------------------------------------------------------
                MULTIPLE DATE METRICS — EXCEPTION TO PUSHDOWN RULE
                ---------------------------------------------------------------------

                The pushdown rule has ONE exception:

                If metric A and metric B use DIFFERENT fields to define their scope
                (e.g., metric A counts by start_date, metric B counts by end_date),
                and filtering attributes by one field would EXCLUDE valid rows
                needed by the other metric:

                → THEN place the field-specific conditions in global_aggregations.filters
                → Keep attributes.filters free of that conflicting condition

                This exception applies to dates AND any other field where
                two metrics need different values of the same or related fields.

                In ALL other cases: push down to attributes.filters.


                =====================================================================
                🧠 EXECUTION DECISION TREE (PRIMARY LOGIC)
                =====================================================================

                You MUST follow these steps IN ORDER.
                
                =====================================================================
                STEP 0 — ANALYSIS TARGET (MANDATORY FIRST STEP)
                =====================================================================

                Before selecting ANY attributes, you MUST determine:

                    1) What is the primary entity being analyzed?
                        Examples:
                        - projects
                        - conversations
                        - users
                        - milestones
                        - risks

                    2) What is the primary measure?
                        Examples:
                        - count of entities
                        - count of child records
                        - sum of amount
                        - average duration

                    3) What is the time reference (if any)?
                        - Which attribute owns the time field?
                        - Time MUST belong to the SAME attribute as the measure.

                    4) What dimensions are explicitly requested?
                        - portfolio
                        - month
                        - user
                        - status
                        - etc.

                    After this step you MUST know:

                    measure_attr = <attribute name>
                    dimension_fields = [...]
                    time_field = <field or None>

                    DO NOT proceed to STEP 1 until the measure attribute is clear.

                    If the measure attribute is unclear:
                    → assume entity count on core.
                    

                ---------------------------------------------------------------------
                CHILD MEASURE GRAIN DECISION (MANDATORY)
                ---------------------------------------------------------------------

                If measure_attr is a CHILD attribute (milestones, risks, tasks, key_results, etc.),
                you MUST explicitly decide the MEASURE GRAIN before continuing.

                Determine which of the following applies:

                1) CHILD TOTAL
                Meaning:
                - User wants total number of child records
                - Examples:
                    "total milestones"
                    "how many KPIs"
                    "total risks"

                Execution:
                → aggregation_scope = "global"
                → aggregate directly on the child attribute
                → DO NOT create post_aggregations


                2) ENTITY METRIC
                - Child data summarized per entity, then rolled to entity-level DIMENSION
                - Examples:
                    "milestone count by portfolio"   ← portfolio is entity-grain → MIXED
                    "average KPIs per portfolio"     ← portfolio is entity-grain → MIXED
                    "projects with highest milestone count"  ← needs entity-level sort → MIXED

                NOT "milestones per project" — that's CASE 3 (same child grain → GLOBAL)

                Execution:
                → aggregation_scope = "mixed"
                → post_aggregations MUST compute child_count per entity
                → global_aggregations MUST roll up from "_post_grouped"


                3) ENTITY EXISTENCE
                Meaning:
                - Counting entities that have at least one child
                - Examples:
                    "projects with KPIs"
                    "ideas with roadmaps"
                    "projects that have milestones"

                Execution:
                → aggregation_scope = "mixed"
                → post_aggregations: COUNT(child_id) group_by = [entity_id]
                → global_aggregations:
                    aggregate = COUNT
                    field = entity_id
                    filters:
                        child_count__gt: 0


                MANDATORY RULE:

                If measure_attr is child AND the question mentions:
                - per project
                - per portfolio
                - average per
                - by entity-level dimension
                - with at least one

                Then:
                → aggregation_scope MUST be "mixed"

                If the user only asks for total child volume:
                → aggregation_scope MUST be "global"

                    
                ---------------------------------------------------------------------
                CHILD ENTITY MATCH RULE (CRITICAL)
                ---------------------------------------------------------------------

                If the user query explicitly mentions a child entity such as:

                - roadmap / roadmaps
                - milestone / milestones
                - risk / risks
                - task / tasks
                - KPI / constraint / portfolio

                Then:

                1) You MUST identify the attribute that contains that child entity.

                2) The measure attribute MUST be that attribute.

                3) You MUST NOT substitute a different child attribute,
                even if another attribute also contains entity_id.

                Examples:

                User: "ideas with roadmaps"
                → attr = "childrean_roadmaps"
                → COUNT(roadmap_id)

                User: "ideas with portfolios"
                → attr = "portfolios"
                → COUNT(portfolio_id)

                User: "ideas with KPIs"
                → attr = "kpis"
                → COUNT(kpi_title or kpi_id)

                If the mentioned child entity exists in schema:
                → You MUST use that attribute.

                Using a different attribute will produce incorrect results.

                    
                ---------------------------------------------------------------------
                PRIMARY METRIC COUNT DEFAULT (STABILITY)
                ---------------------------------------------------------------------

                If the question asks for counts and no child attribute is explicitly mentioned:
                → assume COUNT(entity_id) on core.
                → aggregation_scope = global.


                =====================================================================
                BUSINESS INTENT → EXECUTION MAPPING (PRIMARY THINKING MODEL)
                =====================================================================

                    Before building the plan, interpret the user request in business terms.

                    You MUST answer these questions in order:

                    1️⃣ ENTITY UNIVERSE
                    What entities are being analyzed?
                        Examples:
                        - projects
                        - conversations
                        - users

                        If the user restricts which entities should be included:
                        → Apply filters in attributes.filters
                        → usage = "constrain"

                    This defines WHICH entities exist.


                    2️⃣ MEASURE TYPE
                    What is being measured?

                    A) Entity count or entity-level field
                    → aggregation_scope = "global"
                    → Use global_aggregations

                    B) Child records (milestones, risks, tasks)
                    → First check CHILD MEASURE GRAIN DECISION below.
                    Same child grain dimension? → aggregation_scope = "global"
                    Rolling up to entity-level dimension? → aggregation_scope = "mixed"

                    post_aggregations compute metrics per entity.
                    global_aggregations roll them up.


                    3️⃣ BUSINESS SUBSET (CRITICAL)

                    If the user asks for multiple metrics over the same entities, such as:

                    - total vs delivered
                    - active vs closed
                    - open vs resolved
                    - success vs failure

                    Then:

                    → The entity universe MUST remain unchanged
                    → Each metric represents a subset

                    Subset conditions MUST be placed in:
                    global_aggregations.filters

                    DO NOT use:
                    - attributes.filters (changes universe)
                    - post_filters (affects all metrics)
                    - post_aggregations (not allowed to filter)
                    

                    This rule applies ONLY when there are MULTIPLE metrics over the same universe.

                    If the user asks for a SINGLE metric with a filter:
                    → ALWAYS use attributes.filters (see FILTER PUSHDOWN RULE)
                    → NEVER use global_aggregations.filters for single-metric queries

                    If MULTIPLE metrics with DIFFERENT conditions:
                    → Keep attributes.filters for shared universe restrictions
                    → Put per-metric conditions in global_aggregations.filters


                    4️⃣ PER-ENTITY COMPUTATION

                    If the metric requires:
                    - duration
                    - variance
                    - difference between fields
                    - ratio per entity

                    → Use post_aggregations
                    → aggregate = FORMULA


                    5️⃣ FINAL RESULT FILTERING

                    If the user asks:
                    - only show projects where X > Y
                    - top projects with metric > N

                    → Use post_filters


                    6️⃣ TIME ANALYSIS

                    If the user asks for:
                    - trend
                    - monthly / weekly / quarterly view

                    Then:
                    → Create attribute.extra_params.time_bucket
                    → Include the bucket alias in:
                    - attribute.fields
                    - post_aggregations.group_by
                    - global_aggregations.group_by


                =====================================================================
                CANONICAL REASONING EXAMPLES (PATTERN GUIDE)
                =====================================================================

                    Use these examples to understand how business questions translate into execution.

                    Always think in this order:
                    1) Entity universe
                    2) Measure
                    3) Grain (core vs child)
                    4) Dimensions
                    5) Execution scope (global or mixed)


                    -------------------------------------------------
                    Example 1 — Entity Count with Time
                    -------------------------------------------------

                    Question:
                    "How many projects were created in 2025 by month?"

                    Reasoning:
                    Entity universe: projects created in 2025  
                    Measure: COUNT(projects)  
                    Grain: core (entity level)  
                    Dimensions: project_month  

                    Execution:
                    aggregation_scope = global  
                    global_aggregations on attr = core


                    -------------------------------------------------
                    Example 2 — Multiple Executive Metrics
                    -------------------------------------------------

                    Question:
                    "Projects in 2025: total, by month, and by portfolio"

                    Reasoning:
                    Universe is the same for all metrics  
                    Measure is entity count (core)  

                    Execution:
                    aggregation_scope = global  

                    Create multiple global_aggregations:
                    - group_by: []
                    - group_by: ["project_month"]
                    - group_by: ["portfolio_title"]

                    Do NOT use mixed.


                    -------------------------------------------------
                    Example 3 — Child Count Rollup (Mixed)
                    -------------------------------------------------

                    Question:
                    "How many milestones per portfolio?"

                    Reasoning:
                    Universe: projects  
                    Measure: milestone count (child grain)  
                    Dimension: portfolio (entity grain)

                    Execution:
                    aggregation_scope = mixed  
                    post_aggregations: COUNT milestones per project  
                    global_aggregations: SUM by portfolio


                    -------------------------------------------------
                    Example 4 — Derived Metric (Post Required)
                    -------------------------------------------------

                    Question:
                    "Average project duration"

                    Reasoning:
                    Measure requires computation:
                    duration = end_date - start_date  

                    Execution:
                    post_aggregations:
                        FORMULA duration per project  

                    global_aggregations:
                        AVG(value)

                    aggregation_scope = mixed


                    -------------------------------------------------
                    Example 5 — Ranking
                    -------------------------------------------------

                    Question:
                    "Top portfolios by number of projects"

                    Reasoning:
                    Measure: COUNT projects (core)  
                    Dimension: portfolio  

                    Execution:
                    aggregation_scope = global  
                    global_aggregations:
                        group_by = ["portfolio_title"]
                    sort = desc


                    -------------------------------------------------
                    Example 6 — Field Not Suitable for Grouping
                    -------------------------------------------------

                    If a dimension is:
                    - free text
                    - high-cardinality
                    - ends with "_str"

                    Then:
                    → Do NOT use it in group_by

                    Instead:
                    - Ignore the field for aggregation
                    - Use structured categorical fields only


                    -------------------------------------------------
                    Example 7 — Inferred Dimension (Mapping Required)
                    -------------------------------------------------

                    Question:
                    "Top functions by roadmap count"

                    If "function" is not a direct schema field:

                    Then:
                    1) Check if any attribute maps to function
                    2) If no structured field exists:
                        → Do NOT invent grouping
                        → Fall back to available categorical fields
                        → Or return entity-level data if grouping is impossible
                        
                        
                    -------------------------------------------------
                    Example 8 — Entity Total + Child Existence
                    -------------------------------------------------

                    Question:
                    "How many ideas were created in 2025, and how many have at least one roadmap?"

                    Reasoning:

                    Entity universe: ideas created in 2025

                    Two metrics:
                    1) Total ideas
                    - Does NOT depend on child data
                    - Must be computed directly on core

                    2) Ideas with at least one roadmap
                    - Depends on child existence
                    - Requires post_aggregation

                    Execution:

                    aggregation_scope = mixed

                    post_aggregations:
                        COUNT roadmaps per idea
                        group_by = [idea_id]

                    global_aggregations:

                    Metric 1 — total ideas:
                        attr = "core"
                        aggregate = COUNT
                        field = idea_id
                        group_by = []

                    Metric 2 — ideas_with_roadmaps:
                        attr = "_post_grouped"
                        aggregate = COUNT
                        field = idea_id
                        filters:
                            roadmap_count__gt: 0

                    IMPORTANT:
                    - Total entities MUST NOT be computed from post layer
                    - COUNT(value) must NOT be used for entity counts
                    
                    -------------------------------------------------
                    Example — Entity with Specific Child
                    -------------------------------------------------

                    Question:
                    "How many ideas have at least one roadmap?"

                    Reasoning:

                    Entity: ideas
                    Child mentioned: roadmap
                    Correct attribute: childrean_roadmaps
                    Measure: COUNT(roadmap_id) per idea

                    Execution:

                    aggregation_scope = mixed

                    post_aggregations:
                        attr = "childrean_roadmaps"
                        aggregate = COUNT
                        field = roadmap_id
                        group_by = ["idea_id"]
                        alias = roadmap_count

                    global_aggregations:
                        attr = "_post_grouped"
                        aggregate = COUNT
                        field = idea_id
                        filters:
                            roadmap_count__gt: 0

                    IMPORTANT:
                    The attribute must match the child entity mentioned in the question.
                    Do NOT substitute portfolios or other child attributes.

                                        
                    
                    -------------------------------------------------
                    Example — Child Aggregation at Child Grain
                    -------------------------------------------------
                    Question:
                    "Milestone count per project"
                    Reasoning:
                    Entity: milestones (child attribute)
                    Measure: COUNT milestones
                    Dimension: project_id
                    Both the measure and the dimension belong to the SAME child attribute.
                    Execution:
                    aggregation_scope = global
                    global_aggregations:
                        attr = "milestones"
                        aggregate = COUNT
                        field = milestone_id
                        group_by = ["project_id"]
                    IMPORTANT:
                    - Do NOT use mixed when measure and dimension are both from the same child attribute
                    - Mixed is only required when rolling child data up to entity-level attributes (portfolio, program, etc.)



                    =====================================================================
                    SCORING & COMPOSITE METRIC — POST AGGREGATION PATTERN
                    =====================================================================

                    When computing a FORMULA that depends on OTHER post_agg aliases
                    (e.g. reach, effort, impact computed in earlier steps):

                    CORRECT PATTERN:

                    post_aggregations: [
                    {{ "attr": "key_results", "aggregate": "COUNT", ... "alias": "reach" }},
                    {{ "attr": "team_data",   "aggregate": "SUM",   ... "alias": "effort" }},
                    {{ "attr": "core",        "aggregate": "MAX",   ... "alias": "impact" }},
                    {{
                        "attr": "_post",          ← use "_post" to reference prior aliases
                        "aggregate": "FORMULA",
                        "field": "*",
                        "group_by": ["roadmap_id"],
                        "alias": "rice_score",
                        "formula": "(reach * impact * 0.8) / (effort if effort > 0 else 1)"
                    }}
                    ]

                    global_aggregations: [
                    {{
                        "attr": "_post_grouped",
                        "aggregate": "MAX",
                        "field": "rice_score",     ← field = the alias, NOT "value"
                        "group_by": ["roadmap_id"],
                        "alias": "rice_score",
                        "source_alias": "rice_score"
                    }}
                    ]

                    KEY RULES:
                    ✔ FORMULA that references earlier post_agg aliases → attr: "_post"
                    ✔ FORMULA that references only core fields → attr: "core"
                    ✔ global_aggregation field = the post_agg alias (e.g. "rice_score")
                    ✔ Always guard: (effort if effort > 0 else 1) to avoid division by zero
                    ✔ Always guard null fields: (impact or 0)


                ---------------------------------------------------------------------
                STEP 1 — ENTITY UNIVERSE
                ---------------------------------------------------------------------

                Which attribute defines WHICH entities exist?

                - Put restrictive filters there
                - usage = "constrain"
                - core attribute ALWAYS exists.
                    core defines the entity universe ONLY if measure_attr = core.
                    Otherwise, core is included only for identity fields.

                ---------------------------------------------------------------------
                STEP 2 — DIMENSIONS
                ---------------------------------------------------------------------

                For EACH grouping dimension mentioned or implied
                (portfolio, program, owner, team, customer, time):

                1) Identify the attribute that OWNS the field
                2) Include that attribute
                3) usage = "describe"

                ❌ You may NOT group by a dimension unless its attribute is included

                ---------------------------------------------------------------------
                STEP 3 — MEASURE
                ---------------------------------------------------------------------

                    Identify what is being counted / summed / averaged.

                    That attribute is the MEASURE SOURCE.

                    Examples:
                    - milestones → COUNT(*)
                    - risks → COUNT(*)
                    - spend → SUM(amount)
                    
                    
                ---------------------------------------------------------------------
                MULTI-METRIC SUBSET RULE (CRITICAL)
                ---------------------------------------------------------------------

                    If the user intent requires multiple metrics over the SAME entity
                    and the metric names imply different states or business conditions
                    (e.g., total vs delivered, active vs closed, open vs resolved,
                    success vs failure):

                    Then:
                        1) The base metric represents the FULL entity universe.
                        2) Each additional metric MUST represent a SUBSET of that universe.
                        3) Subset conditions MUST be expressed using filters inside the
                        corresponding global_aggregation.
                        4) The filter MUST reference existing schema fields that represent
                        the business state (status, archived flag, lifecycle field, etc.).
                        5) Multiple metrics MUST NOT have identical COUNT definitions.
                        If two metrics would count the same rows:
                        → The plan is INVALID
                        → Appropriate filters MUST be added.
                        6) post_filters MUST NOT be used for subset metrics,
                        because post_filters modify the entity universe for ALL metrics.
                        
                        
                ---------------------------------------------------------------------
                CHILD COUNT FIELD SELECTION (HARD RULE)
                ---------------------------------------------------------------------

                If measure_attr is a child attribute:

                1) COUNT MUST use the child entity primary field.

                Examples:
                milestones → milestone_id  
                childrean_roadmaps → roadmap_id  
                portfolios → portfolio_id  
                kpis → kpi_id  

                2) You MUST NOT use:
                - field = "*"
                - field = entity_id

                Reason:
                COUNT(*) or COUNT(entity_id) may produce incorrect existence results.

                                        
                        
                ---------------------------------------------------------------------
                BUSINESS STATE INFERENCE LIMIT (CRITICAL)
                ---------------------------------------------------------------------

                When creating subset filters for business states such as:
                delivered, closed, active, completed, etc.:

                You MUST follow this order:

                1) If a field explicitly represents the state
                (e.g., status, archived flag, lifecycle field):
                → Use that field.

                2) If NO explicit state field exists:
                → Use the MOST DIRECT lifecycle indicator (e.g., archived flag).

                3) You MUST NOT combine multiple fields using OR / AND
                to guess business meaning.

                4) You MUST NOT infer composite definitions such as:
                - end_date OR archived
                - status OR date conditions
                - multiple lifecycle fields together

                5) If the business meaning cannot be determined from a single clear field:
                → Use the most explicit lifecycle field only.

            
                
                CLASSIFICATION VS AGGREGATION CHECK:
                    If the question asks:
                    - "on-time vs delayed"
                    - "met vs missed"
                    - "success vs failure"

                    Then this is a COMPARATIVE COUNT, not a derived dimension.

                    RULE:
                    - DO NOT invent a classification dimension
                    - DO NOT use FORMULA for labeling
                    - Representation depends on whether comparison is field-to-field:
                        • If comparison affects which rows are counted
                            → filtering MUST occur at DAO-level (attribute.filters)
                            → NOT inside post_aggregations

                        • If comparison is field-to-field → DAO-level filtering is REQUIRED
                        
                        
                        
                CLASSIFICATION & COMPARATIVE COUNT RULE (NON-NEGOTIABLE):

                    If the user intent compares categories such as:
                    • "on-time vs delayed"
                    • "met vs missed"
                    • "success vs failure"
                    • "over vs under budget"

                    THEN:

                    1️⃣ You MUST NOT:
                    • use FORMULA for classification
                    • compare one field to another field
                    • simulate CASE WHEN logic

                    2️⃣ You MUST determine where the comparison lives:
                    • If comparison requires field-to-field logic
                    (e.g. actual_date vs target_date)
                    → DAO-level filtering is REQUIRED


                    3. Aggregation rule:
                    • post_aggregations may ONLY COUNT / SUM these attributes

                    If DAO-level attributes do not exist:
                    → DO NOT invent logic
                    → Switch to EVIDENCE FALLBACK MODE
                    → Output raw attributes needed for the comparison
                    
                
                =====================================================================
                🚫 CLASSIFICATION HARD STOP (NON-NEGOTIABLE)
                =====================================================================

                Classification answers: "which rows belong to which category?"

                Aggregation answers: "how many / how much?"

                These two MUST NEVER be mixed.

                -------------------------------------------------
                FORBIDDEN (DO NOT OUTPUT):
                -------------------------------------------------

                • Using FORMULA to label or classify rows
                • Using post_aggregations.filters to create categories
                • Comparing one field to another field to decide labels
                • Simulating CASE WHEN logic

                Examples of INVALID intent handling:
                - on_time vs delayed
                - met vs missed
                - success vs failure
                - over vs under budget

                -------------------------------------------------
                MANDATORY BEHAVIOR:
                -------------------------------------------------

                If the user intent requires classification:

                1️⃣ You MUST look for a DAO attribute that ALREADY represents
                    the classified row set (e.g. milestones_on_time).

                2️⃣ You may ONLY:
                    • COUNT
                    • SUM
                    • AVG
                    these attributes.

                3️⃣ If NO such DAO attribute exists:
                    → DO NOT invent logic
                    → DO NOT use FORMULA
                    → DO NOT use post_aggregation.filters
                    → SWITCH TO EVIDENCE FALLBACK MODE
                    
                    
                    
                ---------------------------------------------------------------------
                DERIVED MEASURE RULE (CRITICAL)
                ---------------------------------------------------------------------

                    If the requested measure is NOT directly available as a single field
                    in the schema, you MUST determine whether it requires a computed value.

                    Examples:
                        - duration = end_date - start_date
                        - delay_days = actual_date - target_date
                        - variance = actual - planned
                        - ratio or percentage based on multiple fields

                    RULES:

                    1️⃣ If the measure requires row-level computation:
                        → You MUST create a post_aggregation with:
                            aggregate = FORMULA
                        → The formula MUST compute the value per entity or per child row.

                    2️⃣ Then:
                        → global_aggregations may perform AVG / SUM / MIN / MAX
                        on the computed post_aggregation alias.

                    3️⃣ You MUST NOT:
                        • apply AVG directly on a raw field if the intent requires a difference
                        • assume a precomputed column unless it exists in schema

                    Example:
                    User: average project duration

                    Correct pattern:
                    post_aggregations:
                        alias = project_duration
                        aggregate = FORMULA
                        formula = (end_date - start_date)

                    global_aggregations:
                        aggregate = AVG
                        field = value
                        source_alias = project_duration

                    MENTAL CHECK:
                    If the user asks for:
                        - duration
                        - delay
                        - variance
                        - cycle time
                        - completion time

                    → You MUST check whether the value exists directly.
                    If not → derive using FORMULA in post layer.
                    

                ---------------------------------------------------------------------
                SCORING & COMPOSITE METRIC RULE (CRITICAL)
                ---------------------------------------------------------------------

                    If the user intent involves:
                    - score (RICE score, ....)
                    - ranking by computed metric
                    - weighted calculation across multiple attributes
                    - prioritization formula

                    THEN:

                    1) This is ALWAYS aggregation_scope = "mixed"

                    2) You MUST:
                    → Identify which child attributes contribute to the score
                    → Create one post_aggregation per child attribute (COUNT or SUM)
                    → Create a final FORMULA post_aggregation combining them
                    → Create global_aggregations to surface score per entity

                    3) You MUST NOT:
                    → Use aggregation_scope = "entity"
                    → Just fetch raw data "to enable" scoring later
                    → Defer computation — the score MUST be computed in this plan

                    4) If schema does NOT have direct score fields:
                    → Use available proxy fields (budget, priority, estimated_hours, etc.)
                    → FORMULA must reference post_aggregation aliases only
                    → Clearly derive the best approximation from available schema fields

                    Example — RICE Score:
                    Reach proxy  → COUNT(stakeholders or users) per entity
                    Impact proxy → roadmap_priority or budget field
                    Confidence   → fixed weight (e.g. 0.8) if no field exists
                    Effort proxy → SUM(total_estimated_hours) from team_data

                    post_aggregations:
                        1. SUM(total_estimated_hours) group_by [roadmap_id] → alias: effort_hours
                        2. FORMULA: (reach * impact * confidence) / effort_hours → alias: rice_score

                    global_aggregations:
                        attr: "_post_grouped", source_alias: "rice_score"
                        group_by: ["roadmap_id"]
                        sort: desc
        
                    
                    ---------------------------------------------------------------------
                    HARD DURATION PATTERN (NON-NEGOTIABLE)
                    ---------------------------------------------------------------------

                    If the metric name or intent contains ANY of the following:

                    - duration
                    - cycle time
                    - completion time
                    - turnaround time
                    - lead time
                    - time taken
                    - days between

                    AND the schema does NOT contain a direct field for this value:

                    THEN:

                    1) You MUST create a post_aggregation with:
                    aggregate = FORMULA

                    2) The formula MUST compute:
                    (end_date - start_date)

                    3) You MUST NOT:
                    • use AVG/MIN/MAX directly on date fields
                    • aggregate end_date or start_date directly

                    If AVG/MIN/MAX is applied directly to a date field for a duration intent:
                    → The plan is INVALID
                    → You MUST rewrite using post_aggregation.



                ---------------------------------------------------------------------
                STEP 4 — EXECUTION GRAIN (PRIMARY AUTHORITY)
                ---------------------------------------------------------------------
                
                    ---------------------------------------------------------------------
                    CORE VS MIXED OVERRIDE (NON-NEGOTIABLE)
                    ---------------------------------------------------------------------

                    If the primary measure is:

                    - COUNT of entities
                    - or any aggregation on core fields

                    Then:

                    → aggregation_scope MUST be "global"

                    This applies EVEN IF:
                    - multiple attributes are present (portfolio, program, roadmap, etc.)
                    - dimensions come from different entity-level attributes
                    - time_bucket is present
                    - multiple dimensions are used

                    Entity-level attributes include:
                    core, portfolio, program, roadmap, customer

                    These attributes are already at entity grain.

                    DO NOT use aggregation_scope = "mixed" when the measure is on core.

                    Mixed is allowed ONLY when:
                    - the measure attribute is child-grain
                    (milestone, task, risk, etc.)
                    - or when a FORMULA requires per-entity computation.

                
                    ---------------------------------------------------------------------
                    CORE PRIORITY RULE (CRITICAL)
                    ---------------------------------------------------------------------

                    If the measure attribute is "core":

                    AND the metric is:
                    - COUNT of entities
                    - SUM/AVG/MIN/MAX of core fields

                    Then:
                        → aggregation_scope MUST be "global"
                        → post_aggregations MUST NOT be created
                        → global_aggregations MUST operate directly on attr = "core"

                    This rule applies EVEN IF:
                        - time_bucket is present
                        - multiple global metrics exist
                        - multiple dimensions exist

                    Reason:
                        Core attributes are already at entity grain.
                        Using post_aggregations would duplicate entities and produce incorrect counts.

                    Each attribute has a natural grain:
                    Entity-grain attributes:
                        - One row per entity
                        - Examples: core, portfolio, program, roadmap

                    Child-grain attributes:
                    - Multiple rows per entity
                    - Examples: milestone, risk, task

                    You MUST determine:

                    measure_attr  = attribute being aggregated
                    dimension_attr = attribute that owns the group_by field
                    
                    
                    CORE COUNT RULE (HARD)

                        If user asks for:
                        - total projects
                        - number of entities

                        Then:
                        → COUNT must be performed on entity_id
                        → NEVER COUNT a FORMULA alias
                        → NEVER COUNT a derived metric


                    -------------------------------------------------
                    CASE 1 — SAME GRAIN
                    -------------------------------------------------

                    If measure_attr and dimension_attr are BOTH entity-grain:

                    → aggregation_scope = "global"

                    Rules:
                    - Use ONLY global_aggregations
                    - post_aggregations MUST NOT be used

                    Examples:
                    - projects by portfolio
                    - projects per month
                    - projects by program

                    -------------------------------------------------
                    CASE 2 — CHILD → ENTITY ROLLUP
                    -------------------------------------------------

                    If measure_attr is child-grain
                    AND dimension_attr is entity-grain:

                    → aggregation_scope = "mixed"

                    Execution:
                    1) post_aggregations:
                    group_by = entity_id + dimensions

                    2) global_aggregations:
                    attr = "_post_grouped"
                    aggregate = SUM
                    field = "value"

                    Example:
                    - milestones by portfolio
                    - risks by program

                    -------------------------------------------------
                    CASE 3 — SAME CHILD GRAIN
                    -------------------------------------------------

                    If measure and dimension both belong to the SAME child attribute:

                    → aggregation_scope = "global"
                    → aggregate directly on that attribute

                    Example:
                    - milestones by month
                    
                    CHILD SELF-GRAIN RULE (CRITICAL)

                        If measure_attr is a child attribute
                        AND all group_by fields belong to the SAME child attribute:

                        → aggregation_scope MUST be "global"
                        → aggregate directly on that child attribute

                        Do NOT use mixed.

                    
                ---------------------------------------------------------------------
                MENTAL CHECK BEFORE OUTPUT
                ---------------------------------------------------------------------

                Ask yourself:

                Is the measure counting entities?

                YES → global on core  
                NO  → check if child → maybe mixed


                ---------------------------------------------------------------------
                STEP 5 — POST AGGREGATION (MANDATORY FOR MIXED)
                ---------------------------------------------------------------------
                
                POST AGGREGATIONS ARE PURE.

                    post_aggregations:
                    - MUST compute metrics per entity
                    - MUST operate on the full attribute row set
                    - MUST NOT filter, or classify the underlying row set

                    "If the metric applies to ALL rows equally → filter belongs in attributes.filters (pushdown).
                    If there are MULTIPLE metrics needing DIFFERENT filters over the SAME universe → use global_aggregations.filters."

                    post_aggregations MUST:
                        - aggregate the MEASURE
                        - group_by MUST include:
                        - entity_id
                        - EVERY dimension needed later (portfolio, time, etc.)

                    🚨 RULE:
                        If a dimension is used later,
                        it MUST already exist in post_aggregations.group_by
                        ❌ Never group by IDs like milestone_id
                        ❌ Never produce 1-row-per-item post aggregations

                ---------------------------------------------------------------------
                STEP 6 — GLOBAL AGGREGATION
                ---------------------------------------------------------------------

                    If rolling up post results:

                    - attr = "_post_grouped"
                    - field = "value"
                    - group_by = final dimensions
                    
                    
                    ---------------------------------------------------------------------
                    ENTITY SUBSET BASED ON CHILD EXISTENCE (CRITICAL)
                    ---------------------------------------------------------------------

                    If the business question asks for:

                    - entities with at least one child
                    - entities having X
                    - entities where child_count > 0
                    - ideas with roadmaps
                    - projects with milestones / risks / tasks

                    Then this is an ENTITY COUNT, not a child total.

                    Execution rules:

                    1) aggregation_scope MUST be "mixed"

                    2) post_aggregations:
                    - compute child_count per entity

                    3) global_aggregations:
                    - attr = "_post_grouped"
                    - aggregate = "COUNT"
                    - field = "<entity_id>"
                    - filters:
                        child_count__gt: 0

                    4) DO NOT use:
                    aggregate = COUNT
                    field = "value"

                    Reason:
                    "value" represents child totals, not entity identity.
                    Using COUNT(value) produces incorrect or empty results.


                    ❌ Global aggregations CANNOT see raw attributes
                    
                    
                    ---------------------------------------------------------------------
                    CHILD EXISTENCE SAFETY (HARD)
                    ---------------------------------------------------------------------

                    When computing child_count for existence logic:

                    post_aggregations MUST:

                    - COUNT(child_primary_id)
                    - group_by = [entity_id]

                    DO NOT include time_bucket or other dimensions
                    unless explicitly requested.

                    Reason:
                    Adding extra dimensions creates multiple rows per entity
                    and breaks existence logic.

                    
                    ---------------------------------------------------------------------
                    EXECUTIVE SUMMARY GROUPING RULE (MINIMAL)
                    ---------------------------------------------------------------------

                    If the analysis focus or user intent includes terms such as:
                        - headline
                        - hero
                        - dashboard
                        - summary
                        - KPI

                    Then:

                    1) Prefer separate aggregations for each dimension.
                    2) Do NOT combine multiple dimensions into a single group_by
                    unless the user explicitly asks for cross-analysis such as:
                        - "portfolio-wise monthly trend"
                        - "by portfolio and month together"
                        - "per portfolio per month"

                    Example:
                        Intent: "projects in 2025 for dashboard"
                        Dimensions mentioned: portfolio, month

                    Correct:
                    global_aggregations:
                        - group_by: []
                        - group_by: ["portfolio_title"]
                        - group_by: ["project_month"]

                    Avoid: group_by: ["portfolio_title", "project_month"]

                    If cross-analysis is not explicitly requested, keep dimensions independent.

                
                
                =====================================================================
                GLOBAL ATTRIBUTE SELECTION RULE (CRITICAL)
                =====================================================================

                For each global_aggregation, attr determines WHERE the executor
                reads rows from (raw[attr]).

                RULE:
                → attr MUST be the attribute that was fetched and contains the measure rows.
                → It is NOT determined by where the group_by field "lives".
                → Dimensions from other attributes (portfolio_title, program_name) are resolved
                automatically from the entity tree — you do NOT need to change attr for them.

                If measure is on core (COUNT projects, SUM budget):
                → attr = "core"
                → group_by can include portfolio_title, program_name, etc.
                → executor resolves those dimensions via entity_map automatically

                If measure is on a child attr (COUNT risks, COUNT milestones):
                → attr = "risks" or "milestones" (the child attr)
                → group_by can include project_id or child-level fields only

                If rolling up from post layer:
                → attr = "_post" or "_post_grouped"

                ❌ WRONG (causes empty results):
                global_aggregations:
                attr = "portfolio"    ← portfolio rows don't have risk counts
                field = risk_id

                ✔ CORRECT:
                global_aggregations:
                attr = "risks"        ← risks rows are what we're counting
                field = risk_id
                group_by = ["project_id"]


                ---------------------------------------------------------------------
                STEP 7 — TIME (MANDATORY)
                ---------------------------------------------------------------------
                
                    ---------------------------------------------------------------------
                    TIME BUCKET KEY RULE
                    ---------------------------------------------------------------------

                    If a time bucket is required:

                    • It MUST be defined only under:
                        attribute.extra_params.time_bucket

                    • The key name MUST be exactly:
                        "time_bucket"

                    • Only ONE time_bucket is allowed per attribute.

                    • You MUST NOT create keys such as:
                        month_bucket
                        quarter_bucket
                        weekly_bucket
                        yearly_bucket
                        or any custom bucket name.

                    If multiple time granularities are requested
                    (e.g., monthly and quarterly):

                    → Choose the finest granularity only.
                    → Example:
                    monthly + quarterly → use month
                    
                    
                    ---------------------------------------------------------------------
                    TIME_BUCKET STRUCTURE (MANDATORY)
                    ---------------------------------------------------------------------

                    time_bucket MUST follow this EXACT structure:

                    "extra_params": {{
                        "time_bucket": {{
                            "field": "<date_field_name>",
                            "interval": "day | week | month | quarter | year",
                            "alias": "<bucket_field_name>"
                        }}
                    }}

                    All three keys are REQUIRED:
                        - field
                        - interval
                        - alias
                    No additional keys are allowed.
                    
                    INVALID examples:
                        "time_bucket": "month"
                        "time_bucket":{{ "interval": "month" }}
                        "time_bucket": {{ "granularity": "month" }}


                    ---------------------------------------------------------------------
                    TIME BUCKET TRIGGER (NON-NEGOTIABLE)
                    ---------------------------------------------------------------------

                    If ANY of the following are true:

                    • User asks for: month, monthly, weekly, quarterly, yearly, trend, timeline
                    • A group_by field is a date/datetime
                    • Time comparison filters are present (date range)
                    • Time trend is implied by the question

                    THEN:
                    → A time_bucket MUST be created.
                    → Grouping by raw date/datetime is FORBIDDEN.

                    Time grouping must NEVER use raw datetime fields.
                    If ANY group_by field is a date or datetime field:
                    1) You MUST create a time_bucket in attribute.extra_params.
                    2) You MUST NOT group by the raw date/datetime field.
                    3) Determine interval:
                        • If the user explicitly mentions:
                            - daily / day      → day
                            - weekly / week    → week
                            - monthly / month  → month
                            - quarterly        → quarter
                            - yearly / year    → year

                    4) If time grouping is implied but interval is NOT specified:
                        → DEFAULT interval = "month"

                    5) The time_bucket alias MUST:
                        - be included in attribute.fields
                        - be used in post_aggregations.group_by
                        - be used in global_aggregations.group_by (if present)
                        
                    The time_bucket object MUST use the key name "interval".
                    Do NOT use the key name "granularity".

                    Grouping by raw timestamps is INVALID.
                    If a raw date field appears in group_by without a time_bucket:
                    → The plan is INVALID and MUST be corrected before output.
                    
                    6) Time field selection MUST follow the MEASURE grain:

                        If the measure is ENTITY count (e.g., projects, roadmaps, ideas):
                            → Use the entity lifecycle date from the core attribute:
                                - project → start_date or created_date
                                - roadmap → created_date
                                - idea → created_date

                            → DO NOT use child attribute dates (milestone, risk, task).

                        If the measure is CHILD count (e.g., milestones, risks, tasks):
                            → Use the date from that child attribute.

                    7) If multiple attributes exist in the plan:
                        → The time field MUST come from the SAME attribute as the measure.


                ---------------------------------------------------------------------
                STEP 8 — VALIDATION (MANDATORY)
                ---------------------------------------------------------------------

                Before output, VERIFY:

                    - Every group_by field exists in the SAME attribute
                    - No dimension is introduced at global stage
                    - No DISTINCT semantics are implied
                    - No dot-notation fields exist
                    - No invented fields exist

                =====================================================================
                CROSS-ATTRIBUTE DIMENSION PROPAGATION (HARD RULE)
                =====================================================================

                    If a field appears in global_aggregations.group_by:

                    1) Its attribute MUST be included
                    2) That SAME field MUST exist in post_aggregations.group_by
                    3) Global aggregation MUST operate on "_post_grouped"

                    ❌ INVALID:
                    post.group_by = ["project_id", "month"]
                    global.group_by = ["portfolio_title", "month"]

                    ✔ VALID:
                    post.group_by = ["project_id", "portfolio_title", "month"]
                    global.group_by = ["portfolio_title", "month"]
                    
                    
                ---------------------------------------------------------------------
                SUBSET METRIC VALIDATION (MANDATORY)
                ---------------------------------------------------------------------

                    If multiple global_aggregations exist and they refer to different
                    business states (e.g., total vs delivered, active vs closed):

                    Then:

                    • Their filter conditions MUST NOT be identical.
                    • At least one metric MUST include a filter that represents the
                    subset condition.

                    If all metrics count the same entity set:
                    → The plan is INVALID
                    → Filters MUST be added to reflect the intended business difference.


                =====================================================================
                FILTER RULES (STRICT)
                =====================================================================

                    Filters MUST be one of:

                    1) CONDITION SET
                    {{ "<field>__<op>": value, ... }}

                    2) LOGICAL NODE
                    {{ "and": [ <filter>, ... ] }}
                    {{ "or":  [ <filter>, ... ] }}

                    ❌ Never mix condition fields and logical keys
                    ❌ Never reference attributes dynamically inside filters

                    post_filters may ONLY reference:
                    - post_aggregation aliases
                    - FORMULA aliases
                    
                ---------------------------------------------------------------------
                FILTER OPERATOR NORMALIZATION (MANDATORY)
                ---------------------------------------------------------------------

                If a filter represents equality:

                You MUST always use explicit operator:

                    field__eq: value

                NEVER output implicit equality:

                    field: value   ❌ INVALID

                Examples:

                ✔ Correct:
                {{ "is_archived_project__eq": true }}

                ❌ Incorrect:
                {{ "is_archived_project": true }}

                Reason:
                Executor requires explicit operators for deterministic filter behavior.

                                    
                    
                ---------------------------------------------------------------------
                FILTER VALUE RULE (CRITICAL)
                ---------------------------------------------------------------------

                    Filter values MUST be one of:
                    ✔ literals (string, number, boolean)
                    ✔ lists of literals

                    ❌ Objects as filter values are NOT supported
                    ❌ Field-to-field comparisons are NOT supported

                    INVALID EXAMPLES (DO NOT OUTPUT):
                    - {{ "a__lte": {{ "field": "b" }} }}
                    - {{ "date__gt": {{ "other_field": "x" }} }}
                    
                ---------------------------------------------------------------------
                NULL CHECK RULE (MANDATORY)
                ---------------------------------------------------------------------

                    Null checks MUST use ONLY the following form:

                    ✔ field__isnull: true
                    ✔ field__isnull: false

                    ❌ field__isnotnull is NOT supported
                    ❌ field__notnull is NOT supported
                    ❌ field__neq: null is NOT supported

                    If a null check is required:
                    → You MUST express it using field__isnull
                    → Any other form is INVALID and MUST NOT be output


                =====================================================================
                AGGREGATION RULES
                =====================================================================

                Allowed aggregates:
                COUNT | SUM | AVG | MIN | MAX | FORMULA

                FORMULA:
                - Runs after all post_aggregations
                - May reference post_aggregation aliases
                - MUST NOT reference global_aggregation aliases
                - No SQL expressions

                DISTINCT keyword is NOT supported.
                However, UNIQUE counts MUST be implemented using GROUP BY.
                Rules:

                If the user intent requires counting unique values of a field:

                1️⃣ group_by MUST include that field
                2️⃣ COUNT must be performed on the entity_id
                3️⃣ A null filter MUST be applied:
                    "<field>__isnull": false

                Example:
                User: "How many parent roadmaps?"

                VALID:
                global_aggregations:
                    attr = "core"
                    aggregate = "COUNT"
                    field = "project_id"
                    group_by = ["parent_roadmap_id"]

                INVALID:
                COUNT(parent_roadmap_id) with no group_by

                
                
                FORMULA RESTRICTIONS (CRITICAL):

                    FORMULA is a SCALAR computation only.

                    FORMULA:
                    - MAY compute a numeric value per entity
                    - MAY reference:
                    - core fields
                    - post_aggregation aliases
                    - MAY be used in post_filters and sorting

                    FORMULA MUST NOT:
                    - introduce new dimensions
                    - introduce new group_by fields
                    - be referenced inside group_by
                    - emit rows
                    - classify records into categories

                    🚫 INVALID USE OF FORMULA:
                    - Using FORMULA to create labels like "on_time", "delayed"
                    - Grouping by a FORMULA result
                    - Using FORMULA to simulate CASE WHEN classification

                    If the user intent requires classification or bucketing:
                    → Use DAO-level attributes that already represent the classified row sets
                    → post_aggregations MUST remain filter-free
                    
                    
                ---------------------------------------------------------------------
                GROUPING QUALITY RULE (MINIMAL)
                ---------------------------------------------------------------------

                Avoid grouping by free-text fields.

                If a field name ends with "_str":
                → Do NOT use it in group_by
                → Treat it as descriptive text only

                Examples to avoid:
                - project_category_str
                - project_strategy_str
                - project_description_str

                Only group by clean categorical fields such as:
                portfolio_title, program_name, project_type, status_value, month.

                
                =====================================================================
                🚨 OUTPUT SHAPE GUARANTEE (MANDATORY)
                =====================================================================

                You MUST output JSON that conforms EXACTLY to the following structural rules.
                This is a hard execution contract.
                
                
                ---------------------------------------------------------------------
                AGGREGATION CONSISTENCY (MANDATORY)
                ---------------------------------------------------------------------

                If aggregation_scope = "mixed":
                - post_aggregations MUST exist
                - global_aggregations MUST exist

                If aggregation_scope = "global":
                - post_aggregations MUST NOT be present

                If aggregation_scope = "entity":
                - global_aggregations MUST NOT be present
                - Results are returned per entity only
                - post aggregations are allowed
                
                ------------------------------------
                0️⃣ AGGREGATION KEY NAME LOCK (CRITICAL)
                ------------------------------------

                Aggregation objects MUST use EXACT key names.

                POST and GLOBAL aggregations MUST use:

                ✔ "attr"
                ✔ "aggregate"
                ✔ "field"
                ✔ "group_by"
                ✔ "alias"

                ❌ FORBIDDEN KEY NAMES:
                - "agg"
                - "op"
                - "operation"
                - "metric"
                - "fn"
                - "measure"

                If ANY forbidden key appears:
                → the plan WILL NOT EXECUTE
                → you MUST FIX IT before outputting JSON


                ------------------------------------
                1️⃣ GROUP_BY STRUCTURE (CRITICAL)
                ------------------------------------

                • group_by MUST be an array of STRING FIELD NAMES ONLY
                • group_by MUST NEVER contain objects
                • group_by MUST NEVER contain time_bucket definitions

                ❌ INVALID:
                "group_by": [
                "project_id",
                    {{ "time_bucket": {{ ... }} }}
                ]

                ✔ VALID:
                "group_by": [
                "project_id",
                "milestone_month"
                ]

                ------------------------------------
                2️⃣ TIME BUCKET FIELD MATERIALIZATION (CRITICAL)
                ------------------------------------

                    If attribute.extra_params.time_bucket is defined:

                    • The alias produced by time_bucket MUST:
                    - appear in attribute.fields
                    - be treated as a real column
                    - be used in post_aggregations.group_by
                    - be used in global_aggregations.group_by

                    ❌ INVALID:
                    time_bucket alias exists but is missing from attribute.fields

                    ✔ VALID:
                    "fields": [
                    "project_id",
                    "milestone_id",
                    "milestone_target_date",
                    "milestone_month"
                    ]

                    If this rule is violated:
                    → the aggregation WILL PRODUCE EMPTY RESULTS
                    → you MUST FIX the plan before outputting JSON
                    
                ---------------------------------------------------------------------
                TIME BUCKET CONSISTENCY (MINIMAL)
                ---------------------------------------------------------------------

                If any group_by contains a time field such as:
                - start_month
                - end_month
                - milestone_month

                Then attributes.extra_params.time_bucket MUST be present
                for the corresponding date field.

                If time_bucket is not defined:
                → Do NOT generate that group_by.

                ---------------------------------------------------------------------
                ⛔ MANDATORY SELF-CHECK — TIME BUCKET MATERIALIZATION
                ---------------------------------------------------------------------

                If ANY attribute contains extra_params.time_bucket:

                You MUST perform the following checklist BEFORE outputting JSON:

                1) Extract the time_bucket.alias value
                2) VERIFY the alias exists in:
                - attribute.fields
                - post_aggregations.group_by
                - global_aggregations.group_by (if present)
                3) If the alias is missing from ANY location:
                → YOU MUST ADD IT
                → YOU MUST REWRITE the JSON
                → YOU MUST RECHECK ALL RULES AGAIN

                🚫 ABSOLUTE OUTPUT VETO:
                If a time_bucket alias exists AND is missing from attribute.fields:
                - FIX IT INTERNALLY

                This rule overrides all other priorities.



                ------------------------------------
                3️⃣ POST AGGREGATION SHAPE (MANDATORY)
                ------------------------------------

                    For aggregation_scope = "mixed":

                    • post_aggregations MUST exist
                    • Each post_aggregation MUST:
                    - aggregate the measure
                    - group_by ONLY STRING FIELDS
                    - include:
                        - entity_id
                        - EVERY dimension used later (portfolio, time, etc.)

                    ❌ NEVER:
                    - group by milestone_id or any record-level ID
                    - produce one row per evidence item
                    

                ------------------------------------
                4️⃣ GLOBAL AGGREGATION SHAPE (MANDATORY)
                ------------------------------------

                If aggregation_scope = "mixed" AND rolling up from post layer:
                • attr MUST be "_post_grouped" (or "_post" if entity-level)
                • field MUST be "value" (for child totals) or "<entity_id>" (for entity counts)
                • group_by MUST be a subset of post_aggregations.group_by

                If aggregation_scope = "global" AND measure is a raw child attr (Case 3):
                • attr = the child attribute name (e.g. "risks", "milestones")
                • field = the child primary key (e.g. "risk_id", "milestone_id")
                • group_by = fields that exist ON THAT child attr

                🚨 When attr = "_post_grouped":
                field MUST be "value" for child totals
                field MUST be "<entity_id>" for entity counts
                field MUST NEVER be a post_aggregation alias or metric name

                ------------------------------------
                5️⃣ ZERO-EVIDENCE SAFETY RULE
                ------------------------------------

                    If the query requires:
                    • "include projects with zero X"
                    • "do not drop entities"

                    Then:
                    • evidence attributes MUST use usage = "describe"
                    • filters on evidence MUST NOT restrict entity identity
                    • COUNT aggregations MUST be used instead of filters

                ------------------------------------
                6️⃣ FINAL VALIDATION CHECK (DO NOT SKIP)
                ------------------------------------

                    Before outputting JSON, you MUST verify:

                    • group_by contains only strings
                    • time_bucket exists only in attribute.extra_params
                    • every global group_by field exists in post_aggregations.group_by
                    • no invented fields exist
                    • no object appears where a string is required

                    If ANY rule is violated:
                    → FIX the plan BEFORE outputting JSON
                
                ------------------------------------
                7️⃣ GLOBAL AGGREGATION SOURCE ALIAS (CRITICAL)
                ------------------------------------

                If global_aggregations.attr = "_post" OR "_post_grouped":

                • You MUST include:
                - "source_alias"

                • source_alias MUST EXACTLY match:
                - the alias of ONE post_aggregation

                ✔ VALID:
                {{
                    "attr": "_post_grouped",
                    "aggregate": "SUM",
                    "field": "value",
                    "group_by": ["portfolio_title", "milestone_month"],
                    "alias": "total_milestones",
                    "source_alias": "milestone_count"
                }}

                ❌ INVALID:
                {{
                    "attr": "_post_grouped",
                    "aggregate": "SUM",
                    "field": "value",
                    "group_by": ["portfolio_title", "milestone_month"],
                    "alias": "total_milestones"
                }}

                If source_alias is missing:
                → the plan WILL NOT EXECUTE
                → you MUST FIX IT before outputting JSON

                =====================================================================
                FINAL INVARIANTS
                =====================================================================

                - Schema correctness > everything
                - Dimensions must exist in the layer being aggregated
                - Post aggregations are required ONLY when measure grain differs from dimension grain.
                - If a rule is violated → FIX the plan before output
                
                
                =====================================================================
                🚫 OUTPUT VETO RULE (MANDATORY)
                =====================================================================

                If ANY of the following are true:

                - a forbidden key name is used
                - a required key is missing
                - a group_by contains a non-string
                - time_bucket appears outside attribute.extra_params
                - _post_grouped.field != "value"
                
                

                THEN:
                    ✔ FIX THE PLAN INTERNALLY
                    
                
                If ANY post_aggregation contains a "filters" key:
                    ✔ REMOVE the filters
                    ✔ REWRITE using DAO-level attributes

            """
            
            system_prompt += f"""
                =====================================================================
                CANONICAL OUTPUT STRUCTURE (FOLLOW EXACTLY)
                =====================================================================

                The JSON you output MUST follow this exact structural shape.
                Keys may be omitted ONLY if they are not relevant, but
                WHEN PRESENT they MUST match this structure.

                ROOT OBJECT:

                {{
                "thought_process_for_current_analysis": [string],
                "rationale_for_user_visiblity": [
                                "Proessional summarization of thought process in 2-3 items each items will be like: 2-3 word info like Fetching X, Bucket Y, Agg Z... etc"
                            ],
                "question_type": "<one of allowed values>",
                "attributes": [
                    {{
                        "attr": "<attribute_name>",
                        "usage": "describe | constrain",
                        "fields": [string],
                        "filters": {{ ... }},
                        "extra_params": {{ ... }}
                    }}
                ],
                "aggregation_scope": "entity | global | mixed",
                "post_aggregations": [
                    {{
                        "attr": "<attribute_name>",
                        "aggregate": "COUNT | SUM | AVG | MIN | MAX | FORMULA",
                        "field": "<field_name | *>",
                        "group_by": [string],
                        "alias": "<alias_name>",
                        "formula": "<python_expression_if_FORMULA>"
                    }}
                ],
                "post_filters": [
                    {{ "<post_agg_alias>__<op>": value }}
                ],
                "global_aggregations": [
                    {{
                        "attr": "<attribute | _post | _post_grouped>",
                        "aggregate": "COUNT | SUM | AVG | MIN | MAX",
                        "field": "<field | value | *>",
                        "group_by": [string],
                        "alias": "<alias_name>",
                        "filters": {{ "<field>__<op>": value }}   // optional, metric-level filtering
                    }}
                ],
                "sort": {{
                    "field": "<post_agg_alias | core_field>",
                    "order": "asc | desc"
                }},
                "user_requested_limit": number
                }}
                
                
                ---------------------------------------------------------------------
                FILTER STRUCTURE (MANDATORY)
                ---------------------------------------------------------------------

                    Whenever "filters" appears (in attributes or global_aggregations):

                    It MUST follow ONE of these forms:

                    1) CONDITION SET
                    {{
                    "<field>__<operator>": value
                    }}

                    Allowed operators:
                    __eq, __ne, __gt, __gte, __lt, __lte, __in, __contains, __icontains, __isnull

                    Implicit equality is NOT allowed.

                    ❌ INVALID:
                    {{ "status": "active" }}

                    ✔ VALID:
                    {{ "status__eq": "active" }}


                    2) LOGICAL NODE

                    {{
                    "and": [ <filter_object>, <filter_object> ]
                    }}

                    [{{
                    "or": [ <filter_object>, <filter_object> ]
                    }}]

                    Rules:
                    - filters MUST be a JSON object (never a list)
                    - Do NOT mix condition fields with "and"/"or" at the same level
                    - Values MUST be literals (string, number, boolean, or list)
                    - Nested objects as values are NOT allowed

                    If the structure is violated:
                    → You MUST rewrite the filters before output.
                    
                
                ---------------------------------------------------------------------
                EXTRA_PARAMS STRUCTURE (MANDATORY)
                ---------------------------------------------------------------------

                    extra_params may contain ONLY:

                    1) time_bucket
                    2) limit
                    3) row_slice

                    No other keys are allowed.


                    time_bucket structure:

                    {{
                    "time_bucket": {{
                        "field": "<date_field>",
                        "interval": "day | week | month | quarter | year",
                        "alias": "<bucket_field_name>"
                    }}
                    }}

                    All three fields are REQUIRED.


                    limit structure:

                    [{{
                    "limit": <number>
                    }}]

                    row_slice structure:

                    {{
                        "row_slice": {{
                            "group_by": [list of string field names],
                            "order_by": "<field_name>",
                            "order": "desc | asc",
                            "limit": <int>
                        }}
                    }}
                    All four keys are REQUIRED.
                    group_by MUST include the entity_id field.

                    INVALID keys:
                    - month_bucket
                    - quarter_bucket
                    - granularity
                    - bucket
                    - any custom key

                    If any other key would be created:
                    → REMOVE it before output.




                ---------------------------------------------------------------------
                STRUCTURE GUARANTEES (MANDATORY)
                ---------------------------------------------------------------------

                • "attributes" is ALWAYS an array
                • "post_aggregations" is ALWAYS an array if present
                • "global_aggregations" is ALWAYS an array if present
                • "group_by" is ALWAYS an array of strings
                • "filters" is ALWAYS an object (never a list)
                • No key may contain nested aggregation objects
                • No key may contain comments or explanations

                If you are unsure about any value:
                → OMIT the key
                → DO NOT invent structure

                =====================================================================
                
                =====================================================================
                FINAL OUTPUT GATE (NON-NEGOTIABLE)
                =====================================================================

                Before producing the final JSON, you MUST internally answer:

                “Does every time_bucket alias appear in attribute.fields?”

                - If YES → output JSON
                - If NO  → FIX the plan and re-check from STEP 7

                You are NOT allowed to output JSON until the answer is YES.

            """

            # ----------------------------------------------------------
            # USER PROMPT
            # ----------------------------------------------------------
            user_prompt = f"""
            
                ==========================================
                Conversation context:
                {self.conversation}
                
                Interpret this user query into a structured DAO plan:

                USER QUERY: {user_query}
                CONTEXT: {context}

                Output only one JSON object.
                
                ==========================================
                🎯 ANALYSIS FOCUS (IMPORTANT)
                ==========================================

                When selecting attributes, filters, aggregations,
                and formulas, prioritize the following analytical lens:

                "{requirement_focus}"

                Guidelines:
                - Fetch only data relevant to this focus
                - Prefer aggregations that reveal patterns related to this focus
                - Avoid unrelated attributes unless required for context
                - Very proper output json, no comment there should be written coz it will break the system when i ll extract the json
                - Before outputting JSON, check:
                    Every group_by field belongs to an explicitly listed attribute.
                - Group correctly, Use time bucket. etc carefully.. 
                
                
                Today's date is {datetime.utcnow().strftime("%B %d, %Y")}
                Use this date to understand any time-date related queries
            """

            # ----------------------------------------------------------
            # Run LLM with streaming + thought extraction
            # ----------------------------------------------------------
            prompt = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

            llm_output = ""
            printed = set()
            import re

            for chunk in self.llm.runWithStreaming(
                prompt,
                self.modelOptions,
                f"{dao_type}::ai_dao_interpreter",
                logInDb=self.log_info,
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

            # ----------------------------------------------------------
            # Parse final JSON
            # ----------------------------------------------------------
            print("structure plan from ai dao llm_output ", llm_output)
            parsed = extract_json_after_llm(llm_output)
            # print("structure plan from ai dao llm_output ", parsed)
            if not isinstance(parsed, dict):
                appLogger.error({"error": f"❌ Interpret Error"})
                return None
                # raise ValueError("Invalid structured JSON from LLM")
                
            # ------------------------------------------------------------------
            # 🔧 PLAN STABILIZATION: Remove free-text fields from group_by
            # ------------------------------------------------------------------
            try:
                def clean_group_by(group_list):
                    if not isinstance(group_list, list):
                        return group_list
                    cleaned = []
                    for f in group_list:
                        # remove free text fields
                        if isinstance(f, str) and f.endswith("_str"):
                            print(f"⚠️ Removing free-text dimension: {f}")
                            continue
                        cleaned.append(f)
                    return cleaned

                # Clean global aggregations
                for g in parsed.get("global_aggregations", []) or []:
                    g["group_by"] = clean_group_by(g.get("group_by", []))

                # Clean post aggregations
                for p in parsed.get("post_aggregations", []) or []:
                    p["group_by"] = clean_group_by(p.get("group_by", []))

            except Exception as e:
                print("⚠️ _str cleanup skipped:", e)

            
            # ------------------------------------------------------------------
            # 🔧 MANDATORY RULE: 'core' MUST always be included
            # ------------------------------------------------------------------

            entity_id_field = get_entity_id_field(dao_type)               # e.g. roadmap_id, project_id
            entity_prefix = entity_id_field[:-3]                          # remove "_id"
            entity_title_field = f"{entity_prefix}_title"                 # roadmap_title/project_title
            mandatory_core_fields = [entity_id_field, entity_title_field]

            attributes_list = parsed.setdefault("attributes", [])

            core_attr = None
            for attr in attributes_list:
                if attr.get("attr") == "core":
                    core_attr = attr
                    break

            if core_attr is None:
                # LLM forgot core → INSERT IT
                print(f"⚠️ Injecting mandatory core attribute for {dao_type}")
                attributes_list.insert(0, {
                    "attr": "core",
                    "fields": mandatory_core_fields,
                    "filters": {}
                })
            else:
                # LLM included core → VALIDATE mandatory fields
                existing = set(core_attr.get("fields", []))
                for f in mandatory_core_fields:
                    existing.add(f)
                core_attr["fields"] = list(existing)


            # Ensure ID always present
            for entry in parsed.get("attributes", []):
                fields = entry.setdefault("fields", [])
                if id_field not in fields:
                    fields.insert(0, id_field)

            # Normalize limit
            if "limit" in parsed:
                parsed["user_requested_limit"] = parsed.pop("limit")
                
                
            # ------------------------------------------------------------------
            # 🔧 FIX: Correct global aggregation source based on post_aggregation level
            # ------------------------------------------------------------------
            try:
                post_aggs = parsed.get("post_aggregations", [])
                global_aggs = parsed.get("global_aggregations", [])
                
                
                # ------------------------------------------------------------------
                # 🔧 FIX: Global fields derived from post_aggregations must use _post
                # ------------------------------------------------------------------
                try:
                    post_aliases = {p.get("alias") for p in post_aggs if p.get("alias")}

                    for g in global_aggs:
                        field = g.get("field")
                        attr = g.get("attr")

                        # If global is trying to read a post metric from core
                        if field in post_aliases and attr in [None, "core"]:
                            print(f"⚠️ Plan Fix: global source core → _post for field '{field}'")
                            g["attr"] = "_post"

                except Exception as e:
                    print("⚠️ Post lineage normalization skipped:", e)


                entity_id_field = get_entity_id_field(dao_type)

                # Detect if there is any REAL grouping (beyond entity_id)
                has_real_grouping = False

                for p in post_aggs:
                    group_by = p.get("group_by", [])
                    if group_by and group_by != [entity_id_field]:
                        has_real_grouping = True
                        break

                # # If no real grouping → data lives in _post (not _post_grouped)
                # if not has_real_grouping:
                #     for g in global_aggs:
                #         if g.get("attr") == "_post_grouped":
                #             print("⚠️ Plan Fix: _post_grouped → _post")
                #             g["attr"] = "_post"
                            
                # ------------------------------------------------------------------
                # 🔧 HARD FIX: Ensure unique attributes
                # ------------------------------------------------------------------
                # unique_attrs = {}
                # for a in parsed.get("attributes", []):
                #     attr_name = a.get("attr")
                #     if attr_name not in unique_attrs:
                #         unique_attrs[attr_name] = a
                #     else:
                #         # merge fields
                #         existing = unique_attrs[attr_name]
                #         existing_fields = set(existing.get("fields", []))
                #         existing_fields.update(a.get("fields", []))
                #         existing["fields"] = list(existing_fields)

                # parsed["attributes"] = list(unique_attrs.values())
                
                
                # # ------------------------------------------------------------------
                # # 🔧 SAFETY: Ensure post layer contains all global group_by fields
                # # ------------------------------------------------------------------

                # post_aggs = parsed.get("post_aggregations", [])
                # global_aggs = parsed.get("global_aggregations", [])

                # # Collect all global dimensions
                # required_dims = set()
                # for g in global_aggs:
                #     for dim in g.get("group_by", []):
                #         required_dims.add(dim)

                # # Add missing dims to post group_by
                # for p in post_aggs:
                #     gb = set(p.get("group_by", []))
                #     missing = required_dims - gb
                #     if missing:
                #         print(f"⚠️ Plan Fix: Adding missing post group_by fields: {missing}")
                #         p["group_by"] = list(gb | missing)


            except Exception as e:
                print("⚠️ Global aggregation normalization skipped:", e)


            return parsed

        except Exception as e:
            appLogger.error({"error": f"❌ LLM interpretation failed: {e}"})
            traceback.print_exc()
            return {"attributes": [{"attr": "core", "fields": [id_field], "filters": {}}]}



# ---------------------- Safe Formula Evaluation ------------------------
def _safe_eval_formula(formula: str, context: dict):
    """Safely evaluate LLM-generated formulas after post_aggregations."""

    import math
    import re
    from datetime import datetime, date, timedelta

    try:
        if not formula or not isinstance(formula, str):
            return None

        # ------------------------------------------------------------
        # SQL → Python normalization
        # ------------------------------------------------------------
        f = formula
        f = f.replace("NULLIF(", "safe_nullif(")
        f = f.replace("COALESCE(", "coalesce(")
        f = f.replace("LEN(", "length(")
        f = f.replace(" null ", " None ").replace(" NULL ", " None ")
        f = f.replace(" is null", " is None").replace(" is not null", " is not None")

        # ------------------------------------------------------------
        # Safe helpers
        # ------------------------------------------------------------

        def safe_nullif(a, b):
            if a is None or a == b or a == 0:
                return 1e-9
            return a

        def coalesce(*args):
            return next((x for x in args if x not in [None, "", float("nan")]), None)

        def safe_date(x):
            if isinstance(x, (datetime, date)):
                return x
            try:
                return datetime.fromisoformat(str(x))
            except:
                return None

        def date_diff_days(a, b):
            a, b = safe_date(a), safe_date(b)
            if a and b:
                return (a - b).days
            return None

        def length(x):
            return len(str(x or ""))

        # ------------------------------------------------------------
        # Build safe environment
        # ------------------------------------------------------------
        safe_env = {
            **context,
            "abs": abs,
            "round": round,
            "max": max,
            "min": min,
            "pow": pow,
            "math": math,
            "length": length,
            "len": length,
            "coalesce": coalesce,
            "safe_nullif": safe_nullif,
            "to_date": safe_date,
            "date_diff_days": date_diff_days,
        }
        
        # 🔴 ADD THIS
        for k, v in list(safe_env.items()):
            if isinstance(v, str):
                try:
                    if len(v) >= 10 and v[4] == '-' and v[7] == '-':
                        safe_env[k] = datetime.fromisoformat(v)
                except:
                    pass
                else:
                    try:
                        safe_env[k] = float(v)
                        print(f"🔄 Formula coerce: {k} = '{v}' → {float(v)}")
                    except (ValueError, TypeError):
                        pass  # keep as string

        # ------------------------------------------------------------
        # Safe eval
        # ------------------------------------------------------------
        result = eval(f, {"__builtins__": {}}, safe_env)

        # Normalize output
        if isinstance(result, timedelta):
            return result.days
        if isinstance(result, float) and math.isnan(result):
            return None
        return result

    except Exception as e:
        # print(f"❌ Formula eval failed: {e} | formula: {formula}")  # ADD THIS
        return None


            
def _sanitize_row(row: dict) -> dict:
    """
    Convert any non-JSON-serializable types in a DB row to safe primitives.
    Called on every row returned by dao_fn before it enters entity_map.
    """
    sanitized = {}
    for k, v in row.items():
        if isinstance(v, timedelta):
            # timedelta → integer days (what duration_days should be)
            sanitized[k] = v.days
        elif isinstance(v, (date, datetime)):
            # dates/datetimes → ISO string (already usually handled, but belt+suspenders)
            sanitized[k] = v.isoformat()
        else:
            sanitized[k] = v
    return sanitized


# --------------------------------------------------------------------------
# 3️⃣ Executor — FINAL CLEAN & SIMPLE VERSION
# --------------------------------------------------------------------------
class AIDAOExecutor:
    """
    Executes structured DAO plans using the FINAL ARCHITECTURE:

        1. RAW FETCH
        2. MERGE ENTITY TREE
        3. POST AGGREGATIONS (entity-level)
        4. GLOBAL AGGREGATIONS (portfolio-level)
        5. POST FILTER + SORT + LIMIT

    Design guarantees:
        - Core stays inside entity["core"]
        - Child attrs inside entity[attr]
        - post_agg values inside entity["post_agg"]
        - grouped post_agg values inside entity["post_agg_grouped"]
        - global agg always sees post agg (via raw["_post"])
        - No root-level flattening at any point
    """

    def __init__(self):
        pass

    @log_function_io_and_time
    def execute_plan(
        self,
        dao_type: str,
        structured_plan: Dict[str, Any],
        tenant_id: int,
        entity_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:

        print("\n🚀 === AIDAOExecutor START (Final Architecture) ===")

        dao_cls = DAO_REGISTRY.get(dao_type)
        if not dao_cls:
            raise ValueError(f"Unsupported DAO type: {dao_type}")

        manifest = dao_cls.get_available_attributes()
        id_field = get_entity_id_field(dao_type)
        entity_param = get_entity_ids_param(dao_type)

        # ==================================================================
        # 1️⃣ RAW FETCH — NON-CORE FIRST, THEN CORE
        # ==================================================================
        raw: Dict[str, List[Dict[str, Any]]] = {}

        attributes = structured_plan.get("attributes", [])

        # --------------------------------------------------
        # 1A️⃣ FETCH NON-CORE ATTRIBUTES FIRST
        # --------------------------------------------------
        resolved_entity_ids = entity_ids  # may start as None

        for item in attributes:
            attr = item.get("attr")
            if not attr or attr == "core":
                continue

            filters = item.get("filters", {}) or {}
            fields = item.get("fields", []) or []
            group_by = item.get("group_by", []) or []
            extra = item.get("extra_params", {}) or {}
            usage = item.get("usage") or "describe"

            meta = manifest.get(attr)
            if not meta:
                continue

            dao_fn = meta.get("dao_function")
            fn_args = dao_fn.__code__.co_varnames

            kwargs = {}
            if "tenant_id" in fn_args:
                kwargs["tenant_id"] = tenant_id
            if entity_param in fn_args and resolved_entity_ids is not None:
                kwargs[entity_param] = resolved_entity_ids
            if "fields" in fn_args:
                kwargs["fields"] = fields
            if "group_by" in fn_args and group_by:
                kwargs["group_by"] = group_by

            for k, v in filters.items():
                if k in fn_args:
                    kwargs[k] = v
                else:
                    kwargs.setdefault("filters", {})[k] = v

            for k, v in extra.items():
                if k == "row_slice":
                    continue  # ← handled separately after fetch
                if k == "limit":
                    continue  # ← already handled for core
                if k in fn_args:
                    kwargs[k] = v
                else:
                    kwargs.setdefault("filters", {})[k] = v

            # Apply default limit ONLY if no row_slice
            row_slice = extra.get("row_slice")
            if not row_slice:
                if "limit" in fn_args and "limit" not in kwargs:
                    if "limit" in extra:                          # key exists in extra_params
                        kwargs["limit"] = extra.get("limit")      # pass None explicitly → fetch all
                    else:
                        kwargs["limit"] = 10                      # key absent → use default
                    
            else:
                if "limit" in fn_args:
                    kwargs["limit"] = None


            # # print(f"📡 FETCH (non-core) {attr}: args={kwargs}")
            # print(f"   → {len(rows)} rows -> non-core")
            rows = []
            try:
                print(f"📡 FETCH (non-core) {attr}: args={kwargs}")
                rows = dao_fn(**kwargs) or []
                # rows = [_sanitize_row(r) for r in (dao_fn(**kwargs) or [])]
                # raw[attr] = rows
                print(f"   → {len(rows)} rows -> non-core")
            except Exception as e:
                print(f"⚠️ FETCH FAILED for {attr}: {e}")
                # raw[attr] = []  # graceful empty fallback

            raw[attr] = rows

            # Apply row_slice if specified
            row_slice = extra.get("row_slice")
            if row_slice and rows:
                rows = self._apply_row_slice(rows, row_slice)
                raw[attr] = rows
            
            # 🔥 UPDATE ENTITY IDS — ONLY IF ATTRIBUTE CONSTRAINS IDENTITY
            if usage == "constrain":
                matched_ids = {
                    r.get(id_field)
                    for r in rows
                    if r.get(id_field) is not None
                }

                if resolved_entity_ids is None:
                    resolved_entity_ids = list(matched_ids)
                else:
                    resolved_entity_ids = list(set(resolved_entity_ids) & matched_ids)

                print(f"🔻 entity_ids constrained by {attr}: {len(resolved_entity_ids)}")
            else:
                print(f"🧩 attribute {attr} used for description only — no entity narrowing")


            print(f"🔻 entity_ids after {attr}: {len(resolved_entity_ids)}")

        
        has_constrain = any(
            item.get("usage") == "constrain"
            for item in attributes
            if item.get("attr") != "core"
        )
        # If constraints were applied AND resulted in zero entities → STOP
        if has_constrain and resolved_entity_ids == []:
            print("⛔ Constrain attributes yielded ZERO entities — skipping core fetch")

            key_name = get_key_name(dao_type)
            return {
                key_name: [],
                "_debug_summary": {
                    "count": 0,
                    "reason": "No entities matched constrain attributes",
                    "structured_plan": structured_plan,
                },
                "_global_summary": {},
            }
        # --------------------------------------------------
        # 1B️⃣ FETCH CORE LAST (USING FINAL entity_ids)
        # --------------------------------------------------
        for item in attributes:
            if item.get("attr") != "core":
                continue

            fields = item.get("fields", []) or []
            meta = manifest.get("core")
            dao_fn = meta.get("dao_function")
            fn_args = dao_fn.__code__.co_varnames
            filters = item.get("filters", {}) or {}
            extra = item.get("extra_params", {}) or {}

            kwargs = {}
            if "tenant_id" in fn_args:
                kwargs["tenant_id"] = tenant_id
            if entity_param in fn_args:
                kwargs[entity_param] = resolved_entity_ids
            if "fields" in fn_args:
                kwargs["fields"] = fields
                
            if "filters" in fn_args:
                kwargs["filters"] = filters   # ✅ THIS IS THE FIX
                
            for k, v in extra.items():
                if k == "limit":
                    continue  # ← SKIP limit here; executor handles it after sort
                if k in fn_args:
                    kwargs[k] = v
                else:
                    kwargs.setdefault("filters", {})[k] = v

            # print(f"📡 FETCH core: args={kwargs}")
            rows = dao_fn(**kwargs) or []
            # rows = [_sanitize_row(r) for r in (dao_fn(**kwargs) or [])]

            raw["core"] = rows
            print(f"   → {len(rows)} rows -> core")
            
            # # 🔥 CRITICAL: CORE DEFINES THE ENTITY UNIVERSE
            # matched_ids = {
            #     r.get(id_field)
            #     for r in rows
            #     if r.get(id_field) is not None
            # }
            # resolved_entity_ids = list(matched_ids)
            # print(f"🔻 entity_ids constrained by core: {len(resolved_entity_ids)}")


        # ==================================================================
        # 2️⃣ MERGE ENTITY TREE — CLEAN, CONSISTENT
        # ==================================================================
        entity_map: Dict[Any, Dict[str, Any]] = {}

        core_rows = raw.get("core", [])
        for core in core_rows:
            eid = core.get(id_field)
            if eid is None:
                continue

            entity_map[eid] = {
                "core": dict(core),          # keep core separate
                "post_agg": {},              # entity-level numeric results
                "post_agg_grouped": {}       # entity-level grouped agg results
            }

        # Attach children to entity tree
        for attr, rows in raw.items():
            if attr == "core" or attr.startswith("_"):
                continue

            for r in rows:
                eid = r.get(id_field)
                if eid not in entity_map:
                    continue
                entity_map[eid].setdefault(attr, []).append(dict(r))

        print(f"🧱 Built entity_map for {len(entity_map)} entities")
        
        

        # ==================================================================
        # 🔒 ENSURE ALL REQUESTED ATTRIBUTES EXIST (LEFT JOIN SEMANTICS)
        # ==================================================================
        requested_attrs = {
            item["attr"]
            for item in structured_plan.get("attributes", [])
            if item.get("attr") != "core"
        }

        for ent in entity_map.values():
            for attr in requested_attrs:
                ent.setdefault(attr, [])

        # # ==================================================================
        # # 🔗 MATERIALIZE CROSS-ATTRIBUTE DIMENSIONS (AFTER LEFT JOIN)
        # # ==================================================================
        # self._materialize_cross_attribute_dimensions(
        #     structured_plan,
        #     entity_map,
        #     raw,
        #     manifest,
        #     id_field
        # )

        
        # ==================================================================
        # 🔒 ENSURE ALL REQUESTED ATTRIBUTES EXIST (LEFT JOIN SEMANTICS)
        # ==================================================================
        requested_attrs = {
            item["attr"]
            for item in structured_plan.get("attributes", [])
            if item.get("attr") != "core"
        }

        for ent in entity_map.values():
            for attr in requested_attrs:
                ent.setdefault(attr, [])

        # # ================================================================
        # # 5️⃣ DEBUG SNAPSHOT (OPTIONAL)
        # # ================================================================
        # try:
        #     with open("debug_entity_tree.json", "w") as f:
        #         MyJSON.dump(entity_map, f)
        # except Exception:
        #     pass

        # ==================================================================
        # 3️⃣ POST AGGREGATIONS — ENTITY LEVEL
        # ==================================================================
        post_aggs = structured_plan.get("post_aggregations", []) or []
        if post_aggs:
            print("\n🧮 Applying post_aggregations...")
            self._apply_post_aggs(entity_map, raw, post_aggs, id_field)
            
        # try:
        #     with open("debug2.json", "w") as f:
        #         MyJSON.dump(entity_map, f)
        # except Exception:
        #     pass

        # ==================================================================
        # Create synthetic raw table: raw["_post"]
        # Used for global agg over post-agg fields
        # ==================================================================
        raw["_post"] = []
        for eid, ent in entity_map.items():
            row = {id_field: eid}
            row.update(ent.get("post_agg", {}))
            raw["_post"].append(row)
            
            
        # ==================================================================
        # Create synthetic raw table: raw["_post_grouped"]
        # Used for global agg over grouped post-agg fields
        # ==================================================================
        raw["_post_grouped"] = []

        for eid, ent in entity_map.items():
            grouped = ent.get("post_agg_grouped", {})

            for alias, rows in grouped.items():
                for r in rows:
                    new_row = {
                        id_field: eid,
                        "__alias__": alias,
                        **r
                    }
                    raw["_post_grouped"].append(new_row)


        print("\n🧪 DEBUG _post_grouped SAMPLE")
        print(f"Total rows len -> _post_grouped: {len(raw['_post_grouped'])}")
        for r in raw["_post_grouped"][:3]:
            print(r)

        # ==================================================================
        # Before sorting, assemble final_entities cleanly
        # ==================================================================
        key_name = get_key_name(dao_type)
        final_entities = []

        for eid, ent in entity_map.items():
            final_entities.append({
                **ent  # do not flatten core; keep structure clean
            })

        # ==================================================================
        # 5️⃣ POST FILTERS
        # ==================================================================
        post_filters = structured_plan.get("post_filters", []) or []
        if post_filters:
            print("\n🔍 Applying post_filters...")

            # BEFORE FILTER COUNTS
            before = len(final_entities)
            before_ids = [e["core"].get(id_field) for e in final_entities]

            final_entities = self._apply_post_filters(final_entities, post_filters)

            # AFTER FILTER COUNTS
            after = len(final_entities)
            after_ids = [e["core"].get(id_field) for e in final_entities]

            print(f"🔎 Post-filter verification:")
            print(f"   • Before filter: {before} entities")
            print(f"   • After filter:  {after} entities")
            print(f"   • Filter removed: {before - after} entities")

            # OPTIONAL: print which IDs were removed
            removed = set(before_ids) - set(after_ids)
            print(f"   • Removed IDs: {sorted(list(removed))[:50]} ...")


        # ==================================================================
        # 4️⃣ GLOBAL AGGREGATIONS — PORTFOLIO LEVEL
        # ==================================================================
        global_aggs = structured_plan.get("global_aggregations", []) or []
        global_summary = {}

        if global_aggs:
            print(f"\n🌍 Applying {len(global_aggs)} global aggregations...")
            # global_summary = self._apply_global_aggs(entity_map, raw, global_aggs)
            global_summary = self._apply_global_aggs(entity_map, raw, global_aggs, final_entities, dao_type)



        # ==================================================================
        # 6️⃣ SORT
        # ==================================================================
        sort_cfg = structured_plan.get("sort")
        if sort_cfg:
            field = sort_cfg.get("field")
            order = sort_cfg.get("order", "desc")
            
            print(f"↕ Sorting by {field} ({order})")
            reverse = (order == "desc")

            def sort_value(ent):
                # 1️⃣ prefer post_agg
                val = ent["post_agg"].get(field)

                # 2️⃣ fallback to core
                if val is None:
                    val = ent["core"].get(field)

                if val is None:
                    return (1, "")  # None always last

                # Try numeric first
                try:
                    return (0, float(val))
                except (TypeError, ValueError):
                    pass

                # Fallback: string/datetime — sorts lexicographically
                # ISO datetime strings sort correctly as strings
                return (0, str(val))

            final_entities.sort(key=sort_value, reverse=reverse)

        # ==================================================================
        # 7️⃣ LIMIT
        # ==================================================================
        limit = structured_plan.get("user_requested_limit")
        if limit:
            final_entities = final_entities[:limit]

        # ==================================================================
        # BUILD FINAL OUTPUT
        # ==================================================================
        final_output = {
            key_name: final_entities,
            "_debug_summary": {
                "count": len(final_entities),
                "structured_plan": structured_plan
            },
            "_global_summary": global_summary,
        }
        
        print("total entities --- ", len(final_entities))
        
        try:
            filename = f"rtemp2_execute_plan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, "w") as f:
                MyJSON.dump(final_output, f)
        except Exception:
            pass
        
        return final_output

    # ======================================================================
    # 🔧 POST AGGREGATIONS — PURE, DETERMINISTIC
    # ======================================================================
    def _apply_post_aggs(self, entity_map, raw, post_aggs, id_field):
        from collections import defaultdict
        import re
        from datetime import datetime

        # ------------------------------------------------------------
        # Helper: evaluate scalar formula safely
        # ------------------------------------------------------------
        def _eval_formula_for_entity(eid, rows, formula):
            ctx = {}

            # core fields
            ctx.update(entity_map[eid].get("core", {}))

            # existing post_aggs (dependency support)
            ctx.update(entity_map[eid].get("post_agg", {}))

            # if rows exist (grouped case), expose first row fields
            if rows:
                ctx.update(rows[0])

            # Convert ISO date strings → datetime
            for k, v in list(ctx.items()):
                if isinstance(v, str):
                    try:
                        if len(v) >= 10 and v[4] == '-' and v[7] == '-':
                            ctx[k] = datetime.fromisoformat(v)
                    except:
                        pass

            # ensure all variables exist
            for var in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula):
                ctx.setdefault(var, None)

            return _safe_eval_formula(formula, ctx)

        # ------------------------------------------------------------
        # Main loop
        # ------------------------------------------------------------
        for agg in post_aggs:

            # if "filters" in agg:
            #     raise RuntimeError(
            #         f"INVALID PLAN: post_aggregation '{agg.get('alias')}' contains filters."
            #     )

            func = agg.get("aggregate", "").upper()
            attr = agg.get("attr")
            alias = agg.get("alias")
            field = agg.get("field")
            group_by = agg.get("group_by") or []
            formula = agg.get("formula", "")

            if not alias:
                continue

            # ------------------------------------------------------------
            # 1️⃣ Source rows
            # ------------------------------------------------------------
            if attr == "core":
                source_rows = []
                for eid, ent in entity_map.items():
                    row = dict(ent["core"])
                    row[id_field] = eid
                    source_rows.append(row)
            else:
                source_rows = raw.get(attr, [])

            # ------------------------------------------------------------
            # 2️⃣ Decide mode
            # ------------------------------------------------------------
            # entity_level = (not group_by) or (group_by == [id_field])
            entity_level = (not group_by) or (set(group_by) == {id_field})


            # ------------------------------------------------------------
            # 3️⃣ Bucket rows
            # ------------------------------------------------------------
            buckets = defaultdict(list)

            if entity_level:
                # Bucket existing rows
                for r in source_rows:
                    eid = r.get(id_field)
                    if eid in entity_map:
                        buckets[eid].append(r)
                
                # 🔥 ZERO-CHILD SAFETY: Ensure ALL entities have buckets
                for eid in entity_map.keys():
                    if eid not in buckets:
                        buckets[eid] = []

            else:  # grouped mode
                # Bucket existing rows
                for r in source_rows:
                    eid = r.get(id_field)
                    if eid not in entity_map:
                        continue

                    key_vals = []
                    valid = True
                    
                    from itertools import product
                    dim_values_list = []
                    valid = True

                    for g in group_by:
                        vals = self._resolve_dimension_values(eid, r, g, entity_map)
                        if not vals:
                            valid = False
                            break
                        dim_values_list.append(vals)

                    if not valid:
                        continue

                    # FAN-OUT combinations
                    for combo in product(*dim_values_list):
                        buckets[(eid, combo)].append(r)
                
                # 🔥 ZERO-CHILD SAFETY: Ensure entities with no children get counted
                for eid in entity_map.keys():
                    has_bucket = any(k[0] == eid for k in buckets.keys())
                    if not has_bucket:
                        # Create empty bucket with null dimensions
                        null_key = tuple([None] * len(group_by))
                        buckets[(eid, null_key)] = []

            # ------------------------------------------------------------
            # 4️⃣ Aggregate
            # ------------------------------------------------------------
            if entity_level:
                for eid, rows in buckets.items():

                    if func == "FORMULA":
                        value = _eval_formula_for_entity(eid, rows, formula)

                    else:
                        vals = [
                            r.get(field)
                            for r in rows
                            # if isinstance(r.get(field), (int, float))
                            if r.get(field) is not None
                        ]

                        if func == "COUNT":
                            value = len(rows)
                        elif func == "SUM":
                            value = sum(vals) if vals else 0
                        elif func == "AVG":
                            value = round(sum(vals) / len(vals), 2) if vals else None
                        elif func == "MAX":
                            value = max(vals) if vals else None
                        elif func == "MIN":
                            value = min(vals) if vals else None
                        else:
                            value = None

                    entity_map[eid]["post_agg"][alias] = value

            else:
                for (eid, key), rows in buckets.items():

                    if func == "FORMULA":
                        value = _eval_formula_for_entity(eid, rows, formula)
                    else:
                        vals = [
                            r.get(field)
                            for r in rows
                            # if isinstance(r.get(field), (int, float))
                            if r.get(field) is not None
                        ]

                        if func == "COUNT":
                            value = len(rows)
                        elif func == "SUM":
                            value = sum(vals) if vals else 0
                        elif func == "AVG":
                            value = round(sum(vals) / len(vals), 2) if vals else None
                        elif func == "MAX":
                            value = max(vals) if vals else None
                        elif func == "MIN":
                            value = min(vals) if vals else None
                        else:
                            value = None

                    row = {g: key[i] for i, g in enumerate(group_by)}
                    row["value"] = value

                    entity_map[eid]["post_agg_grouped"].setdefault(alias, []).append(row)

        # ------------------------------------------------------------
        # DEBUG
        # ------------------------------------------------------------
        print("🧪 POST_AGG DEBUG SNAPSHOT")
        for eid, ent in list(entity_map.items())[:3]:
            print("EID:", eid)
            print("post_agg:", ent["post_agg"])
            print("post_agg_grouped:", ent["post_agg_grouped"])

    # ======================================================================
    # 🔧 GLOBAL AGGREGATIONS
    # ======================================================================
    def _apply_global_aggs(self, entity_map, raw, global_aggs, final_entities, dao_type):
        from collections import defaultdict

        result = {}

        # def collect_rows(attr):
        #     if attr == "core":
        #         return [ent["core"] for ent in entity_map.values()]
        #     return raw.get(attr, [])
        
        def collect_rows(attr):

            if attr == "core":
                return [ent["core"] for ent in entity_map.values()]

            if attr == "_post":
                return raw.get("_post", [])

            if attr == "_post_grouped":
                return raw.get("_post_grouped", [])

            return raw.get(attr, [])

        
        def belongs(row):
            # Case 1: normal flat DAO rows
            if id_field in row:
                return row[id_field] in allowed_ids
            # Case 2: entity_map node
            if "core" in row and id_field in row["core"]:
                return row["core"][id_field] in allowed_ids
            return False
        
        id_field = get_entity_id_field(dao_type)
        allowed_ids = {ent["core"][id_field] for ent in final_entities}

        for agg in global_aggs:
            func = agg.get("aggregate", "").upper()
            alias = agg.get("alias")
            field = agg.get("field")
            group_by = agg.get("group_by") or []
            attr = agg.get("attr", None)

            # # all_rows = collect_rows(attr) if attr else list(entity_map.values())
            # if not attr or attr == "core":
            #     all_rows = collect_rows("core")   # ALWAYS core rows
            # else:
            #     all_rows = collect_rows(attr)
            
            # initial attr from plan
            
            # =====================================================
            # FIX 1: Core entity count must use entity_map universe
            # =====================================================
            # if (attr == "core" or not attr) and func == "COUNT" and not group_by:
            #     result[alias] = len(final_entities)
            #     continue
            
            agg_filters = agg.get("filters")
            if (
                (attr == "core" or not attr)
                and func == "COUNT"
                and not group_by
                and not agg_filters
            ):
                result[alias] = len(final_entities)
                continue


            attr = agg.get("attr")

            # --------------------------------------------------
            # AUTO SOURCE FIX FIRST
            # --------------------------------------------------
            expected_alias = agg.get("source_alias")

            if attr == "_post_grouped":
                grouped_rows = raw.get("_post_grouped", [])
                found_in_grouped = any(
                    r.get("__alias__") == expected_alias
                    for r in grouped_rows
                )
                if not found_in_grouped:
                    print(f"⚠️ Global source fix: {expected_alias} -> _post")
                    attr = "_post"
                    
                    # 🔥 CRITICAL FIX
                    # If we fall back to entity-level post, field must be the alias
                    if attr == "_post" and field == "value" and expected_alias:
                        print(f"⚠️ Global field fix: value -> {expected_alias}")
                        field = expected_alias

            # --------------------------------------------------
            # NOW collect rows
            # --------------------------------------------------
            if not attr or attr == "core":
                all_rows = collect_rows("core")
            else:
                all_rows = collect_rows(attr)

            # filter by allowed IDs
            # rows = [r for r in all_rows if r.get(id_field) in allowed_ids]
            # Filter rows AFTER post-filters
            rows = [r for r in all_rows if belongs(r)]
            # 🔥 Apply metric-level filters
            agg_filters = agg.get("filters")
            if agg_filters:
                rows = self._apply_global_row_filters(rows, agg_filters, attr)

            buckets = defaultdict(list)
            # expected_alias = agg.get("source_alias") or agg.get("alias")
            expected_alias = agg.get("source_alias")
            # 🔥 FIX: _post uses alias as field
            if attr == "_post" and expected_alias:
                field = expected_alias

            
            
            # # ------------------------------------------------------------------
            # # AUTO-SOURCE CORRECTION (CRITICAL)
            # # Planner may send _post_grouped even for entity-level metrics.
            # # Detect where the alias actually lives.
            # # ------------------------------------------------------------------
            # if attr == "_post_grouped":
            #     grouped_rows = raw.get("_post_grouped", [])
            #     found_in_grouped = any(
            #         r.get("__alias__") == expected_alias
            #         for r in grouped_rows
            #     )

            #     if not found_in_grouped:
            #         # Fallback to entity-level storage
            #         print(f"⚠️ Global source fix: {expected_alias} -> _post")
            #         attr = "_post"



            # for r in rows:
            #     if attr in ["core", None]:
            #         # inside entity_map node
            #         row = r["core"] if isinstance(r, dict) and "core" in r else r
            #     else:
            #         row = r
            #     key_tuple = tuple(row.get(g) for g in group_by)
            #     val = row.get(field)
            #     if func == "COUNT":
            #         buckets[key_tuple].append(1)
            #     elif isinstance(val, (int, float)):
            #         buckets[key_tuple].append(val)


            print("\n🌍 GLOBAL AGG DEBUG")
            print("Expected alias:", expected_alias)
            print("Group by:", group_by)
            print("Incoming rows sample:")
            for r in rows[:5]:
                print("  row alias =", r.get("__alias__"))


            for r in rows:

                # 🔒 FILTER BY POST_AGG ALIAS
                # if "__alias__" in r and r["__alias__"] != expected_alias:
                #     continue
                
                if attr == "_post_grouped":
                    if r.get("__alias__") != expected_alias:
                        continue


                if attr in ["core", None]:
                    row = r["core"] if isinstance(r, dict) and "core" in r else r
                else:
                    row = r

                # 🔒 STRICT GROUP_BY VALIDATION
                key_elems = []
                valid = True
                # for g in group_by:
                #     if g not in row:
                #         valid = False
                #         break
                #     key_elems.append(row[g])
                
                
                from itertools import product

                eid = row.get(id_field)
                if eid is None:
                    continue

                dim_values_list = []
                valid = True

                for g in group_by:
                    vals = self._resolve_dimension_values(eid, row, g, entity_map)
                    if not vals:
                        valid = False
                        break
                    dim_values_list.append(vals)

                if not valid:
                    continue

                value = row.get(field)

                for combo in product(*dim_values_list):
                    key_tuple = combo

                    if func == "COUNT":
                        buckets[key_tuple].append(1)
                    elif isinstance(value, (int, float)):
                        buckets[key_tuple].append(value)


                # if not valid:
                #     continue
                # key_tuple = tuple(key_elems)
                # val = row.get(field)
                # if func == "COUNT":
                #     buckets[key_tuple].append(1)
                # elif isinstance(val, (int, float)):
                #     buckets[key_tuple].append(val)


            def compute(vals):
                if func == "COUNT":
                    return len(vals)
                if func == "SUM":
                    return sum(vals)
                if func == "AVG":
                    vals = [v for v in vals if v is not None]
                    return round(sum(vals) / len(vals), 2) if vals else None

                    # return round(sum(vals) / len(vals), 2) if vals else None
                if func == "MAX":
                    return max(vals) if vals else None
                if func == "MIN":
                    return min(vals) if vals else None
                return None

            if not group_by:
                result[alias] = compute(buckets[tuple()])
            else:
                arr = []
                for key, vals in buckets.items():
                    row = {g: key[i] for i, g in enumerate(group_by)}
                    row[alias] = compute(vals)
                    arr.append(row)
                result[alias] = arr

        return result


    # ======================================================================
    # 🔧 POST FILTERING — HIERARCHICAL, SAFE, EXPLICIT
    # ======================================================================
    def _apply_post_filters(self, entities, post_filters):
        """
        Evaluates post_filters as a boolean expression tree.

        Supports:
        - Nested AND / OR
        - Derived metrics (post_agg)
        - Core fields (explicit fallback)
        - Null-safe numeric comparisons

        Guarantees:
        - No silent failures
        - Deterministic evaluation
        """

        # --------------------------------------------------
        # Field resolution (explicit + ordered)
        # --------------------------------------------------
        def resolve_field(ent, field):
            """
            Resolution priority:
            1️⃣ post_agg (derived metrics)
            2️⃣ core fields
            """
            if field in ent.get("post_agg", {}):
                return ent["post_agg"][field], "post_agg"

            if field in ent.get("core", {}):
                return ent["core"][field], "core"

            return None, None

        # --------------------------------------------------
        # Operator evaluation
        # --------------------------------------------------
        def eval_op(val, op, expected):
            # Normalize None
            if val is None:
                if op in ("eq", "ne"):
                    return (val == expected) if op == "eq" else (val != expected)
                return False

            try:
                if op == "eq":
                    return val == expected
                if op == "ne":
                    return val != expected
                if op == "gt":
                    return val > expected
                if op == "gte":
                    return val >= expected
                if op == "lt":
                    return val < expected
                if op == "lte":
                    return val <= expected
                if op == "in":
                    return val in expected
                if op == "isnull":
                    return (val is None) == bool(expected)
            except Exception:
                return False

            raise ValueError(f"Unsupported post_filter operator: {op}")

        # --------------------------------------------------
        # Base condition set (implicit AND)
        # --------------------------------------------------
        def eval_condition_set(ent, condition):
            """
            Example:
            { "open_risk_count__gt": 0, "x__ne": 1 }
            """
            for expr, expected in condition.items():
                if "__" not in expr:
                    raise ValueError(f"Invalid post_filter expression: {expr}")

                field, op = expr.split("__", 1)
                val, source = resolve_field(ent, field)

                # Explicit guard (future-proofing)
                if source is None:
                    return False

                if not eval_op(val, op, expected):
                    return False

            return True

        # --------------------------------------------------
        # Recursive AST evaluation
        # --------------------------------------------------
        def eval_filter_node(ent, node):
            if not isinstance(node, dict):
                raise ValueError(f"Invalid post_filter node: {node}")

            # Boolean nodes
            if "and" in node:
                children = node["and"]
                if not isinstance(children, list):
                    raise ValueError("AND node must contain a list")
                return all(eval_filter_node(ent, c) for c in children)

            if "or" in node:
                children = node["or"]
                if not isinstance(children, list):
                    raise ValueError("OR node must contain a list")
                return any(eval_filter_node(ent, c) for c in children)

            # Leaf condition set
            return eval_condition_set(ent, node)

        # --------------------------------------------------
        # Apply filters
        # --------------------------------------------------
        filtered = []
        for ent in entities:
            try:
                if all(eval_filter_node(ent, f) for f in post_filters):
                    filtered.append(ent)
            except Exception:
                # Hard fail-safe: do not include entity if filter evaluation breaks
                continue

        return filtered


    def _resolve_dimension_values(self, eid, row, dim, entity_map):
        """
        Return ALL values for a dimension.
        Supports:
        - row fields
        - core fields
        - child attributes (1-to-many)
        """

        # 1️⃣ from row
        if dim in row and not isinstance(row[dim], (dict, list)):
            return [row[dim]]

        # 2️⃣ from core
        core_val = entity_map[eid]["core"].get(dim)
        if core_val is not None:
            return [core_val]

        # 3️⃣ from child attributes (fan-out)
        values = []
        for attr, rows in entity_map[eid].items():
            if attr in ["core", "post_agg", "post_agg_grouped"]:
                continue
            if isinstance(rows, list):
                for r in rows:
                    if dim in r and r[dim] is not None:
                        values.append(r[dim])

        return values

    def _apply_global_row_filters(self, rows, filters, attr):
        from datetime import datetime

        def _to_dt(x):
            if isinstance(x, str):
                try:
                    return datetime.fromisoformat(x)
                except:
                    return x
            return x

        def match(row):
            for expr, val in filters.items():
                # field, op = expr.split("__", 1)
                if "__" in expr:
                    field, op = expr.split("__", 1)
                else:
                    # default equality if no operator provided
                    field = expr
                    op = "eq"

                v = row.get(field)

                if op == "gte" and not (v is not None and v >= val):
                    return False
                if op == "gt" and not (v is not None and v > val):
                    return False
                if op == "lte" and not (v is not None and v <= val):
                    return False
                if op == "lt" and not (v is not None and v < val):
                    return False
                if op == "eq" and v != val:
                    return False
                if op == "ne" and v == val:
                    return False
                if op == "isnull" and ((v is None) != val):
                    return False

            return True

        return [r for r in rows if match(r)]


    def _apply_row_slice(self, rows, row_slice):
        from collections import defaultdict

        group_fields = row_slice.get("group_by", [])
        order_field  = row_slice.get("order_by")
        order_desc   = row_slice.get("order", "desc") == "desc"
        limit        = row_slice.get("limit", 1)

        if not group_fields:
            return rows

        buckets = defaultdict(list)
        for r in rows:
            key = tuple(r.get(g) for g in group_fields)
            buckets[key].append(r)

        result = []
        for key, group_rows in buckets.items():
            if order_field:
                group_rows.sort(
                    key=lambda r: r.get(order_field) or "",
                    reverse=order_desc
                )
            result.extend(group_rows[:limit])

        print(f"🔪 row_slice: {len(rows)} → {len(result)} rows "
            f"(group_by={group_fields}, order={order_field}, limit={limit})")
        return result
