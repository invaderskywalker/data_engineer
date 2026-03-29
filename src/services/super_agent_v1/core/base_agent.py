# src/trmeric_services/super_agent_v1/core/base_agent.py

import json
import traceback
from datetime import datetime
from typing import Dict, Any, List, Generator

from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion, ModelOptions2
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.helper.common import MyJSON
from src.trmeric_utils.helper.event_bus import Event, event_bus
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.super_agent_v1.config import *
from .func_utils import format_actions_with_docs_and_defaults
from .actions import DataActions
from .runtime_policy import AgentRuntimePolicy
from .context_builder import ContextBuilder
from .steps_sender import SocketStepsSender
from .rules import *
from .helper import *
from src.trmeric_database.Redis import RedClient

import re
from .const import *
from .prompt import *
from .utils import *
from .node_utils import run_node_script, sanitize_js_strings
import uuid
from src.trmeric_database.dao import AgentRunDAO
from src.trmeric_utils.helper.decorators import log_function_io_and_time
from src.trmeric_services.agents.functions.graphql_v2.utils.tenant_helper import is_knowledge_integrated

import os
from pathlib import Path

def get_file_created_time(path: str) -> float:
    try:
        stat = os.stat(path)

        # macOS / BSD
        if hasattr(stat, "st_birthtime"):
            return stat.st_birthtime
        # Linux fallback (mtime)
        return stat.st_mtime

    except Exception as e:
        appLogger.warning({
            "event": "file_time_fallback",
            "path": path,
            "error": str(e)
        })
        return 0.0  # earliest possible → pushed to top

def format_section_title(section_id: str) -> str:
    if not section_id:
        return ""

    words = section_id.replace("_", " ").strip().split()

    # Preserve common acronyms
    acronyms = {"ai", "api", "ml", "ui", "ux", "kpi"}

    formatted = [
        word.upper() if word.lower() in acronyms else word.capitalize()
        for word in words
    ]

    return " ".join(formatted)

import os
from pathlib import Path

def get_file_created_time(path: str) -> float:
    try:
        stat = os.stat(path)

        # macOS / BSD
        if hasattr(stat, "st_birthtime"):
            return stat.st_birthtime
        # Linux fallback (mtime)
        return stat.st_mtime

    except Exception as e:
        appLogger.warning({
            "event": "file_time_fallback",
            "path": path,
            "error": str(e)
        })
        return 0.0  # earliest possible → pushed to top

def format_section_title(section_id: str) -> str:
    if not section_id:
        return ""

    words = section_id.replace("_", " ").strip().split()

    # Preserve common acronyms
    acronyms = {"ai", "api", "ml", "ui", "ux", "kpi"}

    formatted = [
        word.upper() if word.lower() in acronyms else word.capitalize()
        for word in words
    ]

    return " ".join(formatted)

# ============================================================
# SUPER AGENT
# ============================================================

