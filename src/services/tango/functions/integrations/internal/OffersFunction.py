from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.prompts.Offers import ARGUMENTS, RETURN_DESCRIPTION, view_offers

VIEW_OFFERS = TangoFunction(
    name="view_offers",
    description="""A function that returns a table of all the offers of the user""",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_offers,
    func_type="sql",
    integration="trmeric"
)
