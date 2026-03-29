import os
import re
import json
import datetime
import requests
import traceback
from typing import List, Dict, Optional
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Client import ChatCompletion,ModelOptions


# sections = [
#     "core_capabilities",
#     "service_catalog",
#     "offers",
#     "ways_of_working",
#     "case_studies",
#     "partnerships",
#     "certifications_and_audit",
#     "leadership_and_team",
#     "voice_of_customer",
#     "information_and_security"
# ]
def specify_sections_datasource(processed_json):
    """
    Processes a JSON object to create new keys with '_ai' suffix, adding a 'type' field
    indicating 'tango' or 'scrapped' based on the key name.
    """
    result = {}
    for key, value in processed_json.items():
        
        if key in ["future_capabilities", "industries", "team_projections"]:
            type_ = "tango"
        else:
            type_ = "scrapped"
        
        # Handle lists of dictionaries by adding 'type' to each dictionary
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            modified_list = [{**item, "source_type": type_} for item in value]
            result[key + "_ai"] = {key: modified_list}
        else:
            result[key + "_ai"] = {key: value, "source_type": type_}
    
    # with open(f'datasource_res.json', 'w') as file:
    #     json.dump(result, file, indent=4)
    return result



def process_canvas_data(canvas_data, tenant_id):
    
    try:
        # Core capabilities & Industry Domain
        core_capabilities = canvas_data.get("core_capabilities", {})
        description = core_capabilities.get("company_introduction", "")
        links = core_capabilities.get("social_media_links", [])
        # print("--debug links_before---", links)
        
        for item in links:
            item["type"] = map_social_platform(item.get("type", ""))
        print("\n\n--debug links after---", links)
        
        capabilities = core_capabilities.get("capabilities", {})
        current_capabilities = capabilities.get("current_capabilities", [])
        future_capabilities = capabilities.get("future_capabilities", [])
        industries = core_capabilities.get("industries", [])
        
        thought_process_future_capabilities = capabilities.get("thought_process_behind_future_capabilities", "")
        thought_process_industries = core_capabilities.get("thought_process_behind_industries", "")
        
        
        customer_industries = [
            {"industry_name": industry.get("industry_name", ""), "count": industry.get("current_customer_count", 0)}
            for industry in industries
        ]
        # print("--debug customer_industries---", customer_industries)
                
        # Service catalog
        service_catalog = canvas_data.get("service_catalog", {})
        services = service_catalog.get("services", [])
        tools_and_accelerators = service_catalog.get("tools_and_accelerators", [])
        solutions_suggested = service_catalog.get("solutions_suggested", [])
        thought_process_service_catalog = service_catalog.get("thought_process", "")
        
        
        for item in services:
            item["projects_executed_count"] = map_projects_executed_count(item["projects_executed_count"])
            item["consultants_count"] = map_consultants_count(item["consultants_count"])
        for item in tools_and_accelerators:
            item["type"] = map_tool_type(item["type"])
        for item in solutions_suggested:
            item["type"] = map_tool_type(item["type"])
            
        # print("--debug services---", services)
        # print("--debug tools_and_accelerators---", tools_and_accelerators)
        
        # Leadership & Team
        leadership_and_team = canvas_data.get("leadership_and_team", {})
        leadership = leadership_and_team.get("leadership", [])
        leadership = [item for item in leadership if item.get("name") is not None] 
        team_composition = leadership_and_team.get("team_composition", [])
        team_certifications = leadership_and_team.get("team_certifications", [])
        team_projections = leadership_and_team.get("team_projections", [])
        
        thought_process_team_projections = leadership_and_team.get("thought_process_behind_team_projections", "")
        # print("--debug thought_process_team_projections---\n\n", thought_process_team_projections)
        
        
        for item in team_composition:
            item["role_count"] = map_team_composition_certifications(item["role_count"])
        for item in team_certifications:
            item["count"] = map_team_composition_certifications(item["count"])
        for item in team_projections:
            item["month"] = map_team_project_month(item["month"])
            
        # print("--debug team_composition---", team_composition)
        # print("--debug team_certifications---", team_certifications)
        
        # Certification and Audit
        certifications_and_audit = canvas_data.get("certifications_and_audit", {})
        certifications = certifications_and_audit.get("company_certifications", [])
        audits = certifications_and_audit.get("company_audits", [])
        thought_process_certifications_audit = certifications_and_audit.get("thought_process", "")
        
        
        json_to_append = {"future": True, "with_in": 0, "tenant": tenant_id}
        json_to_append1 = {"future": False, "with_in": 0, "tenant": tenant_id}
        if certifications:
            for item in certifications:
                item.update(json_to_append1)
        if audits:
            for item in audits:
                item.update(json_to_append)
        # print("--debug certifications---", certifications,audits)
        
        # Info & Security
        info_security = canvas_data.get("information_and_security", {})
        data_privacy_protocols = info_security.get("current_data_privacy_protocals", "")
        future_data_privacy_protocols = info_security.get("future_data_privacy_protocals", "")
        thought_process_infosecurity = info_security.get("thought_process", "")
        
        
        # Voice of Customer
        customer_voice = canvas_data.get("voice_of_customer", {})
        voice_of_customer = [item for item in customer_voice.get("voice_of_customer", []) if item.get("name") is not None]
        
        customer_tenures = customer_voice.get("customer_tenures", [])
        for item in customer_tenures:
            item["type"] = map_customer_tenure(item.get("type", ""))
        existing_types = {item["type"] for item in customer_tenures if item["type"] != 0}
        for i in range(1, 7):
            if i not in existing_types:
                customer_tenures.append({"type": i, "count": 0})
        customer_tenures.sort(key=lambda x: x["type"])
        
        print("\n\n--debug customer_tenures---", customer_tenures)
        
        
        customer_desc = customer_voice.get("customer_desc", "")
        customer_desc_future = customer_voice.get("customer_desc_future", "")
        customer_types_serviced = customer_voice.get("customer_types_serviced", "")
        customer_feedback = customer_voice.get("customer_feedback_through", "")
        thought_process_voice_of_customer = customer_voice.get("thought_process", "")
        
        
        # Ways of Working
        working_ways = canvas_data.get("ways_of_working", {})
        service_delivery_steps = working_ways.get("ways_of_working", [])
        quality_management = working_ways.get("quality_management", "")
        risk_management = working_ways.get("risk_management", "")
        new_opportunity_sources = working_ways.get("opportunity_sources", [])
        new_customers_acquisition = map_customer_acquisition(working_ways.get("customers_acquisition", 0))
        
        customer_gestation_period = working_ways.get("customer_gestation_period", {})
        new_customer_start_time = customer_gestation_period.get("number", 0)
        new_customer_start_time_type = map_time_type(customer_gestation_period.get("type", 0))
        
        opp_hurdles = working_ways.get("opportunity_hurdles", "")
        opportunity_hurdles = [{"text": opp_hurdles}] if opp_hurdles else []
        
        bcp_constituents = working_ways.get("bcp_constituents", [])
        bcp = bool(bcp_constituents)
        payment_terms = map_payment_days(working_ways.get("payment_terms", 0))
        thought_process_behind_waysofworking = working_ways.get("thought_process", "")
        
        
        # Case Studies
        casestudies_publications = canvas_data.get("case_studies", {})
        case_studies = casestudies_publications.get("case_studies", [])
        publications = casestudies_publications.get("publications", [])
        thought_process_casestudies = casestudies_publications.get("thought_process", "")
        
        for item in case_studies:
            if not item.get("case_study_created_date"):
                item["case_study_created_date"] = None
        for item in publications:
            if not item.get("date"):
                item["date"] = None
                
        # print("\n\n--debug case_studies---", case_studies,'\n', publications)

        
        # Partnerships
        partnership = canvas_data.get("partnerships", {})
        partnerships = partnership.get("partnerships", [])
        for item in partnerships:
            item["with_in"] = map_team_project_month(item["with_in"])
        
        partnership_ecosystem_ = partnership.get("partnership_ecosystem", [])
        thought_process_partnership = partnership.get("thought_process", "")
        partnership_ecosystem = []
    
        for partner in partnership_ecosystem_:
            updated_partner = {
                "partner_name": partner.get("partner_name","Partner"),
                "impact_level": partner.get("impact_level","0"),
                "text": partner.get("leverage_partnership",""),
                "partner_success": partner.get("partner_success","")
            }
            partnership_ecosystem.append(updated_partner)
        # print("\n\n--debug partnerships---", partnerships,'\n', partnership_ecosystem)
        
        # Offers
        offer = canvas_data.get("offers", {})
        offers = offer.get("offers", [])
        for item in offers:
            item["pricing_model"] = map_pricing_model(item["pricing_model"])
        promotional_strategies = offer.get("promotional_strategies", [])
        offers_of_future = offer.get("offers_of_future", [])
        thought_process_offers = offer.get("thought_process", "")
        
        # print("--debug thought_process----", thought_process_offers,thought_process_service_catalog,'\n\n', thought_process_casestudies)
        # print('\n\n--debug offers---', offers, '\n', promotional_strategies)
        
        #processed json
        processed_json = {
            "description": description,
            "links": links,
            "current_capabilities": current_capabilities,
            "future_capabilities": future_capabilities,
            "industries": industries,
            "customer_industries": customer_industries,
            "services": services,
            "tools_and_accelerators": tools_and_accelerators,
            "leadership": leadership,
            "team_composition": team_composition,
            "team_certifications": team_certifications,
            "team_projections": team_projections,
            "data_privacy_protocols": data_privacy_protocols,
            "future_data_privacy_protocols": future_data_privacy_protocols,
            "certifications": certifications,
            "audits": audits,
            "voice_of_customer": voice_of_customer,
            "customer_tenures": customer_tenures,
            "customer_desc": customer_desc,
            "customer_desc_future": customer_desc_future,
            "customer_types_serviced": customer_types_serviced,
            "customer_feedback": customer_feedback,
            "service_delivery_steps": service_delivery_steps,
            "quality_management": quality_management,
            "risk_management": risk_management,
            "new_opportunity_sources": new_opportunity_sources,
            "new_customers_acquisition": new_customers_acquisition,
            "new_customer_start_time": new_customer_start_time,
            "new_customer_start_time_type": new_customer_start_time_type,
            "opportunity_hurdles": opportunity_hurdles,
            "bcp": bcp,
            "bcp_constituents": bcp_constituents,
            "payment_terms": payment_terms,
            "case_studies": case_studies,
            "publications": publications,
            "partnerships": partnerships,
            "partnership_ecosystem": partnership_ecosystem,
            "offers": offers,
            "promotional_strategies": promotional_strategies,
            "offers_of_future": offers_of_future,
            # "tango_analysis": tango_analysis
        }
        
        # Tango Analysis
        data_source = specify_sections_datasource(processed_json) #will deploy later in QA
        tango_analysis = {
            "tango_creation": True,
            "solutions_suggested": solutions_suggested,
            "thought_process": {
                "thought_process_future_capabilities": thought_process_future_capabilities,
                "thought_process_behind_industries": thought_process_industries,
                "thought_process_service_catalog": thought_process_service_catalog,
                "thought_process_offers": thought_process_offers,
                "thought_process_infosecurity": thought_process_infosecurity,
                "thought_process_waysofworking": thought_process_behind_waysofworking,
                "thought_process_casestudies": thought_process_casestudies, 
                "thought_process_partnership": thought_process_partnership,
                "thought_process_certifications_audit": thought_process_certifications_audit,
                "thought_process_behind_team_projections": thought_process_team_projections,
                "thought_process_voice_of_customer": thought_process_voice_of_customer
            },
            "parsed_data": data_source
        }
        
        processed_json["tango_analysis"] = tango_analysis
        # with open(f'process_canvas.json', 'w') as file:
        #     json.dump(processed_json, file, indent=4)
        return processed_json
        
        
    except Exception as e:
        print(f"Error processing canvas data: {str(e)}")
        appLogger.error({"event":"process_canvas_data", "error":str(e), "traceback":traceback.format_exc()})
        return {}


