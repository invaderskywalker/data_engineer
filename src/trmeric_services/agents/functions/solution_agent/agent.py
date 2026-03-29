from typing import List, Any
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from .controller import SolutionAgent
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes


def solution_from_template_create(tenantID: int, userID: int, socketio: Any = None, client_id: str = None, sessionID: str = None, **kwargs) -> List[str]:
    try:
        # Extract kwargs
        sender = kwargs.get("steps_sender") or None
        data = kwargs.get("data")
        roadmap_id = data.get("roadmap_id")
        log_info = kwargs.get("logInfo")
        llm = kwargs.get("llm")
        sessionID = data.get("session_id")
        file_id = data.get("file_id")
        mode = data.get("mode")

        print("debug --business_case_from_template_create ", roadmap_id, log_info, llm, sessionID)

        if not (roadmap_id):
            raise ValueError("roadmap_id  must be provided")

        business_case_ids = []
        agent = SolutionAgent(tenant_id=tenantID, user_id=userID, roadmap_id=roadmap_id, socketio=socketio, client_id=client_id, session_id=sessionID, log_info=log_info, llm=llm, mode=mode)
        agent.create_scope_and_resources_data(file_id,sender=sender)

    except Exception as e:
        sender.sendError(key="Error creating business case",function="business_case_from_template_create")
        appLogger.error({"event": "business_case_from_template_create failed", "error": str(e), "traceback": traceback.format_exc()})
        return []
    
    
def solution_create_for_roadmap(tenantID: int, userID: int, socketio: Any = None, client_id: str = None, sessionID: str = None, **kwargs) -> List[str]:
    try:
        # Extract kwargs
        sender = kwargs.get("steps_sender") or None
        data = kwargs.get("data")
        roadmap_id = data.get("roadmap_id")
        log_info = kwargs.get("logInfo")
        llm = kwargs.get("llm")
        sessionID = data.get("session_id")
        file_id = data.get("file_id")
        mode = data.get("mode")

        print("debug --business_case_from_template_create ", roadmap_id, log_info, llm, sessionID)

        if not (roadmap_id):
            raise ValueError("roadmap_id  must be provided")

        agent = SolutionAgent(tenant_id=tenantID, user_id=userID, roadmap_id=roadmap_id, socketio=socketio, client_id=client_id, session_id=sessionID, log_info=log_info, llm=llm, mode=mode)
        agent.create_solution_from_roadmap_data(sender=sender)

    except Exception as e:
        sender.sendError(key="Error creating business case",function="business_case_from_template_create")
        appLogger.error({"event": "business_case_from_template_create failed", "error": str(e), "traceback": traceback.format_exc()})
        return []



CREATE_ROADMAP_SOLUTION = AgentFunction(
    name="solution_create_for_roadmap",
    description="""This function is used to create the HLD solution for a roadmap from scratch and also from the stored templates.""",
    args=[],
    return_description="",
    function=solution_create_for_roadmap,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)


CREATE_SOLUTION_FROM_TEMPLATE = AgentFunction(
    name="solution_from_template_create",
    description="""This function is used to create the HLD solution from the uploaded file as templates.""",
    args=[],
    return_description="",
    function=solution_from_template_create,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

