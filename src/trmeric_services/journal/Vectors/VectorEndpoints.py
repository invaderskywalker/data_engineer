import json
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Vectors.VectorAnalysis import VectorStateManager
from src.trmeric_services.journal.Vectors.VectorDefinitions import vector_definitions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.Database import db_instance


def process_session_vectors(socket_id: str, user_id: int, tenant_id: int, activity_data: List[Dict] = None, vector_activity_data: str = None):
    """
    Process vector analysis when a session ends.
    Main entry point called by session end handlers.
    
    Args:
        socket_id: The session socket ID
        user_id: The user ID  
        tenant_id: The tenant ID
        activity_data: Required activity data (List[Dict] format) - no fallback querying
        vector_activity_data: Unused parameter (kept for backwards compatibility)
    """
    try:
        # Log start at info level instead of verbose prints
        appLogger.info({"event": "process_session_vectors_start", "session_id": socket_id})
        
        # Check if activity_data is provided
        if not activity_data:
            appLogger.info({"event": "process_session_vectors_no_activity_data", "session_id": socket_id})
            return {
                "success": False,
                "message": "No activity data provided for vector processing",
                "session_id": socket_id
            }
        # Initialize vector state manager
        manager = VectorStateManager(user_id, tenant_id)
        
        # Process the session with the activity data
        manager.process_session_end(socket_id, activity_data)
        
        appLogger.info({"event": "process_session_vectors_complete", "session_id": socket_id})
        return {
            "success": True,
            "message": "Session vectors processed successfully",
            "session_id": socket_id
        }
        
    except Exception as e:
        appLogger.error({
            "event": "process_session_vectors_error",
            "socket_id": socket_id,
            "user_id": user_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "success": False,
            "message": f"Error processing session vectors: {str(e)}",
            "session_id": socket_id
        }


def get_vector_counts_by_category(days: int = 7, tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict:
    """
    Get the number of vectors in each category for the past number of days.
    Returns a JSON with each vector mapped to the count and array of activity IDs.
    
    Args:
        days: Number of days to look back (default: 7)
        tenant_id: Optional tenant ID filter
        user_id: Optional user ID filter (requires tenant_id)
        
    Returns:
        Dict containing vector counts and activity IDs for each vector category
    """
    try:
        # Calculate date threshold with timezone awareness
        date_threshold = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Build base query - use timezone-aware comparison
        where_conditions = [
            f"created_date >= '{date_threshold.isoformat()}'",
            "agent_or_workflow_name LIKE 'vector_entry_%'"
        ]
        
        # Add filters
        if tenant_id is not None:
            where_conditions.append(f"tenant_id = {tenant_id}")
        if user_id is not None:
            where_conditions.append(f"user_id = {user_id}")
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
            SELECT agent_or_workflow_name, input_data, output_data, created_date
            FROM tango_activitylog
            WHERE {where_clause}
            ORDER BY created_date DESC
        """
        
        results = db_instance.retrieveSQLQueryOld(query)
        
        # Process results by vector category
        vector_data = {}
        all_vector_names = list(vector_definitions.keys())
        
        # Initialize all vectors with zero counts
        for vector_name in all_vector_names:
            vector_data[vector_name] = {
                "count": 0,
                "activity_ids": [],
                "entries": []
            }
        
        # Process each result
        for result in results:
            try:
                # Extract vector name from agent_or_workflow_name
                # Format: vector_entry_{vector_name}_{entry_id}
                name_parts = result['agent_or_workflow_name'].split('_')
                
                if len(name_parts) >= 3 and name_parts[0] == 'vector' and name_parts[1] == 'entry':
                    vector_name = '_'.join(name_parts[2:-1])  # Everything except the last part (entry_id)
                    
                    if vector_name in vector_data:
                        # Parse input data to get activity IDs - handle both string and dict cases
                        try:
                            if isinstance(result['input_data'], str):
                                input_data = json.loads(result['input_data']) if result['input_data'] else {}
                            else:
                                input_data = result['input_data'] if result['input_data'] else {}
                        except (json.JSONDecodeError, TypeError) as json_err:
                            input_data = {}
                        
                        activities = input_data.get('activities', [])
                        
                        # Update count and activity IDs
                        vector_data[vector_name]["count"] += 1
                        vector_data[vector_name]["activity_ids"].extend(activities)
                        
                        # Add entry metadata
                        vector_data[vector_name]["entries"].append({
                            "entry_id": name_parts[-1],
                            "session_id": input_data.get('session_id', ''),
                            "created_date": result['created_date'],
                            "activity_count": len(activities)
                        })
                        
            except Exception as e:
                appLogger.warning({
                    "event": "vector_count_parsing_error",
                    "result": result.get('agent_or_workflow_name'),
                    "error": str(e)
                })
                continue
        
        # Calculate totals
        total_vector_entries = sum(data["count"] for data in vector_data.values())
        total_activities = sum(len(data["activity_ids"]) for data in vector_data.values())
        
        return {
            "success": True,
            "period": f"Past {days} days",
            "date_range": {
                "from": date_threshold.isoformat(),
                "to": datetime.now().isoformat()
            },
            "filters": {
                "tenant_id": tenant_id,
                "user_id": user_id
            },
            "summary": {
                "total_vector_entries": total_vector_entries,
                "total_activities": total_activities,
                "vectors_with_activity": sum(1 for data in vector_data.values() if data["count"] > 0)
            },
            "vector_data": vector_data,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_vector_counts_error",
            "days": days,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "success": False,
            "error": f"Error retrieving vector counts: {str(e)}",
            "period": f"Past {days} days"
        }


def get_vector_category_summary(vector_name: str, days: int = 7, tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict:
    """
    Get a comprehensive LLM-generated summary for a specific vector category over a time period.
    
    Args:
        vector_name: The specific vector category to analyze
        days: Number of days to look back (default: 7)
        tenant_id: Optional tenant ID filter
        user_id: Optional user ID filter (requires tenant_id)
        
    Returns:
        Dict containing detailed summary and analysis for the vector category
    """
    try:
        # Validate vector name
        if vector_name not in vector_definitions:
            return {
                "success": False,
                "error": f"Invalid vector name: {vector_name}. Valid options: {list(vector_definitions.keys())}"
            }
        
        # Get vector data for the specified category
        vector_counts_data = get_vector_counts_by_category(days, tenant_id, user_id)
        
        if not vector_counts_data.get("success"):
            return vector_counts_data
        
        vector_data = vector_counts_data["vector_data"].get(vector_name, {})
        
        if vector_data.get("count", 0) == 0:
            return {
                "success": True,
                "vector_name": vector_name,
                "period": f"Past {days} days",
                "summary": f"No activity in {vector_name.replace('_', ' ')} over the past {days} days.",
                "activity_count": 0,
                "entry_count": 0,
                "entries": []
            }
        
        # Fetch detailed transformation data for analysis
        date_threshold = datetime.now(timezone.utc) - timedelta(days=days)
        
        where_conditions = [
            f"created_date >= '{date_threshold.isoformat()}'",
            f"agent_or_workflow_name LIKE 'vector_entry_{vector_name}_%'"
        ]
        
        if tenant_id is not None:
            where_conditions.append(f"tenant_id = {tenant_id}")
        if user_id is not None:
            where_conditions.append(f"user_id = {user_id}")
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
            SELECT agent_or_workflow_name, input_data, output_data, created_date
            FROM tango_activitylog
            WHERE {where_clause}
            ORDER BY created_date DESC
        """
        
        results = db_instance.retrieveSQLQueryOld(query)
        
        # Collect transformation data for LLM analysis
        transformation_narratives = []
        transformation_details = []
        
        for result in results:
            try:
                # Handle both string and dict cases for JSON data
                try:
                    if isinstance(result['input_data'], str):
                        input_data = json.loads(result['input_data']) if result['input_data'] else {}
                    else:
                        input_data = result['input_data'] if result['input_data'] else {}
                    
                    if isinstance(result['output_data'], str):
                        output_data = json.loads(result['output_data']) if result['output_data'] else {}
                    else:
                        output_data = result['output_data'] if result['output_data'] else {}
                except (json.JSONDecodeError, TypeError) as json_err:
                    input_data = {}
                    output_data = {}
                
                # Extract key transformation data
                narrative = output_data.get('narrative', '')
                transformation_delivered = output_data.get('transformation_delivered', '')
                
                if narrative:
                    transformation_narratives.append(narrative)
                
                transformation_details.append({
                    "date": result['created_date'],
                    "narrative": narrative,
                    "transformation": transformation_delivered,
                    "activity_count": len(input_data.get('activities', [])),
                    "session_id": input_data.get('session_id', '')
                })
                
            except Exception as e:
                appLogger.warning({
                    "event": "transformation_data_parsing_error",
                    "error": str(e)
                })
                continue
        
        # Generate AI-powered summary using LLM
        vector_definition = vector_definitions[vector_name]
        vector_intro = vector_definition.get("introduction", "")
        vector_description = vector_definition.get("short_description", "")
        
        summary_context = f"""
VECTOR ANALYSIS REQUEST:
Vector Category: {vector_name.replace('_', ' ').title()}
Time Period: Past {days} days
Description: {vector_description}

VECTOR CONTEXT:
{vector_intro}

TRANSFORMATION NARRATIVES:
{chr(10).join(f"• {narrative}" for narrative in transformation_narratives[:5])}

DETAILED TRANSFORMATION DATA:
{json.dumps(transformation_details[:3], indent=2)}

DATA SUMMARY:
- Total Vector Entries: {vector_data['count']}
- Total Activities Processed: {len(vector_data['activity_ids'])}
- Time Period: {days} days
"""
        
        system_prompt = f"""You are an expert business analyst specializing in organizational transformation analysis. You need to create a comprehensive summary of vector activity and impact.

Create a detailed, executive-level summary that includes:

1. **Activity Overview**: Summarize the volume and frequency of transformation activities
2. **Key Transformations**: Highlight the most significant capabilities delivered
3. **Impact Analysis**: Explain what these transformations mean for the organization
4. **Trend Analysis**: Identify patterns or trends in the transformation activities
5. **Strategic Value**: Articulate the business value and competitive advantages gained

Focus on:
- Concrete business outcomes and capabilities delivered
- Strategic alignment and organizational impact
- Quantifiable improvements where possible
- Future opportunities enabled by these transformations

Be professional, insightful, and business-focused. Use specific examples from the data provided."""
        
        user_message = f"Analyze and summarize the {vector_name.replace('_', ' ')} transformation activities:\n\n{summary_context}"
        
        try:
            # Generate LLM summary
            llm = ChatGPTClient(user_id=user_id or 0, tenant_id=tenant_id or 0)
            ai_summary = llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_message),
                ModelOptions(model="gpt-4o", max_tokens=1500, temperature=0.6),
                f"vector_category_summary_{vector_name}"
            )
            
        except Exception as e:
            appLogger.error({
                "event": "llm_summary_generation_error",
                "vector_name": vector_name,
                "error": str(e)
            })
            ai_summary = f"Unable to generate AI summary for {vector_name}: {str(e)}"
        
        return {
            "success": True,
            "vector_name": vector_name,
            "vector_description": vector_description,
            "period": f"Past {days} days",
            "date_range": {
                "from": date_threshold.isoformat(),
                "to": datetime.now().isoformat()
            },
            "filters": {
                "tenant_id": tenant_id,
                "user_id": user_id
            },
            "metrics": {
                "entry_count": vector_data['count'],
                "activity_count": len(vector_data['activity_ids']),
                "unique_sessions": len(set(detail['session_id'] for detail in transformation_details if detail['session_id']))
            },
            "ai_summary": ai_summary,
            "transformation_highlights": transformation_narratives[:3],
            "entries": vector_data.get('entries', []),
            "activity_ids": vector_data['activity_ids'],
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_vector_category_summary_error",
            "vector_name": vector_name,
            "days": days,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "success": False,
            "error": f"Error generating vector category summary: {str(e)}",
            "vector_name": vector_name,
            "period": f"Past {days} days"
        }


