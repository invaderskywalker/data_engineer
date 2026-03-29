from typing import List, Dict, Any
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import traceback
from src.trmeric_database.Database import db_instance
from datetime import datetime
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes


def update_idea_portfolio_ranks_fn(
    # tenant_id: int,
    # user_id: int,
    tenantID: int = None,
    userID: int = None,
    data: List[Dict[str, Any]] = None,
    # session_id: str = None,
    socketio: Any = None,
    client_id: str = None,
    **kwargs
) -> List[str]:
    """
    Update portfolio rank in idea_conceptportfolio table for an array of ideas.

    Args:
        tenant_id: Tenant ID.
        user_id: User ID performing the operation.
        data: List of dicts with id, portfolio_id, and priority.
        session_id: Session ID for tracking.
        socketio: SocketIO instance for feedback.
        client_id: Client ID for socket room.

    Returns:
        List of results or errors.
    """
    try:
        user_id = userID
        tenant_id = tenantID
        sender = kwargs.get("step_sender") or None
        debugLogger.info(f"Updating idea portfolio ranks for tenant_id: {tenant_id}, {len(data)} ideas")

        # Get max and min rank across all ideas for reference
        rank_query = f"SELECT id, rank FROM idea_concept WHERE tenant_id = {tenant_id};"
        all_ideas = db_instance.retrieveSQLQueryOld(rank_query)

        max_rank, min_rank = 0, 99
        for idea in all_ideas:
            rank = idea.get("rank", 0) or 0
            if rank > max_rank:
                max_rank = rank
            if rank != 0 and rank < min_rank:
                min_rank = rank

        if min_rank == 99 or min_rank == 1:
            min_rank = 0

        debugLogger.info(f"Max rank identified for tenant {tenant_id}: max={max_rank}, min={min_rank}")

        # Update each idea’s portfolio rank
        for _data in data:
            required_fields = ["id", "portfolio_id", "priority"]
            missing_fields = [f for f in required_fields if f not in _data]
            if missing_fields:
                appLogger.error({
                    "event": "Idea portfolio rank update failed",
                    "error": f"Missing required fields: {missing_fields}"
                })
                continue

            idea_id = _data["id"]
            portfolio_id = _data["portfolio_id"]
            portfolio_rank = _data["priority"]

            if not isinstance(portfolio_rank, int):
                appLogger.error({
                    "event": "Idea portfolio rank update failed",
                    "error": f"Rank must be integer for idea {idea_id}"
                })
                continue

            # Update the rank in idea_conceptportfolio
            update_query = """
                UPDATE idea_concept
                SET portfolio_rank = %s
                WHERE id = %s;
            """
            db_instance.executeSQLQuery(update_query, (portfolio_rank, idea_id))
            debugLogger.info(f"Updated portfolio rank {portfolio_rank} for idea ID {idea_id}, portfolio ID {portfolio_id}")

            # Update main idea rank if missing or 0
            idea_rank_query = f"SELECT id, rank FROM idea_concept WHERE id = {idea_id};"
            idea_result = db_instance.retrieveSQLQueryOld(idea_rank_query)

            if idea_result and idea_result[0].get("rank", 0) == 0:
                update_main_rank_query = """
                    UPDATE idea_concept
                    SET 
                        rank = %s,
                        updated_by_id = %s,
                        updated_on = CURRENT_TIMESTAMP
                    WHERE id = %s AND tenant_id = %s;
                """
                db_instance.executeSQLQuery(update_main_rank_query, (portfolio_rank + max_rank, user_id, idea_id, tenant_id))
                debugLogger.info(f"Updated idea rank for idea ID {idea_id}")

            # Socket feedback
            if socketio and client_id:
                socketio.emit(
                    "ideation_agent",
                    {
                        "event": "portfolio_rank_updated",
                        "data": {"idea_id": idea_id, "portfolio_id": portfolio_id, "status": "success"}
                    },
                    room=client_id
                )

    except Exception as e:
        if sender:
            sender.sendError(key="Error updating idea portfolio rank", function="update_idea_portfolio_ranks_fn")
        appLogger.error({
            "event": "Idea portfolio rank update failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })


def update_idea_ranks_fn(
    # tenant_id: int,
    # user_id: int,
    tenantID: int = None,
    userID: int = None,
    data: List[Dict[str, Any]]=None,
    # session_id: str = None,
    socketio: Any = None,
    client_id: str = None,
    **kwargs
) -> List[str]:
    """
    Update rank in idea_concept table for an array of ideas.

    Args:
        tenant_id: Tenant ID.
        user_id: User ID performing the operation.
        data: List of dicts with id and priority.
        session_id: Session ID.
        socketio: SocketIO instance.
        client_id: SocketIO room ID.

    Returns:
        List of results or errors.
    """
    try:
        user_id = userID
        tenant_id = tenantID
        debugLogger.info(f"Updating idea ranks for tenant_id: {tenant_id}, {len(data)} ideas")
        sender = kwargs.get("step_sender") or None

        for _data in data:
            required_fields = ["id", "priority"]
            missing_fields = [f for f in required_fields if f not in _data]
            if missing_fields:
                appLogger.error({
                    "event": "Idea rank update failed",
                    "error": f"Missing required fields: {missing_fields}"
                })
                continue

            idea_id = _data["id"]
            rank = _data["priority"]

            if not isinstance(rank, int):
                appLogger.error({
                    "event": "Idea rank update failed",
                    "error": f"Rank must be integer for idea {idea_id}"
                })
                continue

            update_query = """
                UPDATE idea_concept
                SET 
                    rank = %s,
                    updated_by_id = %s,
                    updated_on = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s;
            """
            db_instance.executeSQLQuery(update_query, (rank, user_id, idea_id, tenant_id))
            debugLogger.info(f"Updated idea rank {rank} for idea ID {idea_id}")

            # Socket feedback
            if socketio and client_id:
                socketio.emit(
                    "ideation_agent",
                    {
                        "event": "idea_rank_updated",
                        "data": {"idea_id": idea_id, "status": "success"}
                    },
                    room=client_id
                )

    except Exception as e:
        if sender:
            sender.sendError(key="Error updating idea rank", function="update_idea_ranks_fn")
        appLogger.error({
            "event": "Idea rank update failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })




UPDATE_IDEA_RANKS = AgentFunction(
    name="update_idea_ranks_fn",
    description="""This function is used to Update rank in idea_concept table for an array of ideas.""",
    args=[],
    return_description="",
    function=update_idea_ranks_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

UPDATE_IDEA_PORTFOLIO_RANKS = AgentFunction(
    name="update_idea_portfolio_ranks_fn",
    description="""This function is used to Update portfolio rank in idea_conceptportfolio table for an array of ideas.""",
    args=[],
    return_description="",
    function=update_idea_portfolio_ranks_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)