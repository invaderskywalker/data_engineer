import json
import traceback
import pandas as pd
import concurrent.futures
from ..config.getter import *
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from ..helper.file_analyser import FileAnalyzer
from ..helper.event_bus import Event, event_bus
from src.database.Database import db_instance
from ..helper.decorators import log_function_io_and_time
from src.trmeric_services.phoenix.nodes import WebSearchNode
from src.utils.web.CompanyScraper import CompanyInfoScraper
from src.api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.journal.ActivityEndpoints import get_user_session_summaries_by_timeframe
from src.trmeric_services.integration.helpers.jira_on_prem_getter import fetch_filtered_integration_data
from src.database.dao import TenantDaoV2, TenantDao, ProviderDao, ProjectsDaoV2, ProjectsDao, ActionsDaoV2, IdeaDao, IntegrationDao, CommonDao
# Placeholder imports for new functions (update these as needed)

from src.trmeric_services.tango.functions.integrations.internal.providers import get_provider_data, get_quantum_data
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetPortfoliosSnapshot import view_portfolio_snapshot
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewRiskSnapshot import view_risk_report_current_quarter
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewValueSnapshot import view_value_snapshot_last_quarter
from src.trmeric_services.tango.functions.integrations.internal.prompts.ViewPerformanceSnapshot import view_performance_snapshot_last_quarter
from src.trmeric_services.agents.functions.roadmap_analyst import getIntegrationData, TrmericVectorSearch, RoadmapAgent, ProjectAgent, view_combined_analysis
from src.trmeric_services.agents.reports.customers.pf.monthly_savings import (
    fetchDataForMonthlySavingsAndAnalysis, 
    monthly_savings_report_with_graph_prompt
)



