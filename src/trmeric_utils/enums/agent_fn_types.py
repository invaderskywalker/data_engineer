
from enum import Enum

class AgentFnTypes(Enum):
    DATA_GETTER = "data-getter"
    ACTION_TAKER = "action-taker"
    ACTION_TAKER_UI = "action-taker-ui"
    SKIP_FINAL_ANSWER = "skip-final-answer"

    
    @classmethod
    def has_role(cls, role):
        return role in cls._value2member_map_


class AgentReturnTypes(Enum):
    RETURN = "return"
    YIELD = "yield"
    
    @classmethod
    def has_role(cls, role):
        return role in cls._value2member_map_