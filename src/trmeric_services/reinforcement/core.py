import re
import json
import traceback
import numpy as np
from datetime import datetime
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ReinforcementDao
from src.trmeric_database.Redis import RedClient


class ReinforcementLearning:
    def __init__(self):
        self.log_info = None
        self.db_instance = db_instance
        self.redis = RedClient()


    def get_tango_feature_info(self, agent_name, feature_name,section=None,subsection=None):
        """
        Retrieve feature information based on agent and feature names.
        """
        try:
            key = f"Reinforcement::Agent::{agent_name}::Feature::{feature_name}"
            if section:
                key += f"::Section::{section}"
            if subsection:
                key += f"::Subsection::{subsection}"
            
            # print("--debug [Tango feature key]------", key)
            res = self.redis.execute(
                query = lambda: ReinforcementDao.fetchTangoFeaturesData(
                    agent_name=f"%{agent_name}%",
                    feature_name=f"%{feature_name}%",
                    section = f"%{section}%" if section else None,
                    subsection = f"%{subsection}%" if subsection else None
                ),
                key_set = key,
                expire = 86400*7*30*12
            )
            return res
        except Exception as e:
            appLogger.error({"event": "get_tango_feature_info","error": str(e),"traceback": traceback.format_exc()})
            return []
        
        
    def get_reinforcement_data(self, tenant_id,agentName=None,featureName=None,section=None,subsection=None, user_id:int=None):
        """
            Retrieves reinforcement data from the database.
        """
        # print("--debug in get_reinforcement_data----------------", tenant_id, featureName,agentName)
        
        try:
            feature_id = None
            if agentName and featureName:
                print("--debug agentName and featureName----------------", agentName, featureName)
                res = self.get_tango_feature_info(agent_name=agentName,feature_name=featureName,section=section,subsection=subsection)

            # print("--debug in get_reinforcement_data feature_id_query ",res)
            feature_id = res[0]['id'] if res else None
            if not feature_id:
                return {"status": "error", "message": "Feature ID not found","tenant_id": tenant_id,"agentName": agentName,"featureName": featureName}
            level = res[0]['level'] if res else None
            # print("--debug in get_reinforcement_data----------------", feature_id, level)
            if level == 'user':
                key_set = f"reinforcement_data::{tenant_id}::{user_id}::{feature_id}"
            else:
                key_set = f"reinforcement_data::{tenant_id}::{feature_id}"

            result = self.redis.execute(
                query = lambda: ReinforcementDao.fetchTangoReinforcementData(tenant_id=tenant_id,feature_id=feature_id, user_id=user_id),
                # key_set = f"reinforcement_data::{tenant_id}::{feature_id}",
                key_set = key_set,
                expire = 86400  # 1 hour expiration
            )
            # print("--debug in get_reinforcement_data result----------------", result[:2])
            return result
        except Exception as e:
            appLogger.error({"event": "get_reinforcement_data","error": str(e),"traceback": traceback.format_exc()})
            return []

    
    def post_reinforcement_data(self, data):
        """
            Inserts reinforcement data into the database
        """
        try:
            # print("--debug in post_reinforcement_data----------------", data)
            agent_name = data.get("agent_name",'')
            feature_name = data.get("feature_name",'')
            section = data.get("section",None)
            subsection = data.get("subsection",None)
            sentiment = data.get("sentiment",None)
            comment = data.get("comment",None) or "No comments."
            feedback_metadata = json.dumps(data.get("feedback_metadata", {}))
            tenant_id = data.get("tenant_id")
            user_id = data.get("user_id")
            
            # print("--debug in post_reinforcement_data values----------------\n", agent_name, feature_name, "Section: ",section, sentiment, comment, feedback_metadata, tenant_id, user_id)

            if not all([agent_name, feature_name, sentiment is not None, comment]):
                # Optional: Add logging to see which field is actually missing
                missing_fields = []
                if not agent_name: missing_fields.append("agent_name")
                if not feature_name: missing_fields.append("feature_name")
                if sentiment is None: missing_fields.append("sentiment") # Specifically check for None
                if not comment: missing_fields.append("comment") # Check for empty string or None
                appLogger.warning({
                    "event": "post_reinforcement_data_validation_fail",
                    "message": "Missing required fields",
                    "missing": missing_fields,
                    "data_received": data # Log the full data received
                })
                return {"status": "error", "message": f"Missing required fields: {', '.join(missing_fields)}"}

            res = self.get_tango_feature_info(agent_name=agent_name,feature_name=feature_name,section=section,subsection=subsection)
            # print("--debug in post_reinforcement_data feature_id_query ",res)
            feature_id = res[0].get('id',None) or None
            level = res[0].get('level',None) or None
            
            section = res[0].get('section',None) or None
            subsection = res[0].get('subsection',None) or None
            # print("--debug feature_id postReq ", feature_id, level, section, subsection)
            if not feature_id:
                return {"status": "error", "message": "Feature ID not found","tenant_id": tenant_id,"agentName": agent_name,"featureName": feature_name, "section": section, "subsection": subsection}
            
            result = ReinforcementDao.insertTangoReinforcementData(sentiment, comment, feedback_metadata,tenant_id, user_id, feature_id)
            print({"status": result,"agent_name": agent_name, "feature_name": feature_name,"section": section, "subsection": subsection, "tenant_id": tenant_id, "user_id": user_id})
            return result
        
        except Exception as e:
            appLogger.error({"event": "post_reinforcement_data","error": str(e),"traceback": traceback.format_exc()})
            return {"status": "error", "message": "Error storing feedback","agent_name": agent_name, "feature_name": feature_name,"section": section, "subsection": subsection, "tenant_id": tenant_id, "user_id": user_id}
        

    def get_delta_prompts(self, tenant_id, feature_name, agent_name,section=None,subsection=None,user_id:int=None, limit=1):
        """
        Retrieve recent delta prompts for a tenant and feature.
        """
        try:
            res = self.get_tango_feature_info(agent_name=agent_name,feature_name=feature_name,section=section,subsection=subsection)
            feature_id = res[0]['id'] if res else None
            # print("--debug [Feature_id] get_delta_prompts ", feature_id, res)
            if not feature_id:
                return []
            
            result = ReinforcementDao.fetchReinforcementDeltaPrompts(tenant_id=tenant_id,feature_id=feature_id,user_id=user_id,limit=limit)
            return result if result else []

        except Exception as e:
            appLogger.error({
                "event": "get_delta_prompts",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return []


    def store_delta_prompt(self, tenant_id, feature_name, agent_name, user_id, delta_prompt, metadata,section=None,subsection=None):
        
        """Store a delta prompt in tango_reinforcementlearning."""
        # print("--debug in store_delta_prompt----------------", tenant_id, feature_name, agent_name, user_id, delta_prompt, metadata,"\nsection-subsection ", section, subsection)
        try:
            # Get feature_id
            res = self.get_tango_feature_info(agent_name=agent_name,feature_name=feature_name,section=section,subsection=subsection)
            feature_id = res[0]['id'] if res else None
            level = res[0]['level'] if res else None

            # print("--debug feature_id store_delta_prompt ", feature_id, level, res)
            
            if not feature_id:
                return {"status": "error", "message": f"Feature {feature_name} not found"}

            result = ReinforcementDao.upsertTangoReinforcementLearning(
                tenant_id = tenant_id,
                user_id = user_id,
                feature_id = feature_id,
                delta_prompt = delta_prompt,
                metadata = metadata
            )
        except Exception as e:
            appLogger.error({"event": "store_delta_prompt","error": str(e),"traceback": traceback.format_exc()})
            return {"status": "error", "message": str(e)}








        
        
        
        
        