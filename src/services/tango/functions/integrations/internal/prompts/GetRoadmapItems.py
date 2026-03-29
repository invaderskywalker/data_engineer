
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.database.Database import db_instance
from src.database.dao.portfolios import PortfolioDao
from src.database.dao.roadmap import RoadmapDao
from src.trmeric_services.tango.functions.Types import TangoFunction


def view_roadmap_items(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    roadmap_id=None,
    **kwargs
):
    print("in view_roadmap_items ", tenantID, userID)
    roadmap_items = RoadmapDao.getRoadmapItems(tenant_id=tenantID)


RETURN_DESCRIPTION = """
    This function returns data for roadmap items
"""

ARGUMENTS = [
    {
        "name": "roadmap_id",
        "type": "int[]",
        "description": "The specific roadmap id(s) that the user is interested in.",
        "conditional": "in",
    },
]


VIEW_ROADMAP_ITEMS = TangoFunction(
    name="view_roadmap_items",
    description="""
    A function that returns the roadmap items 
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_roadmap_items,
    func_type="sql",
    integration="trmeric"
)
