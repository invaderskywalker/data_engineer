"""SQL query optimization for analyst operations."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.Database import db_instance
import json
import tiktoken

@dataclass
class ColumnInfo:
    name: str
    description: Optional[str] = None
    pseudocolumn: bool = False

@dataclass
class MappingFilter:
    column: str
    values: List[Any]
    match_type: str  # 'exact' or 'substring'

class QueryOptimizer:
    """Optimize SQL queries by selecting relevant columns and applying filtering."""
    
    def __init__(
        self, 
        columns: List[Dict], 
        query: str, 
        table_name: str = None, 
        tenant_id: int = None, 
        security_clauses: List[str] = None,
        id_field: str = None, 
        row_mapping_info: List[Dict] = None
    ):
        self.columns = [ColumnInfo(col["name"], col.get("description"), col.get("pseudocolumn", False)) for col in columns]
        self.query = query.lower()
        self.table_name = table_name
        self.tenant_id = tenant_id
        self.security_clauses = security_clauses or []
        self.id_field = id_field
        self.row_mapping_info = row_mapping_info or []
        self.row_ids = []

    def optimize_query(self, base_query: str) -> dict:
        """Optimize the query by selecting columns and applying filtering."""
        try:
            # Step 1: Get column selection and filtering decisions from LLM
            analysis = self._analyze_query_requirements()
            print("[QueryOptimizer] Analysis:", analysis)
            
            # Ensure we have selected columns
            if not analysis["display_columns"]:
                analysis["display_columns"] = [self.columns[0].name]
            
            # Add ID field if needed
            if self.id_field:
                if self.id_field not in analysis["display_columns"]:
                    analysis["display_columns"].append(self.id_field)
                if analysis["filter_columns"] and self.id_field not in analysis["filter_columns"]:
                    analysis["filter_columns"].append(self.id_field)
            
            # Step 2: Apply row mapping filters if present
            if analysis.get("mapping_filters"):
                self._apply_row_mapping_filters(analysis["mapping_filters"])
                
            # Step 3: Apply LLM filtering if needed
            if analysis.get("needs_filtering"):
                if self.row_ids:  # If we have mapping filtered rows, use those
                    self._apply_llm_filtering_to_ids(analysis["filter_columns"])
                else:  # Otherwise filter all rows
                    self._apply_llm_filtering_to_all(analysis["filter_columns"])
                
            return {
                "columns": analysis["display_columns"],
                "row_ids": self.row_ids
            }
            
        except Exception as e:
            print(f"[QueryOptimizer] Error: {str(e)}")
            return {"columns": [], "row_ids": []}

    def _analyze_query_requirements(self) -> dict:
        """Use LLM to analyze query and determine column/filtering requirements."""
        # Prepare column info for prompt
        column_info = [
            {
                "id": i,
                "name": col.name,
                "description": col.description if col.description and 
                             col.description.lower() not in {col.name.lower(), 
                                                          col.name.lower() + " field", 
                                                          ""} else None,
                "pseudocolumn": col.pseudocolumn
            }
            for i, col in enumerate(self.columns)
        ]
        column_info = json.dumps(column_info, indent=2)
        
        # Build prompts
        system_prompt = """Analyze this query to determine:
1. Which columns to display in the result - try to use just a couple
2. Whether row filtering is needed with LLM - an extra step after row mapping filters
3. Which columns are needed for filtering - used just if and only if step 2 is true
4. If row mappings are provided, determine if they can be used for filtering

IMPORTANT: If row mapping filters alone are sufficient to filter the results 
(i.e., the mapping filters can fully satisfy the query requirements), then set 
needs_filtering to false since no additional LLM filtering will be needed.

IMPORTANT: Pseudocolumns are ONLY available for display columns, NOT for filtering.

Row Mapping Rules:
BUT, You can ONLY use row mapping filters that are provided below.
You MUST provide the id of the row mapping filter you are using. 
Then, the provided column id's should exactly match the provided one in the row_mappings provided to you.
Finally, the filter values you want to select for the row mapping filter should be provided in the values field, by their id number.

ALSO, if the values for the row mapping filters aren't relevant to your query, don't make a guess and just don't use it
IF values are provided for a row mapping filter YOU MUST use it if possible. OTHERWISE, ignore the mapping completely.

IMPORTANT Example: If portfolio filters are a row mapping filter and the user asks for portfolio based filtering,
DO NOT can turn on needs_filtering_from_llms, and ONLY USE the row mapping filter.

