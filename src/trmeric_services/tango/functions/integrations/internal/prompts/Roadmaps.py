
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.trmeric_database.Database import db_instance


# return f"""
#     SELECT
#         rr.id,
#         rr.title as roadmap_title,
#         pp.title AS portfolio_title,
#         rr.objectives as roadmap_objectives,
#         rr.start_date as roadmap_start_date,
#         rr.end_date as roadmap_end_date,
#         rr.budget as roadmap_budget,
#         rr.category as roadmap_category,
#         rr.org_strategy_align,
#         rrmc.*,  -- Roadmap Category fields
#         rrc.*,   -- Roadmap Constraints fields
#         rrk.*,   -- Roadmap KPI fields
#         rrsa.*,  -- Roadmap Organizational Strategy Alignment fields
#         rrmp.*   -- Roadmap Team fields
#     FROM roadmap_roadmap AS rr
#     LEFT JOIN roadmap_roadmapportfolio AS rrp ON rr.id = rrp.roadmap_id
#     LEFT JOIN projects_portfolio AS pp ON pp.id = rrp.portfolio_id
#     LEFT JOIN roadmap_roadmapcategory AS rrmc ON rr.id = rrmc.id
#     LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.id
#     LEFT JOIN roadmap_roadmapkpi AS rrk ON rrk.id = rr.id
#     LEFT JOIN roadmap_roadmaporgstratergyalign AS rrsa ON rrsa.id = rr.id
#     LEFT JOIN roadmap_roadmapteam AS rrmp ON rrmp.id = rr.id
# WHERE rr.tenant_id = {tenantId}
# """
# return f"""
#     SELECT
#             rr.id,
#             rr.title as roadmap_title,
#             pp.title AS portfolio_title,
#             rr.objectives as roadmap_objectives,
#             rr.start_date as roadmap_start_date,
#             rr.end_date as roadmap_end_date,
#             rr.budget as roadmap_budget,
#             rr.category as roadmap_category,
#             rr.org_strategy_align,
#             rr.approved_state,
#             uu.first_name as request_owner_first_name,
#             uu.last_name as request_owner_last_name

# --             rrmc.*,  -- Roadmap Category fields
# --             rrc.*,   -- Roadmap Constraints fields
# --             rrk.*,   -- Roadmap KPI fields
# --             rrsa.*  -- Roadmap Organizational Strategy Alignment fields
# --             rrmp.*   -- Roadmap Team fields
#         FROM roadmap_roadmap AS rr
#         LEFT JOIN roadmap_roadmapportfolio AS rrp ON rr.id = rrp.roadmap_id
#         LEFT JOIN projects_portfolio AS pp ON pp.id = rrp.portfolio_id
#         LEFT JOIN roadmap_roadmapcategory AS rrmc ON rr.id = rrmc.id
#         LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.id
#         LEFT JOIN roadmap_roadmapkpi AS rrk ON rrk.id = rr.id
#         LEFT JOIN roadmap_roadmaporgstratergyalign AS rrsa ON rrsa.id = rr.id
#         LEFT JOIN users_user as uu on rr.created_by_id = uu.id
# --         LEFT JOIN roadmap_roadmapteam AS rrmp ON rrmp.id = rr.id
#     WHERE rr.tenant_id = {tenantId}
# """

# pass in the tenant ID into the query


ROADMAP_ARGS = [
    {
        "name": "roadmap_id",
        "type": "int[]",
        "description": "The IDs of the roadmaps you want to view. This must be a list",
        "conditional": "in",
    },
    {
        "name": "portfolio_ids",
        "type": "int[]",
        "description": "The IDs of the portfolio you want to filter these roadmaps on. This must be a list",
        "conditional": "in",
    },
    {
        "name": "priority",
        "type": "str",
        "description": "the priority of roadmaps values are High, Low and Medium.",
        "conditional": "like",
    }
]

