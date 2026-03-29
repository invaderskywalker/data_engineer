
from src.trmeric_services.tango.functions.Types import TangoFunction
# from src.trmeric_services.tango.functions.integrations.internal.prompts.IdeaPads import RETURN_DESCRIPTION
from src.trmeric_services.tango.functions.integrations.internal.prompts.Roadmaps import ROADMAP_ARGS, view_roadmaps, RETURN_DESCRIPTION


VIEW_ROADMAPS = TangoFunction(
    name="view_roadmaps",
    description="Roadmaps represent the strategic initiatives of a company. Everything to do with long term investments and plans and strategy. Could be insightful for the ROI of projects, etc.",
    args=ROADMAP_ARGS,
    return_description=RETURN_DESCRIPTION,
    function=view_roadmaps,
    func_type="sql",
    integration="trmeric"
)