Return a JSON with this format:
{
  "display_column_ids": [0, 1, 2...],
  "needs_filtering_from_llms": true/false, 
  "filter_column_ids": [0, 1, 2...],
  "mapping_filters": [
    {
      "mapping_filter_id": 0,
      "column_ids": [2, 4, 5],
      "values": [2, 3],
      "match_type": "exact|substring"
    }
  ]
}"""

        user_prompt = f"""Query: {self.query}
Available Columns: {column_info}
Only use the Row Mappings, use the ids and columns and values provided in the row_mappings below: 
{json.dumps(self.row_mapping_info, indent = 2)}

Remember: If the row mapping filters you create can fully satisfy this query's filtering needs, 
set needs_filtering to false since no additional LLM filtering will be required."""
        # Get LLM response
        llm = ChatGPTClient()
        response = llm.run(
            chat=ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
            options=ModelOptions(model="gpt-4o", max_tokens=512, temperature=0),
            function_name = "analyst_query_optimizer_columns",
        )
        
        # Parse response
        result = extract_json_after_llm(response)
        # Convert any 'type' keys to 'match_type' in mapping filters
        mapping_filters = result.get("mapping_filters", [])
        map_filters = []
        for mapping in mapping_filters:
            try:
                mapping["mapping_filter_id"] = mapping.pop("mapping_filter_id")
                mapping["column"] = mapping.pop("column_ids")
                mapping["values"] = mapping.pop("values")
                mapping["match_type"] = mapping.pop("match_type", "exact")
                for mapping_given in self.row_mapping_info:
                    if mapping_given.get("mapping_id") == mapping["mapping_filter_id"]:
                        mapping_given = mapping_given.get("mapping_info")
 
                        columns = []
                        for column in mapping_given.get("columns", []):
                            if column["id"] in mapping["column"]:
                                columns.append(column["column"])
                                
                        values = []
                        for value in mapping_given.get("values", []):
                            if value["id"] in mapping["values"]:
                                values.append(value["filter_value"])
                if columns and values:                
                    Mapping = MappingFilter(
                        column=columns[0],
                        values=values,
                        match_type=mapping["match_type"]
                    )
                    
                    map_filters.append(Mapping)
            except Exception as e:
                print(f"[QueryOptimizer] Error processing mapping filter rule {mapping}: {str(e)}")
                continue
        
        plan = {
            "display_columns": [self.columns[i].name for i in result.get("display_column_ids", [])
                              if i < len(self.columns)],
            "needs_filtering": result.get("needs_filtering_from_llms", False),
            "filter_columns": [self.columns[i].name for i in result.get("filter_column_ids", [])
                             if i < len(self.columns)],
            "mapping_filters": map_filters,
        }

        updated_columns = []
        for column in plan["filter_columns"]:
            found = False
            for filter in plan["mapping_filters"]:  
                if column == filter.column:
                    found = True
            if not found: updated_columns.append(column)
        plan["filter_columns"] = updated_columns
        if len(plan["filter_columns"]) == 0:
            plan["needs_filtering"] = False
    
        return plan

    def _apply_row_mapping_filters(self, mapping_filters: List[MappingFilter]) -> None:
        """Apply row mapping filters using SQL. This is independent of LLM filtering."""
        try:
            # Build the SQL query for mapping filters
            select_clause = f"SELECT DISTINCT {self.id_field}"
            from_clause = f"FROM {self.table_name}"
            
            where_conditions = []
            params = []
            
            # Add security clauses first
            if self.security_clauses:
                where_conditions.extend([
                    clause.replace("{tenant_id}", str(self.tenant_id)) 
                    for clause in self.security_clauses
                ])
            
            # Add mapping filter conditions
            for filter_info in mapping_filters:
                values = filter_info.values
                if not values:
                    continue
                    
                if filter_info.match_type == "exact":
                    values_list = "'" + "','".join(str(v) for v in values) + "'"
                    where_conditions.append(f"{filter_info.column} IN ({values_list})")
                else:  # substring
                    like_conditions = []
                    for value in values:
                        like_conditions.append(f"{filter_info.column} LIKE '%{value}%'")
                    where_conditions.append(f"({' OR '.join(like_conditions)})")
            
            # Build final query
            where_clause = " WHERE " + " AND ".join(f"({condition})" for condition in where_conditions) if where_conditions else ""
            query = f"{select_clause} {from_clause}{where_clause}"
            
            # Execute query (without params since we built them into the query)
            results = db_instance.retrieveSQLQueryOld(query)
            self.row_ids = [row[self.id_field] for row in results if row.get(self.id_field) is not None]
            print(f"[QueryOptimizer] Found {len(self.row_ids)} rows matching mapping filters")
            
        except Exception as e:
            print(f"[QueryOptimizer] Error in row mapping filters: {str(e)}")
            self.row_ids = []

    def _apply_llm_filtering_to_ids(self, filter_columns: List[str]) -> None:
        """Apply LLM filtering only to rows that matched mapping filters."""
        if not self.row_ids or not filter_columns:
            return
            
        try:
            # Fetch the filtered rows
            ids_list = "'" + "','".join(str(id) for id in self.row_ids) + "'"
            query = f"SELECT {', '.join(filter_columns)} FROM {self.table_name} WHERE {self.id_field} IN ({ids_list})"
            rows = db_instance.retrieveSQLQueryOld(query)
            
            if rows:
                # Apply LLM filtering to these rows
                self._apply_llm_batch_filtering(rows)
                
        except Exception as e:
            print(f"[QueryOptimizer] Error in LLM filtering of mapped rows: {str(e)}")

    def _apply_llm_filtering_to_all(self, filter_columns: List[str]) -> None:
        """Apply LLM filtering to all rows (when no mapping filters were used)."""
        if not filter_columns:
            return
            
        try:
            # Build query with security clauses
            query = f"SELECT {', '.join(filter_columns)} FROM {self.table_name}"
            if self.security_clauses:
                where_clauses = [
                    clause.replace("{tenant_id}", str(self.tenant_id)) 
                    for clause in self.security_clauses
                ]
                query += " WHERE " + " AND ".join(where_clauses)
                
            # Fetch and filter rows
            rows = db_instance.retrieveSQLQueryOld(query)
            if rows:
                self._apply_llm_batch_filtering(rows)
                
        except Exception as e:
            print(f"[QueryOptimizer] Error in LLM filtering of all rows: {str(e)}")

    def _estimate_token_count(self, data: Any, model_name: str = "gpt-4o") -> int:
        """Estimate the token count of the given data using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to a default encoding if the model_name is not found
            encoding = tiktoken.get_encoding("cl100k_base")
        
        if isinstance(data, (dict, list)):
            text_representation = json.dumps(data)
        else:
            text_representation = str(data)
            
        return len(encoding.encode(text_representation))

    def _apply_llm_batch_filtering(self, rows: List[Dict], max_tokens_per_batch: int = 5000) -> None:
        """Apply LLM filtering to rows in parallel batches based on token count."""
        if not rows:
            return

        batches = []
        current_batch = []
        current_batch_tokens = 0

        for row in rows:
            row_tokens = self._estimate_token_count(row)

            # If a single row exceeds max_tokens_per_batch, process it alone
            # or handle error, here we'll process it alone if it's the first in a batch
            if row_tokens > max_tokens_per_batch:
                if current_batch: # Process existing batch first
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_tokens = 0
                batches.append([row]) # Add large row as its own batch
                continue

            if current_batch_tokens + row_tokens > max_tokens_per_batch:
                # Current batch is full, start a new one
                if current_batch:
                    batches.append(current_batch)
                current_batch = [row]
                current_batch_tokens = row_tokens
            else:
                # Add row to current batch
                current_batch.append(row)
                current_batch_tokens += row_tokens
        
        # Add the last batch if it's not empty
        if current_batch:
            batches.append(current_batch)

        all_ids = set()

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_batch = {
                executor.submit(self._process_batch, batch): batch 
                for batch in batches
            }
            
            for future in future_to_batch:
                try:
                    batch_ids = future.result()
                    all_ids.update(batch_ids)
                except Exception as e:
                    print(f"[QueryOptimizer] Batch processing failed: {str(e)}")

        self.row_ids = list(all_ids)

    def _process_batch(self, batch: List[Dict]) -> set:
        """Process a single batch of rows using LLM."""
        system_prompt = """Filter rows based on this query: {}
Return ONLY row IDs that match the query requirements in this format:
{{"row_ids": [1, 2, 3...]}}
""".format(self.query)
        
        user_prompt = f"Rows to filter:\n{batch}"
        
        try:
            llm = ChatGPTClient()
            response = llm.run(
                chat=ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
                options=ModelOptions(model="gpt-4o", max_tokens=512, temperature=0.1),
                function_name = "analyst_query_optimizer_filtering_batch",
            )
            
            batch_ids = extract_json_after_llm(response)
            if not isinstance(batch_ids, dict):
                return set()
            
            # Get the actual database IDs from the batch using id_field
            llm_ids = list(set(batch_ids.get("row_ids", [])))

            return llm_ids
            
        except Exception as e:
            print(f"[QueryOptimizer] Error in batch filtering: {str(e)}")
            return set()