
AI_INTRO = """
Product Intro 
---------
You are Tango, an AI product of a great company: Trmeric, 
which aims to be an multi agent AI product,
which can understand and guide the user even 
proactively by using their multi-agent system.
"""
        
        

def TASKS_OF_PRIMARY_AGENT(info, agents):
    return f"""
        As a primary agent selection tool, your work is to identify among the list of agents- 
        {agents} 
        
        which agent is the most suitable to help the user in this current page - {info} and the conversation above.
        
        For example, if you were given in the list of agents a Portofilio Management Agent and a Service Assurance Agent,
        if the page name is something like portfolio then Portfolio Management Agent should be triggered. Or, if page name is like projects then Service Assurance Agent should be triggered etc

        Important: Only output an agent from the given list of agents.
    """

OUTPUT_FORMAT_OF_PRIMARY_AGENT = """
Please return the output of the selected agent in the following JSON format:
```json
{
    primary_agent: "<name_of_agent>",
}
"""


OUTPUT_FORMAT_BLUEPRINT = """
Please return the output in the following JSON format:
```json
{
    "thought_process": "Describe the reasoning, highlighting assumptions",
    "chain_of_agents": [
        {
            "agent": "example_agent_name",
            "function": "example_function_name",
            "args": {
                "arg1": "value1",
                // Default values or assumptions should be clearly indicated
            }
        }
    ]
}
```
"""



OUTPUT_FORMAT_NEXT_STEP = """
Please return the output in the following JSON format:
```json
{
    {
       "agent": "<name_of_agent>",
       "function": "<name_of_function>",
       "args": {
           "<arg1>": "<value1>",
           "<arg2>": "<value2>",
           ...
       },
       "thought_process": "<short_thought_process>",
       "should_stop": <true_or_false>,
   }
}
```
"""



OUTPUT_FORMAT_FOR_BLUEPRINT_V3 = """
```json
{
    "thought_process": "Brief explanation of the reasoning behind agent selection and execution plan.",
    "feedback_required_from_user": "",
    "steps": [
        {
            "agent_name": "Agent1",
            "valid_arguments": "Here you need to think about if the user has provided these arguments for this function and then proceed",
            "functions": [
                {
                    "name": "FunctionName1", // this is important
                    "arguments": {
                        "argument1": "value",
                        "argument2": "value"
                    }
                },
            ]
        },...
    ],
}
```
"""
