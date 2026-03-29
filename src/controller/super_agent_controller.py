from flask import request, jsonify, Response
import traceback

from src.database.dao import AgentRunDAO
from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger
from src.s3.s3 import S3Service

from flask import Response, request, jsonify

def _cors_preflight_response():
    response = Response(status=200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = (
        "Authorization, Content-Type, Tenant-User-Token"
    )
    return response


class SuperAgentController:

    # --------------------------------------------------
    # Sessions
    # --------------------------------------------------

    def get_sessions(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            query = """
                SELECT
                    ars.session_id,
                    MAX(ars.created_at) AS last_activity_at,
                    MAX(ars.agent_name) AS agent_name,
                    tct.title AS chat_title
                FROM agent_run_steps ars
                LEFT JOIN tango_chattitles tct
                    ON tct.session_id = ars.session_id
                    AND tct.tenant_id = %s
                    AND tct.user_id = %s
                WHERE ars.tenant_id = %s
                AND ars.user_id = %s
                GROUP BY ars.session_id, tct.title
                ORDER BY last_activity_at DESC;

            """
            rows = db_instance.execute_query_safe(query, (tenant_id, user_id, tenant_id, user_id))
            return jsonify({"sessions": rows})

        except Exception as e:
            appLogger.error({
                "event": "get_sessions",
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def get_runs_for_session(self, session_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            query = """
                SELECT
                    r.run_id,
                    r.agent_name,

                    uq.step_payload AS question,
                    fr.step_payload AS answer,

                    uq.created_at AS asked_at,
                    fr.created_at AS answered_at

                FROM (
                    SELECT DISTINCT run_id, agent_name
                    FROM agent_run_steps
                    WHERE session_id = %s
                    AND tenant_id = %s
                    AND user_id = %s
                ) r

                LEFT JOIN LATERAL (
                    SELECT step_payload, created_at
                    FROM agent_run_steps
                    WHERE run_id = r.run_id
                    AND step_type = 'user_query'
                    ORDER BY created_at ASC
                    LIMIT 1
                ) uq ON TRUE

                LEFT JOIN LATERAL (
                    SELECT step_payload, created_at
                    FROM agent_run_steps
                    WHERE run_id = r.run_id
                    AND step_type = 'final_response'
                    ORDER BY created_at DESC
                    LIMIT 1
                ) fr ON TRUE

                ORDER BY
    uq.created_at ASC; 

            """

            rows = db_instance.execute_query_safe(
                query, (session_id, str(tenant_id), str(user_id))
            )

            return jsonify({"runs": rows})

        except Exception as e:
            appLogger.error({
                "event": "get_runs_for_session",
                "session_id": session_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # --------------------------------------------------
    # Runs
    # --------------------------------------------------

    def get_run_overview(self, run_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            query = """
                SELECT
                    run_id,
                    session_id,
                    agent_name,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS finished_at,
                    COUNT(*) AS total_steps
                FROM agent_run_steps
                WHERE run_id = %s
                  AND tenant_id = %s
                  AND user_id = %s
                GROUP BY run_id, session_id, agent_name
            """

            rows = db_instance.execute_query_safe(
                query, (run_id, tenant_id, user_id)
            )

            return jsonify(rows[0] if rows else {})

        except Exception as e:
            appLogger.error({
                "event": "get_run_overview",
                "run_id": run_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def get_run_steps(self, run_id):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            steps = AgentRunDAO.get_run_steps(
                run_id=run_id,
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                include_payload=True
            )

            return jsonify({
                "run_id": run_id,
                "steps": steps
            })

        except Exception as e:
            appLogger.error({
                "event": "get_run_steps",
                "run_id": run_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def get_run_events(self, run_id):
        try:
            events = AgentRunDAO.get_thoughts_for_run(run_id)
            return jsonify({
                "run_id": run_id,
                "events": events
            })

        except Exception as e:
            appLogger.error({
                "event": "get_run_events",
                "run_id": run_id,
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def get_run_events_tree(self, run_id):
        try:
            step_id = request.args.get("step_id")
            tree = AgentRunDAO.get_run_events_tree(run_id, step_id)

            return jsonify({
                "run_id": run_id,
                "tree": tree
            })

        except Exception as e:
            appLogger.error({
                "event": "get_run_events_tree",
                "run_id": run_id,
                "step_id": request.args.get("step_id"),
                "tenant_id": request.tenant_id,
                "user_id": request.user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def get_artifact_download_url(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            s3_key = request.args.get("key")
            if not s3_key:
                return jsonify({"error": "Missing s3 key"}), 400

            # OPTIONAL (recommended later):
            # Validate that this s3_key belongs to the user
            # by checking agent_run_steps.final_response.exports

            s3_service = S3Service()
            presigned_url = s3_service.generate_presigned_url(
                s3_key=s3_key,
                expiry=60 * 10  # 10 minutes
            )

            if not presigned_url:
                return jsonify({"error": "Failed to generate URL"}), 500

            return jsonify({
                "download_url": presigned_url,
                "expires_in": 600
            })

        except Exception as e:
            appLogger.error({
                "event": "get_artifact_download_url",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500



    def preview_artifact(self):
        print("debiug in here preview_artifact", request.method)
        try:
            if request.method == "OPTIONS":
                return _cors_preflight_response()
            s3_key = request.args.get("key")
            if not s3_key:
                return jsonify({"error": "Missing key"}), 400

            s3 = S3Service()
            response = s3.s3.get_object(
                Bucket=s3.bucket_name,
                Key=s3_key
            )

            binary = response["Body"].read()
            content_type = response.get(
                "ContentType",
                "application/octet-stream"
            )

            resp = Response(binary)
            resp.headers["Content-Type"] = content_type
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"

            return resp

        except Exception as e:
            appLogger.error({
                "event": "preview_artifact",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Failed to preview artifact"}), 500

            