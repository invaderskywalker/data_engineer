

from typing import List, Dict, Any
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import json
import traceback
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import TangoDao, RoadmapDao
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os

class RoadmapInsightsCache:
    def __init__(self, tenant_id: int, user_id: int, session_id: str, init: bool = True):
        """Initialize RoadmapInsights for generating and caching roadmap insights.

        Args:
            tenant_id: Tenant ID for data isolation.
            user_id: User ID initiating the session.
            session_id: Session ID for storing insights.
            init: Whether to initialize insights on instantiation (default: True).
        """
        debugLogger.info(f"Initializing RoadmapInsights for tenant_id: {tenant_id}, session_id: {session_id}")
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.model_options = ModelOptions(model="gpt-4o", max_tokens=16000, temperature=0.2)
        self.dev_env = os.getenv("ENVIRONMENT") in []
        self.insight_types = ["portfolio", "type", "category"]

        if init and not self.dev_env:
            try:
                self.initialize_insights()
            except Exception as e:
                appLogger.error({
                    "event": "Roadmap insights initialization failed",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })

    def check_if_initialize_insights(self, insight_type: str) -> bool:
        """Check if insights for the current day exist in TangoDao.

        Args:
            insight_type: Type of insights (portfolio, type, category).

        Returns:
            bool: True if insights need to be generated, False if cached for today.
        """
        cache_key = f"ROADMAP_{insight_type.upper()}_INSIGHTS_{self.tenant_id}"
        debugLogger.info(f"Checking if should initialize insights for cache_key: {cache_key}")
        existing_cache = TangoDao.fetchLatestTangoStatesTenant(self.tenant_id, cache_key)
        current_date = datetime.now().date()

        if existing_cache:
            latest_cache = existing_cache[0]
            cache_created_date = latest_cache.get("created_date")
            if cache_created_date:
                cache_datetime = datetime.fromisoformat(cache_created_date)
                cache_date = cache_datetime.date()
                if cache_date == current_date:
                    debugLogger.info(
                        f"Cache exists for key: {cache_key}, created today ({cache_date}). Skipping initialization."
                    )
                    return False
                else:
                    debugLogger.info(
                        f"Cache exists for key: {cache_key}, but from {cache_date}, not today ({current_date}). Proceeding."
                    )
            else:
                debugLogger.warning(f"Cache exists for key: {cache_key}, but created_date missing. Proceeding.")
        
        debugLogger.info(f"No cache or outdated for key: {cache_key}. Proceeding with initialization.")
        return True

    def cache_insights(self, insight_type: str, insights: List[Dict[str, Any]]):
        """Cache insights in TangoDao.

        Args:
            insight_type: Type of insights (portfolio, type, category).
            insights: List of insight dictionaries to cache.
        """
        cache_key = f"ROADMAP_{insight_type.upper()}_INSIGHTS_{self.tenant_id}"
        TangoDao.insertTangoState(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            key=cache_key,
            value=json.dumps(insights),
            session_id=self.session_id
        )
        debugLogger.info(f"Cached {insight_type} insights for key: {cache_key}")

    def fetch_roadmap_data(self) -> List[Dict[str, Any]]:
        """Fetch roadmap data for insight generation.

        Returns:
            List of roadmap dictionaries.
        """
        roadmap_data = RoadmapDao.get_data_for_insight_gen(tenant_id=self.tenant_id)
        if not roadmap_data:
            debugLogger.warning("No roadmap data found; using dummy data for simulation.")
            return []
        return roadmap_data


    def generate_insights(self, insight_type: str, roadmap_data: List[Dict[str, Any]], socketio: Any = None, client_id: str = None) -> List[Dict[str, Any]]:
        """Generate insights for a specific insight type using LLM.

        Args:
            insight_type: Type of insights (portfolio, type, category).
            roadmap_data: List of roadmap dictionaries.
            socketio: SocketIO instance for real-time feedback.
            client_id: Client ID for SocketIO room.

        Returns:
            List of insight dictionaries.
        """
        prompts = {
            "portfolio": ChatCompletion(
                system=f"""
                    You are an executive assistant analyzing roadmap data across portfolios to generate insights for senior leadership. The roadmap data includes future projects with details on portfolio, type, category, start/end dates, ranks, and dependencies.

                    **Input Data**:
                    - Roadmap Data: {json.dumps(roadmap_data, indent=2)}
                    - Each roadmap includes:
                    - id, title, type (Enhancement, Project, Program), category (e.g., Data & AI, Customer Experience), start_date, end_date, rank (overall), portfolio_id, portfolio_rank, dependencies.

                    **Task**:
                    Analyze the roadmap data and summarize 4 executive-level insights, each max 20 words, focusing on:
                    1. Major strategic focus areas or capabilities receiving attention (e.g., Data & AI, Customer Experience).
                    2. High-activity or delivery-intensive periods indicating peak delivery phases or bottlenecks.
                    3. Cross-portfolio synergies or shared initiatives (e.g., modernizing the same platform).
                    4. Potential gaps, risks, or areas lacking investment (e.g., high-priority portfolio with no projects).

                    **Output Format**:
                    ```json
                    [
                        {{ "insight": "<text>", "category": "Strategic Focus" }},
                        {{ "insight": "<text>", "category": "Delivery Periods" }},
                        {{ "insight": "<text>", "category": "Cross-Portfolio Synergies" }},
                        {{ "insight": "<text>", "category": "Gaps and Risks" }}
                    ]
                    ```
                    Ensure each insight is concise, non-technical, relevant for senior leadership, and max 20 words.
                """,
                prev=[],
                user="Generate 4 executive-level insights for roadmaps by portfolio, each max 20 words. Output in proper JSON"
            ),
            "type": ChatCompletion(
                system=f"""
                    You are an executive assistant analyzing roadmap data segmented by type (Enhancement, Project, Program) to generate insights for senior leadership.

                    **Input Data**:
                    - Roadmap Data: {json.dumps(roadmap_data, indent=2)}
                    - Each roadmap includes:
                    - id, title, type (Enhancement, Project, Program), category, start_date, end_date, rank, portfolio_id, portfolio_rank, dependencies.

                    **Task**:
                    Analyze the roadmap data and summarize 4 key executive-level insights, each max 20 words, focusing on:
                    1. Overall distribution across types and its implication for strategic priorities.
                    2. Risks from overlapping or heavy program load (e.g., too many large programs with similar timelines).
                    3. Level of enhancement activity as a signal of operational maturity or backlog.
                    4. Balance between transformation (projects/programs) and incremental change (enhancements).

                    **Output Format**:
                    ```json
                    [
                        {{ "insight": "<text>", "category": "Type Distribution" }},
                        {{ "insight": "<text>", "category": "Program Risks" }},
                        {{ "insight": "<text>", "category": "Enhancement Activity" }},
                        {{ "insight": "<text>", "category": "Transformation Balance" }}
                    ]
                    ```
                    Ensure each insight is concise, non-technical, relevant for senior decision-makers, and max 20 words.
                """,
                prev=[],
                user="Generate 4 executive-level insights for roadmaps by type, each max 20 words. Output in proper JSON"
            ),
            "category": ChatCompletion(
                system=f"""
                    You are an executive assistant analyzing roadmap data by capability category (e.g., Data & AI, Customer Experience, ERP Modernization) to generate insights for senior leadership.

                    **Input Data**:
                    - Roadmap Data: {json.dumps(roadmap_data, indent=2)}
                    - Each roadmap includes:
                    - id, title, type (Enhancement, Project, Program), category, start_date, end_date, rank, portfolio_id, portfolio_rank, dependencies.

                    **Task**:
                    Identify the top 5 categories by volume of roadmaps. Summarize 4 executive-level insights, each max 20 words, focusing on:
                    1. Most prioritized capabilities and their strategic implications.
                    2. Capability gaps or underinvestments (e.g., low investment in critical areas).
                    3. Balance between modern (e.g., AI, automation) and legacy (e.g., ERP, infrastructure) themes.
                    4. Whether capability investments are siloed or cross-portfolio.

                    **Output Format**:
                    ```json
                    [
                        {{ "insight": "<text>", "category": "Prioritized Capabilities" }},
                        {{ "insight": "<text>", "category": "Capability Gaps" }},
                        {{ "insight": "<text>", "category": "Modern vs Legacy" }},
                        {{ "insight": "<text>", "category": "Cross-Portfolio Investment" }}
                    ]
                    ```
                    Ensure each insight is concise, non-technical, strategic, and max 20 words.
                """,
                prev=[],
                user="Generate 4 executive-level insights for top 5 roadmap categories, each max 20 words. Output in proper JSON"
            )
        }

        prompt = prompts.get(insight_type)
        if not prompt:
            raise ValueError(f"Invalid insight type: {insight_type}")

        response = self.llm.run(
            prompt,
            self.model_options,
            f"insights::{insight_type}",
            logInDb={"tenant_id": self.tenant_id, "user_id": self.user_id}
        )
        insights = extract_json_after_llm(response)

        if not isinstance(insights, list) or len(insights) != 4:
            error_msg = f"Invalid LLM response for {insight_type} insights"
            appLogger.error({"event": f"{insight_type.capitalize()} insights failed", "error": error_msg})
            if socketio and client_id:
                socketio.emit(
                    "roadmap_agent",
                    {"event": f"{insight_type}_insights", "data": {"status": "error", "error": error_msg}},
                    room=client_id
                )
            return []

        return insights



    def initialize_insights(self):
        """Initialize and cache insights for all insight types."""
        debugLogger.info(f"Initializing roadmap insights for tenant_id: {self.tenant_id}")
        roadmap_data = self.fetch_roadmap_data()

        def process_insight_type(insight_type: str) -> Dict[str, Any]:
            try:
                if not self.check_if_initialize_insights(insight_type):
                    cached_insights = TangoDao.fetchLatestTangoStatesTenant(self.tenant_id, f"ROADMAP_{insight_type.upper()}_INSIGHTS_{self.tenant_id}")
                    insights = json.loads(cached_insights[0]["value"]) if cached_insights else []
                    return {"insight_type": insight_type, "insights": insights, "status": "success", "source": "cache"}
                
                insights = self.generate_insights(insight_type, roadmap_data)
                if insights:
                    self.cache_insights(insight_type, insights)
                    return {"insight_type": insight_type, "insights": insights, "status": "success", "source": "generated"}
                else:
                    return {"insight_type": insight_type, "insights": [], "status": "error", "error": f"Failed to generate {insight_type} insights"}
            except Exception as e:
                appLogger.error({
                    "event": f"{insight_type.capitalize()} insights generation failed",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                return {"insight_type": insight_type, "insights": [], "status": "error", "error": str(e)}

        max_workers = max(len(self.insight_types), 3)
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_insight_type, insight_type) for insight_type in self.insight_types]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    debugLogger.error(f"Error processing insight type: {e}")

        debugLogger.info("Roadmap insights initialization completed")
        return [json.dumps(result) for result in results]

    def fetch_insights(self, insight_types: List[str] = None) -> Dict[str, Any]:
        """Fetch cached insights for specified or all insight types.

        Args:
            insight_types: List of insight types to fetch (portfolio, type, category). If None, fetch all.

        Returns:
            Dictionary mapping insight types to their insights or error messages.
        """
        debugLogger.info(f"Fetching roadmap insights for tenant_id: {self.tenant_id}")
        if not insight_types:
            insight_types = self.insight_types

        cache_keys = [f"ROADMAP_{t.upper()}_INSIGHTS_{self.tenant_id}" for t in insight_types]
        results = TangoDao.fetchLatestTangoStatesTenantMultiple(cache_keys)
        insights_data = {}

        for record in results:
            key = record.get("key")
            insight_type = next(t for t in insight_types if f"ROADMAP_{t.upper()}_INSIGHTS_{self.tenant_id}" == key)
            value = record.get("value")
            try:
                parsed_insights = extract_json_after_llm(value)
                insights_data[insight_type] = {"status": "success", "insights": parsed_insights}
            except Exception as e:
                debugLogger.error(f"Failed to parse JSON for insight_type {insight_type}, key {key}: {e}")
                insights_data[insight_type] = {"status": "error", "error": f"Failed to parse insights: {e}"}

        for insight_type in insight_types:
            if insight_type not in insights_data:
                insights_data[insight_type] = {"status": "error", "error": f"No insights found for {insight_type}"}

        debugLogger.info(f"Fetched insights for {len(insights_data)} insight types")
        return insights_data
    