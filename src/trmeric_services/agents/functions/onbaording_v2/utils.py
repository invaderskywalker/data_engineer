import threading
import time

class SocketStepsSender:
    def __init__(self, agent_name, socketio, client_id):
        self.step_timeline_key = []
        self.agent_name = agent_name
        self.socketio = socketio
        self.client_id = client_id
        

    def sendSteps(self, key, val, delay=0):
        """
        Sends timeline steps with an optional delay in a separate thread.
        
        Args:
            key (str): The timeline key.
            val (bool): Completion status.
            delay (float): Delay in seconds before emitting the event (default: 0).
        """
        if (key not in self.step_timeline_key) and val:
            return

        def emit_with_delay():
            if delay > 0:
                time.sleep(delay)
            try:
                self.socketio.emit(
                    self.agent_name,
                    {
                        "event": "timeline",
                        "data": {"text": key, "key": key, "is_completed": val}
                    },
                    room=self.client_id
                )
                self.step_timeline_key.append(key)
            except Exception as e:
                print(f"Error emitting event: {e}")

        # Run emission in a separate thread
        threading.Thread(target=emit_with_delay, daemon=True).start()