"""Base analyst configuration classes."""

import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from src.trmeric_database.Database import db_instance
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.agents.functions.analyst.analyst_tools.general_utils import calculate_available_roles
from src.trmeric_services.agents.functions.analyst.analyst_tools.query_optimizer import QueryOptimizer
from src.trmeric_database.dao import ProjectsDao

class BaseAnalystConfig:
    """Base class for analyst configurations with common utilities."""
    
    def __init__(self, 
                 columns: List[Dict[str, Any]], 
                 security_clauses: List[str],
                 table_name: str,
                 entity_name: str,
                 id_field: str = "id",
                 table_alias: Optional[str] = None,
                 cluster_column_name: Optional[str] = None):
        """Initialize base configuration.
        
        Args:
            columns: List of column definitions with name, type, description, etc.
            security_clauses: SQL security clauses to apply to all queries
            table_name: SQL table name for this entity
            entity_name: Friendly name of the entity (e.g., "roadmap" or "project")
            id_field: Primary key field name
            table_alias: Optional alias for the main table in SQL queries.
            cluster_column_name: Optional name of the column to use for text clustering.
        """
        self.columns = columns
        self.security_clauses = security_clauses
        self.table_name = table_name
        self.entity_name = entity_name
        self.id_field = id_field
        self.table_alias = table_alias if table_alias else self._generate_alias(table_name)
        self.cluster_column_name = cluster_column_name
        self._data_cache = {}  # For caching fetch_data results

    def _generate_alias(self, table_name: str) -> str:
        """Generates a simple alias from the table name."""
        parts = table_name.split('_')
        if len(parts) > 1 and all(p for p in parts):
            return "".join(p[0] for p in parts).lower()
        elif table_name:
            return table_name[:2].lower() if len(table_name) > 1 else table_name.lower()
        return "t"  # Default alias
    
    def field_mapping(self, row, columns):
        """Build a nested JSON structure from a flat row based on parent relationships."""
        return self.build_nested_json(row, columns)
    
    @staticmethod
    def build_nested_json(row, columns):
        """Build a nested JSON structure from a flat row based on parent relationships."""
        result = {}
        nested = {}
        
        # First handle non-nested fields
        for column in columns:
            col_name = column["name"]
            if "parent" not in column and col_name in row:
                result[col_name] = BaseAnalystConfig._apply_value_mapping(row[col_name], column)
                
        # Then handle nested fields
        for column in columns:
            if "parent" in column:
                parent = column["parent"]
                col_name = column["name"]
                if col_name in row and row[col_name] is not None:
                    if parent not in nested:
                        nested[parent] = []
                    # Find all values for this parent in the current row
                    parent_item = {}
                    for parent_col in columns:
                        if "parent" in parent_col and parent_col["parent"] == parent:
                            if parent_col["name"] in row:
                                key = parent_col["name"].replace(f"{parent}_", "")
                                value = BaseAnalystConfig._apply_value_mapping(row[parent_col["name"]], parent_col)
                                parent_item[key] = value
                    if parent_item:
                        # Only add if we don't already have this combination of values
                        if parent_item not in nested[parent]:
                            nested[parent].append(parent_item)
                        
        # Add nested structures to result
        result.update(nested)
        return result
    
    @staticmethod
    def _apply_value_mapping(value, column_info):
        """Apply value mapping if it exists for the column."""
        if value is None:
            return None
            
        mapping = column_info.get("value_mapping")
        if mapping and (value in mapping or str(value) in mapping):
            return mapping[value] if value in mapping else mapping[str(value)]
        return value
    
    @staticmethod
    def get_parent_columns(columns, requested_columns):
        """Get all parent columns needed for requested columns."""
        needed_parents = set()
        parent_columns = []
        
        # First pass - identify needed parents
        for col in requested_columns:
            for column in columns:
                if column["name"] == col and "parent" in column:
                    needed_parents.add(column["parent"])
                    
        # Second pass - get all columns for needed parents
        if needed_parents:
            for column in columns:
                if "parent" in column and column["parent"] in needed_parents:
                    parent_columns.append(column["name"])
                    
        return list(set(parent_columns))
    
    def get_query(self, fields: Optional[List[str]] = None,obj = None) -> str:
        """Build SQL query for requested fields."""
        db_columns = {col["name"] for col in self.columns if not col.get("is_pseudo", False)}
        
        select_fields_final = set()

        if fields:
            select_fields_final.update(set(fields) & db_columns)
        else:
            select_fields_final.update(db_columns)

        if not select_fields_final and self.id_field in db_columns:
            select_fields_final.add(self.id_field)
        elif self.id_field in db_columns:  # Ensure id_field is always included if it's a db column
            select_fields_final.add(self.id_field)
        
        if not select_fields_final:
            raise ValueError(f"No columns to select for {self.entity_name}. Check field definitions and pseudo column status.")

        select_parts = sorted([f"{self.table_alias}.{field}" for field in select_fields_final])
        
        from_clause = f"{self.table_name} {self.table_alias}"
        
        where_clauses = []
        print("\n\n--debug table name------", self.table_name)
       

        if self.table_name == "workflow_project":
            eligible_projects = ProjectsDao.FetchAvailableProject(tenant_id=obj.tenant_id, user_id=obj.user_id)
            project_ids_str = f"({', '.join(map(str, eligible_projects))})"
            where_clauses.append(f"wp.id in {project_ids_str}")
            
        
        print("\n\n--debug whereclause--", where_clauses)
        if self.security_clauses:
            for sc_template in self.security_clauses:
                parts = sc_template.split(' ', 1)
                if len(parts) == 2:  # "col op val"
                    col_name, rest_of_clause = parts[0], parts[1]
                    where_clauses.append(f"{self.table_alias}.{col_name} {rest_of_clause}")
                else:
                    where_clauses.append(f"{self.table_alias}.{sc_template}")

        query_parts = [f"SELECT {', '.join(select_parts)}", f"FROM {from_clause}"]

        if where_clauses:
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")
        
        query_parts.append(f"ORDER BY {self.table_alias}.{self.id_field}")
        
        return "\n".join(query_parts)
    
        
    def _build_user_prompt_quick(self, len_entities, analysis_reason):
        """Build user prompt for project evaluation."""
        return f"""
        Please analyze these {len_entities} projects, focusing on {analysis_reason}
        
        For list based data, still show a numbered or bulleted formatting.
        """
    
    def _build_system_prompt_quick(self, valid_entities, query, subgoal, analysis_reason, 
                             current_date, df_analysis=None):
        return f"""
        You are a senior strategy consultant.
        Your job is to analyze the following information and give a targetted and concise reply to the user query below

        ## Context
        - General Goal: {query}
        - Subgoal: {subgoal or query}
        - Analysis Purpose: {analysis_reason}
        - Current Date: {current_date}

        ## Important Note About Batched Processing
        You are currently analyzing only a subset (batch) of the complete dataset. The numerical/statistical calculations below were performed on the ENTIRE dataset, not just the batch you can see. 
        Use these calculations to inform your analysis of the batch you have, but understand they reflect the full dataset.

        ## Data Analysis Results - These are IMPORTANT CALCULATIONS. If anything here is pertinent to your subgoal, emphasize it. This is general for the entire dataset. 
        If the subgoal is asking for a calculation like a mean or standard deviation, and it is provided here, emphasize this as your answer in this response. You should bold this answer or create a section for it.
        {df_analysis if df_analysis else "No quantitative analysis was performed on this data."}

        ## Data
        The following is the data for the current batch to be analyzed (no truncation):
        {json.dumps(valid_entities, indent=2)}

        ## Output Instructions
        - Write a markdown report (no JSON, no code blocks, no raw data dumps)
        - Provide a concise and exact reply to the above user question, in a FEW SENTENCES
        - Reference specific project names, priorities, timelines, budgets, constraints, and any other relevant fields
        - Reference the quantitative analysis results when relevant to provide context for your insights
        - Do not repeat database field names unless needed for clarity
        - Remember: Your insights should leverage both the batch data you can see AND the quantitative analysis of the full dataset
        """
    
    def eval_prompt_template(self, obj, entities, query, analysis_plan, subgoal=None, df_analysis=None, quick = False):
        """Evaluate entities and return a markdown report.
        
        Args:
            obj: The GeneralAnalyst instance
            entities: List of entity data to analyze
            query: Original query string
            analysis_plan: Analysis plan with settings
            subgoal: Optional subgoal for the analysis
            df_analysis: Optional dataframe analysis results as markdown
            
        Returns:
            Markdown report with analysis
        """
        # Get available roles for resource context
        all_roles_count_master_data = []  # Add actual role fetching if needed
        all_roles_consumed_for_tenant = []  # Add actual role fetching if needed
        available_roles = calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant)
        web = analysis_plan.get("web_search", False)
        
        current_date = datetime.now().date().isoformat()
        
        # Filter valid entities
        valid_entities = [e for e in entities if e]
        if not valid_entities:
            return f"No valid {self.entity_name} data to analyze."
        
        # Get analysis reason, defaulting to subgoal or query if not provided
        analysis_reason = analysis_plan.get("reason_behind_this_analysis", subgoal or query)
        
        if quick:
            system_prompt = self._build_system_prompt_quick(
                valid_entities=valid_entities,
                query=query,
                subgoal=subgoal,
                analysis_reason=analysis_reason,
                current_date=current_date,
                df_analysis=df_analysis
            )
            
            user_prompt = self._build_user_prompt_quick(
                len_entities=len(valid_entities),
                analysis_reason=analysis_reason
            )   
                 
        else:
            # Build prompt based on entity type - this ensures entity-specific prompting
            system_prompt = self._build_system_prompt(
                valid_entities=valid_entities,
                query=query,
                subgoal=subgoal,
                analysis_reason=analysis_reason,
                current_date=current_date,
                analysis_plan=analysis_plan,
                available_roles=available_roles,
                df_analysis=df_analysis
            )
        
            user_prompt = self._build_user_prompt(
                len_entities=len(valid_entities),
                analysis_reason=analysis_reason
            )
        
        for chunk in obj.llm.runWithStreaming(
            ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
            ModelOptions(model="gpt-4o", max_tokens=4096, temperature=0.2),
            f'tango::{self.entity_name}::evaluate',
            web = web
        ):
            yield chunk
        
    
    def _build_system_prompt(self, valid_entities, query, subgoal, analysis_reason, 
                             current_date, analysis_plan, available_roles, df_analysis=None):
        """Build system prompt for entity evaluation.
        Must be implemented by subclasses to provide entity-specific prompting.
        """
        raise NotImplementedError("Subclasses must implement _build_system_prompt")
    
    def _build_user_prompt(self, len_entities, analysis_reason):
        """Build user prompt for entity evaluation.
        Must be implemented by subclasses to provide entity-specific prompting.
        """
        raise NotImplementedError("Subclasses must implement _build_user_prompt")
    
    def fetch_data(self, obj, subgoal=None, row_mapping_data = None):
        """Fetch entity data with query optimization and proper JSON structure."""
        try:
            # Cache query results by subgoal to avoid redundant fetching
            cache_key = f"{self.entity_name}_data_{obj.tenant_id}_{subgoal}"
            if cache_key in self._data_cache:
                print(f"[{self.entity_name.capitalize()}Analyst] Using cached data for: {subgoal}")
                return self._data_cache[cache_key]
                
            # Initialize query optimizer with columns and query
            optimizer = QueryOptimizer(
                columns=[{
                    "name": col["name"],
                    "description": col["description"],
                    "pseudocolumn": col.get("pseudocolumn", False),
                } for col in self.columns],
                query=subgoal or "",
                table_name=self.table_name,
                tenant_id=obj.tenant_id,
                security_clauses=self.security_clauses,
                id_field=self.id_field,
                row_mapping_info=row_mapping_data
            )
            
            # Pass the actual query for analysis
            optimization_result = optimizer.optimize_query(subgoal or "")
            selected_fields_from_optimizer = optimization_result.get("columns", [])

            new_selected_fields = []
            pseudo_columns = []
            for field in selected_fields_from_optimizer:
                column = next((col for col in self.columns if col["name"] == field), None)
                if column:
                    if column.get("pseudocolumn", False):
                        pseudo_columns.append(field)
                    else:
                        new_selected_fields.append(field)
                else:
                    # Field not found in self.columns, effectively removing it.
                    print(f"Warning: Field '{field}' from optimizer not found in column definitions and will be excluded.")
            
            selected_fields = new_selected_fields
                    
            row_ids = optimization_result.get("row_ids", [])
            
            # Ensure core fields are included
            if self.id_field not in selected_fields:
                selected_fields.insert(0, self.id_field)
            if "title" not in selected_fields:
                selected_fields.insert(1, "title")
                
            # Add parent columns if needed
            parent_cols = self.get_parent_columns(self.columns, selected_fields)
            selected_fields.extend(parent_cols)
            
            # Build and execute query - uses entity-specific implementation
            base_query = self.get_query(fields=selected_fields, obj=obj)
            print("debug ---- ", base_query)
            if row_ids:
                where_clause = f"id IN (" + ", ".join(str(i) for i in row_ids) + ")"
                base_query = base_query.replace("ORDER BY", f"AND {where_clause} ORDER BY")
                
            query = base_query.replace("{tenant_id}", str(obj.tenant_id))
            rows = db_instance.retrieveSQLQueryOld(query)
            
            # Transform rows into proper JSON structure
            result = []
            for row in rows:
                if isinstance(row, dict):
                    processed_row = self.build_nested_json(row, self.columns)
                    result.append(processed_row)
                    
            # Store the last results
            obj.last_results = [r.get(self.id_field) for r in result]
            
            # Cache the result
            self._data_cache[cache_key] = result
        
            if pseudo_columns:
                print(f"Pseudo columns: {pseudo_columns}")
                # Handle pseudo columns if needed
                for row in result:
                    for col_name in pseudo_columns:  # col_name is a string
                        # Find the column definition from self.columns
                        column_def = next((c for c in self.columns if c["name"] == col_name), None)
                        
                        if not column_def:
                            # Log or handle if a pseudo_column name doesn't have a definition
                            print(f"Warning: Pseudo column '{col_name}' not found in column definitions.")
                            row[col_name] = None # Assign None if definition is missing
                            continue

                        params = column_def.get("params", [])
                        args = {}
                        if params:
                            for param in params:
                                param_name, row_name = param
                                if row_name in row:
                                    args[param_name] = row[row_name]
                                elif param_name == "tenant_id":
                                    args[param_name] = obj.tenant_id
                                else:
                                    print(f"Warning: Parameter '{param_name}' for pseudo column '{col_name}' not found in row.")
                            
                        pseudo_column_function = column_def.get("function")
                        if pseudo_column_function:
                            try:
                                pseudo_col_value = pseudo_column_function(**args)
                                row[col_name] = pseudo_col_value
                            except Exception as e:
                                print(f"Error executing pseudo column function for '{col_name}': {e}")
                                row[col_name] = None # Assign None or error indicator on function failure
                        else:
                            row[col_name] = None # Assign None if no function is defined
                                
            return result
            
        except Exception as e:
            print(f"ERROR in {self.entity_name}_fetch_data: {str(e)}")
            print(traceback.format_exc())
            return []
    
    def cluster_func(self, df):
        """Cluster entities based on a specified text column."""
        if not self.cluster_column_name:
            return df, 1 
            
        if self.cluster_column_name not in df.columns or df.empty:
            return df, 1

        text_data = [str(x) if x is not None else "" for x in df[self.cluster_column_name]]

        if not any(text_data):  # All strings are empty
            return df, 1

        vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
        try:
            X = vectorizer.fit_transform(text_data)
        except ValueError: 
            return df, 1

        if X.shape[0] == 0:
            return df, 1

        num_samples = X.shape[0]
        n_clusters = min(3, num_samples)
        if n_clusters < 1: 
            n_clusters = 1 if num_samples > 0 else 0  # if num_samples is 0, n_clusters should be 0
            if n_clusters == 0:  # No samples, no clusters
                return df, 0

        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init='auto').fit(X)
            df["cluster"] = kmeans.labels_
            return df, n_clusters
        except ValueError: 
            return df, 1