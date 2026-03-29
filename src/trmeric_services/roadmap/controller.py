
import time
import json
import datetime
import traceback
from threading import Thread
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.roadmap.RoadmapService import RoadmapService
from src.trmeric_services.project.projectService import ProjectService



class RoadmapController:
    def __init__(self):
        self.roadmapService = RoadmapService()
        self.projectService = ProjectService()
        

    def roadmap_action_controller(
        self,
        action =None,
        data =None,
        metadata=None,
        tenant_id=None,
        user_id=None,
        llm=None,
        logInfo=None,
        model_opts=None,
        qna_controller=None,
        socketio=None,
        client_id=None,
        step_sender =None
    ):
        
        try:
            print("--debug roadmap_action_controller--", action, data,tenant_id,user_id)
            match action:
                case "create_roadmap": #chatflow, name-desc
                    qna_controller.fetchQnaChatPrefillSocketIO( 
                        socketio=socketio,
                        client_id=client_id,
                        metadata = metadata,
                        _type="roadmap",
                        # step_sender = step_sender
                    )
                
                case "create_roadmap1": #obj,org_strategy,kpis
                    self.roadmapService.createRoadmap1(
                        tenantID=tenant_id,
                        userID=user_id,
                        roadmap_id = data.get("roadmap_id",None),
                        socketio = socketio,
                        client_id = client_id,
                        llm = llm,
                        model_opts=model_opts,
                        logInfo=logInfo,
                        step_sender = step_sender
                    )
                    
                case "create_roadmap2": #scope,timeline
                    self.roadmapService.createRoadmap2(
                        tenantID=tenant_id,
                        userID=user_id,
                        roadmap_id = data.get("roadmap_id",None),
                        socketio=socketio,
                        client_id=client_id,
                        llm = llm,
                        model_opts=model_opts,
                        logInfo=logInfo,
                        step_sender = step_sender
                    )
                    
                case "create_roadmap3": #constraints,portfolio,category
                    self.roadmapService.createRoadmap3(
                        tenantID=tenant_id,
                        userID=user_id,
                        roadmap_id = data.get("roadmap_id",None),
                        socketio = socketio,
                        client_id = client_id,
                        llm = llm,
                        model_opts=model_opts,
                        logInfo=logInfo,
                        step_sender = step_sender
                    )
                    
                case "update_roadmap_estimation": #roles,budget
                    self.roadmapService.updateRoadmapEstimation(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        roadmap_id=data.get("roadmap_id"),
                        llm=llm,
                        logInfo= logInfo,
                        model_opts=model_opts,
                        socketio=socketio,
                        client_id=client_id,
                        step_sender = step_sender
                    )
                    
                case "update_roadmap_canvas":
                    self.roadmapService.updateRoadmapCanvas(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        roadmap_id=data.get("roadmap_id"),
                        logInfo=logInfo,
                        llm =llm,
                        model_opts=model_opts,
                        socketio=socketio,
                        client_id=client_id,
                        step_sender = step_sender
                    )
                    
                case "fetch_scope_driveintegration":        
                    roadmap_id = data.get("roadmap_id",None)
                    project_id = data.get("project_id",None)
                    
                    if roadmap_id:
                        self.roadmapService.fetchScopeDriveIntegration( 
                            tenant_id=tenant_id,
                            user_id=user_id,
                            roadmap_id = roadmap_id,
                            docs =data.get("docs"),
                            socketio=socketio,
                            client_id=client_id,
                            logInfo = logInfo,
                            key = data.get("s3_key"),
                            step_sender = step_sender
                        )
                    elif project_id:
                        self.projectService.fetchScopeFromIntegration(
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            project_id = project_id,
                            # docs =data.get("docs"),
                            socketio=socketio,
                            client_id=client_id,
                            logInfo = self.logInfo,
                            key = data.get("s3_key"),
                            step_sender=step_sender
                        )
                
                case "initial_tracker":
                    self.roadmapService.updateRoadmapCreationTrackUtility(
                        tenantID=tenant_id,
                        userID=user_id,
                        roadmap_id = data.get("roadmap_id",None),
                        newly_completed_items=[
                            "roadmap_name_description",
                            "objective_orgStrategy_keyResult",
                            "constraints_portfolio_category"
                        ]
                    )
                
                case "create_roadmap2_ey": #for scope + timeline + thought process
                    print("--debug action, id", action, data)
                    self.roadmapService.createRoadmap2_ey(
                        tenantID=tenant_id,
                        userID=user_id,
                        roadmap_id = data.get("roadmap_id",None),
                        socketio=socketio,
                        client_id=client_id,
                        llm = llm,
                        model_opts=model_opts,
                        logInfo=logInfo,
                        step_sender = step_sender,
                        session_id = data.get("session_id",None)
                    )
                    
                case "roadmap_changelog":
                    self.roadmapService.createDemandAuditHistory(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        roadmap_id=data.get("roadmap_id"),
                        socketio=socketio,
                        client_id=client_id,
                        step_sender = step_sender
                    )

                case _:
                    appLogger.info({
                        "event":"roadmap_action_controller",
                        "action":"Invalid Action",
                        "tenant_id":tenant_id,
                        "user_id":user_id
                    })
                    return None
        
        except Exception as e:
            print("--debug error exec [Action]--", action,e)
            appLogger.error({
                "event": "roadmap_action_controller",
                "action": action,
                "data": data,
                "error": e,
                "traceback": traceback.format_exc()
            })