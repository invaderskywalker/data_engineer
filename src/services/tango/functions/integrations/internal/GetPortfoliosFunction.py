from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetPortfolios import ARGUMENTS, RETURN_DESCRIPTION, view_portfolios

VIEW_PORTFOLIOS = TangoFunction(
    name="view_portfolios",
    description="""A function that returns two tables for roadmap portfolios and project portfolios""",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_portfolios,
    func_type="sql",
    integration="trmeric"
)
