import os
import re
import json
import datetime
from .base import ChatService
from src.trmeric_utils.json_parser import *
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *


class OnboardChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        pass

    def start_session(self, chat,**kwargs):
        systemMessage = {
            "role": "system",
            "content": onboardProcessPrompt(json.dumps(chat.context.get("persona", {}) or {})),
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }
        return systemMessage

    def generate_next_question(self, chat, **kwargs):
        messages = chat.getConvMessagesArr()
        if chat.chat_type == 4 and len(messages) == 2:
            return '''

Here's the first question:
```
{
    "question": "To get started, could you please share the top pain points you are looking to solve by using Trmeric?", 
    "options": [], 
    "hint": ["For example, if you're in the healthcare domain, you might mention challenges like reducing operational inefficiencies or improving patient care delivery."],
    "question_progress": "0%", 
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": [],
    "should_stop": false,
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": false
}
```

Please respond with your answer, and I'll proceed with the next question!'''


    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender):
        messages = [
            {
                "role": "user",
                "content": createOnboardBriefFromQNA(
                    chat.fetchOnlyQna(), "Trmeric",chat.context.get("persona",{}) or {}
                ),
            }
        ]
        return messages