def get_vector_summary(user_id: int, tenant_id: int, vector_name: str, days: int = 7) -> Dict:
    """
    Get a summary of recent activity in a specific vector with AI-generated insights.
    """
    try:
        manager = VectorStateManager(user_id, tenant_id)
        entries = manager.get_vector_entries(vector_name, days)
        
        if not entries:
            return {
                "vector_name": vector_name,
                "period": f"Past {days} days",
                "summary": f"No activity in {vector_name} over the past {days} days.",
                "activity_sessions": 0,
                "total_activities": 0
            }
        
        # Calculate metrics
        session_ids = set(e.session_id for e in entries)
        total_activities = sum(len(e.activity_ids) for e in entries)
        
        # Generate AI summary
        narratives = [entry.narrative_paragraph for entry in entries[:3]]  # Recent 3
        summary_text = "; ".join(narratives) if narratives else "No detailed narratives available"
        
        return {
            "vector_name": vector_name,
            "period": f"Past {days} days", 
            "summary": summary_text,
            "activity_sessions": len(session_ids),
            "total_activities": total_activities
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_vector_summary_error",
            "user_id": user_id,
            "vector_name": vector_name,
            "error": str(e)
        })
        return {
            "vector_name": vector_name,
            "period": f"Past {days} days",
            "summary": f"Error generating summary: {str(e)}",
            "activity_sessions": 0,
            "total_activities": 0
        }


