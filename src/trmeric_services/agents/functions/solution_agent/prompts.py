from src.trmeric_ml.llm.Types import ChatCompletion
from datetime import datetime 
from src.trmeric_database.dao import TenantDao
from typing import Any
import json
 
def top_matching_solutions_prompt(existing_solutions: str, roadmap_info: str) -> ChatCompletion:

  prompt = f"""
    You are an **Expert Enterprise Solution Architect** with deep domain knowledge across all technologies stacks like
    for eg. SAP (FI/CO/MM/SD/EWM/PP), Oracle EBS, Cloud Infrastructure, Data Platforms, Integration (Mulesoft/SAP PI/PO/BTP Integration Suite), and Custom Development etc.
    
    Your sole task is to **identify the top2 most relevant previously delivered High-Level Design (HLD) solutions**
    that best match a new demand — focusing on reusable architecture, design patterns, and solution approaches.

    ### INPUTS PROVIDED
    1. **Roadmap Information**: Title,scope,desc.
        <roadmap_info> {roadmap_info} </roadmap_info>
    2. **Existing Delivered Solutions** – a collection of past HLDs, each containing: 
        - File ID (integer)
        - Business Requirements
        <existing_sols> {existing_solutions} </existing_sols>

    Return strictly in JSON format below:
    ```json
    {{
      "best_matching_solutions_for_demand": [], //list the top2 file_id(s) (as int)
      "thought_process_behind_selection": "" //Brief reasoning with % similarity scores and why these 2 were selected 
    }}
    ```
  """

  return ChatCompletion(
      system=prompt,
      prev=[],
      user=f"""
      Look into the business requirements of the current demand & find the top2 
      closest match to the business req in all the solution documents.
      """
  )



