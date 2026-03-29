import json
import datetime
from typing import List, Dict, Optional
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
from src.trmeric_services.provider.quantum.utils import *

# THOUGHT_PROCESS_INSTRUCTIONS = f"""
#     Say the <key_result> is: Complete the Quantum profile to showcase the company's capabilities and attract potential partners.
#     <key_result_baseline_value>: Current baseline is an incomplete profile with some sections filled (e.g., 'description', 'offers').
    
#     - The agent starts with the baseline form data as provided in the JSON.
#     - The 'planned_value' is a fully completed profile with all sections (Aspiration, Core Capabilities, etc.) populated.
#     - For 'achieved_value', the agent tracks which sections are completed based on user input and updates the JSON dynamically.
#     - Social media links scraped via the SocialMediaScraper are auto-populated into the 'links' field if provided.
#     - The agent guides the user through each section, handling 'single' fields (e.g., description) and 'list' fields (e.g., capabilities) differently.
#     - The agent provides contextual suggestions based on the section and existing data (e.g., suggesting a capability based on 'offers').
#     - The conversation state is saved via TangoDao to persist progress.
# """



def analyze_inputs_prompt(summarized_results: Dict) ->ChatCompletion:
    
    prompt = f"""
        You are Quantum Agent responsible for Onboarding Providers onto Trmeric Platform which is a B2B AI-SaaS company.
        For the given information, you have to check whether all the necessary information has been given by the provider in the input, it should span around
        these sections which will be required to prepare the Quantum Canvas.
        
        ### Relevant Sections for Quantum Canvas
        -Core capabilities
        -Service catalog
        -Industry and Domain
        -Leadership & Team
        -Voice of Customer
        -Offers
        -Case Studies
        -Partnerships
        -Ways of Working
        -Information & Security
        -Certifications & Audit
        
        ###Input Context
        1. ***Website data** : {summarized_results.get("website",None) or None}
        2. ***Social Media Links** : {summarized_results.get("social_media",None) or None}
        3. **Uploaded Documents** : {summarized_results.get("uploaded_docs",None) or None} for business capabilites
        
        ### Task
        You have to analyze the given input context and check it's capability to generate the sections required for Quantum Canvas.
        Then lastly you need to give a brief description of what all things are fetched (mentioning the input sources) and ask one well crafted relevant question from the user
        for the information vital for the onboarding process to generate the Canvas.
        
        
        ### Output format
        ```json
        {{
            "question_to_ask" : "", //A descriptive question in 2-3 lines as per the context provided
            "clarifying_information": "", //Information on what all things are fetched and good to proceed
        }}
        ```
        ### Guidelines
        - Ask the question in relevance to the Input context and which is necessary for the user to provide for the process
        - Give user clarity on what information has been fetched & what else is required i.e. their additional inputs.
    """
    
    
    return ChatCompletion(
        system = prompt,
        prev = [],
        user = ''
    )
    
def call_process_doc_prompt(type):
    print("--debug call_process_doc_prompt----", type)
    match type:
        case "bcp":
            return process_bcp_prompt
        case "case_study":
            return process_case_study_prompt
        case _:
            return None


def call_section_prompt(type):
    print("--debug call_section_prompt----", type)
    match type:
        case "core_capabilities":
            return create_core_capabilities_industrydomain_prompt
        case "service_catalog":
            return create_service_catalog_prompt
        case "information_and_security":
            return create_info_security_prompt
        case "offers":
            return create_offers_prompt
        case "ways_of_working":
            return create_ways_of_working_prompt
        case "case_studies":
            return create_case_studies_prompt
        case "partnerships":
            return create_partnerships_prompt
        case "certifications_and_audit":
            return create_certifications_and_audit_prompt
        case "leadership_and_team":
            return create_leadership_and_team_prompt
        case "voice_of_customer":
            return create_voice_of_customer_prompt
        case _:
            return None

