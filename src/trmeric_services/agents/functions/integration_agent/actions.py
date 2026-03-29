from typing import List, Any
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_database.dao import IntegrationDao, TangoDao, NotificationDao, JobDAO
from src.trmeric_ws.static import UserSocketMap
from datetime import datetime
import json
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes

def run_cron_for_tenants(tenantID: int, userID: int, socketio: Any = None, client_id: str = None, sessionID: str = None, **kwargs) -> List[str]:
    try:
        initiate_job_for_tenant_v2(
            tenant_id=tenantID, 
            socketio=socketio, 
            user_id=userID
        )
    except Exception as e:
        appLogger.error({
            "event": "run_cron_for_tenants failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return

def initiate_job_for_tenant_v2(tenant_id: int, socketio: Any,  user_id: int = None):
    results = IntegrationDao.fetchActiveProjectMappingsFortenant(tenant_id=tenant_id)
    job_type = "user_request_cron"
    job_dao = JobDAO
    # Generate run_id
    run_id = f"initiate_job_for_tenant_v2-cron-{tenant_id}-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    total_items = len(results)
    enqueued_items = 0
    skipped_items = 0
    
    for res in results:
        try:
            project_id = res["trmeric_project_id"]
            integration_mapping_id = res["id"]
            job_user_id = res["user_id"]
            state_key = f"TENANT_LEVEL_INTEGRATION_INFO_"
            state = TangoDao.fetchLatestTangoStatesForTenant(tenant_id, state_key)
            if state:
                state_value = json.loads(state["value"])
                if state_value.get("state") == 1 and job_dao.check_recent_job_for_project(tenant_id, job_user_id, job_type, project_id, hours=0.05):
                    skipped_items += 1
                    client_id = UserSocketMap.get_client_id(user_id)
                    if socketio:
                        socketio.emit(
                            "integration_agent", 
                            {
                                "event": "cron_running_counter",
                                "data": {
                                    "message": "Already in progress",
                                    "state": 1
                                },
                            }, 
                            room=client_id
                        )
                    print(f"Skipping integration-cron for tenant {tenant_id}, user {job_user_id}, project {project_id}: Job exists within last hour")
                    continue
            
            
            TangoDao.deleteTangoStatesForSessionIdAndTenantAndKey(
                session_id="",
                tenant_id=tenant_id,
                key=f"TENANT_LEVEL_INTEGRATION_INFO_{run_id}",
            )
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key=f"TENANT_LEVEL_INTEGRATION_INFO_{run_id}",
                value=json.dumps({
                    "state": 0,
                    "message": "Starting..",
                }),
                session_id=""
            )
            # Enqueue job
            payload = {
                "job_type": job_type,
                "project_id": project_id,
                "integration_mapping_id": integration_mapping_id,
                "run_id": run_id,
                "total_count": total_items
            }
            job_id = job_dao.create(
                tenant_id=tenant_id,
                user_id=job_user_id,
                schedule_id=None,
                job_type=job_type,
                payload=payload
            )
            enqueued_items += 1
            print(f"✅ Enqueued integration-cron job for tenant {tenant_id}, user {job_user_id}, project {project_id} (job_id: {job_id}, run {run_id})")


        except Exception as e:
            appLogger.error({
                "event": "initiate_job_for_tenant_v2",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "project_id": project_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    
def initiate_job_for_tenant(tenant_id: int, socketio: Any,  user_id: int = None):
    job_state_key = "integration_cron_job"
    check = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(
        user_id=user_id, 
        key=job_state_key, 
        session_id=""
    )
    client_id = UserSocketMap.get_client_id(user_id)
    print("check --- ", check)

    service = IntegrationService()
    results = IntegrationDao.fetchActiveProjectMappingsFortenant(tenant_id=tenant_id)
    
    total_items = len(results)
    done_items = 0
    failed_items = 0
    error_messages = set()
    TangoDao.insertTangoState(
        tenant_id=tenant_id, 
        user_id=user_id, 
        key=job_state_key, 
        value="", 
        session_id=""
    )
    
    if len(check) > 0:
        if socketio:
            socketio.emit(
                "integration_agent", 
                {
                    "event": "cron_running_counter",
                    "data": {
                        "message": f"Cannot start, Job already running",
                        "state": 1
                    },
                }, 
                room=client_id
            )
            socketio.sleep(1)
            socketio.emit(
                "integration_agent", 
                {
                    "event": "cron_running_counter",
                    "data": {
                        "message": f"{done_items}/{total_items} Done, {failed_items}/{total_items} Failed",
                        "state": 1
                    },
                }, 
                room=client_id
            )
        return 
    
    if socketio:
        socketio.emit(
            "integration_agent", 
            {
                "event": "cron_running_counter",
                "data": {
                    "message": "Job Starting",
                    "state": 1
                },
            }, 
            room=client_id
        )
        
    # Emit progress update
    if socketio:
        socketio.emit(
            "integration_agent", 
            {
                "event": "cron_running_counter",
                "data": {
                    "message": f"{done_items}/{total_items} Done, {failed_items}/{total_items} Failed",
                    "state": 1
                },
            }, 
            room=client_id
        )
            

    for res in results:
        try:
            client_id = UserSocketMap.get_client_id(user_id)
            tenant_id = res['tenant_id']
            user_id = res["user_id"]
            project_id = res["trmeric_project_id"]
            integration_mapping_id = res["id"]

            if tenant_id == 71:
                continue
            
            appLogger.info({
                "event": "initiate_job_for_tenant",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "project_id": project_id,
                "integration_mapping_id": integration_mapping_id,
                "integration_type": res.get("integration_type"),
            })

            service.updateIntegrationDataV3(
                project_id, tenant_id, user_id, integration_mapping_id, True
            )
            done_items += 1

        except Exception as e:
            appLogger.error({
                "event": "initiate_job_for_tenant",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "project_id": project_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            error_messages.add(str(e))
            failed_items += 1
        
        # Emit progress update
        if socketio:
            socketio.emit(
                "integration_agent", 
                {
                    "event": "cron_running_counter",
                    "data": {
                        "message": f"{done_items}/{total_items} Done, {failed_items}/{total_items} Failed",
                        "state": 1
                    },
                },
                room=client_id
            )

    # Cleanup tango state if session info available
    if user_id:
        TangoDao.deleteTangoStatesForSessionIdAndUserAndKey(session_id="", user_id= user_id, key=job_state_key)
     
    client_id = UserSocketMap.get_client_id(user_id)   
    # Emit progress update
    if socketio:
        socketio.emit(
            "integration_agent", 
            {
                "event": "cron_running_counter",
                "data": {
                    "message": f"{done_items}/{total_items} Done, {failed_items}/{total_items} Failed",
                    "state": 2
                },
            }, 
            room=client_id
        )
        
    # After final socket emit
    NotificationDao.insert_notification(
        type_="Integration Job",
        subject="Integration Cron Finished",
        content=f"Integration job completed: {done_items} done, {failed_items} failed.\n\n Error Message: {error_messages}",
        link=None,
        params={"done": done_items, "failed": failed_items, "total": total_items},
        created_by_id=user_id,
        tenant_id=tenant_id,
        user_id=user_id
    )

    return





RUN_TENANT_CRON = AgentFunction(
    name="run_cron_for_tenants",
    description="""This function is responsible for run_cron_for_tenants""",
    args=[],
    return_description="",
    function=run_cron_for_tenants,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)
