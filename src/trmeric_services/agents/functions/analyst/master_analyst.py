"""GeneralMasterAnalyst: Coordinates analysis across multiple entity types."""

from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.agents.functions.analyst.general_analyst import GeneralAnalyst
from src.trmeric_services.agents.functions.analyst.analyst_configs import ANALYZER_CONFIGS
from src.trmeric_services.agents.functions.analyst.analyst_tools.master_utils import _build_user_context, plan_combined_analysis, start_preplanning_thought_thread
from src.trmeric_api.logging.AppLogger import appLogger
import json, uuid, base64, pickle
import traceback
import concurrent.futures
from typing import Dict, List
from datetime import datetime

class MasterAnalyst:
    """Orchestrates and combines analysis from multiple GeneralAnalyst instances."""
    
    def __init__(self, tenant_id, user_id, analyzer_configs, socketio=None, 
                 llm=None, client_id=None, base_agent=None, sessionID=None):
        print(f"[MasterAnalyst] Initializing for tenant {tenant_id}, user {user_id}")
        # Core properties
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.analyzer_configs = analyzer_configs
        
        # Communication channels
        self.socketio = socketio
        self.llm = llm
        self.client_id = client_id
        
        # Context
        self.base_agent = base_agent
        self.user_context = _build_user_context(base_agent)
        # self.user_context = _build_user_context(base_agent)
        self.sessionID = sessionID
        self.confirmation = False
        
        
    def get_analyzer(self, analyzer_type: str, uuid_str= None) -> GeneralAnalyst:
        """Get a fresh analyzer instance of the specified type."""
        if analyzer_type not in self.analyzer_configs:
            available = list(self.analyzer_configs.keys())
            raise ValueError(f"Analyzer type not found: {analyzer_type}. Available: {available}")
        if not uuid_str:
            uuid_str= str(uuid.uuid4())
        return GeneralAnalyst(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            socketio=self.socketio,
            llm=self.llm,
            client_id=self.client_id,
            base_agent=self.base_agent,
            sessionID=self.sessionID,
            analyst_key=f"{analyzer_type}_analyst",
            uuid= uuid_str,
            **self.analyzer_configs[analyzer_type]
        )

    def process_analyzer_planning(self, analyzer_type, analyzer_plan_map, sub_queries):
        """Process a single analyzer and return its results"""
        try:
            print(f"[MasterAnalyst] Starting parallel processing for analyzer: {analyzer_type}")
            analyzer = self.get_analyzer(analyzer_type)
            analyzer_markdown = ""
            # Pass the correct plan for this analyzer
            analyzer_plan = analyzer_plan_map.get(analyzer_type, {})
            # Set the subgoal attribute on the analyzer if present
            if "analyzer_subgoal" in analyzer_plan:
                analyzer.subgoal = analyzer_plan["analyzer_subgoal"]
            # Process the query with analyzer-specific plan
            for response in analyzer.process_query_planning_phase(query=sub_queries[analyzer_type], analysis_plan=analyzer_plan):
                analyzer_markdown += str(response)
            print(f"[MasterAnalyst] Completed parallel processing for {analyzer_type}")
            # Check if the analyzer used a single batch
            used_single_batch = hasattr(analyzer, 'single_batch_used') and analyzer.single_batch_used
            num_rows = analyzer.num_rows
            uuid_str= analyzer.uuid
            return analyzer_type, analyzer_markdown, used_single_batch, num_rows, uuid_str
        except Exception as e:
            appLogger.error(f"ERROR: Parallel analyzer {analyzer_type} failed: {str(e)}\n{traceback.format_exc()}")
            return analyzer_type, f"Error processing {analyzer_type} analysis: {str(e)}", False

    def process_combined_query_planning(self, query: str):
        print(f"[MasterAnalyst] Processing combined query: {query}")
        try:
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id, 
                user_id=self.user_id,
                key="general_master_analyst", 
                value=f"Query: {query}", 
                session_id=self.sessionID
            )
            if self.socketio:
                self.socketio.emit("agent_switch", {"agent": "analyst"}, room=self.client_id)
            start_preplanning_thought_thread(self.socketio, self.client_id)
            # Plan the analysis
            plan = plan_combined_analysis(query, self.llm, self.socketio, self.client_id, self.user_context, self.analyzer_configs)
            analyzer_plan_map = {}
            for analyzer_cfg in plan.get("analyzer_configs", []):
                name = analyzer_cfg.get("analyzer_name")
                if name:
                    analyzer_plan_map[name] = analyzer_cfg.get("analyzer_settings", {})
                    # Optionally, add subgoal if present
                    if "analyzer_subgoal" in analyzer_cfg:
                        analyzer_plan_map[name]["analyzer_subgoal"] = analyzer_cfg["analyzer_subgoal"]

            # For quick analyst, also pass the correct plan
            if plan.get("clarification_needed", False):
                print("[MasterAnalyst] Clarification needed from user")
                yield plan.get("clarification_message", "Please clarify your query.")
                return
            
            if plan.get("combination_type") == "SEQUENTIAL":
                print("[MasterAnalyst] Sequential analysis requested")
                for chunk in self.process_sequential_analysis(plan):
                    yield chunk
                return
            
            analyzers_to_trigger = [analyzer_cfg["analyzer_name"] for analyzer_cfg in plan.get("analyzer_configs", [])]
            sub_queries = {}
            
            # Create sub_queries from analyzer_subgoal if present
            for analyzer_cfg in plan.get("analyzer_configs", []):
                name = analyzer_cfg.get("analyzer_name")
                if name and "analyzer_subgoal" in analyzer_cfg:
                    sub_queries[name] = analyzer_cfg["analyzer_subgoal"]

            print(f"[MasterAnalyst] Starting analysis with {len(analyzers_to_trigger)} analyzers")
            analysis_markdown = {}
            single_batch_analyzers = {}  # Track which analyzers used a single batch
            num_rows_dict = {}
            uuids = {}
            
            # Execute analyzers using ThreadPoolExecutor (handles both single and multiple analyzers efficiently)
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(analyzers_to_trigger)) as executor:
                # Submit all analyzer jobs
                future_to_analyzer = {
                    executor.submit(self.process_analyzer_planning, analyzer_type, analyzer_plan_map, sub_queries): analyzer_type 
                    for analyzer_type in analyzers_to_trigger if analyzer_type in sub_queries
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_analyzer):
                    analyzer_type = future_to_analyzer[future]
                    try:
                        analyzer_type, result, used_single_batch, num_rows, uuid_str= future.result()
                        analysis_markdown[analyzer_type] = result
                        single_batch_analyzers[analyzer_type] = used_single_batch
                        num_rows_dict[analyzer_type] = num_rows
                        uuids[analyzer_type] = uuid_str
                        print(f"[MasterAnalyst] Collected results from {analyzer_type}")
                    except Exception as e:
                        appLogger.error(f"ERROR: Failed to get results from {analyzer_type}: {str(e)}")

            # Save plan and uuid_strdict into the database
            serialize_data = (plan, uuids)
            base64_data = base64.b64encode(pickle.dumps(serialize_data)).decode('utf-8')
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key="MASTER_ANALYSIS_CONFIRMATION_STEP",
                value=str(base64_data),
                session_id=self.sessionID
            )

            # Check if analysis size requires confirmation
            ROW_THRESHOLD = 10
            total_rows = sum(num_rows_dict.values())
            
            if total_rows > ROW_THRESHOLD:
                # Format confirmation message based on number of analyzers
                if len(num_rows_dict) == 1:
                    # Single analyzer - use sentence form
                    analyzer_type = list(num_rows_dict.keys())[0]
                    num_items = num_rows_dict[analyzer_type]
                    confirmation_message = f"""
### Quick Check

This analysis will process **{num_items} {analyzer_type}s**. Would you like to:
- Continue with the full analysis
- Modify your query to be more specific
- Cancel and try a different approach

Please confirm if you want to proceed.
"""
                else:
                    # Multiple analyzers - use list form
                    analyzer_counts = [f"- {analyzer.capitalize()}: {num_rows} items" for analyzer, num_rows in num_rows_dict.items()]
                    confirmation_message = f"""
### Analysis Size Check

This analysis will process data across multiple areas ({total_rows} total items):
{chr(10).join(analyzer_counts)}

Would you like to:
- Continue with the full analysis
- Modify your query to reduce the scope
- Cancel and try a different approach

Please confirm if you want to proceed.
"""
                yield confirmation_message
                return
            
            # For small analyses, proceed automatically
            self.confirmation = True

            # Log completion
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key="general_master_analyst",
                value=f"Agent Response: Analysis completed", 
                session_id=self.sessionID
            )

        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            print(f"[MasterAnalyst] Critical error: {error_msg}")
            appLogger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield "Sorry, I encountered an error. Please try rephrasing your query."

    def process_analyzer_analysis(self, analyzer_type, uuid_str, sub_queries):
        """Process a single analyzer and return its results"""
        try:
            analyzer = self.get_analyzer(analyzer_type, uuid_str)
            analyzer_markdown = "" 
            print(f"[MasterAnalyst] Starting parallel processing for analyzer: {analyzer_type}")
            for response in analyzer.process_query_analysis_phase(query=sub_queries[analyzer_type]):
                analyzer_markdown += str(response)
            print(f"[MasterAnalyst] Completed parallel processing for {analyzer_type}")
            used_single_batch = hasattr(analyzer, 'single_batch_used') and analyzer.single_batch_used
            return analyzer_type, analyzer_markdown, used_single_batch
        except Exception as e:
            appLogger.error(f"ERROR: Parallel analyzer {analyzer_type} failed: {str(e)}\n{traceback.format_exc()}")
            return analyzer_type, f"Error processing {analyzer_type} analysis: {str(e)}", False
        
    def process_single_analyzer_analysis(self, analyzer_type, uuid_str, sub_queries):
        """Process a single analyzer for all analyzers and return its results"""
        try:
            analyzer = self.get_analyzer(analyzer_type, uuid_str)
            print(f"[MasterAnalyst] Starting parallel processing for analyzer: {analyzer_type}")
            for chunk in analyzer.process_query_analysis_phase(query=sub_queries[analyzer_type]):
                if analyzer.single_batch_used:
                    yield chunk, analyzer.single_batch_used

        except Exception as e:
            appLogger.error(f"ERROR: Parallel analyzer {analyzer_type} failed: {str(e)}\n{traceback.format_exc()}")
            return analyzer_type, f"Error processing {analyzer_type} analysis: {str(e)}", False
        
    def process_combined_query_analysis(self, query: str):
        print(f"[MasterAnalyst] Processing combined query: {query}")
        try:
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id, 
                user_id=self.user_id,
                key="general_master_analyst", 
                value=f"Query: {query}", 
                session_id=self.sessionID
            )
 
            data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(self.sessionID, self.user_id, "MASTER_ANALYSIS_CONFIRMATION_STEP")
            plan, uuids = pickle.loads(base64.b64decode(data[0]["value"].encode('utf-8')))
            analyzers_to_trigger = [analyzer_cfg["analyzer_name"] for analyzer_cfg in plan.get("analyzer_configs", [])]
            sub_queries = {}
            
            # Create sub_queries from analyzer_subgoal if present
            for analyzer_cfg in plan.get("analyzer_configs", []):
                name = analyzer_cfg.get("analyzer_name")
                if name and "analyzer_subgoal" in analyzer_cfg:
                    sub_queries[name] = analyzer_cfg["analyzer_subgoal"]

            analysis_markdown = {}
            single_batch_analyzers = {}
            print(f"[MasterAnalyst] Running {len(analyzers_to_trigger)} analyzers in parallel")
            
            if len(analyzers_to_trigger) == 1:
                yield_decision = False
                for chunk in self.process_single_analyzer_analysis(
                    analyzers_to_trigger[0], uuids[analyzers_to_trigger[0]], sub_queries
                ):
                    analyzer_markdown = ""
                    chunk_data, yield_decision = chunk
                    if yield_decision:
                        yield chunk_data
                    else:
                        analyzer_markdown += chunk_data
                        
                if yield_decision: return
                else: analysis_markdown = {analyzers_to_trigger[0]: analyzer_markdown}
                    
            else:
                # Execute analyzers in parallel using ThreadPoolExecutor
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(analyzers_to_trigger)) as executor:
                    # Submit all analyzer jobs
                    future_to_analyzer = {
                        executor.submit(self.process_analyzer_analysis, analyzer_type, uuids[analyzer_type], sub_queries): analyzer_type 
                        for analyzer_type in analyzers_to_trigger if analyzer_type in sub_queries
                    }
                    
                    # Collect results as they complete
                    for future in concurrent.futures.as_completed(future_to_analyzer):
                        analyzer_type = future_to_analyzer[future]
                        try:
                            analyzer_type, result, used_single_batch = future.result()
                            analysis_markdown[analyzer_type] = result
                            single_batch_analyzers[analyzer_type] = used_single_batch
                            print(f"[MasterAnalyst] Collected parallel results from {analyzer_type}")
                        except Exception as e:
                            appLogger.error(f"ERROR: Failed to get results from {analyzer_type}: {str(e)}")

            # Combine results and yield only the final synthesis
            if analysis_markdown:
                print("[MasterAnalyst] Combining results from all analyzers")
                # If only one analyzer was used, check if it used a single batch
                if len(analyzers_to_trigger) == 1 and len(analysis_markdown) == 1:
                    analyzer_type = analyzers_to_trigger[0]
                    # Skip combination step if single analyzer AND single batch
                    if single_batch_analyzers.get(analyzer_type, False):
                        print(f"[MasterAnalyst] Single analyzer ({analyzer_type}) with single batch used, bypassing combination step")
                        md = analysis_markdown[analyzer_type]
                        yield md[2:-2].replace("\\n", "\n")

                    else:
                        print(f"[MasterAnalyst] Single analyzer ({analyzer_type}) with multiple batches, using combination step")
                        # Multiple batches were used, combine their results
                        final_response = ""
                        for chunk in self.combine_results(
                            analysis_markdown=analysis_markdown,
                            combination_logic=plan["combination_logic"],
                            original_query=query,
                            analyzers_used=analyzers_to_trigger
                        ):
                            final_response += str(chunk)
                        # Yield only the final combined synthesis
                        yield final_response
                else:
                    # Multiple analyzers were used, combine their results
                    final_response = ""
                    for chunk in self.combine_results(
                        analysis_markdown=analysis_markdown,
                        combination_logic=plan["combination_logic"],
                        original_query=query,
                        analyzers_used=analyzers_to_trigger
                    ):
                        final_response += str(chunk)
                    # Yield only the final combined synthesis
                    yield final_response

            # Log completion
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key="general_master_analyst",
                value=f"Agent Response: Analysis completed", 
                session_id=self.sessionID
            )

        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            print(f"[MasterAnalyst] Critical error: {error_msg}")
            appLogger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield "Sorry, I encountered an error. Please try rephrasing your query."

    def combine_results(
        self,
        analysis_markdown: Dict,
        combination_logic: str,
        original_query: str,
        analyzers_used: List[str],
    ):
        """Combine analysis results into a dynamic, user-focused markdown report with JSON reasoning."""
        try:
            # Validate inputs
            if not analyzers_used or not analysis_markdown:
                yield "\n\n**Note:** No valid analyzers or analysis results provided."
                return

            # Collect markdown outputs
            all_markdown = []
            for analyzer in analyzers_used:
                if analyzer in analysis_markdown:
                    all_markdown.append(analysis_markdown[analyzer])
                else:
                    appLogger.warning(f"Analyzer {analyzer} not found in analysis_markdown")

            if not all_markdown:
                yield "\n\n**Note:** No valid analysis results found."
                return

            currentDate = datetime.now().date().isoformat()
            role_context = self.user_context
            # Common context
            base_context = f"""
                User Query: "{original_query}"
                Combination Logic: {combination_logic}
                Analyzers Used: {analyzers_used}
                User Role: {role_context}
                Source Analysis:
                    {''.join(all_markdown)}
                
                Current Date: {currentDate}
            """

            # Prompt configuration
            if len(analyzers_used) > 1:
                system_prompt = f"""
                # Portfolio & Project Insights Synthesizer (Markdown)

                You are a senior strategy consultant synthesizing multiple analyses, resource data, and internal knowledge into a polished markdown report. Deliver actionable, non-obvious insights tailored to the user's role. For complex queries (e.g., ranking), apply a weighted scoring system (30% business impact, 20% resource efficiency, 20% risk, 30% customer impact). Reference specific entity names, statistics, and numbers. Highlight cross-entity patterns, overlaps, and strategic implications.

                ## Context
                {base_context}

                ## Output Requirements
                - Write a structured markdown report with:
                  - **Header**: Frame the analysis
                  - **Analysis**: Detailed insights (100-300 words) addressing query components
                  - **Key Insights**: 2-3 bullet points recapping top findings
                  - **Recommendations**: 1-2 actionable steps
                  - **Sources**: Cite resource data or internal knowledge if used
                - Tailor to user role: {role_context}
                - Map query components to metrics:
                  - Business impact: revenue_growth, kpi_impact
                  - Resource gaps: allocation_percentage, skills
                  - Risk: risk_impact, compliance_cost
                  - Customer impact: customer_satisfaction_score
                - Use tables only for non-obvious patterns or comparisons
                - Avoid JSON or raw data in markdown
                - Never use entity IDs, always use names
                """
                user_prompt = f"""
                Synthesize the analyses, resource data, and internal knowledge into a markdown report tailored to {role_context}. For complex queries, use weighted scoring. Highlight 2-3 non-obvious insights with entity names and numbers. Use tables only for key patterns. End with 1-2 recommendations and sources if applicable.
                """
            else:
                system_prompt = f"""
                # Portfolio or Project Summary (Markdown)

                You are a senior strategy consultant summarizing a single analysis, enriched with resource data and internal knowledge, into a concise markdown report. Go beyond listing facts—highlight 1-2 non-obvious insights or implications. Tailor to the user's role. Reference specific entity names, statistics, and numbers.

                ## Context
                {base_context}

                ## Output Requirements
                - Write a structured markdown report with:
                  - **Header**: Frame the analysis
                  - **Analysis**: Detailed insights (50-200 words) addressing query
                  - **Key Insights**: 1-2 bullet points recapping top findings
                  - **Recommendations**: 1-2 actionable steps
                  - **Sources**: Cite resource data or internal knowledge if used
                - Tailor to user role: {role_context}
                - Map query components to metrics:
                  - Business impact: revenue_growth, kpi_impact
                  - Resource gaps: allocation_percentage, skills
                  - Risk: cost_savings, efficiency_gain
                  - Customer impact: customer_satisfaction_score
                - Highlight 1-2 non-obvious insights
                - Use tables only for key patterns
                - Avoid JSON or raw data in markdown
                - Never use entity IDs, always use names
                """
                user_prompt = f"""
                Summarize the analysis, enriched with resource data and internal knowledge, into a markdown report tailored to {role_context}. Highlight 1-2 non-obvious insights with entity names and numbers. Use tables only for key patterns. End with 1-2 recommendations and sources if applicable.
                """

            # Stream the response
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user=user_prompt
            )

            for chunk in self.llm.runWithStreaming(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=4096, temperature=0.2),
                'tango::master::combine',
                None
            ):
                yield chunk
                
        except Exception as e:
            appLogger.error(f"ERROR in combine_results: {str(e)}\n{traceback.format_exc()}")
            yield "\n\n**Note:** Error combining results. Please review individual analyses above."


    def process_sequential_analysis(self, plan, initial_query=None):
        """
        Run analyzers sequentially, passing each result to the next as input.
        For each analyzer:
          - Run planning phase (fetch/store data)
          - Run analysis phase (get result)
          - Pass result to next analyzer's subgoal/query
        At the end, combine results as in the parallel case.
        """
        import uuid
        try:
            configs = plan.get("analyzer_configs", [])
            previous_result = None
            analysis_markdown = {}
            uuids = {}
            for idx, config in enumerate(configs):
                analyzer_type = config.get("analyzer_name")
                if not analyzer_type:
                    continue
                uuid_str = str(uuid.uuid4())
                uuids[analyzer_type] = uuid_str
                # Build sub_query: inject previous result if present
                if idx == 0:
                    sub_query = config.get("analyzer_subgoal", initial_query or "")
                else:
                    sub_query = f"{config.get('analyzer_subgoal', '')}\n\n[Previous Analysis Result]:\n{previous_result}"
                analyzer_plan = config.get("analyzer_settings", {})
                analyzer = self.get_analyzer(analyzer_type, uuid_str)
                if "analyzer_subgoal" in config:
                    analyzer.subgoal = config["analyzer_subgoal"]
                # --- Planning phase: fetch/store data ---
                for _ in analyzer.process_query_planning_phase(query=sub_query, analysis_plan=analyzer_plan):
                    pass  # planning phase only stores data, no need to yield
                # --- Analysis phase: get result ---
                result = ""
                for chunk in analyzer.process_query_analysis_phase(query=sub_query):
                    result += str(chunk)
                analysis_markdown[analyzer_type] = result
                previous_result = result  # Pass to next analyzer
            # Combine results as in the parallel case
            analyzers_used = [cfg["analyzer_name"] for cfg in configs if cfg.get("analyzer_name")]
            combination_logic = plan.get("combination_logic", "")
            original_query = initial_query or ""
            final_response = ""
            for chunk in self.combine_results(
                analysis_markdown=analysis_markdown,
                combination_logic=combination_logic,
                original_query=original_query,
                analyzers_used=analyzers_used
            ):
                final_response += str(chunk)
                yield chunk

            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key="general_master_analyst",
                value=f"Agent Response: (sequential response completed)",
                session_id=self.sessionID
            )
        except Exception as e:
            error_msg = f"Sequential analysis error: {str(e)}"
            print(f"[MasterAnalyst] Critical error: {error_msg}")
            appLogger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield "Sorry, I encountered an error in sequential analysis. Please try rephrasing your query."

