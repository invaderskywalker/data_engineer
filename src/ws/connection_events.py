from flask import request
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from src.api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.trmeric_integrations.IntegrationRetriever import retrieveIntegrations
from src.trmeric_services.super_agent_v1.core.context_builder import ContextBuilder
from .common import active_connections, decodeAuthToken
from .static import UserSocketMap, ActiveUserSocketMap
from src.api.logging.ProgramState import ProgramState
from src.trmeric_services.journal.ActivityEndpoints import session_summary, tango_session_summary
from src.utils.knowledge.TangoMemory import TangoMem
from src.api.logging.AppLogger import appLogger, debugLogger
# from src.database.mongo.dao import JobDAO, JobModel
from datetime import datetime, timedelta
from src.database.dao import JobDAO, TangoDao, UsersDao
import time
import json
from src.trmeric_services.journal.Vectors.ActivityOnboarding import get_transformation_summary


def build_user_context_async(
    tenant_id,
    user_id,
    session_id
):
    try:
        debugLogger.info({
            "event": "context_build_start",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
        })

        ContextBuilder(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        ).build_context("")


    except Exception as e:
        appLogger.error({
            "event": "context_build_failed",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        })


loop_threads = {}

def start_event_loop(socketio, client_id):
    """Background loop that emits events every second while client is connected."""
    # print("start_event_loop ", client_id)
    while client_id in active_connections:
        # print("start_event_loop yes")
        try:
            # Get tenant_id for the client
            tenant_id = active_connections.get(client_id, {}).get("tenant_id")
            if not tenant_id:
                print(f"No tenant_id found for client {client_id}")
                return
            
            # socketio.emit("heartbeat", {"message": f"Tick for {client_id}"}, room=client_id)
            
            state_key = f"TENANT_LEVEL_INTEGRATION_INFO_"
            state = TangoDao.fetchLatestTangoStatesForTenant(tenant_id, state_key)
            
            if state:
                state_value = json.loads(state["value"])
                for conn_client_id, conn_info in active_connections.items():
                    if UsersDao.checkIfUserBelongsToTenant(tenant_id, conn_info["user_id"]):
                        socketio.emit(
                            "integration_agent",
                            {
                                "event": "cron_running_counter",
                                "data": state_value
                            },
                            room=conn_client_id
                        )
            state = TangoDao.fetchLatestTangoStatesForTenant(
                tenant_id, 
                "TENANT_LEVEL_PROJECT_CREATION_INFO_"
            )
            # if state:
            #     state_value = json.loads(state["value"])
            #     for conn_client_id, conn_info in active_connections.items():
            #         if UsersDao.checkIfUserBelongsToTenant(tenant_id, conn_info["user_id"]):
            #             socketio.emit(
            #                 "sync_agent",
            #                 {
            #                     "event": "project_creation_counter",
            #                     "data": state_value
            #                 },
            #                 room=conn_client_id
            #             )
                        
            state = TangoDao.fetchLatestTangoStatesForTenant(
                tenant_id, 
                "TENANT_LEVEL_ROADMAP_CREATION_INFO_"
            )
            # if state:
            #     state_value = json.loads(state["value"])
            #     for conn_client_id, conn_info in active_connections.items():
            #         if UsersDao.checkIfUserBelongsToTenant(tenant_id, conn_info["user_id"]):
            #             socketio.emit(
            #                 "sync_agent",
            #                 {
            #                     "event": "roadmap_creation_counter",
            #                     "data": state_value
            #                 },
            #                 room=conn_client_id
            #             )
            # else:
            #     socketio.emit(
            #         "integration_agent",
            #         {
            #             "event": "cron_running_counter",
            #             "data": {}
            #         },
            #         room=client_id
            #     )

        except Exception as e:
            print(f"Error sending heartbeat to {client_id}: {e}")
            print("traceback -- ", traceback.format_exc())
            
        time.sleep(2)  # wait 1 second
from src.trmeric_services.journal.Vectors.ActivityOnboarding import get_transformation_summary