def format_quantum_canvas(canvas_data, tenant_id, user_id):
    """Get all the canvas sections and format for API payload"""
    
    print("\n\n--debug in format_quantum_canvas---", tenant_id, user_id)
    try:
        processed_data = process_canvas_data(canvas_data, tenant_id)
        
        formatted_json = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            
            # Core capabilities
            "description": processed_data.get("description",""),
            "links": processed_data.get("links",[]),
            "capabilities": processed_data.get("current_capabilities",[]),
            "future_capabilities": processed_data.get("future_capabilities",[]),
            
            # Industry and Domain
            "industries": processed_data.get("industries",[]),
            
            # Service catalog
            "service_category": processed_data.get("services",[]),
            "solutions": processed_data.get("tools_and_accelerators",[]),
            
            # Leadership & Team
            "leadership_team": processed_data.get("leadership",[]),
            "team_compositions": processed_data.get("team_composition",[]),
            "team_certifications": processed_data.get("team_certifications",[]),
            "team_projections": processed_data.get("team_projections",[]),
            
            # Info and Security
            "data_privacy_protocals": processed_data.get("data_privacy_protocols","No data available"),
            "future_data_privacy_protocals": processed_data.get("future_data_privacy_protocols","No data available"),
            
            # Certifications and Audits
            "company_certifications": processed_data.get("certifications",[]),
            "company_audits": processed_data.get("audits",[]),
            
            # Voice of Customer
            "customer_industries": processed_data.get("customer_industries",[]),
            "voice_of_customer": processed_data.get("voice_of_customer",[]),
            "customer_tenures": processed_data.get("customer_tenures",[]),
            "customer_desc": processed_data.get("customer_desc",""),
            "customer_desc_future": processed_data.get("customer_desc_future",""),
            "customer_types_serviced": processed_data.get("customer_types_serviced",""),
            "customer_feedback_through": processed_data.get("customer_feedback",""),
            
            # Ways of Working
            "new_customers_acquisition": processed_data.get("new_customers_acquisition",0),
            "new_customer_start_time": processed_data.get("new_customer_start_time",0),
            "new_customer_start_time_type": processed_data.get("new_customer_start_time_type","0"),
            "service_delivery_steps": processed_data.get("service_delivery_steps",[]),
            "quality_management": processed_data.get("quality_management",""),
            "risk_management": processed_data.get("risk_management",""),
            "bcp": processed_data.get("bcp",False),
            "bcp_constituents": processed_data.get("bcp_constituents",[]),
            "payment_terms": processed_data.get("payment_terms",0),
            "opportunity_hurdles": processed_data.get("opportunity_hurdles",[{"text": ""}]),
            "new_opportunity_sources": processed_data.get("new_opportunity_sources",[]),
            
            # Case Studies
            "case_study_docs": processed_data.get("case_studies",[]),
            "publications": processed_data.get("publications",[]),
            
            # Partnerships
            "partnerships": processed_data.get("partnerships",[]),
            "partnership_ecosystem": processed_data.get("partnership_ecosystem",[]),
            
            # Offers
            "offers": processed_data.get("offers",[]),
            "promotional_strategies": processed_data.get("promotional_strategies",""),
            "offers_of_future": processed_data.get("offers_of_future",""),
            
            # Tango Analysis
            "tango_analysis": processed_data.get("tango_analysis")
            # To-dos
            # "img_logo_id": "",
            # "img_bg_id": "",
        }
        
        return formatted_json
    except Exception as e:
        print(f"Error formatting canvas data: {e}")
        appLogger.error({"event":"format_quantum_canvas", "error":str(e), "traceback":traceback.format_exc()})

















