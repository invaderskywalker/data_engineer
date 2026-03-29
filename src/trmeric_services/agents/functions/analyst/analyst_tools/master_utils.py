from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
import time, datetime, json
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
import threading
from typing import Dict

def chunk_text(text: str, chunk_size: int = 50) -> list:
    """Split text into chunks of approximately equal size."""
    words = text.split(" ")
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        if current_length + word_length > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    chunks = [c + " " for c in chunks]
    return chunks

def yield_chunks_with_delay(text: str, chunk_size=50):
    """Yield chunks of text with a brief delay between each chunk."""
    for chunk in chunk_text(text, chunk_size):
        time.sleep(0.15)  # Small delay for readability
        yield chunk

def pre_planning_thought():
    # text = """
    # ```json
    # {
    #     "chain_of_thought": "Thanks for the question. Let me take a look at which data types might be relevant here!"
    # }
    # ```
    # """

    text = "Thanks for the question. Let me take a look at which data types might be relevant here...\n"

    for chunk in yield_chunks_with_delay(text, 20):
        yield chunk
        
def planning_thought(plan: dict):
    """Generate an AI-like planning thought process based on the analysis plan.
    
    Args:
        plan (dict): Analysis plan containing analyzer configs and combination logic
        analyzers_to_trigger (list): List of analyzer names to be triggered
    """
    
    # Extract analyzer configs from plan
    analyzer_configs = plan.get("analyzer_configs", [])
    
    thoughts = []
    
    # Add introduction
    if len(analyzer_configs) > 1:
        thoughts.append("### Analysis Plan: \n I'll break this down into multiple steps to give you a comprehensive picture.")
    else:
        thoughts.append("### Analysis Plan: \n ")
    
    # Add thoughts for each analyzer
    for i, config in enumerate(analyzer_configs, 1):
        analyzer_name = config.get("analyzer_name", "").replace("_", " ").strip()
        settings = config.get("analyzer_settings", {})  
        
        analyzer_name_spaced = " ".join(analyzer_name.split())

        # Process subgoal
        raw_subgoal = config.get("analyzer_subgoal", "").strip()
        processed_subgoal = raw_subgoal[:-1].strip() if raw_subgoal.endswith('.') else raw_subgoal
        subgoal_for_sentence = ""
        if processed_subgoal:
            subgoal_for_sentence = processed_subgoal[0].lower() + processed_subgoal[1:]

        # Process parts (calculation_plan, use_clustering)
        parts_phrases = []
        if settings.get("needs_calculation"):
            calculation_plan_value = settings.get('calculation_plan', '').strip()
            if calculation_plan_value.endswith('.'):
                calculation_plan_value = calculation_plan_value[:-1].strip()
            
            if calculation_plan_value:
                first_char_lower = calculation_plan_value[0].lower()
                rest_of_plan = calculation_plan_value[1:]
                processed_calculation_plan = first_char_lower + rest_of_plan
                parts_phrases.append(f"calculate {processed_calculation_plan}")
            else:
                parts_phrases.append("perform necessary calculations") 
        
        if settings.get("use_clustering"):
            parts_phrases.append("group similar items together")
        
        # Process reason
        raw_reason = settings.get("reason_behind_this_analysis", "").strip()
        processed_reason = raw_reason[:-1].strip() if raw_reason.endswith('.') else raw_reason
        reason_for_sentence = ""
        if processed_reason:
            reason_for_sentence = processed_reason.lower()
            
        # Construct the section by joining clauses
        step_clauses = []
        
        main_action_clause = f"I'll analyze the *{analyzer_name_spaced}* data"
        if subgoal_for_sentence:
            main_action_clause += f" to {subgoal_for_sentence}"
        step_clauses.append(main_action_clause)

        if parts_phrases:
            parts_action_clause = f"I'll {' and '.join(parts_phrases)}"
            step_clauses.append(parts_action_clause)
        
        if reason_for_sentence:
            reason_clause = f"This will help *{reason_for_sentence}*"
            step_clauses.append(reason_clause)
            
        final_section_content = ". ".join(filter(None, step_clauses))
        section = f"\n Step {i}: {final_section_content}."
            
        thoughts.append(section)
    
    # Add combination logic if multiple analyzers
    if len(analyzer_configs) > 1 and plan.get("combination_logic"):
        raw_combo_logic = plan.get("combination_logic", "").strip()
        processed_combo_logic = raw_combo_logic[:-1].strip() if raw_combo_logic.endswith('.') else raw_combo_logic

        if processed_combo_logic:
            combo_logic_for_sentence = processed_combo_logic.lower()
            thoughts.append(f"\\nFinally, I'll {combo_logic_for_sentence}.")
        
    thoughts.append("\n\nStarting the analysis... \n\n")
    
    # complete = f"""
    # ```json
    # {{
    #     "chain_of_thought": {" ".join(thoughts)}
    # }}
    # """
    complete = " ".join(thoughts)
    
    for chunk in yield_chunks_with_delay(complete):
        yield chunk
            
