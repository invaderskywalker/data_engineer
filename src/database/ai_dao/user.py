from typing import List, Dict, Any, Optional, Union
from datetime import date
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from .base import BaseDAOQueryBuilder
from .intel import FieldIntel


# -------------------------------------------------------------------------
# Users DAO V3 – Unified Registry & Auto-Manifest
# -------------------------------------------------------------------------
class UsersDaoV3:
    """
    Attribute-level DAO for tenant-scoped users.
    Users are first-class ENTITIES with strong PII semantics.
    """

    # ==============================================================
    # FIELD REGISTRY (Single Source of Truth)
    # ==============================================================

    FIELD_REGISTRY: Dict[str, Dict[str, Any]] = {
        "core": {
            "description": """
                Primary user identity and profile information.
                
                SEMANTICS:
                • Users are tenant-scoped entities.
                • PII fields MUST NOT be used as hard constraints unless explicitly requested.
                • Inactive or deleted users may still exist historically.
            """,
            "table": "users_user",
            "alias": "uu",
            "fields": {
                "user_id": "uu.id AS user_id",
                "username": "uu.username",
                "first_name": "uu.first_name",
                "last_name": "uu.last_name",
                "date_joined": "uu.date_joined",
                "last_login": "uu.last_login",
                "last_visit_date": "uu.last_visit_date",
                "login_counter": "uu.login_counter",
            },
            "intel": {
                # -------------------
                # PII TEXT
                # -------------------
                "first_name": {"type": "pii_text", "column": "uu.first_name"},
                "last_name": {"type": "pii_text", "column": "uu.last_name"},
                "username": {"type": "pii_text", "column": "uu.username"},

                # -------------------
                # DATE FIELDS
                # -------------------
                "date_joined": {"type": "date"},
                "last_login": {"type": "date"},
                "last_visit_date": {"type": "date"},

                # -------------------
                # NUMERIC
                # -------------------
                "login_counter": {"type": "number"},
            },
        },
    }

    # ==============================================================
    # CORE FETCHER
    # ==============================================================

    @staticmethod
    def fetch_core(
        user_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        time_bucket: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> List[Dict]:

        meta = UsersDaoV3.FIELD_REGISTRY["core"]
        alias = meta["alias"]
        all_fields = meta["fields"]
        intel = meta.get("intel", {})

        # ---------------------------------------------------------
        # BASE WHERE — tenant-scoped
        # ---------------------------------------------------------
        where = [f"{alias}.tenant_id = %s"]
        params: List[Any] = [tenant_id]

        if user_ids:
            where.append(f"{alias}.id = ANY(%s)")
            params.append(user_ids)

        # ---------------------------------------------------------
        # NORMALIZE FILTERS (FieldIntel)
        # ---------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=all_fields,
            alias=alias
        )

        # ---------------------------------------------------------
        # TIME BUCKET (rare, but supported)
        # ---------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field", "date_joined")
            bucket_interval = time_bucket.get("interval", "month")
            bucket_alias_field = time_bucket.get("alias") or bucket_field
        elif isinstance(time_bucket, str):
            bucket_field = "date_joined"
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
    # SCHEMA EXPOSURE (MANDATORY FOR AIDAO)
    # ==============================================================

    @staticmethod
    def get_available_attributes() -> Dict[str, Any]:
        return USERS_DATA_MANIFEST


# ==============================================================
# AUTO-GENERATED MANIFEST
# ==============================================================

USERS_DATA_MANIFEST: Dict[str, Any] = {}

for section, meta in UsersDaoV3.FIELD_REGISTRY.items():
    fn_name = f"fetch_{section}"
    fn = getattr(UsersDaoV3, fn_name, None)

    if fn is None:
        appLogger.warning(f"DAO function {fn_name} not found for section {section}")
        continue

    USERS_DATA_MANIFEST[section] = {
        "dao_function": fn,
        "important_info_to_be_understood_by_llm": meta["description"],
        "fields": list(meta["fields"].keys()),
        "sql_mapping": meta["fields"],
        "filters": meta.get("extra_filters", {}),
        "intel": meta.get("intel")
    }
