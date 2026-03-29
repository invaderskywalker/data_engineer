# Import event registrars from specialized modules
from .connection_events import register_connection_events
from .agent_events import register_agent_events
from .function_events import register_function_events
from .state_events import register_state_events
from .audio_events import register_audio_events


def init_websocket_events(socketio):
    """Initialize and register all WebSocket events with the Socket.IO instance."""
    print("Initializing WebSocket events")
    
    # Register all event handlers
    register_connection_events(socketio)
    register_agent_events(socketio)
    register_function_events(socketio)
    register_state_events(socketio)
    # register_audio_events(socketio)
    
    print("All WebSocket events registered successfully")

