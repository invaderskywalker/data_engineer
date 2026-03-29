from typing import Dict, Optional, List
from src.api.logging.AppLogger import appLogger, debugLogger
import traceback
import pandas as pd
import json
from datetime import datetime
from src.database.dao import db_instance, TangoDao, RoadmapDao, ProjectsDaoV2, ProviderDao, TenantDaoV2
from src.services.journal.Activity import detailed_activity
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.services.journal.Vectors.ActivityOnboarding import format_transformation_summary_markdown, onboarding_summary
from ..helper.event_bus import event_bus
from ..schema import SCHEMAS
from ..actions.sheet_mapper_v2 import create_mapping
from ..actions.text_mapper import create_text_mapping
from src.s3.s3 import S3Service
from ..config.actions import *
from ..helper.file_analyser import FileAnalyzer
from src.s3.s3 import S3Service
from src.services.agents.functions.onboarding.creation_tools.AutonomousCreateRoadmap import RoadmapAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..helper.decorators import log_function_io_and_time
from src.ws.static import UserSocketMap
from src.api.logging.ProgramState import ProgramState
from src.utils.api import ApiUtils
from src.database.dao import JobDAO
import uuid
from src.services.agents_v2.actions.file_template import store_template_file,create_template_mapping

class DataActions:
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
            "store_company_context": self.store_company_context,
            "store_enterprise_strategy": self.store_enterprise_strategy,
            # "store_industry_context": self.store_industry_context,
            "store_company_industry_mapping": self.store_company_industry_mapping,
            "store_social_media_context": self.store_social_media_context,
            "store_competitor_context": self.store_competitor_context,
            "store_performance_context": self.store_performance_context,
            "store_company_orgstrategy": self.store_company_orgstrategy,
            "store_portfolio_context": self.store_portfolio_context,
            
            "map_excel_columns": self.map_excel_columns,
            "map_text": self.map_text,
            "update_project": self.update_project,
            
            "set_user_designation": self.set_user_designation,
            "find_suitable_service_provider": self.find_suitable_service_provider,
            
            "create_roadmaps_after_user_satisfaction": self.create_roadmaps,
            "present_ideas_as_ppt": self.present_ideas_as_ppt,
            "contact_providers_for_execution": self.contact_providers_for_execution,
            
            "generate_onboarding_report": self._generate_onboarding_report,
            "generate_and_save_template_file": self.generate_template_file,
            # "generate_report_from_template": self._generate_report_from_template,
        }
        
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
                    from src.services.chat_service.controller.portfolio import _add_portfolio_info
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
    
                
    # @log_function_io_and_time
    # def store_industry_context(self, params: Optional[Dict] = DEFAULT_INDUSTRY_CONTEXT_PARAMS) -> Dict:
    #     """
    #     Stores industry context in tenant_industry table.
    #     """
    #     try:
    #         params = params.copy()
    #         name = params.get("name") or ""
    #         current_time = datetime.now()

    #         if name:
    #             query = f"""
    #                 SELECT id FROM public.tenant_industry
    #                 WHERE name = '{name}' AND deleted_on IS NULL
    #             """
    #             existing = db_instance.retrieveSQLQueryOld(query)
    #         existing = len(existing) > 0

    #         industry_id = None
    #         if not existing:
    #             insert_query = """
    #                 INSERT INTO public.tenant_industry
    #                 (name, trends, value_chain, function_kpis, created_by_id, updated_by_id, created_on, updated_on)
    #                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    #                 RETURNING id;
    #             """
    #             result = db_instance.executeSQLQuery(
    #                 insert_query,
    #                 (
    #                     params.get("name", ""),
    #                     json.dumps(params.get("trends", [])),
    #                     json.dumps(params.get("value_chain", [])),
    #                     json.dumps(params.get("function_kpis", {})),
    #                     self.user_id,
    #                     self.user_id,
    #                     current_time,
    #                     current_time
    #                 ),
    #                 fetch="one"
    #             )
    #             industry_id = result

    #             self.store_company_industry_mapping({
    #                 "industry_id": industry_id[0], 
    #                 "citations": params.get("citations")
    #             })
    #         return {
    #             "message": f"Successfully stored industry context for tenant {self.tenant_id}",
    #             "success": True,
    #             "industry_id": industry_id
    #         }

    #     except Exception as e:
    #         appLogger.error({
    #             "function": "store_industry_context",
    #             "error": str(e),
    #             "traceback": traceback.format_exc(),
    #             "tenant_id": self.tenant_id
    #         })
    #         return {"message": f"Error storing industry context: {str(e)}", "success": False}

    # @log_function_io_and_time
    # def store_company_industry_mapping(self, params: Optional[Dict] = DEFAULT_COMPANY_INDUSTRY_MAPPING_PARAMS) -> Dict:
    #     """
    #     Stores the mapping between a tenant and an industry in tenant_companyindustry table.
    #     """
    #     try:
    #         params = params.copy()
    #         industry_id = params.get("industry_id")
    #         citations = params.get("citations")
            
    #         if not industry_id:
    #             return {"message": "Industry ID required to store company-industry mapping", "success": False}

    #         current_time = datetime.now()

    #         query = f"""
    #             SELECT id FROM public.tenant_companyindustry 
    #             WHERE tenant_id = {self.tenant_id} AND industry_id = {industry_id} AND deleted_on IS NULL
    #         """
    #         existing = db_instance.retrieveSQLQueryOld(query)
    #         existing = len(existing) > 0
            
    #         if not existing:
    #             insert_query = """
    #                 INSERT INTO public.tenant_companyindustry
    #                 (tenant_id, industry_id, citations, created_by_id, updated_by_id, created_on, updated_on)
    #                 VALUES (%s, %s, %s, %s, %s, %s, %s);
    #             """
    #             db_instance.executeSQLQuery(
    #                 insert_query,
    #                 (self.tenant_id, industry_id, json.dumps(citations) if citations else None, self.user_id, self.user_id, current_time, current_time)
    #             )

    #         return {
    #             "message": f"Successfully stored company-industry mapping for tenant {self.tenant_id} and industry {industry_id}",
    #             "success": True
    #         }

    #     except Exception as e:
    #         appLogger.error({
    #             "function": "store_company_industry_mapping",
    #             "error": str(e),
    #             "traceback": traceback.format_exc(),
    #             "tenant_id": self.tenant_id
    #         })
    #         return {"message": f"Error storing company-industry mapping: {str(e)}", "success": False}

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
    def find_suitable_service_provider(self, params: Optional[Dict] = DEFAULT_FIND_SUITABLE_PROVIDER_PARAMS):
        """
            Find the top 3 service providers from trmeric ecosystem
            for a roadmap or project or any idea description.
            
            Example:
                if user wants to find suitable provider for a roadmap or project
                set tag to roadmap or project respectively and 
                pass the roadmap id and project id respectively
                
                but if user wants to find suitable provider from trmeric ecosystem
                set tag to idea and describe the idea in the idea_description
        """
        try:
            roadmap_id = params.get("roadmap_id")
            project_id = params.get("project_id")
            tag = (params.get("tag") or "roadmap").lower()
            idea_description = params.get("idea_description")

            if not tag:
                raise ValueError("Unable to determine what user desires to find providers for")

            # Fetch roadmap or project details based on tag
            if tag == "roadmap" and roadmap_id:
                roadmap_data = RoadmapDao.fetchRoadmapDetails(roadmap_id=roadmap_id)
                context = roadmap_data[0]
            elif tag == "project" and project_id:
                project_data = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                    project_ids=[project_id],
                    projection_attrs=["id", "title", "description", "objectives", "key_results"]
                )
                context = project_data[0]
            else:
                context = idea_description

            # Fetch all provider skills
            all_skills_of_providers = ProviderDao.fetchAllDataFromServiceProviderDetailsTable()
            providers_data = [
                {
                    "service_provider_id": provider.get("service_provider_id"),
                    "primary_skills": (provider.get("primary_skills") or "").lower(),
                    "secondary_skills": (provider.get("secondary_skills") or "").lower(),
                    "other_skills": (provider.get("other_skills") or "").lower()
                }
                for provider in all_skills_of_providers
            ]

            # Check for exact skill matches
            selected_provider_ids = []
            model_options = ModelOptions(
                model="gpt-4.1",
                max_tokens=15000,
                temperature=0.1
            )
            

            
            prompt = f"""
                You are an expert in matching service providers to roadmap requirements based on their skills.
                The roadmap requires expertise in the following context:
                - {context}

                Below is a list of service providers with their skills:
                {json.dumps(providers_data, indent=2)}

                Analyze the roadmap context and compare it with each provider's primary_skills, 
                secondary_skills, and other_skills. Consider partial matches, synonyms, or related skills 
                (e.g., 'Python' might relate to 'Django' or 'data science').

                Return a JSON object with a list of up to 3 service provider IDs that are the best match, 
                along with a brief justification for each:
                ```json
                {{
                    "recommended_providers": [
                        {{
                            "service_provider_id": "provider_id",
                            "justification": "Reason why this provider is a good match"
                        }}
                    ]
                }}
                ```
            """
            
            chat_completion = ChatCompletion(system="", prev=[], user=prompt)
            # print("find suitable provider prompt ", chat_completion.formatAsString())
            output = self.llm.run(chat_completion, model_options, function_name="find_best_provider", logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id})
            print("find suitable provider prompt output ", output)
            response_json = extract_json_after_llm(output)
            selected_provider_ids = [p["service_provider_id"] for p in response_json.get("recommended_providers", [])]

            # Fetch detailed provider info and generate summary
            if selected_provider_ids:
                provider_info = ProviderDao.fetchDataForRecomendation(service_provider_ids=selected_provider_ids)
                provider_summary = ProviderDao.createProviderSummary(provider_info)
            else:
                provider_summary = "No suitable providers found."

            # Generate final ranking with LLM
            prompt = f"""
                You are an expert in ranking service providers for a roadmap.
                Roadmap Context:
                - {context}

                Provider Details:
                {json.dumps(provider_summary, indent=2)}

                Rank up to 3 providers based on their relevance to the roadmap context.
                Return a JSON object with the ranked providers:
                ```json
                {{
                    "ranks": [
                        {{
                            "rank": 1,
                            "service_provider_id": "service_provider_id",
                            "justification": "Reason for ranking"
                        }},...
                    ]
                }}
                ```
            """
            chat_completion = ChatCompletion(system="", prev=[], user=prompt)
            output = self.llm.run(chat_completion, model_options, function_name="rank_providers", logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id})
            response_json = extract_json_after_llm(output)
            print("find suitable provider prompt ranking output ", output)

            # Format result for action_results
            result = [
                {
                    "rank": int(item["rank"]),
                    "service_provider_id": item["service_provider_id"],
                    "justification": item["justification"]
                }
                for item in response_json.get("ranks", [])
            ]
            return json.dumps({"status": "success", "recommended_providers": result}, indent=2)

        except Exception as e:
            appLogger.error({
                "event": "find_best_provider_err",
                "function": "find_best_provider",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return f"Error finding providers: {str(e)}"

    @log_function_io_and_time
    def create_roadmaps(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_ROADMAPS_CREATION):
        """
            Automatically creates one or more roadmaps from natural language descriptions.
            Args:
                params (dict, optional): Parameters for roadmap creation. 
                    Expected keys:
                        - description_of_roadmaps_for_creation (list[str]): 
                        List of text descriptions for new roadmaps. Each entry 
                        should describe the purpose, scope, or goals of one roadmap.
                        
                        - user_satisfied_with_roadmap_plans:
                        only to assign true after user is happy with the roadmap plan
            Behavior:
                - Iterates over the provided roadmap descriptions.
                - Calls `RoadmapAgent().create_roadmap_from_text_input` for each description.
                - Executes roadmap creation in parallel using threads for efficiency.
                - Logs errors and returns either results or error details.
        """
        print("taking action create roadmap ---> ", params)
        description_of_roadmaps_for_creation = params.get("description_of_roadmaps_for_creation") or []
        
        def _create_single_roadmap(idea: str):
            try:
                return RoadmapAgent().create_roadmap_from_text_input(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    input_data=idea,
                    llm=None
                )
            except Exception as e:
                appLogger.error({
                    "event": "_create_single_roadmap_err",
                    "function": "_create_single_roadmap",
                    "idea": idea,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                return f"Error: {e} occured in creating roadmap for idea: {idea}"
        
        try:
            results = []
            cr_confirm = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="create_roadmap_from_agent_confirm", session_id=self.session_id)
            if len(cr_confirm) < 1:
                TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key="create_roadmap_from_agent_confirm", value="", session_id=self.session_id)
                return "Hi, the roadmap creation action was triggered but we want to confirm once if the user is happy with the roadmap plans. and the roadmap description that we suggested"
            
            TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="create_roadmap_from_agent_confirm", session_id=self.session_id)
            
            with ThreadPoolExecutor(max_workers=min(5, len(description_of_roadmaps_for_creation))) as executor:
                future_to_idea = {executor.submit(_create_single_roadmap, idea): idea for idea in description_of_roadmaps_for_creation}
                for future in as_completed(future_to_idea):
                    results.append(future.result())
            return results
        except Exception as e:
            appLogger.error({
                "event": "create_roadmaps_err",
                "function": "create_roadmaps",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return f"Error occurred in roadmap creation: {e}"


    @log_function_io_and_time
    def present_ideas_as_ppt(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_IDEATION_PPT_CREATION) -> Dict:
        """
        Generates a PowerPoint presentation structure for ideas using LLM, incorporating company, industry, and strategy context.
        Supports single idea slides or multiple ideas with optional 2x2 matrix and value chain slides.
        Slide content is generated by LLM to ensure relevance and impact, stored in TangoDao for frontend rendering.

        Args:
            params (dict, optional): Parameters for PPT generation.
                Expected keys:
                    - content_type (str): 'single_idea' or 'multiple_ideas'.
                    - ideas (list[dict]): List of ideas with 'title', 'description', 'impact' (optional).
                    - include_2x2_matrix (bool): Whether to include a 2x2 matrix slide for multiple ideas.
                    - include_value_chain (bool): Whether to include a value chain slide.
                    - axis_x_label (str, optional): X-axis label for 2x2 matrix (default: 'Impact').
                    - axis_y_label (str, optional): Y-axis label for 2x2 matrix (default: 'Time').
                    - quadrant_labels (list[str], optional): Labels for 2x2 quadrants (default: ['Quick Wins', 'Big Bets', 'Long Term', 'Low Priority']).

        Returns:
            dict: JSON structure with slide definitions or error details.
        """
        try:
            print("present_ideas_as_ppt ", params)
            # Default params
            default_params = {
                "content_type": "single_idea",
                "ideas": [],
                "include_2x2_matrix": False,
                "include_value_chain": False,
                "axis_x_label": "Impact",
                "axis_y_label": "Time",
                "quadrant_labels": ["Quick Wins", "Big Bets", "Long Term", "Low Priority"],
            }
            params = params.copy() if params else {}
            params = {**default_params, **params}
            
            print("present_ideas_as_ppt ", params)

            # Validate inputs
            content_type = params.get("content_type").lower()
            ideas = params.get("ideas")
            include_2x2_matrix = params.get("include_2x2_matrix")
            include_value_chain = params.get("include_value_chain")
            axis_x_label = params.get("axis_x_label")
            axis_y_label = params.get("axis_y_label")
            quadrant_labels = params.get("quadrant_labels")
            session_id = self.session_id

            if not ideas:
                appLogger.info({
                    "function": "present_ideas_as_ppt",
                    "message": "No ideas provided for PPT generation",
                    "tenant_id": self.tenant_id
                })
                return {
                    "error": "No ideas provided for PPT generation",
                    "needs_clarification": True,
                    "clarification_question": "Please provide at least one idea with title and description to generate the PPT. 📽️"
                }

            if content_type not in ["single_idea", "multiple_ideas"]:
                appLogger.info({
                    "function": "present_ideas_as_ppt",
                    "message": f"Invalid content_type: {content_type}",
                    "tenant_id": self.tenant_id
                })
                return {
                    "error": f"Invalid content type: {content_type}. Supported types: single_idea, multiple_ideas.",
                    "needs_clarification": True,
                    "clarification_question": "Please specify if the PPT is for a single idea or multiple ideas. 📽️"
                }

            # Fetch contextual data
            company_info = TenantDaoV2.fetch_company(self.tenant_id) or {}
            industry_info = TenantDaoV2.fetch_company_industry(self.tenant_id) or {}
            strategies = TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id) or []
            context = {
                "company_info": company_info,
                "industry_info": industry_info,
                "strategies": strategies
            }

            model_options = ModelOptions(model="gpt-4.1", max_tokens=15000, temperature=0.2)
            slides = []

            # Common LLM system prompt for slide content generation
            system_prompt = f"""
                You are {self.agent_name}, a world-class strategic consultant created by Trmeric.
                Your task is to generate compelling PowerPoint slide content tailored to the user's company, industry, and strategic goals.
                Use the following context to ensure relevance and alignment:

                Context:
                {json.dumps(context, indent=2)}

                Guidelines:
                - Craft professional, concise, and impactful content for slides.
                - Align content with the company's goals, industry trends, and strategies.
                - Use clear, executive-friendly language, avoiding jargon unless relevant.
                - Include emojis for visual emphasis (e.g., 🚀 for ideas, 📊 for matrices, 🔗 for value chains).
                - Return content in JSON format with 'type' (e.g., 'title', 'text', 'list', '2x2_matrix') and 'value'.
                - If data is missing, use placeholders but note limitations transparently.
            """

            # Single Idea Case
            if content_type == "single_idea":
                if len(ideas) > 1:
                    debugLogger.warning({
                        "function": "present_ideas_as_ppt",
                        "message": "Multiple ideas provided for single_idea content_type; using first idea",
                        "tenant_id": self.tenant_id
                    })
                idea = ideas[0]
                prompt = f"""
                    {system_prompt}

                    Generate content for a single slide for the following idea:
                    {json.dumps(idea, indent=2)}

                    The slide should include:
                    - A title with the idea's name (use 'title' field).
                    - A description of the idea (use 'description' field).
                    - Expected impact or benefits (use 'impact' field if provided, else infer from description).
                    - Content should be engaging, aligned with company and industry context, and formatted for a standard slide layout.

                    Return JSON:
                    ```json
                    {{
                        "title": "Slide Title",
                        "emoji": "🚀",
                        "content": [
                            {{"type": "title", "value": "Idea Title"}},
                            {{"type": "text", "value": "Description"}},
                            {{"type": "text", "value": "Expected Impact"}}
                        ],
                        "layout": "standard"
                    }}
                    ```
                """
                chat_completion = ChatCompletion(system=system_prompt, prev=[], user=prompt)
                output = self.llm.run(chat_completion, model_options, function_name="generate_single_idea_slide", logInDb=self.logInfo)
                slide_data = extract_json_after_llm(output)
                if slide_data:
                    slides.append(slide_data)
                else:
                    appLogger.error({
                        "function": "present_ideas_as_ppt",
                        "message": "LLM failed to generate single idea slide",
                        "tenant_id": self.tenant_id
                    })


            # Multiple Ideas Case
            else:
                # Value Chain Slide (if requested)
                if include_value_chain:
                    prompt = f"""
                    
                        Context:
                        {json.dumps(context, indent=2)}

                        Generate content for a value chain slide that illustrates how the following ideas contribute to the company’s or industry’s value chain:
                        {json.dumps(ideas, indent=2)}

                        Instructions:
                        - Create a value chain with 4-5 stages tailored to the company’s industry and strategic goals as provided in the context.
                        - Map each idea to one or more relevant stages, explaining how it enhances that stage (e.g., improves efficiency, drives innovation, adds customer value).
                        - For each stage, include:
                            - Stage Title: 1-2 words, reflecting the stage’s role (e.g., "R&D", "Customer Support").
                            - Description: Max 30 words, summarizing the stage’s role and how the mapped ideas contribute to it.
                            - Mapped Ideas: List titles of ideas impacting this stage.
                        - Competitive Advantage: Max 15 words, describing the market edge gained by executing the ideas in this stage (e.g., lower costs, faster delivery, or superior quality compared to competitors).
                        - Use a linear or interconnected visual structure suitable for a PowerPoint slide.
                        - Include an emoji (e.g., 🔗) in the title to emphasize the value chain concept.
                        - Ensure content is concise, professional, and executive-friendly, with competitive advantages clearly tied to idea execution.

                        Return JSON:
                        ```json
                        {{
                            "title": "Value Chain Impact",
                            "emoji": "🔗",
                            "value_chain_stages": [
                                {{
                                    "stage_title": "", // 1-2 word
                                    "description": "", // Max 30 words, include idea’s role
                                    "mapped_ideas": ["<idea_title>",...], // Titles of ideas impacting this stage
                                    "competitive_advantage": "", // Max 15 words
                                }},
                                ...
                            ],
                            "layout": "value_chain"
                        }}
                        """
                    chat_completion = ChatCompletion(system=system_prompt, prev=[], user=prompt)
                    output = self.llm.run(chat_completion, model_options, function_name="generate_value_chain", logInDb=self.logInfo)
                    print("v chain", output)
                    slide_data = extract_json_after_llm(output)
                    if slide_data:
                        slides.append(slide_data)


                # 2x2 Matrix Slide (if requested)
                if include_2x2_matrix:
                    prompt = f"""
                    
                        Context:
                        {json.dumps(context, indent=2)}

                        Generate content for a 2x2 matrix slide positioning the following ideas:
                        {json.dumps(ideas, indent=2)}

                        Matrix Details:
                        - X-axis: {axis_x_label} (low to high)
                        - Y-axis: {axis_y_label} (low to high)
                        - Quadrants: {quadrant_labels}
                        
                        
                        Instructions:
                        - Use the provided axes: X-axis ({axis_x_label}, low to high), Y-axis ({axis_y_label}, low to high).
                        - Optionally suggest alternative axis labels if they better fit the ideas and context (include in output).
                        - Assign each idea to one of the quadrants ({quadrant_labels}) based on its description, impact, and alignment with company/industry goals.
                        - For each quadrant, list only idea titles and provide a brief justification (max 15 words) for their placement.
                        - Ensure content is concise and visually clear for a PowerPoint slide.
                        - Include an emoji (e.g., 📊) to emphasize the matrix concept.

                        Assign each idea to a quadrant based on its description and impact, considering company and industry context.
                        Return JSON:
                        ```json
                        {{
                            "x_axis_label": "", // 1-2 words
                            "y_axis_label": "", // 1-2 words
                            "quadrants": [
                                {{
                                    "quadrant_title": "",// Example - Quick wins
                                    "x_val": "high/Low",
                                    "y_val": "high/Low",
                                    "ideas": ["<titles>", ...]
                                    
                                }},...
                            ], // 4 quadrants
                            "layout": "2_2_matrix"
                        }}
                        ```
                    """
                    chat_completion = ChatCompletion(system=system_prompt, prev=[], user=prompt)
                    output = self.llm.run(chat_completion, model_options, function_name="assign_ideas_to_2x2", logInDb=self.logInfo)
                    print("2 x 2", output)
                    slide_data = extract_json_after_llm(output)
                    if slide_data:
                        slides.append(slide_data)


                
                # Individual Idea Slides
                # for idea in ideas:
                prompt = f"""
                
                    Context:
                    {json.dumps(context, indent=2)}

                    Generate content for multiple ideas - single slide for each idea:
                    {json.dumps(ideas, indent=2)}

                    Instructions:
                    - For each idea, create a slide with:
                        - Title: Use the idea’s 'title' field (max 10 words).
                        - Description: Summarize the idea’s 'description' field (max 80 words), aligning with company goals and industry trends.
                        - Impacts: List 2-3 expected benefits (max 15 words each). If 'impact' field is missing, infer from description and context.
                    - Use bullet points for impacts to ensure slide readability.
                    - Include an emoji (e.g., 🚀) to emphasize the idea’s potential.
                    - Ensure content is professional, concise, and executive-friendly.
                    Return JSON:
                    ```json
                    {{
                        "slides": [
                            {{
                                "title": "Slide Title",
                                "idea_description": "", // 50 words
                                "impact": [
                                    {{"emoji": "", "title": "", "value": ""}},
                                ], // 3
                                "layout": "standard"
                            }}
                        ]
                    }}
                    ```
                """
                chat_completion = ChatCompletion(system=system_prompt, prev=[], user=prompt)
                output = self.llm.run(chat_completion, model_options, function_name="generate_idea_slide", logInDb=self.logInfo)
                print("slides ", output)
                slide_data = extract_json_after_llm(output)
                slides_ = slide_data.get("slides") or []
                if slides_:
                    slides.extend(slides_)
                else:
                    ## log error
                    pass

            # Store PPT structure in TangoDao
            ppt_structure = {"slides": slides}
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=f"{self.agent_name}_ppt_structure",
                value=json.dumps(ppt_structure),
                session_id=session_id
            )
            
            # with open("slides.json", w) as json_file:
            with open('slides.json', 'w') as file:
                json.dump(ppt_structure, file, indent=4)
             
            if self.socketio:   
                client_id = UserSocketMap.get_client_id(self.user_id)
                self.socketio.emit("streategy_ppt_generated", ppt_structure, room=client_id)



            return {
                "status": "success",
                "message": f"Generated PPT with {len(slides)} slides",
                "ppt_structure": ppt_structure,
                "success": True,
                "key": "tango_ppt_structure"
            }

        except Exception as e:
            appLogger.error({
                "function": "present_ideas_as_ppt",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                "error": f"Failed to generate PPT: {str(e)}",
                "needs_clarification": True,
                "clarification_question": "There was an issue generating the PPT. Please verify the input ideas and try again. 📽️",
                "next_prompts": [
                    {"label": "Provide specific idea details for PPT generation"},
                    {"label": "Clarify if 2x2 matrix or value chain is needed"},
                    {"label": "Retry PPT generation with updated inputs"}
                ]
            }
                
    @log_function_io_and_time
    def contact_providers_for_execution(self, params: Optional[ContactProviderParams] = None) -> str:
        """
            contact_providers_for_execution should be invoked when user has 
            shortlisted providers for their idea/roadmap/project
            then want to connect to the providers
            
            having markdown_mail_body in each email_details is most important
            and user_satisfied_with_email_contents_and_markdown_mail represents if user is happy with markdown_mail_body for each email details
            
            Example::
            "markdown_mail_body": "<only mail content.. no signature here>",
            "closing_salutation": "Best regards,",
            "name_and_designation_string": "<name and position>"
            
        """
        # 🔑 ensure params is always a Pydantic model
        if isinstance(params, dict):
            params = ContactProviderParams(**params)
        elif params is None:
            params = ContactProviderParams()

        print("hello ... ", params.model_dump())
        redo = """
            Hi, the email was not sent to the providers immediately
            confirm once if the user is happy with the email content(s). 
        """
        
        if not params.user_satisfied_with_email_contents_and_markdown_mail:
            return redo + " User is not happy"
        

        # cr_confirm = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="contact_provider_email_confirm", session_id=self.session_id)
        # if len(cr_confirm) < 1:
        #     TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key="contact_provider_email_confirm", value="", session_id=self.session_id)
        #     return redo + ". Confirm Last time"
        # TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="contact_provider_email_confirm", session_id=self.session_id)
            
        # print("trigeering finally --- ", params.dict() )
        
        state = ""
        email_details  = params.email_details
        for mail_data in email_details:
            brief_email = mail_data.markdown_mail_body
            name_and_designation_string = mail_data.name_and_designation_string
            email_subject = mail_data.email_subject
            
            if not brief_email:
                state += f"markdown_mail_body not present: {mail_data}"
                continue
                
            provider_id = mail_data.provider_id
            receiver_email = "abhishek@trmeric.com"
            # receiver_email = ProviderDao.fetch_provider_email(provider_id)
            res = ApiUtils().send_notification_mail_api(
                email_content=brief_email,
                email_data={
                    "email_content": brief_email,
                    "name_and_position": name_and_designation_string,
                    "subject": email_subject
                }, 
                receiver_email=receiver_email,
                template_key='TANGO-CONNECT-PROVIDER'
            )
            state += f"{res} - {mail_data}"
            
        return state

            
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
    def _generate_onboarding_report(self, lookback_hours: int = 2160) -> str:
        """Generate transformation/onboarding analysis report"""
        try:
            # with open("onboarding_report.json", "r", encoding="utf-8") as f:
            #     summary =  json.load(f)
                
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Generating onboarding report"},
                session_id=self.session_id
            )
            # appLogger.info({"function": "_generate_onboarding_report", "tenant_id": self.tenant_id, "user_id": self.user_id, "lookback_hours": lookback_hours})
            
            # # Generate the onboarding summary
            summary = onboarding_summary(self.user_id, self.tenant_id, hours=lookback_hours)
            print("summary -- ", summary.get("success"))
            # with open("onboarding_report.json", "w", encoding="utf-8") as f:
            #     json.dump(summary, f, ensure_ascii=False, indent=4)

            # return summary
            
            if summary.get("success", False):
                # Format as markdown
                markdown_report = format_transformation_summary_markdown(summary)
                
                self.event_bus.dispatch(
                    'SEND_DIRECT_RESPONSE',
                    {'message': markdown_report},
                    session_id=self.session_id
                )
                return markdown_report
            else:
                error_msg = summary.get("message", "Unable to generate onboarding report")
                return f"## Onboarding Report\n\nSorry, I couldn't generate your onboarding report: {error_msg}"
                
        except Exception as e:
            appLogger.error({"function": "_generate_onboarding_report_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            return f"## Onboarding Report\n\nAn error occurred while generating your onboarding report: {str(e)}"






    @log_function_io_and_time
    def generate_template_file(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_TEMPLATE_GENERATION) -> Dict:
        """
        This function will be used by user to upload their template files.
        The agent will extract the template structure in markdown from here.
        User will provide the category name to be used later for this file template 
        """
        try:
            params = params.copy() if params else {}
            params = {**DEFAULT_PARAMS_FOR_TEMPLATE_GENERATION, **params}
            print("--debug generate_template_file params-------",params)

            # mode = params.get("mode", "save_template")
            s3_keys = params.get("s3_keys") or []
            template_name = params.get("template_name", "")
            category = params.get("category", "BRD").upper()
            changes = params.get("changes", "")
            user_satisfied = params.get("user_satisfied_with_template", False)
            wants_modifications = params.get("user_wants_modifications", False)

            print(f"[GENERATE_TEMPLATE_FILE]  S3 Keys: {s3_keys}, Changes: {len(changes)} chars")

            if not s3_keys:
                return {
                    'error': 'No file uploaded for template processing',
                    'needs_clarification': True,
                    'clarification_question': 'Please upload your template file (DOCX, PDF, MD recommended).'
                }

            # Read file content (same as map_text)
            file_data = self.file_analyzer.analyze_files({"files_s3_keys_to_read": s3_keys})
            print("\n------debug file_data------------", len(file_data))
            if not file_data.get('files'):
                return {
                    'error': 'Could not read uploaded template',
                    'needs_clarification': True,
                    'clarification_question': 'Failed to read file. Please try uploading again.'
                }

            file_info = file_data['files'][0]
            # print("\n---debug file_info----------", file_info)
            if file_info.get('error'):
                return {'error': file_info['error'], 'needs_clarification': True}

            file_id = file_info.get('file_id',None)
            content = file_info.get('content', '')
            filename = file_info['filename']
            print("---debug start create_template_mapping for file_id: ", file_id, ": ", filename)

            if not content.strip():
                return {
                    'error': 'Template is empty or unreadable',
                    'needs_clarification': True,
                    'clarification_question': 'Please upload a valid DOCX/PDF/MD file.'
                }

            result = create_template_mapping(
                file_content=content,
                original_filename=filename,
                s3_key=file_info['file_s3_key'],
                category=category,
                template_name=template_name or filename.split('.')[0],
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                llm=self.llm,
            )

            mode = result.get("mode")
            message = result.get("message")
            success  = result.get("success",False)
            # print("--debug generate_template_file-------- result----", mode,"message: ", message,"\nSatisfied: ", user_satisfied)
            generated_document = result.get("generated_document")

            if user_satisfied:
                store_result = store_template_file({
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id,
                    "category": category,
                    "file_id": file_id,
                    "template_structure": generated_document,
                })
                print("\n\n--debug store_template_file res------- ", store_result)
                if store_result:
                    message = f"✅ Your **{category}** template has been saved successfully!\n\n. I'll use this exact format for all future generations."
                else:
                    message += f"\n\n⚠️ Preview ready, but saving failed. Please try again."

            detailed_activity("trucible_template_processed",f"Template {mode} completed: {filename}",user_id=self.user_id)

            response = f"""{message}\n\n{generated_document}"""
            return response

        except Exception as e:
            appLogger.error({
                "function": "generate_template_file",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'error': f'Template processing failed: {str(e)}',
                'needs_clarification': True,
                'clarification_question': 'Something went wrong. Please try uploading the template again.'
            }
        

    # def _generate_report_from_template(self,params:None):
    #     try:
    #         print("--debug in _generate_report_from_template---------", params)
    #         pass
    #     except Exception as e:
    #         appLogger.error({
    #             "function": "_generate_report_from_template",
    #             "error": str(e),
    #             "traceback": traceback.format_exc(),
    #             "tenant_id": self.tenant_id
    #         })
    #         return {
    #             'error': f'Template processing failed: {str(e)}',
    #             'needs_clarification': True,
    #             'clarification_question': 'Something went wrong. Please try uploading the template again.'
    #         }
