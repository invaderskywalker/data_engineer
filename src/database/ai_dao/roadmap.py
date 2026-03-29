# src/database/ai_dao/roadmap.py

from typing import List, Dict, Any, Optional, Union
from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


class RoadmapDaoV3:
    """Modular, attribute-level DAO for roadmap data (v3 unified schema exposure)."""

    FIELD_REGISTRY = {

        # ------------------------------------------------------------------ #
        # CORE                                                                 #
        # ------------------------------------------------------------------ #
        "core": {
            "description": (
                "Primary roadmap metadata and attributes. "
                "Includes identity, dates, budget, CapEx/OpEx financials, "
                "lifecycle stage, type, priority, owner, assignee, "
                "org-strategy alignment, and solution insights."
            ),
            "table": "roadmap_roadmap",
            "alias": "rr",
            "fields": {
                "roadmap_id":                          "rr.id AS roadmap_id",
                "roadmap_title":                       "rr.title AS roadmap_title",
                "roadmap_description_str":             "rr.description AS roadmap_description",
                "roadmap_objectives_str":              "rr.objectives AS roadmap_objectives",
                "roadmap_start_date":                  "rr.start_date AS roadmap_start_date",
                "roadmap_end_date":                    "rr.end_date AS roadmap_end_date",
                "roadmap_created_at":                  "rr.created_on AS roadmap_created_at",
                "roadmap_budget":                      "rr.budget AS roadmap_budget",
                "capex_budget":                        "rr.capex_budget AS capex_budget",
                "opex_budget":                         "rr.opex_budget AS opex_budget",
                "capex_actual":                        "rr.capex_actuals AS capex_actual",
                "opex_actual":                         "rr.opex_actuals AS opex_actual",
                "capex_pr_planned":                    "rr.capex_pr_planned AS capex_pr_planned",
                "opex_pr_planned":                     "rr.opex_pr_planned AS opex_pr_planned",
                "capex_po_planned":                    "rr.capex_po_planned AS capex_po_planned",
                "opex_po_planned":                     "rr.opex_po_planned AS opex_po_planned",
                "roadmap_category_str":                "rr.category AS roadmap_category_str",
                "roadmap_org_strategy_alignment_text": "rr.org_strategy_align AS roadmap_org_strategy_alignment_text",
                "business_case_data":                  "rr.business_case AS business_case_data",
                "solution_insights":                   "rr.tango_analysis -> 'solution_insights' AS solution_insights",
                "roadmap_rank":                        "rr.rank AS roadmap_rank",
                "assigned_to_id":                      "rr.assigned_to_id AS assigned_to_id",
                "assignee_first_name":                 "au_assignee.first_name AS assignee_first_name",
                "assignee_last_name":                  "au_assignee.last_name AS assignee_last_name",
                "owner_first_name":                    "uu.first_name AS owner_first_name",
                "owner_last_name":                     "uu.last_name AS owner_last_name",
                # "is_test_data": (
                #     "CASE WHEN atd.id IS NOT NULL THEN TRUE ELSE FALSE END AS is_test_data"
                # ),
                "roadmap_priority": """CASE
                    WHEN rr.priority = 1 THEN 'Low'
                    WHEN rr.priority = 2 THEN 'Medium'
                    WHEN rr.priority = 3 THEN 'High'
                    ELSE 'Unknown' END AS roadmap_priority
                """,
                "roadmap_ref_id": "rr.ref_id AS roadmap_ref_id",
                "roadmap_type": """CASE
                    WHEN rr.type = 1  THEN 'Program'
                    WHEN rr.type = 2  THEN 'Project'
                    WHEN rr.type = 3  THEN 'Enhancement'
                    WHEN rr.type = 4  THEN 'New Development'
                    WHEN rr.type = 5  THEN 'Enhancements or Upgrade'
                    WHEN rr.type = 6  THEN 'Consume a Service'
                    WHEN rr.type = 7  THEN 'Support a Pursuit'
                    WHEN rr.type = 8  THEN 'Acquisition'
                    WHEN rr.type = 9  THEN 'Global Product Adoption'
                    WHEN rr.type = 10 THEN 'Innovation Request for NITRO'
                    WHEN rr.type = 11 THEN 'Regional Product Adoption'
                    WHEN rr.type = 12 THEN 'Client Deployment'
                    ELSE 'Unknown' END AS roadmap_type""",
                "current_stage": """CASE
                    WHEN rr.current_state = 0   THEN 'Intake'
                    WHEN rr.current_state = 1   THEN 'Approved'
                    WHEN rr.current_state = 2   THEN 'Execution'
                    WHEN rr.current_state = 3   THEN 'Archived'
                    WHEN rr.current_state = 4   THEN 'Elaboration'
                    WHEN rr.current_state = 5   THEN 'Solutioning'
                    WHEN rr.current_state = 6   THEN 'Prioritize'
                    WHEN rr.current_state = 99  THEN 'Hold'
                    WHEN rr.current_state = 100 THEN 'Rejected'
                    WHEN rr.current_state = 999 THEN 'Cancelled'
                    WHEN rr.current_state = 200 THEN 'Draft'
                    ELSE 'Unknown' END AS current_stage""",
            },
            "extra_filters": {},
            "joins": [
                "LEFT JOIN users_user uu ON rr.created_by_id = uu.id",
                "LEFT JOIN users_user au_assignee ON rr.assigned_to_id = au_assignee.id",
                # tenant_id guard on test data join — prevents cross-tenant matches
                "LEFT JOIN adminapis_test_data atd ON atd.table_pk = rr.id AND atd.table_name = 'roadmap' AND atd.tenant_id = rr.tenant_id",
            ],
            "intel": {
                "roadmap_priority": {
                    "type": "enum",
                    "column": "rr.priority",
                    "mapping": {
                        "low": 1,
                        "medium": 2,
                        "high": 3,
                    },
                },
                "roadmap_ref_id": {"type": "text"},
                "current_stage": {
                    "type": "enum",
                    "column": "rr.current_state",
                    "mapping": {
                        "intake": 0, "approved": 1, "execution": 2, "archived": 3,
                        "elaboration": 4, "solutioning": 5, "prioritize": 6,
                        "hold": 99, "rejected": 100, "cancelled": 999, "draft": 200,
                    },
                },
                "roadmap_type": {
                    "type": "enum",
                    "column": "rr.type",
                    "mapping": {
                        "program": 1, "project": 2, "enhancement": 3,
                        "new development": 4, "enhancements or upgrade": 5,
                        "consume a service": 6, "support a pursuit": 7,
                        "acquisition": 8, "global product adoption": 9,
                        "innovation request for nitro": 10,
                        "regional product adoption": 11, "client deployment": 12,
                    },
                },
                "roadmap_start_date":  {"type": "date", "column": "rr.start_date"},
                "roadmap_end_date":    {"type": "date", "column": "rr.end_date"},
                "roadmap_created_at":  {"type": "date", "column": "rr.created_on"},
                "roadmap_budget":      {"type": "number", "column": "rr.budget"},
                "roadmap_priority":    {"type": "number", "column": "rr.rank"},
                "assigned_to_id":      {"type": "number", "column": "rr.assigned_to_id"},
                "capex_budget":        {"type": "number", "column": "rr.capex_budget"},
                "opex_budget":         {"type": "number", "column": "rr.opex_budget"},
                "capex_actual":        {"type": "number", "column": "rr.capex_actuals"},
                "opex_actual":         {"type": "number", "column": "rr.opex_actuals"},
                "capex_pr_planned":    {"type": "number", "column": "rr.capex_pr_planned"},
                "opex_pr_planned":     {"type": "number", "column": "rr.opex_pr_planned"},
                "capex_po_planned":    {"type": "number", "column": "rr.capex_po_planned"},
                "opex_po_planned":     {"type": "number", "column": "rr.opex_po_planned"},
                "owner_first_name":    {"type": "pii_text", "column": "uu.first_name"},
                "owner_last_name":     {"type": "pii_text", "column": "uu.last_name"},
                "assignee_first_name": {"type": "pii_text", "column": "au_assignee.first_name"},
                "assignee_last_name":  {"type": "pii_text", "column": "au_assignee.last_name"},
                "is_test_data":        {"type": "boolean", "column": "atd.id"},
                "roadmap_category_str":                {"type": "text"},
                "roadmap_org_strategy_alignment_text": {"type": "text"},
                "solution_insights": {
                    "type": "json_clean",
                    "exclude_prefixes": [
                        "thought_process", "additional_info", "demandfileuploading",
                        "session_id", "business_value_question",
                    ],
                },
            },
        },

        # ------------------------------------------------------------------ #
        # CONSTRAINTS                                                          #
        # ------------------------------------------------------------------ #
        "constraints": {
            "description": "Constraints linked to a roadmap (Cost, Risk, Resource, Other).",
            "table": "roadmap_roadmapconstraints",
            "alias": "rrc",
            "fields": {
                "roadmap_id":       "rrc.roadmap_id",
                "constraint_title": "rrc.name AS constraint_title",
                "constraint_type":  """CASE
                    WHEN rrc.type = 1 THEN 'Cost'
                    WHEN rrc.type = 2 THEN 'Risk'
                    WHEN rrc.type = 3 THEN 'Resource'
                    ELSE 'Other' END AS constraint_type""",
            },
            "intel": {
                "constraint_type": {
                    "type": "enum",
                    "column": "rrc.type",
                    "mapping": {"cost": 1, "risk": 2, "resource": 3, "other": 4},
                },
                "constraint_title": {"type": "text"},
            },
        },

        # ------------------------------------------------------------------ #
        # PORTFOLIOS                                                           #
        # ------------------------------------------------------------------ #
        "portfolios": {
            "description": "Portfolios this roadmap belongs to, including per-portfolio rank.",
            "table": "roadmap_roadmapportfolio",
            "alias": "rp",
            "joins": [
                "JOIN projects_portfolio pp ON rp.portfolio_id = pp.id",
            ],
            "fields": {
                "roadmap_id":     "rp.roadmap_id",
                "portfolio_id":   "pp.id AS portfolio_id",
                "portfolio_title":"pp.title AS portfolio_title",
                "portfolio_rank": "rp.rank AS portfolio_rank",
                "portfolio_leader_first_name": "pp.first_name AS portfolio_leader_first_name",
                "portfolio_leader_last_name": "pp.last_name AS portfolio_leader_last_name",
            },
            "intel": {
                "portfolio_title": {"type": "text"},
                "portfolio_rank":  {"type": "number", "column": "rp.rank"},
                "portfolio_id":    {"type": "number", "column": "pp.id"},
                "portfolio_leader_first_name":    {"type": "pii_text", "column": "pp.first_name"},
                "portfolio_leader_last_name":    {"type": "pii_text", "column": "pp.first_name"},
            },
        },

        # ------------------------------------------------------------------ #
        # RELEASE CYCLES  (demand queue)                                       #
        # ------------------------------------------------------------------ #
        "release_cycles": {
            "description": (
                "Release cycles (demand queue / roadmap queue / plan queue) "
                "that this roadmap is scheduled into. "
                "Root is roadmap_roadmap; release cycle tables are LEFT JOINed so "
                "roadmaps with no cycle are still returned (NULL cycle fields). "
                "Filtering on release_cycle_title narrows to matched cycles only."
            ),
            "table": "roadmap_roadmap",
            "alias": "rr",
            "joins": [
                "LEFT JOIN roadmap_roadmapreleasecycle rrcycle "
                "ON rr.id = rrcycle.roadmap_id AND rrcycle.tenant_id = rr.tenant_id",
                "LEFT JOIN tenant_release_cycles trc "
                "ON rrcycle.release_cycle_id = trc.id AND trc.tenant_id = rr.tenant_id",
            ],
            "fields": {
                "roadmap_id":               "rr.id AS roadmap_id",
                "release_cycle_id":         "trc.id AS release_cycle_id",
                "release_cycle_title":      "trc.title AS release_cycle_title",
                "release_cycle_start_date": "trc.start_date AS release_cycle_start_date",
                "release_cycle_end_date":   "trc.end_date AS release_cycle_end_date",
            },
            "intel": {
                # iexact → ILIKE without % wrapping for structured labels like "FY27"
                "release_cycle_title":      {"type": "ilike", "column": "trc.title"},
                "release_cycle_start_date": {"type": "date",   "column": "trc.start_date"},
                "release_cycle_end_date":   {"type": "date",   "column": "trc.end_date"},
                "release_cycle_id":         {"type": "number", "column": "trc.id"},
            },
        },

        # ------------------------------------------------------------------ #
        # KEY RESULTS  (KPIs)                                                  #
        # ------------------------------------------------------------------ #
        "key_results": {
            "description": "Key results / KPIs linked to the roadmap.",
            "table": "roadmap_roadmapkpi",
            "alias": "rrkpi",
            "fields": {
                "roadmap_id":       "rrkpi.roadmap_id",
                "key_result_title": "rrkpi.name AS key_result_title",
                "baseline_value":   "rrkpi.baseline_value AS baseline_value",
            },
            "intel": {
                "key_result_title": {"type": "text"},
                # baseline_value is stored as text in DB — keep as text for ILIKE search;
                # cast to numeric only happens in post-agg formulas
                "baseline_value":   {"type": "text"},
            },
        },

        # ------------------------------------------------------------------ #
        # TEAM DATA  (estimates / effort)                                      #
        # ------------------------------------------------------------------ #
        "team_data": {
            "description": (
                "Team effort, estimation, and cost breakdown per roadmap. "
                "Covers both labour and non-labour entries."
            ),
            "table": "roadmap_roadmapestimate",
            "alias": "rrt",
            "fields": {
                "roadmap_id":     "rrt.roadmap_id",
                "team_name":      "rrt.name AS team_name",
                "team_unit_size": "rrt.unit AS team_unit_size",
                "unit_type": """CASE
                    WHEN rrt.type = 1 THEN 'days'
                    WHEN rrt.type = 2 THEN 'months'
                    WHEN rrt.type = 3 THEN 'weeks'
                    WHEN rrt.type = 4 THEN 'hours'
                    ELSE 'Unknown' END AS unit_type""",
                "labour_type": """CASE
                    WHEN rrt.labour_type = 1 THEN 'labour'
                    WHEN rrt.labour_type = 2 THEN 'non labour'
                    ELSE 'Unknown' END AS labour_type""",
                "description":  "rrt.description AS description",
                "start_date":   "rrt.start_date AS start_date",
                "end_date":     "rrt.end_date AS end_date",
                "location":     "rrt.location AS location",
                "allocation":   "rrt.allocation AS allocation",
                "total_estimated_hours": """CASE
                    WHEN rrt.type = 1 THEN rrt.unit * 8
                    WHEN rrt.type = 2 THEN rrt.unit * 160
                    WHEN rrt.type = 3 THEN rrt.unit * 40
                    WHEN rrt.type = 4 THEN rrt.unit
                    ELSE 0 END AS total_estimated_hours""",
                # escape the backslash so Python doesn't mangle the regex
                "total_estimated_cost": r"""CASE
                    WHEN rrt.labour_type = 1 THEN
                        COALESCE(
                            NULLIF(regexp_replace(rrt.estimate_value, '[^0-9.]', '', 'g'), '')::NUMERIC,
                            0
                        ) * CASE
                            WHEN rrt.type = 1 THEN rrt.unit * 8
                            WHEN rrt.type = 2 THEN rrt.unit * 160
                            WHEN rrt.type = 3 THEN rrt.unit * 40
                            WHEN rrt.type = 4 THEN rrt.unit
                            ELSE 0 END
                    WHEN rrt.labour_type = 2 THEN
                        COALESCE(
                            NULLIF(regexp_replace(rrt.estimate_value, '[^0-9.]', '', 'g'), '')::NUMERIC,
                            0
                        )
                    ELSE 0 END AS total_estimated_cost""",
            },
            "intel": {
                "labour_type": {
                    "type": "enum",
                    "column": "rrt.labour_type",
                    "mapping": {"labour": 1, "non labour": 2},
                },
                "unit_type": {
                    "type": "enum",
                    "column": "rrt.type",
                    "mapping": {"days": 1, "months": 2, "weeks": 3, "hours": 4},
                },
                "start_date":            {"type": "date",   "column": "rrt.start_date"},
                "end_date":              {"type": "date",   "column": "rrt.end_date"},
                "description":           {"type": "text"},
                "team_name":             {"type": "text"},
                "location":              {"type": "text"},
                "total_estimated_hours": {"type": "number"},
                "total_estimated_cost":  {"type": "number"},
                "team_unit_size":        {"type": "number"},
                "allocation":            {"type": "number"},
            },
        },

        # ------------------------------------------------------------------ #
        # SCOPES                                                               #
        # ------------------------------------------------------------------ #
        "scopes": {
            "description": "Scope items attached to the roadmap.",
            "table": "roadmap_roadmapscope",
            "alias": "rrs",
            "fields": {
                "roadmap_id": "rrs.roadmap_id",
                "scope_name": "rrs.name AS scope_name",
            },
            "intel": {
                "scope_name": {"type": "text"},
            },
        },

        # ------------------------------------------------------------------ #
        # APPROVAL HISTORY                                                     #
        # ------------------------------------------------------------------ #
        "approval_history": {
            "description": (
                "Approval requests and state transitions for the roadmap. "
                "Tracks who requested, who approved/rejected, when, and comments."
            ),
            "table": "authorization_approval_request",
            "alias": "aar",
            "joins": [
                "LEFT JOIN users_user au ON aar.approver_id = au.id",
                "LEFT JOIN users_user ru ON aar.requestor_id = ru.id",
            ],
            "fields": {
                # roadmap_id comes from request_id when request_type = 1 (Roadmap)
                "roadmap_id":               "aar.request_id AS roadmap_id",
                "request_type": """CASE
                    WHEN aar.request_type = 1 THEN 'Roadmap'
                    WHEN aar.request_type = 2 THEN 'Project'
                    ELSE 'Unknown' END AS request_type""",
                "request_date":             "aar.request_date AS request_date",
                # from_state / to_state decoded to human-readable stage labels
                "from_state": """CASE
                    WHEN aar.from_state = 0   THEN 'Intake'
                    WHEN aar.from_state = 1   THEN 'Approved'
                    WHEN aar.from_state = 2   THEN 'Execution'
                    WHEN aar.from_state = 3   THEN 'Archived'
                    WHEN aar.from_state = 4   THEN 'Elaboration'
                    WHEN aar.from_state = 5   THEN 'Solutioning'
                    WHEN aar.from_state = 6   THEN 'Prioritize'
                    WHEN aar.from_state = 99  THEN 'Hold'
                    WHEN aar.from_state = 100 THEN 'Rejected'
                    WHEN aar.from_state = 999 THEN 'Cancelled'
                    WHEN aar.from_state = 200 THEN 'Draft'
                    ELSE 'Unknown' END AS from_state""",
                "to_state": """CASE
                    WHEN aar.to_state = 0   THEN 'Intake'
                    WHEN aar.to_state = 1   THEN 'Approved'
                    WHEN aar.to_state = 2   THEN 'Execution'
                    WHEN aar.to_state = 3   THEN 'Archived'
                    WHEN aar.to_state = 4   THEN 'Elaboration'
                    WHEN aar.to_state = 5   THEN 'Solutioning'
                    WHEN aar.to_state = 6   THEN 'Prioritize'
                    WHEN aar.to_state = 99  THEN 'Hold'
                    WHEN aar.to_state = 100 THEN 'Rejected'
                    WHEN aar.to_state = 999 THEN 'Cancelled'
                    WHEN aar.to_state = 200 THEN 'Draft'
                    ELSE 'Unknown' END AS to_state""",
                "approver_id":              "aar.approver_id AS approver_id",
                "requestor_id":             "aar.requestor_id AS requestor_id",
                "approval_status": """CASE
                    WHEN aar.approval_status = 1 THEN 'Pending'
                    WHEN aar.approval_status = 2 THEN 'Approved'
                    WHEN aar.approval_status = 3 THEN 'Rejected'
                    ELSE 'Unknown' END AS approval_status""",
                "request_comments":         "aar.request_comments AS request_comments",
                "approval_reject_comments": "aar.approval_reject_comments AS approval_reject_comments",
                "approval_reject_date":     "aar.approval_reject_date AS approval_reject_date",
                "approver_first_name":      "au.first_name AS approver_first_name",
                "approver_last_name":       "au.last_name AS approver_last_name",
                "requestor_first_name":     "ru.first_name AS requestor_first_name",
                "requestor_last_name":      "ru.last_name AS requestor_last_name",
            },
            "intel": {
                "approval_status": {
                    "type": "enum",
                    "column": "aar.approval_status",
                    "mapping": {"pending": 1, "approved": 2, "rejected": 3},
                },
                "request_type": {
                    "type": "enum",
                    "column": "aar.request_type",
                    "mapping": {"roadmap": 1, "project": 2},
                },
                # from_state / to_state are now text labels in SELECT,
                # but intel still points to the raw integer column for WHERE filtering
                "from_state": {
                    "type": "enum",
                    "column": "aar.from_state",
                    "mapping": {
                        "intake": 0, "approved": 1, "execution": 2, "archived": 3,
                        "elaboration": 4, "solutioning": 5, "prioritize": 6,
                        "hold": 99, "rejected": 100, "cancelled": 999, "draft": 200,
                    },
                },
                "to_state": {
                    "type": "enum",
                    "column": "aar.to_state",
                    "mapping": {
                        "intake": 0, "approved": 1, "execution": 2, "archived": 3,
                        "elaboration": 4, "solutioning": 5, "prioritize": 6,
                        "hold": 99, "rejected": 100, "cancelled": 999, "draft": 200,
                    },
                },
                "request_date":         {"type": "date", "column": "aar.request_date"},
                "approval_reject_date": {"type": "date", "column": "aar.approval_reject_date"},
                "approver_id":          {"type": "number", "column": "aar.approver_id"},
                "requestor_id":         {"type": "number", "column": "aar.requestor_id"},
                "approver_first_name":  {"type": "pii_text", "column": "au.first_name"},
                "approver_last_name":   {"type": "pii_text", "column": "au.last_name"},
                "requestor_first_name": {"type": "pii_text", "column": "ru.first_name"},
                "requestor_last_name":  {"type": "pii_text", "column": "ru.last_name"},
                "request_comments":         {"type": "text"},
                "approval_reject_comments": {"type": "text"},
            },
        },



        # ------------------------------------------------------------------ #
        # STAGE DURATIONS                                                      #
        # ------------------------------------------------------------------ #
        #
        # How it works:
        #
        #   1. We anchor the first stage using rr.created_on (roadmap_created_at).
        #      That row has:  stage = initial to_state of first approval row
        #                     OR we derive it by treating created_on as the
        #                     entry into the "Intake" (state=0) stage.
        #
        #   2. Every approval row's `request_date` marks the moment the roadmap
        #      ENTERED `to_state`.  So:
        #
        #        stage_start  = request_date  of the row where to_state = this stage
        #        stage_end    = request_date  of the NEXT transition (LEAD window)
        #                       or CURRENT_DATE if it's the last / active stage
        #
        #   3. duration_days = stage_end - stage_start
        #
        # Timeline anchor row (synthetic):
        #   We UNION a row that represents "entered Intake at created_on" so the
        #   very first stage is covered even when no approval row exists yet.
        #
        # ------------------------------------------------------------------ #

        # ── Add to FIELD_REGISTRY ────────────────────────────────────────────

        "stage_durations": {
            "description": (
                "Time spent (in days) by a roadmap in each lifecycle stage. "
                "Derived from the approval-history state-transition log. "
                "The first stage is anchored at roadmap_created_at (rr.created_on). "
                "The active (current) stage is open-ended up to CURRENT_DATE. "
                "Each row = one stage visit for one roadmap."
            ),
            # Root table is roadmap_roadmap so we can LEFT JOIN approval history
            # and still return rows for roadmaps with zero transitions.
            "table": "roadmap_roadmap",
            "alias": "rr",
            "joins": [],          # all joining is done inside the CTE; build_query not used
            "fields": {
                "roadmap_id":       "sd.roadmap_id",
                "stage_name":       "sd.stage_name",
                "stage_start_date": "sd.stage_start_date",
                "stage_end_date":   "sd.stage_end_date",
                "duration_days":    "sd.duration_days",
                "is_current_stage": "sd.is_current_stage",
            },
            "intel": {
                "stage_name": {
                    "type": "enum",
                    "column": "sd.stage_name",          # post-decoded label, not int
                    "mapping": {
                        "intake": "Intake", "approved": "Approved",
                        "execution": "Execution", "archived": "Archived",
                        "elaboration": "Elaboration", "solutioning": "Solutioning",
                        "prioritize": "Prioritize", "hold": "Hold",
                        "rejected": "Rejected", "cancelled": "Cancelled",
                        "draft": "Draft",
                    },
                },
                "duration_days":    {"type": "number"},
                "stage_start_date": {"type": "date", "column": "sd.stage_start_date"},
                "stage_end_date":   {"type": "date", "column": "sd.stage_end_date"},
                "is_current_stage": {"type": "boolean"},
            },
        },

        # ------------------------------------------------------------------ #
        # PARENT IDEAS                                                         #
        # ------------------------------------------------------------------ #
        "parent_ideas": {
            "description": (
                "Lineage mapping showing the Idea from which this roadmap was created. "
                "Optional — not all roadmaps originate from ideas. "
                "Used for lifecycle traceability and strategic lineage analysis."
            ),
            "table": "roadmap_roadmapideamap",
            "alias": "ir",
            "joins": [
                # tenant guard on idea_concept join
                "JOIN idea_concept ic ON ic.id = ir.idea_id AND ic.tenant_id = ir.tenant_id",
            ],
            "fields": {
                "roadmap_id":         "ir.roadmap_id",
                "parent_idea_id":     "ic.id AS parent_idea_id",
                "parent_idea_title":  "ic.title AS parent_idea_title",
                "idea_category":      "ic.category AS idea_category",
                "idea_budget":        "ic.budget AS idea_budget",
                "idea_start_date":    "ic.start_date AS idea_start_date",
                "idea_end_date":      "ic.end_date AS idea_end_date",
                "idea_current_state": """CASE
                    WHEN ic.current_state = 0 THEN 'Intake'
                    WHEN ic.current_state = 1 THEN 'Approved'
                    WHEN ic.current_state = 2 THEN 'Execution'
                    WHEN ic.current_state = 3 THEN 'Archived'
                    ELSE 'Unknown' END AS idea_current_state""",
            },
            "intel": {
                "parent_idea_title": {"type": "text"},
                "idea_category":     {"type": "text"},
                "idea_budget":       {"type": "number"},
                "idea_start_date":   {"type": "date", "column": "ic.start_date"},
                "idea_end_date":     {"type": "date", "column": "ic.end_date"},
                "idea_current_state": {
                    "type": "enum",
                    "column": "ic.current_state",
                    "mapping": {
                        "intake": 0, "approved": 1, "execution": 2, "archived": 3,
                    },
                },
            },
        },

        # ------------------------------------------------------------------ #
        # DEPENDENCIES                                                         #
        # ------------------------------------------------------------------ #
        "dependencies": {
            "description": (
                "Roadmap dependency graph. "
                "'depends_on' = this roadmap is blocked by another; "
                "'required_by' = other roadmaps depend on this one."
            ),
            # Root is roadmap_roadmap (alias rr)
            "table": "roadmap_roadmap",
            "alias": "rr",
            "joins": [
                # tenant guard on dependency join
                "JOIN roadmap_roadmap_dependency d "
                "ON rr.id IN (d.roadmap_id, d.dependent_roadmap_id) "
                "AND d.tenant_id = rr.tenant_id",
                "JOIN roadmap_roadmap other_rr "
                "ON other_rr.id = CASE "
                "WHEN d.roadmap_id = rr.id THEN d.dependent_roadmap_id "
                "ELSE d.roadmap_id END "
                "AND other_rr.tenant_id = rr.tenant_id",
            ],
            "fields": {
                "roadmap_id":           "rr.id AS roadmap_id",
                "relation": """CASE
                    WHEN d.roadmap_id = rr.id THEN 'depends_on'
                    ELSE 'required_by'
                END AS relation""",
                "dependency_reason":    "d.description AS dependency_reason",
                "dependency_type": """CASE d.dependency_type
                    WHEN 1 THEN 'Technical'
                    WHEN 2 THEN 'Functional'
                    WHEN 3 THEN 'Resource'
                    WHEN 4 THEN 'Sequence'
                    WHEN 5 THEN 'Risk'
                    WHEN 6 THEN 'Compliance'
                    ELSE 'Unknown'
                END AS dependency_type""",
                "related_roadmap_title": "other_rr.title AS related_roadmap_title",
            },
            "intel": {
                "dependency_type": {
                    "type": "enum",
                    "column": "d.dependency_type",
                    "mapping": {
                        "technical": 1, "functional": 2, "resource": 3,
                        "sequence": 4, "risk": 5, "compliance": 6,
                    },
                },
                "related_roadmap_title": {"type": "text"},
                "dependency_reason":     {"type": "text"},
            },
        },

        # ------------------------------------------------------------------ #
        # BUSINESS MEMBERS  (sponsors / stakeholders)                         #
        # ------------------------------------------------------------------ #
        "business_members": {
            "description": """
                Business sponsors and stakeholders linked to the roadmap.
                Each row = one business sponsor/stakeholder entry for a roadmap.

                ALSO REFERRED TO AS:
                • business sponsors / business members / stakeholders
                • business lead / business owner / business representative
                • BU sponsor / BU lead / business unit contact

                FIELDS:
                • sponsor_first_name / sponsor_last_name → person's full name
                • sponsor_email                          → contact email (PII)
                • sponsor_role                           → role/title of the person
                (e.g. 'Business Lead', 'Business Sponsor', 'Stakeholder', 'BU Lead')
                • business_unit                          → the business unit they represent

                USE when user asks about:
                - who is the business sponsor / lead / owner of a roadmap
                - which business unit is associated with a roadmap
                - stakeholder contact details
                - roadmaps owned or sponsored by a specific person or BU

                FILTER GUIDANCE — ROLE-BASED LOOKUPS (CRITICAL):
                When user says "business lead"    → filter: { "sponsor_role__icontains": "lead" }
                When user says "business sponsor" → filter: { "sponsor_role__icontains": "sponsor" }
                When user says "business owner"   → filter: { "sponsor_role__icontains": "owner" }
                When user says "stakeholder"      → filter: { "sponsor_role__icontains": "stakeholder" }
                When user says "BU lead"          → filter: { "sponsor_role__icontains": "lead" }

                For person name lookups → filter on sponsor_first_name or sponsor_last_name.
                For business unit lookups → filter: { "business_unit__icontains": "<bu name>" }

                IMPORTANT — DISPLAY vs FILTER:
                • If the user asks to LIST business sponsors/leads → fetch this attr with NO filter,
                return all rows and let the response show the role column.
                • If the user asks to FILTER roadmaps BY a specific role (e.g. "show roadmaps
                where business lead is X") → apply role filter + name PII post-filter.

                NOTE ON PII:
                sponsor_first_name, sponsor_last_name, and sponsor_email are PII fields.
                They are filtered in Python post-SQL, NOT in the SQL WHERE clause.
                Always include both first and last name fields for name-based lookups.
            """,
            "table": "roadmap_roadmapbusinessmember",
            "alias": "rrbm",
            "joins": [
                "JOIN projects_portfoliobusiness pb "
                "ON pb.id = rrbm.portfolio_business_id"
            ],
            "fields": {
                "roadmap_id":         "rrbm.roadmap_id",
                "sponsor_first_name": "pb.sponsor_first_name AS sponsor_first_name",
                "sponsor_last_name":  "pb.sponsor_last_name AS sponsor_last_name",
                "sponsor_email":      "pb.sponsor_email AS sponsor_email",
                "sponsor_role":       "pb.sponsor_role AS sponsor_role",
                "business_unit":      "pb.bu_name AS business_unit",
            },
            "intel": {
                "sponsor_first_name": {"type": "pii_text", "column": "pb.sponsor_first_name"},
                "sponsor_last_name":  {"type": "pii_text", "column": "pb.sponsor_last_name"},
                "sponsor_email":      {"type": "pii_text", "column": "pb.sponsor_email"},
                "sponsor_role":       {"type": "text"},
                "business_unit":      {"type": "text"},
            },
        }
    }

    # ================================================================== #
    # CORE                                                                 #
    # ================================================================== #
    @staticmethod
    def fetch_core(
        roadmap_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rr.tenant_id = %s"]
        params: List[Any] = [tenant_id]

        if roadmap_ids:
            where.append("rr.id = ANY(%s)")
            params.append(roadmap_ids)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        bucket_interval = bucket_field = bucket_alias_field = None
        if isinstance(time_bucket, dict):
            bucket_field       = time_bucket.get("field", "roadmap_start_date")
            bucket_interval    = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field       = "roadmap_start_date"
            bucket_interval    = time_bucket
            bucket_alias_field = bucket_field

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            limit=limit,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        results = FieldIntel.post_process(results, intel)
        results = FieldIntel.post_execute(results, normalized_filters, intel)
        return results

    # ================================================================== #
    # CONSTRAINTS                                                          #
    # ================================================================== #
    @staticmethod
    def fetch_constraints(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("constraints")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rrc.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # PORTFOLIOS                                                           #
    # ================================================================== #
    @staticmethod
    def fetch_portfolios(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("portfolios")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]
        alias = meta["alias"]

        where = [f"{alias}.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {},
            intel=intel,
            fields=all_fields,
            alias=alias,
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=meta["table"],
            joins=meta.get("joins", []),
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # RELEASE CYCLES                                                       #
    # ================================================================== #
    @staticmethod
    def fetch_release_cycles(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("release_cycles")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        # Resolve SELECT expressions
        selected = fields or list(all_fields.keys())
        select_exprs = [all_fields[f] for f in selected if f in all_fields]
        select_clause = ", ".join(select_exprs)

        # Normalize filters
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )
        print("debug normalized_filters-- ", normalized_filters)

        # Build WHERE
        where_parts: List[str] = []
        params: List[Any] = []

        where_parts.append("rr.id = ANY(%s)")
        params.append(roadmap_ids)

        if tenant_id:
            where_parts.append("rr.tenant_id = %s")
            params.append(tenant_id)

        if normalized_filters:
            filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
                normalized_filters,
                alias=meta["alias"],
                fields_map=all_fields,
            )
            if filter_sql:
                where_parts.append(filter_sql)
                params.extend(filter_params)

        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        # Optional time bucket — appended to SELECT only
        bucket_expr = ""
        if time_bucket:
            if isinstance(time_bucket, dict):
                tb_field         = time_bucket.get("field", "release_cycle_start_date")
                tb_interval      = time_bucket.get("interval", "month")
                bucket_alias_fld = time_bucket.get("alias") or tb_field
            else:
                tb_field         = "release_cycle_start_date"
                tb_interval      = time_bucket
                bucket_alias_fld = tb_field

            base_col = all_fields.get(tb_field, tb_field).split(" AS ")[0].strip()
            bucket_expr = f", DATE_TRUNC('{tb_interval}', {base_col}) AS {bucket_alias_fld}"

        # DISTINCT ON (rr.id) deduplicates — ORDER BY must start with rr.id
        # order_clause = f"ORDER BY rr.id, {order_by}" if order_by else "ORDER BY rr.id"
        order_clause = f"ORDER BY rr.id, {order_by}" if order_by else "ORDER BY rr.id, trc.start_date DESC NULLS LAST"
        
        joins = " ".join(meta.get("joins", []))

        query = f"""
            SELECT DISTINCT ON (rr.id)
                {select_clause}{bucket_expr}
            FROM {meta['table']} {meta['alias']}
            {joins}
            {where_clause}
            {order_clause}
        """.strip()

        appLogger.debug({
            "method": "fetch_release_cycles",
            "query": query,
            "params": params,
        })
        return db_instance.execute_query_safe(query, tuple(params))

    # ================================================================== #
    # KEY RESULTS                                                          #
    # ================================================================== #
    @staticmethod
    def fetch_key_results(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("key_results")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rrkpi.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            group_by=group_by,
            order_by=order_by,
        )

        appLogger.debug({
            "method": "fetch_key_results",
            "filters": normalized_filters,
            "selected_fields": fields,
            "query": query,
        })
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # TEAM DATA                                                            #
    # ================================================================== #
    @staticmethod
    def fetch_team_data(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        sample_rate: float = 1.0,
        group_by: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("team_data")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rrt.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        bucket_interval = bucket_field = bucket_alias_field = None
        if isinstance(time_bucket, dict):
            bucket_field       = time_bucket.get("field", "start_date")
            bucket_interval    = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field       = "start_date"
            bucket_interval    = time_bucket
            bucket_alias_field = bucket_field

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            sample_rate=sample_rate,
            group_by=group_by,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
            order_by=order_by,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # SCOPES                                                               #
    # ================================================================== #
    @staticmethod
    def fetch_scopes(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("scopes")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rrs.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # APPROVAL HISTORY                                                     #
    # ================================================================== #
    @staticmethod
    def fetch_approval_history(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("approval_history")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        # request_type = 1 scopes to roadmap approvals only
        where = ["aar.request_id = ANY(%s)", "aar.request_type = 1"]
        params: List[Any] = [roadmap_ids]

        if tenant_id:
            where.append("aar.tenant_id = %s")
            params.append(tenant_id)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        results = FieldIntel.post_execute(results, normalized_filters, intel)
        return results


# ================================================================== #
    # STAGE DURATIONS                                                      #
    # ================================================================== #
    @staticmethod
    def fetch_stage_durations(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict]:
        """
        Returns one row per (roadmap, stage-visit) with:
            roadmap_id, stage_name, stage_start_date,
            stage_end_date, duration_days, is_current_stage

        Logic
        -----
        Two cases handled:

        Case 1 — Roadmap HAS approval history transitions:
            Each approval row's `request_date` marks when the roadmap
            entered `to_state`. LEAD() gives the next transition date
            as the end of the current stage.

        Case 2 — Roadmap has NO approval history:
            We fall back to a synthetic row using rr.current_state
            (the actual current stage) and rr.created_on as start date.
            This ensures these roadmaps still appear with correct stage
            and duration = (today - created_on).

        The UNION approach:
            - Real transitions from approval history (to_state, request_date)
            - Fallback anchor for roadmaps with zero transitions
              (current_state, created_on) — filtered out when real rows exist
              via LEFT JOIN check
        """
        meta = RoadmapDaoV3._get_section("stage_durations")
        intel = meta.get("intel", {})

        # ── field selection ──────────────────────────────────────────────
        all_fields    = meta["fields"]
        selected      = fields or list(all_fields.keys())
        select_exprs  = [all_fields[f] for f in selected if f in all_fields]
        select_clause = ", ".join(select_exprs)

        # ── tenant guards ────────────────────────────────────────────────
        if tenant_id:
            tenant_filter_anchor  = "AND rr.tenant_id = %s"
            tenant_filter_history = "AND aar.tenant_id = %s"
        else:
            tenant_filter_anchor  = ""
            tenant_filter_history = ""

        # ── optional outer WHERE filters ────────────────────────────────
        filter_sql    = ""
        filter_params: List[Any] = []
        extra_where_parts: List[str] = []

        normalized_filters = FieldIntel.normalize_filters(
            filters or {},
            intel=intel,
            fields=all_fields,
            alias="sd",
        )
        if normalized_filters:
            filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
                normalized_filters,
                alias="sd",
                fields_map=all_fields,
            )
            if filter_sql:
                extra_where_parts.append(filter_sql)

        outer_where  = ("WHERE " + " AND ".join(extra_where_parts)) if extra_where_parts else ""
        order_clause = "ORDER BY sd.roadmap_id, sd.stage_start_date" + (
            f", {order_by}" if order_by else ""
        )

        STATE_DECODE = """
            CASE state_int
                WHEN 0   THEN 'Intake'
                WHEN 1   THEN 'Approved'
                WHEN 2   THEN 'Execution'
                WHEN 3   THEN 'Archived'
                WHEN 4   THEN 'Elaboration'
                WHEN 5   THEN 'Solutioning'
                WHEN 6   THEN 'Prioritize'
                WHEN 99  THEN 'Hold'
                WHEN 100 THEN 'Rejected'
                WHEN 999 THEN 'Cancelled'
                WHEN 200 THEN 'Draft'
                ELSE 'Unknown'
            END
        """

        query = f"""
            WITH

            -- ── Real transitions from approval history ──────────────────
            real_transitions AS (
                SELECT
                    aar.request_id   AS roadmap_id,
                    aar.to_state     AS state_int,
                    aar.request_date AS stage_start_date
                FROM authorization_approval_request aar
                WHERE aar.request_id = ANY(%s)
                  AND aar.request_type = 1
                {tenant_filter_history}
            ),

            -- ── Roadmaps that have at least one real transition ──────────
            roadmaps_with_history AS (
                SELECT DISTINCT roadmap_id FROM real_transitions
            ),

            -- ── Fallback anchor for roadmaps with NO approval history ────
            -- Uses current_state so the stage label is actually correct
            fallback_anchor AS (
                SELECT
                    rr.id            AS roadmap_id,
                    rr.current_state AS state_int,
                    rr.created_on    AS stage_start_date
                FROM roadmap_roadmap rr
                WHERE rr.id = ANY(%s)
                  {tenant_filter_anchor}
                  AND NOT EXISTS (
                      SELECT 1 FROM roadmaps_with_history rwh
                      WHERE rwh.roadmap_id = rr.id
                  )
            ),

            -- ── Combined transitions ─────────────────────────────────────
            all_transitions AS (
                SELECT * FROM real_transitions
                UNION ALL
                SELECT * FROM fallback_anchor
            ),

            -- ── Compute stage windows via LEAD ───────────────────────────
            stage_windows AS (
                SELECT
                    roadmap_id,
                    {STATE_DECODE}     AS stage_name,
                    stage_start_date,
                    LEAD(stage_start_date)
                        OVER (
                            PARTITION BY roadmap_id
                            ORDER BY stage_start_date
                        )              AS stage_end_date
                FROM all_transitions
            ),

            -- ── Materialise computed columns so WHERE can reference them ─
            stage_final AS (
                SELECT
                    roadmap_id,
                    stage_name,
                    stage_start_date,
                    COALESCE(stage_end_date, CURRENT_DATE)          AS stage_end_date,
                    (COALESCE(stage_end_date, CURRENT_DATE)
                        - stage_start_date::date)                   AS duration_days,
                    (stage_end_date IS NULL)                        AS is_current_stage
                FROM stage_windows
            )

            SELECT
                sd.roadmap_id,
                sd.stage_name,
                sd.stage_start_date,
                sd.stage_end_date,
                sd.duration_days,
                sd.is_current_stage
            FROM stage_final sd
            {outer_where}
            {order_clause}
        """

        # Param order matches placeholders in query:
        #   1. real_transitions  WHERE aar.request_id = ANY(%s)
        #   2. tenant_id         AND aar.tenant_id = %s  (if set)
        #   3. fallback_anchor   WHERE rr.id = ANY(%s)
        #   4. tenant_id         AND rr.tenant_id = %s   (if set)
        #   5. filter_params     outer WHERE              (may be empty)
        full_params = tuple(
            [roadmap_ids]
            + ([tenant_id] if tenant_id else [])
            + [roadmap_ids]
            + ([tenant_id] if tenant_id else [])
            + filter_params
        )

        appLogger.debug({
            "method": "fetch_stage_durations",
            "query": query,
            "params": full_params,
        })

        results = db_instance.execute_query_safe(query, full_params)
        results = FieldIntel.post_execute(results, normalized_filters, intel)
        return results
    

    # ================================================================== #
    # PARENT IDEAS                                                         #
    # ================================================================== #
    @staticmethod
    def fetch_parent_ideas(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("parent_ideas")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["ir.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        # tenant scoped via the JOIN (ic.tenant_id = ir.tenant_id) in registry
        # but also add explicit guard when tenant_id is passed
        if tenant_id:
            where.append("ir.tenant_id = %s")
            params.append(tenant_id)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # DEPENDENCIES                                                         #
    # ================================================================== #
    @staticmethod
    def fetch_dependencies(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("dependencies")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rr.id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        if tenant_id:
            where.append("rr.tenant_id = %s")
            params.append(tenant_id)

        # alias must be "rr" — dependency intel columns carry explicit d.* references
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias="rr",
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias="rr",
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # ================================================================== #
    # BUSINESS MEMBERS                                                     #
    # ================================================================== #
    @staticmethod
    def fetch_business_members(
        roadmap_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        meta = RoadmapDaoV3._get_section("business_members")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = ["rrbm.roadmap_id = ANY(%s)"]
        params: List[Any] = [roadmap_ids]

        # tenant guard is in the JOIN; add explicit WHERE guard too
        if tenant_id:
            where.append("pb.tenant_id = %s")
            params.append(tenant_id)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        results = FieldIntel.post_process(results, intel)
        results = FieldIntel.post_execute(results, normalized_filters, intel)
        return results

    # ================================================================== #
    # INTERNAL UTIL                                                        #
    # ================================================================== #
    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        try:
            return RoadmapDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown data section: {section}") from exc

    # ================================================================== #
    # PUBLIC SCHEMA EXPOSURE                                               #
    # ================================================================== #
    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        """Return the auto-generated manifest used by AIDAO / planner."""
        return ROADMAP_DATA_MANIFEST


# ====================================================================== #
# AUTO-GENERATE ROADMAP_DATA_MANIFEST                                     #
# ====================================================================== #
ROADMAP_DATA_MANIFEST: Dict[str, Any] = {}


ROADMAP_DATA_MANIFEST["overall_description"] = """
CRITICAL: In trmeric, a ROADMAP and a DEMAND are the SAME THING.
Users use the words "demand", "roadmap", and "request" interchangeably.
When a user says "list all demands" they mean "list all roadmaps".
When a user says "demand title" they mean "roadmap_title".
When a user says "demand description" they mean "roadmap_description".
When a user says "demand ID" they mean "roadmap_id".
There is NO separate demand entity. The roadmap IS the demand.

Roadmaps are future projects planned in trmeric.
Roadmap → Roadmap parent-child relation does NOT exist.
Only Ideas can be converted to roadmaps (traceable via parent_ideas section).

Planning happens here: roles, business case, scope, solution, CapEx/OpEx budget.
Actual execution happens in Projects (separate entity, not here).

Key terminology aliases used by users:
  - "demand" / "request"                             →  roadmap (same thing)
  - "demand title" / "demand name"                   →  roadmap_title (core)
  - "demand description"                             →  roadmap_description (core)
  - "demand queue" / "roadmap queue" / "plan queue"  →  release_cycles section
  - "demand release cycle" / "scheduled for FY27"    →  release_cycles section, filter release_cycle_title
  - "business sponsors" / "business members"         →  business_members section
  - "dependencies" / "blockers" / "successors"       →  dependencies section
  - "ideas" / "parent ideas"                         →  parent_ideas section
  - "KPIs" / "key results"                           →  key_results section
  - "team" / "estimates" / "effort"                  →  team_data section
  - "constraints"                                    →  constraints section
  - "scopes"                                         →  scopes section
  - "approvals" / "approval history"                 →  approval_history section

CRITICAL — STAGE DURATION RULES:
  - "how long in a stage" / "days in stage" / "time spent in stage" /
    "duration in current stage" / "how long has it been in Draft/Intake/..."
    → ALWAYS use the `stage_durations` section. NEVER use approval_history
      + post_aggregation formulas to compute this manually.
  - `stage_durations` returns one row per (roadmap, stage-visit) with:
      stage_name, stage_start_date, stage_end_date, duration_days, is_current_stage
  - To get duration in the CURRENT stage only → filter: is_current_stage = True
  - To get duration in a SPECIFIC stage (e.g. Draft) → filter: stage_name__eq = 'Draft'
    AND is_current_stage = True  (if asking about current/active time in that stage)
  - duration_days is already computed — DO NOT add post_aggregation FORMULA on top of it.
"""

for _section, _meta in RoadmapDaoV3.FIELD_REGISTRY.items():
    _dao_fn_name = f"fetch_{_section}"
    _dao_fn = getattr(RoadmapDaoV3, _dao_fn_name, None)
    if _dao_fn is None:
        appLogger.warning(
            f"[RoadmapDaoV3] DAO function '{_dao_fn_name}' not found for section '{_section}'"
        )
        continue

    ROADMAP_DATA_MANIFEST[_section] = {
        "dao_function":                           _dao_fn,
        "important_info_to_be_understood_by_llm": _meta["description"],
        "description":                            _meta["description"],
        "fields":                                 list(_meta["fields"].keys()),
        "sql_mapping":                            _meta["fields"],
        "filters":                                _meta.get("extra_filters", {}),
        "intel":                                  _meta.get("intel") or {},
    }