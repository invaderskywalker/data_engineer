import json
import time
import datetime
import threading
import traceback
from flask import Flask, Response, jsonify, request
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_api.logging.LogResponseInfo import logResponseInfo
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_database.dao import TenantDao, ProjectsDao, IntegrationDao, TangoDao, RoadmapDao
from src.trmeric_services.agents.functions.potential_agent.potential import Potential
from src.trmeric_database.Database import db_instance




class PotentialController:
    def __init__(self):
        self.potential_service = Potential()
        
        
    def getResourcesSkillMapping(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            # portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            print("debug ---###--- ",tenant_id,user_id)
            
            resources = TenantDao.fetchResourceDetailsForTenant(tenant_id)
            metrics = self.potential_service.get_potential_metrics(resources, tenant_id, user_id)
            
            # metrics = self.potential_service.get_potential_metrics(portfolios, tenant_id, user_id)
            return jsonify({"status":"success","data": metrics}), 200
        
        except Exception as e:
            appLogger.error({"event": "getResourcesInPortfolios","error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "An error occurred while fetching resources in portfolios."}), 500
    
    
    def createPotentialInsights(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            # portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            print("debug ---###---createPotentialInsights ", tenant_id, user_id)
            
            insights = self.potential_service.create_potential_insights(tenant_id, user_id)
            # print("\n\n\n--debug createPotentialInsights--- ", insights)
        
            return jsonify({"status":"success","data": insights}), 200
        except Exception as e:
            appLogger.error({"event": "createPotentialInsights","error": str(e), "traceback": traceback.format_exc()})
            return jsonify({"error": "An error occurred while fetching resources in portfolios."}), 500
        
        
    def createResourceInsights(self,resource_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            
            print("--debug createResourceInsights--- ", resource_id,tenant_id,user_id)
            info = TenantDao.fetchResourceDetailsForTenant(tenant_id,resource_ids=[resource_id])
            
            insights = self.potential_service.create_resource_insights(resource_id,info,tenant_id,user_id)
            # print("\n\n\n--debug createPotentialInsights--- ", insights)
        
            return jsonify({"status":"success","data": insights}), 200
        
        except Exception as e:
            appLogger.error({"event":"createResourceInsights","error":str(e),"traceback":traceback.format_exc()})
            return jsonify({"error": "Error generating resource insights"}), 500 