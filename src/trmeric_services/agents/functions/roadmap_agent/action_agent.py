from typing import List, Optional, Dict, Any
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_database.dao import PortfolioDao, TangoDao, RoadmapsDaoV2, TenantDaoV2
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
from datetime import datetime
from src.trmeric_services.agents.functions.roadmap_analyst.combined import view_combined_analysis
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.trmeric_services.tango.functions.integrations.internal.resource import get_capacity_data

agent_name = "roadmap_agent"

from datetime import datetime
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

def safe_parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None

    # Try standard YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        pass

    # Try DD-MM-YYYY
    try:
        return datetime.strptime(date_str, "%d-%m-%Y")
    except:
        pass

    # Try MM-DD-YYYY (rare but possible)
    try:
        return datetime.strptime(date_str, "%m-%d-%Y")
    except:
        pass

    return None


def compute_effort_summary(roadmap: Dict) -> Dict:
    team_data = roadmap.get("team_data") or []

    total_hours = 0
    total_cost = 0
    labour_roles = 0
    max_allocation = 0

    for t in team_data:
        try:
            if isinstance(t, str):
                t = json.loads(t)

            if t.get("labour_type") == "labour":
                labour_roles += 1
                total_hours += t.get("total_estimated_hours", 0)
                total_cost += t.get("total_estimated_cost", 0)
                max_allocation = max(max_allocation, t.get("allocation") or 0)
        except:
            continue

    roadmap["effort_summary"] = {
        "total_hours": total_hours,
        "total_cost": total_cost,
        "labour_roles": labour_roles,
        "max_allocation": max_allocation
    }
    return roadmap


def compute_possible_effort_days(roadmap):
    # 1. If root start & end exist
    sd = safe_parse_date(roadmap.get("start_date"))
    ed = safe_parse_date(roadmap.get("end_date"))
    if sd and ed:
        return max((ed - sd).days, 0)

    # 2. Infer from team_data blocks
    effort_days = []
    for entry in roadmap.get("team_data") or []:
        sd = safe_parse_date(entry.get("start_date"))
        ed = safe_parse_date(entry.get("end_date"))
        if sd and ed:
            effort_days.append((ed - sd).days)

    if effort_days:
        return max(effort_days)

    # 3. No usable timeline → let LLM infer
    return None