def _build_user_context(base_agent):
    return "" if not base_agent else f"{base_agent.context_string}\n{base_agent.org_info_string}\n{base_agent.user_info_string}"
    
def start_planning_thought_thread(plan, socketio, client_id):
    """Start a new thread to run planning thought generation without blocking."""
    def planning_thought_worker():
        try:
            print("[MasterAnalyst] Starting planning thought thread")
            for chunk in planning_thought(plan):
                if socketio and client_id:
                    socketio.emit("tango_chat_assistant", chunk, room=client_id)
            print("[MasterAnalyst] Planning thought thread completed")
        except Exception as e:
            appLogger.error(f"ERROR in planning thought thread: {str(e)}\n{traceback.format_exc()}")
    
    # Start the thread without waiting for completion
    thought_thread = threading.Thread(target=planning_thought_worker)
    thought_thread.daemon = True  # Thread will exit when main program exits
    thought_thread.start()
    print("[MasterAnalyst] Planning thought thread started")
    
def start_preplanning_thought_thread(socketio, client_id):
    """Start a new thread to run pre-planning thought generation without blocking."""
    def preplanning_thought_worker():
        try:
            print("[MasterAnalyst] Starting pre-planning thought thread")
            for chunk in pre_planning_thought():
                if socketio and client_id:
                    socketio.emit("tango_chat_assistant", chunk, room=client_id)
            print("[MasterAnalyst] Pre-planning thought thread completed")
        except Exception as e:
            appLogger.error(f"ERROR in pre-planning thought thread: {str(e)}\n{traceback.format_exc()}")
    
    # Start the thread without waiting for completion
    thought_thread = threading.Thread(target=preplanning_thought_worker)
    thought_thread.daemon = True  # Thread will exit when main program exits
    thought_thread.start()
    print("[MasterAnalyst] Pre-planning thought thread started")

