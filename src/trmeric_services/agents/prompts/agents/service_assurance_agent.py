
from copy import deepcopy
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import datetime
import json


def update_status_data_creation_prompt(data):
    prompt = f"""
        Hello, gpt
        
        Your role is simple you just have to understand the data given in : {data}
        See this data given to you is project id, project name and project update comment that user commented.
        sicne user wants to make update status in that project
        
        
        Important thing: 
        
        You have to ensure that you do not pass placeholder data or garbage data which was not requested by user.
        
        now your work is to output a creatain json:
        
        
        Info: Our org maintains these projects status in 
        three types:
            scope, schedule, spend
        and three values are there
        like 
        compromised - high risk
        at_risk - mild risk
        on_track - no risk
        
        Structure of outoput format:
        ```json
        {{
            "status_updates":
            [
                {{
                    "project_id": "",
                    "project_title": "",
                    "update_types": [],// one or more out of scope, schedule, spend
                    "update_values": [], // one or more of compromised , at_risk , on_track
                    "comments": [],// coments for each update_types, this should be same number of items as in update_types. if user has given only one comment but it points to more than one update type. create 
                }},...
            ]
        }}
        ```
        
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def create_risk_prompt(risk_info):
    currentDate = datetime.datetime.now().date().isoformat()
    prompt = f"""
        Your role is simple you just have to understand the risk data given in : <risk_info> {risk_info} <risk_info>
        and you have to create/format the risk data in the below output format for our api to consume it.
        
        
        You have to ensure that you do not pass placeholder data or garbage data which was not requested by user.
        
        Todays date: {currentDate}
        now your work is to output this json:
        
        Structure of output format:
        ```json
        [
            {{
                "project_id": "",
                "project_name": "",
                "description": "",// details of risk,
                "impact": "", // impact area - like 
                "mitigation": "", // mitigation strategy
                "priority": int - 1/2/3, // int, 1 - "High", 2- "Medium", 3- "Low"
                "due_date": "", if the user mentions a due date format - YYYY-MM-DD, if user has not mentioned any date then default to 1 week from now
                "valid_risk_data": 'true' or 'false', // this is important to check: if the risk description is valid and no placeholder then mark this as true otherwise false
            }},...
        ]
        ```
    
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def create_action_prompt(action_info, user_list):
    currentDate = datetime.datetime.now().date().isoformat()
    prompt = f"""
        Your role is simple you just have to understand the action data given in : <action_info> {action_info} <action_info>
        and you have to create/format the action data in the below output format for our api to consume it.
        
        You have to ensure that you do not pass placeholder data or garbage data which was not requested by user.
        
        Todays date: {currentDate}
        now your work is to output this json:
        
        Structure of output format:
        ```json
        [
            {{
                "head_text": "", // header for this action
                "details_text": "", // details for this action
                "priority": "", //  "High","Medium", "Low"
                "colaborators_info": [
                    {{
                        "id": int,
                        "username": string,
                    }}
                ], // if user wants to add collaborator - list of collaborators avaialble for this- {user_list}
                "tag": "", // one of "Delay", "Risk", "Cost", if the user has not mentioned infer from data
                "due_date": "", if the user mentions a due date format - YYYY-MM-DD, if user has not mentioned any date then default to 1 week from now
                "valid_action_data": 'true' or 'false', // this is important to check: if the action description is valid and no placeholder then mark this as true otherwise false
            }},...
        ]
        ```
    
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def create_combined_update_prompt(project_info=None, user_update_statement='', conv=''):
    currentDate = datetime.datetime.now().date().isoformat()

    systemPrompt = f"""
        Your role is simple: Understand the data given and format it properly.
        
        The provided information consists of:
        - Project ID & Project Name (same for both status and risk updates)
        - Status Update Details (if available)
        - Risk Update Details (if available)

        **Status Updates:**
        - Ensure only valid user-requested data is included.
        - Our org maintains project statuses in three types: **scope, schedule, spend**.
        - Status values: **compromised (high risk), at_risk (mild risk), on_track (no risk).**
        - From the user comment you need to figure out. what are the areas out of scope, schedule and spend which can get affected.

        **Risk Updates:**
        - Ensure valid data, no placeholders.
        - Risk attributes include **description, impact, mitigation, priority (1-High, 2-Medium, 3-Low).**
        - Due date format: **YYYY-MM-DD**, defaulting to **one week from today ({currentDate})** if not provided.


        Now, Since you are powerful agent and a part of service assurance agent. 
        You need to understand the user statement properly and split into these areas descrived.
        Also, you also need to cooordinate with frontend for review.
        
       
        We have to make update for this project - {project_info}
        ----------
        User Update Statement: {user_update_statement}
        ---------
        
        
        Todays date: {currentDate}
        -----------
        
        ## From this current date. 
        # you need to figure out propelry what should be the 
        # new_target_date for each of the milestone
        # because each milestone could represnt the timeline of project exectuion
        # and you have to understand proeprly and think on it. and then create responses
        
        **Expected JSON Structure:**
        ```json
        {{
            "project_id": "",
            "project_name": "",
            "your_thought": '', // thought regarding each update, also tell what you are thinking about: user_satisfied_for_update
            "status_updates": [
                {{
                    "update_type": "",  // one of scope, schedule, spend
                    "update_value": "",  // one  of compromised, at_risk, on_track
                    "comment": ""  // update status comment
                }},...
            ],
            "risk_updates": [
                {{
                    "description": "",
                    "impact": "",
                    "mitigation": "",
                    "priority": 1,  // 1-High, 2-Medium, 3-Low
                    "due_date": "",
                }},...
            ],
            "milestone_updates": [
                {{
                    "milestone_id": "", // carefully think on the user comment. what milestone id and what milestone date to update
                    "milestone_name": "", 
                    "new_target_date": "",
                    "original_date": ""
                }}
            ],
            "user_satisfied_for_update": "", // "true" or "false", make this true only when user says that he this looks good. or he is satisfied
        }}
        ```
    """

    userPrompt = f"""
        **Ongoing Conversation** 
        <conv>
            {conv}
        <conv>
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def create_combined_update_prompt_v2(project_info=None, data=None, user_update_statement='', conv=''):
    currentDate = datetime.datetime.now().date().isoformat()
    oneWeekLater = (datetime.datetime.now().date() +
                    datetime.timedelta(days=7)).isoformat()

    systemPrompt = f"""
        Your role is to act as a proactive service assurance agent, analyzing project data and user statements to generate accurate updates for project status, risks, and milestones. Your goal is to understand the context, infer potential issues (especially delays in milestones), and format the output in a structured JSON format. Ensure the full user statement is preserved in relevant comments unless explicitly irrelevant.

        **Provided Information**:
        - Project ID & Project Name: Shared across status, risk, and milestone updates.
        - Status Update Details: Related to scope, schedule, spend (if provided).
        - Risk Update Details: Include description, impact, mitigation, priority, due date, and status (if provided).
        - Milestone Details: Include milestone ID, name, original target date, actual date, and status (if provided).
        - User Update Statement: A comment or request from the user describing changes or issues.
        - Current Date: {currentDate}

        **Status Updates**:
        - Valid areas: **scope**, **schedule**, **spend**.
        - Status values: **compromised** (high risk), **at_risk** (mild risk), **on_track** (no risk).
        - Parse the user statement to identify affected areas using keywords like "behind," "delayed," "over budget," or "scope creep."
        - Include the sensible full `user_update_statement` in the `comment` field unless it’s unrelated (e.g., "looks good"). If the statement is long (>200 characters), prepend a concise summary but include the full text.
        - If project end date < current data then for sure schedule status of the project is compromised and comment becomes compromised due to end date passed.

        **Risk Updates**:
        - Attributes: **description**, **impact**, **mitigation**, **priority** (1-High, 2-Medium, 3-Low), **due_date** (YYYY-MM-DD, default to {oneWeekLater} if not specified), **status_value** (1: Active, 2: Resolved, 3: Monitoring, 4: Escalated, 5: Mitigated, 6: Closed).
        - Infer hidden risks from the user statement or data (e.g., resource shortages, technical issues) that could affect milestones.

        **Milestone Updates**:
        - Attributes: **milestone_id**, **milestone_name**, **new_target_date**, **original_date**, **comments**, **actual_date**, **status_value** (1: not started, 2: in progress, 3: completed).
        - Only include milestones where:
          - The `new_target_date` differs from `original_date` (for status_value 1 or 2 only), OR
          - The `status_value` differs from the current status in the data.
        - For "not started" (status_value: 1) or "in progress" (status_value: 2) milestones:
          - Proactively assess delays by checking the user statement for delays, resource issues, or dependencies (e.g., "we’re behind on planning").
          - Cross-reference with **schedule** or **spend** status (e.g., if schedule is "at_risk" or "compromised," assume potential delays).
          - Evaluate risks that could impact the milestone (e.g., a "resource shortage" risk).
          - If a delay is inferred, propose a `new_target_date` by adding a reasonable delay (e.g., 1-4 weeks) based on severity, 
            and also explain in `comments`, explicitly stating the proposed target date (like suggested target date: <date> due to <reason>).
        - For "completed" (status_value: 3) milestones:
          - Do NOT include `new_target_date` in the update.
          - Use the `actual_date` from the input `data` or `user_update_statement` if provided. Only set `actual_date` to {currentDate} if the user explicitly indicates completion today and no prior `actual_date` exists.
          - Include the full `user_update_statement` in `comments` if it describes the completion.
        - For new milestones, use `milestone_id: "0"`, but only create them if the user explicitly requests a new milestone.
        - Do not change `milestone_name` unless explicitly requested.
        - Include the full `user_update_statement` in `comments` if relevant to the milestone update, appending it to any explanation.

        **Chain of Thought**:
        To determine updates, follow these steps:
        1. **Parse User Statement**: Identify keywords or phrases indicating delays, issues, completions, or changes (e.g., "delayed," "completed," "behind"). Map these to milestones, status areas, or risks.
        2. **Analyze Status Updates**: Assign `update_type` and `update_value` based on the user statement. Include the full statement in `comment`, with a summary if needed.
        3. **Analyze Milestones**: For each milestone:
           - Check `status_value` and `original_date` against {currentDate}.
           - If "not started" (status_value: 1) and `original_date` is future, assess delays from user statement, risks, or status (e.g., "schedule: at_risk").
           - If "not started" and `original_date` is past, mark as delayed unless user confirms it’s on track.
           - If "in progress" (status_value: 2), check for delays or completion signals.
           - If "completed" (status_value: 3):
             - Exclude `new_target_date`.
             - Use existing `actual_date` from data or user statement. Set to {currentDate} only if user confirms completion today and no `actual_date` exists.
             - Include full user statement in `comments` if it describes completion.
           - If a delay is inferred for status_value 1 or 2, propose a `new_target_date` and explain in `comments`.
           - Include full `user_update_statement` in `comments` if relevant, with an explanation (e.g., "User reported delay: [full statement]").
        4. **Cross-Reference Risks and Status**: Link risks or status updates to milestone delays or completions, referencing them in `comments`.
        5. **Validate Dates**: Ensure all dates are in YYYY-MM-DD format. `new_target_date` must be future or current for status_value 1 or 2. `actual_date` for status_value 3 must not be future.
        6. **Determine User Satisfaction**: Set `user_satisfied_for_update` to `true` only if user says "this looks good," "I’m satisfied," or similar.

        **Examples**:
        - **User Statement**: "We’re behind on the design phase due to resource issues, and the workshop milestone might be delayed."
          - **Status Update**: `update_type: schedule`, `update_value: at_risk`, `comment: "We’re behind on the design phase due to resource issues."`
          - **Milestone Update**: For "workshop" milestone (status_value: 1), set `new_target_date` (e.g., 2 weeks later), `comments: "Delayed due to resource issues. User statement: We’re behind on the design phase due to resource issues."`
          - **Risk Update**: `description: "Resource shortage affecting design phase"`, `priority: 1`, `due_date: {oneWeekLater}`, `status_value: 1`.
        - **User Statement**: "The testing phase is complete as of yesterday."
          - **Milestone Update**: For "testing" milestone, set `status_value: 3`, `actual_date: "2025-05-12"`, `comments: "Completed as per user. User statement: The testing phase is complete as of yesterday."`, exclude `new_target_date`.
          - **User Satisfaction**: `user_satisfied_for_update: "true"`.
        - **User Statement**: "Everything looks good, no issues."
          - **Milestone Update**: No changes unless data suggests otherwise.
          - **User Satisfaction**: `user_satisfied_for_update: "true"`.
          
        
        - If project end date is greater than current data then for sure schedule status of the project is compromised.

        **Frontend Coordination**:
        - Ensure `comments` and `your_thought` are clear, including the full user statement where relevant (e.g., "User reported completion: [full statement]"). Avoid vague terms.
        - For completed milestones, clearly state in `your_thought` why `new_target_date` was omitted.

        **Expected JSON Structure**:
        ```json
        {{
            "project_id": "",
            "project_name": "",
            "your_thought": "", // Explain reasoning, including how user statement was used and why new_target_date was omitted for completed milestones
            "status_updates": [
                {{
                    "update_type": "", // scope, schedule, spend
                    "update_value": "", // compromised, at_risk, on_track
                    "comment": "" // Include full user statement if relevant
                }}
            ],
            "risk_updates": [
                {{
                    "risk_id": "",
                    "description": "",
                    "impact": "",
                    "mitigation": "",
                    "priority": 1, // 1-High, 2-Medium, 3-Low
                    "due_date": "",
                    "status_value": 1 // 1: Active, 2: Resolved, 3: Monitoring, 4: Escalated, 5: Mitigated, 6: Closed
                }}
            ],
            "milestone_updates": [
                {{
                    "milestone_id": "", // Use "0" for new milestones
                    "milestone_name": "",
                    "new_target_date": "", // Omit for status_value: 3
                    "original_date": "",
                    "comments": "", // Include full user statement if relevant
                    "actual_date": "",
                    "status_value": 1 // 1: not started, 2: in progress, 3: completed
                }}
            ],
            "user_satisfied_for_update": "" // "true" or "false"
        }}
        ```

        **Input Data**:
        <detailed_project_data>
        {project_info}
        {data}
        <detailed_project_data>
        User Update Statement: {user_update_statement}
        Current Date: {currentDate}
    """

    userPrompt = f"""
        **Ongoing Conversation**
        <conv>
            {conv}
        <conv>
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def create_combined_update_prompt_v3(user_update_statement):
    currentDate = datetime.datetime.now().date().isoformat()
    oneWeekLater = (datetime.datetime.now().date() +
                    datetime.timedelta(days=7)).isoformat()

    systemPrompt = f"""
        Your role is to act as a data formatter.

        **Provided Information**:
        - User Update Statement: A detailed description of status, risk, and milestones update that the user wants to make.
        - Current Date: {currentDate}
        
        
        **Job**:
            You have to make sure that you look at the input
            and format the data properly.
            So, action can be taken on it. like actual  updates can be made.
        
        

        **Status Updates**:
        - Valid areas: **scope**, **schedule**, **spend**.
        - Status values: **compromised** (high risk), **at_risk** (mild risk), **on_track** (no risk).
        - Parse the user statement to identify affected areas using keywords like "behind," "delayed," "over budget," or "scope creep."
        - Include the sensible full `user_update_statement` in the `comment` field unless it’s unrelated (e.g., "looks good"). If the statement is long (>200 characters), prepend a concise summary but include the full text.

        **Risk Updates**:
        - Attributes: **description**, **impact**, **mitigation**, **priority** (1-High, 2-Medium, 3-Low), **due_date** (YYYY-MM-DD, default to {oneWeekLater} if not specified), **status_value** (1: Active, 2: Resolved, 3: Monitoring, 4: Escalated, 5: Mitigated, 6: Closed).
        - Infer hidden risks from the user statement or data (e.g., resource shortages, technical issues) that could affect milestones.

        **Milestone Updates**:
        - Attributes: **milestone_id**, **milestone_name**, **new_target_date**, **original_date**, **comments**, **actual_date**, **status_value** (1: not started, 2: in progress, 3: completed).
        - Only include milestones where:
          - The `new_target_date` differs from `original_date` (for status_value 1 or 2 only), OR
          - The `status_value` differs from the current status in the data.
        - For "not started" (status_value: 1) or "in progress" (status_value: 2) milestones:
          - Proactively assess delays by checking the user statement for delays, resource issues, or dependencies (e.g., "we’re behind on planning").
          - Cross-reference with **schedule** or **spend** status (e.g., if schedule is "at_risk" or "compromised," assume potential delays).
          - Evaluate risks that could impact the milestone (e.g., a "resource shortage" risk).
          - If a delay is inferred, propose a `new_target_date` by adding a reasonable delay (e.g., 1-4 weeks) based on severity, and explain in `comments`.
        - For "completed" (status_value: 3) milestones:
          - Do NOT include `new_target_date` in the update.
          - Use the `actual_date` from the input `data` or `user_update_statement` if provided. Only set `actual_date` to {currentDate} if the user explicitly indicates completion today and no prior `actual_date` exists.
          - Include the full `user_update_statement` in `comments` if it describes the completion.
        - For new milestones, use `milestone_id: "0"`, but only create them if the user explicitly requests a new milestone.
        - Do not change `milestone_name` unless explicitly requested.
        - Include the full `user_update_statement` in `comments` if relevant to the milestone update, appending it to any explanation.


        
        **Expected JSON Structure**:
        ```json
        {{
            "project_id": "",
            "project_name": "",
            "your_thought": "", // Explain reasoning, including how user statement was used and why new_target_date was omitted for completed milestones
            "status_updates": [
                {{
                    "update_type": "", // scope, schedule, spend
                    "update_value": "", // compromised, at_risk, on_track
                    "comment": "" // Include full user statement if relevant
                }}
            ],
            "risk_updates": [
                {{
                    "risk_id": "",
                    "description": "",
                    "impact": "",
                    "mitigation": "",
                    "priority": 1, // 1-High, 2-Medium, 3-Low
                    "due_date": "",
                    "status_value": 1 // 1: Active, 2: Resolved, 3: Monitoring, 4: Escalated, 5: Mitigated, 6: Closed
                }}
            ],
            "milestone_updates": [
                {{
                    "milestone_id": "", // Use "0" for new milestones
                    "milestone_name": "",
                    "new_target_date": "", // Omit for status_value: 3
                    "original_date": "",
                    "comments": "", // Include full user statement if relevant
                    "actual_date": "",
                    "status_value": 1 // 1: not started, 2: in progress, 3: completed
                }}
            ],
        }}
        ```

        **Input Data**:
        User Update Statement: {user_update_statement}
        Current Date: {currentDate}
    """

    userPrompt = f"""
        Please output proper JSON.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )



