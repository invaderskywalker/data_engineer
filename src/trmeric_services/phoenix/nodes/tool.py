# src/trmeric_services/phoenix/nodes/tool.py
from .web_search import WebSearchNode
from .internal_data import InternalDataNode
from .internal_actions import InternalActionNode
from .knowledge import KnowledgeNode
from .knowledge_graph import KnowledgeGraphNode
from ..prompts import *
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.core import  BaseAgent

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
from typing import Dict, List, Any
from datetime import datetime
from src.trmeric_utils.knowledge.KnowledgeAgent import KnowledgeAgent
from src.trmeric_database.dao import TangoDao
from ..constants import *
from ..utils import PhoenixUtils




class ToolNode:
    def __init__(self, base_agent: BaseAgent, network_data={}, agent_name="" ):
        self.network_data = network_data
        self.web_search_node = WebSearchNode(network_data=network_data)
        self.internal_data_node = InternalDataNode(network_data=network_data, agent_name=agent_name)
        self.interna_actions = InternalActionNode(network_data=network_data)
        self.knowledge_node = KnowledgeNode(network_data=network_data)
        self.knowledge_graph_node = KnowledgeGraphNode(network_data=network_data, base_agent=base_agent)
        self.socketio = network_data.get("socketio")
        self.client_id = network_data.get("client_id")
        self.log_info = network_data.get("log_info", {})
        self.base_agent = base_agent
        self.analysis_and_results = ""
        self.analysis = ""
        self.analysis_results = ""
        self.lock = threading.Lock()
        self.steps = []
        self.step_timeline_key = []
        self.check_is_enough = False
        self.agent_name = agent_name
        self.AgentPromptClass = DataAnalysisAgentPrompt
        self.context= self.base_agent.org_info_string + "\n\n"+ self.base_agent.context_string + "\n\n" + self.base_agent.integration_info_string +"\n\n" + self.base_agent.user_info_string
        if self.agent_name == ORION_PLANNING:
            self.AgentPromptClass = PlanningAgentPrompts
            self.check_is_enough = False
            self.context= self.base_agent.org_info_string 
        if self.agent_name == ORION_SOLUTIONING:
            self.AgentPromptClass = SolutioningAgentPrompts
            self.check_is_enough = False
        # self.context= self.base_agent.org_info_string + "\n\n"+ self.base_agent.context_string + "\n\n" + self.base_agent.integration_info_string +"\n\n" + self.base_agent.user_info_string
        print("initiated ToolNode -- ", self.agent_name)

        
    def sendSteps(self, key, val):
        if (key not in self.step_timeline_key) and val:
            return 
        
        self.socketio.emit("custom_agent_v1_ui", 
            {
                "event": "timeline", "data": {"text": key, "key": key, "is_completed": val}
            }, 
            room=self.client_id
        )
        self.steps.append({
            "event": "timeline", "data": {"text": key, "key": key, "is_completed": val}
        })
        self.step_timeline_key.append(key)
        
    
    def run(self, query=None):
        query = query or self.base_agent.conversation.last_user_message() or ""
        conv = self.base_agent.conversation.format_conversation(name="Orion")
        
        step = 1
        self.runSingle(conv=conv, query=query, step=step)
        if PhoenixUtils.checkIfAgentSwitch(session_id=self.log_info.get("session_id"), user_id=self.log_info.get("user_id")):
            self.check_is_enough = False
        if self.check_is_enough:
            self.sendSteps(key="Validating", val=False)
            is_enough_json = self._is_enough(conv, user_query=query, analysis=self.analysis, analysis_data=self.analysis_results)
            self.sendSteps(key="Validating", val=True)
            print("is_enough_json --- ", is_enough_json)
            is_enough = is_enough_json.get("is_enough", True) or True
            while not is_enough:
                step+=1
                self.runSingle(conv=conv, query=query, step=step)
                is_enough = is_enough_json.get("is_enough", True) or True
        return self.analysis, self.analysis_results
            

    def runSingle(self, conv, query=None, step=0):
        """Processes the query step-by-step using LLM to decide actions."""
        self.sendSteps("Thinking", False)
        if not query:
            return
        
        prompt = self.AgentPromptClass.queries_split_prompt(
            conv, 
            query=query, 
            analysis=self.analysis, 
            analysis_results = self.analysis_results,
            extra=self.context
        )
        query_split_response = self.base_agent.llm.run(
            prompt, 
            self.base_agent.modelOptions , 
            'agent::queries_split_prompt', 
            self.log_info
        )
        print("all_queries_to_think", step,  query, query_split_response)

        all_queries_to_think = extract_json_after_llm(query_split_response)
        # print("all_queries_to_think", step,  query, all_queries_to_think)
        all_queries_to_think = all_queries_to_think.get("all_queries_to_think")
        # query_split_response = {
        #     "all_queries_to_think": [query]
        # }
        # all_queries_to_think = [query]

        intent = self._analyze_intent_v2(
            conv, 
            user_latest_query=query, 
            queries=all_queries_to_think,
            analysis=self.analysis, 
            analysis_results = self.analysis_results
        )
        print("debug intent -- ", datetime.now())
        print(json.dumps(intent, indent=2))
        
        self.sendSteps("Thinking", True)
        
        with self.lock:
            self.analysis += f"""
                ---
                The user's query is: {query}. 
                User experience can be enahnced if the data 
                can be collected on multiple aspects and presented to user.
                For that you have created: {query_split_response} 
                ---
            """
            self.analysis += f"""
                Now, after creation of multiple queries.
                Thought and Next steps:
                {intent}
                --------
            """
            
        # self.sendSteps("Gathering Data", False)
        
        nodes = intent.get("nodes", {})
        if nodes:
            self._process_node_v2(conv, nodes)
        

        self.sendSteps("Web Search", True)
        self.sendSteps("Deciding Actions", True)
        self.sendSteps("Internal Data Getter", True)
        self.sendSteps("Knowledge", True)
        # self.sendSteps("Gathering Data", True)
        self.sendSteps("Switching Agent", True)
        
    
    def _analyze_intent_v2(self, conv,  user_latest_query, queries, analysis=None, analysis_results = None) -> dict:
        """Uses LLM to decide the next node and parameters."""
        context = self.context
        prompt = self.AgentPromptClass.stepwise_blueprint_prompt_v2(
            conv,
            user_latest_query,
            queries,
            context,
            analysis=analysis,
            analysis_results=analysis_results
        )
        response = self.base_agent.llm.run(
            prompt, 
            self.base_agent.modelOptions , 
            'agent::_analyze_intent_v2', 
            self.log_info
        )
        # print("debug _analyze_intent ", prompt.formatAsString())
        # print("debug _analyze_intent output ", response)
        try:
            response = extract_json_after_llm(response)
            return response
        except Exception as e:
            return {
                "thought_process": "",
                "nodes": {}
            }
            



    def _process_node_v2(self, conv, nodes: Dict) -> None:
        """Processes all nodes in parallel based on the new intent structure."""
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            
            # Internal Actions Node (list of configs)
            if "activate_other_agent" in nodes:
                internal_action_configs = nodes.get("activate_other_agent", [])
                for config in internal_action_configs:
                    
                    function_name = config.get("agent_name", "")
                    self.sendSteps("Switching Agent", False)
                    # params = config.get("params", {})
                    if function_name:
                        print("⚡⚙️ Triggering Agent: ", function_name)
                        futures.append(
                            executor.submit(self._run_other_agent, function_name)
                        )

            # Web Search Node (single config)
            if "web_search" in nodes:
                web_search_config = nodes.get("web_search", {})
                web_queries = web_search_config.get("web_queries", [])
                if web_queries:
                    print("🌍🔍 Scheduling Web Search Agent for Queries: ", web_queries)
                    self.sendSteps("Web Search", False)
                    futures.append(
                        executor.submit(self._run_web_search, web_queries)
                    )


            # Knowledge Graph Node
            if "knowledge_graph" in nodes:
                knowledge_graph_configs = nodes.get("knowledge_graph", [])
                query = knowledge_graph_configs.get("query", "")
                if query:
                    self.sendSteps("Knowledge Graph Query", False)
                    print("📊 Scheduling Knowledge Graph Query: ", query)
                    futures.append(
                        executor.submit(self._run_knowledge_graph, knowledge_graph_configs)
                    )
                    
            # Internal Data Getter Node (list of configs)
            if "internal_data_getter" in nodes:
                internal_data_configs = nodes.get("internal_data_getter", [])
                for config in internal_data_configs:
                    self.sendSteps("Internal Data Getter", False)
                    function_name = config.get("function", "")
                    params = config.get("params", {})
                    if function_name:
                        print("🌐📊 Scheduling Data Getter Agent: ", config)
                        futures.append(
                            executor.submit(self._run_internal_data, config)
                        )

            # Internal Actions Node (list of configs)
            if "internal_actions" in nodes:
                internal_action_configs = nodes.get("internal_actions", [])
                for config in internal_action_configs:
                    self.sendSteps("Deciding Actions", False)
                    function_name = config.get("function", "")
                    params = config.get("params", {})
                    if function_name:
                        print("⚡⚙️ Scheduling Action Agent: ", config)
                        futures.append(
                            executor.submit(self._run_internal_action, config)
                        )
                        
            # Knowledge Node
            if "knowledge" in nodes:
                knowledge_configs = nodes.get("knowledge", [])
                for config in knowledge_configs:
                    self.sendSteps("Knowledge", False)
                    params = config.get("params", {})
                    print("🧠📚 Scheduling Knowledge Agent: ", config)
                    futures.append(
                        executor.submit(self._run_knowledge, config)
                    )

            # Collect results from all threads
            for future in as_completed(futures):
                try:
                    node_type, config, result = future.result()
                    print("debug ---- future ", node_type, config)
                    with self.lock:
                        if node_type == "internal_data_getter":
                            self.analysis_results += f"""
                                -----------
                                node::{node_type} function::{config.get("function")}
                                output :: 
                                {result}
                                -----------
                            """
                        else:
                            self.analysis_results += f"""
                                -----------
                                {node_type} node output: {result}
                                -----------
                            """
                except Exception as e:
                    print(f"Error processing node: {e}")

    def _run_knowledge_graph(self, config: Dict) -> tuple:
        """Helper to run knowledge graph query."""
        print("_run_knowledge_graph ", config)
        result = self.knowledge_graph_node.run(intent=config)
        return "knowledge_graph", config, result
    
    def _run_other_agent(self, function_name) -> tuple:
        """Helper to run other agent."""
        tenant_id = self.log_info.get("tenant_id")
        user_id = self.log_info.get("user_id")
        session_id = self.log_info.get("session_id")
        key = AGENT_INITIATE_SWITCH_OCCURED
        value = function_name
        TangoDao.insertTangoState(tenant_id, user_id, key, value, session_id)
        key = CURRENT_ACTIVE_AGENT
        TangoDao.insertTangoState(tenant_id, user_id, key, value, session_id)
        return "activate_other_agent", function_name, f"Switching to {function_name} agent"
    
    def _run_web_search(self, web_queries: List[str]) -> tuple:
        """Helper to run web search and return result with node type."""
        result = self.web_search_node.run(sources=web_queries)
        return "web_search", web_queries, result

    def _run_internal_data(self, config: Dict) -> tuple:
        """Helper to run internal data getter and return result with node type."""
        result = self.internal_data_node.run(intent=config)
        return "internal_data_getter", config, result

    def _run_internal_action(self, config: Dict) -> tuple:
        """Helper to run internal action and return result with node type."""
        result = self.interna_actions.run(intent=config)
        return "internal_actions", config, result
    
    def _run_knowledge(self, config: Dict) -> tuple:
        """Helper to run knowledge node and return result with node type."""
        result = self.knowledge_node.run(intent=config)
        return "knowledge", config, result
    
    
    def _is_enough(self, conv, user_query, analysis, analysis_data):
        prompt = self.AgentPromptClass.is_enough_prompt(
            conv=conv, 
            query=user_query,
            analysis=analysis,
            analysis_results=analysis_data
        )
        response = self.base_agent.llm.run(
            prompt, 
            self.base_agent.modelOptions , 
            'agent::_is_enough', 
            self.log_info
        )
        try:
            response = extract_json_after_llm(response)
            return response
        except Exception as e:
            return True