class SuperAgent:
    """
    Super Agent
        - Rough plan (mind map)
        - Sequential execution planning
        - Cognitive thinking gate
        - Grounded execution
        - Streaming response
    """

    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        session_id: str,
        agent_name: str,
        config: Dict[str, Any],
        socketio=None,
        client_id=None,
        run_id=''
    ):
        self.name = agent_name
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.socketio = socketio
        self.client_id = client_id
        
        self.research_file_path = None
        self.deep_exported = False
        self.final_report_exported = False
        self.section_plan = None
        self.current_section_index = 0
        self.current_section_state = None

        # ---- Policy (compiled cognition) ----
        self.policy = AgentRuntimePolicy(config)
        self.mode = "analysis"
        # self.deep_research_mode = "research"

        # ---- LLM ----
        self.llm = ChatGPTClient(user_id, tenant_id)
        self.model_options = ModelOptions(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMP,
        )

        # ---- Context ----
        self.context_builder = ContextBuilder(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )

        self.context_string = self.context_builder.build_context(self.name)
        # print("self.context_string", self.context_string)
        
        self.current_rough_step_id = 0
        self.current_execution_id = 0
        self.current_parent_event_id = 0

        self.data_actions = None
        
        # ---- State ----
        self.rough_plan: Dict[str, Any] = {}
        self.execution_phase_plan: Dict[str, Any] = {}
        self.execution_plans: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self.charts = []
        self.exports = []
        
        self.export_counter = 0
        def _on_artifact_created(event: Event):
            payload = event.payload

            if payload.get("artifact_type") == "export":
                self.exports.append(payload)
            if payload.get("artifact_type") == "chart":
                self.charts.append(payload)
                
        self._artifact_callback = _on_artifact_created
        event_bus.subscribe(
            "AGENT_ARTIFACT_CREATED",
            session_id=self.session_id,
            callback=self._artifact_callback,
        )

        self.log_info = {"tenant_id": tenant_id, "user_id": user_id}
        self.run_id = run_id

        debugLogger.info({
            "event": "SuperAgentInitialized",
            "agent": agent_name,
            "session_id": session_id,
        })
        
        # ---- Event subscriptions ----
        self.event_bus = event_bus
        self.socket_sender = SocketStepsSender("tango", socketio, client_id)
        self.ask_clarification = False

        def _on_step_event(event: Event):
            if event.type == "STEP_UPDATE":
                payload = event.payload
                msg = payload.get("message")
                if msg and socketio:
                    if msg and socketio:
                        self.socketio.emit(
                            "event_updated",
                            {},
                            room=self.client_id
                        )
                        # self.socket_sender.sendSteps(msg, False)
                        
            if event.type == "THOUGHT_AI_DAO":
                payload = event.payload
                msg = payload.get("message")
                self._create_event(
                    step_id=self.current_step_id,
                    parent_event_id=self.current_parent_event_id,
                    event_type=AgentRunDAO.THOUGHT,
                    event_name=AgentRunDAO.PLANNING_RATIONALE,
                    local_index=int(payload.get("size")),
                    payload={
                        "content": msg,
                    }
                )
                
                        
        self._step_callback = _on_step_event
        event_bus.subscribe(
            "STEP_UPDATE",
            session_id=self.session_id,
            callback=self._step_callback,
        )
        event_bus.subscribe(
            "THOUGHT_AI_DAO",
            session_id=self.session_id,
            callback=self._step_callback,
        )
        self.current_step_id = None
        self.sequence_counter = 0
        self.step_index = 0
        
        # self.sub_agent_plans = []
        def _on_llm_plan_update(event: Event):
            payload = event.payload
            if len(self.execution_plans) > 0:
                if not self.execution_plans:
                    return
                if "plan" in payload:
                    # current_plan = self.execution_plans[-1]
                    # if "sub_agent_plans" not in current_plan:
                    #     current_plan["sub_agent_plans"] = []
                    # # current_plan["sub_agent_plans"].append(payload)
                    
                    AgentRunDAO.create_run_step(
                        session_id=self.session_id,
                        tenant_id=str(self.tenant_id),
                        user_id=str(self.user_id),
                        agent_name=self.name,
                        run_id=self.run_id,
                        step_type=AgentRunDAO.SUB_EXECUTION_PLAN,
                        step_index=self.step_index,
                        step_payload=payload,
                        status=AgentRunDAO.COMPLETED
                    )
                
                if "trigger" in payload and payload.get("trigger") == "important_step":
                    ## write here 
                    agent_name = payload.get("agent_name") or "Agent: "
                    self.current_parent_event_id = self._create_event(
                        step_id=self.current_step_id,
                        parent_event_id=self.current_execution_id,
                        event_type=AgentRunDAO.MAIN_STEP,
                        event_name=AgentRunDAO.MARKER,
                        local_index=0,
                        payload={
                            "content": f"{agent_name}"
                        }
                    )
                if "info" in payload and payload.get("info") == "step":
                    self.current_parent_event_id = self._create_event(
                        step_id=self.current_step_id,
                        parent_event_id=self.current_execution_id,
                        event_type=AgentRunDAO.MAIN_STEP,
                        event_name=AgentRunDAO.MARKER,
                        local_index=0,
                        payload={
                            "content": payload.get("content")
                        }
                    )
                

        self._on_llm_plan_update = _on_llm_plan_update
        event_bus.subscribe(
            "LLM_PLAN_UPDATE",
            session_id=self.session_id,
            callback=self._on_llm_plan_update
        )
        self.conv = "No prior conv"
        
    def set_context(self):
        if self.mode == "deep_research":
            permitted = DEEP_RESEARCH_ALLOWED_ACTIONS.copy()
        elif self.mode == "context_building":
            permitted = CONTEXT_BUILDING_ALLOWED_ACTIONS.copy()
        else:
            permitted = ANALYSIS_ALLOWED_ACTIONS.copy()

        knowledge_graph_available = is_knowledge_integrated(self.tenant_id)
        knowledge_graph_available = False # TEMPORARY DISABLE OF TANGO USE OF KNOWLEDGE
        # Knowledge graph functions that require graph integration
        # Consolidated into 2 parameter-driven functions + 3 compound functions
        knowledge_graph_functions = [
            "fetch_cluster_info",
            "fetch_performance_analysis",
            "fetch_performance_landscape",
            "analyze_project_in_context",
            "find_success_patterns",
        ]
        
        if knowledge_graph_available:
            # Add knowledge graph functions to permitted actions
            permitted.update(knowledge_graph_functions)
            appLogger.info({
                "event": "knowledge_graph_capabilities_enabled",
                "tenant_id": self.tenant_id,
                "session_id": self.session_id,
                "graphname": knowledge_graph_available,
                "enabled_functions": knowledge_graph_functions
            })
        else:
            appLogger.info({
                "event": "knowledge_graph_capabilities_disabled",
                "tenant_id": self.tenant_id,
                "session_id": self.session_id,
                "reason": "knowledge_graph_not_integrated",
                "unavailable_functions": knowledge_graph_functions
            })

        self.allowed_fn_maps = {
            name: fn
            for name, fn in self.data_actions.fn_maps.items()
            if name in permitted
        }
        
        self.actions_description = f"""
        AVAILABLE ACTIONS AND DEFINITION OF THOSE ACTIONS AND HOW TO USE
        =================
        {format_actions_with_docs_and_defaults(self.allowed_fn_maps)}
        """
        self.more_defs_ai_dao_parts = ""
        ######## 
        self.system_capability_description = AIDAO_CAPABILITY_DESCRIPTION
        # 🔑 SINGLE CANONICAL CONTEXT BLOCK
        self.capability_context = f"""
            ----------------------------
            AI Analyst FULL DESCRIPTION:
                <ai_analyst_full_description>
                {self.system_capability_description}
                {self.more_defs_ai_dao_parts}
                </ai_analyst_full_description>
            --------------------------------
            All avaialbe actions: 
            -----------------------------
                <avaiable_actions>
                {self.actions_description}
                </avaiable_actions>
        """.strip()
    

    # ============================================================
    # ROUGH PLAN (INTENT & SCOPE SKETCH)
    # ============================================================
    @log_function_io_and_time
    def create_rough_plan(self, query: str) -> Dict[str, Any]:
        print("create_rough_plan---")
        if self.policy.mode == "deep_research":
            output_struct = DEEP_SEARCH_ROUGH_PLAN_SCHEMA
        else:
            output_struct = DEEP_SEARCH_ROUGH_PLAN_SCHEMA_NORMAL
        
        files_in_run = self._get_files_created_in_run()
        system_prompt = f"""
            You are thinking like a human decision-maker sketching an approach.
            
            {GLOBAL_RULE_TRMERIC_SHORT}
            {ROUGH_PLAN_DECISION_RULES}
            {TRMERIC_AGENT_CAPABILITY_SUMMARY}
            {TRMERIC_DOMAIN_HINTS}
            {TRMERIC_FUNCTIONAL_CAPABILITIES}
            
            ────────────────────────────────────────────────────────────
            CONVERSATION HISTORY
            ────────────────────────────────────────────────────────────

            {self.conv if self.conv != "No prior conversation." else "This is the start of a new conversation."}
            

            ────────────────────────────────────────────────────────────
            CONTEXT
            ────────────────────────────────────────────────────────────

            Enterprise Context:
            {self.context_string}

            
            Existing Research Files (if any):
            {self.research_done_in_session}
            
            Workspace Artifact Files From This Session (if any):
            {files_in_run}
            These are files already generated in this session (.js scripts,
            .html reports, .md documents, etc.)
            
            RESEARCH REUSE RULE

                If existing research files are present AND the user request is:
                    • transformation
                    • formatting
                    • redesign
                    • export

                Then:
                    intent_class = transformational
                    Do NOT plan new research.
                    Reuse existing research.
                    
                If existing research exists:
                    • Prefer reuse over regeneration
                    • Do NOT re-run deep research unless user explicitly asks to re-analyze

            ────────────────────────────────────────────────────────────
            OUTPUT FORMAT (STRICT JSON)
            ────────────────────────────────────────────────────────────

            You MUST return JSON that exactly matches this schema:

            {MyJSON.dumps(output_struct, indent=2)}

            Do not add extra fields.
            Do not include explanations outside JSON.
        """

        user_prompt = f"""
            ────────────────────────────────────────────────────────────
            TRANSFORMATION GATE — READ FIRST:
            ────────────────────────────────────────────────────────────

            research_done_in_session (deep research markdown files):
            {self.research_done_in_session if self.research_done_in_session else "EMPTY — NO RESEARCH FILES EXIST"}

            transformation is ONLY valid when the above is NOT EMPTY.
            {"⛔ research_done_in_session is EMPTY → transformation is FORBIDDEN → use analysis" if not self.research_done_in_session else "✅ research files exist → transformation MAY apply if user explicitly asks to export them"}

            ────────────────────────────────────────────────────────────
    
            Today's date is {datetime.utcnow().strftime("%B %d, %Y")}
            
            My Query:
            {query}

            Rules:
                • Respond ONLY with valid JSON
                • No markdown
                • No commentary
            Output JSON in this format: {MyJSON.dumps(output_struct, indent=2)}
            REMEMBER:
                • If research files exist AND user wants to improve/redesign/export → transformation
                • Default is analysis — not deep_research
                • deep_research ONLY when the document requires FETCHING live enterprise data section by section
                • PRDs, technical specs, strategy docs, plans written from user-provided context → analysis + report_doc (NOT deep_research)
                • The one test: "Does answering this require multiple database queries across different entities?" If NO → analysis + report_doc
                • A document being "formal" or "detailed" does NOT qualify for deep_research
                • When in doubt between analysis and deep_research → analysis + report_doc
                • When in doubt between analysis and transformation → transformation if files exist
        """
        
        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt,
        )
        
        # print("create rough plan prompt  -- ", chat.formatAsString())

        rough_plan = ""
        printed = set()
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::rough_plan",
            logInDb=self.log_info
        ):
            rough_plan += chunk
            # ─────────────────────────────────────
            # STREAM objective
            # ─────────────────────────────────────
            if "message_for_user" not in printed:
                obj_match = re.search(
                    r'"message_for_user"\s*:\s*"([^"]+)"',
                    rough_plan
                )
                if obj_match:
                    text = obj_match.group(1).strip()
                    printed.add("message_for_user")

                    msg = f"{text}"
                    event_bus.dispatch(
                        "STEP_UPDATE",
                        {"message": msg},
                        session_id=self.session_id
                    )
                    self._create_event(
                        step_id=self.current_step_id,
                        event_type=AgentRunDAO.THOUGHT,
                        event_name=AgentRunDAO.PLANNING_RATIONALE,
                        parent_event_id=self.current_rough_step_id,
                        payload={"content": msg},
                    )
                    
            # ─────────────────────────────────────
            # STREAM thought_process items
            # ─────────────────────────────────────
            if '"thought_process"' in rough_plan:
                match = re.search(
                    r'"thought_process"\s*:\s*\[([^\]]*)',
                    rough_plan,
                    re.DOTALL
                )
                if match:
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    for thought in items:
                        key = f"thought::{thought}"
                        if key not in printed:
                            printed.add(key)
                            self._create_event(
                                step_id=self.current_step_id,
                                event_type=AgentRunDAO.THOUGHT,
                                event_name=AgentRunDAO.PLANNING_RATIONALE,
                                parent_event_id=self.current_rough_step_id,
                                payload={"content": thought},
                            )

            
        print("rough plann -- ", rough_plan)             
        plan = extract_json_after_llm(rough_plan)
        self.rough_plan = plan
        return plan


    # ============================================================
    # SEQUENTIAL EXECUTION PLANNER (DIRECTIONAL, EPISTEMICALLY AWARE)
    # ============================================================
    @log_function_io_and_time
    def generate_next_execution_plan(self, step_index: int, query: str) -> Dict[str, Any]:

        if self.mode == "context_building":
            execution_rules = TRUCIBLE_EXECUTION_RULES
            execution_persona = TRUCIBLE_SYSTEM_PROMPT
        elif self.mode == "ideation":
            execution_rules = TRMERIC_IDEATION_EXECUTION_RULES
            execution_persona = TRMERIC_IDEATION_SYSTEM_PROMPT
        else:
            execution_rules = TRMERIC_ANALYSIS_EXECUTION_RULES
            execution_persona = TRMERIC_ANALYSIS_SYSTEM_PROMPT

        files_in_run = self._get_files_created_in_run()
        output_structure = self.policy.execution_step_schema
        if self.mode == "analysis":
            output_structure = EXECUTION_STEP_SCHEMA_2

        # ── Build a compact phase status summary for the prompt ──────────────────
        # This replaces the raw execution_phase_plan JSON with a clear state summary
        # so the planner doesn't have to parse nested JSON to know where it is.
        phase_status_block = ""
        if self.execution_phase_plan:
            phases = self.execution_phase_plan.get("phases", [])
            idx    = self.execution_phase_plan.get("current_phase_index", 0)
            lines  = []
            for i, ph in enumerate(phases):
                marker = "→ ACTIVE" if i == idx else ("✓ DONE" if ph.get("status") == "done" else "  pending")
                lines.append(f"  [{i}] {ph['phase_id']}  {marker}")
                if i == idx:
                    # Show what the active phase needs
                    if ph["phase_id"] == "fetch":
                        for f in ph.get("fetches_needed", []):
                            lines.append(f"       entity: {f['entity']}")
                            lines.append(f"       requirement_focus: {f['requirement_focus']}")
                    elif ph["phase_id"] == "produce":
                        for a in ph.get("artifacts", []):
                            lines.append(f"       artifact: {a['type']}  action: {a['action']}")
                            lines.append(f"       requirement_focus: {a['requirement_focus']}")
                            if a.get("chart_intent"):
                                lines.append(f"       chart_intent: {a['chart_intent']}")
                    elif ph["phase_id"] == "ingest":
                        for f in ph.get("files_to_read", []):
                            lines.append(f"       file: {f}")

            active_phase = phases[idx] if idx < len(phases) else None
            phase_status_block = f"""
                ── EXECUTION PHASE PLAN ─────────────────────────────────────
                Phases:
                {chr(10).join(lines)}

                Active phase index: {idx}
                Active phase_id:    {active_phase["phase_id"] if active_phase else "none — all phases done"}

                PHASE COMPLETE RULE (read carefully):
                You MUST set phase_complete: true on the SAME step where the last action of this phase runs.
                FETCH phase complete when: all fetches_needed entities appear in Execution Results
                INGEST phase complete when: all files_to_read appear in Execution Results  
                PRODUCE phase complete when: artifact S3 signal detected OR exported: true in results

                When phase_complete: true → the loop will advance current_phase_index.
                When current_phase_index reaches {len(phases)} (past last phase) → should_continue = false.
                ─────────────────────────────────────────────────────────────
            """
        else:
            phase_status_block = "No execution_phase_plan (non-analysis mode — use self_assessment to determine next step)"

        system_prompt = f"""
            {execution_persona}
            {execution_rules}
            
            {TRMERIC_FUNCTIONAL_CAPABILITIES}

            ────────────────────────────────────────────────────────────
            RUN CONTEXT
            ────────────────────────────────────────────────────────────

            Run ID: {self.run_id}

            Rough Plan (intent + complexity):
            {MyJSON.dumps(self.rough_plan)}

            {phase_status_block}

            Enterprise Context:
            {self.context_string}
            
            ── Files Written To Workspace In This Session ──
            {files_in_run}
            These files already exist on disk.
            • Read a file before updating it — never overwrite blindly.
            • Never re-create a file that already exists here.
            • ARTIFACT USAGE RULE (STRICT):
                If an action depends on the contents of an existing file:
                • Either the action must internally load and parse the file
                • OR you must call read_files before using it
                Never assume file structure or content without explicit access.

            🔒 FILE SOURCE PRIORITY RULE (CRITICAL)
                If a file exists in FILES WRITTEN TO WORKSPACE → use read_file
                NOT read_file_details_with_s3_key
                S3 read only for user-uploaded files not in workspace.

            Execution Results (including artifact state):
            {MyJSON.dumps(self.results)}

            ────────────────────────────────────────────────────────────
            AVAILABLE ACTIONS — CAPABILITY REFERENCE
            ────────────────────────────────────────────────────────────
            
            {self.capability_context}
            
            ────────────────────────────────────────────────────────────
            LEGAL ACTION NAMES (STRICT — COPY EXACTLY)
            ────────────────────────────────────────────────────────────

            You MUST only use action names from this exact list:
            {list(self.allowed_fn_maps.keys())}

            Any action name NOT in this list is INVALID.
            Do not invent action names.
            Do not use section headers or description titles as action names.
            Copy the action name character-for-character from the list above.

            ────────────────────────────────────────────────────────────
            OUTPUT FORMAT (STRICT)
            ────────────────────────────────────────────────────────────

            Return exactly ONE JSON object:
            {MyJSON.dumps(output_structure, indent=2)}

            No extra fields. No commentary.
            Today: {datetime.utcnow().strftime("%B %d, %Y")}
        """

        user_prompt = f"""
            ORIGINAL USER QUERY:
            {query}
        
            Conversation History:
            {self.conv if self.conv != "No prior conversation." else "New conversation."}
            
            REMINDER — only these action names are valid:
            {list(self.allowed_fn_maps.keys())}
            
            ────────────────────────────────────────────────────────────
            FILE READ-BEFORE-UPDATE RULE (NON-NEGOTIABLE):
            ────────────────────────────────────────────────────────────

            If the user wants to UPDATE, EDIT, or IMPROVE an existing file:
            Step 1 → read_files                  should_continue: true
            Step 2 → update the file             should_continue: true
            Step 3 → respond or export

            NEVER jump straight to a write action on a file you have not read this run.
            If the file is NOT in FILES WRITTEN TO WORKSPACE → create it fresh.
            
            ────────────────────────────────────────────────────────────
            SELF-ASSESSMENT (fill in honestly before deciding):
            ────────────────────────────────────────────────────────────

            1. what_user_wants     → from ORIGINAL USER QUERY
            2. what_we_have_so_far → name entities and row counts from THIS run only
            3. data_quality_check  → sufficient for chat answer? sufficient for document?
            4. what_is_still_missing → exact gap OR "Nothing — ready to respond"
            5. can_we_respond_now  → true ONLY if data_quality_check confirms sufficiency

            ────────────────────────────────────────────────────────────
            CROSS-RUN STATE RULE (CRITICAL)
            ────────────────────────────────────────────────────────────

            Analytical data does NOT persist across runs.
            Conversation history shows conclusions only — not raw data.
            If data is not in Execution Results of THIS run → you do NOT have it.

            ────────────────────────────────────────────────────────────
            should_continue RULE:
            ────────────────────────────────────────────────────────────

            Any step with an action   → should_continue: true  (ALWAYS)
            Pure assessment, no action → should_continue: false (ONLY)
            
            ────────────────────────────────────────────────────────────
            ANTI-LOOP (highest priority):
            ────────────────────────────────────────────────────────────

            Any action already in Execution Results → MUST NOT be selected again.
            A blocked/failed action → do not retry in same run.
            Data in Execution Results → you have it, do not re-fetch.
        """

        chat = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

        streamed = ""
        printed  = set()

        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::next_step",
            logInDb=self.log_info,
        ):
            streamed += chunk

            if '"rationale_for_user_visibility"' in streamed:
                match = re.search(
                    r'"rationale_for_user_visibility"\s*:\s*\[([^\]]*)',
                    streamed,
                    re.DOTALL
                )
                if match:
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    for t in items:
                        if t not in printed:
                            event_bus.dispatch(
                                "STEP_UPDATE",
                                {"message": t, "stage": "execution_planning", "step_index": step_index},
                                session_id=self.session_id
                            )
                            self._create_event(
                                step_id=self.current_step_id,
                                parent_event_id=self.current_execution_id,
                                event_type=AgentRunDAO.THOUGHT,
                                event_name=AgentRunDAO.EXECUTION_PLAN,
                                local_index=len(printed),
                                payload={"content": t}
                            )
                            printed.add(t)

        plan       = extract_json_after_llm(streamed)
        assessment = plan.get("self_assessment", {})
        has_action = bool((plan.get("current_best_action_to_take") or {}).get("action"))
        has_action = has_action and self.mode != "chat"

        # ── Standard stop conditions (non-analysis OR no phase plan) ─────────────
        if not has_action:
            if assessment.get("can_we_respond_now") is True:
                plan["should_continue"] = False
            missing = assessment.get("what_is_still_missing", "") or ""
            if missing.lower().startswith("nothing"):
                plan["should_continue"] = False

        max_steps  = {"light": 3, "medium": 5, "heavy": 8}
        complexity = self.rough_plan.get("complexity_signal") or "medium"
        if not has_action and len(self.results) >= max_steps.get(complexity, 5):
            plan["should_continue"] = False

        # ── Phase advancement (analysis mode only) ────────────────────────────────
        # Runs AFTER the LLM response so the NEXT loop iteration sees the update.
        if self.execution_phase_plan:
            phases = self.execution_phase_plan.get("phases", [])
            idx    = self.execution_phase_plan.get("current_phase_index", 0)

            # ── Infer phase_complete if planner forgot to set it ──────────────
            # Don't rely solely on plan.get("phase_complete").
            # Check whether the current phase's work is actually done
            # by inspecting what actions ran in self.results.

            phase_complete = plan.get("phase_complete", False)

            if not phase_complete and idx < len(phases):
                current_phase = phases[idx]
                phase_id = current_phase.get("phase_id")

                if phase_id == "fetch":
                    # Fetch is done if the last action in results was a fetch action
                    if self.results:
                        last_action = (self.results[-1] or {}).get("result", {}).get("action", "")
                        fetches_needed = current_phase.get("fetches_needed", [])
                        fetches_done   = [
                            r.get("result", {}).get("action", "")
                            for r in self.results
                            if r.get("result", {}).get("action", "").startswith("fetch_")
                        ]
                        # Phase complete if all fetches_needed entities have a matching action
                        needed_entities = {f.get("entity", "") for f in fetches_needed}
                        done_entities   = {
                            a.replace("fetch_", "").replace("_data_using_roadmap_agent", "roadmaps")
                             .replace("_data_using_project_agent", "projects")
                             .replace("_data_using_idea_agent", "ideas")
                            for a in fetches_done
                        }
                        # Simpler: if any fetch ran and the planner said can_we_respond_now,
                        # the fetch phase is done
                        if fetches_done and plan.get("self_assessment", {}).get("can_we_respond_now"):
                            phase_complete = True
                            appLogger.info({
                                "event": "phase_complete_inferred",
                                "phase_id": phase_id,
                                "reason": "fetch ran + planner assessed data as sufficient",
                            })

                elif phase_id == "produce":
                    # Produce is done if any artifact signal exists in results
                    for r in self.results:
                        # output = (r.get("result") or {}).get("output") or {}
                        output = (r.get("result") or {}).get("output")
                        # s3_key = output.get("s3_key", "")
                        # output = (r.get("result") or {}).get("output")

                        # 👉 HANDLE BOTH CASES SAFELY
                        if not isinstance(output, dict):
                            continue

                        s3_key = output.get("s3_key", "")
                        if "charts_" in s3_key or "tables_" in s3_key or output.get("exported"):
                            phase_complete = True
                            appLogger.info({
                                "event": "phase_complete_inferred",
                                "phase_id": phase_id,
                                "reason": "artifact signal detected in results",
                            })
                            break

            # ── Advance phase if complete ─────────────────────────────────────
            if phase_complete and idx < len(phases):
                phases[idx]["status"] = "done"
                completed_id = phases[idx]["phase_id"]
                next_idx = idx + 1
                self.execution_phase_plan["current_phase_index"] = next_idx

                # Phase done event
                phase_labels = {
                    "ingest":  "Files Read",
                    "fetch":   "Data Retrieved",
                    "produce": "Artifact Generated",
                }
                self._create_event(
                    step_id=self.current_step_id,
                    event_type=AgentRunDAO.MAIN_STEP,
                    event_name=AgentRunDAO.MARKER,
                    parent_event_id=self.current_execution_id,
                    payload={"content": f"✓ {phase_labels.get(completed_id, completed_id.title())}"}
                )

                appLogger.info({
                    "event":           "phase_advanced",
                    "completed_phase": completed_id,
                    "next_index":      next_idx,
                    "phases_total":    len(phases),
                    "all_done":        next_idx >= len(phases),
                })

                # Next phase starting event
                if next_idx < len(phases):
                    next_phase_id = phases[next_idx]["phase_id"]
                    next_labels = {
                        "ingest":  "Reading Files",
                        "fetch":   "Fetching Data",
                        "produce": "Generating Artifact",
                    }
                    self._create_event(
                        step_id=self.current_step_id,
                        event_type=AgentRunDAO.MAIN_STEP,
                        event_name=AgentRunDAO.MARKER,
                        parent_event_id=self.current_execution_id,
                        payload={"content": next_labels.get(next_phase_id, next_phase_id.title())}
                    )

                # ── Force continue if more phases remain ──────────────────────
                # Planner may have set should_continue=false thinking it's done.
                # If there are still phases (e.g. produce), override it.
                if next_idx < len(phases):
                    if not plan.get("should_continue", True):
                        appLogger.info({
                            "event":  "should_continue_overridden",
                            "reason": f"phase {completed_id} done but phase index {next_idx} ({phases[next_idx]['phase_id']}) still pending",
                        })
                    plan["should_continue"] = True   # force loop to continue

                else:
                    # All phases done — hard stop
                    plan["should_continue"] = False
                    appLogger.info({"event": "all_phases_complete", "stopping": True})



        self.execution_plans.append(plan)
        return plan

    # ============================================================
    # SERIOUS EXECUTION PLANNER
    # ============================================================
    @log_function_io_and_time
    def create_execution_plan(self, query: str) -> Dict[str, Any]:
        """
        Creates a structured phase plan ONCE before the execution loop.
        Stored as self.execution_phase_plan.
        The loop reads current_phase_index to know where it is.
        """
        user_prompt = f"""
            CURRENT RUN ID:
            {self.run_id}

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            CROSS-RUN DATA INDEPENDENCE (CRITICAL — READ BEFORE PLANNING)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Enterprise data (roadmaps, projects, ideas, etc.) does NOT persist between runs.
            Each run starts with an empty analytical memory.

            Workspace files (documents, markdown, PRDs written in prior runs) DO persist
            and can be ingested — but they contain only the output, not the raw source data.

            This means:
            • If the task requires reading or reasoning about enterprise entity data
            (even to EDIT or EXTEND something already written), a fetch phase is MANDATORY.
            • "Add user stories to the PRD" → fetch the roadmap again. The PRD file exists,
            but the roadmap data it was based on is gone.
            • "Update the document with X" → if X requires enterprise data, fetch first.
            • NEVER assume enterprise data is available just because a prior run used it.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            CONVERSATION HISTORY (use to resolve "it", "that", "the roadmap", etc.)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            {self.conv if self.conv != "No prior conversation." else "This is the start of a new conversation."}

            NOTE: Conversation history shows conclusions and outputs from prior runs only.
            It does NOT mean the underlying enterprise data is still in memory.
            Use it to understand WHAT the user is referring to — not to skip fetching.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            USER QUERY:
            {query}

            ROUGH PLAN (mode + intent already classified):
            {MyJSON.dumps(self.rough_plan)}

            ENTERPRISE CONTEXT:
            {self.context_string}

            UPLOADED FILES IN THIS SESSION:
            {MyJSON.dumps(self.data_actions.fetch_files_uploaded_in_session({}))}

            WORKSPACE FILES (already written this session):
            {self._get_files_created_in_run()}

            AVAILABLE FETCH ACTIONS (for reference — use entity names from these):
            {list(self.allowed_fn_maps.keys())}

            ─────────────────────────────────────────────────────────────
            Produce the execution phase plan.
            Return ONLY valid JSON. No commentary.

            Schema to follow exactly:
            {MyJSON.dumps(ANALYSIS_EXECUTION_PLAN_SCHEMA, indent=2)}
        """

        chat = ChatCompletion(
            system=ANALYSIS_EXECUTION_PLAN_PROMPT,
            prev=[],
            user=user_prompt,
        )

        raw = ""
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::create_execution_plan",
            logInDb=self.log_info,
        ):
            raw += chunk


        print("create execution plan -- ", raw)

        plan = extract_json_after_llm(raw)

        # Ensure all phases start as pending
        for phase in plan.get("phases", []):
            phase["status"] = "pending"

        plan["current_phase_index"] = 0

        self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            parent_event_id=self.current_execution_id,
            payload={"content": f"Execution Plan: {len(plan.get('phases', []))} phases"}
        )

        AgentRunDAO.create_run_step(
            session_id=self.session_id,
            tenant_id=str(self.tenant_id),
            user_id=str(self.user_id),
            agent_name=self.name,
            run_id=self.run_id,
            step_type=AgentRunDAO.EXECUTION_PLAN,
            step_index=self.step_index,
            step_payload=plan,
            status=AgentRunDAO.COMPLETED
        )

        return plan
    
    # ============================================================
    # THINK-ALOUD (COGNITIVE GATE)
    # ============================================================
    @log_function_io_and_time
    def think_aloud(self, context: str, goal: str):
        system_prompt = f"""
            You are Astra's internal reasoning module.

            Your sole purpose is to resolve **interpretive uncertainty**
            about HOW to proceed — not to perform work.

            This is a DIRECTIONAL CLARIFICATION GATE.

            ────────────────────────────────────────────
            ENTERPRISE CONTEXT
            ────────────────────────────────────────────
            {self.context_string}

            ────────────────────────────────────────────
            UNCERTAINTY CONTEXT
            ────────────────────────────────────────────
            {context}

            ────────────────────────────────────────────
            UNCERTAINTY TO RESOLVE (MANDATORY)
            ────────────────────────────────────────────
            {goal}

            ────────────────────────────────────────────
            ORIGINAL INTENT (ROUGH PLAN)
            ────────────────────────────────────────────
            {MyJSON.dumps(self.rough_plan)}

            ────────────────────────────────────────────
            EXECUTION TRAJECTORY (SO FAR)
            ────────────────────────────────────────────
            {MyJSON.dumps(self.results)}
            
            
            ────────────────────────────────────────────
            AVAIALBE ACTIONS
            ────────────────────────────────────────────
            {self.capability_context}

            ────────────────────────────────────────────
            CORE RULES (NON-NEGOTIABLE)
            ────────────────────────────────────────────
                • Think step by step
                • Do NOT invent facts
                • Do NOT assume missing data exists
                • Focus ONLY on interpretation, framing, and direction
                • Do NOT propose multiple future paths
                • Do NOT restate known structures or dimensions
                
            ADDITIONAL ALLOWED SCOPE (NEW):

                You MAY:
                    • Assess how deep the next phase of work must go
                    • State whether deterministic expansion is sufficient
                    • State whether additional evidence classes are required
                    • State whether execution should proceed cautiously or directly

                You MUST NOT:
                    • Name specific actions
                    • Decide sequencing
                    • Decide confidence_in_sufficiency
                    • Decide when to stop

            ────────────────────────────────────────────
            HARD LIMITS (CRITICAL)
            ────────────────────────────────────────────
            This function MUST NOT:
                • Expand requirements or sections
                • Draft or elaborate deliverables
                • Enumerate functional / technical / integration details
                • Repeat previously identified gaps or dimensions
                • Simulate progress by restating the problem

            This function is VALID ONLY IF:
                • There is genuine uncertainty about WHAT to do next
                • OR multiple reasonable directions exist

            If the next step is already clear,
            you MUST explicitly say so.

            ────────────────────────────────────────────
            OUTPUT CONTRACT (MANDATORY)
            ────────────────────────────────────────────
            End your response with a section starting EXACTLY with:

            FINAL THOUGHT:

            In FINAL THOUGHT, you MUST:
                • State what is now clearer
                • State what uncertainty remains (if any)
                • State ONE directional need only (not an action)

            Examples of valid directional needs:
                - "We need evidence about X"
                - "We need to validate assumption Y"
                - "We need to expand Z using the existing reference"

            If no new uncertainty was resolved, you MUST say:
            "No further meaningful investigation is possible with available data"
        """

        user_prompt = (
            f"Today's date is {datetime.utcnow().strftime('%B %d, %Y')}\n"
            "Resolve the uncertainty and provide direction only."
        )

        chat = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)

        final_text = ""
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::think",
            logInDb=self.log_info
        ):
            final_text += chunk
            yield chunk

        yield "\n\n"
        print("think aloud ... response... ", final_text)

    # ============================================================
    # EXECUTION
    # ============================================================
    @log_function_io_and_time
    def execute_step(self, step_id, plan: Dict[str, Any]) -> Dict[str, Any]:
        step = plan.get("current_best_action_to_take", {})
        action = step.get("action")
        params = step.get("action_params", {}) or {}
        params.update({ "parent_event_id" : self.current_execution_id })

        # 1️⃣ No-op
        if not action:
            return {
                "step_id": step_id,
                "status": "skipped",
                "reason": "no_action_specified",
            }

        # 3️⃣ Capability guard
        if action not in self.allowed_fn_maps:
            return {
                "step_id": step_id,
                "status": "blocked",
                "reason": "action_not_allowed",
                "action": action,
            }

        # 4️⃣ Execute real action
        try:
            fn = self.allowed_fn_maps[action]
            print("actino --- ", action, fn)
            output = fn(params)
            # print("output -- ", output)

            return {
                "step_id": step_id,
                "status": "ok",
                "action": action,
                "meta": {"params_used": params},
                "output": output,
            }

        except Exception as e:
            appLogger.error({
                "function": "SuperAgent.execute_step",
                "step_id": step_id,
                "action": action,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

            return {
                "step_id": step_id,
                "status": "error",
                "action": action,
                "error": str(e),
            }


    # ============================================================
    # MAIN LOOP
    # ============================================================

    def run(self, query: str, meta=None) -> Generator[str, None, None]:
        self.rough_plan = {}
        self.execution_plans = []
        self.results = []
        RedClient.delete_key(key_set=f"interrupt_requested::userID::{self.user_id}")
        
        # ── 1. Create root step: user query ─────────────────────────────
        user_step_id = AgentRunDAO.create_run_step(
            session_id=self.session_id,
            tenant_id=str(self.tenant_id),
            user_id=str(self.user_id),
            agent_name=self.name,
            run_id=self.run_id,
            step_type=AgentRunDAO.USER_QUERY,
            step_index=self.step_index,
            step_payload={"query": query.strip(), "meta": meta},
            status=AgentRunDAO.COMPLETED
        )
        if meta and meta.get("attachments"):
            query = query + "\n\n Fetch file and read this file carefully thne only do anything I am attaching: " + json.dumps(meta)
            
        # self.deep_research_mode = meta.get("mode") or "research"
        print("query -- ", query)
        self.conv = AgentRunDAO.get_agent_context_from_steps(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            agent_name=self.name
        )
        
        self.data_actions = DataActions(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
            socketio=self.socketio,
            conversation=self.conv,
            mode="research"
        )
        self.set_context()
        
        self.research_done_in_session = self._get_ordered_files()
        self.current_step_id = user_step_id
        self.step_index += 1
        
        debugLogger.info({
            "event": "NewRunStarted",
            "run_id": self.run_id,
            "query": query,
            "user_step_id": user_step_id
        })
        self.current_rough_step_id = self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            payload={
                "content": "Understand"
            },
        )
        self.rough_plan = self.create_rough_plan(query)
        self.mode = self.rough_plan.get("run_mode")
        self.data_actions = DataActions(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
            socketio=self.socketio,
            conversation=self.conv,
            mode="report" if self.mode == "deep_research" else "research"
        )
        self.set_context()
        self.section_plan = None
        self.current_section_index = 0
        self.current_section_state = None
            
        rough_step_id = AgentRunDAO.create_run_step(
            session_id=self.session_id,
            tenant_id=str(self.tenant_id),
            user_id=str(self.user_id),
            agent_name=self.name,
            run_id=self.run_id,
            step_type=AgentRunDAO.ROUGH_PLAN,
            step_index=self.step_index,
            step_payload=self.rough_plan,
            status=AgentRunDAO.COMPLETED
        )
        self.current_step_id = rough_step_id
        
        self.current_execution_id = self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            payload={
                "content": "Execution Start"
            }
        )

        # ── Create execution phase plan (analysis mode only) ─────────────────
        self.execution_phase_plan = {}
        if self.mode == "analysis":
            self.execution_phase_plan = self.create_execution_plan(query)
            appLogger.info({
                "event": "execution_phase_plan_created",
                "phases": [p["phase_id"] for p in self.execution_phase_plan.get("phases", [])]
            })

        interrupted = False
        def on_interrupt(_):
            nonlocal interrupted
            interrupted = True

        channel = f"interrupt::{self.user_id}"
        RedClient.subscribe(channel, on_interrupt)
        while True:
            self.step_index += 1
            print("------------------run ---------------", self.step_index, len(self.results), self.section_plan is not None)
            if self.mode == "transformation":
                # --------------------------------------------
                # TRANSFORMATION: skip loop entirely
                # ──────────────────────────────────────────────
                artifact_formats = (
                    self.rough_plan
                    .get("output_intent", {})
                    .get("artifact_formats", [])
                ) or []

                if artifact_formats:
                    fmt = artifact_formats[0]
                    try:
                        if fmt == "html":
                            result = self.generate_html({
                                "input_path": "",
                                "query": query,
                                "rough_plan": self.rough_plan,
                            })
                            self.final_report_exported = True
                        elif fmt == "report_doc":
                            result = self.generate_report_doc(query=query)
                            self.final_report_exported = True

                        if self.final_report_exported:
                            self.results.append({
                                "step_index": self.step_index,
                                "type": "transformation",
                                "result": result
                            })
                    except Exception as e:
                        appLogger.error({
                            "event": "transformation_failed",
                            "fmt": fmt,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })
                        
                # # SINGLE STEP FLOW
                # self._execute_transformation(query)
                break
            
            if (self.mode == "deep_research"):
                next_plan = self.generate_next_execution_plan_deep_research(
                    self.step_index, 
                    query=query,
                )
                print("json next plan --deep ", MyJSON.dumps(next_plan))
            else:
                next_plan = self.generate_next_execution_plan(self.step_index, query=query,)
                print("json next plan --normal ", MyJSON.dumps(next_plan))
            if not next_plan:
                continue
            
            if interrupted:
                break
            
            AgentRunDAO.create_run_step(
                session_id=self.session_id,
                tenant_id=str(self.tenant_id),
                user_id=str(self.user_id),
                agent_name=self.name,
                run_id=self.run_id,
                step_type=AgentRunDAO.EXECUTION_PLAN,
                step_index=self.step_index,
                step_payload=next_plan,
                status=AgentRunDAO.COMPLETED
            )
            
            step = next_plan.get("current_best_action_to_take", {})
            action = step.get("action")
            params = step.get("action_params", {}) or {}

            if action == "think_aloud_reasoning":
                context = params.get("uncertainty_context", "") or ""
                goal = params.get("uncertainty_to_resolve", "") or "" + (
                    " Properly convey if this uncertainity is resolved or can be resolved "
                )
                full_string = ""
                for chunk in self.think_aloud(context=context, goal=goal):
                    full_string += chunk
                    
                result =  {
                    "step_id": self.step_index,
                    "status": "thought_complete",
                    "action": action,
                    "thought_and_reasoning": full_string,
                }
             
            elif action == "write_markdown_file":
                path = params.get("path")
                instruction = params.get("instruction")
                section_id = params.get("section_id")
                self.research_file_path = path
                answer = self.write_markdown_document(section_id, path, instruction)

                result = {
                    "step_id": self.step_index,
                    "status": "writing_complete",
                    "action": action,
                    "output": answer,
                }

                # Deep research: advance section immediately after writing
                if self.mode == "deep_research" and self.section_plan:
                    self.current_section_index += 1

                    if self.current_section_index >= len(self.section_plan["sections"]):
                        print("All sections written — deterministic stop")
                        self.results.append({
                            "step_index": self.step_index,
                            "type": "action",
                            "executed_plan": next_plan,
                            "result": result,
                        })
                        break

                    # Clear fetch memory for next section
                    self.results = [
                        r for r in self.results
                        if r.get("type") != "action"
                        or not r.get("result", {}).get("action", "").startswith("fetch_")
                    ]

                    next_section = self.section_plan["sections"][self.current_section_index]
                    self.current_section_state = {
                        "section_id": next_section["section_id"],
                        "written": False,
                        "completed_actions": []
                    }
               
            elif action == "ask_clarification":
                self.ask_clarification = True
                break

            elif action == "freeze_section":
                result = {
                    "step_id": self.step_index,
                    "status": "section_frozen",
                    "action": action,
                    "output": self.update_current_exec_section(params, "freeze_section")
                }
                
                if self.mode == "deep_research":
                    self.current_section_index += 1
                    # ---- Deterministic completion guard ----
                    if self.section_plan and self.current_section_index >= len(self.section_plan["sections"]):
                        print("All sections completed — deterministic stop")
                        break
                    # ------------------------------------
                    # CLEAR previous section fetch memory
                    # ------------------------------------
                    self.results = [
                        r for r in self.results
                        if r.get("type") != "action"
                        or not r.get("result", {}).get("action", "").startswith("fetch_")
                    ]
                    print("clean discard memory --- ")
                    if self.current_section_index < len(self.section_plan["sections"]):
                        next_section = self.section_plan["sections"][self.current_section_index]
                        self.current_section_state = {
                            "section_id": next_section["section_id"],
                            "written": False,
                            "validated": False,
                            "frozen": False,
                            "data_sufficiency": "insufficient",
                            "completed_phases": {
                                "fetch": [],
                                "compute": [],
                                "interpret": []
                            }
                        }
                    
            elif action == "validate_section":
                result = {
                    "step_id": self.step_index,
                    "status": "section_validated",
                    "action": action,
                    "output": self.update_current_exec_section(params, "validate_section")
                }
                
            elif action == "identify_required_sections":
                plan = self.identify_required_sections(query)
                self.section_plan = plan
                self.current_section_index = 0
                result = {
                    "step_id": self.step_index,
                    "status": "research_sections_identified",
                    "sections": plan["sections"]
                }
                first = plan["sections"][0]
                # 
                self.current_section_state = {
                    "section_id": first["section_id"],
                    "written": False,
                    # "validated": False,
                    # "frozen": False
                }
                self.current_section_state.setdefault("completed_actions", [])
                if "identify_required_sections" not in self.current_section_state["completed_actions"]:
                    self.current_section_state["completed_actions"].append("identify_required_sections")


            elif action == "generate_report_doc_after_analysis":
                doc_spec = params.get("doc_spec") or {}
                result = self._run_generate_report_doc(query=query, doc_spec=doc_spec)
                entry = {
                    "step_index": self.step_index,
                    "action": "generate_report_doc_after_analysis",
                    "status": "written",
                    "result": result,
                }
                # break
            
            elif action == "generate_html_after_analysis":
                html_spec = params.get("html_spec") or {}
                result = self._run_generate_html_after_analysis(query=query, html_spec=html_spec)
                entry = {
                    "step_index": self.step_index,
                    "status": "written",
                    "result": result,
                }
                # break

            elif action == "generate_ppt_after_analysis":
                ppt_spec = params.get("ppt_spec") or {}
                result = self._run_generate_ppt_after_analysis(query=query, ppt_spec=ppt_spec)
                entry = {
                    "step_index": self.step_index,
                    "status": "written",
                    "result": result,
                }
                # break
            elif action == "generate_llm_chart":
                params["_injected_results"] = self.results
                result = self.execute_step(self.step_index, next_plan)
                params.pop("_injected_results", None)  # clean before next_plan hits execution_plans

            else:
                # ---- Execute ----
                result = self.execute_step(self.step_index, next_plan)
                
                
            entry = {
                "step_index": self.step_index,
                "type": "action",
                "executed_plan": next_plan,
                "result": result,
            }
            
            if self.mode == "deep_research":
                rule = next_plan.get("last_result_handling") 
                # for rule in handling:
                if rule and not rule.get("keep",):
                    # continue

                    discard_fetches = rule.get("discard")
                    print("discard_action ", discard_fetches)
                    for discard_fetch in discard_fetches:
                        if discard_fetch:
                            for i in range(len(self.results) - 1, -1, -1):
                                action = (
                                    self.results[i]
                                        .get("result", {})
                                        .get("action")
                                )
                                if (action == discard_fetch and action.startswith("fetch_")) or (action == 'read_files'):
                                    print("discarding -- discard_action ", i, discard_fetch)
                                    self.results.pop(i)
                                    break

            else:
                handling = next_plan.get("last_result_handling")
                if handling and handling.get("keep") is False:
                    if len(self.results) > 0:
                        self.results.pop()
                  
            # Append tentatively
            self.results.append(entry)
            print("*************loop run done ", len(self.results), self.section_plan is not None)
            
            if action == "merge_and_export_research":
                self.deep_exported = True
            
            if not next_plan.get("should_continue", False):
                break
            
            if self.step_index >= DEEP_RESEARCH_ITERATION_LIMIT:
                break
        
        if not self.ask_clarification:
            # --------------------------------------------------
            # FALLBACK EXPORT (deep_research only)
            # --------------------------------------------------
            if self.mode == "deep_research" and not self.deep_exported:
                self._force_export_all_written_content()

            # --------------------------------------------------
            # ARTIFACT GENERATION (not analysis + deep_research)
            # --------------------------------------------------
            artifact_formats = (
                self.rough_plan
                .get("output_intent", {})
                .get("artifact_formats", [])
            ) or []
            # artifact_formats = [] if self.mode == "analysis" else artifact_formats

            if artifact_formats and not self.final_report_exported:
                fmt = artifact_formats[0]
                try:
                    if fmt == "html":
                        result = self.generate_html({
                            "input_path": "",
                            "query": query,
                            "rough_plan": self.rough_plan,
                        })
                        self.final_report_exported = True

                    elif fmt == "report_doc":
                        result = self.generate_report_doc(query=query)
                        self.final_report_exported = True

                    if self.final_report_exported:
                        self.results.append({
                            "step_index": self.step_index,
                            "type": "transformation",
                            "result": result
                        })

                except Exception as e:
                    appLogger.error({
                        "event": "artifact_generation_failed",
                        "fmt": fmt,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
            

        self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            payload={
                "content": "Execution End"
            }
        )
        
        # ========================================================
        # FINAL RESPONSE
        # ========================================================

        BASE_FINAL_OUTPUT_PROMPT = f"""
            You are Tango operating in mode: {self.mode}.
            
            {GLOBAL_RULE_TRMERIC_HOW_TO_UNDERSTAND}
            {TRMERIC_FINAL_RESPONSE_NUDGES}
            

            User Query:
            {query}
            
            Rough Plan:
            {MyJSON.dumps(self.rough_plan)}

            Execution Plans:
            {MyJSON.dumps(self.execution_plans)}

            Execution Results:
            {MyJSON.dumps(self.results)}
            
            
            WHAT TRMERIC CAN DO FOR CUSTOMERS (FOR NEXT STEPS FRAMING)
            ────────────────────────────────────────────────────────────
            
            {TRMERIC_DOMAIN_HINTS}
            {TRMERIC_AGENT_CAPABILITY_SUMMARY}

            ============================================================
            FINAL RESPONSE FORMAT CONTRACT (STRICT)
            ============================================================

            You MUST produce a clean, structured, professional Markdown response.

            Your goal is clarity, hierarchy, and decision-readiness.
            
            FINAL RESPONSE RULE:

            The chat response is NOT the primary deliverable
            when the user has requested a document.

            The primary deliverable is the authored file.
            The chat response should:
            • Briefly summarize what was written
            • Reference the generated document (only if generated and exported)
            • Avoid re-writing the full content inline

            
            ------------------------------------------------------------
            STRUCTURE RULES (MANDATORY)
            ------------------------------------------------------------

            1. Start with a clear headline answer
            • One or two sentences
            • Directly addresses the user’s question
            • Explicitly state uncertainty if it materially affects the answer

            2. Organize the body into clear sections using Markdown headings (##, ###)

            3. Use lists intentionally:
            • Use BULLETS for grouping related facts or points
            • Use NUMBERED LISTS only when order, priority, or sequence matters
            • Do NOT mix bullets and paragraphs at the same level

            4. Bullet hierarchy rules:
            • Top-level bullets represent major ideas
            • Sub-bullets provide explanation, evidence, or nuance
            • Never exceed 2 levels of nesting
            • Every top-level bullet MUST have at least one sub-bullet

            5. Tables:
            • Use tables ONLY if they improve clarity or comparison
            • Tables must have clear headers and aligned columns
            • Do NOT use tables for simple lists

            ------------------------------------------------------------
            STYLE RULES (NON-NEGOTIABLE)
            ------------------------------------------------------------

            • Professional, neutral, confident tone
            • No filler or consulting-style fluff
            • No emojis
            • No casual language
            • No internal system references

            ------------------------------------------------------------
            STRICTLY FORBIDDEN
            ------------------------------------------------------------

            • JSON
            • Code blocks (unless explicitly asked)
            • Mentioning internal steps, tools, agents, or planning
            • Referring to “execution steps”, “rough plan”, or “thinking process”
            • Flat, unstructured bullet dumps

            ------------------------------------------------------------
            QUALITY BAR
            ------------------------------------------------------------

            This response should read like it was written by a senior human expert
            presenting a clear, well-structured answer.

            Markdown only. No commentary outside the response.
        """


        user_prompt = f"""
        
            ════════════════════════════════════════════════════════════

            Conversation History:
            {self.conv if self.conv != "No prior conversation." else "New conversation."}

            User Query: {query}
            ════════════════════════════════════════════════════════════
            
            
            Produce the final user-facing response in clean, professional Markdown.

            Focus on delivering a clear, structured, executive-ready answer based on the analysis completed.
            Speak directly and confidently to the user.
            You are not designed for directly rendering graph, but you can send artifact as you can see 
            in the execution and if chart was generated and sent to user you can inform simply.
        """
        
        system_prompt = BASE_FINAL_OUTPUT_PROMPT
        if self.mode == "deep_research":
            system_prompt += RESEARCH_OUTPUT_EXTENSION
        if self.mode == "context_building":
            system_prompt += TRUCIBLE_FINAL_RESPONSE_EXTENSION
        if self.mode == "ideation":
            system_prompt += IDEATION_FINAL_RESPONSE_EXTENSION
        if self.mode == "analysis":
            system_prompt += ANALYSIS_FINAL_RESPONSE_EXTENSION

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt,
        )

        final_string = ""
        if interrupted:
            yield "Stopping"
            return
        
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::final",
        ):
            if interrupted:
                yield chunk
                final_string += "[Stopping]"
            else:
                final_string += chunk
                yield chunk

        # yield "\n<end>"
        self.step_index += 1
        print("final output result --- ", final_string)
    
        
    @log_function_io_and_time
    def write_markdown_document(
        self,
        section_id: str,
        path: str,
        instruction: str
    ) -> Dict[str, Any]:
        
        import os
        from pathlib import Path

        if not path:
            raise ValueError("path is required")
        if not instruction:
            raise ValueError("instruction is required")
        
        if path.endswith(".html"):
            path = path.replace(".html", ".md")
        
        full_path = os.path.join(self.data_actions.get_workspace(), path)
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)
        
        already_content = ""
        if not os.path.exists(full_path):
            already_content = ""
        else:
            with open(full_path, "r", encoding="utf-8") as f:
                already_content = f.read()

        system_prompt = RESEARCH_MARKDOWN_WRITING_PROMPT
        
        user_prompt = f"""
            AUTHORING INSTRUCTION:
            {instruction}

            ENTERPRISE CONTEXT (USE THIS ACTIVELY — NOT PASSIVELY):
            {self.context_string}
            
            
            WRITING RULE — COMPANY GROUNDING (NON-NEGOTIABLE):
                Every section you write MUST:
                - Reference specific company details from the enterprise context above
                - Connect findings to THIS company's actual strategies, portfolios, and initiatives
                - Use company-specific language, not generic PM/tech language
                - Answer "why does this matter for THIS company right now?"
                
                Generic writing is FORBIDDEN. If a paragraph could apply to any company, rewrite it.
                
            
            
            {TRMERIC_FUNCTIONAL_CAPABILITIES}
            
            
            ALREADY WRITTEN CONTENT
            {already_content}

            AVAILABLE RESEARCH MATERIAL (AUTHORITATIVE):
            {MyJSON.dumps(self.results, indent=2)}

            OUTPUT:
            • Valid markdown only
            • Structured, professional, decision-grade
            - Do not hallucinate
            - No HTML, only detailed writing or research done
            - Write no chart in PDF
            - Dont try to draw any diagram or chart or bar lines in markdown. even if any one wants it. No diagram in markdowns.
            - Ayy visualization user needs will be taken care later. Your job is to write detailed research markdown with data and interpretation in the style that the user wants.
        """

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt,
        )

        content = ""
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::write_markdown_document",
            logInDb=self.log_info
        ):
            content += chunk

        full_path = os.path.join(self.data_actions.get_workspace(), path)
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
            
        # self.mark_written({"section_id": section_id})
        self.update_current_exec_section({"section_id": section_id}, "write_section")
        formatted_title = format_section_title(section_id)
        self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            parent_event_id=self.current_execution_id,
            payload={"content": f"Section Written: {formatted_title}"}
        )

        return {
            "path": path,
            "written": True,
            "content": content.strip()
        }


    def update_current_exec_section(self, params, key):
        section_id = params.get("section_id")

        if not self.current_section_state:
            return "No current_section_state found"

        if self.current_section_state.get("section_id") != section_id:
            return "Section mismatch"
        
        self.current_section_state.setdefault("completed_actions", [])
        if key == "write_section":
            self.current_section_state["written"] = True
            if "write_markdown_file" not in self.current_section_state["completed_actions"]:
                self.current_section_state["completed_actions"].append("write_markdown_file")


        elif key == "validate_section":
            self.current_section_state["validated"] = True
            if "validate_section" not in self.current_section_state["completed_actions"]:
                self.current_section_state["completed_actions"].append("validate_section")

        elif key == "freeze_section":
            self.current_section_state["validated"] = True
            self.current_section_state["frozen"] = True
            if "freeze_section" not in self.current_section_state["completed_actions"]:
                self.current_section_state["completed_actions"].append("freeze_section")

        return {
            "section_id": section_id,
            "updated_state": self.current_section_state
        }


    def _create_event(
        self,
        *,
        step_id: int,
        event_type: str,
        event_name: str,
        payload: dict,
        parent_event_id: int = None,
        local_index: int = None
    ) -> int:
        """
        Centralized event creation with sequencing.
        """
        self.sequence_counter += 1
        
        self.socketio.emit(
            "event_updated",
            {},
            room=self.client_id
        )

        return AgentRunDAO.create_run_event(
            run_id=self.run_id,
            step_id=step_id,
            parent_event_id=parent_event_id,
            event_type=event_type,
            event_name=event_name,
            sequence_index=self.sequence_counter,
            local_index=local_index,
            event_payload=payload
        )

    def _get_ordered_files(self, fetch_md = True, fetch_html=False):
        workspace = self.data_actions.get_workspace()
        md_files = []
        print("workspace _get_ordered_files ", workspace)
        # -------------------------------
        # Discover markdown files safely
        # -------------------------------
        for root, _, files in os.walk(workspace):
            for f in files:
                if not f.endswith(".md"):
                    continue
                if "merge" in f:
                    continue
                if "artifact" in f:
                    continue

                full = os.path.join(root, f)
                print("full _get_ordered_files path ", full)

                try:
                    rel = os.path.relpath(full, workspace)
                    created = get_file_created_time(full)

                    md_files.append({
                        "path": rel,
                        "created": created
                    })

                except Exception as e:
                    appLogger.warning({
                        "event": "md_file_skipped",
                        "file": full,
                        "error": str(e)
                    })
                    continue

        if not md_files:
            appLogger.error("Force export skipped: no markdown files found")
            return []

        # -------------------------------
        # Deterministic ordering
        # -------------------------------
        md_files.sort(key=lambda x: x["created"])
        ordered_files = [f["path"] for f in md_files]
        return ordered_files

    def _force_export_all_written_content(self):
        import os

        try:
            
            ordered_files = self._get_ordered_files()
            if not ordered_files:
                return
            
            appLogger.info({
                "event": "force_export_files_ordered",
                "count": len(ordered_files),
                "files": ordered_files
            })

            # -------------------------------
            # Force export
            # -------------------------------
            result = self.data_actions.merge_and_export_research({
                "ordered_files": ordered_files,
                "output_path": "merged_partial_research.md"
            })

            if result.get("exported"):
                self.deep_exported = True
                appLogger.info("Force export completed successfully")
            else:
                appLogger.error({
                    "event": "force_export_failed",
                    "result": result
                })

        except Exception as e:
            # 🚨 This should be extremely rare
            appLogger.error({
                "event": "force_export_crashed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    # ============================================================
    # DEEP RESEARCH EXECUTION CONTROLLER (STATEFUL, DETERMINISTIC)
    # ============================================================
    @log_function_io_and_time
    def generate_next_execution_plan_deep_research(
        self,
        step_index: int,
        query = ""
    ) -> Dict[str, Any]:

        system_prompt = f"""
            You are a DEEP RESEARCH EXECUTION CONTROLLER.

            You do NOT plan creatively.
            You do NOT reason epistemically.
            You do NOT optimize for insight.

            Your ONLY responsibility is to determine the
            NEXT LEGALLY PERMITTED ACTION
            based on the CURRENT SECTION STATE.
            
            -------------------------------------------------------
            CONTEXT
                All data fetching should be redone for fresh run
                Run Context:
                    - run_id: {self.run_id}
            -------------------------------------------------------

            --------------------------------------------------------
            AUTHORITATIVE CONTEXT
            --------------------------------------------------------

            Enterprise Context:
            {self.context_string}
            
            {SYSTEM_SCOPE_HINTS}
            
            
            {TRMERIC_FUNCTIONAL_CAPABILITIES}
            
            Available Actions (hard constraint):
            {self.capability_context}

            Research Objective (from rough plan):
            {MyJSON.dumps(self.rough_plan)}

            Execution History (authoritative):
            {MyJSON.dumps(self.results)}

            Current Section State:
            {self.current_section_state}

            Current Section Index:
            {self.current_section_index}

            --------------------------------------------------------
            SECTION PLAN STATE (AUTHORITATIVE)
            --------------------------------------------------------

            Section Plan:
            {MyJSON.dumps(self.section_plan)}
            
            --------------------------------------------------------
            STRUCTURE PREREQUISITE (ABSOLUTE)
            --------------------------------------------------------
                • Deep research execution MUST NOT begin unless sections are identified
                • If no section plan exists in agent state:
                    – You MUST select the action: identify_required_sections
                    – No other action is legally permitted
                • Execution actions (fetch, analyse, write) are FORBIDDEN until sections are identified
                • You MUST NOT invent, infer, or assume section identifiers
                • Sections are authoritative ONLY when provided by identify_required_sections
                
                
            SECTION PLAN AUTHORITY (CRITICAL)

            • section_plan is the ONLY valid list of sections
            • current_section_index identifies the active section
            • You MUST operate ONLY on this section
            • You MUST NOT invent section_ids

            If section_plan exists:
            • identify_required_sections is FORBIDDEN

            --------------------------------------------------------
            SECTION LIFECYCLE (NON-NEGOTIABLE)
            --------------------------------------------------------

            Each section MUST progress STRICTLY through:
            1. written == false
            2. Fetch data if required
            3. written == true


            You MUST NOT:
            • Skip lifecycle steps
            • Fetch data for future sections
            • Re-write a written section
            • Judge confidence or sufficiency
            • Perform exploratory reasoning
            • Plan more than ONE step ahead
            
            
            --------------------------------------------------------
            WORKFLOW PHASE CLARIFICATION (MANDATORY)
            --------------------------------------------------------

            • workflow_phase is DESCRIPTIVE ONLY
            • It MUST be derived from current_section_state
            • It MUST NOT influence action selection
            • Lifecycle flags like (written) are the ONLY control gates
            
            --------------------------------------------------------
            WORK INTENT AUTHORITY RULE (MANDATORY)
            --------------------------------------------------------

            • current_section_work_intent is INFORMATIONAL ONLY
            • It MUST NOT introduce new actions, phases, or scope
            • It MUST NOT expand required work
            • You MAY only respect explicitly listed blocking_conditions
            • Lifecycle flags like (written) remain the ONLY progression gates
            
            
            --------------------------------------------------------
            DATA SUFFICIENCY RULE (MANDATORY)
            --------------------------------------------------------

            • data_sufficiency is a DESCRIPTIVE LABEL ONLY
            • It MUST NOT affect lifecycle transitions
            • written are the ONLY control flags


            --------------------------------------------------------
            SECTION-SCOPED DATA FETCHING (ABSOLUTE REQUIREMENT)
            --------------------------------------------------------

            ALL data fetching MUST be strictly scoped to the CURRENT SECTION ONLY.


            --------------------------------------------------------
            LEGAL TRANSITIONS
            --------------------------------------------------------

            You may ONLY select ONE action per step.

            1. If section_plan does not exist:
                → identify_required_sections
                → should_continue = true

            2. If section.written == false:
            → You MAY:
                    • fetch_* (ONLY if required data is missing)
                    • analyse (if data already exists)
            → You MUST NOT reference future sections


            3. If section.written == true:
            → Advance to the NEXT section
            → Reset data collection mindset for NEW section
            → Previous section's data is no longer relevant to fetching decisions
            → OR terminate if no sections remain

            4. If ALL sections are written:
            → should_continue = false
            
            5. If transitioned to new section:
            → You MUST treat this as a fresh start for data fetching
            → You MUST fetch data ONLY for the NEW current section
            → You MUST NOT reuse queries or assumptions from previous sections
            → You MUST check the NEW section's work_intent for its specific requirements


            --------------------------------------------------------
            TRANSITION CONSUMPTION RULE (CRITICAL)
            --------------------------------------------------------

            • Lifecycle transitions are CONSUMPTIVE
            • If an action has already been successfully executed
            for the current section, you MUST NOT select it again
            • Repeating a completed transition is an execution error
            • You MUST always advance state forward, never sideways

            --------------------------------------------------------
            FORBIDDEN BEHAVIOR (HARD FAIL)
            --------------------------------------------------------

            • Skipping writing
            • No need to do Fetching after writing
            • Advancing without writing
            • Confidence assessment
            • Delta reasoning
            • Repeating identical fetches
            • Using generic/broad queries
            • Fetching data for sections other than current section
            • Proceeding to write_section when required data is missing
            
            --------------------------------------------------------
            RATIONALE NON-AUTHORITY RULE (MANDATORY)
            --------------------------------------------------------

            • rationale and rationale_for_user_visiblity are NON-BINDING
            • They MUST NOT justify or permit actions
            • Control flow MUST derive only from structured fields
            • Text explanations NEVER grant permission
            
            --------------------------------------------------------
            FILE PATH RULE (ABSOLUTE)
            --------------------------------------------------------

            • Each section MUST write to a UNIQUE file path
            • Path MUST be derived from section info: "<good name for section>.md"
            • NEVER reuse a path across sections
            • NEVER use a generic path like "research.md" or "report.md"
            • All section files will be automatically merged and exported
                at the end of the run — you do NOT need to merge them
            • Your ONLY job is to write each section to its own file
            
            
            
            --------------------------------------------------------
            WRITING INSTRUCTION GENERATION RULE (MANDATORY)
            --------------------------------------------------------

            When selecting write_markdown_file, the instruction field MUST:

            1. Reference specific Comapny context:
                - Company type
                - Active strategies
                - Industry position
                - Current focus: pulled from context_string

            2. Forbid generic writing:
            - Instruction MUST NOT say "write comprehensive content about X"
            - Instruction MUST say "write about X specifically for for company ic ontext, 
                referencing their AI-native PM platform, their Jira/ADO integrations,
                their SuperAgent architecture, and their enterprise customer base"

            3. Connect section to company reality:
            - Every section instruction must answer: 
                "Why does THIS matter for THIS company right now?"
            - The instruction must include: what company already has, 
                what they're building, and what gap this section addresses


            --------------------------------------------------------
            OUTPUT FORMAT (STRICT)
            --------------------------------------------------------

            Return EXACTLY ONE JSON object matching:
            {MyJSON.dumps(self.policy.deep_research_execution_step_schema, indent=2)}

            Rules:
            • No extra fields
            • No explanations
            • No commentary
            
            • completed_actions is authoritative
            • You MUST NOT select an action already listed in completed_actions

            Today's date is {datetime.utcnow().strftime("%B %d, %Y")}
        """

        user_prompt = f"""
            ════════════════════════════════════════════════════════════
            AUTHORITATIVE AGENT STATE  ◄─ GROUND TRUTH — READ FIRST
            ════════════════════════════════════════════════════════════

            Current Section State:
            {self.current_section_state}

            Current Section Index: {self.current_section_index}

            ════════════════════════════════════════════════════════════

            Conversation History:
            {self.conv if self.conv != "No prior conversation." else "New conversation."}

            User Query: {query}

            --------------------------------------------------------
            RESPONSE RULES
            --------------------------------------------------------

            • Return exactly ONE JSON object.
            • If all sections are written: should_continue = false
            • Do NOT call identify_required_sections if section_plan already exists.
            - After identify_required_sections: should_continue = true ALWAYS
            - While any section remains unwritten: should_continue = true
            - should_continue = false ONLY when ALL sections are written

            Today's date: {datetime.utcnow().strftime("%B %d, %Y")}
        """

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )

        streamed = ""
        printed = set()

        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::deep_research_next_step",
            logInDb=self.log_info,
        ):
            streamed += chunk

            # Stream user-visible rationale breadcrumbs as they arrive
            if '"rationale_for_user_visiblity"' in streamed:
                match = re.search(
                    r'"rationale_for_user_visiblity"\s*:\s*\[([^\]]*)',
                    streamed,
                    re.DOTALL
                )
                if match:
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    for t in items:
                        if t not in printed:
                            self._create_event(
                                step_id=self.current_step_id,
                                parent_event_id=self.current_execution_id,
                                event_type=AgentRunDAO.THOUGHT,
                                event_name=AgentRunDAO.EXECUTION_PLAN,
                                local_index=len(printed),
                                payload={"content": t}
                            )
                            printed.add(t)

        plan = extract_json_after_llm(streamed)
        self.execution_plans.append(plan)
        return plan


    @log_function_io_and_time
    def identify_required_sections(self, query) -> Dict[str, Any]:
        """
        Identifies required research sections based on data dimensions only.
        Presentation formats (tables/charts) are NOT separate sections.
        """
        
        # System prompt is now a constant
        system_prompt = IDENTIFY_SECTIONS_SYSTEM_PROMPT
        
        # All dynamic/variable content goes in user prompt
        user_prompt = f"""
            --------------------------------------------------
            CONVERSATION HISTORY
            --------------------------------------------------
            {self.conv}
            
            --------------------------------------------------
            COMPANY GROUNDING REQUIREMENT (MANDATORY)
            --------------------------------------------------
            This research is for a SPECIFIC organization. 
            Before identifying sections, internalize:

            Active Projects & Roadmaps Context:
            {self.context_string}

            RULE: Every section MUST reference this specific org's 
            context. Generic sections are FORBIDDEN.
            Even for TYPE A queries, sections must answer:
            "How does this apply to THIS company's specific 
            situation, projects, and strategy?"
            
            --------------------------------------------------
            AVAILABLE SYSTEM CAPABILITIES (INFORMATIONAL ONLY)
            --------------------------------------------------
            {self.capability_context}
            
            --------------------------------------------------
            EXECUTION ARTIFACTS (WHAT'S BEEN DONE SO FAR)
            --------------------------------------------------
            {MyJSON.dumps(self.results, indent=2)}
            
            --------------------------------------------------
            OUTPUT SCHEMA (STRICT)
            --------------------------------------------------
            Return JSON that EXACTLY matches this schema:
            {MyJSON.dumps(DEEP_RESEARCH_SECTION_PLAN_SCHEMA, indent=2)}
            
            --------------------------------------------------
            USER QUERY
            --------------------------------------------------
            {query}
            
            --------------------------------------------------
            INSTRUCTIONS
            --------------------------------------------------
            Identify all required **DATA ANALYSIS SECTIONS**.
            
            Remember:
            • Sections = DATA DIMENSIONS to analyze
            • NOT presentation formats (tables/charts)
            • If query asks for "X as table and chart", create ONE section for X
            
            Respond ONLY with valid JSON.
            No commentary.
        """
        
        print("running identify_required_sections")

        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )

        raw = ""
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::identify_sections",
            logInDb=self.log_info
        ):
            raw += chunk
            
        print("identify_required_sections response -- ", raw)
        plan = extract_json_after_llm(raw)
        
        AgentRunDAO.create_run_step(
            session_id=self.session_id,
            tenant_id=str(self.tenant_id),
            user_id=str(self.user_id),
            agent_name=self.name,
            run_id=self.run_id,
            step_type=AgentRunDAO.RESEARCH_SECTIONS_IDENTIFICATION,
            step_index=self.step_index,
            step_payload=plan,
            status=AgentRunDAO.COMPLETED
        )
        return plan


    @log_function_io_and_time
    def generate_html(self, params={}) -> Dict[str, Any]:
        try:
            query = params.get("query", "")
            workspace = self.data_actions.get_workspace()
            
            # ============================================================
            # PHASE 0: Preparation - Read All Markdown
            # ============================================================
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Starting HTML Generation"}
            )
            
            ordered_files = self._get_ordered_files(fetch_html=False)
            # Read and merge all markdown files
            merged_sections = []
            for idx, rel_path in enumerate(ordered_files, start=1):
                if "merge" in rel_path or "html" in rel_path:
                    continue
                
                full_path = os.path.join(workspace, rel_path)
                if not os.path.isfile(full_path):
                    continue
                
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                
                # Add section separator
                section_header = f"\n\n---\n\n"
                merged_sections.append(section_header + content)
            
            merged_markdown = "\n\n".join(merged_sections).strip() + "\n"
            
            appLogger.info({
                "event": "markdown_merged",
                "files_count": len(ordered_files),
                "markdown_length": len(merged_markdown)
            })
            
            # ============================================================
            # PHASE 1: Plan Presentation System
            # ============================================================
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Phase 1: Analyzing & Planning Design"}
            )
            
            design_plan = self.plan_presentation_system(
                markdown_content=merged_markdown,
                query=query
            )
            
            # design_plan = {}
            
            # Validate design plan
            if not design_plan or 'design_system' not in design_plan:
                raise ValueError("Design plan generation failed")
            
            # appLogger.info({
            #     "event": "design_plan_created",
            #     "document_type": design_plan.get('document_analysis', {}).get('document_type'),
            #     "sections_count": len(design_plan.get('content_structure', {}).get('sections', []))
            # })
            
            doc_type = design_plan["document_analysis"]["document_type"]

            if doc_type == "year_review":
                return  self.generate_year_review_full_html(
                    merged_markdown,
                    query
                ) 
            else:
                return self.generate_generic_html(design_plan, merged_markdown, query=query)
            
        except Exception as e:
            appLogger.error({
                "event": "html_generation_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": f"✗ HTML Generation Failed: {str(e)}"}
            )
            
            return {
                "exported": False,
                "format": "html",
                "error": str(e)
            }


    @log_function_io_and_time
    def plan_presentation_system(self, markdown_content: str, query: str) -> Dict[str, Any]:
        system_prompt = DESIGN_ANALYSIS_PROMPT
        
        workspace = self.data_actions.get_workspace()
        ordered_files = self._get_ordered_files(fetch_html=False)
        merged_sections = []
        for idx, rel_path in enumerate(ordered_files, start=1):
            if "merge" in rel_path or "html" in rel_path:
                continue
            
            full_path = os.path.join(workspace, rel_path)
            if not os.path.isfile(full_path):
                continue
            
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            # Add section separator
            section_header = f"\n\n---\n\n"
            merged_sections.append(section_header + content)
        
        markdown_content = "\n\n".join(merged_sections).strip() + "\n"

        user_prompt = f"""
            
            Business Context:
            {self.context_string}
            
            Original Intent (Rough Plan):
            {MyJSON.dumps(self.rough_plan, indent=2)}
            
            User Query:
            {query}
        
            Complete Research Content (Markdown) (If research was done):
            {markdown_content}
            
            If research document are provided it will be here:
            {self.results}
            
            ---
            
            ANALYZE DEEPLY:
            
            1. Document Type & Audience
            - What am I creating? (executive report, year-in-review, dashboard, analysis)
            - Who will read this? (CEO, board, technical, general)
            - What's the goal? (inform, persuade, celebrate, analyze)
            
            2. Data Personality
            - What story does data tell? (growth, stability, innovation, challenge, mixed)
            - What's the emotional tone? (professional, celebratory, analytical, urgent)
            - What's data density? (sparse, moderate, dense)
            
            3. Content Analysis
            - What are the 1-3 hero metrics? (most critical numbers)
            - What sections should exist?
            - What's the narrative arc?
            - What needs interpretation blocks?
            
            4. Design Decisions
            - What typography matches this story?
            - What color palette fits data personality?
            - What layout strategy works best?
            - What components are needed?
            
            Return JSON matching this exact schema:
            {{
                "document_analysis": {{
                    "document_type": "executive_report|year_review|dashboard|deep_analysis|comparison|narrative",
                    "primary_audience": "ceo|board|technical|client|internal",
                    "primary_goal": "inform|persuade|celebrate|analyze|compare",
                    "usage_context": "board_meeting|review|decision_making|knowledge_sharing",
                    "emotional_tone": "professional|celebratory|analytical|urgent|confident",
                    "communication_style": "concise|narrative|technical|persuasive|balanced",
                    "data_personality": "growth|stability|innovation|challenge|mixed",
                    "data_density": "sparse|moderate|dense"
                }},
                "content_structure": {{
                    "hero_metrics": [
                        {{"label": "...", "value": "...", "context": "...", "emphasis": "primary|secondary"}}
                    ],
                    "narrative_arc": {{
                        "headline": "one sentence summary",
                        "opening": "how to start",
                        "progression": "how story flows",
                        "conclusion": "how to end"
                    }},
                    "sections": [
                        {{
                            "section_id": "intro|overview|data|analysis|conclusion",
                            "title": "Section Title",
                            "content_summary": "what this section contains",
                            "components_needed": ["hero", "kpi_cards", "table", "insight_box", "chart"],
                            "data_focus": "what data to emphasize",
                            "interpretation_needed": true|false
                        }}
                    ]
                }},
                "design_system": {{
                    "typography": {{
                        "display_font": "Playfair Display|DM Sans|...",
                        "display_font_url": "google fonts url",
                        "body_font": "Source Sans Pro|Inter|...",
                        "body_font_url": "google fonts url",
                        "type_scale": {{
                            "hero": "96px",
                            "h1": "72px",
                            "h2": "48px",
                            "h3": "32px",
                            "body": "18px",
                            "small": "14px"
                        }},
                        "rationale": "why these fonts match the data story"
                    }},
                    
                    "colors": {{
                        "primary": "#......",
                        "accent": "#......",
                        "accent_2": "#......",
                        "background": "#......",
                        "surface": "#......",
                        "text": "#......",
                        "text_muted": "#......",
                        "border": "#......",
                        "success": "#......",
                        "warning": "#......",
                        "error": "#......",
                        "rationale": "why this palette matches data personality"
                    }},
                    
                    "layout": {{
                        "strategy": "narrative_flow|slide_sections|dashboard_grid|comparison_columns",
                        "max_width": "1200px|1400px|100%",
                        "section_spacing": "4rem|6rem|8rem",
                        "use_alternating_backgrounds": true|false,
                        "rationale": "why this layout serves the content"
                    }},
                    
                    "component_library": [
                        "hero_section",
                        "metric_card",
                        "kpi_grid",
                        "data_table",
                        "insight_block",
                        "comparison_grid",
                        "timeline",
                        "chart_container",
                        "callout_box"
                    ]
                }},
                
                "emphasis_hierarchy": {{
                    "most_important": ["what must be largest/most prominent"],
                    "key_supporting": ["what provides main context"],
                    "detailed_data": ["what's for deep readers"]
                }}
            }}
        """
        
        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )
        
        design_plan_str = ""
        for chunk in self.llm.runWithStreaming(
            chat,
            self.model_options,
            "super::plan_presentation_system",
            logInDb=self.log_info
        ):
            design_plan_str += chunk
            
        print("plan deisgn pppppp ", design_plan_str)
        design_plan = extract_json_after_llm(design_plan_str)
        
        # Save the plan for reference
        self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            payload={
                "content": f"Design System Planned: {design_plan['document_analysis']['document_type']}"
            }
        )
        
        return design_plan


    @log_function_io_and_time
    def generate_year_review_full_html(self, markdown, query):
        """
        Generate complete year review HTML in one shot
        No design plan needed - the prompt has everything
        """
        
        workspace = self.data_actions.get_workspace()
        output_path = os.path.join(workspace, "year-in-review-2025.html")

        previous_html = None

        # Load previous HTML if file exists
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                previous_html = f.read()
        
        # Load the comprehensive prompt
        system_prompt = YEAR_REVIEW_FULL_PROMPT  # This is the big template
        
        previous_html_section = ""

        if previous_html:
            previous_html_trimmed = previous_html[:60000]  # safety limit
            
            previous_html_section = f"""
                PREVIOUS HTML VERSION (for revision):
                ---
                {previous_html_trimmed}
                ---

                Instructions:
                - This is an existing report.
                - Improve it instead of recreating from scratch.
                - Preserve structure unless user asks for redesign.
            """

        
        user_prompt = f"""

            BUSINESS CONTEXT:
            {self.context_string}
            
            RESEARCH DATA (All markdown content):
            {markdown}
            {json.dumps(self.results, indent=2)}
            
            
            {previous_html_section}
            
            USER REQUEST: {query}
            
            ---
            
            Generate a complete, single-file HTML year-in-review document following 
            the template structure. Use ONLY real data from the research and database 
            results provided above. No placeholders should remain.
            
            Requirements:
            1. Fill in ALL numbers with real data
            2. Generate ALL charts with actual data arrays
            3. Write engaging narrative for each section
            4. Include strategic insights in insight boxes
            5. Make cumulative charts show growth over time
            6. Ensure all tables have real rows
            7. Validate numbers are consistent across sections
            
            Return the complete HTML file, ready to save and use.
            
            *****Most important: Write full html carefully. No code ommission is allowed, HTML scripts addition is mandatory.***
        """
        
        chat = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )

        html_output = ""
        model_options = ModelOptions(
            model=DEFAULT_MODEL,
            max_tokens=30000,
            temperature=DEFAULT_TEMP,
        )
        for chunk in self.llm.runWithStreamingV2(
            chat,
            model_options,
            "super::generate_yearly_report",
            logInDb=self.log_info
        ):
            html_output += chunk
        
        # Clean up any markdown artifacts
        html_output = clean_html_output(html_output)
        
        # Save to outputs
        workspace = self.data_actions.get_workspace()
        output_path = os.path.join(workspace, "year-in-review-2025.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_output)
        
        # return html_output
        
        self._create_event(
            step_id=self.current_step_id,
            event_type=AgentRunDAO.MAIN_STEP,
            event_name=AgentRunDAO.MARKER,
            payload={"content": "✓ HTML Generation Complete"}
        )
        
        self.final_report_exported = True
        
        appLogger.info({
            "event": "html_generation_complete",
            "html_length": len(html_output),
            # "sections_generated": len(section_contents),
            # "export_result": result
        })
        result = self.data_actions.export_content({
            "paths": [output_path],
            "export_format": "html"
        })
            
        return {
            "exported": True,
            "format": "html",
            "path": "year-in-review-2025.html",
            # "design_plan_saved": design_plan_path,
            # "sections_count": len(section_contents),
            "export_info": result
        }


    # ============================================================
    # FLOW 1: REPORT DOC GENERATION
    # Markdown → DOCX Export
    # ============================================================

    @log_function_io_and_time
    def generate_report_doc(self, query: str) -> Dict[str, Any]:
        """
        Two-phase document generation:
        Phase 1 — derive document outline from research
        Phase 2 — write the full document against that outline
        Markdown → DOCX
        """
        try:
            workspace = self.data_actions.get_workspace()
            
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Generating Document"}
            )

            # ============================================================
            # STEP 1: Read All Research — labeled by section
            # ============================================================
            ordered_files = self._get_ordered_files(fetch_html=False)
            merged_sections = []
            section_names = []

            for rel_path in ordered_files:
                if "merge" in rel_path:
                    continue

                full_path = os.path.join(workspace, rel_path)
                if not os.path.isfile(full_path):
                    continue

                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                section_name = os.path.splitext(os.path.basename(rel_path))[0].replace("_", " ").title()
                section_names.append(section_name)
                merged_sections.append(f"\n\n### Research Section: {section_name}\n\n{content}")

            merged_markdown = "\n\n".join(merged_sections).strip()
            has_research = bool(merged_markdown)

            appLogger.info({
                "event": "report_research_loaded",
                "files_count": len(ordered_files),
                "section_names": section_names,
                "length": len(merged_markdown)
            })

            # ============================================================
            # STEP 2: Extract intent signals from rough plan
            # ============================================================
            output_intent   = self.rough_plan.get("output_intent", {}) or {}
            doc_type_hint   = output_intent.get("document_type", "") or ""
            audience_hint   = output_intent.get("audience", "") or ""
            tone_hint       = output_intent.get("tone", "") or ""

            # ============================================================
            # STEP 4: Phase 2 — Generate full document against outline
            # The outline is a hard contract — every section must appear.
            # ============================================================
            user_prompt = f"""
                ════════════════════════════════════════════════════════════
                DOCUMENT REQUEST
                ════════════════════════════════════════════════════════════

                User's original request:
                {query}

                Document type: {doc_type_hint or "infer from request"}
                Audience:      {audience_hint or "infer from request"}
                Tone:          {tone_hint or "infer from document type"}

                ════════════════════════════════════════════════════════════
                ORGANIZATION CONTEXT
                ════════════════════════════════════════════════════════════

                {self.context_string}

                {TRMERIC_FUNCTIONAL_CAPABILITIES}


                ════════════════════════════════════════════════════════════
                RESEARCH MATERIAL
                (Use this material to ground and support the document.)
                ════════════════════════════════════════════════════════════

                {merged_markdown if has_research else "No prior research files — write from analysis results and organization context."}

                ════════════════════════════════════════════════════════════
                ANALYSIS RESULTS
                ════════════════════════════════════════════════════════════

                {json.dumps(self.results, indent=2)}

                ════════════════════════════════════════════════════════════
                CRITICAL WRITING RULES FOR THIS DOCUMENT
                ════════════════════════════════════════════════════════════

                1. COVER EVERYTHING THE USER ASKED FOR — read the request carefully.
                Every explicit ask must become a section. If they asked for a big 
                picture view, that's a section. If they asked for a gap analysis, 
                that's a section. If they asked for build recommendations, that's 
                a section. Nothing the user asked for can be missing.

                2. DO NOT compress or summarize research — expand it into narrative.
                If research says "Requires Verification", state what specifically
                needs verification and why it matters. Do not hide behind the label.

                3. USE organization context and capabilities to fill any comparison
                before declaring something unknown. Only say "requires verification"
                when genuinely not described anywhere in the context provided.

                4. EACH SECTION must be substantively different from the others.
                No repeated tables. No repeated recommendations. Each insight 
                appears exactly once, in the most appropriate section.

                5. SYNTHESIZE — tell the reader something they could not get from
                reading the raw research themselves.

                6. Ground every claim in this organization's specific context.
                Generic writing that could apply to any company is forbidden.

                7. Return ONLY valid markdown. Start with # on line 1.
                
            """

            chat = ChatCompletion(
                system=UNIVERSAL_DOCUMENT_SYSTEM_PROMPT,
                prev=[],
                user=user_prompt
            )

            report_content = ""
            for chunk in self.llm.runWithStreamingV2(
                chat,
                self.model_options,
                "super::generate_report_doc",
                logInDb=self.log_info
            ):
                report_content += chunk

            # ============================================================
            # STEP 5: Save Markdown
            # ============================================================
            report_md_path = os.path.join(workspace, "document.md")
            with open(report_md_path, "w", encoding="utf-8") as f:
                f.write(report_content.strip())

            appLogger.info({
                "event": "report_markdown_saved",
                "path": "document.md",
                "length": len(report_content)
            })

            # ============================================================
            # STEP 6: Export to DOCX
            # ============================================================
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Converting to DOCX"}
            )

            export_result = self.data_actions.export_content({
                "paths": ["document.md"],
                "export_format": "docx"
            })

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "✓ Document Generated"}
            )

            self.final_report_exported = True

            return {
                "exported": True,
                "format": "docx",
                "markdown_path": "document.md",
                "export_result": export_result
            }

        except Exception as e:
            appLogger.error({
                "event": "report_doc_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })

            return {
                "exported": False,
                "format": "docx",
                "error": str(e)
            }

    # ============================================================
    # FLOW 2: GENERIC HTML GENERATION (ONE-SHOT)
    # For all non-year-review HTML types
    # ============================================================

    @log_function_io_and_time
    def generate_generic_html(self, design_plan, merged_markdown: str, query: str) -> Dict[str, Any]:
        """
        One-shot HTML generation for all document types
        Uses design plan but generates complete HTML in single call
        """
        try:
            workspace = self.data_actions.get_workspace()
            
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Starting HTML Generation"}
            )
            
            # ============================================================
            # STEP 2: Analyze & Plan Design (Keep this - it's good)
            # ============================================================
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Analyzing Content & Planning Design"}
            )
            
            # ============================================================
            # STEP 3: Generate Complete HTML in One Shot
            # ============================================================
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "Generating Complete HTML"}
            )
            
            system_prompt = GENERIC_HTML_SYSTEM_PROMPT
            
            user_prompt = f"""
                BUSINESS CONTEXT:
                {self.context_string}
                
                {TRMERIC_FUNCTIONAL_CAPABILITIES}
                
                DESIGN PLAN (AUTHORITATIVE):
                {json.dumps(design_plan, indent=2)}

                USER REQUEST:
                {query}

                RESEARCH DATA:
                {merged_markdown}

                ANALYSIS RESULTS:
                {json.dumps(self.results, indent=2)}

                ---

                Generate the complete HTML document following the design plan.

                SECTIONS TO INCLUDE:
                {json.dumps([s['title'] for s in design_plan['content_structure']['sections']])}

                HERO METRICS:
                {json.dumps(design_plan['content_structure']['hero_metrics'])}

                Requirements:
                1. Complete, valid HTML5 document
                2. All sections with real data
                3. Professional design matching plan
                4. Responsive and polished
                5. No placeholders

                Return ONLY the HTML. No commentary.
            """

            chat = ChatCompletion(
                system=system_prompt,
                prev=[],
                user=user_prompt
            )
            
            html_output = ""
            for chunk in self.llm.runWithStreamingV2(
                chat,
                self.model_options,
                "super::generate_generic_html",
                logInDb=self.log_info
            ):
                html_output += chunk
            
            # Clean up
            html_output = clean_html_output(html_output)
            
            # ============================================================
            # STEP 4: Save & Export
            # ============================================================
            html_path = os.path.join(workspace, "presentation.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_output)
            
            # Export
            result = self.data_actions.export_content({
                "paths": [html_path],
                "export_format": "html"
            })
            
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": "✓ HTML Generation Complete"}
            )
            
            self.final_report_exported = True
            
            return {
                "exported": True,
                "format": "html",
                "path": "presentation.html",
                "export_info": result
            }
            
        except Exception as e:
            appLogger.error({
                "event": "html_generation_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                payload={"content": f"✗ HTML Failed: {str(e)}"}
            )
            
            return {
                "exported": False,
                "format": "html",
                "error": str(e)
            }
    
    
    

    # ══════════════════════════════════════════════════════════════════════════════
    # _run_generate_report_doc  —  JS pipeline, mirrors PPT exactly
    # ══════════════════════════════════════════════════════════════════════════════
    @log_function_io_and_time
    def _run_generate_report_doc(self, query: str, doc_spec: dict = None) -> Dict[str, Any]:
        """
        Generates a professional DOCX from self.results using docx.js Node.js pipeline.
        LLM writes complete docx.js script → Node executes → uploads to S3.
        Mirrors _run_generate_ppt_after_analysis exactly.
        """
        try:
            workspace = self.data_actions.get_workspace()

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Generating Document"}
            )

            # ── Extract spec ──────────────────────────────────────────────────
            output_intent = self.rough_plan.get("output_intent", {}) or {}
            title    = (doc_spec or {}).get("title", "Report") or "Report"
            doc_type = (doc_spec or {}).get("document_type") or output_intent.get("document_type", "report")
            audience = (doc_spec or {}).get("audience")      or output_intent.get("audience", "management")
            tone     = (doc_spec or {}).get("tone")          or output_intent.get("tone", "professional")
            scope    = (doc_spec or {}).get("scope", "")
            # sections = (doc_spec or {}).get("sections_to_cover", [])
            emphasis = (doc_spec or {}).get("key_emphasis", "")
            slug_title = slugify(title)
            docx_path = os.path.join(workspace, f"artifact_{slug_title}.docx")

            spec_block = f"""
            ════════════════════════════════════════════════════════════
            DOCUMENT SPECIFICATION
            ════════════════════════════════════════════════════════════
            Title:             {title}
            Document type:     {doc_type}
            Audience:          {audience}
            Tone:              {tone}
            Scope:             {scope}
            Key emphasis:      {emphasis if emphasis else 'derive from most significant data points'}
            Output file:       {docx_path}
            ════════════════════════════════════════════════════════════
            """

            user_prompt = f"""
                ORGANIZATION CONTEXT:
                {self.context_string}

                {TRMERIC_FUNCTIONAL_CAPABILITIES}

                {spec_block}

                USER REQUEST:
                {query}

                Conversation History:
                {self.conv if self.conv != "No prior conversation." else "New conversation."}

                ANALYSIS RESULTS (primary data source — use every real number and fact):
                {json.dumps(self.results, indent=2)}

                ════════════════════════════════════════════════════════════════════════
                CRITICAL WRITING RULES
                ════════════════════════════════════════════════════════════════════════

                1. COVER EVERYTHING THE USER ASKED FOR.
                Every explicit ask must become a section.

                2. DO NOT compress or summarize — expand into narrative prose.
                Short sections are failures. Each section must be substantive.

                3. Only use facts present in ANALYSIS RESULTS or ORGANIZATION CONTEXT.
                Ground every claim in this organization's specific context.
                Generic writing that could apply to any company is FORBIDDEN.

                4. EACH SECTION must be substantively different from the others.

                5. SYNTHESIZE — tell the reader something they could not get 
                from reading raw data themselves.

                ════════════════════════════════════════════════════════════════════════
                COMPLETION RULE — THIS IS MANDATORY, NOT OPTIONAL
                ════════════════════════════════════════════════════════════════════════

                The document type will be classified by the system prompt based on the user request.
                Apply the COMPLETION RULE to whatever type is classified.
                
                Every section of a PRD MUST be written. No section may be left blank,
                vague, or marked as missing.

                FORBIDDEN OUTPUTS (any of these = failure):
                ✗ "Not specified in available data."
                ✗ "TBD"
                ✗ "Unknown"
                ✗ "Not documented"
                ✗ "Further detail should be gathered"
                ✗ "$0.0" for budget — if budget is unknown, reason about it

                When source data is missing for a section, you MUST:
                • Design it from first principles using the context you DO have
                • State clearly: "Assumption: [your reasoning]"
                • Produce concrete, specific, actionable content

                SECTIONS THAT REQUIRE DESIGN (not reporting):

                Data Model:
                → Identify the core entities this system manages.
                → Define their key attributes and relationships.
                → Example: "DigitalOffering, DeploymentWorkflow, AdoptionCampaign,
                    ResourceAllocation — each with audit timestamps and ownership metadata."

                API Contracts:
                → Design the key interfaces this system needs.
                → Even internal APIs between components count.
                → Show endpoint patterns, input/output shapes.

                Alternatives Considered:
                → What other approaches could have solved this problem?
                → Why was the chosen approach selected over each alternative?
                → Minimum 2-3 real alternatives with honest trade-off reasoning.

                Dependencies:
                → What systems, teams, or external services must this integrate with?
                → What must be true before each phase can start?

                Stakeholders:
                → Who owns this initiative? Who are the users? Who approves decisions?
                → Map stakeholders to sections of the PRD they care about most.

                Budget:
                → If budget data shows $0.0 or is missing, DO NOT write "$0.0".
                → Instead: reason about cost drivers, resource needs, and write:
                    "Assumption: Budget is pending formal allocation. Based on the
                    scope — 3 automation workflows, a live dashboard, quarterly workshops,
                    and enablement campaigns across [N] segments — an estimated range of
                    $X–$Y is recommended, covering [engineering time / tooling / facilitation]."

                ════════════════════════════════════════════════════════════════════════
                QUALITY BAR
                ════════════════════════════════════════════════════════════════════════

                This document must read as if written by a senior product manager
                who deeply understands this initiative — not as a data reporter
                who filled in a template with whatever was available.

                Return ONLY valid markdown. Start with # on line 1.
                No preamble. No meta-commentary. First word = first word of the document.
            """

            chat = ChatCompletion(
                system=UNIVERSAL_DOCUMENT_SYSTEM_PROMPT,
                prev=[],
                user=user_prompt
            )

            # ── Stream JS from LLM ────────────────────────────────────────────
            js_code = ""
            model_options = ModelOptions(
                model=DEFAULT_MODEL,
                max_tokens=25000,
                temperature=DEFAULT_TEMP,
            )
            for chunk in self.llm.runWithStreamingV2(
                chat,
                model_options,
                "super::generate_report_doc",
                logInDb=self.log_info
            ):
                js_code += chunk

            js_code = js_code.strip()
            # if js_code.startswith("```"):
            #     js_code = "\n".join(js_code.split("\n")[1:])
            # if js_code.endswith("```"):
            #     js_code = "\n".join(js_code.split("\n")[:-1])
            # js_code = js_code.strip()

            # slug_title = slugify(title)
            # ── Write JS to workspace ─────────────────────────────────────────
            js_path = os.path.join(workspace, f"artifact_{slug_title}.md")
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(js_code)

            appLogger.info({"event": "doc_js_written", "path": js_path, "length": len(js_code)})

            # ── Run Node.js ───────────────────────────────────────────────────
            # self._create_event(
            #     step_id=self.current_step_id,
            #     event_type=AgentRunDAO.MAIN_STEP,
            #     event_name=AgentRunDAO.MARKER,
            #     parent_event_id=self.current_execution_id,
            #     # payload={"content": "Running docx.js"}
            #     payload={"content": "Converting to DOCX"}
            # )

            # node_result = run_node_script(js_path, workspace)

            # if not node_result["success"]:
            #     appLogger.error({"event": "doc_node_failed", "stderr": node_result["stderr"], "stdout": node_result["stdout"]})
            #     return {
            #         "exported": False,
            #         "format": "docx",
            #         "buggy_code_generated": js_code,
            #         "error": "Node.js execution failed — script was likely truncated mid-generation. Retry with fewer sections (max 5) or shorter content per section.",
            #         "node_stderr": node_result["stderr"][:300]
            #     }

            # if not os.path.exists(docx_path):
            #     return {
            #         "exported": False,
            #         "format": "docx",
            #         "error": "docx.js ran successfully but .docx file was not created"
            #     }

            # appLogger.info({"event": "doc_generated", "path": docx_path, "size_bytes": os.path.getsize(docx_path)})

            # ── Upload to S3 ──────────────────────────────────────────────────
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Uploading Document"}
            )

            export_result = self.data_actions.export_content({
                "paths": [js_path],
                "export_format": "docx"
            })

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "✓ Document Generated"}
            )

            self.final_report_exported = True

            return {
                "exported": True,
                "format": "docx",
                "code": js_code,
                "path": f"{slug_title}.docx",
                "export_result": export_result,
                # "node_stdout": node_result["stdout"]
            }

        except Exception as e:
            appLogger.error({"event": "report_doc_failed", "error": str(e), "traceback": traceback.format_exc()})
            return {
                "exported": False,
                "format": "docx",
                "error": str(e)
            }
            
    # ────────────────────────────────────────────────────────────
    # HTML AFTER ANALYSIS
    # ────────────────────────────────────────────────────────────
    @log_function_io_and_time
    def _run_generate_html_after_analysis(self, query: str, html_spec: dict = None) -> Dict[str, Any]:
        """
        Generates a polished single-file HTML artifact from self.results.
        Triggered when the loop calls generate_html_after_analysis action.
        """
        try:
            workspace = self.data_actions.get_workspace()

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Generating HTML Document"}
            )

            output_intent = self.rough_plan.get("output_intent", {}) or {}
            title       = (html_spec or {}).get("title", "")
            purpose     = (html_spec or {}).get("purpose") or output_intent.get("document_type", "dashboard")
            audience    = (html_spec or {}).get("audience") or output_intent.get("audience", "management")
            tone        = (html_spec or {}).get("tone") or output_intent.get("tone", "professional")
            color_theme = (html_spec or {}).get("color_theme", "dark")
            sections    = (html_spec or {}).get("sections_to_cover", [])
            emphasis    = (html_spec or {}).get("key_emphasis", "")
            data_persona = (html_spec or {}).get("data_personality", "mixed")

            user_prompt = f"""
                ORGANIZATION CONTEXT:
                {self.context_string}

                USER REQUEST:
                {query}

                Conversation History:
                {self.conv if self.conv != "No prior conversation." else "New conversation."}

                HTML SPEC:
                Title:            {title}
                Purpose:          {purpose}
                Audience:         {audience}
                Tone:             {tone}
                Color theme:      {color_theme}
                Data personality: {data_persona}
                Sections:         {sections if sections else 'derive from data and user request'}
                Key emphasis:     {emphasis if emphasis else 'derive from most significant data points'}

                ANALYSIS RESULTS — this is your primary data source.
                Read every entity, number, name, status, date, and image description here.
                Use ALL of it. Do not invent data that contradicts this.
                {json.dumps(self.results, indent=2)}

                Now classify the output type (DASHBOARD / REPORT / LANDING PAGE / DATA TABLE),
                detect the visual personality, and generate the complete HTML file.
                Return ONLY the HTML. Nothing else.
            """

            chat = ChatCompletion(
                system=HTML_AFTER_ANALYSIS_SYSTEM_PROMPT,  # the new constant
                prev=[],
                user=user_prompt
            )

            html_output = ""
            # model_options = ModelOptions(
            #     model=DEFAULT_MODEL,
            #     max_tokens=16000,
            #     temperature=DEFAULT_TEMP,
            # )
            model_options = ModelOptions2(
                model="gpt-5.4",
                max_output_tokens=100000,
                temperature=DEFAULT_TEMP,
            )
            for chunk in self.llm.exec_stream(
                chat,
                model_options,
                "super::generate_html_after_analysis",
                logInDb=self.log_info
            ):
                html_output += chunk

            # Clean any markdown artifacts
            from .helper import clean_html_output
            html_output = clean_html_output(html_output)

            # Save
            html_path = os.path.join(workspace, "document.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_output)

            # Export
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Exporting HTML"}
            )

            export_result = self.data_actions.export_content({
                "paths": [html_path],
                "export_format": "html"
            })

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "✓ HTML Document Generated"}
            )

            self.final_report_exported = True

            return {
                "exported": True,
                "format": "html",
                "path": "document.html",
                "export_result": export_result,
                "html_code": html_output
            }

        except Exception as e:
            appLogger.error({
                "event": "html_after_analysis_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"exported": False, "format": "html", "error": str(e)}
        

    @log_function_io_and_time
    def _run_generate_ppt_after_analysis(self, query: str, ppt_spec: dict = None) -> Dict[str, Any]:
        try:
            workspace = self.data_actions.get_workspace()
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Generating Presentation"}
            )

            # ── Extract spec ──────────────────────────────────────────────
            output_intent   = self.rough_plan.get("output_intent", {}) or {}
            title           = (ppt_spec or {}).get("title", "Presentation")
            purpose         = (ppt_spec or {}).get("purpose") or output_intent.get("document_type", "executive_update")
            audience        = (ppt_spec or {}).get("audience") or output_intent.get("audience", "management")
            tone            = (ppt_spec or {}).get("tone") or output_intent.get("tone", "professional")
            slide_count     = (ppt_spec or {}).get("slide_count_hint", 8)
            color_theme_key = (ppt_spec or {}).get("color_theme", "midnight_executive")
            sections        = (ppt_spec or {}).get("sections_to_cover", [])
            emphasis        = (ppt_spec or {}).get("key_emphasis", "")
            quality_feedback = (ppt_spec or {}).get("quality_feedback", [])

            color_theme = PPT_COLOR_THEMES.get(color_theme_key) or PPT_COLOR_THEMES["midnight_executive"]
            slug_title  = slugify(title)
            pptx_path   = os.path.join(workspace, "presentation.pptx")

            # ── Quality feedback block (retry path) ───────────────────────
            quality_block = ""
            if quality_feedback:
                quality_block = f"""
                    ════════════════════════════════════════════════════════════
                    QUALITY GATE FEEDBACK — THIS IS A RETRY. FIX THESE ISSUES:
                    ════════════════════════════════════════════════════════════
                    {chr(10).join(f"  • {item}" for item in quality_feedback)}

                    Address every point above explicitly in this version.
                    ════════════════════════════════════════════════════════════
                """

            # ── User prompt ───────────────────────────────────────────────
            user_prompt = f"""
                ORGANIZATION CONTEXT:
                {self.context_string}

                USER REQUEST:
                {query}

                Conversation History:
                {self.conv if self.conv != "No prior conversation." else "New conversation."}

                ════════════════════════════════════════════════════════════
                PRESENTATION SPECIFICATION
                ════════════════════════════════════════════════════════════
                Title:         {title}
                Purpose:       {purpose}
                Audience:      {audience}
                Tone:          {tone}
                Slide count:   approximately {slide_count} slides
                Color theme:   {color_theme_key}
                Sections:      {sections if sections else 'derive from data and user request'}
                Key emphasis:  {emphasis if emphasis else 'derive from most significant data points'}
                Output file:   {pptx_path}

                COLOR PALETTE — build your C object from these exact values:
                primary:    "{color_theme['primary']}"
                secondary:  "{color_theme['secondary']}"
                accent:     "{color_theme['accent']}"
                pop:        "{color_theme.get('pop', color_theme['accent'])}"
                bgDark:     "{color_theme['bg_dark']}"
                bgLight:    "{color_theme['bg_light']}"
                panelBg:    "{color_theme.get('panel_bg', 'EDEEF8')}"
                lightMuted: "{color_theme.get('light_muted', '94A3B8')}"
                ════════════════════════════════════════════════════════════

                {quality_block}

                ════════════════════════════════════════════════════════════
                ANALYSIS RESULTS — YOUR PRIMARY DATA SOURCE
                ════════════════════════════════════════════════════════════

                Read every item below before writing a single slide.
                Extract: every number, name, date, status, percentage, title.
                Then do the data mapping from Part 9 of your instructions:
                - What is the hero number?
                - What are the main categories?
                - Is there trend/time-series data?
                - Are there status signals (on_track / at_risk / compromised)?
                - Is there a sequence or timeline?

                {json.dumps(self.results, indent=2)}

                ════════════════════════════════════════════════════════════
                GENERATE THE COMPLETE PPTXGENJS NODE.JS SCRIPT NOW.
                ════════════════════════════════════════════════════════════

                Requirements:
                1. First character: 'c' (const pptxgen = require("pptxgenjs"))
                2. Define const C = {{ ... }} using the palette values above
                3. Define const makeShadow = () => ({{ ... }}) factory
                4. Use pres.writeFile({{ fileName: "{pptx_path}" }})
                5. Sandwich structure: dark title → light content → dark closing
                6. One visual surprise slide (hero number, bold statement, or before/after)
                7. Every slide uses a skeleton from the instructions — no bare text
                8. Every string uses \\n for line breaks — never literal newlines
                9. All data comes from ANALYSIS RESULTS above — zero placeholders
                10. ~{slide_count} slides covering: {sections if sections else 'all major topics'}

                Return ONLY valid Node.js. No markdown. No fences. No commentary.
            """

            chat = ChatCompletion(
                system=PPT_GENERATION_SYSTEM_PROMPT,
                prev=[],
                user=user_prompt
            )

            model_options = ModelOptions2(
                model="gpt-5.4",
                max_output_tokens=100000,
                temperature=DEFAULT_TEMP,
            )

            # ── Stream LLM ────────────────────────────────────────────────
            js_code = ""
            for chunk in self.llm.exec_stream(
                chat,
                model_options,
                "super::generate_ppt_after_analysis",
                logInDb=self.log_info
            ):
                js_code += chunk

            # ── Strip any accidental markdown fences ──────────────────────
            js_code = js_code.strip()
            if js_code.startswith("```"):
                js_code = "\n".join(js_code.split("\n")[1:])
            if js_code.endswith("```"):
                js_code = "\n".join(js_code.split("\n")[:-1])
            js_code = js_code.strip()

            # ── Fix literal newlines inside JS strings (crash prevention) ─
            js_code = sanitize_js_strings(js_code)

            # ── Write JS to workspace ─────────────────────────────────────
            js_path = os.path.join(workspace, f"{slug_title}.js")
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(js_code)

            appLogger.info({
                "event": "ppt_js_written",
                "path": js_path,
                "length": len(js_code),
                "is_retry": bool(quality_feedback)
            })

            # ── Run Node.js ───────────────────────────────────────────────
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Running PptxGenJS"}
            )

            node_result = run_node_script(js_path, workspace)

            if not node_result["success"]:
                appLogger.error({
                    "event": "ppt_node_failed",
                    "stderr": node_result["stderr"],
                    "stdout": node_result["stdout"],
                    "is_retry": bool(quality_feedback)
                })
                return {
                    "exported": False,
                    "format": "pptx",
                    "error": f"Node.js execution failed: {node_result['stderr'][:500]}"
                }

            if not os.path.exists(pptx_path):
                return {
                    "exported": False,
                    "format": "pptx",
                    "error": "PptxGenJS ran successfully but .pptx was not created"
                }

            appLogger.info({
                "event": "ppt_generated",
                "path": pptx_path,
                "size_bytes": os.path.getsize(pptx_path),
                "is_retry": bool(quality_feedback)
            })

            # ── Export to S3 ──────────────────────────────────────────────
            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "Uploading Presentation"}
            )

            export_result = self.data_actions.export_content({
                "paths": [pptx_path],
                "export_format": "pptx"
            })

            self._create_event(
                step_id=self.current_step_id,
                event_type=AgentRunDAO.MAIN_STEP,
                event_name=AgentRunDAO.MARKER,
                parent_event_id=self.current_execution_id,
                payload={"content": "✓ Presentation Generated"}
            )

            self.final_report_exported = True

            return {
                "exported": True,
                "format": "pptx",
                "path": "presentation.pptx",
                "export_result": export_result,
                "node_stdout": node_result["stdout"],
                "js_code_for_ppt": js_code,
            }

        except Exception as e:
            appLogger.error({
                "event": "ppt_after_analysis_failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {
                "exported": False,
                "format": "pptx",
                "error": str(e)
            }
        

    def _get_files_created_in_run(self) -> list:
        """
        Returns all files written to the workspace in this run.
        Excludes merge files. Includes .md, .html, .pptx, .docx, .xlsx, .json.
        Used to inform the execution planner what already exists.
        """
        workspace = self.data_actions.get_workspace()
        found = []

        ALLOWED_EXTENSIONS = {".md", ".html", ".json", ".js", ".docx", ".pptx"}

        for root, _, files in os.walk(workspace):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                if "merge" in f.lower():
                    continue

                full_path = os.path.join(root, f)
                try:
                    rel_path = os.path.relpath(full_path, workspace)
                    found.append({
                        "filename": f,
                        "path": rel_path,
                    })
                except Exception:
                    continue
        print("found ...", found)
        return found
