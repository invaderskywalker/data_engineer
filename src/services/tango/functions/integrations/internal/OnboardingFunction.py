import traceback
from src.ml.llm.Types import ModelOptions
from src.api.logging.AppLogger import appLogger
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.utils.json_parser import extract_json_after_llm
from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.OnboardProcess import onboardProcessPrompt


def process_onboarding(
        eligibleProjects: list[int],
        tenantID: int,
        userID: int,
        user_query: str,
        *args,
        **kwargs
    ):
    """
    Handles the onboarding process by interacting with the user.
    Sequentially asks questions based on predefined prompts to gather information.

    Args:
        tenant_id (int): The tenant ID for the onboarding process.
        user_id (int): The user ID for the onboarding process.
        user_query (str): The user's input for onboarding.

    Returns:
        dict: Processed JSON with onboarding responses or an error message.
    """
    try:
        # Normalize user input for case-insensitive matching
        user_query_lower = user_query.strip().lower()

        # Check if the input signals onboarding intent
        onboarding_keywords = [
            "start onboarding",
            "onboard",
            "let's start the onboarding process",
            "begin onboarding",
            "start the onboarding process"
        ]

        if not any(keyword in user_query_lower for keyword in onboarding_keywords):
            return {
                "message": "No onboarding process triggered. Provide onboarding-related input."
            }

        # Set up LLM client and model options
        llm = ChatGPTClient()
        model_options = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.3
        )

        # Generate prompt
        prompt = onboardProcessPrompt(user_query)

        # Run the LLM with the generated prompt
        response = llm.run(
            prompt,
            model_options,
            "onBoardProcess",
            logInDb={
                "tenant_id": tenantID,
                "user_id": userID
            }
        )

        # Extract JSON from the LLM response
        return extract_json_after_llm(response)

    except Exception as e:
        print("--debug error in onboarding process", e)
        appLogger.error({
            "event": "process_onboarding error",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "error": "An error occurred during the onboarding process.",
            "details": str(e)
        }

#function not in use
ONBOARD_PROCESS = TangoFunction(
    name="process_onboarding",
    description="""
        You are Tango, an AI assistant. Your task is to ask users questions to understand their business
        better through a sequential onboarding process.
    """,
    args=[
        {
            "name": "user_query",
            "type": "str",
            "description": "The user's input for onboarding."
        },
    ],
    return_description="The user's responses captured during the onboarding process.",
    function=process_onboarding,
    func_type="general",
    integration="trmeric"
)