def get_all_vectors_overview(user_id: int, tenant_id: int, days: int = 7) -> Dict:
    """
    Get an overview across all vectors to show transformation progress.
    """
    try:
        all_vectors = [
            "value_vector",
            "strategy_planning_vector", 
            "execution_vector",
            "portfolio_management_vector",
            "governance_vector",
            "learning_vector"
        ]
        
        vector_summaries = {}
        total_sessions = set()
        total_activities = 0
        
        manager = VectorStateManager(user_id, tenant_id)
        
        # Collect data for each vector
        for vector_name in all_vectors:
            entries = manager.get_vector_entries(vector_name, days)
            
            if entries:
                sessions = set(e.session_id for e in entries)
                activities = sum(len(e.activity_ids) for e in entries)
                
                total_sessions.update(sessions)
                total_activities += activities
                
                vector_summaries[vector_name] = {
                    "activity_count": activities,
                    "session_count": len(sessions),
                    "recent_narrative": entries[0].narrative_paragraph if entries else ""
                }
            else:
                vector_summaries[vector_name] = {
                    "activity_count": 0,
                    "session_count": 0,
                    "recent_narrative": "No recent activity"
                }
        
        # Identify most active vector
        most_active = max(vector_summaries.items(), 
                         key=lambda x: x[1]['activity_count']) if vector_summaries else ("none", {"activity_count": 0})
        
        return {
            "period": f"Past {days} days",
            "total_sessions": len(total_sessions),
            "total_activities": total_activities,
            "vector_summaries": vector_summaries,
            "most_active_vector": most_active[0] if most_active[1]['activity_count'] > 0 else "none",
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_all_vectors_overview_error",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "error": str(e)
        })
        return {
            "period": f"Past {days} days",
            "error": f"Error generating overview: {str(e)}",
            "total_sessions": 0,
            "total_activities": 0
        }


