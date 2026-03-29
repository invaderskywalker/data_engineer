from flask import request, jsonify
import time
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.insight.InsightService import InsightService
import traceback


class InsightController:
    def __init__(self):
        self.service = InsightService()

    def createInsightForProjectUpdate(self, project_id):
        try:
            data = request.json.get("data")
            appLogger.info({
                "event": "createInsightForProjectUpdate_start",
                "data": data
            })
            start_time = time.time()
            appLogger.info({
                "event": "createInsightForProjectUpdate",
                "data": data
            })
            result = self.service.createInsightForProjectUpdate(
                data, project_id)
            appLogger.info({
                "event": "createInsightForProjectUpdate",
                "response": result,
                "duration": time.time() - start_time,
                "data": data
            })
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Project Brief content generated successfully",
                        "result": result,
                    }
                ),
                200,
            )
        except Exception as e:
            appLogger.error({
                "event": "createInsightForProjectUpdate",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({
                "status": "error",
                "statusCode": 500,
                "message": "Something went wrong"
            }), 500
