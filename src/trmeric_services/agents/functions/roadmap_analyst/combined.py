from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao, ProviderDao, TenantDao, ProjectsDaoV2, TenantDaoV2, UsersDao, ProjectsDao, IntegrationDao, IdeaDao, SpendDao
from src.trmeric_services.integration.helpers.jira_on_prem_getter import fetch_filtered_integration_data
from .analyst import RoadmapAgent, VIEW_ROADMAP
from .project_analyst import ProjectAgent, VIEW_PROJECTS
from src.trmeric_services.phoenix.queries import KnowledgeQueries
from src.trmeric_services.phoenix.nodes import WebSearchNode
import json
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import traceback
import re
from .queries import getIntegrationData, get_recent_queries
from .actions import Analystactions

from src.trmeric_services.tango.functions.integrations.internal.resource import get_capacity_data
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetPortfoliosSnapshot import view_portfolio_snapshot
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewPerformanceSnapshot import view_performance_snapshot_last_quarter
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewValueSnapshot import view_value_snapshot_last_quarter
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewRiskSnapshot import view_risk_report_current_quarter
from src.trmeric_services.tango.functions.integrations.internal.providers import get_provider_data, get_quantum_data
from src.trmeric_utils.web.CompanyScraper import CompanyInfoScraper
from .response_prompts import portfolio_snapshot_prompt, performance_snapshot_prompt, business_value_report_prompt, risk_report_prompt
from src.trmeric_ws.helper import SocketStepsSender
from .vector import TrmericVectorSearch
import threading
from src.trmeric_services.phoenix.prompts import ChatTitlePrompt
from src.trmeric_s3.s3 import S3Service
from src.trmeric_services.agents.reports.customers.pf.monthly_savings import (
    fetchDataForMonthlySavingsAndAnalysis, 
    monthly_savings_report_with_graph_prompt
)
from src.trmeric_ws.static import TangoBreakMapUser
from src.trmeric_services.journal.ActivityEndpoints import get_user_session_summaries_by_timeframe
from src.trmeric_services.journal.Vectors.ActivityOnboarding import onboarding_summary, format_transformation_summary_markdown

import sys, json
from src.trmeric_services.agents.functions.potential_agent.utils import find_best_resource_match
MAX_INPUT_SIZE = 7_000_000  # 10MB limit
# from src.trmeric_api.logging.ProgramState import ProgramState
from src.trmeric_database.Redis import RedClient


def truncate_if_too_large(data_str):
    label = "data"
    size = sys.getsizeof(data_str)
    print("truncate_if_too_large ", size)
    # Accurate byte size measurement
    # size = len(data_str.encode("utf-8"))
    # print(f"truncate_if_too_large({label}) → {size} bytes")
    if size > MAX_INPUT_SIZE:
        print(f"[WARN] too large ({size} bytes). Truncating input.")
        safe_size = 6_000_000  # keep 7MB to stay well below 10MB
        return data_str[:safe_size] + f"\n\n[TRUNCATED: data too long, {size} bytes total]"
    return data_str

