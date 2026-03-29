from typing import Dict, Generator
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_api.logging.AppLogger import appLogger
import json
import re
import traceback
from datetime import datetime

# Constants
MIN_BUFFER_SIZE = 30
DEFAULT_MODEL = "gpt-4.1"
MAX_TOKENS = 30000

class ResponseGenerator:
    """Generates polished responses by synthesizing results."""
    def __init__(self, config: Dict, context_builder, llm, log_info: Dict):
        self.config = config
        self.context_builder = context_builder
        self.llm = llm
        self.log_info = log_info

    def generate_response(self, results: Dict, plan: Dict, query: str) -> Generator[str, None, None]:
        """Synthesizes results into a polished response using the configured prompt."""
        socket_sender = self.context_builder.socket_sender
        socket_sender.sendSteps("🔗 Synthesizing Insights", False)
        
        response_type = plan["response_type"]
        system_prompt = self.config["prompts"][response_type]["template"].format(
            query=query,
            context=self.context_builder.build_context(),
            results=json.dumps(results, indent=2),
            current_date=datetime.now().date().isoformat(),
            tenant_type=self.context_builder.tenant_type
        )
        
        chat_completion = ChatCompletion(system=system_prompt, prev=[], user=query)
        buffer = ""
        word_boundary = re.compile(r'[\s.,!?;]')
        
        try:
            for chunk in self.llm.runWithStreaming(chat_completion, ModelOptions(model=DEFAULT_MODEL, max_tokens=MAX_TOKENS), 'trucible::combine', logInDb=self.log_info):
                buffer += chunk
                if len(buffer) >= MIN_BUFFER_SIZE or (buffer and word_boundary.search(buffer)):
                    yield buffer
                    buffer = ""
                    if self.context_builder.socketio:
                        self.context_builder.socketio.sleep(0.01)
            if buffer:
                yield buffer
            socket_sender.sendSteps("🔗 Synthesizing Insights", True)
        except Exception as e:
            appLogger.error({"function": "combine_results_error", "error": str(e), "traceback": traceback.format_exc()})
            yield f"Error synthesizing response: {str(e)}"
            