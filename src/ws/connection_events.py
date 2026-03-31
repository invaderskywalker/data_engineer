from flask import request
import traceback
import threading
from src.api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.services.super_agent_v1.core.context_builder import ContextBuilder
from .common import active_connections, decodeAuthToken
from .static import UserSocketMap, ActiveUserSocketMap
from src.api.logging.ProgramState import ProgramState
from src.api.logging.AppLogger import appLogger, debugLogger
from datetime import datetime


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

def register_connection_events(socketio):
    @socketio.on("connect")
    def handle_connect(auth):
        log_event_start("TANGO_AUTH", client_id=request.sid)
        timer_id = start_timer("tango_auth_process", client_id=request.sid)
        client_id = request.sid
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NzQ4ODg1MzIsInVzZXJfaWRlbnRpZmllciI6ImFmNDBiZDA2LTIzYzYtNGNjNC1hNjI1LWEzNDY5ZGJkZjY2YiIsInVzZXJfaWQiOiI0NjciLCJ1c2VybmFtZSI6ImFiaGlzaGVrK2V5QHRybWVyaWMuY29tIiwiZmlyc3RfbmFtZSI6IkFiaGlzaGVrIiwibGFzdF9uYW1lIjoiS3VtYXIiLCJ0ZW5hbnRfaWQiOiI3NzYiLCJ0ZW5hbnRfdHlwZSI6ImN1c3RvbWVyIiwidGVuYW50X2NvbmZpZ3VyYXRpb24iOnsicm9hZG1hcF93b3JrX2Zsb3ciOnsiZWRpdF9zcGxfYWNjZXNzIjp0cnVlLCJjb2xsYWJvcmF0b3JfYWNjZXNzIjpbIm9yZ19lZGl0X3JvYWRtYXBfaW50YWtlIiwib3JnX2VkaXRfcm9hZG1hcF9ldmFsdWF0aW9uIiwib3JnX2VkaXRfcm9hZG1hcF9zb2x1dGlvbiIsIm9yZ19lZGl0X3JvYWRtYXBfcHJpb3JpdGlzYXRpb24iXSwic3RhdHVzX2NoYW5nZV9zcGxfYWNjZXNzIjp0cnVlLCJzdGF0dXNfY2hhbmdlX2FwcHJvdmFsX2FsbF9zdGFnZXMiOnRydWV9LCJpbnRlZ3JhdGlvbl9jb25maWd1cmF0aW9uIjp7ImppcmEiOnsic2VydmVyIjoib25wcmVtIiwiYmFzZV91cmwiOiJodHRwczovL2ppcmEtYWVzLmtwLm9yZyJ9fX0sImN1c3RvbWVyX2lkIjoiMTUzIiwiY3VzdG9tZXJfbmFtZSI6ImV5IiwiY3VzdG9tZXJfYXZhdGFyIjoiIiwidGVuYW50X2FjdGlvbnMiOlt7InJvbGUiOiJvcmdfZGVtYW5kX3JlcXVlc3RvciIsImFjdGlvbnMiOlsib3JnX21hbmFnZV9hbGxfcHJvamVjdHMiLCJvcmdfZWRpdF9yb2FkbWFwX2ludGFrZSIsIm9yZ19zcGFjZXNfcHJvamVjdHNfYWRkX2FjdGlvbiIsIm9yZ19zcGFjZXNfcHJvamVjdHNfdmlldyIsIm9yZ19kZWxldGVfcHJvdmlkZXIiLCJvcmdfYm9va21hcmtfaW5zcGlyYXRpb25zIiwib3JnX21hbmFnZV9hbGxfcG9ydGZvbGlvX3Byb2plY3RzIiwib3JnX3ZpZXdfbm90ZXMiLCJvcmdfdXBkYXRlX3Byb3ZpZGVyIiwib3JnX2VkaXRfcm9hZG1hcF9ldmFsdWF0aW9uIiwib3JnX2NyZWF0ZV9rdWRvcyIsIm9yZ192aWV3X2FjdGl2aXR5Iiwib3JnX2NyZWF0ZV9yb2FkbWFwIiwib3JnX2NyZWF0ZV9wcm92aWRlciIsIm9yZ192aWV3X29mZmVyIiwib3JnX2luc2lnaHRfYWRkX2FjdGlvbiIsIm9yZ19jcmVhdGVfcHJvamVjdCIsIm9yZ192aWV3X2t1ZG9zIiwib3JnX3VwZGF0ZV9vZmZlciIsIm9yZ192aWV3X2luc3BpcmF0aW9ucyIsIm9yZ191cGRhdGVfYWN0aXZpdHkiLCJvcmdfYWRkX2FjdGlvbiIsIm9yZ19saWtlX2t1ZG9zIiwib3JnX3NwYWNlc19wcm9qZWN0c19lZGl0Iiwib3JnX2xpa2VfaW5zcGlyYXRpb25zIiwib3JnX3NwYWNlc19wcm9qZWN0c19hZGRfcHJvamVjdCIsIm9yZ19lZGl0X3JvYWRtYXAiLCJvcmdfcmVzdHJpY3Rfcm9hZG1hcHMiLCJvcmdfaW52aXRlX25ld19tZW1iZXIiLCJvcmdfcm9hZG1hcF9zdGF0dXNfZHJhZnRfdG9faW50YWtlIl0sImFkZGl0aW9uYWxfcm9sZXMiOltdfV0sImV4cCI6MTc3NDk0NjEzMiwiYXZhdGFyIjpudWxsLCJ5ZWFyX2N5Y2xlIjoiSnVseS1KdW4ifQ.TvaC6aPCa4gQKdusAga-jcr6MSmmqNUdAoyTXWWECaw"

        decoded = decodeAuthToken(token)
        
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
        
        active_connections[client_id] = {
            'client_id': client_id,
            'user_name': user_name,
            'user_id': user_identifier,
            "tenant_id": tenant_id
        }
        
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