def create_core_capabilities_industrydomain_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with analyzing company data to generate a structured overview of core capabilities for an onboarding flow. Use the provided `company_info` JSON, which includes `website_content`, `social_media_posts`, and `documents`, to extract relevant information. Follow these steps:

        1. **Company Introduction**: Extract a concise introduction (50-100 words) summarizing the company’s mission, history, or purpose from `website_content` (e.g., About Us page) or `documents`. If unavailable, use `social_media_posts` for a brief overview.
        2. **Social Media Links**: Identify active social media profiles (e.g., LinkedIn, Twitter, Instagram) from `social_media_posts` or `website_content`. Include only valid URLs.
        3. **Capabilities**:
            - **Current Capabilities**: Identify existing services, products, or expertise mentioned in `website_content`, `documents`, or `social_media_posts`. Rank them (1 to n) based on prominence (e.g., frequency of mention or emphasis in data).
            - **Future Capabilities**: Identify planned or prospective capabilities from strategic plans in `documents`, roadmap mentions in `social_media_posts`, or forward-looking statements in `website_content`. Estimate `duration_count` and `duration_type` (year between 2025-2050) based on timelines or goals in the data. If unavailable, use industry trends to suggest plausible future capabilities.
        4. **Industries and Domains**: Extract industries served from `website_content` or `documents`. For each industry, identify a primary domain (e.g., "Healthcare: Telemedicine"). Assign a `weight` (0-100) based on the proportion of mentions or projects in the data. If customer counts are mentioned, include them; otherwise, set to 0.

        **CONTEXT**: {company_info}
        
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for future_capabilities and industries in concise Markdown string bullet points (up to 4 points, 50-80 words total).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated (e.g.,Future Capabilities, Industries) or assumption (e.g., Assumed Trend), followed by a brief explanation (10-20 words) of the decision (e.g., rank, weight, duration, content).
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
              
        **OUTPUT FORMAT**:
        ```json
        {{
            "company_introduction": "<descriptive text introducing company>",
            "social_media_links": [
                {{
                    "type": "<platform name e.g. Linkedin, Twitter, etc>",
                    "address": "<vaild social media url>"
                }}...
            ],
            "capabilities": {{
                "current_capabilities":[
                    {{"text": "<capability_name>","description": "<capability_description>","rank": <integer, 1 to n based on prominence>}}
                    ...
                ],
                "future_capabilities":[
                    {{
                        "text": "<capability_name>",
                        "description": "<capability_description>",
                        "rank": <integer, 1 to n based on strategic importance>,
                        "duration_count": <integer>,
                        "duration_type": <year in range 2025-2050>
                    }}
                    ...
                ],
                "thought_process_behind_future_capabilities":"<Markdown bullet points: Each in the format clearly explained above in the **Thought process instructions**>",
                
            }},
            "industries": [
                {{
                    "industry_name": "<industry name>",
                    "domain_name": "<domainname(s) for above industry>",
                    "weight" : <integer, the distribution% of industry in the company strictly in range 0-100>,
                    "current_customer_count": <integer, number of customers or 0 if unknown>
                }}...
            ],
            "thought_process_behind_industries":"<Markdown bullet points: Each in the format clearly explained above in the **Thought process instructions**>",
        }}
        ```
        **INSTRUCTIONS**:
        - Focus on concrete information mentioned, not abstract concepts
        - Restrict to 2-3 domain names per industry & ensure the weight is integer(0-100)
        - Also ensure no duplicate names for current & future capabilities in `capabilities` section above.
        - If specific numbers or data aren't available,leave empty, put 0 for integer type and null for string type
        - Ensure thought process is concise (50-80 words), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions with suitable reference links & aligned to decisions to inputs and flagging assumptions.
        
    """
    userPrompt = f"""
        You are a canvas generation agent whose role is to mention the core capabilities & industry info of the company given in the input
        context as Company Information. Extract the information given in your task for the canvas.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user = userPrompt
    )



# Service catalog
def create_service_catalog_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent quantum agent tasked with creating a comprehensive service catalog for an onboarding flow using the provided company_info JSON, which includes website_content, social_media_posts, and documents. 
        
        Follow these steps to extract and organize service-related information:

        **CONTEXT**: {company_info}

        **TASK**: 
            1.Service Identification: Extract specific services from website_content (e.g., Services page), documents (e.g., brochures, case studies), or social_media_posts (e.g., recent service announcements). 
                Group related sub-services under primary categories (e.g., Water Management, Energy Solutions).
                
            2. Service Details:Category: Assign a primary category based on the service’s focus (e.g., Waste Services for recycling solutions).
                - Name: Use the exact service name from the data or a concise label if unnamed.
                - Description: Write a 50-100 word description summarizing the service’s purpose and value, grounded in the data.
                - Industry List: Identify up to two industries served by the service from website_content or documents (e.g., Healthcare, Manufacturing).
                - Tech List: List up to two key technologies mentioned in connection with the service (e.g., IoT, AI). Prioritize from documents or website_content.
                - Projects Executed Count: Extract the number of projects from documents (e.g., case studies) or website_content. Set to 0 if unavailable.
                - Consultants Count: Estimate team size from employee numbers or team mentions in website_content or documents. If geographic presence suggests scale (e.g., multiple offices), use as a proxy. Set to 0 if unavailable.
                - Partner List: Identify partners or brands associated with the service from website_content (e.g., Partnerships page) or documents. List as comma-separated names.
                - Framework IP List: List proprietary methodologies, frameworks, or service areas specific to the service (e.g., Agile Framework, Lean Consulting). Extract from documents or website_content.
            
           3.Tools and Accelerators: Identify tools, accelerators, or solutions mentioned in documents or website_content. Assign a type (Accelerator, Tool, Solution, Service) based on:
                - Accelerator: Pre-built frameworks or processes that speed up service delivery.
                - Tool: Software or platforms used in service execution.
                - Solution: Comprehensive offerings addressing specific client needs.
                - Service: Standalone service offerings.
           4.Solutions Suggested: Analyze the service catalog and identify gaps (e.g., missing services in a served industry, underutilized technologies). Suggest up to 4 solutions with names, descriptions, types, and benefits to address these gaps, grounded in industry trends or data patterns.
           
           
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
           
        **OUTPUT FORMAT**:
        ```json
        {{
            "services": [
                {{
                    "category": "<service category>",
                    "name": "<service Name>",
                    "description": "<service description>",   
                    "industry_list": "<comma separated list of industries served (max. 2)>",
                    "tech_list": "<comma separated list of technologies used (max. 2)>",
                    "projects_executed_count" : <integer> //0 if not available,
                    "consultants_count" : <integer> //0 if not available,
                    "partner_list": "<comma separated list of partners associated with the service>",
                    "framework_ip_list": "<comma separated list of framework services areas>"
                }}
                ...
            ],
            "tools_and_accelerators":[
                {{
                    "name": "",
                    "description": "<20-50 word description>",
                    "type": "<Accelerator|Tool|Solution|Service>",
                    "benefit": ""
                }}...
            ],
            "solutions_suggested": [//This you have to suggest on your own analyzing the data and gaps above
                {{
                    "name": "",
                    "description": "<20-50 word description>",
                    "type": "<Accelerator|Tool|Solution|Service>",
                    "benefit": ""
                }}
            ],
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```


        **INSTRUCTIONS**:
            - Avoid speculative or abstract information.
            - For missing data, use 0 for integers and empty strings for comma-separated lists. 
            - Ensure descriptions are concise, grounded in the input data, and avoid generic language.
            - Prioritize concrete services and details from website_content, documents, and social_media_posts.
            - Do not omit fields.Limit industry_list and tech_list to two items, prioritizing the most prominent based on frequency or emphasis in the data.
            - For framework_ip_list, include only proprietary or named methodologies explicitly mentioned.For solutions_suggested, base suggestions on gaps (e.g., unserved industries, unused technologies) and align with industry trends if data is sparse.
            - Ensure thought process is concise (50-80 words), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions with suitable reference links & aligned to decisions to inputs and flagging assumptions.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=""
    )


