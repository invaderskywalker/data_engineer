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
from src.trmeric_database.dao import ProjectsDao, TangoDao, TenantDao, AuthDao, RoadmapDao

from sklearn.cluster import KMeans
from sklearn.preprocessing import OneHotEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import datetime
from datetime import  date
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import tiktoken
from src.trmeric_services.agents.functions.roadmap_analyst.common import clean_raw_data

from src.trmeric_services.tango.functions.integrations.internal.resource import (
    get_capacity_data,
)

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()  # Convert date to string (e.g., '2025-06-07')
        return super().default(obj)


def sanitize_data(data):
    """Sanitize data, handling NaT, NaN, and nested structures gracefully."""
    for item in data:
        for key, value in item.items():
            if isinstance(value, (list, tuple)):
                item[key] = [sanitize_item(v) if isinstance(v, dict) else sanitize_scalar(v) for v in value]
            elif isinstance(value, dict):
                item[key] = sanitize_item(value)
            else:
                item[key] = sanitize_scalar(value)
    return data


def sanitize_item(item):
    """Helper to sanitize a single dictionary."""
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = sanitize_scalar(v)
    return item


def sanitize_scalar(value):
    """Handle NaN, NaT, arrays, and special cases."""
    if isinstance(value, (pd.Series, np.ndarray)):
        return [sanitize_scalar(v) for v in value]
    elif isinstance(value, (list, tuple)):
        return [sanitize_scalar(v) for v in value]
    elif pd.isna(value):
        return None
    elif isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    return value


def calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant):
    """Computes available roles by subtracting consumed roles from master count."""
    master_data_dict = {role["role"]: role["total_count"] for role in all_roles_count_master_data}
    allocated_roles_dict = {role["role"]: role["allocated_count"] for role in all_roles_consumed_for_tenant}
    all_roles = set(master_data_dict.keys()).union(set(allocated_roles_dict.keys()))
    available_roles = {}
    for role in all_roles:
        total_count = master_data_dict.get(role, 0)
        allocated_count = allocated_roles_dict.get(role, 0)
        available_roles[role] = max(total_count - allocated_count, 0)
    return available_roles


def estimate_tokens(text, model="gpt-4o") -> int:
    """Estimate token count using OpenAI's tokenizer."""
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))



ROADMAP_SCHEMA = {
    "thought": "roadmap type, roadmap category  and solution_insights use all of these if user's query wants any of them",
    "fields": {
        "roadmap_id": "integer (unique roadmap identifier)",
        "roadmap_title": "string (roadmap name)",
        "roadmap_description": "string (detailed description of the roadmap)",
        "priority": "string (High, Medium, Low, or Unknown)",
        "roadmap_priority": "integer (overall priority across all roadmaps, lower number = higher priority, nullable)",
        "budget": "float (budget in dollars)",
        "start_date": "date (start date of roadmap)",
        "end_date": "date (end date of roadmap)",
        "category": "string (roadmap category)",
        "roadmap_type": "string (roadmap/demand type)",
        "org_strategy_alignment": "string (description of alignment with org strategy)",
        "constraint_count": "integer (number of constraints)",
        "constraint_names": "list of strings (names of constraints)",
        "constraint_types": "list of strings (types of constraints: Cost, Resource, Risk, Other)",
        "portfolio_count": "integer (number of associated portfolios)",
        "roadmap_priority_in_portfolio": "integer (priority of roadmap in portfolio across all roadmaps, lower number = higher priority, nullable)",
        "roadmap_portfolios": "list of dicts (portfolio details: portfolio_id, portfolio_title, portfolio_leader(s), portfolio_rank (integer, rank of roadmap within this portfolio, lower number = higher priority, nullable))",
        "team_count": "integer (number of team members)",
        "team_data": "list of dicts (team details: name, unit_size, type, labour_type, allocation, estimate_value, description, start_date, end_date, location)",
        "team_resources": "list of dicts (resource details: role, allocation, skills, experience_years, is_active, is_external)",
        "kpi_names": "list of strings (names of key performance indicators)",
        "kpi_baseline_values": "list of strings (baseline values for KPIs)",
        "roadmap_scopes": "list of strings (names of roadmap scopes)",
        "current_state": "string (current state of the roadmap: Intake, Approved, Execution, Archived, Elaboration, Prioritize, Draft)",
        "approval_history": "list of dicts (approval details: request_type, request_id, request_date, from_state, to_state, approver_id, requestor_id, approval_status, request_comments, approval_reject_comments, approval_reject_date)",
        "assigned_to_id": "integer (user ID of the person assigned to the roadmap, nullable)",
        "assignee_name": "string name, if assignee is asked always take this into consideration",
        "solution_insights": "json (additional information like solution_insights and other analysis to be used for detailed analysis or if asked)",
        "demand_queue": "it can also be triggered by these keywords demand queue/ roadmap queue/ plan queue",
        "ideas": "list of dicts (mapped ideas belonging to this roadmap, each containing idea_id, title, description, category, budget, dates, and current_state)",
        "roadmap_dependencies": "list of dicts (dependencies): 'depends_on' (this roadmap depends on another, i.e. blockers) and 'requried_by' (other roadmaps depend on this one, i.e. successors), each containing dependency type, reason, and related roadmap details.",
        "business_members": "list of business sponsors, busienss members anything it can be called with (name,email, role & business unit) info.",
        "capex_purchase_recquistion_planned": "float value",
        "opex_purchase_recquistion_planned": "float value",
        "capex_purchase_order_planned": "float value",
        "opex_purchase_order_planned": "float value",
        "capex_budget": "float value",
        "opex_budget": "float value",
        "capex_actual": "float",
        "opex_actual": "float",
    }
}


