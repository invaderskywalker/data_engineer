import time
import inspect
from contextvars import ContextVar
from functools import wraps
from threading import Thread
import traceback 
from src.trmeric_database.dao.tango import TangoDao
from src.trmeric_api.logging.ProgramState import ProgramState
from src.trmeric_database.dao.users import UsersDao
from src.trmeric_api.logging.AppLogger import appLogger 

from src.trmeric_services.journal.ActivityLogger import ActivityLogger

_activity: ContextVar[dict] = ContextVar("_activity", default=None)

def activity(agent_or_workflow_name: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            activity_data = {
                "socket_id": None, "tenant_id": None, "user_id": None,
                "agent_or_workflow_name": agent_or_workflow_name,
                "input_data": None, "output_data": None,
                "status": "success", "metrics": {}
            }
            token = _activity.set(activity_data)

            try:
                try:
                    bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
                except Exception as e_bind:
                    bound = kwargs
                    appLogger.warning({
                        "event": "activity_signature_binding_failed",
                        "agent_or_workflow": agent_or_workflow_name,
                        "function_name": fn.__name__,
                        "error": str(e_bind)
                    })

                activity_data["user_id"] = bound.get("user_id") or bound.get("userID") 
                activity_data["tenant_id"] = bound.get("tenant_id")
                activity_data["socket_id"] = bound.get("socket_id")
                
                # If we have user_id from parameters, try to populate missing values
                if activity_data["user_id"]:
                    try:
                        program_state_instance = ProgramState.get_instance(activity_data["user_id"])
                        if not activity_data["socket_id"]:
                            activity_data["socket_id"] = program_state_instance.get("socket_id")
                        if not activity_data["tenant_id"]:
                            activity_data["tenant_id"] = UsersDao.fetchUserTenantID(activity_data["user_id"])
                    except Exception as e_program_state:
                        appLogger.warning({
                            "event": "activity_program_state_lookup_failed",
                            "agent_or_workflow": agent_or_workflow_name,
                            "function_name": fn.__name__,
                            "user_id": activity_data["user_id"],
                            "error": str(e_program_state)
                        })

                if args and activity_data.get("input_data") is None:
                    activity_data["input_data"] = args[0]

                start_time = time.time()
                result = None
                try:
                    result = fn(*args, **kwargs)
                    current_activity_data = _activity.get()
                    if current_activity_data is None:
                        return result
                    if current_activity_data["output_data"] is None:
                        current_activity_data["output_data"] = result
                except Exception as e_fn:
                    activity_data["status"] = "error"
                    appLogger.error({
                        "event": "activity_decorated_function_exception",
                        "agent_or_workflow": agent_or_workflow_name,
                        "function_name": fn.__name__,
                        "error": str(e_fn),
                        "traceback": traceback.format_exc()
                    })
                    raise
                finally:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    current_activity_data = _activity.get()
                    if current_activity_data:
                        if isinstance(current_activity_data.get("metrics"), dict):
                            current_activity_data["metrics"]["latency_ms"] = elapsed_ms
                        else:
                            current_activity_data["metrics"] = {"latency_ms": elapsed_ms}
                        
                        # If user_id was set via record() but we don't have socket_id or tenant_id, try to populate them
                        if current_activity_data.get("user_id") and (not current_activity_data.get("socket_id") or not current_activity_data.get("tenant_id")):
                            try:
                                program_state_instance = ProgramState.get_instance(current_activity_data["user_id"])
                                if not current_activity_data.get("socket_id"):
                                    current_activity_data["socket_id"] = program_state_instance.get("socket_id")
                                if not current_activity_data.get("tenant_id"):
                                    current_activity_data["tenant_id"] = UsersDao.fetchUserTenantID(current_activity_data["user_id"])
                            except Exception as e_program_state:
                                appLogger.warning({
                                    "event": "activity_program_state_lookup_failed_finally",
                                    "agent_or_workflow": agent_or_workflow_name,
                                    "function_name": fn.__name__,
                                    "user_id": current_activity_data["user_id"],
                                    "error": str(e_program_state)
                                })
                        
                        description = current_activity_data.pop("description", "")
                        if current_activity_data.get("socket_id") and current_activity_data.get("tenant_id") and current_activity_data.get("user_id"):
                            activity_data_with_description = current_activity_data.copy()
                            activity_data_with_description["description"] = description
                            Thread(target=ActivityLogger._push_async, args=(activity_data_with_description,), daemon=True).start()
                        else:
                            appLogger.warning({
                                "event": "activity_log_push_skipped_missing_ids",
                                "agent_or_workflow": agent_or_workflow_name,
                                "function_name": fn.__name__,
                                "socket_id": current_activity_data.get("socket_id"),
                                "tenant_id": current_activity_data.get("tenant_id"),
                                "user_id": current_activity_data.get("user_id"),
                                "program_state": program_state_instance.get_all() if 'program_state_instance' in locals() else None
                            })
                return result
            except Exception as e_outer:
                appLogger.error({
                    "event": "activity_wrapper_setup_exception",
                    "agent_or_workflow": agent_or_workflow_name,
                    "function_name": fn.__name__,
                    "error": str(e_outer),
                    "traceback": traceback.format_exc()
                })
                raise
            finally:
                _activity.reset(token)
        return wrapper
    return decorator

def activity_log(agent_or_workflow_name: str, input_data, output_data, user_id: int, 
                 tenant_id: int = None, socket_id: str = None, description: str = "", 
                 status: str = "success", metrics: dict = None, **kwargs):
    """
    Standalone function to log activities without using the decorator pattern.
    This is useful for complex workflows where you want to log specific transformations.
    Mirrors all the nuances and behavior of the activity decorator wrapper.
    
    Args:
        agent_or_workflow_name: Name of the agent or workflow
        input_data: Raw input data provided by user
        output_data: Enhanced output data generated by system
        user_id: User ID (required)
        tenant_id: Tenant ID (optional, will be looked up if not provided)
        socket_id: Socket ID (optional, will be looked up if not provided)
        description: Human-readable description of the transformation
        status: Status of the activity (default: "success")
        metrics: Additional metrics dictionary (optional)
    """
    if not user_id:
        appLogger.error({
            "event": "activity_log_missing_user_id",
            "agent_or_workflow": agent_or_workflow_name,
            "error": "user_id is required for activity logging"
        })
        return False
    
    # print("---output" , output_data)
    # print("-- inout --" , input_data)
    # Prepare activity data (matching wrapper structure exactly)
    activity_data = {
        "socket_id": socket_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "agent_or_workflow_name": agent_or_workflow_name,
        "input_data": input_data,
        "output_data": output_data,
        "status": status,
        "metrics": metrics or {}
    }
    
    # Try to populate missing tenant_id and socket_id (same logic as wrapper)
    if activity_data["user_id"] and (not activity_data.get("socket_id") or not activity_data.get("tenant_id")):
        try:
            program_state_instance = ProgramState.get_instance(activity_data["user_id"])
            if not activity_data.get("socket_id"):
                activity_data["socket_id"] = program_state_instance.get("socket_id")
            if not activity_data.get("tenant_id"):
                activity_data["tenant_id"] = UsersDao.fetchUserTenantID(activity_data["user_id"])
        except Exception as e_program_state:
            appLogger.warning({
                "event": "activity_log_program_state_lookup_failed",
                "agent_or_workflow": agent_or_workflow_name,
                "user_id": activity_data["user_id"],
                "error": str(e_program_state)
            })
    
    # Ensure metrics is a dict and add any additional metrics
    if not isinstance(activity_data.get("metrics"), dict):
        activity_data["metrics"] = {}
    
    # Handle description exactly like the wrapper: pop it from data before push
    # but include it in the copy that gets pushed
    description_value = description or ""
    
    # Only proceed if we have the required IDs (same check as wrapper)
    if activity_data.get("socket_id") and activity_data.get("tenant_id") and activity_data.get("user_id"):
        try:
            # Create copy with description for push (matching wrapper behavior)
            activity_data_with_description = activity_data.copy()
            activity_data_with_description["description"] = description_value
            
            # Run async push in background thread (same as wrapper)
            Thread(target=ActivityLogger._push_async, args=(activity_data_with_description,), daemon=True).start()
            
            appLogger.info({
                "event": "activity_log_success",
                "agent_or_workflow": agent_or_workflow_name,
                "user_id": user_id,
                "tenant_id": activity_data.get("tenant_id"),
                "socket_id": activity_data.get("socket_id")
            })
            return True
        except Exception as e:
            appLogger.error({
                "event": "activity_log_push_failed",
                "agent_or_workflow": agent_or_workflow_name,
                "user_id": user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return False
    else:
        # Same warning structure as wrapper
        appLogger.warning({
            "event": "activity_log_push_skipped_missing_ids",
            "agent_or_workflow": agent_or_workflow_name,
            "user_id": user_id,
            "socket_id": activity_data.get("socket_id"),
            "tenant_id": activity_data.get("tenant_id"),
            "program_state": None  # We don't have access to program_state_instance here
        })
        return False
    
def record(field: str, value):
    activity_data = _activity.get()
    if field == "void_activity":
        _activity.set(None)
        return
    if not activity_data:
        return
    if field in activity_data and field != "metrics":
        activity_data[field] = value
    if field == "description":
        activity_data["description"] = value
    else:
        if not isinstance(activity_data.get("metrics"), dict):
            activity_data["metrics"] = {}
        activity_data["metrics"][field] = value

def detailed_activity(activity_name, activity_description="", status="success", user_id=None):                    
    if not user_id:
        appLogger.error({
            "event": "insert_activity_log_detailed_missing_user_id",
            "error": "user_id is required to insert ActivityLogDetailed."
        })
        return False

    tenant_id = UsersDao.fetchUserTenantID(user_id)
    if not tenant_id:
        appLogger.error({
            "event": "insert_activity_log_detailed_missing_tenant_id",
            "user_id": user_id,
            "error": "Could not resolve tenant_id from user_id."
        })
        return False

    try:
        program_state = ProgramState.get_instance(user_id)
        socket_id = program_state.get("socket_id")
    except Exception as e:
        appLogger.error({
            "event": "insert_activity_log_detailed_program_state_error",
            "user_id": user_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return False

    if not socket_id:
        appLogger.error({
            "event": "insert_activity_log_detailed_missing_socket_id",
            "user_id": user_id,
            "error": "Could not resolve socket_id from ProgramState."
        })
        return False

    try:
        TangoDao.insertActivityLogDetailed(
            activity_name=activity_name,
            activity_description=activity_description,
            status=status,
            socket_id=socket_id,
            tenant_id=tenant_id,
            user_id=user_id
        )
        appLogger.info({
            "event": "insert_activity_log_detailed_success",
            "activity_name": activity_name,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "socket_id": socket_id
        })
        return True
    except Exception as e:
        appLogger.error({
            "event": "insert_activity_log_detailed_exception",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "activity_name": activity_name,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "socket_id": socket_id
        })
        return False