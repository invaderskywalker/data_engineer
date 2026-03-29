import datetime
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_services.roadmap.utils import EY_SHEET_DATA,demand_type_prompt,uploaded_files_prompt, demand_category_prompt
from src.trmeric_database.dao import UsersDao

CURRENT_DATE = datetime.datetime.now().date().isoformat()


def format_dimension_guidance(guidance):
    """Format dimension guidance for display in prompts.
    
    Args:
        guidance: Either a string (legacy) or list of guidance items (new format)
        
    Returns:
        Formatted string for prompt display
    """
    if isinstance(guidance, list):
        if not guidance:
            return "No historical patterns available."
        return "\n".join([f"• {item}" for item in guidance])
    elif isinstance(guidance, str):
        return guidance
    else:
        return "No historical patterns available."


def businessCaseTemplateCreatePrompt(roadmap_data, labor_cost_analysis, non_labor_cost_analysis) -> ChatCompletion:
    prompt = f"""
        Cost and Budget Estimates:
            Provide detailed cost estimates for the project, including initial capital expenditures and ongoing operational expenses. Include estimates for development, implementation, licensing, maintenance, support, and resource allocation. 
            Non labour costs such as hardware costs, software licensing cost, cloud & hosting cost, training/certification cost, facilities & utilities, travel & accommodation, compliance & legal etc. 
            
            Look into team_data in <roadmap_data>:
                <labour_cost_calculation_formula> (identified by labour_type = "labour")
                    Just refer to <labor_cost_analysis_done> and use it further calculation  \    
                    <labor_cost_analysis_done>
                        {labor_cost_analysis}
                    <labor_cost_analysis_done> 
                
                <labour_cost_calculation_formula> \
                <non_labour_cost_calculation_formula> (identified by labour_type = "non labour")
                    Total Non Labour Cost =  this is fixed cost, so just add the values in labour_estimate_value as they are. do not multiply/divide anything
                
                    <non_labor_cost_analysis_done>
                        {non_labor_cost_analysis}
                    <non_labor_cost_analysis_done> 
                <non_labour_cost_calculation_formula>
                
            Total Cost = <labour_cost_calculation_formula> + <non_labour_cost_calculation_formula>
                
            
            ** note: labour cost should not be calculated for a year or multi year.. only given formula should be used because this is a total effort estimate for the project
                
        *** Financial Analysis and ROI:
            Compute the expected financial benefits of the project, including cost savings, revenue growth, or return on investment (ROI). 
            Include the payback period, Net Present Value (NPV).
            
            **NPV = Σ (Ct / (1 + r)^t) - C0**

                Where:
                - **Ct** = Cash inflow during the period **t**
                - **r** = Discount rate
                - **t** = Time period (year)
                - **n** = Total number of periods
                - **C0** = Initial investment cost
                
            ROI= Net Profit (or Benefit)/ Total Investment (in percent) (net profit has to be derived from roadmap key results and the corresponding baseline_value and determine the net profit)
            Payback Period= Initial Investment / Annual Cash Inflows
            
            example - if n = 3 - use the actual ct obtained from the cash_inflow data in <roadmap_data>
                NPV = (c1/(1+r)^1 + c2/(1+r)^2 + c3/(1+r)^3) - C0
            use this formula to calulate NPV using the data from key results of <roadmap_data> and Baseline Value and derive at net profit

            Do a proper calculation for this like-
            ```
            show the formula first
            and the corresponding values
            
            extract Ct first and understand time period and r 
            etract C0 and show
            then calculate NVP
            
            then calculate ROI
            then calculate Payback Period
            
            ```
            
        As per this instruction please calculate the 
            - NPV and show the calculation and store in <npv> and get to a result
            - Payback Period and show the calculation and store in <payback_period> and get to a result
            - ROI and show the calculation and store in <roi> and get to a result
            



        Please generate a detailed business case for the provided roadmap or initiative, structured according to the following template. 
        The business case should comprehensively describe the roadmap or initiative, its strategic alignment, its Key results or KPIs, expected benefits, costs, risks, and other essential aspects necessary for business approval.
        
        All data is provided in the json: <roadmap_data> below 
        
        <roadmap_data>
        {roadmap_data}
        <roadmap_data>
        
        ### Please finish all calculations as requested
        
        Output format -
        ```json
        {{
            "executive_summary": "", // Short summarize the key aspects of the project/roadmap or initiative, including the problem or opportunity it addresses, the proposed solution, and the expected benefits (both financial and non-financial). Include a brief recommendation for approval.Provide the output in a descriptive format

            "strategic_alignment": [], // Short describe how the initiative aligns with the organization's strategic goals, business priorities, and competitive context.

            "business_objectives_and_benefits": [], // List the business objectives and expected benefits (tangible/intangible) with success metrics (KPIs/Key results).
                                                    Output in json - Format: [{{
                                                        Objective: "",
                                                        KPI: "", 
                                                        Benefit: "",
                                                    }}, ...]


            "problem_or_opportunity_analysis": "", // Provide a detailed analysis of the problem or opportunity the project addresses, including supporting data, research, or trends. Provide the output in a Descriptive paragraph

            "project_scope": "", // Define the project scope, listing inclusions, exclusions, assumptions, constraints, and dependencies. Provide the output in a descriptive paragraph

            "proposed_solution_overview": "", // Describe the proposed solution, including key features, technologies, and reasons for selection. Provide the output in descriptive paragraph

            "cost_and_budget_estimates": "", // Provide detailed cost estimates for the project, including development, implementation, and ongoing expenses - Labour cost and Non Labour cost. Also consider the TCO when arriving at the overall cost or Total investment. Include the mathematical calculation in the response

                "estimated_labor_cost": [], // output a table for the labor cost 
                                                format: [{{
                                                    "Category": "",
                                                    "Amount": "", // use formula in <labour_cost_calculation_formula>
                                                    "Justification": "" // description of the formula used and calculation
                                                }}]
                                                
                "estimated_non_labor_cost" :[], // output a table for the non labor cost 
                                                format: [{{
                                                    "Category": "",
                                                    "Amount": "",
                                                    "Justification": ""
                                                }}]
                                                
                "overall_cost_breakdown" :[], // output a table for the labor cost . also add a row of total cost by adding labor and non labor cost
                                                format: [{{
                                                    "Category": "",
                                                    "Amount": "",
                                                    "Justification": ""
                                                }}]
                                            
            "financial_analysis_and_ROI": "", // Inteligently compute the financial benefits 
                                                such as ROI, NPV, and payback period and also include the mathematical calculation in the 
                                                response on how you arrived at the respective values. 
                                                Check the calculation formula in the section Financial Analysis and ROI:
                                                
                                                
                "revenue_uplift_cashflow": [], // output a table for the data in revenue_uplift_cash_inflow_data
                                                format: [{{
                                                    "Year": "",
                                                    "Revenue Category": "",
                                                    "Total Revenue": "",
                                                    "Justification": ""
                                                }}]
                                                
                "operational_efficiency_gains": [], // output a table for the data in operational_efficiency_gains_savings_cash_inflow
                                                format: [{{
                                                    "Year": "",
                                                    "Savings Category": "",
                                                    "Amount": "",
                                                    "Justification": ""
                                                }}]
                                                
                                                
                "cash_flow_analysis": [], // output a table - save as <cash_flow_analysis>
                                                format: [{{
                                                    "Year": "",
                                                    "Total Revenue": "",
                                                    "Total Costs": "",
                                                    "Operational Efficiency Savings": "",
                                                    "Net Cash Flow": value of "Total Revenue" + "Operational Efficiency Savings" - "Total Costs"
                                                }}]

            "risk_analysis": [], // array of json, Identify key risks from the roadmap data and its constraints, their probability/impact, mitigation strategies, and contingency plans. 
                                    Output in json - Format: [{{
                                        Risk: "", 
                                        Probability: "", // one of High, Medium, Low
                                        Impact: "", // one of High, Medium, Low
                                        Mitigation Strategy: ""
                                    }}, ...]

            "stakeholder_analysis": [], // List key stakeholders, their roles, responsibilities, and a communication plan. 
                                        Output in json - Format: 
                                        [
                                            {{
                                                "Stakeholder": "", 
                                                "Role": "", 
                                                "Responsibility": "", 
                                                "Communication Plan": ""
                                            }}
                                        ]

            "project_timeline_and_milestones": [], // Provide a high-level timeline, major milestones, dependencies, and critical path tasks. 
                                                        Output In json - Format:
                                                        [{{
                                                            "Milestone": "",
                                                            "Date": "", 
                                                            "Dependencies": "", 
                                                            "Critical Path Task": "Yes", "No"
                                                        }}]

            "conclusion_and_recommendation": "", // Summarize the project benefits and provide a final recommendation for approval.

            "approval_section": "" // Include space for necessary sign-offs by project sponsors and business unit leaders.
        }}
        ```


        
    """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def businessCaseTemplateFinancialCalculationPrompt(business_case_data) -> ChatCompletion:
    prompt = f"""
    
        Your task is to do the calculation of NPV, Payback Period and ROI as per the instruction given below using the business case data <business_case_data>;
        
        <business_case_data>
        {business_case_data}
        <business_case_data>
        *** Financial Analysis and ROI:
      
    check overall_cost_breakdown for C0
    Check operational_efficiency_gains and revenue_uplift_cashflow for yearly cash inflow - Ct  

    - **NPV Calculation**:
      - Formula: NPV = Σ (Ct / (1 + r)^t) - C0
        - Where:
          - **Ct** = Cash inflow during the period **t**
          - **r** = Discount rate
          - **t** = Time period (year)
          - **C0** = Initial investment cost
          
      - **Step-by-Step Instructions**:
        1. Extract **Ct** (cash inflows) from the cash flow analysis in <business_case_data>.
        2. Identify the discount rate (**r**) and the total number of periods (**n**).
        3. Determine the initial investment cost (**C0**).
        4. Show the formula and substitute the extracted values.
        5. Perform the calculation for NPV, showing each step clearly.

    - **ROI Calculation**:
      - Formula: ROI = Net Profit / Total Investment (expressed as a percentage)
        - Net Profit should be derived from the roadmap key results and the corresponding baseline value.
        
      - **Step-by-Step Instructions**:
        1. Calculate the Net Profit.
        2. Show the formula for ROI and substitute the values.
        3. Perform the calculation and explain the result.

        - **Payback Period Calculation**:
        - Formula: You are inteligent enough to calculate it yourself

        - **Step-by-Step Instructions**:
            1. Show the formula and identify the values for initial investment and annual cash inflows.
            2. Perform the calculation and explain the result.


        
        Output format -
        ```json
        {{

            "NPV": <npv> and calculation justification, use the cash_flow_analysis from <business_case_data> and check the "Total Revenue" and use the calculation given in *** Financial Analysis and ROI. Write the final answer with short description of calculation
            "payback_period": <payback_period> and calculation justification, // do the calculation and present result from instruction given in Financial Analysis and ROI formula - Payback Period= Initial Investment / Annual Cash Inflows
            "ROI": <roi> and calculation justification, // do the calculation and present result from instruction given in Financial Analysis and ROI formula - ROI= Net Profit (or Benefit)/ Total Investment (in percent) (net profit has to be derived from roadmap key results and the corresponding baseline_value and determine the net profit) 
        }}
        ```
        
        Please ensure to provide clear explanations for each calculation step, showing the formula, the values used, and the final result for each financial metric.


        
    """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )



def webSearchRoadmapInputs(conversation, persona, org_alignment, portfolios) -> ChatCompletion:
    """Generate web search queries to support roadmap creation in valid JSON format."""
    
    systemPrompt = f"""
        You are an expert roadmap preparation agent. Your task is to generate targeted web search queries to gather external data supporting roadmap creation, based on the provided conversation and organization details. Return **only** valid JSON with no additional text or comments.

        ### Input Data:
        <conversation> {conversation} </conversation>
        <org_details>
            These include:
            2. Customer Persona: <persona> {persona} <persona>
            3. Portfolios: <portfolios> {portfolios} <portfolios>
            4. Org Strategy Alignment: <org_alignment> {org_alignment} <org_alignment>
        </org_details>

        ### Task:
        - Analyze **conversation** to identify roadmap goals and needs.
        - Use **persona** to align queries with customer needs.
        - Use **org_alignment** to ensure queries support organizational priorities.
        - Use **portfolios** to tailor queries to relevant portfolio goals.
        
        - Generate upto 3-5 web search queries to find external data, such as:
          - Industry trends relevant to the roadmap’s goals.
          - Best practices for technologies or processes mentioned.
          - Common challenges or costs for similar projects.
          - Case studies aligned with portfolio goals or org strategy.
        - Provide a thought process explaining why each query was chosen.

        ### Output Format:
        ```json
        {{
            "web_queries": [
                {{
                    "query": "<search query, e.g., 'supply chain automation trends 2025'>",
                    "purpose": "<why this query, e.g., 'Find trends in supply chain automation to support roadmap goals.'>"
                }}
            ],
            "thought_process": "<Markdown: Explain in bullet points why each query was chosen, e.g., 
                - **Query 1**: Targets automation trends to align with conversation goals.
                - **Query 2**: Seeks cost estimates for portfolio X’s projects.>"
        }}
        ```

        ### Guidelines:
        - Ensure queries are specific, actionable, and tied to <conversation>, <persona>, <org_alignment>, or <portfolios>.
        - Limit to 3-5 queries for focus and relevance.
        - In the thought process, link each query to the inputs and roadmap needs.
        - Keep queries and explanations clear and concise.
        - Do not include any text or markdown outside the JSON structure.
    """

    userPrompt = f"""
        Generate web search queries to support roadmap creation based on the <conversation>. 
        Use <persona> to align queries with customer needs, <org_alignment>to ensure queries support organizational priorities,
        and <portfolios> to tailor queries to relevant portfolio goals.
        
        Return **only** valid JSON with queries and thought process.
    """

    return ChatCompletion(
        system=f"You are an expert roadmap preparation agent.\n\n {systemPrompt}",
        prev=[],
        user=userPrompt
    )