class RoadmapAgent:
    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        socketio=None,
        llm=None,
        client_id=None,
        base_agent=None,
        sessionID=None,
    ):
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
        print("debug -- check_track_conformation_state --- ")
        res = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=self.sessionID, user_id=self.user_id, key="analysis_confirmed")
        val = False
        if len(res) > 0:
            val = res[0]["value"] == "True"
        self.analysis_confirmed = val
        print("debug -- check_track_conformation_state --- ", val, res)

    def add_track_conformation_state(self, state):
        print("debug add_track_conformation_state ", state)
        TangoDao.insertTangoState(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            key="analysis_confirmed",
            value=state,
            session_id=self.sessionID,
        )
        self.check_track_conformation_state()

    def _build_user_context(self, base_agent):
        if not base_agent:
            return ""
        return f"{base_agent.context_string}\n{base_agent.org_info_string}\n{base_agent.user_info_string}"


    def plan_analysis_prompt(self, query: str) -> Dict:
        if not self.llm:
            raise ValueError("LLM instance is required for planning analysis")

        TangoDao.insertTangoState(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            key="roadmap_analyst",
            value=f"User Question: {query}",
            session_id=self.sessionID,
        )

        schema_str = json.dumps(ROADMAP_SCHEMA, indent=2)
        conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAllValue(session_id=self.sessionID, user_id=self.user_id, key="roadmap_analyst")[::-1]
        current_date = datetime.datetime.now().date().isoformat()
        system_prompt = f"""
            Ongoing Conversation:
            <ongoing_conversation>
            {conv}
            <ongoing_conversation>

            Schema:
            {schema_str}

            User context:
            {self.user_context}

            User query: "{query}"

            Interpret intent and provide a JSON analysis plan with two step types:
            - type: "filter"
                - field: schema field to filter on (e.g., "roadmap_id", "portfolio_ids", "current_state", "approval_status", "approver_name", "requestor_name", "roadmap_type", "assigned_to_id", "assignee_name", "solution_insights","business_members", "all")
                - operation: "equals", "contains", "in", "in_range"
                - value: value to filter by
                - fields: array of schema fields to include in output (always include "roadmap_title", "roadmap_description")

            Rules:
            - Default fields: Always include ["roadmap_title", "roadmap_description"] in "filter" steps.
            - Roadmap Type Queries:
                - If the query contains phrases like "roadmap types", "what are my roadmap types", or "list roadmap types":
                    - Add a filter step to include all roadmaps with roadmap_type:
                        ```json
                        {{
                            "type": "filter",
                            "field": "all",
                            "operation": "contains",
                            "value": "",
                            "fields": ["roadmap_id", "roadmap_title", "roadmap_description", "roadmap_type"]
                        }}
                        ```
            - Demand Profiling Queries:
                - If the query contains phrases like "demand profiling", "profile my demands", "all my demands", or "analyze all demands":
                    - Add a filter step to include all roadmaps:
                        ```json
                        {{
                            "type": "filter",
                            "field": "all",
                            "operation": "contains",
                            "value": "",
                            "fields": ["roadmap_id", "roadmap_title", "roadmap_description", "category", "current_state", "budget", "start_date", "end_date", "priority", "constraint_count", "portfolio_count", "team_count", "kpi_names", "roadmap_scopes", "roadmap_type", "assigned_to_id", "solution_insights"]
                        }}
                        ```
            - ID-Based Filtering:
                - For portfolio queries (e.g., "Supply Chain"), use "portfolio_ids" with IDs from user_context.
                - For project queries, use "roadmap_id" with roadmap IDs from user_context.
                - For roadmap title queries, use "roadmap_id" with inferred IDs.
                - For assigned user queries (e.g., "roadmaps assigned to user 123"), use "assigned_to_id" with user IDs:
                    ```json
                    {{
                        "type": "filter",
                        "field": "assigned_to_id",
                        "operation": "in",
                        "value": [123],
                        "fields": ["roadmap_title", "roadmap_description", "assigned_to_id"]
                    }}
                    ```
            - State-Based Filtering:
                - For state queries (e.g., "approved roadmaps"), use "current_state" with valid states: 
                ["Intake", "Approved", "Execution", "Archived", "Elaboration", "Prioritize", "Hold", "Rejected","Solutioning", "Draft", "Cancelled"].
            - Type-Based Filtering:
                - If the query specifies a roadmap type (e.g., "roadmaps with type 'Program'"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "roadmap_type",
                        "operation": "in",
                        "value": ["Program"],
                        "fields": ["roadmap_title", "roadmap_description", "roadmap_type"]
                    }}
                    ```
            - Approval-Based Filtering:
                - For approval status queries (e.g., "pending approvals"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "approval_status",
                        "operation": "in",
                        "value": ["Pending"],
                        "fields": ["roadmap_title", "roadmap_description", "approval_history"]
                    }}
                    ```
                - For approver or requestor queries, filter by "approver_name" or "requestor_name" as specified.
            - Assignee-Based Filtering:
                - For assignee queries (e.g., "roadmaps assigned to Alice"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "assignee_name",
                        "operation": "contains",
                        "value": "Alice",
                        "fields": ["roadmap_title", "roadmap_description", "assigned_to_id"]
                    }}
                    ```
                - For assigned user ID queries (e.g., "roadmaps assigned to user 123"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "assigned_to_id",
                        "operation": "in",
                        "value": [123],
                        "fields": ["roadmap_title", "roadmap_description", "assigned_to_id"]
                    }}
                    ```

            - Demand Queue Filtering:
                - If the user query mentions "demand queue", "roadmap queue", or "plan queue":
                    - Treat it as filtering by the release cycle field "demand_queue".
                    - Example:
                        ```json
                        {{
                            "type": "filter",
                            "field": "demand_queue",
                            "operation": "equals",
                            "value": "<queue_name>",
                            "fields": ["roadmap_title", "roadmap_description", "demand_queue"]
                        }}
                        ```
            - Demand Dependencies Filtering:
                - If the user query mentions "demand dependencies", "roadmap dependencies":
                    - Treat it as filtering by the field "roadmap_dependencies" i.e. list of all the roadmaps dependent.
                    - Example:
                        ```json
                        {{
                            "type": "filter",
                            "field": "roadmap_dependencies",
                            "operation": "equals",
                            "value": ["Roadmap1", "Roadmap2"],
                            "fields": ["roadmap_title", "roadmap_description", "roadmap_dependencies"]
                        }}
                        ```
            - Demand Business Members/Sponsors Filtering:
                - If the user query mentions "demand business members", "roadmap business sponsors":
                    - Treat it as filtering by the field "business_members" i.e. list of all the members/sponsors in roadmap.
                    - Example:
                        ```json
                        {{
                            "type": "filter",
                            "field": "business_members",
                            "operation": "equals",
                            "value": <business members details>,
                            "fields": ["roadmap_title", "roadmap_portfolios", "business_members"]
                        }}
                        ```

            - Additional Info Filtering:
                - For additional info queries (e.g., "roadmaps with 'optimization' in additional info"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "solution_insights",
                        "operation": "contains",
                        "value": "optimization",
                        "fields": ["roadmap_title", "roadmap_description", "solution_insights"]
                    }}
                    ```
            - Category-Based Filtering:
                - If the query specifies a category tag (e.g., "roadmaps with category 'Innovation'"), add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "category",
                        "operation": "contains",
                        "value": "Innovation",
                        "fields": ["roadmap_title", "roadmap_description", "category"]
                    }}
                    ```
            - If query mentions a roadmap title (e.g., "Automation Roadmap"):
                - Extract its ID from user_context or infer from roadmap_title (case-insensitive, partial match).
                - Add: "type": "filter", "field": "roadmap_id", "operation": "in", "value": [roadmap_id], "fields": ["roadmap_title", "roadmap_description"]
            - Avoid Name-Based Filtering for Portfolios/Projects:
                - Use "portfolio_ids" or "roadmap_id" unless explicitly requested to search names.
            - Exploratory Queries:
                - Use "all" filter with empty value for broad queries unless demand profiling or roadmap type query is detected:
                    ```json
                    {{
                        "type": "filter",
                        "field": "all",
                        "operation": "contains",
                        "value": "",
                        "fields": ["roadmap_title", "roadmap_description", "category", "roadmap_type", "assigned_to_id", "solution_insights"]
                    }}
                    ```
            - Approval Trends Analysis:
                - For queries like "approval trends" or "frequently rejected roadmaps"
            - If query mentions a roadmap state (e.g., "approved roadmaps", "roadmaps in execution"):
                - Match the state in the query (case-insensitive, partial matches) to all the possbile demand states which can be ["Intake", "Approved", "Execution", "Archived", "Elaboration", "Prioritize", "Hold", "Rejected","Solutioning", "Draft", "Cancelled"].
                - Add a filter step:
                    ```json
                    {{
                        "type": "filter",
                        "field": "current_state",
                        "operation": "in",
                        "value": [matched_state],
                        "fields": ["roadmap_title", "roadmap_description", "current_state"]
                    }}
                    ```
                - Example: For query "show approved roadmaps", add:
                    ```json
                    {{
                        "type": "filter",
                        "field": "current_state",
                        "operation": "in",
                        "value": ["Approved"],
                        "fields": ["roadmap_title", "roadmap_description", "current_state"]
                    }}
                    ```
                - If multiple states are mentioned (e.g., "approved or execution roadmaps"), include all matched states in the "value" list.
                - If no valid state is matched, set "clarification_needed": true and "clarification_message": "Could not identify roadmap state. Please specify a valid state (e.g., Intake, Approved, Execution, Archived, Elaboration, Prioritize)."
            - Idea-Based Queries:
                - If the user asks anything related to ideas such as:
                    "ideas under roadmap", "roadmap ideas",
                    "show ideas for each roadmap", "list roadmaps with their ideas",
                    "attached ideas", "connect ideas", "view ideas in roadmap"
                Then:
                    - Include "ideas" in the filter fields.
                    - Never use solution_insights for idea-related queries.
                    - Use:
                        {{
                            "type": "filter",
                            "field": "all",
                            "operation": "contains",
                            "value": "",
                            "fields": ["roadmap_title", "roadmap_description", "roadmap_portfolios", "ideas"]
                        }}

            - Idea Filtering Rules:
                - If the query contains idea-specific attributes:
                    - "idea title" → use field "ideas.title"
                    - "idea category" → use field "ideas.category"
                    - "idea state" or "approved ideas" → use field "ideas.current_state"

                Example:
                    "Show roadmaps with innovation ideas"
                    ->
                    {{
                        "type": "filter",
                        "field": "ideas.category",
                        "operation": "contains",
                        "value": "Innovation",
                        "fields": ["roadmap_title", "roadmap_description", "ideas"]
                    }}

            - Avoid Name-Based Portfolio Filtering:
                - Do NOT filter by portfolio name unless explicitly requested.
            - Avoid Name-Based Project Filtering:
                - Do NOT filter by project name unless explicitly requested.
            - General Filtering (e.g., "show roadmaps with 'Automation'"):
                - "filter" with "field": "all", "operation": "contains", "fields" defaults to ["roadmap_title", "roadmap_description", "category", "roadmap_type", "assigned_to_id", "solution_insights"]
            - Business impact (e.g., "revenue impact"):
                - "filter" with "field": "kpi_names", "operation": "contains", add "kpi_names", "kpi_baseline_values", then "analysis" with "method": "impact"
            - Budget (e.g., "invest X dollars"):
                - "filter" with "field": "budget", "operation": "less_than", add "budget", then "analysis" with "method": "impact"
            - Overlaps (e.g., "scope overlaps"):
                - "filter" with "field": "roadmap_scopes", "operation": "contains", "value": "", add "roadmap_scopes", then "analysis" with "method": "overlaps"
            - Date Filtering (e.g., "starting in Q3 2025"):
                - "filter" with "field": "start_date", "operation": "in_range", convert quarter:
                    - Q1: Jan 1 - Mar 31, Q2: Apr 1 - Jun 30, Q3: Jul 1 - Sep 30, Q4: Oct 1 - Dec 31
                    - Example: "steps": [{{"type": "filter", "field": "start_date", "operation": "in_range", "value": {{"lower": "2025-07-01", "upper": "2025-09-30"}}, "fields": ["roadmap_title", "roadmap_description", "start_date"]}}]
            - Business member(s) (e.g. , "list all the business members/sponsors):
                - "filter" with "field": "business_members", "operation": "equals".
            - Multi-field (e.g., "category and budget"):
                - Multiple "filter" steps, include all mentioned fields
            - "all" searches:
                - "field": "all" applies to searchable fields: ["roadmap_title", "roadmap_description", "category", "org_strategy_alignment", "roadmap_type", "assignee_name", "solution_insights"]
            - Partial Matching:
                - "contains" for strings (case-insensitive)
            - Follow-Ups:
                - "my roadmaps" uses last_results IDs via "roadmap_id" filter, keep prior "fields"
            - Analysis Detection:
                - Add "analysis" step for queries needing evaluation (e.g., "overlaps", "impact", "ranking", "category_summary")
            - Team Resource Analysis (e.g., "roadmaps with sufficient team resources"):
                - Set "check_team_resources": true, "filter" with "field": "team_data", "operation": "contains", add "team_data", "team_resources", then "analysis" with "method": "resource_allocation"
            - Clustering Detection:
                - Set "use_clustering": true for queries involving "overlaps", "similarities", or "group by scope"; false otherwise
            - Clarification:
                - Set "clarification_needed": true if query is ambiguous (e.g., no clear roadmap/portfolio/project/state/type/assignee/additional_info mentioned and no general intent)

            Important: Today's date: {current_date}. Respect this date.
            example--
                queries like -- From ideation to execution - let's see where your requests are
                chekc for all current_state and for approval history because that approval history tracks the progress


            Output Strict JSON:
            ```json
            {{
                "steps": [],
                "clarification_needed": false,
                "clarification_message": null,
                "reason_behind_this_analysis": "",
                "use_clustering": false,
                "check_team_resources": false
            }}
            ```
            Current date: {current_date}.
        """

        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=f"Generate JSON analysis plan for: '{query}'",
        )
        response = self.llm.run(
            chat_completion,
            ModelOptions(model="gpt-4.1", max_tokens=2000, temperature=0.1),
            "agent::analyst::roadmap::process",
            logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id},
        )

        TangoDao.insertTangoState(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            key="roadmap_analyst",
            value=f"Agent Analysis: {response}",
            session_id=self.sessionID,
        )

        try:
            analysis_plan = extract_json_after_llm(response)
            return analysis_plan
        except json.JSONDecodeError:
            raise ValueError(f"LLM response is not valid JSON: {response}")
        

    def fetch_roadmaps(self, filters: Dict = None) -> List[Dict]:
        filter_string = ""
        if filters:
            conditions = []
            values = self.get_eligible_roadmap_ids()
            conditions.append(f"rr.id IN {values}")
            for condition in filters.get("llm_filters", []):
                field = condition["field"]
                operation = condition["operation"]
                value = condition["value"]
                if field == "all":
                    searchable_fields = [
                        "roadmap_title", "roadmap_description", "category",
                        "org_strategy_alignment", "constraint_names", "scope_names",
                        "roadmap_portfolios", "approval_history", "assignee_name", "roadmap_dependencies","business_members",
                    ]
                    for f in searchable_fields:
                        if f in ["roadmap_title", "roadmap_description", "category", "org_strategy_alignment"]:
                            conditions.append(f"LOWER(rr.{f.split('_')[1] if f.startswith('roadmap_') else f}) LIKE LOWER('%{value}%')")
                        # elif f == "assignee_name":
                        #     conditions.append(f"LOWER(au_assignee.first_name || ' ' || au_assignee.last_name) LIKE LOWER('%{value}%')")
                if field == "roadmap_id" and operation == "in":
                    value = [str(v) for v in value]
                    conditions.append(f"rr.id IN ({', '.join(value)})")
                if field == "portfolio_ids" and operation == "in":
                    value = [str(v) for v in (value if isinstance(value, list) else [value])]
                    conditions.append(f"rp.portfolio_id IN ({', '.join(value)})")
                if field == "current_state" and operation == "in":
                    valid_states = {
                        "Intake": 0, "Approved": 1, "Execution": 2, "Archived": 3,
                        "Elaboration": 4, "Prioritize": 5, "Hold": 6, "Rejected": 7, "Draft": 200
                    }
                    state_values = [str(valid_states.get(v.capitalize(), -1)) for v in (value if isinstance(value, list) else [value]) if v.capitalize() in valid_states]
                    if state_values:
                        conditions.append(f"rr.current_state IN ({', '.join(state_values)})")
                    else:
                        print(f"DEBUG: Invalid state values in LLM filter: {value}")
                if field == "approval_status" and operation == "in":
                    valid_statuses = {"Pending": 1, "Approved": 2, "Rejected": 3}
                    status_values = [str(valid_statuses.get(v.capitalize(), -1)) for v in (value if isinstance(value, list) else [value]) if v.capitalize() in valid_statuses]
                    if status_values:
                        conditions.append(f"aar.approval_status IN ({', '.join(status_values)})")
                if field == "approver_id" and operation == "in":
                    value = [str(v) for v in (value if isinstance(value, list) else [value])]
                    conditions.append(f"aar.approver_id IN ({', '.join(value)})")
                if field == "requestor_id" and operation == "in":
                    value = [str(v) for v in (value if isinstance(value, list) else [value])]
                    conditions.append(f"aar.requestor_id IN ({', '.join(value)})")
                if field == "approver_name" and operation == "contains":
                    conditions.append(f"LOWER(au.first_name || ' ' || au.last_name) LIKE LOWER('%{value}%')")
                if field == "requestor_name" and operation == "contains":
                    conditions.append(f"LOWER(ru.first_name || ' ' || ru.last_name) LIKE LOWER('%{value}%')")
                if field == "assigned_to_id" and operation == "in":
                    value = [str(v) for v in (value if isinstance(value, list) else [value])]
                    conditions.append(f"rr.assigned_to_id IN ({', '.join(value)})")
                if field == "demand_queue" and operation in ["equals", "contains", "in"]:
                    # --- filter directly on tenant_release_cycles before GROUP BY
                    if isinstance(value, list):
                        clean_values = [str(v).lower() for v in value]
                    else:
                        clean_values = [str(value).lower()]

                    if operation == "equals":
                        conditions.append(
                            "(" + " OR ".join([f"LOWER(trc.title) = '{v}'" for v in clean_values]) + ")"
                        )
                    elif operation == "contains":
                        conditions.append(
                            "(" + " OR ".join([f"trc.title ILIKE '%{v}%'" for v in clean_values]) + ")"
                        )
                    elif operation == "in":
                        conditions.append(
                            "(" + " OR ".join([f"LOWER(trc.title) = '{v}'" for v in clean_values]) + ")"
                        )

                # if field == "assignee_name" and operation == "contains":
                #     conditions.append(f"LOWER(au_assignee.first_name || ' ' || au_assignee.last_name) LIKE LOWER('%{value}%')")
                if operation in ["greater_than", "less_than", "in_range"]:
                    if field in ["start_date", "end_date", "budget", "request_date"]:
                        table = "aar" if field == "request_date" else "rr"
                        if operation == "greater_than":
                            conditions.append(f"{table}.{field} >= '{value}'" if field in ["start_date", "end_date", "request_date"] else f"{table}.{field} >= {value}")
                        elif operation == "less_than":
                            conditions.append(f"{table}.{field} <= '{value}'" if field in ["start_date", "end_date", "request_date"] else f"{table}.{field} <= {value}")
                        elif operation == "in_range" and isinstance(value, dict):
                            if "lower" in value and "upper" in value:
                                if value.get("lower") and value.get("upper"):
                                    conditions.append(f"{table}.{field} BETWEEN '{value['lower']}' AND '{value['upper']}'")
                            elif "lower" in value:
                                conditions.append(f"{table}.{field} >= '{value['lower']}'")
                            elif "upper" in value:
                                conditions.append(f"{table}.{field} <= '{value['upper']}'")
            
            if conditions:
                filter_string = " AND (" + " AND ".join(conditions) + ")"

        query = self._get_roadmap_query(filter_string)
        # print("DEBUG ROADMAP QUERY:::", query)
        raw_response_ = db_instance.retrieveSQLQueryOld(query)

        raw_response = clean_raw_data(raw_response_)

        with open("raw_roadmap_data.json", "w") as f:
            json.dump(raw_response, f, indent=2, cls=DateEncoder)
            
        if isinstance(raw_response, str):
            raw_response = json.loads(raw_response)
        if not isinstance(raw_response, list):
            raw_response = [raw_response] if isinstance(raw_response, dict) else []
        self.last_results = [r["roadmap_id"] for r in raw_response]
        return raw_response

    
    def get_eligible_roadmap_ids(self):
        data = RoadmapDao.fetchEligibleRoadmapList(tenant_id=self.tenant_id, user_id = self.user_id)
        res = []
        for d in data:
            res.append(d["roadmap_id"])
        # val = tuple(res) if len(res) != 1 else (res[0])
        # val = tuple(res) if res else ()  # Ensure tuple, even for single item or empty list
        val = f"({', '.join(map(str, res))})"
        print("debug... ", val)
        return val
    

    def _get_roadmap_query(self, filter_string: str = "") -> str:
        base_query = f"""
            SELECT 
                rr.id as roadmap_id, 
                rr.title as roadmap_title, 
                rr.description as roadmap_description,
                rr.objectives as roadmap_objectives, 
                rr.start_date as roadmap_start_date,
                rr.end_date as roadmap_end_date,
                rr.budget as roadmap_budget,
                rr.category as roadmap_category,
                rr.business_case as business_case_data,
                rr.capex_budget AS capex_budget,
                rr.opex_budget AS opex_budget,
                rr.capex_pr_planned AS capex_purchase_recquistion_planned,
                rr.capex_po_planned AS capex_purchase_order_planned,
                rr.opex_pr_planned AS opex_purchase_recquistion_planned,
                rr.opex_po_planned AS opex_purchase_order_planned,
                rr.capex_actuals AS capex_actual,
                rr.opex_actuals AS opex_actual,
                CASE 
                    WHEN rr.type = 1 THEN 'Program'
                    WHEN rr.type = 2 THEN 'Project'
                    WHEN rr.type = 3 THEN 'Enhancement'
                    WHEN rr.type = 4 THEN 'New Development'
                    WHEN rr.type = 5 THEN 'Enhancements or Upgrade'
                    WHEN rr.type = 6 THEN 'Consume a Service'
                    WHEN rr.type = 7 THEN 'Support a Pursuit'
                    WHEN rr.type = 8 THEN 'Acquisition'
                    WHEN rr.type = 9 THEN 'Global Product Adoption'
                    WHEN rr.type = 10 THEN 'Innovation Request for NITRO'
                    WHEN rr.type = 11 THEN 'Regional Product Adoption'
                    WHEN rr.type = 12 THEN 'Client Deployment'
                    ELSE 'Unknown'
                END AS roadmap_type,
                rr.org_strategy_align as roadmap_org_strategy_alignment,
                rr.approved_state,
                rr.rank as roadmap_priority,
                CASE 
                    WHEN rr.current_state = 0 THEN 'Intake'
                    WHEN rr.current_state = 1 THEN 'Approved'
                    WHEN rr.current_state = 2 THEN 'Execution'
                    WHEN rr.current_state = 3 THEN 'Archived'
                    WHEN rr.current_state = 4 THEN 'Elaboration'
                    WHEN rr.current_state = 5 THEN 'Solutioning'
                    WHEN rr.current_state = 6 THEN 'Prioritize'
                    WHEN rr.current_state = 99 THEN 'Hold'
                    WHEN rr.current_state = 100 THEN 'Rejected'
                    WHEN rr.current_state = 999 THEN 'Cancelled'
                    WHEN rr.current_state = 200 THEN 'Draft'
                    ELSE 'Unknown'
                END AS current_state,
                CASE 
                    WHEN COUNT(atd.id) > 0 THEN true
                    ELSE false
                END AS is_test_data,
                uu.first_name as owner_first_name,
                uu.last_name as owner_last_name,
                rr.assigned_to_id as assigned_to_id,
                au_assignee.first_name as assignee_first_name,
                rr.tango_analysis -> 'solution_insights' as solution_insights,

                -- CONSTRAINTS
                json_agg(
                    DISTINCT json_build_object(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        CASE
                            WHEN rrc.type = 1 THEN 'Cost'
                            WHEN rrc.type = 2 THEN 'Risk'
                            WHEN rrc.type = 3 THEN 'Resource'
                            ELSE 'Other'
                        END
                    )::text
                ) FILTER (WHERE rrc.name IS NOT NULL) as roadmap_constraints,

                -- PORTFOLIOS
                json_agg(
                    DISTINCT json_build_object(
                        'portfolio_id', pp.id,
                        'portfolio_title', pp.title,
                        'portfolio_leader_first_name', pp.first_name,
                        'portfolio_leader_last_name', pp.last_name,
                        'portfolio_rank', rp.rank
                    )::text
                ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios,

                -- DEMAND QUEUE
                json_agg(
                    DISTINCT json_build_object(
                        'release_cycle_id', trc.id,
                        'release_cycle_title', trc.title,
                        'release_cycle_start_date', trc.start_date,
                        'release_cycle_end_date', trc.end_date
                    )::text
                ) FILTER (WHERE trc.id IS NOT NULL) AS demand_queue,

                -- KPIs
                json_agg(
                    DISTINCT json_build_object(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::text
                ) FILTER (WHERE rrkpi.name IS NOT NULL) as roadmap_key_results,

                -- TEAM
                json_agg(
                    DISTINCT json_build_object(
                        'team_name', rrt.name,
                        'team_unit_size', rrt.unit,
                        'unit_type', 
                        CASE
                            WHEN rrt.type = 1 THEN 'days'
                            WHEN rrt.type = 2 THEN 'months'
                            WHEN rrt.type = 3 THEN 'weeks'
                            WHEN rrt.type = 4 THEN 'hours'
                            ELSE 'Unknown'
                        END,
                        'labour_type', 
                        CASE
                            WHEN rrt.labour_type = 1 THEN 'labour'
                            WHEN rrt.labour_type = 2 THEN 'non labour'
                            ELSE 'Unknown'
                        END,
                        'description', rrt.description,
                        'start_date', rrt.start_date,
                        'end_date', rrt.end_date,
                        'location', rrt.location,
                        'allocation', rrt.allocation,
                        'total_estimated_hours',
                        CASE
                            WHEN rrt.type = 1 THEN rrt.unit * 8
                            WHEN rrt.type = 2 THEN rrt.unit * 160
                            WHEN rrt.type = 3 THEN rrt.unit * 40
                            WHEN rrt.type = 4 THEN rrt.unit
                            ELSE 0
                        END,
                        'total_estimated_cost',
                        CASE
                            WHEN rrt.labour_type = 1 THEN 
                                COALESCE(
                                    NULLIF(regexp_replace(rrt.estimate_value, '[^0-9\.]', '', 'g'), '')::NUMERIC,
                                    0
                                ) * 
                                CASE
                                    WHEN rrt.type = 1 THEN rrt.unit * 8
                                    WHEN rrt.type = 2 THEN rrt.unit * 160
                                    WHEN rrt.type = 3 THEN rrt.unit * 40
                                    WHEN rrt.type = 4 THEN rrt.unit
                                    ELSE 0
                                END
                            WHEN rrt.labour_type = 2 THEN COALESCE(
                                NULLIF(regexp_replace(rrt.estimate_value, '[^0-9\.]', '', 'g'), '')::NUMERIC,
                                0
                            )
                            ELSE 0
                        END
                    )::text
                ) FILTER (WHERE rrt.name IS NOT NULL) AS team_data,

                -- SCOPES
                json_agg(DISTINCT rrs.name)
                FILTER (WHERE rrs.name IS NOT NULL) as roadmap_scopes,

                -- APPROVAL HISTORY
                COALESCE(
                    json_agg(
                        DISTINCT json_build_object(
                            'request_type', CASE
                                WHEN aar.request_type = 1 THEN 'Roadmap'
                                WHEN aar.request_type = 2 THEN 'Project'
                                ELSE 'Unknown'
                            END,
                            'request_id', aar.request_id,
                            'request_date', aar.request_date,
                            'from_state', CASE
                                WHEN aar.from_state = 0 THEN 'Intake'
                                WHEN aar.from_state = 1 THEN 'Approved'
                                WHEN aar.from_state = 2 THEN 'Execution'
                                WHEN aar.from_state = 3 THEN 'Archived'
                                WHEN aar.from_state = 4 THEN 'Elaboration'
                                WHEN aar.from_state = 5 THEN 'Solutioning'
                                WHEN aar.from_state = 6 THEN 'Prioritize'
                                WHEN aar.from_state = 99 THEN 'Hold'
                                WHEN aar.from_state = 100 THEN 'Rejected'
                                WHEN aar.from_state = 999 THEN 'Cancelled'
                                WHEN aar.from_state = 200 THEN 'Draft'
                                ELSE 'Unknown'
                            END,
                            'to_state', CASE
                                WHEN aar.to_state = 0 THEN 'Intake'
                                WHEN aar.to_state = 1 THEN 'Approved'
                                WHEN aar.to_state = 2 THEN 'Execution'
                                WHEN aar.to_state = 3 THEN 'Archived'
                                WHEN aar.to_state = 4 THEN 'Elaboration'
                                WHEN aar.to_state = 5 THEN 'Solutioning'
                                WHEN aar.to_state = 6 THEN 'Prioritize'
                                WHEN aar.to_state = 99 THEN 'Hold'
                                WHEN aar.to_state = 100 THEN 'Rejected'
                                WHEN aar.to_state = 999 THEN 'Cancelled'
                                WHEN aar.to_state = 200 THEN 'Draft'
                                ELSE 'Unknown'
                            END,
                            'approver_id', aar.approver_id,
                            'requestor_id', aar.requestor_id,
                            'approver_first_name', au.first_name,
                            'approver_last_name', au.last_name,
                            'requestor_first_name', ru.first_name,
                            'requestor_last_name', ru.last_name,
                            'approval_status', CASE
                                WHEN aar.approval_status = 1 THEN 'Pending'
                                WHEN aar.approval_status = 2 THEN 'Approved'
                                WHEN aar.approval_status = 3 THEN 'Rejected'
                                ELSE 'Unknown'
                            END,
                            'request_comments', aar.request_comments,
                            'approval_reject_comments', aar.approval_reject_comments,
                            'approval_reject_date', aar.approval_reject_date
                        )::text
                    ) FILTER (WHERE aar.id IS NOT NULL),
                    '[]'
                ) as approval_history,
                
                -------------------------------------------------
                -- NEW: IDEA MAPPING BLOCK
                -------------------------------------------------
                json_agg(
                    DISTINCT json_build_object(
                        'idea_id', ic.id,
                        'title', ic.title,
                        'short_description', ic.short_description,
                        'elaborate_description', ic.elaborate_description,
                        'category', ic.category,
                        'org_strategy_align', ic.org_strategy_align,
                        'budget', ic.budget,
                        'start_date', ic.start_date,
                        'end_date', ic.end_date,
                        'current_state',
                            CASE
                                WHEN ic.current_state = 0 THEN 'Intake'
                                WHEN ic.current_state = 1 THEN 'Approved'
                                WHEN ic.current_state = 2 THEN 'Execution'
                                WHEN ic.current_state = 3 THEN 'Archived'
                                ELSE 'Unknown'
                            END
                    )::text
                ) FILTER (WHERE ic.id IS NOT NULL) AS ideas,
                
                COALESCE((
                    SELECT json_agg(
                        DISTINCT jsonb_build_object(
                            -- 'dependency_id', d.id,
                            -- 'direction',     CASE WHEN d.dependent_roadmap_id = rr.id THEN 'outgoing' ELSE 'incoming' END,
                            'relation',      CASE WHEN d.dependent_roadmap_id = rr.id THEN 'depends_on' ELSE 'required_by' END,
                            'dependency_reason',   d.description,
                            'dependency_type', CASE d.dependency_type
                                WHEN 1 THEN 'Technical'
                                WHEN 2 THEN 'Functional'
                                WHEN 3 THEN 'Resource'
                                WHEN 4 THEN 'Sequence'
                                WHEN 5 THEN 'Risk'
                                WHEN 6 THEN 'Compliance'
                                ELSE 'Unknown'
                            END,
                            'dependency_type_code', d.dependency_type,
                            -- 'related_roadmap_id',   CASE WHEN d.dependent_roadmap_id = rr.id THEN d.roadmap_id ELSE d.dependent_roadmap_id END,
                            'related_roadmap_title', r2.title
                        )
                    )
                    FROM public.roadmap_roadmap_dependency d
                    LEFT JOIN roadmap_roadmap r2 
                        ON r2.id = CASE WHEN d.dependent_roadmap_id = rr.id THEN d.roadmap_id ELSE d.dependent_roadmap_id END
                        AND r2.tenant_id = rr.tenant_id
                    WHERE d.tenant_id = rr.tenant_id
                    AND (d.dependent_roadmap_id = rr.id OR d.roadmap_id = rr.id)
                ), '[]'::json) AS roadmap_dependencies,

                COALESCE(
                    json_agg(
                        DISTINCT jsonb_build_object(
                            'first_name', pb.sponsor_first_name,
                            'last_name', pb.sponsor_last_name,
                            'email', pb.sponsor_email,
                            'role', pb.sponsor_role,
                            'business_unit', pb.bu_name
                        )
                    ) FILTER (WHERE pb.id IS NOT NULL),
                    '[]'
                ) AS business_members
                
            FROM roadmap_roadmap AS rr 
            LEFT JOIN roadmap_roadmapbusinessmember rrbm ON rrbm.roadmap_id = rr.id
            LEFT JOIN projects_portfoliobusiness pb 
                ON pb.id = rrbm.portfolio_business_id
                AND pb.tenant_id = rr.tenant_id

            LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id
            LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
            LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
            LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
            LEFT JOIN roadmap_roadmapestimate AS rrt ON rrt.roadmap_id = rr.id
            LEFT JOIN roadmap_roadmapscope AS rrs ON rr.id = rrs.roadmap_id
            LEFT JOIN users_user AS uu ON rr.created_by_id = uu.id
            LEFT JOIN authorization_approval_request AS aar ON rr.id = aar.request_id AND aar.request_type = 1
            LEFT JOIN users_user AS au ON aar.approver_id = au.id
            LEFT JOIN users_user AS ru ON aar.requestor_id = ru.id
            LEFT JOIN users_user AS au_assignee ON rr.assigned_to_id = au_assignee.id
            LEFT JOIN roadmap_roadmapreleasecycle AS rrcycle 
                ON rr.id = rrcycle.roadmap_id 
                AND rrcycle.tenant_id = rr.tenant_id
            LEFT JOIN tenant_release_cycles AS trc 
                ON rrcycle.release_cycle_id = trc.id 
                AND trc.tenant_id = rr.tenant_id
            LEFT JOIN adminapis_test_data AS atd
                ON atd.table_pk = rr.id
                AND atd.table_name = 'roadmap'
                AND atd.tenant_id = rr.tenant_id
            
            -- NEW JOINS FOR IDEA MAPPING
            LEFT JOIN roadmap_roadmapideamap AS ir 
                ON rr.id = ir.roadmap_id

            LEFT JOIN idea_concept AS ic
                ON ic.id = ir.idea_id

            WHERE rr.tenant_id = {self.tenant_id}
        """
        
        if filter_string:
            base_query += f" {filter_string}"
        base_query += " GROUP BY rr.id, uu.first_name, uu.last_name, rr.assigned_to_id, au_assignee.first_name, au_assignee.last_name;"
        return base_query


    def execute_analysis(self, raw_data: List[Dict], analysis_plan: Dict) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame(columns=["roadmap_title", "roadmap_description"])

        # print("\n\n---debug execute_analysis------roadmap bm-----", raw_data[0].get("business_members",[]))
        df = pd.DataFrame(
            [
                {
                    "roadmap_id": r["roadmap_id"],
                    "roadmap_title": r.get("roadmap_title", ""),
                    "roadmap_start_date": r.get("roadmap_start_date") or "",
                    "roadmap_description": r.get("roadmap_description", ""),
                    "is_test_data": r.get("is_test_data") or False,
                }
                for r in raw_data
            ]
        )

        required_fields = set()
        for step in analysis_plan.get("steps", []):
            if "fields" in step:
                required_fields.update(step["fields"])
            if step.get("type") == "filter" and step.get("field") not in ["all"]:
                required_fields.add(step["field"])

        field_mapping = {
            "roadmap_id": lambda r: r["roadmap_id"],
            "roadmap_title": lambda r: r.get("roadmap_title"),
            "roadmap_description": lambda r: r.get("roadmap_description"),
            "is_test_data": lambda r:r.get("is_test_data") or False,
            "budget": lambda r: float(r.get("roadmap_budget", 0) or 0),
            "start_date": lambda r: pd.to_datetime(r.get("roadmap_start_date"), errors="coerce"),
            "end_date": lambda r: pd.to_datetime(r.get("roadmap_end_date"), errors="coerce"),
            "category": lambda r: r.get("roadmap_category", ""),
            "org_strategy_alignment": lambda r: r.get("roadmap_org_strategy_alignment", ""),
            "constraint_count": lambda r: len(r.get("roadmap_constraints", []) or []),
            "roadmap_type": lambda r: r.get("roadmap_type", "Unknown"),
            "business_case_data": lambda r: r.get("business_case_data") or {},

            "capex_purchase_recquistion_planned": lambda r: float(r.get("capex_purchase_recquistion_planned")),
            "opex_purchase_recquistion_planned": lambda r: float(r.get("opex_purchase_recquistion_planned")),
            "capex_purchase_order_planned": lambda r: float(r.get("capex_purchase_order_planned")),
            "opex_purchase_order_planned": lambda r: float(r.get("opex_purchase_order_planned")),
            "capex_budget": lambda r: float(r.get("capex_budget")),
            "capex_actual": lambda r: float(r.get("capex_actual")),
            "opex_budget": lambda r: float(r.get("opex_budget")),
            "opex_actual": lambda r: float(r.get("opex_actual")),

            "constraint_names": lambda r: (
                [c["constraint_title"] for c in r.get("roadmap_constraints", []) if c]
                if r.get("roadmap_constraints") is not None else []
            ),
            "constraint_types": lambda r: (
                [c["constraint_type"] for c in r.get("roadmap_constraints", []) if c]
                if r.get("roadmap_constraints") is not None else []
            ),
            "portfolio_count": lambda r: len(r.get("roadmap_portfolios", []) or []),
            "roadmap_priority": lambda r: r.get("roadmap_priority"),
            "roadmap_priority_in_portfolio": lambda r: r.get("roadmap_priority_in_portfolio"),
            "roadmap_portfolios": lambda r: (
                [
                    {
                        "id": p["portfolio_id"],
                        "title": p["portfolio_title"],
                    }
                    for p in r.get("roadmap_portfolios", []) if p
                ]
                if r.get("roadmap_portfolios") is not None else []
            ),
            "team_count": lambda r: len(r.get("team_data", []) or []),
            "team_resources": lambda r: r.get("team_data", []),
            "team_data": lambda r: r.get("team_data", []),
            "kpi_names": lambda r: (
                [k["key_result_title"] for k in r.get("roadmap_key_results", []) if k]
                if r.get("roadmap_key_results") is not None else []
            ),
            "kpi_baseline_values": lambda r: (
                [k["baseline_value"] for k in r.get("roadmap_key_results", []) if k]
                if r.get("roadmap_key_results") is not None else []
            ),
            "roadmap_scopes": lambda r: r.get("roadmap_scopes", []),
            "current_state": lambda r: r.get("current_state", "Unknown"),
            "approval_history": lambda r: (
                [
                    {
                        "request_type": a["request_type"],
                        "request_id": a["request_id"],
                        "request_date": pd.to_datetime(a["request_date"], errors="coerce"),
                        "from_state": a["from_state"],
                        "to_state": a["to_state"],
                        "approver_id": a["approver_id"],
                        "requestor_id": a["requestor_id"],
                        "approver_name": f"{a.get('approver_first_name', '')} {a.get('approver_last_name', '')}".strip() or "Unknown",
                        "requestor_name": f"{a.get('requestor_first_name', '')} {a.get('requestor_last_name', '')}".strip() or "Unknown",
                        "approval_status": a["approval_status"],
                        "request_comments": a["request_comments"],
                        "approval_reject_comments": a["approval_reject_comments"],
                        "approval_or_reject_date_as_per_status": pd.to_datetime(a["approval_reject_date"], errors="coerce"),
                    }
                    for a in r.get("approval_history", []) if a
                ] if r.get("approval_history") is not None else []
            ),
            "assigned_to_id": lambda r: r.get("assigned_to_id"),
            "assignee_name": lambda r: f"{r.get('assignee_first_name', '')} {r.get('assignee_last_name', '')}".strip() or "Unknown",
            "solution_insights": lambda r: (r.get("solution_insights", {}) or {}),
            "demand_queue": lambda r: (r.get("demand_queue") or []),
            "ideas": lambda r: r.get("ideas", []) or [],
            "roadmap_dependencies": lambda r: (r.get("roadmap_dependencies") or []),
            "business_members": lambda r: (
                [
                    {
                        "name": b.get("first_name") + " " + b.get("last_name"),
                        "email": b.get("email"),
                        "role": b.get("role"),
                        "business_unit": b.get("business_unit"),
                    }
                    for b in r.get("business_members", []) if b
                ]
                if r.get("business_members") is not None else []
            ),
        }

        for field in required_fields:
            if field in field_mapping and field not in df.columns:
                df[field] = [field_mapping[field](r) for r in raw_data]

        for step in analysis_plan.get("steps", []):
            if step.get("type") != "filter":
                continue
            field = step.get("field", "all")
            operation = step.get("operation")
            value = step.get("value")
            temp_df = df.copy()

            if field == "all" and operation == "contains" and not value:
                df = temp_df
                
            elif field == "business_members" and operation in ["contains", "equals"]:
                search_value = str(value).lower()

                def has_business_member(members):
                    if not isinstance(members, list):
                        return False
                    for m in members:
                        if not isinstance(m, dict):
                            continue
                        if (
                            search_value in (m.get("name", "")).lower()
                            # or search_value in (m.get("email", "")).lower()
                            # or search_value in (m.get("role", "")).lower()
                            # or search_value in (m.get("business_unit", "")).lower()
                        ):
                            return True
                    return False

                df = temp_df[temp_df["business_members"].apply(has_business_member)]
    
            else:
                print(f"DEBUG: Skipping unsupported filter - field: {field}, operation: {operation}, value: {value}")

            print(f"DEBUG: After filter {field} {operation} {value}, rows = {len(df)}")

        print(f"DEBUG: Final DataFrame rows = {len(df)}, columns = {list(df.columns)}")
        print()
        print(df.head(2))
        print()
        json_required_data = df.to_dict(orient='records')

        with open("processed_roadmap_data.json", "w") as f:
            json.dump(json_required_data, f, indent=2, cls=DateEncoder)
        
        return df


    def process_query(self, query: str, filters: Optional[Dict] = None):
        analysis_plan = self.plan_analysis_prompt(query)
        print(f"DEBUG: Analysis plan = {json.dumps(analysis_plan, indent=2)}")

        llm_filters = []
        searchable_fields = [
            "roadmap_title",
            "roadmap_description",
            "category",
            "org_strategy_alignment",
            "constraint_names",
            "scope_names",
            "roadmap_portfolios",
            "demand_queue",
            "roadmap_dependencies",
            "business_members",
        ]

        for step in analysis_plan.get("steps", []):
            if step["type"] == "filter":
                field = step["field"]
                operation = step["operation"]
                value = step["value"]
                if operation == "in" and value:
                    if field == "roadmap_id":
                        llm_filters.append({"field": "roadmap_id", "operation": "in", "value": value})
                    elif field == "portfolio_ids":
                        llm_filters.append(
                            {
                                "field": "portfolio_ids",
                                "operation": "in",
                                "value": value if isinstance(value, list) else [value],
                            }
                        )
                    elif field == "current_state":
                        llm_filters.append(
                            {
                                "field": "current_state",
                                "operation": "in",
                                "value": value if isinstance(value, list) else [value],
                            }
                        )
                elif operation in ["equals", "contains"] and value:
                    if isinstance(field, list):
                        for f in field:
                            if f in searchable_fields:
                                llm_filters.append({"field": f, "operation": operation, "value": value})
                    elif field == "all":
                        for f in searchable_fields:
                            llm_filters.append({"field": f, "operation": operation, "value": value})
                    elif field in searchable_fields:
                        llm_filters.append({"field": field, "operation": operation, "value": value})
                elif operation in ["greater_than", "less_than", "in_range"]:
                    llm_filters.append({"field": field, "operation": operation, "value": value})

        print("debug 000  filters", llm_filters)
        combined_filters = {"user_filters": filters or {}, "llm_filters": llm_filters}
        # print("debug 1111  filters", combined_filters)
        raw_data = self.fetch_roadmaps(combined_filters if llm_filters or filters else None)

        print(f"DEBUG: Raw data fetched = {len(raw_data)}")

        processed_df = self.execute_analysis(raw_data, analysis_plan)
        processed_data = processed_df.to_dict(orient="records")
        processed_data = sanitize_data(processed_data)
        print(f"DEBUG: Processed data = {len(processed_data)}")

        if self.socketio:
            self.socketio.emit(
                "tango_ui",
                {
                    "event": "roadmap_analysis",
                    "component": "table",
                    "data": processed_data,
                    "response_instruction": "Filtered data",
                    "partial": False,
                },
                room=self.client_id,
            )

        if not analysis_plan.get("steps", []):
            yield "## Here’s Everything\nLoaded all your roadmaps, tons of details! What do you want to analyze next?"
            return

        if analysis_plan.get("clarification_needed", False):
            msg = analysis_plan.get("clarification_message", "Please clarify your query.")
            yield msg
            return

        all_evaluations = []
        all_data = []
        eval_lock = threading.Lock()
        max_threads = min(4, len(processed_data) // self.batch_size + 1)

        def process_batch(batch, batch_num, total_batches):
            print(f"DEBUG: Evaluating batch {batch_num}/{total_batches}, size={len(batch)} in thread {threading.current_thread().name}")
            # batch_evals = self.evaluate_roadmap(batch, query, analysis_plan)
            self.eval_response.extend(batch)
            batch_results = []
            roadmaps = []
            # for roadmap, eval_result in zip(batch, batch_evals):
            #     roadmap.update(eval_result)
            #     roadmaps.append(roadmap)
            #     batch_results.append(eval_result)
            return batch_num, batch, roadmaps

        tokens_count = estimate_tokens(json.dumps(processed_data))
        batch_data_size = tokens_count // 40000 + 1
        self.batch_size = max(1, len(processed_data) // batch_data_size)
        total_batches = max(1, len(processed_data) // self.batch_size)

        # needs_analysis = any(step["type"] == "analysis" for step in analysis_plan["steps"])
        # if not needs_analysis and len(processed_data) > 0:
        #     yield f"#### Ready to Analyze roadmaps\nGot {len(processed_data)} roadmaps.\n\n"
        #     return

        # yield f"\nAnalyzed {len(processed_data)} roadmaps in {total_batches} batches.\n"
        print(f"DEBUG: Tokens={tokens_count}, Batch size={self.batch_size}, Total batches={total_batches}")

        batches = [processed_data[i : i + self.batch_size] for i in range(0, len(processed_data), self.batch_size)]
        if self.socketio:
            self.socketio.emit(
                "tango_ui",
                {
                    "event": "linear_progress",
                    "data": {"id": "roadmap", "completed": 0, "total": len(processed_data)},
                },
                room=self.client_id,
            )

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(process_batch, batch, i + 1, total_batches): i + 1 for i, batch in enumerate(batches)}
            completed_batches = 0
            for future in as_completed(futures):
                batch_num, batch_results, batch_raodmaps = future.result()
                completed_batches += 1
                with eval_lock:
                    all_evaluations.extend(batch_results)
                    all_data.extend(batch_raodmaps)

                if self.socketio:
                    self.socketio.emit(
                        "tango_ui",
                        {
                            "event": "linear_progress",
                            "data": {
                                "id": "roadmap",
                                "completed": len(all_evaluations),
                                "total": len(processed_data),
                            },
                        },
                        room=self.client_id,
                    )
                # yield f"#### Batch Update\nProcessed batch {batch_num}/{total_batches} ({len(all_evaluations)}/{len(processed_data)} roadmaps evaluated).\n"
                if self.socketio:
                    with eval_lock:
                        self.socketio.emit(
                            "tango_ui",
                            {
                                "event": "roadmap_analysis",
                                "component": "table",
                                "data": sanitize_data(all_data),
                                "response_instruction": "Evaluation in progress",
                                "partial": True,
                            },
                            room=self.client_id,
                        )

        # yield self._format_evaluation_results(all_evaluations, query)
        if self.socketio:
            self.socketio.emit(
                "tango_ui",
                {
                    "event": "linear_progress",
                    "data": {"id": "roadmap", "completed": 0, "total": 0},
                },
                room=self.client_id,
            )
        self.ongoing_evaluation = all_evaluations


def view_roadmaps(
    tenantID: int,
    userID: int,
    roadmap_id=None,
    portfolio_ids=None,
    priority=None,
    last_user_message=None,
    socketio=None,
    client_id=None,
    llm=None,
    base_agent=None,
    sessionID=None,
    **kwargs,
):
    if not last_user_message:
        raise ValueError("last_user_message is required")

    socketio.emit("agent_switch", {"agent": "analyst"}, room=client_id)
    filters = {}

    agent = RoadmapAgent(
        tenant_id=tenantID,
        user_id=userID,
        socketio=socketio,
        llm=llm,
        client_id=client_id,
        base_agent=base_agent,
        sessionID=sessionID,
    )
    answer = ""
    for response in agent.process_query(query=last_user_message, filters=filters if filters else None):
        answer += response
        yield response

    TangoDao.insertTangoState(
        tenant_id=tenantID,
        user_id=userID,
        key="roadmap_analyst",
        value=f"Agent Response: {answer}",
        session_id=sessionID,
    )


# Schema and args (unchanged)
ROADMAP_ARGS = [
    {
        "name": "roadmap_id",
        "type": "int[]",
        "description": "List of roadmap IDs.",
        "conditional": "in",
    },
    {
        "name": "portfolio_ids",
        "type": "int[]",
        "description": "List of portfolio IDs.",
        "conditional": "in",
    },
    {
        "name": "priority",
        "type": "str",
        "description": "Priority (High, Medium, Low).",
        "conditional": "like",
    },
    {
        "name": "category",
        "type": "str",
        "description": "Roadmap category.",
        "conditional": "like",
    },
    {
        "name": "start_date",
        "type": "date-bound",
        "description": "Start date range.",
        "conditional": "date-bound",
    },
    {
        "name": "end_date",
        "type": "date-bound",
        "description": "End date range.",
        "conditional": "date-bound",
    },
    {
        "name": "budget",
        "type": "range",
        "description": "Budget range.",
        "conditional": "range",
    },
]

RETURN_DESCRIPTION = """
Deep analysis of roadmap (future projects) planned by this customer. 
Provides detailed per-roadmap insights and batch-level trends based on the user query.
"""

VIEW_ROADMAP = AgentFunction(
    name="view_roadmaps",
    description="Roadmap Analyst.",
    args=ROADMAP_ARGS,
    return_description=RETURN_DESCRIPTION,
    function=view_roadmaps,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name,
)
