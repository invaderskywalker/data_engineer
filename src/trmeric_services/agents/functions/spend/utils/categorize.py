from concurrent.futures import ThreadPoolExecutor, TimeoutError
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.spend.utils.ui_json import start_show_timeline, stop_show_timeline, timeline_event
from src.trmeric_s3.s3 import S3Service
import pandas as pd

categories = ['Software', 'IT Services', 'Communication Services', 'Devices']

def emit_progress(socketio, clientID, message):
    socketio.emit("spend_agent", 
                  message, 
                  room=clientID
                 )

def analyze_categories(df, llm):
    if 'Tango_Category' not in df.columns:
        return " has no categorization done. the data was not categorizable by tango."
    
    distribution = df['Tango_Category'].value_counts(normalize=True) * 100
    distribution = distribution.round(2)
    result = "Category Distribution (%):\n"
    for category, percent in distribution.items():
        result += f"{category}: {percent}%\n"

    system_prompt = """
    You should look at the list of columns and determine which column describes spend data in the IT Sheet. Defer to an invoice total always if it exists.
    Your other task is to determine which column describes the name of what the row of data is representing. The name should be specific, try and find the most descriptive column.
    respond with JSON:
    ```
    {
        "spend_column": "column_name",
        "name_column": "column_name"
    }
    ```
    """
    
    response = llm.run(
        ChatCompletion(system=system_prompt, prev=[], user=f"Here are the columns of the IT Expense Sheet:\n {df.columns}\n . Here is what the top few rows look like: \n{df.head()}.\n"), 
        ModelOptions(model="gpt-4o-mini", max_tokens=100, temperature=0), 
        "spend_per_category_find_column_names",
        memory = False,
        web = False
    )
    
    response = extract_json_after_llm(response)
    spend_column = response.get('spend_column', 'N/A')
    name_column = response.get('name_column', 'N/A')
    
    if spend_column in df.columns and name_column in df.columns:
        for category in df['Tango_Category'].dropna().unique():
            category_df = df[df['Tango_Category'] == category]
            top_rows = category_df.sort_values(by=spend_column, ascending=False).head(3)
            names = top_rows[name_column].tolist()
            result += f"\nTop 3 spend rows for category '{category}': {names}\n"
            
    if spend_column in df.columns:
        # Ensure the spend column is numeric for aggregation
        df[spend_column] = pd.to_numeric(df[spend_column], errors='coerce')
        total_spend = df.groupby('Tango_Category')[spend_column].sum().round(2)
        result += "\nTotal Spend per Category:\n"
        for category, spend in total_spend.items():
            result += f"{category}: {spend}\n"
            
    print(result)
    return result

def create_categories(integrations, llm, socketio, clientID, industry_employee_info, feedback, **kwargs):
    emit_progress(socketio, clientID, start_show_timeline())
    emit_progress(socketio, clientID, timeline_event("Retrieving your files", "file_retrieval", False))
    emit_progress(socketio, clientID, timeline_event("Categorizing your data", "data_categorization", False))    
    
    for integration in integrations:
        print(integration.name)
        if integration.name == "uploaded_files":
            api = integration
            break
    files = api.fetchCurrentSessionUploadedFiles('SPEND_SOURCES', retries = 3)
    print(files)    
    if len(files) == 0:
        emit_progress(socketio, clientID, stop_show_timeline())
        raise Exception("No files found")
    
    emit_progress(socketio, clientID, timeline_event("Retrieving your files", "file_retrieval", True))
            
    if industry_employee_info:
        saved_corpus = f"Information about company industry/number of employees: {industry_employee_info}\n\n"
    saved_corpus = "--START OF UPLOADED FILE DATA---\n\n"
    
    dfs = {}
    for file_id, file_name in files.items():
        saved_corpus += f"This is the data that was retrived from the uploaded file: {file_name}:\n"
        data = S3Service().download_file_as_text(file_id)
        try:
            df = S3Service().download_file_as_pd(file_id)
            categorized_dict = {}
            for key, val in df.items():
                categorized_dict[key] = categorize_df(val, llm, feedback)
            dfs[file_name] = df  # Store DataFrame with its file name as the key
        except Exception as e:
            print(f"Error downloading or processing file {file_name}: {e}")
            continue
        saved_corpus += data
    saved_corpus += "--END OF UPLOADED FILE DATA --- \n\n"
    
    analysis_results = {}
    for file_name, sheets in dfs.items():
        analysis_results[file_name] = {}
        for sheet_name, df in sheets.items():
            result = analyze_categories(df, llm)
            analysis_results[file_name][sheet_name] = result
            print(f"Category analysis for {file_name} - {sheet_name}:\n{result}")
            
    emit_progress(socketio, clientID, timeline_event("Categorizing your data", "data_categorization", True))
    emit_progress(socketio, clientID, stop_show_timeline())    
    
    return dfs, saved_corpus, analysis_results

