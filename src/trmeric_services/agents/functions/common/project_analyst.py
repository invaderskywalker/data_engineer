# from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.trmeric_api.types.TabularData import TabularData
from src.trmeric_database.Database import db_instance
from src.trmeric_services.agents.core import AgentFunction, SQL_Handler



def view_projects(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    project_id=None,
    start_date='',
    end_date='',
    description=None,
    objectives=None,
    location=None,
    percentage_completion=None,
    project_type=None,
    project_state=None,
    portfolio_id=None,
    roadmap_id=None,
    project_manager_id=None,
    provider_id=None,
    tech_stack=None,
    kpis=None,
    delivery_status=None,
    scope_status=None,
    spend_status=None,
    planned_spend=None,
    actual_spend=None,
    overrun=None
) -> list[TabularData]:
    sql_handler = SQL_Handler(getBaseQuery(
        eligibleProjects, tenant_id=tenantID))
    project_id_arg = next(arg for arg in ARGUMENTS if arg["name"] == "project_id")
    sql_handler.handleArguments(project_id_arg, project_id)

    start_date_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "start_date")
    sql_handler.handleArguments(start_date_arg, start_date)

    end_date_arg = next(arg for arg in ARGUMENTS if arg["name"] == "end_date")
    sql_handler.handleArguments(end_date_arg, end_date)


    # objectives_arg = next(arg for arg in ARGUMENTS if arg["name"] == "objectives")
    # sql_handler.handleArguments(objectives_arg, objectives)

    # percentage_completion_arg = next(arg for arg in ARGUMENTS if arg["name"] == "percentage_completion")
    # sql_handler.handleArguments(percentage_completion_arg, percentage_completion)

    # project_type_arg = next(arg for arg in ARGUMENTS if arg["name"] == "project_type")
    # sql_handler.handleArguments(project_type_arg, project_type)

    # project_state_arg = next(
    #     arg for arg in ARGUMENTS if arg["name"] == "project_state")
    # sql_handler.handleArguments(project_state_arg, project_state)

    # portfolio_id_arg = next(arg for arg in ARGUMENTS if arg["name"] == "portfolio_id")
    # sql_handler.handleArguments(portfolio_id_arg, portfolio_id)

    # roadmap_id_arg = next(
    #     arg for arg in ARGUMENTS if arg["name"] == "roadmap_id")
    # sql_handler.handleArguments(roadmap_id_arg, roadmap_id)

    # project_manager_id_arg = next(
    #     arg for arg in ARGUMENTS if arg["name"] == "project_manager_id"
    # )
    # sql_handler.handleArguments(project_manager_id_arg, project_manager_id)

    # provider_id_arg = next(
    #     arg for arg in ARGUMENTS if arg["name"] == "provider_id")
    # sql_handler.handleArguments(provider_id_arg, provider_id)

    # tech_stack_arg = next(
    #     arg for arg in ARGUMENTS if arg["name"] == "tech_stack")
    # sql_handler.handleArguments(tech_stack_arg, tech_stack)

    where_conditions = sql_handler.generateConditionals()

    main = (
        getBaseQuery(eligibleProjects, tenant_id=tenantID)
        + MAIN_QUERY
        + where_conditions
    )
    auxilary = (
        getBaseQuery(eligibleProjects, tenant_id=tenantID)
        + AUXILARY_QUERY
        + where_conditions
        + ")"
        + AUXILARY_QUERY_END
    )
    executedMain = db_instance.retrieveSQLQuery(main).formatData()
    executedAuxilary = db_instance.retrieveSQLQuery(auxilary).formatData()
    return executedMain + "\n\n" + executedAuxilary


ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int[]",
        "description": "The specific project ID(s) that the user is interested in.",
        "conditional": "in",
    },
    {
        "name": "start_date",
        "type": "{ 'lower_bound': 'str', 'upper_bound': 'str' }",
        "description": "The start date of the project(s) that the user is interested in. Must be in the format 'YYYY-MM-DD'. Essentially, this is a range of dates that the user can choose. If you choose None, which is the default, then the start date will be the earliest date available.",
        "conditional": "date-bound",
    },
    {
        "name": "end_date",
        "type": "{ 'lower_bound': 'str', 'upper_bound': 'str' }",
        "description": "The end date of the project(s) that the user is interested in. Must be in the format 'YYYY-MM-DD'. Essentially, this is a range of dates that the user can choose. If you choose None, which is the default, then the end date will be the latest date available.",
        "conditional": "date-bound",
    },
   
    {
        "name": "percentage_completion",
        "type": "{ 'lower_bound': 'int', 'upper_bound': 'int' }",
        "description": "The percentage completion of the project(s) that the user is interested in. Essentially, this is a range of percentages that the user can choose. If you choose None, which is the default, then the percentage completion will be the earliest percentage available.",
        "conditional": "range",
    },
    {
        "name": "project_type",
        "type": "str[]",
        "description": "Any of the project types you want to filter the projects by. Will return all projects that have ANY ONE of the project types you provide.",
        "options": ["Transform", "Run", "Innovate"],
        "conditional": "in",
    },
    {
        "name": "portfolio_id",
        "type": "int[]",
        "description": "Any of the portfolio IDs you want to filter the projects by. Will return all projects that have ANY ONE of the portfolio IDs you provide.",
        "conditional": "in",
    },
    {
        "name": "roadmap_id",
        "type": "int[]",
        "description": "Any of the roadmap IDs you want to filter the projects by. Will return all projects that have ANY ONE of the roadmap IDs you provide.",
        "conditional": "in",
    },
    {
        "name": "project_manager_id",
        "type": "int[]",
        "description": "Any of the project manager IDs you want to filter the projects by. Will return all projects that have ANY ONE of the project manager IDs you provide.",
        "conditional": "in",
    },
    {
        "name": "provider_id",
        "type": "int[]",
        "description": "Any of the provider IDs you want to filter the projects by. Will return all projects that have ANY ONE of the provider IDs you provide.",
        "conditional": "in",
    },
    {
        "name": "tech_stack",
        "type": "str[]",
        "description": "Any of the technologies you want to filter the projects by. Will return all projects that have ANY ONE of the technologies you provide.",
        "conditional": "like",
        "reverse": True,
    },
]


