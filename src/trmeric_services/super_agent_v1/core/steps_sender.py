import threading
import time

class SocketStepsSender:
    def __init__(self, agent_name, socketio, client_id):
        self.step_timeline_key = []
        self.agent_name = agent_name
        self.socketio = socketio
        self.client_id = client_id
        
        

    def sendSteps(self, key, val,time=0, delay=0):
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
                if self.socketio:
                    self.socketio.sleep(seconds = delay)
            try:
                if self.socketio:
                    self.socketio.emit(
                        "agentic_timeline",
                        {
                            "agent": self.agent_name,
                            "event": "timeline",
                            "data": {"text": key, "key": key, "is_completed": val},
                            "time": time
                        },
                        room=self.client_id
                    )
                self.step_timeline_key.append(key)
            except Exception as e:
                print(f"Error emitting event: {e}")

        # Run emission in a separate thread
        threading.Thread(target=emit_with_delay, daemon=True).start()
        
        
    def sendThought(self,chunk):
        if self.socketio:
            self.socketio.emit(
                "agentic_timeline",
                {
                    "agent": self.agent_name,
                    "event": "thought",
                    "data": {"chunk": chunk},
                },
                room=self.client_id
            )
        
        
    def sendError(self,key,function=None,delay=0):
        
        """Send the error logged in steps in workflow for a feature"""
        
        def emit_with_delay():
            if delay > 0:
                self.socketio.sleep(seconds = delay)
            try:
                self.socketio.emit(
                    "general_error",
                    {
                        "agent": self.agent_name,
                        "event": function,
                        "data": {"text": key, "key": key}
                    },
                    room = self.client_id
                )
            except Exception as e:
                print(f"Error emitting event: {e}")
                
        
        threading.Thread(target=emit_with_delay, daemon=True).start()