"""

    rr.total_capital_cost as roadmap_total_capital_cost,
                json_agg(
                    distinct json_build_object(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        case
                            when rrc.type = 1 then 'Cost'
                            when rrc.type = 2 then 'Resource'
                            when rrc.type = 3 then 'Risk'
                            when rrc.type = 4 then 'Scope'
                            when rrc.type = 5 then 'Quality'
                            when rrc.type = 6 then 'Time'
                            else 'Unknown'
                        end
                    )::text
                ) as roadmap_constraints,
                json_agg(
                    distinct pp.title
                ) as roadmap_portfolios,
                json_agg(
                    distinct json_build_object(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::text
                ) as roadmap_key_results,
                json_agg(
                    distinct rrs.name
                ) as roadmap_scope,
                                json_agg(
                                        distinct json_build_object(
                        'team_name', rrt.name,
                                                'team_unit_size', rrt.unit,
                        'labour_type', 
                        case
                            when rrt.labour_type = 1 then 'labour'
                            when rrt.labour_type = 2 then 'non labour'
                            else 'Unknown'
                        end,
                        'labour_estimate_value', rrt.estimate_value,
                        'team_efforts', 
                        case
                            when rrt.type = 1 then 'person days'
                            when rrt.type = 2 then 'person months'
                            else 'Unknown'
                        end
                    )::text
                ) AS team_data,
                -- Separate JSON for cash inflow of type 'savings'
                json_agg(
                    DISTINCT json_build_object(
                        'cash_inflow', rrac.cash_inflow,
                        'time_period', rrac.time_period,
                        'category', rrac.category,
                        'justification_text', rrac.justification_text
                    )::text
                ) FILTER (WHERE rrac.type = 'savings') AS operational_efficiency_gains_savings_cash_inflow,

                -- Separate JSON for cash inflow of type 'revenue'
                json_agg(
                    DISTINCT json_build_object(
                        'cash_inflow', rrac.cash_inflow,
                        'time_period', rrac.time_period,
                        'category', rrac.category,
                        'justification_text', rrac.justification_text
                    )::text
                ) FILTER (WHERE rrac.type = 'revenue') AS revenue_uplift_cash_inflow_data

            from roadmap_roadmap as rr 
            left join roadmap_roadmapconstraints as rrc on rr.id = rrc.roadmap_id
            left join roadmap_roadmapportfolio as rp on rr.id = rp.roadmap_id
            left join projects_portfolio as pp on rp.portfolio_id = pp.id
            left join roadmap_roadmapkpi as rrkpi on rr.id = rrkpi.roadmap_id
            left join roadmap_roadmapscope as rrs on rr.id = rrs.roadmap_id
                        left join roadmap_roadmapestimate as rrt on rrt.roadmap_id = rr.id
            left join roadmap_roadmapannualcashinflow as rrac on rr.id = rrac.roadmap_id
    """