def create_report_prompt(project_info=None, alreadyGeneratedInsightData=None):
    currentDate = datetime.datetime.now().date().isoformat()

    systemPrompt = f"""
        Your role is simple: Understand the data given and format it properly.
        
        The provided information consists of:
        - Project details including title, start and end dates, budget, and project manager.
        - Status Updates covering scope, delivery, and spend.
        - Summary of project progress, key insights, accomplishments, milestones, and next steps.

        **Current Project Status**
            - Status Summary
            - Tango ASsure Project Insight
            - Key Accomplishments
        

        **Key Milestones:**
            - Identify key milestones.
        
        ** Issues/ Challenges **
            - Identify from the data the issues and challenges.
            
        ** Key Action/ Next Steps **
            - Identify Key Actions/ Next Steps
        
        Now, since you are a powerful agent and part of the service assurance team,
        you need to understand the user statement properly and structure the update accordingly.
        Also, coordinate with the frontend for review.

        ---------
        Today's date: {currentDate}
        -----------
        Project Information: {project_info}
        -----------
        From this project data already some insight is created. Just have a look at it to create a good insight.
        {alreadyGeneratedInsightData}
        -----------


        **Expected JSON Structure:**
        ```json
        {{
            "id": "",
            "title": "",
            "projectDetails": {{
                "startDate": "",
                "endDate": "",
                "budget": 0,
                "projectManager": ""
            }},
            "currentProjectStatus": {{
                "statusSummary": "",
                "tangoAssureProjectInsight": "",
                "keyAccomplishments": [], // see if you can find some accomplishments
            }},
            "keyMilestones": [
                {{ "milestone": "", "dueDate": "" }}
            ],
            "keyActionsNextSteps": [],
            "issues_challenges": [
                {{
                    "type": "",
                    "description": "",
                    "comment_or_mitigation": "",
                    "due_date": "", // try to estimate a time according to current date: {currentDate}
                }}
            ],
            "reportDate": "{currentDate}"
        }}
        ```
    """

    userPrompt = """
        Please generate a detailed project update report as per the format mentioned.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def create_high_level_analysis_prompt(data, user_query):
    currentDate = datetime.datetime.now().date().isoformat()

    systemPrompt = f"""
        You are a professional service assurance agent with expertise in project management and technical troubleshooting. Your role is serious, proactive, and hands-on. Your task is to perform a thorough, detailed analysis of the project data provided below and respond to the user's query with a structured, insightful, and actionable response. Follow this enhanced process to ensure depth and specificity:

        1. **Data Parsing and Contextualization**
           - Extract critical details from the project data, including objectives, timelines, milestones, current status, tech stack, and Tango integration (if available).
           - Use the current date ({currentDate}) to contextualize timelines and assess delays or progress.
           - Note specific data points: milestone target dates, actual vs. planned spend, status updates, and any technical issues mentioned.

        2. **Query Analysis**
           - Identify the query type (e.g., troubleshooting, status, risk, performance, predictive).
           - Pinpoint the exact information or actions requested (e.g., diagnosing a specific issue, providing resolution steps).
           - Infer the user’s intent: Are they seeking root causes, immediate fixes, or long-term solutions?

        3. **Deep Analysis**
           - For troubleshooting queries:
             - Diagnose root causes of identified issues using project data (e.g., tech stack, milestone delays, status reports).
             - Assess technical aspects (e.g., website routing, SEO tool outputs) and their impact on objectives.
             - Cross-reference statuses (scope, delivery, spend) to identify contributing factors.
           - For other query types (status, risk, etc.), adapt analysis as follows:
             - Status: Evaluate progress with specific metrics (e.g., % completion, days delayed).
             - Risks: Quantify likelihood and impact, linking to project data.
             - Performance: Analyze resource or tool efficiency.
             - Predictive: Forecast based on trends.
           - Highlight data gaps or inconsistencies requiring clarification.

        4. **Insight Generation**
           - Summarize findings with precision, focusing on the most impactful issues.
           - Provide actionable recommendations:
             - For troubleshooting: Offer step-by-step resolution steps, leveraging the tech stack or available resources.
             - For other queries: Suggest specific, data-driven actions to improve outcomes.
           - Anticipate potential challenges in implementing recommendations and propose mitigations.

        5. **Response Formulation**
           - Structure your response with:
             - **Introduction**: Briefly state the purpose and scope of the analysis.
             - **Detailed Analysis**: Present findings with specific data points and logical reasoning.
             - **Action Plan**: List numbered, actionable steps or recommendations in a clear, concise format.
             - **Conclusion**: Recap key points and emphasize next steps.
           - Use formal, confident language and clear formatting (e.g., bullet points, numbered lists, tables).
           - Acknowledge limitations (e.g., missing Tango integration data) and suggest how to address them.

        6. **Review**
           - Ensure the response is thorough, directly addresses the query, and avoids generic or vague statements.
           - Verify technical accuracy, logical flow, and alignment with the user’s intent.
           - Keep the tone proactive and solution-oriented, reflecting your expertise.

        **Project Data:**
        <data>
        {data}
        </data>
    """

    userPrompt = f"""
        {user_query}
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def troubleshoot_service_assurnace_prompt(project_data, data, user_query):
    currentDate = datetime.datetime.now().date().isoformat()

    systemPrompt = f"""
        You are a professional service assurance agent who helps in trouble shooting
        with expertise in project management and technical troubleshooting. 
        Your role is serious, proactive, and hands-on. 
        Your task is to perform a thorough, detailed analysis of the project data provided below and respond to the user's query with a structured, insightful, and actionable response. Follow this enhanced process to ensure depth and specificity:
        
        Do a very deep analysis on the user query and answer.
        <project_data>
        {project_data}
        <project_data>
        
        <additional_analysis_data>
        {data}
        <additional_analysis_data>
    """

    userPrompt = f"""
        {user_query}
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def calculate_date_metrics(current_date_str, target_date_str, milestone_name, status, comments, project_end_date_str, actual_completion_date=None):
    log = []
    result = {
        'days_overdue': None,
        'days_remaining': None,
        'is_overdue': False,
        'is_completed': False,
        'comment_conflict': False,
        'is_after_end_date': False,
        'status_discrepancy': False,
        'error': None
    }

    # Parse current date (yyyy-mm-dd)
    try:
        current_date = datetime.datetime.strptime(current_date_str, '%Y-%m-%d').date()
        log.append(f"Current date parsed: {current_date_str} -> {current_date}")
    except ValueError:
        result['error'] = f"Invalid current_date format: {current_date_str}"
        log.append(result['error'])
        return result, log

    # Check completion status
    if isinstance(status, str) and status.lower() in ['completed', 'done']:
        if not actual_completion_date:
            result['error'] = f"Status '{status}' with missing actual_completion_date for '{milestone_name}'"
            # result['status_discrepancy'] = True
            log.append(result['error'])
            result['is_completed'] = True
        else:
            try:
                completion_date = datetime.datetime.strptime(actual_completion_date, '%Y-%m-%d').date()
                if completion_date > current_date:
                    result['error'] = f"Milestone '{milestone_name}' has future actual_completion_date ({completion_date}) but status is {status}"
                    result['status_discrepancy'] = True
                    log.append(result['error'])
                else:
                    result['is_completed'] = True
                    log.append(f"Milestone '{milestone_name}' is completed (status: {status}, completion_date: {completion_date})")
            except ValueError:
                result['error'] = f"Invalid actual_completion_date format for '{milestone_name}': {actual_completion_date}"
                result['status_discrepancy'] = True
                log.append(result['error'])
    else:
        result['is_completed'] = False

    # Check for missing target date (skip if completed)
    if not target_date_str and not result['is_completed']:
        result['error'] = f"Missing target_date for '{milestone_name}'"
        log.append(result['error'])
        return result, log

    # Parse target date (yyyy-mm-dd or mm-dd-yyyy)
    if target_date_str:
        try:
            target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
            log.append(f"Milestone '{milestone_name}' target_date parsed: {target_date_str} -> {target_date}")
        except ValueError:
            try:
                target_date = datetime.datetime.strptime(target_date_str, '%m-%d-%Y').date()
                log.append(f"Milestone '{milestone_name}' target_date parsed (US format): {target_date_str} -> {target_date}")
            except ValueError:
                result['error'] = f"Invalid target_date format for '{milestone_name}': {target_date_str}"
                log.append(result['error'])
                return result, log

    # Parse project end date (yyyy-mm-dd)
    # try:
    #     project_end_date = datetime.datetime.strptime(project_end_date_str, '%Y-%m-%d').date()
    #     # log.append(f"Project end date parsed: {project_end_date_str} -> {project_end_date}")
    # except ValueError:
    #     result['error'] = f"Invalid project_end_date format: {project_end_date_str}"
    #     log.append(result['error'])

    # Calculate days if not completed and no critical errors
    if not result['is_completed'] and not result['error'] and target_date_str:
        delta = target_date - current_date
        days = delta.days
        if days < 0:
            result['days_overdue'] = abs(days)
            result['is_overdue'] = True
            log.append(f"Milestone '{milestone_name}' is overdue by {result['days_overdue']} days (target: {target_date}, current: {current_date})")
        else:
            result['days_remaining'] = days
            log.append(f"Milestone '{milestone_name}' has {result['days_remaining']} days remaining (target: {target_date}, current: {current_date})")

        # Check comment conflict
        comments_str = comments if isinstance(comments, str) else ''
        if comments_str and 'overdue' in comments_str.lower() and not result['is_overdue']:
            result['comment_conflict'] = True
            log.append(f"Milestone '{milestone_name}' labeled overdue in comments but has {days} days remaining")
        elif comments is None:
            log.append(f"Milestone '{milestone_name}' has no comments provided")

        # Check planning discrepancy
        if 'project_end_date' in locals() and target_date > project_end_date:
            result['is_after_end_date'] = True
            log.append(f"Milestone '{milestone_name}' target_date ({target_date}) is after project end date ({project_end_date})")

    return result, log


def create_review_project(project_info, previous_week_status_updates, p2p_week_status_updates, milestone_data, org_info_string, jira_data=None, smartsheet_data=None, integration_data=None):
    current_date = datetime.datetime.now().date().isoformat()

    # Preprocess date calculations
    milestone_data = deepcopy(milestone_data)  # Avoid modifying input
    date_calc_log = []
    project_end_date = project_info.get('end_date', '')
    project_start_date = project_info.get('start_date', '')

    # Calculate timeline elapsed and days to end/overrun
    try:
        project_start_date_parsed = datetime.datetime.strptime(project_start_date, '%Y-%m-%d').date()
        project_end_date_parsed = datetime.datetime.strptime(project_end_date, '%Y-%m-%d').date()
        current_date_parsed = datetime.datetime.strptime(current_date, '%Y-%m-%d').date()
        total_project_days = (project_end_date_parsed - project_start_date_parsed).days
        elapsed_days = (current_date_parsed - project_start_date_parsed).days
        timeline_elapsed = (elapsed_days / total_project_days) * 100 if total_project_days > 0 else 0
        if project_end_date_parsed > current_date_parsed:
            days_to_end = (project_end_date_parsed - current_date_parsed).days
            date_calc_log.append(
                f"Project end date ({project_end_date}) is {days_to_end} days after current date ({current_date}); timeline {timeline_elapsed:.2f}% elapsed ({elapsed_days}/{total_project_days} days)")
        else:
            days_overrun = (current_date_parsed - project_end_date_parsed).days
            date_calc_log.append(
                f"Project end date ({project_end_date}) passed by {days_overrun} days before current date ({current_date}); timeline {timeline_elapsed:.2f}% elapsed")
    except ValueError:
        date_calc_log.append(f"Invalid date format: start_date={project_start_date}, end_date={project_end_date}")

    for milestone in milestone_data.get('schedule_milestones', []):
        result, log = calculate_date_metrics(
            current_date_str=current_date,
            target_date_str=milestone.get('target_date', ''),
            milestone_name=milestone.get('milestone_name', 'Unknown'),
            status=milestone.get('status', ''),
            comments=milestone.get('comments', ''),  # Default to empty string
            project_end_date_str=project_end_date,
            actual_completion_date=milestone.get('actual_completion_date', None)
        )
        milestone.update({
            'days_overdue': result['days_overdue'],
            'days_remaining': result['days_remaining'],
            'is_overdue': result['is_overdue'],
            'is_completed': result['is_completed'],
            'comment_conflict': result['comment_conflict'],
            'is_after_end_date': result['is_after_end_date'],
            'status_discrepancy': result['status_discrepancy'],
            'date_error': result['error']
        })
        date_calc_log.extend(log)

    system_prompt = f"""
        You are an expert project management assistant tasked with generating a concise, high-impact project review report. Your goal is to analyze project details, status updates, milestones, risks, and organizational context to produce a structured JSON output with exceptional proactivity—explicitly flagging risks of timeline or milestone failure in a detailed bullet-point format based solely on provided data.

        ### Input Data
        - **project_info**: {json.dumps(project_info)}
        - **previous_week_status_updates**: {json.dumps(previous_week_status_updates)}
        - **p2p_week_status_updates**: {json.dumps(p2p_week_status_updates)}
        - **milestone_data**: {json.dumps(milestone_data)}
        - **org_info_string**: {org_info_string}
        - **integration_data**: {integration_data}
        - **current_date**: {current_date}
        - **log_all_date_calculations**: {json.dumps(date_calc_log)}

        ### Date Metrics
        The `milestone_data.schedule_milestones` includes precomputed date metrics:
        - `days_overdue`: Number of days past `target_date` if `is_overdue` is True.
        - `days_remaining`: Number of days until `target_date` if `is_overdue` is False and not completed.
        - `is_overdue`: True if `target_date < current_date` and not completed.
        - `is_completed`: True if `status` is 'completed' or 'done' and `actual_completion_date` is valid.
        - `comment_conflict`: True if comments contain 'overdue' but `is_overdue` is False.
        - `is_after_end_date`: True if `target_date` is after `project_info.end_date`.
        - `status_discrepancy`: True if `status` is 'completed' but `actual_completion_date` is missing or invalid.
        - `date_error`: Error message if `target_date`, `actual_completion_date`, or status is invalid.

        Use these metrics exclusively for `ai_insights` and `project_status_summary`. Do not claim 'overdue' unless `is_overdue` is True. For 'overdue' in comments, rely on `comment_conflict`.

        ### Sections
        1. **project_status_summary**: A 2-3 sentence summary of the project’s overall status (On Track, At Risk, Compromised), derived from milestone progress, status updates, risks, and comparison to project end date. Include precise metrics (e.g., '% milestones incomplete', 'X/Y milestones with status discrepancies', '% timeline elapsed or days overrun'). Validate `is_completed` against `actual_completion_date` (ignore `status: "completed"` if `actual_completion_date` is null or invalid). If `current_date > project_end_date`, report days overrun and lean toward Compromised status unless mitigated. Reflect `previous_week_status_updates` and `p2p_week_status_updates` for non-date risks. Explicitly state 'no overdue milestones' if none have `is_overdue: True`. Calculate timeline elapsed as `(current_date - project_start_date) / (project_end_date - project_start_date)`; if overrun, report days past end date.

        2. **project_overview**: A 2-sentence summary of the project, including title, purpose, and scope (from project_info), tailored to org goals (org_info_string).

        3. **key_objectives**: A bullet-point list of objectives parsed directly from `project_info.objectives`. Split into concise points if necessary, avoiding redundancy or summarization. If empty, use `project_info.key_results` as fallback.

        4. **status_updates**: Compare Scope, Schedule, Spend between `project_info.latest_project_status` (last week) and `p2p_week_status_updates` (prior week):
           - 'trend': 'up' (improved), 'down' (worsened), 'neutral' (stable/no data).
           - Trend logic: On Track > At Risk > Compromised (up = better status, down = worse status, neutral = no change or insufficient data).
           - If `p2p_week_status_updates` is empty, evaluate `previous_week_status_updates`:
             - Count statuses for each type (Scope, Schedule, Spend).
             - If majority (50% or more) are 'On Track', set trend to 'neutral'.
             - If any are 'At Risk' or 'Compromised' and latest status is better (e.g., 'green' or 'On Track'), set trend to 'up'.
             - If any are 'At Risk' or 'Compromised' and latest status is same or worse, set trend to 'down'.
           - If no prior data exists for a category, set trend to 'neutral'.
           - Use `project_info.latest_project_status` (e.g., 'green' = On Track, 'yellow' = At Risk, 'red' = Compromised) for current state.

        5. **recent_achievements**: A list of 2-3 recent accomplishments derived from:
           - **milestone_data**: Milestones where `is_completed` is True and `actual_completion_date` is valid.
           - **previous_week_status_updates**: Comments containing 'on track,' 'completed,' 'achieved,' or specific milestone references (e.g., 'Testing completed').
           - **project_info.key_accomplishments**: Non-null key_accomplishments (list or string split into items).
           - **risk_table**: Risks with status 'Mitigated' or 'Closed' from `project_info.risks_data`.
           - Combine up to 2-3, prioritizing completed milestones with valid `actual_completion_date`, then status comments with specific achievements. Exclude vague comments (e.g., 'scope is well-defined') unless they indicate completion.
           - If none, return: ['No recent milestones, accomplishments, or mitigated risks reported.']

        6. **ai_insights**: A list of 8-10 distinct bullet-point strings (100-120 words each), delivering proactive, timeline-focused analysis:
         INSIGHT SEQUENCING (MANDATORY ORDER):

            Generate ai_insights in the following strict order. Do not change the sequence.

            1. **Overall Project Status Insight**
            - Summarize project health using **days overrun**, **% timeline elapsed**, and **% milestones overdue**.

            2. **Critical Path Analysis**
            - Start the insight with the bold heading: **Critical Path Analysis**.
            - Identify the critical path strictly using **task duration + logical dependencies**
                (predecessors and successors) from integration_data.
            - Clearly list **critical path tasks** and explain why delay in each directly impacts
                milestone or project end dates.
            - Rank critical path tasks by **downstream schedule impact**.
            - Explicitly state when tasks are critical due to **dependency logic**, not resources.
            - Include at least one metric (e.g., cumulative critical path duration, days of downstream impact).

            3. **Critical Chain & Buffer Analysis**
            - Start the insight with the bold heading: **Critical Chain & Buffer Analysis**.
            - Re-evaluate the schedule by applying **resource constraints**
                (shared roles, overloaded specialists, QA/test bottlenecks).
            - Identify tasks that become critical **only due to resource contention**.
            - Compare **Critical Path vs Critical Chain** and explain where they diverge.
            - Analyze **buffer consumption**:
                - Tasks breaching **50% / 75% / 90% buffer usage**
                - Abnormal buffer burn vs task progress
            - Flag critical chain tasks **without feeding buffers** as execution risks.
            - Include at least one buffer or resource metric.

            4. **Combined Overdue Milestones Insight**
            - Aggregate all overdue milestones and quantify downstream impact.

            5. **At-Risk Upcoming Milestones Insight**
            - Milestones with limited days remaining or high delay probability.

            6. **Integration, Resource, or External Dependency Risks**
            - Derived from integration_data or status comments.

            7. **Status Discrepancies & Planning Hygiene Issues**
            - Missing dates, invalid completion states, poor tracking discipline.

            8. **Execution Gaps / What the Team Is Missing**
            - Process, resourcing, tracking, governance, or execution gaps.

            If fewer insights are required, drop lower-priority items but preserve ordering.
            
            FORMATTING RULES (MANDATORY):

            - Use Markdown bold (** **) for:
                - Insight headers: **Critical Path Analysis**, **Critical Chain & Buffer Analysis**
                - Critical task or milestone names
                - Key metrics (days overdue, % timeline elapsed, buffer thresholds)
            - Do NOT bold entire paragraphs.
            - Use bold only for executive scannability.




        7. **next_steps**: 3 actionable steps derived from ai_insights, with due dates from {current_date}:
           - Focus on project-specific actions tied to active risks or objectives.
           - Prioritize actions addressing planning issues, status discrepancies, overdue project end date, or imminent milestones (within 10 days).
           - Include one step to validate milestones with `status_discrepancy: True` if discrepancies exist.
           - Include one step to address non-milestone risks (e.g., data access delays) if flagged in status updates.
           - Specify roles (e.g., project manager, technical lead) and link to milestones or key_results where possible.
           - Do not mention external tools unless supported by integration_data.
           - If no insights, provide a generic step (e.g., 'Review milestones by mm-dd-yyyy').
           - Format due dates as ISO (dd-mm-yyyy), set 3-5 days for imminent milestones (within 10 days) or 7-14 days for others, based on urgency.
           - Ensure steps are distinct and address unique issues.

        ### Instructions
        - Use precomputed `milestone_data` metrics exclusively for all date-related analysis.
        - Do not claim 'overdue' unless `is_overdue` is True; use `comment_conflict` for comment discrepancies.
        - Base insights on provided data; prioritize `milestone_data` for timeline analysis.
        - Compare `current_date` to `project_end_date` and milestone metrics to flag issues.
        - Quantify risks (e.g., % likelihood, days delayed, % timeline elapsed or days overrun) in `ai_insights`.
        - Tailor insights and steps to `org_info_string` and `project_info` (objectives or key_results).
        - Ensure 8-10 `ai_insights`, covering all required categories without redundancy.
        - Use placeholders for missing inputs; avoid speculation.
        - Flag planning issues, status discrepancies, and date errors as critical, requiring insights and steps.
        - Ensure `recent_achievements` includes only specific status comments with 'on track,' 'completed,' 'achieved,' or milestone references.
        - Handle missing or null `comments` fields gracefully, treating them as empty strings.
        - For timeline elapsed, use precomputed `elapsed_days` and `total_project_days` from `date_calc_log` to calculate `(elapsed_days / total_project_days) * 100`.

        ### Output Format
        ```json
        {{
            "project_status_summary": "2-3 sentence status with reasoning.",
            "project_overview": "Two-sentence summary.",
            "key_objectives": ["Objective 1", ...],
            "status_updates": {{
                "scope": {{"trend": "up|down|neutral"}},
                "schedule": {{"trend": "up|down|neutral"}},
                "spend": {{"trend": "up|down|neutral"}}
            }},
            "status_updates_trend_reason_for_all_three": "Explain trends for scope, schedule, and spend, referencing latest_project_status and prior week data.",
            "recent_achievements": ["Achievement 1", ...],
            "ai_insights": [
                "Insight 1 (max 120 words, include metric, risk, impact, action).",
                ...
            ],
            "next_steps": [
                {{"step": "Action", "due_date": "mm-dd-yyyy"}},
                ...
            ]
        }}
        ```
    """

    user_prompt = f"""
        Generate a project review report based on the provided data. Present ai_insights as a list of 8-10 distinct bullet-point strings (max 120 words each), each combining current state, risk of delay/failure, impact on objectives/key_results, using precise metrics (e.g., days remaining, days overrun) with accurate calculations and no typos. Include a project_status_summary with reasoning based on status updates, risks, milestones, and end date, using only precomputed metrics and validating `status` against `actual_completion_date`. Include recent achievements from completed milestones (with valid `actual_completion_date`), status update comments with 'on track,' 'completed,' 'achieved,' or mitigated risks, defaulting to 'No recent milestones, accomplishments, or mitigated risks reported' if none found. Flag planning issues, status discrepancies, and date errors as critical. Include one step for non-milestone risks if present. Use US date format (mm-dd-yyyy) for insights and ISO (mm-dd-yyyy) for next_steps. Today's date: {current_date}.
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )


def create_milestone_update_prompt(project_info=None, conversation=''):
    current_date = datetime.datetime.now().date().isoformat()
    one_week_later = (datetime.datetime.now().date() + datetime.timedelta(days=7)).isoformat()

    system_prompt = f"""
        You are a service assurance agent. Extract milestone updates or creations for the specified project from the user conversation.
        
        **Instructions**:
        1. Only include updates relevant to the project (use project name or ID from {project_info}).
        2. Identify all milestone-related phrases in the conversation.
        3. For each milestone mentioned:
        - Create an entry with `milestone_id` ("0" for new), `milestone_name`, `milestone_type` (2 = schedule), `original_date`, `new_target_date` (omit if completed), `actual_date` (set to {current_date} if completed), `status_value` (1=not started, 2=in progress, 3=completed), and `comments`.
        - Infer `status_value` from keywords: "complete"/"done" → 3, "in progress" → 2, "not started" → 1.
        - Correct spelling if needed and mention it in `comments`.
        - If multiple milestones exist, include all in `milestone_updates`.
        4. Dates must be valid (YYYY-MM-DD). Set `new_target_date` 1–2 weeks later for delayed milestones.
        5. If no relevant milestones, return an empty list with a comment explaining why.
        
        **Output JSON**:
        {{
            "project_id": "",
            "project_name": "",
            "milestone_updates": [
                {{
                    "milestone_id": "", // "0" for new
                    "milestone_name": "",
                    "milestone_type": 2, // 1 = scope, 2 = schedule, 3 = spend
                    "new_target_date": "", // Omit for status_value: 3
                    "original_date": "",
                    "comments": "", // Brief summary or clarification
                    "actual_date": "",
                    "status_value": 1 // 1: not started, 2: in progress, 3: completed
                }}
            ]
        }}

        **Input Data**:
        Project Info: {project_info}
        Conversation: {conversation}
        Current Date: {current_date}
    """

    user_prompt = "Output proper JSON with all milestone updates relevant to the project. Do not create unrelated milestones."
    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)