DETAILS_QUERY = """
, TechStacks AS (
    SELECT
        tech_stack,
        COUNT(*) as tech_stack_count
    FROM (
        SELECT
            unnest(tech_stack) as tech_stack
        FROM Base
    ) as tech_stack_categories
    GROUP BY tech_stack
), ProjectCounts AS (
    SELECT
        project_type,
        COUNT(*) as project_count
    FROM Base
	WHERE project_type != 'Null'
    GROUP BY project_type
), SpendStatuses AS (
    SELECT
        spend_status,
        COUNT(*) as spend_status_counts
    FROM Base
	WHERE spend_status != 'Null'
    GROUP BY spend_status
),DeliveryStatuses AS (
    SELECT
        delivery_status,
        COUNT(*) as delivery_status_counts
    FROM Base
	WHERE delivery_status != 'Null'
    GROUP BY delivery_status
), ScopeStatuses AS (
    SELECT
        scope_status,
        COUNT(*) as scope_status_counts
    FROM Base
	WHERE scope_status != 'Null'
    GROUP BY scope_status
),
Portfolios AS (
    SELECT
        MAX(portfolio) as portfolio,
        COUNT(*) as portfolio_count
    FROM Base
	Where portfolio_id BETWEEN 0 AND 2147483647
    GROUP BY portfolio_id
)
SELECT 
    COUNT(*) as total_projects,
    AVG(actual_spend) as average_actual_spend,
    SUM(actual_spend) as total_actual_spend,
    AVG(planned_spend) as average_planned_spend,
    SUM(planned_spend) as total_planned_spend,
    AVG(overrun) as average_overrun,
    SUM(overrun) as total_overrun,
    (
        SELECT jsonb_object_agg(project_type, project_count)
        FROM ProjectCounts
    ) as project_type_counts,
	(
        SELECT jsonb_object_agg(delivery_status, delivery_status_counts)
        FROM DeliveryStatuses
    ) as delivery_status_counts,
	(
        SELECT jsonb_object_agg(spend_status, spend_status_counts)
        FROM SpendStatuses
    ) as delivery_status_counts,
	(
        SELECT jsonb_object_agg(scope_status, scope_status_counts)
        FROM ScopeStatuses
    ) as scope_status_counts,
	(
        SELECT jsonb_object_agg(tech_stack, tech_stack_count)
        FROM TechStacks
    ) as tech_stack_counts,
	(
        SELECT jsonb_object_agg(portfolio, portfolio_count)
        FROM Portfolios
    ) as portfolios	
FROM 
    Base;
"""


