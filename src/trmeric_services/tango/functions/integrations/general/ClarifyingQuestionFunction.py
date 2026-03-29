from src.trmeric_services.tango.functions.Types import TangoFunction


def ask_clarifying_question(clarifying_question: str, **kwargs):
    return "Ask the user the following clarifying question: " + clarifying_question


ASK_CLARIFY_QUESTION = TangoFunction(
    name="ask_clarifying_question",
    description="If the user's question is unclear or ambiguous, use this function to ask the user a clarifying question.",
    args=[
        {
            "name": "clarifying_question",
            "type": "str",
            "description": "The clarifying question to ask the user.",
        }
    ],
    return_description="Returns the question that the Copilot should ask the user.",
    func_type="general",
    function=ask_clarifying_question,
    integration="General"
)