def view_general_combined_analysis(
    user_query_for_analyzer: str,
    user_confirmed_analysis_plan: bool,
    tenantID: int,
    userID: int,
    socketio=None,
    client_id=None,
    llm=None,
    base_agent=None,
    sessionID=None,
    **kwargs
):
    """
    Function that handles combined analysis across multiple entity types.
    This is the function that will be registered as an AgentFunction.
    """
    
    # Use the dynamically imported analyzer configurations
    analyzer_configs = ANALYZER_CONFIGS
    
    # Create master analyst
    agent = MasterAnalyst(
        tenant_id=tenantID,
        user_id=userID,
        analyzer_configs=analyzer_configs,
        socketio=socketio,
        llm=llm,
        client_id=client_id,
        base_agent=base_agent,
        sessionID=sessionID
    )
    
    agent.confirmation=user_confirmed_analysis_plan
    # Process query, emitting each chunk immediately to socket.io
    if not agent.confirmation:
        for response in agent.process_combined_query_planning(
            query=user_query_for_analyzer,
            ):
            # Send each chunk to socket.io immediately
            if socketio and client_id:
                socketio.emit("tango_chat_assistant", response, room=client_id)
            yield response

    if agent.confirmation:        
        for response in agent.process_combined_query_analysis(
            query=user_query_for_analyzer,
            ):
            # Send each chunk to socket.io immediately
            if socketio and client_id:
                socketio.emit("tango_chat_assistant", response, room=client_id)
            yield response
    
    # Send end marker after all chunks are processed
    if socketio and client_id:
        socketio.emit("tango_chat_assistant", "<end>", room=client_id)
        socketio.emit("tango_chat_assistant", "<<end>>", room=client_id)

    # Log the interaction with just the first part of the response
    TangoDao.insertTangoState(
        tenant_id=tenantID,
        user_id=userID,
        key="general_master_analyst",
        value=f"Agent Response: (streaming response completed)", 
        session_id=sessionID
    )