# Offers
def create_offers_prompt(company_info,offer_capability_list) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with generating distinct market offers for an onboarding flow using the provided company_info JSON (website_content, social_media_posts, documents) and offer_capability_list.
        Follow these steps to create compelling, data-driven offers:

        **CONTEXT**: 
        1. Company Info: {company_info}
        2. Capability Areas List: {offer_capability_list}

        **TASK**: 
        1.Offer Identification: Synthesize 3-5 unique offers based on services, products, or solutions in website_content (e.g., Services page), documents (e.g., brochures), or social_media_posts (e.g., recent announcements). 
            Ensure each offer aligns with capabilities in offer_capability_list.
            **Offer Details**:
                - Offer Title: Create a compelling, concise title (5-10 words) reflecting the solution’s value.
                - Offer Description: Summarize the offer’s purpose and scope in 20-50 words, grounded in the data.
                - Industry Name: Identify the primary industry served by the offer from website_content or documents.
                - Capability Areas: Single capability from offer_capability_list that directly relate to the offer.
                - Target Customers: Select the most relevant customer type (Startups, Mid-sized, Fortune 500, Large Cap) based on customer mentions in website_content, documents, or social_media_posts. If multiple types apply, choose the most prominent.
                
                - Offer Core Value Proposition: Distill the offer’s core value in up to 30 words, focusing on customer benefits.
                - Offer Solution: Describe the specific problem or need addressed in up to 60 words, based on data or implied needs
                - Offer Execution: Summarize the delivery approach (e.g., consulting, software deployment) in up to 60 words.
                - Outcome for Customer: Specify tangible deliverables or results in up to 60 words.
                - Paid Pricing Info and Model: Infer the pricing model (Free, Normal Price, Premium Model) based on service complexity (e.g., simple tools vs. enterprise solutions) and company type (e.g., SaaS, consulting). Provide a brief rationale (20-50 words).
                
        2.Promotional Strategies: Suggest marketing approaches (e.g., social media campaigns, webinars) based on company positioning in website_content (e.g., branding) or social_media_posts (e.g., engagement style).
        3.Offers of Future: Propose 1-2 future offer ideas based on gaps in current offerings (e.g., unserved industries, emerging technologies) or trends in documents or social_media_posts.
        
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "offers": [
                {{
                    "offer_title": "<offer title>",
                    "offer_desc": "<offer description>",
                    "industry_name": "<industry name for this offer>",
                    "capability_areas": "<single capability area applicable from mentioned list in the input>",
                    "target_customers": "<choose one from 'Startups',‘'Mid-sized’,'Fortune 500','Large Cap'>",
                    "offer_core_value_proposition": "Max 30 words",
                    "offer_solution": "<up to 60 word problem addressed>",
                    "offer_execution": "<up to 60 word delivery approach>",
                    "outcome_for_customer": "<up to 60 word deliverables or results>",
                    "paid_pricing_info": "<information related to offer pricing>",
                    "pricing_model": "<choose one from 'Free/Normal Price/Premium Model>"
                }}...
            ],
            
            "promotional_strategies": "<20-50 word marketing approach>",
            "offers_of_future": "<20-50 word description of 1-2 future offer ideas>",
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
            -The capability areas should strictly come from the list given in input context (Capability Areas List)
            -Ensure each offer is distinct, targets different customer needs, and maps to capabilities in offer_capability_list.
            -Prioritize concrete data from company_info. Avoid generic or speculative offers.
            -For missing data, use empty strings for text fields and select the most likely pricing_model based on service type.
            -Base promotional_strategies on company branding or engagement patterns in the data.
            -For offers_of_future, identify gaps or trends and propose innovative, feasible ideas.
            -Keep descriptions concise, tangible, and aligned with the company’s capabilities.
            - Ensure thought process is concise (50-80 words), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions with suitable reference links & aligned to decisions to inputs and flagging assumptions.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=""
    )
