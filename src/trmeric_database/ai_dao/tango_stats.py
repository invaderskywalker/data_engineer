from typing import List, Dict, Any, Optional, Union
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


class TangoStatsDaoV3:
    """
    DAO for Tango LLM usage statistics.
    Semantic entity: LLM execution event (telemetry)
    """

    FIELD_REGISTRY = {

        "core": {
            "description": """
                LLM execution telemetry.
                Each row represents a model invocation or execution slice.
                NOT session-aligned. NOT message-aligned.
            """,
            "table": "tango_stats",
            "alias": "ts",
            "fields": {
                "stat_id": "ts.id AS stat_id",
                "model": "ts.model",
                "function": "ts.function",
                "total_tokens": "ts.total_tokens",
                "prompt_tokens": "ts.prompt_tokens",
                "completion_tokens": "ts.completion_tokens",
                "created_date": "ts.created_date",
                "user_id": "ts.user_id",
                "tenant_id": "ts.tenant_id",
            },
            "intel": {
                "model": {"type": "text"},
                "function": {"type": "text"},
                "created_date": {"type": "date"},
                "total_tokens": {"type": "number"},
                "prompt_tokens": {"type": "number"},
                "completion_tokens": {"type": "number"},
            }
        }
    }

    # ---------------------------------------------------------
    # INTERNAL
    # ---------------------------------------------------------
    @staticmethod
    def _get_section(section: str) -> Dict[str, Any]:
        try:
            return TangoStatsDaoV3.FIELD_REGISTRY[section]
        except KeyError as exc:
            raise ValueError(f"Unknown TangoStats section: {section}") from exc

    # ---------------------------------------------------------
    # CORE FETCH
    # ---------------------------------------------------------
    @staticmethod
    def fetch_core(
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:

        meta = TangoStatsDaoV3._get_section("core")
        intel = meta.get("intel", {})
        all_fields = meta["fields"]

        where = []
        params: List[Any] = []

        if user_id:
            where.append("ts.user_id = %s")
            params.append(user_id)

        if tenant_id:
            where.append("ts.tenant_id = %s")
            params.append(tenant_id)

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
            bucket_field = time_bucket.get("field", "created_date")
            bucket_interval = time_bucket.get("interval", "day")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "created_date"
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
            group_by=group_by,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
            order_by=order_by,
            limit=limit,
        )

        return db_instance.execute_query_safe(query, params_tuple)

    # ---------------------------------------------------------
    # PUBLIC MANIFEST
    # ---------------------------------------------------------
    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return TANGO_STATS_DATA_MANIFEST


# -------------------------------------------------------------
# AUTO-MANIFEST
# -------------------------------------------------------------
TANGO_STATS_DATA_MANIFEST: Dict[str, Any] = {}

for section, meta in TangoStatsDaoV3.FIELD_REGISTRY.items():
    fn = getattr(TangoStatsDaoV3, f"fetch_{section}", None)
    if not fn:
        appLogger.warning(f"Missing fetch_{section} in TangoStatsDaoV3")
        continue

    TANGO_STATS_DATA_MANIFEST[section] = {
        "dao_function": fn,
        "description": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
    }
