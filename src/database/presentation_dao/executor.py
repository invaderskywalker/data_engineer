# src/database/presentation_dao/executor.py

from typing import Any, Dict, List, Optional
from src.utils.helper.decorators import log_function_io_and_time
from src.utils.helper.common import MyJSON


class PresentationExecutor:
    """
    Deterministic projection engine.

    Takes the presentation plan produced by PresentationInterpreter and
    renders each sheet by:
      1. Resolving the data source
      2. Expanding rows (if row_expansion is declared)
      3. Projecting columns with per-column array display rules
      4. Sorting and limiting

    NO computation. NO inference. NO LLM.

    ── Array display modes (per-column "array_display") ──────────────────
    "expand"       → one row per array item  (driven by sheet row_expansion)
    "collapse"     → join items into a comma-separated string; one row per entity
    "pick_primary" → sort items, return the first one; one row per entity

    ── Per-column optional modifiers ─────────────────────────────────────
    "array_filter"            → pre-filter items before display
                                { "field": str, "value": any, "operator": str }
                                operators: eq (default) | neq | contains | gt | lt

    "collapse_field"          → single sub-field to extract per item
    "collapse_fields"         → list of sub-fields joined per item with a separator
                                (use this for full names: ["first_name","last_name"])
    "collapse_fields_separator" → separator used between sub-fields (default " ")

    collapse_field and collapse_fields are mutually exclusive.
    collapse_fields takes priority if both are accidentally set.

    ── Empty-value handling ──────────────────────────────────────────────
    None values and blank strings ("", "  ") are both treated as empty and
    are silently skipped in collapse output. This prevents " " artefacts
    when first_name or last_name fields are empty strings in the data.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @log_function_io_and_time
    def execute(
        self,
        analytical_truth: Dict[str, Any],
        presentation_plan: Dict[str, Any]
    ) -> Dict[str, Any]:

        sheets_output = []

        for sheet in presentation_plan.get("sheets", []):
            rows = self._build_sheet(analytical_truth, sheet)
            sheets_output.append({
                "sheet_id": sheet["sheet_id"],
                "title":    sheet.get("title"),
                "purpose":  sheet.get("purpose"),
                "data":     rows,
            })

        try:
            with open("presentation_data.json", "w") as f:
                MyJSON.dump(sheets_output, f)
        except Exception:
            pass

        return {"sheets": sheets_output}

    # ------------------------------------------------------------------
    # Sheet builder
    # ------------------------------------------------------------------
    def _build_sheet(
        self,
        analytical_truth: Dict[str, Any],
        sheet: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Build a single sheet:
          1. Resolve data source  →  list of entity dicts
          2. Row expansion        →  fan-out if row_expansion is set
          3. Column projection    →  apply per-column array display logic
          4. Sort + limit
        """
        data_source = sheet["data_source"]
        columns     = sheet.get("columns", [])
        sort_cfg    = sheet.get("sort")
        limit       = sheet.get("limit")
        expansion   = sheet.get("row_expansion")   # None → entity-level sheet

        # ── 1. Resolve data source ──────────────────────────────────
        source_data = self._resolve_path(analytical_truth, data_source)
        if source_data is None:
            return []
        if isinstance(source_data, dict):
            base_rows = [source_data]
        elif isinstance(source_data, list):
            base_rows = source_data
        else:
            return []

        # ── 2. Row expansion ────────────────────────────────────────
        expanded_rows = self._expand_rows(base_rows, expansion) if expansion else base_rows

        # ── 3. Column projection ────────────────────────────────────
        projected = []
        for row_obj in expanded_rows:
            row = {}
            for col in columns:
                label = col.get("label", col["key"])
                row[label] = self._project_column(row_obj, col)
            projected.append(row)

        # ── 4. Sort ─────────────────────────────────────────────────
        if sort_cfg:
            sort_field     = sort_cfg.get("field")
            order          = sort_cfg.get("order", "asc")
            label_for_sort = next(
                (c.get("label", c["key"]) for c in columns if c["key"] == sort_field),
                None,
            )

            def _sort_key(r):
                val = r.get(label_for_sort) if label_for_sort else None
                return (1, "") if val is None else (0, val)

            projected.sort(key=_sort_key, reverse=(order == "desc"))

        # ── 5. Limit ────────────────────────────────────────────────
        if limit and limit > 0:
            projected = projected[:limit]

        return projected

    # ------------------------------------------------------------------
    # Row expansion
    # ------------------------------------------------------------------
    def _expand_rows(
        self,
        base_rows: List[Dict],
        expansion: Dict[str, Any],
    ) -> List[Dict]:
        """
        Expand each base row into N rows — one per item in the expansion array.
        The expanded item is injected under the alias key.
        If the array is empty after filtering, the base row is kept as-is.
        """
        alias        = expansion["as"]
        path         = expansion["path"]
        array_filter = expansion.get("array_filter")
        expanded     = []

        for base_row in base_rows:
            items = self._resolve_path(base_row, path) or []
            if not isinstance(items, list):
                items = [items]
            if array_filter:
                items = self._apply_filter(items, array_filter)

            if not items:
                expanded.append(base_row)
            else:
                for item in items:
                    expanded.append({**base_row, alias: item})

        return expanded

    # ------------------------------------------------------------------
    # Column projection
    # ------------------------------------------------------------------
    def _project_column(self, row_obj: Any, col: Dict[str, Any]) -> Any:
        """
        Resolve one column value for one row, applying array display logic.
        """
        key          = col["key"]
        array_mode   = col.get("array_display")
        array_filter = col.get("array_filter")
        concat_fields = col.get("concat_fields")

        # Scalar concat — merge multiple core.* fields into one value
        if concat_fields:
            sep = col.get("concat_separator", " ")
            parts = []
            for f in concat_fields:
                val = self._resolve_path(row_obj, f)
                if val is not None and str(val).strip():
                    parts.append(str(val))
            return sep.join(parts) or None

        # Plain scalar field — no array involved
        if not array_mode or array_mode == "expand":
            return self._resolve_path(row_obj, key)

        # Array field — resolve first
        items = self._resolve_path(row_obj, key)
        if items is None:
            return None
        if not isinstance(items, list):
            return items  # already a scalar (defensive)

        # Pre-filter before display
        if array_filter:
            items = self._apply_filter(items, array_filter)

        if array_mode == "collapse":
            return self._collapse(items, col)

        if array_mode == "pick_primary":
            return self._pick_primary(items, col)

        # Unknown mode — log and return raw
        print(f"⚠️  Unknown array_display mode '{array_mode}' for key '{key}' — returning raw.")
        return items

    # ------------------------------------------------------------------
    # Array filter
    # ------------------------------------------------------------------
    def _apply_filter(
        self,
        items: List[Any],
        array_filter: Dict[str, Any],
    ) -> List[Any]:
        """
        Pre-filter array items by a field/value condition.

        Schema: { "field": str, "value": any, "operator": "eq|neq|contains|gt|lt" }
        Items that are not dicts pass through unfiltered.
        """
        field    = array_filter.get("field")
        value    = array_filter.get("value")
        operator = array_filter.get("operator", "eq")

        if not field or value is None:
            print("⚠️  array_filter missing 'field' or 'value' — skipping filter.")
            return items

        result = []
        for item in items:
            if not isinstance(item, dict):
                result.append(item)
                continue
            item_val = item.get(field)
            try:
                if operator == "eq":
                    match = item_val == value
                elif operator == "neq":
                    match = item_val != value
                elif operator == "contains":
                    match = (value in str(item_val)) if item_val is not None else False
                elif operator == "gt":
                    match = item_val is not None and item_val > value
                elif operator == "lt":
                    match = item_val is not None and item_val < value
                else:
                    print(f"⚠️  Unknown array_filter operator '{operator}' — treating as eq.")
                    match = item_val == value
            except Exception as e:
                print(f"⚠️  array_filter comparison error: {e}")
                match = False
            if match:
                result.append(item)

        return result

    # ------------------------------------------------------------------
    # Collapse
    # ------------------------------------------------------------------
    def _collapse(self, items: List[Any], col: Dict[str, Any]) -> str:
        """
        Join item values into a single comma-separated string.

        Priority:
          1. collapse_fields  → join multiple sub-fields per item with fields_sep
          2. collapse_field   → single sub-field per item
          3. neither          → stringify the whole item

        None values AND blank/whitespace-only strings are both treated as
        empty and silently skipped. This prevents artefacts like " " when
        first_name or last_name fields are empty strings in the source data.
        """
        collapse_fields = col.get("collapse_fields")        # list of sub-fields
        collapse_field  = col.get("collapse_field")         # single sub-field
        fields_sep      = col.get("collapse_fields_separator", " ")

        def _is_blank(v) -> bool:
            return v is None or (isinstance(v, str) and v.strip() == "")

        parts = []
        for item in items:
            if collapse_fields and isinstance(item, dict):
                # Join multiple sub-fields within this item
                sub_vals = [
                    str(item[f])
                    for f in collapse_fields
                    if not _is_blank(item.get(f))
                ]
                val = fields_sep.join(sub_vals) if sub_vals else None

            elif collapse_field and isinstance(item, dict):
                raw_val = item.get(collapse_field)
                val = None if _is_blank(raw_val) else raw_val

            else:
                val = None if _is_blank(item) else item

            if not _is_blank(val):
                parts.append(str(val))

        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Pick primary
    # ------------------------------------------------------------------
    def _pick_primary(self, items: List[Any], col: Dict[str, Any]) -> Any:
        """
        Sort items by a field, take the first, and return a sub-field value.
        Supports both collapse_field (single) and collapse_fields (multi).
        """
        if not items:
            return None

        sort_by    = col.get("array_sort_by")
        sort_order = col.get("array_sort_order", "asc")

        if sort_by:
            try:
                reverse = sort_order == "desc"
                items = sorted(
                    items,
                    key=lambda x: (
                        (x.get(sort_by) is None, x.get(sort_by))
                        if isinstance(x, dict)
                        else (True, None)
                    ),
                    reverse=reverse,
                )
            except Exception as e:
                print(f"⚠️  pick_primary sort failed on '{sort_by}': {e}")

        primary         = items[0]
        collapse_fields = col.get("collapse_fields")
        collapse_field  = col.get("collapse_field")
        fields_sep      = col.get("collapse_fields_separator", " ")

        def _is_blank(v) -> bool:
            return v is None or (isinstance(v, str) and v.strip() == "")

        if collapse_fields and isinstance(primary, dict):
            sub_vals = [
                str(primary[f])
                for f in collapse_fields
                if not _is_blank(primary.get(f))
            ]
            return fields_sep.join(sub_vals) if sub_vals else None

        if collapse_field and isinstance(primary, dict):
            raw_val = primary.get(collapse_field)
            return None if _is_blank(raw_val) else raw_val

        return primary

    # ------------------------------------------------------------------
    # Dot-path resolver
    # ------------------------------------------------------------------
    def _resolve_path(self, obj: Any, path: str) -> Any:
        """
        Resolve a dot-notation path through dicts and lists.

        Numeric path segments are a plan violation — logged as warnings
        but handled defensively so the sheet doesn't crash.
        """
        if not path:
            return None

        parts = path.split(".")
        if any(p.isdigit() for p in parts):
            print(f"⚠️  PLAN VIOLATION: numeric index in path '{path}' — use array_display instead.")

        cur = obj
        for part in parts:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list):
                # Defensive numeric fallback
                try:
                    cur = cur[int(part)] if 0 <= int(part) < len(cur) else None
                except (ValueError, TypeError):
                    return None
            else:
                return None

        return cur
    