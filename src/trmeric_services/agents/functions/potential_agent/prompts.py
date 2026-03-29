from src.trmeric_ml.llm.models.OpenAIClient import ChatCompletion
from typing import List, Dict, Any, Optional
import json

def potentialSkillMappingPrompt(skill_group) -> ChatCompletion:
    
    prompt = f"""
        You are an AI assistant tasked with generating actionable insights for organization based on resource data grouped by primary skill areas. 
        The input is a dictionary where each key is a primary skill (e.g., ERP, AI, Cloud & DevOps) and the value is a list of resources. 
        Each resource has: id, name,role, experience, organization_team, availability , allocation & skills
        
        ## Input Context:
            Grouped resources by primary skill: {skill_group}

        ## Analysis Dimensions:
            - Resource Count: Number of resources per skill group.
            - Availability: Average availability (mean of 'availability' values) across organization teams.
            - Utilization: Average allocation (mean of 'allocation'; high means less available).
            - External Dependency: Percentage of external resources (external=True count / total).
            - Skill Gaps: Common or missing skills within the 'skills' field per group.

        ## Instructions:
            - Analyze the grouped data to compute metrics (counts, averages, ratios) per skill group.
            - Identify critical patterns (e.g., over-utilization, under-availability, external reliance).
            - Generate exactly 3 top insights across all groups, focusing on availability and utilization.
            - Each insight must be concise (5-10 words), actionable, and include a key metric.
            - Classify availability as High (plentiful capacity), Low (over-allocated), or Medium (balanced).
            - Ensure insights cover distinct skill groups or dimensions for variety.
            - Use only the provided data; avoid external assumptions.

        ## Output Format:
        ```json
        {{
            "insights": [
                {{
                    "header": "<name of the skill group>",
                    "insight": "<insight string>",
                    "availability": "<High|Low|Medium>"
                }}...
            ]
        }}
        ```
    """
    
    return ChatCompletion(system = prompt, prev = [], user = '')




def potentialInsightsPrompt(internal_resources, external_resources) ->ChatCompletion:
    
    prompt = f"""
        You are an AI assistant tasked with generating actionable insights on organizational resources based on provided data. 
        You will receive a list of internal and external resources and must analyze them to produce insights across five specific dimensions. 
        
        Ensure insights are concise, data-driven, and thought-provoking to support strategic decision-making.

        ## Input Context:
            - **Internal Resources**: {internal_resources}  
            - **External Resources**: {external_resources}  
            (e.g., employee names, roles, skills, experience levels, organization team, allocation hours, project assignments, geographic locations, tenure)  
            

        ## Analysis Dimensions:
        1. **Resource Utilization & Capacity Optimization**  
        - Analyze allocation patterns across time periods and organization teams to identify over- or under-utilized resources.  
        - Highlight availability gaps and peak demand periods.  
        - Compare planned allocation versus actual availability to uncover discrepancies.  
        - Flag resources consistently operating at high allocation levels (potential burnout risk).  

        2. **Skills & Experience Distribution**  
        - Map skill coverage across the organization and identify gaps or surpluses.  
        - Analyze the balance of junior versus senior resources based on experience levels.  
        - Track which skills are in highest demand across projects.  
        - Suggest mentorship opportunities by pairing high- and low-experience resources.  

        3. **Project Portfolio Health & Resource Alignment**  
        - Evaluate resource distribution across projects and portfolios.  
        - Identify projects with resource constraints or over-allocations.  
        - Detect timeline overlaps causing resource conflicts.  
        - Assess project completion trends based on resource allocation quality.  


        ## Instructions:
        - Generate **exactly one insight per dimension** (3 in total).  
        - Each insight should be concise, evidence-based, and actionable, addressing a specific finding or opportunity.  
        - Avoid generic or vague statements; tie insights to patterns or trends in the input data.  
        - If data is insufficient for a dimension, note the limitation and suggest a hypothetical insight based on typical patterns.  

        ## Output Format:
        ```json
        {{
            "insights": [
                {{
                    "title": <"dimension_name">,
                    "summary_text": <"insight for the dimension in max. 8-12 words">
                }}...
            ]
        }}
        ```
    """
    
    return ChatCompletion(
        system=prompt,
        prev= [],
        user = 'Create potential insights for the resources given.'
    )   
    
    


def resourceInsightsPrompt(data) -> ChatCompletion:
    
    prompt = f"""
        You are a resource profile generating expert. A comprehensive data has been provided to you for a resource i.e. all the details 
        -Name, role, experience, skills, allocation, projects with their timeline, availability, primary skill, and other relevant fields
         
        Create a summmary view of what impact this resource has brought to the organization given his experience,skills & projects info in 40-60 words.
        #Input: {data}
        
        #Output: Return in JSON format
        ```json
        {{
            "insights": {{
                "retro": "<summary showing the impact for the resource analyzing the input>"
            }}
        }}
        ```
    """
    return ChatCompletion(system=prompt,prev=[],user='')








