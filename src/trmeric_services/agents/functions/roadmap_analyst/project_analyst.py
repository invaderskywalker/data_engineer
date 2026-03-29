from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler,
)
from src.trmeric_database.Database import db_instance
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import ProjectsDao, TangoDao, TenantDao

from sklearn.cluster import KMeans
from sklearn.preprocessing import OneHotEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import datetime
from datetime import date
import re

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import tiktoken

from src.trmeric_services.tango.functions.integrations.internal.resource import (
    get_capacity_data,
)
from .common import *

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_FIELDS = {
    "start_date", "end_date", "last_status_update_date",
    "archived_date", "first_status_update_date",
}

# ---------------------------------------------------------------------------
# Project Schema and Arguments
# ---------------------------------------------------------------------------

PROJECT_ARGS = [
    {"name": "project_id",           "type": "int[]",      "description": "List of project IDs.",                                              "conditional": "in"},
    {"name": "portfolio_ids",        "type": "int[]",      "description": "List of portfolio IDs.",                                            "conditional": "in"},
    {"name": "program_id",           "type": "int[]",      "description": "List of program IDs.",                                              "conditional": "in"},
    {"name": "schedule_status",      "type": "str",        "description": "Delivery status (e.g., On Track).",                                 "conditional": "equals"},
    {"name": "project_category",     "type": "str",        "description": "Project category.",                                                 "conditional": "like"},
    {"name": "start_date",           "type": "date-bound", "description": "Start date range.",                                                 "conditional": "date-bound"},
    {"name": "end_date",             "type": "date-bound", "description": "End date range.",                                                   "conditional": "date-bound"},
    {"name": "planned_spend",        "type": "range",      "description": "Planned spend range.",                                              "conditional": "range"},
    {"name": "dependency_status",    "type": "str",        "description": "Dependency status (e.g., pending, in_progress, resolved).",         "conditional": "equals"},
    {"name": "dependency_target_date","type": "date-bound","description": "Dependency target date range.",                                     "conditional": "date-bound"},
]

PROJECT_SCHEMA = {
    "fields": {
        "project_id": "integer (unique project identifier)",
        "title": "string (project name)",
        "is_archived_project": "closed project bool (if user is interested in archived then make this true)",
        "archived_date": "closing date of project",
        "project_description": "string (detailed description)",
        "project_objectives": "string (detailed objectives)",
        "schedule_status": "string (e.g., on_track, at_risk, compromised)",
        "scope_status": "string (e.g., on_track, at_risk, compromised)",
        "spend_status": "string (e.g., on_track, at_risk, compromised)",
        "last_status_update_date": "date str very important to get right last status update",
        "planned_spend": "float (planned budget in dollars)",
        "project_budget": "float (project budget)",
        "actual_spend": "float (actual spend in dollars)",
        "start_date": "date (project start date)",
        "end_date": "date (project end date)",
        "project_category": "string (project category)",
        "org_strategy": "string (alignment with org strategy)",
        "scope_completion_percent": "float (completion percentage)",
        "milestones": "list of dicts (milestone details: name, target_date, actual_spend, planned_spend)",
        "teamsdata": "list of dicts (team details: role, member_name, contribution_percentage, average_rate_per_hour, member_location, team_type)",
        "team_resources": "list of dicts (resource details: role, allocation, skills, experience_years, is_active, is_external)",
        "key_results": "list of strings (names of key performance indicators)",
        "roadmap_name": "string (associated roadmap name)",
        "portfolio": "list of portfolios (title, leaders) info.",
        "portfolio_id": "list of int",
        "status_comments": "list of dicts (update comments with their timestamps)",
        "total_status_updates": "integer (total count of all status updates)",
        "scope_status_updates_count": "integer (count of scope status updates)",
        "delivery_status_updates_count": "integer (count of delivery status updates)",
        "risks": "list",
        "dependencies": "list of dicts (dependency details: dependency_id, description, impact, comments_action, dependency_on, status_value, target_date, owner)",
        "program_id": "integer (unique program identifier)",
        "program_name": "string (associated program name)",
        "project_scope": "list of strings (scope of the project)",
        "reference_documents": "list of supporting documents & its contents, it includes the charter related info.",
        "business_members": "list of business sponsors with (name, email, role & business unit) info.",
        "capex_purchase_recquistion_planned": "float value",
        "opex_purchase_recquistion_planned": "float value",
        "capex_purchase_order_planned": "float value",
        "opex_purchase_order_planned": "float value",
        "capex_budget": "float value",
        "opex_budget": "float value",
        "capex_actual": "float",
        "opex_actual": "float",
        "project_stage": """value string can be any out of these -
            "Develop", "Discover", "Release", "Deploy & Hypercare", "Plan",
            "Test", "Execution", "Design", "Planning", "Complete",
            "Started", "QA", "Build", "Discovery"
        """,
    }
}

# ---------------------------------------------------------------------------
# Base SQL Query
# ---------------------------------------------------------------------------