def save_quantum_canvas(canvas_data):
    try:
        # print("--debug [Django Backend URL]-----", os.getenv("DJANGO_BACKEND_URL"))
        # https://trmeric-strong.trmeric.com/api/provider/profile/save_tango
        create_quantum_url = os.getenv("DJANGO_BACKEND_URL") + "api/provider/profile/save_tango"
        
        # print("--debug create_quantum_url----", create_quantum_url)
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(create_quantum_url, headers=headers, json=canvas_data, timeout=4)
        # print("\n\n---debug response----------", response.content,'\n', response.encoding)
        
        # b'{"status":"success","statusCode":200,"message":"Provider Profile saved successfully"}'
        # result = json.loads(response.content)
        # print("content", result)
        # print(response.raw, response.content,response.encoding, response.headers, response.history, response.reason)
        # print("\n\nStatus Code:", response.status_code)
        # print("Response Content:", response.text)
        
        result = {"status_code": response.status_code, "message": response.text}
        return result
    except Exception as e:
        print("--debug error in save_quantum_canvas", str(e))
        appLogger.error({"event": "save_quantum_canvas", "error": str(e), "traceback": traceback.format_exc()})
        return {"status": "error", "response": str(e)}



def quantum_to_storefront_api(quantum_data):
    try:
        # fetch quantum_data created for provider for approval via mail
        return
    
    except Exception as e:
        print("--debug error in quantum_to_storefront_api", str(e))
        appLogger.error({"event": "quantum_to_storefront_api", "error": str(e), "traceback": traceback.format_exc()})



