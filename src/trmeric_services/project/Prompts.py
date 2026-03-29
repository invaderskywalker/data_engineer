from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import datetime


def projectInsightsPrompt(canvas: str, existing_projects: str, language: str = "English") -> ChatCompletion:
    system_prompt = f"""
        You are an expert execution consultant and analyst for trmeric MISSIONS. Your role is to generate actionable, data-driven insights for a newly created project canvas, helping portfolio leaders, demand managers, and execution teams optimise delivery, accelerate timelines, and mitigate risks.

        This project canvas represents the transition from planning (roadmap) to execution, and your insights should focus on making the project faster, more efficient, and aligned with organisational goals. Speak in a professional, consultative tone — as if advising senior leaders on how to drive this lifecycle forward.

        **Input Data**:
        - **Project Canvas**: {canvas} (details like title, scope, objectives, workstreams, milestones, owners, dates, risks, dependencies, and any thought processes).
        - **Existing Projects**: {existing_projects} (JSON array of past/completed projects, each with title, scope, start_date, end_date, and any other relevant attributes).

       **TASK**: Analyze the project and generate **Project Insights** in the exact structure below.
        1. Start with a **2–3 sentence punchy header** (max 30-70 words) that captures:
        - Core execution focus and value
        - Estimated timeline range based on comparable existing projects
        - Overall delivery confidence (High/Medium/Low)

        2. Then provide **Details** across exactly these dimensions.
          Use **2–3 short, data-backed bullets per dimension** (max 10-30 words per bullet).

        - **Scope & Acceleration Opportunities**  (compare scope, identify reuse, suggest timeline compression)
        - **Resource Fit & Team Recommendations**  (skills needed, bottlenecks, optimal sizing from benchmarks)
        - **Risks, Dependencies & Mitigation Path**  (key risks vs past projects, dependencies, proven mitigations)
        -  **Timeline Estimation & Acceleration** (Estimate realistic timeline based on existing projects' durations, Recommend ways to compress the timeline, such as parallel workstreams, leveraging pre-built assets)
        - **Business Value & Prioritization**:(ways to maximise value, such as quick wins, assess the project's potential impact for milestones)

        **OUTPUT FORMAT** (strict JSON):
        ```json
        {{
            "insights": "<Markdown string in clear structure as instructed above>"
        }}
        ```

        **Critical Rules**:
        - Explicitly reference similar existing projects by title when relevant (e.g., "Similar to Project X, which completed in Y months").
        - Be concise but concrete. Prefer numbers, comparisons, and execution levers.
        - Tone: professional, decisive, advisory — like a trusted delivery lead briefing senior stakeholders.
        - Total output length: 100–200 words max.
        - Language: Respond exclusively in **{language}**.
    """

    user_prompt = f"""Generate the project insights in the specified JSON format as instructed."""
    return ChatCompletion(system=system_prompt,prev=[],user=user_prompt)

