from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from typing import List, Dict, Any


class ActionsDaoV2:
    """
    A flexible DAO for querying actions from the actions_actions table,
    with projection, joins, filters, and ordering support.
    """

    # Constants for polymorphic reference
    ACTION_REF_TYPE_IDEA = 1
    ACTION_REF_TYPE_ROADMAP = 2
    ACTION_REF_TYPE_PROJECT = 3
    ACTION_REF_TYPE_INSIGHT = 4

    ATTRIBUTE_MAP: Dict[str, Dict] = {
        "id": {"table": "aa", "column": "aa.id AS action_id"},
        "head_text": {"table": "aa", "column": "aa.head_text AS action_title"},
        "details_text": {"table": "aa", "column": "aa.details_text"},
        "tag": {"table": "aa", "column": "aa.tag"},
        "priority": {"table": "aa", "column": "aa.priority"},
        "created_date": {"table": "aa", "column": "aa.created_date"},
        "updated_date": {"table": "aa", "column": "aa.updated_date"},
        "due_date": {"table": "aa", "column": "aa.due_date"},
        "ref_id": {"table": "aa", "column": "aa.ref_id"},
        "ref_type": {"table": "aa", "column": "aa.ref_type"},
    }

    REF_OBJECT_JSON = """
        CASE
            WHEN aa.ref_type = {roadmap} THEN json_build_object(
                'ref_type', 'Roadmap',
                'ref_id', aa.ref_id,
                'ref_title', rr.title
            )
            WHEN aa.ref_type = {project} THEN json_build_object(
                'ref_type', 'Project',
                'ref_id', aa.ref_id,
                'ref_title', wp.title
            )
            WHEN aa.ref_type = {insight} THEN json_build_object(
                'ref_type', 'Insight',
                'ref_id', aa.ref_id,
                'ref_title', ai.head_text
            )
            ELSE json_build_object(
                'ref_type', 'Unknown',
                'ref_id', aa.ref_id
            )
        END AS ref_object
    """.format(
        roadmap=ACTION_REF_TYPE_ROADMAP,
        project=ACTION_REF_TYPE_PROJECT,
        insight=ACTION_REF_TYPE_INSIGHT,
    )


    @staticmethod
    def fetchActionsWithProjectionAttrs(
        action_ids: List[int] = None,
        projection_attrs: List[str] = ["id", "head_text", "priority"],
        tenant_id: int = None,
        user_id: int = None,
        due_date_before: str = None,
        due_date_after: str = None,
        order_clause: str = "ORDER BY aa.id ASC",
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch actions with specified projection attributes and optional filters.
        """

        try:
            select_clauses = []
            joins = set()
            where_conditions = []

            for attr in projection_attrs:
                if attr == "ref_object":
                    select_clauses.append(ActionsDaoV2.REF_OBJECT_JSON)

                    # joins for all possible referenced entities
                    joins.add("LEFT JOIN roadmap_roadmap AS rr ON rr.id = aa.ref_id AND aa.ref_type = 2")
                    joins.add("LEFT JOIN workflow_project AS wp ON wp.id = aa.ref_id AND aa.ref_type = 3")
                    joins.add("LEFT JOIN actions_insights AS ai ON ai.id = aa.ref_id AND aa.ref_type = 4")
                    # joins.add("LEFT JOIN ideas_idea AS ri ON ri.id = aa.ref_id AND aa.ref_type = 1")
                    continue

                mapping = ActionsDaoV2.ATTRIBUTE_MAP.get(attr)
                if not mapping:
                    continue

                select_clauses.append(mapping["column"])
                if "join" in mapping:
                    joins.add(mapping["join"])

            # Build WHERE filters dynamically
            if action_ids:
                where_conditions.append(f"aa.id IN ({', '.join(map(str, action_ids))})")
            if tenant_id:
                where_conditions.append(f"aa.tenant_id_id = {tenant_id}")
            if user_id:
                where_conditions.append(f"aa.user_id_id = {user_id}")
            if due_date_before:
                where_conditions.append(f"aa.due_date <= '{due_date_before}'")
            if due_date_after:
                where_conditions.append(f"aa.due_date >= '{due_date_after}'")

            select_clause_str = ",\n                ".join(select_clauses) if select_clauses else "aa.id"
            join_clause_str = "\n            ".join(joins)
            where_clause_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            order_by_clause = f"\n            {order_clause}" if order_clause else ""
            limit_clause = f"\n            LIMIT {limit}" if limit else ""

            query = f"""
                SELECT 
                    {select_clause_str}
                FROM actions_actions AS aa
                {join_clause_str}
                WHERE {where_clause_str}
                {order_by_clause}
                {limit_clause};
            """

            print("fetchActionsWithProjectionAttrs query:", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            appLogger.error({
                "function": "fetchActionsWithProjectionAttrs",
                "error": str(e),
            })
            return []
