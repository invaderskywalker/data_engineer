import json
import traceback
import threading
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import TangoDao,ProjectsDao,PortfolioDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.prompts.agents import portfolio
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_services.agents.apis.portfolio_api.BasePortfolioApiService import BaseAgentService
from src.trmeric_services.agents.functions.utility.socketio import emit_event,timeline_event,send_timeline_updates
from src.trmeric_services.chat_service.utils import get_consolidated_persona_context_utils,get_tenant_portfoliocontext


def fetch_portfolio_chat_prefill(socketio, client_id, metadata, **kwargs):
    """
    Wrapper method to call QnaController.fetchQnaChatPrefillSocketIO with _type="portfolio".
    """
    from src.controller.qna import QnaController
    return QnaController().fetchQnaChatPrefillSocketIO(
        socketio=socketio,
        client_id=client_id,
        metadata=metadata,
        _type="portfolio"
    )


QNA_CHAT_PREFILL_PORTFOLIO= AgentFunction(
    name="fetch_portfolio_chat_prefill",
    description="This function is used to generate the canvas for portfolio creation.",
    args=[],
    return_description="",
    function=fetch_portfolio_chat_prefill,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

def portfolio_projects_info(
    projects: list[dict],
    params: list[str] = ['project_name', 'roadmap_title', 'objectives', 'kpi_names']
):

    result = []
    for project in projects:
        filtered = {}
        for param in params:
            value = project.get(param)

            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue

            if isinstance(value, list):
                cleaned_list = [v for v in value if v not in (None, "", [])]
                if not cleaned_list:
                    continue  # skip empty list entirely
                value = cleaned_list

            if isinstance(value, dict) and not value:
                continue

            filtered[param] = value

        if filtered:
            result.append(filtered)

    return result


def create_portfolio_profile( 
    tenantID: int,
    userID: int,
    llm= None,
    model_opts2=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    **kwargs
):
    base_agent_service = BaseAgentService()
    sender = kwargs.get("steps_sender",None) or None
    try:
        # sender.sendSteps("Creating portfolio profile", False)

        portfolio_id = data.get("portfolio_id",{}) or {}
        portfolio_context = kwargs.get("portfolio_context",None) or None
        portfolio_info = PortfolioDao.getPortfolioNameById(portfolio_id=portfolio_id,tenant_id =tenantID)
        print("--debug info --------", portfolio_info, "\n\n--debug create_portfolio_profile for----", portfolio_id, "Tenant & user: ", tenantID,userID)

        if not portfolio_id:
            socketio.emit("portfolio_agent", {"event": "create_portfolio_profile", "data": "No portfolio info provided!", "portfolio_id": portfolio_id}, room=client_id)
            return
        # sender.sendSteps("Fetching customer context", False)
        
        context_ = get_consolidated_persona_context_utils(tenant_id=tenantID,user_id=userID)
        customer_context = context_.get("customer_info",{}) or {}
        technologies = context_.get("technologies",[]) or []
        strategic_priorities = context_.get("org_alignment",[]) or []
        portfolio_profile_inputs = {}

        if not portfolio_context: #see the project/roadmaps inside the portfolio
            applicable_projects = sorted(ProjectsDao.FetchAvailableProject(tenant_id=tenantID, user_id=userID))
            portfolio_projects = base_agent_service.fetchProjectsWithAttributesV2(
                portfolio=[portfolio_id],
                tenant_id = tenantID,
                applicable_projects=applicable_projects,
            )
            ongoing_projects = portfolio_projects.get("ongoing_projects",{}) or [{'portfolio_title': 'No portfolio'}]
            archived_projects = portfolio_projects.get("archived_projects",{}) or []
            future_projects = portfolio_projects.get("future_projects",{}) or [{'portfolio_title': 'No portfolio'}]

            print("--debug len of projects------", ongoing_projects[:1], "\nArchived: ", len(archived_projects), "\nFuture: ", future_projects[:1])
            portfolio_profile_inputs['portfolio_title'] = ongoing_projects[0].get("portfolio_title") or ongoing_projects[0].get("portfolio_title") or "Portfolio"
            portfolio_profile_inputs['ongoing_projects'] = portfolio_projects_info(ongoing_projects)
            portfolio_profile_inputs['archived_projects'] = portfolio_projects_info(archived_projects)
            portfolio_profile_inputs['future_projects'] = portfolio_projects_info(future_projects)
        else:
            portfolio_profile_inputs['trucible_context'] = portfolio_context
        

        # with open(f'portfolio_profile_{portfolio_id}_ip.json', 'w') as file:
        #     json.dump(portfolio_profile_inputs, file, indent=2)

        portfolio_profile_prompt = portfolio.portfolioProfilePrompt(
            customer_context = json.dumps(customer_context) or {},
            portfolio_info = json.dumps(portfolio_profile_inputs) or {},
            technologies = technologies,
            strategic_priorities = strategic_priorities,
        )
        # print("--debug portfolio_profile_prompt---------", portfolio_profile_prompt.formatAsString())
        # return

        # portfolio_profile_res = llm.run(portfolio_profile_prompt, model_opts2 , 'agent::create_portfolio', logInfo,socketio=socketio,client_id=client_id)

        portfolio_profile_res = llm.run_rl(portfolio_profile_prompt, model_opts2,'portfolio_agent','canvas::portfolio', logInDb=logInfo,socketio=socketio,client_id=client_id)
        response = extract_json_after_llm(portfolio_profile_res, step_sender = sender)
        # print("--debug portfolio profile response-------", response)

        # sender.sendSteps("Aligning OKR & KPI(s)", True)
        thought_process_behind_keyresults = response.get("thought_process_behind_keyresults","") or ""
        thought_process_behind_businessgoals = response.get('thought_process_behind_businessgoals',"") or ""
        thought_process_behind_techbudget = response.get("thought_process_behind_techbudget","") or ""
        thought_process_behind_strategicpriorities = response.get("thought_process_behind_strategicpriorities", "") or "" 
        
        response.pop('thought_process_behind_keyresults',None)
        response.pop('thought_process_behind_businessgoals',None)
        response.pop("thought_process_behind_techbudget",None)
        response.pop("thought_process_behind_strategicpriorities",None)

        new_tango_analysis = {
            "thought_process_behind_keyresults": thought_process_behind_keyresults,
            "thought_process_behind_businessgoals": thought_process_behind_businessgoals,
            "thought_process_behind_techbudget": thought_process_behind_techbudget,
            "thought_process_behind_strategicpriorities": thought_process_behind_strategicpriorities,
        }

        existing_tango_analysis = {}
        if len(portfolio_info) > 0:
            response["portfolio_name"] = portfolio_info[0].get("title")
            response["parent_id"] = portfolio_info[0].get("parent_id")
            existing_tango_analysis = portfolio_info[0].get("tango_analysis", {}) or {}

        if existing_tango_analysis:
            merged_tango_analysis = {**existing_tango_analysis, **new_tango_analysis}
            response["tango_analysis"] = merged_tango_analysis
        else:
            response["tango_analysis"] = new_tango_analysis

        # sender.sendSteps("Analyzing portfolio projects", True)

        it_leader = response.get("it_leader",{}) or {}
        tech_budget = response.get("tech_budget",{}) or {}
        business_leaders = response.get("business_leaders",[]) or []
        response.pop("it_leader",None)
        response.pop("tech_budget",None)
        response.pop("business_leaders",None)


        if tech_budget.get("value")==0 or len(tech_budget.get("start_date",""))<2 or len(tech_budget.get("end_date",""))<2:
            response["tech_budget"] = {"value": 0,"start_date": None,"end_date": None}
        else:    
            response["tech_budget"] = tech_budget

        name = it_leader.get("name", "") or None
        response["it_leader"] = {
            "first_name": name.split(' ')[0] if name else "",
            "last_name": " ".join(name.split(" ")[1:]) if name else "",
            "role": it_leader.get("role", "") or "",
            "email": it_leader.get("email", "") or ""
        }

        business_leaders_ = []
        if business_leaders:
            for leader in business_leaders:
                name = leader.get("name", "") or None
                if name:
                    business_leaders_.append({
                    "sponsor_first_name": name.split(' ')[0],
                    "sponsor_last_name": " ".join(name.split(" ")[1:]) or "",
                    "sponsor_role": leader.get("role", "") or None,
                    })
        response["business_leaders"] = business_leaders_

        print("\n\n --[[PORTFOLIO]] create_portfolio final 111111111========", response)


        # sender.sendSteps("Creating portfolio profile", True)
        socketio.emit("portfolio_agent", {"event": "create_portfolio_profile", "data": response, "portfolio_id": portfolio_id}, room=client_id)

        return
    except Exception as e:
        sender.safe_send_error(key = "Error creating portfolio profile!", function="create_portfolio_profile")
        appLogger.error({"event": "create_portfolio_profile", "error": str(e), "traceback": traceback.format_exc()})
    return 


def create_portfolio_profile_fxn(
    tenantID: int,
    userID: int,
    llm= None,
    model_opts2=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    **kwargs
):  
    stop_event = threading.Event()
    sender = kwargs.get("steps_sender",None) or None
    portfolio_id = data.get("portfolio_id",None) or None
    
    portfolio_context = get_tenant_portfoliocontext(tenant_id=tenantID,portfolio_ids=[portfolio_id])
    stages = ["Fetching customer context","Aligning OKR & KPI(s)"]
    if portfolio_context:
        stages.append("Extracting portfolio context")
    else:
        stages.append("Analyzing portfolio projects")
    kwargs.update({'portfolio_context': portfolio_context})

    socketio.start_background_task(
        send_timeline_updates,
        socketio,client_id,stop_event,
        agent_name="portfolio_agent",interval = 4,
        stages = stages,
        # stages = ["Fetching customer context","Analyzing portfolio projects","Aligning OKR & KPI(s)"],
    )



    def portfolio_profile_job():
        try:
            #Additional stage before the LLM call
            socketio.sleep(seconds=4)
            emit_event("portfolio_agent",timeline_event("Creating portfolio profile🚀", "timeline", False),socketio,client_id)
            create_portfolio_profile(
                tenantID=tenantID,
                userID=userID,
                llm=llm,
                model_opts2=model_opts2,
                socketio=socketio,
                client_id=client_id,
                logInfo=logInfo,
                data = data,
                **kwargs
            )

            emit_event("portfolio_agent",timeline_event("Creating portfolio profile🚀", "timeline", True), socketio,client_id)
        except Exception as e:
            appLogger.error({"event": "portfolio_profile_fxn_error","error": str(e),"traceback": traceback.format_exc()})
            sender.sendError(key=f"Error in portfolio profile thread",function="portfolio_profile_fxn")
        finally:
            # Stop timeline updates once allocation is complete
            stop_event.set()
            appLogger.info({"event": "create_portfolio_profile_fxn","status": "portfolio_profile_job_completed","portfolio_id":portfolio_id})

    # Launch the allocator safely in background
    socketio.start_background_task(portfolio_profile_job)

    print("--result", {"status": "portfolio_profile_job: started", "portfolio_id": portfolio_id})
    return
    



PORTFOLIO_PROFILE = AgentFunction(
    name="create_portfolio_profile",
    description="This function is used to create profile of the existing portfolio(s) from the projects within it: Ongoing,closed & archived.",
    args=[],
    return_description="",
    function=create_portfolio_profile_fxn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)







def format_output(output):
    del output["ui_instructions"]
    del output["your_thought"]
    return output

def create_portfolio(
    tenantID: int,
    userID: int,
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    last_user_message=None,
    sessionID=None,
    **kwargs
):
    print(
        "debug -- create_portfolio ", 
        tenantID, 
        userID,
        last_user_message, 
        sessionID
    )
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="create_portfolio_conv", 
            value=last_user_message, 
            session_id=sessionID
        )
        # (user_id=userID, key="create_portfolio_conv")
        


    # ###### check what conv has happened.
    # # create prompt for showing UI 
    conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id=sessionID, user_id=userID, key="create_portfolio_conv")
    print("--- conv ")
    prompt = portfolio.create_portfolio_prompt(conv)
    print("--prompt", prompt.formatAsString())
    response = llm.run(prompt, model_opts , 'agent::create_portfolio', logInfo)
    response = extract_json_after_llm(response)
    print("create_portfolio ========", response)
    
    result = ''
    TangoDao.insertTangoState(
        tenant_id=tenantID, 
        user_id=userID,
        key="create_portfolio_conv", 
        value=str(response), 
        session_id=sessionID
    )
    
    socketio.emit("show_ui", {"item": "create_portfolio"}, room=client_id)
    socketio.emit("show_agent_bot", None, room=client_id)
    
    
    if len(conv) == 1:
        # socketio.emit("tango_agent_response", f"Lets get Started. :)", room=client_id)
        socketio.emit("agent_controlled_ui", response, room=client_id)
        socketio.emit("change_agent_width", {"width": 640}, room=client_id)
        return format_output(response)
    
    # socketio.emit("tango_agent_response", response, room=client_id)
    socketio.emit("change_agent_width", {"width": 640}, room=client_id)
    socketio.emit("agent_controlled_ui", response, room=client_id)
    return format_output(response)
        
    

    

RETURN_DESCRIPTION = """
    This function is responsible to render the UI for create project
"""

ARGUMENTS = []

CREATE_PORTFOLIO = AgentFunction(
    name="create_portfolio",
    description="""
        This function is brilliantly created to show the update staus UI whenever user wants to update project status
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=create_portfolio,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)