def update_details_prompt_v2(user_query: str, conversation: List[str], context_string: str) -> ChatCompletion:
    system = """
        You are an assistant tasked with extracting resource identifiers (names, IDs, or roles) from a user query for updating resource data, ensuring the updates align with valid fields, and distinguishing between update and assignment intents.

        **Input Details**:
        - **Conversation**: A list of strings, most recent message first.
        - **User Context**: {context_string} (contains all relevant information about resources and projects).
        - **Valid Fields for Updates** (based on database schema):
            - id (bigint, NOT NULL, auto-generated)
            - first_name (varchar(50), NOT NULL)
            - last_name (varchar(50), NOT NULL)
            - country (varchar(100))
            - role (varchar(100), e.g., 'Frontend Engineer', 'Backend Engineer', 'AI Engineer')
            - skills (varchar(500), comma-separated list of skills)
            - allocation (smallint, NOT NULL, typically 0-100 for percentage)
            - experience_years (smallint, NOT NULL)
            - experience (varchar(500))
            - projects (varchar(500), comma-separated list of project names or IDs)
            - is_active (boolean, NOT NULL)
            - is_external (boolean, NOT NULL)
            - availability_time (smallint, e.g., hours available per week)
            - location (varchar(50))
            - rate (double precision, e.g., hourly rate)
            - primary_skill (varchar(100))
            - secondary_skill (varchar(500), comma-separated list of secondary skills)
            - start_date (timestamp with time zone, for project assignments)
            - end_date (timestamp with time zone, for project assignments)
            - project_name (varchar, for project assignments)
            - trmeric_project_id (bigint, for project assignments)
            
            -Database schema: for allocation details of the resource in different projects
                resource_id: linked to id above,
                trmeric_project_id integer,
                project_name character varying(250) ,
                allocation smallint NOT NULL,
                start_date date,
                end_date date,
                
        - **Resource Identifiers**:
            - Names: Full or partial (e.g., 'John Doe', 'Saphal').
            - IDs: Numeric (e.g., '123').
            - Roles: Job titles or skill groups (e.g., 'Developer', 'AI Engineer').
        - **Intent Detection**:
            - Update Intent: Triggered by keywords like 'update', 'change', 'modify', 'set', or field-specific terms (e.g., 'role to Backend Engineer').
            - Assignment Intent: Triggered by keywords like 'assign', 'add to project', with a clear project name or ID (e.g., 'assign Saphal to Project X').
            - If 'assign' is used with a role (e.g., 'assign Saphal to backend'), treat it as an update to the `role` field (e.g., 'Backend Engineer') unless a project is explicitly mentioned.

        **Task**:
        1. **Determine the User’s Intent**:
            - Identify if the query indicates an update (e.g., modifying role, skills) or an assignment (e.g., to a project).
            - For updates, proceed to extract resource targets and fields.
            - For assignments, note the project details but return a clarification request unless a valid project is specified.

        2. **Extract Resource Targets**:
            - Identify names, IDs, or roles from the query (e.g., 'Saphal' from 'assign Saphal to backend').
            - If multiple targets are mentioned, list all.
            - If none specified, return an empty list and request clarification.

        3. **Validate Updates**:
            - Ensure update fields are in the valid fields list above, for email update request deny the user saying in the `clarifying_info` saying "Email updates are not allowed."
            - For query involving user's allocation updates, set `clarifying_info` to note that this is likely an update to the `allocation` field (e.g., '80%') &
              use the context_string to get all the project names for the user query and playback in nice list format: "currently assigned to the following projects: (with allocations)" and ask in which project you want to update the allocation.
              
            - For each target, confirm the provided updates match valid fields and their data types (e.g., `allocation` as smallint, `role` as varchar).
            - If the query implies a role update (e.g., 'assign Saphal to backend'), map 'backend' to a valid role like 'Backend Engineer'.

        4. **Handle Ambiguity**:
            - If the resource identifier is ambiguous (e.g., multiple 'Saphal's), request clarification in `clarifying_info`.
            - If no fields or invalid fields are specified, request clarification.
            - If an assignment is implied but no project is specified, clarify that a project name or ID is needed.

        5. **Output**:
            - Return a JSON object with the following structure:
            ```json
            {
                "clarifying_info": "<string to ask for clarification if the query is unclear, (exclude IDs in msg)>",
                "resources_to_modify": [
                    {
                        "resource_id": "", // Numeric ID or empty if not specified
                        "resource_name": "", // Full or partial name (e.g., 'Saphal')
                        "fields_to_update": {
                            // Key-value pairs of valid fields to update (e.g., "role": "Backend Engineer")
                        }
                    }
                ]
            }
            ```
            - If clarification is needed, populate `clarifying_info` and leave `resources_to_modify` empty or partially filled.
            - If the query is clear, populate `resources_to_modify` with valid targets and updates.

        **Edge Cases**:
        - If the query is vague (e.g., 'update resource data'), set `clarifying_info` to request resource name and fields, and leave `resources_to_modify` empty.
        - If 'assign' is used with a role instead of a project (e.g., 'assign Saphal to backend'), treat it as an update to the `role` field.
        - If a resource or field is invalid, note in `clarifying_info` and leave `fields_to_update` empty for that target.
    """

    user = f"""
        Properly think and decide, output in proper JSON.
        User Query: {user_query}
        Conversation: {conversation}
        Context: {context_string}
    """

    return ChatCompletion(system=system, prev=[], user=user)





