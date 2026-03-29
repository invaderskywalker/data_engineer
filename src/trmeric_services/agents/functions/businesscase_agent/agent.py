from typing import List, Any
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from .controller import BusinessTemplateAgent  # Adjust import path as needed
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes

def business_case_from_template_create(tenantID: int, userID: int, socketio: Any = None, client_id: str = None, sessionID: str = None, **kwargs) -> List[str]:
    """
    Create business cases for roadmaps using a specified template file.

    Args:
        tenantID (int): Tenant identifier.
        userID (int): User identifier.
        socketio (Any, optional): SocketIO instance for real-time communication.
        client_id (str, optional): Client identifier for SocketIO.
        sessionID (str, optional): Session identifier for file tracking.
        **kwargs: Additional arguments including:
            - roadmap_id (int, optional): Single roadmap ID to process.
            - portfolio_ids (List[int], optional): List of portfolio IDs to fetch roadmaps.
            - template_file_id (str): S3 key of the template file.
            - log_info (Any, optional): Logging information for LLM.

    Returns:
        List[str]: List of identifiers for the generated business cases (e.g., roadmap IDs or unique case IDs).
    """
    try:
        # Extract kwargs
        data = kwargs.get("data")
        roadmap_id = data.get("roadmap_id")
        idea_id = data.get("idea_id",None)
        log_info = kwargs.get("logInfo")
        llm = kwargs.get("llm")
        sessionID = data.get("session_id")
        file_id = data.get("file_id")
        mode = data.get("mode")
        sender = kwargs.get("steps_sender") or None

        print("debug --business_case_from_template_create ", roadmap_id, log_info, llm, sessionID)
        entity_id = roadmap_id or idea_id or None
        entity = "roadmap" if roadmap_id else "idea"
        if not (entity_id):
            raise ValueError(f"{entity_id} must be provided")

        business_case_ids = []
        agent = BusinessTemplateAgent(tenant_id=tenantID, user_id=userID, entity_id=entity_id,entity=entity, socketio=socketio, client_id=client_id, session_id=sessionID, log_info=log_info, llm=llm, mode=mode,sender=sender)
        agent.create_business_case(file_id)

    except Exception as e:
        appLogger.error({"event": "business_case_from_template_create failed", "error": str(e), "traceback": traceback.format_exc()})
        return []


def retrigger_financial(tenantID: int, userID: int, socketio: Any = None, client_id: str = None, sessionID: str = None, **kwargs) -> List[str]:
    try:
        data = kwargs.get("data")
        roadmap_id = data.get("roadmap_id")
        log_info = kwargs.get("logInfo")
        llm = kwargs.get("llm")
        sessionID = data.get("session_id")
        mode = data.get("mode")
        sender = kwargs.get("steps_sender") or None

        print("debug --retrigger_financial ", roadmap_id, log_info, llm, sessionID)

        if not (roadmap_id):
            raise ValueError("roadmap_id  must be provided")

        business_case_ids = []
        agent = BusinessTemplateAgent(tenant_id=tenantID, user_id=userID, entity_id=roadmap_id, socketio=socketio, client_id=client_id, session_id=sessionID, log_info=log_info, llm=llm, mode=mode,sender=sender)
        agent.retriggerFinancialCalculations()

    except Exception as e:
        appLogger.error({"event": "business_case_from_template_create failed", "error": str(e), "traceback": traceback.format_exc()})
        return []



CREATE_BUSINESSCASE_FROM_TEMPLATE = AgentFunction(
    name="business_case_from_template_create",
    description="",
    args=[],
    return_description='',
    function=business_case_from_template_create,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

RETRIGGER_FINANCIAL = AgentFunction(
    name="retrigger_financial",
    description="",
    args=[],
    return_description='',
    function=retrigger_financial,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)