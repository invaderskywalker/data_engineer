
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
import traceback, json

def _check_meaningful_activities(activities: str, session_id: str, user_id: int, tenant_id: int) -> bool:
    """
    Determine if session has meaningful activities using intelligent filtering:
    1. Quick character-based filtering for obvious cases
    2. LLM-based decision for borderline cases
    """
    print(f"[MEANINGFUL_CHECK] Starting check for session {session_id} with {len(activities)} total activities")

    total_content_length = len(activities)
    if total_content_length > 3000:  # Definitely meaningful
        print(f"[MEANINGFUL_CHECK] High content length ({total_content_length}), definitely meaningful")
        return True
    elif total_content_length < 200:  # Definitely not meaningful  
        print(f"[MEANINGFUL_CHECK] Low content length ({total_content_length}), not meaningful")
        return False
    
    # Borderline case - use LLM to decide
    print(f"[MEANINGFUL_CHECK] Borderline content length ({total_content_length}), using LLM to decide")
    return _llm_meaningful_check(activities, session_id, user_id, tenant_id)


def _llm_meaningful_check(activities: str, session_id: str, user_id: int, tenant_id: int) -> bool:
    """Use LLM to determine if activities are meaningful enough for vector analysis"""
    try:

        system_prompt = """You are analyzing session activities to determine if they contain meaningful work worth tracking in organizational transformation vectors.

MEANINGFUL ACTIVITIES (return true):
- User created, edited, or analyzed substantial content
- Strategic planning, roadmap development, or goal setting
- Problem-solving with significant input/output transformation
- Decision-making with analysis or recommendations
- Knowledge creation, documentation, or insights
- Project management with substantial data
- Any work that advances organizational objectives

NOT MEANINGFUL (return false):
- Simple data lookups or basic queries
- Routine status checks or monitoring
- Minimal input/output with trivial content
- Basic navigation or system interactions
- Empty or placeholder activities
- Activities with no substantial user value

Return only a JSON boolean response:
{"meaningful": true} or {"meaningful": false}"""
        user_message = f"Analyze these session activities:\n\n{activities}"

        llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
        response = llm.run(
            ChatCompletion(system=system_prompt, prev=[], user=user_message),
            ModelOptions(model="gpt-4.1", max_tokens=50, temperature=0.1),
            f"meaningful_check_{session_id}"
        )
        
        result = extract_json_after_llm(response)
        is_meaningful = result.get("meaningful", False)
        
        print(f"[MEANINGFUL_CHECK] LLM decision: {'meaningful' if is_meaningful else 'not meaningful'}")
        return is_meaningful
        
    except Exception as e:
        appLogger.error({
            "event": "llm_meaningful_check_error",
            "session_id": session_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        # Default to meaningful on error to avoid losing potentially valuable data
        print(f"[MEANINGFUL_CHECK] LLM error, defaulting to meaningful: {str(e)}")
        return True