from src.trmeric_services.tango.functions.Types import TangoFunction


def answer_follow_up(**kwargs):
    return "The question can be answered by the data already present in the conversation. Please follow-up with the answer."


ANSWER_FOLLOW_UP = TangoFunction(
    name="answer_follow_up",
    description="If the user's question is answerable by the data already present in the conversation, use this function to request the Copilot to follow-up with the answer.",
    args=[],
    return_description="Returns a message to the Copilot to follow-up with the answer.",
    func_type="general",
    function=answer_follow_up,
    integration="General"
)
