import pandas as pd
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.utils.json_parser import extract_json_after_llm
from src.api.logging.AppLogger import appLogger

# Constants
DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS_CLARIFICATION = 200
DEFAULT_MAX_TOKENS_MAPPING = 800
DEFAULT_TEMPERATURE = 0.1

def create_mapping(FIELDS: list[str], data: pd.DataFrame, clarifying_information: str, user_id: int) -> dict[str, any]:
    """
    Create a mapping or request clarifying information based on LLM analysis.

    Args:
        FIELDS (list[str]): A list of available field names.
        data (pd.DataFrame): The dataframe containing the data.
        clarifying_information (str): Additional information to clarify the mapping (optional).
        user_id (int): User ID for the LLM client.

    Returns:
        dict[str, any]: A dictionary with 'type' ('data' or 'clarifying_question') and 'content' (the mapped data list or the question string).
    """
    mapping = {}
    fields = {idx: field for idx, field in enumerate(FIELDS)}
    column_names = {idx: col for idx, col in enumerate(data.columns.tolist())}

    # First, check if clarification is needed
    clarification_system_prompt = """
        You are an expert data analyst specializing in field-to-column mapping. Your task is to evaluate whether the provided information is sufficient to create accurate mappings between requested fields and available data columns.

        ANALYSIS CRITERIA:
        - Field names: {fields}
        - Available columns: {column_names}
        - Data sample to understand content:
        {data_sample}
        {clarifying_info_section}

        EVALUATION GUIDELINES:
            1. Assess if column names clearly correspond to the requested fields
            2. Consider if data content provides additional context for ambiguous column names
            3. Identify potential multiple matches or unclear mappings
            4. Determine if business context is needed (e.g., what constitutes "status" vs "priority")
            5. If clarifying information is provided, check if it already answers potential mapping questions
            6. IMPORTANT: When user refers to column names in clarifying information, use fuzzy matching - they might use abbreviations or partial names that correspond to actual columns

        WHEN TO ASK FOR CLARIFICATION:
            - Column names are generic (e.g., "col1", "field_a") and data content is unclear
            - Multiple columns could match a single field requirement
            - Field requirements are business-specific and need domain knowledge
            - Data types or formats need clarification for proper interpretation
            - The provided clarifying information references columns that don't exist AND can't be reasonably matched to existing columns

        WHEN CLARIFICATION IS NOT NEEDED:
            - Column names clearly match field requirements (exact or obvious synonyms)
            - Data content provides sufficient context to resolve ambiguities
            - Only one reasonable mapping exists for each field
            - The provided clarifying information references columns that exist or can be reasonably matched (e.g., "org_strategy align" could match "Alignment with Org priority")
            - User has provided specific field-to-column mapping instructions, even if using abbreviated column names

        COLUMN MATCHING RULES:
            - Consider partial matches, abbreviations, and semantic equivalents
            - "org_strategy align" should match "Alignment with Org priority"
            - "proj name" should match "Project Name" or "Suggested Project Name"
            - Use common sense fuzzy matching for user-provided column references

        Response format: {{"needs_clarification": true/false, "question": "specific question or empty string", "reasoning": "brief explanation of decision"}}
    """.format(
        fields=fields, 
        column_names=column_names, 
        data_sample=data.head().to_string(),
        clarifying_info_section=f"\n- User provided clarifying information: {clarifying_information}" if clarifying_information else ""
    )

    clarification_user_message = """
        Analyze the field-to-column mapping scenario and determine if clarifying information is needed.

        Consider the semantic relationship between field names and column headers, examine the data sample for context clues, and identify any potential ambiguities that would prevent accurate mapping.

        Focus on practical mapping challenges rather than theoretical possibilities.

        IMPORTANT: If clarifying information has been provided by the user, evaluate whether it already answers the mapping questions you would ask. Only request additional clarification if the provided information doesn't address the specific ambiguities.
    """

    llm = ChatGPTClient(user_id=user_id)
    try:
        clarification_response = llm.run(
            ChatCompletion(system=clarification_system_prompt, prev=[], user=clarification_user_message),
            ModelOptions(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS_CLARIFICATION, temperature=DEFAULT_TEMPERATURE),
            "check_clarification_needed"
        )
        clarification_data = extract_json_after_llm(clarification_response)
        if isinstance(clarification_data, dict) and clarification_data.get('needs_clarification', False):
            return {
                'type': 'clarifying_question',
                'content': clarification_data.get('question', 'Please provide more details about the data mapping requirements.')
            }
    except Exception as e:
        appLogger.error(f"Error in clarification check: {e}")
        # Proceed to mapping if clarification check fails

    # Proceed to mapping if no clarification needed
    system_prompt = """
        You are an expert data mapping specialist with extensive experience in field-to-column analysis. Your task is to create precise mappings between requested fields and available data columns.

        MAPPING CONTEXT:
        Required Fields: {fields}
        Available Columns: {column_names}
        Data Preview: {data_head}

        MAPPING STRATEGY:
        1. Prioritize exact name matches first
        2. Consider semantic equivalents (e.g., "name" ↔ "project_name", "desc" ↔ "description")  
        3. Use data content as context for ambiguous column names
        4. Apply case-insensitive matching throughout
        5. Recognize common abbreviations and variations

        QUALITY STANDARDS:
        - Only create mappings with high confidence (>80% certainty)
        - Avoid forced matches - missing mappings are better than incorrect ones
        - Consider data type compatibility (text fields shouldn't map to numeric columns unless contextually appropriate)
        - Validate that mapped columns contain relevant data based on the sample

        RESPONSE FORMAT:
        Return a ONLY A JSON object mapping field IDs to column IDs:
        {{
            "field_id": "column_id",
            "field_id": "column_id"
        }}

        EXAMPLE SCENARIO:
        If given:
        - Fields: {{0: "project name", 1: "status", 2: "description"}}
        - Columns: {{0: "proj_title", 1: "current_state", 2: "notes"}}

        Correct response:
        {{
            "0": "0",
            "1": "1",
            "2": "2"
        }}

        MAPPING RULES:
        RETURN JUST THE JSON OBJECT IN THE FORM SHOWN ABOVE
        ✓ Include only confident matches
        ✓ Skip fields without clear corresponding columns
        ✓ Consider synonyms: name/title, status/state, desc/description/notes
        ✓ Use data content to resolve ambiguities
        ✗ Don't force mappings for unclear relationships
        ✗ Don't map incompatible data types without strong justification
    """.format(fields=fields, column_names=column_names, data_head=data.head().to_string())
    
    user_message = "Analyze the provided data and create optimal field-to-column mappings based on semantic similarity and data content analysis."
    if clarifying_information:
        user_message += f"\n\nAdditional Context:\n{clarifying_information}"
    llm = ChatGPTClient(user_id=user_id)

    try:
        response = llm.run(
            ChatCompletion(system=system_prompt, prev=[], user=user_message),
            ModelOptions(model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS_MAPPING, temperature=DEFAULT_TEMPERATURE),
            "sheet_match_columns_to_fields"
        )

        response = extract_json_after_llm(response)

        if not isinstance(response, dict):
            raise ValueError("LLM response is not a valid JSON dictionary")

        for field_id, column_id in response.items():
            try:
                field_name = fields[int(field_id)]
                column_name = column_names[int(column_id)]
                mapping[field_name] = column_name
            except (ValueError, KeyError) as e:
                # Skip invalid mappings
                continue

    except Exception as e:
        # Log the error and return empty data if LLM fails
        appLogger.error(f"Error in LLM mapping: {e}")
        mapping = {}

    # Transform the mapped data into the required format
    result_data = []
    
    # Identify unmapped columns
    mapped_columns = set(mapping.values())
    all_columns = set(data.columns)
    unmapped_columns = all_columns - mapped_columns
    
    print(f"[SHEET_MAPPER] Mapped columns: {mapped_columns}")
    print(f"[SHEET_MAPPER] Unmapped columns: {unmapped_columns}")
    
    for _, row in data.iterrows():
        row_data = {}
        
        # Add mapped field data
        for field, column in mapping.items():
            try:
                value = row[column]
                # Convert pandas data types to JSON-serializable types for mapped fields too
                if pd.isna(value):
                    row_data[field] = None
                elif isinstance(value, (pd.Timestamp, pd.NaT.__class__)):
                    row_data[field] = str(value) if not pd.isna(value) else None
                elif hasattr(value, 'item'):  # numpy scalar types
                    row_data[field] = value.item()
                else:
                    row_data[field] = value
            except KeyError:
                # Handle case where mapped column doesn't exist
                appLogger.warning(f"Column '{column}' not found in data")
                row_data[field] = None
        
        # Add unmapped columns as additional_data
        if unmapped_columns:
            additional_data = {}
            for unmapped_col in unmapped_columns:
                try:
                    # Convert pandas data types to JSON-serializable types
                    value = row[unmapped_col]
                    if pd.isna(value):
                        additional_data[unmapped_col] = None
                    elif isinstance(value, (pd.Timestamp, pd.NaT.__class__)):
                        additional_data[unmapped_col] = str(value) if not pd.isna(value) else None
                    elif hasattr(value, 'item'):  # numpy scalar types (int64, float64, etc.)
                        additional_data[unmapped_col] = value.item()
                    elif isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):
                        additional_data[unmapped_col] = str(value)
                    else:
                        # For any other type, try to convert to basic Python types
                        try:
                            # This handles most pandas extension types
                            if hasattr(value, 'to_pydatetime'):
                                additional_data[unmapped_col] = value.to_pydatetime().isoformat()
                            elif hasattr(value, '__str__'):
                                additional_data[unmapped_col] = str(value)
                            else:
                                additional_data[unmapped_col] = value
                        except:
                            additional_data[unmapped_col] = str(value)
                except (KeyError, TypeError) as e:
                    appLogger.warning(f"Error processing unmapped column '{unmapped_col}': {e}")
                    additional_data[unmapped_col] = None
            
            row_data['additional_data'] = additional_data
        
        result_data.append(row_data)
        
    return {
        'type': 'data',
        'content': result_data
    }
