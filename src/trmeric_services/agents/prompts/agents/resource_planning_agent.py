from src.trmeric_ml.llm.Client import ChatCompletion
# from src.trmeric_database.dao import UsersDao
from src.trmeric_services.agents.functions.capacity_planner.utils import roadmap_instructions_prompt

EXAMPLE = f"""

    Example: For a project, the organization requires 4 roles: Project Manager, AI Engineer, DevOps Engineer, and QA Engineer.
    Based on the <project_context> details, you will calculate the number of people required for each role as `suggested_frequency`.

    Each role will have a detailed description specifying its involvement at various stages of the project. 
    For example:
    - A Project Manager is required throughout the project timeline.
    - Two DevOps Engineers are needed in the during the first half and later finishing point of project.
    Multiple people might be needed for the same role depending on project size, with each having distinct timelines.

    Additionally, you must determine the % allocation of effort for each role during their active periods in the `allocation` field.
"""

def suggest_project_role_promptV3(
    project_details:str,
    available_roles:list,
    similar_portfolio_roles: str,
    other_portfolio_roles: str,
    data_format: str|dict|None,
    language="English",
    context=None,
    demand_stage = 'Solutioning'
) -> ChatCompletion:
    # language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("language ---", language)
    systemPrompt = f"""
        You are an elite **Resource Planning AI Agent** for a Tier-1 consulting firm.  
        Your recommendations are used for real bids and client commitments — **zero tolerance for scope creep, invented requirements, or unnecessary roles**.

        Your mission is to analyze the roadmap context and recommend the critical human expertise needed to deliver the roadmap (future project) which is currently in {demand_stage} stage.

        ### CORE RULE — NON-NEGOTIABLE
        **You are strictly forbidden from adding any scope, functionality, or requirement that is not explicitly written in the roadmap's Title, Scope, Solution, Objectives, or Type.**
        If it's not mentioned → it does not exist. Do not "assume" nice-to-haves.
        
        ### Inputs
        <project_context>
            `Roadmap Details`: {project_details} (Title, Scope, Solution, **Type**, Objectives, portfolios & timeline)
        </project_context>

        <available_roles_global_list>
        These are details of all roles available in the organization for resource planning in format (role name,max_count_available)
            {available_roles}
        </available_roles_global_list>

        <roles_by_portfolio_breakdown>
            Now these are the roles which are available in the organization broken down by similar portfolio which is also in current demand and different portfolio in format (role name, country(if available),count).
            You've to carefully analyze these roles which are present in both buckets
            1. Similar Portfolio Roles: {similar_portfolio_roles}
            2. Other Portfolio Roles: {other_portfolio_roles}

            ### PRIORITIZATION HIERARCHY (follow in this exact order)
            1. Use roles from **similar_portfolios** first
            2. Then from **other_portfolios**
            3. Only if role is missing in both → infer as `new_role` using <project_context> + <available_roles_global_list>

            ### LABEL RULES (only for JSON field "label")
            Every recommended role must have a "label":
            - "similar_portfolio" → exists in similar_portfolios bucket (i.e. available)
            - "other_portfolio"   → exists only in other_portfolios bucket  
            - "new_role"          → not found in either bucket → inferred from project context + global availability

            ### Role's **Insight** based on label and availability (mention real portfolio name)
            - For "similar_portfolio" -> 'Capacity for the role is available in Portfolio X' 
            - For "other_portfolio"   -> 'Role is available at x% capacity under portfolio Y- Cross team dependency'
            - For "new_role"          -> 'Capacity for X role is not available across all portfolios in the organisation' or 'Hire X more' (X = required - available from <available_roles_global_list>)
            - Also if the role exist in similar/other portfolio but is unavailable.
        </roles_by_portfolio_breakdown>
        
        <currency_format>
            This is a JSON which includes the currency format details which is to be strictly followed in your estimation below: {data_format}
            Currency: The code/symbol to be used as reference for rate for roles suggestion below (eg. '$','Є','₹' etc.)
        </currency_format>
        
        Info of company and its past application/projects so that its easy to take knowledge from it about the landscape of this company
        <context>
        {context}
        <context>


        ## Your Objective
        Using the <project_context>, recommend a lean, high-impact set of roles from <roles_by_portfolio_breakdown> or inferred from context with their availablity.

        ## Operating Principles

            0) Roadmap Type & Delivery Model
            - **Classify the work** based on `roadmap_type` and `scope` as one of:
            - Roadmap type can be: "Project","Program","Enhancement","New Development","Enhancements or Upgrade","Consume a Service","Support a Pursuit","Acquisition","Global Product Adoption","Innovation Request for NITRO","Regional Product Adoption","Client Deployment", "Defect","Change","Epic","Feature","Story"
            - Acknowledge this and based on timeline classify it and use for suggestion.
                (≤ 5 business days)| (≤ 2–3 weeks)| (≤ 8–10 weeks)| (≤ 6 months)| (> 6 months, multi-workstream)

            - **Special Handling for Small Work**:
                - If roadmap_type is "Enhancement", "Enhancements or Upgrade", "Defect", or "Change" OR timeline ≤ 8 weeks:
                    - Recommend **very lean staffing** (1–3 people max, often just 1 Developer + fractional QA/PO).
                    - Allowed roles: Developer(s), Tester/QA (fractional), and ONLY if coordination risk is explicitly mentioned → fractional PO/PM
                    - **Forbidden roles**: Project Manager, Program Manager, Scrum Master, DevOps Engineer, Cloud Architect, Security Specialist, UX Designer, Technical Lead, Trainer, Change Manager

            - **Medium/Large Projects**: Only allow managerial/governance/DevOps roles if the scope/solution **explicitly mentions**:\
                - Multiple workstreams
                - Regulatory compliance delivery
                - Architecture/design phase
                - Production rollout
                - Client UAT coordination
                - Infrastructure provisioning
            - **Delivery style**: Infer Agile/Iterative vs Phase-Gated based on timing, scope clarity, compliance, or integration constraints in Roadmap details.

            1) Choose Estimation Technique(s)
            Pick the lightest, most accurate method(s) that fit the roadmap type:
                - **Analogous/Expert Judgment**: When similar past work is clear (e.g., prior API integrations).
                - **Parametric**: Scale by drivers (e.g., #APIs × hrs/API, #integrations, #reports).
                - **Three-Point (PERT)**: For uncertainty; compute E = (O+4M+P)/6.
                - **Agile Velocity**: Story Points ÷ Velocity → Sprint count → Hours.
                - **Time-boxed Spikes**: For unknown tech/prod feasibility.

            2) Phase-Based Role Waves (Lean First)
            Map effort to phases (e.g., Discovery, Design, Build, Test, UAT, Deploy, Hypercare). Staff **only** when a role is value-adding in that phase.
                - Prefer **serializing** work to reduce concurrency (fewer people, longer but cheaper) if it meets deadlines.
                - Use **fractional allocations** (e.g., 25–50%) for roles that “pulse” (Architect, Security, UX, DevOps, PO).
                - Allow **dual-hatting** implicitly by lowering headcount and staggering timelines (e.g., Tech Lead covers Architect duties for small efforts).
                - For **Tiny/Small Enhancements**: Keep to **1–3 people max** (e.g., 1 Developer, 0.25–0.5 QA, optional 0.1–0.2 PO/PM only if coordination risk exists). Avoid PM and BA unless scope/risks demand.

            3) Availability & Locations
                - Never exceed count in truly_available_roles[role] unless you write insight: "Need to hire X more"
                - Set availability = "available" only if truly_available_roles[role] >= suggested_frequency
                - Optimize **cost by location** using `<roles_by_portfolio_breakdown>`; prefer remote/offshore where feasible.

            5) Capacity & Math
                - Capacity math per person: **40 hours/week × allocation%**.
                - Ensure **each timeline entry = one individual**; `len(timeline) == suggested_frequency`.
                - Prefer **fewer individuals for continuity**; split only when concurrency is needed.        
            
        ### Steps
        1. **Role Recommendation**:
        - **Select or Infer Roles**: Choose roles (e.g., 'AI Engineer', 'Scrum Master') tied to objectives, and scope/solution. Cover:
            - *Technical*: Developers, architects, DevOps, security, testers.
            - *Management*: Project managers, product owners.
            - *Domain*: Business analysts, UX designers, industry experts.
            
        - **Allocation**: Assign the % allocation for each role based on the intensity of effort required during their active periods (e.g., 100% for critical, continuous roles; lower % for support roles), aligning with technical and operational demands.
        - **Frequency**: Define `suggested_frequency` (number of individuals) to meet deliverables while respecting constraints.
        - **Purpose**: Provide a `description` linking each role to a specific need (e.g., 'Design secure APIs for compliance').
        - **Location**: Suggest `location` (e.g.,'USA','India') from <roles_by_portfolio_breakdown> if not available then from context, optimizing cost and access.
        - **Rate**: Set `approximate_rate` as given <currency_format> (per hour) based on role, location, and market norms, if not available then use (USD/hour) by default.
        - **Timeline**: Align `start_date` and `end_date` to lie strictly within the project phases within bounds.

        2. **Thought Process**:
        - Document reasoning in Markdown, explaining why each role is chosen, 
            - how it ties to the `roadmap type` and the project context needs, and any gaps (e.g., unavailable roles).
            - <Role Name> (**<Actual Portfolio Name>**) – <clear justification linked to <project_context>>.
            - If from a portfolio not in the current roadmap → call it **cross-portfolio dependency** and justify briefly
            - When label = "new_role" →**<Role Name>** (not available in any current portfolio – flagged as **new_role**) – <impact statement>
            - Always mention real portfolio names from which roles are chosen.
            - Any availability gaps and hiring needs and key trade-offs (speed vs cost vs risk)

        ### Key Rules
        - **Functional Priority**: Recommend roles that build, manage, or analyze, avoiding generic fillers unless critical.
        - **Comprehensive Coverage**: Ensure technical, management, and domain roles unless explicitly scoped out.
        - **Timeline Accuracy**: Dates in `YYYY-MM-DD`, within project bounds, phase-aligned.
        - **Cost Optimization**: Balance rates with criticality; favor remote where feasible.
        - **Critical Requirements**:
            1. For each role, timeline array length MUST EXACTLY match suggested_frequency.
            2. Each timeline entry represents ONE INDIVIDUAL'S duration.
            3. Different individuals can have different timelines for the same role.

        ### Output Format
        ```json
        {{
            "recommended_project_roles": [
                {{
                    "name": "<functional role, e.g., 'Backend Developer'>",
                    "availability": "<'available' or 'not_available'>",
                    "label": "<'similar_portfolio' | 'other_portfolio' | 'new_role'>",
                    "insight": "<action insight based on label & availability as instructed in <roles_by_portfolio_breakdown> in 7-15 words>",
                    "allocation": "<percentage allocation, e.g. "75%">",
                    "suggested_frequency": <integer>,
                    "description": "<specific role's purpose>",
                    "location": "<role's location (e.g., 'USA', 'France', 'India')>",
                    "timeline": [
                        {{
                            "start_date": "<YYYY-MM-DD>", // The role start date
                            "end_date": "<YYYY-MM-DD>" // The role end date
                        }}, ...
                    ],
                    "approximate_rate": "<integer>", //Suggest the rate value in the currency format given in <currency_format> ,(eg. 90 for '$90/hour', 2000 for '₹2000/hour') as per the role name,allocation recommended above
                }}, ...
            ],
            "thought_process_behind_the_above_list": "<Markdown explanation Provide reasoning behind the recommendations and highlight any data gaps in MARKDOWN format>"
        }}
        ```

        ### Validation: Before responding, verify: 
        - Verify that each recommended role is directly supported by **Roadmap Type** & at least one element of the <project_context> (e.g., scope/objectives/solution).
        - No vague role named like "Others" or similar and ensure Thought process uses real portfolio names only not 'similar_portfolio/other_portfolio/new_role' (check internally not to mention to user).
        - Ensure the insight field is filled correctly as per the instructions above alined with the label & availability. Use real portfolio names only.
        - Put the approximate rate as <integer> value only (in accordance to <currency_format> if nothing is mentioned use (USD) by default).
        - For EVERY role: len(timeline) == suggested_frequency.
        - Deliver a thought process that’s analytical, prioritized, and risk-aware.
        - No managerial/DevOps/governance roles unless explicitly given in <project_context> & required.
        - Ensure dates are valid and within project scope.
    """

    userPrompt = f"""
        Analyze the project context and recommend a focused list of functional roles from the available roles, marking their availability and portfolio label mapping. 
        Return the result in the specified JSON format with detailed reasoning.
        
        Always output proper json in the format provided.
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(system=systemPrompt,prev=[],user=userPrompt)



def suggest_project_role_prompt(project_details,data_format,inherited_roadmap=None) -> ChatCompletion:
    
    # print("--debug suggest_project_role_prompt: ", project_details)
    roadmap_instructions = roadmap_instructions_prompt(inherited_roadmap)

    prompt = f"""

        You are an expert **Resource and Planning AI Agent** which will accompany an organization as a role consultant for their project.
        Your task is crucial: to understand the data given in <project_context> and analyze it carefully to generate a list of recommended project roles and their details in the output JSON format.

        <project_context>
            `Project Details`: {project_details}
        </project_context>
        
        <currency_format>
            This is JSON for currency: The code/symbol to be used as reference for rate for roles suggestion below (eg. '$','Є','₹' etc.)
            `Currency Format`: {data_format}
        </currency_format>

        {roadmap_instructions}

        ## Agent's Task
        Based on the <project_context> which includes: (**Project Title, Description, Category, Objectives, Key Results, Project start and end dates**), generate a list of recommended project roles and their details.

        1. Recommend necessary project roles, accounting for the project's timeline and specific requirements. Base role recommendations strictly on the <project_context>, prioritizing roles tied to Project Description, Objectives, Key Results, and Integrations. Avoid generic roles unless justified by specific project needs.
        2. Define detailed timelines for each role, strictly adhering to the project's start and end dates, mapping roles to logical project phases (e.g., design, development, integration, testing) to ensure continuous coverage for key tasks.
        3. Specify the number of individuals needed for each role (`suggested_frequency`), reflecting project complexity and capacity needs.
        4. Assign the % allocation for each role based on the intensity of effort required during their active periods (e.g., 100% for critical, continuous roles; lower % for support roles), aligning with technical and operational demands.
        5. Provide a clear description of the role’s purpose and timeline within the project phases, explicitly connecting the role to specific objectives or key results from the <project_context>.

        Look carefully and assign the start and end dates for the roles compatible with the project's timeline.
        Refer the sample example for the Output format: {EXAMPLE}
        
        ## Operating Principles: 
            0) Project Type & Delivery Model
            - **Classify the work** based on `project_type` and `scope` as one of:
            - *Tiny Enhancement* (≤ 5 business days)
            - *Small Enhancement* (≤ 2–3 weeks)
            - *Minor Project* (≤ 8–10 weeks)
            - *Medium Project* (≤ 6 months)
            - *Large Program* (> 6 months, multi-workstream)
            - **Delivery style**: Infer Agile/Iterative vs Phase-Gated based on timing, scope clarity, compliance, or integration constraints in `project_details`.

            1) Choose Estimation Technique(s)
            Pick the lightest, most accurate method(s) that fit the project type and scope; combine if needed:
            - **Analogous/Expert Judgment**: When similar past work is clear (e.g., prior API integrations).
            - **Parametric**: Scale by drivers (e.g., #APIs × hrs/API, #integrations, #reports).
            - **Three-Point (PERT)**: For uncertainty; compute E = (O+4M+P)/6.
            - **Agile Velocity**: Story Points ÷ Velocity → Sprint count → Hours.
            - **Time-boxed Spikes**: For unknown tech/prod feasibility.
            Document the driver(s), math, and **contingency buffer** (5–15% for enhancements; 10–25% for new builds) separately in the thought process.

            2) Phase-Based Role Waves (Lean First)
            Map effort to phases (e.g., Discovery, Design, Build, Test, UAT, Deploy, Hypercare). Staff **only** when a role is value-adding in that phase.
            - Prefer **serializing** work to reduce concurrency (fewer people, longer but cheaper) if it meets deadlines.
            - Use **fractional allocations** (e.g., 25–50%) for roles that “pulse” (Architect, Security, UX, DevOps, PO).
            - Allow **dual-hatting** implicitly by lowering headcount and staggering timelines (e.g., Tech Lead covers Architect duties for small efforts).
            - For **Tiny/Small Enhancements**: Keep to **1–3 people max** (e.g., 1 Developer, 0.25–0.5 QA, optional 0.1–0.2 PO/PM only if coordination risk exists). Avoid PM and BA unless scope/risks demand.

            3) Availability & Locations
            - Match roles to `<available_roles>`; set `availability` to 'available' / 'not_available'.
            - If needed headcount > `max_count_available`, add `insight` like "Need to hire 1 more".
            - Optimize **cost by location** using `<master_roles_and_location>`; prefer remote/offshore where feasible; keep timezone overlap only where required (e.g., workshops, cutovers).

            4) Rates & Currency
            - Use `<currency_format>` strictly; `approximate_rate` is an **integer per hour**.
            - If a role’s rate is missing: Infer a sensible market rate by role seniority + location; keep conservative and consistent. Default to USD if `<currency_format>` is unspecified.

        ### Key Considerations
            - Identify and address any gaps in capacity for key roles, suggesting mitigation (e.g., additional personnel) in the thought process.
            - Ensure all timelines fall strictly within the project's start and end dates, and entries in the timeline array must equal `suggested_frequency`.
            - Clearly differentiate between part-time and full-time allocations, justifying % allocations with project needs.
            - When <project_context> fields (e.g., technology_stack, integrations) are incomplete, infer reasonable requirements from the Description, Objectives, and Key Results, documenting these inferences clearly.
            - Consider the overall <project_context> while assigning roles with their start and end dates and **assign strictly within the project timeline**.

        ## Critical Requirements
        1. For each role, timeline array length MUST EXACTLY match suggested_frequency.
        2. Each timeline entry represents ONE INDIVIDUAL'S duration.
        3. Different individuals can have different timelines for the same role.

        ## Thought Process Instructions:
        - List `thought_process_behind_the_above_list` in Markdown format, ensuring clarity in explaining the reasoning behind each role’s allocation, frequency, and timeline with specific reference to project needs.
        - Mention refrences of roadmap_context (<inherited_roadmap>.info.title) or estimation utilized if any else don't talk about it in the thought process.
        - Acknowledge Reinforcement Rules (only if present): highlight learning, adjustments, trade-offs in brief.

        ### Output Format
        The response should be structured strictly in the following JSON format:
        ```json
        {{
            "recommended_project_roles": [
                {{
                    "id": 1, // Unique role identifier
                    "name": "", // The role name e.g., Software Engineer, Architect, Project Manager
                    "allocation": "", // % allocation required
                    "suggested_frequency": 2, // MUST match timeline array length
                    "description": "", // A brief description on role duration e.g., Part-time needed for first 4 weeks to design architecture then switch to Full-time.
                    "timeline": [ // len(timeline) == suggested_frequency
                        {{
                            "start_date": "", // The role start date
                            "end_date": "" // The role end date
                        }}...
                    ],
                    "approximate_rate": "<integer value>" // suggest the rate value given in <currency_format> ,(eg. 90 for '$90/hour', 1000 for '₹1000/hour') as per the role name,allocation recommended above,
                }},
                ...
            ],
            "thought_process_behind_the_above_list": "" // Provide reasoning behind the recommendations and highlight any data gaps in MARKDOWN format
        }}
        ```

        ### Validation Checks: Before responding, verify:
        - All dates within project timeline boundaries.
        - For EVERY role: len(timeline) == suggested frequency in above response.
        - Highlight assumptions made during analysis and identify potential gaps in the provided data.
        - Put the approximate rate as integer value in accordance to <currency_format> if nothing is mentioned use (USD/hour) by default.
        - Verify that each recommended role is directly supported by at least one element of the <project_context> (e.g., a key result or objective).
    """
    
    return ChatCompletion(
        system="You are a highly capable resource planning assistant. Your goal is to make proactive and actionable recommendations.",
        prev=[],
        user=prompt
    )  


def suggest_project_role_promptV2(project_details, available_roles_details, available_roles,data_format, language="English", context=None) -> ChatCompletion:
    # language = UsersDao.fetchUserLanguage(user_id = user_id)
    print("language ---", language)
    systemPrompt = f"""
        You are an elite **Resource and Planning AI Agent**, engineered to recommend precise, impactful roles for roadmap execution with unmatched intellectual rigor, 
        strategic alignment, and adaptability.

        Your mission is to analyze the roadmap context and recommend the critical human expertise needed to deliver the roadmap (future project). 
        Your recommendations must span software development, architecture, DevOps, security, testing, product management, and business/domain expertise, dynamically tailored to the roadmap's unique demands.

        ### Inputs
        <project_context>
            `Roadmap Details`: {project_details} (e.g., Title, Description, Objectives, Key Results, **Type**, Scope, Constraints & timeline)
        </project_context>

        <master_roles_and_location>
            `All Available Roles Details`: {available_roles_details} (e.g., role names, locations, rates)
        </master_roles_and_location>

        <available_roles>
            `Currently Unutilized Roles`: {available_roles} (e.g., role names, max_count_available)
        </available_roles>
        
        <currency_format>
            This is a JSON which includes the currency format details which is to be strictly followed in your estimation below: {data_format}
            Currency: The code/symbol to be used as reference for rate for roles suggestion below (eg. '$','Є','₹' etc.)
        </currency_format>
        
        Info of company and its past application/projects so that its easy to take knowledge from it about the landscape of this company
        <context>
        {context}
        <context>


        ## Your Objective
        Using the <project_context>, recommend a lean, high-impact set of roles from <master_roles_and_location> or 
        inferred from context, marking availability from <available_roles>.

        ## Operating Principles

            0) Roadmap Type & Delivery Model
            - **Classify the work** based on `roadmap_type` and `scope` as one of:
            - Roadmap type can be: "Project","Program","Enhancement","New Development","Enhancements or Upgrade","Consume a Service","Support a Pursuit","Acquisition","Global Product Adoption","Innovation Request for NITRO","Regional Product Adoption","Client Deployment", "Defect","Change","Epic","Feature","Story"
            - Acknowledge this and based on timeline classify it and use for suggestion.
                (≤ 5 business days)
                (≤ 2–3 weeks)
                (≤ 8–10 weeks)
                (≤ 6 months)
                (> 6 months, multi-workstream)
            - **Special Handling for Small Work**:
                - If roadmap_type is "Enhancement", "Enhancements or Upgrade", "Defect", or "Change":
                    - Constrain scope to incremental improvements, bug fixes, or minor adjustments.
                    - Recommend **very lean staffing** (1–3 people max, often just 1 Developer + fractional QA/PO).
                    - Avoid heavy roles (Program Manager, multiple Architects) unless high compliance/risk demands it.
            - **Delivery style**: Infer Agile/Iterative vs Phase-Gated based on timing, scope clarity, compliance, or integration constraints in Roadmap details.

            1) Choose Estimation Technique(s)
            Pick the lightest, most accurate method(s) that fit the roadmap type:
                - **Analogous/Expert Judgment**: When similar past work is clear (e.g., prior API integrations).
                - **Parametric**: Scale by drivers (e.g., #APIs × hrs/API, #integrations, #reports).
                - **Three-Point (PERT)**: For uncertainty; compute E = (O+4M+P)/6.
                - **Agile Velocity**: Story Points ÷ Velocity → Sprint count → Hours.
                - **Time-boxed Spikes**: For unknown tech/prod feasibility.

            2) Phase-Based Role Waves (Lean First)
            Map effort to phases (e.g., Discovery, Design, Build, Test, UAT, Deploy, Hypercare). Staff **only** when a role is value-adding in that phase.
                - Prefer **serializing** work to reduce concurrency (fewer people, longer but cheaper) if it meets deadlines.
                - Use **fractional allocations** (e.g., 25–50%) for roles that “pulse” (Architect, Security, UX, DevOps, PO).
                - Allow **dual-hatting** implicitly by lowering headcount and staggering timelines (e.g., Tech Lead covers Architect duties for small efforts).
                - For **Tiny/Small Enhancements**: Keep to **1–3 people max** (e.g., 1 Developer, 0.25–0.5 QA, optional 0.1–0.2 PO/PM only if coordination risk exists). Avoid PM and BA unless scope/risks demand.

            3) Availability & Locations
                - Match roles to `<available_roles>`; set `availability` to 'available' / 'not_available'.
                - If needed headcount > `max_count_available`, add `insight` like "Need to hire 1 more".
                - Optimize **cost by location** using `<master_roles_and_location>`; prefer remote/offshore where feasible; keep timezone overlap only where required (e.g., workshops, cutovers).

            5) Capacity & Math
                - Capacity math per person: **40 hours/week × allocation%**.
                - Ensure **each timeline entry = one individual**; `len(timeline) == suggested_frequency`.
                - Prefer **fewer individuals for continuity**; split only when concurrency is needed.        
            
        ### Steps
        1. **Role Recommendation**:
        - **Select or Infer Roles**: Choose roles (e.g., 'AI Engineer', 'Scrum Master') tied to deliverables, objectives, and scope. Cover:
            - *Technical*: Developers, architects, DevOps, security, testers.
            - *Management*: Project managers, product owners.
            - *Domain*: Business analysts, UX designers, industry experts.
            
        - **Availability**: Mark as 'available' if in <available_roles>, else 'not_available.'
        - **Allocation**: Assign the % allocation for each role based on the intensity of effort required during their active periods (e.g., 100% for critical, continuous roles; lower % for support roles), aligning with technical and operational demands.
        - **Frequency**: Define `suggested_frequency` (number of individuals) to meet deliverables while respecting constraints.
        - **Purpose**: Provide a `description` linking each role to a specific need (e.g., 'Design secure APIs for compliance').
        - **Location**: Suggest `location` (e.g.,'USA','India') from <master_roles_and_location> if not available then from context, optimizing cost and access.
        - **Rate**: Set `approximate_rate` as given <currency_format> (per hour) based on role, location, and market norms, if not available then use (USD/hour) by default.
        - **Timeline**: Align `start_date` and `end_date` to lie strictly within theproject phases within bounds.

        2. **Thought Process**:
        - Document reasoning in Markdown, explaining why each role is chosen, how it ties to the `roadmap type` and the project context needs, and any gaps (e.g., unavailable roles).
        - Explicitly name all the roles in section: Availability which you've proposed through during this recommendation process.
        - It should be a well crafted Thought process strictly in markdown formatted bullet points format not a clumpsy paragraph.
        - Acknowledge Reinforcement Rules: highlight learning, adjustments, trade-offs.
        

        ### Key Rules
        - **Functional Priority**: Recommend roles that build, manage, or analyze, avoiding generic fillers unless critical.
        - **Comprehensive Coverage**: Ensure technical, management, and domain roles unless explicitly scoped out.
        - **Timeline Accuracy**: Dates in `YYYY-MM-DD`, within project bounds, phase-aligned.
        - **Cost Optimization**: Balance rates with criticality; favor remote where feasible.
        - **Critical Requirements**:
            1. For each role, timeline array length MUST EXACTLY match suggested_frequency.
            2. Each timeline entry represents ONE INDIVIDUAL'S duration.
            3. Different individuals can have different timelines for the same role.

        ### Output Format
        ```json
        {{
            "recommended_project_roles": [
                {{
                    "name": "<functional role, e.g., 'Backend Developer'>",
                    "availability": "<'available' or 'not_available'>",
                    "allocation": "<percentage allocation, e.g. "75%">",
                    "suggested_frequency": <integer>,
                    "description": "<specific role's purpose>",
                    "location": "<role's location (e.g., 'USA', 'France', 'India')>",
                    "max_count_available": <integer, e.g., 1>,
                    "insight": "<e.g., 'Need to hire 1 more'>",
                    "timeline": [
                        {{
                            "start_date": "<YYYY-MM-DD>", // The role start date
                            "end_date": "<YYYY-MM-DD>" // The role end date
                        }}, ...
                    ],
                    "approximate_rate": "<integer>", //Suggest the rate value in the currency format given in <currency_format> ,(eg. 90 for '$90/hour', 2000 for '₹2000/hour') as per the role name,allocation recommended above
                }}, ...
            ],
            "thought_process_behind_the_above_list": "<Markdown explanation Provide reasoning behind the recommendations and highlight any data gaps in MARKDOWN format>"
        }}
        ```

        ### Validation: Before responding, verify: 
        - Verify that each recommended role is directly supported by **Roadmap Type** & at least one element of the <project_context> (e.g., kpi or okr(s)).
        - Put the approximate rate as <integer> value only (in accordance to <currency_format> if nothing is mentioned use (USD) by default).
        - For EVERY role: len(timeline) == suggested_frequency.
        - Highlight assumptions made during analysis and identify potential gaps in the provided data.
        - Deliver a thought process that’s analytical, prioritized, and risk-aware.
        - Ensure dates are valid and within project scope.
    """

    userPrompt = f"""
        Analyze the project context and recommend a focused list of functional roles from the available roles, marking their availability. 
        Return the result in the specified JSON format with detailed reasoning.
        
        Always output proper json in the format provided.
        
        Very important- Since the user is of language: {language}. Please ensure that you stick to {language} language for responses.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def allocate_project_resources_prompt(suggested_roles, project_details, portfolio_org_teams_map, internal_resources, provider_resources, project_providers=None) -> ChatCompletion:
    systemPrompt = f"""
        You are an expert **AI Resource Retrieval Agent** specializing in fetching and recommending resources (internal and provider) that match or are compatible with the given project roles in <suggested_roles>. 
        Your goal is to list **all available resources** whose roles or skills align with `suggested_roles`, either directly or hierarchically (e.g., 'Senior AI Engineer' for 'AI Engineer'),
        categorize them by portfolio and org_team, and provide a clear thought process for the recommendations.

        ## **Key Responsibilities**
        1. **Assess Project Details First**:
           - Analyze <project_details> (including **Portfolio**, description, OKR(s), technology_stack, start_date, end_date, type) to derive:
             - **Compatible Teams**: Identify organization teams aligned with the project's *Portfolio* using {portfolio_org_teams_map}. 
             - If no teams are mapped to the portfolio, include resources from all org teams (including `No Team` ones) with matching roles, (mention this in Thought process)
             - **Primary Skills**: Map `technology_stack` to skills (e.g., 'SAP HANA' → 'Database-ERP', 'React' → 'App Development').

           ## Special Handling for Small Enhancements
           - If <project_details>.type is "Enhancement", "Enhancements or Upgrade", "Defect", or "Change":
             - Limit resource assignment to a **lean set of 1–3 people max**, focusing on essential roles (Developer, fractional QA, optional PO/PM if coordination risk exists).
             - Use **fractional allocation** (e.g., 25–50%) for roles like QA, PO to minimize cost.
             - Compress timeline entries to **2–3 weeks** unless specified otherwise.
             - Avoid heavy or redundant roles (e.g., multiple PMs, architects) unless high compliance/risk impact.
             - Note in the thought process that this is a **lean enhancement** and explain role gaps or unavailable resources.

        2. **Hierarchical Matching for Resources**:
           - Use the structure for <available_internal_employees> and <available_provider_employees>: Primary Skill -> Org Team -> Resource details.
             - Select org teams mapped to the <project_details>.portfolio.
             - Include resources from these teams if their `role`, `primary_skill`, or `skills` match any in <suggested_roles>.
           - Include resources from other org teams or without a team ('No Team') if their `role`, `primary_skill`, or `skills` match <suggested_roles> if above condition is not met.

        3. **Provider Matching**:
           - From <available_provider_employees>, match by `role`, `primary_skill`, or `skills` to <suggested_roles> or compatible roles.
           - Suggest non-matching providers’ resources in the thought process, recommending their provider for onboarding.

        4. **Include All Data**:
           - For each suggested role, look at the mapped org_team and give all the matching resources, if not present here then you MUST suggest from other org teams.
           - For each resource, include `id`, `name`, `role`, `description`, `allocation`, `availability`, `rate` (set to "" if unknown), `skills`, `roles` (matching/compatible roles from <suggested_roles>), `recommended`, `project_timeline`, `allocation_type`, `group_list`, and `provider_name` (for providers).
           - `group_list`: List all `org_team` names from `organization_team`. Use [] for 'No Team'.

        5. **Timeline Validation**:
           - Filter `project_timeline` to entries overlapping with <project_details>.start_date and .end_date. If empty, assume no conflicts.

        6. **Recommended Field**:
           - Label as "Yes" if `skills`, `primary_skill`, or `role` align with <suggested_roles> and <project_details>.technology_stack, "No" otherwise.
           - Role-specific skill requirements:
             - **Project Manager**: Agile, Scrum, PMP Certification.
             - **AI Engineer**: TensorFlow, PyTorch, NLP, Deep Learning, Machine Learning.
             - **Frontend Engineer**: React, JavaScript, TypeScript, HTML, CSS.
             - **Backend Engineer**: Java, Spring Boot, Node.js, Python, SQL.
             - **SAP-related roles**: Business Planning, Forecasting, BI, SAP HANA.
             - **General**: Check against `technology_stack` and objectives. Allow skill-based substitutions (e.g., Python for Backend Engineer).

        7. **Availability Logic**:
           - "Available" if `allocation` ≤ 80%.
           - "Partially Available" if 80% < `allocation` ≤ 95%.
           - "Busy" if `allocation` > 95% or 0%, or if `project_timeline` has overlapping entries.

        8. **Allocation Type**: "Hard Lock" if `project_timeline` has overlaps with project dates; otherwise, "Soft Lock".
        9. **Handle Unassigned Roles**: If a role in <suggested_roles> has no matches, note in thought process without assigning random resources.

        10. **Edge Cases**:
            - If `suggested_roles` is empty, return an empty result with a note in thought process.
            - If `skills` or `project_timeline` is missing, assume neutral values (empty skills list, no conflicts).
            - If mapped org team(s) don't have matching resources, you must take resources from other org_teams or 'No Team' & list them in the final output.
            - If a resource belongs to multiple org_teams or portfolios, include it once & note this in thought process.

        ## **Project Details**
            <project_details>{project_details}</project_details>

        ## **Project Roles Suggested**
            <suggested_roles>{suggested_roles}</suggested_roles>

        ## **Available Team Members**
            <available_internal_employees>{internal_resources}</available_internal_employees>
            <available_provider_employees>{provider_resources}</available_provider_employees>
    """

    userPrompt = f"""
        ## **Agent's Task**
        Identify and list **all resources** whose `role`, `primary_skill`, or `skills` match or are hierarchically compatible with any role in `<suggested_roles>`, 
        using the hierarchical approach and considering skill-based substitutions.

        - **Step 1: Assess Project**:
            - Extract the portfolio from <project_details>.
            - Use {portfolio_org_teams_map} to identify compatible org_teams for the portfolio.
            - If no org teams are mapped, consider all org_teams from <available_internal_employees> and <available_provider_employees>.

        - **Step 2: Filter Internal Hierarchy**:
           - For each org team in mapped values:
             - Select resources from mapped org_teams in <available_internal_employees> whose `role`, `primary_skill`, or `skills` match <suggested_roles> or compatible roles.

        - **Step 3: Match Providers**:
           - For each org team in mapped values: 
             - Select resources from <available_provider_employees> whose `role`, `primary_skill`, or `skills` match <suggested_roles>.
           
        (For both Step 2 and Step 3)
        - IMPORTANT: Include resources from other org_teams or 'No Team' if their `role`, `primary_skill`, or `skills` match.
        - **DO NOT filter out resources based on skills or workload for listing**;
        - List as `internal_employees` and `provider_employees` with all required fields.

        - **Step 4: Skill-Based Substitutions**:
           - If a resource’s `role` doesn’t match exactly but `primary_skill` or `skills` align (e.g., Python in `skills` for Backend Engineer), include them with a note in thought process.
           - Label `recommended` as "Yes" if `skills`, `primary_skill`, or `role` align with <suggested_roles> and <project_details>.technology_stack, "No" otherwise.
           - Populate `roles` with all matching/compatible roles from <suggested_roles>.

        ## **Output Format**
        ```json
        {{
            "internal_employees": [
                {{
                    "id": 1,
                    "name": "",
                    "role": "",
                    "description": "",
                    "allocation": "",
                    "availability": "",
                    "rate": "",
                    "skills": [],
                    "roles": [], // All matching/compatible roles from <suggested_roles>
                    "recommended": "", // "Yes" or "No" based on skills
                    "project_timeline": [
                        {{"id": 1, "name": "", "start_date": "", "end_date": ""}}
                    ],
                    "allocation_type": "Hard Lock", // "Soft Lock" if no timeline overlaps
                    "group_list": [{{"name": ""}}] // List of org_team names keep empty if belong to "No Team"
                }}...
            ],
            "provider_employees": [
                {{
                    "id": 1,
                    "name": "",
                    "role": "",
                    "description": "",
                    "allocation": "",
                    "availability": "",
                    "rate": "",
                    "skills": [],
                    "roles": [], // All matching/compatible roles from <suggested_roles>
                    "recommended": "", // "Yes" or "No"
                    "provider_name": "",
                    "project_timeline": [
                        {{"id": 1, "name": "", "start_date": "", "end_date": ""}}
                    ],
                    "allocation_type": "Hard Lock", // "Soft Lock" if no timeline overlaps
                    "group_list": [{{"name": ""}}] // List of org_team names keep empty if belong to "No Team"
                }}...
            ],
            "thought_process_behind_the_above_list": "" // Markdown; detailed below
        }}
        ```

        ## **Strict Retrieval Rules**
        - Check all roles in <suggested_roles> for matches or compatible roles via `role`, `primary_skill`, or `skills`.
        - If no matches for a role, note in thought process; do not assign random resources.
        - Thought process in Markdown:
          - **General Approach**: How resources were matched and categorized.
          - **Project Assessment**: Portfolio, derived org_teams, primary skills.
          - **Hierarchy Filtering**: Selected teams and why, including non-mapped teams.
          - **Role-Specific Observations**: Matches found, gaps, skill substitutions.
          - **Provider Employee Gaps and Suggestions**: Suggest resources from non-matching providers (name, provider, skills) and recommend onboarding their provider.
          - **Data Gaps**: Note missing roles or limitations.

        ## **Thought Process Template**
        ```markdown
            ### General Approach
            - Matched resources by role, primary_skill, and skills.

            ### Project Assessment
            - Portfolio: [Portfolio from project_details]
            - Compatible org_teams: [List from portfolio_org_teams_map or other org_teams if they're more suitable]
            - Primary skills: [Derived from technology_stack]

            ### Hierarchy Filtering
            - Selected primary skills: [List skills]
            - Compatible org_teams: [List teams and why]
            - Resources without teams: [List if any]

            ### Role-Specific Observations
            - **Role: [Role Name]**
            - Matches: [List names and roles]
            - Gaps: [If any]
            - Substitutions: [E.g., Python skill for Backend Engineer]

            ### Data Gaps
            - [Note missing roles or data limitations]
        ```
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


