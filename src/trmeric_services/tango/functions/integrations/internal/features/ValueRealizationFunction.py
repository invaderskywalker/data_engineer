from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao.projects import ProjectsDao


def view_value_realization(eligibleProjects: list[int], userID: int, tenantID: int, project_id=None):


    eligibleProjects = ProjectsDao.fetchValueRealizationProjects(tenant_id=tenantID)
    print("--debug eligibleProjects value rz: ", eligibleProjects)
    if project_id:
        main = ProjectsDao.getProjectValueRealizations(project_id, tenantID)
        return db_instance.retrieveSQLQuery(main).formatData()
        
    main = ProjectsDao.getProjectValueRealizations(eligibleProjects, tenantID)    
    return db_instance.retrieveSQLQuery(main).formatData()

ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int[]",
        "description": "The specific project ID(s) whose value realization has been completed and user queries on.",
        "conditional": "in",
    },
    
]


RETURN_DESCRIPTION = """
    Returns a table with a list of projects and key results whose value realization has been performed and summary of generated insights like 
    achieved value, planned value, key learnings derived out of them.
"""

VIEW_VALUE_REALIZATIONS = TangoFunction(
    name="view_value_realization",
    description=f"""
                This function will be explicitly used when the user asks value realization related questions for a project.
                It will give insights related to value derived from the project/ its key learnings.
            """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_value_realization,
    func_type="sql",
    integration="trmeric"
)
