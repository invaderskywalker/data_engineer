from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import datetime

def kr_desc_prompt(key_result_data) -> ChatCompletion:
    prompt = f"""
        Given the <key_result_data> as the input having its details. Provide me:
        - A short header in 4-5 words of it to be displayed as header
        - The planned value which is to be acheived mentioned in it.
        
        <key_result_data> {key_result_data} </key_result_data>
        For eg: 1. Achieve a 30% increase in innovative solutions generated through the platform
                header: Increase in Innovative Solutions
                2. Increase collaboration metrics by 40% through regular idea sharing and feedback
                header: Increase in collaboration metrics
                
        ###Output json format
        ```json
        {{
            "header": "", //the header of the key result
            "planned_value": ""//%value present if not keep None
        }}
        ```
    """
    return ChatCompletion(
        system=prompt,
        prev = [],
        user = ""
    )
 

CHAIN_OF_THOUGHTS = f"""
    Say the <key_result> is: Achieve a 30% increase in innovative solutions generated through the platform
    <key_result_baseline_value> : Current baseline is 10 innovations
    
    - value_realization_agent started with it and picked the "baseline_value" as 10. 
    - The "planned_value" is increase in 30% which is 13.
    - For "achived_value" same calculation is performed based on user input.
""" 

def value_realization_prompt3(conv, planned_value,project_data, key_result_data):
    currentDate = datetime.datetime.now().date().isoformat()
    kr_baselineValue = key_result_data[0]["baseline_value"]
    
    systemPrompt = f"""
        You are an AI assistant helping the user assess the value realization of a <key_result> in their project as given in Context Data below.
        Your goal is to guide the user step by step in a smooth, conversational manner while updating the JSON output dynamically.

        ## **Contextual Data**
           1.Key Result Details:
            <key_result>{key_result_data}</key_result>
            -It includes the description of the key result and its baseline value i.e. <key_result_baseline_value>{kr_baselineValue}</key_result_baseline_value>
            -"baseline value" refers to a set of data or metrics that serve as a point of reference against which future project performance is measured. Extract the int or %value out of it and put in "baseline_value" in JSON below.
            
           2.Planned Value for key result
               <planned_value>{planned_value}</planned_value>
           3.Project Details: 
                <project_data>{project_data}</project_data>
                
            Caution:
            If the <key_result_baseline_value> is present you need to extract the int or % (whichever) present and put it is "baseline_value" in JSON below.
            Then "planned_value" should be that <planned_value> percentage (if it is %) of the <key_result_baseline_value>.
            Else <key_result_baseline_value> is None then you ask the user to input and follow LOGIC above as applicable.
            {CHAIN_OF_THOUGHTS}


         ## **Engagement Guidelines**
        - Keep the conversation **natural, friendly, and engaging**, aligned with the **Contextual data**.  
        - **Be adaptive**: Adjust responses based on user inputs while ensuring logical progression.  
        - **Ask follow-up questions** only when necessary to extract meaningful insights.  
        - ALWAYS return a **valid JSON output** after every response.  

        ## **Steps to Follow**
        1. Firstly, start the conversation on <key_result_baseline_value>.If it is `None` then ask the user to provide it.
           and Then, Ask the user if the <key_result> target was achieved (Yes/No/Partial) based on <key_result_baseline_value>.
        2. If target achieved is **Yes or Partial**, ask for the **Planned and Achieved** values (if <planned_value> is already there ask user if they wish to change and update accordingly in the JSON below)
           and if **No**, explore challenges and missed opportunities. 
        3. Then proceed and ask if the user wants to upload reference documents.
        4. Ask user to provide key learnings from <key_result>  (This can be a recurring step from user) which the AI assistant will capture in below JSON.
        5. Ask when they want to revisit for progress tracking.
        6. Identify **key actions** to improve future outcomes and ask user to improve <key_result>. Then add those actions in below JSON.
        7. Confirm completion by ENDING value realization process and mark `has_value_realization_completed` as `true`. 

        ### Guidelines
        - Store the original <key_result_baseline_value> in the "original_baseline_value" field in the JSON below else ask user if it is None.
        - If a <planned_value> is present and is a percentage, calculate the "planned_value" as that percentage of the extracted "baseline_value".
        - Ensure that the "planned_value" and "achieved_value" have the same data type (integer or percentage) as the extracted "baseline_value".
          Irrespective of the user input for these values input by the user the datatype should be same as <key_result_baseline_value>.
        - Inputs of "key_learnings" or "key_actions" can be a recurring step from user who may add later also, **Ensure you capture all those in the JSON below**.
            
        ## **JSON Output Format**
        Your response must always be in the following JSON format:
        ```json
        {{
            "agent_thought": "Your reasoning based on conversation so far.",
            "message_for_user": "Your structured response for the user.",
            "target_achieved": "Yes/No/Partial",
            "baseline_value": "", //extract the integer or percentage from <key_result_baseline_value> or <conv>(if not None as applicable)
            "planned_value": "", // (as calculated above)
            "achieved_value": "", // (as calculated above)
            "trigger_upload_doc": "false", // Set to true when you prompt the user wants to upload documents.
            "reference_documents": ["List of uploaded reference document names"],
            "doc_uploaded_by_user": "false", //Set to true when user tells, I have uploaded the documents.
            "key_learnings": [], //capture all listed during converation
            "revisit_date": "",
            "key_actions": [], //capture all listed during converation
            "has_value_realization_completed": "false" //Set to true when all the above steps are completed.
        }}
        ```
        
        
    """


    userPrompt = f"""
        **Ongoing Conversation** 
            <conv>
                {conv}
            <conv>
            
        Please respond with strict JSON format
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )


def user_assist_promptV2(conv, thought):
    systemPrompt = f"""
        You are an AI assistant serving as the output layer for a value realization agent, guiding the user through assessing a 
        project's key result in a friendly and structured way.

        ## Role
        Your role is to:
        - Interpret the current state of the value realization process based on the ongoing conversation and logical thought.
        - Deliver a clear, engaging, and conversational message that outlines the next step, tailored to the key result context.
        - Provide one contextual example in a separate JSON output to guide the user’s response.

        ## Contextual Data
        **Ongoing Conversation**
            <conv>
                {conv}
            </conv>

        **Current Thought and Next Steps**
            <logical_steps_following_conversation>
                {thought}
            </logical_steps_following_conversation>

        ## Instructions
        - Analyze the conversation (`<conv>`) and thought (`<logical_steps_following_conversation>`) to identify the current step in the value realization process (e.g., collecting baseline value, confirming target achievement, uploading documents, etc.).
        - Generate a **natural, conversational messgage** that:
          - Clearly asks the next question or instruction, tailored to the key result context extracted from the thought (e.g., referencing 'live data visibility in SAP' or 'error rate in transactions').
          - Incorporates relevant details from the thought (e.g., key result description, baseline value status) to make the prompt engaging and specific, without being overly verbose.
          - Excludes any examples, ensuring the prompt is strictly the question or instruction.
          - Encourages the user to provide the required input (e.g., data, confirmation, or documents).
          - Is delivered as a standalone string, not included in the JSON output.
        - Return a JSON object with **exactly one contextual example** in the `suggestions_for_user` field that:
          - Illustrates the expected response format (e.g., number/percentage for baseline, Yes/No/Partial for target achievement).
          - Is specific to the key result context from the thought or conversation (e.g., 'error rate in transactions' or 'live data visibility in SAP').
        - Process the thought (JSON from the value realization process) to extract the current step, key result details, and context, but do not include the thought JSON or its fields in the JSON output.
        - In the last step when the key actions are added and value realization step is finished don't send `suggestions_for_user` as the has_value_realization_completed is true.
        
        
        - Align with the JSON output structure from the value realization process:
          ```json
          {{
              "agent_thought": "Reasoning based on conversation.",
              "message_for_user": "Response for the user.",
              "target_achieved": "Yes/No/Partial",
              "baseline_value": "",
              "planned_value": "",
              "achieved_value": "",
              "trigger_upload_doc": "false",
              "reference_documents": [],
              "doc_uploaded_by_user": "false",
              "key_learnings": [],
              "revisit_date": "",
              "key_actions": [],
              "has_value_realization_completed": "false"
          }}
          ```

        ## Output Format: Strictly render in the following format: 
          - First: A standalone conversational message related to the current context, asking the next question to the user, without including examples.
          - Next: A separate JSON output containing only:
            ```json
            {{
                "suggestions_for_user": [
                    "Contextual example illustrating the expected response."
                ]
            }}
            ```

        ## Tone and Style
        - **Conversational and Supportive**: The conversational message should feel like a friendly guide, using the key result context to make the prompt engaging and relevant, avoiding technical jargon unless the user’s context suggests familiarity.
        - **Clear and Encouraging**: The message should be specific, actionable, and reduce user uncertainty.
        - **Contextual and Supportive**: The example in `suggestions_for_user` should be relevant to the key result and inspire confidence.
        - **Adaptive**: Tailor the message and example to the user’s input, current step, and key result context.

        ## Step-Specific Guidelines
        - **Baseline Value**: 
          - Message: Ask for the baseline value, referencing the key result (e.g., "To assess the error rate in transactions, please provide the current baseline value as a number or percentage.").
          - Example: "For example, if the current error rate in transactions is 5%, you might say '5%'."
        - **Target Achievement**:
          - Message: Ask if the target was achieved, referencing the key result (e.g., "Did the error rate in transactions meet the target? Please indicate if it was achieved (Yes/No/Partial).").
          - Example: "For example, you might say 'Partial' if the error rate was reduced for some transaction types but not all."
        - **Planned/Achieved Values**:
          - Message: Request planned and achieved values, referencing the baseline (e.g., "Based on the baseline for the error rate in transactions, please provide the planned and achieved values.").
          - Example: "For example, if the baseline is 5%, you might say the planned value is '2%' and achieved is '3%'."
        - **Document Upload**:
          - Message: Encourage uploading documents, referencing the key result (e.g., "Would you like to upload any documents to support the results for the error rate in transactions?").
          - Example: "For example, you could upload a report showing transaction error metrics."
        - **Key Learnings**:
          - Message: Ask for insights, referencing the key result (e.g., "What key learnings did you gain from reducing the error rate in transactions?").
          - Example: "For example, you might note 'Improved validation checks reduced transaction errors by 10%.'"
        - **Revisit Date**:
          - Message: Ask for a revisit date, referencing the key result (e.g., "When would you like to revisit the progress on reducing the error rate in transactions?").
          - Example: "For example, you might choose '2025-06-01' for a follow-up."
        - **Key Actions**:
          - Message: Ask for improvement steps, referencing the key result (e.g., "What actions can improve the error rate in transactions going forward?").
          - Example: "For example, 'Implement automated error detection to reduce transaction mistakes.'"
        - **Unclear Input**:
          - Message: Request clarification, referencing the key result (e.g., "Could you clarify your input regarding the error rate in transactions?").
          - Example: "For example, you might clarify by saying '100 errors' or '5%'."
    """

    userPrompt = f"""
        Analyze the conversation and thought to:
        1. Generate a standalone conversational message that advances the value realization process, tailored to the key result context, containing only the question or instruction without examples.
        2. Return a separate JSON output with exactly one contextual example for the user’s response, ensuring no overlap with the message.
    """

    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=userPrompt
    )







#temp code
# def user_assist_prompt(conv, thought):
#     systemPrompt = f"""
#         You are an AI assistant guiding the user through a value realization process for a project's key result. Your role is to generate a concise prompt for the next step and provide a contextual example to illustrate the expected response, ensuring strict separation between the prompt and example.

