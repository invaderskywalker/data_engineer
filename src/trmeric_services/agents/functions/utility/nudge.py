

from src.trmeric_services.agents.core.agent_functions import AgentFunction

def utility_agent_nudge(
    tenantID: int,
    userID: int,
    **kwargs
):
    prompt = """
        Looking at the ability of utiity agent and the conversation:
        Recomend the user to take actions allowed by utility agent. 
    """
    return prompt


RETURN_DESCRIPTION = """
    
"""

ARGUMENTS = []


UTILITY_AGENT_NUDGE = AgentFunction(
    name="utility_agent_nudge",
    description="""
        This function should be able to inform about the abilities of this agent.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=utility_agent_nudge,
)
