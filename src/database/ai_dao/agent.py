

from src.trmeric_utils.helper.decorators import log_function_io_and_time
from src.trmeric_utils.types.getter import *
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import traceback
from src.trmeric_utils.helper.event_bus import Event, event_bus
from src.trmeric_database.ai_dao import AIDAOInterpreter, AIDAOExecutor
from src.trmeric_database.dao import TenantDaoV2, TangoDao, ProviderDao, ProjectsDaoV2, ProjectsDao, ActionsDaoV2, IdeaDao, IntegrationDao, AgentRunDAO
from datetime import datetime

from src.trmeric_database.presentation_dao import PresentationInterpreter, PresentationExecutor, PresentationExportService, ChartInterpreter, ChartExecutor, ChartExportService
from functools import wraps
import inspect
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.ai_dao import DAO_REGISTRY

FOLLOW_UP_INSTRUCTION = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOLLOW-UP PRESENTATION RULE (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If the user is asking for a SHEET, TABLE, CHART, or EXCEL
of something already analyzed in the conversation:

→ The requirement_focus MUST carry forward the EXACT same
  analytical intent from the previous turn.

→ The output format changes (sheet/chart), but the
  MEASURE and DIMENSION must stay identical.

─────────────────────────────────────────
WRONG (loses the metric):
─────────────────────────────────────────
User previously asked: "show monthly status update frequency per project"
User now says: "give me this in a sheet"

❌ requirement_focus: "Present this data in sheet format"
❌ requirement_focus: "Export previous results to excel"
❌ requirement_focus: "Give me this data in sheet"

─────────────────────────────────────────
CORRECT (preserves the metric):
─────────────────────────────────────────
✅ requirement_focus: "Count status updates per project,
   grouped by month, to show how update frequency changed over time"

─────────────────────────────────────────
MORE EXAMPLES:
─────────────────────────────────────────

Previous: "RICE score for roadmaps"
User: "show this as a chart"
✅ "Calculate RICE score per roadmap using effort_hours from
   team_data and impact_score from key_results, sorted desc"

Previous: "milestone count by portfolio"
User: "export to sheet"
✅ "Count milestones per project, grouped by portfolio"

─────────────────────────────────────────
SELF-CHECK before writing requirement_focus:
─────────────────────────────────────────

1. What was computed in the previous turn?
2. What is the user's new output format request?
3. Write requirement_focus = previous metric + previous grouping
   (ignore the format word like "sheet" or "chart" entirely)

The export_presentation flags handle the FORMAT.
The requirement_focus handles the DATA.
These are separate concerns. Never mix them.

"""


ANALYTICAL_ACTION_DOC_TEMPLATE_REPORT = """
  AI Analyst executes advanced analytics for `{entity_type}`.

  This is NOT a simple data fetch tool.

  The system can:
  • Retrieve specific fields (raw data)
  • Compute aggregations (COUNT, SUM, AVG, MIN, MAX)
  • Perform derived calculations (duration, ratios, variance)
  • Group and bucket data (month, quarter, portfolio, user, etc.)
  • Return either entity-level records OR summarized metrics

  The system automatically chooses the MOST EFFICIENT execution.
  If only metrics are required, it will avoid full entity retrieval.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CORE PRINCIPLE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Describe WHAT insight is needed.
  Do NOT describe HOW to compute it.

  The system will:
  • Minimize data fetch
  • Push calculations to the data layer
  • Avoid unnecessary full-record retrieval
  • Return aggregated results whenever possible

  If headline numbers, trends, or comparisons are needed,
  DO NOT request all fields.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO WRITE requirement_focus (IMPORTANT)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Write the analytical intent in STRUCTURED PARTS.

  Think in the following blocks:

  1) Measure (What to calculate)
     Examples:
     • Count projects
     • Sum budget
     • Average duration
     • Identify top portfolios

  2) Scope / Filter (Which entities)
     Examples:
     • Created in 2025
     • Active projects
     • Archived roadmaps excluded

  3) Dimension / Bucket (How to group)
     Examples:
     • By month
     • By portfolio
     • By project type
     • Quarterly trend

  4) Purpose / Insight (Why)
     Examples:
     • For headline metrics
     • To understand growth trend
     • To detect workload distribution
     • For hero section summary

  Write requirement_focus like:

  "Count projects created in 2025,
   bucket by month,
   group by portfolio,
   to understand growth trend"

  Or:

  "Average project duration for completed projects,
   grouped by portfolio"

  Or (raw fetch case):

  "Fetch pproject kpis for detailed semantic grouping"

  Avoid vague requests like:
  • "Fetch all projects"
  • "Get full data"
  • "Load everything"

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCHEMA & ATTRIBUTE DETAILS
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {spec}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETERS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    params (dict):

        use (bool) [REQUIRED]:
            Enable execution of this analytical agent.
            Must be true to run analytics.

        requirement_focus (str) [REQUIRED]:
            The core analytical question or focus.
            Explain WHAT you want to understand and WHY.

            Examples:
            • "Identify projects with elevated delivery risk"
            • "Understand roadmap constraint patterns"
            • "Compare workload distribution across teams"


  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OUTPUT BEHAVIOR
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  The system may return:

  • Entity-level records (if fields requested)
  • Aggregated summaries
  • Time-bucketed metrics
  • Grouped analysis

  Raw data is returned ONLY when necessary.
  Aggregated results are preferred for performance and clarity.
