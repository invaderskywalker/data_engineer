from .base import ChatService
import os
import re
import json
import traceback
import concurrent.futures
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from .base import ChatService
import datetime
import json
from src.trmeric_services.journal.Activity import detailed_activity, activity, record
from src.trmeric_utils.json_parser import *
from src.trmeric_services.phoenix.queries import KnowledgeQueries

class DiscoveryChat(ChatService):
    def __init__(self, request_info, session_id, chat_type):
        pass

    def start_session(self, chat, **kwargs):

        print("\n--debug DiscoveryChat startSession------roadmapInfo", chat.roadmapInfo is not None)
        content = getPromptIfStarterRoadmap(chat.roadmapInfo) if chat.roadmapInfo is not None else getPromptIfNoRoadmap()
        
        return {
            "role": "system",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }

    def generate_next_question(self, chat, **kwargs):
        messages = chat.getConvMessagesArr()
        print("\n\n---deubg messages discovery", len(messages))

        if chat.chat_type == 1 and len(messages) == 2 and chat.roadmapInfo is None:
            return '''<|end_header_id|>

Here's the first question:

```json
{
    "question": "Excellent choice! Collaborating with the right tech provider can be transformative. Let's narrow things down. Does the nature of work or project be broadly fit into any of the below listed classification?",
    "options": [
        "Data & analytics",
        "Product engineering",
        "Cloud Transformation",
        "IT Infra & Operations",
        "Application maintenance & support",
        "Business applications (ERP, HR etc.)",
        "CX - (Saleforce, Web transfromation etc.)",
        "Cannot be classified into above buckets"
    ],
    "hint": [],
    "question_progress": "0%",
    "counter": 0,
    "last_question_progress": "0%",
    "topics_answered_by_user": {
        "nature of the project": "false",
        "the project's broad objective for the customer": "false",
        "the technology, tools, frameworks, and solutions to be used in the project by the provider": "false",
        "specific business domain or business process knowledge or capabilities required by the provider": "false",
        "preferred location for the provider": "false",
        "new project or an ongoing project": "false",
        "timeline of the project": "false",
        "budget/funding of the project": "false",
        "definition of 'success' for this project": "false",
        "what evaluation criteria will be used to evaluate the provider": "false",
        "if the user wants to share more about the project": "false"
    },
    "should_stop": "false",
    "should_stop_reason": "",
    "are_all_topics_answered_by_user": "false"
}
```

Please respond with one of the options, and I'll proceed with the next question!
'''

    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender):
        return {}