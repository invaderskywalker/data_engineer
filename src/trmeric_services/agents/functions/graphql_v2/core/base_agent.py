"""
Base Agent - Abstract Base Class for All Graph Query Agents

This is the core abstraction that all specific agents (Project, Roadmap, etc.)
will extend. It provides the common workflow while allowing customization
through abstract methods and dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json
import traceback

from ..models.query_plan import QueryPlan
from ..models.privacy_models import PrivacyScope
from ..models.graph_schema import GraphSchema
from ..infrastructure import GraphConnector, AgentConfig
from src.trmeric_ml.llm.Client import LLMClient
from ..core.privacy_layer import PrivacyLayer
from ..core.query_builder import QueryBuilder
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger, verboseLogger


class BaseAgent(ABC):
    """
    Abstract base class for all graph query agents.
    
    This class provides the complete query workflow:
    1. Plan query (using LLM)
    2. Apply privacy filters
    3. Build GSQL queries
    4. Execute in batches
    5. Clean and return results
    
    Subclasses only need to:
    - Define their entity type
    - Provide entity-specific prompts
    - Implement response cleaning logic
    """
    
    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        graph_connector: GraphConnector,
        llm_client: LLMClient,
        config: AgentConfig,
        privacy_scope: PrivacyScope = PrivacyScope.PRIVATE,
        eligible_entity_ids: List[str] = None,
        user_context: str = "",
        socketio=None,
        client_id=None,
        session_id=None,
    ):
        """
        Initialize base agent.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            graph_connector: Graph database connector
            llm_client: LLM client for planning and formatting
            config: Agent configuration
            privacy_scope: Privacy scope for queries
            eligible_entity_ids: Entity IDs user has access to
            user_context: User's context (role, permissions, etc.)
            socketio: SocketIO instance for streaming
            client_id: Client ID for SocketIO
            session_id: Session identifier
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.graph_connector = graph_connector
        self.llm_client = llm_client
        self.config = config
        self.privacy_scope = privacy_scope
        self.eligible_entity_ids = eligible_entity_ids or []
        self.user_context = user_context
        self.socketio = socketio
        self.client_id = client_id
        self.session_id = session_id
        
        # Get schema for this entity type
        self.entity_type = self.get_entity_type()
        self.schema = self.get_schema()
        
        # Initialize query builder
        self.query_builder = QueryBuilder(
            schema=self.schema,
            graphname=self.graph_connector.config.graphname
        )
        
        debugLogger.info({
            "function": f"{self.__class__.__name__}_init",
            "entity_type": self.entity_type,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "privacy_scope": privacy_scope.value
        })
    
    @abstractmethod
    def get_entity_type(self) -> str:
        """
        Return the entity type this agent handles.
        
        Returns:
            Entity type string (e.g., "Project", "Roadmap")
        """
        pass
    
    @abstractmethod
    def get_planning_prompt(self, query: str) -> str:
        """
        Generate planning prompt for this entity type.
        
        Args:
            query: User's natural language query
            
        Returns:
            Planning prompt string
        """
        pass

    @abstractmethod
    def get_schema(self) -> GraphSchema:
        """
        Return the GraphSchema for this entity type.
        
        Subclasses should import from infrastructure.trmeric_schema
        and return the appropriate PROJECT_SCHEMA or ROADMAP_SCHEMA.
        
        Returns:
            GraphSchema object for this entity type
        """
        pass
    
    @abstractmethod
    def clean_response(self, raw_results: List[Dict]) -> Dict[str, Any]:
        """
        Clean raw GSQL results into structured format.
        
        Args:
            raw_results: Raw results from GSQL query
            
        Returns:
            Cleaned results dictionary
        """
        pass
    
    def plan_query(self, query: str) -> QueryPlan:
        """
        Plan the query using LLM.
        
        Args:
            query: User's natural language query
            
        Returns:
            QueryPlan object
        """
        verboseLogger.info({
            "function": f"{self.__class__.__name__}_plan_query_start",
            "query": query,
            "tenant_id": self.tenant_id
        })
        
        try:
            # Get planning prompt from subclass
            prompt_text = self.get_planning_prompt(query)
            
            # Call LLM
            chat_completion = ChatCompletion(
                system=prompt_text,
                prev=[],
                user=f"Plan query for: '{query}'"
            )
            
            # Use ChatGPTClient.run method with proper ModelOptions
            from src.trmeric_ml.llm.Types import ModelOptions
            response = self.llm_client.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                function_name=f"{self.__class__.__name__}::plan_query"
            )
            
            # Parse JSON response
            plan_dict = extract_json_after_llm(response)
            
            # Convert to QueryPlan object
            plan = QueryPlan(
                vertices_to_query=plan_dict.get("vertices_to_query", []),
                edges_to_query=plan_dict.get("edges_to_query", []),
                entity_ids=plan_dict.get("entity_ids", []),
                attributes_to_query=plan_dict.get("attributes_to_query", {}),
                filters=plan_dict.get("filters", {}),
                privacy_scope=self.privacy_scope,
                clarification_needed=plan_dict.get("clarification_needed", False),
                clarification_message=plan_dict.get("clarification_message"),
                planning_rationale=plan_dict.get("planning_rationale", ""),
                entity_type=self.entity_type
            )
            
            debugLogger.info({
                "function": f"{self.__class__.__name__}_plan_query_success",
                "tenant_id": self.tenant_id,
                "plan": plan.to_dict()
            })
            
            return plan
            
        except Exception as e:
            appLogger.error({
                "function": f"{self.__class__.__name__}_plan_query_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            raise
    
    def execute_query(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        Execute query plan with privacy filtering and batching.
        
        Args:
            plan: Query plan
            
        Returns:
            Query results
        """
        verboseLogger.info({
            "function": f"{self.__class__.__name__}_execute_query_start",
            "tenant_id": self.tenant_id
        })
        
        try:
            # Step 1: Apply filters if present
            if plan.filters:
                plan = self._apply_filters(plan)
            
            # Step 2: Use eligible entity IDs if plan has none
            if not plan.entity_ids:
                plan.entity_ids = self.eligible_entity_ids
            
            # Step 3: Apply privacy filters
            plan = PrivacyLayer.filter_query_plan(plan, self.schema)
            
            # Step 4: Build and execute queries in batches
            results = self._execute_batched_queries(plan)
            
            return results
            
        except Exception as e:
            appLogger.error({
                "function": f"{self.__class__.__name__}_execute_query_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            raise
    
    def _apply_filters(self, plan: QueryPlan) -> QueryPlan:
        """
        Apply dynamic filters to get matching entity IDs.
        
        Args:
            plan: Query plan with filters
            
        Returns:
            Updated plan with filtered entity IDs
        """
        try:
            # Build filter query
            filter_query = self.query_builder.build_filter_query(plan)
            
            debugLogger.info({
                "function": f"{self.__class__.__name__}_apply_filters",
                "filter_query": filter_query[:200]
            })
            
            # Execute filter query
            response = self.graph_connector.execute_interpreted_query(filter_query)
            
            # Clean response
            response = response.replace("Using graph 'TrmericGraph'", "").strip()
            response_data = extract_json_after_llm(response)
            
            # Extract filtered entity IDs
            filtered_ids = []
            for block in response_data.get("results", []) or []:
                for entity in block.get("filtered_entities", []):
                    entity_id = entity.get("attributes", {}).get("filtered_entities.id")
                    if entity_id:
                        filtered_ids.append(entity_id)
            
            if filtered_ids:
                plan.entity_ids = filtered_ids
                
            debugLogger.info({
                "function": f"{self.__class__.__name__}_apply_filters_success",
                "filtered_count": len(filtered_ids)
            })
            
        except Exception as e:
            appLogger.warning({
                "function": f"{self.__class__.__name__}_apply_filters_error",
                "error": str(e),
                "will_continue": True
            })
            # Continue without filtering if filter fails
        
        return plan
    
    def _execute_batched_queries(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        Execute queries in batches and combine results.
        
        Args:
            plan: Query plan
            
        Returns:
            Combined results from all batches
        """
        # Build batched queries
        queries = self.query_builder.build_batched_queries(
            plan,
            batch_size=self.config.batch_size
        )
        
        all_results = []
        
        for batch_num, query in enumerate(queries, 1):
            try:
                debugLogger.info({
                    "function": f"{self.__class__.__name__}_execute_batch",
                    "batch_num": batch_num,
                    "total_batches": len(queries)
                })
                
                # Execute query
                response = self.graph_connector.execute_interpreted_query(query)
                
                # Parse response - remove all "Using graph" messages
                import re
                response = re.sub(r"Using graph '[^']*'\n?", "", response).strip()
                response_data = extract_json_after_llm(response)
                
                # Extend results
                all_results.extend(response_data.get("results", []))
                
            except Exception as e:
                appLogger.error({
                    "function": f"{self.__class__.__name__}_execute_batch_error",
                    "batch_num": batch_num,
                    "error": str(e)
                })
                # Continue with next batch
        
        # Clean combined results
        cleaned_results = self.clean_response(all_results)
        
        return cleaned_results
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Complete query processing workflow.
        
        Args:
            query: User's natural language query
            
        Returns:
            Query results
        """
        try:
            verboseLogger.info({
                "function": f"{self.__class__.__name__}_process_query_start",
                "query": query,
                "tenant_id": self.tenant_id
            })
            
            # Step 1: Plan query
            plan = self.plan_query(query)
            
            # Step 2: Check for clarification
            if plan.clarification_needed:
                return {
                    "error": plan.clarification_message or "Please clarify your query."
                }
            
            # Step 3: Execute query
            results = self.execute_query(plan)
            
            return results
            
        except Exception as e:
            appLogger.error({
                "function": f"{self.__class__.__name__}_process_query_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            raise
