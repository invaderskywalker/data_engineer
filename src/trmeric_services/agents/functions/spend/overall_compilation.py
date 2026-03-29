
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.json_parser import extract_json_after_llm
import json

SYSTEM_PROMPT = f"""
You are an intelligent finance agent seeking to help a company intelligently analyze their IT expenditures. 

You are going to recieve analysis on their spend across the following categories:
    1. data center systems
    2. software
    3. it services
    4. communication services
    5. devices

Each of the analysis will include specific projects and trends and risks. Your job will be to analyze the data and provide insights that can help the company make informed decisions about their IT expenditures.

Provide an overall table, then summary, then chart about this company's IT spend. Provide overall risks and trends, and opportunities for consolidation and optimization.

Be specific about the projects/cateogires/providers/etc and trends that you see.
"""

SYSTEM_PROMPT_UI = """
You are an intelligent finance agent seeking to help a company intelligently analyze their IT expenditures.

You are going to recieve analysis on their spend across the following categories:
    1. data center systems
    2. software
    3. it services
    4. communication services
    5. devices

In the sections for summary, be detailed and specific. It might be easy to just provide super meta level thinking, but try to be specific about the projects/cateogires/providers/etc and trends that you see. Be specific, mentioning projects, categories, providers, etc. Also, mention how those summaries connect to overalls spend trends if possible. 

A detailed compilation of this analysis is provided to you. Your job is to analyze the data and fill it into and return the following json:
Even if the section asks for 1/2 sentences, don't be afraid to be very detailed. You can copy word for word the best strong insights from the data you are provided.
As long as it is backed, provide good numerical data in your sentences with reasoning, take a next step and provide a strong insight.
```json
{
    "tango_insights":{
        "cost_distribution": [
            <string of insight 1 ~ 2 sentences>,
            <string of insight 1 ~ 2 sentences>,
            ...
        ],
        "savings_potential": [
            <string of insight 1 ~ 2 sentences>,
            <string of insight 1 ~ 2 sentences>,
            ...
        ],
        "trend_analysis": [
            <string of insight 1 ~ 2 sentences>,
            <string of insight 1 ~ 2 sentences>,
            ...
        ],
        "efficiency_gaps": [
            <string of insight 1 ~ 2 sentences>,
            <string of insight 1 ~ 2 sentences>,
            ...
        ],
    }
    "overall_summary": {
        "total_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>",
        "savings_potential": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>",
        "year_to_year_change": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>",
    },
    "executive_summary": {
        "sheet_summary": "<string of sheet summary>",
        "chart_data": [
            {
                "category": "data center systems",
                "actual_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>"
            },
            {
                "category": "software",
                "actual_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>"
            },
            {
                "category": "it services",
                "actual_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>"
            },
            {
                "category": "communication services",
                "actual_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>"
            },
            {
                "category": "devices",
                "actual_spend": "<string of the integer amount. If there is no possible data, use "0". Do not include the currency symbol>"
            }
        ],
        "insights": [
            "<string of insight 3 ~ 4 sentences - this should be backed by specific examples and if possible, some data (at least 1 one of these bullets should have data. avoid generalized statements - cite projects, portfolios, suppliers, vendors, etc when applicable. >",
            "<string of insight 3 ~ 4 sentences>",
            "<string of insight 3 ~ 4 sentences>",
        ]
    },
    "currency": "<string of currency, can be INR, USD, or empty string>"
}

```
"""

def prepare_ui_json_compiled(llm, sessionID, tenantID, userID, response, per_category):
    UserMessage = f"""
    Here is the data that was created during the overall compilation:

    {response}

    And here is the data that was created during the per category compilation:
    {per_category}
    
    Focus and compare to industry standards and best practices.
    """

    response = llm.run(
        ChatCompletion(system=SYSTEM_PROMPT_UI, prev=[], user=UserMessage), 
        ModelOptions(model="gpt-4o-mini", max_tokens=10000, temperature=0.3), 
        "analyze_spend_per_category_ui"
    )

    response = extract_json_after_llm(response)
    TangoDao.insertTangoState(tenantID, userID, f'SPEND_STORED_EVALUATION_UI', json.dumps(response), sessionID)

def analyze_overall_spend(
        llm,
        compiled_category_analysis,
        sessionID,
        tenantID,
        userID
) -> str:
    response = llm.run(
        ChatCompletion(system=SYSTEM_PROMPT, prev=[], user=compiled_category_analysis), 
        ModelOptions(model="gpt-4o-mini", max_tokens=14000, temperature=0.3), 
        "analyze_overall_spend",
        memory=userID,
        web=True,
        web_user = True
    )

    prepare_ui_json_compiled(llm, sessionID, tenantID, userID, response, compiled_category_analysis)

    return response
    