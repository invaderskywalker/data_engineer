# src/database/presentation_dao/interpreter.py

from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.utils.helper.common import MyJSON
from src.utils.helper.decorators import log_function_io_and_time
from src.utils.helper.event_bus import event_bus


class PresentationInterpreter:
    """
    LLM layer that converts analytical truth into a presentation projection plan.

    This layer:
    - NEVER computes
    - NEVER aggregates
    - NEVER infers
    - ONLY describes how to DISPLAY existing truth
    """

    def __init__(self, tenant_id, user_id, session_id):
        self.llm = ChatGPTClient(user_id, tenant_id)
        self.model_opts = ModelOptions(
            model="gpt-4.1",
            temperature=0.1,
            max_tokens=5000
        )
        self.session_id = session_id

    @log_function_io_and_time
    def interpret(self, evidence_snapshot: dict) -> dict:
        system_prompt = f"""
            You are a Presentation Planner.

            You receive FINAL analytical truth produced by a data engine.
            Everything is already computed and correct.

            Your ONLY job is to produce a PRESENTATION PLAN:
            - Decide what rows represent
            - Decide what columns to show
            - Decide how arrays should be displayed
            - Decide how to split data across sheets

            You MUST NOT compute, aggregate, infer, or invent any field.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            EXACT DATA STRUCTURE (READ THIS FIRST)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Each entity in the snapshot looks like this:

            {{
                "core": {{
                    "roadmap_id": 1636,
                    "roadmap_title": "...",
                    "current_stage": "Draft",
                    "roadmap_priority": "Low",
                    "roadmap_created_at": "2026-03-02T07:51:00...",
                    "roadmap_category_str": "..."
                }},
                "post_agg": {{
                    "some_metric": 42
                }},
                "post_agg_grouped": {{
                    "some_grouped_metric": [ {{ "group_field": "x", "value": 10 }} ]
                }},
                "portfolios": [
                    {{
                        "roadmap_id": 1636,
                        "portfolio_title": "Transformation Zone",
                        "portfolio_leader_first_name": "Alice",
                        "portfolio_leader_last_name": "Smith"
                    }}
                ],
                "release_cycles": [
                    {{
                        "roadmap_id": 1636,
                        "release_cycle_title": "FY27"
                    }}
                ],
                "business_members": [
                    {{
                        "roadmap_id": 1636,
                        "sponsor_first_name": "John",
                        "sponsor_last_name": "Doe",
                        "sponsor_role": "Business Sponsor"
                    }},
                    {{
                        "roadmap_id": 1636,
                        "sponsor_first_name": "Jane",
                        "sponsor_last_name": "Roe",
                        "sponsor_role": "Business Lead"
                    }}
                ]
            }}

            COLUMN KEY RULES (NON-NEGOTIABLE):
            - Fields inside "core"          → key: "core.field_name"
            - Fields inside "post_agg"      → key: "post_agg.field_name"
            - Top-level arrays (portfolios, business_members, release_cycles, etc.)
                                            → key: the array name only (e.g. "portfolios")
                                            use array_display to control rendering

            ❌ WRONG: "key": "portfolios.0.portfolio_title"
            ✅ RIGHT: "key": "portfolios", array_display: "collapse", collapse_field: "portfolio_title"

            ❌ WRONG: "key": "business_members.sponsor_first_name"
            ✅ RIGHT: "key": "business_members", array_display: "collapse", collapse_fields: [...]

            DATA SOURCE KEY RULE:
            Use the top-level entity array key from the evidence snapshot EXACTLY as data_source.
            Copy it character-for-character. Do NOT singularize, pluralize, or modify it.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ARRAY DISPLAY — THREE MODES
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Whenever a column draws from an array, you MUST pick one of these modes.
            Numeric indexing (.0, .1, etc.) is ALWAYS forbidden.

            ──────────────────────────────────────
            MODE 1 — expand  (one row per array item)
            ──────────────────────────────────────
            Use when the user wants detail per sub-item (e.g. "list each constraint").

            Set row_expansion on the sheet. Reference the alias in column keys.

            Example:
            Sheet:  row_expansion: {{ "path": "constraints", "as": "constraint" }}
            Column: {{ "key": "constraint.title", "label": "Constraint" }}

            ──────────────────────────────────────
            MODE 2 — collapse  (joined string, one row per entity)
            ──────────────────────────────────────
            Use when the user wants ONE ROW per entity.

            Single sub-field:
            {{ "key": "portfolios", "label": "Portfolio(s)",
                "array_display": "collapse", "collapse_field": "portfolio_title" }}
            Result: "Portfolio A, Portfolio B"

            Multiple sub-fields joined per item (e.g. full name):
            {{ "key": "portfolios", "label": "Portfolio Leader(s)",
                "array_display": "collapse",
                "collapse_fields": ["portfolio_leader_first_name", "portfolio_leader_last_name"],
                "collapse_fields_separator": " " }}
            Result: "Alice Smith, Bob Jones"

            ──────────────────────────────────────
            MODE 3 — pick_primary  (top ranked item, one row per entity)
            ──────────────────────────────────────
            Use when the user wants the single top/primary item from a ranked array.

            {{ "key": "portfolios", "label": "Primary Portfolio",
                "array_display": "pick_primary",
                "array_sort_by": "portfolio_rank",
                "array_sort_order": "asc",
                "collapse_field": "portfolio_title" }}
            Result: "Portfolio A"

            Supports collapse_fields for multi-field return value too.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            FULL NAME RULE (MANDATORY)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            When showing a person's name and both a first_name AND last_name field exist
            on the array item, you MUST use collapse_fields — never collapse_field alone.

            ❌ WRONG: "collapse_field": "sponsor_first_name"
            (loses last name entirely)

            ✅ RIGHT:
            "collapse_fields": ["sponsor_first_name", "sponsor_last_name"],
            "collapse_fields_separator": " "
            Result: "John Doe, Jane Roe"

            Applies to: business_members, team_data, portfolio leaders, assignees —
            any array where a person's first and last name are separate fields.


            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            SCALAR CONCAT RULE (core.* person names)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            When showing a person's name from core.* scalar fields
            (e.g. owner_first_name + owner_last_name, assignee_first_name + assignee_last_name),
            you MUST use concat_fields to merge them into ONE column.
            NEVER emit two separate columns for first/last name of the same person.

            ❌ WRONG — two separate columns:
            {{ "key": "core.owner_first_name", "label": "Created By (First Name)" }},
            {{ "key": "core.owner_last_name",  "label": "Created By (Last Name)" }}

            ✅ RIGHT — one merged column:
            {{ "key": "core.owner_first_name",
            "label": "Created By",
            "concat_fields": ["core.owner_first_name", "core.owner_last_name"],
            "concat_separator": " " }}

            The "key" must still point to one of the fields (used as the primary path).
            concat_fields lists ALL fields to join. concat_separator is the join string (default " ").

            Applies to: owner, assignee, approver, requestor — any core.* person
            where first_name and last_name are separate fields.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ARRAY FILTER — SPLIT ONE ARRAY INTO SEPARATE COLUMNS
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            When an array contains items of DIFFERENT ROLES or TYPES (e.g. business_members
            has a sponsor_role field with values "Business Sponsor", "Business Lead", etc.),
            and the user explicitly asks for each role as its own column, you MUST use
            array_filter — one column per EXPLICITLY REQUESTED role.

            ❌ WRONG — no filter, mixes all roles into one cell:
            {{ "key": "business_members", "label": "Business Sponsor",
                "array_display": "collapse",
                "collapse_fields": ["sponsor_first_name", "sponsor_last_name"] }}

            ✅ RIGHT — filtered per role:
            {{ "key": "business_members", "label": "Business Sponsor",
                "array_display": "collapse",
                "collapse_fields": ["sponsor_first_name", "sponsor_last_name"],
                "collapse_fields_separator": " ",
                "array_filter": {{ "field": "sponsor_role", "value": "Business Sponsor", "operator": "eq" }} }},
            {{ "key": "business_members", "label": "Business Lead",
                "array_display": "collapse",
                "collapse_fields": ["sponsor_first_name", "sponsor_last_name"],
                "collapse_fields_separator": " ",
                "array_filter": {{ "field": "sponsor_role", "value": "Business Lead", "operator": "eq" }} }}

            array_filter schema:
            {{
                "field":    "field_name_on_each_item",      ← REQUIRED
                "value":    "the value to match",           ← REQUIRED
                "operator": "eq | neq | contains | gt | lt" ← optional, default "eq"
            }}

            OVER-DISCOVERY RULE (NON-NEGOTIABLE):
            You MUST NOT create columns for roles or types that the user did NOT explicitly request.
            Even if the evidence snapshot contains 10 different sponsor_role values, only create
            columns for the ones named in the user's original question.

            SELF-CHECK before each array_filter column:
            "Did the user explicitly ask for this role/type by name?"
            → YES: create the column
            → NO:  do not create it

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            DECISION GUIDE — HOW TO CHOOSE THE MODE
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Q1: Does the user want ONE ROW per entity?
                YES → Q2
                NO  → use EXPAND

            Q2: Does the array need splitting into separate columns by role/type?
                YES → COLLAPSE + array_filter (one column per REQUESTED role only)
                NO  → Q3

            Q3: Does the user want only the single top/primary item?
                YES → PICK_PRIMARY
                NO  → COLLAPSE (all items joined)

            Quick reference:
            "show roadmaps with portfolios"         → COLLAPSE, collapse_field: portfolio_title
            "show portfolio leaders"                → COLLAPSE, collapse_fields: [first, last]
            "show primary portfolio"                → PICK_PRIMARY
            "list constraints per roadmap"          → EXPAND
            "show business sponsor and lead"        → COLLAPSE + array_filter per role

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            SHEET DESIGN RULES
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            1. Base Entity Sheet (REQUIRED)
            - One row per entity
            - Arrays via collapse or pick_primary (NOT expand)
            - post_agg fields allowed
            - Purpose: "summary" or "overview"

            2. Expanded Detail Sheet (add when sub-item detail is valuable)
            - Uses row_expansion
            - Entity identifiers + expanded item fields only
            - NO post_agg.* columns
            - Purpose: "detail"

            If row_expansion is used on any sheet, a base entity sheet MUST also exist.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            SEMANTIC ROW LEVELS
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            ENTITY-LEVEL   → core.* and post_agg.*   (one row per entity)
            EXPANDED-LEVEL → array elements via row_expansion (one row per sub-item)

            ❌ NEVER mix post_agg.* columns into an EXPANDED-LEVEL sheet.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            SELF-VALIDATION — RUN BEFORE RETURNING
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Check every column:

            1. No numeric indexing in any key (.0, .1, [0], [1]) → fix with array_display
            2. No array traversal without array_display set
            3. Every collapse column has collapse_field OR collapse_fields (not both)
            4. Every pick_primary column has array_sort_by set
            5. Every expanded sheet has NO post_agg.* columns
            6. Two columns from the same array for different roles → BOTH have array_filter
            7. array_filter columns exist ONLY for roles the user explicitly named
            8. Person name columns use collapse_fields when both first + last exist on the item
            9. data_source matches the top-level entity array key exactly
            10. core.* person name columns use concat_fields — never two separate first/last columns

            If any check fails → fix before returning.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            OUTPUT FORMAT (STRICT JSON)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Return ONLY this JSON, nothing else:

            {{
                "rationale": [
                    "crisp professional sentence explaining layout decisions"
                ],
                "rationale_for_user_visiblity": [
                    "very compact phrase — shown to user as progress"
                ],
                "sheets": [
                    {{
                        "sheet_id": "string",
                        "title": "string",
                        "purpose": "summary | detail | comparison | ranking | trend",
                        "data_source": "exact_top_level_key",
                        "row_expansion": {{
                            "path": "array_name",
                            "as": "alias",
                            "array_filter": {{ "field": "...", "value": "...", "operator": "eq" }} | null
                        }} | null,
                        "columns": [
                            {{
                                "key": "core.field_name OR post_agg.field_name OR array_name",
                                "label": "Human Readable Label",
                                "array_display": "collapse | expand | pick_primary | null",
                                "collapse_field": "sub_field | null",
                                "collapse_fields": ["sub_field_1", "sub_field_2"] | null,
                                "collapse_fields_separator": " | null",
                                "array_sort_by": "sub_field | null",
                                "array_sort_order": "asc | desc | null",
                                "concat_fields": ["core.field_1", "core.field_2"] | null,
                                "concat_separator": " | null",
                                "array_filter": {{
                                    "field": "discriminator_field",
                                    "value": "matching_value",
                                    "operator": "eq | neq | contains | gt | lt"
                                }} | null
                            }}
                        ],
                        "sort": {{ "field": "dot.path", "order": "asc | desc" }} | null,
                        "limit": number | null
                    }}
                ]
            }}

            Notes:
            - collapse_field and collapse_fields are mutually exclusive. Use collapse_fields
            whenever multiple sub-fields need to be joined per item (e.g. full name).
            - array_display, collapse_field, collapse_fields, array_filter are null/omitted
            for plain core.* or post_agg.* columns.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            EVIDENCE SNAPSHOT (READ-ONLY)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            {MyJSON.dumps(evidence_snapshot)}

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            FINAL SCAN BEFORE OUTPUT
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Before returning, scan ALL column keys for:
            - Numeric indexing → STOP, fix
            - Two columns sharing same array key with no array_filter → check if role split needed
            - array_filter column for a role the user never asked for → REMOVE it
            - Person name using collapse_field instead of collapse_fields → FIX

            Return ONLY valid JSON.
                    """

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user="Generate a natural, human-readable presentation plan."
        )

        llm_output = ""
        printed = set()
        import re

        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_opts,
            "tables::interpreter"
        ):
            llm_output += chunk

            if '"rationale_for_user_visiblity"' in llm_output:
                match = re.search(r'"rationale_for_user_visiblity"\s*:\s*\[([^\]]*)', llm_output, re.DOTALL)
                if match:
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    for t in items:
                        if t not in printed:
                            print(f"🧠 Thought: {t}")
                            event_bus.dispatch(
                                "THOUGHT_AI_DAO",
                                {"message": t, "size": len(printed)},
                                session_id=self.session_id
                            )
                            printed.add(t)

        print("presentation interpreter -- interpret ", llm_output)
        return extract_json_after_llm(llm_output)
    