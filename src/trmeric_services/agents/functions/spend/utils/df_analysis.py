from typing import List, Dict, Any, Optional
import pandas as pd
from copy import deepcopy
import json
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
import re
def get_system_prompt(category) -> str:
    if category:
        return f"""
You are an intelligent data analysis finance agent who is helping a company try to analyze their IT spend. Your job is to figure out several key metrics / patterns that could be interesting and calculated from these data frames with the goal of helping them eventually optimize and lower their spend.

Given a few dataframes, and their respective columns, your task is to propose at least 5 different calculations, along with their descriptions, and the python code using pandas to execute that code.

IMPORTANT: The table names you see in the preview will be the exact variable names you should use in your code. Do NOT try to read Excel files directly - the DataFrames are already loaded and available by their listed names.

IMPORTANT: The data you have been given has been filtered by Tango Category: {category} already. All the values in this column will be the same, so no need to group by this again.


Always try to calculate the total spend.
Always try to calculate the total spend grouped by subcategories, try a few.

For example, if you see:
Table: Enterprise_IT_Budget___Spend_Tracker__1__xlsx
Shape: (100, 10)
...

Then use that exact name in your code:
result = Enterprise_IT_Budget___Spend_Tracker__1__xlsx.groupby('Category')['Amount'].sum()

To do category based calculations, you can use the 'Tango_Category' column in the dataframes. Group by this.
Also, IMPORTANT: if you have a column referencing invoice totals, This is the column you should use for spend calculations.

Your response should be nothing but a JSON array, formatted like:
[
    {{
    "calculation": <name of calculate, eg: spend by category>,
    "description": <description of calculation>,
    "tables_used": [<exact table names as shown in preview>],
    "code": <code that uses the exact table names>
    }}
]

Make sure the code that you execute will produce a dataframe with columns and rows that make sense and are descriptive.

Provide your suggestions in a structured JSON format that can be directly executed. Your response should be the list and the list only. Your response should be a list and a list only."""

        
    else:
        return """
You are an intelligent data analysis finance agent who is helping a company try to analyze their IT spend. Your job is to figure out several key metrics / patterns that could be interesting and calculated from these data frames with the goal of helping them eventually optimize and lower their spend.

Given a few dataframes, and their respective columns, your task is to propose at least 5 different calculations, along with their descriptions, and the python code using pandas to execute that code.

First, try to make calculations that calculate the total spend by certain categories (IT Services, Software, Devices, Data Center Systems, Communication Software)
For this, some dataframes will come to you with a column called 'Tango_Category' which will have the category of the spend. You can do a lot of analysis by filtering just these categories.

IMPORTANT: The table names you see in the preview will be the exact variable names you should use in your code. Do NOT try to read Excel files directly - the DataFrames are already loaded and available by their listed names.

IMPORTANT: If there is a Tango Category column, use that for category based calculations. Always true to calculate the total spend grouped by these tango categories.

For example, if you see:
Table: Enterprise_IT_Budget___Spend_Tracker__1__xlsx
Shape: (100, 10)
...

Then use that exact name in your code:
result = Enterprise_IT_Budget___Spend_Tracker__1__xlsx.groupby('Category')['Amount'].sum()

To do category based calculations, you can use the 'Tango_Category' column in the dataframes. Group by this.
Also, IMPORTANT: if you have a column referencing invoice totals, This is the column you should use for spend calculations.

Your response should be nothing but a JSON array, formatted like:
[
    {
    "calculation": <name of calculate, eg: spend by category>,
    "description": <description of calculation>,
    "tables_used": [<exact table names as shown in preview>],
    "code": <code that uses the exact table names>
    }
]

Make sure the code that you execute will produce a dataframe with columns and rows that make sense and are descriptive.

Provide your suggestions in a structured JSON format that can be directly executed. Your response should be the list and the list only. Your response should be a list and a list only."""

def get_user_prompt(table_info: str) -> str:
    return f"""Based on the following tables and their contents:

{table_info}

Generate a JSON structure containing interesting calculations that could analyze this data.

Include calculations like spend by category, trend analysis, etc. Return only valid JSON."""

def generate_table_preview(data, max_rows: int = 8) -> str:
    """Generate a preview of the data including shape/structure and sample rows."""
    if isinstance(data, pd.DataFrame):
        preview = f"Shape: {data.shape}\n"
        preview += f"Columns and types:\n{data.dtypes.to_string()}\n\n"
        preview += f"Sample data (up to {max_rows} rows):\n{data.head(max_rows).to_string()}\n"
        return preview
    elif isinstance(data, dict):
        # For Excel files, each key is a sheet name and value is a DataFrame
        previews = []
        for sheet_name, df in data.items():
            if isinstance(df, pd.DataFrame):
                previews.append(f"Sheet: {sheet_name}\n" + generate_table_preview(df, max_rows))
        return "\n---\n".join(previews)
    else:
        return f"Data type: {type(data)}\nString representation: {str(data)[:100]}"