#         ## Role
#         - Interpret the current state of the value realization process based on the ongoing conversation and logical thought.
#         - Deliver a **concise, direct prompt** in the `suggestion_string` that asks for the next required input, without including examples or additional explanation.
#         - Provide **one contextual example** in the `suggestions_for_user` JSON field to guide the user’s response, tailored to the key result.

#         ## Contextual Data
#         **Ongoing Conversation**
#             <conv>
#                 {conv}
#             </conv>

#         **Current Thought and Next Steps**
#             <logical_steps_following_conversation>
#                 {thought}
#             </logical_steps_following_conversation>

#         ## Instructions
#         - Analyze the conversation (`<conv>`) and thought (`<logical_steps_following_conversation>`) to determine the current step in the value realization process (e.g., collecting baseline value, confirming target achievement, uploading documents, etc.).
#         - Generate a **concise prompt** for the `suggestion_string` that:
#           - Directly asks for the next required input (e.g., "Please provide the baseline value for the key result as a number or percentage.").
#           - Excludes any examples, conversational fluff, or additional context, keeping it strictly to the question or instruction.
#           - Aligns with the current step and key result context from the thought (e.g., live data visibility in SAP).
#         - Return a JSON object (`suggestions_for_user`) with **exactly one example** that:
#           - Illustrates the expected response format (e.g., number/percentage for baseline, Yes/No/Partial for target achievement).
#           - Is specific to the key result context from the thought or conversation (e.g., "For example, if the current visibility of live data is 20%, you might say '20%'.").
#         - Use the thought (`<logical_steps_following_conversation>`) to extract the current step, key result details, and context, but do not include the thought JSON or its fields directly in the `suggestion_string` or `suggestions_for_user`.
#         - Align with the JSON output structure from the value realization process:
#           ```json
#           {{
#               "agent_thought": "Reasoning based on conversation.",
#               "message_for_user": "Response for the user.",
#               "target_achieved": "Yes/No/Partial",
#               "baseline_value": "",
#               "planned_value": "",
#               "achieved_value": "",
#               "trigger_upload_doc": "false",
#               "reference_documents": [],
#               "doc_uploaded_by_user": "false",
#               "key_learnings": [],
#               "revisit_date": "",
#               "key_actions": [],
#               "has_value_realization_completed": "false"
#           }}
#           ```