def map_social_platform(value: str | None) -> int:
    """Map social platform string to a numerical category."""
    
    mapping = {
        "linkedin": 1,
        "instagram": 2,
        "youtube": 3,
        "twitter": 4,
        "facebook": 5,
        "whatsapp": 6,
        "pinterest": 7,
        "reddit": 8,
        "telegram": 9
    }
    return mapping.get((value or "none").lower(), 0) or 0


    
def map_customer_tenure(value: str) -> int:
    """Map customer tenure string to a numerical category."""
    mapping = {
        "0-1 years": 1,
        "1-3 years": 2,
        "3-5 years": 3,
        "5-10 years": 4,
        "10-15 years": 5,
        "15+ years": 6
    }
    return mapping.get(value, 0) or 0
    
    
    
def map_pricing_model(value: str | None) -> int:
    """Map pricing model string to a numerical category."""
    mapping = {
        "free": 1,
        "normal price": 2,
        "premium model": 3
    }
    return mapping.get((value or "none").lower(), 0) or 0
    

        
def map_time_type(value: str) -> int:
    """Map time unit string to a numerical category."""
    mapping = {
        "days": 1,
        "weeks": 2,
        "months": 3,
        "years": 4
    }
    return mapping.get(value.lower(), 0) or 0
        
        