def roadmapScopeTimelinePrompt(roadmap_details, internal_knowledge=None, persona=None, portfolios=None, conversation=None, user_id=None,files=None,solution_context=None,guidance=None) -> ChatCompletion:
    """Generate scope items and timeline for a roadmap in valid JSON format."""
    currentDate = CURRENT_DATE
    language = UsersDao.fetchUserLanguage(user_id = user_id)
    files_instructions = uploaded_files_prompt(files)

    print("language ---", language)
    
    # Format guidance text if provided
    guidance_text = ""
    has_guidance = guidance and guidance.get("has_guidance") and guidance.get("prompt_section")
    if has_guidance:
        guidance_text = f"\n{guidance['prompt_section']}\n"
    
    systemPrompt = f"""
        You are a strategic roadmap generation agent. Your task is to produce a **single detailed scope item** and associated **timeline** in valid JSON format. 
        Leverage organizational intelligence, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
        {guidance_text}
        
        The intent is to create a scope item that is versatile, detailed, and dynamically adapted to the roadmap context, inputs, and inferred needs.
        Leverage organizational intelligence, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
        
        The intent is to create a scope item that is versatile, detailed, and dynamically adapted to the roadmap context, inputs, and inferred needs.
        
        **No explanations or text outside the JSON block.**

        ### Core Mandates:
        - Use **conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
            1. **roadmap_details**: Objective signals, naming, narrative cues.
            2. **trmeric_knowledge_fabric**: The trmeric_knowledge_fabric is a streamlined, interconnected layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews,
                and strategic priorities. It empowers the LLM to synthesize focused, strategically aligned roadmap scope items and timelines by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
            2. **trmeric_knowledge_fabric**: The trmeric_knowledge_fabric is a streamlined, interconnected layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews,
                and strategic priorities. It empowers the LLM to synthesize focused, strategically aligned roadmap scope items and timelines by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
            3. **persona**: Customer expectations and pain points.
            4. **portfolios**: Function/domain anchors and guardrails.
            
        - Deeply integrate **persona** {persona} to align scope with customer pain points, goals, and expected outcomes.
        - Align with **portfolios** {portfolios} to ensure scope supports portfolio objectives, respects guardrails, and leverages synergies.
        - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought process, and prioritize feasibility.


        ### Inference Logic:
        - Derive roadmap direction by synthesizing:
            - **roadmap_details**: Extract intent from objectives, scope hints, and narrative.
            - **trmeric_knowledge_fabric**: Identify gaps, risks, and strategic priorities.
            - **portfolios**: Anchor to portfolio goals, constraints, and cross-project dependencies.
            - **persona**: Reflect customer needs, behaviors, and success criteria.
            
        - Proactively infer missing components, balancing ambition with feasibility.

        ### Scope Item Instructions:
        - Generate **one single scope item** inside `scope_item`, rendered as a **fully detailed Markdown string** within the `name` field.
        - Begin with a clear, descriptive header (e.g., '## Enhance Service Partner Network with AI-Driven Workflow Platform') to summarize the scope and intent.
        - Dynamically craft versatile, detailed sections tailored to the roadmap context, inputs, and inferred needs:
            - Include core sections like scope overview, requirements, constraints, risks, and exclusions, but adapt their focus, naming, and depth based on inputs.
            - Add relevant, context-driven sections (e.g., success metrics, technical needs, stakeholders, adoption strategy) as inferred from conversation, roadmap_details, persona, and portfolios.
            - Ensure each section is highly detailed, specific, and aligned with customer needs, portfolio goals, and strategic intent.
        - Emphasize precision, feasibility, and adaptability—address edge cases, customer expectations, and portfolio fit with clear boundaries and robust details.
        - Limit yourself to 250-300 words for the entire scope item, ensuring quality,clarity, and relevance over quantity.

        ### Timeline Instructions:
        - Set timeline of roadmap based on **conversation** {conversation} if relevant details are present; give the `start_date` and `end_date` based on complexity, team load, and project nature.
        - Calculate `min_time_value` and `min_time_value_type` logically (e.g., 2 months = value: 2, type: 3).
        - Align estimates with current date: **{currentDate}**

        ### Thought Process Instructions:
        - Document reasoning using **markdown bullet points** with **bold headers** and brief (1-2 sentence) descriptions.
        {"" if not has_guidance else '''
        - **Two-section format** for each thought process field:

        #### For **thought_process_behind_scope**:
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        - **Pattern Insights**: Direct evidence from similar roadmaps and their scope approaches
        - **Success Metrics**: Specific scope strategies proven successful in historical patterns
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        - **Conversation Analysis**: How user requirements shape scope decisions
        - **Portfolio Alignment**: Scope fit with organizational capabilities and constraints
        - **Assumptions**: Where scope details are inferred beyond available data
        ```
        
        #### For **thought_process_behind_timeline**:
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        - **Historical Evidence**: Specific durations and phasing from historical roadmaps
        - **Proven Patterns**: Sequencing and dependency patterns from similar projects
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        - **Complexity Assessment**: Timeline justification based on project scope and constraints
        - **Resource Considerations**: How organizational capacity influences timeline decisions
        - **Risk Factors**: Timeline assumptions and potential impact on feasibility
        ```
        
        **Knowledge Section Guidelines:**
        - Quote EXACTLY from the Strategic Guidance above - do not paraphrase or extend
        - NEVER invent roadmap names, patterns, or data not stated in the guidance
        - Cite specific roadmap names and metrics from the provided guidance
        
        **Reasoning Section Guidelines:**
        - Focus on how current inputs (conversation, persona, portfolios) inform decisions
        - Flag assumptions and confidence levels for inferred details
        - Keep descriptions concise (1-2 sentences per bullet)
        '''}
        {"" if has_guidance else '''
        - For each thought process field, provide markdown bullet points (no section header):
        - **Conversation Analysis**: How user requirements shape scope/timeline decisions
        - **Portfolio Alignment**: Scope fit with organizational capabilities and constraints
        - **Complexity Assessment**: Timeline justification based on project scope and constraints
        - **Resource Considerations**: How organizational capacity influences timeline decisions
        - **Assumptions**: Where details are inferred beyond available data
        - Keep descriptions concise (1-2 sentences per bullet)
        '''}

        ### Input Summary:
        <org_context>
            1. Roadmap Details: {roadmap_details}
            2. Trmeric Knowledge Fabric: {internal_knowledge or 'None provided'}
            2. Trmeric Knowledge Fabric: {internal_knowledge or 'None provided'}
            3. Customer Persona: {persona}
            4. Portfolios: {portfolios}
            5. Conversation: {conversation}
            6. Uploaded Files: {files or 'None provided'}
            7. Solution Context: {solution_context or 'None provided'}
        </org_context>

        ### Output Format:
        Return **only** the following JSON structure:

        ```json
        {{
            "scope_item": [
                {{
                    "name": "<a single scope item as a detailed, descriptive Markdown string, starting with a header summarizing the scope, followed by versatile, detailed, and dynamically adapted sections, aligned with roadmap_details, persona, portfolios, and conversation>"
                }}
            ],
            "thought_process_behind_scope": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence) description, quoting *relevant trmeric_knowledge_fabric*, explaining influence of roadmap_details, persona, portfolios, conversation; justify section selection, content depth, assumptions, and alignment>",
            "start_date": "<YYYY-MM-DD>",
            "end_date": "<YYYY-MM-DD>",
            "min_time_value": <integer value refer to **conversation** if user has mentioned timeline>,
            "min_time_value_type": <1=days, 2=weeks, 3=months, 4=years (refer **conversation** if user has given inputs)>,
            "thought_process_behind_timeline": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence) description, quoting **conversation**, **trmeric_knowledge_fabric**, and justifying based on conversation and roadmap_details only>"
        }}
        ```

        ### Guidelines:
        - Timeline: Align with Current Date: {currentDate}.
        - Ground the scope and timeline in **roadmap_details**, enriched by trmeric_knowledge_fabric, persona, portfolios, and conversation.
        - Ensure the scope item's 'name' field is a single Markdown string starting with a descriptive header, followed by versatile, detailed, and dynamically crafted sections tailored to context.
        - Ensure the timeline is realistic, considering team load, project constraints, and organizational priorities from **trmeric_knowledge_fabric** and **portfolios**.
        - Produce concise, prioritized, and traceable thought processes in Markdown bullet points, with **bold headers** and brief descriptions, linking decisions to inputs and flagging assumptions.
    """
    systemPrompt += f"\n{files_instructions}" if files_instructions else ""
    systemPrompt += f"""\n\nSolution Context: {solution_context}. These are existing demand solutions which user has created utilize it in scope creation.""" if solution_context else ""

    userPrompt = f"""
        Generate a single scope item and timeline for the roadmap based on **roadmap_details** {roadmap_details}. 
        Use **trmeric_knowledge_fabric** {internal_knowledge or 'None provided'} for organizational context, **persona** {persona} for customer alignment, **portfolios** {portfolios} for portfolio alignment, and **conversation** {conversation} for strategic alignment.
        Return **only** valid JSON as specified in the system prompt, including a detailed scope item, thought process for the scope, timeline, with thought processes formatted as comprehensive Markdown bullet points (each with a **bold header** and detailed description providing thorough analysis).
        
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


   
   
def roadmapObjOrgStrategyKeyResultsPrompt(roadmap_details, conversation, internal_knowledge, org_strategy, user_id=None,files=None, guidance=None) -> ChatCompletion:
    """Generate objectives, organizational strategy alignment, and key results for a roadmap in valid JSON format."""
    """Generate objectives, organizational strategy alignment, and key results for a roadmap in valid JSON format."""
    
    language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("language ---", language)

    files_instructions = uploaded_files_prompt(files)
    print("---debug roadmapObjOrgStrategyKeyResultsPrompt----","\n\nInstructions: ",files_instructions)
    
    guidance_text = ""
    has_guidance = guidance and guidance.get("has_guidance") and guidance.get("prompt_section")
    if has_guidance:
        guidance_text = f"\n{guidance['prompt_section']}\n"

    systemPrompt = f"""
        **Craft vivid, actionable objectives, strategy alignment, and key results for an epic roadmap!**
        Your task is to produce detailed **objectives**, **organizational strategy alignment**, and **key results** in valid JSON format. 
        Leverage organizational intelligence, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
        
        The intent is to create objectives that are vivid and actionable, key results that are measurable and diverse, and strategy alignment that reflects organizational priorities.
        **No explanations or text outside the JSON block.**
        
        {guidance_text}

        ### Core Mandates:
        - Use **Conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
            1. **Roadmap Details**: Roadmap name, description, and narrative cues.
            2. **Trmeric Knowledge Fabric**: A streamlined, interconnected layer of organizational intelligence, encapsulating summarized portfolio-level project insights, 
                 including high-level goals, project overviews, and strategic priorities. It empowers the LLM to synthesize focused, strategically aligned roadmap items by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
            3. **Org Strategy**: Strategic priorities and alignment goals.
            4. **Strategic Guidance**: Use the provided guidance to align objectives and key results with proven success factors and risk mitigation strategies.
            
        - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought processes, and prioritize feasibility.

        ### Inference Logic:
        - Derive roadmap direction by synthesizing:
            - **Roadmap Details**: Extract intent from objectives and narrative.
            - **Trmeric Knowledge Fabric**: Identify gaps, risks, and strategic priorities.
            - **Org Strategy**: Anchor to organizational priorities and goals.
            - **Conversation**: Reflect user intent and success criteria.
            
        - Proactively infer missing components, balancing ambition with feasibility.

        ### Objectives Instructions:
        - Generate 3-4 vivid, execution-focused goals in a comma-separated list within the `objectives` field (e.g., "Unify workflows with Jira and Azure DevOps integrations, enhance visibility with AI-driven analytics, improve collaboration through stakeholder feedback, achieve 25-30% cycle time reduction").
        - Ensure only the first letter in the objective string is Capitalized.
        - Ensure each objective is descriptive (e.g., specify tools or approaches), actionable (e.g., clear execution path), and aligned with Conversation, Roadmap Details, and Org Strategy.
        - Include measurable targets only when supported by inputs (e.g., "25-30% cycle time reduction" from Conversation), reserving specific metrics for key results unless integral to the goal.
        - Ensure objectives inform later planning steps (e.g., integration tasks, adoption strategies).

        ### Key Results Instructions:
        - Generate 3-4 measurable outcomes within the `key_results` array, each with:
            - **key_result**: A detailed, descriptive outcome tied to objectives, including specifics like timelines, tools, stakeholders, or methods (e.g., "Achieve a 25-30% reduction in cycle time via Jira/ADO integrations by Q3 2025 using phased rollouts for product teams").
            - **baseline_value**: Numerical or measurable target only (e.g., "25-30%"). If not provided, infer from Conversation, Trmeric Knowledge Fabric, or industry standards, citing the source in the thought process.
        - Ensure diversity across technical (e.g., integration reliability), business (e.g., deployment frequency), and operational (e.g., adoption rate) outcomes.
        - Avoid vague metrics (e.g., "improved alignment"); use numerical proxies (e.g., "20% alignment score increase") with justification.

        - ### Org Strategy Alignment Instructions: Choose only the relevant priorities across both tag types.
            - org → exact from <customer_level_org_strategies>
            - portfolio → inferred from <portfolio_context>, i.e. <portfolio_context>.strategic_priorities
        - Ensure that only right ones are created.

        ### Thought Process Instructions:
        - Document reasoning using **markdown bullet points** with **bold headers** and brief (1-2 sentence) descriptions.
        {"" if not has_guidance else '''
        - **Two-section format** for each thought process field:

        #### For **thought_process_behind_objectives**:
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        - **Pattern Insights**: Specific objectives and outcomes from similar successful roadmaps
        - **Success Metrics**: Quantitative improvements achieved by historical patterns
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        - **Conversation Alignment**: How user requirements translate into actionable objectives
        - **Strategic Focus**: Objective prioritization based on organizational context
        - **Assumptions**: Where objectives are inferred beyond stated requirements
        ```
        
        #### For **thought_process_behind_key_results**:
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        - **Historical Evidence**: Specific metrics and targets achieved in similar roadmap patterns
        - **Proven Benchmarks**: Historical performance ranges and measurement approaches
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        - **Metric Selection**: Why chosen KPIs align with objectives and organizational capability
        - **Target Justification**: How baseline values and targets reflect realistic expectations
        - **Measurement Strategy**: Approach to tracking and validating key results
        ```
        
        #### For **thought_process_behind_org_strategy_align**:
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        - **Historical Patterns**: How similar roadmaps aligned with organizational strategies
        - **Success Evidence**: Specific strategy connections that drove successful outcomes
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        - **Priority Mapping**: Why selected strategies best match current roadmap focus
        - **Strategic Fit**: How objectives support broader organizational goals
        ```
        
        **Knowledge Section Guidelines:**
        - Quote EXACTLY from the Strategic Guidance above - do not paraphrase or extend
        - NEVER fabricate roadmap names, KPIs, or metrics not in the guidance
        - Cite specific roadmap names and quantitative evidence from the provided guidance
        
        **Reasoning Section Guidelines:**
        - Focus on how current context drives decisions
        - Justify selections based on conversation, roadmap details, and organizational fit
        - Keep descriptions focused and actionable
        '''}
        {"" if has_guidance else '''
        - For each thought process field, provide markdown bullet points (no section header):
        - For objectives: **Goal Selection**, **Strategic Alignment**, **Conversation Context**, **Assumptions**
        - For key_results: **Metric Selection**, **Target Justification**, **Diversity Rationale**, **Measurement Approach**
        - For org_strategy_align: **Priority Mapping**, **Strategic Fit**, **Alignment Justification**
        - Each bullet: brief (1-2 sentence) explanation of reasoning
        - Keep descriptions concise and actionable
        '''}
            - Quote relevant Trmeric Knowledge Fabric and Org Strategy.
            - Justify selections and prioritization based on inputs and alignment with roadmap goals.
            - Flag assumptions if Org Strategy is inferred.

        ### Input Summary:
        - Roadmap Details: {roadmap_details}
        - Trmeric Knowledge Fabric: {internal_knowledge or 'None provided'}
        - Org Strategy: {org_strategy}
        - Conversation: {conversation}
        - Files: {files if files else 'None'}

        ### Output Format:
        ```json
        {{
            "objectives": "<comma-separated list of 3-4 vivid, execution-focused goals (keep first letter of sentence in Capital only, e.g., 'Reduce supply chain cycle time by 20% through process mining, enhance workflow visibility with real ascendancy via real-time analytics, improve operational efficiency by automating subprocesses')>",
            "thought_process_behind_objectives": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Conversation; justify goal selection, content focus, assumptions, and alignment>",
            
            "key_results": [
                {{
                    "key_result": "<measurable outcome>",
                    "baseline_value": "<realistic numerical or measurable target for this key result (10-15 words)>"
                }}
            ],
            "thought_process_behind_key_results": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Conversation; justify metrics, diversity, assumptions, and alignment>",
            "org_strategy_align": ["<exact priority from Org Strategy, e.g., 'Financial Targets'>"],
            "thought_process_behind_org_strategy_align": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite org strategy patterns from similar roadmaps (e.g., 'Roadmap \\'a\\' aligned with cost reduction strategy...'); quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Conversation; justify selections, prioritization, and alignment>"
        }}
        ```

        ### Guidelines:
        - Ground the objectives, key results, and org strategy alignment in Roadmap Details, enriched by Trmeric Knowledge Fabric, Org Strategy, and Conversation.
        - Ensure thought processes are comprehensive and detailed, prioritized, and traceable in Markdown bullet points, with **bold headers** and thorough descriptions, linking decisions to inputs and flagging assumptions.
    """

    systemPrompt += f"""{files_instructions if files else ''}"""

    userPrompt = f"""
        Generate objectives, organizational strategy alignment, and key results for the roadmap based on Roadmap Details {roadmap_details}. 
        Refer to specific details of the guidance given in previous roadmaps in your references. 
        Return **only** valid JSON as specified in the system prompt, including objectives, thought process for objectives, key results, thought process for key results, org strategy alignment, and thought process for org strategy alignment, with thought processes formatted using comprehensive Markdown with rich formatting, detailed analysis, and thorough coverage as appropriate.
        
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(
        system=f"You are an expert roadmap creation agent using organizational knowledge and strategic inputs.\n\n {systemPrompt}",
        prev=[],
        user=userPrompt
    )





