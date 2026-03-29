from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
from typing import Optional, Dict, Any

def getWinThemePrompt(
    providerData, description, winTheme, customerData
) -> ChatCompletion:
    """
    This function return gets the prompt for retrieving the win themes for a said provider.

    Args:
    - providerData: The data of the provider
    - description: The description of the opportunity
    """
    
    print("debug ------", winTheme, customerData)

    prompt = f"""
    A provider of tech-services is provided with an opportunity. The description of said opportunity is as follows:
    {description}
    
    The provider has also provided some of his data of service catalog, capabilities, and case studies data as follows:
        <provider_data>
        {providerData}
        <provider_data>
        
    The provider has a list of win themes right now
    <provider_current_win_themes>
        {winTheme}
    <provider_current_win_themes>
    You need to look into this list provided in 
    <provider_current_win_themes> and enhance each rough win theme further \
    and also add additional win themes that you think are important
        
    
    Your task is to find win themes for the provider to crack the opportunity provided by the customer: 
    <customerData>{customerData}<customerData>

    So you need to create a context of the requirements, area of work of the customer so that you can target those areas while constructing win themes.
    
    When building the win theme focus on these five key dimensions to construct win themes. :
    1. Customer-Centric Value Proposition
    2. Differentiation and Unique Value
    3. Alignment with Customer's Strategic Vision
    4. Risk Mitigation and Reliability
    5. Compelling Value-for-Money Proposition
            
    Ouput format - JSON
    ```json
        {{
            win_themes: [] // list of string
        }}
    ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def getWinStrategyPrompt(
    providerData, description, winTheme, win_strategy, customerData
) -> ChatCompletion:
    """
    This function return gets the prompt for retrieving the win strategy for a said provider.

    Args:
    - providerData: The data of the provider
    - description: The description of the opportunity
    - winTheme: The win theme of the opportunity
    - outputFormat: The format of the output
    """

    prompt = f"""
    A provider of tech-services is provided with an opportunity. The description of said opportunity is as follows:
    {description}
    
    The provider has also provided some of his data of service catalog, capabilities, and case studies data as follows:
    <provider_data>
    {providerData}
    <provider_data>
    
    <win_theme>
    {winTheme}
    <win_theme>
    
    
    <rough_win_strategy_written_by_provider>
    {win_strategy}
    <rough_win_strategy_written_by_provider>

    
    Your task is to consider the input provided in <rough_win_strategy_written_by_provider> and include these points when you build
    the win strategy for the provider to crack the opportunity provided by the customer: 
    <customerData>{customerData}<customerData>

    So you need to create a context of the requirements, area of work of the customer so that you can target those areas while constructing win strategy.
    
    When building the win strategy focus on these five key dimensions to construct win strategy based on the <provider_data>:
    1. Customer-Centric Value Proposition
    2. Differentiation and Unique Value
    3. Alignment with Customer's Strategic Vision
    4. Risk Mitigation and Reliability
    5. Compelling Value-for-Money Proposition
            
    Ouput format - JSON
    ```json
        {{
            win_strategy: "", //  in markdown format with separation on dimensions with bullets 
        }}
    ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )




# def getBBDBTextEnhancementPrompt(
#     text, category
# ) -> ChatCompletion:
#     system_prompt = """
#     Hi, you are AN text enhancer for a company called Trmeric.
#     Trmeric is a company where it manages customers projects, roadmaps ideas etc and help manage the projects.
#     Trmeric also manages the providers/partners profile and also their work
    
#     Your job:
#     is just to enahnce the text provided by the providers/partners while they create their profile.
    
#     """
#     user_prompt = f"""
#     User is trying to update section: {category} in his profile.
    
#     and he has already written: {text}.
    
#     Please enhance it and always output JSON:
#     ```json
#     {{
#         "{category}": "",
#     }}
#     ```
#     """

#     return ChatCompletion(
#         system=system_prompt,
#         prev=[],
#         user=user_prompt
#     )



