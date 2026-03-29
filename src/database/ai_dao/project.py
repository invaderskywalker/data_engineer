# src/database/ai_dao/project.py

from __future__ import annotations

from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from src.database.dao import ProjectsDao
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import date
from .intel import FieldIntel
from .base import BaseDAOQueryBuilder


MILESTONES = {
    "field": {
        "project_id": "wpm.project_id",
        "milestone_id": "wpm.id AS milestone_id",
        "milestone_name": "wpm.name AS milestone_name",
        "planned_spend_amount": "wpm.planned_spend AS planned_spend_amount",
        "actual_spend_amount": "wpm.actual_spend AS actual_spend_amount",
        "milestone_target_date": "wpm.target_date AS milestone_target_date",
        "milestone_actual_completion_date": "wpm.actual_date AS milestone_actual_completion_date",
        "milestone_comments": "wpm.comments AS milestone_comments",
        "overrun": "CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END AS overrun",
        "team_id": "wpm.team_id",
        "status_value": """CASE wpm.status_value
            WHEN 1 THEN 'not_started'
            WHEN 2 THEN 'in_progress'
            WHEN 3 THEN 'completed' END AS status_value""",
        "milestone_type": """CASE wpm.type
            WHEN 1 THEN 'scope_milestone'
            WHEN 2 THEN 'schedule_milestone'
            WHEN 3 THEN 'spend_milestone' END AS milestone_type""",
    },
    "intel": {
        "status_value": {
            "type": "enum",
            "column": "wpm.status_value",
            "mapping": {
                "not_started": 1,
                "in_progress": 2,
                "completed": 3,
            },
        },
        "milestone_type": {
            "type": "enum",
            "column": "wpm.type",
            "mapping": {
                "scope": 1,
                "scope_milestone": 1,
                "schedule": 2,
                "schedule_milestone": 2,
                "spend": 3,
                "spend_milestone": 3,
            },
        },
        "milestone_target_date": {"type": "date"},
        "milestone_actual_completion_date": {"type": "date"},
        "milestone_name": {"type": "text"},
        "planned_spend_amount": {"type": "number"},
        "actual_spend_amount": {"type": "number"},
        "overrun": {"type": "number"},
    },
}