def plan_combined_analysis(query, llm, socketio, client_id, user_context, analyzer_configs) -> Dict:
    print(f"[MasterAnalyst] Planning analysis for query: {query}")
    if not llm:
        raise ValueError("LLM instance is required for planning")

    # Convert column structure to schema format for LLM
    analyzer_schemas = {}
    for name, config in analyzer_configs.items():
        if "columns" in config:
            fields = {
                col["name"]: col["description"] 
                for col in config["columns"]
            }
            analyzer_schemas[name] = {"fields": fields}

    system_prompt = f"""
    User query: \"{query}\"
    User context: {user_context}
    Current Date: {datetime.datetime.now().date().isoformat()}
    Available analyzers: {json.dumps(analyzer_schemas, indent=2)}
    
    Analyzer Selection Guidelines: 
    
    For specific information about people, even if related to projects/roadmaps, use the capacity analyzer.
    Plans are defined as roadmaps, as they represent future projects.
    
    Remember that roadmaps represent future projects and strategic initiatives.
    Focus on strategic alignment, resource planning, and portfolio impact.

    Plan analysis that might need multiple analyzers. Consider:
    1. Query intent requires:
        - Single analyzer (e.g., "list delayed projects") 
        - Multiple analyzers (e.g., "compare roadmap objectives with project progress")
        
    2. Sub-query generation:
        - Break complex queries into analyzer-specific sub-queries
        - Do NOT lose entity types such as project, portfolio, etc. in subgoals. Be as precise as possible.
        - Each sub-query should match an analyzer's capabilities
        - Maintain all keywords and context from the original query, words like portfolio, tech stack, etc..
        
    3. Combination logic:
        - How to merge results meaningfully
        - What relationships to look for
        - How to present combined insights
        - null if only one analyzer used
        - SEQUENTIAL - if the analyzers are dependent on each other (
        - PARALLEL - if the analyzers are independent of each other

    4. Analyzer settings - Include all required properties for each analyzer:
        - needs_calculation: Set to true for queries needing statistical/numerical calculations
        - calculation_plan: Detailed description of calculations needed (e.g., "calculate average budget of AI projects")
        - use_clustering: Set to true if similar items need to be grouped
        - web_search: final analysis will have the ability to search the web for questions - only if the question requires it
        - reason_behind_this_analysis: Short description of the analysis purpose, used in evaluation templates
        - quick_analysis: If there is a targeted simple question such as show me Project A's scopes, or show me Portfolio A's average budget, then turn this on - skips detailed analysis
        
    Tool Definitions:
    Calculation - This can be turned on to allow for mathematical calculations at a further step, including substring contains
    Clustering - Use if the entity needs to be grouped by similarity and an embedding layer will implement similarity search

    IMPORTANT:
    - If you set the combination type as sequential, the subgoal of the early analyzers should frame the output to give the relevant context for the second analyzer.
    - quick_analysis reflects whether or not there should be a lengthy analysis AFTER the data is retrieved, NOT including whether the SQL query will be complex. If the actual analysis is simple, leave this on. Should be off for very specific targetted questions and on for open-ended questions.
    - quick_analysis should most likely be off if a user asks for something that is not a provided column, as we will then make our own analysis afterwards to produce an answer for them.
    
    Output format:
    {{
        "analyzer_configs": [
            {{
                "analyzer_name": "roadmap",
                "analyzer_subgoal": "Find the average budgets of the AI roadmaps, compare to current industry standards",
                "analyzer_settings": {{
                    "needs_calculation": true,
                    "calculation_plan": "calculate average budget of AI projects",
                    "use_clustering": false,
                    "web_search": true,
                    "reason_behind_this_analysis": "To understand budget allocation across AI initiatives",
                    "quick_analysis": true
                }}
            }},
            {{
                "analyzer_name": "project",
                "analyzer_subgoal": "group projects by similarity into three sections",
                "analyzer_settings": {{
                    "needs_calculation": false,
                    "calculation_plan": null,
                    "use_clustering": true,
                    "web_search": false,
                    "reason_behind_this_analysis": "To identify patterns in project types",
                    "quick_analysis": false
                }}
            }}
        ],
        "combination_logic": "How to combine the results (null if only one analyzer used)",
        "combination_type": <"SEQUENTIAL" or "PARALLEL">,
        "clarification_needed": false,
        "clarification_message": null
    }}

    Note: Roadmaps are defined as future plans or future projects to be created
    """

    chat_completion = ChatCompletion(
        system=system_prompt, 
        prev=[], 
        user=f"Create analysis plan for: '{query}'"
    )
    
    response = llm.run(
        chat_completion,
        ModelOptions(model="gpt-4o", max_tokens=1024, temperature=0),
        'tango::master::plan',
        None
    )
    print(f"[MasterAnalyst] Analysis plan received: {response}")

    try:
        plan = extract_json_after_llm(response)
        print(f"[MasterAnalyst] Extracted plan configuration:\n  - \n - Analyzers: {plan.get('analyzer_configs', [])}")
        
        # Start the planning thought thread in the background
        start_planning_thought_thread(plan, socketio, client_id)
        
        return plan
    except json.JSONDecodeError:
        raise ValueError(f"Invalid planning response: {response}")