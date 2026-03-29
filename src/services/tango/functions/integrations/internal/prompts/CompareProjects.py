from src.database.Database import db_instance


Arguments = [
    {
        "name": "compare_by",
        "type": "str",
        "description": "Compare the details and statistics of projects by a singular category. For example, you can compare projects by their manager, and see the distribution of spend amongst them. Or you can compare projects by their spend status, and see the distribution of project types amongst them. You cannot compare by any other fields than the one provided in the options otherwise the code will break.",
        "options": [
            "project_manager_id",
            "project_type",
            "project_state",
            "portfolio_id",
            "roadmap_id",
            "provider_id",
            "tech_stack",
            "kpis",
            "delivery_scope",
            "scope_status",
            "spend_status",
        ],
    },
]

ArgumentMapping = {
    "project_manager_id": {
        "base": "wp.project_manager_id_id",
        "corresponding_column": "project_manager_name",
    },
    "project_state": {"base": "wp.state", "corresponding_column": "project_state"},
    "portfolio_id": {"base": "rr.portfolio_id", "corresponding_column": "portfolio"},
    "roadmap_id": {"base": "wp.roadmap_id", "corresponding_column": "roadmap_name"},
    "provider_id": {
        "base": "wpts.provider_id",
        "corresponding_column": "provider_name",
    },
    "tech_stack": {"base": "wp.technology_stack", "corresponding_column": "tech_stack"},
    "kpis": {"base": "wpkpi.name", "corresponding_column": "kpis"},
    "project_type": {"base": "wp.project_type", "corresponding_column": "project_type"},
    "delivery_scope": {
        "base": "wp.delivery_scope",
        "corresponding_column": "delivery_scope",
    },
    "scope_status": {"base": "wp.scope_status", "corresponding_column": "scope_status"},
    "spend_status": {"base": "wp.spend_status", "corresponding_column": "spend_status"},
}