def getRoadmapQuery(tenantId):
    return f"""
            SELECT 
                rr.id, 
                rr.title as roadmap_title, 
                rr.objectives as roadmap_objectives, 
                rr.start_date as roadmap_start_date,
                rr.end_date as roadmap_end_date,
                rr.budget as roadmap_budget,
                rr.category as roadmap_category,
                rr.org_strategy_align as roadmap_org_strategy_alignment,
                rr.approved_state,
                uu.first_name as owner_first_name,
                uu.last_name as owner_last_name,
                CASE 
                    WHEN rr.priority = 1 THEN 'High'
                    WHEN rr.priority = 2 THEN 'Medium'
                    WHEN rr.priority = 3 THEN 'Low'
                    ELSE 'Unknown'
                END AS roadmap_priority,
				rr.total_capital_cost as roadmap_total_capital_cost,
                json_agg(
                    distinct json_build_object(
                        'constraint_title', rrc.name,
                        'constraint_type', 
                        case
                            when rrc.type = 1 then 'Cost'
                            when rrc.type = 2 then 'Resource'
                            when rrc.type = 3 then 'Risk'
                            when rrc.type = 4 then 'Scope'
                            when rrc.type = 5 then 'Quality'
                            when rrc.type = 6 then 'Time'
                            else 'Unknown'
                        end
                    )::text
                ) as roadmap_constraints,
                json_agg(
                    distinct pp.title
                ) as roadmap_portfolios,
                json_agg(
                    distinct json_build_object(
                        'key_result_title', rrkpi.name,
                        'baseline_value', rrkpi.baseline_value
                    )::text
                ) as roadmap_key_results,
				json_agg(
					distinct json_build_object(
                        'team_name', rrt.name,
						'team_unit_size', rrt.unit,
                        'labour_type', 
                        case
                            when rrt.labour_type = 1 then 'labour'
                            when rrt.labour_type = 2 then 'non labour'
                            else 'Unknown'
                        end,
                        'labour_estimate_value', rrt.estimate_value,
                        'team_efforts', 
                        case
                            when rrt.type = 1 then 'person days'
                            when rrt.type = 2 then 'person months'
                            else 'Unknown'
                        end
                    )::text
                ) AS team_data
            from roadmap_roadmap as rr 
            left join roadmap_roadmapconstraints as rrc on rr.id = rrc.roadmap_id
            left join roadmap_roadmapportfolio as rp on rr.id = rp.roadmap_id
            left join projects_portfolio as pp on rp.portfolio_id = pp.id
            left join roadmap_roadmapkpi as rrkpi on rr.id = rrkpi.roadmap_id
            left join roadmap_roadmapscope as rrs on rr.id = rrs.roadmap_id
			left join roadmap_roadmapestimate as rrt on rrt.roadmap_id = rr.id
            left join roadmap_roadmapannualcashinflow as rrac on rr.id = rrac.roadmap_id
            LEFT JOIN users_user as uu on rr.created_by_id = uu.id
        WHERE rr.tenant_id = {tenantId}
		GROUP BY rr.id, pp.title, uu.first_name, uu.last_name;
    """


# def view_roadmaps(tenantID: int, userID: int, roadmap_id=None, **kwargs):
#     sql_handler = SQL_Handler(
#         baseQuery=getRoadmapQuery(tenantID)
#     )
#     roadmap_id_arg = next(
#         arg for arg in ROADMAP_ARGS if arg["name"] == "roadmap_id")
#     sql_handler.handleArguments(roadmap_id_arg, roadmap_id)
#     query = sql_handler.createSQLQuery()
#     response = db_instance.retrieveSQLQuery(query).formatData()
#     return response


def view_roadmaps(tenantID: int, userID: int, roadmap_id=None, portfolio_ids=None, priority=None, **kwargs):
    sql_handler = SQL_Handler(baseQuery=getRoadmapQuery(tenantID))

    # Handle each argument individually based on ROADMAP_ARGS

    roadmap_id_arg = next(
        arg for arg in ROADMAP_ARGS if arg["name"] == "roadmap_id")
    sql_handler.handleArguments(roadmap_id_arg, roadmap_id)

    # portfolio_ids_arg = next(
    #     arg for arg in ROADMAP_ARGS if arg["name"] == "portfolio_ids")
    # sql_handler.handleArguments(portfolio_ids_arg, portfolio_ids)

    # portfolio_ids_arg = next(
    #     arg for arg in ROADMAP_ARGS if arg["name"] == "portfolio_ids")
    # if portfolio_ids is not None:
    #     if isinstance(portfolio_ids, int):  # Convert single integer to list format
    #         portfolio_ids = [portfolio_ids]
    # sql_handler.handleArguments(portfolio_ids_arg, portfolio_ids)

    # priority_arg = next(
    #     arg for arg in ROADMAP_ARGS if arg["name"] == "priority")
    # sql_handler.handleArguments(priority_arg, priority)

    # Additional arguments can be added here in the same manner

    query = sql_handler.createSQLQuery()
    response = db_instance.retrieveSQLQuery(query).formatData()
    return response


RETURN_DESCRIPTION = """
Returns the roadmaps or roadmap items information
of each of the roadmaps by the specific arguments. 
If no arguments are provided, it will return all roadmaps.
"""
