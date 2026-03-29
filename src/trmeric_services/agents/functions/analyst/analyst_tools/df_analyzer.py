"""DataFrame Analyzer for numerical and statistical analysis."""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
import json
from functools import lru_cache
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm

class DataframeAnalyzer:
    def __init__(self, llm):
        self.llm = llm
        self.model_options = ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0)
        self._operation_cache = {}  # Cache for operation results

    @lru_cache(maxsize=32)
    def _get_analysis_plan(self, query: str, columns_str: str) -> List[Dict]:
        """Get analysis plan from LLM with caching for identical queries."""
        print(f"[DfAnalyzer] Planning analysis for query: {query}")
        

        system = f"""You are a data analysis expert. Given a pandas DataFrame and a query:
1. Determine what numerical or statistical operations are needed
2. Return a list of operations to perform as JSON array with:
   - operation: string (e.g., 'mean', 'sum', 'count', 'groupby', 'sort', 'head', etc.)
   - columns: list of column names to operate on (only operate on columns that have numerical data)
   - group_by: list of columns to group by (optional)
   - filter: dict of filter conditions (optional)
   - description: string explaining what this operation calculates

For queries asking about averages, always specify:
```json
{{
  "operation": "mean",
  "columns": ["column_name"],
  "description": "Calculate average of column_name"
}}
```
"""
        
        user = f"""
            Available columns: {columns_str}
            Query: {query}
            Return the analysis operations to perform as JSON.
        """

        try:
            response = self.llm.run(
                chat=ChatCompletion(system=system, prev=[], user=user),
                options=self.model_options,
                function_name="plan_df_analysis"
            )
            print("[DfAnalyzer] Analysis plan received, extracting operations")
            operations = extract_json_after_llm(response)
            return operations
        except Exception as e:
            print(f"[DfAnalyzer] Error getting analysis plan: {str(e)}")
            return []


    def analyze_data(self, query: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Analyze dataframe based on query and return results."""
        print(f"[DfAnalyzer] Analyzing data for query: {query}")
        print(f"[DfAnalyzer] DataFrame shape: {df.shape}")
        
        # Generate cache key
        cache_key = f"{query}_{hash(frozenset(df.columns))}"
        
        # Check cache first
        if cache_key in self._operation_cache:
            print("[DfAnalyzer] Using cached analysis results")
            return self._operation_cache[cache_key]
        
        # Get analysis plan - using caching internally
        operations = self._get_analysis_plan(query, ', '.join(df.columns))
        
        results = []
        for op in operations:
            try:
                print(f"[DfAnalyzer] Executing operation: {op['operation']} on columns: {op.get('columns', [])}")
                # Ensure numeric columns are properly typed
                if op['operation'] in ['mean', 'sum']:
                    for col in op.get('columns', []):
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Execute operation with optimized method
                result = self._execute_operation_optimized(df, op)
                results.append({
                    "success": True,
                    "operation": op["operation"],
                    "description": op["description"],
                    "result": result
                })
            except Exception as e:
                print(f"[DfAnalyzer] Operation failed: {str(e)}")
                results.append({
                    "success": False,
                    "operation": op["operation"],
                    "description": op["description"],
                    "error": str(e)
                })
        
        # Cache results
        self._operation_cache[cache_key] = results
        
        return results

    def _execute_operation_optimized(self, df: pd.DataFrame, operation: Dict) -> Any:
        """Execute a single analysis operation on the dataframe with optimized performance."""
        # Apply filters directly if specified using numpy for speed
        if "filter" in operation:
            filtered_df = df.copy()
            for k, v in operation["filter"].items():
                if k in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df[k] == v]
        else:
            filtered_df = df
            
        # If empty dataframe after filtering, return appropriate result
        if filtered_df.empty:
            if operation["operation"] in ["count"]:
                return 0
            return np.nan
            
        # Execute operation
        op_type = operation["operation"].lower()
        columns = operation.get("columns", df.columns)
        
        if "group_by" in operation:
            grouped = filtered_df.groupby(operation["group_by"])
            
            # Optimize grouped operations
            if op_type == "count":
                return grouped[columns].count()
            elif op_type == "mean":
                return grouped[columns].mean()
            elif op_type == "sum":
                return grouped[columns].sum()
            elif op_type == "max":
                return grouped[columns].max()
            elif op_type == "min":
                return grouped[columns].min()
            else:
                raise ValueError(f"Unsupported group operation: {op_type}")
        else:
            # Direct calculations for non-grouped operations
            if op_type == "count":
                return filtered_df[columns].count()
            elif op_type == "mean":
                result = filtered_df[columns].mean()
                # If single column mean, return scalar for cleaner output
                if len(columns) == 1:
                    return float(result[0]) if isinstance(result, pd.Series) else float(result)
                return result
            elif op_type == "sum":
                result = filtered_df[columns].sum()
                if len(columns) == 1:
                    return float(result[0]) if isinstance(result, pd.Series) else float(result)
                return result
            elif op_type == "max":
                return filtered_df[columns].max()
            elif op_type == "min":
                return filtered_df[columns].min()
            elif op_type == "unique":
                return {col: filtered_df[col].unique().tolist() for col in columns}
            elif op_type == "sort":
                ascending = operation.get("ascending", True)  # Default to ascending order
                return filtered_df.sort_values(by=columns, ascending=ascending)
            elif op_type == "head":
                n = operation.get("n", 5)  # Default to showing top 5 rows
                return filtered_df.head(n)
            else:
                raise ValueError(f"Unsupported operation: {op_type}")

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """Format analysis results into a readable string."""
        output = []
        for result in results:
            if result["success"]:
                # Clearly state the operation type and result
                operation_type = result["operation"].upper()
                output.append(f"### {operation_type}: {result['description']}")
                output.append(f"**Operation**: {operation_type}")
                
                # Format different types of results
                if isinstance(result["result"], (pd.Series, pd.DataFrame)):
                    output.append(f"**Result**:\n```\n{result['result']}\n```")
                elif isinstance(result["result"], dict):
                    output.append("**Result**:\n```")
                    for k, v in result["result"].items():
                        output.append(f"{k}: {v}")
                    output.append("```")
                else:
                    # For scalar results, format more clearly
                    if isinstance(result["result"], (int, float)):
                        output.append(f"**Result**: {result['result']}")
                    else:
                        output.append(f"**Result**:\n```\n{result['result']}\n```")
            else:
                print(f"[DfAnalyzer] Formatting failed result: {result['description']}")
                output.append(f"### ERROR in {result['operation'].upper()}: {result['description']}")
                output.append(f"```\n{result['error']}\n```")
        
        print("[DfAnalyzer] Results formatting complete")
        return "\n".join(output)