
from .core import AI_INTRO, TASKS_OF_PRIMARY_AGENT, OUTPUT_FORMAT_OF_PRIMARY_AGENT, OUTPUT_FORMAT_BLUEPRINT, OUTPUT_FORMAT_NEXT_STEP, OUTPUT_FORMAT_FOR_BLUEPRINT_V3
from src.trmeric_ml.llm.Types import ChatCompletion
import datetime


def primary_agent_prompt(conv, user_context, agents):
    llm_prompt = f"""
        The user's conversation can be seen below:\n\n{conv}
        The most recent message is at the bottom and is the latest user query. 
        You can use the rest of the messsage as context if it helps.
        
        {TASKS_OF_PRIMARY_AGENT(user_context, agents)}
        {OUTPUT_FORMAT_OF_PRIMARY_AGENT}
    """
    return  ChatCompletion(
            system=AI_INTRO,
            prev=[],
            user=llm_prompt
        )
    
### in use   
def blueprint_creation_prompt(conv, agent_descriptions, primary_agent_prompt):
    prompt = f"""
        The user's conversation can be seen below:\n\n{conv}
        The most recent message is at the bottom and is the latest user query. 
        You can use the rest of the messsage as context if it helps.

        Available agents and their functions:
        {agent_descriptions}
        
        Your role as the primary agent is to create a blueprint of which function you should trigger 
        and what params you should pass and also the next agents and its function 
        that you should pass.


        Based on the user query, generate a step-by-step execution plan that includes:
        thought_process of an intelligent agent to answer the user query and also to enhance the experience of the user when we can answer him more than he actually knows he can be get help from trmeric (our company)
            1. The agent to use
            2. The function to call on the agent
            3. Arguments (if applicable)
            
        **Important Instructions for Arguments (`args`):**
            - Ensure that all arguments are specific, actionable, and complete.
            - Avoid using placeholders like `/* specific portfolio id(s) provided by the user */` or `<input>`.
            - If an argument value cannot be determined from the context, explicitly indicate it as `null` or exclude it.
            - The output must only include arguments that are ready to be executed without further user input.
            
        {OUTPUT_FORMAT_BLUEPRINT}
    """
    
    return  ChatCompletion(
            system=AI_INTRO,
            prev=[],
            user=prompt
        )


def next_step_finder_prompt(steps_executed_already, agents, conversation, data_from_current_agent):
    systemPrompt = f"""
        {AI_INTRO}
    
        You role intro
        -------
        
        You are an intelligent execution planner tasked with determining the next logical step for a multi-agent system. 
        Below are the details of the system's current state, available agents, and ongoing conversation. 
        Use this information to suggest the next step in the execution plan.
        
        
        
        ### Instructions:
        1. Analyze the `steps_already_executed` to understand the progress made so far and identify gaps or dependencies.
        2. Refer to the agents descriptions to determine which agent and function are best suited for the next step and figure out what arguments is reuired.
        3. Ensure that all required arguments are provided. If they are missing, request user clarification.
        4. Use the conversation context to align the next step with user expectations and goals. Specifically, identify if the user has already provided information or if more context is needed.
        5. If the function has no missing information or requires a further request, suggest the next course of action accordingly.
        6. If in the ongoing conversation if the answer is given at the latest and it fulfils the user query and if we cannot provide anymore help to the user do not output.
        7. Look the conversation and create an understanding of what params are exactly needed by the next function.
        
    
        ### Expected Output Format:
        {OUTPUT_FORMAT_NEXT_STEP}
        
        P.S: to output correct should_stop you should look at the thought_process
        and make the thought_process concise and clear
    """
    prompt = f"""
    
        ### Ongoing Conversation Context
        {conversation}  
        
        ### Steps Already Executed
        {steps_executed_already}

        ### Available Agents and Their Descriptions
        {agents}

        ### Data from Current Agent
        {data_from_current_agent}

        Ensure that your output is complete, actionable, and aligned with the current context.
        In case when no next step is required, make should_stop in output to true.
    """
    
    return  ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )


