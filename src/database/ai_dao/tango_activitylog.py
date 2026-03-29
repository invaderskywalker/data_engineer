from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


# -------------------------------------------------------------------------
# Tango Activity Log DAO V3 – Execution Telemetry
# -------------------------------------------------------------------------
class TangoActivityLogDaoV3:
    """
    Attribute-level DAO for Tango AI activity logs.

    SEMANTICS:
    • Activity logs are EVIDENCE, not entities.
    • They NEVER define existence of users/projects.
    • They are time-series diagnostics and analytics signals.
    """

    # ==============================================================
    # FIELD REGISTRY
    # ==============================================================

    FIELD_REGISTRY: Dict[str, Dict[str, Any]] = {
        "core": {
            "description": """
                Execution-level activity logs for Tango AI agents and workflows.

                ANALYTICAL RULES:
                • Logs are evidence only.
                • Absence of logs does NOT imply absence of usage.
                • Safe for trend analysis, diagnostics, and aggregation.
                • NEVER identity-defining.
            """,
            "table": "tango_activitylog",
            "alias": "tal",
            "fields": {
                "tango_activity_log_id": "tal.id AS tango_activity_log_id",
                # "session_id": "tal.session_id",
                "agent_or_workflow_name": "tal.agent_or_workflow_name AS agent_or_workflow_name",
                # "status": "tal.status AS ",
                "created_date": "tal.created_date",

                # "tenant_id": "tal.tenant_id",
                # "user_id": "tal.user_id",
            },
            "intel": {
                # -------------------
                # ENUM / STATE
                # -------------------
                # "status": {
                #     "type": "enum",
                #     "column": "tal.status",
                #     "mapping": {
                #         "success": "success",
                #         "failed": "failed",
                #         "error": "error",
                #         "timeout": "timeout",
                #     }
                # },

                # -------------------
                # TEXT
                # -------------------
                "agent_or_workflow_name": {"type": "text"},

                # -------------------
                # DATE / TIME
                # -------------------
                "created_date": {"type": "date"},
            },
        },
    }

    # ==============================================================
    # CORE FETCHER
    # ==============================================================

    @staticmethod
    def fetch_core(
        activity_ids: Optional[List[str]] = None,
        tenant_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> List[Dict]:

        meta = TangoActivityLogDaoV3.FIELD_REGISTRY["core"]
        alias = meta["alias"]
        all_fields = meta["fields"]
        intel = meta.get("intel", {})

        # ---------------------------------------------------------
        # BASE WHERE — tenant scoped
        # ---------------------------------------------------------
        where = []
        params: List[Any] = []

        if tenant_id:
            where.append(f"{alias}.tenant_id = %s")
            params.append(tenant_id)

        if activity_ids:
            where.append(f"{alias}.id = ANY(%s)")
            params.append(activity_ids)

        # if user_ids:
        #     where.append(f"{alias}.user_id = ANY(%s)")
        #     params.append(user_ids)

        # ---------------------------------------------------------
        # NORMALIZE FILTERS (ENUM / DATE / TEXT)
        # ---------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=alias
        )

        # ---------------------------------------------------------
        # TIME BUCKET (FIRST-CLASS)
        # ---------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "created_date")
            bucket_interval = time_bucket.get("interval", "hour")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "created_date"
            bucket_interval = time_bucket
            bucket_alias_field = bucket_field

        # ---------------------------------------------------------
        # BUILD QUERY
        # ---------------------------------------------------------
        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            order_by=order_by,
            limit=limit,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        results = FieldIntel.post_process(results, intel)
        return results

    # ==============================================================
    # PAYLOAD FETCHER
    # ==============================================================

    @staticmethod
    def fetch_payload(
        activity_ids: List[str],
        fields: Optional[List[str]] = None,
        **kwargs
    ) -> List[Dict]:

        meta = TangoActivityLogDaoV3.FIELD_REGISTRY["payload"]
        all_fields = meta["fields"]
        intel = meta.get("intel", {})

        where = ["tal.id = ANY(%s)"]
        params = [activity_ids]

        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias="tal",
            table_name=meta["table"],
            fields=all_fields,
            selected_fields=fields,
            where_clauses=where,
            params=params,
        )

        results = db_instance.execute_query_safe(query, params_tuple)
        return FieldIntel.post_process(results, intel)

    # ==============================================================
    # SCHEMA EXPOSURE (AIDAO)
    # ==============================================================

    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return TANGO_ACTIVITYLOG_DATA_MANIFEST


# ==============================================================
# AUTO-GENERATED MANIFEST
# ==============================================================

TANGO_ACTIVITYLOG_DATA_MANIFEST: Dict[str, Any] = {}

TANGO_ACTIVITYLOG_DATA_MANIFEST["overall_description"] = """
    This represent the the usage of the AI agentic workflows used by customers
    to speed up their processes
    and free their time
    etc
"""

for section, meta in TangoActivityLogDaoV3.FIELD_REGISTRY.items():
    fn_name = f"fetch_{section}"
    fn = getattr(TangoActivityLogDaoV3, fn_name, None)

    if fn is None:
        appLogger.warning(f"DAO function {fn_name} not found for section {section}")
        continue

    TANGO_ACTIVITYLOG_DATA_MANIFEST[section] = {
        "dao_function": fn,
        "important_info_to_be_understood_by_llm": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "filters": meta.get("extra_filters", {}),
    }