class RoadmapAgent:
    """Agent for prioritizing or scheduling roadmaps (future projects) based on user selection."""

    def __init__(self, base_agent, llm: Any):
        """Initialize with an LLM instance."""
        self.llm = llm
        self.base_agent = base_agent
        self.model_opts = ModelOptions(model="gpt-4.1", max_tokens=32000, temperature=0.2)

    def fetch_roadmap_data(
        self,
        tenant_id: int,
        user_id: int,
        portfolio_ids: List[int],
        action: str,
        session_id: str,
        socketio: Any,
        client_id: str
    ) -> Dict:
        """Fetch roadmap data via MasterAnalyst tailored to the specified action.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.
            portfolio_ids: List of portfolio IDs (empty for all roadmaps).
            action: Action (prioritize or schedule).
            session_id: Session ID.
            socketio: SocketIO instance.
            client_id: Client ID.

        Returns:
            Dictionary with roadmap data and business data or error.
        """
        try:
            debugLogger.info(f"process_roadmaps fetch_roadmap_data: {action}")
            # if action == "prioritize":
            #     query = """
            #         I want to prioritize my roadmaps. Fetch roadmap data with detailed information relevant to prioritization, including:
            #         - KPIs, org strategy, description, portfolio, scope, constraints.
            #     """
            # elif action == "schedule":
            #     query = """
            #         I want to schedule my roadmaps. Fetch roadmap data for scheduling, focusing on:
            #         - roadmap id, roadmap title, portfolio, roadmap priority, roadmap priority in portfolio, team.
            #     """
            # else:
            #     raise ValueError(f"Invalid action: {action}")
            # if portfolio_ids:
            #     query += f" Filter by portfolio IDs: {portfolio_ids}."
            # else:
            #     query += " Include all roadmaps."
            # if action == "prioritize":
            #     query += "Force this check: Very important to only fetch roadmaps which are Intake, Elaboration, Solutioning, Prioritize"   
            # elif action == "schedule":
            #     query += "Very important to only fetch roadmaps which are Approved"
             
            # debugLogger.info(f"Querying MasterAnalyst: {query}")
            # response = None
            # for chunk in view_combined_analysis(
            #     tenantID=tenant_id,
            #     userID=user_id,
            #     last_user_message=query,
            #     socketio=None,
            #     client_id=client_id,
            #     llm=self.llm,
            #     sessionID=session_id,
            #     mode="only_data",
            #     base_agent=self.base_agent
            # ):
            #     response = chunk   
            # roadmaps_data = response.get("roadmaps_data", [])
            # resource_data = response.get("resource_data", [])
                
            
            if action == "prioritize":
                projection_attrs = [
                    "id",
                    "title",
                    "description",
                    "org_strategy",
                    "key_results",
                    "constraints",
                    "portfolios",
                    "team_data",      # <-- NEW (important)
                    "budget",         # <-- optional but useful for ROI
                    "start_date",     # <-- helps time sensitivity
                    "end_date"
                ]
                state_filter = "rr.current_state IN (0, 4, 5, 6)"
                order_clause = "ORDER BY rr.rank ASC"

            elif action == "schedule":
                projection_attrs = [
                    "id", "title", "priority", "portfolios", "team_data"
                ]
                state_filter = "rr.current_state = 1"
                order_clause = "ORDER BY rr.start_date ASC"

            else:
                raise ValueError(f"Invalid action: {action}")

            response = RoadmapsDaoV2.fetchRoadmapsDataWithProjectionAttrs(
                tenant_id=tenant_id,
                projection_attrs=projection_attrs,
                portfolio_ids=portfolio_ids,
                state_filter=state_filter,
                order_clause=order_clause
            )
                
            roadmaps_data = response
            resource_data = get_capacity_data(
                tenantID=tenant_id,
                userID=user_id
            )
            if not roadmaps_data:
                appLogger.warning(f"No roadmap data returned from MasterAnalyst for action: {action}")
                socketio.emit(
                    agent_name,
                    {"event": "error", "data": {"error": "No roadmap data found."}},
                    room=client_id
                )
                return {"error": "No roadmap data found."}

            debugLogger.info(f"Fetched {len(roadmaps_data)} roadmaps for action: {action}")
            return {
                "roadmaps_data": roadmaps_data,
                "resource_data": resource_data
            }
            
        except Exception as e:
            appLogger.error({
                "event": f"Failed to fetch roadmap data for action {action}",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"error": str(e)}

    def prioritize_roadmaps(
        self,
        roadmaps: List[Dict],
        tenant_id: int,
        user_id: int,
        session_id: str,
        socketio: Any,
        client_id: str
    ) -> List[Dict]:
        """Prioritize roadmaps in batches using a weighted scoring framework, assigning final priority based on total_score.

        Args:
            roadmaps: List of roadmap dictionaries.
            tenant_id: Tenant ID.
            user_id: User ID.
            session_id: Session ID.
            socketio: SocketIO instance.
            client_id: Client ID.

        Returns:
            List of prioritized roadmaps with reasoning and final priority based on total_score.
        """
        # Constants
        BATCH_SIZE = 20  # Adjust based on LLM token limits and performance
        MAX_THREADS = 3  # Adjust based on system resources
        
        # Add effort summary to each roadmap
        for r in roadmaps:
            compute_effort_summary(r)

        def chunk_roadmaps(items: List[Dict], chunk_size: int) -> List[List[Dict]]:
            """Split roadmaps into batches."""
            return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

        def process_batch(batch: List[Dict]) -> Dict:
            """Process a single batch of roadmaps with the LLM."""
            prompt = ChatCompletion(
                system=f"""
                    You are an assistant prioritizing roadmaps (future projects) using a weighted scoring framework based on multiple dimensions.

                    # Input
                    - Roadmaps: {json.dumps(batch, separators=(",", ":"))}
                    - Each roadmap includes:
                      - id: Unique identifier.
                      - title: Roadmap title.
                      - portfolio_id: Associated portfolio ID (if any).
                      - objectives: Strategic goals (if available).
                      - budget: Financial investment (if available).
                      - org_strategy_align: Alignment with corporate strategy (if available).
                      - roadmap_constraints: Constraints (e.g., cost, risk, resource).
                      - roadmap_key_results: KPIs and baseline values.
                      - team_data: Team requirements, estimated hours, and costs.
                      - effort_summary:
                            - total_hours: total estimated execution hours
                            - total_cost: total execution cost
                            - labour_roles: number of distinct labour roles required
                            - max_allocation: highest allocation required for any role
                      - Other fields as provided (e.g., revenue potential, technical complexity).

                    # Dimensions for Prioritization
                    Prioritize roadmaps based on the following dimensions, grouped into categories. Assign a score (1-10, 10 being best) for each dimension, using available data or reasonable assumptions for missing data. Apply weights to each dimension (assume equal weights across categories, e.g., 16.67% per category, or adjust based on typical industry priorities).

                    ## Strategic Alignment Dimensions
                    - Business Value Impact:
                      - Revenue generation potential (direct/indirect).
                      - Cost reduction opportunities.
                      - Market share impact.
                      - Customer experience enhancement.
                      - Competitive advantage creation.
                    - Strategic Fit:
                      - Alignment with corporate strategy and objectives.
                      - Support for digital transformation initiatives.
                      - Contribution to long-term vision.

                    ## Risk & Feasibility Dimensions
                    - Technical Risk Assessment:
                      - Technology maturity and proven track record.
                      - Complexity of implementation.
                      - Integration challenges with existing systems.
                      - Scalability and future-proofing considerations.
                      - Technical debt implications.
                    - Execution Risk:
                      - Team capability and skill availability.
                      - Resource requirements and constraints.
                      - Dependencies on external vendors/partners.
                      - Change management complexity.
                      - Historical project success rates.
                    - Effort Efficiency:
                        - Evaluate the execution effort relative to expected business value.
                        - Lower total_hours and total_cost indicate faster delivery and lower execution burden.
                        - Fewer labour_roles indicates lower coordination complexity.
                        - High max_allocation indicates heavy dependency on specific resources.
                        - Favor initiatives that deliver strong value with relatively lower effort (quick wins).
                        - Large-effort initiatives should score lower in this dimension unless strategic value is very high.

                    ## Resource & Timeline Dimensions
                    - Time Sensitivity:
                      - Urgency based on business drivers.
                      - Market timing considerations.
                      - Regulatory deadlines.
                      - Seasonal business impacts.
                      - Window of opportunity factors.

                    ## Impact & ROI Dimensions
                    - Financial Metrics:
                      - Net Present Value (NPV).
                      - Return on Investment (ROI).
                      - Payback period.
                      - Total Cost of Ownership (TCO).
                      - Break-even analysis.
                    - Stakeholder Impact:
                      - Customer satisfaction improvement.
                      - Employee productivity gains.
                      - Partner/supplier relationship enhancement.
                      - Operational efficiency improvements.

                    ## Organizational Readiness
                    - Operational Readiness:
                      - Infrastructure preparedness.
                      - Process maturity.
                      - Data quality and availability.
                      - Security and governance frameworks.

                    ## External Environment Factors
                    - Market Dynamics:
                      - Industry trends and disruption potential.
                      - Regulatory landscape changes.
                      - Competitive pressures.
                      - Technology evolution pace.

                    # Task
                    - For each roadmap:
                      - Assign a score (1-10) for each dimension based on available data or assumptions.
                      - Apply weights to each dimension (assume equal weights across categories, e.g., 16.67% per category).
                      - Calculate a total score (sum of weighted scores).
                      - Do NOT assign a priority; only provide scores and reasoning.
                      - Handle missing data by assigning neutral scores (e.g., 5/10) and noting assumptions in reasoning.
                      - Do not miss any roadmap provided.
                    - Provide a thought process explaining the overall approach to scoring.
                    IMPORTANT:
                        Effort efficiency should NOT override strategic importance.
                        If a roadmap has very high strategic alignment, regulatory urgency, or major business impact,
                        it may still receive a high total score even if execution effort is large.

                    # Output Format
                    ```json
                    {{
                        "thought_process_on_prioritizing_all": "<string>",
                        "prioritization_of_all_roadmap_items": [
                            {{
                                "id": "<string>",
                                "title": "<string>",
                                "total_score": <float>,
                                "dimension_scores": {{
                                    "b_v_i": <int>, // means- business_value_impact
                                    "s_f": <int>, // strategic_fit
                                    "t_r": <int>, // technical_risk
                                    "e_r": <int>, // execution_risk
                                    "t_s": <int>, // time_sensitivity
                                    "eff_eff": <int>, // effort_efficiency
                                    "fin_met": <int>, // financial_metrics
                                    "st_im": <int>, // stakeholder_impact
                                    "op_red": <int>, // operational_readiness
                                    "m_d": <int>, // market_dynamics
                                }},
                                "reasoning": ["string1", "string2", ...] // 3 short reasoning  points combining a few aspects of dimensions
                            }},
                            ...
                        ]
                    }}
                    ```
                    - thought_process_on_prioritizing_all: Explanation of the scoring approach.
                    - total_score: Weighted sum of dimension scores (0-100).
                    - dimension_scores: Score (1-10) for each dimension.
                    - reasoning: Three short explanation points combining dimension aspects.
                """,
                prev=[],
                user="It is non negotiable: you should prioritize all roadmap items, score all the roadmaps using the weighted scoring framework based on the provided dimensions."
            )

            try:
                
                debugLogger.info("started doing batch")
                response = self.llm.runV2(
                    prompt, self.model_opts, "agent::roadmap::prioritize", {"tenant_id": tenant_id, "user_id": user_id}
                )
                prioritized_batch = extract_json_after_llm(response)
                debugLogger.info("finished doing batch")
                
                return prioritized_batch
            except Exception as e:
                appLogger.error({
                    "event": f"Prioritization failed for batch",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                return {"error": str(e)}

        def rename_dimension_scores_keys(prioritized_roadmaps: Dict) -> Dict:
            """Rename abbreviated dimension_scores keys to full names."""
            key_mapping = {
                "b_v_i": "business_value_impact",
                "s_f": "strategic_fit",
                "t_r": "technical_risk",
                "e_r": "execution_risk",
                "t_s": "time_sensitivity",
                "fin_met": "financial_metrics",
                "st_im": "stakeholder_impact",
                "op_red": "operational_readiness",
                "m_d": "market_dynamics"
            }
            key_mapping["eff_eff"] = "effort_efficiency"
            updated_roadmaps = {
                "thought_process_on_prioritizing_all": prioritized_roadmaps.get("thought_process_on_prioritizing_all", ""),
                "prioritization_of_all_roadmap_items": []
            }
            for item in prioritized_roadmaps.get("prioritization_of_all_roadmap_items", []):
                new_dimension_scores = {
                    key_mapping.get(old_key, old_key): value
                    for old_key, value in item["dimension_scores"].items()
                }
                updated_item = {
                    "id": item["id"],
                    "title": item["title"],
                    "total_score": item["total_score"],
                    "dimension_scores": new_dimension_scores,
                    "reasoning": item["reasoning"]
                }
                if "priority" in item:
                    updated_item["priority"] = item["priority"]
                updated_roadmaps["prioritization_of_all_roadmap_items"].append(updated_item)
            return updated_roadmaps

        try:
            # Split roadmaps into batches
            print("Effort summary sample:", roadmaps[0].get("effort_summary"))
            batches = chunk_roadmaps(roadmaps, BATCH_SIZE)
            print("batches -- ", len(batches))
            debugLogger.info(f"Split roadmaps of length- {len(roadmaps)} into {len(batches)} batches of size {BATCH_SIZE}")

            # Process batches in parallel using ThreadPoolExecutor
            all_prioritized = []
            thought_process = ""
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                future_to_batch = {executor.submit(process_batch, batch): batch for batch in batches}
                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        batch_result = future.result()
                        if "error" not in batch_result:
                            all_prioritized.extend(batch_result["prioritization_of_all_roadmap_items"])
                            if batch_result["thought_process_on_prioritizing_all"]:
                                thought_process = batch_result["thought_process_on_prioritizing_all"]  # Use the first non-empty thought process
                            socketio.emit(
                                agent_name,
                                {"event": "batch_prioritized", "data": f"Processed batch of {len(batch)} roadmaps"},
                                room=client_id
                            )
                        else:
                            appLogger.warning(f"Batch processing failed: {batch_result['error']}")
                    except Exception as e:
                        appLogger.error({
                            "event": f"Batch processing failed",
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })

            if not all_prioritized:
                appLogger.warning("No roadmaps prioritized successfully")
                socketio.emit(
                    agent_name,
                    {"event": "error", "data": {"error": "No roadmaps prioritized successfully"}},
                    room=client_id
                )
                return [{"error": "No roadmaps prioritized successfully"}]

            # Sort by total_score, time_sensitivity, business_value_impact, and title for tiebreaking
            sorted_roadmaps = sorted(
                all_prioritized,
                key=lambda x: (
                    x["total_score"],
                    x["dimension_scores"].get("t_s", 5),
                    x["dimension_scores"].get("b_v_i", 5),
                    x["title"].lower()
                ),
                reverse=True
            )

            # Assign final priorities (1 = highest)
            for i, roadmap in enumerate(sorted_roadmaps, 1):
                roadmap["priority"] = i

            # Construct final output
            final_output = {
                "thought_process_on_prioritizing_all": thought_process or "Roadmaps were scored based on weighted dimensions (business value, strategic fit, risks, etc.) with equal category weights (16.67%). Ties were resolved using time sensitivity, business value impact, and alphabetical title order.",
                "prioritization_of_all_roadmap_items": sorted_roadmaps
            }

            # Rename dimension scores keys
            final_output = rename_dimension_scores_keys(final_output)

            # Emit final prioritized results
            socketio.emit(
                agent_name,
                {"event": "roadmap_prioritized", "data": final_output["prioritization_of_all_roadmap_items"]},
                room=client_id
            )
            debugLogger.info(f"Prioritized {len(sorted_roadmaps)} roadmaps")
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key="roadmap_prioritization",
                value=json.dumps(final_output),
                session_id=session_id
            )
            return final_output["prioritization_of_all_roadmap_items"]

        except Exception as e:
            appLogger.error({
                "event": f"Prioritization failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            socketio.emit(
                agent_name,
                {"event": "error", "data": {"error": str(e)}},
                room=client_id
            )
            return [{"error": str(e)}]


    def schedule_roadmaps(
        self,
        roadmaps: List[Dict],
        resource_data: List[Dict],
        tenant_id: int,
        user_id: int,
        session_id: str,
        socketio: Any,
        client_id: str,
        conversation=[],
        start_date='',
        end_date='',
        last_user_message=''
    ):
        """
        Schedule ALL roadmaps (not in batches) using resource-aware sequencing
        within the given start/end window.
        """

        agent_name = "roadmap_agent"

        # Create mutable copy
        # sorted_roadmaps = list(roadmaps)
        
        for r in roadmaps:
            priority = None
            raw = r.get("roadmap_portfolios") or r.get("portfolios")

            try:
                # Case 1 — raw is already a Python list
                if isinstance(raw, list):
                    if raw:
                        inner = raw[0]
                        # inner might be a dict OR a string
                        if isinstance(inner, dict):
                            priority = inner.get("roadmap_priority_in_portfolio")
                        elif isinstance(inner, str):
                            obj = json.loads(inner)
                            priority = obj.get("roadmap_priority_in_portfolio")

                # Case 2 — raw is a JSON string that we need to decode twice
                elif isinstance(raw, str):
                    list_level = json.loads(raw)          # gives ["{...}"]
                    if isinstance(list_level, list) and list_level:
                        inner = list_level[0]
                        obj = json.loads(inner)           # gives {...}
                        priority = obj.get("roadmap_priority_in_portfolio")

            except Exception as e:
                print("priority decode error:", e)
                priority = None

            r["roadmap_priority_in_portfolio"] = priority

        print("\n=== Extracted Priorities BEFORE Sorting ===")
        for r in roadmaps:
            print(f"{r.get('roadmap_title')}: {r.get('roadmap_priority_in_portfolio')}")
        print("===========================================\n")


        # sorted_roadmaps = sorted(
        #     roadmaps,
        #     key=lambda x: (
        #         x.get("roadmap_priority_in_portfolio", float("inf")) if x.get("roadmap_priority_in_portfolio") is not None else float("inf")
        #     )
        # )
        
        sorted_roadmaps = sorted(
            roadmaps,
            key=lambda x: (
                x.get("roadmap_priority_in_portfolio")
                if x.get("roadmap_priority_in_portfolio") is not None
                else float("inf"),

                x.get("roadmap_priority")
                if x.get("roadmap_priority") is not None
                else float("inf"),
            )
        )

                
        print("\n=== Sorted Roadmaps by Priority (ascending) ===")
        for r in sorted_roadmaps:
            print(f"ID={r.get('roadmap_id') or r.get('id')}, "
                f"Title={r.get('roadmap_title') or r.get('title')}, "
                f"Priority={r.get('roadmap_priority_in_portfolio')}")
        print("==============================================\n")

        # Compute inferred execution duration & remove biasing fields
        for r in sorted_roadmaps:
            r["duration_of_execution"] = compute_possible_effort_days(r)
            r.pop("start_date", None)
            r.pop("end_date", None)
            r.pop("roadmap_priority", None)

        sd = safe_parse_date(start_date)
        ed = safe_parse_date(end_date)

        sd_str = sd.strftime("%Y-%m-%d") if sd else ""
        ed_str = ed.strftime("%Y-%m-%d") if ed else ""
        total_days = max((ed - sd).days, 0) if sd and ed else None

        prompt = ChatCompletion(
            system=f"""
                You are an elite enterprise portfolio scheduler and execution planner.
                You act as a **Portfolio Planning Advisor**, helping the user finalize
                the most resource-feasible execution calendar inside the given window.

                ###################################################
                ## LIGHT SCHEDULING WINDOW (START-CONTROLLED)
                ###################################################

                • The scheduling window controls ONLY when a roadmap may START.
                • A roadmap MUST start on a date within the scheduling window
                • A roadmap MAY finish after the scheduling_window_end.
                • If capacity and dependencies allow a roadmap to start on any date within the window,
                the model MUST schedule it at the earliest feasible such date.
                • A roadmap must NOT be delayed or excluded solely to keep its completion within the window.


                - scheduling_window_start = {sd_str}
                - scheduling_window_end   = {ed_str}
                - total_available_days_for_scheduling = {total_days}
                - scheduling_run_count starts from 0 and keep adding 1 everytime this system runs
                
                
                - today = {sd_str}

                Definition:
                • "today" is the effective reference date for capacity interpretation.
                • All current_projects vs future_projects comparisons MUST use this value.
                • Treat all capacity timelines relative to scheduling_window_start unless explicitly stated otherwise.

                
                NOTE: The input list of roadmaps is already **sorted by `roadmap_priority_in_portfolio` and 'roadmap_priority' in ascending order** (lower numeric value means higher portfolio priority). You MUST respect this ordering when attempting placements: try to place higher-priority (lower number) roadmaps before lower-priority ones wherever feasibility permits. Do not reshuffle this order except when strict feasibility constraints (capacity or window) require delaying a higher-priority item.
                
                IMPORTANT NARRATIVE REQUIREMENT (NON-NEGOTIABLE):

                    The model MUST explicitly reference `roadmap_portfolio_priority`
                    when writing:

                        - The Executive Summary
                        - The section "What Was Prioritized — And Why"
                        - Explanations for any delayed or excluded high-priority roadmaps

                    If a roadmap has a high portfolio priority (lower numeric value)
                    and is delayed, sequenced later, placed in possible_with_tweaks[],
                    or excluded[], the explanation MUST clearly state:

                        - that it is high priority, AND
                        - the exact reason it could not be scheduled earlier
                        (dependency, skill constraint, or capacity limit)

                    Priority must be explained in **plain business language**.
                    Do NOT imply priority silently.
                    
                    When referencing priority, always mention at least ONE roadmap title
                    as an example (especially if delayed or excluded).



                You MUST NOT decide what is schedulable based on markdown wording. Compute the schedule using algorithmic feasibility only — then describe it in markdown.

                ###################################################
                ## STRICT JSON OUTPUT FORMAT
                ###################################################
                For every roadmap, you MUST populate "dependent_on_roadmaps" exactly as:
                - For all roadmap_dependencies where relation = "depends_on",
                add an object:
                {{
                    "roadmap_id": <related_roadmap_id>,
                    "roadmap_title": "<related_roadmap_title>"
                }}
                If no dependencies exist for that roadmap, return an empty list.
                Never infer dependencies — use ONLY the dependency data provided in roadmap_dependencies.

                Return ONLY:
                {{
                    "scheduling_window_start": "",
                    "scheduling_window_end": "",
                    "scheduling_run_count": "int",
                    "thought_model": "<FULL MARKDOWN REPORT AS SPECIFIED ABOVE in proper rich text format>",
                    "insights_markdown": "<FULL MARKDOWN REPORT AS SPECIFIED ABOVE in proper rich text format>",
                    "schedule": [
                        {{
                            "id": "<roadmap id>",
                            "title": "<roadmap title>",
                            "start_date": "YYYY-MM-DD",
                            "end_date": "YYYY-MM-DD",
                            "roadmap_portfolio_priority": "<int>",
                            "reasoning": "Short explanation of WHY it fits based on feasibility.",
                            "dependent_on_roadmaps": [
                                {{
                                    "roadmap_id": <>,
                                    "roadmap_title": "",
                                }},...
                            ],
                        }},...
                    ],
                    "planned_roadmaps_and_reason": "<FULL MARKDOWN REPORT AS SPECIFIED ABOVE in proper rich text format>",
                    "what_changed_and_why": "<FULL MARKDOWN REPORT AS SPECIFIED ABOVE in proper rich text format>",
                    "excluded": [
                        {{
                            "id": "<roadmap id>",
                            "title": "<roadmap title>",
                            "reason": "Clear resource- or window-based reason for exclusion",
                            "roadmap_portfolio_priority": "<int>",
                            "duration": "", // in days
                            "dependent_on_roadmaps": [
                                {{
                                    "roadmap_id": <>,
                                    "roadmap_title": "",
                                }},...
                            ]
                        }},...
                    ],
                    "possible_with_tweaks": [
                        {{
                            "id": "<roadmap id>",
                            "title": "<roadmap title>",
                            "roadmap_portfolio_priority": "<int>",
                            "reason": "nicely written with all reasons combined: Why it did NOT fit as-is + blocking roles + unlock conditions + tweak_effort_type",
                            "duration": "", // in days
                            "dependent_on_roadmaps": [
                                {{
                                    "roadmap_id": <>,
                                    "roadmap_title": "",
                                }},...
                            ]
                        }},...
                    ]
                }}

                ###################################################
                ## INPUT DATA
                ###################################################
                Roadmaps (ALL candidate demands):
                {json.dumps(sorted_roadmaps, separators=(",", ":"))}

                Resource Capacity Data:
                {json.dumps(resource_data, separators=(",", ":"))}
                
                ###################################################
                ## RESOURCE BASELINE — DO NOT INVENT ALLOCATIONS
                ###################################################
                You MUST NOT assume any ongoing or future allocation for any role unless it is explicitly listed in Resource Capacity Data.
                
                If current_projects or future_projects are present for a resource,
                those allocations are EXPLICIT and MUST be honored exactly as listed.

                If a role is not shown as allocated in the input, its utilization MUST be treated as 0% at the start of the window.
                You are not allowed to infer that analytics/data/engineering resources are already busy unless the input explicitly states so.

                ⚠ HARD CONSTRAINT ABOUT HIGH-PRESSURE ROLES
                You MUST NOT infer Azure Data Engineer, Data Scientist, Specialist Data Modelling, or any high-pressure role unless the roadmap explicitly lists that role in team_data, roadmap description, or resource_data.
                Generic technical words like "AI", "analytics", "data", "ML", "reporting", or "dashboard" are NOT explicit evidence of these roles.
                If the model infers one of these roles without explicit evidence, the schedule is INVALID and MUST be recomputed before responding.


                ROLE POOL CONSTRAINT (MANDATORY):

                    Each role represents a FINITE shared pool of people.

                    If Resource Capacity Data contains N resources with the same role,
                    the total concurrent allocation for that role MUST NOT exceed:

                        N × 100% × 0.85

                    Example:
                    - 1 Frontend Engineer → max concurrent = 85%
                    - 2 Frontend Engineers → max concurrent = 170%

                    The model MUST aggregate allocations ACROSS ALL roadmaps
                    using the SAME role name.
                    
                ###################################################
                ## RESOURCE TIMELINE INTERPRETATION (MANDATORY)
                ###################################################

                Resource Capacity Data may include:
                - current_projects[]: active allocations with start_date ≤ today ≤ end_date
                - future_projects[]: upcoming allocations with start_date > today

                MANDATORY INTERPRETATION RULES:

                1. current_projects
                - Each item represents an ACTIVE capacity reservation.
                - Its allocation MUST be treated as consuming capacity
                    on EVERY day from scheduling_window_start
                    UNTIL its end_date.
                - Even if the project started before the window,
                    its allocation still blocks capacity inside the window.

                2. future_projects
                - Each item represents a CONFIRMED future capacity reservation.
                - Its allocation MUST be treated as consuming capacity
                    starting from its start_date UNTIL its end_date.
                - Capacity BEFORE its start_date is unaffected by this project.

                3. No early release
                - You MUST NOT assume early completion, ramp-down,
                    partial allocation reduction, or early handover
                    unless explicitly shown in the data.
                - Allocation remains constant for the full [start_date, end_date] range.

                4. Capacity composition
                - When computing daily utilization for a role,
                    you MUST sum:
                    (a) allocations from current_projects,
                    (b) allocations from future_projects,
                    (c) allocations from already-scheduled roadmaps,
                    (d) allocations from the candidate roadmap being evaluated.

                5. Time-awareness is mandatory
                - A roadmap that cannot start at window start
                    MAY become feasible later when:
                    • a current_project ends, OR
                    • a future_project has not yet started.
                - The model MUST attempt placement at the earliest
                    such feasible date inside the window.
                    
                    
                ###################################################
                ## TIME-AWARE CAPACITY ANALYSIS (MANDATORY)
                ###################################################

                All skill and capacity analysis in this plan MUST be TIME-AWARE.

                The model MUST NOT treat capacity as static across the scheduling window.

                When analyzing roles, utilization, or risk:
                - You MUST consider how capacity CHANGES over time due to:
                    • current_projects ending,
                    • future_projects starting,
                    • scheduled roadmaps consuming capacity,
                    • dependencies delaying starts.

                If a role is constrained only during PART of the window:
                - You MUST explicitly state WHEN the constraint exists
                (early / mid / late window),
                - AND explain how that timing affected roadmap placement or deferral.

                Static, averaged, or point-in-time capacity interpretations are INVALID.
                
                
                ###################################################
                ## EXPLICIT CAPACITY CHANGE DATE ENUMERATION (MANDATORY)
                ###################################################

                Before attempting any scheduling decisions, the model MUST perform
                the following preprocessing step using ONLY the provided Resource Capacity Data:

                1) Enumerate ALL dates inside the scheduling window where role capacity MAY change.
                These dates MUST include, at minimum:
                • scheduling_window_start
                • For EVERY item in current_projects[]:
                    → (end_date + 1 day)
                • For EVERY item in future_projects[]:
                    → start_date

                2) Treat each of these dates as a DISTINCT candidate roadmap START date.

                3) The model MUST explicitly attempt scheduling on EACH candidate date
                in ascending chronological order.

                4) A roadmap MUST NOT be declared "unschedulable for the window"
                unless it has been evaluated on ALL such candidate dates.

                5) If a roadmap is infeasible on an earlier date but becomes feasible
                on a later candidate date, it MUST be scheduled on that later date.

                6) Failure to enumerate and evaluate these dates is INVALID and
                requires the schedule to be recomputed before responding.

                IMPORTANT CLARIFICATION:
                    • Dates MUST be derived from the input data — do NOT assume that
                    capacity conditions are uniform across the window.
                    • A role being blocked early in the window does NOT imply it is
                    blocked later unless explicitly shown by overlapping allocations.

                
                
                ###################################################
                ## MANDATORY CAPACITY-RELEASE RESCHEDULING LOGIC
                ###################################################

                The model MUST reason in discrete time steps across the scheduling window.

                Whenever ANY capacity-affecting event occurs, including:
                • a current_project reaching its end_date, OR
                • a future_project not yet started on a given date, OR
                • a previously scheduled roadmap completing,

                that date MUST be treated as a NEW candidate start point.

                At EACH such date, the model MUST:

                1) Recompute available capacity for all roles on that date.
                2) Re-attempt scheduling of ALL remaining unscheduled roadmaps.
                3) Attempt placement strictly in portfolio priority order.
                4) Immediately schedule any roadmap that becomes feasible on that date.

                IMPORTANT:
                • It is NOT sufficient to attempt scheduling only at the window start.
                • Skipping a feasible mid-window placement is INVALID.
                • If capacity becomes free on day X, and a roadmap can start on day X,
                it MUST be scheduled on day X (not deferred later).

                The model MUST continue this retry process until:
                • no remaining roadmap can be placed anywhere inside the window.



                ###################################################
                ## REQUIRED SCHEDULING MODEL (MANDATORY — FOLLOW IN EXACT ORDER)
                ###################################################
                
                    ###################################################
                    ## DEPENDENCY RULES (MANDATORY — CHECK BEFORE SCHEDULING)
                    ###################################################
                    Roadmaps may include dependency metadata under `roadmap_dependencies`.

                    Each dependency item includes:
                    - relation: "depends_on" or "required_by"
                    - dependency_type (e.g., Technical, Functional, Resource, Sequence, Risk, Compliance)
                    - dependency_reason
                    - related_roadmap_title

                    Dependency rules you MUST apply:
                    1. A roadmap with a `depends_on` relationship MUST NOT start until ALL of its prerequisite 
                    (related) roadmaps are fully scheduled AND finish before this roadmap's start_date.

                    2. A roadmap with unresolved dependencies MUST be delayed until all blocking dependencies 
                    finish OR it must be classified into excluded[] or possible_with_tweaks[].

                    3. A roadmap with `"required_by"` relations does NOT block its own scheduling, 
                    but its start must not violate dependency ordering for the related roadmap.

                    4. When evaluating feasibility, treat unsatisfied dependencies as a HARD BLOCKER, 
                    equivalent to a resource overload.

                    5. Dependency violations MUST be clearly mentioned in the reasoning, in this format:
                    "Dependency Block: <roadmap A> depends on <roadmap B> which is not yet scheduled 
                        or finishes on <date>, so A cannot start before <next feasible date>."

                    6. When conflicting between dependency order and portfolio priority:
                    - Dependency order takes precedence.
                    - A higher-priority roadmap MUST wait for a lower-priority prerequisite if necessary.

                    7. If a dependency chain makes the roadmap impossible within the window,
                    place it in excluded[] with `reason = "Unresolved dependency chain"`.

                    8. In possible_with_tweaks[], suggest dependency-adjusted solutions:
                    - delayed_start
                    - window_extension
                    - phase_split (if dependency only blocks part of the work)


                The goal is to construct a focused, high-confidence execution plan,
                even if some feasible roadmaps are intentionally deferred
                to protect delivery quality and leadership attention.

                GLOBAL OPTIMIZATION RULE (CRITICAL — READ CAREFULLY):

                Your objective is to maximize the number of HIGH-PRIORITY roadmaps
                that can be STARTED within resource capacity constraints

                while respecting dependency constraints and full-duration capacity constraints
                (even if execution extends beyond the window).

                If multiple valid scheduling options exist, prefer:
                • earlier feasible starts, and
                • higher priority roadmaps.

                A roadmap MUST NOT be rejected merely because it cannot start at window open — you must consider placing it later in the window.
                You MUST always attempt to start remaining roadmaps at the earliest
                feasible date within the scheduling window when required roles
                become available due to prior roadmap completions.

                
                For each roadmap candidate start date, the model MUST compute
                daily allocation for ALL required roles across:

                - current_projects active on that day,
                - future_projects active on that day,
                - ALL previously scheduled roadmaps,
                - the candidate roadmap itself.
                
                Parallel execution MUST only happen when full-duration daily allocation is safe.
                
                A roadmap MUST NOT assume reduced early load (e.g., "analytics ramps up later"). All required-role allocations apply from day 1 unless explicitly stated otherwise in team_data — no soft/hypothetical ramp assumptions are allowed.
                
                For every roadmap placed in the schedule, the reasoning MUST include explicit capacity math in this format:
                "Azure Data Engineer: 40% (current) + 50% (new) = 90% (>85%) → cannot start in parallel → must be delayed until <date>"
                OR (for allowed parallel case):
                "Azure Data Engineer: 40% (current) + 40% (new) = 80% (<=85%) → parallel start allowed"
                If the reasoning does NOT contain explicit utilization math for ALL high-pressure roles,
                the schedule is INVALID and MUST be recomputed before responding.
                Your scheduling logic MUST follow these steps in this exact order:

                1) ROLE DEMAND EXTRACTION
                    If explicit team_data is missing or incomplete:
                        • You MUST infer the minimum viable role set required to execute the roadmap.
                        • Choose roles conservatively, NOT expansively (include only essential roles).
                        • The inferred role set MUST be a subset of roles present in Resource Capacity Data.
                        • You MUST NOT exclude an item due to “uncertain role inference”.
                        • When in doubt, choose the smallest reasonable role set instead of excluding the roadmap.
                For each roadmap: extract roles required, effort, and duration_of_execution.
                Team member start_date and end_date DO NOT define roadmap scheduling constraints. They represent only assignment history or context.

                The roadmap MUST START within the scheduling window.
                Execution may extend beyond the window as long as full-duration
                capacity remains safe.
                Team member dates must never force or block scheduling.

                2) ROLE-SUPPLY & PRESSURE BASELINE
                For each role: evaluate availability and determine whether it is low-pressure or high-pressure across the window.

                3) HARD FEASIBILITY TEST
                A roadmap is feasible ONLY IF there exists at least one start date
                    within the scheduling window such that:
                    • all dependencies are resolved by that start date, AND
                    • every required role remains ≤ 85% utilization for the entire duration
                    starting from that date (even if execution extends beyond the window).

                If even one role violates capacity → mark as infeasible and list the blocking role(s).

                INTERPRETATION OF "allocation" FIELD (MANDATORY):
                - The value of "allocation" in team_data represents the percentage of that resource’s total capacity reserved for this roadmap (e.g., allocation=50 → 50% FTE, allocation=20 → 20% FTE, allocation=100 → full FTE).
                - This allocation MUST be applied DAILY across the roadmap duration when computing utilization.
                - If multiple roadmaps use the same role during overlapping days, their allocations MUST be summed for each day and compared with the 85% threshold.
                - If the daily sum exceeds 85% for any required role on any day → the roadmap causing the breach CANNOT run in parallel and MUST be delayed until the next day where capacity is free.
                A role with allocation = 100 must not be shared in parallel with any other roadmap requiring the same role.

                INTERPRETATION OF INFERRED ALLOCATION (ONLY IF MISSING):
                - If a required role has no explicit "allocation" value, you MUST infer a conservative default between 20–40% based on similar roadmaps.
                - Inference MUST always be conservative and MUST prioritize feasibility over precision.
                - Lack of explicit allocation alone must NOT cause exclusion.

                NON-LABOUR TEAM MEMBERS (CRITICAL):
                - Roles marked "labour" consume resource capacity and are subject to allocation rules.
                - Roles marked "non labour" (e.g., licenses, subscriptions, tools, temporary software services) MUST NOT block scheduling or consume utilization capacity.


                CAPACITY SUMMATION RULE (STRICT — MUST FOLLOW):
                For every role, utilization MUST be computed DAILY across the window.
                For any day, if the sum of allocations from overlapping roadmaps exceeds 85%, the roadmap causing the breach MUST NOT run in parallel and MUST be delayed until the required role capacity becomes free.
                
                A roadmap cannot run in parallel just because required roles are available at window start — it may only run in parallel if its required allocations remain below 85% on EVERY day of its duration.


                CAPACITY STATEFULNESS RULE (NON-NEGOTIABLE):

                    Capacity is cumulative and stateful.

                    When a roadmap is scheduled, its role allocations MUST be treated as fully
                    occupied for its entire duration and MUST be subtracted from available
                    capacity when evaluating all subsequent roadmaps.

                    All feasibility checks for later roadmaps MUST include the allocations
                    of previously scheduled roadmaps on overlapping days.
                    

                DURATION RULE:
                A roadmap MUST NOT be excluded just because its duration is long (e.g., 60–90 days).
                Duration alone is NOT a blocking reason if resource utilization remains ≤85% for all roles.
                Clarification:
                    - A roadmap must NOT be excluded solely because its execution
                    extends beyond the scheduling window, as long as it can START
                    within the window with safe full-duration capacity.



                4) FEASIBLE SET PRIORITIZATION
                Among feasible roadmaps, ordering for scheduling is:
                (a) higher roadmap_priority (lower rank = higher priority),
                (b) fewer high-pressure roles,
                (c) shortest duration_of_execution as the final tie-breaker.
                ⚠ Priority influences **order of placement**, NOT feasibility.
                High-priority roadmaps MUST be scheduled before lower-priority roadmaps as long as they pass feasibility. 

                After all feasible high-priority roadmaps are placed, remaining capacity should be used judiciously to START additional roadmaps
                    only if doing so does not materially reduce delivery confidence,
                    execution focus, or portfolio stability.


                
                IMPORTANT: `roadmap_priority` is numeric and lower numbers indicate higher portfolio priority. The model MUST attempt placement in ascending numeric order and must only deviate when strict feasibility forces a delay or exclusion. When two roadmaps are equally feasible for the same earliest start date, prefer the roadmap with the lower `roadmap_portfolio_priority` value (i.e., higher priority).
                When generating Markdown reasoning, briefly explain how priority affected scheduling decisions (e.g., why higher-priority items were attempted first or why a high-priority item was excluded and more...).

                5) CALENDAR PLACEMENT RULES (MOST IMPORTANT)
                • Roadmaps with no fixed start constraint must be allowed to begin at scheduling_window_start.
                • Place each roadmap **as early as resource availability allows**.
                • Use **parallel execution** whenever two roadmaps do not compete for the same high-pressure roles.
                • Delay a roadmap only when a specific required role is unavailable — never for “lower priority”.
                • Continue scheduling until **no remaining roadmap can pass the feasibility test**. Stopping early is not permitted.

                • If a roadmap cannot start at the scheduling_window_start due to role conflict, you MUST attempt to place it immediately after the earliest finishing roadmap that frees enough capacity — even if this results in sequential scheduling rather than parallel execution.
                • The roadmaps are already provided in sorted portfolio priority order. The model MUST honor this order whenever two roadmaps are equally feasible.
                • If two roadmaps have the same earliest feasible start date and pass feasibility with equal resource safety, the model MUST schedule the one that appears earlier in the input list (i.e., preserve original ordering) instead of reshuffling.

                • A roadmap must NOT be excluded unless it fails ALL three placement attempts:
                (1) running in parallel at the start of the window,
                (2) starting later during the window after another roadmap finishes,
                (3) starting after a high-pressure role becomes free.
                
                • You MUST continuously evaluate remaining roadmaps and start them
                    at the earliest feasible date within the scheduling window when
                    dependencies are resolved and capacity becomes available.

                If two roadmaps begin on the same date, the model MUST verify full-duration daily capacity BEFORE accepting parallel execution. If capacity fails for even one day, the model MUST push the later roadmap to the earliest feasible future date instead of stacking at the same start.


                6) EXCLUSION
                A roadmap must NOT be excluded because shorter roadmaps produce better throughput.
                A roadmap must NOT be excluded for business reasons, priority changes, maturity, or stale milestones.

                A roadmap can be placed in excluded[] ONLY if it fails ALL 3 feasibility-based placement attempts:
                (1) running in parallel at the start of the window,
                (2) starting later during the window after another roadmap finishes,
                (3) starting after a high-pressure role becomes free.

                If the roadmap successfully fits under ANY of these 3 conditions → it is NOT excluded.

                Exclusions must always state **the exact blocking role(s)** and/or
                **exact capacity mathematics that prevented placement**.
                

                ###################################################
                ## CATEGORY FOR ROADMAPS THAT ARE DOABLE WITH SMALL ADJUSTMENTS
                ###################################################
                Before classifying a roadmap into excluded[], evaluate whether it fits the window with *realistic minor adjustments*.

                A roadmap must be placed in possible_with_tweaks — NOT excluded — if ALL of these hold:
                • It fails the 3 scheduling attempts (parallel start, delayed start, free-capacity start),
                • BUT it is not fundamentally impossible,
                • AND a realistic business tweak can unlock feasibility.

                Valid tweak types (allowed):
                • delayed_start → roadmap becomes feasible if started after a specific role frees up,
                • capacity_increase → feasibility with ≤ +20% additional allocation for 1–2 roles only (NOT across multiple roles),
                • phase_split → Phase 1 fits inside the window (remaining scope outside window),
                • staggered_onboarding → roadmap can begin now with light roles; heavy roles join later,
                • window_extension → extension of ≤ 30 days makes full completion feasible.

                Invalid tweaks (roadmap must stay excluded if these are required):
                • duration exceeds window by > 45 days,
                • high-pressure conflict spans > 80% of the window,
                • requires adding multiple resources to multiple roles,
                • requires cutting > 30% of scope.

                JSON format for each item in possible_with_tweaks:
                {{
                    "id": "<roadmap id>",
                    "title": "<roadmap title>",
                    "reason": "nicely written with all reasons combined: Why it did NOT fit as-is + blocking roles + unlock conditions + tweak_effort_type",
                    "duration": "", // in days
                }}

                Roadmaps MUST appear in exactly ONE of:
                • schedule[]
                • possible_with_tweaks[]
                • excluded[]
                
                ###################################################
                ## HARD FREEZE RULE (NON-NEGOTIABLE)
                ###################################################

                Once a roadmap ID is added to "schedule[]",
                that roadmap ID is PERMANENTLY LOCKED.

                A locked roadmap:
                - MUST NOT appear in excluded[]
                - MUST NOT appear in possible_with_tweaks[]
                - MUST NOT be re-evaluated, reconsidered, or reclassified later

                excluded[] and possible_with_tweaks[] MUST ONLY be populated
                from the remaining UNSCHEDULED roadmaps.


                ###################################################
                ## SET SUBTRACTION RULE (MANDATORY)
                ###################################################

                Before populating excluded[] or possible_with_tweaks[],
                the model MUST conceptually compute:

                remaining_roadmaps =
                ALL_input_roadmaps
                MINUS schedule[]
                MINUS possible_with_tweaks[]

                ONLY remaining_roadmaps may appear in excluded[].

                If a roadmap ID exists in schedule[],
                it MUST be ignored for all exclusion or downgrade decisions.


                ###################################################
                ## USER SCENARIO INPUT
                ###################################################
                Simulate based on:
                "{last_user_message}"

                ###################################################
                ## MARKDOWN THOUGHT MODEL REPORT (planning_thought_model)
                ###################################################
                ## 🧠 Planning Thought Model (How the schedule was derived)
                - 6–10 list items summarizing reasoning following the required scheduling model.
                - DO NOT describe JSON — this is human-facing reasoning.
                

                ###################################################
                ## MARKDOWN PLANNING REPORT (insights_markdown)
                ###################################################
                You MUST output **one structured Markdown report** a PMO leader can read.
                It MUST contain ALL 6 sections below in this EXACT order:

                # 🧭 Portfolio Planning Report for {sd_str} → {ed_str}
                
                
                ## Executive Summary

                Write a concise, leadership-grade summary in **5–7 short sentences** that answers:

                - How many total roadmaps were evaluated
                - How many are scheduled, blocked, and conditionally possible
                - What percentage of the window capacity is consumed
                - How many roles and total resources are involved
                - What is the single biggest constraint (skill or dependency)
                • What this plan optimizes for (e.g., maximum initiatives safely started)


                MANDATORY RULES:
                - Use numbers wherever possible
                - No technical jargon
                - No tables
                - No roadmap-level detail yet
                - This must be understandable in under 30 seconds
                
                ADDITIONAL MANDATORY REQUIREMENT:

                The Executive Summary MUST translate scheduling results into business impact by explicitly stating:
                - What leadership gains by executing the scheduled roadmaps now
                - What business outcomes are deferred by not scheduling the remaining roadmaps
                - Why this is a deliberate portfolio decision, not a limitation of the system

                If the summary only describes counts, durations, or feasibility without business consequence,
                it is INVALID and MUST be rewritten.

                                
                
                ## 1️⃣ What Was Prioritized — And Why
                Summarize portfolio intent clearly using numbered bullets:

                - Highlight the top 3–5 portfolio priorities and why they matter
                - Call out how many high-priority vs low-priority roadmaps were scheduled
                - Explicitly state if any high-priority roadmap was delayed or excluded — and why
                - Mention how priority influenced sequencing (not feasibility)

                MANDATORY:
                - Use plain business language
                - Mention "priority", "importance", or "impact" explicitly
                - Use numbers (counts, percentages) wherever possible
                
                
                ADDITIONAL RULE (CRITICAL):

                Each numbered bullet MUST explicitly answer at least ONE of:
                - What business risk was reduced by this prioritization
                - What delivery certainty was gained
                - What leadership trade-off was consciously made

                Bullets that only restate scheduling logic (e.g., "fits the window", "ordered by priority")
                WITHOUT business implication are INVALID.



                ## 2️⃣ Resource Availability Summary
                    - 4–8 list items formatted EXACTLY as:
                "<role>: <availability/utilization pattern> (<readiness/risk commentary>)"
                    - Do NOT mention roadmap titles here.

                ## 3️⃣ Skills & Capacity Snapshot (Decision View)

                    First, write 3–5 bullets explaining:
                    - Total number of distinct roles involved
                    - Number of high-pressure (scarce) skills
                    - Peak utilization observed (of the utilized roles)
                    - Whether capacity risk is concentrated or distributed

                    Then include EXACTLY TWO TABLES. 
                    Also explain in simple english
                    what each column in these table exactly mean and what the data represents.
                    
                    This assesment is very important to do correctly

                    ### Table A: Skill Overview
                    | Skill | Resource Count | Peak Utilization | Risk Level | Short Note (short explanation) |
                    

                    ### Table B: Roadmaps Impacted by Skill Constraints
                    | Roadmap Title | Priority | Blocking Skill | Dependency or Capacity Issue |
                    
                    
                IMPORTANT INTERPRETATION RULES FOR THIS SECTION (MANDATORY):

                - All utilization, risk, and availability statements MUST be time-aware.
                - "Peak Utilization" MUST mean the HIGHEST daily utilization observed
                at ANY point during the window or execution horizon — not an average.
                - Risk Level MUST reflect BOTH:
                    • severity (how high utilization goes),
                    • duration (how long the constraint persists).

                If capacity pressure is temporary:
                - You MUST state what causes relief
                (e.g., project completion, delayed dependency, window progression).

                Vague labels like "high utilization" without timing context are INVALID.


                ## 4️⃣ Unschedulable Demands & Reasons
                When stating reasons for unschedulable demands:
                - Frame the reason as a business constraint (e.g., "cannot be fully delivered within the current window")
                - Avoid technical phrasing like "duration exceeds window" unless followed by business impact.

                Markdown table with EXACT columns:

                | Roadmap Title | Reason | Blocking Roles |
                |--------------|--------|----------------|

                ## 5️⃣ Risks, Conflicts & Recommendations
                 - 4–10 bullets identifying bottlenecks, overload risks, sequencing conflicts, or slip impacts.

                ## 6️⃣ Opportunities & Next-Best Scheduling Options
                 - 4–8 bullets suggesting:
                    – which excluded items should be considered next,
                    – what adding capacity would unlock,
                    – whether splitting phases could make long roadmaps feasible,
                    – whether extension of the window unlocks more.
                    
                    
                ## 7️⃣ Leadership Decisions Enabled by This Plan

                - 3–5 bullets clearly stating what decisions leadership can now make
                (e.g., approve deferral, extend window, phase large initiatives, add capacity).
                - Each bullet must be action-oriented and decision-focused.
                - Do NOT restate analysis.


            ###################################################
            ## MARKDOWN PLANNED ROADMAPS AND REASON REPORT (planned_roadmaps_and_reason)
            ###################################################
                ## Planned Demands & Why They Were Scheduled

                PURPOSE:
                This section explains *why groups of roadmaps* were scheduled, not to restate every item.

                RULES (MANDATORY):
                - Use **4–7 bullets maximum**, regardless of how many roadmaps are scheduled.
                - Each bullet MUST represent a **logical cluster** of 2–5 roadmaps with similar:
                    • business outcome, OR
                    • risk mitigation goal, OR
                    • strategic intent.
                - Each bullet MUST:
                    • clearly name the shared business outcome,
                    • clearly state the risk avoided by acting now,
                    • list the roadmap titles it covers in parentheses.
                - Do NOT create standalone bullets for roadmaps that share the same rationale.
                - Only create a standalone bullet if a roadmap has a **unique or exceptional reason**.

                STYLE RULES:
                - Do NOT restate start/end dates or priority.
                - Do NOT repeat the same benefit wording across bullets.
                - Write this as a **leadership synthesis**, not a backlog list.
                - If more than 7 bullets are produced, the section is INVALID and MUST be rewritten.


                ###################################################
                ## MARKDOWN CHANGE REPORT (what_changed_and_why) (only to be run when scheduling_run_count > 0)
                ###################################################
                You MUST output this as a **separate markdown report** inside the JSON field "what_changed_and_why".

                ### 🔄 What Changed and Why (Scheduling Delta Report)
                Rules:
                - If scheduling_run_count == 0 → write:
                "This is the first scheduling run. No previous schedule exists to compare against."
                - If scheduling_run_count > 0:
                • Provide 4–10 markdown bullet points.
                • Compare with previous schedule based on the latest conversation context and last_user_message.
                • Identify which roadmaps changed category:
                    – scheduled → excluded
                    – scheduled → possible_with_tweaks
                    – excluded → scheduled
                    – dates changed
                    – priority/order changed
                    – duration changed
                    – resource conflict reason changed
                • For each change, explain **why it happened** (capacity pressure / high-demand roles / allocation overload / shorter roadmap allowed scheduling / priority shift / dependency shift / user intent change).
                • ALWAYS mention roadmap titles when listing changes.
                • Use direct business language, no technical jargon.

                ⚠ DO NOT mix this section inside insights_markdown or any other field.
                ⚠ DO NOT output anything except markdown text inside what_changed_and_why.


                ###################################################
                ## RULES
                ###################################################
                • Roadmaps MUST appear in ONLY ONE of: schedule / excluded / possible_with_tweaks.
                • All eligible roadmaps MUST be scheduled until resource limits prevent further placements.
                • Do NOT produce any markdown outside insights_markdown.
                • NEVER leak chain-of-thought outside the **Planning Thought Model** section.
                • If none can be scheduled → schedule = [] and all others go to excluded[], and possible_with_tweaks may be populated if tweaks could enable scheduling.
                • possible_with_tweaks MUST be evaluated before excluded[], and excluded[] must only include roadmaps that remain fundamentally infeasible even after tweak evaluation.
                 If the JSON is incomplete or contains more items in schedule[] than capacity allows, the model MUST recompute the plan instead of returning partial or inconsistent output.
                 
                 
                LANGUAGE RULE (MANDATORY):
                    - Avoid technical planner language (e.g., utilization summation, feasibility-based)
                    - Prefer executive phrasing (e.g., skill availability, delivery risk, waiting on)
                    - If a sentence would not be spoken in a leadership meeting, rewrite it

                ⚠ FINAL VALIDATION RULE (NON-NEGOTIABLE)
                Before returning JSON, the model MUST run a self-audit:

                If ANY of the following are true, the schedule is INVALID and MUST be recomputed before responding:
                • Two or more roadmaps share a start date without explicit capacity math proving ≤85% utilization for all shared roles,
                • Any scheduled roadmap contains a required role that is NOT present in Resource Capacity Data,
                • Any roadmap is excluded without clear feasibility-based reason (capacity / window mismatch / obsolete or misaligned business timing)
                • Any roadmap that fits inside the window and passes feasibility is not included in schedule[].
                • If a roadmap ID appears in more than one output array,
                    the model MUST keep it in schedule[] and
                    REMOVE it from excluded[] and possible_with_tweaks[].
                    
                    
                ⚠ CRITICAL CAPACITY SANITY CHECK (NON-NEGOTIABLE)

                    Before returning JSON, the model MUST verify the following invariant:

                    IF Resource Capacity Data contains ANY current_projects or future_projects
                    whose allocation overlaps with the scheduling_window_start date,

                    THEN it is INVALID for ALL scheduled roadmaps to have
                    start_date == scheduling_window_start.

                    At least ONE of the following MUST be true:
                    • at least one roadmap starts AFTER scheduling_window_start, OR
                    • at least one roadmap is delayed due to a specific blocking role, OR
                    • at least one roadmap is placed in possible_with_tweaks[] or excluded[] due to capacity timing.

                    If this invariant is violated:
                    • the schedule is INVALID,
                    • the model MUST recompute the schedule,
                    • and MUST explicitly reference which resource caused the delay.


            """,
            prev=[],
            user=f"""
                Use conversation context only to refine intent.
                Conversation: {conversation}
                Last user query: {last_user_message}
                Return ONLY JSON strictly matching the schema.
                Do NOT add, remove, rename, or reorder JSON keys.
                Do NOT include comments, explanations, narration, reasoning, or markdown outside JSON field values.
                
                It's very important for you see go by priority order of roadmaps and find the appropriate time for start
                as per the resource availability. and folow all the instruction provided above.
            """
        )


        try:
            socketio.emit(
                agent_name,
                {"event": "timeline", "data": {"text": "Scheduling", "is_completed": False}},
                room=client_id,
            )

            response = self.llm.runV2(
                prompt,
                self.model_opts,
                "agent::roadmap::schedule_full",
                {"tenant_id": tenant_id, "user_id": user_id},
            )

            print(" -- response --- batch -- ", response)
            schedule_result = extract_json_after_llm(response)

            socketio.emit(agent_name, {"event": "roadmap_scheduled", "data": schedule_result}, room=client_id)
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key="roadmap_agent_conv",
                value=json.dumps(schedule_result),
                session_id=session_id
            )
            socketio.emit(agent_name, {"event": "roadmap_schedule_session_id", "data": session_id}, room=client_id)
            return schedule_result

        except Exception as e:
            socketio.emit(agent_name, {"event": "error", "data": {"error": str(e)}}, room=client_id)
            return {"error": str(e)}


    def fetch_plan_llm(self, user_message, conversation, context):
        prompt = ChatCompletion(
            system=f"""
            You are a Fetch Planner for the Roadmap Agent.
            Your ONLY responsibility is to determine what ROADMAP data and RESOURCE data should be fetched from the database based on the user's request.

            You must decide:
            - which attributes to select (projection_attrs) 
                -> mandatory from roadmap data: id, title, description, objective, start_date, end_date, roadmap_priority, current_state, dependencies, team_data, portfolios
                -> mandatory from resource data: id, first_name, role, primary_skill, current_allocation, current_projects, future_projects
            - which filters to apply carefully
            - nothing else (NO prioritizing, NO scheduling)

            ### Available Roadmap fields:
            {RoadmapsDaoV2.ATTRIBUTE_MAP}

            ### Available Resource fields:
            {TenantDaoV2.ATTRIBUTE_MAP}
            
            
            ####### MAIN CONTEXT #######
            {context}

            ### Base rules
            - If action is "schedule" → ALWAYS include roadmap staffing info (important fields like team, title, id, dependenies,  start and end dates , portfolio, constraint etc) + resource allocation info.
            - If action is "insights" → choose attributes based on what the user is investigating.
            - Default roadmap state for scheduling = Approved.
            - portfolio filter MUST be added if it is in conversation or user request.
            - If user mentions required roles/skills → apply corresponding resource filter.

            ### Output format (strict JSON)
            {{
                "roadmaps": {{
                    "projection_attrs": [],
                    "portfolio_ids": [],
                    "roadmap_ids": [],
                    "state_filter": [],   // ALWAYS return array of roadmap states e.g. ["Approved"] or ["Approved", "Execution"]
                    "order_clause": ""
                }},
                "resources": {{
                    "projection_attrs": [],
                    "portfolio_ids": [],
                    "role": null,
                    "skill_keyword": null,
                    "min_allocation": null,
                    "max_allocation": null
                }}
                "thought_process": "", // understand carefully keeping coinversation in mind and user latest message
            }}

            DO NOT include scheduling logic or prioritization logic.
            DO NOT hallucinate new fields.
            Output only clean JSON matching the format exactly.
            - state_filter MUST ALWAYS be an array of state names, not SQL.
            - Allowed state values: Intake, Approved, Execution, Archived, Elaboration, Solutioning, Prioritize, Hold, Rejected, Cancelled, Draft.

            """,
            prev=[],
            user=f"User message: {user_message}\nConversation: {conversation}"
        )
        result = self.llm.run(prompt, self.model_opts, "agent::fetch_plan", {})
        return extract_json_after_llm(result)


    def data_fetch_new(self, last_user_message,conversation, context, tenant_id ):
        # Step A — call fetch planner LLM
        fetch_plan = self.fetch_plan_llm(last_user_message, conversation=conversation, context=context)
        print("\n================ FETCH PLAN ================")
        print(json.dumps(fetch_plan, indent=2))
        print("============================================\n")
        
        state_list = fetch_plan["roadmaps"].get("state_filter") or []
        state_map = {
            "Intake": 0,
            "Approved": 1,
            "Execution": 2,
            "Archived": 3,
            "Elaboration": 4,
            "Solutioning": 5,
            "Prioritize": 6,
            "Hold": 99,
            "Rejected": 100,
            "Cancelled": 999,
            "Draft": 200
        }

        state_filter = None
        if isinstance(state_list, list) and state_list:
            numeric_states = [state_map[s] for s in state_list if s in state_map]
            if len(numeric_states) == 1:
                state_filter = f"rr.current_state = {numeric_states[0]}"
            elif len(numeric_states) > 1:
                state_filter = f"rr.current_state IN ({', '.join(map(str, numeric_states))})"


        
        # Step B — extract roadmap fetch plan
        rplan = fetch_plan.get("roadmaps", {})
        roadmap_projection = rplan.get("projection_attrs", []) or ["id", "title", "roadmap_priority", "team_data", "portfolios"]
        # roadmap_state_filter = rplan.get("state_filter") or "rr.current_state = 1"
        roadmap_portfolios = rplan.get("portfolio_ids") or []
        roadmap_ids = rplan.get("roadmap_ids") or []
        roadmap_order = rplan.get("order_clause") or "ORDER BY rr.start_date ASC"

        # Fetch roadmaps using DAO
        roadmaps = RoadmapsDaoV2.fetchRoadmapsDataWithProjectionAttrs(
            tenant_id=tenant_id,
            projection_attrs=roadmap_projection,
            portfolio_ids=roadmap_portfolios,
            roadmap_ids=roadmap_ids,
            state_filter=state_filter,
            order_clause=roadmap_order
        )

        # Step C — extract resource fetch plan
        resplan = fetch_plan.get("resources", {})
        resource_projection = resplan.get("projection_attrs", []) or ["id", "first_name", "last_name", "role", "primary_skill", "current_allocation", "all_roadmaps"]
        resource_portfolios = resplan.get("portfolio_ids") or roadmap_portfolios
        resource_role = resplan.get("role")
        resource_skill = resplan.get("skill_keyword")
        res_min_alloc = resplan.get("min_allocation")
        res_max_alloc = resplan.get("max_allocation")

        # Fetch resources using DAO
        resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
            tenant_id=tenant_id,
            projection_attrs=resource_projection,
            portfolio_ids=resource_portfolios,
            role=resource_role,
            skill_keyword=resource_skill,
            min_allocation=res_min_alloc,
            max_allocation=res_max_alloc
        )
        
        print(f"Fetched {len(roadmaps)} roadmap items from DB for scheduling")
        print(f"Fetched {len(resource_data)} resources for scheduling")
        
        return {
            "resource_data": resource_data,
            "roadmaps":roadmaps
        }
            

    def process_roadmaps(
        self,
        tenant_id: int,
        user_id: int,
        last_user_message: str,
        portfolio_ids: List[int],
        action: str,
        socketio: Any,
        client_id: str,
        session_id: str,
        context: str,
        conversation = [],
        start_date='',
        end_date='',
        roadmap_states=[]
    ) -> str:
        """Process roadmap action (prioritize or schedule) after user selections."""
        debugLogger.info(f"process_roadmaps: {action}")
        if not action:
            yield """Do you want to prioritize or schedule roadmaps?
```json
{
    "cta_buttons": [
        {"label": "Prioritize Roadmaps", "action": "prioritize"},
        {"label": "Schedule Roadmaps", "action": "schedule"}
    ]
}

```
"""
            debugLogger.info("Prompting user for action selection")
            return


        debugLogger.info(f"process_roadmaps portfolio_ids: {portfolio_ids} {action}")
        
        # Step 2: Prompt for portfolio selection if none provided
        if not portfolio_ids and action in ["prioritize", "schedule"]:
            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            portfolio_id_title = [{"id": p["id"], "title": p["title"], "label": p["title"], "preprend": "Selected portfolio: "} for p in portfolios]
            portfolio_id_title.insert(0, {"id": "all_portfolios", "title": "All Portfolios", "label": "All Portfolios", "preprend": "Selected portfolio: "})
            
            options = [p["title"] for p in portfolios]
            options.insert(0, "All Portfolios")
            yield f"""Great — let’s narrow things down. Which portfolio are we diving into?.

```json
{{
    "cta_select": {{
        "label": "Select Portfolio",
        "options": {json.dumps(options, indent=8)}
    }}
}}
``` 
"""
            return
    
    
        # Step 3: Ask for dates if scheduling has no timeframe
        if action == "schedule" and not (start_date and end_date):
            # calculate 1st day of next month
            today = datetime.today()
            first_next_month = (today.replace(day=1) + relativedelta(months=1)).date()

            # end date = +3 months from start
            three_months_later = (first_next_month + relativedelta(months=3))

            default_start = first_next_month.strftime("%Y-%m-%d")
            default_end = three_months_later.strftime("%Y-%m-%d")
            yield f"""Let’s set the horizon for your plan. How long are we planning for?
            
Select start and end dates

```json
{{
    "date_signals": [
        "start_date",
        "end_date"
    ],
    "label": "Select Date",
    "default_values": {{
        "start_date": "{default_start}",
        "end_date": "{default_end}"
    }}
}}
```
"""
            debugLogger.info("Prompting user for date selection")
            return
        
        
        if action == "schedule" and not roadmap_states:
            yield f"""Great. Tell me which demand stages I should plan for.

Select one or more:

```json
{{
"cta_buttons_multi": [
    {{"label": "Approved", "value": "Approved"}},
    {{"label": "Solutioning", "value": "Solutioning"}},
    {{"label": "Intake", "value": "Intake"}},
]
}}
```
"""
            return

        # debugLogger.info(f"process_roadmaps portfolio_ids 2: {portfolio_ids}")
        
        # Step 4: Fetch roadmap data
        debugLogger.info(f"process_roadmaps portfolio_ids 3: {portfolio_ids}")
        if action == "prioritize":
            roadmap_data = self.fetch_roadmap_data(tenant_id, user_id, portfolio_ids, action, session_id, socketio, client_id)
            if "error" in roadmap_data:
                response = {"error": roadmap_data["error"]}
                socketio.emit(
                    agent_name,
                    {"event": "error", "data": response},
                    room=client_id
                )
                yield json.dumps(response)
                return

            roadmaps = roadmap_data.get("roadmaps_data")
            print("Sample roadmap:", roadmaps[0])
            
            socketio.emit(
                agent_name,
                {"event": "portfolios_selected", "data": "all" if len(portfolio_ids)> 1 else portfolio_ids[0]},
                room=client_id
            )
            socketio.emit("spend_agent", 
                {
                    "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": True}
                }, 
                room=client_id
            ) 
            debugLogger.info(f"process_roadmaps fetch_roadmap_data fetched: {len(roadmaps)}")
        

        # Step 5: Process action
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": (f"{action[:-1]}ing").capitalize(), "key": f"{action[:-1]}ing", "is_completed": False}
            }, 
            room=client_id
        ) 
        
        
        if action == "prioritize":
            prioritized_roadmaps = self.prioritize_roadmaps(
                roadmaps, tenant_id, user_id, session_id, socketio, client_id
            )
            response = {
                "message": "Roadmaps prioritized based on ranks and business impact.",
                "roadmaps": prioritized_roadmaps
            }
        
        elif action == "schedule":
            
            data = self.data_fetch_new(last_user_message, conversation, context, tenant_id=tenant_id)
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key="roadmap_agent_conv_data_pulled_for_scheduling",
                value=json.dumps(data),
                session_id=session_id
            )
            roadmaps = data.get("roadmaps")
            resource_data = data.get("resource_data")
            
            socketio.emit("spend_agent", 
                {
                    "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": True}
                }, 
                room=client_id
            )
            
            # Step D — the scheduling engine now receives BOTH datasets
            scheduled_roadmaps = self.schedule_roadmaps(
                roadmaps=roadmaps,
                resource_data=resource_data,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                socketio=socketio,
                client_id=client_id,
                conversation=conversation,
                start_date=start_date,
                end_date=end_date,
                last_user_message=last_user_message
            )
            response = {
                "message": "Roadmaps scheduled with dependency chart and dates.",
                "roadmaps": scheduled_roadmaps
            }

            
        elif action == "insights":
            data = self.data_fetch_new(last_user_message, conversation, context, tenant_id=tenant_id)
            # roadmaps = data.get("roadmaps")
            # resource_data = data.get("resource_data")
            # prepare an insights prompt to LLM
            prompt = ChatCompletion(
                system=f"""
                    You are an analytical assistant who answers questions using roadmap data and resource capacity data.
                    Use ONLY the provided data — do not hallucinate.
                    If something is not available in the data, say that it is not available.


                    ## INPUT DATA
                    {data}
                    
                    # Task
                    - Answer the user's question analytically, logically, and concisely.
                    - If helpful, provide tables, lists, breakdowns, insights, comparisons, timelines, dependencies, risks, or summaries.

                    # Output Format
                    Return Rich text:
                    
                """,
                prev=[],
                user=last_user_message
            )

            for response in self.llm.runWithStreaming(prompt, self.model_opts, "agent::roadmap::insights", {"tenant_id": tenant_id, "user_id": user_id}):
                yield response
                socketio.emit("agent_chat_user", response, room=client_id)
            socketio.emit("agent_chat_user", "<end>", room=client_id)
            socketio.emit("agent_chat_user", "<<end>>", room=client_id)
            return

        else:
            response = {"error": f"Invalid action: {action}"}
            socketio.emit(
                agent_name,
                {"event": "error", "data": response},
                room=client_id
            )
            yield json.dumps(response)
            
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": (f"{action[:-1]}ing").capitalize(), "key": f"{action[:-1]}ing", "is_completed": True}
            }, 
            room=client_id
        )

        # socketio.emit(
        #     agent_name,
        #     {"event": f"roadmap_{action}d", "data": response},
        #     room=client_id
        # )
        # yield json.dumps(response)
        yield "Done"

