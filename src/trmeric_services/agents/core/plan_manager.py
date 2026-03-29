from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.agents.core import AgentRegistry, BaseAgent
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
import traceback
from src.trmeric_services.agents.prompts import primary_agent_prompt

class PlanManager:
    def __init__(self, agent_registry: AgentRegistry, base_agent: BaseAgent, log_info=None):
        self.llm = ChatGPTClient()
        self.log_info = log_info
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0
        )
        self.agent_registry = agent_registry
        self.base_agent = base_agent

    def generate_blueprint(self):
        """
        Generates a blueprint from the user query by prompting the LLM with agent and function descriptions.
        """
        try:
            agent_descriptions = self._build_agent_descriptions(detailed=True)

            llm_prompt = f"""
            
            The user's conversation can be seen below:\n\n{self.base_agent.conversation.format_conversation()}
            The most recent message is at the bottom and is the latest user query. You can use the rest of the messsage as context if it helps.
    
    
            Available agents and their functions:
            {agent_descriptions}

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


            Please return the output in the following JSON format:
            ```json
            {{
                "thought_process": "",  // updated thought process
                "chain_of_agents": [
                    {{
                        "agent": "<agent_name>", // The agent to use
                        "function": "<function_name>", //  The function to call on the agent
                        "args": <arguments>,// Arguments (if applicable)
                    }}
                ]
            }}
            ```
            """
            
            print("debug -- llm prompt ", llm_prompt)
            
            prompt = ChatCompletion(
                system="",
                prev=[],
                user=llm_prompt
            )


            plan_text = self.llm.run(prompt, options=self.modelOptions, logInDb=self.log_info)
            print("Plan generation response:", plan_text)

            return extract_json_after_llm(plan_text)

        except Exception as e:
            print("Error in generate_blueprint:", e, traceback.format_exc())
            return []
    
    def determine_primary_agent(self, user_context):
        try:
            agents=self._build_agent_descriptions()
            llm_prompt = primary_agent_prompt(conv=self.base_agent.conversation.format_conversation(), user_context=user_context, agents=agents)
            primary_agent_response = self.llm.run(self._generate_primary_agent_prompt(user_context), self.modelOptions , 'agent::determine_primary_agent', self.log_info)
            result = extract_json_after_llm(primary_agent_response)
            primary_agent_name = result.get("primary_agent", '')
            self.primary_agent = self.agent_registry.get_agent(agent_name=primary_agent_name)
        except Exception as e:
            print("error determine_primary_agent", e, traceback.format_exc())
    
    def _build_agent_descriptions(self, detailed: bool = False) -> str:
        """
        Builds a description of all agents and optionally their functions.

        :param detailed: Whether to include function details in the descriptions.
        :return: A string containing descriptions of all agents and their functions (if detailed=True).
        """
        try:
            descriptions = []
            for agent_name, agent_class in self.agent_registry.get_all_agents().items():
                agent_desc = f"Agent: {agent_name}\n{agent_class.description}"
                if detailed:
                    for func in agent_class.functions:
                        agent_desc += f"\n  - Function: {func.name} | Description: {func.description}"
                        agent_desc += f"\n    Output reference: <{agent_name}.{func.name}_output>"
                descriptions.append(agent_desc)
            return "\n".join(descriptions)
        except Exception as e:
            self.log_info.error("Error building agent descriptions", {"error": str(e), "traceback": traceback.format_exc()})
            return ""
