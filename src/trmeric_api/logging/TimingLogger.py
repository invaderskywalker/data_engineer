import logging
import time
from logging.handlers import RotatingFileHandler
import threading
import json
from functools import wraps
import os
from .ProgramState import ProgramState

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Set up the timing logger
TIMING_LOG_PATH = "logs/timing.log"
timing_handler = RotatingFileHandler(TIMING_LOG_PATH, maxBytes=1000000, backupCount=5)
timing_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

timingLogger = logging.getLogger("timing_logger")
timingLogger.setLevel(logging.INFO)
timingLogger.addHandler(timing_handler)

# Thread-local storage to keep track of timing context per request/thread
_thread_local = threading.local()

def start_timer(operation, **context):
    """Start timing an operation with optional context information"""
    try:
        if not hasattr(_thread_local, 'timers'):
            _thread_local.timers = {}
        
        # If user_id is provided, get program state and enrich context
        user_id = context.get('user_id')
        if user_id:
            program_state = ProgramState.get_instance(user_id)
            
            # Add session_id and current_agent from program state if available
            for key in ['current_prompt', 'current_agent', 'session_id']:
                if key not in context:  # Only add if not already in context
                    value = program_state.get(key)
                    if value is not None:
                        context[key] = value
        
        timer_id = f"{operation}_{time.time()}"
        _thread_local.timers[timer_id] = {
            'start': time.time(),
            'operation': operation,
            'context': context
        }
        return timer_id
    except Exception:
        # Return a dummy timer ID that won't fail when stop_timer is called
        return f"error_timer_{time.time()}"

def stop_timer(timer_id):
    """Stop timing an operation and log the duration"""
    try:
        if not timer_id or not hasattr(_thread_local, 'timers') or timer_id not in _thread_local.timers:
            return None
        
        timer = _thread_local.timers.pop(timer_id)
        duration = time.time() - timer['start']
        
        log_entry = {
            'operation': timer['operation'],
            'duration_ms': round(duration * 1000, 2),
            'context': timer['context']
        }
        
        timingLogger.info(json.dumps(log_entry))
        return duration
    except Exception:
        # Silent failure - don't affect main execution flow
        return None

def time_operation(operation, **context):
    """Decorator to time a function execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timer_id = start_timer(operation, **context)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                stop_timer(timer_id)
        return wrapper
    return decorator

def log_timing(operation, duration_ms, **context):
    """Manually log a timing entry"""
    try:
        # If user_id is provided, get program state and enrich context
        user_id = context.get('user_id')
        if user_id:
            program_state = ProgramState.get_instance(user_id)
            
            # Add session_id and current_agent from program state if available
            for key in ['current_prompt', 'current_agent', 'session_id']:
                if key not in context:  # Only add if not already in context
                    value = program_state.get(key)
                    if value is not None:
                        context[key] = value
        
        log_entry = {
            'operation': operation,
            'duration_ms': round(duration_ms, 2),
            'context': context
        }
        timingLogger.info(json.dumps(log_entry))
    except Exception:
        pass  # Silent failure
    
def log_event_start(event_name=None, client_id=None, **additional_context):
    """Log the start of a new tango event with a visible separator"""
    try:
        if not event_name:
            event_name = "UNKNOWN_EVENT"
            
        separator = "\n" + "="*50 + f"\n== NEW TANGO EVENT: {event_name} =="
        if client_id:
            separator += f" (client: {client_id})"
        separator += "\n" + "="*50
        
        # If user_id is provided, get program state and enrich context
        user_id = additional_context.get('user_id')
        if user_id:
            program_state = ProgramState.get_instance(user_id)
            
            # Add session_id and current_agent from program state if available
            for key in ['current_prompt', 'current_agent', 'session_id']:
                if key not in additional_context:  # Only add if not already in context
                    value = program_state.get(key)
                    if value is not None:
                        additional_context[key] = value
        
        context = additional_context.copy() if additional_context else {}
        if client_id:
            context["client_id"] = client_id
            
        log_entry = {
            'event_type': 'event_start',
            'event_name': event_name,
            'timestamp': time.time(),
            'context': context
        }
        
        # Log the separator first as plain text
        timingLogger.info(separator)
        
        # Then log the structured data
        timingLogger.info(json.dumps(log_entry))
    except Exception:
        # Silent failure - logging should never break main application flow
        pass