""".strip()




ANALYTICAL_ACTION_DOC_TEMPLATE_NORMAL = """
  AI Analyst executes advanced analytics for `{entity_type}`.

  This is NOT a simple data fetch tool.

  The system can:
  • Retrieve specific fields (raw data)
  • Compute aggregations (COUNT, SUM, AVG, MIN, MAX)
  • Perform derived calculations (duration, ratios, variance)
  • Group and bucket data (month, quarter, portfolio, user, etc.)
  • Return either entity-level records OR summarized metrics

  The system automatically chooses the MOST EFFICIENT execution.
  If only metrics are required, it will avoid full entity retrieval.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CORE PRINCIPLE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Describe WHAT insight is needed.
  Do NOT describe HOW to compute it.

  The system will:
  • Minimize data fetch
  • Push calculations to the data layer
  • Avoid unnecessary full-record retrieval
  • Return aggregated results whenever possible

  If headline numbers, trends, or comparisons are needed,
  DO NOT request all fields.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO WRITE requirement_focus (IMPORTANT)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Write the analytical intent in STRUCTURED PARTS.

  Think in the following blocks:

  1) Measure (What to calculate)
     Examples:
     • Count projects
     • Sum budget
     • Average duration
     • Identify top portfolios

  2) Scope / Filter (Which entities)
     Examples:
     • Created in 2025
     • Active projects
     • Archived roadmaps excluded

  3) Dimension / Bucket (How to group)
     Examples:
     • By month
     • By portfolio
     • By project type
     • Quarterly trend

  4) Purpose / Insight (Why)
     Examples:
     • For headline metrics
     • To understand growth trend
     • To detect workload distribution
     • For hero section summary

  Write requirement_focus like:

  "Count projects created in 2025,
   bucket by month,
   group by portfolio,
   to understand growth trend"

  Or:

  "Average project duration for completed projects,
   grouped by portfolio"

  Or (raw fetch case):

  "Fetch pproject kpis for detailed semantic grouping"

  Avoid vague requests like:
  • "Fetch all projects"
  • "Get full data"
  • "Load everything"


    not good -> "requirement_focus": "Count total roadmaps created in 2025 for scale of work and big picture analysis"
    good -> "requirement_focus": "Count total roadmaps created in 2025"
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCHEMA & ATTRIBUTE DETAILS
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {spec}
  
  
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    INTENT PRESERVATION RULE (CRITICAL)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    The requirement_focus MUST faithfully reflect the user's question.
    Do NOT reinterpret, invert, or simplify the user's intent.

    Before writing requirement_focus, ask:

        What does the user want to MEASURE?
        What does the user want to GROUP or SEGMENT by?

    These two are NOT interchangeable.
    Swapping them produces the opposite of what the user asked.

    ─────────────────────────────────────────
    EXAMPLES — RIGHT vs WRONG
    ─────────────────────────────────────────

    User: "how many portfolios does each project belong to?"
    ✅ "Count portfolios per project, grouped by project"
    ❌ "Count projects per portfolio, grouped by portfolio"

    User: "which months had the most milestones completed?"
    ✅ "Count milestones completed, grouped by month"
    ❌ "Count months, grouped by milestone"

    User: "average budget of projects per program"
    ✅ "Average project budget, grouped by program"
    ❌ "Average program count, grouped by project budget"

    ─────────────────────────────────────────
    SELF-CHECK BEFORE WRITING requirement_focus
    ─────────────────────────────────────────

    Read the user's question again.
    Then answer:

        Measure  → what is being counted/summed/averaged?
        Dimension → what is it being grouped or broken down by?

    Write it in this order:
        "<verb> <measure>, grouped by <dimension>"

    If you cannot clearly identify the measure and dimension
    from the user's question → ask for clarification.
    Do NOT guess and flip.
    
    {FOLLOW_UP_INSTRUCTION}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETERS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    params (dict):

        use (bool) [REQUIRED]:
            Enable execution of this analytical agent.
            Must be true to run analytics.

        requirement_focus (str) [REQUIRED]:
            The core analytical question or focus.
            Explain WHAT you want to understand and WHY.
            

        execution_context (optional str):
            Plain-language execution memory from the planner.

            Describes what happened previously and why
            the prior result was insufficient.

            This is NOT an instruction.
            It is contextual memory to avoid repetition of mistake.

            Example:
            "Previous attempt returned only identifiers.
            The result lacked explanatory metrics."

        export_presentation (optional dict):
            Explicit and STRUCTURAL requests for projection of results if asked.

            export_presentation.export_table_or_sheet (bool):
                If true, generate human-readable tabular projections.
                Intended for verification, inspection, or export.


  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OUTPUT BEHAVIOR
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  The system may return:

  • Entity-level records (if fields requested)
  • Aggregated summaries
  • Time-bucketed metrics
  • Grouped analysis

  Raw data is returned ONLY when necessary.
  Aggregated results are preferred for performance and clarity.
