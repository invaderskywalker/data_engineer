import json
import traceback
from datetime import datetime
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger


class NotificationDao:
    @staticmethod
    def insert_notification(type_, subject, content, link, params, created_by_id, tenant_id, user_id):
        print("--debug in insert_notification----", type_, subject, content, link, params, created_by_id, tenant_id, user_id)
        try:
            query = """
                INSERT INTO notifications_appnotification (
                    type, subject, content, link, read, created_on, params,
                    created_by_id, tenant_id, user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                type_,
                subject,
                content,
                link,
                False,  # unread
                datetime.now(),
                json.dumps(params) if params else None,
                created_by_id,
                tenant_id,
                user_id
            )
            db_instance.executeSQLQuery(query, values)
            print({'status': 'success', 'event': 'notification_inserted', 'type': type_,'tenant_id': tenant_id,'user_id': user_id})
        except Exception as e:
            appLogger.error({
                "function": "NotificationDao.insert_notification",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "values": values
            })


    @staticmethod
    def notification_exists_after_threshold(tenant_id: int,user_id: int,notification_type: str,project_id: int,threshold_date: datetime) -> bool:
        query = f"""
            SELECT 1
            FROM notifications_appnotification
            WHERE tenant_id = {tenant_id}
            AND user_id = {user_id}
            AND type = '{notification_type}'
            AND deleted_on IS NULL
            AND created_on >= '{threshold_date.isoformat()}'
            AND params ->> 'project_id' = '{project_id}'
            LIMIT 1
        """
        print("Debug - notification_exists_after_threshold Query:", query)
        result = db_instance.retrieveSQLQueryOld(query)
        return len(result) > 0


    @staticmethod
    def notification_exists_today(tenant_id: int,user_id: int,notification_type: str,project_id: int, threshold_date: datetime=None) -> bool:
        query = f"""
            SELECT 1
            FROM notifications_appnotification
            WHERE tenant_id = {tenant_id}
            AND user_id = {user_id}
            AND type = '{notification_type}'
            AND deleted_on IS NULL
            AND created_on >= date_trunc('day', now())
            AND created_on < date_trunc('day', now()) + interval '1 day'
            AND params->>'project_id' = '{project_id}'
            LIMIT 1
        """
        print("Debug - notification_exists_today Query:", query)
        result = db_instance.retrieveSQLQueryOld(query)
        return len(result) > 0