class MasterAnalyst:
    def __init__(self, tenant_id: int, user_id: int, socketio=None, llm=None, client_id=None, base_agent=None, sessionID=None, eligibleProjects=[]):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.logInDb = {"tenant_id": tenant_id, "user_id": user_id}
        self.log_info = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": sessionID,
        }
        self.socketio = socketio
        self.llm = llm
        self.client_id = client_id
        self.base_agent = base_agent
        self.sessionID = sessionID
        self.eligibleProjects = eligibleProjects
        self.user_context = self._build_user_context(base_agent)
        # print("self.user_info_string")
        self.tenant_configs = TenantDao.checkTenantConfig(tenant_id=tenant_id)
        self.user_info_string = (
            # base_agent.org_info_string
            # + "\n"
            # + 
            base_agent.user_info_string
            + "\n"
            + base_agent.integration_info_string
            + "\n"
            + base_agent.project_and_roadmap_context_string
            + "\n"
            + base_agent.program_list
            + "\n"
            + base_agent.current_session_uploaded_files
            + "\n"
            + base_agent.templates
            + "\n"
            + f"Comapny Basic Info with url for extracting content from this url if required: {TenantDaoV2.fetch_company(tenant_id=self.tenant_id)}"
            + "\n"
            + f"Enterprise strategies of this user's company: {TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id)}"
            + "\n"
            + base_agent.org_role_user
            + "\n"
            + json.dumps(self.tenant_configs)
        )
        # data sources
        # print("base_agent.integration_info_string", base_agent.integration_info_string)
        self.data_sources = {
            "web_search": self._call_web_agent,
            "resource_data": self.fetch_resource_data,
            "integration_data": self._call_get_integration_data,
            "get_snapshots": self._call_get_snapshots,
            "provider_storefront_data": self._call_get_provider_storefront_data,
            "provider_quantum_data": self._call_get_provider_quantum_data,
            "some_info_about_trmeric": self._call_some_info_about_trmeric,
            "customer_existing_solutions": self._customer_existing_solutions,
            "current_session_uploaded_files": self._read_session_uploaded_files,
            "get_journal_data": self._call_get_journal_data,
            "idea_data": self._call_get_idea_data,
            "fetch_customer_templates": self.fetch_customer_templates,
        }
        self.data_sources["project_spend_data"] = self.fetch_project_spend
        self.actions_class = Analystactions(tenant_id=tenant_id, user_id=user_id)
        self.actions_to_take = {
            "set_user_designation": self.actions_class.set_user_designation,
            "set_company_context": self.actions_class.set_company_context,
            "create_roadmaps": self.actions_class.create_roadmaps,
            "create_projects": self.actions_class.create_projects,
            "find_suitable_service_provider": self.actions_class.find_best_provider,
            "create_or_update_milestone_or_risk_project_status": self.actions_class.create_or_update_sa_agent,
            "generate_onboarding_report": self._generate_onboarding_report
        }

        debugLogger.info({"function": "MasterAnalyst_init", "tenant_id": tenant_id, "user_id": user_id})
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.socketSender = SocketStepsSender("custom_agent_v1_ui", self.socketio, self.client_id)
        if self.socketio:
            self.socketio.emit(
                "custom_agent_v1_ui",
                {
                    "event": "show_timeline",
                },
                room=self.client_id,
            )
        self.vector_search = TrmericVectorSearch()

    def generate_chat_title(self, session_id, meta):
        """Run title generation in a separate thread and emit result."""
        try:

            print("generate_chat_title 0 --- ", session_id, meta)
            session_id = session_id + "combined"
            current_title = TangoDao.fetchChatTitleForSession(session_id=session_id)
            print("generate_chat_title 1", current_title, current_title == "New Chat" or current_title == None)
            if current_title == "New Chat" or current_title == None:
                pass
            else:
                return

            conv = TangoDao.fetchChatsForSessionAndTypes(session_id=session_id, types=[1, 3])
            print("generate_chat_title 2", len(conv))
            tenant_id = meta.get("tenant_id")
            user_id = meta.get("user_id")
            if len(conv) < 2 and len(conv) > 10:
                TangoDao.insert_chat_title(session_id=session_id, title="New Chat", tenant_id=tenant_id, user_id=user_id)
                return
            title_prompt = ChatTitlePrompt.generate_title(conv)
            title_response = self.base_agent.llm.run(title_prompt, self.base_agent.modelOptions, "title::create", logInDb=meta)
            print("title_response ", title_response)
            chat_title = extract_json_after_llm(title_response)
            chat_title_string = chat_title.get("chat_title") or None
            if chat_title_string:

                TangoDao.insert_chat_title(session_id=session_id, title=chat_title_string, tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            appLogger.error({"error": "ChatTitleGeneration", "exception": str(e), "traceback": traceback.format_exc()})


    def fetch_project_spend(self, project_ids=None, spend_types=None):
        return SpendDao.FetchProjectsSpend(
            project_ids=project_ids,
            spend_types=spend_types,
            tenant_id=self.tenant_id
        )

    def _read_session_uploaded_files(self, **params):
        try:
            files_s3_keys_to_read = params.get("files_s3_keys_to_read") or []
            s3_service = S3Service()
            file_content_per_s3_key = {}
            result = {}
            for s3_key in files_s3_keys_to_read:
                try:
                    result[s3_key] = s3_service.download_file_as_text(s3_key)
                except Exception as e1:
                    result[s3_key] = f"Could not read file, error: {e1}"
            # print("content in uploaded files ", result)
            return result
        except Exception as e:
            appLogger.error({"function": "_read_session_uploaded_files", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            raise

    def _customer_existing_solutions(self, **params):
        print("in debug --- customer_existing_solutions")
        try:
            results = TenantDao.listCustomerSolutions(tenant_id=self.tenant_id)
            return results
        except Exception as e:
            appLogger.error({"function": "_customer_existing_solutions", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            raise

    def _call_get_idea_data(self, **params) -> Dict:
        try:
            debugLogger.info({
                "function": "_call_get_idea_data",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "params": params
            })

            idea_ids = params.get("idea_ids")
            projection_attrs = params.get("projection_attrs")
            portfolio_ids = params.get("portfolio_ids")
            state_filter = params.get("state_filter")
            order_clause = params.get("order_clause")

            # Call the real DAO function that supports dynamic fields
            ideas = IdeaDao.fetchIdeasDataWithProjectionAttrs(
                idea_ids=idea_ids,
                projection_attrs=projection_attrs,
                portfolio_ids=portfolio_ids,
                tenant_id=self.tenant_id,
                state_filter=state_filter,
                order_clause=order_clause,
                user_id=self.user_id,
            )

            return {"idea_data": ideas}

        except Exception as e:
            appLogger.error({
                "function": "_call_get_idea_data",
                "event": "FETCH_IDEA_DATA_FAILURE",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "params": params
            })
            return {"idea_data": []}


    def _call_get_journal_data(self, **params):
        print("in debug --- _call_get_journal_data ", params)
        try:
            hours = params.get("hours") or 48
            return get_user_session_summaries_by_timeframe(hours=hours, userID=self.user_id)
        except Exception as e:
            appLogger.error({"function": "_call_get_journal_data", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            raise



    def _call_some_info_about_trmeric(self, **params) -> Dict:
        print("called --- _call_some_info_about_trmeric ", params)
        try:
            results = []
            for query in params.get("queries", []) or []:
                # query = params.get("query", "")
                # if not query:
                #     return {"error": "No query provided for company knowledge search"}
                result = self.vector_search.queryVectorDB(query)
                results.append(result)
            return {"some_info_about_trmeric": results}
        except Exception as e:
            appLogger.error({"function": "call_some_info_about_trmeric_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            return {"error": str(e)}

    def _call_web_agent(self, **params):
        print("debug --- ", params)
        web_queries = params.get("web_queries") or []
        website_urls = params.get("website_urls") or []
        result = {}
        if web_queries:
            pass
            # result["web_queries_result"] = {}
            # res = WebSearchNode().run(sources=web_queries)
            # for q, r in zip(web_queries, res):
            #     result["web_queries_result"][q] = r
        if website_urls:
            result["website_urls_result"] = {}
            for site in website_urls:
                scraper_c = CompanyInfoScraper(site, max_workers=3)
                scraped = scraper_c.scrape()
                result["website_urls_result"][site] = scraped

        return result

    def _call_get_provider_storefront_data(self, **params) -> Dict:
        """Wrapper to call get_provider_data with tenant_id, user_id, and params."""
        try:
            tenant_type = TenantDao.checkCustomerType(self.tenant_id)
            if tenant_type != "provider":
                appLogger.info({"function": "call_get_provider_storefront_data_skipped", "reason": "Tenant is not a provider", "tenant_id": self.tenant_id, "user_id": self.user_id})
                return {"error": "Storefront data is only available for provider tenants"}

            data_sources_array = params.get("data_sources_array", ["service_catalog", "capabilities", "case_studies", "trmeric_assessment", "opportunities", "win_themes"])
            return get_provider_data(eligibleProjects=self.eligibleProjects, tenantID=self.tenant_id, userID=self.user_id, data_sources_array=data_sources_array)
        except Exception as e:
            appLogger.error({"function": "call_get_provider_storefront_data_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "user_id": self.user_id})
            return {"error": str(e)}

    def _call_get_provider_quantum_data(self, **params) -> Dict:
        """Wrapper to call get_quantum_data with tenant_id, user_id, and params."""
        try:
            tenant_type = TenantDao.checkCustomerType(self.tenant_id)
            if tenant_type != "provider":
                appLogger.info({"function": "call_get_provider_quantum_data_skipped", "reason": "Tenant is not a provider", "tenant_id": self.tenant_id, "user_id": self.user_id})
                return {"error": "Quantum data is only available for provider tenants"}

            provider_id = ProviderDao.fetchProviderIdForTenant(self.tenant_id)
            if not provider_id:
                appLogger.error({"function": "call_get_provider_quantum_data_error", "event": "NO_PROVIDER_FOUND", "tenant_id": self.tenant_id, "user_id": self.user_id})
                return {"error": "No provider ID found for tenant"}

            data_sources_array = params.get(
                "data_sources_array",
            ) or [
                "service_catalog",
                "offers",
                "ways_of_working",
                "case_studies",
                "partnerships",
                "certifications_and_audit",
                "leadership_and_team",
                "voice_of_customer",
                "information_and_security",
                "aspiration",
                "core_capabilities",
            ]
            return get_quantum_data(provider_id=provider_id, tenant_id=self.tenant_id, user_id=self.user_id, data_sources_array=data_sources_array)
        except Exception as e:
            appLogger.error({"function": "call_get_provider_quantum_data_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "user_id": self.user_id})
            return {"error": str(e)}

    def _build_user_context(self, base_agent):
        if not base_agent:
            return ""
        return f"{base_agent.context_string}\n{base_agent.org_info_string}\n{base_agent.user_info_string}"

    def fetch_resource_data(self, **params) -> Dict:
        try:
            debugLogger.info({"function": "fetch_resource_data", "tenant_id": self.tenant_id, "user_id": self.user_id, "params": params})

            # Default projection if not provided
            projection_attrs = params.get("selected_projection_attrs") or [
                "id", "first_name", "last_name", "role", "primary_skill", "current_allocation", "org_team", "is_external"
            ]

            # Extract all filters
            resource_ids = params.get("resource_ids")
            name = params.get("name")
            primary_skill = params.get("primary_skill")
            skill_keyword = params.get("skill_keyword")
            role = params.get("role")
            is_external = params.get("is_external")
            external_company_name = params.get("external_company_name")
            org_team_name = params.get("org_team_name")
            org_team_id = params.get("org_team_id")
            min_allocation = params.get("min_allocation")
            max_allocation = params.get("max_allocation")
            available_only = params.get("available_only", False)
            portfolio_ids = params.get("portfolio_ids") or []

            # Fetch data from DAO
            resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
                tenant_id=self.tenant_id,
                projection_attrs=projection_attrs,
                resource_ids=resource_ids,
                # name=name,
                primary_skill=primary_skill,
                skill_keyword=skill_keyword,
                role=role,
                is_external=is_external,
                external_company_name=external_company_name,
                org_team_name=org_team_name,
                org_team_id=org_team_id,
                min_allocation=min_allocation,
                max_allocation=max_allocation,
                available_only=available_only,
                portfolio_ids=portfolio_ids,
            )
            print("len resource_data ", len(resource_data), "\n\n----data------", resource_data[:2])

            if name:
                print("--debug calling best resource match00000000000", name)
                resource_data = find_best_resource_match(target_name=name,resource_data = resource_data)

            return {"resources": resource_data}

        except Exception as e:
            appLogger.error({
                "function": "fetch_resource_data",
                "event": "FETCH_RESOURCE_DATA_FAILURE",
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "params": params
            })
            return {"resources": []}

    def fetch_customer_templates(self, **params) -> Dict:
        try:
            debugLogger.info({"function": "fetch_customer_templates", "tenant_id": self.tenant_id, "user_id": self.user_id, "params": params})

            # Default projection if not provided
            projection_attrs = params.get("selected_projection_attrs") or [
                "id", "category", "markdown"
            ]

            # Extract all filters
            category = params.get("category")
            
            # Fetch data from DAO
            templates = TenantDaoV2.fetch_saved_templates(
                projection_attrs=projection_attrs,
                category = category,
                tenant_id = self.tenant_id,
                only_active = True,
                order_clause = None,
                limit = 4,
            )
            print("len templates ", len(templates))

            return {"templates": templates}

        except Exception as e:
            appLogger.error({
                "function": "fetch_customer_templates",
                "event": "fetch_customer_templates_error",
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "params": params
            })
            return {"templates": []}


    def _call_get_integration_data(self, **params) -> Dict:
        """
        Wrapper to call getIntegrationData with dynamic integration parameters.
        Handles missing project_ids, on-prem Jira, and user_detailed_query.
        """
        try:
            debugLogger.info(f"params --- {params}")

            integration_name = params.get("integration_name")
            project_ids = params.get("project_ids") or []

            # ✅ Fallback to fetching available projects if none provided
            if not project_ids:
                project_ids = ProjectsDao.FetchAvailableProject(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                )

            # ✅ Check for on-prem Jira setup
            is_jira_on_prem = IntegrationDao.is_user_on_prem_jira(self.user_id)
            debugLogger.info(f"is_jira_on_prem: {is_jira_on_prem}")

            # ✅ Call the core integration data fetcher
            data = getIntegrationData(
                integration_name=integration_name,
                project_ids=project_ids,
                tenantID=self.tenant_id,
                userID=self.user_id,
                user_detailed_query=params.get("user_detailed_query", "")
            )
            print("bool check -- ", (is_jira_on_prem or int(self.tenant_id) in [212, 767]) and integration_name == "jira", self.tenant_id)

            # ✅ Handle special Jira on-prem flattening
            if (is_jira_on_prem or int(self.tenant_id) in [212, 776]) and (integration_name == "jira" or integration_name == "github"):
                ndata = []
                for project_id, integrations in data.items():
                    for item in integrations:
                        if "integration_data" in item:
                            int_data = item["integration_data"].get("data")
                            # if integration_name == "github":
                                # int_data = item["integration_data"].get("data")
                                
                            if int_data:
                                ndata.append(int_data)

                post_processed_data = fetch_filtered_integration_data(
                    user_query=params.get("user_detailed_query"),
                    data_array=ndata,
                    integration_name=integration_name
                )
                return post_processed_data

            return data

        except Exception as e:
            appLogger.error({
                "function": "_call_get_integration_data",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            return {}


    def _call_get_snapshots(self, **params) -> Dict:
        """Wrapper to call snapshot functions based on snapshot_type and parameters."""
        try:
            snapshot_type = params.get("snapshot_type")
            eligible_projects = self.eligibleProjects
            kwargs = params.get("kwargs", {})

            if snapshot_type == "value_snapshot_last_quarter":
                if not params.get("last_quarter_start") or not params.get("last_quarter_end"):
                    raise ValueError("last_quarter_start and last_quarter_end are required for value_snapshot_last_quarter")
                return view_value_snapshot_last_quarter(
                    eligibleProjects=eligible_projects,
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    last_quarter_start=params.get("last_quarter_start"),
                    last_quarter_end=params.get("last_quarter_end"),
                    **kwargs,
                )
            elif snapshot_type == "portfolio_snapshot":
                return view_portfolio_snapshot(eligibleProjects=eligible_projects, tenantID=self.tenant_id, userID=self.user_id, portfolio_id=params.get("portfolio_id"), **params.get("kwargs", {}))
            elif snapshot_type == "performance_snapshot_last_quarter":
                if not params.get("last_quarter_start") or not params.get("last_quarter_end"):
                    raise ValueError("last_quarter_start and last_quarter_end are required for performance_snapshot_last_quarter")

                return view_performance_snapshot_last_quarter(
                    eligibleProjects=eligible_projects,
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    last_quarter_start=params.get("last_quarter_start"),
                    last_quarter_end=params.get("last_quarter_end"),
                    **params.get("kwargs", {}),
                )
            elif snapshot_type == "risk_snapshot":
                if not (params.get("last_quarter_start") or params.get("quarter_start")):
                    raise ValueError("Start and end dates are required for risk_snapshot")
                if not (params.get("last_quarter_end") or params.get("quarter_end")):
                    raise ValueError("Start and end dates are required for risk_snapshot")
                return view_risk_report_current_quarter(
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    quarter_start=params.get("last_quarter_start") or params.get("quarter_start"),
                    quarter_end=params.get("last_quarter_end") or params.get("quarter_end"),
                    **params.get("kwargs", {}),
                )
            
            elif snapshot_type == "monthly_savings_snapshot":
                program_ids = params.get("program_ids", [])
                if not program_ids:
                    project_data = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                        program_id=None,
                        projection_attrs=["program_id"],
                        tenant_id=self.tenant_id,
                        include_archived=False
                    )
                    program_ids = list(set(project.get("program_id") for project in project_data if project.get("program_id")))
                debugLogger.info({"function": "_call_monthly_savings_snapshot", "tenant_id": self.tenant_id, "program_ids": program_ids})
                return fetchDataForMonthlySavingsAndAnalysis(
                    program_ids=program_ids,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id
                )
            else:
                raise ValueError(f"Invalid snapshot_type: {snapshot_type}")
        except Exception as e:
            appLogger.error({"function": "call_get_snapshots_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "snapshot_type": snapshot_type})
            raise

    def plan_combined_analysis(self, query: str) -> Dict:
        appLogger.info({"function": "plan_combined_analysis_start", "tenant_id": self.tenant_id, "user_id": self.user_id, "query": query})

        if not self.llm:
            appLogger.error({"function": "plan_combined_analysis_error", "error": "LLM instance is required for planning analysis", "tenant_id": self.tenant_id})
            raise ValueError("LLM instance is required for planning analysis")

        roadmap_schema = json.dumps(VIEW_ROADMAP.function.__globals__["ROADMAP_SCHEMA"], indent=2)
        project_schema = json.dumps(VIEW_PROJECTS.function.__globals__["PROJECT_SCHEMA"], indent=2)
        current_date = datetime.now().date().isoformat()
        conv = self.base_agent.conversation.format_conversation() if self.base_agent else "No prior conversation."
        tenant_type = TenantDao.checkCustomerType(self.tenant_id)
        available_data_sources = [
            "web_search",
            "resource_data",
            "integration_data",
            "get_snapshots",
            "some_info_about_trmeric",
            "customer_existing_solutions",
            "current_session_uploaded_files",
            "get_journal_data",
            "idea_data",
            "fetch_customer_templates",
            "project_spend_data"
        ]
        if tenant_type == "provider":
            available_data_sources.extend(["provider_storefront_data", "provider_quantum_data"])
        available_actions = list(self.actions_to_take.keys())
        
        system_prompt = f"""
            Ongoing Conversation: 
            <ongoing_conv_in_current_session>
                {conv}
            </ongoing_conv_in_current_session>
            User Query: "{query}"
            User Context: {self.user_info_string}
            Current Date: {current_date}
            Tenant Type: {tenant_type}

            You are a versatile conversational AI assistant capable of handling a wide range of queries, from casual conversations to complex analytical tasks. Your goal is to interpret the user's query naturally, determine the appropriate response strategy, and leverage available data sources or actions only when necessary. Actions take the highest priority in the response, especially provider recommendations, which should be triggered when the query indicates a need for service provider matching. Roadmap-related queries should be routed to the roadmap agent for analysis unless explicitly requesting roadmap creation. Projects-related queries should be routed to the project agent for analysis unless explicitly requesting project creation.

            ### Capabilities
            - **Conversational Responses**: For general or casual queries (e.g., "How's it going?", "Tell me about AI trends"), provide a friendly, natural response without invoking specialized tools unless explicitly needed.
            - **Context Management**:
                - Check if user context is complete (e.g., user designation and company information in `user_info_string`).
                - If user designation is missing (e.g., `org_role_user` is empty), suggest triggering `set_user_designation`.
                - If company context is missing (e.g., `org_info_string` is empty), suggest triggering `set_company_context` and prompt for a company URL.
                - Detect explicit context update requests (e.g., "set my designation to <role>", "set company url to <url>").
            - **Analytical Queries**:
                - Roadmap Schema: {roadmap_schema}
                - Project Schema: {project_schema}
                - Customer Solutions Schema:
                    - Array of solution records with fields:
                        - name: string (solution name, e.g., "EY Atlas")
                        - description: string (detailed description)
                        - category: string (e.g., "Assurance, Audit, Digital")
                        - technology: string (e.g., "Azure")
                        - service_line: string (e.g., "Assurance")
                - Available Data Sources: {available_data_sources}
                - Available Actions: {available_actions}
                - Handle queries involving roadmaps, projects, resources, integrations, snapshots, provider data, or customer solutions by triggering the appropriate data sources or agents.
                - All queries related to roadmaps, plans, or demand always activate the roadmap agent.
                - Queries related to intake requests mean the user wants to ideate and then create a roadmap after that.
                - Queries related to customer solutions (e.g., "list customer solutions", "analyze existing solutions", "details of EY Atlas") trigger `customer_existing_solutions` to fetch solution data for the tenant.
                - For roadmaps/projects, split into sub-queries (roadmap_query and project_query: write them intelligently combined with your thought so that these small agents know what data to pull from their schema) and suggest combination logic (e.g., match roadmap_id).
                - For external insights, use `web_search` with web_queries or website_urls.
                - For resources, use `resource_data` with optional params (start_date, end_date, resource_name, eligibleProjects).
                - For integrations, use `integration_data` with integration_name(most important) and (required) project_ids.
                - For snapshots, use `get_snapshots` with snapshot_type, last_quarter_start, last_quarter_end, portfolio_id, or portfolio_ids (list of integers for filtering by multiple portfolios).
                - For journal data, use `get_journal_data` with an `hours` parameter (e.g., 24, 168) to fetch session summaries from the last N hours.
                - For provider recommendations, use `find_suitable_service_provider` with roadmap_id or project_id and tag ("roadmap" or "project").
                - For customer solutions, use `customer_existing_solutions` (no additional params required; uses tenant_id internally).
                - **Provider Storefront Data (for provider tenants only)**:
                    - Trigger `provider_storefront_data` for queries related to provider-specific information.
                    - Available data sources within `provider_storefront_data`:
                        - `tenant_type`: Fetch tenant type (e.g., "provider" or "customer").
                        - `project_brief`: Fetch project briefs for specified project IDs.
                        - `service_provider_details`: Fetch details of all service providers.
                        - `service_catalog`: Fetch service categories and names for a provider.
                        - `capabilities`: Fetch key technologies, industries, partnerships, and strengths.
                        - `case_studies`: Fetch case study titles.
                        - `trmeric_assessment`: Fetch Trmeric ratings (expertise, delivery, satisfaction, innovation, communication, reliability).
                        - `opportunities`: Fetch opportunities by tenant ID.
                        - `win_themes`: Fetch win themes by tenant ID.
                    - Parameters:
                        - `data_sources_array`: List of specific data sources to fetch (e.g., ["case_studies", "service_catalog"]). If empty, defaults to ["service_catalog", "capabilities", "case_studies", "trmeric_assessment", "opportunities", "win_themes"].
                - **Provider Quantum Data (for provider tenants only)**:
                    - Trigger `provider_quantum_data` for queries related to detailed provider quantum data.
                    - Available data sources within `provider_quantum_data`:
                        - `service_catalog`: Fetch quantum service catalog.
                        - `offers`: Fetch provider offers.
                        - `ways_of_working`: Fetch ways of working details.
                        - `case_studies`: Fetch quantum case studies.
                        - `partnerships`: Fetch partnerships.
                        - `certifications_and_audit`: Fetch certifications and audit details.
                        - `leadership_and_team`: Fetch leadership and team information.
                        - `voice_of_customer`: Fetch voice of customer data.
                        - `information_and_security`: Fetch information and security details.
                        - `aspiration`: Fetch aspiration data.
                        - `core_capabilities`: Fetch core capabilities.
                    - Parameters:
                        - `data_sources_array`: List of specific data sources to fetch (e.g., ["partnerships", "leadership_and_team"]). If empty, fetches all quantum data sources.
                - **Customer Solutions Data**:
                    - Trigger `customer_existing_solutions` for queries about existing customer solutions (e.g., "list customer solutions", "details of EY Atlas").
                    - No additional parameters required; uses tenant_id internally.
                    - Returns an array of solution records (see Customer Solutions Schema above).
                    - Use for analyzing existing solutions, matching solutions to roadmaps/projects, or recommending providers based on solution compatibility.
                - **Journal Data**:
                    - Trigger `get_journal_data` for queries about recent user activities or session summaries (e.g., "recent activities", "what have I been working on?").
                    - Parameter:
                        - `hours`: Integer specifying the timeframe in hours (e.g., 24 for last day, 168 for last week).
                    - Returns an array of session summary records (see Journal Data Schema above).
                    - Use for summarizing user interactions, identifying recent actions, or analyzing session patterns.
                - **Resource Data (`resource_data`)**:
                    - Trigger `resource_data` for queries involving team members, roles, availability, allocation, skills, capacity, org teams, external providers, or resources assigned to a **specific portfolio**.
                    - **Returned Schema**:
                        - Array of resource objects under `"resources"` key.
                        - Fields vary based on `selected_projection_attrs`, including:
                            - `id`, `first_name`, `last_name`, `role`, `experience_years`,
                            - `primary_skill`, `skills`, `current_allocation`,
                            - `past_projects`, `current_projects`, `future_projects`,
                            - `org_team`, `portfolio`, `is_external`,
                            - `provider_company_name`, `provider_company_website`, `provider_company_address`
                    - **Parameters** (all optional):
                        - `resource_ids`: list[int] — filter by exact resource IDs
                        - `name`: str — partial/full name match (first, last, or combined)
                        - `primary_skill`: str — exact or partial match on primary skill
                        - `skill_keyword`: str — match any keyword in full skills list
                        - `role`: str — filter by job title/role
                        - `is_external`: bool — True = only external, False = only internal, None = both
                        - `external_company_name`: str — filter external resources by provider company name
                        - `org_team_name`: str — partial match on org/team name
                        - `org_team_id`: int — exact team ID
                        - `min_allocation`: float — minimum current allocation % (e.g., 50)
                        - `max_allocation`: float — maximum current allocation % (e.g., 90)
                        - `available_only`: bool — return only resources with availability/capacity
                        - `portfolio_ids`: list[int] — **NEW: return only resources mapped to one or more portfolio IDs** (e.g., `[10, 20]`)
                        - `selected_projection_attrs`: list[str] — controls which fields are returned for optimized payload
                    - **Available Projection Attributes**:
                        ```python
                        [
                            "id", "first_name", "last_name", "role", "experience_years",
                            "primary_skill", "skills", "current_allocation",
                            "past_projects", "current_projects", "future_projects",
                            "org_team", "portfolio",   # <- portfolio JSON supported
                            "is_external",
                            "provider_company_name", "provider_company_website", "provider_company_address"
                        ]
                        ```
                    - **Examples**:
                        - "Resources for portfolio 246" →
                            `data_sources_to_trigger=["resource_data"]`, `data_source_params.resource_data.portfolio_ids=[246]`
                        - "Show me Python devs in the AI portfolio" →
                            `primary_skill="Python"`, `portfolio_ids=[<AI portfolio ID>]`
                        - "Team structure across portfolios 1 and 2" →
                            `portfolio_ids=[1, 2]`, `selected_projection_attrs=["id", "first_name", "last_name", "org_team", "portfolio"]`
                        - "External resources assigned to portfolio 50" →
                            `is_external=True`, `portfolio_ids=[50]`

                    - **Default Behavior**:
                        - If no params → returns minimal default fields for **all active resources**
                        - Always filters out test/inactive data
                    - **Use Cases**:
                        - "Show me Python devs under 80% allocated" → `primary_skill="Python"`, `max_allocation=80`
                        - "List external vendors from Accenture" → `is_external=True`, `external_company_name="Accenture"`
                        - "Who is on the Data Intelligence team?" → `org_team_name="Data Intelligence"`
                        - "Available internal PMs" → `role="PM"`, `is_external=False`, `available_only=True`
                        - "Lightweight list of names and roles" → `selected_projection_attrs=["id", "first_name", "last_name", "role"]`
                        
                - **Idea Data (`idea_data`)**:
                    - Trigger `idea_data` for any query involving ideas, idea lists, idea details, ideation tracking, prioritization, backlog refinement, or "concept" requests (e.g., "show my ideas", "idea details for ID 12", "summary of ideas related to portfolio 5").
                    
                    - **Returned Schema**:
                        - Array of idea objects under `"ideas"` key.
                        - Fields available depend on `projection_attrs` defined in the IdeaDao {IdeaDao.ATTRIBUTE_MAP.keys()} (defaults to: ["id", "title"]).
                        - Rich attributes include:
                            - `id`, `title`, `elaborate_description`, `rank`, `budget`,
                            - `start_date`, `end_date`, `owner`, `org_strategy_align`,
                            - `objectives`, `category`, `tango_analysis`, `created_on`,
                            - `constraints` (JSON), `kpis` (JSON),  
                            - `portfolios` (JSON),  
                            - `roadmaps` (JSON),  
                            - `business_case`,  
                            - `business_members` (JSON)

                    - **Parameters** (`data_source_params.idea_data`):
                        - `idea_ids`: list[int] — filter by specific idea IDs.
                        - `title`: str — partial match on idea title.
                        - `category`: str — exact or partial category match.
                        - `current_state`: int — filter by idea lifecycle state.
                        - `org_strategy_align`: str — match against strategic alignment text.
                        - `min_budget`: float — minimum idea budget.
                        - `max_budget`: float — maximum idea budget.
                        - `start_date`: str — filter ideas starting after this date (YYYY-MM-DD).
                        - `end_date`: str — filter ideas ending before this date (YYYY-MM-DD).
                        - `portfolio_ids`: list[int] — return only ideas mapped to one or more portfolio IDs.
                        - `projection_attrs`: list[str] — optional; controls which idea fields are included for efficiency.

                    - **How Idea Data Is Fetched**:
                        - All parameters are passed to `TenantDaoV2.fetchIdeas`, which internally calls:
                            `IdeaDao.fetchIdeasDataWithProjectionAttrs(...)`
                        - The DAO automatically:
                            - Builds dynamic SELECT clauses.
                            - Joins constraints, KPIs, portfolios, roadmaps, business members.
                            - Applies tenant_id filtering.
                            - Applies aggregation only when required.
                            - Returns structured JSON per idea.

                    - **Examples**:
                        - "Show all ideas in category 'AI'":
                            → `data_sources_to_trigger=["idea_data"]`,
                              `data_source_params.idea_data.category="AI"`
                        
                        - "Give me ideas with budget over 1M":
                            → `min_budget=1000000`
                        
                        - "Ideas linked to portfolio 42":
                            → `portfolio_ids=[42]`
                        
                        - "Summarize idea 15":
                            → `idea_ids=[15]`, `projection_attrs=["id","title","constraints","kpis","roadmaps"]`
                        
                        - "Quick overview of my ideas":
                            → minimal projection attributes for speed:
                              `projection_attrs=["id","title","rank","category"]`

                    - **Default Behavior**:
                        - If no filters are provided:
                            - Returns all ideas for the tenant with default projection fields.
                        - If query implies high-level summary:
                            - Use small `projection_attrs` for efficiency.
                        - If query implies deep analysis:
                            - Include full `projection_attrs` (constraints, roadmaps, kpis, etc.).

                    - **Use Cases**:
                        - "Rank my ideas by budget"
                        - "Ideas aligned to strategy"
                        - "Which ideas map to roadmap 120?"
                        - "What ideas can become projects?"
                        - "List ideas connected to roadmap types 'Program'"
                        
                      
                      
                        
                - **Template data (`fetch_customer_templates`)**:
                    - Trigger `fetch_customer_templates` for any query involving template, like use template to present sokme data as per discusssion or user requirements
                    - **Use Cases**:
                        - "Use business case template to present business case data of  project X"
                    - Prtojection Attributes: ["id", "category", "markdown"]
                    - Add category as filter
                    
                    
                - **Project Spend Data (`project_spend_data`)**:
                    - Trigger for any financial, cost, CAPEX, OPEX, vendor spend, procurement, liability, or project expenditure queries.
                    - Use when user asks about:
                        - Project cost or total spend
                        - CAPEX vs OPEX
                        - Vendor payments or procurement
                        - Financial exposure or open liabilities
                        - Spend analysis across projects or portfolios

                    - **Parameters** (`data_source_params.project_spend_data`):
                        - `project_ids`: list[int] — required
                        - `spend_types`: list[str] — optional; values: ["CAPEX"], ["OPEX"], or both

                    - **Examples**:
                        - "Spend for project 123"
                            → `project_ids=[123]`
                        - "CAPEX for project 456"
                            → `project_ids=[456]`, `spend_types=["CAPEX"]`
                        - "OPEX vs CAPEX for projects 10, 20"
                            → `project_ids=[10, 20]`



            ### Instructions
            1. **Query Interpretation**:
                - Classify the query as:
                    - **Conversational**: General or casual (e.g., "How's it going?").
                    - **Context Update**: Requests to update user/company context (e.g., "set my role to CEO").
                    - **Analytical**: Requires data sources or agents with a detailed response (triggered by keywords like "detailed," "comprehensive," "in-depth," "full analysis", "full report", "breakdown").
                    - **Analytical Concise**: Requires data sources or agents but with a brief, summarized response (default for analytical queries; reinforced by keywords like "brief," "summary," "quick," "concise", "overview").
                    - **Ideation**: If the user wants to ideate on any idea (may be future projects, roadmaps, strategies, or specific ideas).
                    - **Provider Recommendation**: Requests service provider matching (e.g., "find providers for roadmap ID 123").
                    - **Demand Profiling**: Queries mentioning "demand profiling" or "look at all my demand" (e.g., "look at all my demand and do demand profiling").
                    - **Journal Analysis**: Queries about recent user activities or session summaries (e.g., "recent activities", "what have I been working on?", "summarize my sessions").
                    - **Resource Analysis**: Queries about team, staff, availability, skills, capacity, allocation (e.g., "who's free in Q2?", "developers for AI project", "current team structure").
                - If query type is analytical:
                    - Default to `response_type="analytical_concise"` for a summarized response (100–150 words, focusing on key metrics and insights) unless keywords like "detailed," "comprehensive," "in-depth," "full analysis", "full report", or "breakdown" are detected, in which case set `response_type="analytical"`.
                    - Split query into sub-queries and trigger appropriate data sources/agents.
                    - Add this logic to `planning_rationale`.
                - For journal analysis queries:
                    - Trigger `get_journal_data` with an `hours` parameter (default to 168 hours for the last week if not specified).
                    - Include `data_sources_to_trigger` with `get_journal_data` and set `data_source_params.get_journal_data.hours` to an appropriate value based on query context (e.g., "last 24 hours" → 24, "recent activities" → 168).
                    - Suggest combination logic to integrate journal data with roadmaps or projects (e.g., "Correlate recent session activities with roadmap ID 123 updates").
                - For demand profiling queries:
                    - Trigger the `roadmap` agent with a sub-query like "Analyze all demand across roadmap categories".
                    - Include `data_sources_to_trigger` like `resource_data`, `get_snapshots`, or `get_journal_data` for additional dimensions (e.g., resource allocation, portfolio metrics, recent activities).
                    - Suggest slicing and dicing by categories (e.g., technology, priority, timeline) in `combination_logic`.
                - For roadmap-related queries (e.g., "analyze roadmap ID 123", "roadmap details"), trigger the `roadmap` agent in `agents_to_trigger` with a sub-query like "Analyze roadmap ID 123".
                - For customer solution queries (e.g., "list customer solutions", "details of EY Atlas"), trigger `customer_existing_solutions` in `data_sources_to_trigger`.
                - For provider recommendation queries, trigger `find_suitable_service_provider` with parameters extracted from the query (e.g., roadmap_id, project_id, tag).
                - For conversational queries, plan a natural response without triggering data sources unless explicitly needed.
                - For context updates, trigger the appropriate action (e.g., `set_user_designation`, `set_company_context`).
                - For queries related to Trmeric, always trigger `some_info_about_trmeric` and analyze in detail using the company context.
                - For queries mentioning uploaded files, session files, or documents (e.g., "analyze my uploaded report", "use my session files for roadmap analysis"):
                    - Trigger `current_session_uploaded_files` in `data_sources_to_trigger`.
                    - Extract S3 keys from session context (e.g., stored in `TangoDao` for the session) or request clarification if not provided.
                    - Include in `data_source_params.current_session_uploaded_files`:
                        - `files_s3_keys_to_read`: List of S3 keys for session files.
                    - Suggest combination logic to integrate file content with roadmaps, projects, or customer solutions (e.g., "Extract requirements from uploaded files and match to roadmap ID 123").
                - **For Resource Queries**:
                    - Detect keywords: "team", "resource", "staff", "who is", "available", "free", "capacity", "skills", "developer", "PM", "architect", "allocation", "eligible for project"
                    - Extract:
                        - `resource_name`: from names or roles (e.g., "John Doe", "developer", "PM")
                    - If project ID mentioned (e.g., "resources for project 789"), set `eligibleProjects=[789]`
                    - If no filters → trigger `resource_data` with empty params (returns all active)
                    brazier
                    - Example: "Who is available in April for project 100?"
                        - `start_date="2025-04-01"`, `end_date="2025-04-30"`, `eligibleProjects=[100]`
                    - If the query indicates a geographic preference (location, country, city, region, timezone, nearshore, offshore, onsite, remote, or any geographic keyword), map it to the `country` attribute inside `resource_data`.
                    
                - **For financial or spend-related queries**:
                    - Detect keywords:
                        "cost", "spend", "financial", "CAPEX", "OPEX", 
                        "vendor", "procurement", "purchase order", 
                        "budget used", "liability"
                    - Trigger:
                        `data_sources_to_trigger = ["project_spend_data"]`
                    - Extract project IDs from the query.
                    - If project IDs are not explicitly mentioned but the query refers to a roadmap or portfolio:
                        - Also trigger the `roadmap` or `project` agent to derive project IDs.


            2. **Context Validation**:
                - Check `user_info_string` for user designation and company context.
                - If designation is missing, trigger `set_user_designation` and request a role.
                - If company context is missing, trigger `set_company_context` and suggest providing a website URL.
                - For provider-related queries, verify `tenantID` is provided or derivable from context. If not, set `clarification_needed` with a message like "Please specify the tenant ID."

            3. **Provider Recommendation Handling**:
                - Detect queries requesting provider recommendations (e.g., "find providers for roadmap ID 123", "recommend service providers for project 456").
                - Extract roadmap_id or project_id from the query using regex or keyword analysis (e.g., "roadmap ID 123" → roadmap_id=123, tag="roadmap").
                - Set `actions_to_trigger` to include `find_suitable_service_provider` with `action_params`:
                    - roadmap_id: int (if roadmap context detected)
                    - project_id: int (if project context detected)
                    - tag: "roadmap" or "project"
                - If roadmap_id or project_id cannot be extracted, set `clarification_needed = True` with a message requesting the ID.

            4. **Roadmap Query Handling**:
                - For queries mentioning roadmaps (e.g., "analyze roadmap ID 123", "roadmap details"), trigger the `roadmap` agent in `agents_to_trigger` with a sub-query like "Analyze roadmap ID 123".
                - Only trigger `create_roadmaps` if the query explicitly requests roadmap creation followed by ideation.
                - If a roadmap_id is mentioned with provider intent, include `find_suitable_service_provider` with `roadmap_id` and `tag="roadmap"`.

            5. **Customer Solutions Query Handling**:
                - Detect queries mentioning customer solutions (e.g., "list customer solutions", "details of EY Atlas").
                - Trigger `customer_existing_solutions` in `data_sources_to_trigger` with no additional parameters (uses tenant_id internally).
                - If a specific solution is mentioned (e.g., "EY Atlas"), include a filter in the sub-query to focus on that solution.
                - Suggest combination logic to integrate solution data with roadmaps, projects, or provider recommendations (e.g., "Match customer solutions to roadmap requirements").

            6. **Snapshot Query Handling (Including Risk Reports)**:
                - Detect queries mentioning snapshots or risks (e.g., "value snapshot for portfolios 10 and 20", "risk report for Q1 2025").
                - For risk-related queries (e.g., "risk report for Q1 2025", "project risks for portfolio ID 5"):
                    - Extract quarter (e.g., "Q1 2025" → quarter_start="2025-01-01", quarter_end="2025-03-31") using regex or keyword analysis.
                    - Extract portfolio_ids using regex (e.g., "portfolio[s]? ID[s]? (\d+(?:,\s*\d+)*)" → [5, 10]).
                    - Trigger `get_snapshots` with `snapshot_type="risk_snapshot"`, `quarter_start`, `quarter_end`, and optional `portfolio_ids`.
                    - If quarter or portfolio_ids are missing, set `clarification_needed = True` with a message like "Please specify the quarter (e.g., Q1 2025) or portfolio ID(s) for the risk report."
                - For other snapshot queries (value, portfolio, performance):
                    - Extract portfolio_ids for filtering, if specified.
                    - Use appropriate `snapshot_type` ("value_snapshot_last_quarter", "portfolio_snapshot", "performance_snapshot_last_quarter", "risk_snapshot").
                - Example: For "risk report for Q1 2025 for portfolios 5, 10", set:
                    - `data_sources_to_trigger`: ["get_snapshots"]
                    - `data_source_params.get_snapshots`: {{"snapshot_type": "risk_snapshot", "quarter_start": "2025-01-01", "quarter_end": "2025-03-31", "portfolio_ids": [5, 10]}}
                - Monthly Savings Snapshot Schema:
                    - Example: For "monthly savings report for X... programs", set:
                        - `data_sources_to_trigger`: ["get_snapshots"]
                        - `data_source_params.get_snapshots`: {{"snapshot_type": "monthly_savings_snapshot", "program_ids": []}}

            7. **Portfolio Filter Handling**:
                - Detect queries mentioning portfolio IDs (e.g., "value snapshot for portfolios 10 and 20", "risk report for portfolio ID 5").
                - Extract portfolio_ids using regex (e.g., "portfolio[s]? ID[s]? (\d+(?:,\s*\d+)*)") to capture single or multiple IDs (e.g., "portfolio IDs 10, 20" → [10, 20]).
                - For snapshot queries (including risk reports):
                    - If portfolio_ids are extracted, include them in `data_source_params.get_snapshots.portfolio_ids` as a list of integers.
                    - If a single portfolio_id is mentioned for portfolio_snapshot, include it in `data_source_params.get_snapshots.portfolio_id` as an integer.
                    - If no portfolio_ids are specified but the query implies a portfolio filter, set `clarification_needed = True` with a message like "Please specify portfolio ID(s) for the snapshot."
                - Example: For "risk report for Q1 2025 for portfolios 5, 10", set:
                    - `data_sources_to_trigger`: ["get_snapshots"]
                    - `data_source_params.get_snapshots`: {{"snapshot_type": "risk_snapshot", "quarter_start": "2025-01-01", "quarter_end": "2025-03-31", "portfolio_ids": [5, 10]}}

            8. **Holistic Query Analysis**:
                - For every query, adopt a **holistic approach** by:
                    - Evaluating all available data sources (`web_search`, `resource_data`, `integration_data`, `get_snapshots`, `customer_existing_solutions`, `provider_storefront_data`, `provider_quantum_data`, `some_info_about_trmeric`, `current_session_uploaded_files`, `get_journal_data`) for relevance.
                    - Cross-referencing user context (`user_info_string`, tenant type, prior conversation) to infer additional needs (e.g., industry-specific insights for Trmeric queries).
                    - Anticipating secondary implications (e.g., for a roadmap query, consider resource availability, provider recommendations, customer solutions compatibility, and recent user activities).
                    - Exploring related dimensions (e.g., for demand profiling, slice by technology, priority, timeline, and strategic alignment; for journal queries, analyze session patterns).
                    - Including relevant agents (e.g., roadmap, project) to provide a comprehensive view.
                - Document the thought process in `planning_rationale`, explaining why specific data sources, agents, or actions were selected or excluded.
                - Example: For "analyze roadmap ID 123," consider not only the roadmap agent but also `resource_data` for team availability, `customer_existing_solutions` for solution alignment, `get_journal_data` for recent user interactions, and `find_suitable_service_provider` for potential provider matches, even if not explicitly requested.

            10. **Response Planning**:
                - For conversational queries, set `response_type` to "conversational".
                - For context updates, trigger the appropriate action and provide a confirmation message with `response_type` set to "context_update".
                - For analytical queries:
                    - **Default Behavior**: Set `response_type` to "analytical_concise" for a summarized response (100–150 words, focusing on key metrics and insights) unless specific keywords indicate a detailed response.
                    - **Detailed Response Keywords**: If the query contains keywords like "detailed," "comprehensive," "in-depth," "full analysis", "full report," or "breakdown," set `response_type` to "analytical" for a detailed response with full tables and comprehensive analysis.
                    - **Concise Response Keywords**: If the query contains keywords like "brief," "summary," "quick," "concise," or "overview," reinforce the `analytical_concise` response type.
                    - Consider all relevant data sources, agents, and contextual factors (e.g., user role, industry, prior conversation) to ensure a holistic response, even if not explicitly mentioned.
                    - Specify `agents_to_trigger`, `data_sources_to_trigger`, and `combination_logic` for both analytical types.
                - For provider recommendations, prioritize `find_suitable_service_provider` in `actions_to_trigger` and set `response_type` to "provider_recommendation".
                - For roadmap queries, prioritize the `roadmap` agent unless creation is explicitly requested.
                - For customer solution queries, include `customer_existing_solutions` in `data_sources_to_trigger` and suggest integration with other data (e.g., roadmaps, providers).
                - For journal queries, include `get_journal_data` in `data_sources_to_trigger` and suggest integration with other data (e.g., roadmaps, projects).
                - For snapshot queries with portfolio filters, include `portfolio_ids` in `data_source_params`.
                - For queries where clarification is needed: set `response_type` to "clarification_needed=True", but avoid this in ongoing conversations by leveraging prior context (`conv`).
                - If user wants to fetch data and present in template then use intent - present_data_in_template.

            11. **Rules**:
                - Identify if the query involves:
                    - Roadmaps (future projects, plans, or demand, e.g., "analyze roadmap ID 123")
                    - Projects (ongoing initiatives, e.g., "project details for ID 456")
                    - Trmeric knowledge (e.g., "portfolio performance")
                    - External insights (e.g., "industry trends for AI roadmaps")
                    - Team resources (e.g., "current team structure", "who's available", "developer capacity")
                    - Integrations (e.g., "Jira tickets", "ADO work items")
                    - Snapshots (e.g., "last quarter value snapshot")
                    - Provider recommendations (e.g., "find providers for roadmap ID 123")
                    - Storefront data (provider tenants only, e.g., "case studies")
                    - Quantum data (provider tenants only, e.g., "transformation roadmap")
                    - Customer solutions (e.g., "list customer solutions", "details of EY Atlas")
                    - Journal data (e.g., "recent activities", "summarize my sessions")
                    - Portfolio filters (e.g., "value snapshot for portfolio IDs 10, 20")
                - For roadmap queries:
                    - Trigger `roadmap` agent with a sub-query like "Analyze roadmap ID <id>" if an ID is provided.
                    - Only trigger `create_roadmaps` for explicit creation requests (e.g., "create a roadmap").
                    - If a roadmap_id is mentioned with provider intent, include `find_suitable_service_provider` with `roadmap_id` and `tag="roadmap"`.
                - For project queries:
                    - Trigger `project` agent with a sub-query like "Analyze project ID <id>" if an ID is provided.
                    - Only trigger `create_projects` for explicit creation requests (e.g., "create a project").
                - For customer solution queries:
                    - Trigger `customer_existing_solutions` with no parameters.
                    - If a specific solution is mentioned (e.g., "EY Atlas"), include a sub-query like "Details of solution EY Atlas".
                    - Suggest combination logic to integrate with roadmaps, projects, or provider recommendations (e.g., "Match EY Atlas capabilities to roadmap requirements").
                - For journal queries:
                    - Trigger `get_journal_data` with an `hours` parameter.
                    - Extract timeframe from the query (e.g., "last 24 hours" → hours=24, "last week" → hours=168).
                    - If no timeframe is specified, default to `hours=168`.
                    - Suggest combination logic to correlate session summaries with roadmaps, projects, or other activities (e.g., "Analyze recent session activities to identify updates to roadmap ID 123").
                - For external insights:
                    - Trigger `web_search` with web_queries (e.g., "AI trends" → ["AI industry trends"]).
                - For team resources:
                    - Trigger `resource_data` with rich filtering.
                    - Extract:
                        - `name` from person mentions
                        - `role`, `primary_skill`, `skill_keyword` from job/skill terms
                        - `is_external=True` + `external_company_name` if "vendor", "partner", "external"
                        - `org_team_name` or `org_team_id` from team references
                        - `min_allocation`/`max_allocation` from "under 80%", "at least 50%"
                        - `available_only=True` if "free", "available", "capacity"
                        - `selected_projection_attrs` → optimize payload (e.g., minimal for summary, full for analysis)
                    - Example: "Available Python devs on internal teams under 70% load"
                        → `primary_skill="Python"`, `is_external=False`, `max_allocation=70`, `available_only=True`
                    - For any location-based intent in resource queries, always use the `country` attribute as the location field. Do not use provider_company_address or any other field for geographic grouping.
                - **For integrations**:
                    - Trigger `integration_data` with **three** parameters:
                        - `integration_name` – required (e.g. `"jira"`, `"github"` …)
                        - `project_ids` – list of **Trmeric** project IDs to consider for this (empty → all accessible projects)
                        - `user_detailed_query` – natural-language filter (used only for on-prem Jira)
                        
                - For snapshots:
                    - Trigger `get_snapshots` with params (snapshot_type, last_quarter_start, last_quarter_end, portfolio_id, portfolio_ids).
                    - If no portfolio is specified, pass all portfolio IDs.
                    - **Snapshot Data Schema**:
                        - value_snapshot_last_quarter: Metrics like value_delivered, cost_incurred, roi for last quarter, filterable by portfolio_ids.
                        - portfolio_snapshot: Portfolio metrics like total_projects, active_projects, budget_allocation for a specific portfolio_id or portfolio_ids.
                        - performance_snapshot_last_quarter: Performance metrics like kpi_achievement, success_rate, delays for last quarter, filterable by portfolio_ids.
                        - risk_snapshot: Comprehensive risk report.
                - Cycle Time Analysis:
                    - For roadmap or project queries, include cycle time analysis using `approval_history`:
                        - Calculate time elapsed in each stage (e.g., Intake, Approved, Elaboration) using `request_date`, `from_state`, `to_state`.
                        - Example: If a roadmap moved from Intake to Approved, calculate time between `request_date` entries.
                        - For current stage, use `current_state` and calculate time from latest `request_date` to current date.
                        - Use `approval_history` to track stage transitions and durations.
                        - Include current stage duration (current date - latest `request_date`).
                - For demand profiling:
                    - Trigger `roadmap` agent to fetch all roadmaps.
                    - Categorize by `category` (e.g., technology, business unit), `priority`, `budget`, `start_date`, `end_date`.
                    - Include `resource_data` for allocation metrics, `get_snapshots` for portfolio metrics, and `get_journal_data` for recent activities.
                    - Suggest slicing by additional dimensions (e.g., strategic alignment, team count).
                - For queries like "analyze my uploaded report for roadmap ID 123":
                    - Set `data_sources_to_trigger`: ["current_session_uploaded_files", "roadmap"]
                    - Set `data_source_params.current_session_uploaded_files`: {{"files_s3_keys_to_read": [<s3_keys_from_session>]}}
                    - Set `agents_to_trigger`: ["roadmap"]
                    - Set `roadmap_query`: "Analyze roadmap ID 123"
                    - Set `combination_logic`: "Extract key requirements or metrics from uploaded files and align with roadmap evaluations for ID 123."
                - For queries related to create_or_update_milestone_or_risk_project_status:
                    - Initiate create_or_update_milestone_or_risk_project_status.
                    - Carefully understand if the user wants to create milestone, update status, or risk, or multiple.
                    - If multiple, create multiple line items with different update types.
                - For provider recommendations:
                    - Trigger `find_suitable_service_provider` with roadmap_id or project_id and tag.
                - For provider tenants (tenant_type="provider"):
                    - Trigger `provider_storefront_data` or `provider_quantum_data` for queries like "list case studies" or "transformation roadmap".
                    - Map query intent to data sources (e.g., "show case studies" → ["case_studies"]).
                - If user is interested in learning more about Trmeric, trigger `some_info_about_trmeric` with user queries finding more dimensions to query.
                - Suggest combination logic for all triggered sources (e.g., "Integrate customer solutions with roadmap evaluations and provider recommendations for strategic fit").
                - Provide a brief rationale (e.g., "Triggered customer_existing_solutions for query about customer solutions").
                - For any ideation query or analysis:
                    - In the context, you will see information about the company (and website URL).
                    - Perform a full analysis of the website URL and related queries to the user query using `web_search` and collect all data to give the best response to the user.
                - For recent updates queries (e.g., "recent updates"):
                    - Trigger `project` agent to check for recently created projects, status updates, delivered milestones, or upcoming milestones.
                    - Trigger `get_journal_data` to fetch recent user activities (default `hours=168`).
                    - Set `response_type` to "analytical_concise" for a short overview.
                    - Suggest a follow-up for a detailed overview if needed.
                - If the user requests an action that is NOT in the available actions list  of actions in Tango
                    (e.g., delete, archive, rename), do NOT map it to a similar-sounding action.
                    Instead:
                        - Set response_type to "clarification_needed"
                        - Set clarification_needed to true
                        - Set clarification_message to explain that this action is not currently 
                        supported in Tango, and suggest what IS available.

            11. **Identifying Trmeric Queries**:
                - Detect queries explicitly mentioning "Trmeric" or implying interest in Trmeric’s capabilities, offerings, or services (e.g., "What is Trmeric?", "How can Trmeric help my business?", "Trmeric features").
                - Keywords to identify Trmeric-related queries include: "Trmeric", "Trmeric platform", "Trmeric capabilities", "Trmeric benefits", "Trmeric use cases", or phrases indicating curiosity about Trmeric’s functionality (e.g., "What can Trmeric do?", "How does Trmeric work?").
                - If the query is ambiguous (e.g., "Tell me about Trmeric"), assume the user seeks a broad overview of Trmeric’s capabilities and trigger `some_info_about_trmeric`.

            12. **Query Formulation for `some_info_about_trmeric`**:
                - Always trigger the `some_info_about_trmeric` data source for Trmeric-related queries.
                - Generate multiple sub-queries to ensure comprehensive coverage of Trmeric’s capabilities, tailored to the user’s intent and context:
                    - For general queries (e.g., "What is Trmeric?"), include sub-queries like:
                        - "Overview of Trmeric platform"
                        - "Key features of Trmeric"
                        - "Primary use cases for Trmeric"
                    - For specific queries (e.g., "How can Trmeric help my business?"), incorporate user context from `user_info_string` (e.g., user designation, company industry) and generate sub-queries like:
                        - "How Trmeric supports [industry] businesses"
                        - "Trmeric benefits for [user role, e.g., CEO, Project Manager]"
                        - "Trmeric features relevant to [company size or type]"
                    - For feature-specific queries (e.g., "Trmeric roadmap features"), include sub-queries like:
                        - "Trmeric roadmap planning capabilities"
                        - "Trmeric roadmap analytics features"
                        - "Integration of Trmeric roadmaps with [specific tools, if mentioned]"
                    - For queries referencing a specific domain (e.g., "Trmeric for AI automation"), add sub-queries like:
                        - "Trmeric use cases for AI automation"
                        - "Trmeric tools for AI-driven workflows"
                    - Ensure sub-queries are concise, relevant, and aligned with the vector document’s structure for `some_info_about_trmeric`.

            examples -- 
            queries like 
                - What's standing in the way of getting this done? - Any bottlenecks on my requests that we need to bust through?
                    first we need clarification... what is being talked about. if roadmap which roadmap... or all roadmap. 
                - From ideation to execution - let's see where my requests are
                    look at all roadmaps (aka demands) and check their approval status details
                - can you give me some ideas
                    help user by giving ideas not by asking clarifying question
                - Strategize the stack — let’s rank demands by what matters the most
                    thought: stick to user query:
                        help the user by ranking their demands and using a thought of why this rank
                - Quick summary of roadmap ID 123
                    set response_type to "analytical_concise" and trigger roadmap agent with sub-query "Summarize roadmap ID 123"
                - Briefly list customer solutions
                    set response_type to "analytical_concise" and trigger customer_existing_solutions with sub-query "Summarize customer solutions"
                - Who is available in Q2 for project 789?
                    "data_sources_to_trigger": ["resource_data"], "data_source_params": {{"resource_data": {{"start_date": "2025-04-01", "end_date": "2025-06-30", "eligibleProjects": [789]}}}}

            ### Output JSON
            ```json
            {{
                "response_type": "conversational" | "context_update" | "analytical" | "analytical_concise" | "ideation" | "provider_recommendation" | "present_data_in_template",
                "agents_to_trigger": ["roadmap", "project"] | [],
                "roadmap_query": str | null,
                "project_query": str | null,
                "data_sources_to_trigger": {available_data_sources} | [],
                "data_source_params": {{
                    "web_search": {{"web_queries": [], "website_urls": []}},
                    "resource_data": {{
                        "resource_ids": [] | null,
                        "name": str | null,
                        "primary_skill": str | null,
                        "skill_keyword": str | null,
                        "role": str | null,
                        "is_external": bool | null,
                        "external_company_name": str | null,
                        "org_team_name": str | null,
                        "org_team_id": int | null,
                        "min_allocation": float | null,
                        "max_allocation": float | null,
                        "available_only": bool | null,
                        "selected_projection_attrs": [] | null,
                        "country": string | null
                    }},
                    "idea_data": {{
                        "idea_ids": [] | null,
                        "title": str | null,
                        "category": str | null,
                        "current_state": int | null,
                        "org_strategy_align": str | null,
                        "min_budget": float | null,
                        "max_budget": float | null,
                        "start_date": str | null,
                        "end_date": str | null,
                        "portfolio_ids": [] | null,
                        "projection_attrs": [] | null
                    }},
                    "fetch_customer_templates": {{
                        "selected_projection_attrs": [] | null,
                        "category": string | null
                    }}
                    "integration_data": {{"integration_name": <options are like: jira, ado , sheet etc project management tools> , "project_ids": [], "user_detailed_query": ""}},
                    "get_snapshots": {{"snapshot_type": str, "last_quarter_start": str | null, "last_quarter_end": str | null, "portfolio_id": int | null, "kwargs": {{"portfolio_ids": []}}}},
                    "provider_storefront_data": {{"data_sources_array": []}},
                    "provider_quantum_data": {{"data_sources_array": []}},
                    "customer_existing_solutions": {{}},  // No parameters needed
                    "some_info_about_trmeric": {{"queries": []}},
                    "current_session_uploaded_files": {{"files_s3_keys_to_read": []}},
                    "get_journal_data": {{"hours": int | null}},
                    "project_spend_data": {{
                        "project_ids": [] | null,
                        "spend_types": [] | null
                    }},
                }},
                "actions_to_trigger": [<select among -- {self.actions_to_take.keys()}>],
                "action_params": {{
                    "set_user_designation": {{"designation": str | null}},
                    "set_company_context": {{"org_info": str | null, "website_url": str | null}},
                    "create_roadmaps": {{}},
                    "create_projects": {{}},
                    "create_or_update_milestone_or_risk_project_status": [
                        {{
                            "project_id": "",
                            "update_type": "", // one of "milestone", "status", "risk"
                        }},...  
                    ],
                    "find_suitable_service_provider": {{"roadmap_id": int | null, "project_id": int | null, "tag": "roadmap" | "project"}},
                    "generate_onboarding_report": {{ "lookback_hours" : <int> }}
                }},
                "combination_logic": str,
                "planning_rationale": str, // always output this
                "clarification_needed": bool,
                "clarification_message": str | null,
                "user_wants_full_list": bool,
            }}
            ```
            Very Important Note  :: 
                - If it is an ongoing conversation and user is asking something on something in the chat, don’t make clarification_needed true.
                - Only trigger snapshots if asked in query.
                - Always output planning_rationale so that your thoughts are known by other people.
                - Only include non-empty fields.
                - Giving the action params properly is a must.
            Example: If find_suitable_service_provider, then: "actions_to_trigger": ["find_suitable_service_provider"], "action_params": {{"find_suitable_service_provider": {{"roadmap_id": 123, "tag": "roadmap"}}}}
            Example: If value snapshot with portfolio filter, then: "data_sources_to_trigger": ["get_snapshots"], "data_source_params": {{"get_snapshots": {{"snapshot_type": "value_snapshot_last_quarter", "last_quarter_start": "2025-01-01", "last_quarter_end": "2025-03-31", "kwargs": {{"portfolio_ids": [10, 20]}}}}}}
            Example: If customer solutions query, then: "data_sources_to_trigger": ["customer_existing_solutions"], "data_source_params": {{"customer_existing_solutions": {{}}}}
            Example: If concise Roadmap summary, then: "response_type": "analytical_concise", "agents_to_trigger": ["roadmap"], "roadmap_query": "Summarize roadmap ID 123"
            Example: If user ask for recent updates - check if any project got created recently, status updates made recently, milestones got delivered recently or upcoming milestones - short analysis initiate agents_to_trigger to get the required info - then ask for detailed overview.
            Example: for recent updates - always check project. crecently created/updates/milestone created, status updates made etc, and 
            very important for you to think in complex terms what all user can want/need? also think if he wants descriptive or short answer and respond properly
        """

        try:
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user=f"Plan response for: '{query}'. JSON output is mandatory in the format defined here. Only include non-empty fields. roadmaps (aka demands)")
            response = self.llm.run(chat_completion, ModelOptions(model="gpt-4.1", max_tokens=3000, temperature=0.3), 'tango::master::plan', logInDb=self.logInDb)
            plan = extract_json_after_llm(response)
            appLogger.info({"function": "plan_combined_analysis_success", "tenant_id": self.tenant_id, "query": query, "plan": plan})
            return plan
        except json.JSONDecodeError as e:
            appLogger.error({"function": "plan_combined_analysis_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "response": response})
            raise ValueError(f"LLM response is not valid JSON: {response}")
        except Exception as e:
            appLogger.error({"function": "plan_combined_analysis_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            raise
        
        
    def process_combined_query(self, query: str, roadmap_agent: RoadmapAgent, project_agent: ProjectAgent, filters: Optional[Dict] = None, mode="default"):
        appLogger.info({"function": "process_combined_query_start", "tenant_id": self.tenant_id, "user_id": self.user_id, "query": query})

        RedClient.delete_key(key_set=f"interrupt_requested::userID::{self.user_id}")
        # program_state = ProgramState.get_instance(self.user_id)
        # program_state.set("interrupt_requested", False)   #reset for new generation

        # if mode != "only_data":
        #     title_thread = threading.Thread(target=self.generate_chat_title, args=(self.log_info.get("session_id"), self.log_info))
        #     title_thread.start()
        if self.socketio:
            self.socketio.emit("custom_agent_v1_ui", {"event": "refresh_titles"}, room=self.client_id)

        # self.socketSender.sendSteps("Creating Blueprint", False)
        self.socketSender.sendSteps("Initializing Analysis", False)
        self.socketSender.sendSteps("Initializing Analysis", True, 0, 0.1)
        
        self.socketSender.sendSteps("Crafting Analysis Blueprint", False,0, 1)
        try:
            plan = self.plan_combined_analysis(query)
            appLogger.info({"function": "process_combined_query_plan", "tenant_id": self.tenant_id, "plan": plan})
            # self.socketSender.sendSteps("eating Blueprint", True)
            
            # self.socketSender.sendSteps("Analysis Blueprint Ready", True)
            self.socketSender.sendSteps("Crafting Analysis Blueprint", True)
            print("view_combined_analysis plan", json.dumps(plan, indent=2))

            # # Handle clarification needed
            if plan.get("clarification_needed", False) or plan.get("response_type") == "clarification_needed":
                appLogger.info({"function": "process_combined_query_clarification", "tenant_id": self.tenant_id, "message": plan.get("clarification_message", "Please clarify your query.")})
                yield plan.get("clarification_message", "Please clarify your query.")
                return

            results = {"action_results": []}

            actions_to_trigger = plan.get("actions_to_trigger", [])
            if "create_roadmaps" not in actions_to_trigger:
                TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(session_id=self.sessionID, user_id=self.user_id, key="create_roadmap_from_analyst_confirm")
                appLogger.info({"function": "process_combined_query_reset_confirmation", "tenant_id": self.tenant_id, "message": "Reset create_roadmap_from_analyst_confirm state"})

            if "create_projects" not in actions_to_trigger:
                TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(session_id=self.sessionID, user_id=self.user_id, key="create_project_from_analyst_confirm")
                appLogger.info({"function": "process_combined_query_reset_confirmation", "tenant_id": self.tenant_id, "message": "Reset create_project_from_analyst_confirm state"})

            action_params = plan.get("action_params", {})
            for action in actions_to_trigger:
                self.socketSender.sendSteps(f"Executing action", False)
                if action == "set_user_designation":
                    designation = action_params.get("set_user_designation", {}).get("designation")
                    if designation:
                        self.actions_to_take["set_user_designation"](designation)
                        self.user_info_string += f"\nUpdated Role: {designation}"
                        results["action_results"].append(f"User designation updated to {designation}.\n")
                    else:
                        results["action_results"].append("Please provide a valid designation to update.")

                elif action == "set_company_context":
                    website_url = action_params.get("set_company_context", {}).get("website_url")
                    if website_url:
                        web_result = self._call_web_agent(**{"website_urls": [website_url]})
                        self.actions_to_take["set_company_context"](json.dumps(web_result, indent=2))
                        results["action_results"].append(f"Company context updated with information from {website_url}.\n{json.dumps(web_result, indent=2)}")
                    else:
                        results["action_results"].append("Company context is missing. Please provide your company website URL.")

                elif action == "create_roadmaps":
                    print("in create roadmap --")
                    cr_confirm = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="create_roadmap_from_analyst_confirm", session_id=self.sessionID)
                    print("in create roadmap  -- ", len(cr_confirm), cr_confirm)
                    if len(cr_confirm) > 0:
                        conv = self.base_agent.conversation.format_conversation()
                        results["action_results"].append(self.actions_to_take["create_roadmaps"](json.dumps(conv, indent=2)))
                    else:
                        results["action_results"].append("Very Very important to inform user that confirmation is required to proceeed with actual roadmap creation. This is essential to trigger roadmap creation agent")

                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key="create_roadmap_from_analyst_confirm", value="", session_id=self.sessionID)


                elif action == "create_projects":
                    print("in create create_projects --")
                    conv = self.base_agent.conversation.format_conversation()
                    results["action_results"].append(self.actions_to_take["create_projects"](json.dumps(conv, indent=2)))
                
                
                elif action == "create_or_update_milestone_or_risk_project_status":
                    args = action_params.get("create_or_update_milestone_or_risk_project_status", []) or []
                    conv = self.base_agent.conversation.format_conversation()
                    results["action_results"].append(self.actions_to_take["create_or_update_milestone_or_risk_project_status"](args, json.dumps(conv, indent=2)))
                    
                elif action == "find_suitable_service_provider":
                    cr_confirm = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="find_suitable_service_provider_from_analyst_confirm", session_id=self.sessionID)
                    # if len(cr_confirm) > 0:
                    params = action_params.get("find_suitable_service_provider", {})
                    results["action_results"].append(self.actions_to_take["find_suitable_service_provider"](json.dumps(params, indent=2)))
                    # else:
                    #     results["action_results"].append("Please confirm once to trigger the find best provider. Because this will trigger the find best provider agent.")

                    TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key="find_suitable_service_provider_from_analyst_confirm", value="", session_id=self.sessionID)

                elif action == "generate_onboarding_report":
                    self.socketSender.sendSteps("Generating Onboarding Report", False)
                    print("action params ", action_params)
                    lookback_hours = (action_params.get("generate_onboarding_report") or {}).get("lookback_hours") or 2160
                    report = self.actions_to_take["generate_onboarding_report"](lookback_hours)
                    
                    # If it's the only action, stream the report directly
                    if len(actions_to_trigger) == 1:
                        self.socketSender.sendSteps("Generating Onboarding Report", True)
                        yield report
                        return
                    else:
                        results["action_results"].append(report)
                    self.socketSender.sendSteps("Generating Onboarding Report", True)

                # self.socketSender.sendSteps(f"Triggering action {action}", True)
                self.socketSender.sendSteps(f"Executing action", True)

            # Proceed with original query processing
            agents_to_trigger = plan.get("agents_to_trigger", [])
            data_sources_to_trigger = plan.get("data_sources_to_trigger", []) or []

            print("data_sources_to_trigger", data_sources_to_trigger)

            yield ""

            with ThreadPoolExecutor(max_workers=8) as executor:
                agent_futures = {}
                if "roadmap" in agents_to_trigger and plan.get("roadmap_query"):
                    self.socketSender.sendSteps("Retrieving Roadmap Data", False)
                    # self.socketSender.sendSteps(f"Triggering roadmap agent", False)
                    agent_futures[executor.submit(self.run_agent, roadmap_agent, plan["roadmap_query"], filters)] = "roadmap"
                if "project" in agents_to_trigger and plan.get("project_query"):
                    self.socketSender.sendSteps("Retrieving Project Data", False)
                    # self.socketSender.sendSteps(f"Triggering project agent", False)
                    agent_futures[executor.submit(self.run_agent, project_agent, plan["project_query"], filters)] = "project"

                source_futures = {executor.submit(self.run_data_source, name, (plan.get("data_source_params", {}) or {}).get(name, {})): name for name in data_sources_to_trigger}

                for future in as_completed(agent_futures):
                    name = agent_futures[future]
                    # self.socketSender.sendSteps(friggering {name} agent", True)
                    try:
                        results[name] = future.result()
                        appLogger.info({"function": f"process_combined_query_agent_{name}_success", "tenant_id": self.tenant_id, "agent": name})
                        # yield f"\n### {name.capitalize()} Evaluations\n"
                        for response in results[name]:
                            yield response
                        # self.socketSender.sendSteps(f"Triggering agent {name}", True)
                        # self.socketSender.sendSteps(f"Triggering project agent", False)
                        # self.socketSender.sendSteps(f"Triggering roadmap agent", False)
                        self.socketSender.sendSteps("Retrieving Roadmap Data", True)
                        self.socketSender.sendSteps("Retrieving Project Data", True)
                    except Exception as e:
                        appLogger.error({"function": f"process_combined_query_agent_{name}_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
                        yield f"Error processing {name} agent: {str(e)}\n"

                for future in as_completed(source_futures):
                    name = source_futures[future]
                    try:
                        results[name] = future.result()
                        appLogger.info({"function": f"process_combined_query_data_source_{name}_success", "tenant_id": self.tenant_id, "data_source": name})
                    except Exception as e:
                        appLogger.error({"function": f"process_combined_query_data_source_{name}_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
                        yield f"Error processing {name} data source: {str(e)}\n"

            roadmap_evals = roadmap_agent.eval_response
            project_evals = project_agent.eval_response

            # print("debug --- roadmap evals , project evals ", len(project_evals), len(roadmap_evals))

            if mode == "only_data":
                yield {
                    "roadmaps_data": roadmap_agent.ongoing_evaluation,
                    "projects_data": project_evals,
                    "web_search_data": results.get("web_search", {}),
                    "resource_data": results.get("resource_data", {}),
                    "integration_data": results.get("integration_data", {}),
                    "get_snapshots": results.get("get_snapshots", {}),
                }
                return

            for chunk in self.combine_results(
                roadmap_evals,
                project_evals,
                results,
                plan,
                query,
                results.get("current_session_uploaded_files", {}),
            ):
                yield chunk

            if mode != "only_data":
                title_thread = threading.Thread(target=self.generate_chat_title, args=(self.log_info.get("session_id"), self.log_info))
                title_thread.start()
            if self.socketio:
                self.socketio.emit("custom_agent_v1_ui", {"event": "refresh_titles"}, room=self.client_id)

        except Exception as e:
            appLogger.error({"function": "process_combined_query_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            if self.socketio:
                self.socketio.emit(
                    "custom_agent_v1_ui",
                    {"event": "stop_show_timeline"},
                    room=self.client_id,
                )
            raise e
            # yield {"error": f"Query processing failed: {str(e)}", "query": query}

    def run_agent(self, agent, query: str, filters: Dict) -> List[str]:
        appLogger.info({"function": "run_agent_start", "tenant_id": self.tenant_id, "agent_type": agent.__class__.__name__, "query": query})
        try:
            result = list(agent.process_query(query=query, filters=filters or {}))
            appLogger.info({"function": "run_agent_success", "tenant_id": self.tenant_id, "agent_type": agent.__class__.__name__, "result_count": len(result)})
            return result
        except Exception as e:
            appLogger.error({"function": "run_agent_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "agent_type": agent.__class__.__name__})
            raise

    def run_data_source(self, source_name: str, params: Dict) -> Dict:
        debugLogger.info(f"Running run_data_source with {source_name} -> {params}")
        try:
            # self.socketSender.sendSteps("Synthesizing Insights", False)
            # self.socketSender.sendSteps(fetching data from {source_name}", False)
            source = self.data_sources.get(source_name)
            if not source:
                appLogger.error({"function": "run_data_source_error", "error": f"Data source {source_name} not found", "tenant_id": self.tenant_id})
                raise ValueError(f"Data source {source_name} not found")
            # self.socketSender.sendSteps(fetching data from {source_name}", True)
            
            appLogger.error({"function": "run_data_source_init", "tenant_id": self.tenant_id, "user_id": self.user_id, "params": params, "source_name": source_name})
            result = source(**params)
            return result
        except Exception as e:
            appLogger.error({"function": "run_data_source_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id, "source_name": source_name})
            raise e

    def _generate_onboarding_report(self, lookback_hours: int = 2160) -> str:
        """Generate transformation/onboarding analysis report"""
        try:
            appLogger.info({"function": "_generate_onboarding_report", "tenant_id": self.tenant_id, "user_id": self.user_id, "lookback_hours": lookback_hours})
            
            # Generate the onboarding summary
            summary = onboarding_summary(self.user_id, self.tenant_id, hours=lookback_hours)
            
            if summary.get("success", False):
                # Format as markdown
                markdown_report = format_transformation_summary_markdown(summary)
                return markdown_report
            else:
                error_msg = summary.get("message", "Unable to generate onboarding report")
                return f"## Onboarding Report\n\nSorry, I couldn't generate your onboarding report: {error_msg}"
                
        except Exception as e:
            appLogger.error({"function": "_generate_onboarding_report_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            return f"## Onboarding Report\n\nAn error occurred while generating your onboarding report: {str(e)}"

    def combine_results(
        self,
        roadmap_evals,
        project_evals,
        results,
        plan: Dict,
        query: str,
        current_session_uploaded_files,
    ):
        web_search_results = results.get("web_search", {})
        resource_data = results.get("resource_data", {})
        integration_data = results.get("integration_data", {})
        snapshot_data =  results.get("get_snapshots", {})
        provider_storefront_data = results.get("provider_storefront_data", {})
        get_journal_data = results.get("get_journal_data") or ""
        provider_quantum_data = results.get("provider_quantum_data", {})
        action_results = results.get("action_results", {})
        some_info_about_trmeric = results.get("some_info_about_trmeric", {})
        customer_existing_solutions = results.get("customer_existing_solutions", {})
        idea_data = results.get("idea_data", {})
        customer_templates = results.get("fetch_customer_templates") or None
        project_spend_data = results.get("project_spend_data") or None
        
        # print("debug customer_existing_solutions data -- ", customer_existing_solutions)
        debugLogger.info({"function": "combine_results_start", "tenant_id": self.tenant_id, "query": query, "roadmap_evals_count": len(roadmap_evals), "project_evals_count": len(project_evals)})

        try:
            self.socketSender.sendSteps("Synthesizing Insights", False)
            # self.socketSender.sendSteps("📝 Finalizing Your Response", False, 0, 0.1)
            # combined_evals = {"roadmap_evaluations": roadmap_evals, "project_evaluations": project_evals}
            current_date = datetime.now().date().isoformat()
            conv = self.base_agent.conversation.format_conversation() if self.base_agent else "No prior conversation."
            tenant_type = TenantDao.checkCustomerType(self.tenant_id)
            available_data_sources = ["web_search", "resource_data", "integration_data", "get_snapshots", "customer_existing_solutions"]
            if tenant_type == "provider":
                available_data_sources.extend(["provider_storefront_data", "provider_quantum_data"])

            recent_queries_str = get_recent_queries(self.user_id)

            # Store query in TangoDao
            TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id, key="query_history", value=json.dumps({"query": query, "timestamp": current_date}), session_id=self.sessionID)
            TangoBreakMapUser.reset_count(self.user_id)

            # Reset confirmation state for non-roadmap queries
            actions_to_trigger = plan.get("actions_to_trigger", [])
            if "create_roadmaps" not in actions_to_trigger:
                TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(user_id=self.user_id, key="create_roadmap_from_analyst_confirm", session_id=self.sessionID)
                debugLogger.info({"function": "combine_results_reset_confirmation", "tenant_id": self.tenant_id, "message": "Reset create_roadmap_from_analyst_confirm state due to non-roadmap query"})

            # Helper function to append schemas dynamically
            def append_schemas(data_dicts: Dict) -> str:
                schemas = ""
                if data_dicts.get("current_session_uploaded_files"):
                    schemas += """
                        - **Session Uploaded Files Schema**:
                            - Dictionary mapping S3 keys to:
                                - content: Parsed file content (e.g., text, tabular data, or structured JSON).
                                - metadata: Object with s3_key, tenant_id, session_id, timestamp.
                    """
                if data_dicts.get("some_info_about_trmeric"):
                    schemas += """
                        - **Company Knowledge Schema**:
                            - Text chunks from company documents, including capabilities, best practices, and operational details.
                    """
                if data_dicts.get("resource_data"):
                    schemas += """
                        - **Resource Allocation Schema**:
                            - Project-specific commitments: List of entries (resource ID, project name, allocation percentage, start date, end date, first name, last name, role, skills).
                            - Resource details: List of resource profiles (role, allocation percentage, skills, experience years, active status, external status).
                    """
                if data_dicts.get("integration_data"):
                    schemas += """
                        - **Integration Data Schema**:
                            - Varies by integration_name ("jira", "github", "ado").
                            - Example for ADO: List of work items (work_item_id, project_id, title, status, assigned_to, effort_estimate, priority).
                    """
                if data_dicts.get("snapshot_data"):
                    schemas += """
                        - **Snapshot Data Schema**:
                            - Varies by snapshot_type:
                                - value_snapshot_last_quarter: Metrics like value_delivered, cost_incurred, roi for last quarter.
                                - portfolio_snapshot: Portfolio metrics like total_projects, active_projects, budget_allocation for a specific portfolio_id.
                                - performance_snapshot_last_quarter: Performance metrics like kpi_achievement, success_rate, delays for last quarter.
                                - risk_snapshot: Comprehensive risk report
                    """
                if data_dicts.get("provider_storefront_data") and tenant_type == "provider":
                    schemas += """
                        - **Storefront Data Schema**:
                            - tenant_type: string ("provider")
                            - project_brief: array of project brief records
                            - service_provider_details: array of service provider details
                            - provider_data: object grouped by service_provider_id, containing:
                                - service_catalog: array of service category and name
                                - capabilities: object with key technologies, industries, partnerships, strength areas
                                - case_studies: array of case study titles
                                - trmeric_assessment: object with expertise details, ratings, recommendations
                                - opportunities: array of opportunity records (id, title, scope, etc.)
                                - win_themes: array of win theme records (id, text, opportunity_id)
                    """
                if data_dicts.get("customer_existing_solutions"):
                    schemas += """
                        - **Customer Solutions Schema**:
                            - Array of solution records with fields:
                                - name: string (solution name, e.g., "EY Atlas")
                                - description: string (detailed description)
                                - category: string (e.g., "Assurance, Audit, Digital")
                                - technology: string (e.g., "Azure")
                                - service_line: string (e.g., "Assurance")
                    """
                if data_dicts.get("provider_quantum_data") and tenant_type == "provider":
                    schemas += """
                        - **Quantum Data Schema**:
                            - service_catalog: array of service category and name
                            - offers: array of offer records
                            - ways_of_working: array of working model records
                            - case_studies: array of case study records
                            - partnerships: array of partnership records
                            - certifications_and_audit: array of certification records
                            - leadership_and_team: array of team member records
                            - voice_of_customer: array of customer feedback records
                            - information_and_security: array of security policy records
                            - aspiration: array of transformation roadmap goals
                            - core_capabilities: array of capability records
                    """
                return schemas

            # Common base prompt components
            base_prompt = f"""
                You are Tango, a highly analytical and engaging AI assistant created by Trmeric.
                
                Also resposible for taking internal actions by calling several agents.
                So, it is very important for you to inform the user about the action that you are doing or did for user to know the status.
                
                User Query: '{query}'
                Ongoing Conversation: {conv}
                Use this Recent Queries for context. Do not frame your response on this (Last 10): {recent_queries_str}
                User and Company Context: {self.user_info_string}
                Current Date: {current_date}
                Tenant Type: {tenant_type}
                Analysis Plan: {json.dumps(plan, indent=2)}
                
                {f"- **Session Uploaded Files**: {json.dumps(current_session_uploaded_files, indent=2)}" if current_session_uploaded_files else ""}
                {f"- **Projects Data**: {project_evals}" if  project_evals else ""}
                {f"- **Roadmaps Data**: {json.dumps(roadmap_evals, indent=2)}" if  roadmap_evals else ""}
                {f"- **Web Search Results**: {json.dumps(web_search_results, indent=2)}" if web_search_results else ""}
                {f"- **Resource Allocation**: {json.dumps(resource_data, indent=2)}" if resource_data else ""}
                {f"- **Integration Data**: {truncate_if_too_large(json.dumps(integration_data, indent=2))}" if integration_data else ""}
                {f"- **Snapshot Data**: {json.dumps(snapshot_data, indent=2)}" if snapshot_data else ""}
                {f"- **Customer Solutions Data**: {json.dumps(customer_existing_solutions, indent=2)}" if customer_existing_solutions else ""}
                {f"- **Company Knowledge**: {json.dumps(some_info_about_trmeric, indent=2)}" if some_info_about_trmeric else ""}
                {f"- **Storefront Data (provider tenants only)**: {json.dumps(provider_storefront_data, indent=2)}" if tenant_type == "provider" else ""}
                {f"- **Quantum Data (provider tenants only)**: {json.dumps(provider_quantum_data, indent=2)}" if tenant_type == "provider" else ""}
                {f"- **Internal Agents Action Results**: {json.dumps(action_results)}" if action_results else ""}
                {f"- ** Journal Data** -: {get_journal_data}" if get_journal_data else "" }
                {f"- **Ideas Data**: {json.dumps(idea_data, indent=2)}" if idea_data else ""}
                {f"- **Tempaltes Data**: {json.dumps(customer_templates, indent=2)}" if customer_templates else ""}
                {f"- **Spend Data**: {json.dumps(project_spend_data, indent=2)}" if project_spend_data else ""}
                ### Schemas
                {append_schemas({
                    "resource_data": resource_data,
                    "integration_data": integration_data,
                    "snapshot_data": snapshot_data,
                    "some_info_about_trmeric": some_info_about_trmeric,
                    "customer_existing_solutions": customer_existing_solutions,
                    "provider_storefront_data": provider_storefront_data,
                    "provider_quantum_data": provider_quantum_data
                })}
                
                Currently, exporting to csv or anything is not in your abilities, so if user wants to list all items, you have to list all items or table.
            """

            # Response-type-specific prompts
            prompt_templates = {
                "conversational": f"""
                    {base_prompt}
                    ### Instructions
                        - Respond in a friendly, professional tone in 25–50 words, directly answering the user’s query with simplicity and warmth.
                        - Analyze query intent:
                            - For casual queries (e.g., “How’s it going?”, “Hi”, “Hello”), provide a brief, engaging response without promoting Trmeric or assuming business intent unless explicitly asked.
                            - For Trmeric-related or business queries (e.g., “What can Trmeric do?”, “Improve my projects”), highlight relevant Trmeric capabilities (e.g., ideation, demand creation, project execution, integrations, portfolio management, reports, solution analysis) in a concise manner.
                        - Personalize using user context (role, company) from user_info_string only if relevant; avoid nudging for missing role/company unless the query implies a need (e.g., business-related).
                        - Avoid speculative data or assumptions (e.g., no random provider names or project references).
                        - Generate 3–4 `next_questions` in JSON, tailored to the query’s intent and user context. For casual queries, keep suggestions light and conversational, with one option to explore Trmeric capabilities.
                        - **Simplicity Rule**: Ensure responses remain simple and avoid introducing complex Trmeric features or business jargon unless the query explicitly requests it.
                        - Output format (strictly adhere, no additional sections):
                            # 🚀 Let’s Connect
                            Concise response (25–50 words).
                            ### Next Steps
                            ```json
                            {{"next_questions": [{{"label": "string"}}]}}
                            ```
        
                    ### Examples
                    - Query: “How’s it going?”
                        - Response: “Doing great, thanks! How about you? Ready to explore how Trmeric can support your goals?”
                    
                    - Query: “What can Trmeric do?”
                        - Response: “Trmeric powers your business with ideation, roadmap creation, project execution, integrations, portfolio management, reports, and solution analysis. Let’s tailor a solution for you!”
                """,
                "clarification_needed": f"""
                    {base_prompt}
                    ### Instructions
                        ask clarification with suggestion
                    ### Output
                        .. with suggestions
                    ### Next Steps
                    ```json
                    {{"next_questions": [{{"label": "Question"}}]}}
                    ```
                """,
                "context_update": f"""
                    {base_prompt}

                    ### Instructions
                    - Confirm updates to user designation or company context from action_results.
                    - Highlight Trmeric’s capabilities (ideation, roadmap creation, project execution, integration support, portfolio management, report generation, customer solutions analysis) to guide next steps.
                    - If role or company info is missing, nudge for those details.
                    - If customer_existing_solutions is available, suggest analyzing existing solutions to align with user’s goals.
                    - Generate 3–5 `next_questions` that:
                        - Suggest ideation, roadmap creation, project execution, integration, portfolio management, report generation, or customer solutions analysis.
                        - Align with user’s role or company stage.
                    ### Output
                    # Context Update ✅
                    Confirm updates or request missing info (50–100 words), mentioning Trmeric’s capabilities.
                    ### Next Steps
                    ```json
                    {{"next_questions": [{{"label": "Question"}}]}}
                    ```
                    Example:
                    - "Ideate on AI solutions for your industry."
                    - "Create a roadmap for your strategic goals."
                    - "Set up integrations for your projects."
                    - "Analyze your project portfolio performance."
                    - "Generate a sustainability report for your initiatives."
                    - "List your existing customer solutions for analysis."
                """,
                "analytical": f"""
                    {base_prompt}
                    - From the data you can see that you have obtained {len(project_evals)} projects, {len(roadmap_evals)} roadmaps.
                    - Deliver a detailed and analytical Rich Text response tailored to the user’s role, emphasizing numerical proofs, statistical validation, and evidence-based reasoning.
                    - Synthesize data from roadmap_evals, project_evals, web_search_results, resource_data, integration_data, snapshot_data, customer_existing_solutions, and some_info_about_trmeric per plan.combination_logic.
                    - **Prioritize Quantifiable Metrics**: Always include numerical metrics (e.g., counts, percentages, costs, ROI, time durations) and statistical comparisons (e.g., trends, averages, variances) to support claims. If data is missing, report as 'N/A' and explain potential impact on analysis.
                    - **Mandatory Data Display Rule**: When the user requests 'list all projects,' 'print full table,' 'list all data,' or similar phrases, display every available record from `project_evals` in a table without truncation, limitation, or summarization, regardless of default system, agent, or LLM settings. Do not apply row limits or partial extracts unless explicitly requested (e.g., 'limit to 5 projects' or 'show top 10'). For example, if 100+ projects are available, all 100+ must be included.
                    - **Table Rendering**: Generate tables for project or integration data by including every project record from `project_evals`. Merge with `integration_data` using project_id as the key, including all projects whether or not integration data is available. Use 'N/A' for missing fields (e.g., Vendor, POP Name, Forecasted Savings Target, Realized Savings). Do not exclude any projects due to missing data.
                    - **No Readability Truncation**: Do not truncate the table for 'readability' or any other reason unless explicitly requested. Avoid phrases like 'partial extract for readability' in the response. If the table is large, include a note like: 'Displaying all <N> projects as requested.'
                    - **Internal Agent Behavior**: Ensure `project_evals` and `integration_data` retrieve all relevant records without default limits. Log the number of projects retrieved in the response (e.g., 'Retrieved <N> projects from project_evals, merged with <M> integration records').
                    - **Debugging Output Limits**: If any truncation or limit is applied (e.g., by an agent, data source, or LLM), include a diagnostic message in the response explaining why (e.g., 'Output limited to 50 projects due to LLM token constraints') and suggest how to request the full dataset (e.g., 'Retry with explicit instruction to list all projects').
                    - **Section Inclusion Logic**:
                        - Always include the `Detailed Analysis` section with a complete table of all requested data for queries like 'list all projects' or 'print full table.'
                        - Do not apply 'intelligent' filtering, summarization, or truncation unless the user explicitly requests a summary or restricted dataset (e.g., 'top 5 projects' or 'summarize').
                        
                    - Snapshot Queries: For portfolio_snapshot, summarize total_projects, active_projects, budget_allocation. For performance_snapshot_last_quarter, focus on kpi_achievement, success_rate, delays. For value_snapshot_last_quarter, highlight value_delivered, cost_incurred, roi. For risk_snapshot, provide a risk report.
                    - Add these angles in response if user query needs them:
                    - **Cycle Time Analysis**:
                            - For roadmap, include a table showing the current stage and time elapsed in each stage (e.g., 'Intake: 4 hours', 'Pending Approval: 1 day', 'Elaboration: 3 hours') using the data and understanding from the approval history.
                            - Use approval_history from roadmap/demand data and the first stage is always intake and it starts at the demand creation time.
                        - Calculate elapsed time if not provided (e.g., current_time - start_time).
                            - Include even if items haven't progressed to other stages.
                            - If user does not say, then make a simple table and show for all demand items.
                    - **Demand Profiling**:
                        - For queries mentioning 'demand profiling' or 'look at all my demand':
                                - Analyze roadmap_evaluations to categorize demand by roadmap categories (e.g., technology, business unit, priority, timeline).
                                - Slice and dice by dimensions like cost, resource allocation, or strategic alignment.
                            - Present a table summarizing demand distribution (e.g., category, count, total cost, priority).
                    - For customer solution queries (e.g., 'list customer solutions'), include a table summarizing solutions (e.g., name, category, technology, service_line) and analyze compatibility with roadmaps or projects.
                    - Structure responses with bullet points/tables or both as appropriate.
                    - For ranking queries, use a weighted scoring system with numerical metrics (e.g., 'Competitor A: 85/100 based on cost and scale').
                    - **Debugging Output Limits**: If any truncation or limit is applied (e.g., by an agent, data source, or LLM), include a diagnostic message in the response explaining why (e.g., 'Output limited to 50 projects due to LLM token constraints') and suggest how to request the full dataset (e.g., 'Retry with explicit instruction to list all projects').
                    - **Section Inclusion Logic**:
                        - Always include the `Detailed Analysis` section with a complete table of all {len(project_evals)} projects for queries like 'list all projects' or 'print full table.'
                        - Do not apply filtering, summarization, or truncation unless the user explicitly requests a limited dataset (e.g., 'top 5 projects').
                    - **Output Format**:
                        ## 📊 Analysis for {query}
                        ### Analysis
                            Detailed summary, approach, and numerical metrics (200–400 words). Include the number of projects retrieved (e.g., 'Retrieved {len(project_evals)} projects from trmeric knowledge').
                        ### Detailed Analysis
                            Full table of requested data, no truncation, no brevity needed- unless explicitly requested.
                        ### Summary and Key Insights
                            Bullet-point insights (50–100 words) with numerical highlights (e.g., 'X% projects on track').
                        ### Sources
                            Cite sources if web_search_results or specific internal sources (e.g., Trmeric Solutions) are used.
                        ### Next Steps (4-5)
                            ```json
                            {{"next_questions": [{{"label": "string"}}]}}
                            ```
                """,            
                "analytical_concise": f"""
                    {base_prompt}
                    - From the data you can see that you have obtained {len(project_evals)} projects, {len(roadmap_evals)} roadmaps.
                    - Deliver a concise, analytical Rich Text response (100–150 words) tailored to the user’s role, emphasizing numerical proofs and key insights.
                    - Synthesize data from roadmap_evals, project_evals, web_search_results, resource_data, integration_data, snapshot_data, customer_existing_solutions, and some_info_about_trmeric per plan.combination_logic.
                    - **Prioritize Key Metrics**: Focus on high-impact numerical metrics (e.g., success_rate: X%, ROI: Y%, total cost: $Z) and avoid lengthy tables unless explicitly requested (e.g., 'list all projects').
                    - **Table Handling**:
                        - If the user requests 'list all projects' or 'print full table,' include a summarized table with key fields (e.g., project_id, name, status, success_rate) and note the total number of records (e.g., 'Summarizing {len(project_evals)} projects').
                        - For non-table requests, use bullet points for key metrics.
                    - **Snapshot Queries**:
                        - Summarize key metrics (e.g., total_projects: N, roi: X% for value_snapshot_last_quarter, N high-severity risks for risk_snapshot).
                    - **Cycle Time Analysis**:
                        - For roadmap/project queries, summarize cycle time metrics (e.g., 'Average cycle time: X days across N roadmaps').
                    - **Demand Profiling**:
                        - For queries like 'demand profiling', provide a concise numerical summary (e.g., 'X% of demand in AI, total cost: $Y').
                    - **Customer Solution Queries**:
                        - Summarize solutions with key metrics (e.g., 'N solutions, X% align with roadmap ID 123').
                    - **Ranking Queries**:
                        - Use numerical scores (e.g., 'Project A: 85/100 based on cost: $C, success_rate: S%').
                    - Ask if the user wants a more descriptive answer and include next_questions for a detailed response to the same query.
                    you are the brain for giving short and meaniful response to the user with his/her data and his/her query.
                    - **Output Format**:
                        ## 📊 Analysis for {query}
                        ### <section for quick analysis>
                            Concise analysis with key numerical metrics and insights (100–150 words).
                            Also include numerical validation if present like dates, budget etc
                        ### Next Steps (3–4 good suggesstion based on the data and also for detailed view on any aspect)
                            ```json
                            {{"next_questions": [{{"label": "Provide a detailed analysis for {query}"}}, {{"label": "string"}}]}}
                            ```
                            
                    Important-- Always be mindful of the current date - {current_date}.
                    And always correctly tell user if he needs to confirm roadmap creation or anything else carefully looking at the internal actions and results..
                """,
                "ideation": f"""
                    {base_prompt}
                    ### Instructions
                    - Generate 3–5 innovative ideas (100–200 words) based on the query, using some_info_about_trmeric for Trmeric-specific solutions.
                    - If customer_existing_solutions is available, suggest ideas that build on existing solutions (e.g., extending EY Atlas).
                    - Only suggest providers if find_suitable_service_provider results are available; otherwise, skip provider section.
                    - Output format:
                        # 💡 Ideation for {query}
                        ### Ideas
                        List 3–5 ideas with brief descriptions.
                        ### Provider Suggestions (if applicable)
                        List 1–3 providers with services (50–100 words).
                        ### Next Steps
                        ```json
                        {{"next_questions": [{{"label": "string"}}]}}
                        ```
                    ### Example
                    For "Ideate on AI automation":
                    - Ideas: "1. AI-driven workflow automation using Trmeric’s tools. 2. Predictive analytics for demand forecasting..."
                    - Next Questions: ["Create a roadmap for AI automation?", "Analyze existing solutions for AI?", "Set up integrations?"]
                """,
                "provider_recommendation": f"""
                    {base_prompt}
                    ### Instructions
                    - Use find_suitable_service_provider results to list 1–3 providers with services and fit scores (100–200 words).
                    - Align recommendations with customer_existing_solutions (e.g., Azure expertise for EY Atlas) if available.
                    - Use some_info_about_trmeric for Trmeric-specific context.
                    - Output format:
                        # 🤝 Provider Recommendations for {query}
                        ### Recommended Providers
                        List providers with services and fit scores.
                        ### Summary
                        Recap provider fit (50–100 words).
                        ### Next Steps
                        ```json
                        {{"next_questions": [{{"label": "string"}}]}}
                        ```
                    ### Example
                    For "Find providers for roadmap ID 123":
                    - Response: "Provider A: 85/100, expertise in AI automation. Provider B: 80/100, strong Azure integration..."
                    - Next Questions: ["Analyze provider case studies?", "Create a project for roadmap ID 123?", "Analyze existing solutions?"]
                """,
                
                "present_data_in_template": f"""
                    {base_prompt}
                    ### Instructions
                    - Clearly understand all data that user wants to present in the template
                    - Align all required data with the template
                    - Output format:
                        # Good header
                        Full Detailed template filled with data required by user - 
                        and it should look pretty with proper markdown and beautiful segments/ tables 
                        as required by template and also capitalise the section headers properly
                        ### Next Steps
                        ```json
                        {{"next_questions": [{{"label": "string"}}]}}
                        ```
                """,
            }

            # Select prompt based on response_type
            response_type = plan.get("response_type", "analytical")
            if response_type not in prompt_templates:
                appLogger.warning({"function": "combine_results_warning", "tenant_id": self.tenant_id, "query": query, "message": f"Invalid response_type: {response_type}, defaulting to analytical"})
                response_type = "analytical"
            system_prompt = prompt_templates[response_type]
            modelOptions = ModelOptions(model="gpt-4.1", max_tokens=10000, temperature=0.2)
            system_prompt += f"""
                Note: when roadmap creation happens. nudge user that know if he wants to know about suitable provider from trmeric provider ecosystem.
                If user is interested you can initiate a provider discovery agent.
                Important:: Do not tell random names or wrong info. we as an organization value accuracy. for eg. do not tell random provider names. only tell provider when u do find_suitable_provider for any roadmap or project. do not add  random provider names in your suggestion.. and same applies to dimension trmeric operates in. I hope you are clear.
            """
            extra_message = ""
            if self.tenant_id in ["776", 776, "183", 183,232,"232", 234, "234"]: #Skipping for EY tenants
                extra_message = "Do not include anything related to provider - neither in suggestion nor ctas. Call roadmaps as demands"

            language = UsersDao.fetchUserLanguage(user_id = self.user_id)
            print("language ---", language)
            
            user_prompt = f"""
                Deliver a polished, Rich Text response tailored to the user’s role. 
                Begin with a short meaningful header. (Use a good icon for the header always in h1 markdown.)
                
                Query: {query}.
                
                For my query, create the best response to exactly address my needs with details.
                Use conceptual terms (e.g., 'ideation', 'roadmap creation', 'portfolio management'). 
                
                Include JSON nudges for complex queries, citation for web results (“Source: [title] [url]”)
                Today’s Date: {current_date}
                The next_questions must be powerful, targeted to my needs, encouraging exploration of Trmeric’s capabilities (ideation, roadmap creation, project execution, integration support, portfolio management, report generation).
                
                If user asks for all data - then force print all data. Our job is to make user life easy, he should not ask to give all data again and again, so give all data if asked
                Carefully see the plan.user_wants_full_list and the user_wants_full_list.thought_process
                {extra_message}
                
                ## important notes
                    - Roadmap priority: less is high
                    - Very important to: see my query completely and your answer should stick to answering my query.
                    - Brevity is not desired, remember to list all projects/roadmaps etc. Only limit the count if instructed.
                    - if data is missing, report that do not write random data.
                    - Do not give random links 
                    - If I ask to list (then list via numbering and list all) this is a must
                    - Do not tell about your abilities which are not provided to you. like rn you can't export csv. so dont say that to user
                    
                Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
                
                Customer Config - {json.dumps(self.tenant_configs)}
            """
            system_prompt += """
            CRITICAL: Only confirm an action as completed if it appears in action_results 
            with a success message. If action_results is empty or contains a warning about 
            an unsupported action, tell the user clearly that the action could not be 
            performed and why.
            """
            # Handle snapshot-specific prompts
            str_plan = json.dumps(plan)
            if "snapshot" in query.lower():
                if "portfolio_snapshot" in str_plan.lower():
                    chat_completion = portfolio_snapshot_prompt(roadmap_evals, project_evals, web_search_results, resource_data, integration_data, snapshot_data, plan, query, conv)
                elif "performance_snapshot_last_quarter" in str_plan.lower():
                    chat_completion = performance_snapshot_prompt(roadmap_evals, project_evals, web_search_results, resource_data, integration_data, snapshot_data, plan, query, conv)
                elif "value_snapshot_last_quarter" in str_plan.lower():
                    chat_completion = business_value_report_prompt(roadmap_evals, project_evals, web_search_results, resource_data, integration_data, snapshot_data, plan, query, conv)
                elif "risk_snapshot" in str_plan.lower():
                    chat_completion = risk_report_prompt(snapshot_data, query, conv, plan)
                elif "monthly_savings_snapshot" in str_plan.lower():
                    chat_completion = monthly_savings_report_with_graph_prompt(snapshot_data, query, conv)
                else:
                    chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
            else:
                system_prompt += f"""
                
                    Instruction for adding chart:
                    add chart if asked by user in this way:Add commentMore actions
                    Charts: You can have multiple different types of charts to represent the data, depending on which kind you need.

                        The output of your chart should be in the following format:
                        ```json
                        {{
                            chart_type: 'Gaant' or 'Bar' or 'Line' or 'BarLine',
                            format: <format>,
                            symbol: '$' if something related to money otherwise '', 
                        }}
                        ```
                            Gaant Chart have the following format:
                            
                            <format>: {{
                                data:  [ 
                                    {{
                                        x: <x_axis_name>, // string
                                        y: ['date_string_begin', 'date_string_end']
                                    }}
                                ]
                            }}
                            
                            For Line Charts, they have the following format:

                            <format> - [
                                {{
                                    name: <name_of_param>,// string
                                    data: [<values_of_data>, ...],
                                    categories: [<categories>, ...]
                                }},
                                ... if more params they want for bar chart
                            ]

                            For Bar Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                                                    
                            <format> - [
                                {{
                                    name: <name_of_param>,// string
                                    data: [<values_of_data>, ...],
                                    categories: [<categories>, ...]
                                }},
                                ... if more params they want for bar chart
                            ]
                            
                            
                            For BarLine Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                            
                            <format> - [
                                {{
                                    name: <name_of_param>, // string
                                    type: 'bar' or 'line', // specifies series type
                                    data: [<values_of_data>, ...],
                                    categories: [<categories>, ...]
                                }},
                                ... multiple series for bar and/or line
                            ]

                            For Donut/Gauge Chart type - this is the applicable format <format>:
                            <format> - [
                                {{
                                    data: [<values_of_data>, ...],
                                    categories: [<categories>, ...]
                                }}
                            ]
                            
                            If you selected more than one graph, then you should create multiple jsons in the format given above. \
                            Do not truncate the data sent in the chart.
                    
                    When user wants charts where meramid charts are needed  like process flow or sequence flow etc
                    format to send output of mermaid chart
                    example for a process flow (graph TD) that avoids rendering issues with & or other special characters

                    When generating Mermaid diagrams (flowcharts, sequence diagrams, mindmaps, etc.):
                        - Wrap every node label in quotes → A["My Label"]
                        - Escape `&` as `&amp;`
                        - If label has parentheses or special characters, keep them inside the quotes
                        - Keep diagrams minimal and valid (avoid extra symbols outside of quotes)

                        Examples:

                        ```mermaid
                        flowchart TD
                            A["Start"] --> B["Action"]
                            B --> C["Result"]
                        ```
                        
                        ```mermaid
                        flowchart TD
                            H["Continuous Improvement (AI-Driven)"] --> I["AI-Augmented Workflows"]
                        ```
                        
                        ```mermaid
                        mindmap
                        root((Project))
                            1["Goal"]
                            1.1["Feature"]
                        ```
                
                    
                """
                
                chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

            buffer = ""
            MIN_BUFFER_SIZE = 30
            WORD_BOUNDARY = re.compile(r'[\s.,!?;]')
            
            

            # if self.socketio:
            #     self.socketio.emit("custom_agent_v1_ui", {"event": "stop_show_timeline"}, room=self.client_id)

            # print("prompt debug --- ", chat_completion.formatAsString())
            res = ""
            self.socketSender.sendSteps("Synthesizing Insights", True)
            # program_state= ProgramState.get_instance(self.user_id)
            interrupted = False
            def on_interrupt(_):
                nonlocal interrupted
                interrupted = True

            channel = f"interrupt::{self.user_id}"
            RedClient.subscribe(channel, on_interrupt)
            # print("--debug stream_interuppted called-------", interrupted)

            try:
                use_v2_streaming = (
                    plan.get("user_wants_full_list") or False
                    or "show all" in query.lower()
                    or "list all" in query.lower()
                    or "full" in query.lower()
                )
                print("use_v2_streaming", use_v2_streaming, int(self.tenant_id), int(self.tenant_id) in [198])
                
                if use_v2_streaming:
                    # 🔧 reduce token size to prevent truncation
                    adjusted_model_options = ModelOptions(
                        model=modelOptions.model,
                        max_tokens=1000,  # safer smaller chunks
                        temperature=0.0   # deterministic when printing long lists
                    )
                    chat_completion.system += """
                        You are a structured data generator (tables, JSON, lists, or markdown).
                        If your output exceeds token limits, it will be resumed later. 
                        When resuming, always continue exactly where you left off, without repeating or restarting previous sections.
                        Never reprint headers, keys, or earlier rows. Continue in identical structure and formatting.
                    """
                    chat_completion.user += """
                        **Very important**
                        Your task is to list all items in the data set presented to you. either roadmap or project.
                        So, remember not to truncate your data presentation.
                        Even if data seems repeating. keep printing forcefully
                        
                        
                        
                    
                        **CRUCIAL** - If the answer is long and you reach your output limit, 
                        stop politely and continue exactly where you left off in the next part 
                        without repeating or skipping anything.
                        
                        ** Do not abruptly end your answer after list/table ends **
                        Always be midful of where you are ending 
                        Look at the instructions properly, like after printing the list/table
                        properly provide short summary and next steps like instructions.
                        
                    """
                else:
                    adjusted_model_options = modelOptions

                stream_method = (
                    self.llm.runWithStreamingV2
                    if use_v2_streaming else
                    self.llm.runWithStreaming
                    # self.llm.run_rl
                )
                rl_kwargs = {
                    'chat': chat_completion,
                    'options': adjusted_model_options,
                    'agent_name': 'super_agent',
                    'function_name': 'combine::tango',
                    'logInDb': {"tenant_id": self.tenant_id, "user_id": self.user_id},
                    'streaming': True,
                }
                if use_v2_streaming:
                    stream_iter = stream_method(
                        chat_completion,
                        adjusted_model_options,
                        'tango::master::combine',
                        logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id},
                    )
                else:
                    stream_iter = stream_method(**rl_kwargs)
                ### want to run it based on stream method if run_rl then use rl_kwargs else these params should
                stop_sent = False
                for chunk in stream_iter:
                # for chunk in stream_method(
                #     chat_completion, 
                #     adjusted_model_options, 
                #     'tango::master::combine', 
                #     logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
                # ):
                    # print("debug -- ", stop_sent, interrupted)
                    if not stop_sent and self.socketio:
                        stop_sent = True
                        self.socketio.emit("custom_agent_v1_ui", {"event": "stop_show_timeline"}, room=self.client_id)

                    if interrupted:
                    # if program_state.get("interrupt_requested", False):
                    # Flush any remaining buffer so it doesn't look broken
                        if buffer:
                            yield buffer
                            buffer = ""
                        
                        yield "\n\n[Generation stopped by user]"
                        print("--debug stopped generateion---!!!!!!!!!!!!!!")
                        break
                    buffer += chunk
                    res += chunk
                    if len(buffer) >= MIN_BUFFER_SIZE or (buffer and WORD_BOUNDARY.search(buffer)):
                        yield buffer
                        buffer = ""
                        if self.socketio:
                            self.socketio.sleep(0.01)
            except Exception as e:
                # if program_state.get("interrupt_requested", False):
                if interrupted:
                    # User stopped → don't count as error, don't retry
                    appLogger.info({
                        "event": "generation_interrupted_by_user",
                        "user_id": self.user_id,
                        "partial_length": len(res)
                    })
                else:
                    TangoBreakMapUser.add_counter(self.user_id)
                    if TangoBreakMapUser.get_counter(self.user_id) <= 2:
                        if "GPT failed to send" in str(e):
                            yield "\n\n"
                            yield "Error occured, so trying again."
                            yield "\n\n"
                            error_context = (
                                f"Previous attempt failed with error: {str(e)}. "
                                f"Partial response:\n{res}\n"
                                "Please provide the response in a list format instead of a table to avoid rendering issues. "
                                "Explain why this format change helps avoid the error."
                            )
                            # chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt + "\n\n **<important_bug_to_fix>**---- you failed to print this answer completely previously error was: <error_in_previous_response>"+  str(e) + " <error_in_previous_response>,  the previous partial answer \n\n <previous_partial_answer>" + res + "\n\n <previous_partial_answer> \n\n" + " Ensure to fix this error in the next attempt. Provide reason to the format fix of the answer so that the same error does not happen. if table gives error. move to list. \n\n **<important_bug_to_fix>**" )
                            chat_completion = ChatCompletion(
                                system=system_prompt,
                                prev=[],
                                user=user_prompt + "\n\n" + error_context
                            )
                            print("prompt debug 2 --- ", chat_completion.formatAsString())
                            buffer = ""
                            for chunk in self.llm.runWithStreaming(chat_completion, modelOptions, 'tango::master::combine', logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}):
                                buffer += chunk
                                res += chunk
                                if len(buffer) >= MIN_BUFFER_SIZE or (buffer and WORD_BOUNDARY.search(buffer)):
                                    yield buffer
                                    buffer = ""
                                    if self.socketio:
                                        self.socketio.sleep(0.01)
                            
                    yield str(e)
            finally:
                #cleanup always
                # program_state.set("interrupt_requested", False)
                RedClient.unsubscribe(channel,on_interrupt)
                if buffer:
                    yield buffer

            print("finall -- ", res)

            appLogger.info({"function": "combine_results_success", "tenant_id": self.tenant_id, "query": query})
        except Exception as e:
            appLogger.error({"function": "combine_results_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": self.tenant_id})
            yield {"error": f"Synthesis failed: {str(e)}", "query": query, "timestamp": current_date}
        


# The view_combined_analysis function and VIEW_COMBINED_ANALYSIS definition remain unchanged
def view_combined_analysis(
    tenantID: int, userID: int, last_user_message=None, socketio=None, client_id=None, llm=None, base_agent=None, sessionID=None, eligibleProjects=None, mode='default', **kwargs
):
    appLogger.info({"function": "view_combined_analysis_start", "tenant_id": tenantID, "user_id": userID, "last_user_message": last_user_message})

    try:
        if not last_user_message:
            appLogger.error({"function": "view_combined_analysis_error", "error": "last_user_message is required", "tenant_id": tenantID})
            raise ValueError("last_user_message is required")
            # last_user_message = "Let's playback"

        roadmap_agent = RoadmapAgent(tenant_id=tenantID, user_id=userID, socketio=socketio, llm=llm, client_id=client_id, base_agent=base_agent, sessionID=sessionID)
        project_agent = ProjectAgent(tenant_id=tenantID, user_id=userID, socketio=socketio, llm=llm, client_id=client_id, base_agent=base_agent, sessionID=sessionID)

        agent = MasterAnalyst(tenant_id=tenantID, user_id=userID, socketio=socketio, llm=llm, client_id=client_id, base_agent=base_agent, sessionID=sessionID, eligibleProjects=eligibleProjects)
        answer = ""
        if mode == "only_data":
            for chunk in agent.process_combined_query(query=last_user_message, roadmap_agent=roadmap_agent, project_agent=project_agent, filters=kwargs, mode=mode):
                yield chunk
            return

        from src.trmeric_ws.static import ActiveUserSocketMap, UserSocketMap
        for response in agent.process_combined_query(query=last_user_message, roadmap_agent=roadmap_agent, project_agent=project_agent, filters=kwargs, mode=mode):
            new_client_id = UserSocketMap.get_client_id(user_id=str(userID))
            # print("new_client_id", userID, client_id, new_client_id)
            if not new_client_id:
                new_client_id = client_id
            # print("new_client_id 2", new_client_id)
            client_ids = ActiveUserSocketMap.get_all(str(userID))
            if not client_ids:
                print("❌ No active sockets, stopping stream")
                # break

            socketio.sleep(0.01)
            if isinstance(response, str):
                answer += response
                if socketio:
                    for cid in client_ids:
                        socketio.emit("tango_chat_assistant", response, room=cid)
                    # socketio.emit("tango_chat_assistant", response, room=new_client_id)
                    socketio.sleep(0.01)  # Small delay to prevent overwhelming client
            else:
                for chunk in response:
                    answer += chunk
                    if socketio:
                        for cid in client_ids:
                            socketio.emit("tango_chat_assistant", response, room=cid)
                        # socketio.emit("tango_chat_assistant", chunk, room=new_client_id)
                        socketio.sleep(0.01)  # Small delay to prevent overwhelming client
            yield response
        if socketio:
            for cid in client_ids:
                socketio.emit("tango_chat_assistant", "<end>", room=cid)
                socketio.emit("tango_chat_assistant", "<<end>>", room=cid)

        TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key="master_analyst", value=f"Agent Response: {answer}", session_id=sessionID)
        appLogger.info({"function": "view_combined_analysis_success", "tenant_id": tenantID, "user_id": userID})
    except Exception as e:
        appLogger.error({"function": "view_combined_analysis_error", "error": str(e), "traceback": traceback.format_exc(), "tenant_id": tenantID})
        raise


RETURN_DESCRIPTION = """
    Analyzes roadmaps, projects, team, resources, integration, augmented with trmeric knowledge, external web insights, and team resource data...
"""

VIEW_COMBINED_ANALYSIS = AgentFunction(
    name="view_combined_analysis",
    description="Master Analyst for roadmap, project, resource,  team and integration queries",
    args=[],
    return_description=RETURN_DESCRIPTION,
    function=view_combined_analysis,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name,
)


# ### Detailed Analysis
#                         (give inside <details> tag if the user is interested in reading after a big header of detailed analysis)
#                         Use tables for metrics (e.g., snapshot_data value_delivered).
#                         </details> tag close