def register_connection_events(socketio):
    @socketio.on("connect")
    def handle_connect(auth):
        log_event_start("TANGO_AUTH", client_id=request.sid)
        timer_id = start_timer("tango_auth_process", client_id=request.sid)
        client_id = request.sid
        decoded = decodeAuthToken(auth.get("token"))
        
        if not decoded:
            print(f"Failed to decode token for client {request.sid}")
            socketio.server.disconnect(request.sid)
            stop_timer(timer_id)
            return

        user_identifier = decoded.get("user_id")
        print("register_connection_events ... adddddd", user_identifier, client_id)
        UserSocketMap.add_mapping(str(user_identifier), client_id)
        ActiveUserSocketMap.add(str(user_identifier), client_id)
        tenant_id = decoded.get("tenant_id")
        user_name = decoded.get("user_name") or ""
        
        
        
        program_state = ProgramState.get_instance(user_identifier)
        program_state.set("tenant_id", tenant_id)
        program_state.set("socket_id", client_id)
        
        active_connections[client_id] = {
            'client_id': client_id,
            'user_name': user_name,
            'user_id': user_identifier,
            "tenant_id": tenant_id
        }
        
        # start loop for this client
        # loop_thread = threading.Thread(target=start_event_loop, args=(socketio, client_id), daemon=True)
        # loop_threads[client_id] = loop_thread
        # loop_thread.start()
        
        debugLogger.info(f"Client connected with session ID: {client_id}, user: {user_name}")
        socketio.emit("response", {"message": f"Hello {user_name} from server!"}, room=client_id)
        
        
        # Fire background context build (NON-BLOCKING)
        context_thread = threading.Thread(
            target=build_user_context_async,
            args=(
                tenant_id,
                user_identifier,
                client_id
            ),
            daemon=True
        )
        context_thread.start()

        try:
            # Run retrieveIntegrations sequentially
            integrations_timer = start_timer("integrations_process", user_id=user_identifier, tenant_id=tenant_id)
            try:
                debugLogger.info(f"Starting retrieveIntegrations for tenant_id: {tenant_id}, user_id: {user_identifier}")
                retrieveIntegrations(tenant_id, user_identifier)
                debugLogger.info("Completed retrieveIntegrations")
            except Exception as e:
                appLogger.error({
                    "event": "retrieveIntegrations failed",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                print(f"Error in retrieveIntegrations: {e}")
            finally:
                stop_timer(integrations_timer)

        except Exception as e:
            appLogger.error({
                "event": "Precache threading failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            print(f"Error in precache threading: {e}")
            
            
        try:
            # Initialize JobDAO
            job_dao = JobDAO
            
            # Generate a unique schedule_id for this socket connection
            schedule_id = f"socket-{client_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            run_id = f"socket-{tenant_id}-{user_identifier}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Define job operations
            job_ops = [
                {
                    "job_type": "portfolio-review",
                    "name": "PortfolioReview",
                    "payload": {
                        "job_type": "portfolio-review",
                        # "schedule_id": schedule_id,
                        "run_id": run_id,
                        # "total_count": 2
                    }
                },
                {
                    "job_type": "roadmap-insights-cache",
                    "name": "RoadmapInsightsCache",
                    "payload": {
                        "job_type": "roadmap-insights-cache",
                        # "schedule_id": schedule_id,
                        "run_id": run_id,
                        # "total_count": 2,
                        "session_id": ""
                    }
                },
            ]

            # Enqueue jobs
            enqueued_jobs = []
            for op in job_ops:
                # Check if a similar job was enqueued in the last hour
                mins = 60 * 24
                if int(tenant_id) == 227:
                    mins = 60 * 12
                if job_dao.check_recent_job(
                    tenant_id=tenant_id, 
                    user_id=user_identifier, 
                    job_type=op["job_type"],
                    minutes=mins
                ):
                    debugLogger.info(f"Skipping {op['name']} for tenant {tenant_id}, user {user_identifier}: Job exists within last hour")
                    continue

                # Create job
                job_id = job_dao.create(
                    tenant_id=tenant_id,
                    user_id=user_identifier,
                    schedule_id=None,
                    job_type=op["job_type"],
                    payload=op["payload"]
                )
                enqueued_jobs.append(job_id)
                debugLogger.info(f"Enqueued {op['name']} job for tenant {tenant_id}, user {user_identifier} (job_id: {job_id})")

            debugLogger.info(f"Enqueued {len(enqueued_jobs)} jobs for tenant {tenant_id}, user {user_identifier}")

        except Exception as e:
            appLogger.error({
                "event": "Socket_connect_job_enqueue_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            print(f"Error enqueuing jobs: {e}")
            
        stop_timer(timer_id)
    
    @socketio.on("disconnect")
    def handle_disconnect():
        """
        Handle client disconnect by scheduling session cleanup jobs.
        All actual processing moved to cronV2.py for better reliability and error handling.
        """
        
        # Remove client from active_connections and get its details
        if request.sid in loop_threads:
            del loop_threads[request.sid]
        client_details = active_connections.pop(request.sid, None)
        
        if client_details:
            actual_user_id = client_details.get('user_id')
            tenant_id = client_details.get('tenant_id')
            user_name = client_details.get('user_name', 'N/A')
            
            ps = ProgramState.get_instance(actual_user_id)
            socket_id = ps.get("socket_id", request.sid)
            session_ids = ps.get("session_ids", [])
            
            print(f"Client with session ID {request.sid} and user {user_name} (ID: {actual_user_id}) disconnected.")
            
            if actual_user_id and tenant_id:
                try:
                    UserSocketMap.remove_mapping(actual_user_id)
                    ActiveUserSocketMap.remove(str(actual_user_id), request.sid)
                    # Initialize JobDAO
                    job_dao = JobDAO
                    
                    # Generate run_id for this disconnect session
                    run_id = f"disconnect-{tenant_id}-{actual_user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                    
                    # Remove duplicates from session_ids
                    unique_session_ids = list(set(session_ids)) if session_ids else []
                    
                    # Create job for session summary
                    session_summary_payload = {
                        "job_type": "session-summary",
                        "run_id": run_id,
                        "user_id": actual_user_id,
                        "socket_id": socket_id,
                        "session_ids": unique_session_ids
                    }
                    
                    job_id = job_dao.create(
                        tenant_id=tenant_id,
                        user_id=actual_user_id,
                        schedule_id=None,
                        job_type="session-summary",
                        payload=session_summary_payload
                    )
                    
                    print(f"Scheduled session-summary job {job_id} for User ID: {actual_user_id}, Socket ID: {socket_id}")
                    
                    # Create individual jobs for each session's tango summary and memory refresh
                    for session_id in unique_session_ids:
                        # Tango session summary job
                        tango_summary_payload = {
                            "job_type": "tango-session-summary",
                            "run_id": run_id,
                            "user_id": actual_user_id,
                            "session_id": session_id
                        }
                        
                        tango_job_id = job_dao.create(
                            tenant_id=tenant_id,
                            user_id=actual_user_id,
                            schedule_id=None,
                            job_type="tango-session-summary",
                            payload=tango_summary_payload
                        )
                        
                        # Memory refresh job
                        memory_refresh_payload = {
                            "job_type": "memory-refresh",
                            "run_id": run_id,
                            "user_id": actual_user_id,
                            "session_id": session_id
                        }
                        
                        memory_job_id = job_dao.create(
                            tenant_id=tenant_id,
                            user_id=actual_user_id,
                            schedule_id=None,
                            job_type="memory-refresh",
                            payload=memory_refresh_payload
                        )
                        
                        print(f"Scheduled tango-session-summary job {tango_job_id} and memory-refresh job {memory_job_id} for session {session_id}")
                    
                    debugLogger.info(f"Successfully scheduled {1 + len(unique_session_ids) * 2} disconnect cleanup jobs for user {actual_user_id}")
                    
                except Exception as e:
                    appLogger.error({
                        "event": "Socket_disconnect_job_scheduling_failed",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "user_id": actual_user_id,
                        "socket_id": socket_id
                    })
                    print(f"Error scheduling disconnect cleanup jobs for user {actual_user_id}: {e}")
                
                # Reset program state for this user
                ps.reset()
            else:
                print(f"User ID or tenant ID not found for disconnected session {socket_id}. Cannot schedule cleanup jobs.")
        else:
            print(f"Unknown client disconnected. No cleanup jobs will be scheduled.")  
                

    @socketio.on("ping")
    def handle_ping(*args):
        user_identifier = request.sid
        socketio.emit("pong", '', room=user_identifier)
