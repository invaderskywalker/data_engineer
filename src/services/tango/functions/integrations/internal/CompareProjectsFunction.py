from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.CompareProjects import Arguments, ReturnDescription, compare_projects_by


COMPARE_BY_PROJECTS = TangoFunction(
    name="compare_projects_by",
    description="""A function that returns a table with descriptive numeric and qualitative details that show
    the distribution of projects based on what you want to compare them by.
    """,
    args=Arguments,
    return_description=ReturnDescription,
    function=compare_projects_by,
    func_type="sql",
    integration="trmeric"
)
