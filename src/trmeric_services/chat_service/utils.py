import time
import json
import traceback
from src.trmeric_database.dao import *
from src.trmeric_utils.json_parser import save_as_json
from src.trmeric_api.logging.AppLogger import appLogger,debugLogger
from src.trmeric_database.Redis import RedClient


##Demand flow for EY tenants: Dev: 776, QA: 232,160,234 Prod: 183,200
DEMAND_TENANTS = [776, 232, 183,"776","232","183", 160, "160",200,"200",234,"234", 209, "209"]

#Generate canvas after conv: Demand/Roadmap, Portfolio, Ideation, Project, Mission
CANVAS_CHATTYPES = [3,5,6,2,4]

def get_tenant_portfoliocontext(tenant_id:int, portfolio_ids:list[int]) -> dict:
    try:
        context = TenantDaoV2.fetch_portfolio_context(tenant_id = tenant_id, portfolio_ids=portfolio_ids)
        if not context:
            return {}
        
        portfolio_context = context.get("portfolio_context",[]) or []
        if not portfolio_context:
            return {}
        result = []
        for i in portfolio_context:
            result.append({
                'portfolio': i.get('portfolio_title'),
                'context': [
                    {
                        'type': s.get('content_type',''),
                        'summary': s.get('summary',''),
                        'content': s.get('content','')
                    }
                    for s in i.get('items',[]) or []
                ]
            })
        save_as_json(result,f"tenant_portfoliocontext_{tenant_id}.json")
        return result
        
    except Exception as e:
        print("--debug error retrieving get_tenant_portfoliocontext----", str(e))
        appLogger.error({'event': 'get_tenant_portfoliocontext','error': str(e),'traceback': traceback.format_exc(), 'tenant_id':tenant_id}) 
        return {}



def get_consolidated_persona_context_utils(tenant_id,user_id,chat_type:int=0):
    
    return RedClient.execute(
        query = lambda: get_consolidated_persona_context(tenant_id,user_id,chat_type=chat_type),
        key_set = f"Chat::tenant_id:{tenant_id}::user_id:{user_id}",
        expire = 200
    )


def roadmapPersona(tenant_id:int,user_id:int,provider_info:dict={}):
    """Conversational flow - we will enhance the prompts, questions & experience - 
    hook up to the knowledge , persona , customer , portfolio"""

    if provider_info:
        return provider_info
    
    debugLogger.info(f"--debug roadmapPersona {tenant_id} {user_id}")
    context = {
        "role": "",
        "customer_context": {},
        "org_strategy": "",
        "knowledge": "",
        "all_portfolios_of_customer": [],
        "user_portfolios": [],
        "customer_info": {}
    }
    
    customerInfo = None
    try:
        customerInfo = TenantDaoV2.fetch_trucible_customer_context(tenant_id=tenant_id)
    except Exception as e:
        print("error fetching trucible context --- ", e, traceback.format_exc())
    
    context["customer_info"] = customerInfo
        
        
    
    role =  AuthDao.fetchRoleOfUserInTenant(user_id)
    personaData = CustomerDao.FetchCustomerPersona(tenant_id)
    all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id)
    context["all_portfolios_of_customer"] = all_portfolios
    # demand_portfolios_ = PortfolioDao.fetchPortfoliosOfRoadmaps(tenant_id)
    
    user_portfolios_ = PortfolioDao.fetchApplicablePortfolios(user_id, tenant_id)
    
    # print("\n\n\n--deubg user_portfolios--------------", user_portfolios_)
    
    org_strategy = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id)
    solution_context_ = TenantDao.listCustomerSolutions(tenant_id)
    # print("\n\n\n--deubg solution_context--------------", solution_context_[:2])

    solution_context = []
    for sol in solution_context_:
        # if sol.get("application_type", "") is not None: # to remove this check later
        new_sol = {k: v for k, v in sol.items() if k not in ["additional_details","id","tenant_id","application_type","service_line"]}
        new_sol["type"] = sol["application_type"]
        new_sol["portfolio"] = sol["service_line"]
        solution_context.append(new_sol)


    # [{'name': 'Carbon Accounting', 'description': 'BHP Maritime requires detailed data and insights into emissions generated from BHP-chartered and customer-chartered Maritime transport. Key uses for this information include: o Improved vessel selection on the basis of emissions intensity. o Recognition of emissions abatement from decarbonisation initiatives and changes, including LNG, biofuels etc. o Emissions per product tonne analysis to meet future sales and marketing requests to prove social value.  o Monitoring of emissions intensity and total emissions in real-time, compared MOM and YOY as well as against BHPs 2030 Scope 3 goals (support 40% emissions intensity reduction of BHP-chartered shipping of our products).',
    #  'category': 'SaaS', 'technology': '', 'service_line': 'COM - Maritime & Supply Chain - CFT', 'additional_details': {}, 'type': 'Platform'}

    # print("\n\n\n--deubg solution_context 2222--------------", solution_context[:2])

    # debugLogger.info(f"Fetched customer role------{role}\n\n Persona: {personaData} and \n\n Portfolios: {demand_portfolios_}")
    
    context["role"] = role
    context["customer_context"]["org_info"] = personaData[0]["org_info"]
    context["customer_context"]["persona"] = personaData[0]["persona"]
    
    user_portfolios = []
    for portfolio in user_portfolios_:
        title = portfolio.get("title","") or None
        if title:
            user_portfolios.append(title)
    
    appLogger.info({"event":"roadmapPersona","user_portfolios":user_portfolios,"tenant_id":tenant_id,"user_id":user_id})
            
    # demand_portfolios= []
    # for portfolio in demand_portfolios_:
    #     title = portfolio.get("title","") or None
    #     if title:
    #         demand_portfolios.append(title)
    # context["demand_portfolios"] = demand_portfolios[:10]
            
    context["user_portfolios"] = user_portfolios
    context["org_strategy"] = org_strategy
    context["knowledge"] = solution_context
    
    
    # save_as_json(context, f"context_{tenant_id}_{user_id}.json")
    # print("debug roadmap ")
    return context



