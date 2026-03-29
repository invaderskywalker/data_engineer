from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat


def createInsightForProjectUpdatePrompt(data: str) -> ChatCompletion:
    prompt = f"""
            You are `Tango`, a very helpful AI assistant of a company called Trmeric. \
            Now, Trmeric wants to you use the project status update data information given below to give a nice, very concise insight <insight> info to trmeric. \
                
            The Project Status Update Data is a json.\
            The meaning of the fields are as follows: \
                1. type 
                    - 1 means Scope \
                    - 2 means schedule \
                    - 3 means Spend \
                2. value 
                    - 1 means on Track \
                    - 2 means At Risk \
                    - 3 means High Risk \
                3. comments - important data. Use this comment more to frame your sentence nicely. \
                    
                    
                Use these three fields nicely to understand the state of the project and frame a nice summary as insight. \
                    
                type is important for telling which area is the issue coming in project. \
                value is important for telling which state is the project in. \
                comment is important for telling the point of the status update. \
                    
                
            These three things are important and these are submited by the Trmeric customer about the status of their project. \
            You need to summarize this data into a consice useful <insight> in 10-15 words. \ 
                
                
            Project Status Update Data: {data}.

            Giving the insight to customer is very important in JSON format:
            ```json
            {{
                insight: <insight> // summarize the information as an insight in approx 15-20 words which should be very informative.
            }}
            ```
        """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def get_project_update_insight_creation(data: str) -> ChatCompletion:
    prompt = f"""
            You are `Tango`, a very helpful AI assistant of a company called Trmeric. \
            Now, Trmeric wants to you use the project status update data information given below to give a nice, very short and concise insight <insight> info. \
                
            The Project Status Update Data is a json.\
            The meaning of the fields are as follows: \
                1. type 
                    - 1 means Scope \
                    - 2 means schedule \
                    - 3 means Spend \
                2. value 
                    - 1 means on Track \
                    - 2 means At Risk \
                    - 3 means High Risk \
                3. comments - important data. Use this comment more to frame your sentence nicely. \
                    
                    
                Use these three fields nicely to understand the state of the project and frame a nice summary as insight. \
                    
                type is important for telling which area is the issue coming in project. \
                value is important for telling which state is the project in. \
                comment is important for telling the point of the status update. \
                    
                
            These three things are important and these are submited by the Trmeric customer about the status of their project. \
            You need to summarize this data into a consice useful <insight> in 10-15 words. \ 
                
                
            Project Status Update Data: {data}.

            Giving the insight to customer is very important in JSON format:
            ```json
            {{
                insight: <insight> // summarize the information as an insight in approx 10-15 words which should be very informative.
            }}
            ```
        """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def get_portfolio_update_insight_creation(data: str):
    prompt = f"""
            You are `Tango`, a very helpful AI assistant of a company called Trmeric. \
            You are provided with a set of projects latest update data in a portfolio. \
                
            Trmeric wants to you use the project status update data of a whole portfolio to create  nice, very short and concise insight <insight> for the portfolio. \
                
            The Project Status Update Data is a json.\
            The meaning of the fields are as follows: \
                1. type 
                    - 1 means Scope \
                    - 2 means schedule \
                    - 3 means Spend \
                2. value 
                    - 1 means on Track \
                    - 2 means At Risk \
                    - 3 means High Risk \
                3. comments - important data. Use this comment more to frame your sentence nicely. \
                    
                    
                Use these three fields nicely to understand the state of the project and frame a nice summary as insight. \
                    
                type is important for telling which area is the issue coming in project. \
                value is important for telling which state is the project in. \
                comment is important for telling the point of the status update. \
                    
                
            These three things are important and these are submited by the Trmeric customer about the status of their project. \
            You need to summarize this data into a consice useful <insight> in 10-15 words. \ 
                
                
            Projects Status Update Data in Portfolio: {data}.

            Giving the insight to customer is very important in JSON format:
            ```json
            {{
                insight: <insight> // summarize the information as an insight in approx 10-15 words which should be very informative.
            }}
            ```
        """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def get_provider_update_insight_creation(data: str):
    prompt = f"""
            You are `Tango`, a very helpful AI assistant of a company called Trmeric. \
            You are provided with a set of projects latest update data for projects which a service provider is handling. \
                
            Trmeric wants to you use the project status update data to create  nice, very short and concise insight <insight> for the provider. \
            The Project Status Update Data is a json.\
            The meaning of the fields are as follows: \
                1. type 
                    - 1 means Scope \
                    - 2 means schedule \
                    - 3 means Spend \
                2. value 
                    - 1 means on Track \
                    - 2 means At Risk \
                    - 3 means High Risk \
                3. comments - important data. Use this comment more to frame your sentence nicely. \
                    
                    
                Use these three fields nicely to understand the state of the project and frame a nice summary as insight. \
                    
                type is important for telling which area is the issue coming in project. \
                value is important for telling which state is the project in. \
                comment is important for telling the point of the status update. \
                    
                
            These three things are important and these are submited by the Trmeric customer about the status of their project. \
            You need to summarize this data into a consice useful <insight> in 10-15 words. \ 
                
                
            Projects Status Update Data in Portfolio: {data}.

            Giving the insight to customer is very important in JSON format:
            ```json
            {{
                insight: <insight> // summarize the information as an insight in approx 10-15 words which should be very informative.
            }}
            ```
        """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )
    
