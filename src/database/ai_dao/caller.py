# src/trmeric_database/ai_dao/__init__.py

import json
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from collections import defaultdict

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ProjectsDao, RoadmapDao
from .project import ProjectsDaoV3
from .roadmap import RoadmapDaoV3
from .idea import IdeaDaoV3
from .user import UsersDaoV3
from .bug_enhancement import BugEnhancementDaoV3
from .tango_conversation import TangoConversationDaoV3
from .tango_activitylog import TangoActivityLogDaoV3
from .tango_stats import TangoStatsDaoV3
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions, ModelOptions2
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.helper.common import MyJSON
from src.trmeric_utils.helper.decorators import log_function_io_and_time
from datetime import datetime, date, timedelta
from src.trmeric_utils.helper.event_bus import Event, event_bus




# --------------------------------------------------------------------------
# 1️⃣ DAO Registry (Expandable to all entities)
# --------------------------------------------------------------------------
DAO_REGISTRY = {
    "project": ProjectsDaoV3,
    "roadmap": RoadmapDaoV3,
    "idea": IdeaDaoV3,
    "issues_aka_bug_enhancement": BugEnhancementDaoV3,
    
    "tango_conversation": TangoConversationDaoV3,
    "tango_activity_log": TangoActivityLogDaoV3,
    "tango_stats": TangoStatsDaoV3,
    "users": UsersDaoV3
}
