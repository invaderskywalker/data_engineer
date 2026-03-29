from typing import Dict
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from src.trmeric_utils.helper.common import MyJSON
from src.trmeric_database.dao import TenantDaoV2, FileDao, ProviderDao, AuthDao, UsersDao, ProjectsDao, RoadmapDao
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_database.Redis import RedClient


class ContextBuilder:
    """Builds enterprise context using automated research and user inputs."""

    def __init__(self, tenant_id: int, user_id: int, session_id=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id or None

    def build_context(self, agent_name: str) -> str:
        """Builds context string from company info, social media, industry trends, etc."""
        from datetime import datetime, timedelta, timezone
        ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        print("Incoming build_context (IST):", ist_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
        print("building context -- ", agent_name)

        # ✅ Create Redis cache key
        cache_key = RedClient.create_key([
            "context_agent",
            # agent_name,
            str(self.tenant_id),
            str(self.user_id)
        ])

        # ✅ Define builder function (excluding `current_session_uploaded_files`)
        def _build_context():
            print(f"🔄 Building fresh context for {cache_key}")
            context = []
            context_sections = []
            try:
                if agent_name == "trucible":
                    context_sections = [
                        "org_role_user",
                        "company_basic_info",
                        "company_competitors_info",
                        "company_industry_info",
                        "company_enterprise_strategies",
                        "accessible_portfolios",
                        "all_files_uploaded_in_agent_by_user"
                    ]

                else:
                    context_sections = [
                        "org_role_user",
                        "info_about_user",
                        # "accessible_portfolios",
                        "company_basic_info",
                        "company_industry_info",
                        "company_enterprise_info",
                        "company_competitors_info",
                        "company_enterprise_strategies",
                        # "integration_info_string",
                        # "project_and_roadmap_context_string",
                        # "program_list",
                        # "providers_list"
                    ]

                # Loop over sections and fetch data
                for section in context_sections:
                    data_text = self._fetch_section_data(section)
                    if data_text:
                        context.append(f"=== {section} ===\n{data_text}")
                        
                print(f"🔄 Building fresh context done for {cache_key}")

                return "\n-----\n".join(context) if context else "No context available."

            except Exception as e:
                appLogger.error({
                    "function": "ContextBuilder.build_context_error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "tenant_id": self.tenant_id
                })
                return f"Error building context: {str(e)}"

        cached_context = RedClient.execute(_build_context, cache_key, expire=300)
        fresh_files_section = self._fetch_section_data("current_session_uploaded_files")

        # ✅ Append fresh section at end
        if fresh_files_section:
            cached_context += f"\n-----\n=== current_session_uploaded_files ===\n{fresh_files_section}"


        print("done fetching context -- ")
        return cached_context

    def _fetch_section_data(self, section_name: str) -> str:
        """Fetches data for a given section name and returns as formatted string."""
        try:
            if section_name == "org_role_user":
                role_of_user = AuthDao.fetchRoleOfUserInTenant(user_id=self.user_id)
                all_roles_in_trmeric_for_tenant = AuthDao.fetchAllRolesInTrmericForTenant(tenant_id=self.tenant_id)
                return f"""
                    Role of this User in Trmeric Platform: {role_of_user}. 
                    All user distinct roles in trmeric are- {all_roles_in_trmeric_for_tenant}.
                """

            elif section_name == "accessible_portfolios":
                from src.trmeric_services.agents import PortfolioApiService
                portfolio_data = PortfolioApiService().get_portfolio_context_of_user(
                    user_id=self.user_id, tenant_id=self.tenant_id
                )
                return f"""
                    So, these are the portfolios that the user has access to:
                    {portfolio_data}
                """

            elif section_name == "info_about_user":
                user_designation_info = UsersDao.fetchUserDesignation(user_id=self.user_id)
                return f"Role of this User in his Org: {user_designation_info}."

            elif section_name == "current_session_uploaded_files":
                # ✅ Always live fetch
                return f"""
                    Files uploaded by customer in this chat session.
                    
                    Details:
                    ----------------------
                    {FileDao.FilesUploadedInS3ForSession(self.session_id)}
                    ----------------------
                """
            
            elif section_name == "current_user":
                return 

            elif section_name == "all_industries_titles":
                return TenantDaoV2.fetch_all_industries()

            elif section_name == "company_basic_info":
                return TenantDaoV2.fetch_company(tenant_id=self.tenant_id)

            elif section_name == "company_industry_info":
                return TenantDaoV2.fetch_company_industry(tenant_id=self.tenant_id)

            elif section_name == "integration_info_string":
                integrations_with_projects = IntegrationService().fetchIntegrationListForUser(
                    self.tenant_id, self.user_id, skip=True
                )
                return MyJSON.json_to_table(integrations_with_projects)

            elif section_name == "project_and_roadmap_context_string":
                self.eligible_projects = ProjectsDao.FetchAvailableProject(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id
                )
                project_arr = ProjectsDao.fetchProjectIdTitleAndPortfolio(
                    tenant_id=self.tenant_id,
                    project_ids=self.eligible_projects
                )
                roadmap_arr = RoadmapDao.fetchEligibleRoadmapList(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id
                )

                return f"""
                    These are the projects that the user has access to:
                    ------------------
                    All the projects which are currently active:
                    {MyJSON.json_to_table(project_arr)}
                    
                    -----------------
                    All roadmap and tenant of this customer: 
                    {MyJSON.json_to_table(roadmap_arr)}
                    -------
                """

            elif section_name == "program_list":
                return f"""
                    ----------
                    All program list for this customer: 
                    {MyJSON.json_to_table(ProjectsDao.fetchAllProgramFortenant(tenant_id=self.tenant_id))}
                    ----------
                """

            elif section_name == "company_enterprise_info":
                return TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id)

            elif section_name == "providers_list":
                return ProviderDao.fetchProvidersListing()

            elif section_name == "company_competitors_info":
                return TenantDaoV2.fetch_competitor(tenant_id=self.tenant_id)

            elif section_name == "company_enterprise_strategies":
                return TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id)

            else:
                return f"No data fetch logic for section '{section_name}'"

        except Exception as e:
            appLogger.error({
                "function": "_fetch_section_data",
                "section_name": section_name,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return f"Error fetching section '{section_name}': {str(e)}"
