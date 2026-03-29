# src/trmeric_database/ai_dao/base.py
from typing import List, Dict, Any, Optional, Tuple, Union

class BaseDAOQueryBuilder:
    """Utility to standardize DAO query building with dynamic aggregation and nested filters."""

    # ------------------------------------------------------------------
    # Recursive filter translator (now alias-aware)
    # ------------------------------------------------------------------
    @staticmethod
    def build_filters(
        filters: Dict[str, Any],
        alias: Optional[str] = None,
        fields_map: Optional[Dict[str, str]] = None
    ) -> Tuple[str, List[Any]]:
        """
        Recursively translates structured filter JSON (with 'and'/'or' logic)
        into SQL WHERE clause and params.

        Now supports alias resolution using fields_map from DAO.
        """
        if not filters:
            return "", []
        
        # -------------------------------------------------------
        # Strip out PII post-filtering fields (handled after SQL)
        # -------------------------------------------------------
        if "__pii_post_filter__" in filters:
            filters = {k: v for k, v in filters.items() if k != "__pii_post_filter__"}


        clauses = []
        params: List[Any] = []

        def qualify(field: str) -> str:
            """Attach alias prefix or resolve alias mapping."""
            # 🧠 Step 1: try to resolve from the DAO's field mapping
            if fields_map and field in fields_map:
                expr = fields_map[field]
                # Handle expressions like "wp.delivery_status AS schedule_status"
                if " AS " in expr:
                    expr = expr.split(" AS ")[0].strip()
                return expr  # already includes alias (e.g. wp.delivery_status)
            # 🧠 Step 2: default aliasing
            # if alias and not field.startswith(f"{alias}."):
            #     return f"{alias}.{field}"
            # if already qualified (e.g., "uu.first_name") → keep as-is
            if "." in field:
                return field

            if alias:
                return f"{alias}.{field}"

            return field
        
        # ✅ Ultimate date parser: handles all human-like and LLM relative time patterns
        def resolve_value(v: Any) -> Tuple[str, List[Any]]:
            import re
            
            # If already numeric (after enum conversion), return directly
            if isinstance(v, (int, float)):
                return "%s", [v]


            # 👉 Field reference (e.g., actual_date__gt: target_date)
            if isinstance(v, str) and fields_map and v in fields_map:
                rhs_expr = fields_map[v]
                if " AS " in rhs_expr:
                    rhs_expr = rhs_expr.split(" AS ")[0].strip()
                return rhs_expr, []

            # 👉 Date keywords (simple)
            if isinstance(v, str) and v.lower() in ("today", "now", "current_date"):
                return "CURRENT_DATE", []

            # 👉 Normalize input for comparison
            if isinstance(v, str):
                val = v.strip().lower()
                # normalized = val.replace(" ", "").replace("_", "")
                # # Common replacements for flexible parsing
                # normalized = normalized.replace("()", "").replace("days", "d").replace("day", "d")
                # normalized = normalized.replace("weeks", "w").replace("week", "w")
                # normalized = normalized.replace("months", "m").replace("month", "m")
                # normalized = normalized.replace("years", "y").replace("year", "y")
                
                clean = val.replace(" ", "").replace("_", "").replace("-", "")
                # YEAR KEYWORDS – BEFORE ANY NORMALIZATION
                if clean == "thisyear":
                    return "date_trunc('year', CURRENT_DATE)", []
                if clean == "lastyear":
                    return "date_trunc('year', CURRENT_DATE) - INTERVAL '1 year'", []
                if clean == "nextyear":
                    return "date_trunc('year', CURRENT_DATE) + INTERVAL '1 year'", []

                # Clean up basic formatting and symbols
                normalized = val.replace(" ", "").replace("_", "").replace("-", "")
                normalized = normalized.replace("()", "")

                # Preserve "thismonth" etc. while still allowing +30d / +2m type forms
                if not re.search(r"thismonth|lastmonth|nextmonth", normalized):
                    normalized = normalized.replace("months", "m").replace("month", "m")

                # Generic replacements for other units (these don't conflict)
                normalized = normalized.replace("days", "d").replace("day", "d")
                normalized = normalized.replace("weeks", "w").replace("week", "w")
                normalized = normalized.replace("years", "y").replace("year", "y")


                # 🧠 Match compact math-like forms and extended variations:
                # Examples it now supports:
                #   today+30d, today-15d, now+2w, now()-90d, current_date+1m
                compact_patterns = [
                    r"^(now|today|currentdate)([-+])(\d+)([dwmy])$",       # today+30d
                    r"^(now|today|current_date)\(\)?\s*([-+])\s*(\d+)\s*([dwmy])$",  # now() + 30d
                ]
                for pattern in compact_patterns:
                    compact = re.match(pattern, normalized)
                    if compact:
                        base, sign, num, unit = compact.groups()
                        unit_map = {"d": "day", "w": "week", "m": "month", "y": "year"}
                        return f"CURRENT_DATE {sign} INTERVAL '{num} {unit_map[unit]}'", []


                # 🧠 Match forms like "last90days", "past30days", "next2weeks", "future3months"
                flexible = re.match(r"^(last|past|next|future)(\d+)([dwmy])$", normalized)
                if flexible:
                    direction, num, unit = flexible.groups()
                    sign = "-" if direction in ("last", "past") else "+"
                    unit_map = {"d": "day", "w": "week", "m": "month", "y": "year"}
                    return f"CURRENT_DATE {sign} INTERVAL '{num} {unit_map[unit]}'", []

                # 🧠 Match more readable forms: "last 90 days", "next 2 weeks", "past 6 months"
                natural = re.search(r"(last|past|next|future)\s*(\d+)\s*(day|week|month|year)", val)
                if natural:
                    direction, num, unit = natural.groups()
                    sign = "-" if direction in ("last", "past") else "+"
                    return f"CURRENT_DATE {sign} INTERVAL '{num} {unit}'", []

                # 🧠 Handle SQL-like "NOW()-90 days" or "NOW() - 3 months"
                sqlish = re.match(r"^now\(\)?[-+](\d+)\s*(day|week|month|year)", val)
                if sqlish:
                    num, unit = sqlish.groups()
                    sign = "-" if "-" in val else "+"
                    return f"CURRENT_DATE {sign} INTERVAL '{num} {unit}'", []

                print("--normalized ", normalized)
                # 🧩 Handle month/quarter/year-level phrases
                if "thismonth" in normalized:
                    return "date_trunc('month', CURRENT_DATE)", []
                if "lastmonth" in normalized or "previousmonth" in normalized:
                    return "date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'", []
                if "nextmonth" in normalized:
                    return "date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'", []

                # 🧭 Handle quarter-level logic with optional offsets
                if "thisquarter" in normalized or re.match(r"^thisquarter([+-]\d+q)?$", normalized):
                    match = re.search(r"([+-]\d+)q", normalized)
                    offset = int(match.group(1)) if match else 0
                    months = offset * 3
                    if months == 0:
                        return "date_trunc('quarter', CURRENT_DATE)", []
                    sign = "+" if months > 0 else "-"
                    return f"date_trunc('quarter', CURRENT_DATE) {sign} INTERVAL '{abs(months)} month'", []

                if "lastquarter" in normalized or "previousquarter" in normalized or re.match(r"^lastquarter([+-]\d+q)?$", normalized):
                    match = re.search(r"([+-]\d+)q", normalized)
                    offset = int(match.group(1)) if match else 0
                    months = -3 + offset * 3
                    sign = "+" if months > 0 else "-"
                    return f"date_trunc('quarter', CURRENT_DATE) {sign} INTERVAL '{abs(months)} month'", []

                if "nextquarter" in normalized or re.match(r"^nextquarter([+-]\d+q)?$", normalized):
                    match = re.search(r"([+-]\d+)q", normalized)
                    offset = int(match.group(1)) if match else 0
                    months = 3 + offset * 3
                    sign = "+" if months > 0 else "-"
                    return f"date_trunc('quarter', CURRENT_DATE) {sign} INTERVAL '{abs(months)} month'", []


                # if "thisyear" in normalized:
                #     return "date_trunc('year', CURRENT_DATE)", []
                # if "lastyear" in normalized or "previousyear" in normalized:
                #     return "date_trunc('year', CURRENT_DATE) - INTERVAL '1 year'", []
                # if "nextyear" in normalized:
                #     return "date_trunc('year', CURRENT_DATE) + INTERVAL '1 year'", []

                # 🧭 Handle week-level
                if "thisweek" in normalized:
                    return "date_trunc('week', CURRENT_DATE)", []
                if "lastweek" in normalized or "previousweek" in normalized:
                    return "date_trunc('week', CURRENT_DATE) - INTERVAL '1 week'", []
                if "nextweek" in normalized:
                    return "date_trunc('week', CURRENT_DATE) + INTERVAL '1 week'", []

                # 🧮 Fiscal year logic (FY starting April)
                if "thisfiscalyear" in normalized or "thisfy" in normalized:
                    return """CASE 
                                WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4 
                                THEN date_trunc('year', CURRENT_DATE) + INTERVAL '3 month'
                                ELSE date_trunc('year', CURRENT_DATE) - INTERVAL '9 month' 
                                END""", []
                if "lastfiscalyear" in normalized or "lastfy" in normalized:
                    return """CASE 
                                WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4 
                                THEN date_trunc('year', CURRENT_DATE) - INTERVAL '9 month'
                                ELSE date_trunc('year', CURRENT_DATE) - INTERVAL '21 month' 
                                END""", []

            # 🧩 Handle explicit date literals like "2025-11-18" or "18-11-2025" or "01/01/2024"
            date_patterns = [
                r"^\d{4}-\d{2}-\d{2}$",   # YYYY-MM-DD
                r"^\d{2}-\d{2}-\d{4}$",   # DD-MM-YYYY
                r"^\d{2}/\d{2}/\d{4}$",   # DD/MM/YYYY
            ]
            for dp in date_patterns:
                if re.match(dp, v.strip()):
                    try:
                        from datetime import datetime
                        if "-" in v:
                            if len(v.split("-")[0]) == 4:  # YYYY-MM-DD
                                parsed = datetime.strptime(v, "%Y-%m-%d").date()
                            else:  # DD-MM-YYYY
                                parsed = datetime.strptime(v, "%d-%m-%Y").date()
                        elif "/" in v:
                            parsed = datetime.strptime(v, "%d/%m/%Y").date()
                        return "%s", [parsed.isoformat()]  # ensures YYYY-MM-DD format
                    except Exception:
                        pass

            # Default fallback → literal
            return "%s", [v]


        def parse_condition(key: str, value: Any) -> Tuple[str, List[Any]]:
            # -------------------------------------------------------
            # PII fallback → force WHERE FALSE
            # -------------------------------------------------------
            
            if key == "__force_false__":
                return "FALSE", []
            
            # Ignore PII post-filter keys safely (should never hit SQL)
            if key == "__pii_post_filter__":
                return "", []

            
            if "__" in key:
                field, op = key.split("__", 1)
            else:
                field, op = key, "eq"
                
                
            col = qualify(field)
            print("parse_condition ", field, op, col)
            # 🔧 Normalize date_isnull → isnull
            if op == "date_isnull":
                op = "isnull"
                
            # -------------------------------------------------------
            # Handle custom date operators (date_gte, date_lt, etc.)
            # -------------------------------------------------------
            if op.startswith("date_"):
                suffix = op.replace("date_", "")  # gte, lt, lte, gt
                op_map = {
                    "gte": ">=",
                    "gt": ">",
                    "lte": "<=",
                    "lt": "<"
                }
                if suffix not in op_map:
                    raise ValueError(f"Invalid date operator: {op}")

                rhs_expr, rhs_params = resolve_value(value)
                return f"{col} {op_map[suffix]} {rhs_expr}", rhs_params


            # 🧠 Handle CASE-based enums (like milestone_type)
            if "CASE" in col.upper() and "WHEN" in col.upper():
                # detect milestone_type mapping
                if "wpm.type" in col:
                    enum_map = {
                        "scope": 1,
                        "scope_milestone": 1,
                        "schedule": 2,
                        "schedule_milestone": 2,
                        "spend": 3,
                        "spend_milestone": 3,
                    }
                    # convert human-friendly value(s) to numeric
                    if isinstance(value, (list, tuple)):
                        mapped_values = [enum_map.get(str(v).lower(), v) for v in value]
                        placeholders = ", ".join(["%s"] * len(mapped_values))
                        return f"wpm.type IN ({placeholders})", mapped_values
                    else:
                        mapped_value = enum_map.get(str(value).lower(), value)
                        return f"wpm.type = %s", [mapped_value]


            # Standard operations
            if op in ["lt", "lte", "gt", "gte"]:
                op_map = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
                rhs_expr, rhs_params = resolve_value(value)
                return f"{col} {op_map[op]} {rhs_expr}", rhs_params

            elif op == "eq":
                rhs_expr, rhs_params = resolve_value(value)
                if rhs_expr != "%s":
                    return f"{col} = {rhs_expr}", rhs_params
                return f"{col} = %s", rhs_params

            elif op == "ne":
                rhs_expr, rhs_params = resolve_value(value)
                if rhs_expr != "%s":
                    return f"{col} <> {rhs_expr}", rhs_params
                return f"{col} <> %s", rhs_params

            elif op == "in":
                placeholders = ", ".join(["%s"] * len(value))
                return f"{col} IN ({placeholders})", list(value)

            elif op == "not_in":
                placeholders = ", ".join(["%s"] * len(value))
                return f"{col} NOT IN ({placeholders})", list(value)

            # 🧩 Smart fix: handle LIKE/ILIKE on DATE or TIMESTAMP columns
            elif op in ["like", "ilike", "not_like", "not_ilike", "contains", "icontains"]:
                op_map = {
                    "like": "LIKE",
                    "ilike": "ILIKE",
                    "not_like": "NOT LIKE",
                    "not_ilike": "NOT ILIKE",
                    "contains": "LIKE",
                    "icontains": "ILIKE",
                }

                # Detect likely date/timestamp fields by name
                if any(tag in field.lower() for tag in ["date", "timestamp"]):
                    # Handle common case like '2026%'
                    if isinstance(value, str) and value.endswith("%") and value[:-1].isdigit():
                        year = int(value[:-1])
                        return f"EXTRACT(YEAR FROM {col}) = %s", [year]
                    # Fallback to safe cast
                    return f"CAST({col} AS TEXT) {op_map[op]} %s", [value]

                # Auto-wrap contains/icontains with %
                if op in ("contains", "icontains"):
                    return f"{col} {op_map[op]} %s", [f"%{value}%"]

                return f"{col} {op_map[op]} %s", [value]


            elif op == "isnull":
                if not value:
                    if any(token in field.lower() for token in ("spend", "amount", "budget")):
                        return f"({col} IS NOT NULL AND {col} <> 0)", []
                    return f"{col} IS NOT NULL", []
                else:
                    return f"{col} IS NULL", []

            elif op == "true":
                return f"{col} IS TRUE", []
            elif op == "false":
                return f"{col} IS FALSE", []
            else:
                rhs_expr, rhs_params = resolve_value(value)
                if rhs_expr != "%s":
                    return f"{col} = {rhs_expr}", rhs_params
                return f"{col} = %s", rhs_params


        def parse_logic(node: Dict[str, Any]) -> Tuple[str, List[Any]]:
            if not isinstance(node, dict):
                return "", []

            sub_clauses: List[str] = []
            sub_params: List[Any] = []

            for key, val in node.items():
                if key in ("and", "or"):
                    child_sql = []
                    child_params: List[Any] = []

                    for v in val:
                        sql, params = parse_logic(v)
                        if sql:                         # 🔥 DROP EMPTY CHILDREN
                            child_sql.append(sql)
                            child_params.extend(params)

                    # 🔥 If NOTHING survived → DROP THIS LOGICAL BLOCK
                    if not child_sql:
                        continue

                    op = " AND " if key == "and" else " OR "
                    sub_clauses.append(f"({op.join(child_sql)})")
                    sub_params.extend(child_params)

                else:
                    cond_sql, cond_params = parse_condition(key, val)
                    if cond_sql:
                        sub_clauses.append(cond_sql)
                        sub_params.extend(cond_params)

            return " AND ".join(sub_clauses), sub_params


        final_clause, final_params = parse_logic(filters)
        return final_clause, final_params

    # ------------------------------------------------------------------
    # Build the complete SELECT query (now alias-aware)
    # ------------------------------------------------------------------
    @staticmethod
    def build_query(
        table_alias: str,
        table_name: str,
        fields: Dict[str, str],
        selected_fields: Optional[List[Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        where_clauses: Optional[List[str]] = None,
        params: Optional[List[Any]] = None,
        sample_rate: Optional[float] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        group_by: Optional[List[str]] = None,
        time_bucket: Optional[str] = None,
        time_bucket_field: Optional[str] = None,
        bucket_alias_field = None,
        joins: Optional[List[str]] = None,
    ) -> Tuple[str, Tuple[Any]]:
        """
        Build dynamic SQL with alias-aware filtering.
        Optionally supports temporal bucketing (time_bucket: day/week/month/quarter/year).
        """
        where_clauses = where_clauses or []
        params = params or []
        
        print("filters ", filters, table_alias, fields)

        # ✅ Pass field mapping to filter builder
        if filters:
            filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
                filters, alias=table_alias, fields_map=fields
            )
            if filter_sql:
                where_clauses.append(filter_sql)
                params.extend(filter_params)

        # ------------------------------------------------------------------
        # 🧠 Temporal bucketing logic (DATE_TRUNC)
        # ------------------------------------------------------------------
        bucket_expr = None
        if time_bucket and  time_bucket_field:
            base_col_expr = (
                fields.get(time_bucket_field, time_bucket_field)
                .split(" AS ")[0]
                .strip()
            )

            if base_col_expr:
                bucket_expr = f"DATE_TRUNC('{time_bucket}', {base_col_expr}) AS {bucket_alias_field}"
                
        # ------------------------------------------------------------------
        # 🛡️ Normalize ORDER BY for time buckets (CRITICAL FIX)
        # ------------------------------------------------------------------
        if order_by and bucket_alias_field:
            # Handle legacy / semantic order_by values
            if order_by.strip().lower() == "time_bucket asc":
                order_by = f"{bucket_alias_field} ASC"
            elif order_by.strip().lower() == "time_bucket desc":
                order_by = f"{bucket_alias_field} DESC"


        # ------------------------------------------------------------------
        # Build SELECT clause
        # ------------------------------------------------------------------
        fields_clause_parts = []

        if bucket_expr:
            fields_clause_parts.append(bucket_expr)

        for item in (selected_fields or fields.keys()):
            if isinstance(item, dict) and "aggregate" in item:
                field_expr = fields.get(item["field"], item["field"])
                alias = item.get("alias", f"{item['aggregate'].lower()}_{item['field']}")
                fields_clause_parts.append(f"{item['aggregate'].upper()}({field_expr}) AS {alias}")
            elif isinstance(item, str):
                if item in fields:
                    fields_clause_parts.append(fields[item])

        fields_clause = ", ".join(fields_clause_parts)
        # sample_clause = f"TABLESAMPLE SYSTEM ({sample_rate * 100})" if sample_rate and sample_rate < 1.0 else ""
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        print("where sql -- ", where_sql)

        # ------------------------------------------------------------------
        # 🧩 Smarter GROUP BY logic
        # ------------------------------------------------------------------
        # group_by_cols = list(group_by or [])

        # # Always group by time_bucket if bucketing
        # if bucket_expr:
        #     group_by_cols.append("time_bucket")
        
        # Detect if ANY aggregate is requested
        is_aggregated = any(
            isinstance(item, dict) and "aggregate" in item
            for item in (selected_fields or [])
        )
        
        # ------------------------------------------------------------------
        # Build FROM clause supporting joins
        # ------------------------------------------------------------------
                
        from_clause = f"{table_name} {table_alias}"
        if joins:
            from_clause += " " + " ".join(joins)

        # ❌ If NOT aggregated → do NOT group, even if time_bucket exists
        if not is_aggregated:
            group_sql = ""
            query = f"""
                SELECT {fields_clause}
                FROM {from_clause}
                {where_sql}
                {f'ORDER BY {order_by}' if order_by else ''}
                {f'LIMIT {limit}' if limit else ''}
            """.strip()
            return query, tuple(params)


        # Automatically add all non-aggregated selected fields to GROUP BY
        # 🚫 Skip auto-grouping for non-aggregated queries
        if not group_by and not time_bucket:
            group_sql = ""
            query = f"""
                SELECT {fields_clause}
                FROM {from_clause}
                {where_sql}
                {f'ORDER BY {order_by}' if order_by else ''}
                {f'LIMIT {limit}' if limit else ''}
            """.strip()
            return query, tuple(params)


if __name__ == "__main__":
    filters = {'start_date__gte': 'thismonth'}
    filters = {"start_date__gte": "01-01-2024"}
    filters = {
        "or": [
          {
            "and": [
              {"start_date__gte": "past6months"},
              {"start_date__lt": "current_date"}
            ]
          },
          {
            "and": [
              {"end_date__gte": "past6months"},
              {"end_date__lt": "current_date"}
            ]
          }
        ]
      }
    table_alias = "wp"
    fields = {
                "project_id": "wp.id AS project_id",
                "project_title": "wp.title AS project_title",
                "project_description": "wp.description AS project_description",
                "project_objectives": "wp.objectives AS project_objectives",
                "start_date": "wp.start_date",
                "end_date": "wp.end_date",
                "latest_schedule_status": "wp.delivery_status AS latest_schedule_status",
                "latest_scope_status": "wp.scope_status AS latest_scope_status",
                "latest_spend_status": "wp.spend_status AS latest_spend_status",
                "project_budget": "wp.total_external_spend AS project_budget",
                "project_category": "wp.project_category",
                "org_strategy": "wp.org_strategy_align AS org_strategy",
                "program_id": "wp.program_id",
                "parent_roadmap_id": "wp.roadmap_id AS parent_roadmap_id",
            }
        
    filter_sql, filter_params = BaseDAOQueryBuilder.build_filters(
        filters, alias=table_alias, fields_map=fields
    )
    print("output ", filter_sql, filter_params)