def generate_vector_insights(user_id: int, tenant_id: int, vector_name: str, activities_text: str) -> str:
    """
    Generate AI insights for a specific vector based on activities.
    """
    try:
        vector_def = vector_definitions.get(vector_name, "Unknown vector")
        
        prompt = f"""Analyze these activities for their impact on the {vector_name.replace('_', ' ')} vector.

Vector Definition: {vector_def}

Activities:
{activities_text}

Provide a brief analysis (2-3 paragraphs) covering:
1. How these activities impact this specific vector
2. What capabilities or improvements were delivered
3. Strategic value created in this area

Keep it executive-level and insight-focused."""
        
        llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
        response = llm.run(
            ChatCompletion(system=prompt, prev=[], user=""),
            ModelOptions(model="gpt-4", max_tokens=300, temperature=0.6),
            f"vector_insights_{vector_name}"
        )
        return response.strip()
        
    except Exception as e:
        appLogger.error({
            "event": "generate_vector_insights_error",
            "vector_name": vector_name,
            "error": str(e)
        })
        return f"Unable to generate insights for {vector_name}: {str(e)}"


def get_vector_summary(user_id: int, tenant_id: int, vector_name: str, days: int = 7) -> Dict:
    """
    Get a summary of recent activity in a specific vector with AI-generated insights.
    """
    try:
        manager = VectorStateManager(user_id, tenant_id)
        entries = manager.get_vector_entries(vector_name, days)
        
        if not entries:
            return {
                "vector_name": vector_name,
                "period": f"Past {days} days",
                "summary": f"No activity in {vector_name} over the past {days} days.",
                "activity_sessions": 0,
                "total_activities": 0
            }
        
        # Calculate metrics
        session_ids = set(e.session_id for e in entries)
        total_activities = sum(len(e.activity_ids) for e in entries)
        
        # Generate AI summary
        narratives = [entry.narrative_paragraph for entry in entries[:3]]  # Recent 3
        summary_text = "; ".join(narratives) if narratives else "No detailed narratives available"
        
        return {
            "vector_name": vector_name,
            "period": f"Past {days} days", 
            "summary": summary_text,
            "activity_sessions": len(session_ids),
            "total_activities": total_activities
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_vector_summary_error",
            "user_id": user_id,
            "vector_name": vector_name,
            "error": str(e)
        })
        return {
            "vector_name": vector_name,
            "period": f"Past {days} days",
            "summary": f"Error generating summary: {str(e)}",
            "activity_sessions": 0,
            "total_activities": 0
        }


