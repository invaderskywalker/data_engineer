# src.database.dao.JobDao.py
from datetime import datetime, timedelta, date
from src.database.Database import db_instance
import json

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()  # Converts to 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'
        return super().default(obj)
    
    
class JobDAO:
    def __init__(self):
        pass

    @staticmethod
    def create(tenant_id, user_id, schedule_id, job_type, payload):
        """Create a new job and return its ID."""
        query = """
            INSERT INTO cron_jobstracker (
                tenant_id, user_id, schedule_id, job_type, payload, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        from src.utils.helper.common import MyJSON
        params = (
            tenant_id,
            user_id,
            schedule_id,
            job_type,
            MyJSON.dumps(payload),
            "pending",
            datetime.utcnow(),
            datetime.utcnow()
        )
        # print("query", query, payload)
        result = db_instance.executeSQLQuery(query, params, fetch="one")
        print("in job dao create ", result)
        return result[0] if result else None

    @staticmethod
    def read(job_id):
        """Read a job by its ID."""
        query = f"""
            SELECT * FROM cron_jobstracker WHERE id = {job_id};
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return result[0] if result else None

    @staticmethod
    def read_by_status(status, limit=100):
        """Read jobs by status, sorted by created_at."""
        query = f"""
            SELECT * FROM cron_jobstracker
            WHERE status = '{status}'
            ORDER BY created_at ASC
            LIMIT {limit};
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def update_status(job_id, status):
        """Update the status of a job."""
        updated_at = datetime.now()

        if status == "done":
            query = """
                UPDATE cron_jobstracker
                SET status = %s, updated_at = %s, done_at = %s
                WHERE id = %s;
            """
            params = (status, updated_at, updated_at, job_id)
        else:
            query = """
                UPDATE cron_jobstracker
                SET status = %s, updated_at = %s
                WHERE id = %s;
            """
            params = (status, updated_at, job_id)

        db_instance.executeSQLQuery(query, params)


    @staticmethod
    def  check_recent_job(tenant_id, user_id, job_type, minutes=60):
        """Check if a job of the same type exists for tenant/user within the last hour."""
        one_hour_ago = datetime.now() - timedelta(minutes=minutes)
        query = f"""
            SELECT id FROM cron_jobstracker
            WHERE tenant_id = {tenant_id}
              AND user_id = {user_id}
              AND job_type = '{job_type}'
              AND created_at >= '{one_hour_ago}';
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return len(result) > 0
    
    @staticmethod
    def check_recent_job_for_project(tenant_id, user_id, job_type, project_id, hours=1):
        """Check if a job of the same type exists for tenant/user/project within the last hour."""
        one_hour_ago = datetime.now() - timedelta(minutes=hours*60)
        query = f"""
            SELECT id FROM cron_jobstracker
            WHERE tenant_id = {int(tenant_id)}
            AND user_id = {user_id}
            AND job_type = '{job_type}'
            AND payload->>'project_id' = '{project_id}'
            AND created_at >= '{one_hour_ago}';
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return len(result) > 0

    @staticmethod
    def check_recent_job_identifier(tenant_id, identifier, job_type, minutes=60):
        """Check if a job of the same type exists for tenant/user within the last hour."""
        one_hour_ago = datetime.now() - timedelta(minutes=minutes)
        query = f"""
            SELECT id FROM cron_jobstracker
            WHERE tenant_id = {tenant_id}
              AND job_type = '{job_type}'
              AND payload->>'identifier' = '{identifier}'
              AND created_at >= '{one_hour_ago}';
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return len(result) > 0

    @staticmethod
    def count_completed_jobs(run_id):
        """Count completed jobs for a given run_id."""
        query = f"""
            SELECT COUNT(*) as count
            FROM cron_jobstracker
            WHERE payload->>'run_id' = '{run_id}'
              AND status = 'done';
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return result[0]["count"] if result else 0
    
    @staticmethod
    def list_jobs_by_tenant(tenant_id):
        query = f"""
            SELECT * FROM cron_jobstracker WHERE tenant_id = {tenant_id};
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return result
