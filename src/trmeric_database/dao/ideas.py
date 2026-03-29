from typing import List, Dict, Any
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger

class IdeaDao:

    ATTRIBUTE_MAP: Dict[str, Dict] = {
        "id": {"table": "ic", "column": "ic.id AS idea_id"},
        "title": {"table": "ic", "column": "ic.title AS idea_title"},
        "elaborate_description": {"table": "ic", "column": "ic.elaborate_description AS idea_elaborate_description"},
        "rank": {"table": "ic", "column": "ic.rank AS idea_rank"},
        # No "status" column in table
        "budget": {"table": "ic", "column": "ic.budget AS idea_budget"},
        "start_date": {"table": "ic", "column": "ic.start_date AS idea_start_date"},
        "end_date": {"table": "ic", "column": "ic.end_date AS idea_end_date"},
        "owner": {"table": "ic", "column": "ic.owner AS idea_owner"},
        # "org_strategy": {"table": "ic", "column": "ic.org_strategy_align AS idea_org_strategy"},
        "org_strategy_align": {
            "table": "ic",
            "column": "ic.org_strategy_align AS idea_org_strategy_align"
        },
        "objectives": {"table": "ic", "column": "ic.objectives AS idea_objectives"},
        "category": {"table": "ic", "column": "ic.category AS idea_category"},
        "tango_analysis": {"table": "ic", "column": "ic.tango_analysis AS idea_tango_analysis"},
        "created_on": {"table": "ic", "column": "ic.created_on AS idea_created_on"},

        # --- JSON Aggregations ---

        "constraints": {
            "table": "icc",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'constraint_title', icc.name,
                    'constraint_type', CASE
                        WHEN icc.type = 1 THEN 'Cost'
                        WHEN icc.type = 2 THEN 'Risk'
                        WHEN icc.type = 3 THEN 'Resource'
                        ELSE 'Other'
                    END
                )::text
            ) FILTER (WHERE icc.name IS NOT NULL) AS idea_constraints""",
            "join": "LEFT JOIN idea_conceptconstraints AS icc ON ic.id = icc.concept_id",
            "group_by": False
        },

        "kpis": {
            "table": "ick",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'kpi_title', ick.title,
                    'weightage', ick.weightage,
                    'baseline_value', ick.baseline_value
                )::text
            ) FILTER (WHERE ick.title IS NOT NULL) AS idea_kpis""",
            "join": "LEFT JOIN idea_conceptkpi AS ick ON ic.id = ick.concept_id",
            "group_by": False
        },

        "portfolios": {
            "table": "icp",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'portfolio_id', p.id,
                    'portfolio_title', p.title,
                    'portfolio_rank', ic.portfolio_rank
                )::text
            ) FILTER (WHERE p.id IS NOT NULL) AS idea_portfolios""",
            "join": """
                LEFT JOIN idea_conceptportfolio AS icp ON ic.id = icp.concept_id
                LEFT JOIN projects_portfolio AS p ON icp.portfolio_id = p.id
            """,
            "group_by": False
        },
        
        "roadmaps": {
            "table": "rm",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'roadmap_id', rm.id,
                    'roadmap_title', rm.title,
                    'roadmap_type', rm.type,
                    'roadmap_priority', rm.priority,
                    'roadmap_start_date', rm.start_date,
                    'roadmap_end_date', rm.end_date
                )::text
            ) FILTER (WHERE rm.id IS NOT NULL) AS idea_roadmaps""",
            "join": """
                LEFT JOIN roadmap_roadmapideamap AS rim ON ic.id = rim.idea_id
                LEFT JOIN roadmap_roadmap AS rm ON rim.roadmap_id = rm.id
            """,
            "group_by": False
        },
        
        "business_case": {
            "table": "ic",
            "column": "ic.tango_analysis ->> 'business_case' AS business_case",
            "group_by": True
        },

        "business_members": {
            "table": "icbm",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'sponsor_first_name', pb.sponsor_first_name,
                    'sponsor_last_name', pb.sponsor_last_name
                )::text
            ) FILTER (WHERE pb.sponsor_first_name IS NOT NULL) AS idea_business_members""",
            "join": """
                LEFT JOIN idea_conceptbusinessmember AS icbm ON ic.id = icbm.concept_id
                LEFT JOIN projects_portfoliobusiness AS pb ON icbm.portfolio_business_id = pb.id
            """,
            "group_by": False
        }
    
    }

    # -------------------------------------------------------------------------
    # Dynamic Query Generator for Flexible Idea Fetching
    # -------------------------------------------------------------------------
    @staticmethod
    def fetchIdeasDataWithProjectionAttrs(
        idea_ids: List[int] = None,
        projection_attrs: List[str] = ["id", "title"],
        portfolio_ids: List[int] = None,
        tenant_id: int = None,
        state_filter: str = None,
        order_clause: str = None,
        user_id: int = None,
        title: str = None,
    ):
        try:
            select_clauses = []
            joins = set()
            group_by_clauses = set()
            where_conditions = []

            # detect if aggregation is needed
            requires_aggregation = any(
                "json_agg" in IdeaDao.ATTRIBUTE_MAP.get(attr, {}).get("column", "")
                for attr in projection_attrs
            )

            # collect select and join clauses
            for attr in projection_attrs:
                mapping = IdeaDao.ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue

                select_clauses.append(mapping["column"])

                join_clause = mapping.get("join")
                if join_clause:
                    # special handling for portfolio filtering
                    if "projects_portfolio AS p" in join_clause and portfolio_ids:
                        pids_str = f"({', '.join(map(str, portfolio_ids))})"
                        join_clause = join_clause.replace(
                            "LEFT JOIN projects_portfolio AS p ON icp.portfolio_id = p.id",
                            f"LEFT JOIN projects_portfolio AS p ON icp.portfolio_id = p.id AND p.id IN {pids_str}"
                        )
                    joins.add(join_clause)

                if mapping.get("group_by", True) and requires_aggregation:
                    group_by_column = mapping["column"].split(" AS ")[0]
                    group_by_clauses.add(group_by_column)

            # where conditions
            if idea_ids:
                ids_str = f"({', '.join(map(str, idea_ids))})"
                where_conditions.append(f"ic.id IN {ids_str}")

            if tenant_id:
                where_conditions.append(f"ic.tenant_id = {tenant_id}")
                
            if title:
                # Safe partial match
                safe_title = title.replace("'", "''")
                where_conditions.append(f"ic.title ILIKE '%{safe_title}%'")
                        
            # if user_id:
            #     where_conditions.append(f"ic.created_by_id = {user_id}")

            if state_filter:
                where_conditions.append(state_filter)

            select_clause_str = ",\n                ".join(select_clauses) if select_clauses else "ic.id"
            join_clause_str = "\n            ".join(joins)
            where_clause_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            group_by_clause = f"\n            GROUP BY {', '.join(group_by_clauses)}" if group_by_clauses and requires_aggregation else ""
            order_by_clause = f"\n            {order_clause}" if order_clause else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM idea_concept AS ic
                {join_clause_str}
                WHERE {where_clause_str}
                {group_by_clause}
                {order_by_clause};
            """

            # print("fetchIdeasDataWithProjectionAttrs query:\n", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            appLogger.error({
                "function": "fetchIdeasDataWithProjectionAttrs",
                "error": str(e),
                "data": {
                    "idea_ids": idea_ids,
                    "portfolio_ids": portfolio_ids,
                    "projection_attrs": projection_attrs,
                    "tenant_id": tenant_id,
                    "state_filter": state_filter,
                    "order_clause": order_clause
                }
            })
            return []

    @staticmethod
    def fetchPreviousIdeasOfTenant(tenant_id):
        query = f"""
        select title, short_description from idea_concept where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchDefaultIdeasStrategy(tenant_id):
        query = f"""
            SELECT title FROM public.idea_conceptstrategy where tenant_id = {tenant_id} and concept_id is null
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchDefaultIdeasKPIs(tenant_id):
        query = f"""
            SELECT title FROM public.idea_conceptkpi where tenant_id = {tenant_id} and concept_id is null
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchIdeaDetails(tenant_id, idea_id):
        query = f"""
            SELECT ic.*,
                json_agg(ickpi.title) AS list_of_kpis,
                json_agg(ics.title) AS list_of_strategies,
                json_agg(icc.name) AS list_of_constraints,
                json_agg(pp.title) AS list_of_portfolios,
                json_agg(icr.rating_type) AS ratings,
                json_agg(
                    distinct json_build_object(
                        'sponsor_first_name', ppb.sponsor_first_name,
                        'sponsor_last_name', ppb.sponsor_last_name
                    )::text
                ) AS list_of_businessmembers
            FROM idea_concept AS ic
            LEFT JOIN idea_conceptkpi AS ickpi ON ickpi.concept_id = ic.id
            LEFT JOIN idea_conceptstrategy AS ics ON ics.concept_id = ic.id
            LEFT join idea_conceptconstraints AS icc ON icc.concept_id = ic.id
            LEFT join idea_conceptportfolio AS icp ON icp.concept_id = ic.id
            LEFT join projects_portfolio AS pp ON pp.id = icp.portfolio_id
            LEFT join idea_conceptrating AS icr ON icr.concept_id = ic.id
            LEFT join idea_conceptbusinessmember AS icb ON icb.concept_id = ic.id
            LEFT join projects_portfoliobusiness AS ppb ON icb.portfolio_business_id = ppb.id
            WHERE ic.id = {idea_id}
            AND ic.tenant_id = {tenant_id}
            GROUP by ic.id;
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []
        
    @staticmethod
    def fetchIdeasIds(tenant_id):
        query = f"""
        select id as idea_id from idea_concept where tenant_id = {tenant_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        arr = []
        for r in result:
            arr.append(r.get("idea_id"))
        return arr
