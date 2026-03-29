from typing import Dict, Optional, List
from src.api.logging.AppLogger import appLogger, debugLogger
import traceback
import pandas as pd
import json
from datetime import datetime
from src.database.dao import db_instance, TangoDao, RoadmapDao, ProjectsDaoV2, ProviderDao, TenantDaoV2
from src.trmeric_services.journal.Activity import  detailed_activity
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.journal.Vectors.ActivityOnboarding import format_transformation_summary_markdown, onboarding_summary
from src.trmeric_services.agents_v2.schema import SCHEMAS
from src.trmeric_services.agents_v2.actions.sheet_mapper_v2 import create_mapping
from src.trmeric_services.agents_v2.actions.text_mapper import create_text_mapping
from src.trmeric_s3.s3 import S3Service
from src.utils.helper.file_analyser import FileAnalyzer
from src.trmeric_s3.s3 import S3Service
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateRoadmap import RoadmapAgent
from src.utils.helper.decorators import log_function_io_and_time

from src.ws.static import UserSocketMap
from src.api.logging.ProgramState import ProgramState
from src.utils.api import ApiUtils
from src.database.dao import JobDAO
import uuid
from src.trmeric_services.agents_v2.actions.file_template import store_template_file,create_template_mapping
from src.utils.helper.event_bus import event_bus

from src.utils.helper.common import MyJSON

from src.utils.types.actions import *
from src.utils.types.getter import *