# Register the function as an AgentFunction
RETURN_DESCRIPTION = """
Analyzes multiple entity types together (roadmaps and projects), combining insights for complex queries using detailed evaluation data.
Provides integrated analysis across planning and execution phases, identifies gaps, overlaps, and opportunities.
"""

VIEW_GENERAL_COMBINED_ANALYSIS = AgentFunction(
    name="view_general_combined_analysis",
    description="General Master Analyst for queries across roadmaps and projects. Always call this function for this agent",
    args=[
        {
            "name": "user_query_for_analyzer",
            "description": '''
            You should pretty much be copying the user's question into this in most cases. You will be useful here if the user asks about a follow up.
            Then, you should represent the question again using the context of the previous messages. Imagine the following analysis step not having access to the chat.
            Then it is YOUR job to make sure the analyzer knows exactly what natural language query to search and analyze for. 
            ''',
            "type": "str",
            "required": "true"
        },
        {
            "name": "user_confirmed_analysis_plan",
            "description": '''
            If you, Tango, have created a plan for the user and asked them to confirm it, you will see this reflected in the chat.
            You will have told the user you are going to analyzer a certain number of projects, roadmaps, etc...     
            ONLY IF the previous message was Tango requesting confirmation AND the user explicitly replied without asking to change anything, then set this to True.
            Otherwise, you should set this to false.
            ''',
            "type": "bool",
            "required": "true"
        },
    ],
    return_description=RETURN_DESCRIPTION,
    function=view_general_combined_analysis,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)