import os
import re
import json
import datetime
import threading
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.prompts.agents import resource_planning_agent
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes,AgentReturnTypes
from src.trmeric_services.agents.functions.utility.socketio import emit_event,timeline_event,send_timeline_updates,end_event
from .utils import parse_resource_recommendataion,group_resources_hierarchically,resource_allocator_context


def resource_allocator(
    tenantID=None,
    userID=None,
    llm=None,
    model_opts=None,
    logInfo=None,
    socketio=None,
    client_id=None,
    sessionID=None,
    **kwargs
):
    """
    Responsible for resource allocation for the project based on:
    1. SocketIO response from frontend (finalized roles selected by user)
    2. Capacity_resource table in db (fetched team data) to allocate people to the project
    """
    data = kwargs.get("data", {})
    sessionID = kwargs.get("sessionID", None)
    sender = kwargs.get("steps_sender",None) or None
    
    team_id = data.get('team_id', None)
    project_id = data.get('project_id', None)
    suggested_roles = data.get('suggested_roles', None)
    model_opts = ModelOptions(model="gpt-4.1", max_tokens=20384, temperature=0)
    
    print("--debug model_opts---", model_opts.model, model_opts.max_tokens)
    print("---debug inside resource_allocator---------", tenantID, userID, project_id, team_id)
    
    TangoDao.upsertTangoState(
        tenant_id=tenantID, 
        user_id=userID,
        key=f"resource_allocator_{project_id}_{team_id}", 
        value=json.dumps(suggested_roles), 
        session_id=sessionID
    )
    
    try:
        project_id_in_conv = project_id
        team_id_in_conv = team_id
                
        context = resource_allocator_context(
            tenant_id=tenantID,
            session_id=sessionID,
            user_id=userID,
            project_id=project_id_in_conv,
            team_id=team_id_in_conv
        )
        resources = context.get("resources", {}) or {}
        project_details = context.get("project_details", {}) or {}
        selected_roles = context.get("selected_roles", []) or json.dumps(suggested_roles)
        portfolio_orgteam_mapping = context.get("portfolio_orgteam_mapping", {}) or {}
        
        print("\n--debug mapping----------", portfolio_orgteam_mapping)
        appLogger.info({"event": "resource_allocator", "status": "context_fetched", "project_id": project_id_in_conv, "team_id": team_id_in_conv, "tenant_id": tenantID})
        
        
        internal_resources = group_resources_hierarchically(resources["internal_resources"], tenant_id=tenantID)
        provider_resources = group_resources_hierarchically(resources["provider_resources"], tenant_id=tenantID, is_external=True)
        print("--debug grouped resources: Internal", len(internal_resources), "\nProvider: ", len(provider_resources))

        prompt = resource_planning_agent.allocate_project_resources_prompt(
            suggested_roles=json.dumps(selected_roles),
            project_details=json.dumps(project_details),
            portfolio_org_teams_map=json.dumps(portfolio_orgteam_mapping),
            internal_resources=json.dumps(internal_resources),
            provider_resources=json.dumps(provider_resources)
        )
        # print("--debug allocator------", prompt.formatAsString())
        # return
        
        # response = llm.run(prompt, model_opts, 'agent::resource_planning_agent', logInfo, socketio=socketio, client_id=client_id)
        response = llm.run_rl(chat = prompt, options = model_opts,
            agent_name = 'resource_planning_agent',function_name = 'resource_allocator::resource_allocator',
            logInDb= logInfo,socketio=socketio,client_id=client_id
        )        
        finalized_resources = extract_json_after_llm(response, step_sender=sender)
        print("--debug finalized resources", finalized_resources.get("provider_employees", [])[:2])
        
        finalized_resources = parse_resource_recommendataion(data=finalized_resources) 
        emit_event("capacity_planner", {"event": "allocator", "data": finalized_resources, "project_id": project_id_in_conv, "team_id": team_id_in_conv}, socketio, client_id)
        emit_event("capacity_planner", end_event("capacity_planner_ended", "project_id", project_id_in_conv, "team_id", team_id_in_conv), socketio, client_id)
        
        appLogger.info({"event": "resource_allocator", "status": "completed", "project_id": project_id_in_conv, "team_id": team_id_in_conv, "tenant_id": tenantID})
    
    except Exception as e:
        print("--debug error in resource_allocator", e)
        sender.sendError(key=f"Error in resource_allocator: {str(e)}", function="resource_allocator")
        appLogger.error({"event": "resource_allocator", "error": str(e), "traceback": traceback.format_exc()})

    return 


def resource_allocator_fxn(
    tenantID=None,
    userID=None,
    llm=None,
    model_opts=None,
    logInfo=None,
    socketio=None,
    client_id=None,
    sessionID=None,
    steps_sender=None,
    **kwargs
):
    """
    Orchestrates background resource allocation with a parallel timeline updater.
    Runs fully asynchronously and safely ends background threads.
    """
    data = kwargs.get("data", {}) or {}
    project_id = data.get("project_id")
    team_id = data.get("team_id")

    # Define stop signal for timeline updates
    stop_event = threading.Event()

    # Launch timeline updater as a background SocketIO task
    socketio.start_background_task(
        send_timeline_updates,
        socketio, client_id, stop_event,
        agent_name = "capacity_planner", interval=8,
        stages=["Fetching the resources", "Gathering project data", "Matching organization teams","Resource agent in action"],
        project_id = project_id, team_id=team_id
    )

    def allocator_job():
        """Inner function to wrap the allocator call safely and ensure stop_event is signaled at completion or error."""

        try:
            #Additional stage before the LLM call
            socketio.sleep(seconds=4)
            emit_event(
                "capacity_planner",timeline_event("Crafting your ideal team🚀", "timeline", False, "project_id", project_id, "team_id", team_id),
                socketio,client_id
            )
            resource_allocator(
                tenantID=tenantID,
                userID=userID,
                llm=llm,
                model_opts=model_opts,
                logInfo=logInfo,
                socketio=socketio,
                client_id=client_id,
                sessionID=sessionID,
                steps_sender=steps_sender,
                **kwargs
            )

            emit_event(
                "capacity_planner",timeline_event("Crafting your ideal team🚀", "timeline", True, "project_id", project_id, "team_id", team_id),
                socketio,client_id
            )
        except Exception as e:
            appLogger.error({"event": "resource_allocator_fxn_error","error": str(e),"traceback": traceback.format_exc()})
            steps_sender.sendError(key=f"Error in allocator thread: {str(e)}",function="resource_allocator_fxn")
        finally:
            # Stop timeline updates once allocation is complete
            stop_event.set()
            appLogger.info({"event": "resource_allocator_fxn","status": "allocator_completed","project_id": project_id,"team_id": team_id})

    # Launch the allocator safely in background
    socketio.start_background_task(allocator_job)

    print("--result", {"status": "started", "project_id": project_id, "team_id": team_id})
    return





RESOURCE_ALLOCATOR = AgentFunction(
    name="resource_allocator",
    description="""
        This function is responsible for allocation of the resources for the project and will be used **only after capacity_planner** once the roles are selected.
        It will return the description of the people who are most suitable for the role, their bandwidth, timeline, schedule etc. 
        as required to do the project.
    """,
    args=[],
    return_description="""
    This function is responsible for resource allocation for the projects created in the platform based on roles.""",
    function=resource_allocator_fxn,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)




    







