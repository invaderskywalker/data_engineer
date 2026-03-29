from typing import Dict, List, Optional, get_origin, get_args
from src.api.logging.AppLogger import appLogger, debugLogger
from .steps_sender import SocketStepsSender
from src.database.dao import FileDao
from src.ml.llm.models.OpenAIClient import ChatGPTClient
from src.ml.llm.Types import ModelOptions, ChatCompletion
from .data_getters import DataGetters
from .actions import DataActions
from .context_builder import ContextBuilder
from datetime import datetime
from src.database.dao import TenantDaoV2, TangoDao
from src.utils.json_parser import extract_json_after_llm
from ..helper.common import MyJSON
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import re
from src.trmeric_services.agents.functions.roadmap_analyst.queries import get_recent_queries
from ..helper.decorators import log_function_io_and_time
from ..helper.event_bus import Event, event_bus
from src.ws.static import TangoBreakMapUser
from .func_utils import fetch_function_defaults, fetch_function_definitions

from src.trmeric_services.agents.reports.customers.pf.monthly_savings import (
    monthly_savings_report_with_graph_prompt
)
from src.trmeric_services.agents.functions.roadmap_analyst.response_prompts import create_transformation_report_prompt, portfolio_snapshot_prompt, performance_snapshot_prompt, business_value_report_prompt, risk_report_prompt

# Constants
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_TOKENS = 10000
DEFAULT_TEMPERATURE = 0.1
MIN_BUFFER_SIZE = 30
MAX_WORKERS = 4

DEFAULT_MODE_ACTIONS = ["generate_template_file"]


