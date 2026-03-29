from src.trmeric_services.tango.functions.Types import TangoFunction
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from src.trmeric_database.dao import TenantDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.Database import db_instance,TrmericDatabase


RETURN_DESCRIPTION = """
    Returns a table which contains the following structure:
    - name (the name of the program)
    - created_on (the date when the program was created)
    - number of projects (the number of projects associated with the program)
    - other relevant information about the projects associated with the program, such as
        - project_name (the name of the project)
        - project_id (the id of the project)
        - start_date (the start date of the project)
        - end_date (the end date of the project)
        - project_status (the status of the project)
"""


def fetchFullProgramsInfo(tenant_id):
    query = f"""
        SELECT 
            pp.id,
            pp.name,
            pp.created_on,
            u.first_name AS created_by_first_name,
            u.last_name AS created_by_last_name,
            STRING_AGG(wp.title, ', ') AS project_names,
            ARRAY_AGG(wp.delivery_status) AS project_delivery_statuses,
            ARRAY_AGG(wp.scope_status) AS project_scope_statuses,
            ARRAY_AGG(wp.spend_status) AS project_spend_statuses,
            SUM(COALESCE(wp.total_external_spend, 0)) AS total_project_budget,
            COUNT(DISTINCT wp.id) AS project_count,
            ARRAY_AGG(
                CASE 
                    WHEN wp.project_manager_id_id IS NOT NULL 
                    THEN jsonb_build_object(
                        'project_title', wp.title,
                        'manager_first_name', pm.first_name,
                        'manager_last_name', pm.last_name
                    )
                    ELSE NULL
                END
            ) FILTER (WHERE wp.project_manager_id_id IS NOT NULL) AS project_managers
        FROM 
            program_program pp
        LEFT JOIN 
            users_user u ON pp.created_by_id = u.id
        LEFT JOIN 
            workflow_project wp ON wp.program_id = pp.id 
                AND wp.archived_on IS NULL 
                AND wp.parent_id IS NOT NULL
        LEFT JOIN 
            users_user pm ON wp.project_manager_id_id = pm.id
        WHERE 
            pp.tenant_id = {tenant_id}
        GROUP BY 
            pp.id, pp.name, pp.created_on, u.first_name, u.last_name
    """
    return db_instance.retrieveSQLQueryOld(query)




def view_programs(
    tenantID: int,
    userID: int,
    # start_date: str = None,
    # end_date: str = None,
    # resource_name: str = None,
    # eligibleProjects = [],
    **kwargs
):
    try:
        print("--debug [View Programs] -- tenantID, userID", tenantID, userID)
        # Set default dates if not provided
        # if start_date is None:
        #     start_date = datetime.now().strftime("%Y-%m-01")  # Start of current month
        # if end_date is None:
        #     start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        #     end_date = (start_dt + timedelta(days=240)).strftime("%Y-%m-%d")  # ~8 months later
        
        programs_data = fetchFullProgramsInfo(tenantID)
        
        return programs_data
        
        
    except Exception as e:
        appLogger.error({
            "function": "view_programs",
            "event": "VIEW_PROGRAMS_FAILURE",
            "user_id": userID,
            "tenant_id": tenantID,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {}

ARGUMENTS = [
    {
        "name": "program_id",
        "type": "int[]",
        "description": "The specific program ID(s) that the user is interested in.",
        "conditional": "in"
    }
]

VIEW_PROGRAMS = TangoFunction(
    name="view_programs",
    description="""
        Deep analysis of programs providing detailed per-project insights and trends based on the user query.
        Program is a grouping of projects, often related to yearly planning or specific initiatives.
        
        Programs are like plans for ongoing and upcoming projects, and multiple projects can share the same program_id.
        A project is associated with a program through the program_id field.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_programs,
    func_type="sql",
    integration="trmeric"
)