def get_all_vectors_overview(user_id: int, tenant_id: int, days: int = 7) -> Dict:
    """
    Get an overview across all vectors to show transformation progress.
    """
    try:
        all_vectors = [
            "value_vector",
            "strategy_planning_vector", 
            "execution_vector",
            "portfolio_management_vector",
            "governance_vector",
            "learning_vector"
        ]
        
        vector_summaries = {}
        total_sessions = set()
        total_activities = 0
        
        manager = VectorStateManager(user_id, tenant_id)
        
        # Collect data for each vector
        for vector_name in all_vectors:
            entries = manager.get_vector_entries(vector_name, days)
            
            if entries:
                sessions = set(e.session_id for e in entries)
                activities = sum(len(e.activity_ids) for e in entries)
                
                total_sessions.update(sessions)
                total_activities += activities
                
                vector_summaries[vector_name] = {
                    "activity_count": activities,
                    "session_count": len(sessions),
                    "recent_narrative": entries[0].narrative_paragraph if entries else ""
                }
            else:
                vector_summaries[vector_name] = {
                    "activity_count": 0,
                    "session_count": 0,
                    "recent_narrative": "No recent activity"
                }
        
        # Identify most active vector
        most_active = max(vector_summaries.items(), 
                         key=lambda x: x[1]['activity_count']) if vector_summaries else ("none", {"activity_count": 0})
        
        return {
            "period": f"Past {days} days",
            "total_sessions": len(total_sessions),
            "total_activities": total_activities,
            "vector_summaries": vector_summaries,
            "most_active_vector": most_active[0] if most_active[1]['activity_count'] > 0 else "none",
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        appLogger.error({
            "event": "get_all_vectors_overview_error",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "error": str(e)
        })
        return {
            "period": f"Past {days} days",
            "error": f"Error generating overview: {str(e)}",
            "total_sessions": 0,
            "total_activities": 0
        }


def generate_vector_insights(user_id: int, tenant_id: int, vector_name: str, activities_text: str) -> str:
    """
    Generate AI insights for a specific vector based on activities.
    """
    try:
        vector_def = vector_definitions.get(vector_name, "Unknown vector")
        
        prompt = f"""Analyze these activities for their impact on the {vector_name.replace('_', ' ')} vector.

Vector Definition: {vector_def}

Activities:
{activities_text}

Provide a brief analysis (2-3 paragraphs) covering:
1. How these activities impact this specific vector
2. What capabilities or improvements were delivered
3. Strategic value created in this area

Keep it executive-level and insight-focused."""
        
        llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
        response = llm.run(
            ChatCompletion(system=prompt, prev=[], user=""),
            ModelOptions(model="gpt-4", max_tokens=300, temperature=0.6),
            f"vector_insights_{vector_name}"
        )
        return response.strip()
        
    except Exception as e:
        appLogger.error({
            "event": "generate_vector_insights_error",
            "vector_name": vector_name,
            "error": str(e)
        })
        return f"Unable to generate insights for {vector_name}: {str(e)}"
