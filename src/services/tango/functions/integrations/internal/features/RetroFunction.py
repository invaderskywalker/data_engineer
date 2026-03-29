from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.database.Database import db_instance
from src.database.dao.projects import ProjectsDao


def view_retro_projects( eligibleProjects: list[int], userID: int, tenantID: int, project_id=None):


    eligibleProjects = ProjectsDao.fetchAllRetroProjects(tenant_id=tenantID)
    print("--debug eligibleProjects retro: ", eligibleProjects)
    if project_id:
        main = ProjectsDao.getProjectRetroInsightsV2(project_id, tenantID)
        return db_instance.retrieveSQLQuery(main).formatData()
        
    main = ProjectsDao.getProjectRetroInsightsV2(eligibleProjects, tenantID)
    return db_instance.retrieveSQLQuery(main).formatData()


ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int[]",
        "description": "The specific project ID(s) whose retrospection has been completed and the user queries on.",
        "conditional": "in",
    },
    
]


RETURN_DESCRIPTION = """
    Returns a table with a list of projects whose retro has been done and summary of retro generated insights like story, detailed analysis etc."
"""

VIEW_RETRO_PROJECTS = TangoFunction(
    name="view_retro_projects",
    description=f"""
            This function will be triggered whenever user asks **RETRO** or retrospective(retro)
            related questions. It will give the insights on retro performed.
        """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_retro_projects,
    func_type="sql",
    integration="trmeric"
)
