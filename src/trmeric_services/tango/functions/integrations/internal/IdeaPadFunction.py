from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.IdeaPads import ARGUMENTS, RETURN_DESCRIPTION, view_ideas


VIEW_IDEAS = TangoFunction(
    name="view_ideas",
    description="View all ideas you have by a portfolio or just all of them at once",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_ideas,
    func_type = "sql",
    integration="trmeric"
)