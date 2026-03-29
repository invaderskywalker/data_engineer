
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler
)
from src.trmeric_database.Database import db_instance


ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int[]",
        "description": "The IDs of which projects you want to get the actions of - if you want all projects, just input None.",
        "conditional": "in",
    },
    {
        "name": "risk_tag",
        "type": "str[]",
        "description": "The tags that you want to filter by. If you want all tags, just input None.",
        "options": ["Cost", "Delay", "Risk"],
        "conditional": "in",
    },
    {
        "name": "priority",
        "type": "str[]",
        "description": "The priority of the actions that you want to get. If you want all priorities, just input None.",
        "options": ["High", "Medium", "Low"],
        "conditional": "in",
    },
]


def getBaseQuery(tenant_id):
    query = f"""
WITH BaseAction as (
		SELECT *,
        actions_actions.tenant_id_id as tenant,
		actions_actions.tag as risk_tag
		FROM actions_actions 
		LEFT JOIN actions_insightsprojectspace on actions_insightsprojectspace.id = actions_actions.id
		LEFT JOIN actions_insights on actions_insights.id = actions_actions.id
		LEFT JOIN actions_actioncomments on actions_insights.id = actions_actioncomments.id
	), Action as (
        Select * from BaseAction
        Where tenant = {tenant_id}
    ) SELECT * from Action
"""
    return query


def view_actions(tenantID: int, project_id=None, risk_tag=None, priority=None, **kwargs):

    handler = SQL_Handler(getBaseQuery(tenantID))

    project_id_arg = next(arg for arg in ARGUMENTS if arg["name"] == "project_id")
    handler.handleArguments(project_id_arg, project_id)

    tag_arg = next(arg for arg in ARGUMENTS if arg["name"] == "risk_tag")
    handler.handleArguments(tag_arg, tag_arg)

    priority_arg = next(arg for arg in ARGUMENTS if arg["name"] == "priority")
    handler.handleArguments(priority_arg, priority)
    query = handler.createSQLQuery()
    response = db_instance.retrieveSQLQuery(query).formatData()
    return response


RETURN_DESCRIPTION = """
Returns a table with a list of actions and their details.
"""
