from typing import List, Optional, Dict, Any
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_database.dao import PortfolioDao, TangoDao, RoadmapsDaoV2, IdeaDao
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
import json
from datetime import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed


class IdeaRankingAgent:
    """Agent for prioritizing or scheduling roadmaps (future projects) based on user selection."""

    def __init__(self, base_agent, llm: Any):
        """Initialize with an LLM instance."""
        self.llm = llm
        self.base_agent = base_agent
        self.model_opts = ModelOptions(model="gpt-4.1", max_tokens=32000, temperature=0.2)


    def fetch_idea_data(
        self,
        tenant_id: int,
        user_id: int,
        portfolio_ids: List[int],
        action: str,
        session_id: str,
        socketio: Any,
        client_id: str
    ) -> Dict:
        """
        Fetch idea data via MasterAnalyst tailored to the specified action.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.
            portfolio_ids: List of portfolio IDs (empty for all ideas).
            action: Action (generate, evaluate, prioritize, elaborate).
            session_id: Session ID.
            socketio: SocketIO instance.
            client_id: Client ID.

        Returns:
            Dictionary with idea data and resource data or error.
        """
        try:
            debugLogger.info(f"process_ideas fetch_idea_data: {action}")
            state_filter = None
            if action == "prioritize":
                projection_attrs = [
                    "id", "title", "priority", "kpis", "constraints", "portfolios"
                ]
                # state_filter = "ic.status IN ('Prioritize', 'Elaboration')"
                order_clause = "ORDER BY ic.rank ASC"

            else:
                raise ValueError(f"Invalid action: {action}")

            # --- Step 3: Fetch data from IdeaDao ---
            response = IdeaDao.fetchIdeasDataWithProjectionAttrs(
                tenant_id=tenant_id,
                projection_attrs=projection_attrs,
                portfolio_ids=portfolio_ids,
                state_filter=state_filter,
                order_clause=order_clause
            )

            ideas_data = response
            # resource_data = get_capacity_data(tenantID=tenant_id, userID=user_id)

            # --- Step 4: Error / empty data handling ---
            if not ideas_data:
                appLogger.warning(f"No idea data returned from MasterAnalyst for action: {action}")
                socketio.emit(
                    "idea_agent",
                    {"event": "error", "data": {"error": "No idea data found."}},
                    room=client_id
                )
                return {"error": "No idea data found."}

            debugLogger.info(f"Fetched {len(ideas_data)} ideas for action: {action}")

            # --- Step 5: Return combined data ---
            return {
                "ideas_data": ideas_data,
                # "resource_data": resource_data
            }

        except Exception as e:
            appLogger.error({
                "event": f"Failed to fetch idea data for action {action}",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"error": str(e)}

    def prioritize_ideas(
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
                    prompt, self.model_opts, "agent::ideation::prioritize", {"tenant_id": tenant_id, "user_id": user_id}
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
                                "ideation_agent",
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
                    "ideation_agent",
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
                "ideation_agent",
                {"event": "idea_prioritized", "data": final_output["prioritization_of_all_roadmap_items"]},
                room=client_id
            )
            debugLogger.info(f"Prioritized {len(sorted_roadmaps)} roadmaps")
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key="idea_prioritization",
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
                "ideation_agent",
                {"event": "error", "data": {"error": str(e)}},
                room=client_id
            )
            return [{"error": str(e)}]


    def process_ideas(
        self,
        tenant_id: int,
        user_id: int,
        last_user_message: str,
        portfolio_ids: List[int],
        action: str,
        socketio: Any,
        client_id: str,
        session_id: str
    ) -> str:
        """Process roadmap action (prioritize or schedule) after user selections."""
        debugLogger.info(f"process_ideas: {action}")
        action = 'prioritize'
#         if not action:
#             yield """Do you want to prioritize or schedule roadmaps?
# ```json
# {
#     "cta_buttons": [
#         {"label": "Prioritize Ideas", "action": "prioritize"},
#     ]
# }