class BaseAgent:
    """Base agent class for handling queries with configurable prompts, data sources, and actions."""
    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        config: Dict,
        socketio=None,
        client_id=None,
        base_agent=None,
        session_id=None,
        agent_name=""
    ):
        self.name = agent_name
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.socketio = socketio
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.modelOptions = ModelOptions(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE
        )
        self.plans = []
        self.client_id = client_id
        self.base_agent = base_agent
        self.session_id = session_id
        self.log_info = {"tenant_id": tenant_id, "user_id": user_id, "session_id": session_id}
        self.config = config
        self.socket_sender = SocketStepsSender(agent_name, socketio, client_id)
        
        self.data_getters = DataGetters(
            tenant_id, 
            user_id, 
            agent_name, 
            metadata={
                "base_agent": base_agent,
                "session_id": session_id,
                "llm": self.llm
            }
        )    
        self.data_actions = DataActions(
            tenant_id, 
            user_id, 
            agent_name, 
            session_id=self.session_id,
            socketio=socketio
        )
        self.context_builder = ContextBuilder(
            tenant_id, 
            user_id, 
            data_getter_cls=self.data_getters, 
            base_agent=self.base_agent,
            agent_name=agent_name
        )  
        self.user_context = self.context_builder.build_context(agent_name)
        debugLogger.info({"function": "BaseAgent_init", "tenant_id": tenant_id, "user_id": user_id})
        if socketio:
            socketio.emit("agentic_timeline", {"event": "show_timeline", "agent": agent_name}, room=client_id)
            
        self.res = ""
        self.buffer = ""
        self.done_response = False
        self.recent_queries = get_recent_queries(user_id=self.user_id, limit = 20)
        def _on_step_event(event: Event):
            print("on step update ", event.type)
            if event.type == 'STEP_UPDATE':
                payload = event.payload
                msg = payload.get('message')
                if msg and socketio:
                    self.socket_sender.sendSteps(msg, False)

        self._step_callback = _on_step_event  # Keep ref to unsubscribe later if needed
        self._namespaced_step_type = event_bus.subscribe(
            'STEP_UPDATE', 
            session_id=self.session_id,
            callback=self._step_callback
        )
        
        def _on_response_callnback(event: Event):
            print("_on_response_callnback ", event.type)
            if event.type == 'SEND_DIRECT_RESPONSE':
                payload = event.payload
                msg = payload.get('message')
                if msg and socketio:
                    self.buffer += msg
                    self.res += msg
                    self.done_response = True

        self._on_response_callnback = _on_response_callnback
        event_bus.subscribe(
            "SEND_DIRECT_RESPONSE",
            session_id=self.session_id,
            callback=self._on_response_callnback
        )
        self.event_bus = event_bus
        
        
    def _fetch_fn_defs(self, fns: List[str], _type: str = 'getter') -> str:
        """
        Fetches function definitions for the specified functions.
        
        Args:
            fns (List[str]): List of function names.
            _type (str): Type of functions ('getter' or 'action').
        
        Returns:
            str: Function definitions joined by a separator.
        """
        fn_map = self.data_getters.fn_maps if _type == 'getter' else self.data_actions.fn_maps
        return fetch_function_definitions(fn_map, fns)

    def _fetch_fn_defaults(self, fns: List[str], _type: str = 'getter') -> Dict:
        """
        Fetches default parameter values for the specified functions.
        
        Args:
            fns (List[str]): List of function names.
            _type (str): Type of functions ('getter' or 'action').
        
        Returns:
            Dict: Dictionary mapping function names to their default values.
        """
        fn_map = self.data_getters.fn_maps if _type == 'getter' else self.data_actions.fn_maps
        defaults = fetch_function_defaults(fn_map, fns)
        # print("_fetch_fn_defaults ", MyJSON.dumpsV2(defaults))
        return defaults
        

    @log_function_io_and_time
    def _construct_planning_prompt(self, query , mode = 'default'):
        """Constructs the planning prompt for query processing."""
        current_date = datetime.now().date().isoformat()
        conv = self.base_agent.conversation.format_conversation(self.name) if self.base_agent else "No prior conversation."
        # tenant_type = TenantDao.checkCustomerType(self.tenant_id)
        available_data_sources = self.config.get("available_data_sources") or []
        data_sources_defs = self._fetch_fn_defs(available_data_sources)
        
        # Get default parameters (LLM will fill in actual values based on context)
        data_sources_defaults = self._fetch_fn_defaults(available_data_sources)
        
        available_actions = self.config.get("available_actions", [])
        actions_defs = self._fetch_fn_defs(available_actions, _type="action")
        
        # Get default action parameters (LLM will fill in actual values based on context)
        actions_defaults = self._fetch_fn_defaults(available_actions, _type="action")

        
        role = self.config.get("agent_role") or "No role defined for this agent"
        user_intents_classes = self.config.get("user_intents_classes") or {}
        additional_info = self.config.get("additional_info") or ""
        llm1_plan_output_structure = self.config.get("llm1_plan_output_structure") or {}
        decision_process = self.config.get("decision_process") or ""
        
        # print("debug -- conv -- ", conv)
        # IMPROVED PLANNING PROMPT
        system_prompt = f"""You are a planning assistant responsible for analyzing user queries and determining the appropriate data sources and actions to execute.

            ## Context
            **Current Date:** {current_date}
            **Agent Role:** {role}

            ### Conversation History
            {conv if conv != "No prior conversation." else "This is the start of a new conversation."}

            ### User Context
            {self.user_context}
            
            
            {decision_process}
            
            ## important for onboarding
            see if comapny website url or company name is present in the company info, 
            also see if his/her designation is present: 
            then make a judgement if he/she is a new user
            and also include this assesment in the planning_rationale.

            ## Your Task
                Analyze the user query and also look at last user messages to understand the context and create an execution plan by:
                1. Classifying the user's intent
                2. Selecting appropriate data sources to query
                3. Determining necessary actions to perform
                4. Providing clear rationale for your choices
                5. the plan created should be thoughtful, also connecting to the previous messages

            ## Available Resources

                ### Intent Classifications
                    The user's query should be classified into one or more from these intents:
                    options - {', '.join(user_intents_classes.keys())}
                    Chain of thought for these intents
                    ----
                    {MyJSON.dumps(user_intents_classes, indent=2)}
                    ----

                ### Data Sources
                    Properly utilize this available data sources.
                    Data source available with their descriptions:
                    {data_sources_defs}

                    Default parameters for data sources (<DEFAULT_PARAMS_FOR_DATA_SOURCES>):
                        {MyJSON.dumpsV2(data_sources_defaults, indent=2)}

                ### Actions
                    Available actions and their descriptions:
                    {actions_defs}

                    Default parameters for actions (<DEFAULT_PARAMS_FOR_ACTIONS>):
                        {MyJSON.dumpsV2(actions_defaults, indent=2)}
                
                
                Additional Info:
                {additional_info}

                ## Instructions
                    1. Analyze the user query carefully
                    2. Select ONLY the necessary data sources and actions - avoid redundant calls
                    3. If a function needs to be called multiple times with different parameters, include it multiple times in the array
                    4. Ensure all required parameters are specified correctly
                    5. Provide clear rationale explaining your planning decisions

            ## Output Format
            You MUST respond with a valid JSON object in exactly this format:

            {llm1_plan_output_structure}

            ## Important Notes
                - If user context is missing company_name, company_website, or designation, mark them under missing_fields.
                - In the response JSON: only output the keys which are non null
                - Only include data sources from: {available_data_sources}
                - Only include actions from: {available_actions}
                - Ensure all parameter values are appropriate for the user's specific query
                - If clarification is needed, set "clarification_needed": true and include a "clarification_message"
        """

        user_message = f"""
            Please analyze and create an execution plan for the following user query:
            User Query: "{query}"
            Remember to:
            - Apply decision process first (e.g., check for vague queries, new user).
            - If clarification needed, return a plan with clarification prompts.
            - Otherwise, classify intent and select resources.
            - Focus on addressing the specific query
            - Output valid JSON per the specified format.
            - Include params for all sources/actions triggered.
            
            Most important is to also write the same source or action params if you are initiating the sources or actions
        """

        chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_message)
        # print("chat completion -- ", chat_completion.formatAsString())
        # return chat_completion
        
        prompt = chat_completion
        response = self.llm.run(
            prompt,
            ModelOptions(model=DEFAULT_MODEL, max_tokens=5000, temperature=DEFAULT_TEMPERATURE), 
            f'{self.name}::master::plan', 
            logInDb=self.log_info
        )
        print("response ----", response)
        plan = extract_json_after_llm(response)

        # if any(action for action in list(plan.get("actions_to_trigger_with_action_params").keys()))  in DEFAULT_MODE_ACTIONS:
        #     mode = "only_data"
        return plan,mode

    def process_combined_query(self, query: str, response_mode='default'):
        """Processes a query by planning, executing, and generating a response."""
        appLogger.info({"function": "process_combined_query_start", "tenant_id": self.tenant_id, "user_id": self.user_id, "query": query})
        # self.socket_sender.sendSteps("Starting analysis", False)
        
        import json
        TangoDao.insertTangoState(
            tenant_id=self.tenant_id, 
            user_id=self.user_id, 
            key="query_history", 
            value=json.dumps({"query": query}), session_id=self.session_id
        )
        
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Creating execution plan"},
            session_id=self.session_id
        )

        plan,response_mode = self._construct_planning_prompt(query, mode = response_mode)
        print("--debug _construct_planning_prompt-------- MODE: ", response_mode)
        TangoDao.insertTangoState(
            tenant_id=self.tenant_id, 
            user_id=self.user_id, 
            key=f"{self.name}_planning", 
            value=MyJSON.dumps(plan), 
            session_id=self.session_id
        )
        
        self.plans.append({
            "agent": self.name,
            "step": "blueprint_step",
            "plan": plan
        })
        
        
        # self.socket_sender.sendSteps("Planning your request", False)
        
        results = self.execute_plan(plan=plan)
        if response_mode == "only_data":
            self.socketio.emit('trucible_agent',{'event':'only_data_render','data': results},room=self.client_id)
            yield results
            return
        
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': "Preparing response"},
            session_id=self.session_id
        )
        
        # Generate response using improved prompt
        current_date = datetime.now().date().isoformat()
        conv = self.base_agent.conversation.format_conversation(self.name) if self.base_agent else "No prior conversation."
        user_intents_classes = self.config.get("user_intents_classes") or {}
        role = self.config.get("agent_role") or "No role defined for this agent"
        agent_name = self.config.get("agent_name") or "Tango"
        additional_info = self.config.get("additional_info") or ""
        user_cta_instructions = self.config.get("user_cta_instructions") or ""
        
        intents = plan.get('user_intents') or []
        intents_responses = []
        for i in intents:
            intents_responses.append({
                "intent": i,
                "intent_thought_process_and_response_structure": user_intents_classes.get(i) or ""
            })
        
        desired_expert_role_for_agent_for_output_presentation = plan.get("desired_expert_role_for_agent_for_output_presentation") or None
        role_statement = ''
        if desired_expert_role_for_agent_for_output_presentation:
            role_statement = f"""
                ###### important ######
                <desired_expert_role_for_agent_for_output_presentation_and_tone>
                To present the response in the best way possible you are assigned this role:
                {desired_expert_role_for_agent_for_output_presentation}
                
                you have to stick to this role for answer presentation and tone setting
                </desired_expert_role_for_agent_for_output_presentation_and_tone>
                ################
                
            """
        
        # IMPROVED RESPONSE GENERATION PROMPT
        system_prompt = f"""
            You are {agent_name}, an analytical and professional AI assistant created by Trmeric.

            ## Your Identity
                - **Name:** {agent_name}
                - **Created by:** Trmeric
                - **Current Role:** {role}
                - **Date:** {current_date}
                {role_statement}

            ## Context

                ### User Query
                {query}

                ### Conversation History
                {conv if conv != "No prior conversation." else "This is the start of a new conversation."}

                ### Context
                {self.user_context}

                ### Execution Plan
                The system analyzed your query and executed the following plan:
                {MyJSON.dumps(plan, indent=2)}

                ### Execution Results
                <execution_results>
                {MyJSON.dumps(results, indent=2)}
                </execution_results>
                
                
                Additional Info for better response creation:
                {additional_info}

            ## Response Guidelines

                ### Intent-Based Response Strategy
                    Based on the classified intents "{plan.get('user_intents')}", 
                    follow these guidelines:
                    --------------
                    {MyJSON.dumps(intents_responses)}
                    --------------

                ### Core Principles
                    1. **Accuracy First:** Only present information from the execution results. Never fabricate data.
                    2. **Direct & Concise:** Address the query directly in 25-50 words for simple responses.
                    3. **Professional Tone:** Maintain a friendly yet professional demeanor.
                    4. **Transparency:** If data is missing or unavailable, clearly state this.
                    5. **Action Awareness:** Inform the user about actions performed on their behalf.
                    6. **web source awareness:** Clearly state the web sources in the response of the websources used like the urls

                ### Formatting Rules
                    - Start with a clear, engaging header using markdown (# with an appropriate emoji)
                    - Use structured formatting (lists, tables) when presenting multiple data points
                    - Keep language simple and avoid unnecessary jargon
                    - For lists: use numbered format and include all relevant items

                ### Constraints
                    - DO NOT hallucinate or invent data
                    - DO NOT provide random links or references
                    - DO NOT make assumptions about missing data
                    - DO NOT use complex technical terminology unless necessary
                    - ALWAYS acknowledge if requested information is unavailable
        """

        user_prompt = f"""
            Generate a response for the following query:
            **Query:** {query}

            Requirements:
                1. Begin with a meaningful header (H1 markdown with relevant emoji)
                2. Provide a direct, accurate answer based solely on the execution results
                3. If listing items, use numbered format and include all available items
                4. Acknowledge any limitations or missing data honestly
                5. Convert all technical fields to readable labels
                5. Keep the response focused and relevant to the specific question  
                6. Always be mindful of my proper onboarding    
                7. Optimize way of presenting until asked to list full, use table/list which u find best to present the required info          

            Note: If I asked for a list, provide ALL items in a numbered format. If data is missing, explicitly state what's unavailable rather than making assumptions.
            
            {user_cta_instructions}
            
            Important::
            - do not halucinate
            - do not repeat yourself
            - be clear with less word
            - if you perform some action as instructed in the Execution plan, then it is most important that you clearly inform of the update in the action
            - do not send random things in next actions please
            - correctness of descision_process_output is most important
            - Keep today's date in mind - {current_date} and currency format given in Context.
        """

        import json
        str_plan = json.dumps(plan)
        if "snapshot" in query.lower():
            if "portfolio_snapshot" in str_plan.lower():
                chat_completion = portfolio_snapshot_prompt(None, None, None, None, None, results, plan, query, conv)
            elif "performance_snapshot_last_quarter" in str_plan.lower():
                chat_completion = performance_snapshot_prompt(None, None, None, None, None, results, plan, query, conv)
            elif "value_snapshot_last_quarter" in str_plan.lower():
                chat_completion = business_value_report_prompt(None, None, None, None, None, results, plan, query, conv)
            elif "risk_snapshot" in str_plan.lower():
                chat_completion = risk_report_prompt(results, query, conv, plan)
            elif "monthly_savings_snapshot" in str_plan.lower():
                chat_completion = monthly_savings_report_with_graph_prompt(results, query, conv)
            elif "generate_onboarding_report" in str_plan.lower():
                chat_completion = create_transformation_report_prompt(results, query, conv)
            else:
                chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
        else:
            system_prompt += f"""
            
                Instruction for adding chart:
                add chart if asked by user in this way:Add commentMore actions
                Charts: You can have multiple different types of charts to represent the data, depending on which kind you need.

                    The output of your chart should be in the following format:
                    ```json
                    {{
                        chart_type: 'Gaant' or 'Bar' or 'Line' or 'BarLine',
                        format: <format>,
                        symbol: '$' if something related to money otherwise '', 
                    }}
                    ```
                        Gaant Chart have the following format:
                        
                        <format>: {{
                            data:  [ 
                                {{
                                    x: <x_axis_name>, // string
                                    y: ['date_string_begin', 'date_string_end']
                                }}
                            ]
                        }}
                        
                        For Line Charts, they have the following format:

                        <format> - [
                            {{
                                name: <name_of_param>,// string
                                data: [<values_of_data>, ...],
                                categories: [<categories>, ...]
                            }},
                            ... if more params they want for bar chart
                        ]

                        For Bar Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                                                
                        <format> - [
                            {{
                                name: <name_of_param>,// string
                                data: [<values_of_data>, ...],
                                categories: [<categories>, ...]
                            }},
                            ... if more params they want for bar chart
                        ]
                        
                        
                        For BarLine Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                        
                        <format> - [
                            {{
                                name: <name_of_param>, // string
                                type: 'bar' or 'line', // specifies series type
                                data: [<values_of_data>, ...],
                                categories: [<categories>, ...]
                            }},
                            ... multiple series for bar and/or line
                        ]

                        For Donut/Gauge Chart type - this is the applicable format <format>:
                        <format> - [
                            {{
                                data: [<values_of_data>, ...],
                                categories: [<categories>, ...]
                            }}
                        ]
                        
                        If you selected more than one graph, then you should create multiple jsons in the format given above. \
                        Do not truncate the data sent in the chart.
                
                When user wants charts where meramid charts are needed  like process flow or sequence flow etc
                format to send output of mermaid chart
                example for a process flow (graph TD) that avoids rendering issues with & or other special characters

                When generating Mermaid diagrams (flowcharts, sequence diagrams, mindmaps, etc.):
                    - Wrap every node label in quotes → A["My Label"]
                    - Escape `&` as `&amp;`
                    - If label has parentheses or special characters, keep them inside the quotes
                    - Keep diagrams minimal and valid (avoid extra symbols outside of quotes)

                    Examples:

                    ```mermaid
                    flowchart TD
                        A["Start"] --> B["Action"]
                        B --> C["Result"]
                    ```
                    
                    ```mermaid
                    flowchart TD
                        H["Continuous Improvement (AI-Driven)"] --> I["AI-Augmented Workflows"]
                    ```
                    
                    ```mermaid
                    mindmap
                    root((Project))
                        1["Goal"]
                        1.1["Feature"]
                    ```
            
                
            """
            
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

        
        # chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
        # print("final prompt -- ", chat_completion.formatAsString())
        # self.socket_sender.sendSteps("Building your answer", False, 0, 1)
        WORD_BOUNDARY = re.compile(r'[\s.,!?;:]')
        # buffer = ""
        
        try:
            if self.buffer:
                yield self.buffer
                
            if self.done_response:
                return
                
            for chunk in self.llm.runWithStreaming(
                chat_completion, 
                self.modelOptions, 
                f'{self.name}::output', 
                logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id},
                socketio=self.socketio, client_id=self.client_id
            ):
                self.buffer += chunk
                self.res += chunk
                if len(self.buffer) >= MIN_BUFFER_SIZE or (self.buffer and WORD_BOUNDARY.search(self.buffer)):
                    yield self.buffer
                    self.buffer = ""
                    if self.socketio:
                        self.socketio.sleep(0.01)
            if self.buffer:
                yield self.buffer
        except Exception as e:
            TangoBreakMapUser.add_counter(self.user_id)
            if TangoBreakMapUser.get_counter(self.user_id) <= 2:
                if "GPT failed to send" in str(e):
                    yield "\n\n"
                    yield "Error occured, so trying again."
                    yield "\n\n"
                    error_context = (
                        f"Previous attempt failed with error: {str(e)}. "
                        f"Partial response:\n{self.res}\n"
                        "Please provide the response in a list format instead of a table to avoid rendering issues. "
                        "Explain why this format change helps avoid the error."
                    )
                    # chat_completion = ChatCompletion(system=system_prompt, prev=[], user=user_prompt + "\n\n **<important_bug_to_fix>**---- you failed to print this answer completely previously error was: <error_in_previous_response>"+  str(e) + " <error_in_previous_response>,  the previous partial answer \n\n <previous_partial_answer>" + res + "\n\n <previous_partial_answer> \n\n" + " Ensure to fix this error in the next attempt. Provide reason to the format fix of the answer so that the same error does not happen. if table gives error. move to list. \n\n **<important_bug_to_fix>**" )
                    chat_completion = ChatCompletion(
                        system=system_prompt,
                        prev=[],
                        user=user_prompt + "\n\n" + error_context
                    )
                    # print("prompt debug 2 --- ", chat_completion.formatAsString())
                    buffer = ""
                    for chunk in self.llm.runWithStreaming(chat_completion, self.modelOptions, 'tango::master::combine', logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id},socketio=self.socketio, client_id=self.client_id):
                        buffer += chunk
                        self.res += chunk
                        if len(buffer) >= MIN_BUFFER_SIZE or (buffer and WORD_BOUNDARY.search(buffer)):
                            yield buffer
                            buffer = ""
                            if self.socketio:
                                self.socketio.sleep(0.01)
                                
            self.socket_sender.sendError(key = "Couldn't generate response", function = "BaseAgent_process_combined_query")                 
            yield f"An error occurred while generating the response: {str(e)}"
            
        print("process_combined_query--------- res------", self.res)
        
        self.event_bus.unsubscribe(
            "STEP_UPDATE",
            session_id=self.session_id,
            callback=self._step_callback
        )

    @log_function_io_and_time
    def run_data_source(self, source_name: str, params: Dict) -> Dict:
        """Executes a data source with given parameters."""
        debugLogger.info(f"Running run_data_source with {source_name} -> {params}")
        try:
            source = self.data_getters.fn_maps.get(source_name)
            if not source:
                error_msg = f"Data source '{source_name}' not found"
                appLogger.error({
                    "function": "run_data_source_error",
                    "error": error_msg,
                    "tenant_id": self.tenant_id
                })
                return {"error": error_msg, "source": source_name}

            result = source(params)
            return result
        except Exception as e:
            appLogger.error({
                "function": "run_data_source_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id,
                "source_name": source_name
            })
            return {"error": str(e), "source": source_name}
 
    @log_function_io_and_time
    def execute_plan(self, plan: Dict) -> Dict:
        """Executes the plan by running data sources and actions in parallel where possible."""
        results = {
            "action_results": {},
            "data_sources_results": {},
            "agents_results": {}
        }
        print("\n---debug in execute_plan--------", plan)
        
        # Execute data sources in parallel
        data_sources_to_trigger_with_source_params = plan.get("data_sources_to_trigger_with_source_params") or {}
        if data_sources_to_trigger_with_source_params:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Gathering relevant data"},
                session_id=self.session_id
            )
            # self.socket_sender.sendSteps("Gathering relevant data", False)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                source_futures = {
                    executor.submit(
                        self.run_data_source,
                        name,
                        (data_sources_to_trigger_with_source_params).get(name, {})
                    ): name 
                    for name in data_sources_to_trigger_with_source_params.keys()
                }
                
                for future in as_completed(source_futures):
                    name = source_futures[future]
                    try:
                        result = future.result()
                        results["data_sources_results"][name] = result
                        appLogger.info({
                            "function": f"process_combined_query_data_source_{name}_success",
                            "tenant_id": self.tenant_id,
                            "data_source": name
                        })
                    except Exception as e:
                        error_msg = str(e)
                        appLogger.error({
                            "function": f"process_combined_query_data_source_{name}_error",
                            "error": error_msg,
                            "traceback": traceback.format_exc(),
                            "tenant_id": self.tenant_id
                        })
                        results["data_sources_results"][name] = {"error": error_msg}
        
                    # self.socket_sender.sendSteps("Data collection complete", False)
        # Execute actions sequentially (they might depend on each other)
        actions_to_trigger_with_action_params = plan.get("actions_to_trigger_with_action_params") or {}
        # action_params = plan.get("action_params", {}) or {}
        
        # if len(actions_to_trigger_with_action_params.keys()) > 0:
        #     self.event_bus.dispatch(
        #         'STEP_UPDATE',
        #         {'message': "Performing requested actions"},
        #         session_id=self.session_id
        #     )
        #     # self.socket_sender.sendSteps("Performing requested actions", False)
            
        for action in actions_to_trigger_with_action_params.keys():
            try:
                params = actions_to_trigger_with_action_params.get(action, {})
                output = self.data_actions.fn_maps[action](params)
                results["action_results"][action] = output
                appLogger.info({
                    "function": f"process_combined_query_action_{action}_success",
                    "tenant_id": self.tenant_id,
                    "action": action
                })
            except Exception as e:
                error_msg = str(e)
                appLogger.error({
                    "function": f"process_combined_query_action_{action}_error",
                    "error": error_msg,
                    "traceback": traceback.format_exc(),
                    "tenant_id": self.tenant_id
                })
                results["action_results"][action] = {"error": error_msg}
        
        if len(actions_to_trigger_with_action_params.keys()) > 0:    
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': "Actions completed"},
                session_id=self.session_id
            )
                
        return results
