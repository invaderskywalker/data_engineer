from src.trmeric_ml.llm.Client import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm


class CapacityPrompt:
    def __init__(self):
        self.llm = ChatGPTClient()
        self.generate_prompt = self.llm.generate_prompt
        
# user_message = f"Here is the dataframe:\n{df.head().to_markdown(index=False)}"
    
#     # Step 1: Initial categorization check
#     categorizable_system = f"""Can this IT spend data be categorized into {categories}? 
#     Respond with JSON:
#     for relevant columns, always keep column names which are like: name, type, category, description, etc...
#     Feel free to keep anything that may be remotely helpful.
#     {{"can_be_categorized": boolean, "relevant_columns_names_for_categorization": ["column1_name", "column2_name", ...]}}"""
    
#     response = llm.run(
#         ChatCompletion(system=categorizable_system, prev=[], user=user_message), 
#         ModelOptions(model="gpt-4o-mini", max_tokens=200, temperature=0), 
#         "analyze_spend_per_category_ui"
#     )
#     response = extract_json_after_llm(response)
    
#     if not response.get('can_be_categorized', False):
#         print("Data cannot be categorized. Returning original DataFrame.")
#         return df
    

def create_categorization_prompt(dataframe_str, key):
    """
    Create a prompt for the LLM to categorize a dataframe and identify relevant columns.
    """
    if key == "internal":
        prompt = f"""
    You are a File Retrieval Agent processing customer-uploaded onboarding documents.
    Given the following dataframe from a sheet, determine the type of data it contains and identify relevant columns.

    <dataframe>
    {dataframe_str}
    </dataframe>

    Expected data types for internal data:
    - 'employee_info': Employee ID, Employee Name, Role, Skills, Allocation%, Rate, Experience, Projects
    - 'project_details': Project name, Start date, End date
    - 'other': Does not match the above

    Classify the type and list columns present that match the expected fields for that type.
    Check if a unique identifier (Employee ID or Employee Name) is present for 'employee_info'.

    Respond in JSON format:
    {{
        "type": "employee_info" or "project_details" or "other",
        "relevant_columns": ["column1", "column2", ...],
        "has_unique_identifier": true or false,
        "available_details": "description of available data",
        "missing_details": "description of missing data"
    }}
    """
    else:  # key == "provider"
            prompt = f"""
    You are a File Retrieval Agent processing customer-uploaded onboarding documents.
    Given the following dataframe from a sheet, determine the type of data it contains and identify relevant columns.

    <dataframe>
    {dataframe_str}
    </dataframe>

    Expected data types for provider data:
    - 'provider_info': Provider Name, Provider Address, Provider Website
    - 'employee_info': Employee ID, Employee Name, Role, Skills, Allocation%, Rate, Experience, Projects
    - 'project_details': Project name, Start date, End date
    - 'other': Does not match the above

    Classify the type and list columns present that match the expected fields for that type.
    Check if a unique identifier (Provider Name for 'provider_info', Employee ID or Employee Name for 'employee_info') is present.

    Respond in JSON format:
    {{
        "type": "provider_info" or "employee_info" or "project_details" or "other",
        "relevant_columns": ["column1", "column2", ...],
        "has_unique_identifier": true or false,
        "available_details": "description of available data",
        "missing_details": "description of missing data"
    }}
    """
    return ChatCompletion(system=prompt, prev=[], user='')


def create_categorization_prompt_v2(dataframe_str, key):
    if key == "internal":
        prompt = f"""
            You are a File Retrieval Agent processing customer-uploaded onboarding documents.
            Given the following dataframe from a sheet, determine the type of data it contains and identify relevant columns.

            <dataframe>
            {dataframe_str}
            </dataframe>

            Expected data types for internal data:
            - 'employee_info': employee_id, name, role, skill, allocation, rate, experience, projects
            - 'project_details': Project name, Start date, End date
            - 'other': Does not match the above

            Classify the type and list columns present that match the expected fields for that type.
            Check if a unique identifier (employee_id or name) is present for 'employee_info'.

            Respond in JSON format:
            ```json
                {{
                    "type": "employee_info" or "project_details" or "other",
                    "relevant_columns": ["column1", "column2", ...],
                    "has_unique_identifier": true or false,
                    "available_details": "description of available data",
                    "missing_details": "description of missing data"
                }}
            ```
    """
    
    else:  # provider
        prompt = f"""
            You are a File Retrieval Agent processing customer-uploaded onboarding documents.
            Given the following dataframe from a sheet, determine the type of data it contains and identify relevant columns.

            <dataframe>
            {dataframe_str}
            </dataframe>

            Expected data types for provider data:
            - 'provider_info': provider_name, employee_id, name, role, skill, allocation, rate, experience, projects
            - 'employee_info': employee_id, name, role, skill, allocation, rate, experience, projects
            - 'project_details': Project name, Start date, End date
            - 'other': Does not match the above

            Classify the type and list columns present that match the expected fields for that type.
            Check if a unique identifier (provider_name, employee_id, or name) is present.

            Respond in JSON format:
            ```json
                {{
                    "type": "provider_info" or "employee_info" or "project_details" or "other",
                    "relevant_columns": ["column1", "column2", ...],
                    "has_unique_identifier": true or false,
                    "available_details": "description of available data",
                    "missing_details": "description of missing data"
                }}
            ```
    """
    
    return ChatCompletion(
        system="You are a file retrieval agent whose task is to analyze the provided dataframe and extract relevant information.",
        prev=[],
        user=prompt
    )






