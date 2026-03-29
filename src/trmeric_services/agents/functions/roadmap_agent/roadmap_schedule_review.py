import json
import traceback
from datetime import datetime
from .action_agent import RoadmapAgent
from typing import List, Dict, Any, Optional
from src.trmeric_database.dao import TangoDao, TenantDaoV2
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes

agent_name = "roadmap_agent"

# ---------------- Helpers ----------------

def safe_parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            pass
    return None


def compute_schedule_window_from_edited(edited_schedule: List[Dict[str, Any]]) -> (str, str):
    """Infer global scheduling window from user-edited schedule."""
    starts, ends = [], []
    for item in edited_schedule or []:
        sd = safe_parse_date(item.get("start_date", ""))
        ed = safe_parse_date(item.get("end_date", ""))
        if sd:
            starts.append(sd)
        if ed:
            ends.append(ed)
    if not starts or not ends:
        return "", ""
    return min(starts).strftime("%Y-%m-%d"), max(ends).strftime("%Y-%m-%d")


# ---------------- Review Agent ----------------

class RoadmapScheduleReviewAgent:
    """
    Second-phase engine:
    - takes user-edited schedule
    - fetches latest roadmap + resource data
    - evaluates feasibility & risks
    - returns a single rich Markdown report explaining impact
    """

    def __init__(self, base_agent, llm: Any):
        self.llm = llm
        self.base_agent = base_agent
        self.model_opts = ModelOptions(model="gpt-4.1", max_tokens=32000, temperature=0.2)

    def build_context_and_conversation(self, tenant_id: int, user_id: int, session_id: str):
        conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
            session_id=session_id,
            user_id=user_id,
            key="roadmap_agent_conv",
        )
        conversation = [c.get("value", "") for c in conv_][::-1]

        context = (
            self.base_agent.user_info_string
            + "\n"
            + self.base_agent.roadmap_context_string
            + "\n"
            + f"Company Basic Info: {TenantDaoV2.fetch_company(tenant_id=tenant_id)}"
        )
        return conversation, context

    def data_fetch_for_review(
        self,
        tenant_id: int,
        last_user_message: str,
        conversation: List[str],
        context: str,
    ):
        """
        Reuse RoadmapAgent's data_fetch_new to get:
        - roadmaps: latest roadmap data (with team_data etc.)
        - resource_data: latest resource/capacity info
        """
        base_roadmap_agent = RoadmapAgent(self.base_agent, self.llm)
        data = base_roadmap_agent.data_fetch_new(
            last_user_message=last_user_message,
            conversation=conversation,
            context=context,
            tenant_id=tenant_id,
        )
        return data.get("roadmaps", []), data.get("resource_data", [])

    def review_schedule_changes(
        self,
        tenant_id: int,
        user_id: int,
        session_id: str,
        socketio: Any,
        client_id: str,
        edited_schedule: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Main review function:
        - validates edited schedule
        - uses conversation/context + DB data
        - calls LLM to generate a single Markdown report
        - emits and returns {"insights_markdown": <markdown>}
        """

        try:
            socketio.emit(
                "spend_agent",
                {
                    "event": "timeline",
                    "data": {
                        "text": "Reviewing Changes",
                        "key": "Reviewing Changes",
                        "is_completed": False,
                    },
                },
                room=client_id,
            )

            # basic input validation
            if not edited_schedule:
                raise ValueError("edited_schedule is empty")

            # for item in edited_schedule:
            #     if not item.get("id") or not item.get("start_date") or not item.get("end_date"):
            #         raise ValueError("Invalid schedule item found in edited_schedule")

            conversation, context = self.build_context_and_conversation(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
            )
            datas = TangoDao.fetchTangoStatesForUserAndKeyAll(
                user_id=user_id,
                key="roadmap_agent_conv_data_pulled_for_scheduling",
            )
            data = []
            if datas and len(datas) > 0:
                data = datas[0]
                
            print("data s -- ", not datas)
            # latest DB-backed data
            # roadmaps, resource_data = self.data_fetch_for_review(
            #     tenant_id=tenant_id,
            #     last_user_message=f"Fetch all resources and roadmap data for scheduling, take all dates and roadmap states and portfolio from conversation "+ str(conversation),
            #     conversation=conversation,
            #     context=context,
            # )
            

            # LLM prompt: output ONLY markdown, no JSON
            prompt = ChatCompletion(
                system=f"""
                    You are a **Roadmap Schedule Change Impact Reviewer** for an enterprise PMO.

                    Context:
                    - An automated engine generated an initial roadmap schedule.
                    - The user has MANUALLY edited that schedule in the UI (changing dates, sequencing, etc.).
                    - You now need to REVIEW those changes and explain their impact.

                    ############################################################
                    ## INPUT DATA
                    ############################################################

                    - Roadmap master data from DB (authoritative source for each roadmap) and Resource capacity data (roles, allocations, roadmap assignments):
                    {data}

                    - User-edited schedule (this is what the user wants):
                    {json.dumps(edited_schedule, separators=(",", ":"))}

                    - Conversation/context (contains all the past conv and scheduling done):
                    {conversation}

                    ############################################################
                    ## YOUR TASK
                    ############################################################
                    Generate a SINGLE, rich MARKDOWN report that:
                    1. Clearly explains WHAT the user changed (per roadmap).
                    2. Explains the IMPACT of those changes:
                        - on timelines,
                        - on resource capacity / overload,
                        - on dependencies,
                        - on overall portfolio feasibility and risk.
                    3. Uses clear, PMO-friendly language:
                        - concise, direct, business-focused.
                        - no apologizing, no "as an AI", no meta-comments.
                    4. Provides elaborated reasons — not just 1-line comments — especially where changes are risky or problematic.

                    You are NOT rescheduling.
                    You are reviewing the user's changes and explaining:
                    - which changes are safe,
                    - which introduce risk,
                    - where conflicts or overloads appear,
                    - where dependencies get broken,
                    - and what you would recommend.

                    ############################################################
                    ## REQUIRED MARKDOWN STRUCTURE (FOLLOW EXACTLY)
                    ############################################################

                    You MUST produce Markdown in this structure (all sections required):

                    ## 📝 Schedule Change Review Summary
                    - 3–6 bullet points summarizing the overall nature of changes and risk level.

                    ### 1️⃣ Summary of User Edits (Roadmap-by-Roadmap)
                    - For each roadmap that appears in the edited schedule:
                      - Use one bullet in this format:
                        - **<Roadmap Title> (ID: <id>)** — dates changed from `<old_start> → <old_end>` to `<new_start> → <new_end>`; additional notes if it was pulled in, pushed out, shortened, extended, newly added, or removed.
                      - If DB data does not contain the previous dates, say "previous dates not available in system; only new dates visible".

                    ### 2️⃣ Impact Analysis by Roadmap
                    For each roadmap in the edited schedule, create a subheading:

                    #### <Roadmap Title> (ID: <id>)
                    - **Change type:** (pulled in / pushed out / compressed / extended / unchanged)
                    - **Timeline impact:** Explain how this affects its completion relative to window from con check, key milestones, and adjacent work.
                    - **Resource impact:** Explicitly mention any overloaded roles (e.g., "Data Engineer exceeds 85% allocation between Mar 10–24 due to overlap with <Other Roadmap>").
                    - **Dependency / sequencing impact:** If any obvious dependency is violated or improved.
                    - **Risk assessment:** One of: `Low`, `Medium`, `High` with 1–2 sentence elaboration.
                    - **Recommendation:** Very concrete advice, e.g., "Keep as-is", "Prefer pushing start by 1–2 weeks", "Consider extending duration by 10–15 days".

                    If you cannot detect any special impact due to limited data, state that explicitly but still comment briefly.

                    ### 3️⃣ Portfolio-Level Impact
                    - 3–7 bullets covering:
                      - overall throughput changes (more roadmaps packed, or less),
                      - clustering of work in certain months/weeks,
                      - concentration of pressure on specific roles,
                      - whether the plan still seems realistic inside scheduling window.

                    ### 4️⃣ Key Risks Introduced by the Edits
                    - 4–10 bullets.
                    - Each bullet should mention:
                      - which roadmap(s),
                      - which role(s),
                      - what time window,
                      - and what the practical risk is (delay, quality, burnout, dependency slip, etc.).

                    ### 5️⃣ Opportunities / Positive Effects of the Edits
                    - 3–8 bullets on:
                      - better alignment with strategy,
                      - earlier delivery of key outcomes,
                      - de-risking of specific areas,
                      - any simplification or clearer phasing created by the user edits.

                    ### 6️⃣ Recommended Next Actions for the PMO / Portfolio Lead
                    - 4–8 bullets.
                    - Prioritize highly actionable steps, e.g.:
                      - "Lock in the new dates for <X> as they are low-risk and improve sequencing."
                      - "Revisit resourcing plan for Data Engineering for weeks 12–14."
                      - "Ask business owner of <Y> whether they are comfortable with compressed QA window."

                    ### 7️⃣ Change Log (Before vs After — if data allows)
                    If you can infer old vs new dates from data:
                    - Add a Markdown table:

                    | Roadmap | ID | Before (start → end) | After (start → end) | Comment |
                    |--------|----|-----------------------|---------------------|---------|

                    If you cannot get previous dates reliably:
                    - Still create the table, but set "Before" as "Not available" and explain that only the new dates are visible.

                    ############################################################
                    ## OUTPUT FORMAT
                    ############################################################
                    - OUTPUT MUST BE PURE MARKDOWN.
                    - Do NOT wrap it in JSON.
                    - Do NOT add any keys like "insights_markdown".
                    - No backticks around the whole output.
                """,
                prev=[],
                user="Carefully see and tell me with these cahnges what all can get impacted in proper markdown",
            )

            debugLogger.info("[schedule_review] Calling LLM for markdown review of edited schedule")
            markdown_report = self.llm.runV2(
                prompt,
                self.model_opts,
                "agent::roadmap::schedule_review_markdown",
                {"tenant_id": tenant_id, "user_id": user_id},
            )

            # We assume runV2 returns plain text
            insights_markdown = markdown_report

            # Emit to frontend as a simple payload with markdown
            payload = {"insights_markdown": insights_markdown}
            socketio.emit(
                agent_name,
                {"event": "roadmap_schedule_reviewed", "data": payload},
                room=client_id,
            )

            # Save snapshot
            try:
                TangoDao.insertTangoState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    key="roadmap_schedule_review_markdown",
                    value=json.dumps(payload),
                    session_id=session_id,
                )
            except Exception as e:
                appLogger.error({
                    "event": "Failed to save roadmap_schedule_review_markdown snapshot",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

            socketio.emit(
                "spend_agent",
                {
                    "event": "timeline",
                    "data": {
                        "text": "Reviewing Changes",
                        "key": "Reviewing Changes",
                        "is_completed": True,
                    },
                },
                room=client_id,
            )

            return payload

        except Exception as e:
            appLogger.error({
                "event": "Roadmap schedule review failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            socketio.emit(
                agent_name,
                {"event": "error", "data": {"error": str(e)}},
                room=client_id,
            )
            socketio.emit(
                "spend_agent",
                {
                    "event": "timeline",
                    "data": {
                        "text": "Reviewing Changes",
                        "key": "Reviewing Changes",
                        "is_completed": True,
                    },
                },
                room=client_id,
            )
            return {"error": str(e)}


# ---------------- Entrypoint ----------------

def roadmap_schedule_review_fn(
    tenantID: int,
    userID: int,
    # edited_schedule: List[Dict[str, Any]],
    data: List[Dict[str, Any]] = None,
    # last_user_message: str = "",
    socketio: Any = None,
    client_id: str = None,
    llm: Any = None,
    sessionID: str = None,
    base_agent=None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Entry point for schedule review flow (Markdown-only).
    Returns: {"insights_markdown": "<markdown>"} or {"error": "..."}
    """
    edited_schedule =data if data else {}
    try:
        debugLogger.info(
            f"[schedule_review] tenant={tenantID}, user={userID}, edited_items={len(edited_schedule)}"
        )

        agent = RoadmapScheduleReviewAgent(base_agent=base_agent, llm=llm)
        return agent.review_schedule_changes(
            tenant_id=tenantID,
            user_id=userID,
            session_id=sessionID,
            socketio=socketio,
            client_id=client_id,
            edited_schedule=edited_schedule,
        )

    except Exception as e:
        appLogger.error({
            "event": "roadmap_schedule_review_fn failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        if socketio and client_id:
            socketio.emit(
                agent_name,
                {"event": "error", "data": {"error": str(e)}},
                room=client_id,
            )
        return {"error": str(e)}


ROADMAP_SCHEDULE_REVIEW = AgentFunction(
    name="roadmap_schedule_review_fn",
    description="""This function is used to review changes in a roadmap schedule and return markdown insights.""",
    args=[],
    return_description="",
    function=roadmap_schedule_review_fn,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)
