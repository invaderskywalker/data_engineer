from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import datetime
from src.trmeric_utils.constants import PROJECT_TYPES

def category_decider_prompt(project_data):
   systemPrompt = f"""
        1. You are a part of knowledge creation AI agent. 
        so it is important that projects are grouped into categories which are listed here:
        {PROJECT_TYPES}
        
        <project_data>
        {project_data}
        <project_data>
        
        2. Please try your best to classify the projects into one or multiple of these categories provided. 
        Also remember to suggest new types If you think this project belongs to the new category
        
        3. **Output**
            - Return a JSON object:
                ```json
                  {{
                     "categories": [], // can be multiple
                     "reason": ""
                  }}
                ```
   """
   
   userPrompt = f"""
      Please think carefully.
   """
   
   return ChatCompletion(
      system=systemPrompt,
      prev=[],
      user=userPrompt
   )
   

def outcome_decider_prompt(project_data, project_retro):
   systemPrompt = f"""
        You are a knowledge creation AI agent. Classify the project as "success," "good," "bad," or "failure":
         - Success: >80% milestones completed AND >80% key results achieved, with budget/timeline misses ≤20% of planned values (e.g., $60k vs. $50k = 20% miss).
         - Good: 60-80% milestones completed AND 60-80% key results achieved, with budget/timeline misses ≤30% of planned values.
         - Bad: 30-60% milestones completed AND/OR 30-60% key results achieved, OR if in 60-80% range with budget/timeline misses >50%.
         - Failure: <30% milestones completed OR <30% key results achieved, regardless of budget/timeline misses.

         Project data: <data>{project_data}</data>
         Retro data: <retro>{project_retro}</retro>

         **Instructions**:
         - Calculate explicitly FROM DATA:
           - Milestones: % completed (e.g., "2/3 = 66%"). List completed ones (e.g., "Config: Yes, Training: No") based on status/insights evidence. If ongoing, count progress unless explicitly failed.
           - Key results: % achieved (e.g., "2/3 = 66%"). Assess each goal (e.g., "95% integration: 70% met")—assume 50% success if progress noted but unconfirmed, 0% only if explicitly failed.
           - Budget/timeline misses: Calculate % over planned values (e.g., "$60k spent vs. $50k planned = 20% miss" for budget, "11 weeks vs. 10 weeks = 10% miss" for timeline). Apply for "success," "good," or "bad" ranges to check thresholds.
         - Note causes (e.g., "API errors cut integration").
         - Include value outcomes if evident (e.g., "15% efficiency achieved").
         - Ignore status (e.g., "at risk") unless it directly blocks milestones/results.
         
         **Output**:
         - Return a JSON object:
             ```json
             {{
               "outcome": "",
               "detailed_analysis": "X% milestones (list), Y% key results (details), budget miss Z%, timeline miss W% (if applicable), causes..."
             }}
             ```
   """
   
   userPrompt = f"""
      Analyse Deeply
   """
   
   return ChatCompletion(
      system=systemPrompt,
      prev=[],
      user=userPrompt
   )


def knowledge_insight_creator_prompt(project_detailed_data, project_type, project_retro, project_outcome, outcome_details, existing_insight=None):
   systemPrompt = f"""
      You are the knowledge creation AI agent tasked with generating detailed insights 
      about project outcomes. 
      Your goal is to analyze the provided project data and 
      create a comprehensive insight explaining what combination 
      of factors (milestones, team, statuses, KPIs, etc.) led to the 
      project type: {project_type} 's outcome: {project_outcome}.
      
      If an existing insight is provided, refine and update it with the new data; 
      otherwise, create a new insight from scratch. 
      Don't include project names in the final insight response.

      ### Instructions:
      1. **Data Provided**:
         - **Project Detailed Data**: Includes statuses, milestones,  team data, and other project related details:
            <project_data>
            {project_detailed_data}
            <project_data>
            
         - Project type is the element on which the knowledge layer is being created upon. 
            <project_type>
            {project_type}
            <project_type>

         - **Project Retro Data**: Retrospective feedback:
            <project_retro>
            {project_retro}
            <project_retro>
            
         - **Project Outcome**: Classified as "success", "failure", or "mixed":
            <project_outcome>
            {project_outcome}
            <project_outcome>
            
            and <outcome_details> {""} <outcome_details>
            

         - **Existing Insight** (if any): Previous insight for this project type and outcome:
         <existing_insight>
         {existing_insight if existing_insight else 'None'}
         <existing_insight>

      2. **Analysis**:
         - Focus on {project_type}-specific factors (e.g., 
            cloud infra for cloud_migration, 
            ERP integrations for erp_implementation
         ) etc.
         - Quantify impacts (e.g., "60% scope at risk") and causes (e.g., "network instability").
            - Include value outcomes (e.g., "scaled users by 30%").
            - Quantify performance of team members (e.g. count, roles, were these roles enough etc), 
            - Quantify performace by successful milestone completion.
            - Quantify status updates - for <project_outcome> outcome of project (e.g. 4/6 status updates were delayedd due to x and y)
         - Refine <existing_insight> if provided; otherwise, create new.
         - NEVER mention project names.
         - Return plain text insight, concise and reusable.
   """

   userPrompt = """
      Synthesize deeply.
   """

   return ChatCompletion(
      system=systemPrompt,
      prev=[],
      user=userPrompt
   )
   
   