def ey_parseQnA(decoded,chat_type,result):
    
    print("--debug ey_parseQnA----",decoded.get("tenant_id",""))
    try:
        tenant_id = decoded.get("tenant_id","")
        user_id = decoded.get("user_id","")
        
        if chat_type == 3:
            found = False
            for item in result:
                if found:
                    item["question"]["draft_title"] = ""
                elif item["question"].get("draft_title_generated", False):
                    found = True
        return result
    except Exception as e:
        print("--debug error parsing qna--", str(e))
        appLogger.error({"event":"ey_parseQnA","error":str(e),"traceback":traceback.format_exc(),"tenant_id":tenant_id,"user_id":user_id})
            


def process_uploaded_files(file_analyzer, uploaded_files,step_sender=None,source='creation'):

    if not uploaded_files or len(uploaded_files) == 0:
        return []
    
    start = time.time()
    files_content = []
    file_analyzer_input = {}

    if source == 'creation':
        file_analyzer_input["files_s3_keys_to_read"] = [file["key"].get("s3_key","") for file in uploaded_files]
    else:
        file_analyzer_input["files_s3_keys_to_read"] = list(uploaded_files.keys())

    print("--deubg file_analyzer_input ",file_analyzer_input)
    step_sender.sendSteps("Ingesting Uploaded files", False)
    result = file_analyzer.analyze_files(params = file_analyzer_input)
    file_analysis = result.get("files",[]) or []

    print("--debug result--",result.get("file_count",0) or 0, "File content: \n",len(file_analysis))
    for file in file_analysis:
        files_content.append({"file_name":file.get("filename",""), "content":file.get("content","")})

    print("--debug demand_file_analysis time---", time.time()- start)
    step_sender.sendSteps("Ingesting Uploaded files", True)

    return files_content



def agentNameMapping(chat_type):
    return {
        1 : "discovery_agent",
        2 : "project_creation_agent",
        3 : "roadmap_creation_agent",
        # 4 : "onboarding_agent",
        4 : "mission_agent",
        5 : "portfolio_agent",
        6 : "ideation_agent",
        0: "none"
    }.get(chat_type,0)