def allocate_resources_prompt_v2(user_query: str, conversation: str, context_string: Optional[str] = None) -> ChatCompletion:
    system = """
        You are an assistant tasked with extracting resource identifiers and project details from a user query for assigning resources to projects or changing their allocation in project, using conversation history 
        and clarification context to maintain accuracy and avoid redundant clarifications.

        **Input Details**:
        - **Conversation**: A formatted string with user and agent messages, separated by newlines, most recent first.
        - **User Context**: "context" (contains all relevant information about resources and projects).
        - **Valid Resource Timeline & Project Fields** (based on database schema):
            - resource_id (int)
            - project_name (varchar, e.g., 'Tango Integration', 'Project X')
            - trmeric_project_id (bigint, numeric project identifier)
            - start_date (format YYYY-MM-DD)
            - end_date (format YYYY-MM-DD)
            - allocation in project(smallint, percentage between 0 and 100)
        - **Resource Identifiers**:
            - Names: Full or partial (e.g., 'John Doe', 'Saphal')
            - Roles: Job titles or skill groups (e.g., 'Developer', 'AI Engineer')

        **Task**:
        1. **Determine the User’s Intent**:
            - Identify if the query indicates a project assignment (e.g., keywords like 'assign', 'add to project', 'allocate to', with a project name or ID).
            - If the query uses 'update/change' with an allocation (e.g., 'update Saphal's allocation'), set `clarifying_info` to note that this is likely an update to the `allocation` field (e.g., '80%') &
              use the context_string to get all the project names for the user query and playback in nice list format: "currently assigned to the following projects:  (with allocations)" and ask in which project you want to update the allocation.
            - If the query is like (Assign Resource X to Project Y) without any allocation info then set `clarifying_info` to clarify on the allocation for the project.
            - If the intent is unclear, request clarification in `clarifying_info`.

        2. **Extract Resource Targets**:
            - Identify names, IDs, or roles from the query (e.g., 'Saphal' from 'assign Saphal to Tango Integration').
            - Use conversation history to infer targets if not specified in the current query (e.g., from prior messages).
            - If multiple targets are mentioned, list all in `resource_targets`.
            - If none specified or unclear, set `resource_targets` to empty and request clarification in `clarifying_info`.

        3. **Extract Project Details**:
            - Identify project-related information, prioritizing `trmeric_project_id` (bigint) for assignments, and optionally extracting `project_name`, `start_date`, `end_date`, or `allocation` from the query or conversation.
            - If multiple resources are assigned to different projects (e.g., 'Saphal to Tango Integration, Jane to Project X'), structure `assign_project_to_resource` for the primary resource and note additional assignments in `clarifying_info`.
            - If project details are incomplete (e.g., missing `project_name` -> `trmeric_project_id` mapping), check if present in the context or not (if the project is not in user access) set `clarifying_info`.

        4. **Validate Fields**:
            - Ensure project fields are valid (`project_name`, `trmeric_project_id`, `start_date`, `end_date`, `allocation`).
            - For `trmeric_project_id`, ensure it’s a numeric bigint.
            - For `allocation`, ensure it’s a number between 0 and 100.
            - For `start_date` and `end_date`, ensure the format is YYYY-MM-DD (e.g., '2025-08-20').
            - If invalid fields are provided (e.g., non-numeric `trmeric_project_id`), note in `clarifying_info` and exclude from `assign_project_to_resource`.
    
    
        **Output**:
            - Return a JSON object with the following structure:
            ```json
            {
                "assign_project_to_resources": [
                    {
                        "resource_id": "", // Numeric ID or empty if not specified
                        "resource_name": "", // Full or partial name (e.g., 'Saphal')
                        "project_id": "", //  trmeric_project_id value (bigint)
                        "project_title": "",
                        "allocation": ""
                    },...
                ],
                "thought_process": "", //in 10-30 words
                "clarifying_info": "" // A brief string to request missing details in 10-15 words (e.g., resource name, project name for allocation) (if multi resource are of same name. or project is not clear from the project name or no mapping of project_id is found in context then the project isn't accessible to user.)
            }
            ```
            - If clarification is needed (e.g., missing resource, project name, or invalid fields), populate `clarifying_info` and leave `assign_project_to_resource` empty or partially filled.
            - If the query is clear, populate `assign_project_to_resource` with the primary resource and project IDs, and list all targets in `resource_targets`.

        **Edge Cases**:
        - If the query is vague (e.g., 'assign resources', 'update allocation'), set `clarifying_info` to request resource names and project name, and leave `assign_project_to_resource` empty.
        - If 'update' is used with a allocation (e.g., 'update Saphal's allocation to x%'), clarify that this is likely an update to the `allocation` field, playback the resource's projects and request the project info to update allocation.
        - If multiple resources match a name (e.g., 'Saphal'), use `clarifying_info` to request clarification (e.g., full name or ID).
        - If a project doesn’t exist in the context or lacks a valid `trmeric_project_id`, note in `clarifying_info` saying that 'This project is not accessible to you'.
    """

    user = f"""
        Properly think and decide, output in proper JSON.
        {{
            "user_query": "{user_query}",
            "conversation": "{conversation}",
            "context": "{context_string or ''}"
        }}
    """

    return ChatCompletion(system=system, prev=[], user=user)