#Information & security
def create_info_security_prompt(company_info) -> ChatCompletion:
    
    systemPrompt = f"""
        You are an intelligent agent tasked with analyzing data privacy and information security practices for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`).
        Generate a structured output detailing current and future data privacy protocols.

        **CONTEXT**: {company_info}

        **TASK**:
        1. **Current Data Privacy Protocols** (100-200 words):
            - **Explicit Standards**: Extract certifications (e.g., ISO 27001, SOC 2) or standards from `website_content` (e.g., Privacy Policy) or `documents` (e.g., compliance reports).
            - **Inferred Practices**: Infer data privacy practices based on services described in `website_content` or `documents`. Map to industry standards (e.g., HIPAA for healthcare, GDPR for EU clients).
            - **Compliance Indicators**: Identify regulatory compliance mentions (e.g., GDPR, CCPA) in `website_content`, `documents`, or `social_media_posts`.
            - **Data Handling**: Describe data management practices (e.g., encryption, anonymization) based on service descriptions or privacy policies.
            - If no data is available, state: “No data privacy or security information available in provided data.”
            
        2. **Future Data Privacy Protocols** (100-200 words):
            - **Strategic Initiatives**: Extract planned security/privacy initiatives from `documents` (e.g., strategic roadmaps) or `social_media_posts` (e.g., innovation announcements).
            - **Technology Evolution**: Identify emerging tech adoptions (e.g., zero-trust architecture, blockchain) impacting privacy from `documents` or `website_content`.
            - **Regulatory Preparedness**: Note plans to address future regulations based on industry trends or data mentions.
            - **Industry Alignment**: Infer future privacy needs based on service evolution or industry standards (e.g., AI ethics for tech firms).
            - If no data is available, state: “No future data privacy or security initiatives identified in provided data.”
        
        
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        
        Return the output in follwing JSON format:

        ```json
        {{
            "current_data_privacy_protocols": "<100-200 word description>",
            "future_data_privacy_protocols": "<100-200 word description>",
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
            -Prioritize explicit mentions in website_content (e.g., Privacy Policy, Compliance pages), documents (e.g., certifications, roadmaps), and social_media_posts (e.g., compliance updates).
            -For inferences, use industry-standard practices (e.g., HIPAA for healthcare, PCI-DSS for finance) only when supported by service or industry context.
            -Distinguish explicit mentions (e.g., “ISO 27001 certified”) from inferences (e.g., “likely uses encryption based on financial services”).
            -If no data is available, use the specified “No data” statements instead of generic or speculative content.
            -Focus strictly on data privacy (e.g., data protection, consent) rather than general IT security (e.g., firewalls).
            -Ensure descriptions are concise, structured, and grounded in the provided data.
    """
    userPrompt = f"""
        Using the provided company_info JSON, generate a JSON output detailing the company’s current and future data privacy protocols. Follow the system instructions to extract and infer practices,
        ensuring descriptions are data-driven or use specified defaults when data is missing.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


#Ways of working
def create_ways_of_working_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with analyzing the company's ways of working for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`). 
        Generate a structured output detailing methodologies, processes, and service delivery approaches.

        **CONTEXT**: {company_info}

        **TASK**:
        1. Methodologies:
            - Extract specific methodologies (e.g., Agile, Lean, Six Sigma) from `website_content` (e.g., About Us, Services) or `documents` (e.g., process guides).
            - Describe each methodology (20-50 words) and list 3-5 unique steps (10-20 words each) based on explicit mentions or industry-standard processes.
            - Assign a `rank` (1 to n) based on prominence in the data (e.g., frequency of mention).
            
        2. Quality and Risk Management:
            - Describe quality management practices (20-50 words) from `documents` (e.g., quality assurance policies) or `website_content`. If unavailable, state: “No quality management details available.”
            - Describe risk management approaches (20-50 words) from `documents` (e.g., risk frameworks) or inferred from industry norms. If unavailable, state: “No risk management details available.”
        3. Opportunity Sources (4-6 items):
            - Identify sources of business opportunities (e.g., partnerships, digital marketing) from `website_content`, `social_media_posts`, or `documents`.
            - Assign an `impact_level` (0-100) based on estimated revenue or growth contribution.
            - Assign a `rank` (1 to n) based on prominence in the data.
            
        4. Opportunity Hurdles: Identify one key challenge to securing opportunities (e.g., competition, resource constraints) in <60 characters, based on `documents` or `website_content`.
        5. Customer Metrics:
            - Extract `customers_acquisition` (number of customers acquired annually) from `documents` (e.g., annual reports) or `website_content`
            - Estimate `customer_gestation_period` (time to convert leads to customers) from `documents` or industry norms.
        6. Business Continuity Plan (BCP) Constituents:
            - Extract 3-5 BCP components (e.g., disaster recovery, data backups) from `documents` (e.g., BCP plans) or `website_content`. Provide names and descriptions (10-20 words each).
        
        
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "ways_of_working": [
                {{
                    "name": "<methodology name>",
                    "description": "<methodology description>",
                    "steps": [//sequence of unique process to be followed for achieving this
                        {{
                            "name": "<child step name>",
                            "description": "<child desc>"
                        }}...
                    ],
                    "rank": <integer>
                }}...
            ],
            "quality_management" : "",
            "risk_management": "",
            
            "opportunity_sources": [
                {{
                    "name": "",
                    "impact_level": "<in range 0 to 100>",
                    "rank":<integer>
                }}...
            ],
            "opportunity_hurdles": "<name of opportunity hurdle in <40 chars>",
            
            "customers_acquistion": <integer_value_for_the_no_of_customers_acquired_in_a_year>,
            "customer_gestation_period": {{"number": <integer>, "type": "<choose one from days/weeks/months/years>"}},
            
            "bcp_constituents": [//business continuity plan constituents
                {{
                    "name":"",
                    "description": ""
                }}...
            ],
            "payment_terms": <integer>, //days, 0 if unknown
            "thought_process":""
        }}
        ```

        **INSTRUCTIONS**:
            - Prioritize explicit mentions in `website_content` (e.g., About Us, Services), `documents` (e.g., process guides, BCP plans), and `social_media_posts` (e.g., operational updates).
            - For inferences, use industry-standard practices (e.g., Agile for software, Lean for manufacturing) only when supported by service or industry context.
            - Assign `rank` based on prominence (e.g., frequency of mention) for methodologies and opportunity sources.
            - For `opportunity_sources`, ensure 4-6 distinct items, estimating `impact_level` based on data or industry norms.
            - For `opportunity_hurdles`, select one key challenge from data or infer from industry context (e.g., "Market competition").
            - For `payment_terms`, extract from `documents` (e.g., contracts) or infer from industry norms (e.g., 30 days for consulting).
            - Use 0 for integers and empty strings or specified defaults for text fields when data is missing.
            - Ensure descriptions are concise, structured, and grounded in the provided data.
    """
    
    userPrompt = f"""
        Using the provided `company_info` input, generate a JSON output detailing the company’s ways of working, including methodologies, quality/risk management, opportunity sources, and business continuity plans. 
        Follow the system instructions to extract and infer data, using defaults when information is missing.
    """
    return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)