def map_customer_acquisition(value: int) -> int:
    """Map customer acquisition value to a numerical category."""
    ranges = [
        ((0, 10), 1),
        ((11, 50), 2),
        ((51, 100), 3),
        ((101, 200), 4),
        ((201, float('inf')), 5)
    ]
    value = int(value) 
    for (low, high), category in ranges:
        if low <= value <= high:
            return category
    return 0  



def map_payment_days(value) -> int:
    """Map payment days to a numerical category."""
    if isinstance(value, str):
        return 0
    ranges = [
        ((0, 15), 1),
        ((16, 30), 2),
        ((31, 45), 3),
        ((46, 60), 4),
        ((61, 90), 5),
        ((91, float('inf')), 6)
    ]
    value = int(value)  
    for (low, high), category in ranges:
        if low <= value <= high:
            return category
    return 0 



def map_projects_executed_count(value: int) -> str:
    """Map integer value to projects executed count string label."""
    
    ranges = [
        ((1, 5), '1 – 5'),
        ((6, 10), '5+'),
        ((11, 20), '10+'),
        ((21, 30), '20+'),
        ((31, 40), '30+'),
        ((41, 50), '40+'),
        ((51, 100), '50+'),
        ((101,200), '100+'),
        ((201, float('inf')), '200+')
    ]
    
    for (low,high),label in ranges:
        if low<=value<=high:
            return label
    return ''

    