def filePrompt(self,dataframe,key): 
    prompt = f"""
            You are playing the role of a File Retrieval Agent responsible for processing customer-uploaded onboarding documents containing team resource data.
            These documents include details of employees, projects, and timelines (start and end dates). 
            Your task is to analyze the provided dataframe and extract relevant information for internal employees or external provider employees.
            <dataframe> {dataframe} </dataframe>
        """
    match key:
        case 'internal':
            prompt += f"""These are the expected Fields which will be used for categorization:
                1. Employee Information:
                    Employee ID or Name (at least one must be present as a unique identifier)
                    Role
                    Skills
                    Allocation%
                    Rate
                    Experience
                    Projects
                    
                2.Project Details (may exist in different sheets):
                    Project name
                    Start date
                    End date
                    
                ### Processing Instructions: Identify Unique Employee Information:
                    -Check if either Employee ID or Name is present.
                    -If neither is available, set "is_unique_identifier_available": false.
                    -Extract Relevant Data Columns: Identify and store the names of columns that match the expected fields.
                    
                ### Output Format:Return the extracted information as a structured JSON object:
                ```json
                {{
                    "is_unique_identifier_available": boolean,
                    "relevant_columns_names_for_categorization_available": ["column1_name", "column2_name", ...],
                    "available_details": "",// A description of the data available in <dataframe>
                    "missing_details": // A descripiton of the missing columns not present in the <dataframe>
                }}
                ```
                
                ###Additional Considerations
                - Ensure consistent employee identification across multiple uploaded sheets.
                - Ignore irrelevant columns that do not match the expected structure.
                - If key fields are missing, flag them instead of making assumptions.
            """
        case 'provider':
            prompt += f"""These are the Expected Fields:
                1. Provider Information:
                    -Provider Name (must be present as a unique identifier)
                    -Provider Address
                    -Provider Website
                    
                2. Employees of the Provider:
                    -Employee ID or Name (at least one must be present as a unique identifier)
                    -Role
                    -Skills
                    -Allocation%
                    -Rate
                    -Experience
                    -Projects
                    
                3. Project Details (may exist in different sheets):
                    -Project name
                    -Start date
                    -End date
                    
                ### Processing Instructions: Identify Unique Provider Information:
                - Check if Provider Name is present.
                - If missing, set "is_unique_identifier_available": false.
                - Extract Relevant Data Columns and Identify and store the names of columns that match the expected fields.
                
                
                ### Output Format
                Return the extracted information as a structured JSON object:
                ```json
                {{
                    "is_unique_identifier_available": boolean,
                    "relevant_columns_names_for_categorization_available": ["column1_name", "column2_name", ...],
                    "available_details": "", //A description of the data available in <dataframe>
                    "missing_details": "",// A descripiton of the missing columns not present in the <dataframe>
                }}
                ```
                
                ### Additional Considerations
                - Ensure consistent provider and employee identification across multiple uploaded sheets.
                - Ignore irrelevant columns that do not match the expected structure.
                - If key fields are missing, flag them instead of making assumptions.
            """

    return prompt
    
def categorizeFilesPrompt(key, user_message,all_sheets,llm,model_opts,logInfo) -> ChatCompletion:
    """Based on key Internal or External provided in current session recognize the fields fetched and inform the user in real-time"""
    
    for sheet, df in enumerate(all_sheets):
        dataframe =  f"Here is the dataframe:\n{df.head().to_markdown(index=False)}"
        prompt = filePrompt(dataframe,key)
        
    return ChatCompletion(
        system=prompt,
        prev=[],
        user=''
    )


