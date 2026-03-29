from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction, AgentReturnTypes
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_services.agents.apis.service_assurance import ServiceAssuranceApis
from src.trmeric_utils.constants.project_status import PROJECT_STATUS_TYPE_TO_CODE, PROJECT_STATUS_VALUE_TO_CODE
from src.trmeric_database.dao import ProjectsDao, KnowledgeDao, TangoDao
import datetime
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import get_jira_data
from src.trmeric_services.agents.precache import ServiceAssurancePrecache
from src.trmeric_services.agents.prompts.agents import create_high_level_analysis_prompt, troubleshoot_service_assurnace_prompt
from src.trmeric_services.tango.types.TangoYield import TangoYield
import time
import json
from src.trmeric_services.agents.notify.prompts import *
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.web.WebSearchAgent import WebSearchAgent
from src.trmeric_utils.html_formatter import *



def service_assurance_troubleshoot(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    last_user_message=None,
    project_ids=[],
    sessionID=None,
    logInfo=None,
    **kwargs
):
    print("debug service_assurance_troubleshoot ---- ")
    project_selected_key = "service_assurance_troubleshoot_project_selected"
    shown_project_list_key = "service_assurance_troubleshoot_shown_project_list"
    shown_project_list = len(TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=shown_project_list_key)) > 0

    shown_ui_key = "service_assurance_troubleshoot_shown_ui"
    
    projects = ProjectsDao.FetchProjectNamesForIds(_project_ids=eligibleProjects)
    project_selected_items = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=project_selected_key)
    project_selected = -1
    if len(project_selected_items) > 0:
        project_selected = int(project_selected_items[0]["value"])
    else:
        if len(project_ids) == 1:
            TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key=project_selected_key, value=project_ids[0], session_id=sessionID)
        else:
            ## send project list
            cta_buttons = []
            for project in projects:
                button = {
                    "label": project["project_title"],  # Using project_title as the button label
                }
                cta_buttons.append(button)

            yield "Select any one of these projects for troubleshoot"
            data_string = f"""
```json
    {{
        "cta_buttons": {json.dumps(cta_buttons)}
    }}
```
            """
            yield data_string
            return
            # return data_string
    
        
    project_selected_items = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=project_selected_key)
    if len(project_selected_items) > 0:
        project_selected = int(project_selected_items[0]["value"])
        
        
    def showUIData(project_selected, sessionID, userID, ui_data_key, tenantID):
        print("getting triggered----- showUIData", project_selected)
        ui_data_key = f"S_A_ANALYSIS_{project_selected}"
        print("getting triggered----- showUIData 2", ui_data_key)
        show_ui_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=ui_data_key)
        socketio.emit("service_assurance_troubleshoot_agent", 
            {
                "event": "insight_data",
                "data": show_ui_data[0]["value"]
            }, 
            room=client_id
        )
        TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key=shown_ui_key, value="", session_id=sessionID)
        yield "✅ Detailed insight triggered"
        return
    
        
    ui_data_key = f"S_A_ANALYSIS_{project_selected}"
    web_sources = f"WEB_ANALYSIS_{project_selected}"
        
        
    socketio.emit("spend_agent", 
        {
            "event": "show_timeline",
        }, 
        room=client_id
    )

    socketio.emit("spend_agent", 
        {
            "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": False}
        }, 
        room=client_id
    )
    
    already_analysed_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=ui_data_key)
    decider_web_search = True
    
    project_details = ProjectsDao.fetch_project_details_for_service_assurance(
        project_id=project_selected
    )[0]
    project_statuses = ProjectsDao.fetchProjectStatuses(project_id=project_selected)
    project_details["status"]= project_statuses
    
    project_basic_data = ProjectsDao.fetchBasicInfoForServiceAssuranceNotifyAgent(project_id=project_selected)
    if len(already_analysed_data) > 0:
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Deciding if web search needed", "key": "Deciding if web search needed", "is_completed": False}
            }, 
            room=client_id
        )
        
        classify_prompt = web_search_decider_prompt(project_basic_data, analysis_data=already_analysed_data, last_user_message=last_user_message)
        classify_response = llm.run(
            classify_prompt,
            options=model_opts,
            function_name="ServiceAssuranceNotificationAnalyst::web_search_decider_prompt",
            logInDb=logInfo
        )
        classification_result = extract_json_after_llm(classify_response)
        need_web_search_again = classification_result.get("need_web_search_again", False) or False
        decider_web_search = need_web_search_again
        print("debug need_web_search_again-- ", need_web_search_again, classify_response)
        search_results = already_analysed_data[0]
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Deciding if web search needed", "key": "Deciding if web search needed", "is_completed": True}
            }, 
            room=client_id
        )
        
    if decider_web_search:
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Finding Project Type", "key": "Finding Project Type", "is_completed": False}
            }, 
            room=client_id
        )
        
        classify_prompt = create_classification_prompt(project_basic_data, last_user_message)
        classify_response = llm.run(
            classify_prompt,
            options=model_opts,
            function_name="ServiceAssuranceNotificationAnalyst::classifyProject",
            logInDb=logInfo
        )
        classification_result = extract_json_after_llm(classify_response)
        project_type = classification_result.get("project_type", "unknown")
        print("debug -- ", classify_response)
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Finding Project Type", "key": "Finding Project Type", "is_completed": True}
            }, 
            room=client_id
        )
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Determine WebSearch Sources", "key": "Determine WebSearch Sources", "is_completed": False}
            }, 
            room=client_id
        )

        websearch_agent = WebSearchAgent()
        already_pulled_sources = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=web_sources)
        
        web_search_prompt = create_web_source_finder(project_data=project_details, project_type=project_type, last_user_message=last_user_message)
        web_search_response = llm.run(
            web_search_prompt,
            options=model_opts,
            function_name="ServiceAssuranceNotificationAnalyst::web_search",
            logInDb=logInfo
        )
        print("web_search_response", web_search_response)
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Determine WebSearch Sources", "key": "Determine WebSearch Sources", "is_completed": True}
            }, 
            room=client_id
        )
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Searching Web", "key": "Searching Web", "is_completed": False}
            }, 
            room=client_id
        )
        web_search_response = extract_json_after_llm(web_search_response)
        web_search_queries = web_search_response.get("relevant_sources", []) or []
        web_search_queries = web_search_queries[:3]
        search_results = [websearch_agent.query_search_engine(query, skip_source=True) for query in web_search_queries]
        
        TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key=web_sources, value=json.dumps(search_results), session_id=sessionID)
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Searching Web", "key": "Searching Web", "is_completed": True}
            }, 
            room=client_id
        )
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Enriching Data", "key": "Enriching Data", "is_completed": False}
            }, 
            room=client_id
        )
        
        prompt = create_insight_and_action_prompt_v2(
            project_data=project_details, 
            web_queries=web_search_queries,
            web_insights_data=search_results,
            project_type=project_type,
            insight_v1=already_analysed_data
        )
        print("debug prompt -- ", prompt.formatAsString())
        
        response = llm.run(
            prompt,
            options=model_opts,
            function_name="ServiceAssuranceNotificationAnalyst::create_data",
            logInDb=logInfo
        )
        print("debug prompt -- response create_data")
        print(response)
        clean_res = clean_html(html_content=response)
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Enriching Data", "key": "Enriching Data", "is_completed": True}
            }, 
            room=client_id
        )
        TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key=ui_data_key, value=clean_res, session_id=sessionID)


    ui_data_key = f"S_A_ANALYSIS_{project_selected}"
    print("getting triggered----- showUIData 2", ui_data_key)
    show_ui_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=ui_data_key)
    socketio.emit("service_assurance_troubleshoot_agent", 
        {
            "event": "insight_data",
            "data": show_ui_data[0]["value"]
        }, 
        room=client_id
    )
    
    yield "✅ Detailed insight triggered"
    shown_ui = len(TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=shown_ui_key)) > 0
    
    
    TangoDao.insertTangoState(tenant_id=tenantID, user_id=userID, key=shown_ui_key, value="", session_id=sessionID)
    
    if shown_ui:
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": True}
            }, 
            room=client_id
        )

        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Analysing", "key": "Analysing", "is_completed": False}
            }, 
            room=client_id
        )
        
        
        
        project_data = ProjectsDao.fetch_project_details_for_service_assurance(
            project_id=project_selected
        )[0]
        
        ui_data_key = f"S_A_ANALYSIS_{project_selected}"
        show_ui_data = TangoDao.fetchTangoStatesForUserIdbyKey(user_id=userID, key=ui_data_key)
        
        prompt = troubleshoot_service_assurnace_prompt(project_data=project_data, data=show_ui_data, user_query=last_user_message)
        print("debug -- prompt", prompt.formatAsString())
        analysis = ""
        for chunk in llm.run(prompt, model_opts , 'agent::service_assurance::analyst', logInfo):
            analysis += chunk
            yield chunk
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Analysing", "key": "Analysing", "is_completed": True}
            }, 
            room=client_id
        )
        
        
        # time.sleep(1)
        
    socketio.emit("spend_agent", 
        {
            "event": "stop_show_timeline",
        }, 
        room=client_id
    )
    return ""
    
        
    

RETURN_DESCRIPTION = """
    A detailed list of projects with updates, milestone statuses, and identified risks or successes. 
    Supplemental insights from the knowledge layer and integrations, if applicable.
"""

ARGUMENTS = [
    {
        "name": "project_ids",
        "type": "int[]",
        "required": 'true',
        "description": """Project Ids that user wants troubleshooting on, either all projects or specific project""",
    },
]

SERVICE_ASSURANCE_TROUBLESHOOT = AgentFunction(
    name="service_assurance_troubleshoot",
    description="""
        
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=service_assurance_troubleshoot,
    return_type=AgentReturnTypes.YIELD.name,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)
