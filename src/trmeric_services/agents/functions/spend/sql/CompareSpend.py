from src.trmeric_database.Database import db_instance

ArgumentMapping = {
    "project_manager_id": {
        "base": "wp.project_manager_id_id",
        "corresponding_column": "project_manager_name",
    },
    "project_state": {
        "base": "wp.state",
        "corresponding_column": "project_state"
    },
    "portfolio_id": {
        "base": "rr.portfolio_id",
        "corresponding_column": "portfolio"
    },
    "roadmap_id": {
        "base": "wp.roadmap_id",
        "corresponding_column": "roadmap_name"
    },
    "provider_id": {
        "base": "wpts.provider_id",
        "corresponding_column": "provider_name",
    },
    "tech_stack": {
        "base": "wp.technology_stack",
        "corresponding_column": "tech_stack"
    },
    "kpis": {
        "base": "wpkpi.name",
        "corresponding_column": "kpis"
    },
    "project_type": {
        "base": "wp.project_type",
        "corresponding_column": "project_type"
    },
    "delivery_scope": {
        "base": "wp.delivery_scope",
        "corresponding_column": "delivery_scope"
    },
    "scope_status": {
        "base": "wp.scope_status",
        "corresponding_column": "scope_status"
    },
    "spend_status": {
        "base": "wp.spend_status",
        "corresponding_column": "spend_status"
    },
    "project_category": {
        "base": "wp.project_category",
        "corresponding_column": "project_category",
    },
}


def compare_projects_by_spend(
    eligibleProjects: list[int],
    compare_by: str,
    tenantID: int,
    **kwargs
):
    """
    Analyze spend metrics grouped by a user-specified field (e.g., provider_id, tech_stack, project_type, etc.).

    It returns:
      - group_by (the raw grouping value)
      - corresponding (display-friendly name, if applicable)
      - total_projects
      - average_actual_spend / total_actual_spend
      - average_planned_spend / total_planned_spend
      - average_overrun / total_overrun

    :param eligibleProjects: A list of valid project IDs to analyze
    :param compare_by: One of the valid keys in `ArgumentMapping`
    :param tenantID: The tenant ID for which the data is retrieved
    :param kwargs:
        * "requestedColumns": if you only want certain columns returned

    :return: Formatted response containing spend metrics grouped by the compare_by field
    """

    # Validate the compare_by field
    if compare_by not in ArgumentMapping:
        raise ValueError(
            f"Invalid compare_by argument: {compare_by}. "
            f"Must be one of {list(ArgumentMapping.keys())}."
        )

    base = ArgumentMapping[compare_by]["base"]                # e.g. wpts.provider_id
    corresponding_col = ArgumentMapping[compare_by]["corresponding_column"]  # e.g. provider_name

    # Handle the case where there's exactly one eligibleProject
    if len(eligibleProjects) == 1:
        project_tuple = f"({eligibleProjects[0]})"
    else:
        project_tuple = tuple(eligibleProjects)

    # Build the query
    query = f"""
    WITH Base AS (
        SELECT
            wp.id AS project_id,

            -- The key grouping value (e.g. wpts.provider_id, wp.technology_stack, etc.)
            {base} AS group_by_value,

            /* 
               We define ALL possible "corresponding columns" that appear in ArgumentMapping.
               That way, no matter which 'compare_by' is requested, the column is available
               for 'MAX({corresponding_col}) AS corresponding' in the final SELECT.
            */
            MAX(tp.company_name) AS provider_name,
            MAX(uu.first_name || ' ' || uu.last_name) AS project_manager_name,
            MAX(rr.portfolio_id) AS portfolio_id, -- might be used if compare_by=portfolio_id
            MAX(pp.title) AS portfolio,
            MAX(rr.title) AS roadmap_name,
            MAX(wp.technology_stack) AS tech_stack,
            MAX(wpkpi.name) AS kpis,
            MAX(wp.project_type) AS project_type,
            MAX(wp.scope_status) AS scope_status,
            MAX(wp.spend_status) AS spend_status,
            MAX(wp.project_category) AS project_category,
            MAX(wp.state) AS project_state,

            -- Basic spend columns
            COALESCE(MAX(wpm.actual_spend), 0) AS actual_spend,
            COALESCE(MAX(wpm.planned_spend), 0) AS planned_spend,
            COALESCE(
                MAX(
                    CASE 
                        WHEN wpm.actual_spend > wpm.planned_spend 
                            THEN wpm.actual_spend - wpm.planned_spend
                        ELSE 0
                    END
                ), 
            0) AS overrun

        FROM workflow_project AS wp
        
        /* 
            Include relevant LEFT JOINs:
              - wpm => project milestones for spend
              - wpts => projectteamsplit for provider_id
              - rr => roadmap for portfolio_id/roadmap_id
              - pp => portfolio table
              - wpkpi => project kpi
              - uu => user table for project_manager
              - tp => tenant_provider table for provider_name
        */
        LEFT JOIN workflow_projectmilestone AS wpm 
            ON wp.id = wpm.project_id

        LEFT JOIN workflow_projectteamsplit AS wpts
            ON wp.id = wpts.project_id

        LEFT JOIN roadmap_roadmap AS rr
            ON wp.roadmap_id = rr.id

        LEFT JOIN projects_portfolio AS pp
            ON rr.portfolio_id = pp.id

        LEFT JOIN workflow_projectkpi AS wpkpi
            ON wp.id = wpkpi.project_id
        
        LEFT JOIN users_user AS uu
            ON wp.project_manager_id_id = uu.id

        LEFT JOIN tenant_provider AS tp
            ON wpts.provider_id = tp.id

        WHERE
            wp.tenant_id_id = {tenantID}
            AND wp.archived_on IS NULL
            AND wp.parent_id IS NOT NULL
            AND wp.id IN {project_tuple}
        
        GROUP BY
            wp.id,
            {base}
    )
    SELECT
        group_by_value AS group_by,
        /* 
           We do "MAX({corresponding_col})" as "corresponding".
           E.g., if compare_by='provider_id', 
                 corresponding_col='provider_name' -> "MAX(provider_name) as corresponding"
        */
        MAX({corresponding_col}) AS corresponding,
        
        COUNT(*) AS total_projects,
        
        AVG(actual_spend) AS average_actual_spend,
        SUM(actual_spend) AS total_actual_spend,
        
        AVG(planned_spend) AS average_planned_spend,
        SUM(planned_spend) AS total_planned_spend,
        
        AVG(overrun) AS average_overrun,
        SUM(overrun) AS total_overrun

    FROM Base
    WHERE group_by_value IS NOT NULL
    GROUP BY group_by_value
    """


    # Execute the query
    response = db_instance.retrieveSQLQuery(query)

    # Optionally filter columns if 'requestedColumns' is passed
    if "requestedColumns" in kwargs:
        response = response.getColumns(kwargs["requestedColumns"])

    # Debug: see the available columns

    # Return the final, formatted data
    return response.formatData()
