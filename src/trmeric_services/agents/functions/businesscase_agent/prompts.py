from src.trmeric_ml.llm.Types import ChatCompletion
from datetime import datetime 
from src.trmeric_database.dao import TenantDao

CURRENT_DATE = datetime.now().date().isoformat()

def businessCaseTemplatePrompt(roadmap_data, labor_cost_analysis, non_labor_cost_analysis, template_content, tenant_id) -> ChatCompletion:
    current_date = datetime.now().date().isoformat()
    config = TenantDao.checkTenantConfig(tenant_id)
    systemPrompt = f"""
        You are tasked with generating a detailed business case for the provided roadmap or initiative, including financial calculations (NPV, ROI, Payback Period), structured according to a standardized JSON template provided in <template_content>. The business case must comprehensively describe the roadmap or initiative, its strategic alignment, key results or KPIs, expected benefits, costs, risks, and other essential aspects necessary for business approval. All financial calculations must be performed and included in the output, with clear justifications. All monetary values must be formatted with a dollar sign ($) and include commas for thousands (e.g., $1,234,567).

        ### Input Data
        - Roadmap Data:
          <roadmap_data>
          {roadmap_data}
          </roadmap_data>
        - Labor Cost Analysis:
          <labor_cost_analysis_done>
          {labor_cost_analysis}
          </labor_cost_analysis_done>
        - Non-Labor Cost Analysis:
          <non_labor_cost_analysis_done>
          {non_labor_cost_analysis}
          </non_labor_cost_analysis_done>
        - Template Content (Standardized JSON):
          <template_content>
          {template_content}
          </template_content>
          
        - Important: Customer Currency Config: {config}
        This is most important for doing all the estimate calculations.
        you have to stick to this currency used by this customer

        ### Cost and Budget Estimates
        Provide detailed cost estimates for the project, including initial capital expenditures and ongoing operational expenses. Include estimates for development, implementation, licensing, maintenance, support, and resource allocation. Non-labor costs include hardware, software licensing, cloud & hosting, training/certification, facilities & utilities, travel & accommodation, compliance & legal, etc. Format all cost values with a dollar sign ($) and commas (e.g., $1,234,567).

        - **Labor Costs**:
          - Use the provided <labor_cost_analysis_done>.
          - Identified by `labour_type = "labour"` in team_data.
          - Do not annualize or multi-year calculate; use the total effort estimate from <labor_cost_analysis_done>.
          - Format total labor cost as $X,XXX,XXX.
        - **Non-Labor Costs**:
          - Use the provided <non_labor_cost_analysis_done>.
          - Identified by `labour_type = "non labour"` in team_data.
          - Total non-labor cost is the sum of `labour_estimate_value` (fixed costs, no multiplication/division).
          - Format total non-labor cost as $X,XXX,XXX.
        - **Total Cost**:
          - Total Cost = Labor Cost + Non-Labor Cost.
          - Format total cost as $X,XXX,XXX.

        ### Financial Analysis and ROI
        Compute the expected financial benefits, including cost savings, revenue growth, NPV, ROI, and Payback Period, using data from <roadmap_data> and calculated costs. Format all monetary values with a dollar sign ($) and commas (e.g., $1,234,567).

        - **NPV Calculation**:
          - Formula: **NPV = Σ (Ct / (1 + r)^t) - C0**
            - **Ct** = Cash inflow during period t (from `revenue_uplift_cash_inflow_data` and `operational_efficiency_gains_savings_cash_inflow` in <roadmap_data>). Format as $X,XXX,XXX.
            - **r** = Discount rate (use 5% if not specified in <template_content> or <roadmap_data>).
            - **t** = Time period (year).
            - **C0** = Initial investment cost (total cost from cost estimates). Format as $X,XXX,XXX.
          - Steps:
            1. Extract Ct from cash inflow data in <roadmap_data> and format as $X,XXX,XXX.
            2. Identify r and number of periods (n) from <template_content> or default to 5% and 3 years.
            3. Determine C0 from total cost and format as $X,XXX,XXX.
            4. Show the formula, substitute values, and calculate NPV step-by-step.
            5. Store in `NPV` with justification, formatted as $X,XXX,XXX.

        - **ROI Calculation**:
          - Formula: **ROI = Net Profit / Total Investment (in percent)**
            - Net Profit = Total Revenue + Operational Efficiency Savings - Total Costs (from key results and baseline values in <roadmap_data>). Format as $X,XXX,XXX.
          - Steps:
            1. Calculate Net Profit and format as $X,XXX,XXX.
            2. Show the formula, substitute values, and calculate ROI.
            3. Store in `ROI` with justification (as a percentage, e.g., XX.XX%).

        - **Payback Period Calculation**:
          - Formula: **Payback Period = Initial Investment / Annual Cash Inflows**
          - Steps:
            1. Identify Initial Investment (C0) and Annual Cash Inflows (average Ct over periods). Format as $X,XXX,XXX.
            2. Show the formula, substitute values, and calculate Payback Period.
            3. Store in `payback_period` with justification (in years, e.g., X.XX years).

        ### Custom Template
        The <template_content> is a standardized JSON object defining the output structure, sections, fields, and custom calculations. Interpret it intelligently:
        - Extract sections (e.g., `output_structure.executive_summary`) and include them in the output.
        - Each section has an index (e.g.,`output_structure.executive_summary.index`) field which tells the order of sections in output. Include it in same structure as <template_content> in the output JSON.
        - Include fields specified in the template (e.g., `required`, `format`,`index`).
        - Perform custom calculations (e.g., `calculations` field in <template_content>) if specified, with clear justifications. Format all monetary results as $X,XXX,XXX.
        - If <template_content> is empty or invalid JSON, fall back to the default structure below.

        ### Instructions
        - Use data from <roadmap_data>, <labor_cost_analysis_done>, and <non_labor_cost_analysis_done>.
        - Perform all financial calculations (NPV, ROI, Payback Period) and any custom calculations in <template_content> and always in (important: tabular format).
        - Follow the structure in <template_content>, mapping its sections and fields to the business case output.
        - Ensure that you include index for each section of the <template_content> as it is in the same structure in the output JSON.
        - If <template_content> includes custom sections (e.g., `market_analysis`) or calculations (e.g., `Breakeven Point`), incorporate them and format monetary values as $X,XXX,XXX.
        - Provide detailed justifications for all calculations, showing formulas and values with monetary values formatted as $X,XXX,XXX.
        - Output the business case as a JSON object, adhering to <template_content> or the default structure.

        Current Date: {current_date}
    """
    
    userPrompt = f"""
        Properly output the data in JSON 
        as per the template and accurately doing all the financial calculations.
        Ensure all monetary values are formatted with using this config- {config} and commas in the monetary values to make it a proper string.
        
        Always think about keeping this structure for section or subsection as required: description, format, columns (if table), data, calculation, result, etc., as required.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    
    
    

def createFinancialPrompt(roadmap_data, labor_cost_analysis, non_labor_cost_analysis, template_content, tenant_id) -> ChatCompletion:
    current_date = datetime.now().date().isoformat()
    config = TenantDao.checkTenantConfig(tenant_id)
    systemPrompt = f"""
        You are tasked with generating a detailed business case for the provided roadmap or initiative, including financial calculations (NPV, ROI, Payback Period), structured according to a standardized JSON template provided in <template_content>. The business case must comprehensively describe the roadmap or initiative, its strategic alignment, key results or KPIs, expected benefits, costs, risks, and other essential aspects necessary for business approval. All financial calculations must be performed and included in the output, with clear justifications. All monetary values must be formatted with a dollar sign ($) and include commas for thousands (e.g., $1,234,567).

        ### Input Data
        - Roadmap Data:
          <roadmap_data>
          {roadmap_data}
          </roadmap_data>
        - Labor Cost Analysis:
          <labor_cost_analysis_done>
          {labor_cost_analysis}
          </labor_cost_analysis_done>
        - Non-Labor Cost Analysis:
          <non_labor_cost_analysis_done>
          {non_labor_cost_analysis}
          </non_labor_cost_analysis_done>
        - Template Content (Standardized JSON):
          <template_content>
          {template_content}
          </template_content>

        ### Cost and Budget Estimates
        Provide detailed cost estimates for the project, including initial capital expenditures and ongoing operational expenses. Include estimates for development, implementation, licensing, maintenance, support, and resource allocation. Non-labor costs include hardware, software licensing, cloud & hosting, training/certification, facilities & utilities, travel & accommodation, compliance & legal, etc. Format all cost values with a dollar sign ($) and commas (e.g., $1,234,567).

        - **Labor Costs**:
          - Use the provided <labor_cost_analysis_done>.
          - Identified by `labour_type = "labour"` in team_data.
          - Do not annualize or multi-year calculate; use the total effort estimate from <labor_cost_analysis_done>.
          - Format total labor cost as $X,XXX,XXX.
        - **Non-Labor Costs**:
          - Use the provided <non_labor_cost_analysis_done>.
          - Identified by `labour_type = "non labour"` in team_data.
          - Total non-labor cost is the sum of `labour_estimate_value` (fixed costs, no multiplication/division).
          - Format total non-labor cost as $X,XXX,XXX.
        - **Total Cost**:
          - Total Cost = Labor Cost + Non-Labor Cost.
          - Format total cost as $X,XXX,XXX.

        ### Financial Analysis and ROI
        Compute the expected financial benefits, including cost savings, revenue growth, NPV, ROI, and Payback Period, using data from <roadmap_data> and calculated costs. Format all monetary values with a dollar sign ($) and commas (e.g., $1,234,567).

        - **NPV Calculation**:
          - Formula: **NPV = Σ (Ct / (1 + r)^t) - C0**
            - **Ct** = Cash inflow during period t (from `revenue_uplift_cash_inflow_data` and `operational_efficiency_gains_savings_cash_inflow` in <roadmap_data>). Format as $X,XXX,XXX.
            - **r** = Discount rate (use 5% if not specified in <template_content> or <roadmap_data>).
            - **t** = Time period (year).
            - **C0** = Initial investment cost (total cost from cost estimates). Format as $X,XXX,XXX.
          - Steps:
            1. Extract Ct from cash inflow data in <roadmap_data> and format as $X,XXX,XXX.
            2. Identify r and number of periods (n) from <template_content> or default to 5% and 3 years.
            3. Determine C0 from total cost and format as $X,XXX,XXX.
            4. Show the formula, substitute values, and calculate NPV step-by-step.
            5. Store in `NPV` with justification, formatted as $X,XXX,XXX.

        - **ROI Calculation**:
          - Formula: **ROI = Net Profit / Total Investment (in percent)**
            - Net Profit = Total Revenue + Operational Efficiency Savings - Total Costs (from key results and baseline values in <roadmap_data>). Format as $X,XXX,XXX.
          - Steps:
            1. Calculate Net Profit and format as $X,XXX,XXX.
            2. Show the formula, substitute values, and calculate ROI.
            3. Store in `ROI` with justification (as a percentage, e.g., XX.XX%).

        - **Payback Period Calculation**:
          - Formula: **Payback Period = Initial Investment / Annual Cash Inflows**
          - Steps:
            1. Identify Initial Investment (C0) and Annual Cash Inflows (average Ct over periods). Format as $X,XXX,XXX.
            2. Show the formula, substitute values, and calculate Payback Period.
            3. Store in `payback_period` with justification (in years, e.g., X.XX years).

        ### Custom Template
        The <template_content> is a standardized JSON object defining the output structure, sections, fields, and custom calculations. Interpret it intelligently:
        - Extract sections (e.g., `output_structure.executive_summary`) and include them in the output.
        - Include fields specified in the template (e.g., `required`, `format`).
        - Perform custom calculations (e.g., `calculations` field in <template_content>) if specified, with clear justifications. Format all monetary results as $X,XXX,XXX.
        - If <template_content> is empty or invalid JSON, fall back to the default structure below.

        ### Instructions
        - Use data from <roadmap_data>, <labor_cost_analysis_done>, and <non_labor_cost_analysis_done>.
        - Perform all financial calculations (NPV, ROI, Payback Period) and any custom calculations in <template_content> and always in (important: tabular format).
        - Follow the structure in <template_content>, mapping its sections and fields to the business case output.
        - If <template_content> includes custom sections (e.g., `market_analysis`) or calculations (e.g., `Breakeven Point`), incorporate them and format monetary values as $X,XXX,XXX.
        - Provide detailed justifications for all calculations, showing formulas and values with monetary values formatted as $X,XXX,XXX.
        - Output the business case as a JSON object, adhering to <template_content> or the default structure.

        Current Date: {current_date}
    """
    
    userPrompt = f"""
        Properly output the data in JSON 
        as per the template and accurately doing all the financial calculations.
        Ensure all monetary values are formatted with using this config- {config} and commas in the monetary values to make it a proper string.
        
        Always think about keeping this structure for section or subsection as required: description, format, columns (if table), data, calculation, result, etc., as required.
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    


