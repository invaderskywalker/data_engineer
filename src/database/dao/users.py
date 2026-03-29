from src.trmeric_database.Database import db_instance
import os
from datetime import datetime, timedelta


class UsersDao:

    @staticmethod
    def fetchUserInfoWithId(user_id):
        query = f"""
        select id, first_name, last_name, email from users_user where id = {user_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]
        else: 
            return None
        
    @staticmethod
    def fetchUserDesignation(user_id):
        query = f"""
            select id AS user_id, first_name, position from users_user where id = {user_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]
        else: 
            return None
        
    @staticmethod
    def fetchUserTenantID(user_id):
        query = f"""
        select tenant_id from users_user where id = {user_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]["tenant_id"]
        else:
            return None
        
    @staticmethod
    def fetchUserSessionSummaries(user_id, limit=5, days: float = None):
        # If days is provided (can be fractional), compute a time threshold and filter by created_date
        if days is not None:
            try:
                days_float = float(days)
            except Exception:
                days_float = None

            if days_float is not None:
                time_threshold = datetime.utcnow() - timedelta(days=days_float)
                time_str = time_threshold.strftime('%Y-%m-%d %H:%M:%S')
                query = f"""
        select session_id, output_data, created_date from tango_activitylog
        where user_id = {user_id}
        and agent_or_workflow_name = 'activity_session_summary'
        and created_date >= '{time_str}'
        order by created_date desc
        limit {limit}
        """
            else:
                query = f"""
        select session_id, output_data, created_date from tango_activitylog where user_id = {user_id} and agent_or_workflow_name = 'activity_session_summary' order by created_date desc limit {limit}
        """
        else:
            query = f"""
        select session_id, output_data, created_date from tango_activitylog where user_id = {user_id} and agent_or_workflow_name = 'activity_session_summary' order by created_date desc limit {limit}
        """

        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result
        else:
            return None
        

    @staticmethod
    def fetchTenantIdForUser(user_id):
        query = f"""
            select tenant_id from users_user where id = {user_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]
        else: 
            return None
        
    @staticmethod
    def checkIfUserBelongsToTenant(target_tenant_id, user_id):
        tenant_id = UsersDao.fetchTenantIdForUser(user_id=user_id)
        # print("checkIfUserBelongsToTenant", tenant_id, tenant_id.get("tenant_id"),  target_tenant_id, tenant_id.get("tenant_id") == target_tenant_id)
        return str(tenant_id.get("tenant_id")) == str(target_tenant_id)
        
    @staticmethod
    def fetchUserLanguage(user_id):
        env = os.getenv("ENVIRONMENT")
        SPANISH="Spanish"
        ENGLISH="English"
        if user_id is None:
            return ENGLISH
        if env == "prod":
            return ENGLISH
        if env == "qa":
            if (int(user_id) in [284, 346]):
                return SPANISH
            return ENGLISH
        # if env == "dev":
        #     if (int(user_id) in [467]):
        #         return SPANISH
        return ENGLISH

