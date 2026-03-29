from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.agents.functions.spend.utils.spend import spend_add_sources, spend_cancel
from src.trmeric_services.agents.functions.spend.utils.spend import analyze_spend, emit_progress
from src.trmeric_services.agents.functions.spend.utils.categorize import create_categories
from src.trmeric_services.agents.functions.spend.utils.ui_json import ui_json
from src.trmeric_services.agents.functions.spend.utils.df_serialization import deserialize_dfs, serialize_dfs
import json
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_services.journal.Activity import detailed_activity, activity_log
from src.trmeric_s3.s3 import S3Service
import pandas as pd

def spend_evaluation(client_id, tenantID: int, userID: int, llm, integrations, sessionID, user_specified_category_to_analyze_further = '', industry_employee_info = None, user_feedback_on_categories_for_their_files = '', **kwargs):
    socketio = kwargs.get('socketio')
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    sources_added = False
    employees_asked = False
    initial_eval = False
    spend_dcs_eval = None
    spend_s_eval = None
    spend_is_eval = None
    spend_cs_eval = None
    spend_d_eval = None
    category_feedback = ""
    categories_confirmed = False

    for state in states:
        if state['key'] == 'SPEND_ADD_SOURCE':
            sources_added = True
        if state['key'] == 'SPEND_ASK_EMPLOYEES':
            employees_asked = True
        if state['key'] == 'SPEND_EVALUATION_FINISHED':
            initial_eval = True
        if state['key'] == 'SPEND_STORED_DCS_EVAL':
            spend_dcs_eval = state['value']
        if state['key'] == 'SPEND_STORED_S_EVAL':
            spend_s_eval = state['value']
        if state['key'] == 'SPEND_STORED_IS_EVAL':
            spend_is_eval = state['value']
        if state['key'] == 'SPEND_STORED_CS_EVAL':
            spend_cs_eval = state['value']
        if state['key'] == 'SPEND_STORED_D_EVAL':
            spend_d_eval = state['value']
        if state['key'] == 'SPEND_CATEGORIES_CONFIRMED':
            categories_confirmed = True
        if state['key'] == 'SPEND_PICKLED_DFS':
            pickled_dfs = state['value']
        if state['key'] == 'SPEND_SAVED_CORPUS':
            saved_corpus = state['value']
        if state['key'] == 'SPEND_USER_FEEDBACK':
            category_feedback += state['value'] + '\n\n'
                 
            
    if not employees_asked:
        TangoDao.insertTangoState(tenantID, userID, 'SPEND_ASK_EMPLOYEES', '', sessionID)
        
        # Log activity: User initiated spend analysis
        detailed_activity(
            activity_name="spend_analysis_initiation",
            activity_description="User initiated comprehensive IT spend analysis. Tango requested company context including employee count to provide industry-benchmarked insights.",
            user_id=userID
        )
        
        return "Great. To continue further in this spend analysis, please provide the number of employees in your organization."
    
    if not sources_added:
        return spend_add_sources(tenantID, userID, sessionID, socketio, client_id)

    if not categories_confirmed:
        if user_feedback_on_categories_for_their_files:
            TangoDao.insertTangoState(tenantID, userID, 'SPEND_USER_FEEDBACK', user_feedback_on_categories_for_their_files, sessionID)
            category_feedback += user_feedback_on_categories_for_their_files + '\n\n'
        try:
            dfs, saved_corpus, analysis_results =  create_categories(integrations, llm, socketio, client_id, industry_employee_info, feedback = category_feedback)
            
            # Log activity: Successfully categorized spend data
            detailed_activity(
                activity_name="spend_data_categorization",
                activity_description="User uploaded IT spend files. Tango intelligently analyzed and categorized expenses into Software, IT Services, Communication Services, and Devices with detailed subcategory breakdowns.",
                user_id=userID
            )
            
        except Exception as e:
            if str(e) == 'No files found':
                return "No files found. Please upload files to analyze your spend."
            print(e)
        serialized_dfs = serialize_dfs(dfs)

        TangoDao.insertTangoState(tenantID, userID, 'SPEND_PICKLED_DFS', serialized_dfs, sessionID)
        print("finished dfs")
        TangoDao.insertTangoState(tenantID, userID, 'SPEND_SAVED_CORPUS', saved_corpus, sessionID)
        yield_after = f"""
```json
{{
"cta_buttons": [
    {{
        "label": "Confirm Categories",
        "action": "spend_confirm_categories_button"
    }}
]
}}
```
        """ 
        ret_val = f"Explicity show this data correctly without altering any of the values: Here are the categories I have identified for your files: {analysis_results}. Please explicitly confirm if these are acceptable. If not, provide feedback and Tango will consider this and recategorize."
        return TangoYield(return_info=ret_val, yield_info=yield_after)
    if not initial_eval:
        # Decode the Base64 string back to binary
        loaded_dfs = deserialize_dfs(pickled_dfs)

        print("DataFrames loaded from the database!")
        analyzed_spend = analyze_spend(tenantID, userID, sessionID, llm, socketio, client_id, loaded_dfs, saved_corpus)
        
        # Log activity: Completed comprehensive spend analysis
        detailed_activity(
            activity_name="spend_analysis_completion",
            activity_description="User confirmed expense categories. Tango generated comprehensive spend analysis with cost optimization strategies, savings potential calculations, and actionable recommendations across all IT spend categories.",
            user_id=userID
        )
        
        uijson = ui_json(sessionID)
        
        # Fetch raw uploaded files for activity log (same logic as categorize.py)
        raw_data_sample = "No data available"
        data_truncated = False
        
        try:
            # Find the uploaded_files integration (same as categorize.py)
            uploaded_files_api = None
            for integration in integrations:
                if integration.name == "uploaded_files":
                    uploaded_files_api = integration
                    break
            
            if uploaded_files_api:
                files = uploaded_files_api.fetchCurrentSessionUploadedFiles('SPEND_SOURCES', retries=3)
                
                if files:
                    sample_tables = []
                    total_rows = 0
                    max_rows = 50  # Limit total rows across all files
                    
                    for file_id, file_name in files.items():
                        try:
                            # Download file as DataFrame (same as categorize.py)
                            df_dict = S3Service().download_file_as_pd(file_id)
                            
                            for sheet_name, df in df_dict.items():
                                if df is not None and not df.empty:
                                    # Take sample of rows from this sheet
                                    rows_to_take = min(10, len(df), max_rows - total_rows)
                                    if rows_to_take > 0:
                                        sample_df = df.head(rows_to_take)
                                        
                                        # Convert to markdown table
                                        table_md = f"\n**{file_name} - {sheet_name}**\n"
                                        table_md += sample_df.to_markdown(index=False, tablefmt="pipe")
                                        
                                        if len(df) > rows_to_take:
                                            table_md += f"\n*...and {len(df) - rows_to_take} more rows*"
                                            data_truncated = True
                                        
                                        sample_tables.append(table_md)
                                        total_rows += rows_to_take
                                        
                                        if total_rows >= max_rows:
                                            data_truncated = True
                                            break
                            
                            if total_rows >= max_rows:
                                break
                                
                        except Exception as e:
                            print(f"Error processing file {file_name}: {e}")
                            continue
                    
                    if sample_tables:
                        raw_data_sample = "\n".join(sample_tables)
                        if data_truncated:
                            raw_data_sample += "\n\n*Note: Data has been truncated for display purposes. Full dataset was analyzed.*"
                            
        except Exception as e:
            print(f"Error fetching raw data for activity log: {e}")
            raw_data_sample = f"Error extracting data sample: {str(e)}"
        
        # Log full input/output transformation for LLM analysis
        activity_log(
            agent_or_workflow_name="spend_evaluation_complete",
            input_data={
                "user_request": "Comprehensive IT spend analysis",
                "employee_info": industry_employee_info,
                "uploaded_files": "IT spend data files",
                "categories_confirmed": True,
                "raw_spend_uploaded_data": raw_data_sample
            },
            output_data=uijson,
            user_id=userID,
            description="Complete spend analysis transformation: User uploaded IT spend files, Tango categorized expenses, performed comprehensive analysis with cost optimization strategies, savings calculations, and generated actionable recommendations across all categories."
        )
        
        TangoDao.insertTangoState(tenantID, userID, 'SPEND_EVALUATION_FINISHED', json.dumps(uijson), sessionID)
        emit_progress(socketio, client_id, uijson)
        return f"Hereanalyzed_spend"
    
    if user_specified_category_to_analyze_further == '':
        return "Using the above data, attempt to analyze the user's question and provide an appropriate response."
    elif user_specified_category_to_analyze_further not in ['data center systems', 'software', 'it services', 'communication services', 'devices']:
        return "The category you specified is not valid. Please specify a valid category."
    else:
        # Log activity: Deep dive into specific spend category
        detailed_activity(
            activity_name="spend_category_deep_dive",
            activity_description=f"User requested detailed analysis of {user_specified_category_to_analyze_further.title()} spend category. Tango provided specialized insights including cost optimization strategies, vendor analysis, and actionable recommendations for this specific category.",
            user_id=userID
        )
        
        # Return appropriate category analysis
        if user_specified_category_to_analyze_further == 'data center systems':
            return f"Using the above data, attempt to analyze the user's question and provide an appropriate response for {user_specified_category_to_analyze_further}. Below is further info for the category: {spend_dcs_eval}"
        elif user_specified_category_to_analyze_further == 'software':
            return f"Using the above data, attempt to analyze the user's question and provide an appropriate response for {user_specified_category_to_analyze_further}. Below is further info for the category: {spend_s_eval}"
        elif user_specified_category_to_analyze_further == 'it services':
            return f"Using the above data, attempt to analyze the user's question and provide an appropriate response for {user_specified_category_to_analyze_further}. Below is further info for the category: {spend_is_eval}"
        elif user_specified_category_to_analyze_further == 'communication services':
            return f"Using the above data, attempt to analyze the user's question and provide an appropriate response for {user_specified_category_to_analyze_further}. Below is further info for the category: {spend_cs_eval}"
        elif user_specified_category_to_analyze_further == 'devices':
            return f"Using the above data, attempt to analyze the user's question and provide an appropriate response for {user_specified_category_to_analyze_further}. Below is further info for the category: {spend_d_eval}"
        
        
