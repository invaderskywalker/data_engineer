import json
from collections import defaultdict
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ProviderDao,QuantumDao
from src.trmeric_services.tango.functions.Types import TangoFunction



RETURN_DESCRIPTION = """
    Returns a dictionary containing quantum data for a provider's onboarding process for the specified tenant and provider. The structure includes:

    - aspiration (object): Provider's company description and aspiration documents.
    - core_capabilities (array): List of technologies and associated modules used by the provider.
    - service_catalog (array): List of service categories and details offered by the provider.
    - industry_and_domain (array): List of industries served by the provider.
    - leadership_and_team (object): Team composition and projections for the provider.
    - voice_of_customer (array): Customer feedback details.
    - offers (array): List of provider's offers and their details.
    - case_studies (jsonb): Case study documents stored as JSONB.
    - partnerships (array): List of partner details.
    - ways_of_working (object): Service delivery process and management practices.
    - information_and_security (object): Data privacy and security protocols.
    - certifications_and_audit (array): List of certifications held by the provider's team.
"""


def get_quantum_data(provider_id: int, tenant_id: int, user_id: int, data_sources_array=[]) -> dict:
    
    """
        Fetches quantum data for a given tenant and provider including different sections like service catalog, offers, ways of working,
        case studies, partnerships, certifications and audit,leadership and team, voice of customer, and information and security.
    """
    try:
        print("\n\n----debug get_quantum_data------ ", provider_id, tenant_id, user_id, data_sources_array)
        quantum_data = {}
        sections = data_sources_array if len(data_sources_array) > 0 else  [
            "service_catalog",
            "offers",
            "ways_of_working",
            "case_studies",
            "partnerships",
            "certifications_and_audit",
            "leadership_and_team",
            "voice_of_customer",
            "information_and_security"
        ]
        
        if tenant_id is None or provider_id is None:
            appLogger.error({
                "function": "get_quantum_data",
                "event": "INVALID_INPUT",
                "provider_id": provider_id,
                "user_id": user_id,
                "tenant_id": tenant_id
            })
            return quantum_data

        print("--debug quantum ids ------ ", provider_id,tenant_id)
        ###the db calls to fetch the quantum sections data
        # Fetch data for each requested section
        for section in sections:
            match section:
                case "service_catalog":
                    quantum_data["service_catalog"] = QuantumDao.fetch_service_catalog(tenant_id, provider_id)
                case "offers":
                    quantum_data["offers"] = QuantumDao.fetch_offers(tenant_id, provider_id)
                case "ways_of_working":
                    quantum_data["ways_of_working"] = QuantumDao.fetch_ways_of_working(tenant_id, provider_id)
                case "case_studies":
                    quantum_data["case_studies"] = QuantumDao.fetch_case_studies(tenant_id, provider_id)
                case "partnerships":
                    quantum_data["partnerships"] = QuantumDao.fetch_partnerships(tenant_id, provider_id)
                case "certifications_and_audit":
                    quantum_data["certifications_and_audit"] = QuantumDao.fetch_certifications_and_audit(tenant_id, provider_id)
                case "leadership_and_team":
                    quantum_data["leadership_and_team"] = QuantumDao.fetch_leadership_and_team(tenant_id, provider_id)
                case "voice_of_customer":
                    quantum_data["voice_of_customer"] = QuantumDao.fetch_voice_of_customer(tenant_id, provider_id)
                case "information_and_security":
                    quantum_data["information_and_security"] = QuantumDao.fetch_information_and_security(tenant_id, provider_id)
                case "aspiration":
                    quantum_data["aspiration"] = QuantumDao.fetch_aspiration(tenant_id, provider_id)
                case "core_capabilities":
                    quantum_data["core_capabilities"] = QuantumDao.fetch_core_capabilities(tenant_id, provider_id)
                case _:
                    print("Invalid section requested:", section)
                    appLogger.error({
                        "function": "get_quantum_data",
                        "event": "INVALID_SECTION",
                        "section": section,
                        "tenant_id": tenant_id,
                        "provider_id": provider_id
                    })    

        with open(f"quantum_data_{tenant_id}_{provider_id}.json", "w") as file:
            json.dump(quantum_data, file, indent=4)
            
        return quantum_data

    except Exception as e:
        appLogger.error({
            "function": "get_quantum_data",
            "event": "FETCH_QUANTUM_DATA_FAILURE",
            "provider_id": provider_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "error": str(e)
        })
        return {}




FETCH_QUANTUM_DATA = TangoFunction(
    name="fetch_quantum_data_by_function",
    description="""
        Fetches comprehensive quantum data for a provider for a specified tenant and provider, including all the relevant sections such as
        "service_catalog","offers","ways_of_working","case_studies","partnerships","certifications_and_audit","leadership_and_team",
        "voice_of_customer","information_and_security".
    """,
    args=[],
    return_description=RETURN_DESCRIPTION,
    function=get_quantum_data,
    func_type="sql",
    integration="trmeric"
)