class DataGetters:
    """
    A utility class to fetch and process various data sources such as
    S3 files, web queries, company website data, and tenant-related data.
    """

    def __init__(self, tenant_id: int, user_id: int, agent_name="", metadata = {}):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.agent_name = agent_name
        self.file_analyzer = FileAnalyzer(tenant_id=tenant_id)
        self.vector_search = TrmericVectorSearch()  # Initialize vector search for company knowledge
        self.eligibleProjects = ProjectsDao.FetchAvailableProject(tenant_id, user_id)
        
        self.base_agent = metadata.get("base_agent")
        self.session_id = metadata.get("session_id")
        self.llm = metadata.get("llm")
        self.event_bus = event_bus
        
        self.fn_maps = {
            "web_search": self.web_search,
            "read_file_details_with_s3_key": self.read_file_details_with_s3_key,
            "analyze_file_structure": self.analyze_files,
            "fetch_company": self.fetch_company,
            "fetch_company_industry": self.fetch_company_industry,
            "fetch_company_performance": self.fetch_company_performance,
            "fetch_competitor": self.fetch_competitor,
            "fetch_enterprise_strategy": self.fetch_enterprise_strategy,
            "fetch_industry": self.fetch_industry,
            "fetch_social_media": self.fetch_social_media,
            
            # New functions added to fn_maps
            "fetch_resource_data": self.fetch_resource_data,
            "fetch_integration_data": self.fetch_integration_data,
            "get_snapshots": self.get_snapshots,
            
            
            "fetch_provider_storefront_data": self.fetch_provider_storefront_data,
            "fetch_provider_quantum_data": self.fetch_provider_quantum_data,
            "fetch_provider_offers": self.fetch_provider_offers,
            
            
            "fetch_info_about_trmeric_with_vector_search": self.fetch_some_info_about_trmeric,
            "fetch_customer_existing_solutions": self.fetch_customer_existing_solutions,
            
            "get_journal_data": self.get_journal_data,
            
            ## call agents
            "fetch_projects_data_using_project_agent": self.fetch_data_using_project_agent,
            "fetch_roadmaps_data_using_roadmap_agent": self.fetch_data_using_roadmap_agent,
            
            
            "fetch_assigned_actions": self.fetch_actions,
            
            "fetch_idea_data": self.fetch_idea_data,
            "fetch_saved_templates": self.fetch_saved_templates,
            # "fetch_project_or_roadmap_data_with_natural_language": self.fetch_project_or_roadmap_data_with_natural_language
        }
        
    @log_function_io_and_time
    def fetch_portfolio_context(self, params: Optional[Dict] = DEFAULT_FETCH_PORTFOLIO_CONTEXT_PARAMS) -> Dict:
        """
            Fetches portfolio-level contextual data stored in the `portfolio_context` table.

            This function is used to retrieve **already curated and confirmed** portfolio context
            such as strategy narratives, KPIs, risks, priorities, investment themes, operating models,
            or executive narratives associated with one or more portfolios.

            Portfolio Context represents **applied strategy and execution intelligence**
            at the portfolio level (NOT company-wide, NOT project-level).

            --------------------
            When this function is used
            --------------------
            - During `user_first_interaction` to show whether portfolio context exists (✅ / ❌)
            - During playback (answering: "What do we know about this portfolio?")
            - During analysis / ideation to ground responses in real portfolio intent
            - Before storing new portfolio context to avoid duplication
            - When reasoning across projects, roadmaps, and investments under a portfolio

            --------------------
            Input Parameters
            --------------------
            params: dict

                {
                    "portfolio_ids": list[int], # If provided, fetch context only for these portfolio IDs.
                                                # If empty or missing, fetch all portfolios for the tenant.

                }

            --------------------
            Expected Behavior
            --------------------
            - Always scope data by `tenant_id`
            - Never return unconfirmed or draft data
            - If multiple portfolios are requested, group results by `portfolio_id`
            - If no data exists, return empty structures (do NOT error)

            --------------------
            Output Structure
            --------------------
            Returns a dictionary structured for LLM reasoning and UI playback:

                {
                    "portfolio_context": [
                        {
                            "portfolio_id": int,
                            "items": [
                                {
                                    ....
                                }
                            ]
                        }
                    ]
                }

            --------------------
            Notes for the Agent
            --------------------
            - This function is READ-ONLY.
            - Do NOT infer or synthesize missing context here.
            - If portfolio context is missing, the agent should:
                → inform the user
                → suggest uploading or adding Portfolio Context
            - Do NOT mix Portfolio Context with Enterprise Strategy or Project data.

        """
        
        portfolio_ids = params.get("portfolio_ids") or []
        return TenantDaoV2.fetch_portfolio_context(tenant_id=self.tenant_id, portfolio_ids=portfolio_ids)


    @log_function_io_and_time
    def web_search(self, params: Optional[Dict] = DEFAULT_WEB_AGENT_PARAMS) -> Dict:
        """
        Here we can do deep web search using: web_queries_string: we can write multiple queries that we would ideally search in web
        use website_urls when u know what website to use
        """
        try:
            params = params.copy()
            web_queries = (params.get("web_queries_string") or []) 
            # + (params.get("website_web_queries_also_add_which_company_in_string") or [])
            website_urls = params.get("website_urls", [])
            result = {}

            debugLogger.info(f"running web_search with {web_queries} and {website_urls}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {}

                # Submit web queries task
                if web_queries:
                    futures["web_queries_result"] = executor.submit(
                        self.fetch_first_search_list, web_queries=web_queries
                    )

                # Submit scraping tasks
                if website_urls:
                    futures["website_urls_result"] = {
                        site: executor.submit(self._scrape_site, site)
                        for site in website_urls if site != ""
                    }

                # Collect results
                for key, fut in futures.items():
                    if key == "web_queries_result":
                        try:
                            res = fut.result()  # wait for web queries (list of URL arrays)
                            query_results = {q: r for q, r in zip(web_queries, res)}                            
                            all_scraped_urls = []
                            result["web_queries_result"] = query_results
                            
                            # Collect all top URLs across queries for deduplication and concurrent scraping
                            all_top_urls_set = set()
                            query_top_urls_map = {}  # Maps query to its list of top_urls (for later mapping)
                            import re
                            reject_url_patterns = re.compile(r"(pdf|scribd|wordpress|youtube|buffer)", re.IGNORECASE)

                            for q, urls in query_results.items():
                                filtered_urls = [url for url in urls if not reject_url_patterns.search(url)]
                                top_urls = filtered_urls[:5]
                                query_top_urls_map[q] = top_urls
                                all_top_urls_set.update(top_urls)
                            
                            print("all_top_urls_set ", all_top_urls_set)
                            # Submit all unique scrape tasks concurrently
                            scrape_futures = {
                                url: executor.submit(self._scrape_single_page, url)
                                for url in all_top_urls_set
                            }
                            
                            # Wait for all scrapes to complete concurrently
                            scraped_contents = {}
                            for url, scrape_fut in scrape_futures.items():
                                # print("debug  ", url, scrape_fut)
                                try:
                                    scraped_contents[url] = scrape_fut.result()
                                except Exception as scrape_error:
                                    appLogger.error(f"Error scraping {url}: {str(scrape_error)}")
                                    scraped_contents[url] = {}
                            
                            # Build per-query scraped dicts using the shared scraped_contents
                            for q, top_urls in query_top_urls_map.items():
                                query_scraped = {
                                    url: scraped_contents.get(url, {})
                                    for url in top_urls
                                    if url in scraped_contents  # Already ensured by set, but safe
                                }
                                all_scraped_urls.append(query_scraped)
                            
                            query_results["scraped_contents"] = all_scraped_urls
                            result["web_queries_result"] = query_results
                        except Exception as e:
                            appLogger.error(f"Error in web queries: {str(e)}")
                            result["web_queries_result"] = {}
              
                    elif key == "website_urls_result":
                        result["website_urls_result"] = {}
                        for site, site_future in fut.items():
                            try:
                                result["website_urls_result"][site] = site_future.result()
                            except Exception as scrape_error:
                                appLogger.error(f"Error scraping {site}: {str(scrape_error)}")
                                result["website_urls_result"][site] = {}
            
            # with open(f'data_scrape.json', 'w') as json_file:
            #     json.dump(result, json_file, indent=2)
                
            return result

        except Exception as e:
            appLogger.error({
                "function": "web_search",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {}


    @log_function_io_and_time
    def _scrape_site(self, site: str) -> Dict:
        """Helper method to scrape a single site (extracted for thread pooling)."""
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': f"Scraping: {site}"},
            session_id=self.session_id
        )
        scraper_c = CompanyInfoScraper(site, max_workers=3)
        res = scraper_c.scrape()
        # with open(f'_scrape_site.json', 'w') as json_file:
        #     json.dump(res, json_file, indent=2)
        return res
    
    @log_function_io_and_time
    def _scrape_single_page(self, site: str) -> Dict:
        """Helper method to scrape a single site (extracted for thread pooling)."""
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': f"Scraping: {site}"},
            session_id=self.session_id
        )
        try:
            scraper_c = CompanyInfoScraper(site, max_workers=3)
            out = scraper_c.scrape_single_page()
            if len(out) > 0:
                if ("error" in out[0]):
                    return ""
                if ("content" in out[0]):
                    out[0]["content"] = " ".join(out[0]["content"].split(" ")[:400])
            
            safe_url = site.replace("https://", "").replace("http://", "").replace("/", "_")
            # with open(f'_scrape_single_page_{safe_url}.json', 'w') as json_file:
            #     json.dump(out, json_file, indent=2)
            return out
        except Exception as e:
            print("error here ", e, traceback.format_exc())
            return ""

    @log_function_io_and_time
    def fetch_first_search_list(self, web_queries):
        for q in web_queries:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': f"WebSearch for Query: {q}"},
                session_id=self.session_id
            )
        return WebSearchNode().runV2(sources=web_queries)
        
        
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
    def analyze_files(self, params: Optional[Dict] = DEFAULT_S3_FILE_PARAMS) -> Dict:
        """
        Analyzes files uploaded in the current session from S3 using FileAnalyzer.
        Supports CSV, Excel, DOCX, DOC, PDF, and TXT formats with structured output.
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Analysing files"},
            session_id=self.session_id
        )
        return self.file_analyzer.analyze_files(params)
    
    @log_function_io_and_time    
    def read_file_details_with_s3_key(self, params: Optional[Dict] = DEFAULT_S3_FILE_PARAMS) -> Dict:
        """
        Reads and analyzes files uploaded in the current session from S3 using provided keys.
        Delegates to FileAnalyzer to handle various file types (TXT, DOC, DOCX, PDF, CSV, Excel).
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Reading files"},
            session_id=self.session_id
        )
        return self.file_analyzer.analyze_files(params)

    @log_function_io_and_time
    def fetch_resource_data(self, params: Optional[Dict] = DEFAULT_RESOURCE_DATA_PARAMS) -> Dict:
        """
        Fetch comprehensive **resource data** for the given tenant, combining multiple data sources
        (resources, portfolios, timelines, org teams, and external providers) into a unified analytical view.

        ---
        🔍 **Purpose**
        This function acts as a universal resource intelligence API for Tango and Trmeric’s analytical agent system.
        It supports rich querying and dynamic projections for capacity planning, portfolio staffing analysis,
        provider dependency monitoring, and skill-based talent discovery.

        ---
        ⚙️ **Data Coverage**
        - Core resource details (name, role, skills, experience)
        - Portfolio membership information (multiple portfolios per resource)
        - Allocation summary and project timelines (past, current, future)
        - Organizational team mappings (leaders, group name, team ID)
        - External provider details (company name, website, address)

        ---
        🎯 **Supported Filters**
        | Param | Type | Description |
        |-------|------|-------------|
        | `resource_ids` | list[int] | Filter by specific resource IDs |
        | `name` | str | Partial or full name match (first, last, or combined) |
        | `primary_skill` | str | Filter by primary skill keyword |
        | `skill_keyword` | str | Match any keyword in the broader skills field |
        | `role` | str | Filter by role/title |
        | `is_external` | bool | True = only external, False = only internal, None = all |
        | `external_company_name` | str | Filter by provider company name |
        | `org_team_name` | str | Partial match on org/team name |
        | `org_team_id` | int | Exact match on team ID |
        | `portfolio_ids` | list[int] | Filter by one or more portfolio IDs |
        | `min_allocation` | float | Minimum current allocation % |
        | `max_allocation` | float | Maximum current allocation % |
        | `selected_projection_attrs` | list[str] | List of attributes to include in results |

        ---
        📊 **Available Projection Attributes**
        Project only the required fields for lightweight or high-detail results:
        ```python
        [
            "id",
            "first_name",
            "last_name",
            "role",
            "experience_years",
            "primary_skill",
            "skills",
            "current_allocation",
            "past_projects",
            "current_projects",
            "future_projects",
            "org_team",
            "portfolio",
            "is_external",
            "provider_company_name",
            "provider_company_website",
            "provider_company_address"
        ]
            ```

            ---
            🧠 **Intended Analytical Use Cases**
            - Identify **overallocated resources** (e.g., current_allocation > 100)
            - List **available engineers** by skill or role (e.g., “Python”, “Frontend”)
            - Filter **external vendors** by company name or domain
            - Get **org team structures** with members and leaders
            - Support **capacity heatmaps** or AI-driven resource assignment planning

            ---
            📦 **Example Input**
            ```python
            params = {
                "primary_skill": "Python",
                "is_external": False,
                "min_allocation": 20,
                "max_allocation": 80,
                "selected_projection_attrs": [
                    "id", "first_name", "last_name",
                    "role", "primary_skill",
                    "current_allocation", "org_team"
                ]
            }
            ```

            ---
            ✅ **Example Output**
            ```json
            {
                "resources": [
                    {
                        "id": 14,
                        "first_name": "Ravi",
                        "last_name": "Sharma",
                        "role": "Data Engineer",
                        "primary_skill": "Python",
                        "current_allocation": 60,
                        "org_team": [
                            {
                                "team_id": 2,
                                "org_team": "Data Intelligence",
                                "leader_first_name": "Ananya",
                                "leader_last_name": "Mehta"
                            }
                        ],
                        "is_external": false
                    }
                ]
            }
            ```

            ---
            🧩 **Integration Notes**
            - Used by Tango and MasterAnalyst for analytical, resource optimization, and provider recommendation intents.
            - Automatically filters test/inactive data.
            - Safe to call with partial params (uses defaults from DEFAULT_RESOURCE_DATA_PARAMS).

            ---
            🔁 **Returns**
            Dict with structure:
            ```json
            { "resources": [ { <fields> } ] }
            ```

            ---
            ⚠️ **Error Handling**
            - Logs detailed error context (user_id, tenant_id, traceback)
            - Returns `{ "resources": [] }` on failure
        """
        try:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Fetching resource data for tenant"},
                session_id=self.session_id
            )

            params = params or {}

            # Extract all filters
            projection_attrs = params.get("selected_projection_attrs") or [
                "id", "full_name", "role", "primary_skill", "current_allocation"
            ]
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
                name=name,
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
                portfolio_ids=portfolio_ids
            )

            return {"resources": resource_data}

        except Exception as e:
            appLogger.error({
                "function": "fetch_resource_data",
                "event": "FETCH_RESOURCE_DATA_FAILURE",
                "user_id": getattr(self, 'user_id', None),
                "tenant_id": getattr(self, 'tenant_id', None),
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"resources": []}
    
    @log_function_io_and_time
    def fetch_integration_data(self, params: Optional[Dict] = DEFAULT_INTEGRATION_DATA_PARAMS) -> Dict:
        """
        Fetches and optionally post-processes integration data for a specific integration type (e.g., Jira),
        based on the provided parameters.

        This method acts as the unified entry point for retrieving integration data from both
        **cloud-based** and **on-premise** sources. It supports dynamic query-driven filtering for
        on-premise Jira integrations and can be extended for other integrations in the future.

        ---
        ### Workflow Summary
        1. **Parameter Resolution**:
        - Reads the `integration_name` (e.g., "jira") and `project_ids` from `params`.
        - If no params are provided, defaults to `DEFAULT_INTEGRATION_DATA_PARAMS`.

        2. **Integration Data Retrieval**:
        - Calls `getIntegrationData()` with tenant, user, integration name, and project IDs.
        - This function fetches raw integration data (e.g., Jira issues, projects, epics, etc.)
            for the specified scope.

        3. **On-Premise Jira Handling**:
        - Detects if the user is connected to an **on-prem Jira** using `IntegrationDao.is_user_on_prem_jira()`.
        - If `True`:
            - Extracts only the `"integration_data"` key from each record.
            - Runs semantic filtering through `fetch_filtered_integration_data()`, which parses
            the `user_detailed_query` (e.g., "List all projects where MP3-Web team is working")
            and filters data accordingly.

        - If `False` (cloud or general integration):
            - Returns raw data as fetched from the integration API.

        ---
        ### Parameters
        - **params** (`Optional[Dict]`, default=`DEFAULT_INTEGRATION_DATA_PARAMS`):
            Configuration dictionary controlling what data to fetch and how to post-process it.

            | Key | Type | Description |
            |------|------|-------------|
            | `integration_name` | `str` | Name of the integration (e.g., `"jira"`, `"slack"`, etc.). |
            | `project_ids` | `List[int]` | List of Trmeric project IDs to limit data retrieval. If empty, all accessible projects are fetched. |
            | `user_detailed_query` | `str` | Natural language query for post-filtering integration data (used mainly for on-prem Jira). Example: `"List all projects where MP3-Web team is working."` |

        ---
        ### Returns
        - **Dict**
            - For **on-prem Jira**, returns filtered integration data that semantically matches
            the user’s natural language query.
            - For **cloud integrations**, returns raw data as provided by `getIntegrationData()`.

            Example (filtered output for MP3-Web team):
            ```json
            [
                {
                    "project_name": "Jira Platform Revamp",
                    "team_name": "MP3-Web",
                    "project_key": "JP-124",
                    "status": "In Progress",
                    "sprint": "Sprint 2025.3.4"
                },
                ...
            ]
            ```

        ---
        ### Error Handling
        - Logs any exception with full traceback and contextual metadata (tenant_id, user_id).
        - Returns an empty dictionary `{}` on error to prevent upstream failures.

        ---
        ### Example Usage
        ```python
        params = {
            "integration_name": "jira",
            "project_ids": [],  # Allow all projects
            "user_detailed_query": "List all projects where MP3-Web team is working."
        }

        jira_team_data = self.fetch_integration_data(params)
        ```

        ---
        ### Notes
        - Setting `project_ids` to an empty list (`[]`) effectively means **“fetch from all projects”**.
        - The filtering logic in `fetch_filtered_integration_data()` ensures that the final output
        strictly adheres to the user’s intent without hallucination or inclusion of irrelevant data.
        """

        try:
            params = params or {}
            integration_name = params.get("integration_name")
            project_ids = params.get("project_ids") or []
            if len(project_ids) == 0:
                project_ids = ProjectsDao.FetchAvailableProject(
                    tenant_id=self.tenant_id, 
                    user_id=self.user_id,
                )
            
            is_jira_on_prem = IntegrationDao.is_user_on_prem_jira(self.user_id)
            data = getIntegrationData(
                integration_name=integration_name,
                project_ids=project_ids,
                tenantID=self.tenant_id,
                userID=self.user_id,
            )
            print("is_jira_on_prem ", is_jira_on_prem)
            # 4️⃣ On-prem Jira handling
            if is_jira_on_prem and integration_name == "jira":
                # Flatten out the grouped structure
                ndata = []
                for project_id, integrations in data.items():
                    for item in integrations:
                        if "integration_data" in item:
                            ndata.append(item["integration_data"].get("data") or {})
                            
                post_proceeded_data = fetch_filtered_integration_data(
                    user_query=params.get("user_detailed_query"),
                    data_array=ndata
                )
                return post_proceeded_data
            else:
                return data
                
        except Exception as e:
            appLogger.error({
                "function": "fetch_integration_data",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            return {}

    @log_function_io_and_time
    def get_snapshots(self, params: Optional[Dict] = DEFAULT_SNAPSHOTS_PARAMS) -> Dict:
        """
        Fetches snapshot data based on snapshot type and parameters.
        """
        try:
            params = params or {}
            snapshot_type = params.get("snapshot_type")
            portfolio_ids = params.get("user_chosen_portfolio_ids")
            eligible_projects = self.eligibleProjects
            kwargs = params.get("kwargs", {})

            if snapshot_type == "value_snapshot_last_quarter":
                if not params.get("last_quarter_start") or not params.get("last_quarter_end"):
                    raise ValueError("last_quarter_start and last_quarter_end are required for value_snapshot_last_quarter")
                if not portfolio_ids:
                    raise Exception("select portfolios among the portfolios")
                return view_value_snapshot_last_quarter(
                    eligibleProjects=eligible_projects,
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    last_quarter_start=params.get("last_quarter_start"),
                    last_quarter_end=params.get("last_quarter_end"),
                    portfolio_ids=portfolio_ids,
                    **kwargs,
                )
            elif snapshot_type == "portfolio_snapshot":
                return view_portfolio_snapshot(
                    eligibleProjects=eligible_projects,
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    portfolio_id=params.get("portfolio_ids"),
                    **kwargs
                )
            elif snapshot_type == "performance_snapshot_last_quarter":
                if not params.get("last_quarter_start") or not params.get("last_quarter_end"):
                    raise ValueError("last_quarter_start and last_quarter_end are required for performance_snapshot_last_quarter")
                return view_performance_snapshot_last_quarter(
                    eligibleProjects=eligible_projects,
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    last_quarter_start=params.get("last_quarter_start"),
                    last_quarter_end=params.get("last_quarter_end"),
                    **kwargs,
                )
            elif snapshot_type == "risk_snapshot":
                if not (params.get("last_quarter_start") or not params.get("quarter_start")):
                    raise ValueError("Start and end dates are required for risk_snapshot")
                if not (params.get("last_quarter_end") or not params.get("quarter_end")):
                    raise ValueError("Start and end dates are required for risk_snapshot")
                return view_risk_report_current_quarter(
                    tenantID=self.tenant_id,
                    userID=self.user_id,
                    portfolio_ids=portfolio_ids,
                    quarter_start=params.get("last_quarter_start") or params.get("quarter_start"),
                    quarter_end=params.get("last_quarter_end") or params.get("quarter_end"),
                    **kwargs,
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
                appLogger.info({
                    "function": "get_snapshots",
                    "tenant_id": self.tenant_id,
                    "program_ids": program_ids
                })
                return fetchDataForMonthlySavingsAndAnalysis(
                    program_ids=program_ids,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id
                )
            else:
                raise ValueError(f"Invalid snapshot_type: {snapshot_type}")
        except Exception as e:
            appLogger.error({
                "function": "get_snapshots",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "snapshot_type": snapshot_type
            })
            raise Exception(f"Error in snapshot -- {e}")

    @log_function_io_and_time
    def fetch_provider_storefront_data(self, params: Optional[Dict] = DEFAULT_PROVIDER_STOREFRONT_PARAMS) -> Dict:
        """
        Fetches provider data for all provider ids given in provider_ids on factors: data_sources_array
        passing provider_ids is MANDATORY
        """
        try:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Fetching provider storefront data"},
                session_id=self.session_id
            )
            print("fetch_provider_storefront_data ", params)
            data_sources_array = params.get("data_sources_array")
            provider_ids = params.get("provider_ids")
            result = {}
            for p_id in provider_ids:
                try:
                    tenant_id = ProviderDao.fetchTenantIdForProvider(provider_id=p_id)
                    print("tenant id for provider --- ", tenant_id)
                    if tenant_id:
                        users = TenantDao.FetchUsersOfTenant(tenant_id)
                        print("user id for provider --- ", tenant_id)
                        if users:  
                            user_id = users[0]["user_id"]
                        else:
                            user_id = 0
                    else:
                        raise Exception("Something went wrong")
                    
                    ## and user id from tenant id
                    result[p_id] = get_provider_data(
                        eligibleProjects=self.eligibleProjects,
                        tenantID=tenant_id,
                        userID=user_id,
                        data_sources_array=data_sources_array
                    )
                except Exception as e:
                    result[p_id] = str(e)
            return result
        except Exception as e:
            appLogger.error({
                "function": "fetch_provider_storefront_data",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            return {}

    @log_function_io_and_time
    def fetch_provider_quantum_data(self, params: Optional[Dict] = DEFAULT_PROVIDER_QUANTUM_PARAMS) -> Dict:
        """
        Fetches provider quantum data for a provider.
        """
        try:
            # params = params or {}
            # tenant_type = TenantDao.checkCustomerType(self.tenant_id)
            # if tenant_type != "provider":
            #     appLogger.info({
            #         "function": "fetch_provider_quantum_data",
            #         "reason": "Tenant is not a provider",
            #         "tenant_id": self.tenant_id,
            #         "user_id": self.user_id
            #     })
            #     return {"error": "Quantum data is only available for provider tenants"}
            
            print("fetch_provider_storefront_data ", params)
            data_sources_array = params.get("data_sources_array")
            provider_id = params.get("provider_id")
            ## get tenant id  from provider id
            tenant_id = ProviderDao.fetchTenantIdForProvider(provider_id=provider_id)
            print("tenant id for provider --- ", tenant_id)
            if tenant_id:
                users = TenantDao.FetchUsersOfTenant(tenant_id)
                print("user id for provider --- ", tenant_id)
                if users:  
                    user_id = users[0]["user_id"]
                else:
                    user_id = 0
            else:
                raise Exception("Something went wrong")


            data_sources_array = params.get("data_sources_array") or [
                "service_catalog", "offers", "ways_of_working", "case_studies",
                "partnerships", "certifications_and_audit", "leadership_and_team",
                "voice_of_customer", "information_and_security", "aspiration",
                "core_capabilities"
            ]
            return get_quantum_data(
                provider_id=provider_id,
                tenant_id=tenant_id,
                user_id=user_id,
                data_sources_array=data_sources_array
            )
        except Exception as e:
            appLogger.error({
                "function": "fetch_provider_quantum_data",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            return {}

    @log_function_io_and_time
    def fetch_some_info_about_trmeric(self, params: Optional[Dict] = DEFAULT_SOME_INFO_ABOUT_TRMERIC_PARAMS) -> Dict:
        """
        Fetches information about the company using vector search based on queries.
        """
        try:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Fetching Info about trmeric"},
                session_id=self.session_id
            )
            params = params or {}
            results = []
            for query in params.get("queries_to_ask_for_vector_search", []) or []:
                result = self.vector_search.queryVectorDB(query)
                results.append(result)
            return {"some_info_about_trmeric": results}
        except Exception as e:
            appLogger.error({
                "function": "fetch_some_info_about_trmeric",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            return {}

    @log_function_io_and_time
    def fetch_customer_existing_solutions(self, params: Optional[Dict] = {}) -> Dict:
        """
        Fetches existing solutions for a customer tenant. (Placeholder implementation)
        """
        return TenantDao.listCustomerSolutions(tenant_id=self.tenant_id)

    @log_function_io_and_time
    def fetch_data_using_project_agent(self, params = DEFAULT_PARAMS_FOR_PROJECT_AGENT):
        """
        This function will be used when user wants to fetch roadmap data.
        roadmap data has many columns and many rows
        but it can be filtered properly if the query is clear and plain text written in natural language
        """
        print("params -- fetch_data_using_project_agent --- ", params)
        query = params.get("project_agent_natural_language_text") or "Fetch projects"
        print("params -- fetch_data_using_project_agent --- 1 ", query)
        
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching projects data"},
            session_id=self.session_id
        )
        project_agent = ProjectAgent(
            tenant_id=self.tenant_id, 
            user_id=self.user_id, 
            socketio=None, 
            llm=self.llm, 
            client_id=None, 
            base_agent=self.base_agent, 
            sessionID=self.session_id
        )
        for response in project_agent.process_query(query=query, filters=None):
            pass
        print("params -- fetch_data_using_project_agent --- 2 ")
        return project_agent.eval_response

    @log_function_io_and_time
    def fetch_data_using_roadmap_agent(self, params = DEFAULT_PARAMS_FOR_ROADMAP_AGENT):
        """
        This function will be used when user wants to fetch project data.
        project data has many columns and many rows
        but it can be filtered properly if the query is 
        clear and plain text written in natural language
        """
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Fetching roadmaps data"},
            session_id=self.session_id
        )
        print("params -- fetch_data_using_roadmap_agent --- ", params)
        query = params.get("roadmap_agent_natural_language_text") or "Fetch all roadmaps- title, description, key results and objectives"
        
        print("params -- fetch_data_using_roadmap_agent --- 1 ", query)
        
        roadmap_agent = RoadmapAgent(
            tenant_id=self.tenant_id, 
            user_id=self.user_id, 
            socketio=None, 
            llm=self.llm, 
            client_id=None, 
            base_agent=self.base_agent, 
            sessionID=self.session_id
        )
        answer = ""
        for response in roadmap_agent.process_query(query=query, filters=None):
            # answer += response
            # yield response
            pass
        print("params -- fetch_data_using_roadmap_agent --- 2 ")
        # roadmap_agent.process_query(query=query)
        return roadmap_agent.eval_response
    
    @log_function_io_and_time
    def fetch_provider_offers(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_PROVIDER_OFFERS):
        """
        Fetch provider(s)/trmeric partner(s) offers when provider_ids is passed.
        Passing provider_ids is MANDATORY.
        If no provider id is passed, data will be returned empty.
        """
        try:
            provider_ids = params.get("provider_ids") or []
            if not provider_ids:
                return {}

            # Convert provider_ids list into comma-separated string
            provider_ids_str = ", ".join(str(pid) for pid in provider_ids)

            query = f"""
                WITH BaseOffers AS (
                    SELECT 
                        ao.id AS offer_id,
                        ao.provider_id,
					    tp.company_name as provider_name,
                        ao.title,
                        ao.desc_short AS short_description,
                        ao.provider_id,
                        ao.description,
                        --         ao.output,
                        --         ao.timing,
                        --         ao.expiry_date,
                        --         ao.created_date,
                        --         ao.view_count,
                        --         ao.provider_id,
                        --         aoc.customer_id,
                        ao.category,
                        ao.is_paid,
                                --         ao.category_sub AS subcategory,
                        ao.category_tags AS tags
                    FROM amplify_offer AS ao
                    JOIN amplify_offer_customer_provider_map AS aoc
                        ON aoc.provider_id = ao.provider_id
                    left join public.tenant_provider as tp on tp.id = ao.provider_id
                    WHERE ao.provider_id IN ({provider_ids_str})
                    GROUP BY ao.id, ao.title, ao.desc_short, ao.provider_id, ao.description, ao.category, ao.is_paid, ao.category_tags, tp.company_name, ao.provider_id         
				    order by ao.id asc
                )
                SELECT * FROM BaseOffers;
            """

            rows = db_instance.retrieveSQLQueryOld(query)

            # Group results by provider_id for easy lookup
            result = {}
            for row in rows:
                p_id = row["provider_id"]
                if p_id not in result:
                    result[p_id] = []
                result[p_id].append(row)

            return result

        except Exception as e:
            print("Exception in fetch_provider_offers:", e)
            return {}
        

    @log_function_io_and_time
    def get_journal_data(self, params: Optional[JournalParams] = None ):
        if isinstance(params, dict):
            params = JournalParams(**params)
        elif params is None:
            params = JournalParams()
            
        hours = params.back_hours_to_query_from_now
        return get_user_session_summaries_by_timeframe(hours=hours, userID=self.user_id)
    

    @log_function_io_and_time
    def fetch_actions(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_FETCHING_ACTIONS):
        """
        Fetches action items for (tasks, insights, roadmap actions, etc.) for the current tenant and user.

        This function acts as a unified interface to retrieve action data stored in the `actions_actions` table.
        It supports rich filtering, projection, ordering, and joins to polymorphic references (Project, Roadmap, Insight).

        Parameters:
        -----------
        params : dict, optional
            {
                "projection_attrs": ["id", "head_text"], # Attributes to include in SELECT
                "due_date_before": str (YYYY-MM-DD),     # Filter: due_date <= given date
                "due_date_after": str (YYYY-MM-DD),      # Filter: due_date >= given date
                "order_clause": str,                     # Custom ORDER BY clause
                "limit": int                             # Limit results
            }
        """
        try:
            # --- Step 1: Initialize and merge defaults ---
            params = params or {}
            defaults = {
                "action_ids": [],
                "projection_attrs": ["id", "head_text", "priority", "due_date", "ref_object"],
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "due_date_before": None,
                "due_date_after": None,
                "order_clause": "ORDER BY aa.id DESC",
                "limit": 50
            }

            for k, v in defaults.items():
                params.setdefault(k, v)
            
            # --- Step 2: Notify UI or event bus ---
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': f"Fetching actions for tenant {params['tenant_id']}"},
                session_id=self.session_id
            )

            # --- Step 3: Execute query using DAO ---
            results = ActionsDaoV2.fetchActionsWithProjectionAttrs(
                action_ids=params["action_ids"],
                projection_attrs=params["projection_attrs"],
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                due_date_before=params["due_date_before"],
                due_date_after=params["due_date_after"],
                order_clause=params["order_clause"],
                limit=params["limit"]
            )

            # --- Step 4: Return structured response ---
            return results or []

        except Exception as e:
            appLogger.error({
                "function": "fetch_actions",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return []


    @log_function_io_and_time
    def fetch_idea_data(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_FETCHING_IDEAS):
        """
        Wrapper to fetch idea data from IdeaDao using structured params.

        Args:
            params (Dict, optional): A dictionary containing filters and projections.
                Supported keys:
                    - projection_attrs: list of attribute keys to project
                    - idea_ids: list of idea IDs to filter
                    - portfolio_ids: list of portfolio IDs to filter
                    - state_filter: SQL WHERE condition (string)
                    - order_clause: SQL ORDER clause (string)
                    - limit: integer limit for pagination (default 50)
        Returns:
            List[Dict]: List of fetched ideas data
        """

        try:
            # --- Merge with defaults safely ---
            merged_params = {**DEFAULT_PARAMS_FOR_FETCHING_IDEAS, **(params or {})}

            # --- Extract parameters ---
            projection_attrs = merged_params.get("projection_attrs")
            idea_ids = merged_params.get("idea_ids")
            portfolio_ids = merged_params.get("portfolio_ids")
            state_filter = merged_params.get("state_filter")
            order_clause = merged_params.get("order_clause")
            limit = merged_params.get("limit")

            # --- Fetch data ---
            results = IdeaDao.fetchIdeasDataWithProjectionAttrs(
                idea_ids=idea_ids,
                projection_attrs=projection_attrs,
                portfolio_ids=portfolio_ids,
                tenant_id=self.tenant_id,
                state_filter=state_filter,
                order_clause=order_clause
            )

            # --- Apply limit manually if not handled in SQL ---
            if limit and isinstance(results, list):
                results = results[:limit]

            return results

        except Exception as e:
            appLogger.error({
                "function": "fetch_idea_data",
                "error": str(e),
                "params": params
            })
            return []


    @log_function_io_and_time
    def fetch_saved_templates(self, params: Optional[Dict] = None) -> List[Dict]:
        """
        Fetches saved document templates for the tenant.
        Supports filtering by category, active status, and flexible projection.
        Returns structured template data including full markdown content.
        """
        try:
            # Merge with defaults safely
            merged_params = {**DEFAULT_PARAMS_FOR_FETCHING_TEMPLATES, **(params or {})}

            projection_attrs = merged_params.get("projection_attrs")
            category = merged_params.get("category")
            tenant_id = merged_params.get("tenant_id") or self.tenant_id
            only_active = merged_params.get("only_active", True)
            limit = merged_params.get("limit")
            order_clause = merged_params.get("order_clause")

            if not tenant_id:
                return []

            results = TenantDaoV2.fetch_saved_templates(
                projection_attrs=projection_attrs,
                category = category,
                tenant_id = self.tenant_id,
                only_active = only_active,
                order_clause=order_clause,
                limit = limit,
            )

            # Normalize results into clean dicts
            templates = []
            for row in results:
                template = {attr: row.get(attr) for attr in projection_attrs if attr in row}
                # Ensure markdown is string
                if "markdown" in template and template["markdown"] is None:
                    template["markdown"] = ""
                templates.append(template)

            print("--debug templates----------", templates)

            return templates

        except Exception as e:
            appLogger.error({
                "function": "fetch_saved_templates",
                "error": str(e),
                "tenant_id": self.tenant_id,
                "params": params
            })
            return []



    ####### Fetch Tenant metrics to track tango usage patterns ###########
    DEFAULT_PARAMS_FOR_USAGE = {
        "user_roles": None,
        "company": None,
        "workflows": "project|roadmap|idea|resource|all",
        "start_date": None,
        "end_date": None,
    }
    @log_function_io_and_time
    def fetch_tenant_usage_patterns(self, params: Optional[Dict] = DEFAULT_PARAMS_FOR_USAGE):
        """
        Fetches tenant usage patterns based on specified filters. It will cover the metrics to compute
        the tango usage for all the tenant customers.
        """
        try:
            params = params or {}
            results = []
          
            # --- Step 2: Notify UI or event bus ---
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': f"Fetching usage patterns for tenant{params['tenant_id']}"},
                session_id=self.session_id
            )
            results = CommonDao.fetch_tenant_usage(tenant_id = self.tenant_id,params = params)
            return results or []

        except Exception as e:
            appLogger.error({
                "function": "fetch_tenant_usage_patterns",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return []