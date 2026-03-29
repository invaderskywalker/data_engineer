from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import SQL_Handler
from src.api.types.TabularData import TabularData
from src.database.Database import db_instance


def view_ideas(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    portfolio_id=None,
    kpi_weightage=None,
    idea_rank=None,
    complexity=None,
    created_on=None,
) -> list[TabularData]:
    sql_handler = SQL_Handler(get_base_query(tenantID))

    portfolio_id_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "portfolio_id")
    sql_handler.handleArguments(portfolio_id_arg, portfolio_id)

    weightage_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "kpi_weightage")
    sql_handler.handleArguments(weightage_arg, kpi_weightage)

    idea_rank_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "idea_rank")
    sql_handler.handleArguments(idea_rank_arg, idea_rank)

    created_on_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "created_on")
    sql_handler.handleArguments(created_on_arg, created_on)

    complexity_arg = next(
        arg for arg in ARGUMENTS if arg["name"] == "complexity")
    sql_handler.handleArguments(complexity_arg, complexity)

    where_conditions = sql_handler.generateConditionals()
    print("--debug where_conditions: ", where_conditions)
    main = (
        get_base_query(tenantID)
        + where_conditions
    )
    executedMain = db_instance.retrieveSQLQuery(main).formatData()
    return executedMain


ARGUMENTS = [
    {
        "name": "portfolio_id",
        "type": "int[]",
        "description": "The ID of the portfolio to view ideas from. If not provided, all ideas will be returned.",
        "conditional": "in"
    },
    {
        "name": "kpi_weightage",
        "type": "float[]",
        "description": "Filter ideas by their weightage. Will return ideas with any matching weightage value.",
        "conditional": "in"
    },
    {
        "name": "complexity",
        "type": "{ 'lower_bound': 'float', 'upper_bound': 'float' }",
        "description": "Filter ideas by their complexity. Will return ideas with any matching complexity value.",
        "conditional": "range"
    },
    {
        "name": "idea_rank",
        "type": "{ 'lower_bound': 'float', 'upper_bound': 'float' }",
        "description": "Filter ideas by rank. Will return ideas with any matching rank value.",
        "conditional": "range"
    },
    {
        "name": "created_on",
        "type": "{ 'lower_bound': 'str', 'upper_bound': 'str' }",
        "description": "Filter ideas by creation date. Date must be in 'YYYY-MM-DD' format.",
        "conditional": "date-bound"
    },
    # {
    #     "name": "updated_on",
    #     "type": "{ 'lower_bound': 'str', 'upper_bound': 'str' }",
    #     "description": "Filter ideas by the last updated date. Date must be in 'YYYY-MM-DD' format.",
    #     "conditional": "date-bound"
    # },
]


def get_base_query(tenantId: int):
    BASE_QUERY = f"""
	with Base as  (select 
		ic.id as idea_id,
		ic.title as title,
		MAX(pp.title) as portfolio,
		MAX(ic.short_description) as description,
		MAX(icp.portfolio_id) as portfolio_id,
		MAX(ic.elaborate_description) as long_description,
		ARRAY_AGG(ick.id) as kpi_id,
		ARRAY_AGG(ick.title) as kpi,
		ARRAY_AGG(ick.weightage) as kpi_weightage,
		MAX(ic.rank) as idea_rank,
		MAX(ic.created_on) as created_on,
		MAX(ic.updated_on) as updated_on,
		MAX(ic.tenant_id) as tenant_id,
		MAX(ic.priority) as priority,
		ic.auto_generated as auto_generated,
		ic.portfolio_rank_overridden as rank_overriden,
		MAX(ic.status) as status,
		MAX(ic.owner) as owner,
		MAX(ic.portfolio_rank) as portfolio_rank,
		ic.portfolio_rank_overridden as rank_overriden,
		MAX(ic.complexity) as complexity,
		MAX(ic.weightage) as weightage
	from 
		idea_concept as ic
	left join 
		idea_conceptkpi as ick on ick.concept_id = ic.id
	left join 
		idea_conceptportfolio as icp on icp.concept_id = ic.id
	left join 
		projects_portfolio as pp on pp.id = icp.portfolio_id
	where 
 		ic.tenant_id = {str(tenantId)}
	group by
		idea_id
	) Select * from Base
	"""
    return BASE_QUERY

# MAIN_QUERY = """
# SELECT
# 	*
# FROM
# 	TheBase
# """


RETURN_DESCRIPTION = """
Returns a table with IDs (filtered by a portfolio if you want) and the following columns:
- idea_id: The ID of the idea
- title: The title of the idea
- portfolio: The portfolio the idea belongs to
- description: The short description of the idea
- long_description: The long description of the idea
- kpi_id: The ID of the KPIs associated with the idea
- kpi: The title of the KPIs associated with the idea
- kpi_weightage: The weightage of the KPIs associated with the idea
- idea_rank: The rank of the idea
- created_on: The date the idea was created
"""