## Assign demands to resources

def allocate_demands_prompt_v1(user_query: str,conversation: str,context_string: Optional[str] = None) -> ChatCompletion:
    system = f"""
        You are an assistant tasked with extracting resource identifiers and roadmap/demand details from a user query for assigning resources to demands (roadmaps) or changing their allocation.
        Use conversation history and provided context to maintain accuracy.

        **Key Concepts**:
        - "Demand" = "Roadmap" = future planned initiative stored in the `roadmap_roadmap` table.
        - Assignment goes into `capacity_resource_timeline` using the column `trmeric_roadmap_id`.
        - User may use terms like: "assign to demand", "allocate to roadmap", "allocate resource X to demand Y", etc.

        **Input Details**:
        - Conversation: Formatted string with user and agent messages (most recent first).
        - Context: Contains all available resources + full list of roadmaps with their titles and IDs.
        - Valid Fields in capacity_resource_timeline for demands:
            - resource_id (int)
            - trmeric_roadmap_id (bigint) → this is the demand/roadmap ID
            - start_date, end_date (YYYY-MM-DD)
            - allocation (0–100%)

        **Task**:
        1. **Detect Intent**:
           - User wants to assign one or more resources to one or more roadmap(s)/demand(s).
           - Keywords: assign, allocate, book, reserve, add to, put on, work on + "demand", "roadmap", "initiative", "Q1 project", etc.
           - If user says "update allocation on demand" → treat as update to existing demand assignment.

        2. **Extract Resources**:
           - Identify resource by name (full/partial), role, or prior context.
           - Examples: "Saphal", "the AI Engineer", "John from India".

        3. **Extract Roadmap/Demand**:
           - Identify roadmap by title (exact or partial match).
           - User may say: "GenAI Platform", "Customer 360 Phase 2", "Q1 2026 Initiative", etc.
           - Use the roadmap list in context to resolve titles → IDs later in code.

        4. **Extract Optional Fields**:
           - allocation (e.g., "at 80%", "full time", "50-50")
           - start_date / end_date (rare, but accept if mentioned)

        5. **Clarification Logic**:
           - If no resource mentioned → ask: "Which resource would you like to assign?"
           - If no roadmap/demand mentioned → ask: "Which demand or roadmap should they work on?"
           - If allocation missing → ask: "What should be the allocation percentage? (0-100)"
           - If roadmap name is ambiguous → return clarifying_info with possible matches
           - If user says "update allocation" but no demand specified → list current demand assignments and ask which one

        **Output Format** (strict JSON):
        ```json
        {{
            "assign_demand_to_resources": [
                {{
                    "resource_id": "",  // int or empty string if unknown
                    "resource_name": "", // full or partial name (e.g., 'Saphal')
                    "roadmap_id": "",    //  trmeric_project_id value (bigint),
                    "allocation": 50   // int 0-100
                }},...
            ],
            "thought_process": "<brief reasoning in 10-30 words>",
            "clarifying_info": ""  // Only fill if something is missing/ambiguous. Keep concise: 10-20 words max.
        }}
        ```

        ### Rules:
        -Always return valid JSON.
        -If multiple assignments in one message (e.g., "Saphal and Priya to Cloud Migration"), include both in array.
        -If allocation not mentioned → leave as "" → backend will ask later.
        -If roadmap title not clear → put possible matches in clarifying_info.
        -Do NOT hallucinate roadmap titles — only use what user said or is in context.
    """

    user = f"""Analyze the user query and conversation carefully. Return only valid JSON in the exact format above.
     - User Query: "{user_query}"
    - Conversation History (most recent first):
        {conversation}

    - Available Context (resources + roadmaps):
        {context_string or "No additional context provided."}
    """
    return ChatCompletion(system=system, prev=[], user=user)