# ```
# """
#             debugLogger.info("Prompting user for action selection")
#             return


        debugLogger.info(f"process_ideas portfolio_ids: {portfolio_ids} {action}")
        
        # Step 2: Prompt for portfolio selection if none provided
        if not portfolio_ids and action in ["prioritize", "schedule"]:
            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            portfolio_id_title = [{"id": p["id"], "title": p["title"], "label": p["title"], "preprend": "Selected portfolio: "} for p in portfolios]
            portfolio_id_title.insert(0, {"id": "all_portfolios", "title": "All Portfolios", "label": "All Portfolios", "preprend": "Selected portfolio: "})
            yield f"""Please select a portfolio from the list of portfolios.

```json
{{
    "cta_buttons": {json.dumps(portfolio_id_title, indent=8)}
}}
``` 
"""
            return
    
        
        # debugLogger.info(f"process_ideas portfolio_ids 2: {portfolio_ids}")
        
        # Step 4: Fetch roadmap data
        debugLogger.info(f"process_ideas portfolio_ids 3: {portfolio_ids}")
        roadmap_data = self.fetch_idea_data(
            tenant_id, 
            user_id, 
            portfolio_ids, 
            action, 
            session_id, 
            socketio, 
            client_id,
        )
        if "error" in roadmap_data:
            response = {"error": roadmap_data["error"]}
            socketio.emit(
                "ideation_agent",
                {"event": "error", "data": response},
                room=client_id
            )
            yield json.dumps(response)
            return

        ideas_data = roadmap_data.get("ideas_data")
        
        socketio.emit(
            "ideation_agent",
            {"event": "portfolios_selected", "data": "all" if len(portfolio_ids)> 1 else portfolio_ids[0]},
            room=client_id
        )
        
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": "Gathering Data", "key": "Gathering Data", "is_completed": True}
            }, 
            room=client_id
        ) 
        

        # Step 5: Process action
        
        socketio.emit("spend_agent", 
            {
                "event": "timeline", "data": {"text": (f"{action[:-1]}ing").capitalize(), "key": f"{action[:-1]}ing", "is_completed": False}
            }, 
            room=client_id
        ) 
        
        debugLogger.info(f"process_ideas fetch_idea_data fetched: {len(ideas_data)}")
        if action == "prioritize":
            prioritized_roadmaps = self.prioritize_ideas(
                ideas_data, tenant_id, user_id, session_id, socketio, client_id
            )
            response = {
                "message": "Roadmaps prioritized based on ranks and business impact.",
                "roadmaps": prioritized_roadmaps
            }
        # elif action == "schedule":
        #     scheduled_roadmaps = self.schedule_roadmaps(
        #         roadmaps, tenant_id, user_id, session_id, socketio, client_id
        #     )
        #     response = {
        #         "message": "Roadmaps scheduled with dependency chart and dates.",
        #         "roadmaps": scheduled_roadmaps
        #     }
        else:
            response = {"error": f"Invalid action: {action}"}
            socketio.emit(
                "ideation_agent",
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
        #     "ideation_agent",
        #     {"event": f"roadmap_{action}d", "data": response},
        #     room=client_id
        # )
        # yield json.dumps(response)
        yield "Done"

def basic_fn(
    tenantID: int,
    userID: int,
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
                key="ideation_agent_conv",
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
            session_id=sessionID, user_id=userID, key="ideation_agent_conv"
        )
        conversation = [c.get("value", "") for c in conv_]
        conversation = conversation[::-1]
        context =  base_agent.user_info_string
        prompt = ChatCompletion(
            system=f"""
                You are an assistant tasked with analyzing a conversation and user context to determine the user's intended action ('prioritize' or 'schedule') and the portfolio IDs they are interested in.

                **Input Details**:
                - **Context**: {context}
                - Contains user-specific information (e.g., user preferences, available portfolios). Parse this to understand the user’s portfolio options.
                
                - A list of strings representing the conversation history, with the most recent message first.
                - Analyze the conversation to identify the user’s intent (e.g., keywords like 'prioritize' or references to specific portfolios).

                **Task**:
                1. Determine the user’s intended action:
                - If the conversation mentions 'prioritize', 'rank', or similar terms, set the action to 'prioritize'.
                - If no clear action is mentioned, default to an empty string ("").
                2. Identify portfolio IDs:
                - Extract portfolio IDs (e.g., numeric or string identifiers) mentioned in the conversation or implied by the context.
                - If no specific portfolios are mentioned, return an empty list ([]).
                3. Output the result in the following JSON format:
                ```json
                {{
                    "portfolio_ids": [], // do not 
                    "action": "" // 'prioritize'
                }}
                ```
            """,
            prev=[],
            user=f"""
            Properly think and decide and output in proper json. User Query: {last_user_message}
            Only make decision by looking at this ongoing conversation:
            - **Conversation**: {conversation}
            """
        )
        
        response = llm.run(
            prompt, 
            ModelOptions(model="gpt-4.1", max_tokens=16000, temperature=0.2),
            "agent::ideation::decision", 
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
        
        
        
        
        
    
        agent = IdeaRankingAgent(base_agent, llm)
        answer = ''
        for response in agent.process_ideas(
            tenant_id=tenantID,
            user_id=userID,
            last_user_message=last_user_message,
            portfolio_ids=portfolio_ids,
            action=action,
            socketio=socketio,
            client_id=client_id,
            session_id=sessionID
        ):
            yield response
            answer += response
            
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="ideation_agent_conv",
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
            "event": f"Ideation agent failed",
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

IDEA_RANKING_AGENT = AgentFunction(
    name="ideation_agent",
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
            "description": "Action to perform: 'prioritize'"
        }
    ],
    return_description="Yields JSON-formatted prompts for action/portfolio selection or roadmap data with prioritization or scheduling results, including reasoning.",
    function=basic_fn,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)