def compare_projects_by(eligibleProjects: list[int], compare_by: str, tenantID: int, **kwargs):
    base = ArgumentMapping[compare_by]["base"]
    correspondingColumn = ArgumentMapping[compare_by]["corresponding_column"]

    query = f"""WITH Base AS (
    SELECT
        MAX(wp.title) as title,
        MAX(wp.start_date) as start_date,
        MAX(wp.end_date) as end_date,
        MAX(wp.objectives) as objectives,
        MAX(wp.comparison_criterias) as comparison_criterias,
        MAX(wp.project_location) as project_location,
        MAX(wp.project_category) as project_category,
        MAX(wps.actual_percentage) as percent_complete,
        MAX(wp.project_type) as project_type,
        MAX(wp.sdlc_method) as sdlc_method,
        MAX(wp.current_stage) as current_stage,
        MAX(wp.state) as project_state,
        MAX(pp.title) as portfolio,
        MAX(pp.id) as portfolio_id,
        MAX(wp.roadmap_id) as roadmap_id,
        MAX(rr.title) as roadmap_name,
        MAX(CASE 
            WHEN rr.budget = 0 THEN 0 
            ELSE wpm.planned_spend / rr.budget 
        END) as percent_roadmap_planned_budget,
        MAX(wp.project_manager_id_id) as project_manager_id,
		MAX((' ')) as project_manager_name,
        MAX(wpprov.id) as provider_id,
        MAX(tp.company_name) as provider_name,
        MAX(wp.technology_stack) as tech_stack,
        ARRAY_AGG(DISTINCT wpkpi.name) as KEY_RESULTS,
        MAX(wp.delivery_status) as delivery_status,
        MAX(wp.scope_status) as scope_status,
        MAX(wp.spend_status) as spend_status,
        ARRAY_AGG(DISTINCT jsonb_build_object(
            'comment', wps.comments,
            'timestamp', wps.created_date
        )) as comment,
        MAX(wp.spend_type) as spend_type,
        MAX(wpm.planned_spend) as planned_spend,
        MAX(wpm.actual_spend) as actual_spend,
        MAX(CASE WHEN wpm.actual_spend > wpm.planned_spend THEN wpm.actual_spend - wpm.planned_spend ELSE 0 END) as overrun,
        ARRAY_AGG(DISTINCT jsonb_build_object(
            'team_id', wpse.team_id,
            'actual_spend', wpse.actual_spend,
            'planned_spend', wpse.planned_spend,
            'name', wpse.name,
            'target_date', wpse.target_date
        )) as milestones,
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
        workflow_projectteam as wpt on wp.id=wpt.project_id
    LEFT JOIN
        workflow_projectteamsplit as wpts on wp.id=wpts.project_id
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
        workflow_projectteam as wptj on wptj.project_id = wp.id
    WHERE
        wp.tenant_id_id = {tenantID} 
        AND wp.archived_on IS NULL
        AND wp.parent_id is not NULL
        AND wp.id IN {tuple(eligibleProjects)}
    GROUP BY
        wp.id, {base}
), CategoryCounts AS (
    SELECT
        project_category as category,
        COUNT(*) as category_count,
		{compare_by} as group_by
    FROM Base
	WHERE project_category Is Not Null
    GROUP BY category, {compare_by}
), TechStacks AS (
    SELECT
        tech_stack,
        COUNT(*) as tech_stack_count,
		{compare_by} as group_by
    FROM Base
	WHERE tech_stack is not Null
    GROUP BY tech_stack, {compare_by}
),
ProjectCounts AS (
    SELECT
        project_type,
        COUNT(*) as project_count,
		{compare_by} as group_by
    FROM Base
	WHERE project_type != 'Null'
    GROUP BY project_type, {compare_by}
), SpendStatuses AS (
    SELECT
        spend_status,
        COUNT(*) as spend_status_counts,
		{compare_by} as group_by
    FROM Base
	WHERE spend_status != 'Null'
    GROUP BY spend_status, {compare_by}
),DeliveryStatuses AS (
    SELECT
        delivery_status,
        COUNT(*) as delivery_status_counts,
		{compare_by} as group_by
    FROM Base
	WHERE delivery_status != 'Null'
    GROUP BY delivery_status, {compare_by}
), ScopeStatuses AS (
    SELECT
        scope_status,
        COUNT(*) as scope_status_counts,
		{compare_by} as group_by
    FROM Base
	WHERE scope_status != 'Null'
    GROUP BY scope_status, {compare_by}
),
Portfolios AS (
    SELECT
        MAX(portfolio) as portfolio,
        COUNT(*) as portfolio_count,
		{compare_by} as group_by
    FROM Base
	Where portfolio_id BETWEEN 0 AND 2147483647
    GROUP BY portfolio_id, {compare_by}
)
SELECT 
	{compare_by},
	MAX(Base.{correspondingColumn}) AS corresponding,
    COUNT(*) as total_projects,
    AVG(actual_spend) as average_actual_spend,
    SUM(actual_spend) as total_actual_spend,
    AVG(planned_spend) as average_planned_spend,
    SUM(planned_spend) as total_planned_spend,
    AVG(overrun) as average_overrun,
    SUM(overrun) as total_overrun,
    (
        SELECT jsonb_object_agg(project_type, project_count)
        FROM ProjectCounts WHERE
		ProjectCounts.group_by = Base.{compare_by}
    ) as project_type_counts,
	(
        SELECT jsonb_object_agg(delivery_status, delivery_status_counts)
        FROM DeliveryStatuses WHERE
		DeliveryStatuses.group_by = Base.{compare_by}
    ) as delivery_status_counts,
	(
        SELECT jsonb_object_agg(spend_status, spend_status_counts)
        FROM SpendStatuses WHERE
		SpendStatuses.group_by = Base.{compare_by}
    ) as delivery_status_counts,
	(
        SELECT jsonb_object_agg(scope_status, scope_status_counts)
        FROM ScopeStatuses WHERE
		ScopeStatuses.group_by = Base.{compare_by}
    ) as scope_status_counts,
	(
        SELECT jsonb_object_agg(category, category_count)
        FROM CategoryCounts WHERE
		CategoryCounts.group_by = Base.{compare_by}
    ) as category_counts,
	(
        SELECT jsonb_object_agg(tech_stack, tech_stack_count)
        FROM TechStacks WHERE
		TechStacks.group_by = Base.{compare_by}
    ) as tech_stack_counts,
	(
        SELECT jsonb_object_agg(portfolio, portfolio_count)
        FROM Portfolios WHERE
		Portfolios.group_by = Base.{compare_by}
    ) as portfolios	
FROM 
    Base
WHERE 
    Base.{compare_by} IS NOT NULL
GROUP BY
    Base.{compare_by}
"""
    print (query)
    response = db_instance.retrieveSQLQuery(query)
    print (response)
    # if the kwargs have 'requestedColumns', then filter the response to only include those columns
    if "requestedColumns" in kwargs:
        response = response.getColumns(kwargs["requestedColumns"])
    print (response.getColumnNames())
    return response.formatData()


ReturnDescription = """
Returns a singular table with the following fields:

First column: whatever you are comparing by
total_projects: the number of projects in that group
average_actual_spend: the average actual spend of the projects in that group
total_actual_spend: the total actual spend of the projects in that group
average_planned_spend: the average planned spend of the projects in that group
total_planned_spend: the total planned spend of the projects in that group
average_overrun: the average overrun of the projects in that group	
total_overrun: the total overrun of the projects in that group	
project_type_counts: the total number of projects by each project type in that group
delivery_status_counts: a JSON showing how many projects are each stage of delivery in that group
spend_status_counts: a JSON showing how many projects are in each spend status in that group
scope_status_counts: a JSON showing how many projects are in each scope status in that group
category_counts: a JSON showing how many projects are in each category in that group
tech_stack_counts: a JSON showing how many projects are using each technology in that group
project_manager: a JSON showing how many projects each project manager is managing in that group
portfolios: a JSON showing how many projects are in each portfolio in that group
"""