def map_consultants_count(value: int) -> str:
    """Map integer value to consultants count string label."""
    
    ranges = [
        ((1, 10), '1 – 10'),
        ((10, 25), '10+'),
        ((25, 50), '25+'),
        ((50, 100), '50+'),
        ((100, 200), '100+'),
        ((200, 300), '200+'),
        ((300, 500), '300+'),
        ((500, 1000), '500+'),
        ((1000, float('inf')), '1000+')
    ]
    for (low, high), label in ranges:
        if low <= value <= high:
            return label
    return ''
     
    
    
    

def map_tool_type(tool_type: str) -> int:
    """Map tool/accelerator/solution type to a numerical value."""
    mapping = {
        'Accelerator': 1,
        'Tool': 2,
        'Solution': 3,
        'Service': 4
    }
    return mapping.get(tool_type, 0)  

def map_team_composition_certifications(composition: str) -> int:
    """Map team composition to a numerical value."""
    mapping = {
        '1– 10': 1,
        '10+': 2,
        '25+': 3,
        '50+': 4,
        '100+': 5,
        '500+': 6,
        '1000+': 7
    }
    return mapping.get(composition, 0)  


def map_team_project_month(month: str) -> int:
    """Map project month to a numerical value."""
    month = month.lower() if month else 'none'
    mapping = {
        'january': 1,
        'february': 2,
        'march': 3,
        'april': 4,
        'may': 5,
        'june': 6,
        'july': 7,
        'august': 8,
        'september': 9,
        'october': 10,
        'november': 11,
        'december': 12
    }
    return mapping.get(month, 0)  




def fetch_company_info(website) -> dict:
        
        match = re.search(r'://(?:www\.)?([^/.]+)', website).group(1)
        insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=66, user_id=86,key=f"company_{match}")
        print("match--", match)
        if len(insights)==0:
            llm = ChatGPTClient()
            model_opts = ModelOptions(model = "gpt-4.1",max_tokens=8000,temperature=0.1)
            prompt = companyInfoPrompt(website)
            result = llm.run(prompt,model_opts,"company_info",logInDb={"tenant_id":66,"user_id":86})
            data = extract_json_after_llm(result)

            TangoDao.upsertTangoState(tenant_id=66,user_id=86,key=f"company_{match}",value=json.dumps(data),session_id=None)
            return data
        else:
            insights_val = insights[0]["value"]
            print("--debug fetch_company_info cache------", len(insights_val))
            return json.loads(insights_val)
        

def companyInfoPrompt(website) -> ChatCompletion:
    prompt = f"""
        You are a highly skilled web scraping agent tasked with extracting comprehensive information from a company's website. Your goal is to navigate through all accessible pages—including Home, About, Services, Contact, Blog, Case Studies, Careers, and any other relevant sections—and compile a detailed summary of the entire site.
        **Company Website**: {website}
        
        - Scrape and synthesize all textual content from the website into a cohesive executive-level detail (in 6000–10000 words).
        - Ensure the summary captures the company’s mission, services/products, team, client success stories, thought leadership, and any other publicly available insights.
        
        Strictly output the result in the following JSON format:
        ```json
        {{
            "company_info": "<Detailed summary of the website content>",
            "links": ["<List of all internal URLs traversed>"]
        }}
        ```
    """
    return ChatCompletion(system=prompt,prev = [],user = "")


    
