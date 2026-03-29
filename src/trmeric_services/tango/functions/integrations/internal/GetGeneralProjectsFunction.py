from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetGeneralProjects import ARGUMENTS, RETURN_DESCRIPTION, view_projects

VIEW_PROJECTS = TangoFunction(
    name="view_projects",
    description="A function to use when the user inquires anything regarding projects - including their spend, their scopes, team info, team member utilization etc.",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_projects,
    func_type="sql",
    integration="trmeric"
)
