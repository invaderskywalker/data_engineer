from typing import List, Dict, Any, Optional, Union
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


class TangoConversationDaoV3:
    """
    DAO for Tango conversation data.
    Semantic entity: conversation session
    """

    FIELD_REGISTRY = {

        # ---------------------------------------------------------
        # CORE — SESSION IDENTITY
        # ---------------------------------------------------------
        "core": {
            "description": """
                Simply a table for questions asked by user and response give n by system
            """,
            "table": "tango_tangoconversations",
            "alias": "tc",
            "fields": {
                "tango_conversation_id": "tc.id AS tango_conversation_id",
                # "session_id": "tc.session_id AS session_id",
                "user_id": "tc.created_by_id AS user_id",
                "user_first_name": "uu.first_name AS user_first_name",
                "message_created_date": "tc.created_date AS message_created_date",
                
                "message_intent": "tc.type AS message_intent",
                # "msg_actor": "tc.type AS msg_actor",
                "content": "tc.message AS content",
            },
            "intel": {
                "message_intent": {
                    "type": "enum",
                    "column": "tc.type",
                    "mapping": {
                        "question": 1,
                        "user": 1,
                        "system_response": 3,
                        "system": 3,
                    }
                },
                
                # "msg_sctor": {
                #     "type": "enum",
                #     "column": "tc.type",
                #     "mapping": {
                #         # "question": 1,
                #         "user": 1,
                #         # "system_response": 3,
                #         "system": 3,
                #     }
                # },
                
                "user_first_name": {"type": "pii_text", "column": "uu.first_name"},
                "user_last_name": {"type": "pii_text", "column": "uu.last_name"},
            },
            "where_extra": "tc.type = 1",
            "joins": [
                "LEFT JOIN users_user uu ON tc.created_by_id = uu.id",
            ]
        },
    }

    # ---------------------------------------------------------
    # INTERNAL
    # ---------------------------------------------------------
    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        try:
            return TangoConversationDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown TangoConversation section: {section}") from exc

    # ---------------------------------------------------------
    # CORE FETCH
    # ---------------------------------------------------------
    @staticmethod
    def fetch_core(
        session_ids: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> List[Dict]:

        meta = TangoConversationDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = []
        params: List[Any] = []
        
        if tenant_id:
            where.append("uu.tenant_id = %s")
            params.append(tenant_id)

        if session_ids:
            where.append("tc.session_id = ANY(%s)")
            params.append(session_ids)

        if user_id:
            where.append("tc.created_by_id = %s")
            params.append(user_id)
            
        # ---------------------------------------------------------
        # APPLY STATIC WHERE (semantic constraint)
        # ---------------------------------------------------------
        where_extra = meta.get("where_extra")
        if where_extra:
            where.append(where_extra)

        normalized_filters = FieldIntel.normalize_filters(
            filters or {},
            intel=intel,
            fields=all_fields,
            alias=meta["alias"]
        )

        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "session_start")
            bucket_interval = time_bucket.get("interval", "day")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "session_start"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=meta["alias"],
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            group_by=["session_id", "user_id", "chat_mode"],
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
            order_by=order_by,
            limit=limit,
            joins=meta.get("joins") or [],
        )

        results= db_instance.execute_query_safe(query, params_tuple)
        results = FieldIntel.post_process(results, intel)
        return results

    # ---------------------------------------------------------
    # PUBLIC MANIFEST
    # ---------------------------------------------------------
    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return TANGO_CONVERSATION_DATA_MANIFEST


# -------------------------------------------------------------
# AUTO-MANIFEST
# -------------------------------------------------------------
TANGO_CONVERSATION_DATA_MANIFEST: Dict[str, Any] = {}

TANGO_CONVERSATION_DATA_MANIFEST["overall_description"] = """
    Tango is an AI powered Chatbot for Trmeric which can
    answer any of the customer question on the data present in platform
    like roadmaps, projects, portfolios, ideas, project execution etc.
"""

for section, meta in TangoConversationDaoV3.FIELD_REGISTRY.items():
    fn = getattr(TangoConversationDaoV3, f"fetch_{section}", None)
    if not fn:
        appLogger.warning(f"Missing fetch_{section} in TangoConversationDaoV3")
        continue

    TANGO_CONVERSATION_DATA_MANIFEST[section] = {
        "dao_function": fn,
        "description": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "intel": meta.get("intel")
    }
