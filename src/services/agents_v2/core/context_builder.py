import json
import traceback
from typing import Dict
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import TenantDaoV2, FileDao, ProviderDao, TenantDao


class ContextBuilder:
    """Builds enterprise context using automated research and user inputs."""

    def __init__(self, tenant_id: int, user_id: int, data_getter_cls, base_agent, agent_name):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data_getters = data_getter_cls
        self.base_agent = base_agent
        self.agent_name = agent_name

    def build_context(self, agent_name: str) -> str:
        """Builds context string from company info, social media, industry trends, etc."""
        print("building context -- ", agent_name)
        
        context = []
        context_sections = []
        try:
            if agent_name == "trucible":
                context_sections = [
                    "org_role_user",
                    "current_session_uploaded_files",
                    # "all_industries_titles",
                    
                    "company_basic_info",
                    "company_competitors_info"
                    "company_industry_info",
                    "company_enterprise_strategies",
                    
                    "all_files_uploaded_in_agent_by_user",
                    "company_configuration_info",
                    
                    "user_info_string",
                    
                    "company_portfolio_context"
                ]
                
            if agent_name == "tango":
                context_sections = [
                    # "org_role_user",
                    "current_session_uploaded_files",
                    
                    "company_basic_info",
                    "company_industry_info",
                    "company_enterprise_info",
                    "company_competitors_info",
                    "company_enterprise_strategies",
                    "company_configuration_info",

                    "user_info_string",
                    "integration_info_string",
                    "project_and_roadmap_context_string",
                    "program_list",
                    "providers_list",
                    # "company_portfolio_context"
                ]

            # Loop over sections and fetch data
            for section in context_sections:
                data_text = self._fetch_section_data(section)
                if data_text:
                    context.append(f"=== {section} ===\n{data_text}")

            res = "\n-----\n".join(context) if context else "No context available."
            # print("context -- ", res)
            return res

        except Exception as e:
            appLogger.error({
                "function": "ContextBuilder.build_context_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return f"Error building context: {str(e)}"

    def _fetch_section_data(self, section_name: str) -> str:
        """Fetches data for a given section name and returns as formatted string."""
        try:
            return {
                "org_role_user": self.base_agent.org_role_user,
                "current_session_uploaded_files": self.base_agent.current_session_uploaded_files,
                "all_industries_titles": TenantDaoV2.fetch_all_industries(),
                "company_basic_info": TenantDaoV2.fetch_company(tenant_id=self.tenant_id),
                "company_portfolio_context": TenantDaoV2.fetch_portfolio_context(tenant_id=self.tenant_id),
                "company_industry_info": TenantDaoV2.fetch_company_industry(tenant_id=self.tenant_id),
                "user_info_string": self.base_agent.user_info_string,
                "integration_info_string": self.base_agent.integration_info_string,
                "project_and_roadmap_context_string": self.base_agent.project_and_roadmap_context_string,
                "program_list": self.base_agent.program_list,
                "providers_list": ProviderDao.fetchProvidersListing(),
                "company_enterprise_info": TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id),
                "all_files_uploaded_in_agent_by_user": FileDao.FileUploadedInType(_type=self.agent_name.upper(), user_id=self.user_id),
                "company_competitors_info": TenantDaoV2.fetch_competitor(tenant_id=self.tenant_id),
                "company_enterprise_strategies": TenantDaoV2.fetch_enterprise_strategy(tenant_id=self.tenant_id),
                "company_configuration_info": TenantDao.checkTenantConfig(tenant_id=self.tenant_id)
            }.get(section_name, f"No data fetch logic for section '{section_name}'") or f"No data for section '{section_name}'"
    
    
        except Exception as e:
            appLogger.error({
                "function": "_fetch_section_data",
                "section_name": section_name,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return f"Error fetching section '{section_name}': {str(e)}"