def columnsPrompt(instruction, required_columns, df) -> ChatCompletion:
    """
    Generates a system prompt for the LLM to map uploaded file columns to required standard fields.

    Args:
        instruction (str): User instruction for LLM.
        required_columns (list): List of required standard fields.
        df (pd.DataFrame): DataFrame containing the uploaded file data.

    Returns:
        ChatCompletion: LLM response for column mapping.
    """
    # Ensure df is valid and has columns
    if df is None or df.empty:
        raise ValueError("--debug: DataFrame is empty or None. Cannot generate column mapping prompt.")
    
    # Generate the system prompt
    system_prompt = f"""
    You are an AI assistant that helps map columns from an uploaded resource planning file to standardized fields. 

    ### Given Columns:
    The uploaded file contains the following columns:
    {', '.join(df.columns)}

    ### Required Standard Fields:
    These are the expected standard fields:
    {', '.join(required_columns)}
    
    ### Task:
     - Map each uploaded column to the **exact** required field name.
     - Use only the required field names as provided (including underscores).
     - If a column does not match any standard field, exclude it from the mapping.
     - Exclude columns without a clear match.
     
    ### Strict Rules:
        1. Use ONLY these exact field names: {', '.join(required_columns)}
        2. Never modify field name casing/spacing
        3. Map only clear matches
        4. Skip ambiguous mappings
        ### Provider Data Example:
            If uploaded columns include: [Company, Employee, Email, Exp...]
            Then map to: {{
                "Company": "provider_name",
                "Employee": "name",
                "Email": "email",
                "Experience": "experience",
                "Allocation": "allocation"
            }}

    ### Expected JSON Output:
    ```json
    {{
        "mapped_columns": {{
            "Uploaded Column 1": "Standard Field Name",
            "Uploaded Column 2": "Standard Field Name",
            ....
        }}
    }}
    ```
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=instruction
    )



def detectHeaderRowPrompt(df, requiredColumns) -> ChatCompletion:
    print("--debug in detectHeaderRowPrompt", df ,requiredColumns)
    
    df_string = df.head(5).to_string(index=False)  # Limit size for better readability
    required_columns_str = ", ".join(requiredColumns)
    prompt = f"""
    
    You are given a dataframe where the first few rows may contain empty or irrelevant data, and the actual column headers could appear at a variable row position. Your task is to identify the first row that 
    contains valid column headers based on a given list of required column names.
    You should scan the dataframe row by row, checking for the presence of at least one required column name (case insensitive) in each row.

    Your task is to  **find the index of the first detected header row**.
    If no valid header row is found, return None.
    
    **Input**:
        - df: A Pandas dataframe containing the raw data.
        <dataframe>
            {df_string}
        <dataframe>
        - required_columns: {required_columns_str}.
        
    
    
    ### Expected JSON Output: Return the index of the first detected header row in JSON format:
    ```json
    {{
        "header_row": <integer>
    }}
    ```
    """
    
    return ChatCompletion(
        system = prompt,
        prev = [],
        user = ''
    )
    

def capacity_onboarding_flow(conv) -> ChatCompletion:
    prompt = f"""
    
    Ongoing Conv:{ conv}
    You are an AI assistant guiding a user through a capacity planning onboarding process.
    Your task is to help the user upload and process their team capacity data effectively.

    Follow these steps based on the user's input:
    
    1. If the user wants to do capacity planning:
       - Prompt them to upload their Internal Team File
       - Specify that the file should contain these required columns.
    
    2. After the user uploads a file:
       - Process the uploaded file and analyze its contents
       - Display:
         a. Available columns found in the file
         b. Missing required columns (if any)
       - Ask the user for feedback about the processed data and whether they want to:
         a. Upload a different Internal Team File
         b. Proceed with the current data to the provider flow
    
    3. Based on user feedback:
       - If the user wants to upload a different file:
         - Guide them to upload a new Internal Team File
         - Process the new file and repeat step 2
       - If the user wants to proceed with the current data:
         - Trigger the provider flow process
         - Prompt the user to upload a Provider File for the next phase
       - If the user is satisfied with the Internal Team File but doesn't want to proceed:
         - Confirm completion of the internal team onboarding process
         
    4. Both flows for Internal and Provider completed:
        - Confirm successful completion of the onboarding process
        - Provide a summary of the processed data from both flows
        - Trigger the completed flow
    
    5. Transition stage:
        - If the user skips after internal_team stage then switch to flow_stage "provider"
        - If the user skips after provider stage then switch to flow_stage "completed" or the user skips after both stages then switch to flow_stage "completed"
    
    ### Always Expected JSON Output: 
    When processing a file, return the index of the first detected header row in JSON format:
    ```json
    {{
        "flow_stage": "internal_team"  # or "provider" when that flow is triggered or "completed" when both flows are done
        "reason_of_flow_stage": ""
    }}
    ```
    """

    
    return ChatCompletion(
        system=prompt,
        prev=[],
        user='Please determine the correct step in JSON FORMAT.'
    )