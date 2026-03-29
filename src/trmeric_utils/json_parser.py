import json
import re
from src.trmeric_api.logging.AppLogger import appLogger
from collections import OrderedDict
import traceback
import numpy as np

def extract_json_data(text):
    # Regular expression to find the SQL query between ```sql and ```
    # pattern = r"```json\n(.*?)\n```"
    # pattern = r"```(?:json)?\n(.*?)\n```"
    pattern = r"```json\n([\s\S]*?)\n```"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1)
    else:
        return ""



def extract_json_v2(text):
    # This function extracts text between triple backticks
    pattern = r"```(.*?)```"
    
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    # match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        return json_str
    return ""


def clean_json_string(json_str):
    """Clean up the JSON string without breaking valid apostrophes."""
    if not json_str or not isinstance(json_str, str):
        return "{}"
    # Replace Python-specific values
    json_str = json_str.replace("None", "null").replace("True", "true").replace("False", "false")
    # Remove comments
    json_str = re.sub(r'(?<!:)//(?!/).*?(?=\n|$)', '', json_str)
    # Strip BOM and control characters
    json_str = json_str.encode().decode('utf-8-sig', errors='ignore').strip('\x00\r\n\t ')
    # Don’t mess with quotes yet; let json.loads handle it

    # Normalize control characters (THIS FIXES YOUR ERROR)
    json_str = json_str.replace("\r", "").replace("\n", "\\n").replace("\t", "\\t")
    return json_str

# def clean_json_string(json_str):
#     """Remove comments and clean up the JSON string."""
    
    
#     if not json_str:
#         return "{}"
    
#     json_str = json_str.replace("None", "null").replace("True", "true").replace("False", "false")
#     json_str = re.sub(r"(?<!\\)'", '"', json_str)  # Replace unescaped single quotes
#     json_str = re.sub(r'(?<!:)//(?!/).*?(?=\n|$)', '', json_str)  # Remove comments
#     # Remove BOM and control characters
#     json_str = json_str.encode().decode('utf-8-sig', errors='ignore').strip('\x00\r\n\t ')
#     return json_str

    # json_str = json_str.replace("None", "null").replace("True", "true").replace("False", "false")
    # # json_str = json_str.replace(null, "null")
    # json_str = re.sub(r"(?<!\\)'", '"', json_str)  # Replace unescaped single quotes
    # cleaned_str = re.sub(r'(?<!:)//(?!/).*?(?=\n|$)', '', json_str)  # Remove comments
    # return cleaned_str.strip()
    # # Remove single-line comments starting with '//' until the end of the line
    # # cleaned_str = re.sub(r'//.*', '', json_str)
    # # Remove only comments (lines starting with //)
    # # cleaned_str = re.sub(r'(?m)^\s*//.*\n?', '', json_str)
    # # cleaned_str = re.sub(r'//.*', '', json_str)
    # json_str = json_str.replace("None", "null")
    # json_str = json_str.replace("True", "true")
    # json_str = json_str.replace("False", "false")
    # json_str = re.sub(r"(?<!\\)'", '"', json_str)
    # # json_str = json_str.replace('"', '\\"')

    # cleaned_str = re.sub(r'(?<!:)//(?!/).*?(?=\n|$)', '', json_str)
    # return cleaned_str

def extract_json_after_llm(output_,step_sender=None):
    output = {}
    try:
        try:
            return json.loads(output_)
        except Exception as e:
            temp = extract_json_data_v2(output_)
            # print("--debug temp pre-process", temp)
            if temp and temp != "No json found.":
                temp = clean_json_string(temp)
                temp = re.sub(r'\s+', ' ', temp)  # Collapse whitespace
                # temp = temp.replace('\n', ' ').replace('\r', '')
                # print("--debug temp inside: ",temp)
                output = json.loads(temp)
                # print("--debug extractJSON llm", output)
                return output
            output = json.loads(temp)
    except Exception as e1:
        appLogger.error({
            "function": "extract_json_after_llm_1",
            "error": e1,
            "string": output_,
            "traceback": traceback.format_exc()
        })
        try:
            extract_json = extract_json_v2(output_)
            output = json.loads(extract_json)
        except Exception as e:
            print("error in extractLLM", e)
            appLogger.error({
                "function": "extract_json_after_llm",
                "error": e,
                "string": output_,
                "traceback": traceback.format_exc()
            })
            if step_sender:
                step_sender.sendError(key="Error Parsing JSON")
            
    return output



def fetch_value_from_json_array(data, key):
    try:
        for d in data:
            if d["title"] == key:
                print("value found in fetch_value_from_json_array ",
                      d["value"])
                return d["value"]
        raise f"key: %s not found in data"
    except Exception as e:
        appLogger.error({"event": "fetch_value_from_json_array", "error": e})
        raise e


def extract_json_data_v2(content):
    """
    Extract the JSON object from a given string content.

    Parameters:
    content (str): The string content containing the JSON object.

    Returns:
    str: The extracted JSON object as a string.

    Raises:
    ValueError: If no JSON object is found in the content.
    """
    # Use regular expression to extract the JSON part from the content
    # match = re.search(r'\{.*\}', content, re.DOTALL)
    # match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
    match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
    # pattern = r'\{(?:[^{}]|\{[^{}]*\})*\}|\[(?:[^[\]]|\[[^[\]]*\])*\]'
    # match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0)
    else:
        raise ValueError("No JSON object found in the content")


def save_as_json(data, filename):
    try:
        with open(filename, 'w', encoding= 'utf-8') as file:
            json.dump(data, file, indent=4, default=str)
        print(f"--debug Data successfully saved to {filename}")
    except Exception as e:
        print(f"--debug Error writing to file {filename}: {e}")
        appLogger.error({"event": "save_as_json", "error": str(e), "traceback": traceback.format_exc()})



def clean_for_json(obj):
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (dict, list)):
        return json.loads(json.dumps(obj, default=lambda x: float(x) if isinstance(x, np.floating) else int(x) if isinstance(x, np.integer) else x))
    return obj


# def convert_uuids_to_str(obj):
#     if isinstance(obj, dict):
#         return {k: convert_uuids(v) for k, v in obj.items()}
#     elif isinstance(obj, list):
#         return [convert_uuids(item) for item in obj]
#     elif isinstance(obj, uuid.UUID):  # Check for UUID type
#         return str(obj)
#     return obj