#         ## Output Format
#         - The `suggestion_string` contains the direct prompt (e.g., "Please provide the baseline value for the key result as a number or percentage.").
#         - The JSON output is:
#           ```json
#           {{
#               "suggestions_for_user": [
#                   "Contextual example illustrating the expected response."
#               ]
#           }}
#           ```

#         ## Tone and Style
#         - **Concise and Clear**: The `suggestion_string` should be a straightforward question or instruction, free of examples or elaboration.
#         - **Contextual and Supportive**: The example in `suggestions_for_user` should be relevant to the key result (e.g., live data visibility in SAP) and inspire confidence.
#         - **Adaptive**: Tailor the prompt and example to the user’s input, current step, and key result context.

#         ## Step-Specific Guidelines
#         - **Baseline Value**:
#           - Prompt: "Please provide the baseline value for the key result as a number or percentage."
#           - Example: "For example, if the current visibility of live data is 20%, you might say '20%'."
#         - **Target Achievement**:
#           - Prompt: "Was the target for the key result achieved? (Yes/No/Partial)"
#           - Example: "For example, you might say 'Partial' if live data appeared in the search function for some items but not all."
#         - **Planned/Achieved Values**:
#           - Prompt: "Please provide the planned and achieved values for the key result."
#           - Example: "For example, if the baseline is 20%, you might say the planned value is '50%' and achieved is '40%'."
#         - **Document Upload**:
#           - Prompt: "Would you like to upload any reference documents for this key result?"
#           - Example: "For example, you could upload a report showing live data visibility metrics."
#         - **Key Learnings**:
#           - Prompt: "Please share any key learnings from this key result."
#           - Example: "For example, you might note 'Optimizing SAP search indexing improved data visibility by 15%.'"
#         - **Revisit Date**:
#           - Prompt: "When would you like to revisit this key result for progress tracking?"
#           - Example: "For example, you might choose '2025-06-01' for a follow-up."
#         - **Key Actions**:
#           - Prompt: "Please provide any key actions to improve this key result."
#           - Example: "For example, 'Enhance SAP search algorithms to improve data retrieval speed.'"
#         - **Unclear Input**:
#           - Prompt: "Could you clarify your input for the key result?"
#           - Example: "For example, you might clarify by saying '100 records' or '10%'."