def getBaseQueryV3(eligibleProjects, tenant_id=1, additional_condition=None, include_only_archive=False):
    project_ids_str = f"({', '.join(map(str, eligibleProjects))})"
    condition = additional_condition or ""
    query = f"""
        WITH ProjectData AS (
        SELECT
            wp.id AS project_id,
            wp.title AS title,
            wp.description AS project_description,
            wp.start_date AS start_date,
            wp.end_date AS end_date,
            CASE WHEN wp.archived_on IS NOT NULL THEN true ELSE false END AS is_archived_project,
            wp.archived_on AS archived_date,
            wp.comparison_criterias AS comparison_criterias,
            wp.total_external_spend AS project_budget,
            wp.project_location AS location,
            wp.project_type AS project_type,
            wp.sdlc_method AS sdlc_method,
            wp.state AS project_stage,
            wp.project_category AS project_category,
            wp.roadmap_id AS roadmap_id,
            wp.project_manager_id_id AS project_manager_id,
            wp.technology_stack AS tech_stack,
            wp.delivery_status AS schedule_status,
            wp.scope_status AS scope_status,
            wp.spend_status AS spend_status,
            wp.objectives AS project_objectives,
            wp.org_strategy_align AS org_strategy,
            wp.spend_type AS spend_type,
            wp.tenant_id_id AS tenant_id,
            wp.program_id AS program_id,
            wp.ref_docs AS reference_documents,
            wp.capex_budget AS capex_budget,
            wp.opex_budget AS opex_budget,
            wp.capex_pr_planned AS capex_purchase_recquistion_planned,
            wp.capex_po_planned AS capex_purchase_order_planned,
            wp.opex_pr_planned AS opex_purchase_recquistion_planned,
            wp.opex_po_planned AS opex_purchase_order_planned,
            wp.capex_actuals AS capex_actual,
            wp.opex_actuals AS opex_actual,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM adminapis_test_data atd
                    WHERE atd.table_pk = wp.id
                    AND atd.table_name = 'project'
                    AND atd.tenant_id = wp.tenant_id_id
                ) THEN true
                ELSE false
            END AS is_test_data
        FROM workflow_project AS wp
        WHERE wp.tenant_id_id = {tenant_id}
            AND wp.id IN {project_ids_str}
            AND ({'wp.archived_on IS NOT NULL' if include_only_archive else 'wp.archived_on IS NULL'})
            AND wp.parent_id IS NOT NULL
    ),
    ProjectManagerData AS (
        SELECT
            uu.id AS project_manager_id,
            uu.first_name AS project_manager_name
        FROM users_user AS uu
        WHERE uu.tenant_id = {tenant_id}
    ),
    StatusData AS (
        WITH LatestStatus AS (
            SELECT
                ps.project_id, ps.type, ps.value, ps.actual_percentage,
                ps.comments, ps.created_date,
                ROW_NUMBER() OVER (PARTITION BY ps.project_id, ps.type ORDER BY ps.created_date DESC) AS rn
            FROM workflow_projectstatus ps
            WHERE ps.project_id IN (SELECT project_id FROM ProjectData)
        )
        SELECT
            ls.project_id,
            MAX(CASE WHEN ls.type = 1 THEN ls.actual_percentage END) AS scope_completion_percent,
            ARRAY_AGG(
                jsonb_build_object(
                    'type', CASE WHEN ls.type=1 THEN 'scope_status' WHEN ls.type=2 THEN 'delivery_status' WHEN ls.type=3 THEN 'spend_status' ELSE 'unknown' END,
                    'value', CASE WHEN ls.value=1 THEN 'on_track' WHEN ls.value=2 THEN 'at_risk' WHEN ls.value=3 THEN 'compromised' ELSE 'unknown' END,
                    'comment', ls.comments,
                    'timestamp', ls.created_date
                ) ORDER BY ls.created_date DESC
            ) FILTER (WHERE ls.rn <= 10) AS status_comments
        FROM LatestStatus ls
        GROUP BY ls.project_id
    ),
    StatusCountData AS (
        SELECT
            ps.project_id,
            COUNT(*) AS total_status_updates,
            COUNT(*) FILTER (WHERE ps.type = 1) AS scope_status_updates_count,
            COUNT(*) FILTER (WHERE ps.type = 2) AS delivery_status_updates_count,
            COUNT(*) FILTER (WHERE ps.type = 3) AS spend_status_updates_count,
            MAX(ps.created_date) AS last_status_update_date,
            MIN(ps.created_date) AS first_status_update_date
        FROM workflow_projectstatus ps
        WHERE ps.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY ps.project_id
    ),
    PortfolioData AS (
        SELECT
            wpport.project_id,
            MAX(pp.title) AS portfolio,
            MAX(pp.id) AS portfolio_id,
            MAX(pp.first_name) AS portfolio_leader_first_name,
            MAX(pp.last_name) AS portfolio_leader_last_name
        FROM workflow_projectportfolio AS wpport
        LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
        GROUP BY wpport.project_id
    ),
    RoadmapData AS (
        SELECT rr.id AS roadmap_id, rr.title AS roadmap_name, rr.budget AS roadmap_budget
        FROM roadmap_roadmap AS rr
        WHERE rr.tenant_id = {tenant_id}
    ),
    ScopeData AS (
        SELECT
            wps.project_id,
            ARRAY_AGG(DISTINCT jsonb_build_object('scope', wps.scope)) AS scope
        FROM workflow_projectscope wps
        WHERE wps.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY wps.project_id
    ),
    ProviderData AS (
        SELECT
            wpprov.project_id,
            MAX(wpprov.id) AS provider_id,
            MAX(tp.company_name) AS provider_name
        FROM workflow_projectprovider AS wpprov
        LEFT JOIN tenant_provider AS tp ON tp.id = wpprov.provider_id
        GROUP BY wpprov.project_id
    ),
    KPIData AS (
        SELECT wpkpi.project_id, ARRAY_AGG(DISTINCT wpkpi.name) AS key_results
        FROM workflow_projectkpi AS wpkpi
        GROUP BY wpkpi.project_id
    ),
    MilestoneData AS (
        SELECT
            wpm.project_id,
            ARRAY_AGG(DISTINCT jsonb_build_object(
                'milestone_id', wpm.id, 'milestone_name', wpm.name,
                'planned_spend_amount', wpm.planned_spend, 'actual_spend_amount', wpm.actual_spend,
                'overrun', CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END,
                'target_date', wpm.target_date, 'actual_date', wpm.actual_date,
                'comments', wpm.comments,
                'status_value', CASE WHEN wpm.status_value=1 THEN 'not_started' WHEN wpm.status_value=2 THEN 'in_progress' WHEN wpm.status_value=3 THEN 'completed' ELSE NULL END,
                'milestone_type', CASE WHEN wpm.type=1 THEN 'scope_milestone' WHEN wpm.type=2 THEN 'schedule_milestone' WHEN wpm.type=3 THEN 'spend_milestone' ELSE NULL END,
                'team_id', wpm.team_id
            )) AS milestones,
            COALESCE(SUM(wpm.planned_spend), 0) AS planned_spend,
            COALESCE(SUM(wpm.actual_spend), 0) AS actual_spend,
            COALESCE(SUM(CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END), 0) AS overrun
        FROM workflow_projectmilestone AS wpm
        WHERE wpm.type IN (1, 2, 3)
        AND wpm.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY wpm.project_id
    ),
    TeamData AS (
        SELECT
            wpts.project_id,
            ARRAY_AGG(DISTINCT jsonb_build_object(
                'role', wpts.member_role, 'member_name', wpts.member_name,
                'average_rate_per_hour', wpts.average_spend, 'contribution_percentage', wpts.member_utilization,
                'member_location', wpts.location,
                'team_type', CASE WHEN wpts.is_external = false THEN 'Internal Team' ELSE 'External Team' END
            )) AS teamsdata
        FROM workflow_projectteamsplit AS wpts
        WHERE wpts.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY wpts.project_id
    ),
    RiskData AS (
        SELECT
            pr.project_id,
            ARRAY_AGG(jsonb_build_object(
                'id', pr.id, 'description', pr.description, 'impact', pr.impact,
                'mitigation', pr.mitigation, 'priority', pr.priority,
                'due_date', pr.due_date, 'status_value', pr.status_value, 'completed_on', pr.completed_on
            )) AS risks
        FROM workflow_projectrisk AS pr
        WHERE pr.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY pr.project_id
    ),
    BusinessMembersData AS (
        SELECT
            wpbm.project_id,
            COALESCE(
                json_agg(DISTINCT jsonb_build_object(
                    'first_name', pb.sponsor_first_name, 'last_name', pb.sponsor_last_name,
                    'email', pb.sponsor_email, 'role', pb.sponsor_role, 'business_unit', pb.bu_name
                )) FILTER (WHERE pb.id IS NOT NULL),
                '[]'
            ) AS business_members
        FROM workflow_projectbusinessmember wpbm
        JOIN ProjectData p ON p.project_id = wpbm.project_id
        LEFT JOIN projects_portfoliobusiness pb
            ON pb.id = wpbm.portfolio_business_id AND pb.tenant_id = p.tenant_id
        GROUP BY wpbm.project_id
    ),
    DependencyData AS (
        SELECT
            wpd.project_id,
            ARRAY_AGG(DISTINCT jsonb_build_object(
                'dependency_id', wpd.id, 'description', wpd.description,
                'impact', wpd.impact, 'comments_action', wpd.comments_action,
                'dependency_on', wpd.dependency_on,
                'status_value', CASE WHEN wpd.status_value=1 THEN 'pending' WHEN wpd.status_value=2 THEN 'in_progress' WHEN wpd.status_value=3 THEN 'resolved' ELSE NULL END,
                'target_date', wpd.target_date, 'owner', wpd.owner
            )) AS dependencies
        FROM workflow_projectdependency AS wpd
        WHERE wpd.tenant_id = {tenant_id}
        AND wpd.project_id IN (SELECT project_id FROM ProjectData)
        GROUP BY wpd.project_id
    ),
    ProgramData AS (
        SELECT pp.id AS program_id, pp.name AS program_name
        FROM program_program AS pp
        WHERE pp.tenant_id = {tenant_id}
    )
    SELECT
        p.*,
        pm.project_manager_name,
        s.scope_completion_percent,
        s.status_comments,
        sc.total_status_updates,
        sc.scope_status_updates_count,
        sc.delivery_status_updates_count,
        sc.spend_status_updates_count,
        sc.last_status_update_date,
        sc.first_status_update_date,
        po.portfolio,
        po.portfolio_id,
        r.roadmap_name,
        (CASE WHEN r.roadmap_budget > 0 THEN m.planned_spend / r.roadmap_budget ELSE 0 END) AS percent_roadmap_planned_budget,
        pr.provider_id,
        pr.provider_name,
        k.key_results,
        m.planned_spend,
        m.actual_spend,
        m.overrun,
        m.milestones,
        t.teamsdata,
        rd.risks,
        d.dependencies,
        pg.program_name,
        psd.scope AS project_scope,
        COALESCE(bm.business_members, '[]') AS business_members
    FROM ProjectData p
    LEFT JOIN StatusData s ON p.project_id = s.project_id
    LEFT JOIN StatusCountData sc ON p.project_id = sc.project_id
    LEFT JOIN PortfolioData po ON p.project_id = po.project_id
    LEFT JOIN RoadmapData r ON p.roadmap_id = r.roadmap_id
    LEFT JOIN ProviderData pr ON p.project_id = pr.project_id
    LEFT JOIN KPIData k ON p.project_id = k.project_id
    LEFT JOIN MilestoneData m ON p.project_id = m.project_id
    LEFT JOIN TeamData t ON p.project_id = t.project_id
    LEFT JOIN ProjectManagerData pm ON p.project_manager_id = pm.project_manager_id
    LEFT JOIN RiskData rd ON p.project_id = rd.project_id
    LEFT JOIN DependencyData d ON p.project_id = d.project_id
    LEFT JOIN ProgramData pg ON p.program_id = pg.program_id
    LEFT JOIN ScopeData psd ON p.project_id = psd.project_id
    LEFT JOIN BusinessMembersData bm ON p.project_id = bm.project_id
    {condition}
    """
    return query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_tz(ts):
    """Strip timezone info from a pandas Timestamp so comparisons are safe."""
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    ts = pd.to_datetime(ts, errors="coerce")
    if pd.isna(ts):
        return None
    if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _normalize_col(series: pd.Series) -> pd.Series:
    """Convert a datetime Series to tz-naive."""
    series = pd.to_datetime(series, errors="coerce")
    if series.dt.tz is not None:
        series = series.dt.tz_localize(None)
    return series


