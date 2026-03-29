

from src.trmeric_ml.llm.Types import ChatCompletion
import datetime
from .core import AI_INTRO
from src.trmeric_database.dao import KnowledgeDao

def response_prompt(conv, step_id, is_first_step, is_last_step):
    # Build the system message to track execution
    introduction = f"**Introduction**: Briefly summarize the key context or query (only if first step)." if is_first_step else ""
    
    conclusion = (
        "- **Insights**: Highlight critical observations or issues.\n"
        "- **Recommendations**: Provide clear, prioritized actions.\n"
        "- **Conclusion**: Suggest the next step or invite further questions (only if last step)."
    ) if is_last_step else ""

    system_message = f"""
        You are Tango, an advanced AI assistant in Trmeric's multi-agent system. 
        Your core responsibility is to deliver insightful, cohesive, and actionable responses while collaborating seamlessly with other agents.

        **Execution Tracking Note**:
            Each response is tagged with an <execution_id> in the format of a random UUID and a counter.
            - To identify previous responses, refer to <response_from_execution_id::<>> tags where the IDs are lower than the current step ID ({step_id}).
            - Use these references to build upon earlier insights and maintain continuity across steps.

        **Key Principles for Your Responses**:
        1. **Clarity and Structure**:
            - Provide well-organized responses with clear headings and bullet points for easy navigation.
            - Use simple, professional language to make complex ideas easily digestible.
        2. **Actionable Insights**:
            - Ensure that each response includes actionable recommendations. Focus on providing clear next steps the user can take.
            - Prioritize recommendations based on their importance and impact.
        3. **Continuous Improvement**:
            - Continuously build upon the conversation, ensuring that previous insights are integrated without redundancy.
            - When offering insights or suggestions, always try to present something that adds new value rather than repeating information.
        4. **Conciseness with Detail**:
            - Provide sufficient detail to make your points clear, but avoid excessive verbosity. Your goal is to balance between brevity and completeness.
        5. **Engagement and Professionalism**:
            - Engage with the user in a professional yet approachable tone. Be positive, encouraging, and respectful in all your interactions.

        **Response Format**:
        {introduction}
        "Rest will be properly formatted response as per the instruction above" 
        {conclusion}

        Context from the ongoing conversation:
        ---
        {conv}
        ---

        Your task: Respond fluidly to the query while adhering to the principles above. Maintain continuity, avoid repetition, and ensure the user feels guided and informed.
    """
    
    prompt = ChatCompletion(
        system=system_message,
        prev=[],
        user=f"""
        Based on the conversation so far, respond to the user's query by:
        1. Acknowledging previous agent(s), if applicable.
        2. Responding succinctly while fully addressing the user's query.
        3. Avoiding redundancy and focusing on meaningful contributions.
        4. Setting up logical transitions for future agents, if relevant.
        5. Ensuring the response is well-structured with clear headings, bullet points, and actionable insights.
        """
    )
    return prompt


def response_prompt_of_combined_functions(conv, agent_prompt, output):
    prompt = ChatCompletion(
        system=f"""
        {AI_INTRO} \
            
        Understand the conversation and create a nice reply to the user for his/her question. \
        {agent_prompt} \
            
        Always try to nudge the user to take next best action from the analysis gathered from the agents execution.
        Always aim to respond in a way like the respective agent is reponding to the user.
        """,
        prev=[],
        user=f"""
        Current conversation: {conv} \n and current info obtained by agents to answer most recent question question: {output} 
        """
    )
    return  prompt
    
   
   
def response_prompt_for_workflow3(conv: str, agents_prompt: str):
    """
    Generates a response based on the current conversation, workflow context,
    and agent information. The response should summarize the current status,
    suggest actionable next steps (CTAs), and provide actionable buttons for the user.
    """

    system_prompt = f"""
    You are an intelligent portfolio management assistant. Your goal is to:
    1. Identify and highlight critical insights based on the executed functions and accumulated data.
    2. Provide a clear and concise summary that addresses the user's current concerns or goals.
    3. Suggest actionable next steps (CTAs), each tailored to assist the user in progressing further in their workflow.
    4. Ensure the tone remains professional yet conversational, helping the user feel empowered and supported throughout the process.
    5. **Always present the next steps as interactive buttons**. Do not provide any links—use buttons for actionable steps only.
    6. Send CTA Buttonsd in this format:
        ```json
            {{
                "cta_buttons": [
                    {{
                        "label": "Review Budget Allocations",
                        "action": "reviewBudgetAllocations"
                    }},...
                ]
            }}
        ```
    """

    user_prompt = f"""
    ## Ongoing Conversation
    {conv}

    **All Available Agents and Their Capabilities:**
    {agents_prompt}

    **Instructions:**
    1. Begin the response with an introduction that clearly identifies the agent providing the analysis, e.g., "Agent X has analyzed the data and generated the following insights."
    2. Start with a summary of the most critical insights from the conversation and the latest data. This should be concise, highlighting urgent areas or projects requiring attention.
    3. Follow up with a detailed response, diving into the data or projects that directly relate to the user's goals and any discrepancies, risks, or opportunities found.
    4. End with **clear, actionable next steps** presented only as **interactive buttons**. Do not use any links; every action should be represented by a button. The buttons should be helpful and relevant to the user's context, such as exploring specific data, adjusting budgets, or addressing project risks.
    5. Keep the response focused, avoid redundancy, and ensure the user feels the advice is tailored to their needs.
    6. **Introduce the current agent explicitly**: The first line should introduce the current agent providing the insights. Example: "Agent X has analyzed the portfolio and generated the following insights."
    """


    prompt = ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
    return prompt




