import json
import psycopg2.extras
from typing import List, Dict, Optional, Any
from datetime import datetime
from src.database.Database import db_instance
from src.utils.helper.common import MyJSON
from src.api.logging.AppLogger import appLogger, debugLogger
import traceback


class AgentRunDAO:
    
    # Step types
    USER_QUERY       = "user_query"
    ROUGH_PLAN       = "rough_plan"
    
    RESEARCH_SECTIONS_IDENTIFICATION = "research_sections_identification"
    # Step types (add these)
    EXECUTION_PLAN      = "execution_plan"
    SUB_EXECUTION_PLAN  = "sub_execution_plan"
    EXECUTION_RESULT    = "execution_result"
    FINAL_RESPONSE      = "final_response"
    
    # Statuses
    COMPLETED        = "completed"
    RUNNING          = "running"
    FAILED           = "failed"
    
    # Event types
    THOUGHT          = "thought"
    STEP_UPDATE      = "step_update"
    ACTION           = "action"
    ACTION_RESULT    = "action_result"
    
    # Thought subtypes (event_name)
    THINK_ALOUD      = "think_aloud_reasoning"
    RESEARCH_UPDATE  = "sequential_research_update"
    RESEARCH_CLOSURE = "research_closure"
    PLANNING_RATIONALE = "planning_rationale"
    EXECTION_RATIONALE = "execution_rationale"
    
    MARKER = "marker"
    MAIN_STEP = "main_step"
    

    # -------------------------------------------------------------------------
    # CREATE methods - INSERT
    # -------------------------------------------------------------------------

    @staticmethod
    def create_run_step(
        session_id: str,
        tenant_id: str,
        user_id: str,
        agent_name: str,
        run_id: str,
        step_type: str,
        step_index: int,
        step_payload: dict,
        status: str = COMPLETED
    ) -> Optional[int]:
        """
        Insert new AgentRunStep and return its id
        Returns None if insert failed
        """
        payload_json = json.dumps(step_payload)  # safe serialization

        query = """
            INSERT INTO agent_run_steps (
                session_id, tenant_id, user_id, agent_name, run_id,
                step_type, step_index, step_payload, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        params = (
            session_id,
            tenant_id,
            user_id,
            agent_name,
            run_id,
            step_type,
            step_index,
            payload_json,           # we send string → PostgreSQL will cast to jsonb
            status
        )

        try:
            result = db_instance.executeSQLQuery(query, params, fetch="one")
            if result and len(result) > 0:
                return result[0]  # first column = id
            return None
        except Exception as e:
            print(f"Error creating run step: {e}")
            return None

    @staticmethod
    def create_run_event(
        run_id: str,
        step_id: int,
        parent_event_id: Optional[int] = None,
        event_type: str = "thought",
        event_name: str = "",
        sequence_index: int = 0,
        local_index: Optional[int] = None,
        event_payload: Optional[dict] = None
    ) -> Optional[int]:
        payload_json = json.dumps(event_payload or {})

        query = """
            INSERT INTO agent_run_events (
                run_id, step_id, parent_event_id,
                event_type, event_name,
                sequence_index, local_index,
                event_payload, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        params = (
            run_id,
            step_id,
            parent_event_id,
            event_type,
            event_name,
            sequence_index,
            local_index,
            payload_json
        )

        try:
            result = db_instance.executeSQLQuery(query, params, fetch="one")
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            print(f"Error creating run event: {e}")
            return None

    # -------------------------------------------------------------------------
    # READ methods - SELECT
    # -------------------------------------------------------------------------

    @staticmethod
    def get_run_steps(
        run_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        include_payload: bool = True
    ) -> List[Dict]:

        payload_select = "step_payload" if include_payload else "NULL AS step_payload"

        where_clauses = ["run_id = %s"]
        params: List[Any] = [run_id]

        if tenant_id is not None:
            where_clauses.append("tenant_id = %s")
            params.append(tenant_id)

        if user_id is not None:
            where_clauses.append("user_id = %s")
            params.append(user_id)

        query = f"""
            SELECT 
                id,
                step_type,
                step_index,
                status,
                created_at,
                {payload_select}
            FROM agent_run_steps
            WHERE {' AND '.join(where_clauses)}
            ORDER BY step_index ASC
        """
        try:
            return db_instance.execute_query_safe(query, tuple(params))
        except Exception as e:
            print(f"Error fetching run steps: {e}")
            return []

    @staticmethod
    def get_latest_run_for_session(
        session_id: str,
        tenant_id: str,
        user_id: str,
        agent_name: Optional[str] = None
    ) -> Optional[str]:

        where_clauses = [
            "session_id = %s",
            "tenant_id = %s",
            "user_id = %s",
        ]
        params: List[Any] = [session_id, str(tenant_id), str(user_id)]

        if agent_name:
            where_clauses.append("agent_name = %s")
            params.append(agent_name)

        query = f"""
            SELECT run_id
            FROM agent_run_steps
            WHERE {' AND '.join(where_clauses)}
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            rows = db_instance.execute_query_safe(query, tuple(params))
            return rows[0]["run_id"] if rows else None
        except Exception as e:
            print(f"Error getting latest run: {e}")
            appLogger.error({
                "function":"get_latest_run_for_session",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return None


    @staticmethod
    def get_thoughts_for_run(
        run_id: str,
        thought_types: List[str] = None
    ) -> List[Dict]:
        # if thought_types is None:
        #     thought_types = ["think_aloud_reasoning", "sequential_research_update", "research_closure"]

        query = f"""
            SELECT *
            FROM agent_run_events
            WHERE run_id = '{run_id}'
            ORDER BY id ASC
        """
        # params = (run_id, thought_types)
        # params = (run_id,)

        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error fetching thoughts: {e}")
            return []

    @staticmethod
    def get_run_events_tree(run_id: str, step_id: Optional[int] = None) -> List[Dict]:
        step_filter = "AND step_id = %s" if step_id else ""
        params = [run_id]
        if step_id:
            params.append(step_id)

        query = f"""
            WITH RECURSIVE event_tree AS (
                SELECT 
                    id, run_id, step_id, parent_event_id,
                    event_type, event_name, sequence_index, local_index,
                    event_payload, created_at,
                    1 as depth
                FROM agent_run_events
                WHERE run_id = %s
                  AND parent_event_id IS NULL
                  {step_filter}

                UNION ALL

                SELECT 
                    e.id, e.run_id, e.step_id, e.parent_event_id,
                    e.event_type, e.event_name, e.sequence_index, e.local_index,
                    e.event_payload, e.created_at,
                    t.depth + 1
                FROM agent_run_events e
                INNER JOIN event_tree t ON e.parent_event_id = t.id
                WHERE t.depth < 10
            )
            SELECT * FROM event_tree
            ORDER BY sequence_index ASC, depth ASC, local_index ASC NULLS LAST
        """

        try:
            return db_instance.execute_query_safe(query, tuple(params))
        except Exception as e:
            print(f"Error fetching event tree: {e}")
            return []
      
      
    # -------------------------------------------------------------------------
    # UPDATE methods - Update
    # -------------------------------------------------------------------------

      
    @staticmethod
    def update_run_step(
        step_id: int,
        status: Optional[str] = None,
        step_payload: Optional[dict] = None
    ) -> bool:
        updates = []
        params = []

        if status is not None:
            updates.append("status = %s")
            params.append(status)

        if step_payload is not None:
            updates.append("step_payload = %s")
            params.append(json.dumps(step_payload))

        if not updates:
            return False

        params.append(step_id)

        query = f"""
            UPDATE agent_run_steps
            SET {', '.join(updates)}
            WHERE id = %s
        """

        try:
            db_instance.executeSQLQuery(query, tuple(params))
            return True
        except Exception as e:
            print(f"Error updating run step {step_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # HELPER methods
    # -------------------------------------------------------------------------
    @staticmethod
    def get_agent_context_from_steps(
        session_id: str,
        tenant_id: str,
        user_id: str,
        agent_name: str,
        max_steps: int = 1000
    ) -> str:
        """
        Build SESSION-SCOPED memory across ALL runs.

        IMPORTANT:
        - Includes run boundaries explicitly.
        - Previous run execution failures are historical only.
        - Only CURRENT run execution state is binding.
        """

        # --------------------------------------------------
        # 2️⃣ Fetch completed steps for that run
        # --------------------------------------------------
        steps_query = """
            SELECT
                step_type,
                step_payload,
                run_id,
                step_index,
                created_at
            FROM agent_run_steps
            WHERE session_id = %s
            AND tenant_id = %s
            AND user_id = %s
            AND agent_name = %s
            AND status = 'completed'
            ORDER BY created_at ASC, step_index ASC
        """

        params = (session_id, str(tenant_id), str(user_id), agent_name)

        try:
            rows = db_instance.execute_query_safe(steps_query, params)
        except Exception as e:
            print(f"Error building agent context: {e}")
            return "No prior agent context."

        if not rows:
            return "No prior agent context."

        rows = rows[-max_steps:]

        # --------------------------------------------------
        # 3️⃣ Distill steps into safe memory blocks
        # --------------------------------------------------
        context_blocks: List[str] = []
        current_run = None

        for row in rows:
            step_type = row.get("step_type")
            payload = row.get("step_payload") or {}
            run_id = row.get("run_id")

            # --------------------------------------------------
            # Explicit Run Boundary
            # --------------------------------------------------
            if run_id != current_run:
                current_run = run_id
                context_blocks.append(
                    f"\n--- RUN {run_id} (HISTORICAL CONTEXT) ---"
                )

            # -------------------------------
            # USER QUERY — ground truth
            # -------------------------------
            if step_type == AgentRunDAO.USER_QUERY:
                query_text = payload.get("query")
                if query_text:
                    context_blocks.append(
                        f"USER QUERY:\n{query_text}"
                    )

            # -------------------------------
            # ROUGH PLAN — intent grounding
            # -------------------------------
            elif step_type == AgentRunDAO.ROUGH_PLAN:
                context_blocks.append(
                    "AGENT UNDERSTANDING (ROUGH PLAN):\n"
                    + MyJSON.dumps(payload)
                )

            # --------------------------------------------------
            # FINAL RESPONSE (semantic continuity)
            # --------------------------------------------------
            elif step_type == AgentRunDAO.FINAL_RESPONSE:
                context_blocks.append(
                    "AGENT EXECUTION PLAN:\n"
                    + MyJSON.dumps(payload)
                )

            # --------------------------------------------------
            # EXECUTION PLAN (INFORMATIONAL ONLY)
            # --------------------------------------------------
            elif step_type == AgentRunDAO.EXECUTION_PLAN:
                context_blocks.append(
                    "SUB AGENT EXECUTION PLAN FOLLOWING MAIN AGENT PLAN:\n"
                    + MyJSON.dumps(payload)
                )

            elif step_type == AgentRunDAO.SUB_EXECUTION_PLAN:
                context_blocks.append(
                    "SUB AGENT EXECUTION PLAN FOLLOWING MAIN AGENT PLAN:\n"
                    + MyJSON.dumps(payload)
                )

            # NOTE:
            # We intentionally do NOT include execution results
            # or failure flags as binding memory.

        if not context_blocks:
            return "No usable prior agent context."

        return (
            "=== SESSION MEMORY (RUN-AWARE, NON-BINDING) ===\n\n"
            + "\n\n".join(context_blocks)
            + "\n\nIMPORTANT:\n"
            "- Only the CURRENT RUN execution results are binding.\n"
            "- Previous run failures may be retried if appropriate.\n"
        )


    @staticmethod
    def get_agent_qna_steps(
        session_id: str,
        tenant_id: str,
        user_id: str,
        agent_name: str,
        max_steps: int = 1000
    ) -> str:
        """
        Build agent reasoning context from AgentRunStep
        across ALL runs in a session.

        Canonical agent memory.
        """

        # --------------------------------------------------
        # 2️⃣ Fetch completed steps for that run
        # --------------------------------------------------
        steps_query = """
            SELECT
                step_type,
                step_payload,
                run_id,
                step_index,
                created_at
            FROM agent_run_steps
            WHERE session_id = %s
            AND tenant_id = %s
            AND user_id = %s
            AND agent_name = %s
            AND status = 'completed'
            ORDER BY created_at ASC, step_index ASC
        """

        params = (session_id, tenant_id, user_id, agent_name)

        try:
            rows = db_instance.execute_query_safe(steps_query, params)
        except Exception as e:
            print(f"Error building agent context: {e}")
            return "No prior agent context."

        if not rows:
            return "No prior agent context."

        # Safety window: only keep last N meaningful steps
        rows = rows[-max_steps:]

        # --------------------------------------------------
        # 3️⃣ Distill steps into safe memory blocks
        # --------------------------------------------------
        context_blocks: List[str] = []

        for row in rows:
            step_type = row.get("step_type")
            payload = row.get("step_payload") or {}
            run_id = row.get("run_id") or ""

            # -------------------------------
            # USER QUERY — ground truth
            # -------------------------------
            if step_type == AgentRunDAO.USER_QUERY:
                query_text = payload.get("query")
                if query_text:
                    context_blocks.append(
                        f"USER QUERY:\n{query_text}"
                    )

            # -------------------------------
            # FINAL RESPONSE — NEVER reused
            # -------------------------------
            elif step_type == AgentRunDAO.FINAL_RESPONSE:
                context_blocks.append(
                    f"AGENT RESPONSE :\n{MyJSON.dumps(payload)}"
                )

        if not context_blocks:
            return "No usable prior agent context."

        return (
            "=== AGENT MEMORY (SESSION SCOPED) ===\n\n"
            + "\n\n".join(context_blocks)
        )
