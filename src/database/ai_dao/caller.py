# src/database/ai_dao/__init__.py


from .project import ProjectsDaoV3
from .roadmap import RoadmapDaoV3
from .idea import IdeaDaoV3
from .user import UsersDaoV3
from .bug_enhancement import BugEnhancementDaoV3
from .tango_conversation import TangoConversationDaoV3
from .tango_activitylog import TangoActivityLogDaoV3
from .tango_stats import TangoStatsDaoV3




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
