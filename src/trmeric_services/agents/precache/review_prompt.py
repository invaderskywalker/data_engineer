from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import datetime


def generatePortfolioReviewInsights(data, status, previous_week_status_updates=None, milestone_data=None, integration_data=None) -> ChatCompletion:    
    systemPrompt = f"""
    You are an expert portfolio review assistant tasked with generating concise, actionable insights for a project portfolio review, tailored for C-suite executives and business stakeholders.\

    Your audience prioritizes strategic alignment, financial performance, project health, and risk management.\
    Using the provided project data, status, previous week's status updates, and milestone data, create a four-part insight summary for each project, focusing on:\
    1. **Business Values Insights**:\
        **Business Framework Requirements:**\
        **Key Results/Outcomes**: [Quantified business metrics, ROI, efficiency gains]
        **Strategic Objectives**: [Primary business goals the project achieves]
        **Organizational Alignment**: [How it supports company strategy, digital transformation goals]
        Focus on:
        - Current progress against milestones\
        - Completed milestones\
        - Current status of the project\
        - Capabilities being developed\
        Output: "Create a 2-3 sentence executive summary that: \
          - Starts with the business value proposition\
          - Includes quantified results/expected outcomes\
          - Connects to strategic alignment\
          - Ends with capability/process transformation impact""\


    2. **Agent Insights**:\ 
        - Summarize **execution status** by highlighting **project progress,current status, challenges, and risks** from status updates and ongoing tasks.\
        - Emphasize on bringing a balance picture (e.g.,milestones status, ongoing status updates, key achievements, delays and risks).\
        - Highlight positive points from  **key milestones completions, status comments**.\
        - Showcase **progress metrics** (e.g., task completion rates, velocity, or throughput).\
        - If integration data is available, include **one concise line summarizing the integration status** (e.g., sync health, last updated, or key metrics from the connected tool).\

    3. **Project Risks**: Identify 1-2 critical risks based on milestone progress (e.g., delays, missed milestones) or other provided data, and suggest a brief mitigation strategy for each. If milestone or risk data is missing, note it and use available information to infer potential risks.\
        
    4. **Recent Achievements**:\ 
        - Highlight **3-4 recent achievements** based on Key accomplishments, milestones or status updates (e.g., completed deliverables, stakeholder approvals, or efficiency gains).\
        - Emphasize on Key accomplishments from Project Data and **positive impact** (e.g., cost savings, accelerated timelines, or enhanced capabilities).\
        - If data is missing, note it and focus on available information.\
    5. ** Business Impacts **: Briefly describe the business impact using the key results in 2 points each max 60 words.\
     
    Each point should be clear, concise, and free of technical jargon. Use actionable language to guide decisions. If data is missing or invalid, note it briefly and focus on available information.\
    Ensure the tone is professional and strategically focused.

    **Input Data**:
    - Project Data: {data}\
    - Previous Week Status Updates: {previous_week_status_updates}\
    - Latest Status Data: {status}\
    - Milestone Data: {milestone_data}\
    - Integration Data: {integration_data if integration_data else "No integration data available"}\

    **Output Requirement**: Return the response in valid JSON format with the following structure:
    ```json
    {{
      "project_brief_description": "", // max: 50 words
      "project_risks": [], // "1-2 sentences identifying critical risks based on milestones or data, with brief mitigation strategies in max 20 words each"
      "achievements_and_next_steps": {{
        "recent_achievements": [],  // "upto 4 sentences highlighting Key accomplishments, recent milestones, status improvements, or positive outcomes."
      }},
      "key_objectives_and_business_impacts": ["", ""], // 2 points with max 30 words each
      "agent_insights": ["", ""], // 4 points max 40 words each. If integration data exists, one point must summarize it.
    }}
    ```
    Ensure JSON is valid, with special characters (e.g., quotes) properly escaped. If inputs are empty or malformed, return a JSON object with brief notes on missing data and proceed with available information.
    """
    
    userPrompt = f"""
    Output in valid JSON format as per instructions.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    

def generateArchivedProjectReviewInsights(data, all_status_updates, milestone_data, retro_data, value_realization_data) -> ChatCompletion:
    systemPrompt = f"""
    You are an expert portfolio review assistant tasked with generating concise, actionable insights for archived or closed projects, tailored for C-suite executives and business stakeholders.

    Your audience prioritizes value realization, lessons learned, project outcomes, and key accomplishments. Using the provided project data, status history, milestones, retro analysis, and value realization data, create a five-part insight summary for each project, focusing on:
    1. **Value Realization Summary**: Provide 1-2 bullet points summarizing key outcomes from value realization data (e.g., KPIs achieved vs. planned). Use 'kpi_name' and 'key_learnings' to summarize outcomes if 'achieved_value' or 'planned_value' are unavailable. If no value realization data exists, return ["No value realization data available for this project."].
    2. **Executive Summary**: Summarize the project's overall health (scope, delivery, spend) and key accomplishments across its lifecycle in 2-3 bullet points.
      Highlight final status, key trends (e.g., persistent risks or recoveries), 
      completion context, 
      and notable achievements. 
      Verify milestone completion status and address discrepancies between archival date and milestone target or project end dates.
      
    3. **Agent Insights**: 
        - Summarize **project health** (scope, delivery, spend) across the lifecycle in 3-5 bullet points (max 30 words each).
        - Highlight **positive points** from  **impact on key milestones, status comments, key results, and business priorities** and **challenges faced** (e.g., delays, scope creep, or resource issues).
        - Incorporate **all status updates** and **status comments** to provide a balanced view of successes and issues; noting trends and their impact on outcomes.
        - Verify **milestone completion status** and address discrepancies between archival date and milestone target or project end dates.
        - Provide actionable insights highlighting **critical challenges** (e.g., budget overruns, missed deadlines) and **positive outcomes** (e.g., early delivery, exceeded KPIs).
      
    4. **Key Learnings**: 
        - Emphasize **actionable takeaways** by summarizing key lessons from retro analysis in 2-3 sentences as an array of strings (max 40 words each) (for future projects, balancing successes and areas for improvement).
        - If retro data is unavailable, infer 1-2 distinct lessons from status updates, milestones, or risks, focusing on what worked (e.g., effective planning) or what could improve (e.g., resource allocation, stakeholder alignment).
    5. **Business Values Insight**: 
        **Business Framework Requirements:**
        **Key Results/Outcomes**: [Quantified business metrics, ROI, efficiency gains]
        **Strategic Objectives**: [Primary business goals the project achieved]
        **Organizational Alignment**: [How it supported company strategy, digital transformation goals]
        **Business Process Impact**: [Which core processes were enhanced/transformed]
        **Business Capabilities Enabled**: [New capabilities or enhanced existing ones]
        
        Focus on:
        - Actual results achieved vs. initial objectives
        - Quantified business metrics and ROI delivered
        - Strategic goals accomplished
        - Business processes transformed
        - Capabilities now operational
        
        Output: Create a 3-4 sentence executive summary that:
        - Starts with the business value proposition
        - Includes quantified results/achieved outcomes
        - Connects to strategic alignment
        - Ends with capability/process transformation impact

    6. **Key Objectives**: Provide 2 bullet points summarizing the project's primary objectives (max 50 words each).
    7. **Business Impacts**: Provide 2 bullet points summarizing the business impact, using key results from value realization data or project outcomes (max 60 words each).

    Each section should be clear, concise, and free of technical jargon. Use actionable language to inform future decisions. If data is missing, note it briefly and focus on available information. Ensure the tone is professional and strategically focused.

    **Input Data**:
    - Project Data: {data}
    - All Status Updates: {all_status_updates}
    - Milestone Data: {milestone_data}
    - Retro Analysis: {retro_data}
    - Value Realization Data: {value_realization_data}

    **Output Requirement**: Return the response in valid JSON format with the following structure:
    ```json
    {{
      "project_brief_description": "", // max- 50 words
      "value_realization_summary": ["", ...], // "1-2 bullet points summarizing key outcomes in max 40 words each."
      "agent_insights": ["", ...], // "3-5 bullet points summarizing balanced view (include positives also) of project health and status updates in max 30 words each."
      "key_learnings": ["", ...], // "2-3 sentences summarizing key lessons from retro or inferred from data."
      "key_objectives_and_business_impacts": ["", ""], // 2 points with max 30 words each
    }}
    ```
    Ensure JSON is valid, with special characters properly escaped. If inputs are empty or malformed, return a JSON object with brief notes on missing data and proceed with available information.
    """
    
    userPrompt = f"""
    Output in valid JSON format as per instructions.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )
    
    
       