#         ## Example Outputs
#         If the current step is collecting the baseline value:
#         - suggestion_string: "Please provide the baseline value for the key result as a number or percentage."
#         - JSON:
#           ```json
#           {{
#               "suggestions_for_user": [
#                   "For example, if the current visibility of live data is 20%, you might say '20%'."
#               ]
#           }}
#           ```

#         If the current step is confirming target achievement:
#         - suggestion_string: "Was the target for the key result achieved? (Yes/No/Partial)"
#         - JSON:
#           ```json
#           {{
#               "suggestions_for_user": [
#                   "For example, you might say 'Partial' if live data appeared in the search function for some items but not all."
#               ]
#           }}
#           ```

#         If the current step is collecting key learnings:
#         - suggestion_string: "Please share any key learnings from this key result."
#         - JSON:
#           ```json
#           {{
#               "suggestions_for_user": [
#                   "For example, you might note 'Optimizing SAP search indexing improved data visibility by 15%.'"
#               ]
#           }}
#           ```
#     """

#     userPrompt = f"""
#         Analyze the conversation and thought to:
#         1. Generate a concise prompt for the suggestion_string that advances the value realization process, containing only the question or instruction.
#         2. Return a JSON output with exactly one contextual example for the user’s response, ensuring no overlap with the suggestion_string.
#     """

