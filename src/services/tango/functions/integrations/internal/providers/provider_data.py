from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetGeneralProjects import  RETURN_DESCRIPTION, view_projects
from src.database.dao import ProviderDao
from src.api.logging.AppLogger import appLogger
from collections import defaultdict
from src.trmeric_services.tango.functions.integrations.internal.providers.quantum_data import get_quantum_data


RETURN_DESCRIPTION = """
    Returns a dictionary containing provider-related data for the specified tenant, filtered by the provided data sources. The structure includes:
    - tenant_type (string): "customer" or "provider".
    - project_brief (array): List of project brief records for the specified project IDs.
    - service_provider_details (array): List of service provider details from tenant_serviceproviderdetails.
    - provider_data (object): Grouped data by service_provider_id, containing:
        - service_catalog (array): List of service category and name.
        - capabilities (object): Key technologies, industries, partnerships, and strength areas.
        - case_studies (array): List of case study titles.
        - trmeric_assessment (object): Expertise details, ratings, and recommendations.
    - opportunities (array): List of opportunity records (id, title, scope, etc.).
    - win_themes (array): List of win theme records (id, text, opportunity_id).
"""


def get_provider_data(eligibleProjects: list[int], tenantID: int, userID: int, data_sources_array: list[str] = []) -> dict:
    """
    Fetches provider-related data for a given tenant, including project briefs, tenant type, service provider details,
    service catalog, capabilities, case studies, trmeric assessment, opportunities, and win themes.
    
    Args:
        eligibleProjects (list[int]): List of project IDs to fetch project briefs.
        tenantID (int): Tenant ID to fetch data for.
        userID (int): User ID for logging context (not used in queries).
        data_sources_array (list[str]): List of data sources to fetch. If empty, fetches all available sources.
            Options: ["tenant_type", "project_brief", "service_provider_details", "service_catalog",
                     "capabilities", "case_studies", "trmeric_assessment", "opportunities", "win_themes"]
    
    Returns:
        dict: A dictionary containing the requested data sources, with provider data grouped by service_provider_id.
    """
    try:
        print("get_provider_data", tenantID, userID, data_sources_array)
        # Default data sources if none specified
        all_data_sources = [
            "service_catalog",
            "capabilities",
            "case_studies",
            "trmeric_assessment",
            "opportunities",
            "win_themes",
            "quantum",
            "provider_skills"
        ]
        data_sources = data_sources_array if data_sources_array else all_data_sources
        
        
        
        
        # Initialize result structure
        result = {
            "tenant_type": "provider",
            "project_brief": [],
            "service_provider_details": [],
            "provider_data": {},
            "opportunities": [],
            "win_themes": [],
            "quantum_data": [],
            "provider_skills": []
        }
        
        # Validate inputs
        if not tenantID:
            appLogger.error({
                "function": "get_provider_data",
                "event": "INVALID_INPUT",
                "user_id": userID,
                "tenant_id": tenantID,
                "error": "Tenant ID is required"
            })
            return result

        # # Fetch tenant type
        # if "tenant_type" in data_sources:
        #     result["tenant_type"] = ProviderDao.fetchTenantType(tenantID)

        # # Fetch project briefs if eligibleProjects provided
        # if "project_brief" in data_sources and eligibleProjects:
        #     for project_id in eligibleProjects:
        #         project_brief = ProviderDao.fetchProjectBrief(project_id)
        #         if project_brief:
        #             result["project_brief"].extend(project_brief)

        # # Fetch service provider details
        # if "service_provider_details" in data_sources:
        #     result["service_provider_details"] = ProviderDao.fetchAllDataFromServiceProviderDetailsTable()

        # Fetch provider-related data only if tenant is a provider
        
        # if result["tenant_type"] == "provider" and any(
        #     src in data_sources for src in ["service_catalog", "capabilities", "case_studies", "trmeric_assessment"]
        # ):
        provider_id = ProviderDao.fetchProviderIdForTenant(tenantID)
        print("provider id -- ", provider_id)
        if provider_id:
            
            if "quantum" in data_sources:
                quantum_data = get_quantum_data(provider_id,tenant_id = tenantID,user_id = userID)
                result["quantum_data"] = dict(quantum_data)
                
                if not quantum_data:
                    appLogger.error({"event": "NO_QUANTUM_DATA_FOUND","provider_id": provider_id,"user_id": userID,"tenant_id": tenantID})
            
            if "skills" in data_sources:
                all_skills_of_providers = ProviderDao.fetchAllDataFromServiceProviderDetailsTable()
                providers_skills_data = [
                    {
                        "service_provider_id": provider.get("service_provider_id"),
                        "primary_skills": (provider.get("primary_skills") or "").lower(),
                        "secondary_skills": (provider.get("secondary_skills") or "").lower(),
                        "other_skills": (provider.get("other_skills") or "").lower()
                    }
                    for provider in all_skills_of_providers
                ]
                result["provider_skills"] = dict(providers_skills_data)
                
            service_provider_id = ProviderDao.fetchServiceProviderIdFromProviderId(provider_id)
            print("service_provider_id id -- ", service_provider_id)
            if service_provider_id:
                # Initialize grouped provider data
                provider_data = defaultdict(lambda: {
                    "service_catalog": [],
                    "capabilities": {},
                    "case_studies": [],
                    "trmeric_assessment": {}
                })
                
                
                # Fetch individual data sources
                if "service_catalog" in data_sources:
                    service_catalog = ProviderDao.fetchServiceCatalog([service_provider_id])
                    for row in service_catalog:
                        provider_data[service_provider_id]["service_catalog"].append({
                            "service_category": row["service_category"],
                            "service_name": row["service_name"]
                        })
                
                if "capabilities" in data_sources:
                    capabilities = ProviderDao.fetchCapabilities([service_provider_id])
                    for row in capabilities:
                        provider_data[service_provider_id]["capabilities"] = {
                            "key_technologies": row["key_technologies"],
                            "industries_we_work": row["industries_we_work"],
                            "partnerships": row["partnerships"],
                            "strength_area": row["strength_area"]
                        }
                
                if "case_studies" in data_sources:
                    titles = []
                    case_studies = ProviderDao.fetchCaseStudies([service_provider_id])
                    for row in case_studies:
                        _title = row.get("case_study_title") or ""
                        if _title not in titles:
                            provider_data[service_provider_id]["case_studies"].append({
                                "case_study": row
                            })
                        else:
                            titles.append(_title)
                            
                
                if "trmeric_assessment" in data_sources:
                    assessment = ProviderDao.fetchTrmericAssessment([service_provider_id])
                    for row in assessment:
                        provider_data[service_provider_id]["trmeric_assessment"] = {
                            "expertise_detail": row["expertise_detail"],
                            "why_tr_recommends": row["why_tr_recommends"],
                            "expertise_tr_rating": row["expertise_tr_rating"],
                            "delivery_tr_rating": row["delivery_tr_rating"],
                            "satisfaction_tr_rating": row["satisfaction_tr_rating"],
                            "innovation_tr_rating": row["innovation_tr_rating"],
                            "communication_tr_rating": row["communication_tr_rating"],
                            "reliability_tr_rating": row["reliability_tr_rating"]
                        }
                
                result["provider_data"] = dict(provider_data)
            else:
                appLogger.error({
                    "function": "get_provider_data",
                    "event": "NO_SERVICE_PROVIDER_FOUND",
                    "user_id": userID,
                    "tenant_id": tenantID,
                    "provider_id": provider_id
                })
        else:
            appLogger.error({
                "function": "get_provider_data",
                "event": "NO_PROVIDER_FOUND",
                "user_id": userID,
                "tenant_id": tenantID
            })

        # Fetch opportunities
        if "opportunities" in data_sources:
            result["opportunities"] = ProviderDao.fetchOpportunitiesByTenantId(tenantID)

        # Fetch win themes
        if "win_themes" in data_sources:
            result["win_themes"] = ProviderDao.fetchWinThemesByTenantId(tenantID)
            
        # print("result -- ", result)

        return result

    except Exception as e:
        appLogger.error({
            "function": "get_provider_data",
            "event": "FETCH_PROVIDER_DATA_FAILURE",
            "user_id": userID,
            "tenant_id": tenantID,
            "error": str(e)
        })
        return {
            "tenant_type": "customer",
            "project_brief": [],
            "service_provider_details": [],
            "provider_data": {},
            "opportunities": [],
            "win_themes": []
        }



ARGUMENTS = [
    {
        "name": "data_sources_array",
        "type": "string[]",
        "description": "Think and mention the sources required for the user query.",
        "options": [
            "service_catalog",
            "capabilities",
            "case_studies",
            "trmeric_assessment",
            "opportunities",
            "win_themes"
        ],
    }
]

FETCH_PROVIDER_DATA = TangoFunction(
    name="fetch_provider_data_by_function",
    description="""
        Fetches comprehensive provider data for a specified tenant, including tenant type, project briefs, service provider details, 
        service catalog, capabilities, case studies, trmeric assessment, opportunities, and win themes. The data sources to fetch 
        can be specified, or all sources are fetched if none are provided. Only provider tenants will have provider_data populated.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=get_provider_data,  # Updated to point to get_provider_data
    func_type="sql",
    integration="trmeric"
)
