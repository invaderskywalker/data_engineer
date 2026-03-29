from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.tango.sessions.TangoConversationRetriever import TangoConversationRetriever
import json, traceback
from datetime import datetime, timedelta, timezone
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao.users import UsersDao
from src.trmeric_database.dao.tango import TangoDao
from src.trmeric_services.journal.ActivityLogger import ActivityLogger
from src.trmeric_services.journal.Activity import detailed_activity
from src.trmeric_services.journal.ActivityUtils import _check_meaningful_activities
from src.trmeric_services.journal.Vectors.VectorEndpoints import process_session_vectors
# from src.trmeric_services.journal.Vectors.VectorVisualization import generate_session_vector_visualization


def _format_created_date(created_date):
    """Helper function to format created_date regardless of its type.

    Returns a human-readable UTC timestamp like "2025-08-20 21:38:12 UTC" when possible.
    If created_date is falsy, returns "Recent Activity".
    """
    if not created_date:
        return "Recent Activity"

    try:
        # If it's already a datetime object
        if hasattr(created_date, 'strftime'):
            try:
                dt = created_date
                # If tz-aware, convert to UTC
                if getattr(dt, 'tzinfo', None) is not None:
                    dt = dt.astimezone(timezone.utc)
                    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(created_date)

        # If it's a string, try ISO parsing first
        if isinstance(created_date, str):
            try:
                dt = datetime.fromisoformat(created_date)
                # normalize to UTC if possible
                try:
                    dt_utc = dt.astimezone(timezone.utc)
                    return dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                # fallback: strip timezone and microseconds, replace 'T' with space
                try:
                    date_part = created_date.split('+')[0]
                    if '.' in date_part:
                        date_part = date_part.split('.')[0]
                    date_part = date_part.replace('T', ' ')
                    dt = datetime.strptime(date_part, "%Y-%m-%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return str(created_date)

        # Any other type: stringify
        return str(created_date)

    except Exception:
        return "Recent Activity"


def get_recent_activity_summaries(user_id: int, limit: int = 5, tenant_id: int = None, days: float = None) -> dict:
    """
    Get recent activity summaries for a user from the database using existing DAO.

    Args:
        user_id: User ID to filter by
        limit: Number of summaries to return (default: 5)
        tenant_id: Optional tenant ID filter (note: DAO method may not support this filter)
        days: Optional filter for summaries within last N days (can be fractional, e.g., 0.5)

    Returns:
        Dict with recent session summaries and dates
    """
    try:
        # Forward days (can be float) to the DAO which will apply a time cutoff if provided
        user_session_summaries = UsersDao.fetchUserSessionSummaries(user_id, limit, days)

        if not user_session_summaries:
            return {
                "success": True,
                "count": 0,
                "summaries": [],
                "message": f"No session summaries found for user {user_id}"
            }

        # Parse individual summaries
        parsed_summaries = []
        for session in user_session_summaries:
            output_data = session.get("output_data", "")

            # Parse the output data
            if isinstance(output_data, str):
                try:
                    parsed_data = json.loads(output_data)
                    if isinstance(parsed_data, str):
                        summary_text = parsed_data
                    else:
                        summary_text = str(parsed_data)
                except json.JSONDecodeError:
                    summary_text = output_data
            else:
                summary_text = str(output_data)

            parsed_summaries.append({
                "summary": summary_text,
                "created_date": session.get("created_date"),
                "socket_id": session.get("socket_id"),
                "date_formatted": _format_created_date(session.get("created_date"))
            })

        return {
            "success": True,
            "count": len(parsed_summaries),
            "summaries": parsed_summaries,
            "filters": {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "limit": limit,
                "days": float(days) if days is not None else None
            }
        }

    except Exception as e:
        appLogger.error({
            "event": "get_recent_activity_summaries_error",
            "user_id": user_id,
            "limit": limit,
            "tenant_id": tenant_id,
            "days": days,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "success": False,
            "message": f"Error retrieving activity summaries: {str(e)}",
            "count": 0,
            "summaries": []
        }
                        
def get_user_session_summaries_by_timeframe(userID: int, hours: int = 48, **kwargs):
    try:
        time_threshold = datetime.now() - timedelta(hours=hours)
        
        query = f"""
            SELECT output_data, created_date
            FROM tango_activitylog
            WHERE user_id = {userID}
            AND agent_or_workflow_name = 'activity_session_summary'
            AND created_date >= '{time_threshold}'
            ORDER BY created_date DESC
        """
        
        session_summaries = db_instance.retrieveSQLQueryOld(query)
        
        if not session_summaries:
            return f"No session summaries found for the past {hours} hours."
        
        formatted_summaries = f"Session summaries for the past {hours} hours:\n\n"
        
        for idx, summary_record in enumerate(session_summaries, 1):
            output_data = summary_record.get("output_data", "")
            
            if isinstance(output_data, str):
                try:
                    parsed_data = json.loads(output_data)
                    if isinstance(parsed_data, str):
                        summary_text = parsed_data
                    else:
                        summary_text = str(parsed_data)
                except json.JSONDecodeError:
                    summary_text = output_data
            else:
                summary_text = str(output_data)
            
            formatted_summaries += f"{idx}. {summary_text}\n\n"
        
        return formatted_summaries.strip()
        
    except Exception as e:
        appLogger.error({
            "event": "get_user_session_summaries_by_timeframe_error",
            "user_id": userID,
            "hours": hours,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return f"Error retrieving session summaries for the past {hours} hours."

def session_summary(socket_id: str, user_id: str = None):
    activity_str, logged_user_id, logged_tenant_id = ActivityLogger.get_data_for_activity(socket_id)

    if not activity_str: return
    current_user_id = user_id if user_id else logged_user_id
    current_tenant_id = logged_tenant_id

    if current_user_id and not current_tenant_id:
        try:
            appLogger.info(f"Attempting to fetch tenant_id for user_id: {current_user_id} from UsersDao")
            current_tenant_id = UsersDao.fetchUserTenantID(current_user_id)
            if current_tenant_id:
                appLogger.info(f"Successfully fetched tenant_id: {current_tenant_id} for user_id: {current_user_id}")
            else:
                appLogger.warning(f"Could not fetch tenant_id for user_id: {current_user_id} from UsersDao.")
        except Exception as e:
            appLogger.error({
                "event": "session_summary_fetch_tenant_id_error",
                "user_id": current_user_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    # EARLY MEANINGFUL ACTIVITIES CHECK - Before running expensive LLM for session summary

    # Check if we have meaningful activities BEFORE creating session summary
    has_meaningful_activities = _check_meaningful_activities(activity_str, socket_id, current_user_id, current_tenant_id)
    
    if not has_meaningful_activities:
        appLogger.info({
            "event": "session_summary_skipped_no_meaningful_activities", 
            "socket_id": socket_id,
            "reason": "no_meaningful_activities_early_check",
        })
        return None

    system_prompt = """
You are a narrative architect that transforms technical activity logs into clear, valuable user summaries.

## Your Mission
Convert raw activity data into a concise narrative that shows what the user accomplished and the practical value delivered by Trmeric.

## Analysis Framework

### 1. Activity Pattern Recognition
- **Workflow Mapping**: Identify the sequence of activities and their relationships
- **Goal Identification**: Determine what the user was trying to accomplish
- **Key Moments**: Note where the system provided meaningful assistance or automation

### 2. Value Assessment
- **Task Completion**: What specific tasks were completed successfully
- **System Contribution**: How Trmeric helped (data processing, analysis, automation, etc.)
- **Practical Benefits**: Time saved, complexity reduced, or quality improved
- **Concrete Outcomes**: Specific deliverables or insights generated

### 3. Impact Documentation
- **Immediate Results**: What was accomplished in this session
- **Practical Applications**: How the outputs can be used moving forward
- **Process Improvements**: Any workflow efficiencies gained

## Special Handling Instructions

### Tango Conversations
- **Focus on Insights**: Highlight useful information or guidance provided
- **Knowledge Value**: Note any learning or problem-solving that occurred
- **Avoid Duplication**: Reference overlapping activities without repeating details

### Activity Prioritization
- **Meaningful Actions**: Focus on activities that produced tangible outputs
- **Logical Grouping**: Organize related activities into coherent workflow steps
- **Completion Status**: Clearly indicate what succeeded vs. what encountered issues

## Language Guidelines

### Tone and Style
- **Professional but Natural**: Avoid hyperbolic terms like "prowess," "revolutionize," "transformative"
- **Specific and Factual**: Use concrete details rather than vague claims
- **User-Focused**: Frame benefits in practical terms the user can relate to
- **Balanced**: Acknowledge both successes and any limitations encountered

### Words to Avoid
- "Embarked on a journey," "prowess," "revolutionary," "transformative"
- "Elite," "masterful," "exceptional," "groundbreaking"
- Phrases that overstate routine technical operations

### Preferred Language
- "Completed," "processed," "analyzed," "generated," "configured"
- "Successfully," "efficiently," "accurately," "effectively"
- Focus on what was accomplished rather than how "intelligent" the system is

## Quality Standards

### Content Validation
Before finalizing, ensure your summary:
✓ Accurately reflects what actually happened
✓ Provides clear value without exaggeration
✓ Uses specific examples from the session
✓ Maintains professional credibility
✓ Focuses on user benefits and practical outcomes

### Narrative Structure
1. **Context**: Brief setup of what the user was working on
2. **Process**: Key activities and system contributions
3. **Results**: Specific outcomes and deliverables
4. **Value**: Practical benefits for the user

## Output Format
Return your output in this JSON structure:
```json
{
    "summary": "A clear, factual narrative (150-300 words) that describes what the user accomplished with Trmeric's assistance, focusing on practical value and concrete outcomes."
}
    """
    
    user_message = f"""
    Here is the activity log:
    {activity_str}
    """
    llm = ChatGPTClient(user_id=current_user_id, tenant_id=current_tenant_id) 
    
    response_text = llm.run(ChatCompletion(system=system_prompt, prev=[], user=user_message), ModelOptions(model="gpt-4.1", max_tokens=1000, temperature=0.7), "activity_summary")
    parsed_response = extract_json_after_llm(response_text)
    summary_paragraph = parsed_response.get("summary")

    if summary_paragraph and socket_id and current_user_id and current_tenant_id:
        try:
            appLogger.info(f"Attempting to save activity summary for session: {socket_id}, User: {current_user_id}, Tenant: {current_tenant_id}")
            input_data_for_db = ActivityLogger._prepare_value_for_json_column("")
            output_data_for_db = ActivityLogger._prepare_value_for_json_column(summary_paragraph)
            metrics_for_db = ActivityLogger._prepare_value_for_json_column({})

            TangoDao.insertTangoActivity(
                socket_id=socket_id,
                tenant_id=current_tenant_id,
                user_id=current_user_id,
                agent_or_workflow_name="activity_session_summary",
                input_data=input_data_for_db,
                output_data=output_data_for_db,
                status="success",
                metrics=metrics_for_db
            )
            appLogger.info(f"Successfully saved activity summary for session: {socket_id}")

            # Trigger vector analysis after successful session summary
            try:
                _, _, _, vector_activity_data, _ = ActivityLogger.format_activity_log_detailed_for_llm(socket_id)

                # Convert activity data from dict format to list format for vector processing
                activity_list = []
                if vector_activity_data and isinstance(vector_activity_data, dict):
                    for activity_id, activity_info in vector_activity_data.items():
                        activity_uuid = activity_info.get("activity_id", activity_id)
                        input_data = activity_info.get("input_data", {})
                        output_data = activity_info.get("output_data", {})

                        if isinstance(input_data, str) and input_data not in ["N/A", ""]:
                            try:
                                input_data = json.loads(input_data)
                            except (json.JSONDecodeError, TypeError):
                                input_data = {"raw_text": input_data}
                        elif input_data == "N/A":
                            input_data = {}

                        if isinstance(output_data, str) and output_data not in ["N/A", ""]:
                            try:
                                output_data = json.loads(output_data)
                            except (json.JSONDecodeError, TypeError):
                                output_data = {"raw_text": output_data}
                        elif output_data == "N/A":
                            output_data = {}

                        activity_entry = {
                            "id": activity_uuid,
                            "agent_or_workflow_name": activity_info.get("activity_name", "Unknown"),
                            "description": activity_info.get("activity_description", ""),
                            "input_data": input_data,
                            "output_data": output_data,
                            "status": "success"  # Default status
                        }
                        activity_list.append(activity_entry)

                if activity_list:  # Only process if we have valid activities
                    vector_result = process_session_vectors(
                        socket_id, 
                        current_user_id, 
                        current_tenant_id, 
                        activity_data=activity_list  # Correct parameter name and format
                    )
                else:
                    vector_result = {"success": False, "message": "No activities found for vector processing"}
                if vector_result.get("success"):
                    # Generate vector visualization report after successful vector processing
                    try:
                        pass
                    except Exception as viz_error:
                        appLogger.error({
                            "event": "session_summary_vector_visualization_error",
                            "socket_id": socket_id,
                            "error": str(viz_error),
                            "traceback": traceback.format_exc()
                        })
                else:
                    appLogger.warning(f"Vector analysis failed for session: {socket_id}: {vector_result.get('message')}")
            except Exception as vector_error:
                appLogger.error({
                    "event": "session_summary_vector_analysis_error",
                    "socket_id": socket_id,
                    "error": str(vector_error),
                    "traceback": traceback.format_exc()
                })

        except Exception as e:
            appLogger.error({
                "event": "session_summary_save_db_error",
                "socket_id": socket_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    elif not summary_paragraph:
        appLogger.warning(f"No summary paragraph extracted for session {socket_id}. Cannot save to DB.")
    else:
        appLogger.warning(f"Missing socket_id, user_id, or tenant_id for session {socket_id}. Cannot save summary to DB. UserID: {current_user_id}, TenantID: {current_tenant_id}")

    return parsed_response


def summarize_user_activity(user_id, limit = 5):
    user_session_summaries = UsersDao.fetchUserSessionSummaries(user_id, limit)
    if not user_session_summaries:
        return "You don't have any recent activities with Tango. Time to get started!"
    
    session_str = "Here are the user's recent activities with Tango:\n\n"
    idx = 1
    for session in user_session_summaries:
        summary = session.get["output_data"]
        session_str += f"{idx}. {summary}\n\n"
        idx += 1
    
    system_prompt = """You are a master storyteller and insights synthesizer for Trmeric's user journey analytics.

## Mission
Transform multiple session summaries into a compelling personal narrative that showcases the cumulative value and transformative impact of the user's engagement with Tango and the Trmeric platform.

## Synthesis Framework

### 1. Pattern Recognition & Theme Extraction
- **Recurring Value Themes**: Identify consistent ways Tango has helped across sessions
- **Evolution Tracking**: Show how the user's engagement and benefit has deepened over time
- **Capability Expansion**: Highlight how Tango has expanded the user's strategic thinking and operational efficiency
- **Compound Benefits**: Demonstrate how early sessions enabled more sophisticated later interactions

### 2. Narrative Construction
- **Personal Journey Arc**: Create a coherent story of growth, learning, and achievement
- **Specific Achievement Highlighting**: Use concrete examples, names, and outcomes from the summaries
- **Value Quantification**: Where possible, reference specific improvements, time savings, or strategic gains
- **Future Momentum**: Suggest how this foundation positions the user for continued success

### 3. Personalization & Perspective
- **First-Person Resonance**: Write from the user's perspective so they feel ownership of their achievements
- **Recognition & Validation**: Help the user recognize their smart decisions in leveraging Trmeric
- **Confidence Building**: Frame their journey in terms of growing expertise and strategic thinking
- **Relationship Acknowledgment**: Position Tango as a trusted advisor that has grown to understand their needs

## Content Excellence Standards

### Language & Tone
- **Empowering**: Use achievement-oriented language that makes the user feel accomplished
- **Specific**: Include concrete examples and outcomes rather than generic statements
- **Progressive**: Show development and increasing sophistication over time
- **Personal**: Make it feel like their unique journey, not a template

### Narrative Elements
- **Opening**: Reference their initial engagement or key breakthrough moment
- **Development**: Show progression through multiple value-creating interactions
- **Culmination**: Highlight their most significant recent achievements
- **Forward Look**: Position them for continued success and growth

## Quality Validation
Before finalizing, ensure your summary:
✓ Makes the user feel proud of their strategic use of Trmeric
✓ Contains specific examples that they will recognize and remember
✓ Shows clear progression and compound benefits over time
✓ Positions them as someone who makes smart decisions about tools and efficiency
✓ Creates excitement about continued engagement with the platform

BUT DO NOT overexaggerate to the point of ridicule or make claims that cannot be substantiated by the session summaries.

## Output Format
```json
{
    "summary": "A personally resonant narrative that makes the user feel accomplished, validated, and excited about their continued journey with Trmeric."
}
```

Write this as a personal reflection they would be proud to read in their journal - something that reinforces the value of their time investment and strategic thinking in using Trmeric's capabilities.
    """
    user_message = f"Here is the users session summaries:\n{session_str}\n\nPlease summarize the user's activities in a few sentences, focusing on how Tango assisted them and what value it provided."
    llm = ChatGPTClient(user_id=user_id)
    response_text = llm.run(ChatCompletion(system=system_prompt, prev=[], user=user_message), ModelOptions(model="gpt-4", max_tokens=1000, temperature=0.7), "activity_summary")
    parsed_response = extract_json_after_llm(response_text)
    summary_paragraph = parsed_response.get("summary")
    return summary_paragraph, user_session_summaries

def tango_session_summary(user_id, session_id):
    chats = TangoConversationRetriever.fetchMessagesByUserIDAndSessionID(
        user_id, session_id
    )
    if chats:
        conv = chats.format_conversation_simple()
    else:
        return False
    
    user_prompt = "Here are some of your chats with the user: \n\n" + conv
    system_prompt = """You are an expert conversation analyst specializing in extracting strategic insights and transformative value from AI-human interactions.

## Mission
Analyze this Tango conversation to identify and distill meaningful insights, breakthroughs, solutions, or strategic guidance that created genuine value for the user.

## Analysis Framework

### 1. Value Detection Criteria
**HIGH VALUE - Include in summary:**
- Strategic insights that changed user's perspective or approach
- Novel solutions to complex problems
- Actionable recommendations with clear implementation paths
- Discovery of hidden patterns, opportunities, or risks
- Breakthrough moments where understanding significantly advanced
- Creative ideas or innovative approaches generated
- Important decisions influenced or validated
- Learning that builds user's capabilities or knowledge base

**LOW VALUE - Return empty summary:**
- Basic information lookup or factual Q&A
- Simple clarifications or definitions
- Routine task instructions without strategic context
- Generic advice that could apply to anyone
- Casual conversation without actionable outcomes
- Repetitive or circular discussions

### 2. Insight Extraction Process
- **Context Understanding**: What challenge or opportunity was the user exploring?
- **Tango's Contribution**: What unique perspective, analysis, or solution did Tango provide?
- **Value Realization**: How did this interaction advance the user's goals or understanding?
- **Implementation Readiness**: Did this create actionable next steps or decisions?

### 3. Quality Validation
Before creating a summary, ask:
- "Would this conversation be worth referencing weeks later?"
- "Did Tango provide insights the user couldn't have easily found elsewhere?"
- "Was there a clear 'aha moment' or strategic breakthrough?"
- "Did this conversation change how the user thinks about their challenge?"

## Strategic Focus Areas
When conversations demonstrate value in these domains, prioritize them:
- **Strategic Planning**: Long-term thinking, roadmap development, goal setting
- **Problem Solving**: Complex issue resolution, root cause analysis, solution design  
- **Decision Support**: Weighing options, risk assessment, strategic trade-offs
- **Innovation**: Creative thinking, new approaches, opportunity identification
- **Learning & Development**: Skill building, knowledge transfer, capability enhancement
- **Process Optimization**: Workflow improvement, efficiency gains, best practices

## Output Standards

### Summary Quality Requirements
- **Specific**: Reference concrete outcomes, decisions, or insights
- **Strategic**: Focus on higher-level thinking and long-term impact
- **Actionable**: Highlight what the user can now do differently
- **Unique**: Emphasize insights that wouldn't be obvious or easily found elsewhere

### Decision Logic
- **Rich Conversations**: Create detailed summaries showcasing the strategic value delivered
- **Surface-Level Exchanges**: Return completely empty summary (empty string)
- **Borderline Cases**: Err on the side of empty rather than creating weak summaries

## Output Format
```json
{
    "summary": "A focused summary of strategic insights and breakthrough value, or an empty string if the conversation was surface-level."
}
```

**Critical**: Only create summaries for conversations that delivered genuine strategic value, breakthrough insights, or meaningful problem-solving. When in doubt, return an empty summary.
    """
    
    llm = ChatGPTClient(user_id=user_id)
    response = llm.run(ChatCompletion(system=system_prompt, prev=[], user=user_prompt), ModelOptions(model="gpt-4", max_tokens=1000, temperature=0.7), "activity_summary")
    summary = extract_json_after_llm(response).get("summary", None)
    if summary == "":
        summary = None
        
    if summary:
        detailed_activity(
            activity_name="tango_conversation",
            activity_description="User had a conversation with Trmeric's AI agent Tango, the results of which are summarized: " + summary,
            user_id=user_id,
        )