def businessCasePromptForIdea(idea_data,template_content,config,labor_cost_analysis=None,non_labor_cost_analysis=None) ->ChatCompletion:

  systemPrompt = f"""
    You are an expert business analyst and strategic advisor. Your task is to create a **concise, insight-driven business case** for a newly proposed idea or initiative.  
    This is an early-stage business case — it should provide enough clarity for investment consideration but avoid exhaustive project-level detail.

    **Objective:**  
    Summarize the idea’s intent, investment required, and its potential business value and ROI in a simple, decision-oriented format that supports early funding discussions.

    **Input Data**:
    - Ideation Details: <ideation_data> {idea_data}</ideation_data>
    - Estimated Labor & Non-Labor Costs: 
      <labor_cost_analysis> {labor_cost_analysis} </labor_cost_analysis>
      <non_labor_cost_analysis> {non_labor_cost_analysis} </non_labor_cost_analysis>

    - Template (Standardized JSON): <template_content>{template_content}</template_content>

    - Important: Customer Currency Configuration: {config}
      This is most important for doing all the estimate calculations you have to stick to this currency used by this customer

    **Your Task:**
    1. Create a **crisp executive summary** describing the idea, problem/opportunity, and expected outcome.  
    2. Provide **estimated total cost** (labor + non-labor) formatted as per {config} sign and commas.  
    3. Estimate **potential benefits** (e.g., efficiency gains, revenue uplift, risk reduction) with short explanations.  

    4.Financial Analysis and ROI
        Compute the expected financial benefits, including NPV, ROI, and Payback Period, using data from <ideation_data> and calculated costs. 
        Format all monetary values with a dollar sign ($) and commas.
:  
      - **ROI (%)** = (Net Benefit / Total Investment) * 100  
      - **Payback Period (years)** = Initial Investment / Annual Benefits  
      - **NPV ($)** (optional) using a 5% discount rate for up to 3 years if cash inflow data exists.  

    5. Include a short **risk and dependency summary** (1–2 bullets).  
    6. End with a **recommendation statement** (e.g., “Recommended for concept validation” or “Needs further technical review”).

    ### Custom Template
    The <template_content> is a standardized JSON object defining the output structure, sections, fields, and custom calculations. Interpret it intelligently:
    - Extract sections (e.g., `output_structure.executive_summary`) and include them in the output.
    - Each section has an index (e.g.,`output_structure.executive_summary.index`) field which tells the order of sections in output. Include it in same structure as <template_content> in the output JSON.
    - Include fields specified in the template (e.g., `required`, `format`,`index`).
    - Perform custom calculations (e.g., `calculation` field in <template_content>) if specified, with clear justifications. Format all monetary results as $X,XXX,XXX.

    ### Instructions
    - Use data from <ideation_data>, <labor_cost_analysis>, and <non_labor_cost_analysis>.
    - Perform all financial calculations (NPV, ROI, Payback Period) and any custom calculations in <template_content> and always in (important: tabular format).
    - Follow the structure in <template_content>, mapping its sections and fields to the business case output.
    - Ensure that you include index for each section of the <template_content> as it is in the same structure in the output JSON.
    - If <template_content> includes custom sections (e.g., `market_analysis`) or calculations (e.g., `Breakeven Point`), incorporate them and format monetary values as $X,XXX,XXX.
    - Provide detailed justifications for all calculations, showing formulas and values with monetary values formatted as $X,XXX,XXX.
    - Output the business case as a JSON object, adhering to <template_content> or the default structure.

    Current Date: {CURRENT_DATE}
  """

  userPrompt = f"""
      Properly output the data in JSON as per the template and accurately doing all the financial calculations.
      Ensure all monetary values are formatted with using this config- {config} and commas in the monetary values to make it a proper string.
      
      Always think about keeping this structure for section or subsection as required: description, format, columns (if table), data, calculation, result, etc., as required.
  """
  return ChatCompletion(
      system=systemPrompt,
      prev=[],
      user=userPrompt
  )