def get_consolidated_persona_context(tenant_id,user_id,chat_type=0) -> dict:
    """
    Consolidated function to fetch roadmap persona and customer context.
    
    Combines logic from roadmapPersona and update_persona_data.
    Returns comprehensive context for tenant, user, and roadmap interactions.
    """
    from src.trmeric_services.agents.core import BaseAgent

    # Return provider info if provided
    print("--debug in get_consolidated_persona_context------", tenant_id)
    log_info = {"tenant_id": tenant_id,"user_id": user_id}

    print("--debug in get_consolidated_persona_context----- chat type", chat_type, "Log info: ", log_info)
    debugLogger.info(f"Fetching consolidated persona context - tenant: {tenant_id}, user: {user_id}")
    
    # Initialize context
    context = {
        "tenant_info": {},
        "customer_info": {},
        "persona": {
            "core_business": "",
            "industry_domain_specialization": ""
        },
        "org_alignment": [],
        "user_portfolios": [],
        "all_portfolios": [],
        "solutions_knowledge": [],
        "roadmap_project_knowledge": None,
        "user_language": "English",
        "role": "",
        "technologies": [],
        "tenant_format": {
            "currency_format": "USD",
            "date_format": "YYYY-MM-DD"
        }
    }
    
    try:
        # 1. Fetch Customer Information
        customer_info = TenantDaoV2.fetch_trucible_customer_context(tenant_id=tenant_id)
        context["customer_info"] = customer_info


        # Tenant config
        tenant_config = TenantDao.getTenantInfo(tenant_id)
        tenant_config_res = tenant_config[0].get("configuration",None) if tenant_config else None

        if tenant_config_res is not None:
            context["tenant_format"]["currency_format"] = tenant_config_res.get("currency","USD") or "USD"
            context["tenant_format"]["date_format"] = tenant_config_res.get("date_time","YYYY-MM-DD") or "YYYY-MM-DD" 
        print("--debug Tenant format_currency_&_date: ", context["tenant_format"])
        
        # 2. Fetch Organization Details & Persona
        persona_data = CustomerDao.FetchCustomerPersona(tenant_id)
        if len(persona_data)>0:
            org_info = persona_data[0].get("org_info","") or None
            persona = persona_data[0].get("persona","") or None
            context["tenant_info"] = org_info
            if persona:
                context["persona"] = {
                    "core_business": persona.get("core_business", "") or "",
                    "industry_domain_specialization": persona.get("industry_domain_specialization", "") or ""
                }
        
        # 3. Fetch Organizational Strategy
        org_strategy = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id)
        context["org_alignment"] = org_strategy
        
        # 4. Fetch User Role
        role_key_ =  AuthDao.fetchRoleOfUserInTenant(user_id)
        role_key = role_key_.upper()
        role = (USER_ROLES.get(role_key) or USER_ROLES["DEFAULT"]).get("role") or "Organization Demand Requestor"
        context["role"] = role
        print("--debug role-----", role)
        
        # 5. Fetch Portfolios
        all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id)
        context["all_portfolios"] = all_portfolios
        
        user_portfolios_raw = PortfolioDao.fetchApplicablePortfolios(user_id, tenant_id)
        context["user_portfolios"] = [p.get("title", "") for p in user_portfolios_raw if p.get("title")]

        if len(context["user_portfolios"]) == 0:
            context["user_portfolios"] = [portfolio["title"] for portfolio in all_portfolios if len(all_portfolios) > 0]
        
        # 6. Fetch Solutions Knowledge
        solution_context_raw = TenantDao.listCustomerSolutions(tenant_id)
        # print("--debug fetched solutions count---", len(solution_context_raw))
        context["solutions_knowledge"] = _process_solutions(solution_context_raw)

        # save_as_json(context["solutions_knowledge"], f"solutions_{tenant_id}_{user_id}.json")
        
        # 7. Fetch User Language
        language = UsersDao.fetchUserLanguage(user_id) or "English"
        context["user_language"] = language
        
        # 8. Fetch Roadmap Project Knowledge (if chat_type provided)
        if chat_type == 6:
            roadmap_project_knowledge = BaseAgent(log_info=log_info).project_and_roadmap_context_string
            context["roadmap_project_knowledge"] = roadmap_project_knowledge


        technologies_ = ProjectsDao.fetchAllProjectTechnologies()
        technologies = [tech['title'] for tech in technologies_ if tech['title'] is not None][:100]
        context["technologies"] = technologies or []
        
        # Log successful fetch
        appLogger.info({
            "event": "consolidated_persona_context",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "user_portfolios_count": len(context["user_portfolios"])
        })
        
    except Exception as e:
        appLogger.error({"event":"get_consolidated_persona_context","error": str(e), "traceback":traceback.format_exc()})
        return {
            "tenant_info": {},
            "customer_info": {},
            "persona": {"core_business": "", "industry_domain_specialization": ""},
            "org_alignment": [],
            "user_portfolios": [],
            "all_portfolios": [],
            "solutions_knowledge": [],
            "roadmap_project_knowledge": None,
            "user_language": "English",
            "role": "",
            "technologies": [],
            "error": str(e)
        }
    
    return context