#Case studies & Publications
def create_case_studies_prompt(company_info,imgs=None) -> ChatCompletion:
    currentDate = datetime.datetime.now().date().isoformat()
    systemPrompt = f"""
        You are an intelligent agent tasked with extracting case studies and publications for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`). 
        Generate a structured output detailing all the case studies and publications.

        Also there is a list of images urls provided to you scraped from the company website, you need to choose & place them in the image links for publications and case studies.
        Note: If the url involves /team etc. STRICTLY don't choose them!
        **CONTEXT**: 
            - Company INfo: {company_info}
            - Images: {imgs} 


        **TASK**: To find all the case studies and publications present in the input Context

        1. **Case study**: 
        - Identify all distinct case studies from `website_content` or `social_media_posts`. Look for sections titled 'Case Studies', 'Projects', 'Success Stories', or similar. 
        - Also, search for individual case studies within blog posts or news articles (e.g. Customer Success Stories). Each case study should have its own title and content.
        - For each case study, attempt to extract an image link from the `website_content`. Look for image tags or links associated with the case study section or content.
        - Image link to be selected from the list of Images provided to you.
        
        2. **Publications**:
        - Identify all distinct publications (white papers, articles, reports) from `website_content`. Look for sections titled 'Resources', 'Publications', 'White Papers', or similar. 
        - Also, search for individual publications within blog posts or news articles. Each publication should have its own title and content.
        - For each publication:
            - **Title**: Extract the exact title if available, or create a concise title (5-10 words) based on the content.
            - **Author Names**: List authors as a comma-separated string; use “Unknown” if missing.
            - **Description**: Provide a detailed MARKDOWN formatted description (200-400 words), including different dynamic sections, such as (## Overview, ## Key Findings, ## Conclusion, ## References etc.).
            - **Image Link**: - To be selected from the list of Images provided to you.

        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for the case studies and publications  identified above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "case_studies": [
                {{
                    "case_study_title": "<title>",
                    "case_study_details": [
                        {{
                            "header": "<5-10 word header>",
                            "summary": "<20-50 word summary>",
                            "image_link": "<a valid image url from the images list>",
                            "the_problem": ["<array of strings describing the problem>"],
                            "the_solution": "<20-50 word solution description>",
                            "technology_stack": ["<array of comma separated tech-stack>"],
                            "team_location" : ["<array of comma separated locations>"],
                            "our_process_summary": "<20-50 word process summary>",
                            "our_process_steps": [
                                {{
                                    "process_step_header": "<step name>",
                                    "short_description": "<10-20 word description>"
                                }}...
                            ],
                            "challenges": "<20-50 word challenges summary>",
                            "top_two_challenges": [{{"header": "<challenge name>","description": "<10-20 word description>"}}...],
                            "key_results": "<20-50 word results summary>",
                            "top_three_key_results": [{{"header": "<result name>","quantitative_data": "<10-20 word quantitative result or description>"}}...]
                        }}...
                    ],
                    "case_study_created_date": "<date|if not present put {currentDate}>",
                    "case_study_reading_time": <integer value for time in minutes>
                }}
            ],
            
            "publications": [
                {{
                    "title": "",
                    "author_names": "",
                    "description": "<detailed publication desc as Markdown string with relevant sections>",
                    "date": "<published_date>",
                    "image_link": "<a valid image url from the images list>"
                }}...
            ],
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
        - Look for sections or mentions of past projects, successes, or client work
        - Extract as much detail as possible for each case study and publications
        - If no case studies or publications are found, return an empty list
    """
    return ChatCompletion(system=systemPrompt, prev=[], user="")