class TrucibleActions:
    """
    A utility class to perform insert/update actions on tenant-related tables
    based on processed document data provided by the planning LLM.
    """
    def __init__(self, tenant_id: int, user_id: int, agent_name="", session_id="", socketio=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.agent_name = agent_name
        self.session_id = session_id
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        self.file_analyzer = FileAnalyzer(tenant_id=tenant_id)
        self.s3_service = S3Service()
        self.llm = ChatGPTClient()
        self.socketio = socketio
        self.event_bus = event_bus
        self.fn_maps = {
            "fetch_company": self.fetch_company,
            "fetch_company_industry": self.fetch_company_industry,
            "fetch_company_performance": self.fetch_company_performance,
            "fetch_competitor": self.fetch_competitor,
            "fetch_enterprise_strategy": self.fetch_enterprise_strategy,
            "fetch_industry": self.fetch_industry,
            "fetch_social_media": self.fetch_social_media,
            
            
            
            "store_company_context": self.store_company_context,
            "store_enterprise_strategy": self.store_enterprise_strategy,
            "store_company_industry_mapping": self.store_company_industry_mapping,
            "store_social_media_context": self.store_social_media_context,
            "store_competitor_context": self.store_competitor_context,
            "store_performance_context": self.store_performance_context,
            "store_company_orgstrategy": self.store_company_orgstrategy,
            "store_portfolio_context": self.store_portfolio_context,
            
            "map_excel_columns": self.map_excel_columns,
            "map_text": self.map_text,
            "update_project": self.update_project,
            "map_from_conversation": self.map_from_conversation,
            
            "set_user_designation": self.set_user_designation,
        }
        
        
    @log_function_io_and_time
    def fetch_company(self, params: Optional[Dict] = DEFAULT_COMPANY_PARAMS) -> list:
        """
        Fetches company data for a tenant.
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching Company Info"},
            session_id=self.session_id
        )
        return TenantDaoV2.fetch_company(self.tenant_id)

    @log_function_io_and_time
    def fetch_company_industry(self, params: Optional[Dict] = DEFAULT_COMPANY_INDUSTRY_PARAMS) -> list:
        """
        Fetches company-industry mappings for a tenant.
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching Company Industry"},
            session_id=self.session_id
        )
        return TenantDaoV2.fetch_company_industry(self.tenant_id)

    @log_function_io_and_time
    def fetch_company_performance(self, params: Optional[Dict] = DEFAULT_COMPANY_PERFORMANCE_PARAMS) -> list:
        """
        Fetches performance data for a tenant, optionally filtered by period.
        """
        try:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Fetching Company Performace"},
                session_id=self.session_id
            )
            period = params.get("period")
            query = f"""
                SELECT id, tenant_id, period, revenue, profit, funding_raised, investor_info, citations
                FROM public.tenant_companyperformance
                WHERE tenant_id = {self.tenant_id} AND deleted_on IS NULL
            """
            if period:
                query += f" AND period = '{period}'"
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[DataGetters.fetch_company_performance] tenant_id={self.tenant_id}, error={e}")
            return []

    @log_function_io_and_time
    def fetch_competitor(self, params: Optional[Dict] = DEFAULT_COMPETITOR_PARAMS) -> list:
        """
        Fetches competitor data for a tenant, optionally filtered by competitor name.
        """
        try:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Fetching Company from context"},
                session_id=self.session_id
            )
            competitor_name = params.get("competitor_name") or None
            query = f"""
                SELECT id, tenant_id, name, summary, recent_news, financials, citations
                FROM public.tenant_competitor
                WHERE tenant_id = {self.tenant_id} AND deleted_on IS NULL
            """
            if competitor_name:
                query += f" AND name ilike '%{competitor_name}%'"
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[DataGetters.fetch_competitor] tenant_id={self.tenant_id}, error={e}")
            return []

    @log_function_io_and_time
    def fetch_enterprise_strategy(self, params: Optional[Dict] = DEFAULT_ENTERPRISE_STRATEGY_PARAMS) -> list:
        """
        Fetches enterprise strategy and its sections for a tenant, optionally filtered by title.
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching enterprise strategy from context"},
            session_id=self.session_id
        )
        if params is None:
            params = DEFAULT_ENTERPRISE_STRATEGY_PARAMS.copy()
            
        return TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id, **params)
    

    @log_function_io_and_time
    def fetch_industry(self, params: Optional[Dict] = DEFAULT_INDUSTRY_PARAMS) -> list:
        """
        Fetch industry info: you can query by industry ids or particular industry name
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching industry from context"},
            session_id=self.session_id
        )
        industry_ids = params.get("industry_ids", []) or []
        name = params.get("name") or ""
        return TenantDaoV2.fetch_industry(industry_ids, name)

    @log_function_io_and_time
    def fetch_social_media(self, params: Optional[Dict] = DEFAULT_SOCIAL_MEDIA_PARAMS) -> list:
        try:
            platform = params.get("platform")
            query = f"""
                SELECT id, tenant_id, platform, handle, latest_posts, last_updated
                FROM public.tenant_socialmedia
                WHERE tenant_id = {self.tenant_id} AND deleted_on IS NULL
            """
            if platform:
                query += f" AND platform = '{platform}'"
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error(f"[DataGetters.fetch_social_media] tenant_id={self.tenant_id}, error={e}")
            return []

        
    @log_function_io_and_time
    def store_portfolio_context(
        self,
        params: Optional[List[Dict]] = DEFAULT_PORTFOLIO_CONTEXT_PARAMS
    ) -> Dict:
        """
        Persist CONFIRMED portfolio-level context entries into storage.

        This action is **write-only** and **append-only**.
        Every valid item in `params` creates a NEW row in `tenant_portfoliocontext`.

        ────────────────────────────────────────────────────────────
        WHAT THIS FUNCTION STORES
        ────────────────────────────────────────────────────────────
        This function stores **Portfolio Context**, which represents
        detailed-level, cross-project intelligence that applies to an
        ENTIRE PORTFOLIO — never to a single project or roadmap.

        Examples of valid Portfolio Context include (non-exhaustive):

        • Portfolio Strategy
        • Portfolio Vision & North Star
        • Portfolio-level KPIs (NOT project KPIs)
        • Investment Themes
        • Strategic Priorities
        • Operating Model & Governance
        • Portfolio-wide Risks & Constraints
        • Executive Narratives & Decisions
        • Long-term Capability or Technology Bets

        🚫 DO NOT use this for:
        - Project metrics
        - Sprint metrics
        - Team-level KPIs
        - Roadmap-level execution data
        - Operational logs or events

        ────────────────────────────────────────────────────────────
        CORE BEHAVIOR (VERY IMPORTANT)
        ────────────────────────────────────────────────────────────
        • This action accepts an ARRAY of context items.
        • EACH ITEM = ONE SEMANTIC CONTEXT = ONE DATABASE RECORD.
        • A single uploaded document can produce MULTIPLE records
        if it contains multiple distinct semantic contexts.

        There is NO deduplication, NO updates, and NO overwrites.
        Calling this function multiple times WILL create new rows.

        ────────────────────────────────────────────────────────────
        REQUIRED PRE-CONDITIONS (HARD GUARDRAILS)
        ────────────────────────────────────────────────────────────
        An item is stored ONLY IF ALL conditions below are true:

        1. The data is explicitly classified as "Portfolio Context"
        2. A valid `portfolio_id` is identified and confirmed
        3. `content_type` is present and semantically correct
        4. `content` is very detailed from the data provided by the user
        5. The content has already been shown to the user
        6. The user has explicitly confirmed persistence
        → user_confirmed MUST be True

        If `user_confirmed` is False → the item is SKIPPED.

        ────────────────────────────────────────────────────────────
        PARAMS STRUCTURE
        ────────────────────────────────────────────────────────────
        params: List[Dict]

        Each dict MUST follow this structure:

        [
            {
                "portfolio_id": <ID of the portfolio this context belongs to>,

                "content_type": <STRING ENUM>
                    Examples:
                    - "portfolio_strategy"
                    - "portfolio_kpis"
                    - "investment_themes"
                    - "portfolio_risks"
                    - "operating_model"
                    - "executive_narrative"

                "title": <Short human-readable label>,
                "summary": <Concise abstract of the context>,

                "content": {
                    // very very detailed
                },

                "doc_s3_keys": [<S3 keys of source documents>],
                "citations": [<optional references or page numbers>],

                "source_type": "doc_upload" | "manual" | "integration",

                "user_confirmed": true | false
            }
        ]

        ────────────────────────────────────────────────────────────
        CRITICAL SEMANTIC RULES
        ────────────────────────────────────────────────────────────
        • `content_type` determines WHAT gets created downstream
        (KPIs, strategy objects, themes, etc.)
        • Incorrect or vague content_type WILL lead to wrong entities
        being created (e.g., wrong KPIs).

        ⚠️ CONTENT TYPE MUST BE PRECISE AND INTENTIONAL ⚠️

        ────────────────────────────────────────────────────────────
        SAFETY & FAILURE HANDLING
        ────────────────────────────────────────────────────────────
        • If any required field is missing → item fails
        • If user_confirmed is False → item is NOT stored
        • Failures are reported PER ITEM
        • Successful items do NOT rollback on partial failures

        ────────────────────────────────────────────────────────────
        RETURN VALUE
        ────────────────────────────────────────────────────────────
        Returns a per-item result list with success/failure details,
        including the created portfolio_context_id for each success.

        ────────────────────────────────────────────────────────────
        SUMMARY (READ THIS TWICE)
        ────────────────────────────────────────────────────────────
        ONE item = ONE semantic portfolio context = ONE DB row.
        This function is irreversible and creates durable intelligence.
        Misclassification here WILL pollute downstream reasoning.
        """


        try:
            # ---------------- Normalize input ----------------
            if not params:
                return {
                    "success": False,
                    "message": "No portfolio context data provided."
                }

            # Backward compatibility: single dict → list
            if isinstance(params, dict):
                params = [params]

            if not isinstance(params, list):
                return {
                    "success": False,
                    "message": "Invalid params format. Expected a list of portfolio context objects."
                }

            results = []
            current_time = datetime.now()

            insert_query = """
                INSERT INTO tenant_portfoliocontext
                (
                    tenant_id,
                    portfolio_id,
                    content_type,
                    title,
                    summary,
                    content,
                    source_type,
                    doc_ids,
                    citations,
                    created_by_id,
                    updated_by_id,
                    created_on,
                    updated_on
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """

            for idx, item in enumerate(params):
                item = item.copy()

                # ---------- Guardrail: user confirmation ----------
                if not item.get("user_confirmed", False):
                    results.append({
                        "success": False,
                        "index": idx,
                        "message": "User confirmation missing. Item was not stored."
                    })
                    continue

                portfolio_id = item.get("portfolio_id")
                content_type = item.get("content_type")
                content = item.get("content")

                if "kpi" in content_type.lower() or "strateg" in content_type.lower() or "priorit" in content_type.lower():
                    print("--debug start _add_portfolio_info---------------------")
                    from src.trmeric_services.chat_service.controller.portfolio import _add_portfolio_info
                    model_options = ModelOptions("gpt-4.1", 3000, 0.1)
                    res = _add_portfolio_info(content_type,portfolio_id,content,self.llm,self.logInfo,model_options)
                    print("--debug resportolio----", res)
                # ---------- Required field validation ----------
                if not portfolio_id or not content_type or not content:
                    results.append({
                        "success": False,
                        "index": idx,
                        "message": "Missing required fields: portfolio_id, content_type, or content."
                    })
                    continue

                # ---------- Execute insert ----------
                result = db_instance.executeSQLQuery(
                    insert_query,
                    (
                        self.tenant_id,
                        portfolio_id,
                        content_type,
                        item.get("title", ""),
                        item.get("summary", ""),
                        json.dumps(content),
                        item.get("source_type", "doc_upload"),
                        json.dumps(item.get("doc_s3_keys", [])),
                        json.dumps(item.get("citations", [])),
                        self.user_id,
                        self.user_id,
                        current_time,
                        current_time
                    ),
                    fetch="one"
                )

                results.append({
                    "success": True,
                    "portfolio_context_id": result[0] if result else None,
                    "portfolio_id": portfolio_id,
                    "content_type": content_type
                })

            return {
                "success": True,
                "message": "Portfolio context processing completed",
                "results": results
            }

        except Exception as e:
            appLogger.error({
                "function": "store_portfolio_context",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "success": False,
                "message": "Error storing portfolio context",
                "error": str(e)
            }


    @log_function_io_and_time
    def store_company_context(self, params: Optional[Dict] = DEFAULT_COMPANY_CONTEXT_PARAMS) -> Dict:
        """
        Stores or updates company context in tenant_company table.
        """
        try:
            params = params.copy()
            doc_ids = params.get("doc_s3_keys", [])
            citations = params.get("citations") or []
            current_time = datetime.now()

            query = f"""
                SELECT id FROM public.tenant_company
                WHERE tenant_id = {self.tenant_id} AND deleted_on IS NULL
            """
            existing = db_instance.retrieveSQLQueryOld(query)
            existing_id = existing[0]["id"] if existing else None

            if existing_id:
                update_query = """
                    UPDATE public.tenant_company
                    SET name = %s, description = %s, business_units = %s, culture_values = %s,
                        management_team = %s, doc_ids = %s, citations = %s, company_url = %s, updated_by_id = %s, updated_on = %s
                    WHERE tenant_id = %s AND deleted_on IS NULL
                    RETURNING id;
                """
                result = db_instance.executeSQLQuery(
                    update_query,
                    (
                        params.get("name", ""),
                        params.get("description", ""),
                        json.dumps(params.get("business_units", [])),
                        params.get("culture_values", ""),
                        json.dumps(params.get("management_team", [])),
                        json.dumps(doc_ids),
                        json.dumps(citations),
                        params.get("company_url", ""),
                        self.user_id,
                        current_time,
                        self.tenant_id
                    ),
                    fetch='one'
                )
            else:
                insert_query = """
                    INSERT INTO public.tenant_company
                    (tenant_id, name, description, business_units, culture_values, management_team,
                    doc_ids, citations, company_url, created_by_id, updated_by_id, created_on, updated_on)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """
                result = db_instance.executeSQLQuery(
                    insert_query,
                    (
                        self.tenant_id,
                        params.get("name", ""),
                        params.get("description", ""),
                        json.dumps(params.get("business_units", [])),
                        params.get("culture_values", ""),
                        json.dumps(params.get("management_team", [])),
                        json.dumps(doc_ids),
                        json.dumps(citations),
                        params.get("company_url", ""),
                        self.user_id,
                        self.user_id,
                        current_time,
                        current_time
                    ),
                    fetch='one'
                )

            return {
                "message": f"Successfully stored company context for tenant {self.tenant_id}",
                "success": True,
                "company_id": result
            }

        except Exception as e:
            appLogger.error({
                "function": "store_company_context",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {"message": f"Error storing company context: {str(e)}", "success": False}
      
    @log_function_io_and_time  
    def store_enterprise_strategy(self, params: Optional[Dict] = DEFAULT_ENTERPRISE_STRATEGY_PARAMS) -> Dict:
        """
        Stores or updates enterprise strategy and its sections in tenant_enterprisestrategy and tenant_strategysection tables.
        """
        try:
            params = params.copy()
            title = params.get("title", "")
            doc_ids = params.get("doc_s3_keys", [])
            citations = params.get("citations", [])
            sections = params.get("detailed_strategies_sections", [])
            current_time = datetime.now()

            # Check if strategy exists
            query = f"""
                SELECT id FROM public.tenant_enterprisestrategy
                WHERE tenant_id = {self.tenant_id} AND title = '{title}' 
            """
            existing = db_instance.retrieveSQLQueryOld(query)
            strategy_id = existing[0]["id"] if existing else None

            if strategy_id:
                # Update existing strategy
                update_query = """
                    UPDATE public.tenant_enterprisestrategy
                    SET title = %s, doc_ids = %s, citations = %s, updated_by_id = %s, updated_on = %s
                    WHERE id = %s
                    RETURNING id;
                """
                result = db_instance.executeSQLQuery(
                    update_query,
                    (title, json.dumps(doc_ids), json.dumps(citations), self.user_id, current_time, strategy_id),
                    fetch='one'
                )
            else:
                # Insert new strategy
                insert_query = """
                    INSERT INTO public.tenant_enterprisestrategy
                    (tenant_id, title, doc_ids, citations, created_by_id, updated_by_id, created_on, updated_on)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """
                result = db_instance.executeSQLQuery(
                    insert_query,
                    (self.tenant_id, title, json.dumps(doc_ids), json.dumps(citations), self.user_id, self.user_id, current_time, current_time),
                    fetch="one"
                )
                strategy_id = result[0]

            # Handle sections (unchanged)
            results = {"strategy_id": strategy_id, "detailed_strategies_sections": []}
            for section in sections:
                section_name = section.get("section_name", "")
                content = section.get("content", "") or ""
                structured_content = section.get("structured_content", None) or None

                if not section_name:
                    results["detailed_strategies_sections"].append({
                        "section_name": section_name or "unnamed",
                        "success": False,
                        "message": "Section name is required"
                    })
                    continue

                # Check if section exists
                section_query = f"""
                    SELECT id FROM public.tenant_strategysection
                    WHERE strategy_id = {strategy_id} AND section_name = '{section_name}' 
                """
                existing_section = db_instance.retrieveSQLQueryOld(section_query)
                section_id = existing_section[0]["id"] if existing_section else None

                if section_id:
                    # Update existing section
                    update_section_query = """
                        UPDATE public.tenant_strategysection
                        SET content = %s, structured_content = %s, updated_on = %s
                        WHERE id = %s AND deleted_on IS NULL;
                    """
                    db_instance.executeSQLQuery(
                        update_section_query,
                        (content, json.dumps(structured_content) if structured_content else None, current_time, section_id)
                    )
                    results["detailed_strategies_sections"].append({
                        "section_name": section_name,
                        "success": True,
                        "message": f"Updated section {section_name}"
                    })
                else:
                    # Insert new section
                    insert_section_query = """
                        INSERT INTO public.tenant_strategysection
                        (strategy_id, section_name, content, structured_content, created_on, updated_on)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """
                    db_instance.executeSQLQuery(
                        insert_section_query,
                        (strategy_id, section_name, content, json.dumps(structured_content) if structured_content else None, current_time, current_time)
                    )
                    results["detailed_strategies_sections"].append({
                        "section_name": section_name,
                        "success": True,
                        "message": f"Inserted section {section_name}"
                    })

            return {
                "message": f"Successfully stored enterprise strategy for tenant {self.tenant_id}",
                "success": True,
                "results": results
            }

        except Exception as e:
            appLogger.error({
                "function": "store_enterprise_strategy",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "message": f"Error storing enterprise strategy: {str(e)}",
                "success": False,
                "results": {}
            }
    
    @log_function_io_and_time
    def store_company_orgstrategy(self, params: Optional[Dict] = DEFAULT_ORGSTRATEGY_PARAMS) -> Dict:
        """
        Stores the organization strategies/ alignments in roadmap_roadmaporgstratergyalign table.
        """
        try:
            params = params.copy()
            org_strategies = params.get("org_strategies_to_create", []) or []
            # current_time = datetime.now()
            print("--debug store_company_orgstrategy params----", params)

            if not org_strategies:
                return {
                    "message": "No org strategies are found for creation. Please retry!",
                    "success": False,
                    "results": org_strategies
                }

            payload = []
            for strategy in org_strategies:
                payload.append({'tenant_id': self.tenant_id, 'title': strategy})

            values_lines = []
            for item in payload:
                # print("--debug item------", item)
                escaped_title = item['title'].replace("'", "''")
                values_lines.append(
                    f"  ('{item['tenant_id']}', '{escaped_title}')"
                )

            values_block = ",\n".join(values_lines)
            insert_query = f"""
                INSERT INTO public.roadmap_roadmaporgstratergyalign
                (tenant_id, title)
                VALUES
                {values_block}
            """

            print("--debug org_strategies to query--------\n", insert_query)
            result = db_instance.executeSQLQuery(insert_query, params=None)
            return {
                "message": f"Successfully stored organization strategy/alignment for tenant {self.tenant_id}",
                "success": True,
                "results": result
            }

        except Exception as e:
            appLogger.error({"function": "store_company_orgstrategy","error": str(e),"traceback": traceback.format_exc()})
            return {
                "message": f"Error storing org strategy: {str(e)}",
                "success": False,
                "results": {}
            }
    
    @log_function_io_and_time
    def store_social_media_context(self, params: Optional[List[Dict]] = [DEFAULT_SOCIAL_MEDIA_CONTEXT_PARAMS]) -> Dict:
        """
        Stores or updates multiple social media contexts in tenant_socialmedia table.
        """
        try:
            results = []
            current_time = datetime.now()

            for social_media in params:
                print("debug --- ", social_media)
                social_media = social_media.copy()
                platform = social_media.get("platform", "")
                # document_id = social_media.get("document_id", "")
                if not platform:
                    results.append({
                        "platform": platform or "unnamed",
                        "success": False,
                        "message": "Platform is required"
                    })
                    continue

                try:
                    print("debug 2")
                    # Check if social media context exists
                    query = f"""
                        SELECT id, latest_posts FROM 
                        public.tenant_socialmedia 
                        WHERE tenant_id = {self.tenant_id} 
                        AND platform = '{platform}' 
                        AND deleted_on IS NULL
                    """
                    existing = db_instance.retrieveSQLQueryOld(query)
                    existing_bool = len(existing) > 0

                    if existing_bool:
                        # Handle latest_posts
                        latest_posts = existing[0]["latest_posts"] if existing_bool and existing[0].get("latest_posts") else []
                        if isinstance(latest_posts, str):
                            latest_posts = json.loads(latest_posts)
                    else:
                        latest_posts = []
                    # if document_id:
                    #     latest_posts.append({"document_id": document_id})

                    if existing_bool:
                        update_query = """
                            UPDATE public.tenant_socialmedia
                            SET handle = %s, latest_posts = %s, last_updated = %s, updated_by_id = %s, updated_on = %s
                                WHERE tenant_id = %s AND platform = %s AND deleted_on IS NULL;
                        """
                        db_instance.executeSQLQuery(
                            update_query,
                            (
                                social_media.get("handle", ""),
                                json.dumps((social_media.get("latest_posts", []) or []) + latest_posts),
                                current_time,
                                self.user_id,
                                current_time,
                                self.tenant_id,
                                platform
                            )
                        )
                        results.append({
                            "platform": platform,
                            "success": True,
                            "message": f"Successfully updated social media context for platform {platform}"
                        })
                    else:
                        insert_query = """
                            INSERT INTO public.tenant_socialmedia
                            (tenant_id, platform, handle, latest_posts, last_updated, created_by_id, updated_by_id, created_on, updated_on)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        db_instance.executeSQLQuery(
                            insert_query,
                            (
                                self.tenant_id,
                                platform,
                                social_media.get("handle", ""),
                                json.dumps(social_media.get("latest_posts", []) + latest_posts),
                                current_time,
                                self.user_id,
                                self.user_id,
                                current_time,
                                current_time
                            )
                        )
                        results.append({
                            "platform": platform,
                            "success": True,
                            "message": f"Successfully inserted social media context for platform {platform}"
                        })

                except Exception as e:
                    appLogger.error({
                        "function": "store_social_media_context",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "tenant_id": self.tenant_id,
                        "platform": platform
                    })
                    results.append({
                        "platform": platform,
                        "success": False,
                        "message": f"Error storing social media context for platform {platform}: {str(e)}"
                    })

            return results

        except Exception as e:
            appLogger.error({
                "function": "store_social_media_context",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "message": f"Error processing social media contexts: {str(e)}",
                "success": False,
                "results": []
            }

    @log_function_io_and_time
    def store_competitor_context(self, params: Optional[List[Dict]] = [DEFAULT_COMPETITOR_CONTEXT_PARAMS]) -> Dict:
        """
        Stores or updates multiple competitor contexts in tenant_competitor table.
        """
        try:
            results = []
            current_time = datetime.now()

            for competitor in params:
                competitor = competitor.copy()
                name = competitor.get("name", "")
                doc_ids = competitor.get("doc_s3_keys", [])
                competitor_company_url = competitor.get("company_url") or ""
                if not name:
                    results.append({
                        "competitor": name or "unnamed",
                        "success": False,
                        "message": "Competitor name is required"
                    })
                    continue

                query = f"""
                    SELECT id FROM public.tenant_competitor WHERE tenant_id = {self.tenant_id} AND name = '{name}'
                    AND deleted_on IS NULL
                """
                existing = db_instance.retrieveSQLQueryOld(query)
                existing = len(existing) > 0

                try:
                    if existing:
                        update_query = """
                            UPDATE public.tenant_competitor
                            SET summary = %s, recent_news = %s, financials = %s, citations = %s, doc_ids = %s,
                                updated_by_id = %s, updated_on = %s
                            WHERE tenant_id = %s AND name = %s AND company_url = %s AND deleted_on IS NULL;
                        """
                        db_instance.executeSQLQuery(
                            update_query,
                            (
                                competitor.get("summary", ""),
                                json.dumps(competitor.get("recent_news", [])),
                                json.dumps(competitor.get("financials", {})),
                                json.dumps(competitor.get("citations", [])),
                                json.dumps(doc_ids),
                                self.user_id,
                                current_time,
                                self.tenant_id,
                                name,
                                competitor_company_url
                            )
                        )
                        results.append({
                            "competitor": name,
                            "success": True,
                            "message": f"Successfully updated competitor context for {name}"
                        })
                    else:
                        insert_query = """
                            INSERT INTO public.tenant_competitor
                            (tenant_id, name, summary, recent_news, financials, citations, doc_ids, company_url,
                            created_by_id, updated_by_id, created_on, updated_on)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """
                        db_instance.executeSQLQuery(
                            insert_query,
                            (
                                self.tenant_id,
                                name,
                                competitor.get("summary", ""),
                                json.dumps(competitor.get("recent_news", [])),
                                json.dumps(competitor.get("financials", {})),
                                json.dumps(competitor.get("citations", [])),
                                json.dumps(doc_ids),
                                competitor_company_url,
                                self.user_id,
                                self.user_id,
                                current_time,
                                current_time
                            )
                        )
                        results.append({
                            "competitor": name,
                            "success": True,
                            "message": f"Successfully inserted competitor context for {name}"
                        })
                        
                except Exception as e:
                    appLogger.error({
                        "function": "store_competitor_context",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "tenant_id": self.tenant_id,
                        "competitor": name
                    })
                    results.append({
                        "competitor": name,
                        "success": False,
                        "message": f"Error storing competitor context for {name}: {str(e)}"
                    })

            return {
                "message": f"Processed competitor contexts for tenant {self.tenant_id}",
                "success": True,
                "results": results
            }

        except Exception as e:
            appLogger.error({
                "function": "store_competitor_context",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "message": f"Error processing competitor contexts: {str(e)}",
                "success": False,
                "results": []
            }

    @log_function_io_and_time
    def store_performance_context(self, params: Optional[Dict] = DEFAULT_PERFORMANCE_CONTEXT_PARAMS) -> Dict:
        """
        Stores or updates company performance context in tenant_companyperformance table.
        """
        try:
            params = params.copy()
            period = params.get("period", "")
            doc_ids = params.get("doc_s3_keys", [])
            current_time = datetime.now()

            query = f"""
                SELECT id FROM public.tenant_companyperformance 
                WHERE tenant_id = {self.tenant_id} AND period = '{period}' AND deleted_on IS NULL
            """
            existing = db_instance.retrieveSQLQueryOld(query)
            existing = len(existing) > 0

            if existing:
                update_query = """
                    UPDATE public.tenant_companyperformance
                    SET revenue = %s, profit = %s, funding_raised = %s, investor_info = %s, citations = %s, doc_ids = %s,
                        updated_by_id = %s, updated_on = %s
                    WHERE tenant_id = %s AND period = %s AND deleted_on IS NULL;
                """
                db_instance.executeSQLQuery(
                    update_query,
                    (
                        params.get("revenue"),
                        params.get("profit"),
                        params.get("funding_raised"),
                        json.dumps(params.get("investor_info", [])),
                        json.dumps(params.get("citations", [])),
                        json.dumps(doc_ids),
                        self.user_id,
                        current_time,
                        self.tenant_id,
                        period
                    )
                )
            else:
                insert_query = """
                    INSERT INTO public.tenant_companyperformance
                    (tenant_id, period, revenue, profit, funding_raised, investor_info, citations, doc_ids,
                     created_by_id, updated_by_id, created_on, updated_on)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                db_instance.executeSQLQuery(
                    insert_query,
                    (
                        self.tenant_id,
                        period,
                        params.get("revenue"),
                        params.get("profit"),
                        params.get("funding_raised"),
                        json.dumps(params.get("investor_info", [])),
                        json.dumps(params.get("citations", [])),
                        json.dumps(doc_ids),
                        self.user_id,
                        self.user_id,
                        current_time,
                        current_time
                    )
                )

            return {
                "message": f"Successfully stored performance context for tenant {self.tenant_id} and period {period}",
                "success": True
            }

        except Exception as e:
            appLogger.error({
                "function": "store_performance_context",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {"message": f"Error storing performance context: {str(e)}", "success": False}

    @log_function_io_and_time
    def map_excel_columns(self, params: Optional[Dict] = DEFAULT_MAP_EXCEL_PARAMS) -> Dict:
        """
        Map Excel or CSV columns to predefined fields for project, potential, or roadmap files.
        Uses FileAnalyzer to fetch file data and create_mapping to generate column mappings.
        Supports selecting a specific sheet for Excel files.
        """
        try:
            # Copy params to avoid modifying the original
            params = params.copy() if params else DEFAULT_MAP_EXCEL_PARAMS.copy()
            file_type = params.get("type", "").lower()
            s3_key = params.get("s3_key", "")
            user_input = params.get("user_input", "")
            sheet_name = params.get("name_of_sheet_to_process", None)
            user_satisfied = params.get("user_satisfied_with_your_provided_mapping", False) or False
            user_wants_more_modifications = params.get("user_wants_more_modifications", True)

            # Debug logging
            print(f"[MAP_EXCEL_COLUMNS] Starting with params:")
            print(f"  - file_type: {file_type}")
            print(f"  - s3_key: {s3_key}")
            print(f"  - sheet_name: {sheet_name}")
            print(f"  - user_input: {user_input}")
            print(f"  - user_satisfied: {user_satisfied}")
            print(f"  - user_wants_more_modifications: {user_wants_more_modifications}")

            # Validate inputs
            if not s3_key:
                print("[MAP_EXCEL_COLUMNS] ERROR: No S3 key provided")
                return {
                    'error': 'No S3 key provided for file mapping',
                    'needs_clarification': True,
                    'clarification_question': 'Please upload a spreadsheet file first.'
                }

            if not file_type:
                print("[MAP_EXCEL_COLUMNS] ERROR: No file type provided")
                return {
                    'error': 'No file type provided for mapping',
                    'needs_clarification': True,
                    'clarification_question': 'Please specify the file type (project, potential, or roadmap).'
                }

            if file_type not in list(SCHEMAS.keys()):
                print(f"[MAP_EXCEL_COLUMNS] ERROR: Invalid file type: {file_type}")
                return {
                    'error': f'File type "{file_type}" is not supported. Supported types: project, potential, roadmap, project_update.',
                    'needs_clarification': True,
                    'clarification_question': f'Please specify a valid file type (project, potential, roadmap, project_update) instead of "{file_type}".'
                }

            # Fetch file data using FileAnalyzer
            print(f"[MAP_EXCEL_COLUMNS] Fetching file data for S3 key: {s3_key}")
            file_data = self.file_analyzer.analyze_files({"files_s3_keys_to_read": [s3_key]})
            print(f"[MAP_EXCEL_COLUMNS] FileAnalyzer result: {file_data.keys()}")

            # Check if file data was retrieved
            if not file_data.get('files', []):
                print("[MAP_EXCEL_COLUMNS] ERROR: No file data retrieved")
                return {
                    'error': f'Could not retrieve file data for S3 key: {s3_key}',
                    'needs_clarification': True,
                    'clarification_question': 'Could you verify that the file exists in S3 and try again?'
                }

            file_info = file_data['files'][0]
            # print(f"[MAP_EXCEL_COLUMNS] File info: {file_info}")

            # Check for errors in file retrieval
            if file_info.get('error'):
                print(f"[MAP_EXCEL_COLUMNS] ERROR: FileAnalyzer error: {file_info['error']}")
                return {
                    'error': file_info['error'],
                    'needs_clarification': True,
                    'clarification_question': 'There was an issue reading your spreadsheet. Could you verify the file format and try again?'
                }

            # Verify file type is CSV or Excel
            if file_info['file_type'] not in ['csv', 'xlsx']:
                print(f"[MAP_EXCEL_COLUMNS] ERROR: Unsupported file type: {file_info['file_type']}")
                return {
                    'error': f'File type "{file_info["file_type"]}" is not a spreadsheet. Only CSV and Excel files are supported.',
                    'needs_clarification': True,
                    'clarification_question': 'Please upload a CSV or Excel file for column mapping.'
                }

            # Get analysis and DataFrame
            analysis = file_info.get('analysis', {})
            if not analysis or analysis.get('error'):
                print(f"[MAP_EXCEL_COLUMNS] ERROR: Analysis error: {analysis.get('error', 'No analysis data')}")
                return {
                    'error': analysis.get('error', 'Could not analyze file structure'),
                    'needs_clarification': True,
                    'clarification_question': 'Could not analyze the spreadsheet structure. Please verify the file content and try again.'
                }

            # Handle sheet selection
            sheets = analysis.get('sheets', [])
            if not sheets:
                print("[MAP_EXCEL_COLUMNS] ERROR: No sheets found in file")
                return {
                    'error': 'No sheets found in the spreadsheet',
                    'needs_clarification': True,
                    'clarification_question': 'The file does not contain any valid sheets. Please upload a valid spreadsheet.'
                }

            # Select sheet based on user input or default to first sheet
            if file_info['file_type'] == 'xlsx' and len(sheets) > 1 and not sheet_name:
                sheet_names = [sheet['sheet_name'] for sheet in sheets]
                print(f"[MAP_EXCEL_COLUMNS] WARNING: Multiple sheets found but no sheet_name specified. Sheets: {sheet_names}")
                return {
                    'error': 'Multiple sheets found in Excel file',
                    'needs_clarification': True,
                    'clarification_question': f'Please specify a sheet name to map. Available sheets: {", ".join(sheet_names)}'
                }

            selected_sheet = None
            if sheet_name:
                for sheet in sheets:
                    if sheet['sheet_name'].lower() == sheet_name.lower():
                        selected_sheet = sheet
                        break
                if not selected_sheet:
                    sheet_names = [sheet['sheet_name'] for sheet in sheets]
                    print(f"[MAP_EXCEL_COLUMNS] ERROR: Specified sheet '{sheet_name}' not found. Available sheets: {sheet_names}")
                    return {
                        'error': f'Sheet "{sheet_name}" not found in the file',
                        'needs_clarification': True,
                        'clarification_question': f'Please specify a valid sheet name. Available sheets: {", ".join(sheet_names)}'
                    }
            else:
                selected_sheet = sheets[0]  # Default to first sheet
                sheet_name = selected_sheet['sheet_name']
                print(f"[MAP_EXCEL_COLUMNS] Using default sheet: {sheet_name}")

            # Get DataFrame from FileAnalyzer
            df_dict = self.s3_service.download_file_as_pd_v2(s3_key, filename=file_info['filename'])
            df = df_dict.get(sheet_name, pd.DataFrame())
            if df is None or df.empty:
                print(f"[MAP_EXCEL_COLUMNS] ERROR: DataFrame for sheet '{sheet_name}' is empty or invalid")
                return {
                    'error': f'No valid data found in sheet "{sheet_name}"',
                    'needs_clarification': True,
                    'clarification_question': 'The selected sheet is empty or invalid. Please verify the sheet content or select another sheet.'
                }

            print(f"[MAP_EXCEL_COLUMNS] DataFrame loaded for sheet '{sheet_name}': {df.shape} (rows, columns)")
            # print(f"[MAP_EXCEL_COLUMNS] Columns: {list(df.columns)}")

            # Log successful data loading
            detailed_activity(
                "trucible_mapping_data_loaded",
                f"Successfully loaded DataFrame for sheet '{sheet_name}' with {df.shape[0]} rows and {df.shape[1]} columns",
                user_id=self.user_id
            )

            # Get target fields from schema
            target_fields = SCHEMAS.get(file_type, [])
            if not target_fields:
                print(f"[MAP_EXCEL_COLUMNS] ERROR: No schema found for file type '{file_type}'")
                return {
                    'error': f'No field schema found for type "{file_type}"',
                    'available_types': list(SCHEMAS.keys()),
                    'needs_clarification': True,
                    'clarification_question': f'The file type "{file_type}" is not supported for mapping. Available types: {", ".join(SCHEMAS.keys())}'
                }

            # print(f"[MAP_EXCEL_COLUMNS] Target fields for {file_type}: {target_fields}")

            # Fetch context for mapping
            print(f"[MAP_EXCEL_COLUMNS] Fetching context from TangoDao")
            context = TangoDao.fetchTangoStatesForUserIdKeyandSession(
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                session_id=self.session_id
            )
            # print(f"[MAP_EXCEL_COLUMNS] Context: {context}")

            # Call create_mapping
            print(f"[MAP_EXCEL_COLUMNS] Calling create_mapping with user_input: '{user_input}'")
            mapping_result = create_mapping(
                FIELDS=target_fields,
                data=df,
                clarifying_information=user_input,
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                file_type_lower=file_type,
                mode="all" if user_satisfied else "preview",
                context=context,
                filename=file_info['filename']
            )

            # print(f"[MAP_EXCEL_COLUMNS] Mapping result: {mapping_result}")

            # Store mapping in TangoDao
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                value=json.dumps(mapping_result.get("sheet_columns_to_fields_mapping", [])),
                session_id=self.session_id
            )

            # Log mapping completion
            detailed_activity(
                "trucible_mapping_completed",
                f"Column mapping completed for sheet '{sheet_name}' with result type: {mapping_result.get('type')}",
                user_id=self.user_id
            )
            return mapping_result
        
        except Exception as e:
            print(f"[MAP_EXCEL_COLUMNS] EXCEPTION: {str(e)}")
            appLogger.error({
                "function": "map_excel_columns",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'error': f'Failed to process mapping: {str(e)}',
                'needs_clarification': True,
                'clarification_question': 'There was an issue analyzing your spreadsheet. Could you verify the file format and try again?'
            }
     
    @log_function_io_and_time       
    def set_user_designation(self, params: Optional[Dict] = DEFAULT_SET_USER_DESIGNATION):
        """
            Stores or updates user designation. 
            To trigger this whenever user provides his/her designation
        """
        try:
            designation = params.get("designation")
            query = """
                UPDATE users_user
                SET position = %s
                WHERE id = %s
            """
            db_instance.executeSQLQuery(query, (designation, self.user_id))
            appLogger.info({
                "action": "set_user_designation",
                "user_id": self.user_id,
                "designation": designation
            })
        except Exception as e:
            appLogger.error({
                "action": "set_user_designation_failed",
                "error": str(e),
                "user_id": self.user_id
            })
            return f"Error occured while setting designation: {e} "
    
            
    @log_function_io_and_time
    def map_text(self, params: Optional[Dict] = DEFAULT_MAP_DOCS_PARAMS) -> Dict:
        """
        Maps content from text-based files (DOC, DOCX, PDF, TXT, PPT, PPTX) to schema fields.
        Identifies single or multiple items (projects, roadmaps, potentials, project_updates) based on user-specified number and schedules creation.

        Args:
            params (dict):
                type (str): One of "project", "roadmap", "potential", "project_update". Determines which schema is used for mapping.
                s3_keys (list[str]): S3 keys for files to process.
                user_input (str): Optional user clarification or context.
                user_wants_more_modifications (bool): If True, mapping is previewed before scheduling.
                user_satisfied_with_your_provided_mapping (bool): If True, mapping is scheduled immediately.
                num_items (int or str): Number of items to extract (default: 1).

        Returns:
            dict: Mapping results, errors, or clarification prompts.

        Type options:
            - "project"
            - "roadmap"
            - "potential"
            - "project_update"
        """
        try:
            params = params.copy() if params else {}
            s3_keys = params.get("s3_keys") or []
            file_type = params.get("type", "").lower()
            num_items = params.get("num_items") or params.get("num_projects") or 1
            user_input = params.get("user_input", "")
            user_satisfied = params.get("user_satisfied_with_your_provided_mapping", False)
            user_wants_more_modifications = params.get("user_wants_more_modifications", True)

            print(f"[MAP_TEXT] Starting with params:")
            print(f"  - s3_keys: {s3_keys}")
            print(f"  - file_type: {file_type}")
            print(f"  - num_items: {num_items}")
            print(f"  - user_input: {user_input}")
            print(f"  - user_satisfied: {user_satisfied}")
            print(f"  - user_wants_more_modifications: {user_wants_more_modifications}")

            if not s3_keys:
                print("[MAP_TEXT] ERROR: No S3 keys provided")
                return {
                    'error': 'No S3 keys provided for text file mapping',
                    'needs_clarification': True,
                    'clarification_question': 'Please upload one or more text-based files (DOC, DOCX, PDF, TXT, PPT, PPTX).'
                }

            if not file_type:
                print("[MAP_TEXT] ERROR: No file type provided")
                return {
                    'error': 'No file type provided for mapping',
                    'needs_clarification': True,
                    'clarification_question': 'Please specify the file type (project, roadmap, or potential).'
                }

            if file_type not in list(SCHEMAS.keys()):
                print(f"[MAP_TEXT] ERROR: Invalid file type: {file_type}")
                return {
                    'error': f'File type "{file_type}" is not supported. Supported types: project, roadmap, potential, project_update.',
                    'needs_clarification': True,
                    'clarification_question': f'Please specify a valid file type (project, roadmap, potential, project_update).'
                }

            print(f"[MAP_TEXT] Fetching file data for S3 keys: {s3_keys}")
            file_data = self.file_analyzer.analyze_files({"files_s3_keys_to_read": s3_keys})

            if not file_data.get('files', []):
                print("[MAP_TEXT] ERROR: No file data retrieved")
                return {
                    'error': f'Could not retrieve file data for S3 keys: {s3_keys}',
                    'needs_clarification': True,
                    'clarification_question': 'Could you verify that the files exist in S3 and try again?'
                }

            # Validate file types (only DOC, DOCX, PDF, TXT, PPT, PPTX)
            valid_file_types = ['txt', 'doc', 'docx', 'pdf', 'ppt', 'pptx']
            text_contents = []
            for file_info in file_data['files']:
                if file_info.get('error'):
                    print(f"[MAP_TEXT] ERROR: FileAnalyzer error for {file_info['file_s3_key']}: {file_info['error']}")
                    return {
                        'error': file_info['error'],
                        'needs_clarification': True,
                        'clarification_question': 'There was an issue reading one of the files. Could you verify the file format and try again?'
                    }
                if file_info['file_type'] not in valid_file_types:
                    print(f"[MAP_TEXT] ERROR: Unsupported file type: {file_info['file_type']}")
                    return {
                        'error': f'File type "{file_info["file_type"]}" is not supported. Only DOC, DOCX, PDF, TXT, PPT, and PPTX are supported.',
                        'needs_clarification': True,
                        'clarification_question': 'Please upload only DOC, DOCX, PDF, TXT, PPT, or PPTX files.'
                    }
                text_contents.append({
                    'filename': file_info['filename'],
                    's3_key': file_info['file_s3_key'],
                    'content': file_info['content'],
                    'analysis': file_info['analysis']
                })

            print(f"[MAP_TEXT] Retrieved {len(text_contents)} valid text files")

            target_fields = SCHEMAS.get(file_type, [])
            if not target_fields:
                print(f"[MAP_TEXT] ERROR: No schema found for file type '{file_type}'")
                return {
                    'error': f'No field schema found for type "{file_type}"',
                    'available_types': list(SCHEMAS.keys()),
                    'needs_clarification': True,
                    'clarification_question': f'The file type "{file_type}" is not supported for mapping. Available types: {", ".join(SCHEMAS.keys())}'
                }

            print(f"[MAP_TEXT] Fetching context from TangoDao")
            context = TangoDao.fetchTangoStatesForUserIdKeyandSession(
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                session_id=self.session_id
            )

            print(f"[MAP_TEXT] Calling create_text_mapping for {num_items} {file_type}s")
            mapping_result = create_text_mapping(
                FIELDS=target_fields,
                text_contents=text_contents,
                num_items=num_items,
                clarifying_information=user_input,
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                file_type_lower=file_type,
                mode="all" if user_satisfied else "preview",
                context=context
            )

            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                value=json.dumps(mapping_result.get("project_mappings", [])),
                session_id=self.session_id
            )

            detailed_activity(
                "trucible_text_mapping_completed",
                f"Project mapping completed for {len(text_contents)} text files with {num_items} items",
                user_id=self.user_id
            )

            return mapping_result

        except Exception as e:
            print(f"[MAP_TEXT] EXCEPTION: {str(e)}")
            appLogger.error({
                "function": "map_text",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'error': f'Failed to process text mapping: {str(e)}',
                'needs_clarification': True,
                'clarification_question': 'There was an issue analyzing your text files. Could you verify the file format and try again?'
            }
    
    
    @log_function_io_and_time
    def _match_industry_with_llm(self, industry_data: Dict) -> Optional[int]:
        """
        Uses LLM to match an industry based on name, trends, value_chain, and KPIs.

        Args:
            industry_data (dict): Contains name, trends, value_chain, function_kpis.

        Returns:
            int or None: Matched industry ID or None if no match.
        """
        try:
            # Fetch existing industries
            query = """
                SELECT id, name, trends, value_chain, function_kpis 
                FROM public.tenant_industry 
                WHERE deleted_on IS NULL
            """
            existing_industries = db_instance.retrieveSQLQueryOld(query)

            # Prepare context for LLM
            context = {
                "provided_industry": {
                    "name": industry_data.get("name", ""),
                    "trends": industry_data.get("trends", []),
                    "value_chain": industry_data.get("value_chain", []),
                    "function_kpis": industry_data.get("function_kpis", {})
                },
                "existing_industries": existing_industries
            }

            # LLM system prompt
            system_prompt = f"""
                You are {self.agent_name}, a strategic consultant created by Trmeric.
                Your task is to match a provided industry to an existing industry based on name, trends, value chain, and KPIs.
                Return the ID of the best-matching industry or null if no match is found.

                Context:
                {json.dumps(context, indent=2)}

                Guidelines:
                - Compare the provided industry name, trends, value chain, and KPIs with existing industries.
                - Use semantic similarity (e.g., similar terms, synonyms, or overlapping concepts) for matching.
                - Prioritize exact or near-exact name matches, then check trends, value chain, and KPIs for confirmation.
                - If no match is found (similarity below 80%), return null.
                - Return JSON with the matched industry ID or null.

                Return JSON:
                ```json
                {{"industry_id": <id or null>}}
                ```
            """

            model_options = ModelOptions(model="gpt-4.1", max_tokens=1000, temperature=0.3)
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user="Match the provided industry to an existing one and output in proper JSON")
            output = self.llm.run(chat_completion, model_options, function_name="match_industry", logInDb=self.logInfo)
            result = extract_json_after_llm(output)

            return result.get("industry_id")

        except Exception as e:
            appLogger.error({
                "function": "_match_industry_with_llm",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return None

    @log_function_io_and_time
    def store_company_industry_mapping(self, params: Optional[CompanyIndustryMappingParams] = None) -> Dict:
        """
        Stores or updates industry and company-industry mapping using SQL queries.
        its very important to only send non empty items (this is industry of the company and this knowledge is very important for trmeric)
        Uses LLM to match industries; creates industry only if no match exists.

        Returns:
            dict: Response with success status, message, and industry_id.
        """
        try:
            # Default params
            if params is None:
                params = CompanyIndustryMappingParams()
            else:
                params = CompanyIndustryMappingParams(**params)

            print("params ", params)
            
            
            industry_info = params.industry_info
            citations = params.citations
            current_time = datetime.now()

            # Validate industry name
            if not industry_info.name:
                return {
                    "message": "Industry name is required",
                    "success": False
                }

            # Step 1: Match or create industry
            # Check if industry exists by name
            query = f"""
                SELECT id FROM public.tenant_industry
                WHERE name = '{industry_info.name}' AND deleted_on IS NULL
            """
            existing = db_instance.retrieveSQLQueryOld(query)
            industry_id = None
            if len(existing) > 0:
                industry_id = existing[0]["id"] if existing else None

            print("debug 1 -- ind id ", industry_id)
            if not industry_id:
                # Use LLM to match industry
                industry_id = self._match_industry_with_llm(industry_info)
                print("debug 2 -- ind id ", industry_id)
                if not industry_id:
                    # Insert new industry
                    insert_query = """
                        INSERT INTO public.tenant_industry
                        (name, trends, value_chain, function_kpis, created_by_id, updated_by_id, created_on, updated_on)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id;
                    """
                    result = db_instance.executeSQLQuery(
                        insert_query,
                        (
                            industry_info.name,
                            json.dumps(industry_info.trends),
                            json.dumps(industry_info.value_chain),
                            json.dumps(industry_info.function_kpis),
                            self.user_id,
                            self.user_id,
                            current_time,
                            current_time
                        ),
                        fetch="one"
                    )
                    industry_id = result[0]
                    appLogger.info({
                        "function": "store_company_industry_mapping",
                        "message": f"Created new industry: {industry_info.name}",
                        "tenant_id": self.tenant_id
                    })

            # Step 2: Store or update company-industry mapping
            query = f"""
                SELECT id FROM public.tenant_companyindustry
                WHERE tenant_id = {self.tenant_id} AND industry_id = {industry_id} AND deleted_on IS NULL
            """
            existing = db_instance.retrieveSQLQueryOld(query)
            
            print("debug 3 -- ind id ", existing)
            existing = len(existing) > 0

            if not existing:
                insert_query = """
                    INSERT INTO public.tenant_companyindustry
                    (tenant_id, industry_id, citations, created_by_id, updated_by_id, created_on, updated_on)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                db_instance.executeSQLQuery(
                    insert_query,
                    (
                        self.tenant_id,
                        industry_id,
                        json.dumps([citation.model_dump() for citation in citations]) if citations else None,
                        self.user_id,
                        self.user_id,
                        current_time,
                        current_time
                    )
                )
            else:
                update_query = """
                    UPDATE public.tenant_companyindustry
                    SET citations = %s, updated_by_id = %s, updated_on = %s
                    WHERE tenant_id = %s AND industry_id = %s AND deleted_on IS NULL;
                """
                db_instance.executeSQLQuery(
                    update_query,
                    (
                        json.dumps([citation.model_dump() for citation in citations]) if citations else None,
                        self.user_id,
                        current_time,
                        self.tenant_id,
                        industry_id
                    )
                )

            return {
                "message": f"Successfully stored company-industry mapping for tenant {self.tenant_id} and industry {industry_id}",
                "success": True,
                "industry_id": industry_id
            }

        except Exception as e:
            appLogger.error({
                "function": "store_company_industry_mapping",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "message": f"Error storing company-industry mapping: {str(e)}",
                "success": False
            }
            
    @log_function_io_and_time
    def update_project(self, params: Optional[Dict] = None) -> Dict:
        """Validate project updates and schedule a job (no inline execution)."""
        try:
            params = params.copy() if params else {}
            mapped_data = params.get("mapped_data", [])
            if not mapped_data:
                return {
                    'error': 'No project data provided',
                    'needs_clarification': True,
                    'clarification_question': 'Please provide project updates with appropriate fields defined by the schema.'
                }
            
            # Minimal validation - just ensure mapped_data is a list
            if isinstance(mapped_data, dict):
                mapped_data = [mapped_data]
            elif not isinstance(mapped_data, list):
                mapped_data = []
            
            # No specific field validation - expect schema-compliant data
            validated_data = []
            for update_data in mapped_data:
                if isinstance(update_data, dict) and update_data:  # Basic dict check
                    validated_data.append(update_data)
            
            if not validated_data:
                return {
                    'error': 'No valid project update data found',
                    'needs_clarification': True,
                    'clarification_question': 'Please provide valid project update data.'
                }
            
            run_id = f"project_update-direct-{self.tenant_id}-{self.user_id}-{uuid.uuid4()}"
            job_dao = JobDAO
            socket_id = None
            try:
                socket_id = UserSocketMap.get_client_id(str(self.user_id))
            except Exception:
                pass
            if not socket_id:
                try:
                    ps = ProgramState.get_instance(self.user_id)
                    if isinstance(ps, dict):
                        socket_id = ps.get("socket_id")
                except Exception:
                    socket_id = None
            payload = {
                "job_type": "update-project",
                "run_id": run_id,
                "total_count": len(validated_data),
                "mapped_data": validated_data,
                "socket_id": socket_id,
                "creator_source": "trucible_direct_input"
            }
            job_id = job_dao.create(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                schedule_id=None,
                job_type="update-project",
                payload=payload

            )
            detailed_activity(
                user_id=self.user_id,
                activity_name="trucible_project_update_scheduled",
                activity_description=f"Scheduled {len(validated_data)} project updates (job_id: {job_id}, run_id: {run_id})"
            )
            return {
                'success': True,
                'mode': 'scheduled',
                'message': f'Successfully scheduled {len(validated_data)} project updates for processing (no inline execution).',
                'job_id': job_id,
                'run_id': run_id,
                'total_updates': len(validated_data)
            }
        except Exception as e:
            appLogger.error({
                "function": "update_project",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'error': f'Failed to schedule project updates: {str(e)}',
                'needs_clarification': True,
                'clarification_question': 'There was an issue scheduling the updates. Please try again.'
            }
    
    
    
    @log_function_io_and_time
    def map_from_conversation(self, params: Optional[Dict] = DEFAULT_MAP_CONV_PARAMS) -> Dict:
        """
        Maps user-provided typed/conversational text to a schema and schedules creation.
        No file upload required — works entirely from user_detailed_input.
        
        Params:
            type (str): one of project | roadmap | potential | project_update | idea_creation_schema
            user_detailed_input (str): the typed text describing the record(s)
            num_items (int): how many records to extract (default 1)
            user_satisfied_with_your_provided_mapping (bool): if True, schedules jobs
            user_wants_more_modifications (bool): if True, returns preview only
        """
        try:
            params = params.copy() if params else {}
            file_type = params.get("type", "").lower()
            user_input = params.get("user_detailed_input", "")
            num_items = params.get("num_items") or params.get("num_projects") or 1
            user_satisfied = params.get("user_satisfied_with_your_provided_mapping", False)
            user_wants_more_modifications = params.get("user_wants_more_modifications", True)

            print(f"[MAP_FROM_CONVERSATION] Starting with params:")
            print(f"  - file_type: {file_type}")
            print(f"  - num_items: {num_items}")
            print(f"  - user_input: {user_input[:100]}...")
            print(f"  - user_satisfied: {user_satisfied}")
            print(f"  - user_wants_more_modifications: {user_wants_more_modifications}")

            if not user_input:
                return {
                    'error': 'No input text provided',
                    'needs_clarification': True,
                    'clarification_question': 'Please describe the data you want to store.'
                }

            if not file_type or file_type not in list(SCHEMAS.keys()):
                return {
                    'error': f'Invalid or missing type. Supported: {", ".join(SCHEMAS.keys())}',
                    'needs_clarification': True,
                    'clarification_question': f'Please specify a valid type: {", ".join(SCHEMAS.keys())}'
                }

            schema_dict = SCHEMAS.get(file_type, {})
            schema_fields = list(schema_dict.keys())
            schema_types = {k: v for k, v in schema_dict.items()}

            context = TangoDao.fetchTangoStatesForUserIdKeyandSession(
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                session_id=self.session_id
            )

            mode = "all" if user_satisfied else "preview"

            SYSTEM_PROMPT = f"""
                You are an expert data extractor. The user has typed a description of one or more {file_type} records.
                Your job is to extract structured data from their text and map it to the schema fields.

                Schema fields:
                {MyJSON.dumps(schema_dict, indent=2)}

                Rules:
                - Extract exactly num_items records from the input
                - For each record, map all available information to schema fields
                - If a field cannot be determined from the input, use "" or []
                - Do not invent data — only use what the user provided
                - If critical fields are missing, ask in clarification_question

                Output Format:
                ```json
                {{
                    "thought_process": "",
                    "clarification_question": "",
                    "item_mappings": [
                        {{
                            "field1": "value1",
                            "field2": "value2"
                        }},...
                    ]
                }}
                ```
            """

            user_prompt = MyJSON.dumps({
                "user_input": user_input,
                "num_items": num_items,
                "file_type": file_type,
                "schema_fields": schema_fields,
                "all_planning_context": context
            })

            model_options = ModelOptions(
                model="gpt-4.1",
                temperature=0.1,
                max_tokens=10000
            )
            llm = ChatGPTClient(user_id=self.user_id, tenant_id=self.tenant_id)
            chat_completion = ChatCompletion(
                system=SYSTEM_PROMPT,
                prev=[],
                user=user_prompt
            )
            response = llm.run(
                chat_completion,
                model_options,
                'super::trucible::conv::mapping',
                logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
            )
            print(f"[MAP_FROM_CONVERSATION] LLM response: {response[:200]}")
            mappings = extract_json_after_llm(response)

            if not mappings.get("item_mappings"):
                return {
                    'error': 'Could not extract structured data from input',
                    'needs_clarification': True,
                    'clarification_question': mappings.get("clarification_question") or
                        f'Could not identify {file_type} data from your description. Could you provide more detail?'
                }

            # Store context
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=f"{self.agent_name}_planning",
                value=json.dumps(mappings.get("item_mappings", [])),
                session_id=self.session_id
            )

            scheduling_message = ''
            if mode == 'all':
                run_id = f"{file_type}-creation-{self.tenant_id}-{self.user_id}-{uuid.uuid4()}"
                job_dao = JobDAO
                job_type = f"create-{file_type}"

                for item in mappings["item_mappings"]:
                    payload = {
                        "job_type": job_type,
                        "run_id": run_id,
                        "total_count": len(mappings["item_mappings"]),
                        "data": item,
                        "extra_data": {},
                        "original_used_data": item,
                        "socket_id": ProgramState.get_instance(self.user_id).get("socket_id"),
                        "filename": "conversation_input",
                        "creator_source": "trucible",
                        "mode": "conv"
                    }
                    job_dao.create(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        schedule_id=None,
                        job_type=job_type,
                        payload=payload
                    )

                scheduling_message = f"All items have been scheduled for {file_type} creation"

            return {
                "item_mappings": mappings.get("item_mappings", []),
                "clarification_question": mappings.get("clarification_question", ""),
                "mode": mode,
                "scheduling_message": scheduling_message,
                "formatted_results_according_to_mapping": mappings.get("item_mappings", [])[:2]
            }

        except Exception as e:
            print(f"[MAP_FROM_CONVERSATION] EXCEPTION: {str(e)}")
            appLogger.error({
                "function": "map_from_conversation",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'error': f'Failed to process conversation mapping: {str(e)}',
                'needs_clarification': True,
                'clarification_question': 'Something went wrong processing your input. Could you try again?'
            }
    