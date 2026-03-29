import pandas as pd
from src.trmeric_services.agents.functions.onboarding.prompts.CapacityPrompt import detectHeaderRowPrompt
from src.trmeric_utils.json_parser import extract_json_after_llm

def detect_header_row(df, required_columns,llm,model_opts,logInfo):
    """
    Detects the first row in a DataFrame that contains column headers.
    """
    # print("--debug in detect_header_row", df, required_columns)
    prompt = detectHeaderRowPrompt(df,required_columns)
    response = llm.run(prompt, model_opts, 'agent::onboarding_capacity::header_row', logInfo)
    print("--debug response", response)

    headerRow = extract_json_after_llm(response)
    return headerRow["header_row"]

def clean_dataframe(df, required_columns,llm,model_opts,logInfo):
    """
    Loads an Excel file, detects the header row dynamically, and extracts a clean DataFrame.
    """
    # Detect the actual header row
    # print("--debug in clean_dataframe", df)
    header_row = detect_header_row(df, required_columns,llm,model_opts,logInfo)

    # print("--debug headerrow", header_row)
    if header_row is None:
        print("No valid header row found!")
        return df

    # Set the detected row as the header
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)  # Drop rows above header

    # Drop fully empty columns if any
    df = df.dropna(how="all", axis=1)

    return df