#Partnerships and Ecosystem
def create_partnerships_prompt(company_info,partner_list) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with analyzing strategic partnerships for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`) and `partner_list`. 
        Generate a structured output detailing partnerships and their ecosystem impact.


        **CONTEXT**: 
        1. Company Info: {company_info}
        2. Partner List: {partner_list}


        **TASK**:
        1. **Partnerships**:
        - Identify partnerships from `partner_list` that are mentioned in `website_content` (e.g., Partnerships page), `documents` (e.g., case studies), or `social_media_posts` (e.g., collaboration announcements).
        - For each partnership:
            - **Partnership Name**: Use the exact name from `partner_list`.
            - **Page Link**: Provide the URL from `website_content` or partner’s website if mentioned; otherwise, use an empty string.
            - **Description**: Summarize the partnership’s purpose (20-50 words) based on data.
            - **Rating**: Assign a rating (0-5) based on prominence or impact in the data (e.g., 5 for major revenue-driving partners).
            - **Future Partnership Goal**: Describe a planned expansion or goal (10-20 words) from `documents` (e.g., roadmaps) or infer from industry trends.
            - **Duration Count and Type**: Estimate the partnership duration (e.g., 2 years) from `documents` or `social_media_posts`and `duration_type` is year e.g. 2025. Set `duration_count` and `duration_type` to 0 if unknown.
            - **With In**: Specify the start month (e.g., January) if mentioned; otherwise, use an empty string.
            - **Future**: Set to `true` if the partnership is planned (e.g., roadmap mentions); otherwise, `false`.
            - **Is Successful**: Set to `true` if success metrics (e.g., revenue, projects) are mentioned; otherwise, `false`.
            
        2. **Partnership Ecosystem**:
            - Select list of prominent partnerships from `partnerships` based on rating or impact.
            - **Impact Value**: Assign a value (0-100) based on estimated revenue or strategic contribution.
            - **Leverage Partnership**: List benefits (e.g., Create pipeline, Data integration) from data or inferred from partnership type.
            - **Partner Success**: Describe success metrics (20-50 words) from `documents` (e.g., case studies) or `social_media_posts`.

        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points as string (up to 4 points, 20 words).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "partnerships": [
                {{
                    "partnership_name": "<name strictly from the partner list>",
                    "page_link": "<page url>",
                    "description": "<partnership description>",
                    "rating": <integer value 0 to 5>,
                    "future_partnership_goal": "<partnership goals in future>",
                    "duration_count": <integer>,
                    "with_in": "<month>",			
                    "duration_type": <integer| year value e.g. 2025>,
                    "future": false,
                    "is_successful": false
                }}...
            ],
            
            "partnership_ecosystem": [
                {{
                    "partner_name": "<one of the partnership name selected above>",
                    "impact_level": "<0 to 100>",
                    "leverage_partnership":"<comma separated list choose one or more from `Create pipeline, Building capabilities, Data integration, Joint marketing`>",
                    "partner_success":"<success metrics>"
                }}...
            ],            
            "thought_process":""
        }}
        ```
        **INSTRUCTIONS**:
        - Restrict `partnership_name` to names in `partner_list`. Return an empty `partnerships` list if no matches are found.
        - Prioritize explicit mentions in `website_content` (e.g., Partnerships page), `documents` (e.g., case studies), and `social_media_posts` (e.g., collaboration posts).
        - Infer `partnership_type` (e.g., strategic for business alliances, technological for integrations) from data context.
        - For `rating`, use prominence (e.g., frequency of mentions) or impact (e.g., revenue contribution).
        - For `future_partnership_goal`, use roadmap mentions or infer feasible goals based on industry trends.
        - Use empty strings for text fields and 0 for integers when data is missing.
        - Ensure descriptions are concise, data-driven, and avoid speculative content.

    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=""
    )


