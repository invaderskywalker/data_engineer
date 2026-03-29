"""General Analyst class for handling analysis operations."""
import json
import pandas as pd
import traceback
from typing import Dict, List, Optional, Generator
from .analyst_tools.general_utils import (
    estimate_tokens, generator_cleaner, build_user_context,
    build_row_mapping_args, build_row_mapping, emit_table_to_ui
)
from .analyst_tools.df_analyzer import DataframeAnalyzer
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
import pickle, base64

MAX_TOKENS_PER_BATCH = 30000

class GeneralAnalyst:
    def __init__(self, tenant_id, user_id, socketio=None, llm=None, client_id=None, 
                 base_agent=None, sessionID=None, analyst_key=None, uuid=None, **config):
        print(f"[GeneralAnalyst] Initializing {analyst_key} for tenant {tenant_id}")
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.socketio = socketio
        self.llm = llm
        self.client_id = client_id
        self.base_agent = base_agent
        self.sessionID = sessionID
        self.analyst_key = analyst_key or "general_analyst"
        self.uuid = uuid
        
        # Initialize mapping cache
        self._mapping_cache = {}
        
        # Build user context from base agent if available
        self.user_context = build_user_context(self.base_agent)
        
        # Load configuration
        self.columns = config.get("columns", [])
        self.field_mapping = config.get("field_mapping")
        self.eval_prompt_template = config.get("eval_prompt_template")
        self.fetch_data = config.get("fetch_data")
        self.cluster_func = config.get("cluster_func")
        self.id_field = config.get("id_field")
        self.row_mapping = config.get("row_mapping")
        
        # Cache key for row mappings
        self._cache_key = f"row_mapping_{self.tenant_id}_{self.user_id}"
        
        # Initialize row mapping data with cache
        self.row_mapping_data = self._get_row_mapping_data()
        
        # Initialize dataframe analyzer
        self.df_analyzer = DataframeAnalyzer(llm)

        # Metadata
        self.single_batch_used = False
        self.num_rows = 0

    def _get_row_mapping_data(self) -> List[Dict]:
        """Get row mapping data using cache if available."""
        if self._cache_key in self._mapping_cache:
            print("[GeneralAnalyst] Using cached row mappings")
            return self._mapping_cache[self._cache_key]
            
        mappings = build_row_mapping(self.row_mapping, self.tenant_id, self.user_id)
        self._mapping_cache[self._cache_key] = mappings
        return mappings

    def _get_data(self, subgoal: Optional[str] = None) -> List[Dict]:
        """Get data using the configured fetch function, passing subgoal."""
        print(f"[GeneralAnalyst] Fetching data with subgoal: {subgoal}")
        if not self.fetch_data:
            raise ValueError("Data fetch function not configured")
            
        # Get the data using the configured fetch function
        data = self.fetch_data(self, subgoal=subgoal, row_mapping_data=self.row_mapping_data)
        if not data:
            return []
            
        print(f"[GeneralAnalyst] Retrieved {len(data)} records")
        return data

    def _evaluate_data(self, data: List[Dict], query: str, analysis_plan: Dict, subgoal: Optional[str] = None, df_analysis: Optional[str] = None) -> List[Dict]:
        """Evaluate data using the configured template, passing subgoal."""
        if not self.eval_prompt_template:
            raise ValueError("Eval prompt template not configured")
        for chunk in self.eval_prompt_template(self, data, query, analysis_plan, subgoal=subgoal, df_analysis=df_analysis, quick = analysis_plan.get("quick_analysis", False)):
            yield chunk

    def _emit_table_to_ui(self, data: List[Dict]):
        """Emit table data to UI using the utility function."""
        emit_table_to_ui(
            data=data,
            socketio=self.socketio,
            client_id=self.client_id,
            analyst_key=self.analyst_key,
            id_field=self.id_field
        )

    def _process_batch(self, batch: List[Dict], query: str, plan: Dict, df_analysis: Optional[str] = None) -> Generator[str, None, None]:
        """Process a batch of data and return LLM-driven evaluation results as a generator of markdown strings."""
        try:
            # Filter batch data based on selected columns if provided
            processed_batch = batch
            # Call the evaluation function from config, passing df_analysis data to template
            for chunk in self._evaluate_data(processed_batch, query, plan, 
                                                subgoal=self.subgoal if hasattr(self, 'subgoal') else None,
                                                df_analysis=df_analysis):
                yield chunk

        except Exception as e:
            appLogger.error(f"Error in LLM-driven batch processing: {str(e)}\n{traceback.format_exc()}")
            yield f"""\n**Error processing analysis batch:** {str(e)}\n"""

    def process_query_planning_phase(self, query: str, analysis_plan: Dict = None) -> Generator[str, None, None]:
        """Process an analysis query with dynamic batching."""
        print(f"[GeneralAnalyst] Processing query: {query}")
        try:
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=self.analyst_key,
                value=f"Query: {query}",
                session_id=self.sessionID
            )

            if self.socketio and self.client_id:
                self.socketio.emit("agent_switch", {"agent": "analyst"}, room=self.client_id)

            plan = analysis_plan or {}

            # Ensure reason_behind_this_analysis is included
            if "analyzer_subgoal" in plan and "reason_behind_this_analysis" not in plan:
                plan["reason_behind_this_analysis"] = plan["analyzer_subgoal"]
            
            print(f"[GeneralAnalyst] Analysis plan: {plan}")
            
            if plan.get("clarification_needed", False):
                yield plan.get("clarification_message", "Please clarify your query.")
                return

            # Get and validate data, pass subgoal
            data = self._get_data(subgoal=query)
            if not data:
                print("[GeneralAnalyst] No data found")
                yield "No data found matching your criteria."
                return

            self.num_rows = len(data)
            serialize_data = (data, plan)
            base64_data = base64.b64encode(pickle.dumps(serialize_data)).decode('utf-8')

            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=f"ANALYST_PLAN_CONFIRMATION_{self.uuid}",
                value=str(base64_data),
                session_id=self.sessionID
            )

        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            appLogger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield "Sorry, I encountered an error processing your query. Please try again or rephrase your question."

    def process_query_analysis_phase(self, query: str) -> Generator[str, None, None]:
        """Process an analysis query with dynamic batching."""
        print(f"[GeneralAnalyst] Processing query: {query}")
        try:
            # pull table data from stored database plan
            data_load = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(self.sessionID, self.user_id, f"ANALYST_PLAN_CONFIRMATION_{self.uuid}")
            
            if not data_load:
                print("[GeneralAnalyst] No stored data found for analysis")
                yield "No data found for analysis. Please try running your query again."
                return
                
            try:
                data, plan = pickle.loads(base64.b64decode(data_load[0]["value"].encode('utf-8')))
            except (IndexError, pickle.UnpicklingError, base64.binascii.Error) as e:
                print(f"[GeneralAnalyst] Error loading stored data: {str(e)}")
                yield "Error loading analysis data. Please try running your query again."
                return

            # Emit table to UI after query optimization
            # self._emit_table_to_ui(data)

            # Initialize combined response
            combined_response = []
            
            # Flag to identify if only one batch is used
            single_batch_used = True

            # Calculate df_analysis_results upfront if needed
            df_analysis_markdown = None
            if plan.get("needs_calculation", False):
                print("[GeneralAnalyst] Performing calculations on data")
                df = pd.DataFrame(data)
                calc_results = self.df_analyzer.analyze_data(query, df)
                df_analysis_markdown = self.df_analyzer.format_results(calc_results)
                print(df_analysis_markdown)
                print("[GeneralAnalyst] Calculations complete, results ready to pass to evaluation steps")

            # --- Dynamic Batching Logic ---
            current_batch = []
            current_batch_tokens = 0
            total_items = len(data)
            processed_items = 0
            batch_number = 0

            try:
                base_prompt_text = self.eval_prompt_template(self, [], query, plan, subgoal=query, df_analysis=df_analysis_markdown, quick = plan.get("quick_analysis", False))
                if not isinstance(base_prompt_text, str):
                    base_prompt_text = json.dumps(base_prompt_text)
                base_prompt_tokens = estimate_tokens(base_prompt_text)
            except Exception as e:
                 appLogger.warning(f"Could not estimate base prompt tokens accurately: {e}. Using fallback.")
                 base_prompt_tokens = 1000

            for item in data:
                try:
                    item_str = json.dumps(item)
                    item_tokens = estimate_tokens(item_str)
                except TypeError as e:
                    appLogger.warning(f"Could not serialize item for token estimation: {e}. Skipping item: {item.get(getattr(self, 'id_field', 'id'), 'N/A')}")
                    continue

                if not current_batch or (current_batch_tokens + item_tokens + base_prompt_tokens) <= MAX_TOKENS_PER_BATCH:
                    current_batch.append(item)
                    current_batch_tokens += item_tokens
                else:
                    # If we're creating a second batch, set the flag to False
                    self.single_batch_used = False
                    batch_number += 1
                    if total_items > MAX_TOKENS_PER_BATCH:
                        combined_response.append(f"\nProcessing batch {batch_number} ({len(current_batch)} items)...\n")
                    # Pass df_analysis_markdown to _process_batch
                    for result in self._process_batch(current_batch, query, plan, df_analysis_markdown):
                        combined_response.append(result)
                    processed_items += len(current_batch)

                    current_batch = [item]
                    current_batch_tokens = item_tokens


            if current_batch:
                batch_number += 1
                if batch_number > 1:  # Only show batch info if multiple batches were used
                    self.single_batch_used = False
                    combined_response.append(f"\nProcessing final batch {batch_number} ({len(current_batch)} items)...\n")
                    for result in self._process_batch(current_batch, query, plan, df_analysis_markdown):
                        combined_response.append(result)
                    processed_items += len(current_batch)
                    combined_response.append(f"\n**Analysis complete!**\n")
                    final_response = "".join([str(r) for r in combined_response if r])            
                    yield final_response    
                else:
                    # if just one batch we can do streaming up to the master
                    self.single_batch_used = True
                    for chunk in self._process_batch(current_batch, query, plan, df_analysis_markdown):
                        yield chunk

            # Log completion
            TangoDao.insertTangoState(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                key=self.analyst_key,
                value="Analysis completed",
                session_id=self.sessionID
            )



        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            appLogger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield "Sorry, I encountered an error processing your query. Please try again or rephrase your question."



