import os
import re
import json
import datetime
import traceback
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.prompts.agents import resource_planning_agent
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes
from src.trmeric_services.agents.functions.utility.socketio import emit_event,timeline_event,start_show_timeline,stop_show_timeline,end_event
from .utils import capacity_planner_context

def timeline_payload(is_completed: bool,id1, id1_val,id2, id2_val):
    return [
        timeline_event("Synthesizing scope","timeline",is_completed,id1,id1_val,id2, id2_val),
        timeline_event("Synthesizing technology","timeline",is_completed,id1,id1_val,id2, id2_val),
        timeline_event("Synthesizing budget","timeline",is_completed,id1,id1_val,id2, id2_val),
        timeline_event("Synthesizing timelines","timeline",is_completed,id1,id1_val,id2, id2_val),
    ]
    

def capacity_planner( 
    tenantID =None,
    userID =None,
    llm =None,
    model_opts =None,
    logInfo =None,
    socketio=None,
    client_id=None,
    project_id=None,
    team_id= None ,
    **kwargs
):

    """Build the capacity planner for the project """
    data = kwargs.get("data",{})
    project_id = data.get('project_id', None)
    team_id = data.get('team_id', None)

    print("---debug inside capacity_planner---------",tenantID,userID, project_id, team_id)
    try:
        sender = kwargs.get("steps_sender") or None 
        
        project_id_in_conv = project_id
        team_id_in_conv = team_id
        print("--debug in conv", project_id_in_conv,team_id_in_conv)        
        
        model_opts = ModelOptions(model="gpt-4.1",max_tokens=15000,temperature=0.1)
        
        emit_event("capacity_planner",[
            timeline_event("Synthesizing scope","timeline",False,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
            timeline_event("Synthesizing budget","timeline",False,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
            timeline_event("Synthesizing technology","timeline",False,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
        ],socketio,client_id)
                
        context = capacity_planner_context(tenant_id=tenantID,project_id=project_id_in_conv)
        project_details = context.get("project_context",{}) or {}
        roadmap_context = context.get("roadmap_context",{}) or {}
        print("--debug project details", project_details, "\n\nAttached roadmap: ", roadmap_context)

        appLogger.info({"event":"capacity_planner","status":"context_fetched","project_id":project_id_in_conv,"team_id":team_id_in_conv,"tenant_id":tenantID})
        # print("--debug project details", project_details)
        project_start_date, project_end_date = project_details.get("start_date",""), project_details.get("end_date","")
        # print("\n--debug project dates", project_start_date, " ", project_end_date)        
        
        tenant_config_res = context.get("tenant_config",None) or None
        
        tenant_formats = {}
        if tenant_config_res is not None:
            tenant_formats["currency_format"] = tenant_config_res.get("currency",{})
            tenant_formats["date_format"] = tenant_config_res.get("date_time",{})
        appLogger.info({"event":"tenant_config", "data": tenant_formats,"tenant_id":tenantID})
        # print("\n\n--debug tenant_config_res---", tenant_config_res, '\n',tenant_formats)
        
        # print("--debug project dates", project_start_date, project_end_date)
        emit_event("capacity_planner",[
            timeline_event("Synthesizing scope","timeline",True,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
            timeline_event("Synthesizing budget","timeline",True,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
            timeline_event("Synthesizing technology","timeline",True,"project_id", project_id_in_conv,"team_id", team_id_in_conv),
            ],
        socketio,client_id)

        if project_start_date and project_end_date:
            
            emit_event("capacity_planner",  timeline_event("Synthesizing timelines","timeline",False,"project_id", project_id_in_conv,"team_id", team_id_in_conv),socketio,client_id )
            socketio.sleep(seconds = 3)
            emit_event("capacity_planner",  timeline_event("Resource agent in action","timeline",False,"project_id", project_id_in_conv,"team_id", team_id_in_conv),socketio,client_id )
            
            prompt = resource_planning_agent.suggest_project_role_prompt(
                project_details = json.dumps(project_details,indent=2),
                data_format=tenant_formats.get("currency_format",None),
                inherited_roadmap = json.dumps(roadmap_context,indent=2)
            )
            # print("--planner", prompt.formatAsString())
            # return
            # response = llm.run(prompt, model_opts , 'agent::resource_planning_agent', logInfo)
            response = llm.run_rl(chat = prompt,options = model_opts,
                agent_name = 'resource_planning_agent',function_name = 'capacity_planner::capacity_planner',
                logInDb= logInfo,socketio=socketio,client_id=client_id
            )
            
            # print("--debug capacity_planner-----------", response)
            response = extract_json_after_llm(response,step_sender=sender)
            
            emit_event("capacity_planner",{"event": "planner","data": response,"project_id": project_id_in_conv,"team_id": team_id_in_conv},socketio,client_id)
            emit_event("capacity_planner",  timeline_event("Synthesizing timelines","timeline",True,"project_id", project_id_in_conv,"team_id", team_id_in_conv),socketio,client_id )
            
            emit_event("capacity_planner",  timeline_event("Resource agent in action","timeline",True,"project_id", project_id_in_conv,"team_id", team_id_in_conv),socketio,client_id )
        else:
            appLogger.info({"event":"capacity_planner","status":"invalid project dates","data":{project_start_date, project_end_date},"project_id":project_id_in_conv,"team_id":team_id_in_conv,"tenant_id":tenantID})
            emit_event("capacity_planner",{
                    "event": "planner",
                    "data": {"recommended_project_roles": []},
                    "message":f"Project start date: {project_start_date} and end date: {project_end_date} are not available.", 
                    "project_id": project_id_in_conv,
                    "team_id": team_id_in_conv
                },
                socketio,client_id
            )
            
        appLogger.info({"event":"capacity_planner","status":"completed","project_id":project_id_in_conv,"team_id":team_id_in_conv,"tenant_id":tenantID})

    except Exception as e:
        print("--debug error in capacity_planner",e)
        sender.sendError(key=f"Error in capacity_planner",function="capacity_planner")
        appLogger.error({
            "event": "capacity_planner",
            "error": e,
            "traceback": traceback.format_exc()
        })



CAPACITY_PLANNER = AgentFunction(
    name="capacity_planner",
    description="""
        This function is responsible for capacity planner for the project.
        It will return all the roles, their duration and allocation percentage (monthwise) which will be required throughout the project.
    """,
    args=[],
    return_description="""This function is responsible for creating the capacity planner of the project""",
    function=capacity_planner,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)