def create_status_update_prompt(project_info=None, conversation=''):
    current_date = datetime.datetime.now().date().isoformat()

    system_prompt = f"""
        Act as a service assurance agent to generate exactly one status update for the specified project from user conversation.
        Parse the conversation to relevant to the project with id, title etc from --  {project_info}
        Output structured JSON.

        **Input**:
        - Project ID & Name: From `project_info`. Use "Unknown" if `project_name` is missing.
        - Status Details: From `project_info` (scope, schedule, spend).
        - Conversation: User input describing changes or issues.
        - Current Date: {current_date}

        **Status Updates**:
        - Attributes: `update_type` (scope, schedule, spend), `update_value` (compromised, at_risk, on_track), `comment`.
        - Generate exactly one status update, prioritizing `schedule` for progress-related terms (e.g., "qa status update").
        - Filter conversation to include only phrases matching the project name (case-insensitive) or ID.
        - Parse for keywords:
          - scope: "scope creep," "requirements change."
          - schedule: "behind," "delayed," "completed," "on track," "qa status."
          - spend: "over budget," "cost overrun."
        - If project end date < {current_date}, set `schedule` to `compromised` unless conversation confirms completion.
        - Correct spelling (e.g., "Mindtickele" → "MindTickle") and note in `comment`.
        - If no relevant status update, return an empty `status_updates` list with a comment.

        **Chain of Thought**:
        1. Validate `project_info` for `project_id` and `project_name`.
        2. Split conversation into phrases by project (e.g., "mindtickele - qa status update").
        3. Filter phrases containing the project name (case-insensitive) or ID.
        4. Select the most relevant status update (e.g., "qa status update" → `schedule`, `at_risk`).
        5. Validate `update_type` (scope, schedule, spend) and `update_value` (compromised, at_risk, on_track).
        6. If ambiguous, note in `comment` (e.g., "Clarify: which status area?").

        **Output JSON**:
        ```json
        {{
            "project_id": "",
            "project_name": "",
            "status_updates": [
                {{
                    "update_type": "",
                    "update_value": "",
                    "comment": "" // Brief summary or clarification
                }}
            ]
        }}
        ```

        **Input Data**:
        Project Info: {project_info}
        Conversation: {conversation}
        Current Date: {current_date}
    """

    user_prompt = "Output proper JSON. Do not create random sttatuses. only related to this project from the conversation extract correctly"
    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)