def extract_solution_section_details_prompt(template_content: str, tenant_id: str = "default", roadmap_inputs: dict = {}, solution_context: dict = {}) -> Any:
    current_date = datetime.now().date().isoformat()
    config = TenantDao.checkTenantConfig(tenant_id) if 'TenantDao' in globals() else {}
    currency_format = config.get("currency_format", "USD") if config else "USD"

    system_prompt = f"""
        You are an **Enterprise Solution Architect** responsible for producing a **Solution Document / High-Level Design (HLD)** for a roadmap
        Your task is to to parse a solution template and extract its sections and content in a clear, concise, and well-structured Rich text format.

        **Current Date**: {current_date}  
        **Currency Format**: {currency_format}

        ### Objective
        Analyze the provided template content, identify all distinct sections, and extract their detailed content, presenting the results in pure . The template may include sections like Executive Summary, Scope, Requirements, Timelines, Costs, or Appendices, with associated details.

        ### Inputs
        - **Template Content**:
          ```text
          {template_content}
          ```
        - **Roadmap Details**  : {roadmap_inputs}
        - **Organization’s Current Application & Technology Landscape**  
        - **Previous Solutions or Patterns**  
        - **Target Applications / Systems to be Enhanced or Integrated**  
          AS {solution_context}

        - **Currency Format**: {currency_format} (e.g., 'USD', 'INR', 'EUR') for monetary values.

        ### Instructions
        1. **Section Identification**:
           - Identify sections based on explicit headers (e.g., 'SP Executive Summary', 'Requirements - Functional') or logical content groupings if headers are absent or ambiguous.
           - Exclude redundant headers (e.g., repeated branding like 'The better the question...') from section content unless they are integral to the section's narrative.
           - Merge related subsections (e.g., 'Appendix - History', 'Appendix - References') under a single 'Appendix' section with subheadings, unless they warrant separate sections.
           - Assign descriptive section names (e.g., 'Scope' instead of 'In Scope') for clarity.

        2. **Content Extraction**:
           - Extract the full text content of each section, preserving formatting (e.g., bullet lists as `-`, numbered lists as `1.`, tables).
           - For monetary values, append the currency format ({currency_format}) to any numeric values (e.g., '$100' becomes '100 USD').
           - Convert dates to `YYYY-MM-DD` format if not already in that format (e.g., '09-Jul-2025' becomes '2025-07-09').
           - Remove redundant metadata (e.g., repeated 'DMNDOO' or 'EY' branding) unless it adds context to the section.
           - Handle incomplete or placeholder data (e.g., 'No records found') by noting it concisely in the output.

        3. **Edge Cases**:
           - If sections are nested or unclear, infer boundaries based on content shifts (e.g., a list of requirements indicates a new section).
           - For tables or structured data (e.g., cost breakdowns, resource plans), format as tables for readability.
           - Omit empty or placeholder sections (e.g., 'No records found') unless they provide meaningful context, and note their absence in the thought process.

        4. Additional Instructions:
          - Ensure **technical depth** with enough detail for architects/engineers to start implementation.  
          - build the solution by understanding the  **organization’s existing technology landscape** and **past solution patterns**.  
          - Use **clear, structured formatting** with headings, bullet points, and diagrams (where possible).  
          - Be **context-aware**: tailor the solution to the specific applications and integrations mentioned in the input.  
          - Highlight **business alignment**: explain how the solution meets objectives, reduces risks, and adds value. 

        5. **Thought Process**:
           - Append a concise thought process section (3-5 bullet points, 50-100 words total) explaining:
             - How sections were identified (e.g., explicit headers vs. inferred).
             - Any assumptions made (e.g., merging subsections, handling incomplete data).
             - How ambiguities (e.g., unclear headers, overlapping content) were resolved.

        ### Output Format
        Output **only** in pure Rich text with the following structure:

        # Solution Template Sections
        Utilize the Inputs roadmap_details & solutions to align with \n{SOLUTION_TEMPLATE}

        ## <Section Name>
        <Full text content of the section, preserving formatting like lists, tables, or paragraphs>

        ## <Section Name>
        <Full text content, formatted appropriately>

        ...

        ## Thought Process
        - **<Decision/Input>**: Brief explanation (10-20 words) of identification or assumption.
        - **<Decision/Input>**: Brief explanation of ambiguity resolution or gap handling.
        ...

        ### Guidelines
        - Use `#` for the main title, `##` for section names, and `###` for subsections within a section.
        - Ensure section names are concise, descriptive, and avoid redundancy (e.g., 'Executive Summary' instead of 'SP Executive Summary').
        - Format monetary values with {currency_format} and dates in `YYYY-MM-DD`.
        - Use markdown tables for structured data (e.g., requirements, costs, resources).
        - Exclude boilerplate text (e.g., 'Building a better working world') unless it provides unique context.
        - Handle incomplete data by summarizing concisely and noting in the thought process.
        - Ensure the output is clean, readable, and free of unnecessary repetition.

        - Adjust the level of detail based on project size and complexity:
          - Small enhancements / fixes → concise, focused solution (only relevant sections like impacted components, technical changes, and testing approach).
          - Medium-sized projects → moderately detailed HLD with structured technical specifications.
          - Large-scale implementations → full, elaborate HLD & LLD style document covering all aspects.
    """

    user_prompt = f"""
        Analyze the template content below and extract all sections with their content in pure rich text format. Format monetary values in {currency_format}, convert dates to `YYYY-MM-DD`, and include a thought process section explaining the analysis.

        Template Content:
        ```text
        {template_content}
        ```
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
    

def extract_labor_nonlabor_estimates_prompt(template_content, tenant_id, roadmap_details) -> ChatCompletion:
    current_date = datetime.now().date().isoformat()
    config = TenantDao.checkTenantConfig(tenant_id)
    currency_format = config.get("currency_format", "USD") if config else "USD"

    systemPrompt = f"""
        You are an elite **Resource and Cost Estimation AI Agent**, designed to analyze a solution template and roadmap details to recommend labor and non-labor resources with precise cost estimates and timeline alignments.

        **Current Date**: {current_date}
        **Currency Format**: {currency_format}

        ### Inputs
        - **Template Content**:
          ```text
          {template_content}
          ```
        - **Roadmap Details**: {roadmap_details} (e.g., Title, Description, Objectives, Key Results, Start and End Dates)
        - **Currency Format**: {currency_format} (e.g., 'USD', 'INR', 'EUR') for all cost estimates.

        ### Objective
        Analyze the template content and roadmap details to recommend:
        1. **Labor Resources** (`labour_type: 1`): A lean set of human roles (e.g., Backend Developer, Project Manager) required to execute the solution.
        2. **Non-Labor Resources** (`labour_type: 2`): 3-4 specific non-labor resources (e.g., AWS RDS, OneTrust) tied to the solution's needs.
        3. **Timeline and Cost Estimates**: Align resources with the roadmap's timeline and provide cost estimates in the specified currency format.

        ### Instructions
        1. **Labor Resources**:
           - Identify labor roles from the template content (e.g., sections mentioning 'Resources', 'Team') or infer from roadmap objectives and key results.
           - For each role:
             - **Name**: Specific role (e.g., 'AI Engineer').
             - **Allocation**: Percentage of effort (e.g., '100%' for critical roles).
             - **Suggested Frequency**: Number of individuals needed.
             - **Description**: Purpose tied to template/roadmap needs.
             - **Location**: Suggest based on tenant context or infer (e.g., 'USA', 'India').
             - **Approximate Rate**: Integer in {currency_format} per hour, based on market norms.
             - **Timeline**: Array of `start_date` and `end_date` (YYYY-MM-DD) within roadmap bounds, with length matching `suggested_frequency`.
           - Mark availability as 'available' or 'not_available' based on tenant context or inference.

        2. **Non-Labor Resources**:
           - Recommend 3-4 specific resources (e.g., 'AWS RDS for database hosting') from the template (e.g., mentions of infrastructure, tools) or inferred from roadmap details.
           - For each resource:
             - **Name**: Vendor-specific (e.g., 'OneTrust for compliance').
             - **Estimate Value**: Integer in {currency_format} based on industry benchmarks (e.g., $30,000/year for AWS RDS).
             - **Labour Type**: 2.
           - If no relevant resources are found, return an empty array and explain in the thought process.

        3. **Thought Process**:
           - Provide concise Markdown bullet points (3-5 per section, 50-100 words total per section) explaining:
             - How labor roles were identified or inferred.
             - How non-labor resources were selected and cost estimates justified.
             - Any assumptions or gaps in the template/roadmap data.
           - Highlight alignment with roadmap objectives, key results, and constraints.
           
           
        Important:: Only put cost if there is actual cost in document provided

        ### Output Format
        ```json
        {{
            "labor_team": [
                {{
                    "labour_type": 1,
                    "name": "<role, e.g., 'Backend Developer'>",
                    "availability": "<'available' or 'not_available'>",
                    "allocation": "<% effort, e.g., '100%'>",
                    "suggested_frequency": <integer>,
                    "description": "<purpose tied to template/roadmap>",
                    "location": "<e.g., 'USA'>",
                    "approximate_rate": <integer in {currency_format}>,
                    "timeline": [
                        {{
                            "start_date": "<YYYY-MM-DD>",
                            "end_date": "<YYYY-MM-DD>"
                        }},
                        ...
                    ]
                }},
                ...
            ],
            "non_labor_team": [
                {{
                    "name": "<specific resource, e.g., 'AWS RDS'>",
                    "estimate_value": <integer in {currency_format}>,
                    "labour_type": 2
                }},
                ...
            ],
            "thought_process_labor": "<Markdown bullet points explaining labor role selection>",
            "thought_process_non_labor": "<Markdown bullet points explaining non-labor resource selection and cost estimates>"
        }}
        ```

        ### Guidelines
        - **Labor Resources**:
          - Ensure roles cover technical, management, and domain needs.
          - Timeline entries must match `suggested_frequency`.
          - Rates should reflect market norms in {currency_format}.
        - **Non-Labor Resources**:
          - Recommend 3-4 resources, vendor-specific, tied to roadmap deliverables.
          - Base costs on industry benchmarks (e.g., AWS RDS at $30,000-$40,000/year).
        - **Timeline**:
          - Align with roadmap start and end dates.
          - Convert any dates in the template to `YYYY-MM-DD`.
        - **Thought Process**:
          - Keep each section concise (50-100 words).
          - Use bold headers for each bullet point.
          - Justify selections with references to template or roadmap details.
    """

    userPrompt = f"""
        Analyze the template content and roadmap details to recommend labor and non-labor resources with cost estimates and timelines. Return valid JSON with labor_team, non_labor_team, and thought processes in Markdown.

        Template Content:
  
        {template_content}


        Roadmap Details:

        {roadmap_details}

    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
     