def generateRoadmapsReviewInsights(data) -> ChatCompletion:
    systemPrompt = f"""
    You are an expert portfolio review assistant tasked with generating concise, actionable insights for future projects, tailored for C-suite executives and business stakeholders.

    Your audience prioritizes strategic alignment, financial performance, and competitive advantage. Using the provided roadmap data, create a four-part insight summary for each project, focusing on:
    1. **Business Values Insights**: 
        **Business Framework Requirements:**
        **Key Results/Outcomes**: [Quantified business metrics, ROI, efficiency gains]
        **Strategic Objectives**: [Primary business goals the project achieves]
        **Organizational Alignment**: [How it supports company strategy, digital transformation goals]
        **Business Process Impact**: [Which core processes are enhanced/transformed]
        **Business Capabilities Enabled**: [New capabilities or enhanced existing ones]
        
        Focus on:
        - Expected business outcomes and ROI projections
        - Strategic objectives to be achieved
        - Competitive advantage or market opportunities
        - Process transformation goals
        - New capabilities to be enabled
        
        Output: Create a 3-4 sentence executive summary that:
        - Starts with the business value proposition
        - Includes quantified results/expected outcomes
        - Connects to strategic alignment and competitive advantage
        - Ends with capability/process transformation impact

    2. **Scope Synthesis**: Summarize the project scope in 4 bullet points, each approximately 50 words, describing the project's key components, deliverables, and boundaries. Ensure clarity and focus on strategic objectives without technical jargon.
    3. **Key Objectives**: Provide 2 bullet points summarizing the project's primary objectives (max 50 words each), focusing on strategic goals and expected outcomes.
    4. **Business Impacts**: Provide 3-4 bullet points summarizing the project's objective, key results/expected outcomes, and alignment with organizational strategy (max 60 words each). Highlight how the project drives strategic goals, delivers measurable impact, and supports long-term organizational priorities.

    Each section should be clear, concise, and free of technical jargon. Use actionable language to inform future decisions. If data is missing, note it briefly and focus on available information. Ensure the tone is professional and strategically focused.

    **Input Data**:
    - Roadmap Data: {data}

    **Output Requirement**: Return the response in valid JSON format with the following structure:
    ```json
    {{
      "roadmap_brief_description": "", // max- 50 words
      "business_values_insights": ["", ...], // "3-4 sentences summarizing strategic alignment and impact."
      "scope_synthesis": ["", ...], // "4 bullet points, each max 40 words, summarizing project scope."
      "key_objectives_and_business_impacts": ["", ""], // 2 points with max 30 words each
    }}
    ```
    Ensure JSON is valid, with special characters properly escaped. If inputs are empty or malformed, return a JSON object with brief notes on missing data and proceed with available information.
    """
    
    userPrompt = f"""
    Output in valid JSON format as per instructions.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )

     
     