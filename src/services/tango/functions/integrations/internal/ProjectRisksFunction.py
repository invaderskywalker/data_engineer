from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.database.Database import db_instance


def view_projects_risks(
    eligibleProjects: list[int],
    userID: int,
    tenantID: int,
    project_id=None,
):
    if project_id:
        main = getBaseQuery(project_id, tenantID)
        return db_instance.retrieveSQLQuery(main).formatData()
        
    main = getBaseQuery(eligibleProjects, tenantID)
    return db_instance.retrieveSQLQuery(main).formatData()


ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int[]",
        "description": "The specific project ID(s) that the user is interested in.",
        "conditional": "in",
    }
]


def getBaseQuery(eligibleProjects, tenant_id):
    project_ids_str = f"({', '.join(map(str, eligibleProjects))})" 
    query = f"""
            SELECT wp.id as project_id, wp.title, wpr.description as risk_description, wpr.impact as risk_impact, wpr.mitigation as risk_mitigation 
            FROM workflow_projectrisk as wpr
            join workflow_project as wp on wp.id = wpr.project_id
            where wp.tenant_id_id = {tenant_id}
            and wpr.project_id IN {project_ids_str}
        """
    return query


RETURN_DESCRIPTION = """
    Returns a table with a list of risks and their description and mitigations.
"""

VIEW_PROJECT_RISKS = TangoFunction(
    name="view_projects_risks",
    description="A function to use when the user inquires anything regarding projects - including their spend, their scopes, etc.",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_projects_risks,
    func_type="sql",
    integration="trmeric"
)
