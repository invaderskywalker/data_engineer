from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from typing import List, Dict

class ProjectsDaoV2:
    
    ATTRIBUTE_MAP: Dict[str, Dict] = {
        "id": {"table": "wp", "column": "id"},
        "title": {"table": "wp", "column": "title"},
        "description": {"table": "wp", "column": "description"},
        "objectives": {"table": "wp", "column": "objectives"},
        "technology_stack": {"table": "wp", "column": "technology_stack"},
        "project_category": {"table": "wp", "column": "project_category"},
        "start_date": {"table": "wp", "column": "start_date"},
        "end_date": {"table": "wp", "column": "end_date"},
        "key_accomplishments": {"table": "wp", "column": "key_accomplishments"},
        "project_budget": {"table": "wp", "column": "total_external_spend AS project_budget"},
        "org_strategy": {"table": "wp", "column": "org_strategy_align AS org_strategy"},
        "program_id": {"table": "wp", "column": "program_id"},
        "project_manager_id_id": {"table": "wp", "column": "project_manager_id_id"},
        "stage": {"table": "wp", "column": "state AS stage"},
        "program_name": {
            "table": "pp",
            "column": "pp.name AS program_name",
            "join": """
                LEFT JOIN program_program AS pp ON wp.program_id = pp.id
            """,
            "group_by": False
        },
        "key_results": {
            "table": "wpkpi",
            "column": "ARRAY_AGG(DISTINCT wpkpi.name) AS key_results",
            "join": """
                LEFT JOIN workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id
            """,
            "group_by": False
        },
        "scope": {
            "table": "wps",
            "column": "ARRAY_AGG(DISTINCT jsonb_build_object('scope', wps.scope)) AS scope",
            "join": """
                LEFT JOIN workflow_projectscope AS wps ON wps.project_id = wp.id
            """,
            "group_by": False
        },
        "status": {
            "table": "ps",
            "column": """
                ps.scope_completion_percent,
                ps.status_comments
            """,
            "join": """
                LEFT JOIN LATERAL (
                    SELECT
                        -- latest scope completion %
                        MAX(
                            CASE
                                WHEN s.type = 1 THEN s.actual_percentage
                            END
                        ) FILTER (WHERE s.rn = 1) AS scope_completion_percent,

                        -- last 10 status comments (all types)
                        ARRAY_AGG(
                            jsonb_build_object(
                                'type', CASE
                                    WHEN s.type = 1 THEN 'scope_status'
                                    WHEN s.type = 2 THEN 'schedule_status'
                                    WHEN s.type = 3 THEN 'spend_status'
                                END,
                                'value', CASE
                                    WHEN s.value = 1 THEN 'on_track'
                                    WHEN s.value = 2 THEN 'at_risk'
                                    WHEN s.value = 3 THEN 'compromised'
                                END,
                                'comment', s.comments,
                                'timestamp', s.created_date,
                                'detailed_status', s.detailed_status
                            )
                            ORDER BY s.created_date DESC
                        ) FILTER (WHERE s.rn <= 10) AS status_comments

                    FROM (
                        SELECT
                            ps.*,
                            ROW_NUMBER() OVER (
                                PARTITION BY ps.type
                                ORDER BY ps.created_date DESC
                            ) AS rn
                        FROM workflow_projectstatus ps
                        WHERE ps.project_id = wp.id
                    ) s
                ) ps ON true
            """,
            "group_by": False,
            "raw": True,
        }


    }

    @staticmethod
    def fetchProjectsDataWithProjectionAttrs(
        project_ids: List[int] = None,
        projection_attrs: List[str] = ["id", "title"],
        program_id: int = None,
        tenant_id: int = None,
        include_archived: bool = False,
        include_parent: bool = False,
        project_manager_id: int = None,
    ):
        """
        Fetch project data with specified projection attributes, optionally filtering by project_ids or program_id.
        
        Args:
            project_ids (List[int], optional): List of project IDs to filter by.
            program_id (int, optional): Program ID to filter projects by.
            projection_attrs (List[str]): Attributes to include in the result.
            tenant_id (int, optional): Tenant ID to filter projects by.
            include_archived (bool): Whether to include archived projects.
        
        Returns:
            List of project data dictionaries.
        """
        try:
            # Initialize query components
            select_clauses = []
            joins = set()
            group_by_clauses = set()
            where_conditions = []

            # Check if aggregation is required (e.g., for key_results)
            requires_aggregation = any(
                "ARRAY_AGG" in ProjectsDaoV2.ATTRIBUTE_MAP.get(attr, {}).get("column", "")
                for attr in projection_attrs
            )

            # Build SELECT and JOIN clauses based on projection attributes
            for attr in projection_attrs:
                mapping = ProjectsDaoV2.ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue
                # Use table alias explicitly in SELECT clause
                column = mapping["column"]
                if not mapping.get("raw"):
                    if "AS" not in column and mapping["table"]:
                        column = f"{mapping['table']}.{column}"
                        
                select_clauses.append(column)
                if "join" in mapping:
                    joins.add(mapping["join"])
                if mapping.get("group_by", True) and requires_aggregation:
                    # Use table alias in GROUP BY clause
                    group_by_column = mapping["column"].split(" AS ")[0]
                    if "AS" not in mapping["column"] and mapping["table"]:
                        group_by_column = f"{mapping['table']}.{group_by_column}"
                    group_by_clauses.add(group_by_column)

            # Add pp.name to GROUP BY if program_name is selected and aggregation is required
            if "program_name" in projection_attrs and requires_aggregation:
                group_by_clauses.add("pp.name")

            # Construct WHERE clause
            if project_ids:
                project_ids_str = f"({', '.join(map(str, project_ids))})"
                where_conditions.append(f"wp.id IN {project_ids_str}")
            if program_id:
                where_conditions.append(f"wp.program_id = {program_id}")
            if tenant_id:
                where_conditions.append(f"wp.tenant_id_id = {tenant_id}")
            if not include_archived:
                where_conditions.append("wp.archived_on IS NULL")
            if not include_parent:
                where_conditions.append("wp.parent_id IS NOT NULL")
            if project_manager_id is not None:
                where_conditions.append(f"wp.project_manager_id_id = {project_manager_id}")
            

            # Combine clauses
            select_clause_str = ",\n                ".join(select_clauses) if select_clauses else "wp.id"
            join_clause_str = "\n            ".join(joins)
            where_clause_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            group_by_clause = f"\n            GROUP BY {', '.join(group_by_clauses)}" if group_by_clauses and requires_aggregation else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM workflow_project AS wp
                {join_clause_str}
                WHERE {where_clause_str}
                {group_by_clause};
            """
            
            # print("query in fetchProjectsDataWithProjectionAttrs:\n", query)
            return db_instance.retrieveSQLQueryOld(query)
        
        except Exception as e:
            appLogger.error({
                "function": "fetchProjectsDataWithProjectionAttrs",
                "error": str(e),
                "data": {
                    "project_ids": project_ids,
                    "program_id": program_id,
                    "projection_attrs": projection_attrs,
                    "tenant_id": tenant_id
                }
            })
            return []


    @staticmethod
    def fetch_all_child_projects(tenant_id: int, include_archived: bool = False):
        try:
            query = f"""
                SELECT id FROM workflow_project
                WHERE tenant_id_id = {tenant_id}
                AND parent_id IS NOT NULL
                {"AND archived_on IS NULL" if not include_archived else ""}
            """
            print("query in fetch_all_child_projects:\n", query)
            rows = db_instance.retrieveSQLQueryOld(query)
            return [row['id'] for row in rows]

        except Exception as e:
            appLogger.error({
                "function": "fetch_all_child_projects",
                "error": str(e),
                "data": {"tenant_id": tenant_id}
            })
            return []
        
    @staticmethod
    def update_org_strategy(project_id: int, org_strategy_str: str):
        try:
            query = f"""
                UPDATE workflow_project
                SET org_strategy_align = %s
                WHERE id = %s
            """
            print(f"Running update query for project_id {project_id} with strategy '{org_strategy_str}'")
            db_instance.executeSQLQuery(query, (org_strategy_str, project_id))
            return True
        except Exception as e:
            appLogger.error({
                "function": "update_org_strategy",
                "error": str(e),
                "data": {"project_id": project_id}
            })
            return False
        
    @staticmethod
    def fetchTenantIdAndCreatedByIDForProjectId(project_id):
        try:
            query = f"""
                SELECT tenant_id_id as tenant_id, created_by_id as user_id
                from workflow_project
                where id = {project_id}
            """
            res = db_instance.retrieveSQLQueryOld(query)
            if len(res) > 0:
                return res[0]
            return None
        except Exception as e:
            return None
        
        

