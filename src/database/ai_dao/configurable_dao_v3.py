from typing import List, Dict, Any, Optional
from functools import lru_cache

from src.database.Database import db_instance
from src.database.models import (
    DAOAttribute,
    DAOField,
    DAOFieldIntel,
)

from .intel import FieldIntel
from .base import BaseDAOQueryBuilder

# ==============================================================

# CONFIG LOADER (DB → RUNTIME)

# ==============================================================

class DAOConfigLoader:

    @staticmethod
    @lru_cache(maxsize=128)
    def load_attr(entity_type: str, attr_name: str) -> Dict[str, Any]:
        """
        Loads full config for an attribute from DB.
        Cached for performance.
        """

        session = db_instance.get_session()

        attr = (
            session.query(DAOAttribute)
            .filter_by(
                entity_type=entity_type,
                attr_name=attr_name,
                is_active=True
            )
            .first()
        )

        if not attr:
            raise ValueError(f"No config found for {entity_type}.{attr_name}")

        fields = session.query(DAOField).filter_by(attr_id=attr.id).all()
        intel_rows = session.query(DAOFieldIntel).filter_by(attr_id=attr.id).all()

        # Build fields map
        fields_map = {f.field_name: f.sql_expression for f in fields}

        # Build intel map
        intel: Dict[str, Any] = {}
        for row in intel_rows:
            intel[row.field_name] = {
                "type": row.type,
                "column": row.column_name,
                "mapping": row.mapping or {},
            }

        return {
            "meta": attr,
            "fields": fields_map,
            "intel": intel,
        }

    @staticmethod
    def clear_cache():
        """Manual cache invalidation (use when configs change)."""
        DAOConfigLoader.load_attr.cache_clear()

# ==============================================================
# UNIVERSAL CONFIGURABLE DAO (V3)
# ==============================================================

class ConfigurableDAO:
    """
    Universal DAO Engine.
    - Works for ANY entity (project, roadmap, etc.)
    - Fully driven by DB configuration
    - Single execute() method
    """

    def __init__(self, entity_type: str):
        self.entity_type = entity_type

    # ----------------------------------------------------------
    # MAIN EXECUTE FUNCTION
    # ----------------------------------------------------------
    def execute(
        self,
        attr: str,
        entity_ids: Optional[List[int]] = None,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        time_bucket: Optional[Any] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:

        # ------------------------------------------------------
        # 1️⃣ Load configuration
        # ------------------------------------------------------
        cfg = DAOConfigLoader.load_attr(self.entity_type, attr)

        meta = cfg["meta"]
        fields_map = cfg["fields"]
        intel = cfg["intel"]

        alias = meta.table_alias

        # ------------------------------------------------------
        # 2️⃣ Base WHERE conditions
        # ------------------------------------------------------
        where: List[str] = list(meta.base_where or [])
        params: List[Any] = []

        # ------------------------------------------------------
        # 3️⃣ Tenant filter
        # ------------------------------------------------------
        if tenant_id:
            where.append(f"{alias}.tenant_id_id = %s")
            params.append(tenant_id)

        # ------------------------------------------------------
        # 4️⃣ Entity filter (project_id / roadmap_id etc.)
        # ------------------------------------------------------
        if entity_ids:
            where.append(f"{alias}.{meta.id_field} = ANY(%s)")
            params.append(entity_ids)

        # ------------------------------------------------------
        # 5️⃣ Extra WHERE from config
        # ------------------------------------------------------
        if meta.where_extra:
            where.append(meta.where_extra)

        # ------------------------------------------------------
        # 6️⃣ Normalize filters using Intel layer
        # ------------------------------------------------------
        normalized_filters = FieldIntel.normalize_filters(
            filters=filters or {},
            intel=intel,
            fields=fields_map,
            alias=alias,
        )

        # ------------------------------------------------------
        # 7️⃣ Time bucket handling
        # ------------------------------------------------------
        bucket_interval = None
        bucket_field = None
        bucket_alias_field = None

        if isinstance(time_bucket, dict):
            bucket_field = time_bucket.get("field")
            bucket_interval = time_bucket.get("interval")
            bucket_alias_field = time_bucket.get("alias") or bucket_field

        elif isinstance(time_bucket, str):
            bucket_interval = time_bucket

        # ------------------------------------------------------
        # 8️⃣ Build SQL query
        # ------------------------------------------------------
        query, params_tuple = BaseDAOQueryBuilder.build_query(
            table_alias=alias,
            table_name=meta.table_name,
            joins=meta.joins or [],
            fields=fields_map,
            selected_fields=fields,
            filters=normalized_filters,
            where_clauses=where,
            params=params,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            time_bucket=bucket_interval,
            time_bucket_field=bucket_field,
            bucket_alias_field=bucket_alias_field,
        )

        # ------------------------------------------------------
        # 9️⃣ Execute query
        # ------------------------------------------------------
        results = db_instance.execute_query_safe(query, params_tuple)

        # ------------------------------------------------------
        # 🔟 Post-processing (PII + cleanup)
        # ------------------------------------------------------
        return FieldIntel.post_execute(results, normalized_filters, intel)

    # ----------------------------------------------------------
    # UTILITY: LIST AVAILABLE ATTRIBUTES
    # ----------------------------------------------------------
    def get_available_attributes(self) -> List[str]:
        session = db_instance.get_session()

        rows = (
            session.query(DAOAttribute)
            .filter_by(
                entity_type=self.entity_type,
                is_active=True
            )
            .all()
        )

        return [r.attr_name for r in rows]

    # ----------------------------------------------------------
    # UTILITY: RELOAD CONFIG CACHE
    # ----------------------------------------------------------
    def reload_config(self):
        DAOConfigLoader.clear_cache()
