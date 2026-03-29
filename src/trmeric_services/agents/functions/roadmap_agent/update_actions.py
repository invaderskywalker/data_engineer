# update actions py
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_database.dao import TangoDao, RoadmapPrioritizationDao
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes

agent_name = "roadmap_agent"

def update_roadmap_dates_fn(
    # tenant_id: int,
    # user_id: int,
    # roadmap_data: List[Dict[str, Any]],
    # session_id: str = None,
    tenantID: int = None,
    userID: int = None,
    data: List[Dict[str, Any]] = None,
    socketio: Any = None,
    client_id: str = None,
    **kwargs
) -> List[str]:
    """Update start_date and end_date in roadmap_roadmap table for an array of roadmaps.

    Args:
        tenant_id: Tenant ID for data isolation.
        user_id: User ID performing the operation.
        roadmap_data: List of dictionaries with roadmap_id, start_date, and end_date.
        session_id: Session ID for tracking.
        socketio: SocketIO instance for real-time feedback.
        client_id: Client ID for SocketIO room.
        **kwargs: Additional arguments.

    Returns:
        List of JSON-formatted responses indicating success or failure for each roadmap.
    """
    user_id = userID
    roadmap_data = data
    tenant_id = tenantID
    try:
        # print("in here update_roadmap_dates_fn ", roadmap_data)
        sender = kwargs.get("steps_sender") or None
        debugLogger.info(f"Updating dates for tenant_id: {tenant_id}, {len(roadmap_data)} roadmaps")
        required_data = roadmap_data.get("data")
        session_id = roadmap_data.get("session_id")
        TangoDao.insertTangoState(
            tenant_id=tenant_id,
            user_id=user_id,
            key="roadmap_agent_schedule_created",
            value=json.dumps(roadmap_data.get("all")),
            session_id=session_id
        )
        TangoDao.insert_chat_title(
            session_id=session_id,
            title="Schedule snapshot",
            tenant_id=tenant_id,
            user_id=user_id,
            agent_name='roadmap_schedule',
        )

        for data in required_data:
            # Validate required fields
            print("in here update_roadmap_dates_fn 1 ")
            required_fields = ["id", "start_date", "end_date"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                error_msg = f"Missing required fields for roadmap_id {data.get('roadmap_id', 'unknown')}: {missing_fields}"
                sender.sendError(key=error_msg,function="update_roadmap_dates_fn")
                appLogger.error({"event": "Dates update failed", "error": error_msg})
                return
            
            print("in here update_roadmap_dates_fn 2")

            roadmap_id = data["id"]
            start_date = data["start_date"]
            end_date = data["end_date"]
            
            print("in here update_roadmap_dates_fn 3 ", roadmap_id, start_date, end_date)

            # Validate date format and logic
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                if end < start:
                    error_msg = f"end_date must be after start_date for roadmap_id {roadmap_id}"
                    appLogger.error({"event": "Dates update failed", "error": error_msg})
                    continue
            except ValueError as ve:
                error_msg = f"Invalid date format for roadmap_id {roadmap_id}, expected YYYY-MM-DD, got: start_date={start_date}, end_date={end_date}"
                sender.sendError(key=error_msg,function="update_roadmap_dates_fn")
                appLogger.error({"event": "Dates update failed", "error": error_msg})
                continue
            
            
            print("in here update_roadmap_dates_fn 4 ", roadmap_id, start, end)

            # Update roadmap dates
            update_query = """
                UPDATE roadmap_roadmap
                SET 
                    start_date = %s,
                    end_date = %s,
                    updated_by_id = %s,
                    updated_on = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s;
            """
            params = (start_date, end_date, user_id, roadmap_id, tenant_id)
            db_instance.executeSQLQuery(update_query, params)
            debugLogger.info(f"Updated dates for roadmap ID {roadmap_id}: {start_date} to {end_date}")

            # Emit success event via SocketIO if provided
            if socketio and client_id:
                socketio.emit(
                    agent_name,
                    {
                        "event": "dates_updated",
                        "data": {"roadmap_id": roadmap_id, "status": "success"}
                    },
                    room=client_id
                )

    except Exception as e:
        sender.sendError(key="Error updating dates",function="update_roadmap_dates_fn")
        appLogger.error({"event": "Dates update/insert failed","error": str(e),"traceback": traceback.format_exc()})


def update_roadmap_portfolio_ranks_fn(
    # tenant_id: int,
    # user_id: int,
    tenantID: int = None,
    userID: int = None,
    data: List[Dict[str, Any]] = None,
    # roadmap_data: List[Dict[str, Any]],
    session_id: str = None,
    socketio: Any = None,
    client_id: str = None,
    **kwargs
) -> List[str]:
    """Update portfolio rank in roadmap_roadmapportfolio table for an array of roadmaps.

    Args:
        tenant_id: Tenant ID for data isolation.
        user_id: User ID performing the operation.
        data: List of dictionaries with roadmap_id, portfolio_id, and rank.
        session_id: Session ID for tracking.
        socketio: SocketIO instance for real-time feedback.
        client_id: Client ID for SocketIO room.
        **kwargs: Additional arguments.

    Returns:
        List of JSON-formatted responses indicating success or failure for each roadmap.
    """
    user_id = userID
    roadmap_data = data
    tenant_id = tenantID
    try:
        sender = kwargs.get("steps_sender") or None
        debugLogger.info(f"Updating portfolio ranks for tenant_id: {tenant_id}, {len(roadmap_data)} roadmaps")

        update_query = f"""
            SELECT id, rank from roadmap_roadmap
            WHERE  tenant_id = {tenant_id};
        """
        data = db_instance.retrieveSQLQueryOld(update_query)
        max_rank = 0
        min_rank = 99
        if (len(data)>0):
            for d in data:
                rank = d.get("rank", 0) or 0
                if rank > max_rank:
                    max_rank = rank
                
                if rank == 0:
                    pass
                else:
                    if rank < min_rank:
                        min_rank = rank
        
        if min_rank == 99 or min_rank == 1:
            min_rank = 0
                    
        debugLogger.info(f"max rank identified for tenant: {tenant_id} - {max_rank} - {min_rank}")
        
        for data in roadmap_data.get("roadmap_list") or []:
            # Validate required fields
            required_fields = ["id", "portfolio_id", "priority"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                error_msg = f"Missing required fields for roadmap_id {data.get('roadmap_id', 'unknown')}: {missing_fields}"
                appLogger.error({"event": "Portfolio rank update failed", "error": error_msg})
                # yield json.dumps({"error": error_msg, "roadmap_id": data.get("roadmap_id")})
                continue

            roadmap_id = data["id"]
            portfolio_id = data["portfolio_id"]
            portfolio_rank = data["priority"]

            # Validate rank is an integer
            if not isinstance(portfolio_rank, int):
                error_msg = f"Portfolio rank must be an integer for roadmap_id {roadmap_id}, got: {portfolio_rank}"
                appLogger.error({"event": "Portfolio rank update failed", "error": error_msg})
                # yield json.dumps({"error": error_msg, "roadmap_id": roadmap_id})
                continue

            # Update existing portfolio rank
            update_query = """
                UPDATE roadmap_roadmapportfolio
                SET rank = %s
                WHERE roadmap_id = %s AND portfolio_id = %s;
            """
            params = (portfolio_rank, roadmap_id, portfolio_id)
            db_instance.executeSQLQuery(update_query, params)
            debugLogger.info(f"Updated portfolio rank {portfolio_rank} for roadmap ID {roadmap_id}, portfolio ID {portfolio_id}")


            update_query = f"""
                SELECT id, rank from roadmap_roadmap
                WHERE  id = {roadmap_id};
            """
            data = db_instance.retrieveSQLQueryOld(update_query)
            debugLogger.info(f"Checking rankfor roadmap ID {roadmap_id}, len{len(data)}")
            # print("data -- ", data)
            if len(data)> 0:
                for d in data:
                    rank = d.get("rank", 0) or 0
                    debugLogger.info(f"Checking rankfor roadmap ID {roadmap_id}, rank {rank}")
                    if rank == 0:
                    #     pass
                    # else:
                        update_query = """
                            UPDATE roadmap_roadmap
                            SET 
                                rank = %s,
                                updated_by_id = %s,
                                updated_on = CURRENT_TIMESTAMP
                            WHERE id = %s AND tenant_id = %s;
                        """
                        params = (portfolio_rank+max_rank, user_id, roadmap_id, tenant_id)
                        db_instance.executeSQLQuery(update_query, params)
                        debugLogger.info(f"Updated roadmap rank {rank} for roadmap ID {roadmap_id}")
               

            
        # Emit success event via SocketIO if provided
        if socketio and client_id:
            socketio.emit(
                agent_name,
                {
                    "event": "portfolio_rank_updated",
                    "data": {"roadmap_id": roadmap_id, "portfolio_id": portfolio_id, "status": "success"}
                },
                room=client_id
            )
            
        # ---- Record AI prioritization snapshot ----
        try:
            ai_snapshot_state = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(
                tenant_id=tenant_id,
                user_id=user_id,
                key="roadmap_prioritization"
            )
            print("ai snpashot data -- ", len(ai_snapshot_state))
            if len(ai_snapshot_state) > 0:
                ai_snapshot_state = ai_snapshot_state[0]
                ai_snapshot = ai_snapshot_state.get("value")
                ai_snapshot_json = json.loads(ai_snapshot)
                reason = roadmap_data.get("reason")
                was_reordered = reason != ""
                    
                RoadmapPrioritizationDao.insertPrioritizationHistory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    ai_prioritization_snapshot=ai_snapshot_json,
                    was_reordered=was_reordered,
                    reason_for_change=reason,
                    after_change=roadmap_data,
                    session_id=session_id
                )
                debugLogger.info(f"Saved roadmap_prioritization_history for tenant={tenant_id}, user={user_id}")
        except Exception as e:
            appLogger.error({
                "event": "Failed to record prioritization snapshot (portfolio ranks)",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
                
            

    except Exception as e:
        # sender.sendError(key="Error updating portfolio rank",function="update_roadmap_portfolio_ranks_fn")
        appLogger.error({
            "event": "Portfolio rank update/insert failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        

def update_roadmap_ranks_fn(
    # tenant_id: int,
    # user_id: int,
    # rank_data: List[Dict[str, Any]],
    tenantID: int = None,
    userID: int = None,
    data: List[Dict[str, Any]] = None,
    session_id: str = None,
    socketio: Any = None,
    client_id: str = None,
    **kwargs
) -> List[str]:
    """Update rank in roadmap_roadmap table for an array of roadmaps.

    Args:
        tenant_id: Tenant ID for data isolation.
        user_id: User ID performing the operation.
        rank_data: List of dictionaries with roadmap_id and rank.
        session_id: Session ID for tracking.
        socketio: SocketIO instance for real-time feedback.
        client_id: Client ID for SocketIO room.
        **kwargs: Additional arguments.

    Returns:
        List of JSON-formatted responses indicating success or failure for each roadmap.
    """
    user_id = userID
    rank_data = data
    tenant_id = tenantID
    try:
        debugLogger.info(f"Updating roadmap ranks for tenant_id: {tenant_id}, {len(rank_data)} roadmaps")
        sender = kwargs.get("steps_sender") or None

        for data in rank_data.get("roadmap_list") or []:
            # Validate required fields
            required_fields = ["id", "priority"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                error_msg = f"Missing required fields for roadmap_id {data.get('roadmap_id', 'unknown')}: {missing_fields}"
                appLogger.error({"event": "Roadmap rank update failed", "error": error_msg,"traceback":traceback.format_exc()})
                continue

            roadmap_id = data["id"]
            rank = data["priority"]

            # Validate rank is an integer
            if not isinstance(rank, int):
                error_msg = f"Roadmap rank must be an integer for roadmap_id {roadmap_id}, got: {rank}"
                appLogger.error({"event": "Roadmap rank update failed", "error": error_msg})
                continue

            # Update roadmap rank
            update_query = """
                UPDATE roadmap_roadmap
                SET 
                    rank = %s,
                    updated_by_id = %s,
                    updated_on = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s;
            """
            params = (rank, user_id, roadmap_id, tenant_id)
            db_instance.executeSQLQuery(update_query, params)
            debugLogger.info(f"Updated roadmap rank {rank} for roadmap ID {roadmap_id}")

            # Emit success event via SocketIO if provided
            if socketio and client_id:
                socketio.emit(
                    agent_name,
                    {
                        "event": "roadmap_rank_updated",
                        "data": {"roadmap_id": roadmap_id, "status": "success"}
                    },
                    room=client_id
                )
                
                    # ---- Record AI prioritization snapshot ----
        try:
            print("ai snpashot data -- ", len(ai_snapshot_state))
            if len(ai_snapshot_state) > 0:
                ai_snapshot_state = ai_snapshot_state[0]
                ai_snapshot = ai_snapshot_state.get("value")
                ai_snapshot_json = json.loads(ai_snapshot)
                reason = rank_data.get("reason")
                was_reordered = reason != ""
                    
                RoadmapPrioritizationDao.insertPrioritizationHistory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    ai_prioritization_snapshot=ai_snapshot_json,
                    was_reordered=was_reordered,
                    reason_for_change=reason,
                    after_change=rank_data,
                    session_id=session_id
                )
            debugLogger.info(f"Saved roadmap_prioritization_history for tenant={tenant_id}, user={user_id}")
        except Exception as e:
            appLogger.error({
                "event": "Failed to record prioritization snapshot (roadmap ranks)",
                "error": str(e),
                "traceback": traceback.format_exc()
            })


    except Exception as e:
        sender.sendError(key="Error updating roadmap rank",function="update_roadmap_ranks_fn")
        appLogger.error({
            "event": "Roadmap rank update failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        

UPDATE_ROADMAP_DATES = AgentFunction(
    name="update_idea_ranks_fn",
    description="""This function is used to Update start_date and end_date in roadmap_roadmap table for an array of roadmaps.""",
    args=[],
    return_description="",
    function=update_roadmap_dates_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)



UPDATE_ROADMAP_RANKS = AgentFunction(
    name="update_idea_ranks_fn",
    description="""This function is used to Update rank in roadmap_roadmap table for an array of roadmaps.""",
    args=[],
    return_description="",
    function=update_roadmap_ranks_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

UPDATE_ROADMAP_PORTFOLIO_RANKS = AgentFunction(
    name="update_idea_portfolio_ranks_fn",
    description="""This function is used to Update portfolio rank in roadmap_roadmapportfolio table for an array of roadmaps.""",
    args=[],
    return_description="",
    function=update_roadmap_portfolio_ranks_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

