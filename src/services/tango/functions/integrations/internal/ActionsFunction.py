from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.Actions import ARGUMENTS, RETURN_DESCRIPTION, view_actions

VIEW_ACTIONS = TangoFunction(
    name="get_actions",
    description="""A function that returns a table of all the pending action items of the user.""",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_actions,
    func_type="sql",
    integration="trmeric"
)
