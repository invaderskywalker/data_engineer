from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from typing import List, Dict


class RoadmapsDaoV2:

    ATTRIBUTE_MAP: Dict[str, Dict] = {
        "id": {"table": "rr", "column": "rr.id AS roadmap_id"},
        "title": {"table": "rr", "column": "rr.title AS roadmap_title"},
        "description": {"table": "rr", "column": "rr.description AS roadmap_description"},
        "objectives": {"table": "rr", "column": "rr.objectives"},
        "org_strategy": {"table": "rr", "column": "rr.org_strategy_align AS roadmap_org_strategy_alignment"},
        "start_date": {"table": "rr", "column": "rr.start_date"},
        "end_date": {"table": "rr", "column": "rr.end_date"},
        "budget": {"table": "rr", "column": "rr.budget AS roadmap_budget"},
        "category": {"table": "rr", "column": "rr.category AS roadmap_category"},
        "roadmap_priority": {"table": "rr", "column": "rr.rank AS roadmap_priority"},
        "current_state": {
            "table": "rr",
            "column": """CASE 
                WHEN rr.current_state = 0 THEN 'Intake'
                WHEN rr.current_state = 1 THEN 'Approved'
                WHEN rr.current_state = 2 THEN 'Execution'
                WHEN rr.current_state = 3 THEN 'Archived'
                WHEN rr.current_state = 4 THEN 'Elaboration'
                WHEN rr.current_state = 5 THEN 'Solutioning'
                WHEN rr.current_state = 6 THEN 'Prioritize'
                WHEN rr.current_state = 99 THEN 'Hold'
                WHEN rr.current_state = 100 THEN 'Rejected'
                WHEN rr.current_state = 999 THEN 'Cancelled'
                WHEN rr.current_state = 200 THEN 'Draft'
                ELSE 'Unknown'
            END AS current_state"""
        },
        "constraints": {
            "table": "rrc",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'constraint_title', rrc.name,
                    'constraint_type', CASE
                        WHEN rrc.type = 1 THEN 'Cost'
                        WHEN rrc.type = 2 THEN 'Risk'
                        WHEN rrc.type = 3 THEN 'Resource'
                        ELSE 'Other'
                    END
                )::text
            ) FILTER (WHERE rrc.name IS NOT NULL) as roadmap_constraints""",
            "join": "LEFT JOIN roadmap_roadmapconstraints AS rrc ON rr.id = rrc.roadmap_id",
            "group_by": False
        },
        "portfolios": {
            "table": "pp",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'portfolio_id', pp.id,
                    'portfolio_title', pp.title,
                    'roadmap_priority_in_portfolio', rp.rank
                )::text
            ) FILTER (WHERE pp.id IS NOT NULL) as roadmap_portfolios""",
            "join": """
                LEFT JOIN roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
                LEFT JOIN projects_portfolio AS pp ON rp.portfolio_id = pp.id
            """,
            "group_by": False
        },
        "key_results": {
            "table": "rrkpi",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'key_result_title', rrkpi.name,
                    'baseline_value', rrkpi.baseline_value
                )::text
            ) FILTER (WHERE rrkpi.name IS NOT NULL) as roadmap_key_results""",
            "join": "LEFT JOIN roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id",
            "group_by": False
        },
        "dependencies": {
            "table": "rr",
            "column": """
                COALESCE((
                    SELECT json_agg(
                        DISTINCT jsonb_build_object(
                            'relation',
                                CASE 
                                    WHEN d.roadmap_id = rr.id 
                                        THEN 'depends_on'
                                    ELSE 'required_by'
                                END,
                            'dependency_reason', d.description,
                            'dependency_type', 
                                CASE d.dependency_type
                                    WHEN 1 THEN 'Technical'
                                    WHEN 2 THEN 'Functional'
                                    WHEN 3 THEN 'Resource'
                                    WHEN 4 THEN 'Sequence'
                                    WHEN 5 THEN 'Risk'
                                    WHEN 6 THEN 'Compliance'
                                    ELSE 'Unknown'
                                END,
                            'dependency_type_code', d.dependency_type,
                            
                            -- REQUIRED: Include related roadmap ID
                            'related_roadmap_id',
                                CASE 
                                    WHEN d.roadmap_id = rr.id 
                                        THEN d.dependent_roadmap_id
                                    ELSE d.roadmap_id
                                END,

                            -- TITLE of the related roadmap
                            'related_roadmap_title', r2.title
                        )
                    )
                    FROM public.roadmap_roadmap_dependency d
                    LEFT JOIN roadmap_roadmap r2 
                        ON r2.id = CASE 
                                        WHEN d.roadmap_id = rr.id 
                                            THEN d.dependent_roadmap_id
                                        ELSE d.roadmap_id
                                END
                        AND r2.tenant_id = rr.tenant_id
                    WHERE 
                        d.tenant_id = rr.tenant_id
                        AND (
                            d.roadmap_id = rr.id 
                            OR d.dependent_roadmap_id = rr.id
                        )
                ), '[]'::json) AS roadmap_dependencies
            """,
            "group_by": False
        },
        "team_data": {
            "table": "rrt",
            "column": """json_agg(
                DISTINCT json_build_object(
                    'team_name', rrt.name,
                    'team_unit_size', rrt.unit,
                    'unit_type', CASE
                        WHEN rrt.type = 1 THEN 'days'
                        WHEN rrt.type = 2 THEN 'months'
                        WHEN rrt.type = 3 THEN 'weeks'
                        WHEN rrt.type = 4 THEN 'hours'
                        ELSE 'Unknown'
                    END,
                    'labour_type', CASE
                        WHEN rrt.labour_type = 1 THEN 'labour'
                        WHEN rrt.labour_type = 2 THEN 'non labour'
                        ELSE 'Unknown'
                    END,
                    'description', rrt.description,
                    'start_date', rrt.start_date,
                    'end_date', rrt.end_date,
                    'location', rrt.location,
                    'allocation', rrt.allocation,
                    'total_estimated_hours',
                    CASE
                        WHEN rrt.type = 1 THEN rrt.unit * 8
                        WHEN rrt.type = 2 THEN rrt.unit * 160
                        WHEN rrt.type = 3 THEN rrt.unit * 40
                        WHEN rrt.type = 4 THEN rrt.unit
                        ELSE 0
                    END,
                    'total_estimated_cost',
                    CASE
                        WHEN rrt.labour_type = 1 THEN 
                            COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0) * 
                            CASE
                                WHEN rrt.type = 1 THEN rrt.unit * 8
                                WHEN rrt.type = 2 THEN rrt.unit * 160
                                WHEN rrt.type = 3 THEN rrt.unit * 40
                                WHEN rrt.type = 4 THEN rrt.unit
                                ELSE 0
                            END
                        WHEN rrt.labour_type = 2 THEN COALESCE(NULLIF(rrt.estimate_value, '')::NUMERIC, 0)
                        ELSE 0
                    END
                )::text
            ) FILTER (WHERE rrt.name IS NOT NULL) AS team_data""",
            "join": "LEFT JOIN roadmap_roadmapestimate AS rrt ON rrt.roadmap_id = rr.id",
            "group_by": False
        }
    }

    @staticmethod
    def fetchRoadmapsDataWithProjectionAttrs(
        roadmap_ids: List[int] = None,
        projection_attrs: List[str] = ["id", "title"],
        portfolio_ids: List[int] = None,
        tenant_id: int = None,
        state_filter: str = None,
        order_clause: str = None
    ):
        """
        Fetch roadmap data with specified projection attributes, optionally filtering by roadmap_ids, portfolios, state, and tenant.
        """
        try:
            select_clauses = []
            joins = set()
            group_by_clauses = set()
            where_conditions = []

            requires_aggregation = any(
                "json_agg" in RoadmapsDaoV2.ATTRIBUTE_MAP.get(attr, {}).get("column", "")
                for attr in projection_attrs
            )

            for attr in projection_attrs:
                mapping = RoadmapsDaoV2.ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue
                column = mapping["column"]
                select_clauses.append(column)
                if "join" in mapping:
                    joins.add(mapping["join"])
                if mapping.get("group_by", True) and requires_aggregation:
                    group_by_column = mapping["column"].split(" AS ")[0]
                    group_by_clauses.add(group_by_column)

            if roadmap_ids:
                roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
                where_conditions.append(f"rr.id IN {roadmap_ids_str}")
            if portfolio_ids:
                portfolio_ids_str = f"({', '.join(map(str, portfolio_ids))})"
                where_conditions.append(f"pp.id IN {portfolio_ids_str}")
            if tenant_id:
                where_conditions.append(f"rr.tenant_id = {tenant_id}")
            if state_filter:
                where_conditions.append(state_filter)

            select_clause_str = ",\n                ".join(select_clauses) if select_clauses else "rr.id"
            join_clause_str = "\n            ".join(joins)
            where_clause_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            group_by_clause = f"\n            GROUP BY {', '.join(group_by_clauses)}" if group_by_clauses and requires_aggregation else ""
            order_by_clause = f"\n            {order_clause}" if order_clause else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM roadmap_roadmap AS rr
                {join_clause_str}
                WHERE {where_clause_str}
                {group_by_clause}
                {order_by_clause};
            """
            
            print("fetchRoadmapsDataWithProjectionAttrs query ", query)

            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            appLogger.error({
                "function": "fetchRoadmapsDataWithProjectionAttrs",
                "error": str(e),
                "data": {
                    "roadmap_ids": roadmap_ids,
                    "portfolio_ids": portfolio_ids,
                    "projection_attrs": projection_attrs,
                    "tenant_id": tenant_id,
                    "state_filter": state_filter,
                    "order_clause": order_clause
                }
            })
            return []