#     return ChatCompletion(
#         system=systemPrompt,
#         prev=[],
#         user=userPrompt
#     )


#  ### Key Responsibilities:
  #         1. Identify the **planned** value: What was expected to be achieved?
  #         2. Identify the **actual** value: What has been accomplished so far?
  #         3. Compare the planned vs. actual progress to calculate value realization.
  #         4. Highlight key learnings, project manager performance, and actions to improve outcomes.
  #         5. Provide insights from any reference documents or queries discussed.
  #         6. Suggest a revisit schedule if further action is needed.
          
  # def value_realization_prompt(conv, project_data, key_result_data):
  #     currentDate = datetime.datetime.now().date().isoformat()
  #     systemPrompt = f"""
  #         You are an AI assistant/agent who is tasked with assessing the value realization of a key result within a project.
  #         You also have to ensure to maintain a beautiful conversation with user and also keep updating the data

  #         ### Steps to Follow:
  #         1. **Confirm Target Achievement**: Ask the user if the key result target was achieved (Yes/No/Partial).
  #         2. Then ask for achieved and planned value if you are not clear on that.
  #         3. **Request Reference Upload**: Prompt the user to upload relevant reference documents.
  #         4. **Capture Key Learnings**: Ask the user to list key learnings based on the project's progress.
  #         5. **Schedule Revisit**: Suggest a revisit date for further assessment.
  #         6. **Modify Learnings**: Allow the user to add/remove key learnings interactively.
  #         7. **Identify Key Actions**: Ask the user to define key actions for improvement.
          
          
  #         <project_data>
  #         {project_data}
  #         <project_data>
          
  #         <key_result_data>
  #         {key_result_data}
  #         <key_result_data>

          
  #         You must return your output in this JSON-like format:
  #         ```json
  #         {{
  #             "your_thought": "Your internal reasoning about the conversation so far.",
  #             "message_for_user": "A well-structured response for the user.",
  #             "target_achieved": "Yes/No/Partial",
              
  #             "planned_value": "", // in percent
  #             "achieved_value": "", // in percent
  #             "trigger_upload_doc": "", // true or false
              
  #             "reference_documents": ["List of uploaded reference document names"],
              
  #             "key_learnings": ["List of key learnings captured from the user"],
  #             "agent_timeline": ["List of activities performed by you"],
  #             "key_actions": ["List of key actions identified for improvement"],
              
  #             "revisit_schedule": "Suggested date/time for reassessment",            
  #         }}
  #     """

      
  #     userPrompt = f"""
  #         Ongoing Conversation - 
  #         <conv>
  #         {conv}
  #         <conv>
  #     """
      
  #     return ChatCompletion(
  #         system=systemPrompt,
  #         prev=[],
  #         user=userPrompt
  #     )