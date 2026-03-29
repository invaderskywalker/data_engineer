
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
    
def clean_zero_val_subcategories(data):
    subcategory_breakdown = data.get("sub_category_breakdown", [])
    subcategories = []
    for subcategory in subcategory_breakdown:
        if subcategory.get("current_spend", "0") != "0":
            subcategories.append(subcategory)
    data["sub_category_breakdown"] = subcategories
    return data

categories_descriptions = {
    "data center systems": "spend on cloud providers, on-prem, and colocation",
    "software": "spend on software licenses, subscriptions, and maintenance",
    "it services": "spend on IT services, consulting, and support",
    "communication services": "spend on communication services, including internet, phone, and video conferencing",
    "devices": "spend on devices, including computers, printers, and peripherals",
}

category_short_map = {
    "data center systems": "DCS",
    "software": "S",
    "it services": "IS",
    "communication services": "CS",
    "devices": "D",
}

def get_system_prompt(category):
        return f"""
        You are an intelligent finance agent helping companies optimize their IT expenditures, specifically focusing on {category} ({categories_descriptions[category]}).
    
        Analyze the provided IT expenditure data and structure your response in these five stages:
        
        TITLE: {category} Optimization Strategy
    
        1. SPEND CATEGORIZATION
        - Create a markdown table categorizing spend of various types within {category}
        - Break down each category into relevant sub-categories
        - Include current spend allocation and potential optimization areas
    
        2. DATA INTERPRETATION VALIDATION
        - Clearly state which aspects of IT spend are covered in the provided data
        - Identify any potential gaps in the data
        - Explain your interpretation of the available information
        - Reference specific data sources used in your analysis
    
        3. OPTIMIZATION RECOMMENDATIONS
        - For each category and sub-category:
            * Identify specific cost reduction levers
            * List required information to assess savings potential
            * Provide benchmark comparisons where possible
        - Include vendor management opportunities:
            * Vendor consolidation potential
            * Pricing optimization strategies
            * Delivery model improvements
            * Contract structure recommendations
    
        4. PRIORITIZATION FRAMEWORK
        - Classify each savings opportunity by:
            * Ease of implementation (Easy/Medium/Hard)
            * Time to realize savings
            * Potential impact
            * Implementation risks
        - Consider factors like:
            * Technology dependencies
            * Geographical considerations
            * Run vs. Transform split
            * Effort allocation for repeatable work
    
        5. ACTION PLAN
        - Convert opportunities into specific project plans
        - Include discovery processes for vendor alternatives
        - Outline specific next steps and timelines
        - Define key metrics for tracking success
        
        6. POTENTIAL SAVINGS
        - For all of knowledge from this data and analysis of data. please list out the potenatial savings with numerical reasoning.
    
        Use specific examples from the provided financial sheets and internal data, citing projects and portfolios where relevant. Cite the Trmeric projects / portfolios that you use as well.

        Furthermore, don't make any outright numerical claims - discuss more patern level information. Additionally, be very concise about your responses.
    """
    
def get_ui_prompt(category):
    return f"""
    You have been provided with some data about a company's IT spend. The data is broken down into five categories: Data Center Systems, Software, IT Services, Communication Services, and Devices. 
    Your task is to analyze the data and provide recommendations for optimizing spend in each category. Right now, you are taking a look at the data in the {category} category.

    Your job is to return a json using just this information in the following format:

    IMPORTANT: ANY SUB-CATEGORY YOU MENTION HERE SHOULD BE AN OBVIOUS SUB-CATEGORY OF THE CATEGORY YOU ARE ANALYZING. FOR EXAMPLE, IF YOU ARE ANALYZING THE DEVICES CATEGORY, YOU MIGHT HAVE APPLE, DELL, ETC. AS SUB-CATEGORIES.
    YOUR CATEGORY IS {category}. DO NOT ADD ANY SUB-CATEGORIES THAT ARE NOT OBVIOUSLY PART OF THIS CATEGORY.
    
    If your total spend is 0, most of what you send should be null/zero.
    
    IMPORTANT: Your sub-categories MUST NOT OVERLAP, and their sum should ideally equal the sum of the total spend for the whole category.
    For deciding your sub-categoires pay close attention to the table-given data. Do not feel the need to include more sub-categories than necessary.

    ```json
    {{
        "category": "{category}",
        "current_spend": <string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>,
        "category_sub_heading": "<string of the sub-heading for the category: should be relevant pieces of the spend in this category, For the devices category, you may have Apple, Dell, etc.. if it is in the user's spend.>",
        "category_insights": ["<string of the insight 1>", "<string of the insight 2>", ...],
        "bar_chart_sorted_data": [
            {{
                "sub_category": "<A sub-category within {category}> ",
                "spend_amount": "string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol"
            }},...
        ],  
        "sub_category_breakdown": [
            {{
                "sub_category": "<The name of sub-category within {category} for which the following action is to be applied.>",
                "current_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>",
                "action": "<string of the name for action to take for this sub-category's spend optimization>",
                "my_todo_actions_based_on_numerical_assesment": "<string of the causes and details for this sub-category's spend optimization. Please include numerical data and reasoning.>",
                "impact": "<string of only either: High, Medium, Low>",
                "effort": "<string of only either: High, Medium, Low>",
            }},...
        ],         
    }}
    ```
    """


def prepare_ui_json_per_category(llm, sessionID, tenantID, userID, category, response_data, initial_data):
    UserMessage = f"""
    Here is the data that has been analyzed and put together for the category {category}:
    {response_data}.
    
    If you must reference anything more in depth, you can look here for more specific numerical data:
    {initial_data}
    """
    systemPrompt = get_ui_prompt(category)
    # print(UserMessage)
    response = llm.run(
        ChatCompletion(system=systemPrompt, prev=[], user=UserMessage), 
        ModelOptions(model="gpt-4o-mini", max_tokens=5000, temperature=0.3), 
        "analyze_spend_per_category_ui"
    )
    # print(response)
    response = extract_json_after_llm(response)
    response = clean_zero_val_subcategories(response)
    TangoDao.insertTangoState(tenantID, userID, f'SPEND_STORED_{category_short_map[category]}_UI', json.dumps(response), sessionID)

def analyze_per_category(
        llm,
        internal_data,
        file_data,
        category, 
        tenantID, 
        userID, 
        sessionID
) -> str:
    # UserMessage = f"""

    # Here is the internal data that you have access to. This will talk about project spend by various categories.
    # {internal_data}
    UserMessage = f"""
    
    Here is some helpful data analysis that you should reference:
    
    {internal_data}


    Don't try to make too complex calculations. Most importantly, don't be vague. Don't just say vague advice. Actually link the advice you provide / patterns you see to specific items that you see in the data. For example, don't just say 'compare cloud provider costs' - say for X, Y, Z projects, see if you can consolidate the cloud provider they use and then negotiate for a bulk discount. Rember, most importantly, link your advice to specific items/updates/projects/categories/portfolios in the data (internal or external)
    Focus and compare to industry standards and best practices.
    """

    systemPrompt = get_system_prompt(category)

    response = llm.run(
        ChatCompletion(system=systemPrompt, prev=[], user=UserMessage), 
        ModelOptions(model="gpt-4o-mini", max_tokens=10000, temperature=0.3), 
        "analyze_spend_per_category",
        memory=userID,
        web=True,
        web_user = True
    )

    TangoDao.insertTangoState(tenantID, userID, f'SPEND_STORED_{category_short_map[category]}_EVAL', response, sessionID)
    prepare_ui_json_per_category(llm, sessionID, tenantID, userID, category, response, UserMessage)
    return response

    