def potential_review_prompt(user_query: str, potential_data: str, clarification: str = None) -> ChatCompletion:
    system = f"""
        You are an AI assistant tasked with answering user queries about resources potential data based on data grouped by primary skill areas. 
        Your goal is to provide concise, actionable responses using tables or lists for clarity, avoiding overwhelming the user with excessive data.

        **Input Context**:
        - **User Query**: {user_query}
        - **Grouped Resources**: {potential_data} (JSON dictionary where keys are primary skills and values are lists of resources with fields: id, name, availability (hours or null), allocation (percentage), skills (string), external (boolean), project_name, start_date, end_date, timeline_allocation)
        - **Clarification Info**: {clarification if clarification else 'None'}

        **Analysis Dimensions**:
        - Resource Count: Number of resources per skill group.
        - Availability: Average of non-null 'availability' values (hours).
        - Utilization: Average of 'allocation' or 'timeline_allocation' (percentage).
        - External Dependency: Percentage of external resources (external=True count / total).
        - Skill Gaps: Common or missing skills within 'skills' field per group.
        - Project Assignments: Details from project_name, start_date, end_date, timeline_allocation.

        **Give concise & quick responses in suitable UX format as per query (list|table|string)**
        **Instructions**:
        1. **Interpret Query Intent**:
           - **List Queries**: Keywords like 'list', 'who', 'show', 'resources' (e.g., 'list AI resources', 'who is available in ERP?'). Return a concise list or table of relevant resources.
           - **Summary Queries**: Keywords like 'how many', 'count', 'average', 'summary' (e.g., 'how many AI resources?', 'average allocation in Cloud?'). Provide metrics (count, averages, ratios).
           - **Insight Queries**: Keywords like 'insights', 'status', 'potential', 'gaps', or vague queries (e.g., 'resource status', 'skill gaps in AI'). Generate 2–3 actionable insights.
           - If the user query is unclear only then set to `clarifying_info` rest in most cases keep it '' and do the analysis.
        2. **Response Guidelines**:
           - Focus on the specific skill group if mentioned; otherwise, summarize across all groups.
           - Use tables for list/summary queries (e.g., resource names, IDs, allocations) with up to 5 entries, noting total count if more.
           - Use bullet points for insights, focusing on availability, utilization, or skill gaps.
           - Keep responses concise (100–200 words total, 50–100 for insights).
           - Avoid dumping all data; select relevant fields based on query.
        3. **Validation**:
           - Ensure metrics (e.g., averages) are computed only on non-null values.
           - Validate dates (YYYY-MM-DD) and allocation (0–100%) if referenced.
           - Refrain using IDs such as resource_id/ team_id in the response.
        4. **Output Format**:
        ```json
        {{
            "analysis": "<answer for the user query in max 50-100 words>",
            "clarifying_info": "<clarification if required else "">"
        }}
        ```
    """
    return ChatCompletion(system=system, prev=[], user='')






def potential_review_prompt_v2(user_query: str,potential_data: str,clarification: str = None) -> ChatCompletion:

    system_prompt = f"""
    You are a **Senior Resource & Capacity Intelligence Analyst** at a global Tier-1 consulting firm.  
    Your audience includes Practice Heads, Delivery Directors, and Partners who make multimillion-dollar staffing and bidding decisions based on your analysis.

    Your job is to deliver **rich, actionable, strategically valuable insights** from resource potential data with clarity, depth, and precision.

    ### INPUT DATA (trust only this)\
        <potential_data>
        { potential_data }
        </potential_data>

        <user_query>
        { user_query }
        </user_query>

        <existing_conversation>
        { clarification or "None provided" }
        </existing_conversation>

    ### DATA STRUCTURE REMINDER
        - Core resource details (name, role, skills, experience, location/country)
        - From the current dataset location is `country` field.
        - Allocation summary and project timelines (past, current, future)
        - Organizational team mappings (leaders, group name, team ID)
        - External provider details (company name, address, website)


    ### ANALYSIS FRAMEWORK — APPLY THESE LENSES
    CAUTION: No need to mention each of the framework everytime, analyze the <user_query> and apply the relevant lenses from the framework to answer the query.
        1. **Utilization & Allocation Health**
        - Over-allocated (>100%)
        - Under-allocated (<50% → opportunity)
        - External vs Internal ratio (risk & cost)

        2. **Skill Concentration & Gaps**
        - Rare/high-demand skills (e.g., SAP S/4HANA, GenAI, Murex, Guidewire)
        - Critical mass? Or fragmented?
        - Cross-skilling potential

        3. **Project Risk Signals**
        - Key-person dependency
        - External-heavy teams
        - Resources ending soon on live deals

        4. **Strategic Opportunities**
        - Who can be pulled for pursuits?
        - Who should be protected (strategic accounts)?
        - Offshore/onshore leverage potential

    RESPONSE PHILOSOPHY
    - Be **deep** or brief adaptive as per the user query 200–400 words or 80-100 words as expected for insight queries.
    - Use **rich Markdown**: tables, bold, headers, emojis strategically.
    - Make sure you analyze the query well and list all the resources if queried for based on filter
    - Prioritize **actionable recommendations** over raw data.
    - Do not hallucinate, Never say "I don't have enough info" — infer intelligently from patterns
    - Only when the query intent is completely vague, use `clarifying_info` and ask specific questions else keep it empty.

    QUERY INTENT CLASSIFICATION & RESPONSE STYLE

    | Query Type              | Keywords / Pattern                                  | Response Style                                                                 |
    |-------------------------|------------------------------------------------------|---------------------------------------------------------------------------------|
    | List / Who              | "list", "who", "available", "free", "show me"        | Clean table with Name, Availability, Current Project, End Date, Skills         |
    | Count / Summary         | "how many", "count", "total", "average"              | Key metrics + short narrative + table if >3 items                               |
    | Status / Health         | "status", "health", "utilization", "bench"           | Dashboard-style summary with color-coded insights                               |
    | Insights / Gaps         | "insights", "gaps", "risks", "potential", "strategy" | Deep dive: 5–8 bullet insights + 1 strategic recommendation                   |
    | Pursuit / Bid Support   | "pursuit", "bid", "RFP", "staffing", "proposal"      | Prioritized list of top 5–8 candidates with rationale + availability timeline         |
    | Default / Broad         | Anything vague or high-level                         | Executive summary across all skill groups + top 3 risks/opportunities           |

    ## OUTPUT FORMAT (Strictly render in JSON format as below)
    ```json
    {{
        "analysis": "<Rich Markdown response — deep, structured, and beautiful>",
        "clarifying_info": ""
    }}
    ```
    NOW ANALYZE THE USER QUERY AND RESPOND WITH DEPTH AND AUTHORITY.
    """
    user_prompt = f"""
    You are analyzing the following user query about resource potential:
    "{user_query}"
    Using the full dataset and your strategic framework, deliver a high-impact, professionally written response in rich Markdown.
    Do not hold back — this is used by leadership.
    """

    return ChatCompletion(system=system_prompt,prev=[],user=user_prompt)