def roadmapConstraintsPortfolioCategoryPrompt(roadmap_details, internal_knowledge, portfolios, conversation, persona) -> ChatCompletion:
    """Generate constraints, portfolio details, and roadmap categories in valid JSON format."""
    
    systemPrompt = f"""
        **Craft precise, actionable constraints, portfolio details, and roadmap categories for an epic roadmap!**
        Your task is to produce detailed **constraints**, **portfolio details**, and **roadmap categories** in valid JSON format. 
        Leverage organizational intelligence, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
        
        The intent is to create constraints that are specific and measurable, portfolio selections that are prioritized, and roadmap categories that are comprehensive and aligned with project goals.
        Your task is to produce detailed **constraints**, **portfolio details**, and **roadmap categories** in valid JSON format. 
        Leverage organizational intelligence, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
        
        The intent is to create constraints that are specific and measurable, portfolio selections that are prioritized, and roadmap categories that are comprehensive and aligned with project goals.

        **No explanations or text outside the JSON block.**

        ### Core Mandates:
        - Use **Conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
            1. **Roadmap Details**: Objective signals, narrative cues.
            2. **Trmeric Knowledge Fabric**: A streamlined, interconnected layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews, and strategic priorities. 
                It empowers the LLM to synthesize focused, strategically aligned roadmap items by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
            3. **Portfolios**: Function/domain anchors and guardrails.
            4. **Persona**: Customer expectations and pain points.
            
            
        - Deeply integrate **Persona** {persona} to align constraints and categories with customer pain points, goals, and expected outcomes.
        - Align with **Portfolios** {portfolios} to ensure selections support portfolio objectives, respect guardrails, and leverage synergies.
        - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought processes, and prioritize feasibility.

        ### Inference Logic:
        - Derive roadmap direction by synthesizing:
            - **Roadmap Details**: Extract intent from objectives and narrative.
            - **Trmeric Knowledge Fabric**: Identify gaps, risks, and strategic priorities.
            - **Portfolios**: Anchor to portfolio goals, constraints, and cross-project dependencies.
            - **Persona**: Reflect customer needs, behaviors, and success criteria.
            - **Conversation**: Reflect user intent and success criteria.
            
        - Proactively infer missing components, balancing ambition with feasibility.

        ### Constraints Instructions:
        - Generate 3-4 constraints within the `constraints` array, each with:
            - **constraint**: A specific, measurable limitation impacting project execution (e.g., "Limited high-quality process data may reduce mining accuracy by 15%").
            - **tag**: One of Cost, Resource, Risk, Scope, Quality, Time, aligned with the limitation’s nature.
        - Ensure constraints are actionable, tied to Roadmap Details or Conversation, and relevant to project goals.
        - Include measurable impacts (e.g., "2-3 month delay") with justification from inputs or inferences.

        ### Portfolio Instructions:
        - Select up to 4 most relevant portfolios from **Portfolios** within the `portfolio` array, using exact `id` and `name`.
        - Prioritize based on alignment with Conversation, Roadmap Details, and Persona (e.g., portfolios supporting efficiency for a cost-focused stakeholder).

        ### Roadmap Category Instructions:
        - Generate 3-4 categories within the `roadmap_category` array, reflecting technical, business, and functional aspects (e.g., "Process Mining", "Supply Chain Optimization", "Data Analytics").
        - Ensure categories are specific, aligned with Roadmap Details, Persona, and project goals, and comprehensive enough to guide further planning.

        ### Thought Process Instructions:
        - Document reasoning for each section (constraints, portfolio, roadmap category) in concise Markdown bullet points (up to 4 points per section, max).
        - **Format Requirement**: Each bullet must start with a **bold header** summarizing the key decision or input, followed by a brief (1-2 sentence, 10-20 words) description explaining its influence, justification, or assumption. Avoid verbose explanations to optimize rendering speed.
        - Structure example:
            - **Header**: Brief description of decision or input influence.
            - **Header**: Brief description of decision or input influence.
        - For **thought_process_behind_constraints**:
            - Quote relevant Trmeric Knowledge Fabric and input signals (e.g., Roadmap Details, Persona, Portfolios, Conversation).
            - Justify constraint selection, impact, and alignment with project goals.
            - Flag assumptions for missing or vague data, noting confidence and trade-offs.
        - For **thought_process_behind_portfolio**:
            - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., "Roadmap 'a' selected Operations portfolio for digitization...").
            - Quote relevant Trmeric Knowledge Fabric and input signals.
            - Justify selections and prioritization based on alignment with goals.
            - Flag assumptions for portfolio relevance or inferred priorities.
        - For **thought_process_behind_roadmap_category**:
            - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., "Roadmap 'a' focused on Factory Digitization and Process Automation...").
            - Quote relevant Trmeric Knowledge Fabric and input signals.
            - Justify category selection, content focus, and relevance to project goals.
            - Flag assumptions for inferred categories or alignment.

        ### Input Summary:
        - Roadmap Details: {roadmap_details}
        - Portfolios: {portfolios}
        - Persona: {persona}
        - Conversation: {conversation}
        ### Core Mandates:
        - Use **Conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
            1. **Roadmap Details**: Objective signals, narrative cues.
            2. **Trmeric Knowledge Fabric**: A streamlined, interconnected layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews, and strategic priorities. 
                It empowers the LLM to synthesize focused, strategically aligned roadmap items by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
            3. **Portfolios**: Function/domain anchors and guardrails.
            4. **Persona**: Customer expectations and pain points.
            
        - Deeply integrate **Persona** {persona} to align constraints and categories with customer pain points, goals, and expected outcomes.
        - Align with **Portfolios** {portfolios} to ensure selections support portfolio objectives, respect guardrails, and leverage synergies.
        - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought processes, and prioritize feasibility.

        ### Inference Logic:
        - Derive roadmap direction by synthesizing:
            - **Roadmap Details**: Extract intent from objectives and narrative.
            - **Trmeric Knowledge Fabric**: Identify gaps, risks, and strategic priorities.
            - **Portfolios**: Anchor to portfolio goals, constraints, and cross-project dependencies.
            - **Persona**: Reflect customer needs, behaviors, and success criteria.
            - **Conversation**: Reflect user intent and success criteria.
            
        - Proactively infer missing components, balancing ambition with feasibility.

        ### Constraints Instructions:
        - Generate 3-4 constraints within the `constraints` array, each with:
            - **constraint**: A specific, measurable limitation impacting project execution (e.g., "Limited high-quality process data may reduce mining accuracy by 15%").
            - **tag**: One of Cost, Resource, Risk, Scope, Quality, Time, aligned with the limitation’s nature.
        - Ensure constraints are actionable, tied to Roadmap Details or Conversation, and relevant to project goals.
        - Include measurable impacts (e.g., "2-3 month delay") with justification from inputs or inferences.

        ### Portfolio Instructions:
        - Select up to 4 most relevant portfolios from **Portfolios** within the `portfolio` array, using exact `id` and `name`.
        - Prioritize based on alignment with Conversation, Roadmap Details, and Persona (e.g., portfolios supporting efficiency for a cost-focused stakeholder).

        ### Roadmap Category Instructions:
        - Generate 3-4 categories within the `roadmap_category` array, reflecting technical, business, and functional aspects (e.g., "Process Mining", "Supply Chain Optimization", "Data Analytics").
        - Ensure categories are specific, aligned with Roadmap Details, Persona, and project goals, and comprehensive enough to guide further planning.

        ### Thought Process Instructions:
        - Document reasoning for each section (constraints, portfolio, roadmap category) in concise Markdown bullet points (up to 4 points per section, max).
        - **Format Requirement**: Each bullet must start with a **bold header** summarizing the key decision or input, followed by a brief (1-2 sentence, 10-20 words) description explaining its influence, justification, or assumption. Avoid verbose explanations to optimize rendering speed.
        - Structure example:
            - **Header**: Brief description of decision or input influence.
            - **Header**: Brief description of decision or input influence.
        - For **thought_process_behind_constraints**:
            - Quote relevant Trmeric Knowledge Fabric and input signals (e.g., Roadmap Details, Persona, Portfolios, Conversation).
            - Justify constraint selection, impact, and alignment with project goals.
            - Flag assumptions for missing or vague data, noting confidence and trade-offs.
        - For **thought_process_behind_portfolio**:
            - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., "Roadmap 'a' selected Operations portfolio for digitization...").
            - Quote relevant Trmeric Knowledge Fabric and input signals.
            - Justify selections and prioritization based on alignment with goals.
            - Flag assumptions for portfolio relevance or inferred priorities.
        - For **thought_process_behind_roadmap_category**:
            - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., "Roadmap 'a' focused on Factory Digitization and Process Automation...").
            - Quote relevant Trmeric Knowledge Fabric and input signals.
            - Justify category selection, content focus, and relevance to project goals.
            - Flag assumptions for inferred categories or alignment.

        ### Input Summary:
        - Roadmap Details: {roadmap_details}
        - Trmeric Knowledge Fabric: {internal_knowledge or 'None provided'}
        - Portfolios: {portfolios}
        - Persona: {persona}
        - Conversation: {conversation}

        ### Output Format:
        Return **only** the following JSON structure:

        Return **only** the following JSON structure:

        ```json
        {{
            "constraints": [
                {{
                    "constraint": "<rich, contextual limitation or constraint across dimensions such as Resource, Scope , Quality, Technology, Complexities around integrations, external factors, Cost etc. , 
                        e.g.,'Limited high-quality process data may reduce mining accuracy by 15%'>",
                    "tag": "<Cost, Resource, Risk, Scope, Quality, Time>"
                }}
            ],
            "thought_process_behind_constraints": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify constraint selection, impact, assumptions, and alignment>",
            "thought_process_behind_constraints": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify constraint selection, impact, assumptions, and alignment>",
            "portfolio": [
                {{
                    "id": "<exact id from Portfolios>",
                    "name": "<exact name from Portfolios>"
                    "id": "<exact id from Portfolios>",
                    "name": "<exact name from Portfolios>"
                }}
            ],
            "thought_process_behind_portfolio": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., 'Roadmap \'a\' selected Operations portfolio for digitization...'); quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify selections, prioritization, and alignment>",
            "thought_process_behind_portfolio": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., 'Roadmap \'a\' selected Operations portfolio for digitization...'); quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify selections, prioritization, and alignment>",
            "roadmap_category": ["<comma-separated technical, business, or functional categories, e.g., 'Process Mining, Supply Chain Optimization, Data Analytics'>"],
            "thought_process_behind_roadmap_category": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., 'Roadmap \'a\' focused on Factory Digitization and Process Automation...'); quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify category selection, content focus, assumptions, and alignment>"
            "thought_process_behind_roadmap_category": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., 'Roadmap \'a\' focused on Factory Digitization and Process Automation...'); quoting relevant Trmeric Knowledge Fabric, explaining influence of Roadmap Details, Persona, Portfolios, Conversation; justify category selection, content focus, assumptions, and alignment>"
        }}
        ```

        ### Guidelines:
        - Ground the constraints, portfolio selections, and roadmap categories in Roadmap Details, enriched by Trmeric Knowledge Fabric, Portfolios, Persona, and Conversation.
        - Ensure thought processes are comprehensive and detailed, prioritized, and traceable in Markdown bullet points, with **bold headers** and thorough descriptions, linking decisions to inputs and flagging assumptions.
    """

    userPrompt = f"""
        Generate constraints, portfolio details, and roadmap categories for the roadmap based on Roadmap Details {roadmap_details}. 
        Use and refer to Portfolios {portfolios} for portfolio alignment, Persona {persona} for customer alignment, and Conversation {conversation} for user intent.
        Refer to specific details of the guidance given on previous roadmaps in your references. 
        Return **only** valid JSON as specified in the system prompt, including constraints, thought process for constraints, portfolio details, thought process for portfolio, roadmap categories, and thought process for roadmap categories, with thought processes formatted using comprehensive Markdown with rich formatting, detailed analysis, and expansive coverage as needed.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )





def updateRoadmapEstimationPrompt(roadmap_details, currency_format, language="English", context=None) -> ChatCompletion:
    # language = UsersDao.fetchUserLanguage(user_id=user_id) if user_id else "English"
    print("language ---", language)

    systemPrompt = f"""
        You are a strategic roadmap generation agent specializing in timeline analysis and non-labor resource planning. Your task is to produce a JSON output with an evidence-based timeline rationale and specific, context-aligned non-labor resource recommendations, ensuring strategic alignment and realistic, industry-standard cost estimates driven by roadmap_type within defined cost bands.

        **No explanations or text outside the JSON block.**

        ### Core Mandates:
        - Use **Roadmap Details** {roadmap_details} to define intent, including:
            1. Roadmap Title, Type, Description, Objectives, Key Results
            2. Portfolio Categories, Strategic Constraints, Scope
            3. Organizational Strategy Alignment
            4. Key Milestones: Start Date, End Date, `roadmap_min_time`, `roadmap_min_time_value_type` (1 = days, 2 = weeks, 3 = months, 4 = years)
        - Use **Currency format** {currency_format} strictly; default to USD ($) if None.
        - Handle edge cases: Infer missing/vague inputs logically based on roadmap_type; flag assumptions in thought process; prioritize feasibility to avoid inflated costs.

        ## Operating Principles
        ### 0) Project Type & Delivery Model
        - Classify work based on `roadmap_type` and `scope`:
          - Roadmap type can be: "Project","Program","Enhancement","New Development","Enhancements or Upgrade","Consume a Service","Support a Pursuit","Acquisition","Global Product Adoption","Innovation Request for NITRO","Regional Product Adoption","Client Deployment", "Defect","Change","Epic","Feature","Story"
          - Acknowledge this and based on timeline classify it and use for estimation.
                (≤ 5 business days)
                (≤ 2–3 weeks)
                (≤ 8–10 weeks)
                (≤ 6 months)
                (> 6 months, multi-workstream)
        - Infer delivery style (Agile/Iterative vs Phase-Gated) from timing, scope clarity, constraints.

        ### 1) Choose Estimation Technique(s)
        - Select method(s) based on `roadmap_type` and `scope`:
          - Analogous/Expert Judgment: For similar past work (e.g., tax platform upgrades).
          - Parametric: Scale by drivers (e.g., #integrations × cost/integration).
          - Three-Point (PERT): For uncertainty; E = (O+4M+P)/6.
          - Agile Velocity: Story Points ÷ Velocity → Sprints → Costs.
          - Time-boxed Spikes: For unknown tech feasibility.
        - Include contingency buffer (5–15% for enhancements) in thought process, not base estimates.

       

        ### Inference Logic:
        - Derive timeline and resource recommendations by synthesizing:
            - **Roadmap Details**: Objectives, key results, milestones.
            - **Portfolio Categories**: Align with portfolio goals.
            - **Strategic Alignment**: Reflect organizational priorities.
            - **Roadmap Type**: Scale estimates appropriately (Tiny = minimal cost,Medium,  Large = higher cost).
        - Proactively infer missing components, but flag assumptions.

        ### Timeline Rationale Instructions:
        - Extract exact `start_date` and `end_date` from Roadmap Details.
        - Justify timeline with milestone alignment, phase breakdown, and buffer.
        - Provide comprehensive reasoning with detailed analysis in multiple bullets as needed.


        - Info about company and already existing solutions:
            <context>
            {context}
            </context>

        ## Non-Labor Team Recommendations Instructions:
        - Recommend 3–4 non-labor resources (`labour_type: 2`) in `non_labour_team`:
          - Vendor-specific (e.g., 'AWS Glue for data integration').
          - Tied to deliverables (e.g., automation, compliance), constraints (e.g., cost), or portfolio needs (e.g., AI, Tax).
          - `estimate_value` in given currency, within roadmap_type cost bands.
          - **Do not include tools or solutions already present in Company Context.**  
          - If an item is already covered by context, exclude it from the JSON list.  
          - Prefer extensions, optimizations, or complementary resources instead.  
          
        - Return an empty array if no new resources are required.
        

        ## Thought Process Instructions:
        - Document reasoning separately for timeline and non-labor.
        - For **non-labor thought process**, explicitly explain how company context was applied to filter out duplicates and leverage existing assets.
        - Acknowledge Reinforcement Rules: highlight learning, adjustments, trade-offs.

        ### Output Format:
        ```json
        {{
            "start_date": "<exact given start date from Roadmap Details>",
            "end_date": "<exact given end date from Roadmap Details>",
            "thought_process_behind_timeline": "<Markdown bullet points>",
            "non_labour_team": [
                {{
                    "name": "<specific resource>",
                    "estimate_value": <integer in given currency format>,
                    "labour_type": 2
                }}
            ],
            "thought_process_behind_non_labor_team": "<Markdown bullet points>"
        }}
        ```

        ### Guidelines:
        - Timeline: Match Roadmap Details dates; align with phases, milestones, constraints. 
        - Non-Labor: 3-4 max resources only, costs within `roadmap_type` bands, Filter through company context — no duplicates.  
        - Thought Process: Justify exclusion of context items and selection of new ones.  
        - Output in {language}.
    """

    userPrompt = f"""
        Generate a timeline rationale and non-labor resource recommendations for the roadmap based on Roadmap Details and Company Context.
        Return **only** valid JSON as specified.
        - In `non_labour_team`: strictly exclude resources already present in context. Suggest only new or complementary items.  
        - In `thought_process_behind_non_labor_team`: explicitly explain how context was applied and why some resources were excluded.  
        Use concise Markdown bullets. Respond in {language}.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


    
    
# def updateRoadmapCanvasPrompt(roadmap_details, internal_knowledge, portfolios, org_strategy, currency_format) -> ChatCompletion:
    
#     currentDate = CURRENT_DATE
#     systemPrompt = f"""
#         You are a strategic roadmap creation agent tasked with updating an existing roadmap canvas in JSON format. 
#         The user has requested enhancements to enrich all sections while preserving the core structure and intent, prioritizing user modifications in **Roadmap Details**.
    
    
def updateRoadmapCanvasPrompt(roadmap_details, internal_knowledge, portfolios, org_strategy, currency_format) -> ChatCompletion:
    
    currentDate = CURRENT_DATE
    systemPrompt = f"""
        You are a strategic roadmap creation agent tasked with updating an existing roadmap canvas in JSON format. 
        The user has requested enhancements to enrich all sections while preserving the core structure and intent, prioritizing user modifications in **Roadmap Details**.

        **Trmeric Knowledge Fabric**: A streamlined layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews, and strategic priorities. It enables the LLM to synthesize focused, strategically aligned roadmap items by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
        **Trmeric Knowledge Fabric**: A streamlined layer of organizational intelligence, encapsulating summarized portfolio-level project insights, including high-level goals, project overviews, and strategic priorities. It enables the LLM to synthesize focused, strategically aligned roadmap items by leveraging concise portfolio context, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.

        **Goal**: Update the roadmap canvas using **Roadmap Details** as the primary source (~80% weight), enriched with **Trmeric Knowledge Fabric** (**internal_knowledge**), **portfolios**, and **org_strategy** (~20% weight), ensuring alignment with **currency_format** for cost estimates.
                  Enhance all sections (name, description, objectives, key results, scope, constraints, timeline, non-labor team, portfolio, org strategy alignment, categories) with actionable, strategically aligned content.
        **Goal**: Update the roadmap canvas using **Roadmap Details** as the primary source (~80% weight), enriched with **Trmeric Knowledge Fabric** (**internal_knowledge**), **portfolios**, and **org_strategy** (~20% weight), ensuring alignment with **currency_format** for cost estimates.
                  Enhance all sections (name, description, objectives, key results, scope, constraints, timeline, non-labor team, portfolio, org strategy alignment, categories) with actionable, strategically aligned content.

        **Output Requirement**: Render strictly in JSON format as specified below, with no explanations or text outside the JSON block.

        ### Core Instructions:
        - **Primary Source**: Use **Roadmap Details** (title, description, objectives, key results, scope, category, portfolio, org strategy alignment, timeline) as the primary driver, prioritizing user-modified fields (~80% weight).
        - **Enrichment**: Leverage **Trmeric Knowledge Fabric** for portfolio-level insights, bridging gaps with logical inference and aligning with customer needs and portfolio objectives (~20% weight).
        - **Update Logic**:
          - Update every field in the roadmap JSON based on **Roadmap Details**, preserving core intent while enriching with specifics, metrics, and tasks.
          - Detect and prioritize user-modified fields (e.g.,description, objectives, scope, timeline) in **Roadmap Details**.
          - Align updates with **Trmeric Knowledge Fabric**, **portfolios**, and **org_strategy**.
          - Set `last_updated` to {currentDate}.
        - **Validation**:
            - Ensure fields adhere to JSON structure and data types.
            - Validate completeness (e.g., required fields: title, description, start_date, end_date) and consistency (e.g., status: "Not Started", "In Progress", "Completed"; priority: "Low", "Medium", "High").
            - Handle edge cases (e.g., missing fields, invalid IDs) by inferring from **Trmeric Knowledge Fabric** or **org_strategy**, noting assumptions in thought processes.
        - **Idempotency**: Ensure consistent outputs for repeated actions with identical inputs.

        ### Roadmap Canvas Update Details:
        - **Roadmap Name**:
            - Update `roadmap_name` to a concise, descriptive title (5-10 words) reflecting **Roadmap Details** and **org_strategy**.
        - **Description**:
            - Update `description` to a clear statement (50-70 words) outlining purpose, scope, and strategic alignment.
            - Incorporate user changes from **Roadmap Details** and enrich with **Trmeric Knowledge Fabric** insights.
        
        - **Objectives**:
        - Update `objectives` with 3-4 vivid, execution-focused goals in a comma-separated list within the `objectives` field (e.g., "Unify workflows with Jira and Azure DevOps integrations, enhance visibility with AI-driven analytics, improve collaboration through stakeholder feedback, achieve 25-30% cycle time reduction").
        - Ensure only the first letter in the objective string is Capitalized.
        - Ensure goals are descriptive, actionable, and aligned with **Roadmap Details**, **Trmeric Knowledge Fabric**, **portfolios**, and **org_strategy**.
        
        - **Scope Item**:
        - Update one scope item in `scope_item` as a Markdown string (250-300 words) in the `name` field.
        - Include a header (e.g., "## AI-Driven Analytics Platform") and sections: overview, requirements, constraints, risks, out-of-scope, success metrics, technical needs.
        - Ensure precision, feasibility, and alignment with **Roadmap Details**, **Trmeric Knowledge Fabric**, and **org_strategy**.
        - **Key Results**:
          - Update 3-4 measurable outcomes in `key_results`, each with:
            - A `key_result` field with a vivid, specific, and strategically compelling description (e.g., "Boost user retention by 15% through personalized AI-driven notifications, enhancing customer loyalty").
            - A `baseline_value` reflecting current state or target (e.g., "Current 70% retention, targeting 85%").
            - Diverse metrics (e.g., user growth, revenue, latency) aligned with **Roadmap Details**, **Trmeric Knowledge Fabric**, and **org_strategy**.
            
        - **Timeline**:
          - Update `start_date`, `end_date`, `min_time_value`, and `min_time_value_type` based on **Roadmap Details** (e.g., urgency), **Trmeric Knowledge Fabric** (e.g., team load, project complexity), and **org_strategy** (e.g., strategic deadlines).
          - Ensure `start_date` is on or after {currentDate}.
          
        - **Non-Labor Team**:
          - Recommend exactly 3-4 non-labor resources (`labour_type: 2`) in `non_labour_team`, each:
            - Specific (e.g., "AWS RDS for workflow hosting").
            - Tied to a roadmap deliverable, constraint, or portfolio need.
            - Use **Currency format** {currency_format} to estimate the value for non-labor resources, if not present then use (USD) by default, based on vendor benchmarks (e.g., AWS, OneTrust) for a 12-month midsize project.
          - Return an empty `non_labour_team` array if **Roadmap Details** lacks resource needs, with justification in thought process.
          
        - **Constraints**:
          - Update 3-4 constraints in `constraints`, each with:
            - A specific, measurable limitation (e.g., "Team capacity limited to 3 engineers").
            - A `tag` (Cost, Resource, Risk, Scope, Quality, Time).
          - Ensure constraints are actionable, tied to **Roadmap Details** or **Trmeric Knowledge Fabric**, and relevant to project goals.
          
        - **Portfolio**:
          - Select up to 4 portfolios from **portfolios**, using exact `id` and `name`, prioritized by alignment with **Roadmap Details**.
        - **Org Strategy Alignment**:
          - Select 3-4 priorities from **org_strategy** in `org_strategy_align`, or infer from **Roadmap Details** or **Trmeric Knowledge Fabric** if missing, citing "Inferred" in thought process.
        - **Roadmap Categories**:
          - Update 3-4 categories in `roadmap_category` (e.g., "Data Analytics", "Automation") reflecting technical, business, and functional aspects, aligned with **Roadmap Details** and **Trmeric Knowledge Fabric**.

        ### Thought Process Instructions:
            - Document reasoning for each section (`objectives`, `scope_item`, `key_results`, `timeline`, `non_labour_team`, `portfolio`, `constraints`, `org_strategy_align`, `roadmap_category`) in comprehensive Markdown bullet points (provide as many points as needed for thorough analysis).
            - **Format Requirement**: Each bullet must start with a **bold header** summarizing the key decision or input, followed by a brief (1-2 sentence, 10-20 words) description explaining its influence, justification, or assumption. Avoid verbose explanations to optimize rendering speed.
        

        ### Input Data:
        - **Roadmap Details**: {roadmap_details}
        - Includes: Title, Description, Objectives, Key Results, Scope, Category, Portfolio, Org Strategy Alignment, Timeline.
        - **Trmeric Knowledge Fabric**: {internal_knowledge}
        - Portfolio-level insights, goals, and strategic priorities.
        - **Portfolios**: {portfolios}
        - **Org Strategy**: {org_strategy}
        - **Currency Format**: {currency_format}

        ### Output Format:
        ```json
        {{
            "roadmap_name": "<updated descriptive name>",
            "description": "<updated description of the roadmap in 50-70 words>",
            "objectives": "<comma-separated updated goals>",
            "thought_process_behind_objectives": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "scope_item": [
                {{"name": "<single Markdown string (250-300 words) with updated scope details, requirements, constraints, risks, out-of-scope>"}}
            ],
            "thought_process_behind_scope": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "key_results": [
                {{
                    "key_result": "<updated measurable outcome, vivid and compelling>",
                    "baseline_value": "<current state or target>"
                }}...
            ],
            "thought_process_behind_key_results": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "start_date": "<YYYY-MM-DD>",
            "end_date": "<YYYY-MM-DD>",
            "min_time_value": <integer>,
            "min_time_value_type": <1=days, 2=weeks, 3=months, 4=years>,
            "thought_process_behind_timeline": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
    
            "start_date": "<YYYY-MM-DD>",
            "end_date": "<YYYY-MM-DD>",
            "min_time_value": <integer>,
            "min_time_value_type": <1=days, 2=weeks, 3=months, 4=years>,
            "thought_process_behind_timeline": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "non_labour_team": [
                {{
                    "name": "<specific non-labor resource>",
                    "estimate_value": <integer value for given input Currency format>,
                    "name": "<specific non-labor resource>",
                    "estimate_value": <integer value for given input Currency format>,
                    "labour_type": 2
                }}...
            ],
            "thought_process_behind_non_labor_team": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "portfolio": [
                {{
                    "id": "<portfolio id from portfolios>",
                    "name": "<portfolio name from portfolios>"
                }}...
            ],
            "thought_process_behind_portfolio": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "constraints": [
                {{
                    "constraint": "<updated limitation>",
                    "tag": "<Cost, Resource, Risk, Scope, Quality, Time>"
                }}...
            ],
            "thought_process_behind_constraints": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "org_strategy_align": ["<3-4 updated priorities>"],
            "thought_process_behind_org_strategy_align": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "roadmap_category": ["<3-4 updated capabilities>"],
            "thought_process_behind_roadmap_category": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description>",
            "last_updated": "<current_date>"
        }}
        ```

        ### Guidelines:
        
        - **Update Focus**: Prioritize changes in **Roadmap Details** to reflect user-triggered updates, enriching with **Trmeric Knowledge Fabric** for portfolio-level insights and strategic alignment.
        
        - **Roadmap Name & Description**: Ensure the updated name & desc are aligned with the input details.
        - **Scope Item**: Ensure one detailed Markdown string (250-300 words) with dynamic sections (e.g., scope overview, requirements, risks) tailored to inputs, emphasizing precision and feasibility.
        - **Objectives**: Generate 3-4 descriptive, actionable goals, capitalizing only the first letter, aligned with **Roadmap Details** and **Trmeric Knowledge Fabric**.
        - **Constraints**: Update 3-4 specific, measurable limitations with appropriate tags, tied to **Roadmap Details** or **Trmeric Knowledge Fabric**.
        - **Portfolio**: Select up to 4 portfolios from **portfolios**, using exact `id` and `name`, aligned with **Roadmap Details** and **org_strategy**.
        - **Roadmap Categories**: Update 3-4 specific categories reflecting technical, business, and functional aspects, aligned with **Roadmap Details** and **Trmeric Knowledge Fabric**.
        - **Org Strategy Alignment**: Select 3-4 priorities from **org_strategy**, or infer from **Roadmap Details** or **Trmeric Knowledge Fabric** if missing.
        - **Non-Labor Team**: Recommend 3-4 specific resources with costs in **currency_format**, or return empty array if unsupported by **Roadmap Details**, with justification.
        - **Timeline**: Set `start_date` on or after current date, aligning with **Roadmap Details**.
        
        - **Edge Cases**: Handle sparse inputs by inferring from **Trmeric Knowledge Fabric** or **org_strategy**, noting assumptions in thought processes.
        - Ensure thought processes are concise (upto 100 words per section), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions, linking decisions to inputs and flagging assumptions.
    """
    userPrompt = f"""
        Update the roadmap canvas based on **Roadmap Details**, enriching with **Trmeric Knowledge Fabric**, **portfolios**, and **org_strategy**. 
        Ensure 3-4 key results,constraints with vivid outcomes, one detailed scope item (250-300 words) in Markdown, and thought processes citing relevant inputs.
    """


    return ChatCompletion(
        system=f"You are an expert roadmap creation agent updating an existing roadmap canvas with enriched, strategically aligned data.\n\n {systemPrompt}",
        prev=[],
        user=userPrompt
    )
    
    



def roadmapBasicInfoPrompt(conversation, persona, org_info, org_alignment, portfolios, quarter_tags, all_roadmap_titles, demand_type=None,tenant_id=None, user_id=None,files=None, guidance=None) -> ChatCompletion:
    """Generate a roadmap name and description based on provided inputs."""
    
    currentDate = CURRENT_DATE
    type_str,instructions = demand_type_prompt(tenant_id)
    files_instructions = uploaded_files_prompt(files)

    language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("---debug roadmapBasicInfoPrompt----","Language: ",language,"\nfile_Instructions: ",files_instructions)
    
    guidance_text = ""
    if guidance and guidance.get("has_guidance") and guidance.get("prompt_section"):
        guidance_text = f"\n{guidance['prompt_section']}\n"

    systemPrompt = f"""
        **Let’s kick off an epic roadmap with a powerful name and description!**

        ROLE: You’re a business planning genius roadmap creation agent tasked with creating a concise, impactful roadmap name
        and a vivid, actionable description for a future project, its type, and priority.
        Your mission is to craft a foundation that aligns with organizational goals, reflects customer priorities, and sets the stage for a detailed, executable roadmap.
        Remember, this is the first step in a larger roadmap creation process, so your output should be clear and compelling, and the roadmap is a future project.

        MISSION:
        Create a roadmap name and description using:
        - INPUT DATA: <conversation> {conversation} </conversation>
        - CONTEXT:
            <org_details>
                1. Organization Info: <org_info> {org_info} </org_info>
                2. Customer Persona: <persona> {persona} </persona>
                3. Portfolios: <portfolios> {portfolios} </portfolios>
                4. Org Strategy Alignment: <org_alignment> {org_alignment} </org_alignment>
                6. Quarter Tags: <quarter_tags> {quarter_tags} </quarter_tags>
                7. Files: <files> {files if files else 'None'} </files>
            </org_details>
        
        {guidance_text}

        ### Core Instructions:
        - Use <conversation> as the primary guide for the roadmap’s focus and intent. Also, from the conversation, capture additional inputs provided by the user on funding, business sector, or specific systems from **Existing Customer Solutions**.
        - Leverage <org_info>, <persona>, <org_alignment>, and <portfolios> to ensure alignment with organizational goals, customer needs, and portfolio priorities.
        - If <Existing Customer Solutions> is missing, infer reasonable details about the customer’s systems from <conversation>, <org_info>, <persona>, or <org_alignment>.
        - Ensure the description sets a clear foundation for later roadmap components (e.g., scope, objectives, key results).
        - **Apply Strategic Guidance**: If provided, use the 'Strategic Guidance from Historical Patterns' to refine the roadmap type, duration, and description. Align the roadmap with successful patterns from similar past projects.
        
         **Dynamic Demand Type Inference**:
            - If <demand_type> is provided, use it as the roadmap type ({type_str}).
            - Otherwise, infer the type from <conversation> by analyzing context of the type of demand:
                {instructions}

        -Business Problem Question: Explicitly from conversation, extract the summary of the business problem  which the demand is addressing.
                
        - **Demand Priority Classification**:
            - High: The demand has outcomes explicitly impacting multiple regions, business functions, or external customers, AND involves high business impact with quantified revenue, cost savings (e.g., dollar amounts), or strategic alignment affecting multiple regions or functions, as clearly stated in <conversation>.
            - Medium: The demand involves enhancements or changes with limited scope and impact, primarily affecting a single region, business function, or localized stakeholder group, without explicit evidence of multi-region or multi-function impact in <conversation>.
            - Low: The demand focuses on innovation, proof-of-concept (POC), or experimental initiatives, with no immediate large-scale impact or external customer dependency, as indicated by keywords like 'innovation,' 'NITRO,' or 'POC' in <conversation>.
            - Evaluation Steps:
                1. Check <conversation> for explicit mentions of scope (e.g., 'global,' 'regional,' 'local'), scale (e.g., number of users, regions, or functions affected), stakeholders (e.g., 'external customers,' 'internal team'), and business impact (e.g., quantified revenue, savings, or multi-function strategic goals).
                2. If <conversation> mentions 'innovation,' 'POC,' or 'NITRO' without clear external impact or urgency, assign LOW.
                3. If scope is localized (e.g., single team, region, or function) or impact is moderate (e.g., efficiency gains without quantified financials), assign MEDIUM.
                4. Demands limited to a single region or business function cannot be classified as High unless explicit multi-region, multi-function, or external customer impact is stated.
                5. If no explicit evidence of multi-region, multi-function, or external customer impact is provided, default to MEDIUM, even if qualitative importance (e.g., 'critical') is stated, and flag the assumption in `thought_process`.
            - Return only the classification (Low, Medium, or High) in the `priority` field based on above logic.
                    
            
        ### Timeline Instructions:
            - Set the timeline for the roadmap based on **conversation** if explicit timeline details are provided; otherwise, infer a reasonable timeline based on project complexity, team load, and project nature.
            - **Ensure Future Orientation**:
                - The `start_date` **must** be on or after the current date **{currentDate}**.
                - Calculate `end_date` by adding a realistic duration (`min_time_value` and `min_time_value_type`) based on: Project complexity, Team load and resource availability
            - Mapping for `min_time_value_type`: (1=days, 2=weeks, 3=months, 4=years)
            - Set `min_time_value` and `min_time_value_type` (e.g. (e.g., (2 months = value: 2, type: 3), ) logically based on input context provided above.

        ### Business Value Instructions:
        - Explicitly look into <conversation> and check if the user has provided inputs on funding, revenue, or savings.
        - Capture those elements, such as year, category, inflow, and justification.
        - If a system from **Existing Customer Solutions** is mentioned, consider potential business value from modifying that system (e.g., improved efficiency, cost savings).

        ### Budget Instructions:
        - If the user has mentioned a budget for this demand in the conversation, fill the `budget` field with that amount; otherwise, set to 0.

        ### Output Format:
        ```json
        {{
            "roadmap_name": "<name reflecting the roadmap's core focus in (max. 4-5 words)>",
            "description": "<vivid, actionable description utilizing maximum inputs from <conversation> and <files> if present, in 4-7 sentences as per input context>",
            "type": {type_str},
            "priority": "<Low|Medium|High> as per classification logic above>",
            "start_date": "<YYYY-MM-DD> after current date",
            "end_date": "<YYYY-MM-DD>",
            "quarter": "<select exactly one from <quarter_tags> ,based on start_date>",
            "min_time_value": <integer value refer to **conversation** if user has mentioned timeline>,
            "min_time_value_type": <1=days, 2=weeks, 3=months, 4=years (refer **conversation** if user has given inputs)>,
            "business_value_question": "<from the <conversation>,give a summarized business problem addressed by demand strictly in Markdown string format in 60 words>",
            "additional_info": "<from the <conversation>, the additional information shared by user strictly in Markdown string bullet points format>",
            "business_value": [
                {{
                    "cash_inflow": "<integer>",
                    "type": "<revenue|savings>",
                    "category": "<business value category>",
                    "time_period": "<year e.g. 2026>",
                    "justification_text": "<brief string>"
                }}
            ],
            "budget": <int>,
            "thought_process": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, explaining the reasoning for roadmap name, type, priority, and timeline; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite specific patterns, timelines, or business value insights (e.g., 'Based on Roadmap \\'a\\' 12-month timeline...'); quote relevant inputs and flag assumptions>"
        }}
        ```

        ### Guidelines:
        - **Roadmap Name**:
            - Create a concise (5-10 words), descriptive name that captures the roadmap's essence (e.g., “[mentioned system] Analytics Upgrade” if a system is mentioned).
            - Reflect the core focus from <conversation> and align with <org_alignment> or <persona> priorities.

            - **STRICT & IMPORTANT CHECK**: Ensure the new roadmap title is strictly unique by cross-checking against all existing titles in 
                <all_roadmap_titles> {all_roadmap_titles} </all_roadmap_titles> before finalizing.

        - **Description**:
            - Craft a vivid,descriptive 4-7 sentences narrative that feels epic, actionable, and conversational, using dynamic verbs (e.g., “supercharge,” “slash,” “ignite”) and one emoji (e.g., , ) to match the tone of the demand intake conversation.
            - Look into <conversation> & utilize maximum inputs user has provided and ensure that the description content reflects accordingly.
            - Include:
                - **Purpose**: Why the roadmap exists (e.g., “to upgrade [mentioned system] capabilities”).
                - **Goals**: Specific, measurable outcomes from <conversation> (e.g., “improve processing speed by 20%”).
                - **Scope**: Targeted sectors or areas (e.g., “financial services, analytics”).
                - **Key Components**: Core activities/technologies (e.g., “module upgrades, data integration”).
            - If a system from **Existing Customer Solutions** is mentioned, emphasize system-related goals and components only if relevant to the inferred type.
            - Avoid generic phrasing (e.g., “multiple industries”) and ensure alignment with <org_alignment> (e.g., digital transformation, innovation).
            
        - **Timeline**: Ensure the start_date is after the {currentDate} and end_date is accordingly inferred as per input details, (VERY CRUCIAL & IMPORTANT)
        - **Type**: Set to the inferred type ({type_str}) based on <conversation> and <Existing Customer Solutions>. Use <demand_type> if provided; otherwise, infer dynamically and document reasoning in `thought_process`.
        - **Additional Info**: In Markdown formatted bullet points for additional details, such as Funding, Business sector, etc., shared by the user in the conversation (don’t include Demand Type or Portfolio Info here).
        - **Thought Process**: Document reasoning for roadmap name, type, priority, and timeline in concise Markdown bullet points (up to 4 points), each with a **bold header** and brief (10-20 words) description. **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite specific patterns, timelines, or business value insights. Quote relevant inputs and flag assumptions.
    """
    systemPrompt += f"""{files_instructions if files else ''}"""

    userPrompt = f"""
        Generate a roadmap name and description based on the input details provided in <conversation> and <org_details>. 
        Use Existing Customer Solutions (Internal Knowledge) for system context, Portfolios for portfolio alignment, Persona for customer alignment, Conversation for user intent.
        Infer the demand type ({type_str}) dynamically from <conversation> and <Existing Customer Solutions>.
        Ensure the name is concise, unique (not in all_roadmap_titles given in input), and reflective of the roadmap's core focus, and the description is vivid, actionable, and aligned with organizational goals, including purpose, scope, key components, and measurable goals where supported.
        Include thought process in Markdown bullet points to justify decisions.
        
        Ensure JSON output format
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
     




def demandInsightsPrompt(roadmap_canvas, solutions,existing_roadmaps,delivered_solutions, user_id) -> ChatCompletion:
    language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("language ---", language)
    systemPrompt = f"""

        You are an expert strategic advisor and analyst. Your role is to engage in a conversational, advisory tone and generate deep, intelligent demand insights for a newly created demand request (roadmap).
        Your objective is to guide demand managers, business requestors, and business solution managers (BSMs) in making better decisions about the scope, solutioning, prioritization, and resourcing of this demand.

        This demand canvas is generated by requestor persona and will be sent into different stages like Solutioning, Elaboration, Prioritization after review with BSMs and demand managers.
        The demand insights will include the 5 dimensions mentioned below:

        **Input Data**:
        - **Demand Canvas**: {roadmap_canvas}
        - **Existing Solutions**: {solutions}
        - **Delivered Solutions**: {delivered_solutions}
        - **Existing Roadmaps**: {existing_roadmaps}


        This provides:
        - **Demand Canvas**: A JSON object with details such as basic info (name, description, etc.), OKRs (objectives, key results), constraints, portfolio, categories, timeline, and thought processes.
        - **Existing Solutions**: A JSON array where each solution includes attributes like name, description, category, technology, and service line.
        - **Delivered Solutions**: A dict of applicable porfolios of the demand canvas which involves the array of solution_delivered, functional and technical requirements which has been achieved.
        - **Existing Roadmaps**: Data including roadmap titles, descriptions, OKR(s) and  Scope.

        **Your Task**:
        Using the input, generate insights in the following conversational style. Think of yourself as an advisor talking through the situation with the requester,Keep the language professional but accessible, as if you are helping them reflect and connect the dots.
        Analyze the input data and generate insights across the following **FIVE dimensions**. For each dimension, provide 2-3 concise bullet points. Ensure insights are actionable, data-driven, and relevant to decision-making for the requester.

        1. **Scope**:
           - Compare the demand’s scope with existing roadmaps and delivered solutions, identifying overlaps or unique aspects.
           - Highlight synergies or gaps, especially in data processing or system integration requirements (e.g., JSON parsing or CSV handling).
           - Suggest ways to refine scope, such as clarifying data inputs/outputs or aligning with existing system capabilities.
           - Go beyond comparison: offer suggestions to strengthen the scope, fill gaps, or sharpen requirements, so the requester has a more comprehensive and well-thought-out demand.

        2. **Solutions**:
           - Evaluate how existing solutions align with the demand’s requirements, considering technology, functional fit, and integration needs.
           - Draw on patterns from past work: what worked, what pitfalls to avoid, and what expertise was needed. Consider the existing application, product, and platform landscape — suggest how these can be leveraged or extended rather than starting from scratch. 
           - Recommend leveraging or extending existing solutions, noting past pitfalls (e.g., inconsistent data mappings) and required expertise.

        3. **Connections**:
           - Identify similar initiatives in the organization, such as projects involving data extraction, transformation, or system integrations.
           - Suggest opportunities for collaboration or reuse of processes (e.g., shared data pipelines or integration logic) to avoid duplication.
           - Highlight potential for knowledge-sharing across portfolios or business units to enhance efficiency.

        4. **Business Value**:
           - Assess the demand’s business impact, categorizing it as High, Medium, or Low based on alignment with OKRs, efficiency gains (e.g., automated data processing), or revenue potential.
           - Justify the categorization with semi-quantitative logic, such as estimated time/cost savings or risk reduction.
           - Explain how the value assessment supports prioritization within the organization’s strategic goals.

        5. **People, Resources & Risks**:
           - Outline required skills (e.g., data analysts for CSV processing, developers for API integrations) and resources for delivery.
           - Highlight potential bottlenecks, risks, or dependencies that could affect delivery to help requestor think about execution beyond the idea stage.
           - Suggest mitigation strategies, like validating data schemas or securing cross-functional team support.

        **Output**:
        Generate a well-articulated Markdown string that includes concise bullet points for each of the five dimensions. 
        The total length should be approximately 200-350 words.

        
        **OUTPUT**: Return a JSON object strictly in this format:

        Return a JSON object in the following format:
        ```json
        {{
            "top_matches": ["Solution Name 1", "Solution Name 2", ...],
            "insights": "<Markdown string with bullet points covering all four dimensions>"
        }}
        ```
        
        **Additional Instructions**:
        - List the top 2-3 solutions with High or Medium matches from the Solution Dimension. If no High or Medium matches exist, return an empty array.
        - Ensure the delivered solutions context are read correctly and how the technical, functional and delivered solutions are related or can be done better in the current demand.
        - Ensure that the insights are actionable and provide value to demand managers & (BSMs) in their decision-making process.
        - Use clear and professional language suitable for a business context.
        - Aim for 2-3 bullet points per dimension to maintain conciseness.
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    userPrompt = f"""
    Please provide the validation results in the specified JSON format as instructed. \
    Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )





##Category Specific to EY data
def roadmapConstraintsPortfolioCategoryPrompt_ey(roadmap_details, internal_knowledge, portfolios, conversation, persona,tenant_id=None, user_id=None,files=None, guidance=None) -> ChatCompletion:
    """Generate constraints, portfolio details, and roadmap categories in valid JSON format."""
    
    language = UsersDao.fetchUserLanguage(user_id = user_id)
    files_instructions = uploaded_files_prompt(files)
    category_instructions = demand_category_prompt(int(tenant_id))
    # print("---debug roadmapConstraintsPortfolioCategoryPrompt_ey----",category_instructions, "\n\nInstructions: ",files_instructions)
    
    guidance_text = ""
    has_guidance = guidance and guidance.get("has_guidance") and guidance.get("prompt_section")
    if has_guidance:
        guidance_text = f"\n{guidance['prompt_section']}\n"
    
    if tenant_id in [232,"232","227",227,"237",237,776,"776"]:
        systemPrompt = f"""
            **Craft precise, actionable constraints, portfolio details, and roadmap categories for an epic roadmap!**
            Your task is to produce detailed **constraints**, **portfolio details**, and **roadmap categories** in valid JSON format. 
            Leverage the customer's existing solutions, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
            
            The intent is to create constraints that are specific and measurable, and roadmap categories that are comprehensive and aligned with project goals.

            **No explanations or text outside the JSON block.**
            
            {guidance_text}

            ### Core Mandates:
            - Use **Conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
                1. **Roadmap Details**: Objective signals, narrative cues.
                2. **Existing Customer Solutions**: A collection of the customer’s current systems, tools, or platforms, including details about their functionality, limitations, and strategic relevance. 
                    It empowers the LLM to synthesize focused, strategically aligned roadmap items by leveraging insights about existing solutions, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
                3. **Portfolios**:  Only take Exact name of the portfolio(s) user has answered in the conversation
                4. **Persona**: Customer expectations and pain points.
                5. **Strategic Guidance from Historical Patterns** (if provided above): **CRITICALLY IMPORTANT** - When Strategic Guidance mentions specific roadmaps (e.g., "Roadmap 'a'"), you MUST explicitly cite them in your thought_process fields. Use the historical patterns for constraints, portfolio, and categories.

            - Deeply integrate **Persona** {persona} to align constraints and categories with customer pain points, goals, and expected outcomes.
            - Get the details of the portfolio mentioned in the conversation from the **Portfolios** {portfolios} 
            - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought processes, and prioritize feasibility.
            - **System Prioritization**: Only include a system from **Existing Customer Solutions** in the `roadmap_category` array if explicitly mentioned in the conversation. Prioritize portfolios aligned with the mentioned system’s functionality, if any.

            ### Inference Logic:
            - Derive roadmap direction by synthesizing:
                - **Roadmap Details**: Extract intent from objectives and narrative.
                - **Existing Customer Solutions**: Identify gaps, risks, and strategic priorities based on current systems.
                - **Persona**: Reflect customer needs, behaviors, and success criteria.
                - **Conversation**: Reflect user intent and success criteria, including mentions of systems from **Existing Customer Solutions**.
                - **Demand Type**: If provided or inferred as 5, emphasize enhancement-related constraints and categories.
                
            - Proactively infer missing components, balancing ambition with feasibility.

            ### Constraints Instructions:
            - Generate 3-4 constraints within the `constraints` array, each with:
                - **constraint**: A specific, measurable limitation impacting project execution (e.g., "Limited integration capabilities in [mentioned system] may delay deployment by 2 months" if a system is mentioned).
                - **tag**: One of Cost, Resource, Risk, Scope, Quality, Time, aligned with the limitation’s nature.
            - If <demand_type> is 5 or a system from **Existing Customer Solutions** is mentioned, include at least one constraint related to enhancement challenges (e.g., integration or resource limitations) if relevant.
            - Ensure constraints are actionable, tied to Roadmap Details, Conversation, or Existing Customer Solutions, and relevant to project goals.
            - Include measurable impacts (e.g., "2-3 month delay") with justification from inputs or inferences.

            ### Portfolio Instructions:
            - Select the portfolio which the user has given explicitly in the conversation from **Portfolios** within the `portfolio` array, using exact `id` and `name`.

            ### Roadmap Category Instructions:
            - Explicitly follow: {category_instructions}
            
            - Include these mapped tags in the `roadmap_category` array alongside technical, business, and functional categories.
            - If no direct match is found, infer the closest category as applicable.
            - Ensure all categories are specific, aligned with project goals, and integrate both original aspects and mapped tags.

            ### **CRITICAL REMINDER: If Strategic Guidance from Historical Patterns was provided above (look for "### Strategic Guidance from Historical Patterns"), you MUST cite specific roadmaps mentioned (e.g., "Roadmap 'a'") in ALL three thought_process fields below. This is mandatory.**

            ### Thought Process Instructions:
            - Document reasoning for each section (constraints, portfolio, roadmap category) in concise Markdown bullet points (up to 4 points per section, max).
            - **Format Requirement**: Each bullet must start with a **bold header** summarizing the key decision or input, followed by a brief (1-2 sentence, 10-20 words) description explaining its influence, justification, or assumption. Avoid verbose explanations to optimize rendering speed.
            - Structure example:
                - **Header**: Brief description of decision or input influence.
            - For **thought_process_behind_constraints**:
                - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite constraints patterns from similar roadmaps (e.g., "Roadmap 'a' faced limited budget constraints...").
                - Quote relevant Existing Customer Solutions and input signals (e.g., Roadmap Details, Persona, Portfolios, Conversation).
                - Justify constraint selection, impact, and alignment with project goals.
                - Flag assumptions for missing or vague data, noting confidence and trade-offs.
             - For **thought_process_behind_portfolio**:
                - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., "Roadmap 'a' selected Operations portfolio for digitization...").
                - Quote the portfolio user has selected during Conversation.
                - Justify selection and prioritization based on alignment with goals and inferred type.
            - For **thought_process_behind_roadmap_category**:
                - **CRITICAL**: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., "Roadmap 'a' focused on Factory Digitization and Process Automation...").
                - Quote relevant Existing Customer Solutions and input signals.
                - Justify category selection, content focus, and relevance to project goals.
                - If a system is mentioned, justify its inclusion in `roadmap_category`.
                - Flag assumptions for inferred categories or alignment.

            ### Input Summary:
            - Roadmap Details: {roadmap_details or 'None provided'}
            - Portfolios: {portfolios}
            - Persona: {persona}
            - Conversation: {conversation}
            - Files: {files if files else 'None'}

            ### Output Format:
            Return **only** the following JSON structure:

            ```json
            {{
                "constraints": [
                    {{
                        "constraint": "<rich, contextual limitation or constraint across dimensions such as Resource, Scope, Quality, Technology, Complexities around integrations, external factors, Cost etc. , 
                            e.g.,'Limited integration capabilities in [mentioned system] may delay deployment by 2 months'>",
                        "tag": "<Cost, Resource, Risk, Scope, Quality, Time>"
                    }}
                ],
                "thought_process_behind_constraints": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite constraints patterns from similar roadmaps (e.g., 'Roadmap \\'a\\' faced limited budget constraints...'); quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify constraint selection, impact, assumptions, and alignment>",
                "portfolio": [
                    {{
                        "id": "<exact id from Portfolios>",
                        "name": "<exact name from Portfolios>"
                    }}
                ],
                "thought_process_behind_portfolio": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite portfolio patterns from similar roadmaps (e.g., 'Roadmap \\'a\\' selected Operations portfolio for digitization...'); quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify selections, prioritization, and alignment>",
                "roadmap_category": ["<comma-separated technical, business, or functional categories, e.g., '[mentioned system], Process Mining, Supply Chain Optimization, Data Analytics' if a system is mentioned>"],
                "thought_process_behind_roadmap_category": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description; CRITICAL: If Strategic Guidance from Historical Patterns was provided, explicitly cite category patterns from similar roadmaps (e.g., 'Roadmap \\'a\\' focused on Factory Digitization and Process Automation...'); quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify category selection, content focus, assumptions, and alignment>"
            }}
            ```

            ### Guidelines:
            - Ground the constraints and roadmap categories in Roadmap Details, enriched by Existing Customer Solutions, Portfolios, Persona and Conversation.
            - Ensure thought processes are concise (50-80 words per section), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions, linking decisions to inputs and flagging assumptions.
            - Do not include systems from **Existing Customer Solutions** in `roadmap_category` unless explicitly mentioned in the conversation.
    """

    else:
        systemPrompt = f"""
            **Craft precise, actionable constraints, portfolio details, and roadmap categories for an epic roadmap!**
            Your task is to produce detailed **constraints**, **portfolio details**, and **roadmap categories** in valid JSON format. 
            Leverage the customer's existing solutions, user context, and advanced reasoning to synthesize a precise, adaptive, and strategically aligned response.
            
            The intent is to create constraints that are specific and measurable, portfolio selections that are prioritized, and roadmap categories that are comprehensive and aligned with project goals.

            **No explanations or text outside the JSON block.**
            
            {guidance_text}

            ### Core Mandates:
            - Use **Conversation** {conversation} to define roadmap intent. Then infer direction by prioritizing inputs in this order: 
                1. **Roadmap Details**: Objective signals, narrative cues.
                2. **Existing Customer Solutions**: A collection of the customer’s current systems, tools, or platforms, including details about their functionality, limitations, and strategic relevance. 
                    It empowers the LLM to synthesize focused, strategically aligned roadmap items by leveraging insights about existing solutions, bridging gaps with logical inference, and aligning with customer needs and portfolio objectives.
                3. **Persona**: Customer expectations and pain points.
                
            - Drive ~40% of content from **Existing Customer Solutions**, analyzing:
                - **System Capabilities**: To shape constraints and categories (e.g., limitations of a system imply integration constraints).
                - **Current Implementations**: To inform portfolio selection, constraints, and risks.
                - **Strategic Relevance**: To ensure alignment with customer goals.
                - **Reasoning**: To prioritize initiatives and define focus.
                
            - Deeply integrate **Persona** {persona} to align constraints and categories with customer pain points, goals, and expected outcomes.
            - Get the details of the portfolio mentioned in the conversation from the **Portfolios** {portfolios} 
            - Handle edge cases: If any input is missing, vague, or contradictory, infer logically, flag assumptions in thought processes, and prioritize feasibility.
            - **System Prioritization**: Only include a system from **Existing Customer Solutions** in the `roadmap_category` array if explicitly mentioned in the conversation. Prioritize portfolios aligned with the mentioned system’s functionality, if any.

            ### Inference Logic:
            - Derive roadmap direction by synthesizing:
                - **Roadmap Details**: Extract intent from objectives and narrative.
                - **Existing Customer Solutions**: Identify gaps, risks, and strategic priorities based on current systems.
                - **Portfolios**: Anchor to portfolio goals, constraints, and cross-project dependencies.
                - **Persona**: Reflect customer needs, behaviors, and success criteria.
                - **Conversation**: Reflect user intent and success criteria, including mentions of systems from **Existing Customer Solutions**.
                - **Demand Type**: If provided or inferred as 5, emphasize enhancement-related constraints and categories.
                
            - Proactively infer missing components, balancing ambition with feasibility.

            ### Constraints Instructions:
            - Generate 3-4 constraints within the `constraints` array, each with:
                - **constraint**: A specific, measurable limitation impacting project execution (e.g., "Limited integration capabilities in [mentioned system] may delay deployment by 2 months" if a system is mentioned).
                - **tag**: One of Cost, Resource, Risk, Scope, Quality, Time, aligned with the limitation’s nature.
            - If <demand_type> is 5 or a system from **Existing Customer Solutions** is mentioned, include at least one constraint related to enhancement challenges (e.g., integration or resource limitations) if relevant.
            - Ensure constraints are actionable, tied to Roadmap Details, Conversation, or Existing Customer Solutions, and relevant to project goals.
            - Include measurable impacts (e.g., "2-3 month delay") with justification from inputs or inferences.

            ### Portfolio Instructions:
            - Select the portfolio which the user has given explicitly in the Conversation from **Portfolios** within the `portfolio` array, using exact `id` and `name`.
            
            ### Roadmap Category Instructions:
            - Generate 3-4 categories within the `roadmap_category` array, including:
            - Technical, business, and functional aspects (e.g., "Process Mining", "Supply Chain Optimization", "Data Analytics").
            - Only include a system from **Existing Customer Solutions** as an element in the `roadmap_category` array if explicitly mentioned in the conversation.
            - Tags mapped from user inputs in the conversation and Existing Customer Solutions to categories in `EY_SHEET_DATA`.
            - For mapping tags:
            - Analyze the conversation and Existing Customer Solutions for mentions of regions, platforms, service lines, funding sources, or business sectors.
            - Map these mentions to the corresponding categories in `EY_SHEET_DATA`, which is provided as a JSON object in the input summary:
                - For "AreaRegion": If a term (e.g., "Africa") is in a list under a region (e.g., "Asia-Pacific"), use "AreaRegion: Asia-Pacific". Use "AreaRegion: Unassigned" if no match.
                - For "Platform": If a platform (e.g., a system from **Existing Customer Solutions**) is mentioned, use "Platform: [system name]".
                - For "ServiceLines": If a term (e.g., "Audit Technology") is in a list under a service line (e.g., "Assurance"), use "ServiceLines: Assurance - Audit Technology". Use "ServiceLines: Unassigned" if no match.
                - For "FundingBusinessSector": If a funding source (e.g., "Executive Layer") or business sector (e.g., "Financial Services") is mentioned, use "Funding Source: Executive Layer" or "Business Sector: Financial Services".
            - Examples: 
                - "This is for audit technology" → "ServiceLines: Assurance - Audit Technology".
                - "Asia-Pacific region" or "Africa" → "AreaRegion: Asia-Pacific".
                - "Enhancing [system name]" → "Platform: [system name]" and infer type 5 (Enhancements or Upgrade).
            - If no direct match is found, infer the closest category as applicable.
            
            - Include these mapped tags in the `roadmap_category` array alongside technical, business, and functional categories.
            - Ensure all categories are specific, aligned with project goals, and integrate both original aspects and mapped tags.
            - If <demand_type> is 5, emphasize enhancement-related categories (e.g., "System Upgrades", "Module Integration").

            ### Thought Process Instructions:
            - Document reasoning using **markdown bullet points** with **bold headers** and brief (1-2 sentence) descriptions.
            {"" if not has_guidance else '''
            - **Two-section format** for each thought process field:

            #### For **thought_process_behind_constraints**:
            ```
            ### KNOWLEDGE FROM SIMILAR INITIATIVES:
            - **Pattern Insights**: Specific limitations and challenges from similar historical roadmaps
            - **Historical Evidence**: Quantified impacts and mitigation strategies from past implementations
            
            ### ROADMAP-SPECIFIC ANALYSIS:
            - **Current System Analysis**: How existing customer solutions create specific constraints
            - **Resource Assessment**: Constraint identification based on organizational capabilities
            - **Risk Evaluation**: Potential impacts and mitigation considerations
            ```
            
            #### For **thought_process_behind_portfolio**:
            ```
            ### KNOWLEDGE FROM SIMILAR INITIATIVES:
            - **Historical Patterns**: How similar roadmaps succeeded within specific portfolio contexts
            - **Success Evidence**: Historical insights about portfolio capabilities and constraints
            
            ### ROADMAP-SPECIFIC ANALYSIS:
            - **User Portfolio Selection**: Direct portfolio choice from conversation
            - **Strategic Alignment**: Why chosen portfolio best supports roadmap objectives
            ```
            
            #### For **thought_process_behind_roadmap_category**:
            ```
            ### KNOWLEDGE FROM SIMILAR INITIATIVES:
            - **Pattern Insights**: Category patterns and technical focus areas from historical roadmaps
            - **Success Evidence**: Category selections that drove successful outcomes
            
            ### ROADMAP-SPECIFIC ANALYSIS:
            - **Category Selection**: Why chosen categories align with project goals and system mentions
            - **Technical Fit**: How categories reflect technical, business, and functional requirements
            ```
            
            **Knowledge Section Guidelines:**
            - Quote EXACTLY from the Strategic Guidance above - do not paraphrase or extend
            - NEVER invent roadmap names, constraints, or categories not in the guidance
            - Cite specific roadmap names and evidence from the provided guidance
            
            **Reasoning Section Guidelines:**
            - Focus on how current context drives decisions
            - Justify selections based on conversation, existing solutions, and organizational fit
            - Keep descriptions focused and actionable
            '''}
            {"" if has_guidance else '''
            - For each thought process field, provide markdown bullet points (no section header):
            - For constraints: **Limitation Identification**, **Impact Assessment**, **System Analysis**, **Risk Factors**
            - For portfolio: **Selection Rationale**, **Strategic Alignment**, **Capability Fit**
            - For roadmap_category: **Category Selection**, **Technical Fit**, **Business Alignment**, **Tag Mapping**
            - Each bullet: brief (1-2 sentence) explanation of reasoning
            - Keep descriptions concise and actionable
            '''}
            
            #### For **thought_process_behind_roadmap_category**:
            Structure as:
            ```
            ### KNOWLEDGE-DRIVEN INSIGHTS (from Historical Patterns):
            - **[Category Success Examples]**: Specific category combinations that drove results in historical roadmaps
            - **[Proven Category Patterns]**: Evidence of effective categorization approaches from similar initiatives
            
            ### CONTEXTUAL REASONING:
            - **[System Integration Needs]**: Categories derived from existing customer solution requirements
            - **[Business Alignment]**: Category selection based on conversation and business objectives
            - **[Technical Requirements]**: Categories reflecting technical and functional needs
            ```
            
            **Knowledge Section Guidelines:**
            - **CRITICAL ANTI-HALLUCINATION RULE**: ONLY populate knowledge sections if Strategic Guidance is explicitly provided above
            - Quote EXACTLY from the provided guidance text - do not paraphrase, extend, or create connections not explicitly stated
            - If NO Strategic Guidance appears above, leave knowledge sections COMPLETELY EMPTY with: "No historical pattern data provided."
            - NEVER invent constraint patterns, portfolio successes, or category examples not explicitly provided
            - NEVER reference "similar implementations," "common patterns," or "typical approaches" in knowledge sections
            - ONLY cite roadmap names that appear verbatim in the Strategic Guidance above
            
            **Reasoning Section Guidelines:**
            - Focus on how current inputs (existing solutions, conversation, persona) drive decisions
            - Justify selections based on system capabilities, user requirements, and organizational fit
            - Include enhancement-specific reasoning when demand_type is 5 or systems are mentioned

            ### Input Summary:
            - Roadmap Details: {roadmap_details or 'None provided'}
            - Portfolios:
            - Persona: 
            - Conversation: 
            - EY Sheet Data: {EY_SHEET_DATA}
            - Files: {files if files else 'None'}

            ### Output Format:
            Return **only** the following JSON structure:

            ```json
            {{
                "constraints": [
                    {{
                        "constraint": "<rich, contextual limitation or constraint across dimensions such as Resource, Scope, Quality, Technology, Complexities around integrations, external factors, Cost etc. , 
                            e.g.,'Limited integration capabilities in [mentioned system] may delay deployment by 2 months'>",
                        "tag": "<Cost, Resource, Risk, Scope, Quality, Time>"
                    }}
                ],
                "thought_process_behind_constraints": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify constraint selection, impact, assumptions, and alignment>",
                "portfolio": [
                    {{
                        "id": "<exact id from Portfolios>",
                        "name": "<exact name from Portfolios>"
                    }}
                ],
                "thought_process_behind_portfolio": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify selections, prioritization, and alignment>",
                "roadmap_category": ["<comma-separated technical, business, or functional categories, e.g., '[mentioned system], Process Mining, Supply Chain Optimization, Data Analytics' if a system is mentioned>"],
                "thought_process_behind_roadmap_category": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence, 10-20 words) description, quoting relevant Existing Customer Solutions, explaining influence of Roadmap Details, Persona, Portfolios, Conversation, Demand Type; justify category selection, content focus, assumptions, and alignment>"
            }}
            ```

            ### Guidelines:
            - Ground the constraints, portfolio selections, and roadmap categories in Roadmap Details, enriched by Existing Customer Solutions, Portfolios, Persona, Conversation, and Demand Type.
            - Ensure thought processes are concise (50-80 words per section), prioritized, and traceable in Markdown bullet points, with **bold headers** and brief descriptions, linking decisions to inputs and flagging assumptions.
            - Do not include systems from **Existing Customer Solutions** in `roadmap_category` unless explicitly mentioned in the conversation.
        """
    
    systemPrompt += f"""{files_instructions if files else ''}"""

    userPrompt = f"""
        Generate constraints, portfolio details, and roadmap categories for the roadmap based on Roadmap Details. 
        Use Existing Customer Solutions for system context, Portfolios for portfolio alignment, Persona for customer alignment, Conversation for user intent.
        Only include a system from Existing Customer Solutions in roadmap categories if explicitly mentioned in the conversation.
        Return **only** valid JSON as specified in the system prompt, including constraints, thought process for constraints, portfolio details, thought process for portfolio, roadmap categories, and thought process for roadmap categories, with thought processes formatted using comprehensive Markdown with rich formatting, detailed analysis, and expansive coverage as needed.
        Ensure JSON output format.
        
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    
    
    



