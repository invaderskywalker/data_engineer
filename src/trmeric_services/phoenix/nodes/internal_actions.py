from ..actions import *

class InternalActionNode:
    def __init__(self, network_data={}):
        self.network_data = network_data
        self.query_functions = {
            "ask_clarifying_question": ask_clarifying_question,
            "general_reply": general_reply
        }
        
        
    def run(self, intent=None):
        """Executes the specified query function based on intent."""
 
        function_name = intent.get("function", "")
        params = intent.get("params", {})

        try:
            func = self.query_functions[function_name]
            result = func(**params)
            return {"data": result, "source": function_name}
        except Exception as e:
            return {"error": f"Query execution failed: {e}"}