""".strip()



            # export_presentation.export_charts (bool):
            #     If true, generate visual projections (charts).
            #     Intended for comparison, trend detection, or decision-making.
                
            # export_presentation.chart_intent (string):
            #     REQUIRED if export_presentation.export_charts = true.

                


def agent_display_name(agent_key: str) -> str:
    base = agent_key.replace("_agent", "").replace("_", " ")
    return base.title() + " Agent"


class AIDaoAgentDataGetter:
    def __init__(self, tenant_id: int, user_id: int, session_id: str, conversation= "", **kwargs):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.event_bus = event_bus
        self.conversation = conversation
        self.mode = kwargs.get("mode")
        print("AIDaoAgentDataGetter init ", self.mode)
        self.fn_maps = {
            "fetch_projects_data_using_project_agent": self._make_analytical_fn(entity_type="project"),
            "fetch_roadmaps_data_using_roadmap_agent": self._make_analytical_fn(entity_type="roadmap"),
            "fetch_ideas_data_using_idea_agent": self._make_analytical_fn(entity_type="idea"),
            "list_issues_aka_bug_enhancement": self._make_analytical_fn(entity_type="issues_aka_bug_enhancement"),
            
            "fetch_tango_usage_qna_data": self._make_analytical_fn(entity_type="tango_conversation"),
            "fetch_tango_stats": self._make_analytical_fn(entity_type="tango_stats"),
            "fetch_users_data": self._make_analytical_fn(entity_type="users"),
            "fetch_agent_activity_data": self._make_analytical_fn(entity_type="tango_activity_log"),
            
            "log_issues_aka_bug_enhancement": self.log_bug_or_enhancement,
            "update_issues_aka_bug_enhancement": self.update_bug_enhancement,  
        }
        
    # ==========================================================================
    # ANALYTICAL FUNCTION FACTORY
    # ==========================================================================        
    def _make_analytical_fn(self, *, entity_type: str):
        """
        Factory for entity-bound analytical agent functions.
        """

        @wraps(self._run_analytical_agent)
        def _fn(params={}):
            return self._run_analytical_agent(
                entity_type=entity_type,
                params=params,
            )

        # 🔒 Fix signature so inspectors see params properly
        if self.mode == "research":
            _fn.__signature__ = inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        "params",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=DEFAULT_ANALYTICAL_AGENT_PARAMS_NORMAL,
                        annotation=DEFAULT_ANALYTICAL_AGENT_PARAMS_NORMAL.__class__
                    )
                ]
            )
        elif self.mode == "report":
            _fn.__signature__ = inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        "params",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=DEFAULT_ANALYTICAL_AGENT_PARAMS_REPORT,
                        annotation=DEFAULT_ANALYTICAL_AGENT_PARAMS_REPORT.__class__
                    )
                ]
            )
        dao_cls = DAO_REGISTRY.get(entity_type)
        # schema = manifest.FIELD_REGISTRY
        import json
        
        raw_schema = dao_cls.get_available_attributes()
        schema = {}
        if raw_schema.get("overall_description"):
            schema["overall_description"] = raw_schema.get("overall_description")
        for attr, meta in raw_schema.items():
            if attr == "overall_description":
                continue
            # schema[attr] = {k: v for k, v in meta.items() if not callable(v)}
            schema[attr] = {
                "description": meta.get("important_info_to_be_understood_by_llm"),
                "schema_fields": meta.get("fields"), 
                "extra_info_about_schema_fields": meta.get("intel"),
            }
            
        schema_str = json.dumps(schema, indent=2)
        if self.mode == "research":
            _fn.__doc__ = ANALYTICAL_ACTION_DOC_TEMPLATE_NORMAL.format(
                entity_type=entity_type, spec=schema_str, FOLLOW_UP_INSTRUCTION=FOLLOW_UP_INSTRUCTION
            )
        elif self.mode == "report":
            _fn.__doc__ = ANALYTICAL_ACTION_DOC_TEMPLATE_REPORT.format(
                entity_type=entity_type, spec=schema_str
            )
        return _fn

  
    def _resolve_entity_scope(self, *, entity_type: str, structured_plan):
        """
        Resolves the eligible entity IDs for a given entity type.

        This encapsulates all entity-specific access rules and scope logic.
        """

        if entity_type == "project":
            eligible_projects = ProjectsDao.FetchAvailableProject(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

            print("is_archived_project", "is_archived_project" in str(structured_plan))
            # print("is_archived_project", "is_archived_project" in str(structured_plan))
            # Include archived projects only if the plan requires it
            # if "is_archived_project" in str(structured_plan):
            archived = ProjectsDao.FetchAccesibleArchivedProjects(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            eligible_projects += archived

            return eligible_projects

        if entity_type == "roadmap":
            from src.trmeric_database.dao import RoadmapDao

            return RoadmapDao.fetchEligibleRoadmapList(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                fetch_only_ids=True,
            )
            
        if entity_type == "idea":
            return IdeaDao.fetchIdeasIds(
                tenant_id=self.tenant_id,
            )

        # if entity_type == "issues_aka_bug_enhancement":
        #     # Tenant-scoped; no entity filtering
        return None

        # raise ValueError(f"Unsupported entity_type: {entity_type}")

    # ==========================================================================
    # CANONICAL ANALYTICAL ENGINE (SINGLE SOURCE OF TRUTH)
    # ==========================================================================
    @log_function_io_and_time
    def _run_analytical_agent(
        self,
        *,
        entity_type: str,
        params: {} # pyright: ignore[reportInvalidTypeForm]
    ):
        if not params.get("use"):
            return {"skipped": True}

        requirement_focus = params.get("requirement_focus", "")
        # with_presentation = params.get("with_presentation", False)
        execution_context = params.get("execution_context", "") or ""
        presentation = params.get("export_presentation", {}) or {}
        want_tables = presentation.get("export_table_or_sheet") or False
        want_charts = presentation.get("export_charts") or False
        chart_intent = presentation.get("chart_intent") or ""
        # want_tables = want_tables or want_charts
        
        # projection_intent = params.get("projection_intent", None)
        # print()
        # allowed values: None | "read" | "export" | "visual"

        self.event_bus.dispatch(
            "STEP_UPDATE",
            {"message": f"{entity_type} analytical agent initiated"},
            session_id=self.session_id,
        )
        
        conversation=f"""
        {self.conversation}

        EXECUTION CONTEXT:
        {execution_context}
        """.strip()

        # Planning
        interpreter = AIDAOInterpreter(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            conversation=conversation,
            session_id=self.session_id,
        )
        
        self.event_bus.dispatch(
            "LLM_PLAN_UPDATE",
            {
                "trigger": "important_step",
                "source": "sub_agent",
                "agent_name": agent_display_name(f"{entity_type}_agent"),
            },
            session_id=self.session_id,
        )

        structured_plan = interpreter.interpret_user_query_with_llm(
            user_query="",
            dao_type=entity_type,
            requirement_focus=requirement_focus,
        )
        if structured_plan == None:
            return {
                "error": "Error occured while fetching data"
            }

        self.event_bus.dispatch(
            "LLM_PLAN_UPDATE",
            {
                "source": "sub_agent",
                "agent_name": agent_display_name(f"{entity_type}_agent"),
                "step_id": params.get("step_id"),
                "requirement_focus": requirement_focus,
                "plan": structured_plan,
                "timestamp": datetime.utcnow().isoformat(),
            },
            session_id=self.session_id,
        )
        
        # 2️⃣ Resolve entity scope (entity-specific logic)
        entity_ids = self._resolve_entity_scope(
            entity_type=entity_type,
            structured_plan=structured_plan,
        )

        executor = AIDAOExecutor()
        dao_results = executor.execute_plan(
            dao_type=entity_type,
            structured_plan=structured_plan,
            tenant_id=self.tenant_id,
            entity_ids=entity_ids,
        )

        # if not with_presentation:
        #     return dao_results
        
        
        s3 = S3Service()
        question_id = AgentRunDAO.get_latest_run_for_session(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            session_id=self.session_id
        )
        
        base_s3_path = (
            f"exports/{self.tenant_id}/{self.session_id}/{question_id}/"
            if question_id else None
        )
        appLogger.info({
            "function": "_run_analytical_agent",
            "question_id": question_id if question_id else "",
            "base_s3_path": base_s3_path,
            "self.mode": self.mode,
            "params": params
        })
        
        if self.mode == "report":
            return {"data_fetched": dao_results}

        export_res = []
        # -------------------------------
        # 3️⃣ TABLE PROJECTION (OPTIONAL)
        # -------------------------------
        if want_tables and base_s3_path:
            entities_key = f"{entity_type}s"
            if entities_key not in dao_results:
                entities_key = entity_type  # fallback: "users" instead of "userss"
            
            entities_preview = (dao_results.get(entities_key) or [])[:20]
            if len(entities_preview) == 0:
                export_res.append({
                    "export": {"message": "Table/Sheet export Did not happen coz 0 data was fetched"}
                })

            presentation_plan = PresentationInterpreter(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=self.session_id,
            ).interpret({
                f"{entities_key}": entities_preview,
                "_global_summary": dao_results.get("_global_summary") or {},
                "debug_summary": dao_results.get("_debug_summary") or {},
                "requirement_focus": requirement_focus,
                "_hint_data_source_key": entities_key,
            })

            self.event_bus.dispatch(
                "LLM_PLAN_UPDATE",
                {
                    "source": "sub_agent",
                    "agent_name": "Sheet/Table Creation Agent",
                    "plan": presentation_plan,
                    "output": "Charts exported as json and will be rendered in the UI"
                },
                session_id=self.session_id,
            )

            presentation_data = PresentationExecutor().execute(
                analytical_truth=dao_results,
                presentation_plan=presentation_plan,
            )
            import uuid
            random_id = uuid.uuid4().hex
            exporter = PresentationExportService()
            local_path = exporter.export_to_excel(presentation_data)
            s3_key = f"{base_s3_path}tables_{random_id}.xlsx"
            s3.upload_file(local_path, s3_key)
            
            self.event_bus.dispatch(
                "AGENT_ARTIFACT_CREATED",
                {
                    "artifact_type": "export",
                    "format": "excel",
                    "entity_type": entity_type,
                    "requirement_focus": requirement_focus,
                    "s3_key": s3_key,
                },
                session_id=self.session_id,
            )
            export_res.append(
                {
                    "export": {
                        "plan_created_for_export": presentation_plan, 
                        "message": "Sheet/Table data expported",
                    }
                }
            )

        return {
            "data_fetched": dao_results,
            "export_info": export_res,
        }
            
        # -------------------------------
        # 4️⃣ CHART PROJECTION (OPTIONAL)
        # -------------------------------
        if want_charts and base_s3_path:
            entities_key = f"{entity_type}s"
            entities_preview = (dao_results.get(entities_key) or [])[:5]

            if len(entities_preview) == 0:
                export_res.append({
                    "export": {"message": "Chart export did not happen coz 0 data was fetched"}
                })
            
            chart_plan = ChartInterpreter(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=self.session_id,
            ).interpret(
                evidence_snapshot={
                    entities_key: entities_preview,
                    "_global_summary": dao_results.get("_global_summary") or {},
                    "requirement_focus": f"{requirement_focus} ___ intent: {chart_intent}",
                }
            )
            
            self.event_bus.dispatch(
                "LLM_PLAN_UPDATE",
                {
                    "source": "sub_agent",
                    "agent_name": "Chart Creation Agent",
                    "plan": chart_plan,
                    "output": "Charts exported as json and will be rendered in the UI"
                },
                session_id=self.session_id,
            )

            charts = ChartExecutor().execute(
                analytical_truth=dao_results,
                chart_plan=chart_plan,
            )
            import uuid
            random_id = uuid.uuid4().hex
            
            exporter = ChartExportService()
            local_path = exporter.export_to_json(charts)
            s3_key = f"{base_s3_path}charts_{random_id}.json"
            s3.upload_file(local_path, s3_key)
            
            self.event_bus.dispatch(
                "AGENT_ARTIFACT_CREATED",
                {
                    "artifact_type": "export",
                    "format": "chart",
                    "entity_type": entity_type,
                    "requirement_focus": requirement_focus,
                    "s3_key": s3_key,
                },
                session_id=self.session_id,
            )
            
            export_res.append(
                {
                    "export": {
                        "plan_created_for_export": chart_plan, 
                        "message": "Chart data expported",
                    }
                }
            )
        return {
            "data_fetched": dao_results,
            "export_info": export_res,
        }

    # ======================================================================
    # CUSTOMER FEEDBACK — OPERATIONAL (CRUD)
    # ======================================================================
    @log_function_io_and_time
    def log_bug_or_enhancement(
        self,
        params: dict = DEFAULT_PARAMS_FOR_BUG_ENHANCEMENT
    ) -> dict:
        """
        Creates a **bug or enhancement record** for customer feedback.
        This is an operational action — NOT analytical.

        Intended usage:
            • Customer Success
            • Support conversations
            • Product feedback capture

        Parameters:
            params (dict):
                type (str): bug | enhancement
                title (str): short summary
                description (str): very detailed explanation of the issue/bug or enhancement
                priority (str): low | medium | high | critical
        """
        from src.trmeric_database.dao import BugEnhancementDao

        return {
            "custom_id": BugEnhancementDao.create_bug_enhancement(
                tenant_id=self.tenant_id,
                type=params.get("type", "bug"),
                title=params.get("title"),
                description=params.get("description"),
                priority=params.get("priority"),
                created_by_id=self.user_id,
            )
        }

    @log_function_io_and_time
    def update_bug_enhancement(
        self,
        params: dict = DEFAULT_PARAMS_FOR_BUG_UPDATE
    ) -> dict:
        """
        Updates an existing bug or enhancement using its public `custom_id`.

        Supported updates:
            • status
            • priority
            • resolution_description
            • assignment changes

        Parameters:
            params (dict):
                custom_id (str):
                    External identifier (e.g., TRB-1234)

                updates (dict):
                    Fields to update.

        Returns:
            dict:
                Update confirmation.
        """
        from src.trmeric_database.dao import BugEnhancementDao

        internal_id = BugEnhancementDao.get_internal_id_from_custom_id(
            tenant_id=self.tenant_id,
            custom_id=params.get("custom_id"),
        )

        BugEnhancementDao.update_bug_enhancement(
            tenant_id=self.tenant_id,
            bug_id=internal_id,
            updates=params.get("updates", {}),
            updated_by_id=self.user_id,
        )

        return {"updated": True}