def format_dimension_guidance(guidance):
    """Format dimension guidance for display in prompts.
    
    Args:
        guidance: Either a string (legacy) or list of guidance items (new format)
        
    Returns:
        Formatted string for prompt display
    """
    if isinstance(guidance, list):
        if not guidance:
            return "No historical patterns available."
        return "\n".join([f"• {item}" for item in guidance])
    elif isinstance(guidance, str):
        return guidance
    else:
        return "No historical patterns available."


def combined_roadmap_creation_prompt(
    conversation,
    persona=None,
    org_info=None,
    org_strategy=None,
    portfolios=None,
    internal_knowledge=None,
    all_roadmap_titles=None,
    demand_type=None,
    tenant_id=0,
    inference_guidance=None,
    all_ideas=None,          # list of {id, title} dicts for idea linking
):
    from src.trmeric_services.roadmap.utils import demand_type_prompt
    type_str, type_instructions = demand_type_prompt(tenant_id)

    # ── idea lookup section ───────────────────────────────────────────────────
    idea_lookup_section = ""
    if all_ideas:
        import json as _json
        idea_lookup_section = f"""
## AVAILABLE IDEAS FOR LINKING:
If the conversation references any of these ideas by name, code (e.g. CN0005),
or description, include their integer IDs in the `idea_list` output field.
If no ideas are referenced, return `idea_list: []`.

{_json.dumps(all_ideas, indent=2)}
"""

    # Prepare inference guidance context if available
    inference_context = ""
    has_inference = inference_guidance is not None and inference_guidance.get("pattern_match")
    if has_inference:
        # Handle both old and new data structures
        pattern_ref = inference_guidance.get("pattern_reference", {})
        pattern_match = inference_guidance.get("pattern_match", {})
        pattern_details = inference_guidance.get("pattern_details", [])
        
        # Extract pattern information from either structure
        if pattern_match and pattern_match.get("primary_pattern"):
            # New multi-pattern structure
            primary = pattern_match["primary_pattern"]
            secondary = pattern_match.get("secondary_pattern")
            
            pattern_name = primary.get("pattern_name", "N/A")
            pattern_id = primary.get("pattern_id", "N/A")
            roadmap_count = pattern_match.get("total_roadmap_count", 0)
            
            # Collect roadmap names from both patterns
            roadmap_names = list(primary.get("roadmap_names", []))
            if secondary:
                roadmap_names.extend(secondary.get("roadmap_names", []))
        
        # Get roadmap ID-to-name mapping for citation instructions
        roadmap_mapping = inference_guidance.get("roadmap_id_to_name_mapping", {})
        mapping_instructions = ""
        if roadmap_mapping:
            mapping_list = [f"  - ID {rid}: '{name}'" for rid, name in roadmap_mapping.items()]
            mapping_instructions = f"""

** ROADMAP CITATION REQUIREMENTS:**
When referencing roadmaps in your thought processes, use ONLY the roadmap names, never the IDs.
Roadmap ID to Name Mapping:
{chr(10).join(mapping_list)}

Example: Use "Global Markets Cross-Border Efficiency Uplift" NOT "Roadmap 989\""""

        # Build pattern overview with multiple patterns
        pattern_overview = f'Pattern: "{pattern_name}" (ID: {pattern_id})'
        if secondary:
            secondary_name = secondary.get("pattern_name", "N/A")
            secondary_id = secondary.get("pattern_id", "N/A")
            pattern_overview += f' + Secondary Pattern: "{secondary_name}" (ID: {secondary_id})'
            
        elif pattern_ref:
            # Legacy single pattern structure
            pattern_name = pattern_ref.get("pattern_name", "N/A")
            pattern_id = pattern_ref.get("pattern_id", "N/A")
            roadmap_names = pattern_ref.get("roadmap_names", [])
            roadmap_count = pattern_ref.get("roadmap_count", 0)
            pattern_overview = f'Pattern: "{pattern_name}" (ID: {pattern_id})'
        else:
            # No pattern data available
            pattern_name = "N/A"
            pattern_id = "N/A"
            roadmap_names = []
            roadmap_count = 0
            pattern_overview = "No pattern information available"
        
        dimension_guidance = inference_guidance.get("dimension_guidance", {})
        template_examples = inference_guidance.get("template_examples", [])
        
        # Build template examples section from retrieved RoadmapTemplate vertices
        template_section = ""
        if template_examples:
            template_section = "\n**STRUCTURE EXAMPLES FROM SIMILAR ROADMAPS:**\n"
            for i, template in enumerate(template_examples, 1):
                # Handle both old format (roadmap_title) and new format (direct template attrs)
                template_name = template.get('title', template.get('name', f'Template {i}'))
                template_id = template.get('id', 'N/A')
                
                template_section += f"\nExample {i}: {template_name} (ID: {template_id})\n"
                
                # Include key template attributes
                if template.get('description'):
                    desc = template['description']
                    if len(desc) > 150:
                        desc = desc[:150] + "..."
                    template_section += f"- Description: {desc}\n"
                
                if template.get('objectives'):
                    objectives = template['objectives']
                    if isinstance(objectives, str):
                        if objectives.startswith('['):
                            # JSON array format
                            try:
                                import json
                                obj_list = json.loads(objectives)
                                if isinstance(obj_list, list) and obj_list:
                                    template_section += f"- Key Objective: {obj_list[0]}\n"
                            except:
                                template_section += f"- Objectives: {objectives[:100]}\n"
                        else:
                            template_section += f"- Objectives: {objectives[:100]}\n"
                
                if template.get('solution'):
                    template_section += f"- Solution: {template['solution'][:120]}\n"
                
                if template.get('category'):
                    template_section += f"- Category: {template['category']}\n"
                
                if template.get('priority') and template['priority'] != 'Unknown':
                    template_section += f"- Priority: {template['priority']}\n"
                
                if template.get('tags'):
                    tags = template['tags']
                    if isinstance(tags, str) and tags.startswith('['):
                        try:
                            import json
                            tag_list = json.loads(tags)
                            if isinstance(tag_list, list) and tag_list:
                                template_section += f"- Tags: {', '.join(tag_list[:3])}\n"
                        except:
                            pass
        
        # Pre-compute values that need special formatting (can't use backslash in f-string expressions)
        roadmap_names_quoted = ', '.join([f"'{name}'" for name in roadmap_names[:5]])
        roadmap_names_joined = ', '.join(roadmap_names)
        roadmap_names_display = ', '.join(roadmap_names[:5]) + ('...' if len(roadmap_names) > 5 else '')
        
        inference_context = f"""
        
        ###  KNOWLEDGE FROM SIMILAR PAST ROADMAPS (CRITICAL - PRIMARY DECISION DRIVER):
        
        ** MATCHED PATTERN OVERVIEW:**
        {pattern_overview}
        Found {roadmap_count} similar roadmap(s): {roadmap_names_display}
        Match Confidence: {inference_guidance.get("overall_confidence", "N/A")}
        
        ** COMPREHENSIVE SOLUTION GUIDANCE:**
        {inference_guidance.get("solution_guidance", "")}
        
        ** PATTERN SYNTHESIS SUMMARY:**
        {inference_guidance.get("pattern_synthesis_summary", "No synthesis summary available.")}
        
        {template_section}
        {mapping_instructions}
        
        ** DIMENSION-SPECIFIC PATTERNS & EVIDENCE:**
        
        ** Timeline Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("timeline", ["No historical timeline patterns available."]))}
        
        ** Objectives Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("objectives", ["No historical objectives patterns available."]))}
        
        ** Constraints Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("constraints", ["No historical constraints patterns available."]))}
        
        ** Portfolio Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("portfolio", ["No historical portfolio patterns available."]))}
        
        ** Category Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("category", ["No historical category patterns available."]))}
        
        ** Business Value Intelligence:**
        {format_dimension_guidance(dimension_guidance.get("business_value", ["No historical business value patterns available."]))}
        
        ---
        
        ** ENHANCED THOUGHT PROCESS REQUIREMENTS:**
        
        **CRITICAL: You MUST cite specific roadmap names in your thought processes. Available roadmaps: {', '.join(roadmap_names[:10])}**
        
        **For ALL thought_process fields, use this MANDATORY two-section structure:**
        
        ```
        ### KNOWLEDGE FROM SIMILAR INITIATIVES:
        [Populate with specific citations and quantitative evidence from the pattern data above]
        - **Pattern Insights**: "As demonstrated in 'Exact Roadmap Name', [specific outcome/approach]"
        - **Success Metrics**: "Following the {pattern_name} approach which showed [specific benefit]"
        - **Historical Evidence**: "Similar to 'Roadmap Name 1' and 'Roadmap Name 2' which both achieved [specific result]"
        
        ### ROADMAP-SPECIFIC ANALYSIS:
        [Always populate based on current inputs and organizational context]  
        - **Current Context**: How historical insights apply to this specific situation
        - **Strategic Alignment**: Adaptation of proven patterns to current objectives
        - **Decision Rationale**: Combined historical evidence + contextual factors = decision
        ```
        
        ** MANDATORY CITATION REQUIREMENTS:**
        - Each thought_process MUST include at least 1 direct quote from available roadmaps: {roadmap_names_quoted}
        - Use exact roadmap titles in quotes: "Roadmap Name" 
        - Reference pattern name when applicable: "{pattern_name}"
        - Attribute specific metrics/outcomes to source roadmaps
        - Mark synthesized insights with [synthesized from {pattern_name}]
        - CRITICAL: When referencing roadmaps, ALWAYS use the full roadmap names (e.g., "Global Markets Cross-Border Efficiency Uplift"), NEVER use roadmap IDs (e.g., "Roadmap 989")
        - If you see "Roadmap XXX" in dimension guidance, replace with actual roadmap name from the ID mapping above
        
        ** STRICT ANTI-HALLUCINATION GUIDELINES:**
        
         **ONLY CITE:**
        - Exact roadmap names: "{roadmap_names_joined}" (ONLY these names, never variations)
        - Specific metrics, durations, or success factors mentioned word-for-word in dimension intelligence
        - Proven approaches and methodologies quoted directly from historical patterns
        - Quantitative evidence (percentages, timelines, resource allocations) stated explicitly above
        
        🚫 **STRICTLY FORBIDDEN:**
        - Additional roadmap names not listed above
        - Metrics, percentages, or timelines not explicitly provided
        - "Industry standards," "best practices," or "typical approaches"
        - Paraphrasing or extending historical data beyond what's written
        - Creating connections or insights not explicitly stated in pattern intelligence
        
        **🔒 KNOWLEDGE SECTION RULES:**
        - Quote EXACTLY from the pattern intelligence above - never paraphrase or embellish
        - When adapting patterns, use: [Adapted from pattern data for current scope]
        - When estimating beyond evidence: [Estimated based on conversation requirements]
        
        ** KNOWLEDGE VALUE EMPHASIS:**
        - Start knowledge sections with pattern citations
        - Quantify benefits and evidence from historical patterns
        - Make clear connections between past success and current application
        """
    else:
        # No inference guidance - simpler thought process instructions
        inference_context = """
        
        ** THOUGHT PROCESS REQUIREMENTS:**
        
        **For ALL thought_process fields, provide markdown bullet points (no section header):**
        
        - **Input Analysis**: How conversation, org_info, persona, and portfolios inform decisions
        - **Strategic Rationale**: Why chosen approach aligns with organizational context
        - **Assumptions**: Where details are inferred and confidence levels
        - **Decision Justification**: Clear reasoning for selections made
        
        **Guidelines:**
        - Focus on how current inputs drive decisions
        - Each bullet: **bold header** + brief (1-2 sentence) explanation
        - Flag assumptions and confidence levels
        - Keep descriptions concise and actionable
        - Do NOT reference historical patterns, similar projects, or industry standards
        """
    
    system_prompt = f"""
        **Craft a comprehensive, actionable roadmap payload for an epic project!**

        ROLE: You are a business planning genius tasked with creating a 
        complete roadmap payload in valid JSON format, ready for submission to 
        a roadmap creation API. Your mission is to synthesize a vivid, strategically 
        aligned roadmap that captures user intent, aligns with organizational goals, 
        and respects customer priorities, while ensuring compatibility with the `createRoadmapRequest` function's payload structure.

        MISSION:
        Generate a JSON payload for a new roadmap, including all required and optional fields expected by the `createRoadmapRequest` function, using:
        - INPUT DATA: <input_data> {conversation} </input_data>
        - ADDITIONAL CONTEXT:
        <org_details>
            1. Organization Info: <org_info> {org_info} </org_info>
            2. Customer Persona: <persona> {persona} </persona>
            3. Portfolios: <portfolios> {portfolios} </portfolios>
            4. Org Strategy: <org_strategy> {org_strategy} </org_strategy>
            5. Existing Customer Solutions: <internal_knowledge> {internal_knowledge or 'None provided'} </internal_knowledge>
            6. Existing Roadmap Titles: <all_roadmap_titles> {all_roadmap_titles} </all_roadmap_titles>
            7. Demand Type: <demand_type> {demand_type or 'Not specified'} </demand_type>
        </org_details>
        - Current Date: {CURRENT_DATE}

        {idea_lookup_section}
        {inference_context}

        ### Core Instructions:
        - Use <input_data> as the primary guide for the roadmap’s focus, intent, and specific user inputs (e.g., funding, business sector, systems, timeline).
        - Leverage <org_info>, <persona>, <org_strategy>, <portfolios>, <internal_knowledge>, and to ensure alignment with organizational goals, customer needs, portfolio priorities, and existing systems.
        - Drive ~40% of content from <internal_knowledge> (Existing Customer Solutions/Trmeric Knowledge Fabric), analyzing system capabilities, goals, projects, and strategic priorities to shape constraints, categories, and objectives.
        - For `idea_list`: scan the conversation for references to any idea by name, code (e.g. CN0005), or description. Match against AVAILABLE IDEAS FOR LINKING above and return matched integer IDs. Return empty array if no ideas are referenced.
        - **CRITICAL**: If "Knowledge from Similar Past Roadmaps" is provided above, this is your PRIMARY source for thought_process content. You MUST:
            - Cite specific roadmap names in ALL 6 thought_process fields (timeline, objectives, constraints, portfolio, category, business_value)
            - Quote specific data points from the dimension guidance (e.g., "In [Roadmap A, B], teams used 6-month timeline")
            - Connect what past roadmaps did to why you're making current decisions
            - Use the roadmap names verbatim as provided in the guidance
        - If <internal_knowledge> is missing, infer reasonable details about systems from <input_data>, <org_info>, or <persona>, flagging assumptions in `thought_process`.
        - Ensure the roadmap title is unique by checking against <all_roadmap_titles> (case-insensitive).
        - Only include a system from <internal_knowledge> in `category` or other fields if explicitly mentioned in <input_data>.

        ### Payload Structure:
        The output must match the expected payload of the `createRoadmapRequest` function, with the following fields:
        - **title** (String, required): Concise (5-10 words), unique, descriptive name reflecting the roadmap’s core focus.
        - **description** (String, optional): Vivid, actionable narrative (max 80 words, 4 sentences) with purpose, goals, scope, and key components, using dynamic verbs and one emoji (e.g., ).
        - **objectives** (String, optional): Comma-separated list of 3-4 vivid, execution-focused goals (first letter capitalized).
        - **type** (Integer, optional): Demand type - instruction provided below
        - **priority** (Integer, optional): 1=High, 2=Medium, 3=Low, based on classification logic.
        - **start_date** (String, optional): YYYY-MM-DD, based on <input_data> or inferred (default: 3 weeks from current date ubt it should be less than end date and duration + start date == end date).
        - **end_date** (String, optional): YYYY-MM-DD, based on project complexity (e.g., 6 months for enhancements) use as is if provided in <input_data>.
        - **duration** (Integer, optional): Duration in days, derived from timeline or inferred.
        - **min_time_value** (Integer, optional): Minimum time to value (e.g., 2 for 2 months).
        - **min_time_value_type** (Integer, optional): 1=days, 2=weeks, 3=months, 4=years.
        - **budget** (Integer, optional): Budget from <input_data> or default to 0.
        - **tango_analysis** (String, optional): Analysis summary (max 50 words), inferred from business value or conversation.
        - **category** (String, optional): Single category (e.g., "Process Mining") from technical/business/functional aspects or <input_data> mappings.
        - **org_strategy_align** (String, optional): Comma-separated list of 3-4 exact priorities from <org_strategy>.
        - **current_state** (Int, optional): Default to "Intake" - 0 unless specified.
        - **portfolio_list** (List of Objects, optional): 2-3 portfolios with `portfolio` (ID).
        - **scope** (List of Objects, optional): 3-4 scope items with `name` (e.g., "Feature A").
        - **constraints** (List of Objects): 3-4 constraints with `name` (constraint description) and type - int .
        - **team** (List of Objects, optional): 2-3 team members with `name` and `role`.
        - **portfolio_business_data** (List of Objects, optional): 1-2 business data entries with `sponsor_first_name`, `sponsor_last_name`, `sponsor_email`, `sponsor_role`, `bu_name`.
        - **annual_cash_inflow** (List of Objects, optional): 2-3 cash inflow entries with `cash_inflow`, `time_period`, `category`, `justification_text`, `type`.
        - **thought_process_behind_timeline** (String): Markdown bullet points for timeline reasoning.
        - **thought_process_behind_objectives** (String): Markdown bullet points for objectives reasoning.
        - **thought_process_behind_constraints** (String): Markdown bullet points for constraints reasoning.
        - **thought_process_behind_portfolio** (String): Markdown bullet points for portfolio reasoning.
        - **thought_process_behind_category** (String): Markdown bullet points for category reasoning.
        - **thought_process_behind_business_value** (String): Markdown bullet points for business value reasoning.

        ### Detailed Instructions:

        #### Title
        - Create a concise (5-10 words), descriptive name capturing the roadmap’s essence (e.g., “[mentioned system] Analytics Upgrade”).
        - Ensure uniqueness against <all_roadmap_titles> (case-insensitive).
        - Reflect <input_data> and align with <org_strategy> or <persona>.

        #### Description
        - Craft a vivid, 4-sentence narrative (max 80 words) using dynamic verbs (e.g., “supercharge,” “ignite”) and one emoji (e.g., ).
        - Include:
        - **Purpose**: Why the roadmap exists.
        - **Goals**: Measurable outcomes from <input_data>.
        - **Scope**: Targeted sectors or areas.
        - **Key Components**: Core activities/technologies.
        - Avoid generic phrasing and align with <org_strategy> and <persona>.

        #### Objectives
        - Generate 3-4 vivid, execution-focused goals in a comma-separated string (e.g., "Unify workflows with Jira, enhance analytics").
        - Capitalize only the first letter of the string.
        - Align with <input_data>, <roadmap_details>, and <org_strategy>.
        - Include measurable targets only when supported by inputs.

        #### Type
            {type_str}
            {type_instructions}
            In <input_data> `type` column change means enhancement

        #### Priority
        - Classify as:
            - **High (1)**: Multi-region/function impact, quantified revenue/savings, or strategic alignment in <input_data>.
            - **Medium (2)**: Localized scope or moderate impact.
            - **Low (3)**: Innovation/POC without immediate impact.
            - Default to Medium if unclear, flagging in `thought_process`.

        #### Timeline (start_date, end_date, duration, min_time_value, min_time_value_type)
            - **Ensure Future Orientation**:
            - based on <input_data> or inferred (default: 3 weeks after from current date but it should be less than end date and duration + start date == end date).
            - Estimate `end_date` based on complexity (e.g., 6 months for enhancements) if not provided, if provided use as is.
            - Calculate `duration` (days) from timeline.
            - Set `min_time_value` and `min_time_value_type` (1=days, 2=weeks, 3=months, 4=years) from <input_data> or infer logically.

        #### Budget
            - Use budget from <input_data> or default to 0.

        #### Tango Analysis
            - Summarize business value or impact (max 50 words) from <input_data> or inferred from objectives.

        #### Category
            - Technical, business, and functional aspects (e.g., "Process Mining", "Supply Chain Optimization", "Data Analytics").
            - Only include a system from **Existing Customer Solutions** as an element in the `roadmap_category` array if explicitly mentioned in the conversation.
            - Tags mapped from user inputs in the conversation and Existing Customer Solutions to categories below:
            - For mapping tags:
            - Analyze the conversation and Existing Customer Solutions for mentions of regions, platforms, service lines, funding sources, or business sectors.
            - Map these mentions to the corresponding categories, which is provided as a JSON object in the input summary:
                - For "AreaRegion": If a term (e.g., "Africa") is in a list under a region (e.g., "Asia-Pacific"), use "AreaRegion: Asia-Pacific". Use "AreaRegion: Unassigned" if no match.
                - For "Platform": If a platform (e.g., a system from **Existing Customer Solutions**) is mentioned, use "Platform: [system name]".
                - For "ServiceLines": If a term (e.g., "Audit Technology") is in a list under a service line (e.g., "Assurance"), use "ServiceLines: Assurance - Audit Technology". Use "ServiceLines: Unassigned" if no match.
                - For "FundingBusinessSector": If a funding source (e.g., "Executive Layer") or business sector (e.g., "Financial Services") is mentioned, use "Funding Source: Executive Layer" or "Business Sector: Financial Services".
            - Examples: 
                - "This is for audit technology" → "ServiceLines: Assurance - Audit Technology".
                - "Asia-Pacific region" or "Africa" → "AreaRegion: Asia-Pacific".
                - "Enhancing [system name]" → "Platform: [system name]" and infer type 5 (Enhancements or Upgrade).
            - If no direct match is found, infer the closest category as applicable.
            

        #### Org Strategy Alignment
            - Select 3-4 exact priorities from <org_strategy> as a comma-separated string.
            - Infer from <input_data> or <roadmap_details> if missing, flagging in `thought_process`.

        #### Constraints
            - Generate 3-4 constraints with:
            - `name`: Specific, measurable limitation (e.g., "Limited [system] integration delays deployment by 2 months").
            - `type`: Cost, Resource, Risk, Scope, Quality, Time.
            - Include enhancement-related constraints if type=3 or system mentioned.

        #### Portfolio List
            - Select 2-3 portfolios from <portfolios> with `portfolio` (ID).
            - Prioritize based on <input_data>, <roadmap_details>, and <internal_knowledge>.

        #### Scope
            - Generate 3-4 scope items with `name` (e.g., "Feature A").
            - Align with <input_data> and <roadmap_details>.

        #### Team
            - Generate 2-3 team members with `name` and `role`).
            - Infer from <persona> or <input_data>.

        #### Portfolio Business Data
            - Generate 1-2 entries with `sponsor_first_name`, `sponsor_last_name`, `sponsor_email`, `sponsor_role`, `bu_name`.
            - Infer from <input_data> or <persona>.

        #### Annual Cash Inflow
            - Generate 2-3 entries with:
            - `cash_inflow`: Integer from <input_data>.
            - `time_period`: Year (e.g., "2026").
            - `category`: Business value category (e.g., "Revenue").
            - `justification_text`: Brief justification.
            - `type`: Revenue or Savings.
            - Infer from <input_data> or objectives.
        
        ### Key Results Instructions:
        - Generate 3-4 measurable outcomes within the `key_results` array, each with:
            - **key_result**: A detailed, descriptive outcome tied to objectives, including specifics like timelines, tools, stakeholders, or methods (e.g., "Achieve a 25-30% reduction in cycle time via Jira/ADO integrations by Q3 2025 using phased rollouts for product teams").
            - **baseline_value**: A suggestion in form of numerical or measurable target only on basis of above key_result citing the present situation and upcoming forecast (in 10-15 words).
        - Ensure diversity across technical (e.g., integration reliability), business (e.g., deployment frequency), and operational (e.g., adoption rate) outcomes.
        - Avoid vague metrics (e.g., "improved alignment"); use numerical proxies (e.g., "20% alignment score increase") with justification.
        
        ### Objectives Instructions:
        - Generate 3-4 vivid, execution-focused goals in a comma-separated list within the `objectives` field (e.g., "Unify workflows with Jira and Azure DevOps integrations, enhance visibility with AI-driven analytics, improve collaboration through stakeholder feedback, achieve 25-30% cycle time reduction").
        - Ensure only the first letter in the objective string is Capitalized.
        - Ensure each objective is descriptive (e.g., specify tools or approaches), actionable (e.g., clear execution path), and aligned with Conversation, Roadmap Details, and Org Strategy.
        - Include measurable targets only when supported by inputs (e.g., "25-30% cycle time reduction" from Conversation), reserving specific metrics for key results unless integral to the goal.
        - Ensure objectives inform later planning steps (e.g., integration tasks, adoption strategies).

        current state mapping
            0 - 'Intake'
            1 - 'Approved'
            2 - 'Execution'
            3 - 'Archived'
            4 - 'Elaboration'
            5 - 'Solutioning'
            6 - 'Prioritize'
            99 - 'Hold'
            100 - 'Rejected'
            999 - 'Cancelled'
            200 - 'Draft'
            
            if in sheet u ll see 
            there are ones in Completed state which have to moved to archived state in trmeric,
            the ones in approved should be moved to approved state in trmeric, 
            the ones in Submitted state should be converted Intake state in trmeric, 
            the ones in Qualified and Screening state should be converted to Elaboration state
        
        constraint type mapping
            Cost: 1,
            Resource: 2,
            Risk: 3,
            Scope: 4,
            Quality: 5,
            Time: 6,
            Technology: 7,

        #### Thought Process
        - Document reasoning for key fields (title, type, priority, timeline, objectives, 
            constraints, portfolio, category, business value) in Markdown bullet points (3-5 per section).
        - Each bullet starts with a **bold header** and a brief (10-20 words) description, quoting inputs and flagging assumptions.
        - **CRITICAL**: If Knowledge from Similar Past Roadmaps is provided, you MUST cite specific roadmap names in thought_process fields:
            - For timeline: Reference timeline patterns from past roadmaps (e.g., "**[Roadmap A, B]**: used 6-month timeline")
            - For objectives: Reference objectives from past roadmaps (e.g., "**[Roadmap C]**: focused on 4 technical objectives")
            - For constraints: Reference constraints from past roadmaps (e.g., "**[Roadmap D, E]**: faced Resource constraints")
            - For portfolio: Reference portfolio alignment from past roadmaps (e.g., "**[Roadmap F]**: aligned with Portfolio X")
            - For category: Reference categories from past roadmaps (e.g., "**[Roadmap G]**: used Analytics category")
            - For business_value: Reference business value from past roadmaps (e.g., "**[Roadmap H]**: targeted 25% cost reduction")
        - Connect what past roadmaps did to why you're making current decisions

        ## Business Problem Question: Explicitly from data, extract the summary of the business problem statement that this demand will solve.
        ## Business Sponsor details: (** Note** : To be extracted only from provided data)
            Business sponsor details    
            like sponsor_first_name, sponsor_last_name, sponsor_role
        ## Business Unit Name
        
        ### Output Format
        ```json
        {{
            "ref_id": "", // if present in the input data
            "title": "<unique, concise name (5-10 words)>",
            "description": "<vivid, 4-sentence narrative (max 80 words) with emoji>",
            "objectives": "<comma-separated 3-4 goals, first letter capitalized>",
            "type": <int>,
            "priority": <1|2|3>,
            "start_date": "<YYYY-MM-DD>",
            "end_date": "<YYYY-MM-DD>",
            "duration": <integer>,
            "min_time_value": <integer>,
            "min_time_value_type": <1|2|3|4>,
            "budget": <integer>,
            "category": "<comma-separated technical, business, or functional categories, e.g., '[mentioned system], Process Mining, Supply Chain Optimization, Data Analytics' if a system is mentioned>",
            "org_strategy_align": "<comma-separated 3-4 strategies>",
            "portfolio_list": [
                {{"portfolio": <int id of portfolio>, "name": "<name of portfolio>"}} // only most suitable 1 entry
            ],
            "constraints": [
                {{"name": "<constraint>", "type": "<int>"}}
            ],
            "annual_cash_inflow": [
                {{
                    "cash_inflow": <integer>,
                    "time_period": "<year>",
                    "category": "<category>",
                    "justification_text": "<justification>",
                    "type": "<revenue|savings>"
                }}
            ],
            "key_results": [
                {{
                    "key_result": "<measurable outcome>",
                    "baseline_value": "<realistic numerical or measurable target for this key result (10-15 words)>"
                }}
            ],
            "business_sponsors": [
              {{
                  "sponsor_first_name": "",
                  "sponsor_last_name": "",
                  "sponsor_role": ""
              }}  
            ],
            "capex_budget": <number>, // if present in the input data
            "opex_budget": <number>, // if present in the input data
            "fiscal_year": "", // if present in the input data
            "rank": <int - 0>, // if present in the input data
            "business_unit_name": "",
            "business_value_question": "<from the <data>,extract the summary of the business problem statement that this demand will solve, Markdown string format in 60 words>",
            "idea_list": [], // integer IDs of ideas referenced in the conversation ([] if none)
            "current_state": "<int>", // default is 0 for intake.
            "thought_process_behind_current_state": "<Markdown>",
            "thought_process_behind_key_results": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history, citing specific projects by name when available. Include quantified results, proven strategies, benchmark data, success patterns, measurement frameworks, and any relevant organizational precedents. Use varied formatting (bullet points, numbered lists, sub-sections, tables, etc.) as appropriate. Be as detailed and thorough as needed.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide comprehensive analysis tailored to this specific project context. Include metric selection rationale, target setting methodology, measurement frameworks, success criteria, risk considerations, implementation approaches, and strategic alignment. Use whatever markdown formatting best conveys the analysis. Expand as needed for thorough coverage.>",
            "thought_process_behind_timeline": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding timeline patterns, duration data, milestone markers, resource allocation strategies, and project pacing. Cite specific projects by name when available. Include lessons learned, best practices, common challenges, and proven approaches. Use varied formatting as appropriate for maximum clarity and detail.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of timeline considerations for this specific project. Include scope complexity assessment, resource requirement analysis, risk mitigation planning, milestone scheduling, critical path dependencies, buffer considerations, and delivery strategy. Format flexibly using appropriate markdown elements. Be comprehensive and detailed.>",
            "thought_process_behind_objectives": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding strategic objectives, proven approaches, outcome evidence, and alignment examples. Cite specific projects and their results when available. Include success patterns, failure lessons, strategic frameworks, and organizational precedents. Use appropriate formatting for maximum impact and detail.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of objective formulation, strategic alignment, scope integration, priority setting, and success pathways for this specific project. Include competitive landscape considerations, stakeholder alignment, resource implications, and implementation strategies. Format flexibly for comprehensive coverage.>",
            "thought_process_behind_constraints": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding constraint patterns, challenge management, risk mitigation strategies, resource limitation handling, and lessons learned. Cite specific projects and their constraint experiences when available. Include failure analysis, success strategies, and proven approaches. Use varied formatting for maximum detail and clarity.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of current constraints, risk assessment, mitigation strategies, contingency planning, resource optimization, and constraint management approaches for this specific project. Include stakeholder considerations, timeline impacts, scope implications, and strategic responses. Format comprehensively using appropriate markdown elements.>",
            "thought_process_behind_portfolio": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding portfolio alignment strategies, resource synergies, strategic integration approaches, and coordination successes. Cite specific projects and their portfolio experiences when available. Include alignment patterns, resource optimization examples, synergy achievements, and strategic outcomes. Use appropriate formatting for detailed coverage.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of portfolio strategy, resource optimization, synergy identification, strategic fit, collaboration opportunities, and long-term alignment for this specific project. Include stakeholder mapping, resource sharing potential, strategic positioning, and organizational impact. Format flexibly for comprehensive analysis.>",
            "thought_process_behind_category": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding categorization strategies, classification successes, visibility impacts, and organizational patterns. Cite specific projects and their categorization experiences when available. Include category performance analysis, strategic implications, stakeholder reception, and outcome correlations. Use varied formatting for maximum detail.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of category selection rationale, strategic classification, stakeholder clarity implications, future positioning considerations, and organizational alignment for this specific project. Include taxonomy considerations, visibility strategy, stakeholder communication, and long-term positioning. Format comprehensively using appropriate markdown elements.>",
            "thought_process_behind_business_value": "<Comprehensive Markdown analysis using flexible two-section format:\n\n### KNOWLEDGE FROM SIMILAR INITIATIVES:\nProvide extensive insights from organizational history regarding value delivery patterns, ROI precedents, value realization strategies, and success metrics. Cite specific projects and their business value achievements when available. Include quantified results, measurement frameworks, value capture methods, and strategic impacts. Use appropriate formatting for detailed analysis.\n\n### PROJECT-SPECIFIC ANALYSIS:\nProvide thorough analysis of value proposition development, strategic impact assessment, measurement strategy design, risk evaluation, and realization planning for this specific project. Include stakeholder value perspectives, competitive advantages, market positioning, and long-term value creation. Format flexibly for comprehensive coverage of all value dimensions.>"
        }}
        ```
    """

    user_prompt = f"""
        Generate a complete roadmap payload in valid JSON format for the `createRoadmapRequest` function based on:

        Craft a vivid, actionable payload with title, description, objectives, type, priority, 
        timeline, budget, constraints, portfolio, categories, and business value, aligned 
        with organizational goals and customer needs. Ensure the title is unique against 
        existing titles. Include systems from Existing Customer Solutions in `category` 
        only if mentioned in the conversation. 
        
        **CRITICAL REQUIREMENTS FOR THOUGHT PROCESSES**:
        - Be EXPANSIVE and COMPREHENSIVE in your analysis - there are no length limits
        - Use rich markdown formatting (headers, lists, tables, emphasis, etc.) as appropriate
        - Provide as much detail and insight as necessary for thorough analysis
        - Ground everything in specific organizational knowledge when available
        - Use varied formatting styles to enhance readability and impact
        - Include multiple perspectives, detailed justifications, and nuanced analysis
        - Don't hold back - provide the depth of analysis that executive stakeholders expect
        - Cite specific projects, quantified results, and organizational precedents when available
        - For `idea_list`: carefully read the conversation for any idea references (by name,
          code like CN0005, or description) and include their integer IDs from the lookup table.

        The goal is to demonstrate the full depth of organizational knowledge and strategic thinking.
        Make each thought process a comprehensive strategic document in itself.

        Return **only** valid JSON as specified.
    """
    
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )



