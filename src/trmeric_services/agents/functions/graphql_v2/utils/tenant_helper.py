
import os
from src.trmeric_services.agents.functions.graphql_v2.infrastructure import GraphConnector, GraphConnectorConfig
from src.trmeric_api.logging.AppLogger import appLogger

def is_knowledge_integrated(tenant_id: int) -> str:
    """
    Check if pattern knowledge is integrated for a given tenant.
    
    Verifies if TigerGraph database exists for the tenant in the expected format.
    Environment-aware tenant graphs are named:
    - dev/qa: g_{ENVIRONMENT}_{tenant_id} (e.g., g_dev_648)
    - prod/none: g_{tenant_id}
    
    Args:
        tenant_id: The tenant ID to check
        
    Returns:
        str: graphname if knowledge graph exists for tenant, None otherwise
    """
    try:
        env = os.getenv("ENVIRONMENT", None)
        if env and (env == "dev" or env == "qa" or env == "prod"):
            graphname = f"g_{env}_{tenant_id}"
        else:
            return None

        # Build config from environment for consistency
        config = GraphConnectorConfig.from_env(graphname)
        connector = GraphConnector(config)

        # Ensure we can connect and set graph context; if graph doesn't exist, this fails
        connected = connector.ensure_connected()
        if connected:
            appLogger.info({
                "event": "knowledge_integration_check",
                "tenant_id": tenant_id,
                "graphname": graphname,
                "result": "integrated"
            })
            return graphname
        else:
            appLogger.warning({
                "event": "knowledge_integration_check",
                "tenant_id": tenant_id,
                "graphname": graphname,
                "result": "not_integrated",
                "error": "Failed to establish connection"
            })
            return None
    except Exception as e:
        appLogger.warning({
            "event": "knowledge_integration_check",
            "tenant_id": tenant_id,
            "graphname": graphname if 'graphname' in locals() else "",
            "result": "not_integrated",
            "error": str(e)
        })
        return None