# def call_quantum_assist_prompt(category,text,quantum_context):
#     match category:
#         case "core_capabilities":
#             return getBBDBTextEnhancementPrompt
#         case "industry_footprint:
#             return dfs
#         case "service_catalog":
#             return getBBDBTextEnhancemene
#         case "voice_of_customer":
#             return getBBDBTextEnhance
#         case "offers":
#             return getBBDBTextEnhance
#         case "info_security":
#             return sfsf
#         case _:
#             return None
            
            
def get_quantum_assist_prompt(category, text, quantum_context) -> ChatCompletion:
    """
        Generates a ChatCompletion prompt for enhancing or generating content based on the specified category.
    """
    # Check if the category exists in the data
    if category not in CATEGORY_DATA:
        return None

    # Retrieve category-specific data
    data = CATEGORY_DATA[category]
    specific_instructions = data["instructions"]
    json_format = data["json_format"]

    # Construct the system prompt with category-specific instructions
    system_prompt = f"""
        You are a an assist agent playing role of enhancer/generator for Trmeric, a platform managing provider profiles,projects and roadmaps.
        This is the provider's data used in the onboarding flow which includes:
            - Company's Website Scrapped data
            - Social media data
            - Uploaded docs data
            
        **QUANTUM CONTEXT** {quantum_context}
        
        **TASK**: Your task is to enhance or generate content for the "{category}" section using input Quantum context 
        and user provided inputs text i.e. \n{text}
        
        **OUTPUT FORMAT**: Strictly render in below json format:
        ```json
        {json_format}
        ```
        
        **INSTRUCTIONS**:
         - {specific_instructions}
    """
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=""
    )



# Define category-specific instructions and JSON output formats
CATEGORY_DATA = {
    
    "company_intro": {
        "instructions": "Enhance or generate content for the company introduction.",
        "json_format": f"""
            {{
                "company_introduction": "<descriptive text introducing company>"
            }}
        """
    },
    
    "current_capability": {
        "instructions": "Enhance or generate content for Identify existing services, products, or expertise mentioned. Rank them (1 to n) based on prominence.",
        "json_format": f"""
            {{
                "current_capabilities": [
                    {{
                        "text": "<capability_name>",
                        "description": "",
                        "rank": <integer>
                    }}...
                ]
            }}
        """
    },
    
    "future_capability": {
        "instructions": "Enhance or generate content for planned or prospective capabilities from strategic plans in the forward-looking statements in `website_content`. Estimate `duration_count` and `duration_type` (year between 2025-2050) based on timelines or goals in the data. If unavailable, use industry trends to suggest plausible future capabilities.",
        "json_format": f"""
            {{
                "future_capabilities": [
                    {{
                        "text": "<capability_name>",
                        "description": "<capability_description>",
                        "rank": <integer>,
                        "duration_count": <integer>,
                        "duration_type": <year in range 2025-2050>
                    }}
                ]
            }}
        """
    },
    
    "offers_promotion": {
        "instructions": "Enhance or generate content for promotional strategies, providing concise marketing approaches.",
        "json_format": f"""
            {{
                "promotional_strategies": "<20-50 word marketing approach>",
            }}
        """
    },
    "offers_future":{
        "instructions": "Enhance or generate content for company's future offers, providing future offer ideas.",
        "json_format": f"""
            {{
                "offers_of_future": "<20-50 word description of 1-2 future offer ideas>"
            }}
        """
    },
    
    "service_catalog": {
        "instructions": "Enhance or generate content for the service catalog, focusing on tools, accelerators, and their descriptions.",
        "json_format": f"""
            {{
                "tools_and_accelerators": [
                    {{
                        "name": "<tool or accelerator name>",
                        "description": "<brief description>",
                        "type": "<Accelerator|Tool|Solution|Service>",
                        "benefit": "<key benefit>"
                    }}...
                ]
            }}
        """
    },
    
    # "industry_footprint": {
    #     "instructions": "Enhance or generate content for the industry footprint, detailing industries served and their domains.",
    #     "json_format": f"""
    #         {{
    #             "industries": [
    #                 {{
    #                     "industry_name": "<industry name>",
    #                     "domain_name": "<single domain name for above industry>",
    #                     "weight": <integer, 0-100>,
    #                     "current_customer_count": <integer>
    #                 }}
    #             ]
    #         }}
    #     """
    # },
    
    "customer_current_desc": {
        "instructions": "Enhance or generate content for the voice of customer section, including current aspirations.",
        "json_format": f"""
            {{
                "customer_desc": "<a descriptive text on current customer perception of the company>"
            }}
        """
    },
    "customer_future_desc": {
        "instructions": "Enhance or generate content for the voice of customer section, including future aspirations.",
        "json_format": f"""
            {{
                "customer_desc_future": "<a descriptive text on future aspirations about the customers>"
            }}
        """
    },
    
    "current_privacy": {
        "instructions": "Enhance or generate content for information security, focusing on current privacy policies and security practices.",
        "json_format": f"""
            {{
                "current_data_privacy_protocols": "<detailed description>"
            }}
        """
    },
    "future_privacy": {
        "instructions": "Enhance or generate content for information security, what to focus on privacy policies and security practices.",
        "json_format": f"""
            {{
                "future_data_privacy_protocols": "<detailed description>"
            }}
        """
    },
    "quality_management": {
        "instructions":"Enhance or generate the quality management practices (20-50 words) (e.g., quality assurance policies)",
        "json_format": f"""
            {{
                "quality_management" : ""
            }}
        """
    },
    "risk_management": {
        "instructions":"Enhance or generate the  risk management approaches (e.g., risk frameworks)",
        "json_format": f"""
            {{
                "risk_management": ""
            }}
        """
    }
}

