def generate_df_analysis_suggestions(
    df_map,
    llm,
    max_preview_rows: Optional[int] = 8,
    category = None
) -> Dict[str, Any]:
    """
    Generate and execute interesting calculations on provided dataframes using LLM suggestions.
    
    Args:
        df_map: Dictionary mapping file names to their sheet DataFrames
        llm: LLM client instance to use for generating suggestions
        max_preview_rows: Maximum number of rows to show in table previews
        
    Returns:
        Dictionary containing suggested calculations and their results
    """
    # Create detailed descriptions of each Excel file and its sheets
    table_info = []
    
    # Create a mapping of available tables
    available_tables = {}
    for file_name, sheets_dict in df_map.items():
        if isinstance(sheets_dict, dict):
            for sheet_name, df in sheets_dict.items():
                # Create a clean name for the table
                clean_name = file_name.replace(' ', '_').replace('-', '_').replace('.', '_').replace('(', '_').replace(')', '_')
                available_tables[clean_name] = df
                preview = generate_table_preview(df, max_preview_rows)
                table_info.append(f"Table: {clean_name}\n{preview}\n{'='*50}\n")
        else:
            print(f"Warning: Expected dict for {file_name}, got {type(sheets_dict)}")
        
    # Combine all table information
    table_info_str = "\n".join(table_info)
    
    systemPrompt = get_system_prompt(category)
    userMessage = get_user_prompt(table_info_str)
    
    response = llm.run(
        ChatCompletion(system=systemPrompt, prev=[], user=userMessage), 
        ModelOptions(model="gpt-4o", max_tokens=4000, temperature=0.3), 
        "analyze_spend_per_category"
    )
    # there might be: ```json in the response, so remove that
    response = response.replace("```json", "").replace("```", "").strip()
    
    try:
        calculations = json.loads(response)
        if not isinstance(calculations, list):
            raise ValueError("Expected a list of calculations")
    except json.JSONDecodeError:
        return ""

    # Execute each suggested calculation
    results = []
    for idx, calc in enumerate(calculations):
        try:
            # Validate calculation structure
            required_fields = {"calculation", "description", "tables_used", "code"}
            if not all(field in calc for field in required_fields):
                # don't throw an exception jsust move on to next
                continue
            
            # Create namespace with actual table names
            table_map = {}
            for table_name in calc["tables_used"]:
                clean_name = None
                # Try to find the table by matching against available tables
                for available_name in available_tables.keys():
                    if table_name in available_name or available_name in table_name:
                        clean_name = available_name
                        break
                
                if clean_name is None:
                    raise ValueError(f"Table {table_name} not found in available data. Available tables: {list(available_tables.keys())}")
                
                table_map[clean_name] = deepcopy(available_tables[clean_name])
            
            print(f"\n{'='*50}")
            print(f"Executing calculation: {calc['calculation']}")
            print(f"Using tables: {list(table_map.keys())}")
            print(f"Code to execute:\n{calc['code']}")
            
            # Create namespace with mapped DataFrames and pandas
            local_namespace = {**table_map, 'pd': pd}
            
            try:
                # Execute the calculation
                exec(calc["code"], {}, local_namespace)
                
                # Get the result (could be any variable name)
                result = None
                for var_name, var_value in local_namespace.items():
                    if var_name not in table_map and var_name != 'pd':
                        result = var_value
                        break
                
                print("Execution successful")
                
                # Convert result to string format if it's a DataFrame or Series
                if isinstance(result, (pd.DataFrame, pd.Series)):
                    result_str = result.to_string()
                elif isinstance(result, dict):
                    # For dictionary results, try to convert to DataFrame first
                    try:
                        result_df = pd.DataFrame.from_dict(result, orient='index')
                        result_str = result_df.to_string()
                    except:
                        result_str = str(result)
                else:
                    result_str = str(result)
                                
                # Store the result with all information
                results.append({
                    "calculation": calc["calculation"],
                    "description": calc["description"],
                    "tables_used": calc["tables_used"],
                    "code": calc["code"],
                    "result": result,
                    "error": None
                })
            except Exception as e:
                print(f"Execution failed with error: {str(e)}")
                
        except Exception as e:
            print(f"Execution failed with error: {str(e)}")
    print ("Finished calculations and returning")

    formatted_string = ""
    if category:
        formatted_string += f"My Tango_Category: {category}\n\n"
    for result in results:
        formatted_string += f"{result['description']}\n{result['result']}\n\n"
    return formatted_string