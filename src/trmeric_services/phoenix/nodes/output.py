from src.trmeric_services.agents.core import  BaseAgent
from ..prompts import *
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from ..constants import *


class OutputNode:
    def __init__(self, base_agent: BaseAgent, network_data={}, agent_name=""):
        self.socketio = network_data.get("socketio")
        self.client_id = network_data.get("client_id")
        self.log_info = network_data.get("log_info", {})
        self.base_agent = base_agent
        self.agent_name = agent_name
        self.AgentPromptClass = DataAnalysisAgentPrompt
        if self.agent_name == ORION_PLANNING:
            self.AgentPromptClass = PlanningAgentPrompts
        if self.agent_name == ORION_SOLUTIONING:
            self.AgentPromptClass = SolutioningAgentPrompts
    
    def word_count(self, text):
        try:
            return len(text.split())
        except Exception as e:
            return 0
        
    def run(self, conv, query, data, analysis):
        # prompt = self.AgentPromptClass.output_prompt(
        #     conv=conv, 
        #     query=query, 
        #     data=data,
        #     analysis=analysis,
        #     extra=self.base_agent.org_info_string + "\n\n" + self.base_agent.user_info_string
        # )
        # print("output node promopt --- ", self.word_count(prompt.formatAsString()))
        
        # data = SummarizerService({
        #     "tenant_id": self.log_info.get("tenant_id"),
        #     "user_id": self.log_info.get("user_id")
        # }).summarizer(
        #     data, 
        #     f"""
        #     This data is obtained by using the thought: {analysis}.
        #     Extract all key points and a general understanding of this data and always keep the thought in mind.
        #     """,
        #     "chat"
        # )
        
        prompt = self.AgentPromptClass.output_prompt(
            conv=conv, 
            query=query, 
            data=data,
            analysis=analysis,
            extra=self.base_agent.org_info_string + "\n\n" + self.base_agent.user_info_string
        )
        print("final input prompt --- ", prompt.formatAsString())
        # print("output node promopt --- ", prompt.formatAsString())
        
        res = "" 
        for chunk in self.base_agent.llm.runWithStreaming(
            prompt, 
            self.base_agent.modelOptions41, 
            'agent::OutputNode::run', 
            self.log_info
        ):
            res += chunk
            yield chunk
            
        print("fianl Output -- ", res)
            
            
    def runMini(self,  query, analysis, response):
        prompt = self.AgentPromptClass.output_prompt_mini(
            query=query, 
            analysis=analysis,
            response=response
        )

        for chunk in self.base_agent.llm.runWithStreaming(
            prompt, 
            self.base_agent.modelOptions, 
            'agent::OutputNode::mini::run', 
            self.log_info
        ):
            yield chunk