# # Define category-specific instructions and JSON output formats
# CATEGORY_DATA = {
    
#     "description": {
#         "instructions": "Enhance or generate content for the company introduction.",
#         "json_format": f"""
#             {{
#                 "company_introduction": "<descriptive text introducing company>"
#             }}
#         """
#     },
    
#     "current_capability": {
#         "instructions": "Enhance or generate content for Identify existing services, products, or expertise mentioned. Rank them (1 to n) based on prominence.",
#         "json_format": f"""
#             {{
#                 "current_capabilities": [
#                     {{
#                         "text": "<capability_name>",
#                         "description": "",
#                         "rank": <integer>
#                     }}...
#                 ]
#             }}
#         """
#     },
    
#     "future_capability": {
#         "instructions": "Enhance or generate content for planned or prospective capabilities from strategic plans in the forward-looking statements in `website_content`. Estimate `duration_count` and `duration_type` (year between 2025-2050) based on timelines or goals in the data. If unavailable, use industry trends to suggest plausible future capabilities.",
#         "json_format": f"""
#             {{
#                 "future_capabilities": [
#                     {{
#                         "text": "<capability_name>",
#                         "description": "<capability_description>",
#                         "rank": <integer>,
#                         "duration_count": <integer>,
#                         "duration_type": "<year in range 2025-2050>"
#                     }}
#                 ]
#             }}
#         """
#     },
    
#     "offers": {
#         "instructions": "Enhance or generate content for promotional strategies and future offers, providing concise marketing approaches and future offer ideas.",
#         "json_format": f"""
#             {{
#                 "promotional_strategies": "<20-50 word marketing approach>",
#             }}
#         """
#     },
#     "offers_future":{
#         "instructions": "Enhance or generate content for promotional strategies and future offers, providing concise marketing approaches and future offer ideas.",
#         "json_format": f"""
#             {{
#                 "offers_of_future": "<20-50 word description of 1-2 future offer ideas>"
#             }}
#         """
#     },
    
#     "service_catalog": {
#         "instructions": "Enhance or generate content for the service catalog, focusing on tools, accelerators, and their descriptions.",
#         "json_format": f"""
#             {{
#                 "tools_and_accelerators": [
#                     {{
#                         "name": "<tool or accelerator name>",
#                         "description": "<brief description>",
#                         "type": "<Accelerator|Tool|Solution|Service>",
#                         "benefit": "<key benefit>"
#                     }}...
#                 ]
#             }}
#         """
#     },
    
#     "industry_footprint": {
#         "instructions": "Enhance or generate content for the industry footprint, detailing industries served and their domains.",
#         "json_format": f"""
#             {{
#                 "industries": [
#                     {{
#                         "industry_name": "<industry name>",
#                         "domain_name": "<single domain name for above industry>",
#                         "weight": <integer, 0-100>,
#                         "current_customer_count": <integer>
#                     }}
#                 ]
#             }}
#         """
#     },
    
#     "customer_current_desc": {
#         "instructions": "Enhance or generate content for the voice of customer section, including current  aspirations.",
#         "json_format": f"""
#             {{
#                 "customer_desc": "<a descriptive text on current customer perception of the company>"
#             }}
#         """
#     },
#     "customer_future_desc": {
#         "instructions": "Enhance or generate content for the voice of customer section, including future aspirations.",
#         "json_format": f"""
#             {{
#                 "customer_desc_future": "<a descriptive text on future aspirations about the customers>"
#             }}
#         """
#     },
    
#     "info_security": {
#         "instructions": "Enhance or generate content for information security, focusing on privacy policies and security practices.",
#         "json_format": f"""
#             {{
#                 "current_data_privacy_protocols": "<detailed description>",
#                 "future_data_privacy_protocols": "<detailed description>"
#             }}
#         """
#     },
#     "future_privacy": {
#         "instructions": "Enhance or generate content for information security, focusing on privacy policies and security practices.",
#         "json_format": f"""
#             {{
#                 "future_data_privacy_protocols": "<detailed description>"
#             }}
#         """
#     },
#     "ways_of_working": {
#         "instructions":- "Enhance or generate the quality management practices (20-50 words) (e.g., quality assurance policies) and risk management approaches",
#         "json_format": f"""
#             {{
#                 "quality_management" : "",
#                 "risk_management": "",
#             }}
#         """
#     }
# }