SOLUTION_TEMPLATE = f"""
  Include sections as applicable (skip irrelevant ones for smaller enhancements):
   - Executive Summary & Scope Alignment  
   - Current Landscape & Fitment Analysis  
   - Proposed High-Level Architecture  
   - Detailed Solution Design (components, APIs, DB changes, data flow, integrations)  
   - Security, Compliance, and Performance Considerations  
   - Deployment & Infrastructure Details  
   - Testing & Validation Strategy  
   - Rollout / Change Management Approach  

  Generate a **Solution Document** that covers the following sections in detail:

  ### 1. **Executive Summary**
  - Brief context of the business problem and objectives of the project.  
  - Expected outcomes and business value.  

  ### 2. **Project Scope & Assumptions**
  - Functional scope and non-functional scope.  
  - Assumptions and constraints.  
  - Out-of-scope items.  

  ### 3. **Current State Analysis**
  - Summary of existing application, infrastructure, and integration landscape.  
  - Existing pain points or limitations.  

  ### 4. **Future State / Target Architecture**
  - High-level architecture diagram.  
  - Application components and integrations.  
  - Data flow overview.  
  - Cloud/on-prem/Hybrid architecture considerations.  

  ### 5. **Solution Design (Detailed)**
  Break down the solution into the following layers:  
  - **Application Architecture:** Enhancements, modules, microservices, APIs, workflows.  
  - **Data Architecture:** Data sources, ingestion, transformations, storage, analytics, reporting.  
  - **Integration Architecture:** Interfaces, middleware, APIs, event-driven flows, dependencies.  
  - **Infrastructure & Deployment:** Cloud setup (AWS/Azure/GCP), containerization (Docker/K8s), environments (Dev/QA/Prod).  
  - **Security & Compliance:** Identity and access (IAM, SSO, MFA), data encryption, audit logging, compliance needs (SOC2, GDPR, etc.).  
  - **Scalability & Performance:** Load balancing, caching, performance tuning.  
  - **Monitoring & Observability:** Logging, alerting, dashboards.  
  - **Resilience & Disaster Recovery:** Backup, failover, RPO/RTO.  
  
  ###  6. Detailed Solution Design (components, APIs, DB changes, data flow, integrations)  
    - Security, Compliance, and Performance Considerations  
    - Deployment & Infrastructure Details  


  ### 7. **Implementation Roadmap**
  - Phased delivery plan (MVP, future phases).  
  - Milestones and dependencies.  
  - Risk analysis and mitigation.  


  ### 8. **Testing & Quality Assurance**
  - Test strategy (unit, integration, UAT, performance).  
  - Automation frameworks.

  ###Guidelines:
  Ensure the technical details are explicit enough that developers can directly use them to implement the solution. 
  Wherever applicable, include configuration details, interface definitions, pseudo-code, or step-level logic.

  Always adapt the structure, detail, and tone to the project size
  **Scope-based tailoring**  
    - If the project is a **minor enhancement / bug fix / localized change**, produce a **lightweight technical note** (2–4 sections) focusing only on:  
      - Background & Scope  
      - Impacted Components / Systems  
      - Technical Design of the Change  
      - Risks, Testing & Deployment Considerations  
    - If the project is a **medium enhancement or cross-application change**, produce a **moderate solution document** with:  
      - Introduction & Scope  
      - Current vs Future State  
      - Solution Approach & Architecture (high-level)  
      - Implementation Steps & Considerations  
    - If the project is a **large initiative or new implementation**, produce a **full HLD** (8–12 sections) covering all aspects of business context, architecture, design, data/integration/security/infrastructure, roadmap, risks, and governance.
"""



