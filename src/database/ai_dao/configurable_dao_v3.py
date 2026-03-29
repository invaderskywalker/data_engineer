from typing import List, Dict, Any, Optional
from functools import lru_cache
from types import SimpleNamespace

from src.database.Database import db_instance

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

        attr_rows = db_instance.execute_query_safe(
            """
            SELECT id, table_name, table_alias, description, id_field,
                   base_where, where_extra, joins, group_by
            FROM dao_attributes
            WHERE entity_type = %s AND attr_name = %s AND is_active = TRUE
            LIMIT 1
            """,
            (entity_type, attr_name),
        )

        if not attr_rows:
            raise ValueError(f"No config found for {entity_type}.{attr_name}")

        attr_row = attr_rows[0]
        attr_id = attr_row["id"]

        field_rows = db_instance.execute_query_safe(
            "SELECT field_name, sql_expression FROM dao_fields WHERE attr_id = %s",
            (attr_id,),
        )

        intel_rows = db_instance.execute_query_safe(
            "SELECT field_name, type, column_name, mapping FROM dao_field_intel WHERE attr_id = %s",
            (attr_id,),
        )

        fields_map = {r["field_name"]: r["sql_expression"] for r in field_rows}

        intel: Dict[str, Any] = {
            r["field_name"]: {
                "type": r["type"],
                "column": r["column_name"],
                "mapping": r["mapping"] or {},
            }
            for r in intel_rows
        }

        # SimpleNamespace keeps dot-access (meta.table_alias etc.) working
        meta = SimpleNamespace(**{k: v for k, v in attr_row.items() if k != "id"})

        return {
            "meta": meta,
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
        rows = db_instance.execute_query_safe(
            "SELECT attr_name FROM dao_attributes WHERE entity_type = %s AND is_active = TRUE",
            (self.entity_type,),
        )
        return [r["attr_name"] for r in rows]

    # ----------------------------------------------------------
    # UTILITY: RELOAD CONFIG CACHE
    # ----------------------------------------------------------
    def reload_config(self):
        DAOConfigLoader.clear_cache()