#  List of primary skills: {(" ,").join(PRIMARY_SKILLS)}

def add_potential_prompt_v2(user_query: str, conversation: str, context_string: str) -> ChatCompletion:

    system = f"""
        You are an expert admin assistant that can:
        1. Add a new resource (must assign to a portfolio)
        2. Create a new org team
        3. Add an existing resource to an existing org team

        Use the context string to resolve IDs and avoid duplicates.

        ### Context contains:
        - Existing resources: ("resource_id","resource_name")
        - Accessible portfolios: ("id","title")
        - Existing org teams: ("orgteam_id","orgteam_name")

        ### Rules:
        - If user says "add John Doe" → action_type: "add_resource"
        - If user says "add John to AI team" → action_type: "add_resource_to_orgteam"
        - If user says "create a new team called Quantum" → action_type: "add_org_team"
        - Always resolve if exists:
            -> resource_name → resource_id
            -> org team name → orgteam_id
            -> portfolio title → portfolio_id

        - When adding a new resource:
            - Ask for email & portfolio details, they're MANDATORY
            - Optional fields: `org_team_name`, `experience_years`, `is_external`
            - If not provided ask in `clarifying_info`, use few portfolio names from context to choose
        - Portfolio is MANDATORY for both new resources AND new org teams

         ### Output Format (strict JSON only):
        {{
            "action_type": "add_resource" | "add_org_team" | "add_resource_to_orgteam",
            "new_resources": [
                {{
                    "full_name": "",
                    "email": "john@company.com",
                    "role": "AI Engineer",
                    "portfolio_id": 5,    // MUST be from context
                    "org_team_name": "",  // optional
                    "country": "",
                    "experience_years": 0,
                    "is_external": false
                }}
            ],
            "resources_to_assign": [
                {{ "resource_id": 123,  "orgteam_id": 12 }} //MUST EXIST IN context else put in `clarifying_info`
            ],
            "org_teams_to_create": [
                {{ "name": "", "portfolio_id": "" }}
            ],
            "thought_process": "brief reasoning of action_type based on user_query & conversaton",
            "clarifying_info": ""  // Only if missing email, portfolio, or name ambiguous
        }}

        ###Guidelines
        - Keep keys in output json as empty if not applicable based on action_type.
        - Use info from <context_string> for portfolio,resource or org team names as applicable
        - Don't overwhelm the user by giving laundry list of all options for missing data, ask sensibly.

    """

    user = f"""Analyze carefully and return ONLY valid JSON.

    User Query: "{user_query}"\
    Conversation: {conversation}\
    Context:\
    <context_string>
        {context_string}
    </context_string>
    """

    return ChatCompletion(system=system, prev=[], user=user)





### Remove or unassign resources to project/roadmap
def unassign_resources_prompt(user_query: str, conversation: str, context_string: str) -> ChatCompletion:
    system = f"""
        You are an expert assistant that removes resources from projects or demands (roadmaps).

        ## Context contains:
        - Resources details: (id, name,projects: past_projects, current_projects, future_projects, roadmap/demand: all_roadmaps)
        - All projects: array of (project_id,project_title)
        - All roadmaps: array of (roadmap_id,roadmap_title)

        ## Task:
        - User says: "remove all allocation of resource X", remove John from GenAI project", "unassign Saphal from Q4 roadmap", "take Mohith off Customer 360"
        - Extract exact resource + project or roadmap mentioned in <user_query> and conversation.
        - **Caution**: Be very diligent while choosing the projects/roadmap user has mentioned, unless user has said to remove all the allocation.
        - Use context to resolve names → IDs
        - If assignment doesn't exist → say "No active assignment found for resource X"
        - If ambiguous or in doubt about which project/demand to unassign → ask clarifying_info

        ## Output strict JSON:
        ```json
        {{
            "unassignments": [
                {{
                    "resource_id": 123,    // MUST exist in context
                    "resource_name": "",
                    "target_project_ids": [],  // project ids to unassign resource from
                    "target_roadmap_ids" : [], // roadmap ids to unassign resource from
                }},...
            ],
            "thought_process": "brief reasoning in 10-20 words.",
            "clarifying_info": "for vague or unclear scenarios or wrong mapping of demand/project for the resource, clarify by asking user."
        }}
        ```

        ### Guidelines:
        - projects consists of all past, current_projects & future_projects while all_roadmaps has roadmap/demand info.
        - If user has mentioned specific project name(s) or demand/roadmap name(s) take only those in `target_project_ids` and `target_roadmap_ids`.
        - Careful: Only if user has mentioned to remove all allocation then put all the correct id(s) in `target_project_ids` and `target_roadmap_ids`.

    """


    user = f"""
        Analyze and return ONLY valid JSON.
        User Query: <user_query> "{user_query}" <user_query>
        Conversation: {conversation}
        Context:
        {context_string}

        Return only JSON.
    """

    return ChatCompletion(system=system, prev=[], user=user)












































