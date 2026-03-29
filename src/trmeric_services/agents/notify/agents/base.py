# base.py

from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.web.WebSearchAgent import WebSearchAgent

class BaseNotifyAgent:
    def __init__(self, name, tenant_id, user_id):
        self.name = name
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=15000,
            temperature=0.1
        )
        self.logInfo = {
            "tenant_id": tenant_id,
            "user_id": user_id
        }
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.websearch_agent = WebSearchAgent()
        print(f"Notification system initialized {self.name}")