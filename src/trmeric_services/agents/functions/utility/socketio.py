import traceback
from src.trmeric_api.logging.AppLogger import appLogger


def emit_event(event, event_data, socketio, client_id):
    
    if isinstance(event_data,list):
        for payload in event_data:    
            # print("emit event -- fxn ---- ",event, payload)
            socketio.emit(event, payload, room=client_id)
            socketio.sleep(seconds = 1)
    else:
        socketio.emit(event,event_data,room=client_id)


def start_show_timeline(id1, id2):
    return {"event": "show_timeline"}

def stop_show_timeline():
    return {"event": "stop_show_timeline"}

# def timeline_event(text, key, is_completed, id1, id1_val, id2, id2_val):
#     return { "event": "timeline", "data": {"text": text, "key": key, "is_completed": is_completed},id1:id1_val, id2: id2_val}

def end_event(event, id1,id1_val, id2,id2_val):
    return {"event": event, "data": "<<end>>",id1:id1_val, id2: id2_val}



def timeline_event(text, key, is_completed, *args):
    """
    Build a timeline event payload dynamically using key–value pairs.
    *args: Variable-length list of key/value pairs:
    e.g. ("project_id", 123, "team_id", 456, "user_id", "u001")
    """
    if len(args) % 2 != 0:
        raise ValueError("Extra arguments must be in key-value pairs.")

    extra_fields = {args[i]: args[i + 1] for i in range(0, len(args), 2)}

    payload = {
        "event": "timeline",
        "data": {
            "text": text,
            "key": key,
            "is_completed": is_completed
        }
    }

    payload.update(extra_fields)
    # print("--debug timeline_event payload------", payload)
    return payload



def send_timeline_updates(socketio, client_id, stop_event,agent_name="agent", interval=8, **kwargs):
    """
    Sends periodic timeline updates until stop_event is set. Safe for background execution with Flask-SocketIO.
    """
    step_counter = 0
    stages = kwargs.pop("stages",[]) or []
    print("--debug kwargs-------", kwargs)
    # Flatten kwargs into alternating key/value pairs for timeline_event
    extra_args = []
    for k, v in kwargs.items():
        extra_args.extend([k, v])

    try:
        while not stop_event.is_set() and step_counter < len(stages):
            stage = stages[step_counter % len(stages)]

            emit_event(agent_name,timeline_event(stage, "timeline", False, *extra_args),socketio,client_id)
            socketio.sleep(seconds=interval)
            emit_event(agent_name,timeline_event(stage, "timeline", True, *extra_args),socketio,client_id)

            step_counter += 1

    except Exception as e:
        appLogger.error({"event": "timeline_thread_error","error": str(e),"traceback": traceback.format_exc()})