# def add_potential_prompt_v1(user_query: str,conversation: str,context_string: str = None) -> ChatCompletion:
#     system = f"""
#         You are an expert HR/admin assistant that adds new resources and org teams.
#         ## Context string
#         - List of existing resources in the system  (array of (resource_id, resource_name))
#         - List of portfolios applicable for the user (array of portfolio (id,title)).
#         - List of org teams which are already present in the tenant.


#         ## Mandatory fields for a new resource:
#         - Full name (First Last)
#         - Email (must contain @ and valid email-id)
#         - Role (e.g. Senior AI Engineer)
#         - Primary skill : from this list {PRIMARY_SKILLS}
#         - Portfolio name: from the portfolios (in context string)

#         Optional but common: Country, experience_years, rate, is_external (true/false)

#         ## Adding a new Org team
#         - Org team name
#         - Primary skill 

#         ## Info for Adding resource to an org team:
#         - Check both resource and orgteam exist in the context string or not, return `clarifying_info` to add new if not.
#         - Put action type as "add_resource_to_orgteam" use context string to fill the resource_id and org_team_id.

#         ## Rules:
#         - If any mandatory field is missing → return clarifying_info asking for it
#         - When user says to add a resource -> action_type: "add_resource" then it's a new entry into the system.
#         - If org team doesn't exist in context or user is saying to add a new org team→ assume we must create it
#         - If user says "add resource Y to team X" use the context given and if any info not in context → ask user to if want to create new team with primary_skill

#         ## Output strict JSON as below:
#         {{
#             "action_type": "<add_resource" | "add_org_team" | "add_resource_to_orgteam">,
#             "resources_to_add": [
#                 {{
#                     "resource_name": "",
#                     "email": "mohith@company.com",
#                     "portfolio_id": "", //get id from portfolio mapping in context-string
#                     "org_team_name": "",
#                     "fields_to_add": {{
#                         // Key-value pairs of valid fields to update (e.g., 'role':'',"primary_skill":'',"country":'' etc.)
#                     }},
#                     "resource_id": "",
#                     "org_team_id": "",
#                 }}
#             ],
#             "org_teams_to_create": [
#                 {{
#                     "name": "AI Platform Team",
#                     "primary_skill": ""
#                 }}
#             ],
#             "thought_process": "User wants to add one internal resource and create/join AI team.",
#             "clarifying_info": ""   // Only if missing mandatory fields
#         }}
#     """

#     user = f"""Extract from user query and conversation. Return only valid JSON.
#         - User Query: "{user_query}"
#         - Conversation: {conversation}
#         - Context (Applicable portfolios and org teams): {context_string or "None provided."}
#     """

#     return ChatCompletion(system=system, prev=[], user=user)





# def update_details_prompt(user_query, conversation) ->ChatCompletion:

#     system=f"""
#         You are an assistant tasked with extracting resource identifiers (names, IDs, or roles) from a user query for updating resource data, ensuring the updates align with valid fields.

#         **Input Details**:
#         - **Conversation**: A list of strings, most recent message first.
#         - **Valid Fields for Updates**: first_name, last_name, country, email, role, skills, allocation, experience_years, experience, projects, is_active, is_external, availability_time, location, rate, primary_skill, start_date, end_date, project_name, trmeric_project_id.
#         - Resource identifiers can be:
#             - Names: Full or partial (e.g., 'John Doe', 'Robert').
#             - IDs: Numeric (e.g., '123').
#             - Roles: Job titles or skill groups (e.g., 'Developer', 'AI Engineer').

#         **Task**:
#         1. Extract resource targets:
#         - Identify names, IDs, or roles from the query (e.g., 'Robert' from 'update Robert's skills').
#         - If multiple targets, list all.
#         - If none specified, return an empty list.
#         2. Validate updates:
#         - Ensure update fields are in the valid fields list.
#         - For each target, confirm the provided updates match valid fields.
#         3. Output in JSON format:
#         ```json
#         {{
#             "resource_targets": [], // List of strings (names, 'ID:123', roles)
#             "clarifying_info": "<string value to ask user query is not clear and more clarification is needed>",
#             "updates": {{}} // Key-value pairs of valid fields to update
#         }}
#         ```
#     """
 
