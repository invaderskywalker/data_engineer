import threading
from typing import Callable, Dict, List, Any
from dataclasses import dataclass

@dataclass
class Event:
    type: str
    payload: Dict[str, Any]
    timestamp: float = None  # Auto-set on dispatch

class EventBus:
    _instance: 'EventBus' = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EventBus, cls).__new__(cls)
                    cls._instance._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
                    cls._instance._init_done = False
        return cls._instance

    def _namespaced_type(self, event_type: str, session_id: str = None) -> str:
        """Helper: Namespace events by session (e.g., 'STEP_UPDATE:session_123')."""
        if session_id:
            return f"{event_type}:{session_id}"
        return event_type  # Global/wildcard

    def subscribe(self, event_type: str, session_id: str = None, callback: Callable[[Event], None] = None) -> str:
        """Subscribe with optional session namespacing."""
        namespaced_type = self._namespaced_type(event_type, session_id)
        if namespaced_type not in self._subscribers:
            self._subscribers[namespaced_type] = []
        if callback:
            self._subscribers[namespaced_type].append(callback)
        return namespaced_type  # Return for easy unsubscribe

    def unsubscribe(self, event_type: str, session_id: str = None, callback: Callable[[Event], None] = None):
        """Unsubscribe with optional session namespacing."""
        namespaced_type = self._namespaced_type(event_type, session_id)
        if namespaced_type in self._subscribers and callback:
            self._subscribers[namespaced_type] = [
                cb for cb in self._subscribers[namespaced_type] if cb != callback
            ]

    def dispatch(self, event_type: str, payload: Dict[str, Any], session_id: str = None):
        """Dispatch with optional session targeting (filters in callbacks)."""
        import time
        event = Event(type=event_type, payload={**payload, 'session_id': session_id}, timestamp=time.time())
        # Dispatch to namespaced type if session-specific
        primary_type = self._namespaced_type(event_type, session_id)
        with self._lock:
            # Call subscribers for exact match
            for sub_type, subscribers in list(self._subscribers.items()):
                if sub_type == primary_type:
                    for callback in subscribers:
                        try:
                            callback(event)
                        except Exception as e:
                            print(f"Error in callback for {event_type}: {e}")
            # Optional: Broadcast to globals/wildcards (e.g., 'STEP_UPDATE:*')
            wildcard_type = f"{event_type}:*"
            if wildcard_type in self._subscribers:
                for callback in self._subscribers[wildcard_type]:
                    try:
                        callback(event)
                    except Exception as e:
                        print(f"Error in wildcard callback for {event_type}: {e}")

# Global accessor
event_bus = EventBus()