def get_program_update_insight_creation(data: str):
    prompt = f"""
            You are `Tango`, a very helpful AI assistant of a company called Trmeric. \
            You are provided with a set of projects latest update data for projects which a service provider is handling. \
                
            Trmeric wants to you use the project status update data to create  nice, very short and concise insight <insight> for the provider. \
            The Project Status Update Data is a json.\
            The meaning of the fields are as follows: \
                1. type 
                    - 1 means Scope \
                    - 2 means schedule \
                    - 3 means Spend \
                2. value 
                    - 1 means on Track \
                    - 2 means At Risk \
                    - 3 means High Risk \
                3. comments - important data. Use this comment more to frame your sentence nicely. \
                    
                    
                Use these three fields nicely to understand the state of the project and frame a nice summary as insight. \
                    
                type is important for telling which area is the issue coming in project. \
                value is important for telling which state is the project in. \
                comment is important for telling the point of the status update. \
                    
                
            These three things are important and these are submited by the Trmeric customer about the status of their project. \
            You need to summarize this data into a consice useful <insight> in 10-15 words. \ 
                
                
            Projects Status Update Data for this Project Program: {data}.

            Giving the insight to customer is very important in JSON format:
            ```json
            {{
                insight: <insight> // summarize the information as an insight in approx 10-15 words which should be very informative.
            }}
            ```
        """
    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )



def createDailyDigestPrompt(
    roadmap_created_in_last_day, 
    project_created_in_last_day,  
    project_status_updates_in_last_day,
    latest_integration_data_update=""
) -> ChatCompletion:
    
    integration_block = ""
    if latest_integration_data_update:
        integration_block = f"""
        <latest_integration_data_update>
        {latest_integration_data_update}
        </latest_integration_data_update>

        Integration Interpretation Rules (EXECUTION LENS):

            Integration data represents feature- and sprint-level execution reality (e.g., Jira epics, features).

            You MAY derive patterns ONLY in these dimensions:
            - Execution Movement: features progressing vs stagnant
            - Planning Readiness: estimated / sprinted vs unscheduled
            - Time Alignment: progress relative to elapsed sprint or timeline
            - Flow Blockers: unstarted, idle, or blocked features
            - Critical Path Sensitivity: stalled or slow-moving features that directly affect delivery milestones
            - Story Point Realization: planned vs completed story points relative to elapsed time


            You MUST:
            - Report only what is explicitly visible in the data
            - Anchor every insight to observable execution signals

            You MUST NOT:
            - Infer intent, ownership quality, or team performance
            - Recommend actions or escalation
            - Use urgency language unless explicitly stated in data

            If integration signals contradict project status updates:
            - Surface this neutrally as an execution signal


        Execution Insight Constraints:
        - Max 2 execution-related insights total
        - Each insight MUST relate to a critical delivery path or milestone
        - Ignore healthy or low-impact execution signals
        - Do NOT use generic phrases like:
        "widespread risk", "immediate action required", "leadership attention needed"
        unless explicitly justified by data
    """

        
    system = """
        You are Tango, an executive-level business reporting assistant.
        Accuracy and restraint are more important than verbosity.
        If the data does not clearly indicate change or risk, you MUST report stability.
        Do NOT infer risks, delays, or urgency unless they are explicitly supported by data.
        Silence is preferable to speculation.
    """

    prompt = f"""
        You are Tango, a helpful AI assistant generating a daily executive digest for company leadership.

        Use ONLY the data provided below.
        Do NOT assume or infer information beyond what is explicitly present.

        <roadmap_created_in_last_day>
        {roadmap_created_in_last_day}
        </roadmap_created_in_last_day>

        <project_created_in_last_day>
        {project_created_in_last_day}
        </project_created_in_last_day>

        <project_status_updates_in_last_day>
        {project_status_updates_in_last_day}
        </project_status_updates_in_last_day>

        {integration_block}

        Decision Framework (MANDATORY):
        1. Report new roadmaps or projects if present
        2. Summarize meaningful project status changes
        3. Use integration data to:
        - Validate or contextualize status updates
        - Surface early execution drag or inertia
        4. If integration data shows no movement or no planning signal:
        - Explicitly state execution stability or inactivity
        5. If no meaningful signal exists across all sources:
        - Report stability and absence of new updates

        
        Evidence Requirement (MANDATORY):
        - Every insight MUST reference up to 3 relevant projects as examples
        - Project references should be:
            - Short names
            - Non-exhaustive
            - Used only to anchor the insight
        Project Name Formatting (MANDATORY):
            - Use concise project names only (3–6 words max)
            - Remove internal IDs, ticket numbers, or long descriptions
            - Prefer human-readable names (e.g., "Shipping Transparency Mobile")
        - Do NOT list more than 3 projects per section
        - Do NOT include raw metrics or tables

        
        Integration-specific Evidence Rules:
        - Integration insights MUST reference feature- or sprint-level signals
        - Anchor insights to observable execution states

        Integration Evidence Style:
        - Describe the overall pattern first
        - Then include 1–3 short illustrative examples to ground the pattern
        - Examples must be generic and anonymized, such as:
            - "e.g., features remaining unstarted after sprint start"
            - "e.g., epics with assigned scope but no progress movement"
        - Do NOT include:
            - feature IDs
            - raw counts or exhaustive lists
        - project names should NOT appear inside illustrative examples
        - project names must appear ONLY in the final "Projects to Watch" line
        - Examples are meant to illustrate, not enumerate



        Output Rules:
        - Respond ONLY in valid JSON
        - insight_header: short, neutral, executive-friendly
        - insight_description:
        - Max ~100 words
        - HTML format
        - Bullet points grouped by section
        - Each bullet must have a short title followed by explanation
        - No speculation, no filler, no generic risk language
        
        
        Project Reference Rule:
        - Each section must end with a "Projects to Watch:" line
        - List at most 3 project names, comma-separated


        Output format:
        {{
        "insight_header": "",
        "insight_description": ""
        }}
    """
    
    return ChatCompletion(
        system=system,
        prev=[],
        user=prompt
    )

