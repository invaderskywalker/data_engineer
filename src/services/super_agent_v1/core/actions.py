# src/services/super_agent_v1/core/actions.py


from typing import Dict, Optional, List
from src.api.logging.AppLogger import appLogger, debugLogger
import traceback
import pandas as pd
import json
import re
import base64
from datetime import datetime
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.utils.helper.event_bus import event_bus
from src.s3.s3 import S3Service
from src.utils.helper.file_analyser import FileAnalyzer
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.helper.decorators import log_function_io_and_time
import uuid
from src.utils.types.actions import *
from src.utils.types.getter import *
from src.database.ai_dao.agent import AIDaoAgentDataGetter
from src.utils.vectorstore.client import TrmericVectorStoreClient
from pathlib import Path
from .style import *


class DataActions:
    def __init__(self, tenant_id: int, user_id: int, agent_name="", session_id="", socketio=None, conversation="", mode = 'research'):
        print("DataActions init ", mode)
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.agent_name = agent_name
        self.session_id = session_id
        self.logInfo = {"tenant_id": tenant_id, "user_id": user_id}
        self.file_analyzer = FileAnalyzer(tenant_id=tenant_id)
        self.s3_service = S3Service()
        self.llm = ChatGPTClient()
        self.socketio = socketio
        self.event_bus = event_bus
        self.conversation = conversation
        # self.web_data_getter = WebDataGetter(
        #     tenant_id=self.tenant_id,
        #     user_id=self.user_id,
        #     session_id=session_id,
        # )
        # self.trucible_actions = TrucibleActions(
        #     tenant_id=self.tenant_id,
        #     user_id=self.user_id,
        #     session_id=session_id,
        #     agent_name='SuperAgent::Trucible'
        # )
        self.vectorstore_client = TrmericVectorStoreClient()
        self.ai_dao_getter = AIDaoAgentDataGetter(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=session_id,
            conversation=conversation,
            mode=mode
        )
        self.mode = mode
        self.fn_maps = {}
        self.fn_maps.update(self.ai_dao_getter.fn_maps)
    

    def get_workspace(self) -> str:
        """
        Per-run working directory where the agent writes like a human researcher.
        """
        # base = f"/tmp/agent_runs/{self.session_id}"
        # os.makedirs(base, exist_ok=True)

        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "../../../../"))
        base = os.path.join(root, f".cache/agent_runs/{self.session_id}")
        os.makedirs(base, exist_ok=True)
        return base
