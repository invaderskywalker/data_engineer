from src.trmeric_api.logging.AppLogger import appLogger
from flask import request
import traceback
import os
from datetime import datetime
from src.trmeric_database.dao import ProjectsDao
from src.trmeric_services.agents.functions.graphql.analysis import GraphLoaderService
from src.trmeric_services.agents.functions.graphql_v2.infrastructure import GraphSchemaInitializer, GraphConnector, GraphConnectorConfig
from src.trmeric_services.agents.functions.graphql_v2 import MasterAnalyst
from src.trmeric_services.agents.functions.graphql_v2.data_loading import PostgresConnector, PostgresConfig, ProjectQueries, RoadmapQueries
from src.trmeric_services.agents.functions.graphql_v2.analysis.portfolio_aggregator import PortfolioPatternAggregator
from src.trmeric_services.agents.functions.graphql_v2.analysis.customer_aggregator import CustomerPatternAggregator
from src.trmeric_services.agents.functions.graphql_v2.loaders import BatchGraphLoader
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
import concurrent.futures

# Allowed tenant gates per environment
QA_ALLOWED_TENANTS = {160}
PROD_ALLOWED_TENANTS = {2, 209, 156, 160, 227, 225, 55, 158, 183, 66, 102, 198}


class GraphQLController:
    def __init__(self):
        pass
    
    def _get_graphname(self, tenant_id):
        """Generate tenant-specific graph name (TigerGraph-compatible: must start with letter/underscore)"""
        if not tenant_id:
            raise ValueError("tenant_id is required")

        tenant_id_int = int(tenant_id)
        env = (os.getenv("ENVIRONMENT", "") or "").lower()

        if env == "dev":
            return f"g_dev_{tenant_id_int}"

        if env == "qa":
            if tenant_id_int in QA_ALLOWED_TENANTS:
                return f"g_qa_{tenant_id_int}"
            raise ValueError("tenant_id not allowed for QA environment")

        if env == "prod":
            if tenant_id_int in PROD_ALLOWED_TENANTS:
                return f"g_prod_{tenant_id_int}"
            raise ValueError("tenant_id not allowed for PROD environment")

        raise ValueError("Unsupported or missing ENVIRONMENT")
    
    def initialize_graph(self):
        """
        Drop existing graph and recreate schema
        Expected request JSON:
        {
            "tenant_id": int
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            if not tenant_id:
                return {"event": "error", "message": "tenant_id is required"}, 400
            
            graphname = self._get_graphname(tenant_id)
            
            appLogger.info({
                "function": "initialize_graph",
                "tenant_id": tenant_id,
                "graph_name": graphname,
                "action": "recreating_tenant_graph"
            })
            
            initializer = GraphSchemaInitializer(graphname=graphname)
            if not initializer.recreate_graph_plain(graphname):
                return {"event": "error", "message": "Failed to initialize graph"}, 500
            
            return {
                "event": "success",
                "message": f"Graph '{graphname}' recreated successfully",
                "graph_name": graphname
            }
        except Exception as e:
            appLogger.error({
                "function": "initialize_graph",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500

    def initialize_global_schema(self):
        """
        Create global schema types once (no tenant graph creation). Admin-only.
        """
        try:
            appLogger.info({"function": "initialize_global_schema", "action": "creating_global_schema_types"})
            initializer = GraphSchemaInitializer(graphname="TrmericGraph")
            if not initializer.create_schema_types():
                return {"event": "error", "message": "Failed to create global schema types"}, 500
            return {"event": "success", "message": "Global schema types created"}
        except Exception as e:
            appLogger.error({
                "function": "initialize_global_schema",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500
    
    def load_roadmaps(self):
        """
        Fetch roadmaps and analyze/load them to graph
        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "roadmap_limit": int,    # optional, defaults to 15
            "roadmap_ids": [int]     # optional, explicit list overrides roadmap_limit query
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data")
            roadmap_limit = request.json.get("roadmap_limit", None)
            explicit_roadmap_ids = request.json.get("roadmap_ids", None)
            
            if not tenant_id or not user_id:
                return {"event": "error", "message": "tenant_id and user_id are required"}, 400
            
            graphname = self._get_graphname(tenant_id)
            
            appLogger.info({
                "function": "load_roadmaps",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "graph_name": graphname,
                "roadmap_limit": roadmap_limit,
                "explicit_roadmap_ids": explicit_roadmap_ids
            })
            
            # Fetch roadmap IDs from database (or use explicit list)
            pg = PostgresConnector(PostgresConfig.from_env())
            if explicit_roadmap_ids:
                roadmap_ids = set(int(i) for i in explicit_roadmap_ids)
            else:
                with pg.cursor() as cursor:
                    roadmap_ids = RoadmapQueries.fetch_all_roadmap_ids(cursor, tenant_id, limit=roadmap_limit)
            
            if not roadmap_ids:
                return {
                    "event": "success",
                    "message": "No roadmaps found for this tenant",
                    "roadmap_count": 0
                }
            
            # Initialize LLM and analyst
            llm = ChatGPTClient(user_id, tenant_id)
            analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)
            
            # Use provided customer_data or construct a minimal default
            if not customer_data:
                customer_data = {
                    "customer": {"id": f"tenant_{tenant_id}", "name": ""},
                    "industry": {"id": "general", "name": "General"},
                    "industry_sector": {"id": "general", "name": "General"}
                }
            customer_id = customer_data.get("customer", {}).get("id", f"tenant_{tenant_id}")
            
            appLogger.info({
                "function": "load_roadmaps",
                "status": "starting_analysis",
                "graph_name": graphname,
                "roadmap_count": len(roadmap_ids)
            })
            
            analyst.analyze_and_load_roadmaps(
                customer_id,
                roadmap_ids,
                customer_data
            )
            
            return {
                "event": "success",
                "message": f"Successfully loaded {len(roadmap_ids)} roadmaps to graph",
                "graph_name": graphname,
                "roadmap_count": len(roadmap_ids),
                "roadmap_ids": list(roadmap_ids)
            }
        except Exception as e:
            appLogger.error({
                "function": "load_roadmaps",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500
    
    def load_projects(self):
        """
        Fetch projects and analyze/load them to graph
        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "project_limit": int     # optional, defaults to 15
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data")
            project_limit = request.json.get("project_limit", None)
            
            if not tenant_id or not user_id:
                return {"event": "error", "message": "tenant_id and user_id are required"}, 400
            
            graphname = self._get_graphname(tenant_id)
            
            appLogger.info({
                "function": "load_projects",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "graph_name": graphname,
                "project_limit": project_limit
            })
            
            # Fetch project IDs from database
            pg = PostgresConnector(PostgresConfig.from_env())
            with pg.cursor() as cursor:
                project_ids = ProjectQueries.fetch_all_project_ids(cursor, tenant_id, limit=project_limit)
            
            if not project_ids:
                return {
                    "event": "success",
                    "message": "No projects found for this tenant",
                    "project_count": 0
                }
            
            # Initialize LLM and analyst
            llm = ChatGPTClient(user_id, tenant_id)
            analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)
            
            # Use provided customer_data or construct a minimal default
            if not customer_data:
                customer_data = {
                    "customer": {"id": f"tenant_{tenant_id}", "name": ""},
                    "industry": {"id": "general", "name": "General"},
                    "industry_sector": {"id": "general", "name": "General"}
                }
            customer_id = customer_data.get("customer", {}).get("id", f"tenant_{tenant_id}")
            
            analyst.analyze_and_load_projects(
                customer_id,
                project_ids,
                customer_data
            )
            
            return {
                "event": "success",
                "message": f"Successfully loaded {len(project_ids)} projects to graph",
                "graph_name": graphname,
                "project_count": len(project_ids),
                "project_ids": list(project_ids)
            }
        except Exception as e:
            appLogger.error({
                "function": "load_projects",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500
    
    def initialize_and_load(self):
        """
        Full knowledge load for a tenant in one call:
          1. Recreate tenant graph
          2. Load roadmaps
          3. Load projects

        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "customer_data": {...},
            "roadmap_limit": int,   # optional
            "project_limit": int    # optional
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data")
            roadmap_limit = request.json.get("roadmap_limit", None)
            project_limit = request.json.get("project_limit", None)

            if not tenant_id or not user_id or not customer_data:
                return {"event": "error", "message": "tenant_id, user_id, and customer_data are required"}, 400

            customer_id = customer_data.get("customer", {}).get("id")
            if not customer_id:
                return {"event": "error", "message": "customer_id not found in customer_data"}, 400

            # Ensure industry and industry_sector keys exist to avoid downstream KeyError
            if not isinstance(customer_data.get("industry"), dict):
                appLogger.warning({"function": "initialize_and_load", "warning": "customer_data.missing_industry", "tenant_id": tenant_id})
                customer_data["industry"] = {"id": None}

            if not isinstance(customer_data.get("industry_sector"), dict):
                appLogger.warning({"function": "initialize_and_load", "warning": "customer_data.missing_industry_sector", "tenant_id": tenant_id})
                customer_data["industry_sector"] = {"id": None}
            graphname = self._get_graphname(tenant_id)

            appLogger.info({
                "function": "initialize_and_load",
                "tenant_id": tenant_id,
                "graph_name": graphname,
                "action": "starting_full_knowledge_load"
            })

            # Step 1: Recreate tenant graph
            initializer = GraphSchemaInitializer(graphname=graphname)
            if not initializer.recreate_graph_plain(graphname):
                return {"event": "error", "message": "Failed to initialize graph"}, 500

            appLogger.info({"function": "initialize_and_load", "step": "graph_initialized", "graph_name": graphname})

            # Shared LLM + analyst
            llm = ChatGPTClient(user_id, tenant_id)
            analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)

            # Step 2: Load roadmaps
            pg = PostgresConnector(PostgresConfig.from_env())
            with pg.cursor() as cursor:
                roadmap_ids = RoadmapQueries.fetch_all_roadmap_ids(cursor, tenant_id, limit=roadmap_limit)

            roadmap_count = len(roadmap_ids) if roadmap_ids else 0
            if roadmap_ids:
                appLogger.info({"function": "initialize_and_load", "step": "loading_roadmaps", "roadmap_count": roadmap_count})
                analyst.analyze_and_load_roadmaps(customer_id, roadmap_ids, customer_data)

            # Step 3: Load projects
            with pg.cursor() as cursor:
                project_ids = ProjectQueries.fetch_all_project_ids(cursor, tenant_id, limit=project_limit)

            project_count = len(project_ids) if project_ids else 0
            if project_ids:
                appLogger.info({"function": "initialize_and_load", "step": "loading_projects", "project_count": project_count})
                analyst.analyze_and_load_projects(customer_id, project_ids, customer_data)

            appLogger.info({"function": "initialize_and_load", "step": "complete", "graph_name": graphname})

            return {
                "event": "success",
                "message": "Graph initialized and knowledge loaded successfully",
                "graph_name": graphname,
                "roadmap_count": roadmap_count,
                "project_count": project_count
            }
        except Exception as e:
            appLogger.error({
                "function": "initialize_and_load",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500

    def graphLoadData(self):
        try:
            tenant_id = request.json.get("tenant_id")
            project_ids = ProjectsDao.get_all_child_projects(tenant_id=tenant_id)
            customer_data = request.json.get("customer_data")
            customer_id = customer_data.get("customer").get("id")
            print("debug ----- ", project_ids, tenant_id, customer_id)
            GraphLoaderService().analyse_and_load_data(tenant_id, customer_id, project_ids, customer_data)
            return {"event": "success"}
        except Exception as e:
            print("error ", e)
            appLogger.error({
                "function": "graphLoadData",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error"}

    def connect_patterns(self):
        """
        Connect RoadmapPattern to ProjectScore and ProjectPattern vertices.
        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")

            if not tenant_id or not user_id:
                return {"event": "error", "message": "tenant_id and user_id are required"}, 400

            graphname = self._get_graphname(tenant_id)

            appLogger.info({
                "function": "connect_patterns",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "graph_name": graphname
            })

            # Initialize LLM and analyst
            llm = ChatGPTClient(user_id, tenant_id)
            analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)

            # Connect patterns
            result = analyst.connect_patterns()

            if result.get("event") == "error":
                return {"event": "error", "message": result.get("message", "Unknown error")}, 500

            return {
                "event": "success",
                "message": result.get("message", "Patterns connected successfully"),
                "graph_name": graphname,
                "statistics": {
                    "patterns_processed": result.get("patterns_processed", 0),
                    "roadmaps_with_projects": result.get("roadmaps_with_projects", 0),
                    "edges_created": result.get("edges_created", 0),
                    "edge_breakdown": result.get("edge_breakdown", {})
                }
            }
        except Exception as e:
            appLogger.error({
                "function": "connect_patterns",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500
    
    def aggregate_portfolio(self):
        """
        Aggregate workflow-level patterns into portfolio-level patterns.
        Processes ALL portfolios for the tenant at once.
        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "customer_data": {"customer": {"id": ...}, "industry": {"id": ...}}  // optional
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data", {})
            
            if not tenant_id or not user_id:
                return {
                    "event": "error",
                    "message": "tenant_id and user_id are required"
                }, 400
            
            graphname = self._get_graphname(tenant_id)
            
            appLogger.info({
                "function": "aggregate_portfolio",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "graph_name": graphname
            })
            
            # Initialize graph connector
            graph_config = GraphConnectorConfig.from_env(graphname)
            graph = GraphConnector(graph_config)
            graph.connect()
            
            # Initialize LLM client
            llm = ChatGPTClient(user_id, tenant_id)
            
            # Create aggregator
            aggregator = PortfolioPatternAggregator(
                graph_connector=graph,
                tenant_id=tenant_id,
                llm_client=llm,
                customer_id=customer_data.get("customer", {}).get("id"),
                industry_id=customer_data.get("industry", {}).get("id")
            )
            
            # Run aggregation for ALL portfolios
            result = aggregator.aggregate_all_portfolios()
            
            if result["metadata"]["status"] == "no_portfolios":
                return {
                    "event": "success",
                    "message": f"No portfolios found for tenant_id={tenant_id}",
                    "graph_name": graphname,
                    "portfolios_processed": 0
                }
            
            # Load vertices and edges to graph
            # Result format is already correct: Dict[vertex_type, List[(id, attrs)]] for vertices
            # and Dict[edge_type, List[(from_id, to_id)]] for edges
            vertices_by_type = result["vertices"]
            edges_by_type = result["edges"]
            
            loader = BatchGraphLoader(graph)
            load_result = loader.load_graph_structure(
                vertices=vertices_by_type,
                edges=edges_by_type
            )
            
            if load_result.get("total_vertices_failed", 0) > 0 or load_result.get("total_edges_failed", 0) > 0:
                return {
                    "event": "partial_success",
                    "message": f"Portfolio patterns created with some failures",
                    "graph_name": graphname,
                    "load_stats": load_result,
                    "metadata": result["metadata"]
                }, 200
            
            return {
                "event": "success",
                "message": f"Portfolio patterns created for {result['metadata']['portfolios_processed']} portfolios",
                "graph_name": graphname,
                "portfolios_processed": result["metadata"]["portfolios_processed"],
                "portfolios_skipped": result["metadata"]["portfolios_skipped"],
                "total_portfolios": result["metadata"]["total_portfolios"],
                "successful_portfolios": result["metadata"]["successful_portfolios"],
                "vertices_loaded": load_result["total_vertices_loaded"],
                "edges_loaded": load_result["total_edges_loaded"]
            }
        except Exception as e:
            appLogger.error({
                "function": "aggregate_portfolio",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500

    def aggregate_customer(self):
        """
        Synthesize all PortfolioPatterns into a single CustomerPattern.
        This is the apex vertex — a strategic, LLM-generated summary of the entire
        organization's project and roadmap landscape.

        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "customer_data": {
                "customer": {"id": "...", "name": "..."},
                "industry": {"id": "...", "name": "..."},
                "industry_sector": {"id": "...", "name": "..."}
            }
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data")

            if not tenant_id or not user_id or not customer_data:
                return {
                    "event": "error",
                    "message": "tenant_id, user_id, and customer_data are required"
                }, 400

            graphname = self._get_graphname(tenant_id)

            appLogger.info({
                "function": "aggregate_customer",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "graph_name": graphname
            })

            # Initialize graph connector
            graph_config = GraphConnectorConfig.from_env(graphname)
            graph = GraphConnector(graph_config)
            graph.connect()

            # Also load customer/industry/sector vertices from customer_data
            loader = BatchGraphLoader(graph)
            loader.load_customer_data([customer_data], tenant_id=tenant_id)

            # Initialize LLM client and aggregator
            llm = ChatGPTClient(user_id, tenant_id)
            aggregator = CustomerPatternAggregator(
                graph_connector=graph,
                tenant_id=tenant_id,
                llm_client=llm,
                customer_data=customer_data
            )

            result = aggregator.aggregate()

            if result["metadata"]["status"] == "no_portfolio_patterns":
                return {
                    "event": "success",
                    "message": f"No portfolio patterns found for tenant_id={tenant_id}. Run aggregate-portfolio first.",
                    "graph_name": graphname
                }

            if result["metadata"]["status"] == "error":
                return {"event": "error", "message": result["metadata"].get("error", "Unknown error")}, 500

            # Load to graph
            vertices_by_type = result["vertices"]
            edges_by_type = result["edges"]

            load_result = loader.load_graph_structure(
                vertices=vertices_by_type,
                edges=edges_by_type
            )

            return {
                "event": "success",
                "message": "Customer pattern created",
                "graph_name": graphname,
                "customer_pattern_id": result["metadata"]["customer_pattern_id"],
                "portfolio_count": result["metadata"]["portfolio_count"],
                "vertices_loaded": load_result["total_vertices_loaded"],
                "edges_loaded": load_result["total_edges_loaded"]
            }
        except Exception as e:
            appLogger.error({
                "function": "aggregate_customer",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500

    def run_knowledge_pipeline(self):
        """
        Execute the full knowledge graph pipeline end-to-end:
          1. Initialize graph schema
          2. Load roadmaps + projects (in parallel)
          3. Connect patterns (roadmap → project via scores)
          4. Aggregate portfolio patterns
          5. Aggregate customer pattern

        Expected request JSON:
        {
            "tenant_id": int,
            "user_id": int,
            "customer_data": {
                "customer": {"id": "...", "name": "..."},
                "industry": {"id": "...", "name": "..."},
                "industry_sector": {"id": "...", "name": "..."}
            },
            "roadmap_limit": int,    # optional
            "project_limit": int,    # optional
            "roadmap_ids": [int],    # optional, explicit list overrides roadmap_limit query
            "project_ids": [int]     # optional, explicit list overrides project_limit query
        }
        """
        try:
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            customer_data = request.json.get("customer_data")
            roadmap_limit = request.json.get("roadmap_limit", None)
            project_limit = request.json.get("project_limit", None)
            explicit_roadmap_ids = request.json.get("roadmap_ids", None)
            explicit_project_ids = request.json.get("project_ids", None)

            if not tenant_id or not user_id or not customer_data:
                return {
                    "event": "error",
                    "message": "tenant_id, user_id, and customer_data are required"
                }, 400

            graphname = self._get_graphname(tenant_id)
            customer_id = customer_data.get("customer", {}).get("id", f"tenant_{tenant_id}")
            pipeline_start = datetime.now()

            appLogger.info({
                "function": "run_knowledge_pipeline",
                "tenant_id": tenant_id,
                "graph_name": graphname,
                "stage": "starting"
            })

            results = {
                "tenant_id": tenant_id,
                "graph_name": graphname,
                "stages": {}
            }

            # ── Stage 1: Initialize graph ──
            appLogger.info({"function": "run_knowledge_pipeline", "stage": "initialize"})
            initializer = GraphSchemaInitializer(graphname=graphname)
            
            # Ensure global vertex/edge types exist before creating tenant graph
            if not initializer.create_schema_types():
                appLogger.warning({"function": "run_knowledge_pipeline", "stage": "initialize", "note": "create_schema_types returned False (types may already exist)"})
            
            if not initializer.recreate_graph_plain(graphname):
                return {
                    "event": "error",
                    "message": f"Failed to create graph '{graphname}'. Global schema types may be missing.",
                    "stages": results["stages"]
                }, 500
            results["stages"]["initialize"] = "success"

            # ── Stage 2: Load roadmaps + projects in parallel ──
            appLogger.info({"function": "run_knowledge_pipeline", "stage": "load_data"})

            pg = PostgresConnector(PostgresConfig.from_env())
            if explicit_roadmap_ids:
                roadmap_ids = set(int(i) for i in explicit_roadmap_ids)
            else:
                with pg.cursor() as cursor:
                    roadmap_ids = RoadmapQueries.fetch_all_roadmap_ids(cursor, tenant_id, limit=roadmap_limit)
            if explicit_project_ids:
                project_ids = set(int(i) for i in explicit_project_ids)
            else:
                with pg.cursor() as cursor:
                    project_ids = ProjectQueries.fetch_all_project_ids(cursor, tenant_id, limit=project_limit)

            roadmap_result = None
            project_result = None

            def _load_roadmaps():
                llm = ChatGPTClient(user_id, tenant_id)
                analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)
                analyst.analyze_and_load_roadmaps(customer_id, roadmap_ids, customer_data)
                return len(roadmap_ids)

            def _load_projects():
                llm = ChatGPTClient(user_id, tenant_id)
                analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)
                analyst.analyze_and_load_projects(customer_id, project_ids, customer_data)
                return len(project_ids)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                if roadmap_ids:
                    futures["roadmaps"] = executor.submit(_load_roadmaps)
                if project_ids:
                    futures["projects"] = executor.submit(_load_projects)

                for key, future in futures.items():
                    try:
                        count = future.result()
                        results["stages"][f"load_{key}"] = {"status": "success", "count": count}
                    except Exception as e:
                        results["stages"][f"load_{key}"] = {"status": "error", "error": str(e)}
                        appLogger.error({
                            "function": "run_knowledge_pipeline",
                            "stage": f"load_{key}",
                            "error": str(e)
                        })

            # ── Stage 3: Connect patterns ──
            appLogger.info({"function": "run_knowledge_pipeline", "stage": "connect_patterns"})
            llm = ChatGPTClient(user_id, tenant_id)
            analyst = MasterAnalyst(tenant_id, user_id, llm=llm, graphname=graphname)
            connect_result = analyst.connect_patterns()
            results["stages"]["connect_patterns"] = {
                "status": "success" if connect_result.get("event") != "error" else "error",
                "edges_created": connect_result.get("edges_created", 0)
            }

            # ── Stage 4: Aggregate portfolio patterns ──
            appLogger.info({"function": "run_knowledge_pipeline", "stage": "aggregate_portfolio"})
            graph_config = GraphConnectorConfig.from_env(graphname)
            graph = GraphConnector(graph_config)
            graph.connect()

            portfolio_aggregator = PortfolioPatternAggregator(
                graph_connector=graph, tenant_id=tenant_id, llm_client=llm,
                customer_id=customer_id,
                industry_id=customer_data.get("industry", {}).get("id")
            )
            portfolio_result = portfolio_aggregator.aggregate_all_portfolios()

            if portfolio_result["metadata"]["status"] != "no_portfolios":
                portfolio_loader = BatchGraphLoader(graph)
                portfolio_load = portfolio_loader.load_graph_structure(
                    vertices=portfolio_result["vertices"],
                    edges=portfolio_result["edges"]
                )
                results["stages"]["aggregate_portfolio"] = {
                    "status": "success",
                    "portfolios_processed": portfolio_result["metadata"].get("portfolios_processed", 0),
                    "vertices_loaded": portfolio_load["total_vertices_loaded"],
                    "edges_loaded": portfolio_load["total_edges_loaded"]
                }
            else:
                results["stages"]["aggregate_portfolio"] = {"status": "skipped", "reason": "no portfolios"}

            # ── Stage 5: Aggregate customer pattern ──
            appLogger.info({"function": "run_knowledge_pipeline", "stage": "aggregate_customer"})
            customer_aggregator = CustomerPatternAggregator(
                graph_connector=graph,
                tenant_id=tenant_id,
                llm_client=llm,
                customer_data=customer_data
            )
            customer_result = customer_aggregator.aggregate()

            if customer_result["metadata"]["status"] == "success":
                customer_loader = BatchGraphLoader(graph)
                # Load customer/industry vertices first
                customer_loader.load_customer_data([customer_data], tenant_id=tenant_id)
                customer_load = customer_loader.load_graph_structure(
                    vertices=customer_result["vertices"],
                    edges=customer_result["edges"]
                )
                results["stages"]["aggregate_customer"] = {
                    "status": "success",
                    "customer_pattern_id": customer_result["metadata"]["customer_pattern_id"],
                    "vertices_loaded": customer_load["total_vertices_loaded"],
                    "edges_loaded": customer_load["total_edges_loaded"]
                }
            else:
                results["stages"]["aggregate_customer"] = {
                    "status": customer_result["metadata"]["status"],
                    "reason": customer_result["metadata"].get("error", "no portfolio patterns")
                }

            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            results["event"] = "success"
            results["message"] = "Knowledge pipeline completed"
            results["duration_seconds"] = round(pipeline_duration, 1)

            appLogger.info({
                "function": "run_knowledge_pipeline",
                "stage": "complete",
                "duration_seconds": pipeline_duration,
                "stages": results["stages"]
            })

            return results

        except Exception as e:
            appLogger.error({
                "function": "run_knowledge_pipeline",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {"event": "error", "message": str(e)}, 500