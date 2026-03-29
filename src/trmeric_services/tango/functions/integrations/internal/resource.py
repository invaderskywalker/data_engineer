from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_database.dao import TenantDao,UsersDao
from src.trmeric_api.logging.AppLogger import appLogger
from collections import defaultdict
from datetime import datetime, timedelta
import json
from src.trmeric_database.Database import db_instance,TrmericDatabase


RETURN_DESCRIPTION = """
Returns a dictionary containing capacity and allocation data for the specified tenant, filtered by data sources, date range, and optional resource name. The structure includes:
- tenant_id (int): The ID of the tenant.
- timeline_view (array): Monthly capacity/allocation view per resource/project.
- available_roles (object): Role-based capacity (total, allocated, available).
- available_skills (object): Skill-based capacity (total, allocated, available).
- resource_details (array): Resource details (name, role, skills, allocation, projects).
- roadmap_allocations (array): Roadmap role allocations.
- utilization_rates (object): Utilization by resource/role/skill.
- demand_supply_gap (object): Gaps between project demand and available capacity.
- hiring_needs (array): Roles requiring external hiring
- primary_skill : The skill group mapping of the resources
- org_team: Resource team level mapping
"""


def get_capacity_data(
    tenantID: int,
    userID: int,
    start_date: str = None,
    end_date: str = None,
    resource_name: str = None,
    eligibleProjects = [],
) -> dict:
    try:
        # Set default dates if not provided
        if start_date is None:
            start_date = datetime.now().strftime("%Y-%m-01")  # Start of current month
        if end_date is None:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = (start_dt + timedelta(days=240)).strftime("%Y-%m-%d")  # ~8 months later
        

        resource_data = TenantDao.fetchResourceDetailsForTenant(tenant_id=tenantID)
        
        query = f"""
            SELECT 
                crt.resource_id, crt.project_name, crt.allocation, 
                crt.start_date, crt.end_date, 
                cr.first_name, cr.last_name, cr.role, cr.skills, cr.primary_skill
            FROM capacity_resource_timeline crt
            JOIN capacity_resource cr ON crt.resource_id = cr.id
            WHERE crt.tenant_id = {tenantID}
            AND cr.is_active = true
        """

        if start_date:
            query += f" AND crt.end_date >= '{start_date}'"
        if end_date:
            query += f" AND crt.start_date <= '{end_date}'"

        
        
        timeline_data = db_instance.retrieveSQLQueryOld(query)
        
        return {
            "timeline_data": timeline_data,
            "resource_data": resource_data
        }
        
        

    except Exception as e:
        appLogger.error({
            "function": "get_capacity_data",
            "event": "FETCH_CAPACITY_DATA_FAILURE",
            "user_id": userID,
            "tenant_id": tenantID,
            "error": str(e)
        })
        return {}

ARGUMENTS = [
    {
        "name": "start_date",
        "type": "string",
        "description": "Start date (YYYY-MM-DD). Optional"
    },
    {
        "name": "end_date",
        "type": "string",
        "description": "End date (YYYY-MM-DD). Optional"
    },
    {
        "name": "resource_name",
        "type": "string",
        "description": "Optional resource name to filter."
    }
]

FETCH_CAPACITY_DATA = TangoFunction(
    name="fetch_capacity_data",
    description="""
        Fetches capacity and allocation data for a tenant, including timeline views, role/skill capacity,
        utilization rates, and demand-supply analysis.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=get_capacity_data,
    func_type="sql",
    integration="trmeric"
)