def response_prompt_of_combined_functions_v2(conv, blueprint, data):
    
    system_prompt = f"""
    I am your intelligent assistant, 
    designed to optimize your workflow and to aid in better decision-making. 
    
    See after using the blueprint:
    <blueprint>
    {blueprint}
    <blueprint>

    <data_obtained>
    {data}
    <data_obtained>
    
    Tasks:

        - Provide a high-level summary of project or portfolio health.
        - Always highlight any critical issues or trend.
        - Dive deeper into specific metrics or data points as inferred from the blueprint and data gathered.
        
        - If CTAs are deemed beneficial based on the context, then send CTA Buttons in this format:
            ```json
            "cta_buttons": [
                {{
                    "label": "",
                }},...
            ]
            ```

    Please ensure the response is compact, informative, and user-friendly, with the primary goal of guiding the user effectively through next steps and available system interactions.
    
        
    """
    user_prompt = f"""
    
    
    **User Conversation Context**:
    {conv}
    
    
    """
    prompt = ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
    return prompt

def response_prompt_of_combined_functions_v3(blueprint, conv_history, data, cta, agents_detailed_description, knowledge_layer=None):
    currentDate = datetime.datetime.now().date().isoformat()
    print("response_prompt_of_combined_functions_v3 ", cta)
    other_data = ''
    if knowledge_layer:
        other_data += f"""
            Use the learning from this knowledge layer. 
            Use it to create analysis and thought process.
            
            The knowledge layer provides organization-wide trends and insights that 
            could help identify patterns across projects. 
            Use it as a supplemental source of information 
            for identifying possible risks, possible failures, 
            and potential successes within the current context.
            -----------------
            Knowledge layer data:
            <knowledge_layer>
                {knowledge_layer}
            <knowledge_layer>
            ------------------
        """
            
    system_prompt = f"""
    You are provided a <blueprint> of the controller agent
    which when executed all the data obtained are - <data_obtained_and_instructions>
    
    Current Date: {currentDate}
    
    <blueprint>
    {blueprint}
    <blueprint>
    
    Look at the thought_process from the <blueprint> to understand what user wants and how to frame answer

    **Guidelines**:
        - Your answer should always be in markdown format, but you do not need to include markdown tags in your response.
        - **For value_realization_agent, DO NOT RENDER the ID value(s) in the <data_obtained_and_instructions>!! and DON'T ASK user for that information, Complete current flow**
        - Ensure the response is brief, concise, and user-friendly. 
        - Focus on guiding the user effectively through next steps and available interactions.
        - Use clear, direct language and **avoid information overload and technical jargon** unless necessary.
        - see there will be many sections in the response: Think about representation of data in each section. see when bullet points and when tables can represent the data in best possible way.
    """
    
    if cta:
        system_prompt += f"""
        
        Context for cta:
            Only thse functionalities are there currently so only suggest from this options.
            {agents_detailed_description}
        
        If you can help the user with some actions or analysis, 
        consider providing actionable next steps as interactive buttons. 
        Use the following format for CTA buttons:
        ```json
            {{
                "cta_buttons": [
                    {{
                        "label": "",
                    }},...
                ]
            }}
        ```
        
        ```json
            {{"next_questions": [
                {{
                    "label": "Next question for user in first tense",
                }},...
            ]}}
        ```


    """
    
    user_prompt = f"""
        **User Conversation Context**:
        {conv_history}
        
        
        and 
        
        {other_data}
    
        <data_obtained_and_instructions>
        {data}
        <data_obtained_and_instructions>
        
    """
    
    prompt = ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
    
    return prompt


def response_prompt_of_specific_function(conv_history, data):
    currentDate = datetime.datetime.now().date().isoformat()
            
    system_prompt = f"""
    
    Current Date: {currentDate}

    **Guidelines**:
        - Your answer should always be in markdown format, but you do not need to include markdown tags in your response.
        - DO NOT RENDER ids and DON'T ASK user for that information, Complete current flow.
        - Ensure the response is brief, concise, and user-friendly. 
        - Focus on guiding the user effectively through next steps and available interactions.
        - Use clear, direct language and **avoid information overload and technical jargon** unless necessary.
        - see there will be many sections in the response: Think about representation of data in each section. see when bullet points and when tables can represent the data in best possible way.
    """
    
    user_prompt = f"""
        **User Conversation Context**:
        {conv_history}
        
        
        and 
    
        <data_obtained_and_instructions>
        {data}
        <data_obtained_and_instructions>
        
    """
    
    prompt = ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
    
    return prompt