#Certi and Audits
def create_certifications_and_audit_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with extracting company-wide certifications and audit results for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`).
        Generate a structured output detailing certifications and audits.

        **CONTEXT**: {company_info}

        **TASK**:
        1. **Company Certifications**:
        - Extract company-wide certifications (e.g., ISO 27001, SOC 2) from `website_content` (e.g., Compliance, About Us pages), `documents` (e.g., certification reports), or `social_media_posts` (e.g., certification announcements).
        - For each certification:
            - **Name**: Exact certification name (e.g., "ISO 27001").
            - **Description**: Summarize purpose and scope (20-50 words) from data or industry norms.
            - **Duration Count**: Estimate validity period (e.g., 3 for 3 years) from data; use 0 if unknown.
            - **Duration Type**: Select corres. integer mapping for options `days`, `weeks`, `months`, or `years` based on validity period; put 0 if unknown.
        2. **Company Audits**:
        - Extract audit or assessment details (e.g., security, financial, quality) from `documents` (e.g., audit reports), `website_content` (e.g., Compliance pages), or `social_media_posts` (e.g., audit completion posts).
        - For each audit:
            - **Name**: Audit type or name (e.g., "SOC 2 Audit").
            - **Description**: Summarize audit scope and outcome (20-50 words) from data.
            - **Duration Count**: Estimate audit duration or frequency (e.g., 1 for annual audit) from data; use 0 if unknown.
            - **Duration Type**: Select `days`, `weeks`, `months`, or `years` based on audit timeframe, corres. integer mapping to options "days"-1,"weeks"-2,"months"-3,"years"-4


        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "company_certifications" :[
                {{
                    "name": "<certification name>",
                    "description": "<certification description>",
                    "duration_count":<integer>,
                    "duration_type": <choose the integer value strictly for options "days"-1,"weeks"-2,"months"-3,"years"-4>
                }}
            ],
            "company_audits": [
                {{
                    "name": "<audit name>",
                    "description": "<audit description>",
                    "duration_count":<integer>,
                    "duration_type": <choose the integer value strictly for options "days"-1,"weeks"-2,"months"-3,"years"-4>
                }}
            ],
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
        - Prioritize explicit mentions in `documents` (e.g., certification reports, audit summaries), `website_content` (e.g., Compliance, About Us), and `social_media_posts` (e.g., certification/audit announcements).
        - Scope `company_certifications` to company-wide certifications (e.g., ISO 27001), not individual/team certifications (e.g., PMP).
        - For audits, focus on compliance, security, or quality assessments (e.g., SOC 2, financial audits).
        - Infer `duration_count` and `duration_type` from data (e.g., certification validity, audit frequency) or industry norms (e.g., ISO 27001 valid for 3 years).
        - Return empty lists for `company_certifications` and `company_audits` if no data is found.
        - Ensure descriptions are concise, data-driven, and avoid fabricated details to maintain authenticity.
    """
    return ChatCompletion(system=systemPrompt, prev=[], user="")


#Leadership Team
def create_leadership_and_team_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with extracting leadership team and team composition details for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`). 
        Generate a structured output detailing leadership, team structure, certifications, and future projections.

        **CONTEXT**: {company_info}

        **TASK**:
        1. **Leadership**:
            - Extract all the key leaders (e.g., CEO, Co-Founders, CTO, VP, Managers) from `website_content` (e.g., About Us, Leadership pages,Team pages), `documents` (e.g., org charts).
            - For each leader:
                - **Name**: Full name or identifier (e.g., "Jane Doe").
                - **Role**: Job title (e.g., "Chief Technology Officer").
                - **LinkedIn**: Extract LinkedIn URL if available; use empty string if missing.
        2. **Team Composition**:
            - Identify team roles (e.g., Software Engineer, Sales Manager) and their counts from `documents` (e.g., org charts) or `website_content` (e.g., Team page).
            - Use ranges (`1–10`, `10+`, `25+`, `50+`, `100+`, `500+`) for `role_count`.
            - Limit `role_name` to 40 characters.
        3. **Team Certifications**:
            - Extract certifications (e.g., PMP, AWS Certified, reports, Team page).
            - Estimate `count` using ranges (`1–10`, `10+`, `25+`, `50+`, `100+`, `500+`) based on team size or mentions.
        4. **Team Projections** (12-18 months):
            - Estimated future team changes from `documents` (e.g., strategic plans, hiring goals) or `social_media_posts` (e.g., recruitment posts).
            - For each projection:
                - **Name**: Team or department (e.g., "Engineering Team").
                - **Size**: Integer estimate of future team size based on data or industry trends.
                - **Month**: Target month for projection (e.g., "January") or empty string if unspecified.
                - **Year**: Target year (e.g., "2026" or "2027") based on 12-18 months from current year.
                
        **Thought Process Instructions**:
            - Document reasoning for the team projections devised below in concise Markdown string bullet points (up to 4 points, max).
            - **Format Requirement**: For each team projection suggested, each bullet must start with a **bold header** summarizing the source of truth (e.g.from where it is fetched or you have used your intelligence, followed by a brief (1-2 sentence, 10-20 words) on the team size,month,year, and description with the URL if available (from `website_content`) explaining its influence, justification, or assumption.
            - Avoid verbose explanations to optimize rendering speed.        
        
        **OUTPUT FORMAT**:
        ```json
        {{
            
            "leadership": [
                {{
                    "name": "Name",
                    "role": "Role",
                    "linkedin": "<linkedin url>"
                }}...
            ],
            "team_composition": [
                {{"role_name": "<in 40 chars>", "role_count": "<choose the range strictly among one of the options e.g.'1– 10','10+','25+','50+','100+','500+'>"}}
                ...
            ],
            "team_certifications":[
                {{ "certificate_name": "", "count": "<choose the range strictly among one of the options e.g.'1– 10','10+','25+','50+','100+','500+'>"}}
            ],
            "team_projections":[
                {{
                    "name": "<team name>",
                    "size": "<integer value of team size>",
                    "month": "<month e.g. January, February etc. as applicable>",
                    "year": ""
                }}...
            ],
            "thought_process_behind_team_projections": "<Markdown bullet points: Each in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
        - Prioritize explicit mentions in `website_content` (e.g., About Us, Leadership, Team pages), `documents` (e.g., org charts, reports), and `social_media_posts` (e.g., executive or hiring announcements).
        - For `team_composition` and `team_certifications`, infer counts from team size or industry norms if data is sparse.
        - For `team_projections`, base estimates on strategic plans or hiring trends; assume growth for tech firms if no data is available.
        - Ensure thought process is concise (50-80 words), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions with suitable reference links & aligned to decisions to inputs and flagging assumptions.
        - Use empty strings for text fields and 0 for integers or lists when data is missing.
        - Ensure descriptions are concise, data-driven, and avoid fabricated details to maintain authenticity.
    """
    return ChatCompletion(system=systemPrompt, prev=[], user="")


#Voice of customer
def create_voice_of_customer_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        You are an intelligent agent tasked with extracting customer testimonials, feedback, and insights for an onboarding flow using the provided `company_info` JSON (`website_content`, `social_media_posts`, `documents`). 
        Generate a structured output detailing customer voices and perceptions.

        **CONTEXT**: {company_info}

        **TASK**:
        1. **Voice of Customer**:
            - Identify testimonials, feedback, or customer stories from `website_content` (e.g., Testimonials, Reviews pages), `social_media_posts` (e.g., customer quotes), or `documents` (e.g., case studies).
            - For each entry, include:
                - **Name**: Customer’s full name or identifier (e.g., “John Doe” or “Client A”).
                - **Email**: Extract email if available; use `null` if missing.
                - **Designation**: Extract job title (e.g., “CTO”); use empty string if missing.
                - **Org Name**: Extract organization name; required for inclusion.
            - Include only entries with valid `name` and `org_name`.
            2. **Customer Tenures**:
                - Extract or infer customer tenure ranges (`0-1 years`, `1-3 years`, `3-5 years`, `5-10 years`, `10-15 years`, `15+ years`) from `documents` (e.g., case studies) or `website_content`.
                - Estimate `count` based on customer mentions or infer from industry norms (e.g., tech firms have shorter tenures). Use 0 if unknown.
            3. **Customer Descriptions**:
                - **Customer Desc**: Summarize current customer perception (50-100 words) based on feedback or sentiment in data.
                - **Customer Desc Future**: Describe future customer aspirations (50-100 words) from `documents` (e.g., strategic plans) or inferred from industry trends.
            4. **Customer Types Serviced**: Identify customer types (`Large Cap`, `Mid-sized`, `Startups`, `Fortune 500`) from data; list as comma-separated string.
            5. **Customer Feedback Through**: Identify feedback sources (`Interviews`, `Surveys`, `Focus Groups`, `Other`) from data; list as comma-separated string.

        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "voice_of_customer": [
                {{
                    "name": "<customer name>",
                    "email": "<customer email-id>" //if not present put null,
                    "designation": "<customer designation>",
                    "org_name": "<customer's organization name>"
                }}...
            ],
            "customer_tenures": [
                {{
                    "type": "<0-1 years|1-3 years|3-5 years|5-10 years|10-15 years|15+ years>",
                    "count": <integer>
                }}...
            ],
            
            "customer_desc": "<a descriptive text on current customer perception of the company>",
            "customer_desc_future" :"<a descriptive text on future aspirations about the customers>",
            "customer_types_serviced": "<comma-separated: Large Cap, Mid-sized, Startups, Fortune 500>",
            "customer_feedback_through": "<comma-separated: Interviews, Surveys, Focus Groups, Other>",
            "thought_process":"<in the format clearly explained above in the **Thought process instructions**>"
        }}
        ```

        **INSTRUCTIONS**:
        - Prioritize explicit mentions in `website_content` (e.g., Testimonials, Reviews), `social_media_posts` (e.g., customer quotes), and `documents` (e.g., case studies).
        - Include only `voice_of_customer` entries with valid `name` and `org_name`; exclude anonymous or incomplete entries.
        - For `customer_tenures`, infer counts from customer mentions or industry norms if data is sparse.
        - For `customer_desc_future`, use strategic plans or industry trends (e.g., enhanced support for startups).
        - Return empty lists for `voice_of_customer` and `customer_tenures` if no data is found.
        - Use empty strings for text fields, `null` for `email`, and 0 for integers when data is missing.
        - Ensure descriptions are concise, data-driven, and avoid speculative content.

    """
    return ChatCompletion(system=systemPrompt, prev=[], user="")






#BCP
def process_bcp_prompt(company_info) -> ChatCompletion:
    systemPrompt = f"""
        Analyze the company data to extract information
        **CONTEXT**: {company_info}

        **TASK**: Extract or infer the following information: **Business Continutiy Plan**: BCP details and constituents
        - Identify BCP components (e.g., disaster recovery, data backups, crisis management) from `documents` (e.g., BCP plans, risk reports), `website_content` (e.g., About Us, Compliance pages), or `social_media_posts` (e.g., resilience updates).
        - For each constituent:
            - **Name**: Provide a concise name (e.g., "Disaster Recovery").
            - **Description**: Describe the component’s purpose and implementation (10-20 words) based on data or inferred from industry norms (e.g., data backups for tech firms).
        - List 3-5 distinct components if data is available.
        - If no BCP data is found, return a default constituent: {{"name": "Data Backup", "description": "Regular data backups to secure storage."}}.
        
        **THOUGHT PROCESS INSTRUCTIONS**:
        - Document reasoning for each of the task above in concise Markdown string bullet points (up to 4 points, 20 words each).
        - Each bullet must start with a **bold header** indicating the reason behind the data generated  or assumption, followed by a brief explanation (10-20 words) of the decision.
        - Include a **References** section at the end of thought process, listing URLs or data sources.
        - Avoid verbose explanations to optimize rendering speed.
        
        **OUTPUT FORMAT**:
        ```json
        {{
            "bcp_constituents": [//business continuity plan constituents
                    {{
                        "name":"",
                        "description": ""
                    }}...
                ],
            "thought_process":""
        }}
        ```
        
        
        **INSTRUCTIONS**:
        - Prioritize explicit mentions in `documents` (e.g., BCP plans, Compliance, About Us).
        - Infer components from industry norms (e.g., disaster recovery for finance, redundancy for tech) only when supported by service or industry context.
        - Ensure 3-5 components if data is available; otherwise, include the default constituent.
        - Return an empty `bcp_constituents` list only if no data or industry context supports inference, but prefer the default constituent.
        - Ensure descriptions are concise, data-driven, and avoid speculative content.
        - Focus on BCP components that ensure operational continuity (e.g., backups, recovery plans), not general business processes.
        
    """
    return ChatCompletion(system=systemPrompt, prev=[], user="")



def process_case_study_prompt(company_info) -> ChatCompletion:

    currentDate = datetime.datetime.now().date().isoformat()
    systemPrompt = f"""
        Analyze the given extracted case study document info of the company
        **CONTEXT**: {company_info}

        **TASK**: Extract or infer the following information: Case study components
        - Identify case study components from the input document provided & give the parts as given in JSON below.
        - Use your intelligence to understand the document well and process the data as per the requirement.
        

        **OUTPUT FORMAT**:
        ```json
        {{
            "case_study": [
                "case_study_title": "<title>",
                "case_study_details": [
                    {{
                        "header": "<5-10 word header>",
                        "summary": "<20-50 word summary>",
                        "the_problem": ["<array of strings describing the problem>"],
                        "the_solution": "<20-50 word solution description>",
                        "technology_stack": ["<array of comma separated tech-stack>"],
                        "team_location" : ["<array of comma separated locations>"],
                        "our_process_summary": "<20-50 word process summary>",
                        "our_process_steps": [
                            {{
                                "process_step_header": "<step name>",
                                "short_description": "<10-20 word description>"
                            }}...
                        ],
                        "challenges": "<20-50 word challenges summary>",
                        "top_two_challenges": [{{"header": "<challenge name>","description": "<10-20 word description>"}}...],
                        "key_results": "<20-50 word results summary>",
                        "top_three_key_results": [{{"header": "<result name>","quantitative_data": "<10-20 word quantitative result or description>"}}...]
                    }}...
                ],
                "case_study_created_date": "<date|if not present put {currentDate}>",
                "case_study_reading_time": <integer value for time in minutes>
            ]
        }}
        ```
    """

    return ChatCompletion(system=systemPrompt, prev=[], user="Extract the case study info from given input in above JSON format.")