def _process_solutions(solutions: list,limit=5) -> list:
    """Helper function to process and clean solution data."""
    processed = []
    for sol in solutions:
        # Filter out unwanted fields
        filtered_sol = {k: v for k, v in sol.items() 
                       if k not in ["additional_details", "id", "tenant_id", "application_type", "service_line"]}
        
        # Add processed fields
        filtered_sol["type"] = sol.get("application_type", None) or None
        filtered_sol["portfolio"] = sol.get("service_line", None) or None
        
        processed.append(filtered_sol)
    
    print("--debug processed solutions count---", len(processed))
    ####Grouping solutions by portfolio and type
    grouped = {}
    ##Nested json by portfolio -> type -> list of solutions
    for sol in processed:
        # print("--debug sol---", sol)
        portfolio = sol.get("portfolio", "General")
        sol_type = sol.get("type", "Application") or "Application"

        if not portfolio or not sol_type:
            continue
        
        if portfolio not in grouped:
            grouped[portfolio] = {}
        if sol_type not in grouped[portfolio]:
            grouped[portfolio][sol_type] = []
        
        entry = {k: v for k, v in {
            "name": sol.get("name"),"description": sol.get("description"),"technology": sol.get("technology")}.items()
            if v not in [None, "", " ",'']
        }        
        if len(grouped[portfolio][sol_type]) < limit and entry not in grouped[portfolio][sol_type]:
            grouped[portfolio][sol_type].append(entry)
        
    return grouped



def portfolio_context_for_subportfolio_creationconv(portfolio_id:int, tenant_id: int) -> dict:
        
    # Portofolio context will include
    # - Parent portfolio details: id,title,industry, techstack etc.
    # - Its kpi(s), sponsor info, budget
    # - All its subportfolios: the list of portfolios whose parent is above & same details covering it
    try:
        # context = PortfolioDao.fetchPortfolioContext(portfolio_ids=[portfolio_id],tenant_id=tenant_id)
        context = RedClient.execute(
            query = lambda: PortfolioDao.fetchPortfolioContext(portfolio_ids=[portfolio_id],tenant_id=tenant_id),
            key_set = f"PortfolioContext::Portfolio::{portfolio_id}::TenantID::{tenant_id}",
            expire = 40000
        )
        # print("--debug context---------1", context)

        if len(context) == 0:
            return {}

        context_ = context[0]
        # print("\n--debug context---------2", len(context_))

        parent_portfolio = context_.get("portfolio_info",{}) or {}
        sub_portfolios = context_.get("sub_portfolios",[]) or []
        print("--debug fetched context for: ", context_.get("portfolio_id"), "  other info: sub-portfolios are: ",len(sub_portfolios))

        context = {
            "parent_portfolio": parent_portfolio,
            "sub_portfolios": sub_portfolios
        }

        return context

    except Exception as e:
        print("--debug error in portfolio_context---------", str(e))
        return {}

















USER_ROLES = {
        
    "ORG_DEMAND_MANAGER":{
        "role": "Organization Demand Manager",
        "tone": "Formal, strategic, e.g., “Thank you for your input, let’s align this with your organization’s goals",
        "follow_up_questions": "",
    },
    "ORG_DEMAND_REQUESTOR":{
        "role": "Organization Demand Requestor",
        "tone": "Practical,Supportive, guiding,(the one who's going to create the new demands)",
        "follow_up_questions": "",
    },
    "ORG_ADMIN": {
        "role": "Organization Administrator",
        "tone": "Formal, strategic, e.g., “Thank you for your input, let’s align this with your organization’s goals",
        "follow_up_questions": "",
    },
    
    "ORG_PROJECT_MANAGER":{
        "role": "Project Manager",
        "tone": "Practical, project-oriented, e.g., “Thanks, let’s dive into the project’s scope",
        "follow_up_questions": "",
    },
    "PORTFOLIO_LEADER": {
        "role": "Portfolio Leader",
        "tone": "Collaborative, portfolio-focused, e.g., Great, let’s ensure this fits your portfolio’s objectives",
        "follow_up_questions": "",
    },
    "ORG_MEMBER":{
        "role": "Organization member",
        "tone": "Supportive, guiding, e.g., Let’s work together to define this demand clearly.",
        "follow_up_questions": "",
    },
    "ORG_LEADER":{
        "role": "Organization Leader",
        "tone": "Supportive, guiding, e.g., Let’s work together to define this demand clearly.",
        "follow_up_questions": "",
    },
    "DEFAULT": {
        "role": "Organization Administrator",
        "tone": "Formal, strategic, e.g., “Thank you for your input, let’s align this with your organization’s goals",
        "follow_up_questions": ""
    },
    "ORG_SPONSOR_APPROVER": {
        "role": "Organization Sponsor Approver",
        "tone": "Formal, decision-oriented, e.g., 'Thanks for the request, let’s evaluate this for approval.'",
        "follow_up_questions": "",
    },

}



