

from .v1.deep_research import DEEP_RESEARCH_CONFIG
from .v1.customer_success import CUSTOMER_SUCCESS_CONFIG
from .v1.analyst import ANALYST_CONFIG
from .v1.ideation_agent import IDEATION_CONFIG

from .trucible_prompt import *
from .analyst_prompt import *
from .allowed_actions_by_mode import *
from .ideation_prompt import *
from .ppt_prompt import *
from .docx_prompt import *

CONFIG_MAP = {
    "deep_research": DEEP_RESEARCH_CONFIG,
    "analyst": ANALYST_CONFIG,
    "customer_success": CUSTOMER_SUCCESS_CONFIG,
    "ideation_agent": IDEATION_CONFIG,
}