# -------------------------------------------------------------------------
# Project DAO V3 – Unified Registry & Auto-Manifest
# -------------------------------------------------------------------------
class ProjectsDaoV3:
    """Modular, attribute-level DAO for project data (v3 with unified schema exposure)."""

    # ==============================================================
    # FIELD_REGISTRY – SINGLE SOURCE OF TRUTH
    # ==============================================================
    FIELD_REGISTRY: Dict[str, Dict[str, Any]] = {

        # ==============================================================
        # CORE — primary project metadata
        # ==============================================================
        "core": {
            "description": """
                The primary source of high-level project metadata.
                This section determines whether a project should be treated as active or closed.
                By default, only active (non-archived) projects are returned unless the query
                explicitly asks for archived/closed/completed projects.
                Any user question about project progress, spend, strategy alignment, or health
                should first reference this table.

                IMPORTANT FINANCIAL FIELDS:
                • project_budget        → total external spend budget (wp.total_external_spend)
                • capex_budget / opex_budget → capex/opex split of budget
                • capex_actual / opex_actual → actual capex/opex spend recorded
                • capex_pr_planned / opex_pr_planned → purchase requisition planned values
                • capex_po_planned / opex_po_planned → purchase order planned values
                These are project-level financial fields, distinct from milestone-level spend.

                STATUS FIELDS:
                • latest_schedule_status / latest_scope_status / latest_spend_status
                  → current rolled-up statuses (on_track / at_risk / compromised)
                • scope_completion_percent → latest scope completion % from status history

                STAGE FIELD:
                • project_stage → current lifecycle stage (e.g. Plan, Design, Build, Test, Deploy & Hypercare, Complete)


                IMPORTANT FIELD TYPES:
                - project_id → integer (wp.id). NEVER apply text filters (icontains, ilike) on project_id.
                If the user mentions a project name or code like "EPMOFY26", filter on project_title instead
                using project_title__icontains.
                - project_title → free text. Use icontains for partial name matching.


                BUSINESS DEFINITIONS:
                • "Compromised" / "Red" project     → ANY ONE of the three statuses = compromised
                    Filter: use OR logic across all three status fields
                    
                • "At Risk" / "Amber" project       → ANY ONE of the three statuses = at_risk
                    AND none are compromised
                    Filter: at least one = at_risk AND none = compromised
                    
                • "On Track" / "Green" project      → NONE of the three statuses = compromised
                    AND NONE of the three statuses = at_risk
                    AND AT LEAST ONE status = on_track (i.e. not all null)
                    Filter: exclude compromised AND exclude at_risk AND at least one is on_track


                FILTER PATTERNS:
                User says "show compromised projects":
                → filters: { "or": [
                    {"latest_schedule_status__eq": "compromised"},
                    {"latest_scope_status__eq": "compromised"},
                    {"latest_spend_status__eq": "compromised"}
                    ]}

                User says "show at risk projects":
                → filters: { "and": [
                    {"or": [
                        {"latest_schedule_status__eq": "at_risk"},
                        {"latest_scope_status__eq": "at_risk"},
                        {"latest_spend_status__eq": "at_risk"}
                    ]},
                    {"latest_schedule_status__ne": "compromised"},
                    {"latest_scope_status__ne": "compromised"},
                    {"latest_spend_status__ne": "compromised"}
                    ]}

                User says "show green / on track projects":
                → filters: { "and": [
                    {"latest_schedule_status__ne": "compromised"},
                    {"latest_scope_status__ne": "compromised"},
                    {"latest_spend_status__ne": "compromised"},
                    {"latest_schedule_status__ne": "at_risk"},
                    {"latest_scope_status__ne": "at_risk"},
                    {"latest_spend_status__ne": "at_risk"},
                    {"or": [
                        {"latest_schedule_status__eq": "on_track"},
                        {"latest_scope_status__eq": "on_track"},
                        {"latest_spend_status__eq": "on_track"}
                    ]}
                    ]}

                User says "no status update" / "never updated":
                → filters: {
                    "latest_schedule_status__isnull": true,
                    "latest_scope_status__isnull": true,
                    "latest_spend_status__isnull": true
                    }

                IMPORTANT: "Green status" in user language = on_track means
                    NONE are compromised, NONE are at_risk, and at least one is on_track.
                "Red status" = compromised on ANY dimension.
                "Amber status" = at_risk on ANY dimension (and not compromised).

            """,
            "table": "workflow_project",
            "alias": "wp",
            "fields": {
                # --- Identity ---
                "project_id": "wp.id AS project_id",
                "project_title": "wp.title AS project_title",
                "project_description_str": "wp.description AS project_description_str",
                "project_objectives_str": "wp.objectives AS project_objectives_str",

                # --- Lifecycle ---
                "created_on": "wp.created_on",
                "start_date": "wp.start_date",
                "end_date": "wp.end_date",
                "project_stage": "wp.state AS project_stage",

                # --- Archive ---
                "is_archived_project": "CASE WHEN wp.archived_on IS NOT NULL THEN true ELSE false END AS is_archived_project",
                "archived_on": "wp.archived_on AS archived_on",

                # --- Statuses ---
                "latest_schedule_status": "wp.delivery_status AS latest_schedule_status",
                "latest_scope_status": "wp.scope_status AS latest_scope_status",
                "latest_spend_status": "wp.spend_status AS latest_spend_status",

                # --- Budget (top-level) ---
                "project_budget": "wp.total_external_spend AS project_budget",

                # --- CapEx / OpEx budget ---
                "capex_budget": "wp.capex_budget AS capex_budget",
                "opex_budget": "wp.opex_budget AS opex_budget",

                # --- CapEx / OpEx actuals ---
                "capex_actual": "wp.capex_actuals AS capex_actual",
                "opex_actual": "wp.opex_actuals AS opex_actual",

                # --- Purchase Requisition planned ---
                "capex_pr_planned": "wp.capex_pr_planned AS capex_pr_planned",
                "opex_pr_planned": "wp.opex_pr_planned AS opex_pr_planned",

                # --- Purchase Order planned ---
                "capex_po_planned": "wp.capex_po_planned AS capex_po_planned",
                "opex_po_planned": "wp.opex_po_planned AS opex_po_planned",

                # --- Classification ---
                "project_category_str": "wp.project_category AS project_category_str",
                "project_strategy_str": "wp.org_strategy_align AS project_strategy_str",
                "spend_type": "wp.spend_type AS spend_type",

                # --- Technical metadata ---
                "project_location": "wp.project_location AS project_location",
                "project_type": "wp.project_type AS project_type",
                "sdlc_method": "wp.sdlc_method AS sdlc_method",
                "technology_stack": "wp.technology_stack AS technology_stack",

                # --- Relationships ---
                "program_id": "wp.program_id",
                "program_name": "prog.name AS program_name",
                "parent_roadmap_id": "wp.roadmap_id AS parent_roadmap_id",

                # --- People ---
                "project_manager_name": "uu.first_name AS project_manager_name",
                "created_by_user_id": "wp.created_by_id AS created_by_user_id",
            },
            "joins": [
                "LEFT JOIN users_user uu ON uu.id = wp.project_manager_id_id",
                "LEFT JOIN program_program prog ON prog.id = wp.program_id",
                "LEFT JOIN roadmap_roadmap rr ON rr.id = wp.roadmap_id",
            ],
            "intel": {
                "project_id": {"type": "number", "column": "wp.id"},
                "latest_schedule_status": {
                    "type": "enum",
                    "column": "wp.delivery_status",
                    "mapping": {
                        "on_track": "on_track",
                        "at_risk": "at_risk",
                        "compromised": "compromised"
                    },
                },
                "latest_scope_status": {
                    "type": "enum",
                    "column": "wp.scope_status",
                    "mapping": {
                        "on_track": "on_track",
                        "at_risk": "at_risk",
                        "compromised": "compromised"
                    },
                },
                "latest_spend_status": {
                    "type": "enum",
                    "column": "wp.spend_status",
                    "mapping": {
                        "on_track": "on_track",
                        "at_risk": "at_risk",
                        "compromised": "compromised"
                    },
                },
                "project_stage": {
                    "type": "enum",
                    "column": "wp.state",
                    "mapping": {
                        "develop": "Develop",
                        "discover": "Discover",
                        "release": "Release",
                        "deploy_hypercare": "Deploy & Hypercare",
                        "plan": "Plan",
                        "test": "Test",
                        "execution": "Execution",
                        "design": "Design",
                        "planning": "Planning",
                        "complete": "Complete",
                        "started": "Started",
                        "qa": "QA",
                        "build": "Build",
                        "discovery": "Discovery",
                    },
                },
                "project_manager_name": {"type": "pii_text", "column": "uu.first_name"},
                "start_date": {"type": "date"},
                "end_date": {"type": "date"},
                "archived_on": {"type": "date"},
                "created_by_user_id": {"type": "number"},
                "project_title": {"type": "text"},
                "project_description_str": {"type": "text"},
                "project_objectives_str": {"type": "text"},
                "project_category_str": {"type": "text"},
                "project_strategy_str": {"type": "text"},
                "project_budget": {"type": "number", "column": "wp.total_external_spend"},
                "capex_budget": {"type": "number", "column": "wp.capex_budget"},
                "opex_budget": {"type": "number", "column": "wp.opex_budget"},
                "capex_actual": {"type": "number", "column": "wp.capex_actuals"},
                "opex_actual": {"type": "number", "column": "wp.opex_actuals"},
                "capex_pr_planned": {"type": "number", "column": "wp.capex_pr_planned"},
                "opex_pr_planned": {"type": "number", "column": "wp.opex_pr_planned"},
                "capex_po_planned": {"type": "number", "column": "wp.capex_po_planned"},
                "opex_po_planned": {"type": "number", "column": "wp.opex_po_planned"},
            },
        },

        # ==============================================================
        # PROJECT SCOPE — scope line items per project
        # ==============================================================
        "project_scope": {
            "description": """
                Scope line items associated with a project.
                Each row represents a discrete scope entry.
                Use when the user asks about what is in scope, scope items, or scope definition.
            """,
            "table": "workflow_projectscope",
            "alias": "wps",
            "fields": {
                "project_id": "wps.project_id",
                "scope": "wps.scope AS scope",
            },
            "intel": {
                "scope": {"type": "text"},
            },
        },

        # ==============================================================
        # MILESTONES
        # ==============================================================
        "milestones": {
            "description": """
                Evidence records attached to projects.

                IMPORTANT ANALYST RULES:
                • Milestones are NOT identity-defining; they are evidence.
                • Projects may exist with ZERO milestones.
                • Spend analysis MUST scope to milestone_type = 'spend_milestone'.
                • Absence of spend milestones implies actual_spend = 0, not missing project.
                • Milestones should DECORATE projects, not FILTER them, unless explicitly requested.
                • Use overrun field to identify milestones where actual > planned spend.
            """,
            "table": "workflow_projectmilestone",
            "alias": "wpm",
            "fields": MILESTONES.get("field"),
            "extra_filters": {
                "limit": "int",
            },
            "intel": MILESTONES.get("intel"),
        },

        "milestones_on_time": {
            "description": "Milestones completed on or before target date.",
            "table": "workflow_projectmilestone",
            "alias": "wpm",
            "fields": MILESTONES.get("field"),
            "intel": MILESTONES.get("intel"),
            "where_extra": "wpm.actual_date IS NOT NULL AND wpm.actual_date <= wpm.target_date",
        },

        "milestones_delayed": {
            "description": "Milestones completed after target date.",
            "table": "workflow_projectmilestone",
            "alias": "wpm",
            "fields": MILESTONES.get("field"),
            "intel": MILESTONES.get("intel"),
            "where_extra": "wpm.actual_date IS NOT NULL AND wpm.actual_date > wpm.target_date",
        },

        # ==============================================================
        # PROJECT STATUS HISTORY — raw per-update rows
        # ==============================================================
        "project_status_history": {
            "description": """
                Raw per-update project status rows with comments.
                Each row = one status update (schedule / scope / spend).

                USE THIS when user asks for:
                - recent status comments / updates for a specific project
                - latest N status updates
                - status narrative / communication log
                - what was said in the last update

                DO NOT use for trend/count queries — use project_status_monthly instead.

                FIELDS:
                • type         → status dimension (schedule / scope / spend)
                • value        → status value (on_track / at_risk / compromised)
                • comment      → free-text update comment
                • created_date → timestamp of the update
                • actual_percentage → scope completion % at time of update


                CRITICAL — "NOT UPDATED IN X DAYS/MONTHS" QUERIES:
                    When the user asks for projects that have NOT been updated recently
                    (e.g. "not updated in last 1 month", "stale projects", "no recent updates"):

                    DO NOT use row_slice + post_filter on created_date directly.
                    created_date lives inside a child attribute and post_filter
                    cannot resolve it — this will produce ZERO results.

                    CORRECT PATTERN — MANDATORY:
                    1. Fetch project_status_history with NO filters and NO row_slice.
                    Set extra_params: { "limit": null } to fetch ALL rows, not just the default 10.
                    Without limit: null, the MAX will run on truncated data and produce wrong results.
                    2. Add a post_aggregation:
                        attr = "project_status_history"
                        aggregate = MAX
                        field = "created_date"
                        group_by = ["project_id"]
                        alias = "last_update_date"
                    3. Add a post_filter:
                        { "last_update_date__lt": "<cutoff_date>" }
                    4. Do NOT add any FORMULA post_aggregation — the post_filter on the MAX alias is sufficient.

                    This puts last_update_date into post_agg where post_filter
                    can correctly resolve it.

                    post_filter MUST ONLY reference post_aggregation aliases.
                    post_filter MUST NEVER reference raw child attribute fields directly.
                    
            """,
            "table": "workflow_projectstatus",
            "alias": "ps",
            "fields": {
                "project_id": "ps.project_id",
                "type": """CASE ps.type
                    WHEN 1 THEN 'schedule'
                    WHEN 2 THEN 'scope'
                    WHEN 3 THEN 'spend'
                    ELSE 'unknown' END AS type""",
                "value": """CASE ps.value
                    WHEN 1 THEN 'on_track'
                    WHEN 2 THEN 'at_risk'
                    WHEN 3 THEN 'compromised'
                    ELSE 'unknown' END AS value""",
                "comment": "ps.comments AS comment",
                "created_date": "ps.created_date",
                "actual_percentage": "ps.actual_percentage",
            },
            "extra_filters": {
                "limit": "int",
            },
            "intel": {
                "type": {
                    "type": "enum",
                    "column": "ps.type",
                    "mapping": {"schedule": 1, "scope": 2, "spend": 3},
                },
                "value": {
                    "type": "enum",
                    "column": "ps.value",
                    "mapping": {"on_track": 1, "at_risk": 2, "compromised": 3},
                },
                "created_date": {"type": "date"},
                "actual_percentage": {"type": "number"},
            },
        },

        # ==============================================================
        # PROJECT STATUS MONTHLY — pre-aggregated trend view
        # ==============================================================
        "project_status_metrics": {
            "description": """
                Aggregated analytical view of project status updates.

                USE THIS when user asks for:
                - total number of status updates
                - status update counts
                - status trends over time
                - how often status changed
                - schedule/scope/spend health trends
                - projects with no recent updates

                This attribute provides aggregated statistics derived from
                workflow_projectstatus.

                Rows represent grouped metrics such as:

                • update_count → number of updates in a time bucket
                • dominant_status → most frequent status in the bucket
                • latest_update_date → last update in the bucket
                • total_updates_in_month → total updates across types

                IMPORTANT:
                Use this attribute for **analytics and counts**.

                DO NOT use project_status_history unless the user explicitly
                asks to see individual comments or update records.
            """,
            "table": "workflow_projectstatus",
            "alias": "ps",
            "fields": {
                "project_id": "ps.project_id",
                "status_month": "DATE_TRUNC('month', ps.created_date) AS status_month",
                "type": """CASE ps.type
                    WHEN 1 THEN 'schedule'
                    WHEN 2 THEN 'scope'
                    WHEN 3 THEN 'spend'
                    ELSE 'unknown' END AS type""",
                "dominant_status": "MODE() WITHIN GROUP (ORDER BY ps.value) AS dominant_status",
                "update_count": "COUNT(*) AS update_count",
                "total_updates_in_month": "NULL AS total_updates_in_month",  # computed via window in fetcher
                "latest_update_date": "MAX(ps.created_date) AS latest_update_date",
            },
            "intel": {
                "type": {
                    "type": "enum",
                    "column": "ps.type",
                    "mapping": {"schedule": 1, "scope": 2, "spend": 3},
                },
                "status_month": {"type": "date"},
            },
        },

        # ==============================================================
        # RISKS
        # ==============================================================
        "risks": {
            "description": """
                Project-level risks with impact, mitigation, priority and status.

                STATUS VALUES:
                • Active / Resolved / Monitoring / Escalated / Mitigated / Closed

                IMPACT (priority) VALUES:
                • High (1) / Medium (2) / Low (3)

                Use when user asks about risk exposure, high-priority risks,
                overdue risks, escalated risks, or risk mitigation status.
            """,
            "table": "workflow_projectrisk",
            "alias": "wpr",
            "fields": {
                "project_id": "wpr.project_id",
                "risk_id": "wpr.id AS risk_id",
                "description": "wpr.description",
                "impact_area": "wpr.impact AS impact_area",
                "mitigation": "wpr.mitigation",
                "due_date": "wpr.due_date",
                "completed_on": "wpr.completed_on",
                "impact": """CASE wpr.priority
                    WHEN 1 THEN 'High'
                    WHEN 2 THEN 'Medium'
                    WHEN 3 THEN 'Low'
                    ELSE 'Unknown' END AS impact""",
                "status_value": """CASE wpr.status_value
                    WHEN 1 THEN 'Active'
                    WHEN 2 THEN 'Resolved'
                    WHEN 3 THEN 'Monitoring'
                    WHEN 4 THEN 'Escalated'
                    WHEN 5 THEN 'Mitigated'
                    WHEN 6 THEN 'Closed'
                    ELSE 'Unknown' END AS status_value""",
            },
            "intel": {
                "status_value": {
                    "type": "enum",
                    "column": "wpr.status_value",
                    "mapping": {
                        "active": 1,
                        "resolved": 2,
                        "monitoring": 3,
                        "escalated": 4,
                        "mitigated": 5,
                        "closed": 6,
                    },
                },
                "impact": {
                    "type": "enum",
                    "column": "wpr.priority",
                    "mapping": {"high": 1, "medium": 2, "low": 3},
                },
                "due_date": {"type": "date"},
                "completed_on": {"type": "date"},
                "description": {"type": "text"},
                "mitigation": {"type": "text"},
            },
        },

        # ==============================================================
        # DEPENDENCIES
        # ==============================================================
        "dependencies": {
            "description": """
                Project inter-dependencies with target dates, owner, and status.

                STATUS VALUES:
                • pending / in_progress / resolved

                Use when user asks about blocked projects, pending dependencies,
                overdue dependencies, or cross-project dependency chains.

                IMPORTANT:
                • dependency_on → the entity/team/project this project depends on
                • owner         → person responsible for resolving
                • target_date   → expected resolution date
            """,
            "table": "workflow_projectdependency",
            "alias": "wpd",
            "fields": {
                "project_id": "wpd.project_id",
                "dependency_id": "wpd.id AS dependency_id",
                "description": "wpd.description",
                "impact": "wpd.impact",
                "comments_action": "wpd.comments_action",
                "dependency_on": "wpd.dependency_on",
                "owner": "wpd.owner",
                "target_date": "wpd.target_date",
                "status_value": """CASE wpd.status_value
                    WHEN 1 THEN 'pending'
                    WHEN 2 THEN 'in_progress'
                    WHEN 3 THEN 'resolved' END AS status_value""",
            },
            "intel": {
                "status_value": {
                    "type": "enum",
                    "column": "wpd.status_value",
                    "mapping": {"pending": 1, "in_progress": 2, "resolved": 3},
                },
                "target_date": {"type": "date"},
                "description": {"type": "text"},
                "dependency_on": {"type": "text"},
                "owner": {"type": "text"},
            },
        },

        # ==============================================================
        # TEAMS DATA
        # ==============================================================
        "teamsdata": {
            "description": """
                Team split data for a project — internal/external members,
                their roles, utilization, location, and hourly rates.

                USE when user asks about:
                - who is on the team
                - team composition (internal vs external)
                - member utilization / contribution percentage
                - cost per hour / rate analysis
                - team location breakdown
            """,
            "table": "workflow_projectteamsplit",
            "alias": "wpts",
            "fields": {
                "project_id": "wpts.project_id",
                "role": "wpts.member_role AS role",
                "member_name": "wpts.member_name",
                "average_rate_per_hour": "wpts.average_spend AS average_rate_per_hour",
                "contribution_percentage": "wpts.member_utilization AS contribution_percentage",
                "member_location": "wpts.location AS member_location",
                "is_external": "wpts.is_external",
                "team_type": "CASE WHEN wpts.is_external THEN 'External' ELSE 'Internal' END AS team_type",
            },
            "intel": {
                "member_name": {"type": "pii_text", "column": "wpts.member_name"},
                "role": {"type": "text"},
                "member_location": {"type": "text"},
                "average_rate_per_hour": {"type": "number"},
                "contribution_percentage": {"type": "number"},
                "team_type": {
                    "type": "enum",
                    "column": "wpts.is_external",
                    "mapping": {"external": True, "internal": False},
                },
            },
        },

        # ==============================================================
        # BUSINESS MEMBERS / SPONSORS
        # ==============================================================
        "business_members": {
            "description": """
                Business sponsors and stakeholders associated with a project.

                Each row = one business sponsor linked to a project.
                Fields include name, email, role, and business unit.

                USE when user asks about:
                - business sponsors / stakeholders
                - who is the sponsor of a project
                - projects owned by a specific business unit
                - stakeholder contact details
            """,
            "table": "workflow_projectbusinessmember",
            "alias": "wpbm",
            "joins": [
                "LEFT JOIN projects_portfoliobusiness pb ON pb.id = wpbm.portfolio_business_id",
            ],
            "fields": {
                "project_id": "wpbm.project_id",
                "sponsor_first_name": "pb.sponsor_first_name",
                "sponsor_last_name": "pb.sponsor_last_name",
                "sponsor_email": "pb.sponsor_email",
                "sponsor_role": "pb.sponsor_role",
                "business_unit": "pb.bu_name AS business_unit",
            },
            "intel": {
                "sponsor_first_name": {"type": "pii_text", "column": "pb.sponsor_first_name"},
                "sponsor_last_name": {"type": "pii_text", "column": "pb.sponsor_last_name"},
                "sponsor_email": {"type": "pii_text", "column": "pb.sponsor_email"},
                "sponsor_role": {"type": "text"},
                "business_unit": {"type": "text"},
            },
        },

        # # ==============================================================
        # # REFERENCE DOCUMENTS
        # # ==============================================================
        # "reference_documents": {
        #     "description": """
        #         Supporting reference documents attached to a project,
        #         including charters, design docs, and other file attachments.

        #         Each row = one document entry (contains the S3 file key for retrieval).

        #         USE when user asks about:
        #         - project charter
        #         - supporting / reference documents
        #         - attached files
        #         - document contents (requires file fetch via FileAnalyzer)

        #         NOTE: The 'file' field contains the S3 key. Actual content
        #         is fetched separately via FileAnalyzer.analyze_files().
        #     """,
        #     "table": "workflow_project",
        #     "alias": "wp",
        #     "fields": {
        #         "project_id": "wp.id AS project_id",
        #         "ref_docs": "wp.ref_docs AS ref_docs",
        #     },
        #     "intel": {},
        # },

        # ==============================================================
        # PORTFOLIO
        # ==============================================================
        "portfolio": {
            "description": """
                Portfolio entity (tenant-scoped).
                Links projects to their parent portfolio and exposes portfolio leader info.

                USE when user asks about:
                - which portfolio a project belongs to
                - projects under a specific portfolio
                - portfolio leadership
            """,
            "table": "projects_portfolio",
            "alias": "pp",
            "joins": [
                "LEFT JOIN workflow_projectportfolio wpport ON wpport.portfolio_id = pp.id",
            ],
            "fields": {
                "portfolio_id": "pp.id AS portfolio_id",
                "portfolio_title": "pp.title AS portfolio_title",
                "portfolio_leader_first_name": "pp.first_name AS portfolio_leader_first_name",
                "portfolio_leader_last_name": "pp.last_name AS portfolio_leader_last_name",
                "project_id": "wpport.project_id",
            },
            "intel": {
                "portfolio_title": {"type": "text"},
                "portfolio_leader_first_name": {"type": "pii_text", "column": "pp.first_name"},
                "portfolio_leader_last_name": {"type": "pii_text", "column": "pp.last_name"},
            },
        },

        # ==============================================================
        # PROGRAM
        # ==============================================================
        "program": {
            "description": """
                Program association per project.
                A program groups related projects under a common initiative.

                USE when user asks about:
                - which program a project belongs to
                - projects under a specific program
                - program-level health / rollup
            """,
            "joins": [
                "JOIN program_program pp ON wp.program_id = pp.id",
            ],
            "fields": {
                "project_id": "wp.id AS project_id",
                "program_id": "pp.id AS program_id",
                "program_name": "pp.name AS program_name",
            },
            "intel": {
                "program_name": {"type": "text"},
            },
        },

        # ==============================================================
        # KEY RESULTS / KPIs / OKRs
        # ==============================================================
        "key_results": {
            "description": """
                Key Results / KPIs / OKRs tracked for the project.
                Useful for tying delivery outcomes to measurable business results.

                USE when user queries involve:
                - KPIs / OKRs / key results
                - business impact / success metrics
                - strategic outcome tracking
            """,
            "table": "workflow_projectkpi",
            "alias": "wpkpi",
            "fields": {
                "project_id": "wpkpi.project_id",
                "key_result": "wpkpi.name AS key_result",
            },
            "intel": {
                "key_result": {"type": "text"},
            },
        },

        # ==============================================================
        # BUDGET SUMMARY — aggregated planned vs actual per project
        # ==============================================================
        "budget_summary": {
            "description": """
                Aggregated spend summary per project from spend milestones.
                Gives a single row per project with:
                • total_planned_spend  → sum of planned spend across spend milestones
                • total_actual_spend   → sum of actual spend across spend milestones
                • total_overrun        → sum of (actual - planned) where actual > planned

                IMPORTANT:
                • Only includes milestone_type = 'spend_milestone' (type = 3)
                • Projects with no spend milestones will have 0 values, not be absent
                • Use for over-budget analysis, spend variance, portfolio spend rollup

                DO NOT confuse with project_budget (core) which is the headline budget figure.
            """,
            "table": "workflow_projectmilestone",
            "alias": "wpm",
            "where_extra": "wpm.type = 3",
            "group_by": "wpm.project_id",
            "fields": {
                "project_id": "wpm.project_id",
                "total_planned_spend": "COALESCE(SUM(wpm.planned_spend), 0) AS total_planned_spend",
                "total_actual_spend": "COALESCE(SUM(wpm.actual_spend), 0) AS total_actual_spend",
                "total_overrun": "COALESCE(SUM(CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END), 0) AS total_overrun",
                "spend_milestone_count": "COUNT(*) AS spend_milestone_count",
            },
            "intel": {
                "total_planned_spend": {"type": "number"},
                "total_actual_spend": {"type": "number"},
                "total_overrun": {"type": "number"},
            },
        },

    }

    # ==============================================================
    # CORE FETCHERS – ALL USE FIELD_REGISTRY
    # ==============================================================

    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        """Helper – raise clear error if section missing."""
        try:
            return ProjectsDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown data section: {section}") from exc

    # -----------------------------------------------------------------
    # CORE
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_core(
        project_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        fields: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        # ---------------------------------------------------------
        # BASE WHERE CONDITIONS
        # ---------------------------------------------------------
        where = ["wp.tenant_id_id = %s", "wp.parent_id is not %s"]
        params: List[Any] = [tenant_id, None]

        if project_ids:
            where.append("wp.id = ANY(%s)")
            params.append(project_ids)

        # ---------------------------------------------------------
        # ARCHIVED LOGIC
        # (Handled outside FieldIntel because it changes base WHERE)
        # ---------------------------------------------------------
        if filters and "is_archived_project" in filters:
            val = filters.pop("is_archived_project")
            if val is True:
                where = ["wp.tenant_id_id = %s", "wp.parent_id is not %s", "wp.archived_on IS NOT NULL"]
            else:
                where = ["wp.tenant_id_id = %s", "wp.parent_id is not %s", "wp.archived_on IS NULL"]
            params = [tenant_id, None]
            # if project_ids:
            #     where.append("wp.id = ANY(%s)")
            #     params.append(project_ids)

        # ---------------------------------------------------------
        # NORMALIZE FILTERS (ENUMS, DATE, TEXT, PII)
        # ---------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"],
        )

        # ---------------------------------------------------------
        # TIME BUCKET
        # ---------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "start_date")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias", bucket_field)
        elif isinstance(time_bucket, str):
            bucket_field = "start_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        # ---------------------------------------------------------
        # BUILD FINAL QUERY
        # ---------------------------------------------------------
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
        return results

    # -----------------------------------------------------------------
    # PROJECT SCOPE
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_project_scope(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("project_scope")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # MILESTONES
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_milestones(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("milestones")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "milestone_target_date")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "milestone_target_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        is_aggregated = any(isinstance(f, dict) and "aggregate" in f for f in (fields or []))
        use_group_by = group_by if is_aggregated else None
        if is_aggregated:
            order_by = None

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            group_by=use_group_by,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # INTERNAL SHARED MILESTONE FETCHER
    # -----------------------------------------------------------------
    @staticmethod
    def _fetch_milestones_internal(
        meta: Dict[str, Any],
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> List[Dict]:

        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        where_extra = meta.get("where_extra")
        if where_extra:
            where.append(where_extra)

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "milestone_target_date")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "milestone_target_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        is_aggregated = any(isinstance(f, dict) and "aggregate" in f for f in (fields or []))
        use_group_by = group_by if is_aggregated else None
        if is_aggregated:
            order_by = None

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            group_by=use_group_by,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # DERIVED MILESTONES — ON TIME
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_milestones_on_time(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:
        meta = ProjectsDaoV3._get_section("milestones_on_time")
        return ProjectsDaoV3._fetch_milestones_internal(
            meta=meta, project_ids=project_ids, tenant_id=tenant_id,
            filters=filters, order_by=order_by, fields=fields,
            group_by=group_by, time_bucket=time_bucket,
        )

    # -----------------------------------------------------------------
    # DERIVED MILESTONES — DELAYED
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_milestones_delayed(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:
        meta = ProjectsDaoV3._get_section("milestones_delayed")
        return ProjectsDaoV3._fetch_milestones_internal(
            meta=meta, project_ids=project_ids, tenant_id=tenant_id,
            filters=filters, order_by=order_by, fields=fields,
            group_by=group_by, time_bucket=time_bucket,
        )

    # -----------------------------------------------------------------
    # PROJECT STATUS HISTORY (raw per-update with ROW_NUMBER + time_bucket)
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_project_status_history(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        limit: int = 20,
        order_by: Optional[str] = "ps.created_date DESC",
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        from textwrap import dedent

        meta = ProjectsDaoV3._get_section("project_status_history")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        # TIME BUCKET MODE (trend view)
        if time_bucket:
            bucket_interval = None
            bucket_field = None
            bucket_alias_field = None

            if isinstance(time_bucket, dict):
                bucket_field = time_bucket.get("field", "created_date")
                bucket_interval = time_bucket.get("interval", "month")
                bucket_alias_field = time_bucket.get("alias", bucket_field)
            else:
                bucket_field = "created_date"
                bucket_interval = time_bucket
                bucket_alias_field = bucket_field

            query, params_tuple = BaseDAOQueryBuilder.build_query(
                table_alias=alias,
                table_name=table,
                fields=all_fields,
                selected_fields=fields,
                filters=normalized_filters,
                where_clauses=where,
                params=params,
                group_by=["project_id", "type", "value"],
                order_by=f"{bucket_alias_field} ASC",
                time_bucket=bucket_interval,
                time_bucket_field=bucket_field,
                bucket_alias_field=bucket_alias_field,
            )
            return db_instance.execute_query_safe(query, params_tuple)

        # LATEST N STATUS UPDATES PER PROJECT (ROW_NUMBER MODE)
        filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
            normalized_filters, alias=alias, fields_map=all_fields
        )
        if filter_sql:
            where.append(filter_sql)
            params.extend(filter_params)

        where_clause = f"WHERE {' AND '.join(where)}"

        if not fields:
            resolved_fields = list(all_fields.values())
            outer_fields = list(all_fields.keys())
        else:
            resolved_fields = [all_fields[f] for f in fields if f in all_fields]
            outer_fields = [f for f in fields if f in all_fields]

        select_clause = ", ".join(resolved_fields)

        order_field = order_by.split()[0] if order_by else f"{alias}.created_date"
        order_dir = order_by.split()[1] if order_by and len(order_by.split()) > 1 else "DESC"
        # If no limit → fetch all rows (row_slice will handle it)
        if limit is None:
            query = dedent(f"""
                SELECT {select_clause}
                FROM {table} {alias}
                {where_clause}
                ORDER BY {order_field} {order_dir}
            """)
            return db_instance.execute_query_safe(query, tuple(params))

        # Otherwise use ROW_NUMBER limiting
        final_limit = max(1, limit)
        query = dedent(f"""
            SELECT {", ".join(outer_fields)}
            FROM (
                SELECT
                    {select_clause},
                    ROW_NUMBER() OVER (
                        PARTITION BY {alias}.project_id
                        ORDER BY {order_field} {order_dir}
                    ) AS rn
                FROM {table} {alias}
                {where_clause}
            ) sub
            WHERE rn <= %s
            ORDER BY project_id
        """)
        params.append(final_limit)
        return db_instance.execute_query_safe(query, tuple(params))

    # -----------------------------------------------------------------
    # STATUS MONTHLY SNAPSHOT
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_project_status_metrics(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:

        if filters and "time_bucket" in filters:
            filters.pop("time_bucket")
        if filters and "limit" in filters:
            filters.pop("limit")

        meta = ProjectsDaoV3._get_section("project_status_monthly")
        alias, table = meta["alias"], meta["table"]
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
            normalized_filters, alias=alias, fields_map=all_fields
        )
        if filter_sql:
            where.append(filter_sql)
            params.extend(filter_params)

        where_sql = f"WHERE {' AND '.join(where)}"

        query = f"""
            SELECT
                project_id,
                status_month,
                type,
                dominant_status,
                update_count,
                SUM(update_count) OVER (
                    PARTITION BY project_id, status_month
                ) AS total_updates_in_month,
                latest_update_date
            FROM (
                SELECT
                    {alias}.project_id,
                    DATE_TRUNC('month', {alias}.created_date) AS status_month,
                    CASE {alias}.type
                        WHEN 1 THEN 'schedule'
                        WHEN 2 THEN 'scope'
                        WHEN 3 THEN 'spend'
                        ELSE 'unknown' END AS type,
                    CASE MODE() WITHIN GROUP (ORDER BY {alias}.value)
                        WHEN 1 THEN 'on_track'
                        WHEN 2 THEN 'at_risk'
                        WHEN 3 THEN 'compromised'
                        ELSE 'unknown'
                    END AS dominant_status,
                    COUNT(*) AS update_count,
                    MAX({alias}.created_date) AS latest_update_date
                FROM {table} {alias}
                {where_sql}
                GROUP BY
                    {alias}.project_id,
                    DATE_TRUNC('month', {alias}.created_date),
                    {alias}.type
            ) grouped
            ORDER BY project_id, status_month ASC
        """

        return db_instance.execute_query_safe(query, tuple(params))

    # -----------------------------------------------------------------
    # RISKS
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_risks(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("risks")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        # ---------------------------------------------------------
        # BASE WHERE
        # ---------------------------------------------------------
        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        # ---------------------------------------------------------
        # 1️⃣ Normalize filters using FieldIntel
        # ---------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "due_date")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "due_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        # ---------------------------------------------------------
        # 3️⃣ Build final SQL with QueryBuilder
        # ---------------------------------------------------------
        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=f"{alias}.due_date ASC",
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # DEPENDENCIES
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_dependencies(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("dependencies")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        # ---------------------------------------------------------
        # TIME BUCKET (optional, future-proof)
        # ---------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "target_date")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field

        elif isinstance(time_bucket, str):
            bucket_field = "target_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        # ---------------------------------------------------------
        # BUILD QUERY
        # ---------------------------------------------------------
        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # TEAMS
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_teamsdata(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        team_type: Optional[str] = None,
        sample_rate: float = 1.0,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("teamsdata")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        if team_type:
            where.append(f"{alias}.is_external = %s")
            params.append(team_type.lower() == "external")

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            alias, table, all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            sample_rate=sample_rate,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # BUSINESS MEMBERS / SPONSORS
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_business_members(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("business_members")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        # tenant scoping via join to projects_portfoliobusiness
        if tenant_id:
            where.append("pb.tenant_id = %s")
            params.append(tenant_id)

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            joins=meta.get("joins") or [],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # REFERENCE DOCUMENTS
    # Note: raw ref_docs JSON column is returned; caller must use
    # FileAnalyzer.analyze_files() to fetch actual document content.
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_reference_documents(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("reference_documents")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]

        where = [f"{alias}.id = ANY(%s)"]
        if tenant_id:
            where.append(f"{alias}.tenant_id_id = %s")

        params: List[Any] = [project_ids]
        if tenant_id:
            params.append(tenant_id)

        select_parts = [
            all_fields[f] for f in (fields or all_fields.keys()) if f in all_fields
        ]

        query = f"""
            SELECT {', '.join(select_parts)}
            FROM {table} {alias}
            WHERE {' AND '.join(where)}
        """
        return db_instance.execute_query_safe(query, tuple(params))

    # -----------------------------------------------------------------
    # PORTFOLIO
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_portfolio(
        tenant_id: int,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("portfolio")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        # ---------------------------------------------------------
        # BASE WHERE — tenant scoped (same invariant as core)
        # ---------------------------------------------------------
        where = [f"{alias}.tenant_id_id = %s"]
        params: List[Any] = [tenant_id]

        # ---------------------------------------------------------
        # NORMALIZE FILTERS
        # ---------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        # ---------------------------------------------------------
        # TIME BUCKET (rare, but supported for symmetry)
        # ---------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field")
            bucket_interval = time_bucket.get("interval")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_interval = time_bucket

        # ---------------------------------------------------------
        # BUILD QUERY (pure V3 path)
        # ---------------------------------------------------------
        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=table,
            joins=meta.get("joins"),
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
        return FieldIntel.post_execute(results, normalized_filters, intel)

    # -----------------------------------------------------------------
    # PROGRAM
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_program(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("program")
        all_fields = meta["fields"]

        where = ["wp.program_id = pp.id", "wp.id = ANY(%s)"]
        params: List[Any] = [project_ids]

        if tenant_id:
            where.append("pp.tenant_id = %s")
            params.append(tenant_id)

        select_parts = [
            all_fields[f] for f in (fields or all_fields.keys()) if f in all_fields
        ]

        query = f"""
            SELECT {', '.join(select_parts)}
            FROM workflow_project wp
            {' '.join(meta.get('joins', []))}
            WHERE {' AND '.join(where)}
        """
        return db_instance.execute_query_safe(query, tuple(params))

    # -----------------------------------------------------------------
    # KEY RESULTS
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_key_results(
        project_ids: List[int],
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict]:

        meta = ProjectsDaoV3._get_section("key_results")
        alias, table, all_fields = meta["alias"], meta["table"], meta["fields"]
        intel = meta.get("intel", {})

        where = [f"{alias}.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        normalized_filters = FieldIntel.normalize_filters(
            filters or {}, intel=intel, fields=all_fields, alias=alias
        )

        has_aggregates = any(
            isinstance(f, dict) and "aggregate" in f for f in (fields or [])
        )

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            alias, table, all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            group_by=["wpkpi.project_id"] if has_aggregates else None,
        )
        return db_instance.execute_query_safe(query, params_tuple)

    # -----------------------------------------------------------------
    # BUDGET SUMMARY
    # -----------------------------------------------------------------
    @staticmethod
    def fetch_budget_summary(
        project_ids: List[int],
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:
        """
        Aggregated planned vs. actual spend per project from spend milestones.
        Only includes milestone_type = 'spend_milestone' (wpm.type = 3).
        """
        meta = ProjectsDaoV3._get_section("budget_summary")
        all_fields = meta["fields"]

        select_parts = [
            all_fields[f] for f in (fields or all_fields.keys()) if f in all_fields
        ]

        where = ["wpm.project_id = ANY(%s)"]
        params: List[Any] = [project_ids]

        # Immutable filter: spend milestones only
        where_extra = meta.get("where_extra", "")
        if where_extra:
            where.append(where_extra)

        # Optional spend threshold filters
        if filters:
            if filters.get("actual_spend__gt"):
                where.append("wpm.actual_spend > wpm.planned_spend")
            if filters.get("actual_spend__lt"):
                where.append("wpm.actual_spend < wpm.planned_spend")
            if filters.get("actual_spend__gte"):
                where.append("wpm.actual_spend >= wpm.planned_spend")
            if filters.get("actual_spend__lte"):
                where.append("wpm.actual_spend <= wpm.planned_spend")

        where_clause = " AND ".join(where)

        query = f"""
            SELECT {', '.join(select_parts)}
            FROM workflow_projectmilestone wpm
            WHERE {where_clause}
            GROUP BY {meta.get('group_by')}
        """

        return db_instance.execute_query_safe(query, tuple(params))

    # -----------------------------------------------------------------
    # PUBLIC SCHEMA EXPOSURE
    # -----------------------------------------------------------------
    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        """Return the auto-generated manifest (used by AIDAO / planner)."""
        return PROJECT_DATA_MANIFEST


# ==============================================================
# AUTO-GENERATE PROJECT_DATA_MANIFEST FROM FIELD_REGISTRY
# ==============================================================
PROJECT_DATA_MANIFEST: Dict[str, Any] = {}
PROJECT_DATA_MANIFEST["overall_description"] = """
    Projects are the entities which get executed.
    Roadmap -> Project conversion happens which can be tracked using parent_roadmap_id.

    SECTION GUIDE:
    • core                    → primary project metadata, statuses, budgets, capex/opex, stage
    • project_scope           → scope line items per project
    • milestones              → all milestones (scope/schedule/spend types)
    • milestones_on_time      → milestones completed on or before target date
    • milestones_delayed      → milestones completed after target date
    • budget_summary          → aggregated planned vs actual spend from spend milestones
    • project_status_monthly  → monthly aggregated status trend (counts, dominant status)
    • risks                   → project risks with priority, status, mitigation
    • dependencies            → inter-project/team dependencies with status and dates
    • teamsdata               → team split (internal/external, roles, utilization, rates)
    • business_members        → business sponsors and stakeholders
    • portfolio               → portfolio association and leadership
    • program                 → program association
    • key_results             → KPIs / OKRs / key results tracked per project
"""

for section, meta in ProjectsDaoV3.FIELD_REGISTRY.items():
    dao_fn_name = f"fetch_{section}"
    dao_fn = getattr(ProjectsDaoV3, dao_fn_name, None)

    if dao_fn is None:
        appLogger.warning(f"DAO function {dao_fn_name} not found for section {section}")
        continue

    PROJECT_DATA_MANIFEST[section] = {
        "dao_function": dao_fn,
        "important_info_to_be_understood_by_llm": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "filters": meta.get("extra_filters", {}),
        "intel": meta.get("intel") or {},
    }