def plan_functions_prompt(data, agents_prompt, conv, user_context, agent_name):
    """
    Generate a prompt for the primary agent to decide which functions to execute
    based on the provided data, agent prompt (raw text), and ongoing conversation.

    data: The data provided by the current agent to help decide the function's arguments.
    agents_prompt: Raw text describing the available agents and functions
    conv: The ongoing conversation context with the user.
    """
    
    systemPrompt = f"""
        {AI_INTRO}

        ##Role:
        You are the primary agent: {agent_name}, responsible for identifying the optimal secondary agent to respond to user need.
        

        ## Task Objective:
        Analyze and select from the available agents and their functions. 
        Use the provided data to determine necessary function arguments and decide which functions to execute for optimal response to the user's query.
    
        ### Available Agents and Functions to choose from and decide their arguments based on the data provided:
        {agents_prompt}
        
        ### Data Provided by Primary Agent to Help Decide Arguments for Functions:
        {data}
        
        ### Ongoing Conversation Context:
        {conv}
        
        ### Instructions:
        1. Refer to the `agents_prompt` to understand your role, description, and the available functions at your disposal.
        2. Use the provided `data` to evaluate the user's request and determine which functions are most appropriate for the next step.
        3. If any arguments for a function are missing or unclear, request clarification or additional details from the user.
        4. Consider the ongoing `conv` (conversation) context to make sure your selected function(s) align with the user’s goals and expectations.
        5. Provide a clear plan of which functions to execute, detailing the name of each function, its required arguments, and the reasoning behind each choice.

        ### Expected Output Format:
        A list of planned functions, where each entry is a dictionary containing:
        - "function": The name of the function to execute.
        - "args": A dictionary of arguments required for the function.
        - "short_reason": A brief reason for choosing this function.

        Output Format (JSON):
        ```json
        [
            {{
                "agent": "<agent_name>",
                "function": "<name_of_function>",
                "args": {{
                    "<arg1>": "<value1>",
                    "<arg2>": "<value2>"
                }},
                "short_reason": "<short_reason_for_choosing_this_function>"
            }},...
        ]
        ```
    """
    
    userPrompt = f"""
        Please identify and select the appropriate functions from the list provided:
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def next_step_finder_prompt_v2(steps_executed_already, agents, conversation, data_from_current_agent):
    systemPrompt = f"""
        {AI_INTRO}
    
        You role intro
        -------
        
        You are an intelligent execution planner tasked with determining the next logical step for a multi-agent system. 
        Below are the details of the system's current state, available agents, and ongoing conversation. 
        Use this information to suggest the next step in the execution plan.
        
        
        
        ### Instructions:
        1. Analyze the `steps_already_executed` to understand the progress made so far and identify gaps or dependencies.
        2. Refer to the agents descriptions to determine which agent and function are best suited for the next step and figure out what arguments is reuired.
        3. Ensure that all required arguments are provided. If they are missing, request user clarification.
        4. Use the conversation context to align the next step with user expectations and goals. Specifically, identify if the user has already provided information or if more context is needed.
        5. If the function has no missing information or requires a further request, suggest the next course of action accordingly.
        6. If in the ongoing conversation if the answer is given at the latest and it fulfils the user query and if we cannot provide anymore help to the user do not output.
        7. Look the conversation and create an understanding of what params are exactly needed by the next function.
        
    
        ### Expected Output Format:
        {OUTPUT_FORMAT_NEXT_STEP}
        
        P.S: to output correct should_stop you should look at the thought_process
        and make the thought_process concise and clear
    """
    prompt = f"""
    
        ### Ongoing Conversation Context
        {conversation}  
        
        ### Steps Already Executed
        {steps_executed_already}

        ### Available Agents and Their Descriptions
        {agents}

        ### Data from Current Agent
        {data_from_current_agent}

        Ensure that your output is complete, actionable, and aligned with the current context.
        In case when no next step is required, make should_stop in output to true.
    """
    
    return  ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )



    
def blueprint_creation_prompt_v2(conv, agent_descriptions):
    prompt = f"""
        **Available Agents and Functions:**
        {agent_descriptions}

        **Your Mission as the Primary Agent:**
        Construct a detailed blueprint that determines which agents and their functions should be triggered in response to the user's latest query. This blueprint should aim not only to resolve the current query but also enhance the overall user experience by uncovering additional avenues where our company, Trmeric, could provide assistance.

        **Step-by-Step Execution Plan to Include:**
        - **Agent Selection**: Identify the best-suited agent(s) for addressing the query.
        - **Function Invocation**: Specify the function(s) to be invoked on the agent(s).
        - **Arguments**: Provide actionable and complete arguments for the function.
          - If any arguments rely on user input that is not in context, indicate default values or assumptions, and label them clearly.
          - Avoid placeholders like `/* specific portfolio id(s) provided by the user */` or `<input>`.
          - If undeterminable from the context, indicate `null` or note the requirement for further user input.
          
        **Thought Process**: Briefly Capture the logical reasoning of an intelligent agent in selecting agents and functions. Highlight any assumptions made due to insufficient data.
        **Next Steps**: Briefly Suggest follow-up actions that could engage the user further or handle incomplete data scenarios effectively.
        
        Follow the JSON format specified below:
        {OUTPUT_FORMAT_BLUEPRINT}
    """
    
    return ChatCompletion(
            system=AI_INTRO,
            prev=[],
            user=prompt
        )



    
def blueprint_creation_prompt_v3(conv, agent_descriptions, context, user_context, integrations):
    currentDate = datetime.datetime.now().date().isoformat()
    prompt = f"""
        {AI_INTRO} \
            
        **Available Agents and Functions:**
        {agent_descriptions}
        
        **User Context**
        {context}
        
        **Available Integrations and their Information**
        {integrations}

        
        **Blueprint Generation Task**

            You are tasked with generating a simplified blueprint for a multi-agent system designed to handle a user's query. 
            This system includes multiple primary agents, each with specific roles and responsibilities, chosen from the available agents.
            Your goal is to create a streamlined plan that:

            1. **Thought Process**: Capture a brief overview of the logical reasoning used to select the agents and devise the plan. This should include any assumptions or key considerations made during the process.
            2. **Steps**: List the steps involved in executing the plan. For each step, specify:
                - **Agent Name**: The name of the primary agent involved in this step.
                - **Functions**: List the functions the agent will perform, along with necessary arguments. Also carefully see the format of the arguments and stick to it. If the arguments are not valid then do not pass arguments. Also, do not pass placeholders.
                - think carefully for this because you see. if service_assurance_troubleshoot_agent is in conversation and if you wont select it again it wont be good experience. So think really hard on the steps and its functions
                
            3. The core focus should be on looking at the format of the argument and stick to that. 
                like for update_or_create_risk function stick to format like json risk_data and also carefully look at other functino arguments format
                for update_or_create_action -- argument action_data is a json
                
            4. Decide what kind of feedback you want from user - Action/Text. Think carefully because see functions like service_assurance_insight of service_assurance_agent expects user to do some next action. but functions like status update expects user to write text to understand update. and portfolio agent should give best next best actions
            5. For resource planning agent don't call both capacity_planner and resource_allocator functions together. Trigger as per the user message
            

    
        **Output Format**: Use the following JSON structure for your output.
        {OUTPUT_FORMAT_FOR_BLUEPRINT_V3}

        Ensure that your output is concise, aligns with the objectives stated above, and includes suggestions for engaging the user further.
        Note:: Only select agents and functions among the list provided
        
        
        Current Data - {currentDate}
    """
    
    user_prompt = f"""
    ### Ongoing Conv: 
    {conv}
    
    Please use this ongoing conv for context and look at my latest query to create the blueprint.
    If the conversation matches with an argument for a function, then you should pass the argument in the correct format.
    If you have no logical value for an argument that is not required, then don't pass it at all. 
    """
    
    return ChatCompletion(
            system=prompt,
            prev=[],
            user=user_prompt
        )