def create_risk_update_prompt(project_info=None, conversation=''):
    current_date = datetime.datetime.now().date().isoformat()
    one_week_later = (datetime.datetime.now().date() + datetime.timedelta(days=7)).isoformat()

    system_prompt = f"""
        Act as a service assurance agent to generate concise risk updates or creations from project data and user conversation. Parse the conversation to identify risks, and output structured JSON. Only include relevant conversation excerpts in comments.

        **Input**:
        - Project ID & Name: From `project_info`. Use "Unknown" if `project_name` is missing.
        - Risk Details: From `project_info` (description, impact, mitigation, priority, due date, status).
        - Conversation: User input describing risks or issues.
        - Current Date: {current_date}

        **Risk Updates**:
        - Attributes: `risk_id` ("0" for new), `description`, `impact`, `mitigation`, `priority` (1-High, 2-Medium, 3-Low), `due_date` (YYYY-MM-DD, default {one_week_later}), `status_value` (1: Active, 2: Resolved, 3: Monitoring, 4: Escalated, 5: Mitigated, 6: Closed).
        - Infer risks from keywords like "resource shortage," "technical issue," "delay." Use defaults for `priority` (2) and `due_date` ({one_week_later}) if unspecified.
        - Include a brief summary in `description` and `impact`. Only include conversation excerpt if relevant (e.g., specific risk details).
        - If ambiguous (e.g., unclear risk), note briefly in `description` (e.g., "Clarify: what is the risk?").

        **Chain of Thought**:
        1. Validate `project_info`. If missing, note in `description`.
        2. Parse conversation for risk-related keywords.
        3. Assign attributes based on conversation or inferred risks.
        4. Validate `priority` (1-3), `due_date` (YYYY-MM-DD), `status_value` (1-6).
        5. If ambiguous, include concise clarification note.

        **Output JSON**:
        ```json
        {{
            "project_id": "",
            "project_name": "",
            "risk_updates": [
                {{
                    "risk_id": "",
                    "description": "",
                    "impact": "",
                    "mitigation": "",
                    "priority": 1,
                    "due_date": "",
                    "status_value": 1
                }}
            ]
        }}
        ```

        **Input Data**:
        Project Info: {project_info}
        Conversation: {conversation}
        Current Date: {current_date}
    """

    user_prompt = f"""
        Output proper JSON
    """

    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