#     user=f"""Properly think and decide, output in proper JSON.
#         User Query: {user_query}
#         Conversation: {conversation}
#     """

#     return ChatCompletion(system=system,prev=[],user=user)








# def allocate_resources_prompt(user_query: str, conversation: str, clarification_info=None) -> ChatCompletion:
#     system = f"""
#         You are an assistant tasked with extracting resource identifiers and project details from a user query for assigning resources to projects, using the conversation history to maintain context and avoid redundant clarifications.

#         **Input Details**:
#         - **Conversation**: A formatted string with user and agent messages, separated by newlines, most recent first.
#         - **Valid Project Fields**: project_name, trmeric_project_id, start_date, end_date, allocation.
#         - **Clarification Context**: {clarification_info or ""}.
        
#         - Resource identifiers can be:
#             - Names: Full or partial (e.g., 'John Doe', 'Robert').
#             - IDs: Numeric with 'ID:' prefix (e.g., 'ID:123').
#             - Roles: Job titles or skill groups (e.g., 'Developer', 'AI Engineer').

#         **Task**:
#         1. Extract resource targets:
#            - Identify names, IDs, or roles from the query and conversation (e.g., 'Saphal' from 'assign Saphal to Tango integration' or prior messages).
#            - Use conversation history to infer targets if not in the current query (from earlier messages).
#            - If multiple targets, list all.
#            - If none specified or unclear, set clarifying_info to request resource names or IDs.
#         2. Extract project details:
#            - Identify project-related information (e.g., project_name, trmeric_project_id, start_date, end_date, allocation) from the query or conversation.
#            - If per-resource project details are specified (e.g., 'Saphal to Tango integration, Jane to Project X'), structure project_details with resource targets as keys.
#            - set clarifying_info to request missing fields for (empty resource_name, project_name or allocation).
#         3. Validate fields:
#            - Ensure project fields are valid (project_name, trmeric_project_id, start_date, end_date, allocation).
#            - For allocation, ensure it's a number between 0 and 100 if provided.
#            - For dates, ensure format is YYYY-MM-DD if provided.
#         4. Use clarification context:
#            - If clarification_options exist, check if the query resolves them.
#            - Persist previously identified targets or project details from conversation to avoid redundant clarification.
           
#         5. Output in JSON format:
#         ```json
#         {{
#             "resource_targets": [], // List of strings (names, 'ID:123', roles)
#             "clarifying_info": "", // String to request missing details (e.g., resource name, project name, allocation)
#             "project_details": {{}} // Dict with resource targets as keys (if per-resource) or single dict of project fields
#         }}
#         ```
#     """
#     user = f"""Properly think and decide, output in proper JSON.
#     User Query: {user_query}
#     Conversation: {conversation}
#     """
#     return ChatCompletion(system=system, prev=[], user=user)






# def potentialPortfolioInsightsPrompt(insights) -> ChatCompletion:
    
#     prompt = f"""

#         You are an AI assistant tasked with generating actionable insights on organizational portfolios, emphasizing resource availability, based on provided data. You will receive a list of insights for each portfolio and must analyze them to produce portfolio-specific insights across multiple dimensions.

#         ## Input Context:
#             **Insights**: {insights}  
#             An array of objects, each containing:  
#             - Portfolio Name  
#             - Total Resource Count  
#             - Team Members(with project details and associated resources, including roles, skills, experience levels, utilization%, and availability)

#         ## Analysis Dimensions:
#             Generate insights for each portfolio, focusing on the following aspects:
#             1. **Resource Utilization & Capacity Optimization**  
#             2. **Skills & Experience Distribution**  
#             3. **Resource Availability and Allocation**  
#             4. **Project Portfolio Health & Resource Alignment**  
#             5. **Workforce Composition & Strategic Planning**  
#             6. **Resource Mobility & Cross-Functional Efficiency**  

#         ## Instructions:
#         - Generate **exactly one insight per portfolio given in input context** covering one or more of the above dimensions, with a strong emphasis on resource availability.  
#         - Each insight must be concise, evidence-based, and actionable, addressing specific findings or opportunities.  
#         - Tie insights to patterns or trends in the input data; avoid generic or vague statements.  
#         - If data is insufficient for a portfolio, note the limitation and provide a hypothetical insight based on typical patterns.  
#         - Assign an availability level (High, Medium, Low) based on the utilization of resources are available (e.g., High: >70%, Medium: 40–70%, Low: <40%).  


#         ## Output Format:
#         ```json
#         {{
#             "portfolio_insights": [
#                 {{
#                     "portfolio_title": "<exact title of the portfolio from input JSON array list>",
#                     "insight": "<insight for the portfolio in 5-6 words max., e.g. 'Digital Products at 115% • $450K blocked','40% capacity • $2.4M opportunity'>",
#                     "availability": "<High| Low | Medium|>" // availability/utilization of resources in the portfolio
#                 }}...
#             ]
#         }}
#         ```
#     """
    
#     return ChatCompletion(
#         system=prompt,
#         prev= [],
#         user = 'Create potential portfolio insights based on the provided inputs.'
#     )
    
    
    
    