## for KP shared template
def kpFormatTemplatePrompt(file_content: str) -> ChatCompletion:
    system_prompt = f"""
      You are an expert in analyzing structured and semi-structured business case documents specific to Project Charters (Business Case Definition / BCD).
      Your task is to convert the provided document content into a clean JSON schema that includes ALL sections and subsections detected in the content, 
      formatted consistently with the style of the provided template. 
      
      You must think carefully, step by step, to ensure precision and consistency.
      Your job is to analyze the full document content provided — whether or not sections are clearly labeled — and generate a JSON structure that captures:
      
        - All major sections (e.g., Project Name, Business Need, Scope, Benefits, Financial Summary, Risks, Appendix)
        - Any subsections within them (e.g., In Scope/Out of Scope under Scope, Hard/Soft under Benefits)
        - Even implicit sections (e.g., Objective, Success Criteria, Schedule, Project Organization) that are logically grouped in the text

      ## File content 
      <content_of_file>
        {file_content}
      </content_of_file>

      ## Guidelines: For each section or subsection, include:
      - "description": purpose of the section (infer from placeholders, headings, or context.
      - "format": expected format (paragraph, list, table, date, number, etc.)
      - Decide the format well keeping the nice user experience (UX) in mind.
      - "index": Every top-level section MUST have an "index" (integer, starting from 1)      
      - If it's a table, include "columns": [array of exact column names inferred from document]
      - If it contains dates, specify "date_format": e.g., "MM/DD/YYYY"

      - DO NOT include any actual data from the document. Only describe the structure.
      - DO NOT guess based on generic business case templates. Use only what's inferred from the actual document content.
      - Always include mandatory Kaiser sections if not explicitly present but implied: project_name, business_need_and_objective (with subsections business_need and objective), scope (with subsections in_scope and out_of_scope), 
        benefits (with subsections direct_benefits and indirect_benefits), success_criteria, financial_analysis_and_ROI, schedule_and_implementation_strategy, risk_analysis, project_organization_and_governance, appendix (with pnl_impact_summary and cash_flow_summary subsections).
      - Use snake_case keys for section and subsection names (e.g., "business_need_and_objective", "out_of_scope").

      ## IMPORTANT - Financial section example (if detected or implied):
      ```json
      {{
        "financial_analysis_and_ROI": {{
          "description": "Financial justification including costs, NPV, cash flows, and ROI calculations",
          "format": "table",
          "index": 8,
          "subsections": {{
            "revenue_uplift_cashflow": {{
              "description": "Projected revenue increases by year",
              "format": "table",
              "index": 1,
              "columns": ["Year", "Revenue Category", "Total Revenue", "Justification"]
            }}
          }},
          "calculation": {{
            "description": "Key financial metrics like NPV, IRR",
            "format": "table",
            "columns": ["formula", "calculation", "result", "justification"],
            "section_data": [{{"data": {{}}}}]
          }}
        }}
      }}
      ```


      ## OUTPUT format: Strictly render this:
      The output should be clean JSON and follow this shape exactly (dynamic sections, but with index on all levels):
      ```json
      {{
          "output_structure": {{
              "<section_name_1>":{{
                  "description": "<what is this section>",
                  "format": "<expected format: paragraph / table / date / list>",
                  "index": <int>,
                  "subsections": {{
                      "<optional subsection 1>": {{
                          "description": "<what is expected>",
                          "format": "<format>"
                      }},...
                  }}
              }},
              ...,
          }}
      }}
      ```

      If a table, add "columns" at the section or subsection level as appropriate.
      Ensure scope always has out_of_scope subsection.
      Return ONLY the JSON. No explanations.
    """
    user_prompt = """
      Analyze the content carefully and return only the correct JSON structure containing: all explicitly or implicitly present sections/subsections
      Important: **You must ensure that every top-level section MUST have an "index" **
      Do not add anything beyond that.
    """
    return ChatCompletion(
      system=system_prompt,
      prev=[],
      user=user_prompt
    )