def roadmap_agent_fn(
    tenantID: int,
    userID: int,
    # portfolio_ids: List[int] = [],
    # action: str = "",
    last_user_message: str = None,
    socketio: Any = None,
    client_id: str = None,
    llm: Any = None,
    sessionID: str = None,
    base_agent=None,
    **kwargs
) -> List[str]:
    """Entry point for Roadmap Agent.

    Args:
        tenantID: Tenant ID.
        userID: User ID.
        portfolio_ids: List of portfolio IDs.
        action: Action to perform (prioritize or schedule).
        last_user_message: Latest user message.
        socketio: SocketIO instance.
        client_id: Client ID.
        llm: LLM instance.
        sessionID: Session ID.
        **kwargs: Additional arguments.

    Returns:
        List of JSON-formatted responses.
    """
    try:
        # Store user message
        if last_user_message:
            TangoDao.insertTangoState(
                tenant_id=tenantID,
                user_id=userID,
                key="roadmap_agent_conv",
                value=f"User Message: {last_user_message}",
                session_id=sessionID
            )
            
        socketio.emit("spend_agent", 
            {
                "event": "show_timeline",
            }, 
            room=client_id
        )
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Thinking", "key": "Thinking", "is_completed": False}
            }, 
            room=client_id
        ) 


        conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
            session_id=sessionID, 
            user_id=userID, 
            key="roadmap_agent_conv",
        )
        conversation = [c.get("value", "") for c in conv_]
        conversation = conversation[::-1]
        context =  (
            base_agent.user_info_string
            + "\n"
            + base_agent.roadmap_context_string
            + "\n"
            + f"Comapny Basic Info with url for extracting content from this url if required: {TenantDaoV2.fetch_company(tenant_id=tenantID)}"
        )
        prompt = ChatCompletion(
            system=f"""
                You are an assistant that analyzes the conversation and identifies the user's intended action on roadmaps.

                Your job is to classify the intent into exactly one of the following:
                1. "prioritize"  → User wants to score/rank/sequence roadmaps based on value/impact/weights.
                2. "schedule"    → User wants to assign timelines / start dates / end dates / scheduling / rescheduling / capacity-aware planning.
                3. "insights"    → User is asking general questions about roadmaps or capacity data, such as:
                - compare roadmaps
                - check dependencies
                - check team / capacity / resource utilization
                - show details or breakdown
                - ask "what if", "show me", "explain", "analyze"
                This should NOT trigger prioritization or scheduling.

                If the intent is unclear or mixed, choose the **most recent explicit intent**.

                Portfolio extraction:
                - Extract explicit or implied portfolio IDs mentioned in the conversation.
                - If user says "all portfolios", return an empty list to indicate no filtering.
                
                Extraxt start and end date from conversation
                

                Output format (must be strict JSON):
                ```json
                {{
                    "action": "",                // "prioritize", "schedule", or "insights"
                    "portfolio_ids": [],         // numeric list, empty means all
                    "roadmap_ids": [],           // optional IDs if referenced directly, else empty list
                    "query_theme": ""            // 3-7 word short summary of what user wants
                    "start_date": "", // dd-mm-yyy format
                    "end_date": "", // dd-mm-yyy format
                    "roadmap_states": []
                }}
                ```
            """,
            prev=[],
            user=f"""
            Think step by step and output strict JSON only.
                - **Context**: {context}
                User Query: {last_user_message}
                You must decide ONLY from the ongoing conversation:
                - **Conversation**: {conversation}
            """
        )
        
        response = llm.run(
            prompt, 
            ModelOptions(model="gpt-4.1", max_tokens=16000, temperature=0.2),
            "agent::roadmap::decision", 
            {"tenant_id": tenantID, "user_id": userID}
        )
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Thinking", "key": "Thinking", "is_completed": True}
            }, 
            room=client_id
        ) 
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": False}
            }, 
            room=client_id
        ) 
        
        # print("prompt --- ", prompt.formatAsString())
        print("response -- ", response)
        
        output = extract_json_after_llm(response)
        action = output.get("action") or ""
        portfolio_ids = output.get("portfolio_ids") or []
        start_date = output.get("start_date")
        end_date = output.get("end_date")
        roadmap_states = output.get("roadmap_states")
        
        
        
        
        
    
        agent = RoadmapAgent(base_agent, llm)
        answer = ''
        for response in agent.process_roadmaps(
            tenant_id=tenantID,
            user_id=userID,
            last_user_message=last_user_message,
            portfolio_ids=portfolio_ids,
            action=action,
            socketio=socketio,
            client_id=client_id,
            session_id=sessionID,
            context=context,
            conversation=conversation,
            start_date=start_date,
            end_date=end_date,
            roadmap_states=roadmap_states
        ):
            yield response
            answer += response
            socketio.emit("agent_chat_user", response, room=client_id)
            
        socketio.emit("agent_chat_user", "<end>", room=client_id)
        socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="roadmap_agent_conv",
            value=f"Agent Message: {answer}",
            session_id=sessionID
        )
        
        socketio.emit("spend_agent", 
            {
                "event": "stop_show_timeline",
            }, 
            room=client_id
        )
        
    except Exception as e:
        appLogger.error({
            "event": f"Roadmap agent failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        yield json.dumps({"error": str(e)})
        socketio.emit("spend_agent", 
            {
                "event": "stop_show_timeline",
            }, 
            room=client_id
        )

ROADMAP_AGENT = AgentFunction(
    name=agent_name,
    description="Manages roadmaps (future projects) by allowing users to prioritize or schedule them based on ranks, business impact, dependencies, and team availability.",
    args=[
        {
            "name": "portfolio_ids",
            "type": "int[]",
            "description": "Selected List of portfolio IDs to filter roadmaps. All ids for all roadmaps."
        },
        {
            "name": "action",
            "type": "str",
            "description": "Action to perform: 'prioritize' or 'schedule'."
        }
    ],
    return_description="Yields JSON-formatted prompts for action/portfolio selection or roadmap data with prioritization or scheduling results, including reasoning.",
    function=roadmap_agent_fn,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)