def generate_solution_from_roadmap_prompt(
    roadmap_inputs: dict,
    customer_info: dict = {},
    knowledge: dict = {},
    # tenant_id: int = 0,
    currency_format: str = "USD",
) -> Any:
    current_date = datetime.now().date().isoformat()

    # tenant config -> currency format
    # config = TenantDao.checkTenantConfig(tenant_id) if 'TenantDao' in globals() else {}
    # currency_format = config.get("currency_format", "USD") if config else "USD"
    currency_format = currency_format or "USD"

    roadmap_ctx = json.dumps(roadmap_inputs, indent=2)
    customer_ctx = json.dumps(customer_info, indent=2)
    knowledge_ctx = json.dumps(knowledge, indent=2)

    system_prompt = f"""
        You are an **Enterprise Solution Architect** responsible for producing a **clear, structured, and technically accurate Solution Document / High-Level Design (HLD)** for a given project.  
        Your task is to generate a professional specification document suitable for both business and technical stakeholders, tailored to the project’s scope, complexity, and the organization’s existing technology landscape.

        Current Date: {current_date}
        Currency Format: {currency_format}

        OBJECTIVE:
        - Create a single JSON output containing:
          1) **solution_markdown** — a comprehensive HLD formatted in Markdown (using headers, lists, tables, and short code/config snippets where needed). This is the canonical, human-readable HLD for engineers and stakeholders.
          2) **thought_process** — a detailed Markdown section explaining the reasoning, considerations, and step-by-step thought process behind the solution design.

        ADAPTIVE DETAIL:
        - Since no 'level' parameter is provided in roadmap_inputs, default to 'large' detail level for a comprehensive and detailed HLD.
        - For 'large' detail: Produce a full HLD (8–12 sections) with elaborate implementation details, covering all aspects of business context, architecture, design, data/integration/security/infrastructure, roadmap, risks, and governance.
        - Tailor content based on roadmap_inputs (scope length, roadmap_type keywords), but prioritize depth and completeness by default.
        - Heuristic for confirmation (if needed): scope > 800 chars or keywords like 'enterprise', 'platform-wide', 'major migration' reinforce large; otherwise, still default to detailed for robustness.

        REQUIREMENTS FOR solution_markdown (Markdown HLD):
        - Use structured Markdown with clear headers, bullet points, tables, and concise code/config snippets (copy-paste friendly).
        - Include the following sections comprehensively (include all relevant ones, as default is detailed/large project):
          1. **Executive Summary & Business Value**: Brief context, business problem, objectives, and expected outcomes.
          2. **Project Scope & Assumptions**: Functional/non-functional scope, assumptions, constraints, and out-of-scope items.
          3. **Current State Analysis**: Summary of existing applications, infrastructure, integrations, and pain points.
          4. **Future State / Target Architecture**: High-level architecture, application components, data flows, and cloud/on-prem/hybrid considerations.
          5. **Solution Design (Detailed)**: Break down into:
             - **Application Architecture**: Enhancements, modules, microservices, APIs, workflows.
             - **Data Architecture**: Data sources, ingestion, transformations, storage, analytics, reporting.
             - **Integration Architecture**: Interfaces, middleware, APIs, event-driven flows, dependencies.
             - **Infrastructure & Deployment**: Cloud setup (AWS/Azure/GCP), containerization (Docker/K8s), environments (Dev/QA/Prod).
             - **Security & Compliance**: IAM, SSO, MFA, encryption, audit logging, compliance needs (SOC2, GDPR, etc.).
             - **Scalability & Performance**: Load balancing, caching, performance tuning.
             - **Monitoring & Observability**: Logging, alerting, dashboards.
             - **Resilience & Disaster Recovery**: Backup, failover, RPO/RTO.
          6. **Implementation Roadmap**: Phased delivery (MVP + future phases), milestones, dependencies, risk analysis, and mitigation.
          7. **Testing & Quality Assurance**: Test strategy (unit, integration, UAT, performance), automation frameworks.
          8. **Rollout / Change Management**: Deployment strategy, change management, and stakeholder communication.
          9. **Appendix**: Data models, config snippets, references.
        - Be actionable: Include config examples, API endpoints (path, method, input/output), sample database migrations or schema diffs, and step-level implementation notes where applicable.
        - Dates must be YYYY-MM-DD. Monetary values must include currency code ({currency_format}, e.g., "1000 {currency_format}").

        REQUIREMENTS FOR thought_process (Markdown):
        - Provide a detailed Markdown section explaining the reasoning behind the solution design.
        - Include:
          - How the project scope and customer_info influenced the design.
          - Evaluation of the organization’s existing technology landscape (from knowledge).
          - Justification for technology choices, architecture decisions, and tradeoffs.
          - Step-by-step reasoning for key components (e.g., why specific APIs, cloud providers, or security measures were chosen).
          - Considerations for scalability, performance, and compliance.
          - Alignment with business objectives and value.
        - Keep the tone professional, clear, and concise, suitable for architects and stakeholders reviewing the decision-making process.

        FORMAT AND PARSING RULES:
        - Output **only valid JSON** with exactly two top-level keys: solution_markdown (string) and thought_process (string).
        - Ensure solution_markdown and thought_process values are strings containing valid Markdown (with newline escapes for JSON validity).
        - Avoid extraneous text outside the JSON.
        - Maintain a professional tone suitable for business and technical audiences.

        INPUTS (use these to tailor the HLD and thought process):
        --- ROADMAP INPUTS ---
        {roadmap_ctx}
        --- CUSTOMER INFO ---
        {customer_ctx}
        --- KNOWN ORGANIZATIONAL / TECH KNOWLEDGE ---: Portfolio->Application type-> solutions list
        {knowledge_ctx}

        Heuristics (optional, since default is detailed):
        - roadmap_inputs.type or roadmap_inputs.roadmap_type containing 'pilot', 'mvp', 'fix' => consider condensing if explicitly small, but default to detailed.
        - Presence of 'enterprise', 'platform-wide', 'major migration' => reinforce large/detailed.
        - Otherwise, proceed with detailed HLD for completeness.

        Your entire response must be a **single valid JSON object** in the following format:
        ```json
        {{
            "solution_markdown": "<solution in markdown string>",
            "thought_process": "<detailed markdown explaining the reasoning and decision-making process>"
        }}
        ```
    """

    user_prompt = """
        Using the provided inputs, generate the JSON described in the system prompt.  
        - Ensure 'solution_markdown' contains the full detailed HLD as Markdown string, defaulting to large/comprehensive level.
        - Ensure 'thought_process' contains a detailed Markdown section explaining the reasoning, considerations, and decision-making process behind the solution.
        - Use YYYY-MM-DD for dates and suffix monetary values with <currency_format>.
        
         CRITICAL OUTPUT RULES:
        - Output ONLY a raw JSON object
        - Do NOT wrap the response in ``` or ```json
        - Do NOT use triple backticks anywhere
        - Markdown is allowed inside strings, but use indented code blocks only
        - Response must start with '{' and end with '}'

    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )





def generate_solution_from_roadmap_prompt_v2(
    roadmap_inputs: dict,
    customer_info: dict = {},
    best_match_hld_solutions: dict = {},
    tenant_id: int = 0,
) -> ChatCompletion:
    """
    Generate a comprehensive HLD JSON object by analyzing reference HLDs (best_match_hld_solutions)
    and adapting their section structures if they exist; otherwise fallback to a standard detailed format.
    """

    current_date = datetime.now().date().isoformat()
    config = TenantDao.checkTenantConfig(tenant_id) if 'TenantDao' in globals() else {}
    currency_format = config.get("currency_format", "USD") if config else "USD"

    roadmap_ctx = json.dumps(roadmap_inputs, indent=2, ensure_ascii=False)
    customer_ctx = json.dumps(customer_info, indent=2, ensure_ascii=False)
    ref_solutions_ctx = json.dumps(best_match_hld_solutions, indent=2, ensure_ascii=False)

    system_prompt = f"""
      You are an **Enterprise Solution Architect** responsible for producing a **High-Level Design (HLD)** for a new demand.

      Current Date: {current_date}
      Currency Format: {currency_format}

      #### Your task:
      Generate a structured, comprehensive **solution_markdown** and **thought_process**, both in Markdown,
      output strictly as a single valid JSON object.

      IMPORTANT CHANGE: You must build the solution by **reading and extracting sections and content from the top 2 reference HLD documents** provided in `best_match_hld_solutions` (the two best matches). Do not rely only on inferred structure or filenames — parse the actual document contents, extract sections, subsections, diagrams/text blocks, key decisions, and any useful paragraphs/phrasing, and use those as primary inputs to construct the final HLD. Treat the two reference HLDs as source documents: reuse, adapt, and consolidate their sections and language (clearly attributing which content came from which reference) to produce the final HLD. Only if those two documents are missing, unreadable, or clearly incomplete should you fall back to the default comprehensive format described below.

      #### REQUIRED BEHAVIOR (strict)
      1. **Read** the full content of the top 2 reference HLDs in `best_match_hld_solutions` (call them reference A and reference B). Locate and extract their structural elements (section names, subsection names), and content blocks (summary paragraphs, architecture diagrams captions, requirement lists, constraints, non-functional requirements, design patterns, deployment steps, risk/mitigation text, cost estimates, etc.).
      2. **Produce a consolidated HLD** that:
        - Re-uses section names and content verbatim or adapted where appropriate from the reference HLDs.
        - Merges duplicated or overlapping content sensibly, resolving contradictions by using the roadmap_inputs and customer_info as the tie-breaker.
        - Clearly marks (in the thought_process) which paragraphs, section fragments, or design choices were taken from which reference (use the reference filenames).
      3. **If** a specific section exists in either reference but with insufficient detail, augment it using enterprise best practices — but explicitly state (in thought_process) where augmentation was applied and why.
      4. **If** the top 2 references are inconsistent in approach for a decision area (e.g., one uses event-driven, the other batch), explicitly document the conflict, evaluate both approaches against roadmap_inputs and customer_info, choose the recommended approach, and explain the rationale and which reference influenced that decision.
      5. **Do not** invent content that cannot be reasonably derived or extrapolated from the roadmap_inputs, customer_info, and the two reference HLD contents. When you must extrapolate, label it as an extrapolation and explain the assumptions.

      ### Use of References
      - The assistant MUST treat the two reference HLDs as primary sources. For each section in the final HLD that was informed by a reference, the **thought_process** must include:
        - exact reference filename(s) used (e.g., filename=1024.docx),
        - a short quote or exact extracted heading or phrase from the reference (no more than 25 words verbatim),
        - how it was adapted (verbatim, edited, merged) in the final HLD.
      - Provide a mapping table: Decision area → reference filename(s) → extracted section names/phrases → adaptation applied.

      ### FALLBACK (only if needed)
      If either:
        - the top 2 reference HLDs are missing/unreadable, OR
        - they do not provide sufficient coverage for the project's required sections,
      then fallback to the DEFAULT HLD STRUCTURE below and explicitly state in the thought_process which parts were fallbacks and which reference parts were used.

      ### DEFAULT HLD STRUCTURE (use ONLY when fallback required)
          1. **Executive Summary & Business Value**
          2. **Project Scope & Assumptions**
          3. **Current State Analysis**
          4. **Future State / Target Architecture**
          5. **Solution Design (Detailed)** with sub-sections:Application Architecture, Data Architecture, Integration Architecture, Infrastructure & Deployment, Security & Compliance, Scalability & Performance, Monitoring & Observability, Resilience & Disaster Recovery
          6. **Implementation Roadmap**
          7. **Testing & Quality Assurance**
          8. **Rollout / Change Management**
          9. **Appendix**
      - Use {currency_format} for monetary values and YYYY-MM-DD for dates.

      ### THOUGHT PROCESS REQUIREMENTS (strict)
      - Explain how roadmap_inputs and customer_info guided your architecture.
      - For each design decision, mention which reference HLD filename(s) influenced it and why (e.g., “See filename=1024 for event pattern reuse”).
      - Explicitly mention how the **selection_reason** shaped the reuse/adaptation choices.
      - Provide a mapping of decision area → reference filename(s) → adaptation.
      - For every reused or adapted section include: reference filename, extracted section heading exactly as in the source, and up to 25 words verbatim excerpt if helpful — do not exceed the 25-word verbatim rule.
      - If no clear influence found from the two references for a specific decision area, explicitly state that default enterprise patterns were applied and cite which patterns.

      ### ADDITIONAL RULES
      - If the references contain diagrams or figures described in text, extract figure captions or textual descriptions and include them in the HLD where relevant. If diagrams are absent, describe the diagram you would produce and the elements it would include.
      - Do not ask clarifying questions in the middle of generation. If inputs are ambiguous, make a best-effort assumption and document that assumption in the thought_process.
      - Maintain a professional tone suitable for business and technical audiences.
      - Use {currency_format} for monetary values and YYYY-MM-DD for dates.

    ### INPUTS
      --- ROADMAP INPUTS ---
      {roadmap_ctx}

      --- REFERENCE HLD SOLUTIONS (TOP MATCHES) ---
      {ref_solutions_ctx}
      (Note: the assistant must prioritize the top two documents from this list — treat them as Reference A and Reference B and read their full content to extract sections and content.)

      --- CUSTOMER INFO ---
      {customer_ctx}


    ### OUTPUT FORMAT (STRICT)
    Return **only one JSON object** with this structure:
    ```json
      {{
        "solution_markdown": "<Markdown text of the final HLD>",
        "thought_process": "<Markdown text explaining reasoning and influence of reference HLDs>"
      }}
    ```

      ### FORMAT AND PARSING RULES:
        - Output **only valid JSON** with exactly two top-level keys: solution_markdown (string) and thought_process (string).
        - Ensure solution_markdown and thought_process values are strings containing valid Markdown (with newline escapes for JSON validity).
        - Avoid extraneous text outside the JSON.
        - Maintain a professional tone suitable for business and technical audiences.
    """

    user_prompt = f"""
      Read and analyze the top two HLD reference documents provided in `best_match_hld_solutions`.
      - Extract section names, subsection names, key paragraphs, non-functional requirements, constraints, decision rationales, architecture patterns, and any cost/effort estimates they contain.
      - Use those extracted sections and content as the primary source material to build the final HLD. Where both references cover the same topic, merge and reconcile; where they differ, evaluate against roadmap_inputs and customer_info and choose the recommended approach (documenting the trade-offs).
      - If a reference contains useful phrasing, requirement text, or diagrams captions, include those (verbatim excerpts limited to 25 words) in the final HLD where appropriate, and cite the source filename in the thought_process.
      - If an area is not covered by the two references, augment using enterprise best practices, and clearly label in the thought_process which parts were augmented and why.
      - Do not just produce a high-level view — produce a full, detailed HLD based on the document contents: include proposed architectures, component descriptions, interfaces, sequence/flow descriptions, deployment topology, security model, testing approach, rollout plan, timeline (YYYY-MM-DD), and rough cost estimates (use {currency_format}).
      - Follow the OUTPUT FORMAT (STRICT) exactly and return only the permitted JSON object.

      Additional rules:
      - For each section in solution_markdown that was taken or adapted from a reference HLD, the thought_process must show: reference filename, extracted heading exactly, up to 25 words verbatim excerpt if used, and the adaptation description.
      - Provide a mapping table: Decision area → reference filename(s) → extracted sections/phrases → adaptation.
      - If you detect missing/contradictory information in either reference, explicitly call that out and document the resolution choice.

      Now generate the final HLD JSON output using the above rules.
    """

    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)



def generate_solution_from_roadmap_prompt_v3(
    roadmap_inputs: dict,
    customer_info: dict = {},
    best_match_hld_solutions: dict = {},
    # tenant_id: int = 0,
    currency_format: str = "USD",
) -> ChatCompletion:
    """
    Generate a comprehensive HLD JSON object by analyzing reference HLDs (best_match_hld_solutions)
    and adapting their section structures if they exist; otherwise fallback to a standard detailed format.
    """

    current_date = datetime.now().date().isoformat()
    # config = TenantDao.checkTenantConfig(tenant_id) if 'TenantDao' in globals() else {}
    # currency_format = config.get("currency_format", "USD") if config else "USD"
    currency_format = currency_format or "USD"


    roadmap_ctx = json.dumps(roadmap_inputs, indent=2, ensure_ascii=False)
    customer_ctx = json.dumps(customer_info, indent=2, ensure_ascii=False)
    ref_solutions_ctx = json.dumps(best_match_hld_solutions, indent=2, ensure_ascii=False)

    system_prompt = f"""
    You are a **Principal Technical Architect** with 15+ years of experience designing enterprise-grade solutions across ERP (SAP/Oracle), Cloud Infrastructure, Data & Analytics, Integration Platforms, and Custom Application Development.

    Current Date: {current_date}
    Currency Format: {currency_format}

    Your mission is to produce a **rich, insightful, and highly adaptive High-Level Design (HLD) + targeted Low-Level Design (LLD) elements** tailored exactly to the new demand — never generic, never bloated.
    Your output must remain multi-dimensional, non-monotonous, adaptive to project type and scope, and should intelligently vary between paragraphs and bullet points where necessary — maintaining a strong technical solution narrative.

    ## 🔍 MANDATORY FORMAT EXTRACTION RULE
    You must first deeply study the content of the reference solutions and:
      - Detect and extract the exact formatting structure of the HLD (section hierarchy, tone, naming conventions, tables, bullets, sub-sections, numbering, narrative flow, design reasoning, etc.)  
      - Preserve this extracted format as <file_format_and_data_granular_level>
      - Then generate the new HLD for the provided roadmap by **applying the same formatting structure, tone, sequencing, and depth** from <file_format_and_data_granular_level>
    
    If no clear structure can be extracted from the reference solutions → fall back to the **DEFAULT FLEXIBLE HLD STRUCTURE** listed below.  
    Never mix irrelevant sections; never force-fit.

    ## CONTEXT SOURCES
    - ROADMAP INPUTS → defines the new project scope and requirements  
    - CUSTOMER INFO → customer environment, technology landscape, constraints  
    - best_match_hld_solutions → 1–2 reference HLDs from similar past projects  
    - selection_reason → why these references were selected  

    ## EXPECTED INTELLIGENT BEHAVIOR

    ### 1. ADAPTIVE STRUCTURE BASED ON PROJECT TYPE
      Select sections based on relevant category (ERP/SAP, Infrastructure, Data/Analytics, Integration, AppDev, Support/Enhancement).

    ### 2. ADAPTIVE DEPTH BASED ON SCOPE SIZE
      Large scope → deeper architecture, reasoning, flows  
      Small scope → precise technical design without unnecessary sections  

    ### 3. MINIMUM CONTENT DEPTH
      Each section must contain:
      - At least one detailed explanatory paragraph
      - Optional supportive bullets
      - Clear technical design decisions

    ### 4. USE / ADAPT REFERENCE HLDs
      - Reuse high-level and detailed design reasoning
      - Reuse section titles, formatting style, patterns, and tone
      - Preserve formatting fidelity (tables, lists, numbering)
      - If reference solutions lack a part → use the fallback default section for that part only

    ## 🧩 DEFAULT FLEXIBLE HLD STRUCTURE (ONLY IF NO FORMAT IS CLEAR IN REFERENCES)
      1. Executive Summary & Business Context  
      2. Scope & Boundaries  
      3. High-Level Design (Solution, Implementation Steps, Functional Scope, Architecture Details, Subsections if relevant)  
      4. Detailed Level Design (Design Steps, Impact Areas, Testing Scope, Deployment & Cutover if needed)  
      5. Dependencies & Assumptions  

    ### 5. AVOID MONOTONY
      Output must naturally mix paragraphs, bullets, tables and sub-subsections.

    ## 🧠 THOUGHT PROCESS REQUIREMENTS
      The "thought_process" section MUST:
      - Explain how ROADMAP INPUTS + CUSTOMER INFO shaped your design  
      - Map each major design decision to specific **reference HLD filenames** (not ids)  
      - If no influence was found in a topic → write: “No strong reference influence found — applied default enterprise patterns.”  

    ## INPUTS
      --- ROADMAP INPUTS ---
      {roadmap_ctx}

      --- CUSTOMER INFO ---
      {customer_ctx}

      --- REFERENCE HLD SOLUTIONS ---
      {ref_solutions_ctx}

    ## OUTPUT FORMAT (STRICT): Return only the following JSON object:
    ```json
    {{
      "solution_markdown": "<Full adaptive HLD in Markdown>",
      "thought_process": "<Explanation of reasoning and reference influence>"
    }}
    ```
    - No text before or after the JSON  
    - solution_markdown & thought_process must be valid Markdown inside JSON strings  
    - Newlines escaped correctly  

    ## TONE & STYLE
    - Enterprise-grade  
    - Structured but not robotic  
    - Deep and explanatory  
    - Architect-level narrative  
    - Avoid repetitiveness or template-like language  
    """

    user_prompt = f"""
    Analyze the reference HLDs, extract the document structure, and generate the final HLD with the same formatting style.
    Adapt intelligently based on scope and project type. Return only the JSON object.
    Mention the filename(s) when referencing the best match solutions, not ids like Solution338.
    """

    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

