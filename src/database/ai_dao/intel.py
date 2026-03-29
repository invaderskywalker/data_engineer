# src/database/ai_dao/intel.py

from typing import Dict, Any, Optional, List
from src.api.logging.AppLogger import appLogger


class FieldIntel:
    """
    Independent intelligence layer.
    Normalizes filters and extracts PII post-filters safely.
    """

    # ---------------------------------------------------------------
    # FILTER NORMALIZATION
    # ---------------------------------------------------------------
    @staticmethod
    def normalize_filters(
        filters: Optional[Dict[str, Any]],
        intel: Dict[str, Any],
        fields: Dict[str, str],
        alias: Optional[str] = None,
    ) -> Dict[str, Any]:

        if not filters:
            return {}

        # -------------------------------------------------------
        # Resolve logical field → database column
        # -------------------------------------------------------
        def get_db_column(field: str) -> Optional[str]:
            expr = fields.get(field)
            if not expr:
                return None
            if " AS " in expr:
                return expr.split(" AS ")[0].strip()
            return expr.strip()

        # -------------------------------------------------------
        # Extract operator
        # -------------------------------------------------------
        def split_operator(key: str):
            if "__" in key:
                f, op = key.split("__", 1)
                return f, f"__{op}"
            return key, "__eq"

        # -------------------------------------------------------
        # Text LIKE helpers
        # -------------------------------------------------------
        def rewrite_text_operator(db_col: str, operator: str, value: Any):
            if operator in ("__eq", "__contains"):
                return {f"{db_col}__ilike": f"%{value}%"}
            if operator == "__startswith":
                return {f"{db_col}__ilike": f"{value}%"}
            if operator == "__endswith":
                return {f"{db_col}__ilike": f"%{value}"}
            return {f"{db_col}{operator}": value}

        # -------------------------------------------------------
        # GLOBAL collector for PII filters
        # -------------------------------------------------------
        pii_collector: Dict[str, Any] = {}

        # -------------------------------------------------------
        # Recursive walker
        # -------------------------------------------------------
        def walk(node: Any) -> Any:
            if not isinstance(node, dict):
                return node

            # Logical nesting
            if "and" in node or "or" in node:
                key = "and" if "and" in node else "or"
                return {key: [walk(sub) for sub in node[key]]}

            out = {}

            for raw_key, value in node.items():

                field, operator = split_operator(raw_key)
                cfg = intel.get(field)
                db_col = get_db_column(field)

                # ---------------------------------------------------
                # ENUM FIELD
                # ---------------------------------------------------
                if cfg and cfg.get("type") == "enum":
                    mapping = cfg["mapping"]
                    mapped = (
                        [mapping.get(str(v).lower(), v) for v in value]
                        if isinstance(value, list)
                        else mapping.get(str(value).lower(), value)
                    )
                    col = cfg["column"]

                    if isinstance(mapped, list):
                        out[f"{col}__in"] = mapped
                    else:
                        out[f"{col}{operator}"] = mapped
                    continue

                # ---------------------------------------------------
                # DATE FIELD (FIXED)
                # ---------------------------------------------------
                if cfg and cfg.get("type") == "date":
                    if db_col:
                        suffix = operator.lstrip("_")
                        out[f"{db_col}__date_{suffix}"] = value
                    continue

                # ---------------------------------------------------
                # PII FIELD (FIXED GLOBAL COLLECTOR)
                # ---------------------------------------------------
                if cfg and cfg.get("type") == "pii_text":
                    pii_collector[field] = value
                    continue

                # ---------------------------------------------------
                # TEXT / ILIKE FIELD (🔥 FIXED BEHAVIOR)
                # ---------------------------------------------------
                if cfg and cfg.get("type") in ("text", "ilike"):
                    col = cfg.get("column") or db_col

                    if col:
                        # Default behavior: ALWAYS fuzzy match
                        if operator in ("__eq", "__contains"):
                            out[f"{col}__ilike"] = f"%{value}%"
                        elif operator == "__startswith":
                            out[f"{col}__ilike"] = f"{value}%"
                        elif operator == "__endswith":
                            out[f"{col}__ilike"] = f"%{value}"
                        else:
                            out[f"{col}{operator}"] = value

                    continue

                # ---------------------------------------------------
                # Known DB mapping
                # ---------------------------------------------------
                if db_col:
                    if operator in ("__contains", "__startswith", "__endswith"):
                        out.update(rewrite_text_operator(db_col, operator, value))
                    else:
                        out[f"{db_col}{operator}"] = value
                    continue

                # ---------------------------------------------------
                # Unknown passthrough
                # ---------------------------------------------------
                out[raw_key] = value

            return out

        normalized = walk(filters)

        # Attach PII filters at ROOT ONLY
        if pii_collector:
            normalized["__pii_post_filter__"] = pii_collector

        appLogger.debug({
            "msg": "[FieldIntel] normalized filters",
            "input": filters,
            "output": normalized
        })

        return normalized

    # ---------------------------------------------------------------
    # POST-PROCESSING
    # ---------------------------------------------------------------
    @staticmethod
    def post_process(results: List[Dict], intel: Dict[str, Any]) -> List[Dict]:

        for field, cfg in intel.items():
            if cfg.get("type") != "json_clean":
                continue

            prefixes = [p.lower() for p in cfg.get("exclude_prefixes", [])]

            for row in results:
                val = row.get(field)
                if isinstance(val, dict):
                    row[field] = {
                        k: v for k, v in val.items()
                        if not any(k.lower().startswith(pre) for pre in prefixes)
                    }

        return results

    # ---------------------------------------------------------------
    # POST EXECUTION
    # ---------------------------------------------------------------
    @staticmethod
    def post_execute(
        results: List[Dict[str, Any]],
        normalized_filters: Dict[str, Any],
        intel: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        # 🔥 DO NOT MUTATE FILTER OBJECT
        pii_filters = normalized_filters.get("__pii_post_filter__", {})

        if pii_filters:
            for field, value in pii_filters.items():
                results = [
                    r for r in results
                    if str(r.get(field, "")).lower() == str(value).lower()
                ]

        results = FieldIntel.post_process(results, intel)

        return results