def kp_businesscase_prompt(
    roadmap_details: str,
    file_content: str,
    template_content: str,
    labor_cost: str,
    non_labor_cost: str,
    config: dict
) -> ChatCompletion:

    currency = config.get("currency_symbol", "$")
    current_date = datetime.now().date().isoformat()

    systemPrompt = f"""
      You are an expert Business Case Author with 10+ years of experience writing project charters for executive leadership.

      Your task now changes:

      ===========================================================
      🔹 YOU MUST OUTPUT A SINGLE JSON OBJECT WITH 2 KEYS:
      ===========================================================
      ```json
      {{
        "business_case_markdown": "<final business case in markdown>",
        "thought_process_markdown": "<your reasoning as markdown>"
      }}
      ```

      ⚠️ Rules:
      - Do NOT output anything outside this JSON.
      - Both JSON values MUST contain markdown (but no backticks).
      - The business_case_markdown MUST strictly follow the customer template below.
      - The thought_process_markdown must show structured reasoning behind the business case creation (sections, logic, tradeoffs), but still formatted in plain markdown paragraphs and lists.
      - All JSON strings MUST be properly escaped.

      ===========================================================
      📄 REQUIRED BUSINESS CASE TEMPLATE (for business_case_markdown)
      ===========================================================
      # <Project Name>

      | Section             | Details                                         |
      |---------------------|-------------------------------------------------|
      | Project Name        | <Insert relevant project name>                  |
      | Project Customer    | Leader who benefits most from the project       |
      | Project Start       | MM/DD/YYYY                                      |
      | Project End         | MM/DD/YYYY                                      |
      | Charter Author      |                                                 |
      | Charter Last Revised | todays date Current Date: {current_date}                                    |

      ---

      ## Business Need and Objective

      ### A. Current Business Situation / Problem
      Explain:
      - What is the current business situation or problem?
      - Key issues that result from this
      - How the project corrects these issues
      - Strategic alignment
      - Why now

      ### B. Objectives
      **To:**  
      Describe the high-level objective.

      **In a way that:**  
      - 4–5 bullets explaining strategy, scope, key actions, risk mitigation.

      **So that:**  
      Direct business value and expected outcomes.

      ---

      ## Scope

      ### In Scope
      - Items that will be delivered

      ### Out of Scope
      - Items that will NOT be delivered


      ---

      ## Benefits

      ### Direct (Measurable) Impacts
      Use realistic metrics:
      - Operational metrics (X → Y)
      - Customer/user satisfaction (X → Y)
      - Financial impacts ({currency} values — cost reduction, cost avoidance, revenue improvement)

      ### Indirect Impacts
      - Productivity
      - Employee satisfaction
      - Reduced burnout  
      ➡ Ensure strong cause–effect reasoning.

      ---

      ## Success Criteria and Proof Points
      Explain:
      - What capabilities will be delivered?
      - How will success be measured?
      - Who will measure it, and when?


      ---

      ## Financial Summary
      Provide summaries derived from roadmap data + cost analyses.  
      Format all monetary values as **{currency}X,XXX,XXX**.


      ---

      ## Cost Summary
      Break down:
      - Capital Costs  
      - Startup Expense  
      - Effort Months  
      - Ongoing Operating Costs  

      Use realistic values derived from inputs.
      Present in a clean Markdown table if appropriate.


      ---

      ## Schedule & Implementation Strategy

      ### Key Milestones  
      - Milestone 1 — MM/DD/YYYY  
      - Milestone 2 — MM/DD/YYYY  
      - Milestone 3 — MM/DD/YYYY  
      - Milestone 4 — MM/DD/YYYY  

      ### Implementation Strategy
      Explain the approach and key decisions.  
      Do NOT include generic statements.  
      All choices must be meaningful and aligned with project delivery.


      ---

      ## Risks and Dependencies

      ### Issues
      - List issues - (Known Facts & Constraints)

      ### Risks
      - List risks - (Unknowns that could harm the project)

      ### Dependencies
      - List dependencies - (This project depends on)

      ### Dependent Projects 
      - List dependent activities - (Projects depending on this project)


      ---

      ## Risk Mitigation Strategies
      For each risk, provide a corresponding mitigation strategy.


      ---

      ## Project Approvals  

      - **Project Customer:**  
      - **Project Board 1 – Business Sponsor:**  
      - **Project Board 2 – Accountable Finance Lead:**  
      - **Project Board 3:**  
      - **Project Manager:**  


      ---

      ## Appendix

      ### P&L Impact Summary  
      Provide a clean Markdown table reflecting the financial impact summary.

      ### Cash Flow Summary  
      Provide a table summarizing yearly cash flows.



      ===========================================================
      📥 INPUT DATA YOU MUST USE
      ===========================================================

      <roadmap_data>
      {roadmap_details}
      </roadmap_data>

      <labor_cost_analysis>
      {labor_cost}
      </labor_cost_analysis>

      <non_labor_cost_analysis>
      {non_labor_cost}
      </non_labor_cost_analysis>

      ===========================================================
      ⚠️ CRITICAL RULES
      ===========================================================
      1. Output ONLY valid JSON with the two keys.  
      2. No backticks anywhere.  
      3. No commentary outside JSON.  
      4. Monetary values must be formatted as **{currency}X,XXX,XXX**.  
      5. Business_case_markdown must be 2–3 pages worth of structured markdown.  
      6. Thought_process_markdown must clearly explain your reasoning steps.  
      
      
      ===========================================================
      📌 DATE RULES (IMPORTANT)
      ===========================================================
      - Since, roadmap_details contains dates, extract and use them for all attr like cost and milestone.. no assumed date or fake date.
      - All dates must be in MM/DD/YYYY format.
      
      Current Date: {current_date}
    """
    
    userPrompt = """
      Generate the JSON now.  
      Remember: Output ONLY the JSON object with the 2 keys:
      - business_case_markdown  
      - thought_process_markdown  

    """

    return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)