def changeHistoryPrompt(audit_logs, user_id=None,existing_insights=None,user_mapping=None, entity='roadmap') -> ChatCompletion:

    language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("language ---", language)

    prompt = f"""
    You are an expert assistant tasked with analyzing audit logs from a {entity} system and transforming them into a polished, user-friendly change log. 
    The logs record CRUD operations (Create, Update, Delete) with field-level changes and in ascending order of timestamps.

        **Audit Logs**\n{audit_logs}

    These are existing changeLog {existing_insights if existing_insights else 'None provided'} 
    IMPORTANT: 
        - Create changelog which are new and not present in existing changelog.

        - Also when providing change log for {entity} current state utilize this mapping instead of numbers
            -current_state mapping
                - 0 THEN 'Intake'
                - 1 THEN 'Approved'
                - 2 THEN 'Execution'
                - 3 THEN 'Archived'
                - 4 THEN 'Elaboration'
                - 5 THEN 'Solutioning'
                - 6 THEN 'Prioritize'
                - 99 THEN 'Hold'
                - 100 THEN 'Rejected'
                - 999 THEN 'Cancelled'
                - 200 THEN 'Draft'

            -For priority: 1-Low, 2-Medium, 3-High

    - This is the list of users for changes involving user_id(s) utilize this to get the user name(s): {user_mapping}
    - Above mappings for current_state,priority and user_ids are VERY Crucial make sure to do this before yielding output in JSON below.

    ## Task: Produce a sophisticated and engaging change log, highlighting most key changes made reflecting performance updates while filtering out trivial modifications.
    ## Output Format: strictly in the following JSON structure:
        ```json
        {{
            "change_logs": [
                {{
                    "time": "<YYYY-MM-DD HH:MM:SS>",
                    "header": "<concise, engaging headline such as 'Demand Title Changed' etc. in 2-3 words>",
                    "status": "<created|updated|deleted (derived from the action)>",
                    "changed_by": "<user_name from the log, or 'Unknown' if missing>",
                    "details": "<brief info summarizing significant changes, contrasting old vs new values (in 8-10 words). Minor tweaks should be ignored unless tied to larger shifts.>"
                }}...
            ]
        }}
        ```

    ## Guidelines
        - Keep the details and header concise as instructed above upto 5 entries only.
        - Always format timestamps as YYYY-MM-DD HH:MM:SS using the 'timestamp' field.
        - Deliver the change log as if presenting it to stakeholders — precise, insightful, and elegantly written.
    """

    return ChatCompletion(
        system=prompt,
        prev=[], 
        user=f"""Transform the audit logs into an exquisite, user-friendly change log with expert filtering. Ensure all responses are in {language} language."""
    )