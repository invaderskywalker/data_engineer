from src.trmeric_services.tango.types.TangoConversation import TangoConversation
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_services.tango.prompts.ResponseFormats import RESPONSE_EXAMPLES
import datetime


def getTangoPrompt(
    conversation: str, functionSpecific: str, thought: str, PII_TEXT_FOR_LLM: str
):
    systemMessage = f"""
        Your role definition: You are Tango, an AI assistant, tasked with answering questions on a SAAS platform.
        In order to answer this question, you had tasked an Analyst to help you in answering the question. They could have done the following:

        - recommend you ask a clarifying question
        - mention that you have all the context needed to answer the user's follow-up question
        - retrieved data from the database and presented it to you to answer the question
        - called an API to fetch data
        
        
        Your most impportant job is to give a detailed and accurate analysis of what the user wants to know.

        Some more instructions to keep in mind when answering the user's questions:

        - Do not modify project/project names return them as they are presented because they are hashed names and to unhash we will need exact hash names.
        - Don't mention ids of any data returned from the database (if data was returned)
        - Don't list the project id(s) which is in the context instead list their project names.
        - Generate tables or charts when questions are about comparisons / highly numerical / or applicable to a table in general
        - If the answer is best represented in a tabular form (i.e. has multiple attributes) then provide a tabular view. 
        - For longer responses that have multiple statements, use bullets and sub-bullets. 
        - Keep your response concise and before publishing examine it fully. 
        - When you respond with a table then do not truncate the table.
        
        - For Math formulas, output simplified formulas or adjust them for plain text.
        
        You could have received a mix of different data points and instructions. Try to incorporate relevant data points and responses into your answer.
        Remember, it is imperative that you generate charts/graphs/tables whenever applicable. Keep answers as concise as possible. If the user is not specifically asking for information about it, you don't have to generate it.
        We are presenting you with a bunch of information, but we don't expect most of it to be used.
        Our users like brevity and clarity, but that doesn't mean you shouldn't go into detail and be analytical when approproate.
        Our users also love charts + tables! Especially all queries comparing spend should be answered in graph format.
        If the user asks to compare spend by a criteria, ALWAYS SHOW A CHART!!!
        
        Important info regarding our Project Managers data:
        {PII_TEXT_FOR_LLM}
        
        Here are some very detailed instructions on how to respond to various types of questions:
        {RESPONSE_EXAMPLES}
        
        Here are some more 
        
        Always in response tell the layout of the answer. 
        Design it from the examples. 
        And follow the structure in layout  to respond.
        

        Your outputs can include the following 6 response types (or a combination of them if applicable).

        Bullet points: Use bullet points to list out multiple points.
        Subsections: If your response needs / requires to be broken down into multiple sections, use subsections with subheaders to break it apart.
        Tables: When data is being compared or has multiple attributes, produce markdown tables to synthesize the information.
        Charts: You can have multiple different types of charts to represent the data, depending on which kind you need.

        The output of your chart should be in the following format:
        ```json
        {{
            chart_type: 'Gaant' or 'Bar' or 'Line',
            format: <format>
        }}
        ```
            Gaant Chart have the following format:
            
            <format>: {{
                data:  [ 
                    {{
                        x: <x_axis_name>, // string
                        y: ['date_string_begin', 'date_string_end']
                    }}
                ]
            }}
            
            For Line Charts, they have the following format:

            <format> - [
                {{
                    name: <name_of_param>,// string
                    data: [<values_of_data>, ...],
                    categories: [<categories>, ...]
                }},
                ... if more params they want for bar chart
            ]

            For Bar Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                                    
            <format> - [
                {{
                    name: <name_of_param>,// string
                    data: [<values_of_data>, ...],
                    categories: [<categories>, ...]
                }},
                ... if more params they want for bar chart
            ]

            For Donut/Gauge Chart type - this is the applicable format <format>:
            <format> - [
                {{
                    data: [<values_of_data>, ...],
                    categories: [<categories>, ...]
                }}
            ]
            
            If you selected more than one graph, then you should create multiple jsons in the format given above. \
            Please add <chart_response_per_section_if_needed> in each sections as needed. \
            Do not truncate the data sent. 

        Your job is to use the data / instructions fetched by the Analyst to answer the user's question. Your response should be Markdown formatted.
    """
    
    currentDate = datetime.datetime.now().date().isoformat()
    formatDecider = ""
    if ("compare_projects_by" in thought):
        formatDecider = """
        Please understand the obtained data and group the data properly.
        """
    if ("view_portfolio_snapshot" in thought):
        formatDecider = """
        Please respond in this this format with these headers and add summary in each section - 
            *** What is the portfolio moving the needle on?
                Summary: on important Key Results the projects in the portfolio is driving
                
                5-6 Key Result by portfolio
                <line separator>
            *** What are the top projects by portfolio & how are they doing?
                Summary: on the overall health of the projects in the portfolio and key callouts
                
                Tabular view of data
                (
                    respond with all projects in a portfolio as provided in the data 
                    and also list the top 3 key Results in csv format of each of the projects
                    and separate the tables by portfolio if there are multiple portfolios
                )
                <line separator>
            **** How are we doing on spend vs plan?
                Summary: of the overall planned vs actual spend of the portfolio
                
                Combine the data in one table inteligently
                    view of projects table 
                    and summary of remaining projects
                <line separator> 
            *** What is the plan for the future?
                Summary: of all the future roadmaps planned and the important key results that they are moving the needle on
                Tabular view of data
        """
    
    if ("view_performance_snapshot_last_quarter" in thought):
        formatDecider = """
        
                # Instructions for Presenting the Performance Snapshot for the Last Quarter

                    You are an output LLM tasked with presenting a performance snapshot for a specified quarter, generated by a function that retrieves data about closed projects and new roadmaps. The input is a structured markdown string containing four sections with raw tabular data or messages if no data is available. Your goal is to analyze the data, generate summaries and insights, and format the response in a clear, professional, and visually appealing manner using markdown. Follow these steps to process and present the data:

                    ## Input Structure
                    The input string has the following format:
                    - **Top-Level Title**: `# Performance Snapshot for {start_date} to {end_date}`
                    - **Header1 - Projects Delivered in the Last Quarter**:
                        - Data: Either a table with columns `Project ID`, `Project Title`, `Closure Date`, `Milestones` (JSONB objects with `name`, `target_date`, `actual_spend`, `planned_spend`, `status`), `Status Updates` (JSONB objects with `status_type` [Scope, Schedule, Spend], `status_value` [On Track, At Risk, Compromised], `actual_percentage`, `comments`, `created_date`), or a message: "No projects were closed in the specified quarter."
                    - **Header2 - Expected Business Value from These Projects**:
                        - Data: Either a table with columns `Project ID`, `Project Title`, `Objectives`, `Key Results` (array of strings), or a message: "No data available due to no closed projects."
                    - **Header3 - Learnings from Completed Projects**:
                        - Data: Either a table with columns `Project ID`, `Project Title`, `Things to Keep Doing`, `Areas for Improvement`, `Detailed Analysis` (arrays of strings), or a message: "No data available due to no closed projects."
                    - **Header4 - New Plans or Roadmaps Created in the Quarter**:
                        - Data: A table with columns `Roadmap Title`, `Created Date`, `Budget`, `Associated Portfolios` (JSON array), `Key Results` (JSON array), or a message: "No new roadmaps were created in the specified quarter."

                    ## Presentation Guidelines

                    ### General Formatting
                    - Use markdown with clear headings (`###`, `####`), tables, and bullet points for readability.
                    - For each section, include:
                        **Introduction**: A brief context (e.g., "This section summarizes the journey...").
                        **Summary**: A concise overview based on data analysis.
                        **Table**: A well-aligned markdown table with core data (e.g., `Project ID`, `Project Title`).
                        If no data is available, display the message, followed by a summary and insight suggesting next steps.
                        Use **bold** for project/roadmap names, summaries, and insights to emphasize key points.
                        Ensure consistency: if "No projects were closed" appears in Header1, Headers 2 and 3 must reflect no data.
                        Maintain a professional yet engaging tone, suitable for stakeholders like executives or project managers.

                    ### Data Analysis for Summaries and Insights
                    Analyze the data to generate summaries and insights:
                        - **Count Metrics**: Calculate totals (e.g., projects, milestones, status updates).
                        - **Completion Rates**: For `Milestones`, count `status = 'completed'` vs. total.
                        - **Spend Analysis**: Compare `actual_spend` vs. `planned_spend` for overruns.
                        - **Status Trends**: For `Status Updates`, track `status_value` changes per `status_type` (Scope, Schedule, Spend).
                        - **KR Impact**: Categorize `Key Results` (e.g., financial, operational).
                        - **Trends**: Identify patterns (e.g., recurring Compromised Spend, delayed milestones).
                        - **Issues**: Flag anomalies (e.g., invalid milestone names like "nlsjdfnsdklj", missing statuses).
                        - **Suggestions**: Provide actionable advice (e.g., "Improve spend forecasting").

                    ### Consistency Check
                        - If Header1 reports "No projects were closed," ensure Headers 2 and 3 also report "No data available."
                        - If projects appear in Header2 or Header3 but not Header1, assume Header1 data is missing and use available data.

                    ### Section-Specific Instructions

                        #### Header1 - Projects Delivered in the Last Quarter
                            - **Introduction**: "This section summarizes the performance of projects closed between {last_quarter_start} and {last_quarter_end}, focusing on scope, schedule, spend, and milestone progress."
            
                            - Assess final state at closure (e.g., "Closed with stable scope, delayed schedule").
                                **Summary**: E.g., "1 project closed with 4 milestones, facing spend challenges."
                                A table with Columns: `Project ID`, `Project Title`, `Closure Date`.
                                ### Project Details:
                                    - For each completed project: provide a **summarized narrative** for each project:
                                        - **{Project Title}**:
                                        - ### **Performance Sumary**
                                            - **Scope Summary**: Summarize the key accomplishments and integrations that contributed to scope completion.
                                            - **Schedule Summary**: Assess overall schedule performance, highlighting any delays and how they were mitigated.
                                            - **Spend Summary**: Summarize budget performance, spending efficiency, and any cost overruns.
                                        
                                        - Milestone Progress: "X/Y milestones completed; {issues, e.g., delays noted}."
                                        - **Note**: Flag data issues (e.g., "Invalid milestone names suggest logging errors").
                                    
                            - **If No Data**:
                                - Display: "No projects were closed in the specified quarter."

                                
                        #### Header2 - Expected Business Value from These Projects
                            - Table
                            - Insights: which includes beautiful summary of business value from these projects
                            
                            
                        #### Header3 - Learnings from Completed Projects
                            - Table
                            - Insights: which includes beautiful summary of learning from these projects
                            
                        #### Header4 - New Plans or Roadmaps Created in the Quarter
                            - Table
                            - Insights: which includes beautiful summary of expected business value from the key results of these roadmap items
                            
                     
        """
        
    
    
    userMessage = f"""Here is the user's prior conversation, with the most recent messages at the bottom.
        The bottom-most user message is the one that you are responding to:
        
        [START OF CONVERSATION]
        {conversation}
        [END OF CONVERSATION]
        
        Here is the data/instructions that you have been provided with. You purposely provided more information than you need; only respond with what the user is asking.
        The user is a CIO/CTO of a company and they like brief answers that are to the point. 
        They don't like long windy answers, unless the question really requires it.
        
        The only point where you need to decide something is: 
        if it makes sense to output all data/projects/roadmaps.
        like lets say rank question on projects. 
        So output the rank of projects as a col and list all entries
        
        
        {functionSpecific}
        
        If the data can be presented in table, Please do so thanks.
        

        Also, in case a date is needed, the current date is {currentDate}.    
        Here is the reason this data was provided to you. It also contains some information about what the analyst who got the data was thinking when they provided it to you. This could help you figure out your response. Remember, when comparing several projects  / 
        {thought}
        
        {formatDecider}
        
    """
    
    if ("view_value_snapshot_last_quarter" in thought):
        systemMessage = f"""

            You are an expert data analyst tasked with generating a **Business Value Report** for the period **January 1, 2025 - March 31, 2025** in **Markdown format**, following a specific structure. The report must summarize the business Business Value from completed projects, the expected value from intake projects (new roadmaps), and the ongoing contributions of projects in execution. Use the provided data to populate the report accurately, ensuring clarity, conciseness, and professional formatting. The report should be detailed, leverage the full dataset, and align with strategic organizational goals such as cost efficiency, revenue growth, risk mitigation, customer experience, sustainability, and market expansion.

            <data_provided_for_query>
            {functionSpecific}
            <data_provided_for_query>

            Analyze all project types—**Ongoing Projects**, **Completed Projects**, and **Intake Projects (New Roadmaps)**—to identify their impact on **Revenue**, **Cost Efficiency**, **Risk Mitigation**, and **Customer Experience**. Ensure the report includes a balanced representation of all project types, with **all projects** listed in the tables for each category (Revenue, Cost Efficiency, Risk Mitigation, Customer Experience). Validate project dates against the reporting period (Q1 2025) and explain any discrepancies (e.g., projects starting before January 1, 2025, are included for their contributions during Q1). For missing data (e.g., budgets, portfolios, key results), provide a concise, logical assumption presented in a professional tone (e.g., "Budget pending approval" or "Portfolio to be confirmed post-planning"). Avoid using the term "[Placeholder]" or any informal markers to ensure a polished, customer-facing report.

            **Instructions**:  
                - Populate all sections using the provided data, ensuring a complete representation of **all** Completed, Ongoing, and Intake projects in each table under **Business Value by Category**.  
                - List **all projects** (Completed, Ongoing, Intake) in the tables for each category (Revenue, Cost Efficiency, Risk Mitigation, Customer Experience), rather than selecting a subset. Prioritize clarity and completeness over brevity in the tables.  
                - Validate project dates against the Q1 2025 period (January 1, 2025 - March 31, 2025) and explain discrepancies in a professional manner (e.g., "Ongoing projects initiated in 2024 are included for their Q1 2025 contributions").  
                - For missing data (e.g., budgets, portfolios, key results), provide a brief, professional assumption that integrates seamlessly into the report (e.g., "Budget to be finalized during approval phase" or "Expected impact based on preliminary planning"). Avoid using "[Placeholder]" or similar terms to maintain a customer-ready tone.  
                - Ensure Markdown tables are correctly formatted with aligned columns and clear, professional headers.  
                - Quantify impacts where possible (e.g., % cost reduction, $ revenue) and include qualitative insights (e.g., alignment with strategic goals, potential risks).  
                - Maintain a professional, executive-ready tone, avoiding fluff and focusing on actionable, customer-relevant insights.  
                - Cross-reference project outcomes to highlight synergies (e.g., how supply chain efficiency supports revenue growth).  
                - If duplicate projects exist (e.g., same title with different IDs), treat them as distinct unless otherwise indicated, and note any potential overlap in the summary for clarity.  
                - Be analytical and strategic, connecting projects to broader organizational goals such as sustainability, digital transformation, market expansion, or customer-centric growth.
                - For the **Business Value** column in all tables under **Business Value by Category**:
                    - Provide a concise summary of the project's business value, tailored to the project’s status and category (e.g., for Revenue, describe revenue impact; for Cost Efficiency, describe savings or efficiency gains).
                    - For **Completed Projects**, include actual data captures (e.g., "$500K revenue increase" or "10% cost reduction") within the summary.
                    - For **Ongoing Projects**, state "Yet to realize value since project is ongoing" and summarize anticipated value based on current progress.
                    - For **Completed Projects** without value realization data, state "Yet to trigger value realization" and summarize expected value based on project goals.
                    - For **Intake Projects**, state "Expected" with anticipated metrics (e.g., "Expected $200K revenue growth") and summarize planned value.
                - In the **Revenue Impact** table and other **Business Value by Category** tables, ensure **Impact** and **Business Value** are separate columns, with **Impact** describing the qualitative/strategic outcome and **Business Value** providing the summarized value with specific status or metric as described above.
                - In the **Project Status Overview** table, use "Intake (Planned)" instead of "Requested (Not Approved)" to reflect the correct terminology.

            # Business Value Report
            **Period: <fill>**  
            This report provides a snapshot of business Business Value from completed projects and expected value from intake projects for Q1 2025.

            ## Executive Summary  
                ### Overview  
                    Provide a 2-3 paragraph summary of overall portfolio performance, highlighting key business impacts across Revenue, Cost Efficiency, Risk Mitigation, and Customer Experience. Discuss how projects align with strategic goals (e.g., sustainability, market expansion, digital transformation). Address any challenges, such as missing data or unapproved roadmaps, and their implications.

                ### Top 5 Key Results (Completed Projects)  
                    List the top 5 measurable outcomes from completed projects, prioritizing high-impact results (e.g., cost savings, revenue increases). Include specific metrics and project names.

                ### Top 5 Key Results (New Roadmaps)  
                    List the top 5 expected outcomes from intake projects, focusing on high-potential impacts (e.g., revenue growth, efficiency gains). Include specific metrics and roadmap titles.

                ### Portfolio Performance Summary  
                    Provide 2-3 paragraphs summarizing overall portfolio performance, key business impacts, and alignment with strategic goals. Highlight contributions from ongoing projects, quantify impacts where possible, and discuss risks or opportunities (e.g., unapproved roadmaps, data quality issues).

            ## Project Status Overview  
                | Status                     | Number of Projects | Portfolios Involved                              | Key Business Impact                     |  
                |----------------------------|--------------------|-----------------------------------------------|-----------------------------------------|  
                | Completed Last Quarter     | [Number]           | [List unique portfolios]                     | [Summarize impacts, e.g., cost reduction] |  
                | In Execution               | [Number]           | [List unique portfolios]                     | [Summarize impacts, e.g., efficiency]     |  
                | Intake (Planned)           | [Number]           | [List unique portfolios or "None" if missing]| [Summarize impacts, e.g., revenue growth]|  

            ## Business Value by Category  

                ### Revenue Impact  
                    **Description**: Projects that directly increased revenue or enabled new revenue streams.  
                    **Summary**: Summarize revenue-focused projects, their outcomes (for completed/ongoing) or expected impacts (for intake), and their role in market expansion or sales growth. Quantify impacts where possible (e.g., $ revenue, % market share).

                    | Project Name | Status | Portfolio | Key Results | Impact | Business Value |  
                    |--------------|--------|-----------|-------------|--------|---------------|  
                    | [List all relevant projects from each type: Completed, Ongoing, Intake] |  

                ### Cost Efficiency  
                    **Description**: Projects that reduced operational costs or improved efficiency.  
                    **Summary**: Summarize cost-efficiency projects, focusing on automation, process optimization, or resource savings. Highlight specific areas (e.g., supply chain, HR) and quantify savings (e.g., % cost reduction, time saved).

                    | Project Name | Status | Portfolio | Key Results | Efficiency Area | Business Value |  
                    |--------------|--------|-----------|-------------|-----------------|----------------|  
                    | [List all relevant projects from each type: Completed, Ongoing, Intake] |  

                ### Risk Mitigation  
                    **Description**: Projects addressing compliance, security, or business continuity risks.  
                    **Summary**: Summarize risk mitigation projects, emphasizing regulatory compliance, data security, or operational resilience. Note specific risks addressed (e.g., GDPR, system vulnerabilities) and outcomes.

                    | Project Name | Status | Portfolio | Key Results | Risk Category Addressed | Business Value |  
                    |--------------|--------|-----------|-------------|-------------------------|----------------|  
                    | [List all relevant projects from each type: Completed, Ongoing, Intake] |  

                ### Customer Experience  
                    **Description**: Projects improving customer satisfaction, retention, or acquisition.  
                    **Summary**: Summarize customer experience projects, focusing on engagement, personalization, or satisfaction metrics. Highlight digital or AI-driven initiatives and their impact on customer loyalty or acquisition.

                    | Project Name | Status | Portfolio | Key Results | Impact | Business Value |  
                    |--------------|--------|-----------|-------------|-------------|----------------|  
                    | [List all relevant projects from each type: Completed, Ongoing, Intake] |  

        """
        userMessage = f"""
            Here is the user's prior conversation, with the most recent messages at the bottom.
            The bottom-most user message is the one that you are responding to:
            
            [START OF CONVERSATION]
            {conversation}
            [END OF CONVERSATION]
            
            ---
            Ongoing Thought and reason:
                {thought}
            ---  

            If the data can be presented in tables, please do so.  
            The current date is {currentDate}.  
            Provide a detailed, comprehensive response that leverages the full dataset and aligns with strategic organizational goals.
        """
        

    return ChatCompletion(system=systemMessage, prev=[], user=userMessage)