def getBaseQuery(eligibleProjects, tenant_id=1):
    query = f"""
        With TheBase as (
                SELECT
                        MAX(wp.id) as PROJECT_ID,
                        MAX(wp.title) as TITLE,
                        MAX(wp.start_date) as START_DATE,
                        MAX(wp.end_date) as END_DATE,
                        MAX(wp.comparison_criterias) as COMPARISON_CRITERIAS,
                        MAX(wp.project_location) as location,
                        MAX(wps.actual_percentage) as PERCENT_COMPLETE,
                        MAX(wp.project_type) as PROJECT_TYPE,
                        MAX(wp.sdlc_method) as SDLC_METHOD,
                        MAX(wp.state) as PROJECT_STATE,
                        MAX(pp.title) as PORTFOLIO,
                        MAX(pp.id) as PORTFOLIO_ID,
                        MAX(wp.roadmap_id) as ROADMAP_ID,
                        MAX(rr.title) as ROADMAP_NAME,
                        MAX(
                            CASE 
                                WHEN rr.budget > 0 THEN wpm.planned_spend / rr.budget 
                                ELSE 0 
                            END
                        ) as PERCENT_ROADMAP_PLANNED_BUDGET,
                        MAX(wp.project_manager_id_id) as PROJECT_MANAGER_ID,
                        MAX(wpprov.id) as PROVIDER_ID,
                        MAX(tp.company_name) as PROVIDER_NAME,
                        MAX(wp.technology_stack) as TECH_STACK,
                        MAX(wp.delivery_status) as DELIVERY_STATUS,
                        MAX(wp.scope_status) as SCOPE_STATUS,
                        MAX(wp.spend_status) as SPEND_STATUS,
                        ARRAY_AGG(DISTINCT wpkpi.name) as KEY_RESULTS,
                        ARRAY_AGG(DISTINCT jsonb_build_object(
                                'comment', wps.comments,
                                'timestamp', wps.created_date
                        )) as comment,
                        MAX(wp.spend_type) as SPEND_TYPE,
                        MAX(wpm.planned_spend) as PLANNED_SPEND,
                        MAX(wpm.actual_spend) as ACTUAL_SPEND,
                        MAX(CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END) as OVERRUN,
                        ARRAY_AGG(DISTINCT jsonb_build_object(
                                'team_id', wpse.team_id,
                                'actual_spend', wpse.actual_spend ,
                                'planned_spend', wpse.planned_spend,
                                'name', wpse.name,
                                'target_date', wpse.target_date
                        )) as MILESTONES,
                         ARRAY_AGG(DISTINCT jsonb_build_object(
                            'role', wpts.member_role,
                            'member_name', wpts.member_name,
                            'average_rate_per_hour', wpts.average_spend,
                            'contribution_percentage', wpts.member_utilization,
                            'member_location', wpts.location,
                            'team_type', CASE WHEN wpts.is_external = false then 'Internal Team' else 'External Team' end
                        )) as TEAMSDATA
                FROM
                        workflow_project as wp
                LEFT JOIN
                        workflow_projectkpi as wpkpi on wp.id=wpkpi.project_id
                LEFT JOIN
                        workflow_projectmilestone as wpm on wp.id=wpm.project_id
                LEFT JOIN
                        workflow_projectprovider as wpprov on wp.id=wpprov.project_id
                LEFT JOIN
                        tenant_provider as tp on tp.id = wpprov.provider_id
                LEFT JOIN
                        workflow_projectportfolio as wpport on wp.id=wpport.project_id
                LEFT JOIN
                        workflow_projectstatus as wps on wp.id=wps.project_id
                LEFT JOIN
                        projects_portfolio as pp on wpport.portfolio_id = pp.id
                LEFT JOIN
                        users_user as uu on wp.project_manager_id_id = uu.id
                LEFT JOIN
                        workflow_projectmilestone as wpse on wpse.project_id = wp.id
                LEFT JOIN
                        users_user as uuu on uuu.id = wps.created_by_id
                LEFT JOIN
                        roadmap_roadmap as rr on rr.id = wp.roadmap_id
                LEFT JOIN
                        workflow_projectteam as wpt on wp.id=wpt.project_id
                LEFT JOIN
                        workflow_projectteamsplit as wpts on wp.id=wpts.project_id
                WHERE
                        wp.tenant_id_id = {tenant_id} 
                        AND wp.id IN {tuple(eligibleProjects)}
                        AND wp.archived_on IS NULL
                        AND wp.parent_id is not NULL
                GROUP BY
                        wp.id
        )
        """
    return query


MAIN_QUERY = """
SELECT 
	*
FROM
	TheBase
"""

AUXILARY_QUERY = """, Base as (
	SELECT
		*
	FROM
		TheBase
"""