SPEND_FUNC = AgentFunction(
    name="spend_evaluation",
    description="""
    Call this function when the user wants to evaluate their spend and receive detailed insights on their spend and where to save money.
    You will still need to call this function after the user confirms their categories as that is an intermediary step.
    If no other functions make sense to be called for this agent, call this function.
    """,
    args=[
        {
            "name": "user_specified_category_to_analyze_further",
            "description": "If the Tango has asked the user if they'd like to analyze a category further, then you can pass the category here. This must be a string of 'data center systems', 'software', 'it services', 'communication services', or 'devices'.",
            "type": "str",
        },
        {
            "name": "industry_employee_info",
            "description": "If in the chat, the user has spoken about their industry or the number of employees in their organization, pass that information here.",
            "type": "str",
        },
        {
            "name": "user_feedback_on_categories_for_their_files",
            "description": "If the user has provided feedback on the categories of their files after Tango has provided categories, pass that information here. You will see this after the Tango gives the user of a breakdown by category and asks for confirmation. copy the feedback and do not summarize, you can reformat it clearer without loss of information.",
            "type": "str",
            "required": "true"
        },
    ],
    return_description="Detailed insights on the user's spend and where they can save money.",
    function=spend_evaluation,
)

SPEND_CANCEL = AgentFunction(
    name="spend_cancel",
    description="""
    If the user is in the middle of doing a spend evaluation and wishes to cancel their progress, call this function.
    """,   
    args = [],
    return_description="Options of what the user can do next",
    function=spend_cancel,
)