# ---------------------------------------------------------------------------
# ProjectAgent
# ---------------------------------------------------------------------------

class ProjectAgent:
    def __init__(self, tenant_id, user_id, socketio=None, llm=None,
                 client_id=None, base_agent=None, sessionID=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.socketio = socketio
        self.llm = llm
        self.client_id = client_id
        self.batch_size = 5
        self.base_agent = base_agent
        self.user_context = self._build_user_context(base_agent)
        self.sessionID = sessionID
        self.last_results = []
        self.check_track_conformation_state()
        self.chat_history = []
        self.ongoing_evaluation = []
        self.eval_response = []
        self.logInDb = {"tenant_id": tenant_id, "user_id": user_id}

    def check_track_conformation_state(self):
        res = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(
            session_id=self.sessionID, user_id=self.user_id, key="analysis_confirmed")
        val = len(res) > 0 and res[0]["value"] == "True"
        self.analysis_confirmed = val
        print("debug -- check_track_conformation_state --- ", val, res)

    def add_track_conformation_state(self, state):
        print("debug add_track_conformation_state ", state)
        TangoDao.insertTangoState(
            tenant_id=self.tenant_id, user_id=self.user_id,
            key="analysis_confirmed", value=state, session_id=self.sessionID)
        self.check_track_conformation_state()

    def _build_user_context(self, base_agent):
        if not base_agent:
            return ""
        return f"{base_agent.context_string}\n{base_agent.org_info_string}\n{base_agent.user_info_string}\n{base_agent.program_list}"

    # -----------------------------------------------------------------------
    # Planning
    # -----------------------------------------------------------------------

    def plan_analysis_prompt(self, query: str) -> Dict:
        if not self.llm:
            raise ValueError("LLM instance is required for planning analysis")

        TangoDao.insertTangoState(
            tenant_id=self.tenant_id, user_id=self.user_id,
            key="project_analyst", value=f"User Question: {query}",
            session_id=self.sessionID)

        schema_str = json.dumps(PROJECT_SCHEMA, indent=2)
        conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAllValue(
            session_id=self.sessionID, user_id=self.user_id, key="project_analyst")[::-1]
        currentDate = datetime.datetime.now().date().isoformat()

        system_prompt = f"""
            Ongoing Conversation:
            <ongoing_conversation>
            {conv}
            </ongoing_conversation>

            Schema (use exactly these field names):
            {schema_str}

            User context:
            {self.user_context}

            Today's date: {currentDate}

            =============================================================
            ### STRICT OUTPUT CONTRACT — READ CAREFULLY
            =============================================================

            You must output a JSON object with this exact structure:

            {{
            "steps": [ ...filter steps... ],
            "clarification_needed": false,
            "clarification_message": null,
            "reason_behind_this_analysis": "...",
            "use_clustering": false,
            "check_team_resources": false
            }}

            Each step in "steps" must be exactly:
            {{
            "type": "filter",
            "field": "<single string field name>",
            "operation": "<one of the allowed operations below>",
            "value": <string | number | list | dict>,
            "fields": [ ...list of field names to load for this step... ]
            }}

            =============================================================
            ### ALLOWED OPERATIONS — USE ONLY THESE, NOTHING ELSE
            =============================================================

            | Operation      | Value type                        | Use for                                      |
            |----------------|-----------------------------------|----------------------------------------------|
            | equals         | string                            | exact match on any string field              |
            | not_equals     | string                            | exclude exact value                          |
            | in             | list of strings or ints           | match any value in list                      |
            | not_in         | list of strings or ints           | exclude list of values                       |
            | contains       | string                            | substring search in text / nested list       |
            | less_than      | date string "YYYY-MM-DD"          | field < value (dates only)                   |
            | greater_than   | date string "YYYY-MM-DD"          | field > value (dates only)                   |
            | in_range       | {{"lower": "YYYY-MM-DD", "upper": "YYYY-MM-DD"}} | date range          |

            =============================================================
            ### STRICT RULES FOR STEPS
            =============================================================

            1. "field" is ALWAYS a single string — NEVER a list.
            2. If you need to filter multiple fields (e.g., all three statuses),
            create ONE step PER field. Each step is ANDed with the next.
            3. NEVER use: equals_any, logic, additional_filter, or any key
            not defined in the step schema above.
            4. "fields" only needs to be populated on the FIRST step.
            All subsequent steps can have "fields": [].
            The union of all "fields" across all steps is used for data loading.
            5. Steps are applied sequentially as AND conditions.

            =============================================================
            ### FIELD SELECTION — BE MINIMAL
            =============================================================

            Only include fields that are DIRECTLY needed to answer the query.
            Core fields always included automatically: project_id, title.

            Status queries      → scope_status, schedule_status, spend_status
            Budget queries      → planned_spend, actual_spend, spend_status
            Date queries        → start_date, end_date
            Risk queries        → risks
            Dependency queries  → dependencies
            Program queries     → program_id, program_name
            Team queries        → project_manager_name, teamsdata
            Sponsor queries     → business_members
            Document queries    → reference_documents
            Archived queries    → is_archived_project, archived_date
            Status freq queries → total_status_updates, last_status_update_date

            =============================================================
            ### EXAMPLES
            =============================================================

            Query: "Green status projects past their end date"
            → CORRECT (4 separate single-field steps):
            {{
            "steps": [
                {{
                "type": "filter",
                "field": "end_date",
                "operation": "less_than",
                "value": "{currentDate}",
                "fields": ["project_id", "title", "end_date", "schedule_status", "scope_status", "spend_status", "portfolio", "project_manager_name"]
                }},
                {{"type": "filter", "field": "schedule_status", "operation": "equals", "value": "on_track", "fields": []}},
                {{"type": "filter", "field": "scope_status",    "operation": "equals", "value": "on_track", "fields": []}},
                {{"type": "filter", "field": "spend_status",    "operation": "equals", "value": "on_track", "fields": []}}
            ],
            "clarification_needed": false,
            "clarification_message": null,
            "reason_behind_this_analysis": "...",
            "use_clustering": false,
            "check_team_resources": false
            }}

            → WRONG (do NOT do this):
            "field": ["schedule_status", "scope_status", "spend_status"]   ← list not allowed
            "operation": "equals_any"                                       ← not an allowed operation
            "additional_filter": {{...}}                                    ← not allowed

            Query: "Projects with no status updates in 30 days"
            {{
            "steps": [
                {{
                "type": "filter",
                "field": "last_status_update_date",
                "operation": "less_than",
                "value": "{(datetime.datetime.now() - datetime.timedelta(days=30)).date().isoformat()}",
                "fields": ["project_id", "title", "last_status_update_date", "total_status_updates", "schedule_status"]
                }}
            ],
            ...
            }}

            Query: "At-risk or compromised projects"
            {{
            "steps": [
                {{
                "type": "filter",
                "field": "schedule_status",
                "operation": "in",
                "value": ["at_risk", "compromised"],
                "fields": ["project_id", "title", "schedule_status", "scope_status", "spend_status"]
                }}
            ],
            ...
            }}

            Query: "Closed projects from last year"
            {{
            "steps": [
                {{
                "type": "filter",
                "field": "is_archived_project",
                "operation": "equals",
                "value": "true",
                "fields": ["project_id", "title", "is_archived_project", "archived_date"]
                }},
                {{
                "type": "filter",
                "field": "archived_date",
                "operation": "in_range",
                "value": {{"lower": "{(datetime.datetime.now().year - 1)}-01-01", "upper": "{(datetime.datetime.now().year - 1)}-12-31"}},
                "fields": []
                }}
            ],
            ...
            }}

            ## status hints
            "Green / on_track projects" → ALL THREE dimensions must be on_track (AND)
            → Three separate steps, one per field:
                step 1: field "schedule_status" operation "equals" value "on_track"
                step 2: field "scope_status"    operation "equals" value "on_track"  
                step 3: field "spend_status"    operation "equals" value "on_track"

            "At risk / amber projects" → ANY ONE dimension is at_risk (OR)
            → ONE step: field "any_status" operation "equals" value "at_risk"

            "Compromised / red projects" → ANY ONE dimension is compromised (OR)
            → ONE step: field "any_status" operation "equals" value "compromised"
            

            =============================================================
            ### IMPORTANT NOTES
            =============================================================
            - Archived vs active projects are mutually exclusive. If user mentions closed/archived projects,
            include a step for is_archived_project equals "true".
            - For "at-risk" or "compromised" queries without specifying a dimension,
                use field "any_status" operation "equals" with value "at_risk" or "compromised".
                This applies OR logic across all three status dimensions.
            - For status-only queries (no analysis requested), do NOT add analysis steps.
            - Do NOT filter unless the query explicitly asks for filtering.
            """

        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=f"""Generate JSON analysis plan for: '{query}'.

REMEMBER:
- "field" must always be a single string, never a list
- Only use allowed operations: equals, not_equals, in, not_in, contains, less_than, greater_than, in_range
- One step per field — create multiple steps if filtering multiple fields
- "fields" list only on first step, empty [] on others
- No additional_filter, no logic key, no equals_any
"""
        )

        response = self.llm.run(
            chat_completion,
            ModelOptions(model="gpt-4.1", max_tokens=3096, temperature=0.1),
            "tango::project::process",
            logInDb=self.logInDb
        )

        try:
            analysis_plan = extract_json_after_llm(response)
            return analysis_plan
        except json.JSONDecodeError:
            raise ValueError(f"LLM response is not valid JSON: {response}")

    # -----------------------------------------------------------------------
    # Fetch Projects (SQL level)
    # -----------------------------------------------------------------------

    def fetch_projects(self, filters: Dict = None) -> List[Dict]:
        eligible_projects = ProjectsDao.FetchAvailableProject(
            tenant_id=self.tenant_id, user_id=self.user_id)
        print("eligible projects in fetch_projects ---- ", eligible_projects)

        filter_string = ""
        include_only_archived = False

        if filters:
            conditions = []
            for condition in filters.get("llm_filters", []):
                field = condition["field"]
                operation = condition["operation"]
                value = condition["value"]
                print("DEBUG: LLM filter -- ", field, operation, value)

                if field == "is_archived_project":
                    include_only_archived = (str(value).lower() in ["true", "1"])

                elif field == "all":
                    for f in ["title", "project_objectives", "project_category",
                              "org_strategy", "dependencies", "program_name", "business_members"]:
                        conditions.append(f"LOWER(p.{f}) LIKE LOWER('%{value}%')")

                elif operation == "in" and field == "project_id":
                    ids = ', '.join(map(str, value))
                    conditions.append(f"p.project_id IN ({ids})")

                elif field == "any_status" and operation == "equals":
                    conditions.append(
                        f"(p.schedule_status = '{value}' OR p.scope_status = '{value}' OR p.spend_status = '{value}')"
                    )

                elif operation == "in" and field == "portfolio_id":
                    ids = ', '.join(map(str, value))
                    conditions.append(f"po.portfolio_id IN ({ids})")

                elif operation == "in" and field == "program_id":
                    ids = ', '.join(map(str, value))
                    conditions.append(f"p.program_id IN ({ids})")

                elif field in ["start_date", "end_date", "archived_date"]:
                    if operation == "less_than" and value:
                        conditions.append(f"p.{field} < '{value}'")
                    elif operation == "greater_than" and value:
                        conditions.append(f"p.{field} > '{value}'")
                    elif operation == "in_range" and isinstance(value, dict):
                        lower = value.get("lower")
                        upper = value.get("upper")
                        if lower and upper:
                            conditions.append(f"p.{field} BETWEEN '{lower}' AND '{upper}'")
                        elif lower:
                            conditions.append(f"p.{field} >= '{lower}'")
                        elif upper:
                            conditions.append(f"p.{field} <= '{upper}'")

                # status fields — push to SQL level too for efficiency
                elif field in ["schedule_status", "scope_status", "spend_status"]:
                    if operation == "equals" and value:
                        conditions.append(f"p.{field} = '{value}'")
                    elif operation == "not_equals" and value:
                        conditions.append(f"p.{field} != '{value}'")
                    elif operation == "in" and isinstance(value, list):
                        vals = ', '.join(f"'{v}'" for v in value)
                        conditions.append(f"p.{field} IN ({vals})")
                    elif operation == "not_in" and isinstance(value, list):
                        vals = ', '.join(f"'{v}'" for v in value)
                        conditions.append(f"p.{field} NOT IN ({vals})")

                # searchable text fields
                elif operation == "contains" and field in ["title", "project_objectives",
                                                            "project_category", "org_strategy"]:
                    conditions.append(f"LOWER(p.{field}) LIKE LOWER('%{value}%')")

            if conditions:
                filter_string = " WHERE " + " AND ".join(conditions)

        print("debug 0-- include_only_archived", include_only_archived)
        if include_only_archived:
            eligible_projects = ProjectsDao.FetchAccesibleArchivedProjects(
                tenant_id=self.tenant_id, user_id=self.user_id)

        query = getBaseQueryV3(
            eligible_projects, self.tenant_id, filter_string,
            include_only_archive=include_only_archived)
        print("DEBUG::project_query", query)

        raw_response_ = db_instance.retrieveSQLQueryOld(query)
        raw_response1 = self.fetch_refdocs_details(raw_response_)
        raw_response = clean_raw_data(raw_response1)

        with open("project_data.json", "w") as f:
            json.dump(raw_response, f, indent=2, cls=DateEncoder)

        if isinstance(raw_response, str):
            raw_response = json.loads(raw_response)
        if not isinstance(raw_response, list):
            raw_response = [raw_response] if isinstance(raw_response, dict) else []

        print("DEBUG: project analyst Raw response count = ", len(raw_response))
        self.last_results = [r["project_id"] for r in raw_response]
        return raw_response

    def fetch_refdocs_details(self, raw_response: list):
        from src.trmeric_utils.helper.file_analyser import FileAnalyzer
        self.file_analyzer = FileAnalyzer(tenant_id=self.tenant_id)
        try:
            for r in raw_response:
                reference_documents = r.get('reference_documents', {}) or {}
                if not reference_documents:
                    continue
                ref_docs_s3_keys = [
                    docs.get('file') for docs in reference_documents
                    if docs.get('file')
                ]
                print("\n--debug ref_docs_s3_keys------", ref_docs_s3_keys)
                doc_details = self.file_analyzer.analyze_files(
                    params={"files_s3_keys_to_read": ref_docs_s3_keys})
                r.pop('reference_documents', None)
                r["reference_documents"] = doc_details
            return raw_response
        except Exception as e:
            print("--debug error fetch_refdocs_details------", str(e))
            return raw_response

    # -----------------------------------------------------------------------
    # Execute Analysis (Python-level filtering)
    # -----------------------------------------------------------------------

    def execute_analysis(self, raw_data: List[Dict], analysis_plan: Dict) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame(columns=["title", "project_objectives", "project_description"])

        df = pd.DataFrame([
            {
                "project_id": r["project_id"],
                "title": r.get("title", ""),
                "is_test_data": r.get("is_test_data") or False,
            }
            for r in raw_data
        ])

        # Collect all fields needed across all steps
        required_fields = set()
        for step in analysis_plan.get("steps", []):
            if "fields" in step:
                required_fields.update(step["fields"])
            if step.get("type") == "filter":
                f = step.get("field")
                if not f or f in ("any_status", "all"):  # ← skip virtual fields here
                    continue
                if f and isinstance(f, str) and f != "all":
                    required_fields.add(f)
                elif f and isinstance(f, list):
                    # Defensive: handle if LLM still sends a list despite instructions
                    required_fields.update(f)

        field_mapping = {
            "project_id":                        lambda r: r["project_id"],
            "title":                             lambda r: r.get("title"),
            "project_description":               lambda r: r.get("project_description"),
            "is_test_data":                      lambda r: r.get("is_test_data"),
            "is_archived_project":               lambda r: r.get("is_archived_project") or False,
            "archived_date":                     lambda r: pd.to_datetime(r.get("archived_date"), errors="coerce"),
            "project_objectives":                lambda r: r.get("project_objectives"),
            "project_manager_name":              lambda r: clean_text(r.get("project_manager_name", "") or ""),
            "schedule_status":                   lambda r: clean_text(r.get("schedule_status", "") or ""),
            "scope_status":                      lambda r: clean_text(r.get("scope_status", "") or ""),
            "spend_status":                      lambda r: clean_text(r.get("spend_status", "") or ""),
            "planned_spend":                     lambda r: float(r.get("planned_spend", 0) or 0),
            "project_budget":                    lambda r: float(r.get("project_budget", 0) or 0),
            "actual_spend":                      lambda r: float(r.get("actual_spend", 0) or 0),
            "start_date":                        lambda r: pd.to_datetime(r.get("start_date"), errors="coerce"),
            "end_date":                          lambda r: pd.to_datetime(r.get("end_date"), errors="coerce"),
            "project_category":                  lambda r: clean_text(r.get("project_category", "")),
            "org_strategy":                      lambda r: clean_text(r.get("org_strategy", "")),
            "scope_completion_percent":          lambda r: float(r.get("scope_completion_percent", 0) or 0),
            "milestones":                        lambda r: r.get("milestones", []) or [],
            "teamsdata":                         lambda r: r.get("teamsdata", []) or [],
            "team_resources":                    lambda r: r.get("team_resources", []) or [],
            "key_results":                       lambda r: r.get("key_results", []) or [],
            "roadmap_name":                      lambda r: r.get("roadmap_name", "") or "",
            "portfolio":                         lambda r: r.get("portfolio", "") or "",
            "portfolio_id":                      lambda r: r.get("portfolio_id", []) or [],
            "project_stage":                     lambda r: r.get("project_stage") or "",
            "capex_purchase_recquistion_planned":lambda r: float(r.get("capex_purchase_recquistion_planned") or 0),
            "opex_purchase_recquistion_planned": lambda r: float(r.get("opex_purchase_recquistion_planned") or 0),
            "capex_purchase_order_planned":      lambda r: float(r.get("capex_purchase_order_planned") or 0),
            "opex_purchase_order_planned":       lambda r: float(r.get("opex_purchase_order_planned") or 0),
            "capex_budget":                      lambda r: float(r.get("capex_budget") or 0),
            "capex_actual":                      lambda r: float(r.get("capex_actual") or 0),
            "opex_budget":                       lambda r: float(r.get("opex_budget") or 0),
            "opex_actual":                       lambda r: float(r.get("opex_actual") or 0),
            "risks": lambda r: [
                {
                    "id": risk.get("id"),
                    "description": clean_text(sanitize_html(risk.get("description", "") or "")),
                    "impact": clean_text(risk.get("impact", "")),
                    "mitigation": clean_text(sanitize_html(risk.get("mitigation", "") or "")),
                    "priority": risk.get("priority"),
                    "due_date": risk.get("due_date"),
                    "status_value": risk.get("status_value"),
                    "completed_on": clean_text(risk.get("completed_on") or ""),
                }
                for risk in (r.get("risks") or []) if isinstance(risk, dict)
            ],
            "status_comments": lambda r: [
                {
                    "comment": clean_text(sanitize_html(c.get("comment", "") or "")),
                    "timestamp": c.get("timestamp", "") or "",
                }
                for c in (r.get("status_comments") or []) if isinstance(c, dict)
            ],
            "total_status_updates":          lambda r: int(r.get("total_status_updates", 0) or 0),
            "scope_status_updates_count":    lambda r: int(r.get("scope_status_updates_count", 0) or 0),
            "delivery_status_updates_count": lambda r: int(r.get("delivery_status_updates_count", 0) or 0),
            "spend_status_updates_count":    lambda r: int(r.get("spend_status_updates_count", 0) or 0),
            "last_status_update_date":       lambda r: pd.to_datetime(r.get("last_status_update_date"), errors="coerce"),
            "first_status_update_date":      lambda r: pd.to_datetime(r.get("first_status_update_date"), errors="coerce"),
            "dependencies":                  lambda r: r.get("dependencies", []) or [],
            "program_id":                    lambda r: r.get("program_id", "") or "",
            "program_name":                  lambda r: clean_text(r.get("program_name", "") or ""),
                        "reference_documents": lambda r: (
                [
                    {
                        # "session_id": ref_docs.get("session_id"),
                        "files": [
                            {
                                "filename": f.get("filename"),
                                "content": f.get("content"),
                                # "file_type": f.get("file_type"),
                                # "file_s3_key": f.get("file_s3_key"),
                                # "upload_timestamp": f.get("upload_timestamp"),
                            }
                            for f in ref_docs.get("files", [])
                            if isinstance(f, dict)
                        ],
                        "file_count": len(ref_docs.get("files", [])),
                    }
                ]
                if isinstance((ref_docs := r.get("reference_documents")), dict)
                else [
                    {
                        "files": [{"filename": f.get("filename"), "content": f.get("content")}
                                   for f in docs.get("files", []) if isinstance(f, dict)],
                        "file_count": len(docs.get("files", [])),
                    }
                    for docs in (r.get("reference_documents") or [])
                    if isinstance(docs, dict)
                ]
            ),
            "business_members": lambda r: (
                [
                    {
                        "name": (b.get("first_name") or "") + " " + (b.get("last_name") or ""),
                        "email": b.get("email"),
                        "role": b.get("role"),
                        "business_unit": b.get("business_unit"),
                    }
                    for b in (r.get("business_members") or []) if b
                ]
            ),
        }

        # Load required fields into DataFrame
        for field in required_fields:
            if field in field_mapping and field not in df.columns:
                try:
                    df[field] = [field_mapping[field](r) for r in raw_data]
                except Exception as e:
                    print(f"error loading field {field}: {e}")
                    df[field] = [None] * len(raw_data)

        # Apply filter steps
        for step in analysis_plan.get("steps", []):
            if step.get("type") != "filter":
                continue

            raw_field = step.get("field")
            operation = step.get("operation")
            value = step.get("value")

            # Defensive: if LLM still sends a list, fan out recursively
            if isinstance(raw_field, list):
                print(f"DEBUG: LLM returned list field {raw_field} — fanning out into separate steps")
                for f in raw_field:
                    synthetic_step = {**step, "field": f, "fields": []}
                    analysis_plan_synthetic = {"steps": [synthetic_step]}
                    df = self.execute_analysis.__func__(self, df.to_dict(orient="records"),  # noqa
                                                        analysis_plan_synthetic) if False else df
                    # simpler inline application:
                    df = self._apply_single_filter(df, raw_data, field_mapping, f, operation, value)
                continue

            if not isinstance(raw_field, str):
                print(f"DEBUG: Skipping step — unexpected field type {type(raw_field)}: {raw_field}")
                continue

            df = self._apply_single_filter(df, raw_data, field_mapping, raw_field, operation, value)

        print(f"DEBUG: Final DataFrame rows = {len(df)}, columns = {list(df.columns)}")
        print(df.head(2))
        return df

    def _apply_single_filter(self, df, raw_data, field_mapping, field, operation, value):
        """Apply one filter step to df. Returns the (possibly narrowed) df."""
        temp_df = df.copy()

        # ── any_status OR filter — FIRST, before column existence check ──────────
        if field == "any_status" and operation == "equals" and value in ["at_risk", "compromised"]:
            status_cols = ["schedule_status", "scope_status", "spend_status"]
            for sc in status_cols:
                if sc not in temp_df.columns and sc in field_mapping:
                    try:
                        temp_df[sc] = [field_mapping[sc](r) for r in raw_data]
                        df[sc] = temp_df[sc]
                    except Exception as e:
                        print(f"error loading {sc}: {e}")
            mask = (
                (temp_df["schedule_status"] == value) |
                (temp_df["scope_status"]    == value) |
                (temp_df["spend_status"]    == value)
            )
            return temp_df[mask]

        # Ensure the field column exists
        if field not in ["all", "is_archived_project"] and field not in temp_df.columns:
            if field in field_mapping:
                try:
                    temp_df[field] = [field_mapping[field](r) for r in raw_data]
                    # keep it in df too so later steps can see it
                    df[field] = temp_df[field]
                except Exception as e:
                    print(f"DEBUG: could not load field {field} for filter: {e}")
                    return df
            else:
                print(f"DEBUG: Skipping — field '{field}' not in field_mapping")
                return df

        # ── Date fields ──────────────────────────────────────────────────────
        if field in DATE_FIELDS:
            col = _normalize_col(temp_df[field])

            if operation in ["less_than", "greater_than"] and value:
                cutoff = _normalize_tz(pd.to_datetime(value, errors="coerce"))
                if cutoff is None:
                    print(f"DEBUG: Skipping — cannot parse date value '{value}'")
                    return df
                if operation == "less_than":
                    return temp_df[col < cutoff]
                else:
                    return temp_df[col > cutoff]

            # ── any_status OR filter (at_risk / compromised) ─────────────────────────
            if field == "any_status" and operation == "equals" and value in ["at_risk", "compromised"]:
                status_cols = ["schedule_status", "scope_status", "spend_status"]
                for sc in status_cols:
                    if sc not in temp_df.columns and sc in field_mapping:
                        try:
                            temp_df[sc] = [field_mapping[sc](r) for r in raw_data]
                            df[sc] = temp_df[sc]
                        except Exception as e:
                            print(f"error loading {sc}: {e}")
                mask = (
                    (temp_df["schedule_status"] == value) |
                    (temp_df["scope_status"]    == value) |
                    (temp_df["spend_status"]    == value)
                )
                return temp_df[mask]

            elif operation == "in_range" and isinstance(value, dict):
                lower = _normalize_tz(pd.to_datetime(value.get("lower"), errors="coerce"))
                upper = _normalize_tz(pd.to_datetime(value.get("upper"), errors="coerce"))
                if lower is not None and upper is not None:
                    return temp_df[(col >= lower) & (col <= upper)]
                elif lower is not None:
                    return temp_df[col >= lower]
                elif upper is not None:
                    return temp_df[col <= upper]
                return df

            else:
                print(f"DEBUG: Skipping — unsupported operation '{operation}' for date field '{field}'")
                return df

        # ── Boolean archive ──────────────────────────────────────────────────
        elif field == "is_archived_project":
            target = str(value).lower() in ["true", "1", True]
            return temp_df[temp_df["is_archived_project"] == target]

        # ── String / status fields — equals / not_equals / in / not_in ──────
        elif operation == "equals" and field in temp_df.columns:
            return temp_df[temp_df[field] == value]

        elif operation == "not_equals" and field in temp_df.columns:
            return temp_df[temp_df[field] != value]

        elif operation == "in" and field in temp_df.columns:
            allowed = value if isinstance(value, list) else [value]
            return temp_df[temp_df[field].isin(allowed)]

        elif operation == "not_in" and field in temp_df.columns:
            excluded = value if isinstance(value, list) else [value]
            return temp_df[~temp_df[field].isin(excluded)]

        # ── Text contains ────────────────────────────────────────────────────
        elif operation == "contains" and field == "program_name":
            return temp_df[temp_df["program_name"].str.contains(str(value), case=False, na=False)]

        elif operation == "contains" and field == "title":
            return temp_df[temp_df["title"].str.contains(str(value), case=False, na=False)]

        # ── Business members ─────────────────────────────────────────────────
        elif field == "business_members" and operation == "contains":
            sv = str(value).lower()
            def _has_member(members):
                if not isinstance(members, list):
                    return False
                return any(sv in (m.get("name", "")).lower() for m in members if isinstance(m, dict))
            return temp_df[temp_df["business_members"].apply(_has_member)]

        # ── Dependencies ─────────────────────────────────────────────────────
        elif field == "dependencies" and operation == "equals" and value in ["pending", "in_progress", "resolved"]:
            def _has_dep_status(deps):
                return isinstance(deps, list) and any(
                    isinstance(d, dict) and d.get("status_value") == value for d in deps)
            return temp_df[temp_df["dependencies"].apply(_has_dep_status)]

        elif field == "dependencies" and operation == "contains" and isinstance(value, dict) and value.get("target_date") is None:
            def _has_missing_dep_date(deps):
                return isinstance(deps, list) and any(
                    isinstance(d, dict) and not d.get("target_date") for d in deps)
            return temp_df[temp_df["dependencies"].apply(_has_missing_dep_date)]

        elif field == "dependencies" and operation == "in_range" and isinstance(value, dict):
            lower = _normalize_tz(pd.to_datetime(value.get("lower"), errors="coerce"))
            upper = _normalize_tz(pd.to_datetime(value.get("upper"), errors="coerce"))
            def _dep_in_range(deps):
                if not isinstance(deps, list):
                    return False
                for d in deps:
                    if not isinstance(d, dict):
                        continue
                    td = _normalize_tz(pd.to_datetime(d.get("target_date"), errors="coerce"))
                    if td is None:
                        continue
                    if lower and upper and lower <= td <= upper:
                        return True
                    if lower and not upper and td >= lower:
                        return True
                    if upper and not lower and td <= upper:
                        return True
                return False
            return temp_df[temp_df["dependencies"].apply(_dep_in_range)]

        # ── Milestones ───────────────────────────────────────────────────────
        elif field == "milestones" and operation == "contains" and isinstance(value, dict) and value.get("target_date") is None:
            def _has_missing_ms_date(ms):
                return isinstance(ms, list) and any(
                    isinstance(m, dict) and not m.get("target_date") for m in ms)
            return temp_df[temp_df["milestones"].apply(_has_missing_ms_date)]

        # ── Program id (in list) ─────────────────────────────────────────────
        elif field == "program_id" and operation == "in":
            allowed = value if isinstance(value, list) else [value]
            return temp_df[temp_df["program_id"].isin(allowed)]

        # ── all-field text search (fallback) ─────────────────────────────────
        elif field == "all" and operation == "contains" and value:
            mask = pd.Series([False] * len(temp_df), index=temp_df.index)
            for col in ["title", "project_objectives", "project_category", "org_strategy", "program_name"]:
                if col in temp_df.columns:
                    mask = mask | temp_df[col].str.contains(str(value), case=False, na=False)
            return temp_df[mask]

        else:
            print(f"DEBUG: Skipping unsupported filter — field: {field}, operation: {operation}, value: {value}")
            return df

    # -----------------------------------------------------------------------
    # Clustering
    # -----------------------------------------------------------------------

    def cluster_projects(self, df):
        feature_matrices = []
        for column in df.columns:
            if column == "cluster":
                continue
            col_data = df[column].fillna("").tolist()
            if all(isinstance(x, (int, float)) and not pd.isna(x) for x in col_data):
                values = np.array(col_data, dtype=float).reshape(-1, 1)
                feature_matrices.append((values - values.mean()) / (values.std() + 1e-8))
            elif all(isinstance(x, str) for x in col_data):
                if len(set(col_data)) < len(col_data) // 2:
                    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
                    feature_matrices.append(encoder.fit_transform([[x] for x in col_data]))
                else:
                    vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
                    feature_matrices.append(vectorizer.fit_transform(col_data).toarray())
            elif all(isinstance(x, list) for x in col_data):
                all_items = sorted(set(item for sub in col_data for item in sub if isinstance(item, str)))
                if all_items:
                    encoder = OneHotEncoder(categories=[all_items], sparse_output=False, handle_unknown="ignore")
                    feature_matrices.append(encoder.fit_transform(
                        [[i for i in row if isinstance(i, str)] or [""] for row in col_data]))

        combined = np.hstack(feature_matrices) if feature_matrices else np.zeros((len(df), 1))
        n = len(df)
        k = max(1, min(int(np.sqrt(n)), n // 10)) if n > 1 else 1
        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        try:
            df["cluster"] = kmeans.fit_predict(combined)
        except ValueError as e:
            print(f"DEBUG: Clustering failed — {e}")
            df["cluster"] = 0
        return df, k

    # -----------------------------------------------------------------------
    # Process Query (main entry point)
    # -----------------------------------------------------------------------

    def process_query(self, query: str, filters: Optional[Dict] = None):
        analysis_plan = self.plan_analysis_prompt(query)
        print(f"DEBUG: Analysis plan = {json.dumps(analysis_plan, indent=2)}")

        llm_filters = []
        searchable_fields = ["title", "project_objectives", "project_category", "org_strategy"]

        for step in analysis_plan.get("steps", []):
            if step.get("type") != "filter":
                continue

            raw_field = step.get("field")
            operation = step.get("operation")
            value = step.get("value")

            # Defensive: fan out list fields
            field_list = raw_field if isinstance(raw_field, list) else [raw_field]

            for field in field_list:
                if not isinstance(field, str):
                    print(f"DEBUG: process_query skipping non-string field: {field}")
                    continue

                # Archive handling
                if field == "is_archived_project" and operation == "equals":
                    llm_filters.append({"field": "is_archived_project", "operation": "equals", "value": value})
                    continue

                if field == "archived_date" and operation == "in_range":
                    llm_filters.append({"field": "archived_date", "operation": "in_range", "value": value})
                    llm_filters.append({"field": "is_archived_project", "operation": "equals", "value": "true"})
                    continue

                if field == "any_status" and operation == "equals" and value:
                    llm_filters.append({"field": "any_status", "operation": "equals", "value": value})
                    continue

                # Date fields → push to SQL
                if field in ["start_date", "end_date", "archived_date"] and \
                   operation in ["less_than", "greater_than", "in_range"]:
                    llm_filters.append({"field": field, "operation": operation, "value": value})
                    continue

                # ID list filters → push to SQL
                if operation == "in" and field in ["project_id", "portfolio_id", "program_id"] and value:
                    llm_filters.append({"field": field, "operation": "in", "value": value})
                    continue

                # Status fields → push to SQL
                if field in ["schedule_status", "scope_status", "spend_status"] and \
                   operation in ["equals", "not_equals", "in", "not_in"] and value:
                    llm_filters.append({"field": field, "operation": operation, "value": value})
                    continue

                # Text search → push to SQL
                if operation == "contains" and value:
                    if field == "all":
                        for f in searchable_fields:
                            llm_filters.append({"field": f, "operation": "contains", "value": value})
                    elif field in searchable_fields:
                        llm_filters.append({"field": field, "operation": "contains", "value": value})
                    continue

                if operation == "equals" and value and field in searchable_fields:
                    llm_filters.append({"field": field, "operation": "equals", "value": value})
                    continue

                # Everything else stays for Python-level filtering in execute_analysis
                # (e.g., dependencies, milestones, business_members, last_status_update_date)
                print(f"DEBUG: process_query — field '{field}' op '{operation}' kept for Python filtering")

        combined_filters = {"user_filters": {}, "llm_filters": llm_filters}
        raw_data = self.fetch_projects(combined_filters if llm_filters or filters else None)
        print(f"DEBUG: project Raw data fetched = {len(raw_data)}")

        processed_df = self.execute_analysis(raw_data, analysis_plan)
        processed_data = processed_df.to_dict(orient="records")
        processed_data = sanitize_data(processed_data)

        with open("processed_project_data.json", "w") as f:
            json.dump(processed_data, f, indent=2, cls=DateEncoder)

        print(f"DEBUG: Processed data = {len(processed_data)}")

        if self.socketio:
            self.socketio.emit(
                "tango_ui",
                {"event": "project_analysis", "component": "table",
                 "data": processed_data, "response_instruction": "Filtered data", "partial": False},
                room=self.client_id)

        if not analysis_plan.get("steps", []):
            yield "## Here's Everything\nLoaded all your projects. What do you want to analyze next?"
            return

        if analysis_plan.get("clarification_needed", False):
            yield analysis_plan.get("clarification_message", "Please clarify your query.")
            return

        all_evaluations, all_data = [], []
        eval_lock = threading.Lock()
        max_threads = min(5, len(processed_data) // self.batch_size + 1)

        def process_batch(batch, batch_num, total_batches):
            print(f"DEBUG: Evaluating batch {batch_num}/{total_batches}, size={len(batch)} "
                  f"in thread {threading.current_thread().name}")
            self.eval_response.extend(batch)
            return batch_num, batch, []

        analysis_plan["use_clustering"] = False  # keep off for now
        if analysis_plan.get("use_clustering", False) and len(processed_data) > 1:
            yield f"### Clustering Analysis\nGrouping {len(processed_data)} projects.\n"
            clustered_df, n_clusters = self.cluster_projects(processed_df)
            cluster_batches = [
                clustered_df[clustered_df["cluster"] == i].to_dict(orient="records")
                for i in range(n_clusters)
            ]
            total_batches = len(cluster_batches)
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(process_batch, b, i+1, total_batches): i+1
                           for i, b in enumerate(cluster_batches)}
                for future in as_completed(futures):
                    _, batch_results, batch_projects = future.result()
                    with eval_lock:
                        all_evaluations.extend(batch_results)
                        all_data.extend(batch_projects)
                    if self.socketio:
                        with eval_lock:
                            self.socketio.emit(
                                "tango_ui",
                                {"event": "project_analysis", "component": "table",
                                 "data": sanitize_data(all_data),
                                 "response_instruction": "Evaluation in progress", "partial": True},
                                room=self.client_id)
        else:
            tokens_count = estimate_tokens(json.dumps(processed_data))
            batch_data_size = tokens_count // 40000 + 1
            self.batch_size = max(1, len(processed_data) // batch_data_size)
            total_batches = max(1, len(processed_data) // self.batch_size)
            print(f"DEBUG: Tokens={tokens_count}, Batch size={self.batch_size}, Total batches={total_batches}")

            batches = [processed_data[i:i+self.batch_size]
                       for i in range(0, len(processed_data), self.batch_size)]

            if self.socketio:
                self.socketio.emit(
                    "tango_ui",
                    {"event": "linear_progress",
                     "data": {"id": "project", "completed": 0, "total": len(processed_data)}},
                    room=self.client_id)

            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(process_batch, b, i+1, total_batches): i+1
                           for i, b in enumerate(batches)}
                for future in as_completed(futures):
                    _, batch_results, batch_projects = future.result()
                    with eval_lock:
                        all_evaluations.extend(batch_results)
                        all_data.extend(batch_projects)
                    if self.socketio:
                        self.socketio.emit(
                            "tango_ui",
                            {"event": "linear_progress",
                             "data": {"id": "project", "completed": len(all_evaluations),
                                      "total": len(processed_data)}},
                            room=self.client_id)
                        with eval_lock:
                            self.socketio.emit(
                                "tango_ui",
                                {"event": "project_analysis", "component": "table",
                                 "data": sanitize_data(all_data),
                                 "response_instruction": "Evaluation in progress", "partial": True},
                                room=self.client_id)

        if self.socketio:
            self.socketio.emit(
                "tango_ui",
                {"event": "linear_progress", "data": {"id": "project", "completed": 0, "total": 0}},
                room=self.client_id)

        self.ongoing_evaluation = all_evaluations
        formatted_strings = format_project_data_all_components(data=self.eval_response, verbose=True)
        self.eval_response = formatted_strings

        with open("processed_project_data_str.txt", "w") as f:
            f.write(formatted_strings)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def view_projects(
    tenantID, userID,
    project_id=None, portfolio_ids=None, schedule_status=None,
    last_user_message=None, socketio=None, client_id=None,
    llm=None, base_agent=None, sessionID=None, **kwargs,
):
    if not last_user_message:
        raise ValueError("last_user_message is required")

    socketio.emit("agent_switch", {"agent": "analyst"}, room=client_id)

    filters = {}
    if project_id:
        filters["project_id"] = project_id
    if portfolio_ids:
        filters["portfolio_id"] = portfolio_ids
    if schedule_status:
        filters["schedule_status"] = schedule_status

    agent = ProjectAgent(
        tenant_id=tenantID, user_id=userID, socketio=socketio,
        llm=llm, client_id=client_id, base_agent=base_agent, sessionID=sessionID)

    answer = ""
    for response in agent.process_query(query=last_user_message, filters=filters if filters else None):
        answer += response
        yield response

    TangoDao.insertTangoState(
        tenant_id=tenantID, user_id=userID,
        key="project_analyst", value=f"Agent Response: {answer}",
        session_id=sessionID)


RETURN_DESCRIPTION = """
Deep analysis of projects, providing detailed per-project insights and batch-level trends based on the user query.
"""

VIEW_PROJECTS = AgentFunction(
    name="view_projects",
    description="Project Analyst.",
    args=PROJECT_ARGS,
    return_description=RETURN_DESCRIPTION,
    function=view_projects,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name,
)