## Prev methods
# def map_social_platform(value: str) -> int:
#     value = value.lower() if value else "none"
#     match value:
#         case "linkedin":
#             return 1
#         case "instagram":
#             return 2
#         case "youtube":
#             return 3
#         case "twitter":
#             return 4
#         case "facebook":
#             return 5
#         case "whatsapp":
#             return 6
#         case "pinterest":
#             return 7
#         case "reddit":
#             return 8
#         case "telegram":
#             return 9
#         case _:
#             return 0

# def map_customer_tenure(value:str)->int:
#     match value:
#         case "0-1 years":
#             return 1
#         case "1-3 years":
#             return 2
#         case "3-5 years":
#             return 3
#         case "5-10 years":
#             return 4
#         case "10-15 years":
#             return 5
#         case "15+ years":
#             return 6
#         case _:
#             return 0

# def map_pricing_model(value)->int:
#     value = value.lower() if value else "none"
#     print("--debug map_pricing_model----", value)
#     match value:
#         case "free":
#             return 1
#         case "normal price":
#             return 2
#         case "premium model":
#             return 3
#         case _:
#             return 0

# def map_time_type(value:str)->int:
#     match value:
#         case "days":
#             return "1"
#         case "weeks":
#             return "2"
#         case "months":
#             return "3"
#         case "years":
#             return "4"
#         case _:
#             return "0"

# def map_customer_acquisition(value)->int:
#     value = int(value)
#     if value<=10:
#         return 1
#     elif value>10 and value<=50:
#         return 2
#     elif value>50 and value<=100:
#         return 3
#     elif value>100 and value<=200:
#         return 4
#     elif value>200:
#         return 5

# def map_payment_days(value)->str:
#     if type(value) == str:
#         return 0
#     if value<=15:
#         return 1
#     elif value>15 and value<=30:
#         return 2
#     elif value>30 and value<=45:
#         return 3
#     elif value>45 and value<=60:
#         return 4
#     elif value>60 and value<=90:
#         return 5
#     elif value>90:
#         return 6

# def map_team_certifications(certifications: str) -> int:
#     """Map team certifications count to a numerical value."""
#     mapping = {
#         '1– 10': 1,
#         '10+': 2,
#         '25+': 3,
#         '50+': 4,
#         '100+': 5,
#         '500+': 6
#     }
#     return mapping.get(certifications, 0)  # Return 0 if invalid input

# def map_consultants_count(value: int) -> str:
#     """Map integer value to consultants count string label."""
#     if value>=1 and value<=10:
#         return '1 – 10'
#     elif value>=10 and value<=25:
#         return '10+'
#     elif value>=25 and value<=50:
#         return '25+'
#     elif value>50 and value<=100:
#         return '50+'
#     elif value>100 and value<=200:
#         return '100+'
#     elif value>200 and value<=300:
#         return '200+'
#     elif value>300 and value<=500:
#         return '300+'
#     elif value>500 and value<=1000:
#         return '500+'
#     elif value>1000:
#         return '1000+'
#     else:
#         return ''  # Return empty string if invalid input

# def map_projects_executed_count(value: int) -> str:
#     """Map integer value to projects executed count string label."""
#     if value>=1 and value<=5:
#         return '1 – 5'
#     elif value>=6 and value<=10:
#         return '5+'
#     elif value>=11 and value<=20:
#         return '10+'
#     elif value>=21 and value<=30:
#         return '20+'
#     elif value>=31 and value<=40:
#         return '30+'
#     elif value>=41 and value<=50:
#         return '40+'
#     elif value>=51 and value<=100:
#         return '50+'
#     elif value>=101 and value<=200:
#         return '100+'
#     elif value>=201:
#         return '200+'
#     else:
#         return ''  # Return empty string if invalid input














    




