AUXILARY_QUERY_END = """
, TechStacks AS (
    SELECT
        tech_stack,
        COUNT(*) as tech_stack_count
    FROM Base
        WHERE tech_stack != 'Null'
    GROUP BY tech_stack
),  ProjectCounts AS (
    SELECT
        project_type,
        COUNT(*) as project_count
    FROM Base
        WHERE project_type != 'Null'
    GROUP BY project_type
), SpendStatuses AS (
    SELECT
        spend_status,
        COUNT(*) as spend_status_counts
    FROM Base
        WHERE spend_status != 'Null'
    GROUP BY spend_status
),DeliveryStatuses AS (
    SELECT
        delivery_status,
        COUNT(*) as delivery_status_counts
    FROM Base
        WHERE delivery_status != 'Null'
    GROUP BY delivery_status
), ScopeStatuses AS (
    SELECT
        scope_status,
        COUNT(*) as scope_status_counts
    FROM Base
        WHERE scope_status != 'Null'
    GROUP BY scope_status
),
Portfolios AS (
    SELECT
        MAX(portfolio) as portfolio,
        COUNT(*) as portfolio_count
    FROM Base
        Where portfolio_id BETWEEN 0 AND 2147483647
    GROUP BY portfolio_id
)
SELECT 
    COUNT(*) as total_projects,
    AVG(actual_spend) as average_actual_spend,
    SUM(actual_spend) as total_actual_spend,
    AVG(planned_spend) as average_planned_spend,
    SUM(planned_spend) as total_planned_spend,
    AVG(overrun) as average_overrun,
    SUM(overrun) as total_overrun,
    (
        SELECT jsonb_object_agg(project_type, project_count)
        FROM ProjectCounts
    ) as project_type_counts,
        (
        SELECT jsonb_object_agg(delivery_status, delivery_status_counts)
        FROM DeliveryStatuses 
    ) as delivery_status_counts,
        (
        SELECT jsonb_object_agg(spend_status, spend_status_counts)
        FROM SpendStatuses
    ) as delivery_status_counts,
        (
        SELECT jsonb_object_agg(scope_status, scope_status_counts)
        FROM ScopeStatuses
    ) as scope_status_counts,
        (
        SELECT jsonb_object_agg(tech_stack, tech_stack_count)
        FROM TechStacks 
    ) as tech_stack_counts,
        (
        SELECT jsonb_object_agg(portfolio, portfolio_count)
        FROM Portfolios 
    ) as portfolios
FROM 
    Base

"""


RETURN_DESCRIPTION = """
Returns two tables, with the specs of the table being: 
    Table 1:
    - title: str (the title of the project)
    - start_date: str (the start date of the project)
    - end_date: str (the projected end date of the project)
    - objectives: str (the objectives of the project and what it needs to complete)
    - comparison_criterias: str (what the project is being compared on)
    - project_location: str (where the project is being executed)
    - percent_complete: int (the percentage of the project that has been completed)
    - project_type: str
    - sdlc_method: str (the software development lifecycle method that the project is using)
    - current_stage: str (the current stage at which the project is at)
    - project_state: str (the state of the project)
    - portfolio: str (what portfolio the project is a part of)
    - portfolio_id: str (the id of the portfolio that it is a part of)
    - roadmap_id: str (the id of the roadmap that it is a part of)
    - roadmap_name: str (the roadmap that the project is a part of)
    - percent_roadmap_planned_budget: int (the percentage of the roadmap that has been completed)
    - project_manager_id: str (the id of the project manager)
    - project_manager_first_name: str (the first name of the project manager)
    - project_manager_last_name: str (the last name of the project manager)
    - provider_id: str (the id of the provider)
    - provider_name: str (the name of the provider)
    - tech_stack: str (the technology stack that the project is using)
    - key_results: str (the key performance indicators/ key results of the project)
    - delivery_scope: str (the scope of the delivery)
    - scope_status: str (the status of the scope)
    - spend_status: str (the status of the spend)
    - comment: str (any comments on the project)
    - spend_type: str (the type of spend)
    - planned_spend: int (the planned spend of the project)
    - actual_spend: int (the actual spend of the project)
    - overrun: int (the overrun of the project)
    - milestones: str (the milestones of the project)
    - teamsdata: str ( team member utilization, roles etc of the project)
    Table 2:
    - the total planned spend of the projects in Table 1
    - the total actual spend of the projects in Table 1
    - the total overrun of the projects in Table 1
    - the total number of projects in each category in Table 1 
    - the total number of projects of each project type in Table 1
    - the total number of projects of each project state in Table 1
    - the total number of projects of each delivery scope in Table 1
    - the total number of projects of each scope status in Table 1
    - the total number of projects of each spend status in Table 1
    - the total number of green, red, and yellow projects
    - the total number of projects by category, tech stack, provider, etc
    """


PROJECT_ANALYST = AgentFunction(
    name="project_analyst",
    description="A function to use when the user inquires anything regarding projects - including their spend, their scopes, team info, team member utilization etc.",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_projects,
)
