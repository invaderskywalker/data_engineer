from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger, debugLogger
import traceback
import json
from datetime import datetime


class RoadmapPrioritizationDao:
    @staticmethod
    def insertPrioritizationHistory(
        tenant_id: int,
        user_id: int,
        ai_prioritization_snapshot: dict,
        was_reordered: bool,
        reason_for_change: str = None,
        after_change: dict = None,
        session_id: str = None
    ) -> None:
        """Insert a record into roadmap_roadmapprioritizationhistory."""
        try:
            query = """
                INSERT INTO roadmap_roadmapprioritizationhistory
                    (tenant_id, user_id, ai_prioritization_snapshot, was_reordered,
                     reason_for_change, after_change, session_id, created_on)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """
            params = (
                tenant_id,
                user_id,
                json.dumps(ai_prioritization_snapshot),
                was_reordered,
                reason_for_change,
                json.dumps(after_change) if after_change else None,
                session_id,
                datetime.utcnow(),  # 👈 add current UTC time
            )
            db_instance.executeSQLQuery(query, params)
            debugLogger.info(
                f"Inserted roadmap_roadmapprioritizationhistory (tenant={tenant_id}, reordered={was_reordered})"
            )
        except Exception as e:
            appLogger.error({
                "event": "Failed to insert roadmap_roadmapprioritizationhistory",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            
    @staticmethod
    def fetchLatestPrioritizationSnapshot(tenant_id: int, user_id: int):
        """Fetch the latest saved prioritization snapshot."""
        try:
            query = """
                SELECT ai_prioritization_snapshot
                FROM roadmap_roadmapprioritizationhistory
                WHERE tenant_id = %s AND user_id = %s
                ORDER BY created_on DESC
                LIMIT 1;
            """
            params = (tenant_id, user_id)
            result = db_instance.retrieveSQLQueryOld(query, params)
            return result[0]["ai_prioritization_snapshot"] if result else None
        except Exception as e:
            appLogger.error({
                "event": "Failed to fetch latest roadmap_roadmapprioritizationhistory",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            return None