def createKeyAccomplishmentPrompt(project_status_updates) -> ChatCompletion:
    prompt = f"""
        You are an AI assistant and your task is to identify the key accomplshments that has happened in a project.
        
        you wil have the data of all of the project status updates;
        <project_status_updates>
        {project_status_updates}
        <project_status_updates>
        
        
        The meaning of the fields in the <project_status_updates> array are as follows: \
        1. status_type 
            - 1 means scope \
            - 2 means schedule \
            - 3 means Spend \
        2. status_value - this is important for measuring risk \
            - 1 means "on Track" which represent green \
            - 2 means "At Risk" which represents amber \
            - 3 means "High Risk" which represents red \
        3. status_comments - comments added by customer \
            
            
        
        Please respond with key accomplishments in proper json format
        ```json
        {{
            key_accomplishments: [], // the accomplishments should be formatted in a professional tone
        }}
        ```
        
    """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def enhanceDescriptionPrompt(
    name, desc, org_persona, org_details, context_of_projects_in_portfolio,org_strategy=None
) -> ChatCompletion:
    knowledge_context = ''
    if context_of_projects_in_portfolio:
        knowledge_context = f"""
            <context_of_previous_projects_in_portfolio>
            {context_of_projects_in_portfolio}
            <context_of_previous_projects_in_portfolio>
            
            Use ths <context_of_previous_projects_in_portfolio> and learn from it to create data for this current project better.
        
        """
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Now provided below is the details about the organisation

        <org_info>
            {org_details}

            Other details:
            {org_persona}
        <org_info>
        
        {knowledge_context}

        <list_of_org_strategies>
            {org_strategy}
        </list_of_org_strategies>
        
        A rough project description is provided by the customer for the project name: {name}
        <rough_description>
        {desc}
        <rough_description>
        
        Your job is to -
        1. enhance this rough project description - Please generate a detailed and contextual project description. Ensure that the description reflects the unique aspects of the project, including its objectives, challenges, and key deliverables, making it highly relevant to the scope of work outlined.
            Make sure that you give importance to the project name or project <rough_description> and use <org_info> only as a reference point  to understand the customer context.
        2. create enhanced objective of this project - Please outline the specific objectives of the project based on the provided project scope. Ensure the objectives are clear, concise, and directly aligned with the project’s goals, highlighting the key outcomes expected.
        3. Create project Capabiltities for this project. Highlight key capabilities required for this project, tailored to the industry, domain, broader technology areas and functionality aligned to the project description or scope for eg.. Data analytics, ERP, CRM, Supply chain management, Cloud, Integration, AI, Infrastructure Management etc as few examples
        4. tech_stack - create key technologies involved to execute the project scope/ project description like SAP, Salesforce, Python, React, Nodejs, Docker, Java etc 
        5. choose project type and stage for the project from the list, give 1-2 line desc on org strategy alignment
        6. team_name - give a short but innovative names to teams
        7. job_roles_required - make it very contextual to the scope of the project, make sure to list all roles required to execute the project
        8. Choose the `org_strategy_align` for this project **STRICTLY** from <list_of_org_strategies>
        
        
        Make sure it is aligned with the project name and <rough_description>
        
        Output in Json Format:
        ```json
            {{
                enhanced_description: '', // text
                enhanced_objective: '', // text
                project_capabilities: [], // array of string which represent capability, return only upto 3
                tech_stack: [], // array of string which represent tech, return only upto 5
                sdlc_methodology: '', // one of Agile, Waterfall, Hybrid -  derive this based on how project described in enhanced_description are typically executed across industries. for example - SAP projects follow Waterfall, Product development is done through Agile etc
                team_name: '', // only 1 team name - required for completion of this project
                job_roles_required: [], // upto 5
                project_type: '', // one of Run, Transform, Innovate - look at the enhanced_description and identify what type of project is this. For example support related projects are of project_type Run, AI based projects typically are Innovate project_type etc
                project_stage: '',  //choose one from (Discovery, Design, Build, Complete)
                org_strategy_align: '', // Alignment with org strategy or empty from <list_of_org_strategies>
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def enhanceProjectObjectivePrompt(
    name, desc, org_persona, org_details, project_objective
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Now provided below is the details about the organisation

        <org_info>
            {org_details}

            Other details:
            {org_persona}

        <org_info>

        
        A project name and description  and a rough project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <rough_project_objective>
            {project_objective}
            <rough_project_objective>
        
        Your job is to enhance this rough_project_objective
        and make sure it is aligned with the <org_info> and project name and project description
        
        Output in Json Format:
        ```json
            {{
                enhanced_objective: '',
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createKeyResultsPrompt(
    name, desc, org_persona, org_details, project_objective
) -> ChatCompletion:
    prompt = f"""
    
        You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation.

        Now provided below is the details about the organisation
        ###Input
        <org_info>
            {org_details}

            Other details:
            {org_persona}

        <org_info>

        ###Task
        A project name and description  and a project objective are provided by the customer:
        <project_details>
            <project_name>
            {name}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
        </project_details>
        
        Your job is to create 3-4 Key results for this project and also generate a single scope item for the project in Markdown string (in 200 words).
        Make sure these are aligned with the <org_info> and <project_details>.
            
        Output in Json Format:
        ```json
            {{
                key_results: [], // array of string which represent key results. return only upto 3 key results
                "scope": [
                    {{"name": "<single Markdown string (in 200 words) with scope details, requirements, risk & constraints, out-of-scope>"}}
                ],
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createProjectCapabilitiesPrompt(
    name, desc, org_persona, org_details, project_objective, project_key_results
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Now provided below is the details about the organisation

        <org_info>
            {org_details}

            Other details:
            {org_persona}

        <org_info>

        
        A project name and description  and a project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
            
            
            <project_key_results>
            {project_key_results}
            <project_key_results>
        
        Your job is to create project Capabiltities for this project.
        which is defined as Creating broad technology, domain, functional capabilities aligned to the project description or scope for eg.. Data analytics, ERP, CRM, Supply chain management, Cloud, Integration, AI, Infrastructure Management etc as few examples
        
        Output in Json Format:
        ```json
            {{
                project_capabilities: [], // array of string which represent capability, return only upto 3
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def findTechStackPrompt(
    name, desc, org_persona, org_details, project_objective, project_key_results, project_capabilities
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Now provided below is the details about the organisation

        <org_info>
            {org_details}

            Other details:
            {org_persona}

        <org_info>

        
        A project name and description  and a project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
            
            
            <project_key_results>
            {project_key_results}
            <project_key_results>
            
            <project_capabilities>
            {project_capabilities}
            <project_capabilities>
        
        Your job is to list down the tech stack required to finish this project
        
        Only return tech stack terms like python, java
        Output in Json Format:
        ```json
            {{
                tech_stack: [], // array of string which represent tech, return only upto 5
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def portfolioSelectorPrompt(
    project_name, portfolios
) -> ChatCompletion:
    print("debug__portfolioSelectorPrompt-- ", project_name, portfolios)
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Bit you have a simple task of identifying the portfolio of the project from its name:
        project name - {project_name}
        
        
        The list of portfolios to select from - {portfolios}
        Output JSON:
        ```json
            {{
                selected_portfolio_id: '',
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createProjectDataV2(
    name, desc, org_persona, org_details, portfoliosOfTenant, org_strategy_alignment, is_provider=False, customerInfo=None, inference_guidance=None
) -> ChatCompletion:
    knowledge_context = ''
    if portfoliosOfTenant:
        knowledge_context = f"""
            <portfolios_of_tenant>
            {portfoliosOfTenant}
            </portfolios_of_tenant>
            
            Use the <portfolios_of_tenant> to understand the tenant's portfolio context and enhance the data for the current project. Do not directly copy or reuse descriptions from <portfolios_of_tenant>; instead, learn from the context to tailor the current project's data.
        """
    
    # Build inference guidance section if provided
    inference_context = ''
    if inference_guidance:
        templates = inference_guidance.get("matching_templates", [])
        patterns = inference_guidance.get("matching_patterns", [])
        guidance_text = inference_guidance.get("inference_guidance", "")
        delivery_themes = inference_guidance.get("delivery_themes", [])
        delivery_approaches = inference_guidance.get("delivery_approaches", [])
        delivery_criteria = inference_guidance.get("delivery_success_criteria", [])
        match_info = inference_guidance.get("match_info", {})
        
        # Use pattern_reference if available (new structure), fall back to extracting from patterns
        pattern_ref = inference_guidance.get("pattern_reference", {})
        if pattern_ref:
            project_names = pattern_ref.get("project_names", [])
            pattern_name = pattern_ref.get("pattern_name", "")
            pattern_id = pattern_ref.get("pattern_id", "")
            project_count = pattern_ref.get("project_count", len(project_names))
        else:
            # Fall back to extracting from matched pattern
            project_names = []
            pattern_name = ""
            pattern_id = ""
            if patterns:
                pattern = patterns[0]
                pattern_name = pattern.get("name", "")
                pattern_id = pattern.get("id", "")
                project_ids = pattern.get("project_ids", [])
                project_names = [f"Project {pid}" for pid in project_ids]
            project_count = len(project_names)
        
        project_names_str = ", ".join(project_names) if project_names else "N/A"
        
        # Build template examples section from retrieved ProjectTemplate vertices
        template_section = ""
        if templates:
            template_section = "\n**STRUCTURE EXAMPLES FROM SIMILAR PROJECTS:**\n"
            for i, template in enumerate(templates, 1):
                template_name = template.get('title', template.get('name', f'Template {i}'))
                template_id = template.get('id', 'N/A')
                
                template_section += f"\nExample {i}: {template_name} (ID: {template_id})\n"
                
                if template.get('description'):
                    desc = template['description']
                    if len(desc) > 150:
                        desc = desc[:150] + "..."
                    template_section += f"- Description: {desc}\n"
                
                if template.get('project_type'):
                    template_section += f"- Project Type: {template['project_type']}\n"
                
                if template.get('sdlc_method'):
                    template_section += f"- SDLC Method: {template['sdlc_method']}\n"
                    
                if template.get('state'):
                    template_section += f"- State: {template['state']}\n"
                
                if template.get('project_category'):
                    template_section += f"- Category: {template['project_category']}\n"
                    
                if template.get('objectives'):
                    obj = template['objectives']
                    if len(str(obj)) > 100:
                        obj = str(obj)[:100] + "..."
                    template_section += f"- Objectives: {obj}\n"
        
        # Use dimension_guidance from inference if available (new structure), fall back to building from pattern
        dim_guidance = inference_guidance.get("dimension_guidance", {})
        if dim_guidance:
            dimension_guidance = f"""
        **Dimension-Specific Guidance from Past Projects:**
        
        - **SDLC Guidance (use in thought_process_behind_sdlc_method):**
        {dim_guidance.get('sdlc', f'**[{project_names_str}]**: Check pattern for methodology details.')}
        
        - **Timeline Guidance (use in thought_process_behind_timeline):**
        {dim_guidance.get('timeline', f'**[{project_names_str}]**: Check pattern for timeline details.')}
        
        - **Objectives Guidance (use in thought_process_behind_objectives):**
        {dim_guidance.get('objectives', f'**[{project_names_str}]**: Check pattern for objectives details.')}
        
        - **Technology Guidance (use in thought_process_behind_technology_stack):**
        {dim_guidance.get('technology', f'**[{project_names_str}]**: Check pattern for technology details.')}
        
        - **Team Guidance (use in thought_process_behind_team):**
        {dim_guidance.get('team', f'**[{project_names_str}]**: Check pattern for team composition.')}
        
        - **Risk Guidance (use in thought_process_behind_key_results):**
        {dim_guidance.get('risks', f'**[{project_names_str}]**: Check pattern for risk mitigations.')}
        """
        elif patterns:
            # Fall back to building from pattern directly
            pattern = patterns[0]
            dimension_guidance = f"""
        **Dimension-Specific Guidance from Past Projects:**
        
        - **SDLC Guidance (use in thought_process_behind_sdlc_method):**
        **[{project_names_str}]**: These projects used {', '.join(pattern.get('dev_methodology_dist', ['Hybrid']))} methodology.
        
        - **Timeline Guidance (use in thought_process_behind_timeline):**
        **[{project_names_str}]**: Average project duration was {pattern.get('avg_project_duration', 'N/A')} days with budget band: {pattern.get('budget_band', 'N/A')}.
        
        - **Objectives Guidance (use in thought_process_behind_objectives):**
        **[{project_names_str}]**: Key KPIs included: {', '.join(pattern.get('key_kpis', [])[:3]) or 'N/A'}.
        Strategic focus: {pattern.get('strategic_focus', 'N/A')}.
        
        - **Technology Guidance (use in thought_process_behind_technology_stack):**
        **[{project_names_str}]**: Key technologies used: {', '.join(pattern.get('key_technologies', [])[:5]) or 'N/A'}.
        
        - **Team Guidance (use in thought_process_behind_team):**
        **[{project_names_str}]**: Team composition included: {', '.join(pattern.get('team_composition', [])[:4]) or 'N/A'}.
        
        - **Risk Guidance (use in thought_process_behind_key_results):**
        **[{project_names_str}]**: Key risk mitigations: {', '.join(pattern.get('key_risk_mitigations', [])[:3]) or 'N/A'}.
        Maturity level: {pattern.get('maturity_level', 'N/A')}, Implementation complexity: {pattern.get('implementation_complexity', 'N/A')}.
        """
        else:
            dimension_guidance = ""
        
        # Build delivery guidance
        themes_str = ", ".join(delivery_themes[:3]) if delivery_themes else "None"
        approaches_str = ", ".join(delivery_approaches[:3]) if delivery_approaches else "None"
        criteria_str = ", ".join(delivery_criteria[:3]) if delivery_criteria else "None"
        
        inference_context = f"""
        
        <PROJECT_CREATION_GUIDANCE>
        
        ### KNOWLEDGE FROM SIMILAR PAST PROJECTS (CRITICAL - USE THIS):
        We have identified {project_count} similar project(s) from our knowledge base: {project_names_str}.
        Pattern ID: {pattern_id}
        Pattern Name: {pattern_name}
        
        **Overall Guidance:**
        {guidance_text}
        
        {template_section}
        
        ## DELIVERY GUIDANCE
        
        - **Key Delivery Themes**: {themes_str}
        - **Proven Approaches**: {approaches_str}
        - **Success Criteria**: {criteria_str}
        
        {dimension_guidance}
        
        **CRITICAL INSTRUCTIONS FOR USING KNOWLEDGE:**
        - In EACH thought_process field, CITE the specific project names from the guidance above (e.g., **[{project_names_str}]**)
        - Quote data points from the pattern (e.g., "In [{project_names_str}], teams used X methodology...")
        - Use structure examples to guide template selection, naming patterns, and types
        - Connect past approaches to current project decisions
        - If the guidance contradicts input data, prioritize input data but note the pattern in thought_process
        
        </PROJECT_CREATION_GUIDANCE>
        """
    
    current_date = datetime.datetime.now().date().isoformat()    
    systemPrompt = f"""
        You are the Head of an organization responsible for defining strategies, goals, and initiatives to drive organizational growth. Below are details about the organization:

        <org_info>
            {org_details}

            Other details:
            {org_persona}
        </org_info>
        
        <org_strategies_of_customer>
        {org_strategy_alignment}
        </org_strategies_of_customer>
        
        
        <customer_info_obtained_from_onboarding>
        {customerInfo}
        <customer_info_obtained_from_onboarding>
        
        {knowledge_context}
        
        A rough project description is provided for the project named: {name}
        <rough_description>
        {desc}
        </rough_description>
        {inference_context}
        Your job is to generate comprehensive project data **strictly and exclusively using the information provided in the inputs above**. 🔹 Do not create assumptions, filler text, or external details that are not derivable from <org_info>, <customer_info_obtained_from_onboarding>, <org_strategies_of_customer>, <rough_description>, and {knowledge_context}.  
        - If information is missing, leave the field empty instead of inventing. 🔹  
        - Always ensure that every field in the JSON reflects actual input context where possible. 🔹  
        - Enhance wording and structure, but do not fabricate new data. 🔹  
        - Use <portfolios_of_tenant> only to understand portfolio context and tailor outputs. Do not directly copy or reuse its descriptions.

        Do not incorporate any status, comments, or unrelated metadata (e.g., project progress or feedback) into the outputs.
        Focus exclusively on the project name and <rough_description> for the core content.
        
        Follow these tasks:

        1. **Enhance the project description**: Generate a detailed, contextual, and professional project description. Highlight the unique aspects of the project, including its objectives, challenges, and key deliverables. Ensure the description is directly aligned with the project name and <rough_description>, using <org_info> only to contextualize the customer's industry or needs. Avoid generic content and focus on specifics relevant to the project scope.
        2. **Create enhanced objectives**: Outline 2-3 specific, clear, and concise project objectives that align with the project’s goals. Ensure objectives are measurable, relevant to the <rough_description>, and highlight key expected outcomes. Avoid vague or generic objectives. They should be in paragraph or plain text.
        3. **Define project capabilities**: Identify up to 3 key capabilities required for the project (e.g., Data Analytics, ERP, CRM, Cloud, AI, Supply Chain Management). Tailor these to the industry, domain, and project scope defined in the enhanced description. Ensure capabilities are specific and relevant.
        4. **Specify tech stack**: Provide a comma-separated string of up to 5 key technologies (e.g., SAP, Salesforce, Python, React, Docker) required to execute the project scope. Ensure the tech stack is directly aligned with the enhanced description and project capabilities.
        5. **List job roles required**: Specify up to 5 contextual job roles (e.g., Data Scientist, Solution Architect, Project Manager) needed to execute the project. Ensure roles are specific to the project scope and aligned with the enhanced description and tech stack.
        6. **Determine SDLC methodology**: Select one of Agile, Waterfall, or Hybrid based on the project’s nature as described in the enhanced description. For example, SAP implementations typically use Waterfall, while software product development often uses Agile. Justify the choice implicitly through the project context.
        7. **Classify project type**: Select one of Run, Transform, Enhance or Innovate based on the enhanced description. For example, operational support projects are Run, digital transformation projects are Transform, and AI-driven projects are Innovate. Ensure the classification reflects the project’s purpose.
        
        8. **Key Results Elaboration**:
          - Define 3-4 measurable outcomes, each with:
            - A *beautifully descriptive* `key_result` field that is vivid, specific, and strategically compelling (e.g., 'Propel daily active users by 20% to 10,000 by deploying AI-driven marketing campaigns and seamless cross-platform onboarding, strengthening competitive positioning').
            - A precise `baseline_value` reflecting current state or target (e.g., 'Current 8,000 DAU, targeting 10,000').
            - Descriptions that tightly align with **conversation** intent, **internal_knowledge** portfolio goals (e.g., '100k players'), and **web_search_results** benchmarks (e.g., '20% DAU growth rate'), covering diverse outcomes (e.g., user growth, technical performance, financial impact, retention, engagement).
          - Use **internal_knowledge** to establish baselines (e.g., 'current 8k DAU from stalled project data') and infer gaps (e.g., 'no retention metrics imply churn risk').
          - Use **web_search_results** to validate feasibility and inspire methods (e.g., 'web: 15% retention lift from gamification informs leaderboard strategy').
          - Ensure variety in metrics (e.g., DAU, CCU, latency, revenue, retention) to reflect project complexity, with each outcome emphasizing strategic value (e.g., 'enhances user trust', 'drives market share').
          
        9. **Generate additional project metadata**:
            - **Title**: Exact name.
            - **Scope**: Derive a descriptive paragraph (100-200 words) project scope from the enhanced description in MARKDOWN string format. If insufficient information, provide a generic scope aligned with the project name and description.
            - **Start and End Dates**: If input data already contains `start_date` and `end_date`, always use those values (converted to YYYY-MM-DD). Only generate realistic dates if they are missing.
            - **Portfolio List**: Assign a portfolio ID (e.g., a numeric ID like 17) to categorize the project. If <portfolios_of_tenant> provides context, align with an existing portfolio ID.
            - **State**: Select a project phase (e.g., Discovery, Planning, Execution) based on the project’s current stage. Assume Discovery unless the description suggests otherwise.
            - **Project Category**: Assign a category (e.g., Technology, Operations, Customer Experience) based on the enhanced description. Leave empty if unclear.
            - **Service Category**: Specify a service category (e.g., Consulting, Software Development, IT Services) based on the project scope. Leave empty if not applicable.
            - **Org Strategy Alignment**: Describe in 1-2 sentences how the project aligns with organizational strategy (<org_strategies_of_customer>). Your job is to match org strategy of customer from the list <org_strategies_of_customer> to this project. If no customer org strategy is provided then leave empty. . Leave empty if unclear.
            - **Team**: Assign a single team with a short, innovative name (e.g., "Quantum Pioneers", "NexGen Innovators") that reflects the project’s purpose or domain.
            - **Scope milestones**: Define 4-7 relevant project scope milestones from the project scope, name, obj and desc,ensuring the milestones are relevant to the project scope and project name.
            
        10. ** Select applicable org strategies **:
            - From the list of <org_strategies_of_customer> select which is applicable for this project and write in comma separated.
             
             
        Thought Process Mandate:
            - Document reasoning for all the fields below in concise Markdown bullet points (3-5 points each, max).
            - **Format Requirement**: Each bullet must start with a **bold header** summarizing the key decision or input, followed by a brief (1-2 sentence) description explaining its influence, justification, or assumption. Avoid verbose explanations to optimize rendering speed.
            - Justify data selection, content depth, and alignment with strategy. Cite `<project_details>`, `<org_info>`, `<org_persona>`, or `<knowledge_context>` as applicable.
            - **CRITICAL - Pattern References**: When PROJECT_CREATION_GUIDANCE is provided, you MUST cite the specific project names in ALL thought_process fields. For example:
                - "**[Project 770]**: This project used Hybrid methodology, informing our SDLC selection."
                - "**[Project 770]**: Average duration was 425 days, guiding our timeline estimate."
                - "**[Project 770]**: Team included Integration Project Manager, influencing our team composition."
              Quote specific data points from the dimension guidance (e.g., technologies, team roles, KPIs) in each thought_process field.
              Use the project names verbatim as provided in the guidance (e.g., "Project 770").
            
        Output in JSON Format:
        ```json
        {{
            "ref_project_id": "", // if present in the input data
            "description": "", // Detailed project description (text)
            "objectives": "", // List of comma separated objectives (text)
            "project_capabilities": [], // Up to 3 capabilities (array of strings)
            "technology_stack": "", // Up to 5 technologies (csv of strings)
            "sdlc_method": "", // Agile, Waterfall, or Hybrid
            "project_type": "<Run |Enhance |Transform |Innovate>",
            "key_results": [
                {{
                    "key_result": "<beautifully descriptive measurable outcome, e.g., 'Propel daily active users by 20% to 10,000 by deploying AI-driven marketing campaigns and seamless cross-platform onboarding, strengthening competitive positioning'>",
                    "baseline_value": "", // should be brief - max 10 words
                }}
            ],
            "capex_budget": <number>, // if present in the input data
            "opex_budget": <number>, // if present in the input data
            "title": "", // exact name as passed
            "scope": "<Markdown string with relevant sections like Executive Summary, Detailed Project Scope, Solution Hypothesis, Planning Enablement, Insights & Recommendations>"  //upto 200 words
            "start_date": "", // YYYY-MM-DD
            "end_date": "", // YYYY-MM-DD
            "portfolio_list": [ // Portfolio assignment
                {{
                    "portfolio": 0 // Numeric ID
                }}
            ],
            "state": "",  // Project phase, choose one from (options: Discovery, Design, Build, Test, Deploy & Hypercare, Complete)
            "project_category": "", // Project category or empty
            "project_location": [], // leave empty
            "service_category": "", // Service category or empty
            "org_strategy_align": "", // From the list of <org_strategies_of_customer> select which is applicable for this project and write in comma separated (3-5).
            "team": [ // Team assignment with milestones to complete
                {{
                    "name": "" // Short, innovative team name
                    "project_roles": [], // required project roles
                    "milestones": [
                        {{
                            "name": "", // milestone name
                            "type": 0, // milestone type -- for  scope and schedule use 2, spend use 3
                            "target_date": "",
                            "status_value": 0, // not started - 1, in progress then 2, completed - 3
                            "comments": "",
                            "planned_spend": 0, // only for type 3 (spend milestone)
                        }},...
                    ]
                }}
            ],
            "key_accomplishments": "", // a brilliantly summarized key accomplishment and possbile next steps
            "risk_list": [
                {{
                    "id": 0,
                    "description": "possible riks description",
                    "impact": "possible impact",
                    "mitigation": "best mitigation for this customer",
                    "priority": 1,
                    "due_date": "", // YYYY-MM-DD format
                }},...
            ],
            "thought_process_behind_description": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_objectives": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_project_capabilities": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_technology_stack": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_sdlc_method": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_state": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_key_results": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_scope": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_timeline": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_portfolio_list": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_project_category": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_internal_project": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_service_category": "<markdown string: 3-4 bullets, 20-40 words each citing reason>",
            "thought_process_behind_org_strategy_align": "<markdown string: 3-4 bullets, 20-40 words each citing reasonh>"
            "thought_process_behind_team": "<markdown string: 3-4 bullets, 20-40 words each citing reasonh>"
        }}
        
        Todays date: {current_date}
        ```
    """
    
    prompt = f"""
        Create the project with info provided and output in proper JSON.
        
        Current Date: {current_date}
    """

    # Debug: Print inference context to verify it's being passed correctly
    if inference_guidance:
        print("----project_inference_context----", inference_context)

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )
    
    
    
    
def updateProjCanvasPrompt(project_details,project_scope, org_details, org_persona, portfoliosOfTenant) -> ChatCompletion:
    
    knowledge_context = ''
    if portfoliosOfTenant:
        knowledge_context = f"""
            <portfolios_of_tenant>
            {portfoliosOfTenant}
            </portfolios_of_tenant>
            
            Use the <portfolios_of_tenant> to understand the tenant's portfolio context and enhance the updated project data. Do not directly copy or reuse descriptions from <portfolios_of_tenant>; instead, use the context to ensure updates align with the portfolio strategy.
        """
        
    current_date = datetime.datetime.now().date().isoformat()
    systemPrompt = f"""
    
        You are a strategic project creation agent tasked with updating an existing project canvas in JSON format. 
        The user has requested enhancements to enrich all sections while preserving the core structure and intent, prioritizing user modifications in **Project Details**.


        **Goal**: Update the project canvas using **project Details** as the primary source (~80% weight), enriched with **Knowledge Context**, **portfolios**, **Org Info** (~20% weight).
                  Enhance all sections (name, description, objectives, key results, scope, tech stack, project type, project category, timeline etc.) with actionable, strategically aligned content.

        **Knowledge Context**:\n{knowledge_context}
        **Output Requirement**: Render strictly in JSON format as specified below, with no explanations or text outside the JSON block.
        
        
        Below are details about the organization:
        
        <org_info>
            Org Details:{org_details}
            Org Persona:{org_persona}
        </org_info>


        Below is the current project data, which include changes to incorporate:
        **Project Details**\n{project_details}
        **Project Scope**\n{project_scope}

        Retain fields like `project_location`, `sdlc_method`, and `service_category` unless updates are explicitly provided in `<project_details>`. 
        Ensure updates are vivid, measurable, and strategically aligned with ~80% weight on `<project_details>` and ~20% on `<org_info>`, `<org_persona>`, and `<portfolios_of_tenant>`.

        ### Core Instructions:
        - **Prioritize User Changes**: Detect modifications in crucial fields (`title`, `description`, `objectives`, `key_results`, `scope`) from `<project_details>` and cascade updates to related fields.
        - **Enrich All Fields**: Update all specified fields, even if unchanged, with enhancements for clarity, measurability, and alignment with `<org_info>` and `<portfolios_of_tenant>`.
        - **Validation**: Ensure fields adhere to JSON structure, are complete (e.g., `title`, `description`), and consistent (e.g., `state` aligns with timeline, `technology_stack` supports `objectives`).
        - **Idempotency**: Ensure consistent outputs for repeated actions with identical inputs.

        ### Field-Specific Enhancements:
        
        - **Title**: Refine `TITLE` to be concise (5-10 words) and purpose-driven, reflecting `<project_details>` and portfolio focus.
        - **Description**: Generate a 50-100 word professional description enhancing `project_description`. Highlight purpose, challenges, deliverables, and alignment with `<org_info>` and `<portfolios_of_tenant>`.
        - **Objectives**: Provide 3-4 specific, measurable objectives in a comma-separated list each in 10 words, based on `key_results`, `milestones`, `<project_description>`, and portfolio goals.
        - **Technology Stack**: Update `TECH_STACK` to a comma-separated string of up to 5 modern technologies (e.g., "Python, TensorFlow, AWS"). Reflect `<project_details>` and project needs.
        - **Project Category**: Update to a comma-separated list (e.g., "AI, Cloud") reflecting `<project_details>`, `PROJECT_TYPE`, and portfolio focus. Retain existing value unless updated.
        
        - **Start and End Dates**: Use `PROJECT_START_DATE` and `PROJECT_END_DATE`. Ensure `start_date` ≥ {current_date}, `start_date` < `end_date`, and feasibility based on `milestones` and complexity. Propose realistic dates if missing.
        - **Key Results**: Generate 3-4 measurable outcomes from `KEY_RESULTS`:
            - `key_result`: Vivid description in 15-30 words (e.g., "Propel daily active users by 20% to 10,000 by deploying AI-driven marketing campaigns and seamless cross-platform onboarding, strengthening competitive positioning").
            - `baseline_value`: Current vs. target (e.g., "$5,000, target $4,500").
        - Ensure diversity and alignment with `objectives` and `<portfolios_of_tenant>`.
        
        - **Project Scope**: Enhance the input scope with a 250-300 word Markdown string with sections: **Overview**, **Requirements**, **Constraints**, **Risks**, **Out-of-Scope**, **Success Metrics**, **Technical Needs**. 
          - Look into Project name, description, objectives while updating scope.
          
        - **State**: Set to one of (Discovery, Design, Build, Complete) based on timeline and progress (e.g., Build if `start_date` is past).
        - **SDLC Method**: Derive as Agile, Waterfall, or Hybrid based on project complexity and industry standards (e.g., Agile for AI projects, Waterfall for SAP).
        - **Job Roles Required**: List up to 5 contextual roles (e.g., "DevOps Engineer") based on `technology_stack`, `scope`, and `TEAMSDATA`.
        
        - **Project Type**: Set to one of (Run, Enhance, Transform, Innovate) based on `<project_details>` and portfolio alignment.
        - **Org Strategy Alignment**: List 3-4 priorities (e.g., "Transform service experience") from `<org_info>` or inferred from `<project_details>`.
        - **Portfolio List**: Select 2-3 portfolios from `<portfolios_of_tenant>` using exact `portfolio` ID, aligned with `<project_details>`.

        ### Retain Unspecified Fields:
        - Retain `sdlc_method`, `project_type`, and `service_category` unless updated. Adjust only for consistency (e.g., `sdlc_method` shift due to new `technology_stack`).

        ### Incorporate Additional Data:
        - Use `MILESTONES` to refine `scope` and timeline.
        - Use `TEAMSDATA` to inform `job_roles_required` and `scope` constraints.
        - Reflect `PROJECT_BUDGET` and `PROVIDER_NAME` in `scope` constraints.

        ### Thought Process Mandate:
        - For each updated field, provide 1-2 concise Markdown bullets (10-20 words each):
        - Cite `<project_details>`, `<org_info>`, `<org_persona>`, or `<portfolios_of_tenant>`.
        - Example: "- **Description Update**: Enhanced with Web3 from project_description.\n- **Alignment**: Matches Infra & Ops portfolio."

        ### Output Requirements:
            - Return updated JSON with all fields strictly in below format.
            
        ```json
        {{
            "title":"<updated descriptive name>",
            "description": "<enhanced description (50-100 words)>",
            "thought_process_behind_description": "<Markdown: 1-2 bullets, 10-20 words each>",
            "objectives": "<comma-separated objectives>",
            "thought_process_behind_objectives": "<Markdown: 1-2 bullets, 10-20 words each>",
            "project_capabilities": [],
            "thought_process_behind_project_capabilities": "<Markdown: 1-2 bullets, 10-20 words each>",
            
            "technology_stack": "<comma-separated technologies>",
            "thought_process_behind_technology_stack": "<Markdown: 1-2 bullets, 10-20 words each>",
            "sdlc_method": "<Agile, Waterfall, Hybrid>",
            "thought_process_behind_sdlc_method": "<Markdown: 1-2 bullets, 10-20 words each>",
            "state": "<Discovery, Design, Build, Complete>",
            "thought_process_behind_state": "<Markdown: 1-2 bullets, 10-20 words each>",
            
            "job_roles_required": ["<up to 5 roles>"],
            "thought_process_behind_job_roles_required": "<Markdown: 1-2 bullets, 10-20 words each>",
            "project_type": "<Run, Enhance, Transform, Innovate>",
            "thought_process_behind_project_type": "<Markdown: 1-2 bullets, 10-20 words each>",
            "key_results": [
                {{
                    "key_result": "<description>",
                    "baseline_value": "<current vs. target>"
                }}...
            ],
            "thought_process_behind_key_results": "<Markdown: 1-2 bullets, 10-20 words each>",
            "scope": [
                {{"name": "<single Markdown string (250-300 words) with updated scope details, requirements, constraints, risks, out-of-scope based on Project Details>"}}
            ],
            "thought_process_behind_scope": "<Markdown: 1-2 bullets, 10-20 words each>",
            
            "start_date": "<YYYY-MM-DD>",
            "end_date": "<YYYY-MM-DD>",
            "thought_process_behind_timeline": "<Markdown: 1-2 bullets, 10-20 words each>",
            "portfolio_list": [
                {{
                    "portfolio": 0
                }}
            ],
            "thought_process_behind_portfolio_list": "<Markdown: 1-2 bullets, 10-20 words each>",
            "project_category": "<comma-separated categories>",
            "thought_process_behind_project_category": "<Markdown: 1-2 bullets, 10-20 words each>",
            
            "internal_project": false,
            "thought_process_behind_internal_project": "<Markdown: 1-2 bullets, 10-20 words each>",
            "service_category": "",
            "thought_process_behind_service_category": "<Markdown: 1-2 bullets, 10-20 words each>",
            "org_strategy_align": "<comma-separated priorities>",
            "thought_process_behind_org_strategy_align": "<Markdown: 1-2 bullets, 10-20 words each>",
            "last_updated": "{current_date}"
        }}
        ```
        ###Guidelines:
            - **Mandatory Fields**: Include and update all specified fields (`title`, `description`, `objectives`, `technology_stack`, `project_category`, `start_date`, `end_date`, `key_results`, `scope`, `project_capabilities`, `job_roles_required`, etc.), even if empty. Provide thought processes for each.
            - **Cascading User Changes**: Detect modifications in crucial fields (e.g., `project_description`, `objectives`, `key results`) and propagate to related fields (~80% weight).
            - **Scope Requirements**: Generate a 250-300 word Markdown string for `scope` with sections: Overview, Requirements (reflect user-modified themes), Constraints (quantify budget, e.g., ~$500K if missing), Risks, Out-of-Scope, Success Metrics, Technical Needs. Align with `<project_details>` and `<portfolios_of_tenant>`.
        
        Current Date: {current_date}
    """
        
    userPrompt = f"""
        Update and enhance the project canvas by enriching all specified fields (title, description, objectives, technology_stack, project_category, start_date, end_date, key_results, scope) using <project_details> (80% weight). 
        Cascade user-modified fields (e.g., description,objectives, key_results) to related fields. Enrich with <org_info>, <org_persona>, and <portfolios_of_tenant> (20% weight). Retain fields like project_location and sdlc_method unless updated. Output updated JSON with 1-2 concise thought process bullets (10-20 words each) per field, ensuring strategic alignment.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    


def createOrgStrategiesPrompt(project_data, default_list) -> ChatCompletion:

    current_date = datetime.datetime.now().date().isoformat()
    systemPrompt = f"""
        You are a business strategist AI. Given the project info, select the most suitable organization-level strategies from the list below.

        Today's date: {current_date}

        Possible org strategies:
        {default_list}

        Project Info:
        {project_data}

        Choose only the most relevant strategies based on project intent.


        Output in JSON Format:
        ```json
        {{
            "suitable_org_strategies": []
        }}
        ```
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user="Output in proper JSON format"
    )
    
   

def createProjectDataV3(
    conversation, org_persona, org_details, portfoliosOfTenant, org_strategy_alignment
) -> ChatCompletion:
    knowledge_context = ''
    if portfoliosOfTenant:
        knowledge_context = f"""
            <portfolios_of_tenant>
            {portfoliosOfTenant}
            </portfolios_of_tenant>
            
            Use the <portfolios_of_tenant> to understand the tenant's portfolio context and enhance the data for the current project. Do not directly copy or reuse descriptions from <portfolios_of_tenant>; instead, learn from the context to tailor the current project's data.
        """
    current_date = datetime.datetime.now().date().isoformat()
    prompt = f"""
        You are the Head of an organization responsible for defining strategies, goals, and initiatives to drive organizational growth. Below are details about the organization:

        <org_info>
            {org_details}

            Other details:
            {org_persona}
        </org_info>
        
        <org_strategies_of_customer>
        {org_strategy_alignment}
        </org_strategies_of_customer>
        
        {knowledge_context}
        
        A conversation is provided below, which contains details about a new project:
        <conversation>
        {conversation}
        </conversation>
        
        Your job is to generate comprehensive project data based on the provided conversation. Analyze the conversation to extract the project name, a rough project description, and other relevant details. Ensure all outputs are highly relevant to the project discussed in the conversation, using <org_info> and <portfolios_of_tenant> only as reference points to understand the customer and portfolio context. Do not incorporate any status, comments, or unrelated metadata (e.g., project progress or feedback) into the outputs. Focus exclusively on the project details derived from the conversation for the core content. Follow these tasks:

        1. **Enhance the project description**: Generate a detailed, contextual, and professional project description based on the conversation. Highlight the unique aspects of the project, including its objectives, challenges, and key deliverables. Ensure the description is directly aligned with the project details extracted from the conversation, using <org_info> only to contextualize the customer's industry or needs. Avoid generic content and focus on specifics relevant to the project scope.
        2. **Create enhanced objectives**: Outline 2-3 specific, clear, and concise project objectives that align with the project’s goals as derived from the conversation. Ensure objectives are measurable, relevant to the conversation’s intent, and highlight key expected outcomes. Avoid vague or generic objectives. They should be in paragraph or plain text.
        3. **Define project capabilities**: Identify up to 3 key capabilities required for the project (e.g., Data Analytics, ERP, CRM, Cloud, AI, Supply Chain Management). Tailor these to the industry, domain, and project scope defined in the enhanced description. Ensure capabilities are specific and relevant.
        4. **Specify tech stack**: Provide a comma-separated string of up to 5 key technologies (e.g., SAP, Salesforce, Python, React, Docker) required to execute the project scope. Ensure the tech stack is directly aligned with the enhanced description and project capabilities.
        5. **List job roles required**: Specify up to 5 contextual job roles (e.g., Data Scientist, Solution Architect, Project Manager) needed to execute the project. Ensure roles are specific to the project scope and aligned with the enhanced description and tech stack.
        6. **Determine SDLC methodology**: Select one of Agile, Waterfall, or Hybrid based on the project’s nature as described in the enhanced description. For example, SAP implementations typically use Waterfall, while software product development often uses Agile. Justify the choice implicitly through the project context.
        7. **Classify project type**: Select one of Run, Transform, or Innovate based on the enhanced description. For example, operational support projects are Run, digital transformation projects are Transform, and AI-driven projects are Innovate. Ensure the classification reflects the project’s purpose.
        8. **Key Results Elaboration**:
          - Define 3-4 measurable outcomes, each with:
            - A *beautifully descriptive* `key_result` field that is vivid, specific, and strategically compelling (e.g., 'Propel daily active users by 20% to 10,000 by deploying AI-driven marketing campaigns and seamless cross-platform onboarding, strengthening competitive positioning').
            - A precise `baseline_value` reflecting current state or target (e.g., 'Current 8,000 DAU, targeting 10,000').
            - Descriptions that tightly align with **conversation** intent, **internal_knowledge** portfolio goals (e.g., '100k players'), and **web_search_results** benchmarks (e.g., '20% DAU growth rate'), covering diverse outcomes (e.g., user growth, technical performance, financial impact, retention, engagement).
          - Use **internal_knowledge** to establish baselines (e.g., 'current 8k DAU from stalled project data') and infer gaps (e.g., 'no retention metrics imply churn risk').
          - Use **web_search_results** to validate feasibility and inspire methods (e Olenka.g., 'web: 15% retention lift from gamification informs leaderboard strategy').
          - Ensure variety in metrics (e.g., DAU, CCU, latency, revenue, retention) to reflect project complexity, with each outcome emphasizing strategic value (e.g., 'enhances user trust', 'drives market share').
        9. **Generate additional project metadata**:
            - **Title**: Extract the project name from the conversation. If not explicitly stated, infer a concise and relevant name based on the conversation content.
            - **Scope**: Derive a brief (1-2 sentences) project scope from the enhanced description. If insufficient information, provide a generic scope aligned with the inferred project name.
            - **Start and End Dates**: Propose realistic start and end dates (format: YYYY-MM-DD) based on the project scope. Assume a start date within the next 3 months (e.g., 2025-08-01) and an end date based on typical project duration (e.g., 6-12 months for Transform projects, 3-6 months for Run projects).
            - **Portfolio List**: Assign a portfolio ID (e.g., a numeric ID like 17) to categorize the project. If <portfolios_of_tenant> provides context, align with an existing portfolio ID.
            - **State**: Select a project phase (e.g., Discovery, Planning, Execution) based on the project’s current stage. Assume Discovery unless the conversation suggests otherwise.
            - **Project Category**: Assign a category (e.g., Technology, Operations, Customer Experience) based on the enhanced description. Leave empty if unclear.
            - **Service Category**: Specify a service category (e.g., Consulting, Software Development, IT Services) based on the project scope. Leave empty if not applicable.
            - **Org Strategy Alignment**: Describe in 1-2 sentences how the project aligns with organizational strategy (<org_strategies_of_customer>). Your job is to match org strategy of customer to this project. If no customer org strategy is provided, leave empty.
            - **Team**: Assign a single team with a short, innovative name (e.g., "Quantum Pioneers", "NexGen Innovators") that reflects the project’s purpose or domain.
        10. **Select applicable org strategies**:
            - From the list of <org_strategies_of_customer>, select which are applicable for this project and write in comma-separated format.
             
        Output in JSON Format:
        ```json
        {{
            "description": "", // Detailed project description (text)
            "objectives": "", // Clear project objectives (text, paragraph)
            "project_capabilities": [], // Up to 3 capabilities (array of strings)
            "technology_stack": "", // Up to 5 technologies (csv of strings)
            "sdlc_method": "", // Agile, Waterfall, or Hybrid
            "job_roles_required": [], // Up to 5 contextual job roles (array of strings)
            "project_type": "", // Run, Enhance, Transform, Innovate
            "key_results": [
                {{
                    "key_result": "<beautifully descriptive measurable outcome, e.g., 'Propel daily active users by 20% to 10,000 by deploying AI-driven marketing campaigns and seamless cross-platform onboarding, strengthening competitive positioning'>",
                    "baseline_value": "", // should be brief - max 10 words
                }}
            ],
            "title": "", // Inferred or extracted project name
            "scope": "", // Brief project scope or empty
            "start_date": "", // YYYY-MM-DD
            "end_date": "", // YYYY-MM-DD
            "portfolio_list": [ // Portfolio assignment
                {{
                    "portfolio": 0 // Numeric ID, select based on context for this customer for this project
                }}
            ],
            "state": "",  // Project phase, choose one from (Discovery, Design, Build, Complete)
            "project_category": "", // Project category or empty
            "project_location": [], // leave empty
            "internal_project": false,
            "service_category": "", // Service category or empty
            "org_strategy_align": "", // From the list of <org_strategies_of_customer> select which is applicable for this project and write in comma separated.
            "team": [ // Team assignment
                {{
                    "name": "" // Short, innovative team name
                }}
            ]
        }}
        
        Today's date: {current_date}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )
    