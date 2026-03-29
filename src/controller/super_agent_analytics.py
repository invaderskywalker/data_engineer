from flask import request, jsonify
from datetime import datetime, timedelta
import traceback
from typing import Optional, Dict, Any, List

from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger


class SuperAgentAnalyticsController:
    """
    Analytics controller for SuperAgent execution tracking.
    Provides comprehensive metrics for admin dashboard.
    """

    # ─────────────────────────────────────────────────────────────
    # OVERVIEW & SUMMARY METRICS
    # ─────────────────────────────────────────────────────────────

    def get_analytics_overview(self):
        """
        High-level dashboard metrics with time-frame filtering.
        
        Query params:
        - start_date: ISO datetime (default: 7 days ago)
        - end_date: ISO datetime (default: now)
        - tenant_id: optional filter
        - user_id: optional filter
        """
        try:
            # Parse filters
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            user_id = request.args.get('user_id')

            # Default to last 7 days
            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                WITH run_durations AS (
                    SELECT 
                        run_id,
                        EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) as duration_seconds
                    FROM agent_run_steps
                    WHERE created_at BETWEEN %s AND %s
                        AND (%s IS NULL OR tenant_id = %s)
                        AND (%s IS NULL OR user_id = %s)
                    GROUP BY run_id
                )
                SELECT 
                    COUNT(DISTINCT ars.run_id) as total_runs,
                    COUNT(DISTINCT ars.session_id) as total_sessions,
                    COUNT(DISTINCT ars.user_id) as active_users,
                    COUNT(DISTINCT ars.tenant_id) as active_tenants,
                    COUNT(*) as total_steps,
                    COUNT(CASE WHEN ars.status = 'completed' THEN 1 END) as completed_steps,
                    COUNT(CASE WHEN ars.status = 'failed' THEN 1 END) as failed_steps,
                    COUNT(CASE WHEN ars.status = 'running' THEN 1 END) as running_steps,
                    ROUND(AVG(rd.duration_seconds)::numeric, 2) as avg_run_duration_seconds,
                    ROUND(MAX(rd.duration_seconds)::numeric, 2) as max_run_duration_seconds,
                    ROUND(MIN(rd.duration_seconds)::numeric, 2) as min_run_duration_seconds
                FROM agent_run_steps ars
                LEFT JOIN run_durations rd ON ars.run_id = rd.run_id
                WHERE ars.created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR ars.tenant_id = %s)
                    AND (%s IS NULL OR ars.user_id = %s)
            """

            params = (
                start_date, end_date, tenant_id, tenant_id, user_id, user_id,
                start_date, end_date, tenant_id, tenant_id, user_id, user_id
            )

            result = db_instance.execute_query_safe(query, params)

            return jsonify({
                "overview": result[0] if result else {},
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "tenant_id": tenant_id,
                    "user_id": user_id
                }
            })

        except Exception as e:
            appLogger.error({
                "event": "get_analytics_overview",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # TIME-SERIES ANALYTICS
    # ─────────────────────────────────────────────────────────────

    def get_execution_timeline(self):
        """
        Execution timeline with configurable bucketing.
        
        Query params:
        - start_date, end_date, tenant_id, user_id (same as overview)
        - granularity: hour, day, week (default: day)
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            user_id = request.args.get('user_id')
            granularity = request.args.get('granularity', 'day')

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            # Validate granularity
            if granularity not in ['hour', 'day', 'week']:
                granularity = 'day'

            query = f"""
                SELECT 
                    date_trunc('{granularity}', created_at) as time_bucket,
                    COUNT(DISTINCT run_id) as total_runs,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(*) as total_steps,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_steps,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_steps
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                    AND (%s IS NULL OR user_id = %s)
                GROUP BY time_bucket
                ORDER BY time_bucket ASC
            """

            params = (start_date, end_date, tenant_id, tenant_id, user_id, user_id)
            rows = db_instance.execute_query_safe(query, params)

            return jsonify({
                "timeline": rows,
                "granularity": granularity
            })

        except Exception as e:
            appLogger.error({
                "event": "get_execution_timeline",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # PATTERN DISTRIBUTION
    # ─────────────────────────────────────────────────────────────

    def get_pattern_distribution(self):
        """
        Step type distribution with success rates.
        Shows which step types are most common and their reliability.
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            user_id = request.args.get('user_id')

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                SELECT 
                    step_type,
                    COUNT(*) as total_count,
                    COUNT(DISTINCT run_id) as runs_using,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running_count,
                    ROUND(
                        (COUNT(CASE WHEN status = 'completed' THEN 1 END)::numeric / 
                         NULLIF(COUNT(*)::numeric, 0)) * 100, 
                        2
                    ) as success_rate
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                    AND (%s IS NULL OR user_id = %s)
                GROUP BY step_type
                ORDER BY total_count DESC
            """

            params = (start_date, end_date, tenant_id, tenant_id, user_id, user_id)
            rows = db_instance.execute_query_safe(query, params)

            return jsonify({
                "patterns": rows
            })

        except Exception as e:
            appLogger.error({
                "event": "get_pattern_distribution",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # USER ANALYTICS
    # ─────────────────────────────────────────────────────────────

    def get_user_analytics(self):
        """
        Per-user activity breakdown.
        Shows most active users and their usage patterns.
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            limit = int(request.args.get('limit', 50))

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                SELECT 
                    user_id,
                    tenant_id,
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(DISTINCT run_id) as total_runs,
                    COUNT(*) as total_steps,
                    MIN(created_at) as first_activity,
                    MAX(created_at) as last_activity,
                    COUNT(DISTINCT DATE(created_at)) as active_days,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_steps
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                GROUP BY user_id, tenant_id
                ORDER BY total_runs DESC
                LIMIT %s
            """

            params = (start_date, end_date, tenant_id, tenant_id, limit)
            rows = db_instance.execute_query_safe(query, params)

            return jsonify({
                "users": rows
            })

        except Exception as e:
            appLogger.error({
                "event": "get_user_analytics",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # DETAILED RUN INSPECTION
    # ─────────────────────────────────────────────────────────────

    def get_detailed_runs(self):
        """
        Paginated runs with ALL steps per run (full execution trace).
        Best for debugging / observability.
        """
        try:
            # Pagination
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            offset = (page - 1) * per_page

            # Filters
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            user_id = request.args.get('user_id')
            agent_name = request.args.get('agent_name')

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            # ─────────────────────────────────────────────
            # 1. Get paginated run summaries
            # ─────────────────────────────────────────────

            runs_query = r"""
                SELECT 
                    run_id,
                    session_id,
                    user_id,
                    tenant_id,
                    agent_name,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS finished_at,
                    EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) AS duration_seconds,
                    COUNT(*) AS total_steps,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_steps
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                    AND (%s IS NULL OR user_id = %s)
                    AND (%s IS NULL OR agent_name = %s)
                GROUP BY run_id, session_id, user_id, tenant_id, agent_name
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
            """

            params = (
                start_date, end_date,
                tenant_id, tenant_id,
                user_id, user_id,
                agent_name, agent_name,
                per_page, offset
            )

            runs = db_instance.execute_query_safe(runs_query, params)

            if not runs:
                return jsonify({"runs": [], "pagination": {"page": page, "per_page": per_page, "total": 0, "pages": 0}})

            run_ids = [r["run_id"] for r in runs]

            # ─────────────────────────────────────────────
            # 2. Fetch ALL steps for these runs
            # ─────────────────────────────────────────────

            steps_query = r"""
                SELECT 
                    run_id,
                    step_type,
                    step_index,
                    status,
                    step_payload,
                    created_at
                FROM agent_run_steps
                WHERE run_id = ANY(%s)
                ORDER BY created_at ASC
            """

            steps = db_instance.execute_query_safe(steps_query, (run_ids,))

            # ─────────────────────────────────────────────
            # 3. Group steps by run_id
            # ─────────────────────────────────────────────

            steps_map = {}
            for step in steps:
                steps_map.setdefault(step["run_id"], []).append(step)

            # Attach steps to runs
            for run in runs:
                run["steps"] = steps_map.get(run["run_id"], [])

            # ─────────────────────────────────────────────
            # 4. Total count for pagination
            # ─────────────────────────────────────────────

            count_query = """
                SELECT COUNT(DISTINCT run_id) AS count
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                    AND (%s IS NULL OR user_id = %s)
                    AND (%s IS NULL OR agent_name = %s)
            """

            count_params = (
                start_date, end_date,
                tenant_id, tenant_id,
                user_id, user_id,
                agent_name, agent_name
            )

            total_result = db_instance.execute_query_safe(count_query, count_params)
            total = total_result[0]['count'] if total_result else 0

            return jsonify({
                "runs": runs,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            })

        except Exception as e:
            appLogger.error({
                "event": "get_detailed_runs",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500
        
    # ─────────────────────────────────────────────────────────────
    # AGENT-SPECIFIC ANALYTICS
    # ─────────────────────────────────────────────────────────────

    def get_agent_breakdown(self):
        """
        Performance breakdown by agent name.
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                SELECT 
                    agent_name,
                    COUNT(DISTINCT run_id) as total_runs,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as total_steps,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_steps,
                    ROUND(
                        (COUNT(CASE WHEN status = 'completed' THEN 1 END)::numeric / 
                         NULLIF(COUNT(*)::numeric, 0)) * 100, 
                        2
                    ) as success_rate
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                GROUP BY agent_name
                ORDER BY total_runs DESC
            """

            params = (start_date, end_date, tenant_id, tenant_id)
            rows = db_instance.execute_query_safe(query, params)

            return jsonify({
                "agents": rows
            })

        except Exception as e:
            appLogger.error({
                "event": "get_agent_breakdown",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # FAILURE ANALYSIS
    # ─────────────────────────────────────────────────────────────

    def get_failure_analysis(self):
        """
        Detailed analysis of failed executions.
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            tenant_id = request.args.get('tenant_id')
            limit = int(request.args.get('limit', 50))

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                SELECT 
                    run_id,
                    session_id,
                    user_id,
                    tenant_id,
                    agent_name,
                    step_type,
                    step_index,
                    step_payload,
                    created_at
                FROM agent_run_steps
                WHERE status = 'failed'
                    AND created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                ORDER BY created_at DESC
                LIMIT %s
            """

            params = (start_date, end_date, tenant_id, tenant_id, limit)
            rows = db_instance.execute_query_safe(query, params)

            # Group failures by step_type
            failure_summary_query = """
                SELECT 
                    step_type,
                    COUNT(*) as failure_count,
                    COUNT(DISTINCT run_id) as affected_runs
                FROM agent_run_steps
                WHERE status = 'failed'
                    AND created_at BETWEEN %s AND %s
                    AND (%s IS NULL OR tenant_id = %s)
                GROUP BY step_type
                ORDER BY failure_count DESC
            """

            summary_params = (start_date, end_date, tenant_id, tenant_id)
            summary = db_instance.execute_query_safe(failure_summary_query, summary_params)

            return jsonify({
                "failures": rows,
                "summary": summary
            })

        except Exception as e:
            appLogger.error({
                "event": "get_failure_analysis",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    # ─────────────────────────────────────────────────────────────
    # TENANT OVERVIEW
    # ─────────────────────────────────────────────────────────────

    def get_tenant_overview(self):
        """
        Overview of all tenants and their usage.
        """
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).isoformat()
            if not end_date:
                end_date = datetime.now().isoformat()

            query = """
                SELECT 
                    tenant_id,
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(DISTINCT run_id) as total_runs,
                    COUNT(*) as total_steps,
                    MIN(created_at) as first_activity,
                    MAX(created_at) as last_activity
                FROM agent_run_steps
                WHERE created_at BETWEEN %s AND %s
                GROUP BY tenant_id
                ORDER BY total_runs DESC
            """

            params = (start_date, end_date)
            rows = db_instance.execute_query_safe(query, params)

            return jsonify({
                "tenants": rows
            })

        except Exception as e:
            appLogger.error({
                "event": "get_tenant_overview",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500
        