def process_chunk(chunk, columns, categorize_system, llm):
    """Process an individual chunk of data with error handling and retry on output size mismatch."""
    attempt = 0
    while attempt < 2:
        try:
            if columns:
                chunk = chunk[columns]
            
            # Report progress for this chunk
            print(f"Processing a chunk with {len(chunk)} row(s)...")
            chunk_items = "\n __________________ \n ".join([str(row) for _, row in chunk.iterrows()])
            
            cat_response = llm.run(
                ChatCompletion(
                    system=categorize_system,
                    user=f"Categorize these items:\n{chunk_items}. Your output array should have length {len(chunk)}",
                    prev=[],
                ),
                ModelOptions(model="gpt-4o-mini", max_tokens=300, temperature=0.0),
                "categorize_chunk",
                memory = False,
                web = False
            )
            cat_data = extract_json_after_llm(cat_response)
            
            # Ensure the length of categories matches the chunk
            categories_out = cat_data.get('categories', [])
            if len(categories_out) != len(chunk):
                print(f"Warning: Category length mismatch. Expected {len(chunk)}, got {len(categories_out)}")
                print(f"Categories: {categories_out}")
                print(f"Chunk: {chunk}")
                attempt += 1
                if attempt < 2:
                    print("Retrying...")
                continue  # Retry if sizes don't match
            
            return categories_out
        
        except Exception as e:
            print(f"Error processing chunk: {str(e)}")
            # Return default categories for this chunk so that the overall process can continue.
            return ['N/A'] * len(chunk)

def categorize_df(df, llm, feedback):
    """Main categorization function with parallel processing"""
    user_message = f"Here is the dataframe:\n{df.head().to_markdown(index=False)}"
    
    # Step 1: Initial categorization check
    categorizable_system = f"""Can this IT spend data be categorized into {categories}? 
    Respond with JSON:
    for relevant columns, always keep column names which are like: name, type, category, description, etc...
    Feel free to keep anything that may be remotely helpful.
    {{"can_be_categorized": boolean, "relevant_columns_names_for_categorization": ["column1_name", "column2_name", ...]}}"""
    
    response = llm.run(
        ChatCompletion(system=categorizable_system, prev=[], user=user_message), 
        ModelOptions(model="gpt-4o-mini", max_tokens=200, temperature=0), 
        "analyze_spend_per_category_ui",
        memory = False,
        web = False
    )
    response = extract_json_after_llm(response)
    
    if not response.get('can_be_categorized', False):
        print("Data cannot be categorized. Returning original DataFrame.")
        return df

    print(f"Data can be categorized. Proceeding with categorization columns {response.get('relevant_columns_names_for_categorization', [])}")
    # Step 2: Parallel categorization
    columns = response.get('relevant_columns_names_for_categorization', [])
    categorize_system = f"""Categorize each IT spending item into one of {categories}. 
    Make sure you give a category for every single row provided to you.
    Important Rules:
    1. Categorize Cloud/AWS as Software
    2. Categorize Zoom as Communication Services
    3. Use 'N/A' only when no category matches
    4. Focus on item descriptions for categorization

    Return JSON format:
    {{"categories": ["category1", "category2", ...]}}\n"""
    
    if feedback:
        categorize_system += f"""
        IMPORTANT: Please make changes based on the following user feedback (ALWAYS FOLLOW THE USER FEEDBACK):
        ___BEGIN USER FEEDBACK___
            User Feedback Considerations: {feedback}
        ___END USER FEEDBACK___
        """
        
    print(categorize_system)

    chunk_size = 8
    futures = []
    chunks = []
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all chunks for parallel processing and store the chunks for later use
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i+chunk_size]
            chunks.append(chunk)
            futures.append(
                executor.submit(
                    process_chunk,
                    chunk=chunk,
                    columns=columns,
                    categorize_system=categorize_system,
                    llm=llm,
                )
            )

        # Collect results in original order after all tasks have been submitted.
        row_categories = []
        for chunk, future in zip(chunks, futures):
            try:
                # Attempt to retrieve results with a timeout.
                result = future.result(timeout=30)
            except TimeoutError:
                print(f"Timeout occurred for a chunk with {len(chunk)} row(s)")
                result = ['N/A'] * len(chunk)
            print(f"Processed chunk result length: {len(result)}")
            row_categories.extend(result)

    # Ensure the length of row_categories matches the DataFrame length
    print(f"Expected length: {len(df)}, Actual length: {len(row_categories)}")
    
    if len(row_categories) < len(df):
        row_categories.extend(['N/A'] * (len(df) - len(row_categories)))
    elif len(row_categories) > len(df):
        row_categories = row_categories[:len(df)]

    df['Tango_Category'] = row_categories
    return df
