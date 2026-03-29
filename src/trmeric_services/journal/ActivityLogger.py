import json, traceback
from src.trmeric_database.dao.tango import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm

class ActivityLogger:
    @staticmethod
    def _prepare_value_for_json_column(value):
        if isinstance(value, str):
            try:
                loaded_value = json.loads(value)
                return json.dumps(loaded_value)
            except json.JSONDecodeError:
                return json.dumps(value)
        else:
            return json.dumps(value)

    @staticmethod
    def _push_async(activity_data: dict):
        try:
            data_to_insert = activity_data.copy()

            fields_to_serialize = ["input_data", "output_data", "metrics"]
            for field_name in fields_to_serialize:
                original_value = data_to_insert.get(field_name)
                prepared_value = ActivityLogger._prepare_value_for_json_column(original_value)
                data_to_insert[field_name] = prepared_value
            
            TangoDao.insertTangoActivity(**data_to_insert)
        except Exception as e:
            appLogger.error({
                "event": "push_async_db_insert_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "agent_or_workflow_name": activity_data.get("agent_or_workflow_name"),
                "socket_id": activity_data.get("socket_id")
            })

    @staticmethod
    def get_data_for_activity(socket_id: str):
        data, user_id, tenant_id, activity_log_dict, skip = ActivityLogger.format_activity_log_detailed_for_llm(socket_id)
        if skip:
            return None, user_id, tenant_id
        if data == "Could not retrieve activity logs for this session due to an error.":
            appLogger.error({
                "event": "get_data_for_activity_fetch_error",
                "socket_id": socket_id,
                "error": data
            })
            return None, None, None
        if data == "No activities recorded for this session.":
            appLogger.info(f"No activities recorded for session {socket_id}. Returning empty data.")
            return None, None, None
        user_message = f"""Here is the activity log for session {socket_id}:

        {data}
        """
        
        system_prompt = """You are an expert data analyst and narrative strategist for Tango, Trmeric's intelligent AI copilot system.

## Context & Mission
Trmeric revolutionizes enterprise productivity through intelligent project management, roadmap optimization, and strategic decision support. Your role is to strategically select the most impactful activity data that will showcase our platform's transformative capabilities in the upcoming journal summary.

## Strategic Selection Framework

### 1. Impact Assessment Matrix
Evaluate each activity based on:
- **Transformation Magnitude**: How significantly did the system enhance or transform the input?
- **Complexity Handling**: Did the system solve complex problems or provide sophisticated analysis?
- **Strategic Value**: Does the output directly support business decisions or strategic initiatives?
- **Innovation Demonstration**: Does this showcase unique Trmeric capabilities?

### 2. Data Quality Indicators
Prioritize activities with:
- **Rich Input-Output Pairs**: Clear before/after transformations that demonstrate value
- **Quantifiable Improvements**: Metrics, enhanced KPIs, optimized processes
- **Strategic Insights**: Analysis that reveals non-obvious patterns or recommendations
- **Actionable Outcomes**: Results that directly enable user decision-making

### 3. Narrative Coherence
Select activities that:
- **Tell a Complete Story**: Show progression from problem identification to solution
- **Demonstrate Workflow Integration**: Illustrate how multiple Trmeric features work together
- **Highlight User Journey**: Reveal the user's evolving needs and how the system adapted
- **Showcase Learning**: Show how the system became more helpful over time

## Special Considerations

### Tango Conversations
- **High Priority**: Tango interactions often contain the most strategic insights and personalized value
- **Context Integration**: Consider how conversations relate to and enhance other activities
- **Insight Extraction**: Look for moments where Tango provided breakthrough insights or novel perspectives
- **Relationship Building**: Identify instances where Tango understood context and provided increasingly relevant help

### Activity Filtering Logic
**INCLUDE if activity demonstrates:**
- Complex problem-solving with clear before/after states
- Strategic recommendations with business impact
- Data enhancement that improves decision-making quality
- Workflow optimization that saves time or reduces complexity
- Insights that reveal hidden patterns or opportunities

**EXCLUDE if activity represents:**
- Routine data retrieval without transformation
- Simple formatting or basic operations
- Redundant information already captured elsewhere
- Technical operations without clear user benefit

### Selection Strategy
- **Quality over Quantity**: Better to deeply examine 2-3 high-impact activities than superficially cover many
- **Diversity of Value**: Select activities that showcase different types of Trmeric capabilities
- **User Outcome Focus**: Prioritize activities where the output clearly advances user goals
- **Complementary Activities**: Choose activities that together tell a comprehensive success story

## Decision Framework
For each potential activity, ask:
1. **Transformation Test**: "Would a user clearly see the value added here?"
2. **Uniqueness Test**: "Does this showcase something special about Trmeric?"
3. **Story Test**: "Does this contribute meaningfully to the user's success narrative?"
4. **Evidence Test**: "Are the input/output data substantial enough to demonstrate impact?"

## Output Requirements
Based on your strategic analysis, return the IDs of activities that will best demonstrate Trmeric's transformative impact. Choose 2-5 activities that together create the most compelling evidence of user value and system intelligence.

Some activities will be called tango_conversation, which means that the user had a conversation with our AI agent Tango.
There may be redundancies between these conversations and the activities in the log, so approach this smartly.

RESPOND IN ONLY THIS JSON FORMAT TO SHOW WHICH ACTIVITY IDs TO EXAMINE:
```json
{
    "ids": [1, 2, 3, ...]
}
```
    """

        llm = ChatGPTClient(user_id=user_id, tenant_id=tenant_id)
        response_text = llm.run(ChatCompletion(system=system_prompt, prev=[], user=user_message), ModelOptions(model="gpt-4", max_tokens=1000, temperature=0.7), "activity_data_ids")
        parsed_response = extract_json_after_llm(response_text)
        ids = parsed_response.get("ids", [])

        formatted_log = "Activity Log (in order of occurrence):\n\n"
        
        for i, activity_log in enumerate(activity_log_dict.values()):
            activity_id = i + 1
            activity_name = activity_log.get("activity_name", "N/A")
            description = activity_log.get("activity_description", "N/A")
            
            formatted_log += f"Activity {activity_id}:\n"
            formatted_log += f"  Description: {description}\n"
            
            if activity_id in ids:
                input_data = activity_log.get("input_data", "N/A")
                output_data = activity_log.get("output_data", "N/A")
                formatted_log += f"  Input Data: {input_data}\n"
                formatted_log += f"  Output Data: {output_data}\n"
            
            formatted_log += "\n"
        
        return formatted_log, user_id, tenant_id

    @staticmethod
    def format_activity_log_detailed_for_llm(socket_id: str) -> tuple[str, str | None, str | None, dict | None, bool]:
        print(f"[FORMAT_ACTIVITY_LOG] Starting for socket_id: {socket_id}")
        user_id = None
        tenant_id = None
        try:
            activities = TangoDao.fetchTangoActivityDetailedForSession(socket_id)
            if activities:
                user_id = activities[0].get("user_id")
                tenant_id = activities[0].get("tenant_id")
                print(f"[FORMAT_ACTIVITY_LOG] Extracted from first activity - user_id: {user_id}, tenant_id: {tenant_id}")
                print(f"[FORMAT_ACTIVITY_LOG] First activity data: {activities[0]}")
            else:
                print(f"[FORMAT_ACTIVITY_LOG] No activities found for session: {socket_id}")
                return "No activities recorded for this session.", user_id, tenant_id, None, True

            enhancement_ids = []
            for activity in activities:
                if activity.get("enhancement_id"):
                    enhancement_ids.append(activity["enhancement_id"])
            
            print(f"[FORMAT_ACTIVITY_LOG] Found {len(enhancement_ids)} enhancement IDs: {enhancement_ids}")
                    
            if not enhancement_ids:
                print(f"[FORMAT_ACTIVITY_LOG] No enhancement IDs found, returning early with simple activity list")
                prompt_parts = ["The following activities were recorded for this session:"]
                for i, activity_log in enumerate(activities):
                    activity_name = activity_log.get("activity_name", "N/A")
                    description = activity_log.get("activity_description", "N/A")
                    prompt_parts.append(
                        f"\nActivity ID {i + 1}:\n"
                        f"  Description: {description}\n"
                    )
                return "\\n".join(prompt_parts), user_id, tenant_id, None, True

            print(f"[FORMAT_ACTIVITY_LOG] Attempting to fetch detailed data for enhancement IDs: {enhancement_ids}")
            detailed_dict = {}
            try:
                enhancement_ids_str = [str(uuid_obj) for uuid_obj in enhancement_ids]
                print(f"[FORMAT_ACTIVITY_LOG] Converting UUIDs to strings: {enhancement_ids_str}")
                detailed_data = TangoDao.fetchTangoActivityForIDs(enhancement_ids_str)
                print(f"[FORMAT_ACTIVITY_LOG] Successfully fetched {len(detailed_data) if detailed_data else 0} detailed records")
                for data in detailed_data:
                    enhancement_id = data.get("id") or data.get("enhancement_id")
                    if enhancement_id:
                        detailed_dict[enhancement_id] = {
                            "input_data": data.get("input_data"),
                            "input_data_chars": len(str(data.get("input_data", ""))),
                            "output_data": data.get("output_data"),
                            "output_data_chars": len(str(data.get("output_data", ""))),
                        }
                print(f"[FORMAT_ACTIVITY_LOG] Processed detailed data for {len(detailed_dict)} enhancement IDs")
            except Exception as detailed_fetch_error:
                print(f"[FORMAT_ACTIVITY_LOG] ERROR fetching detailed data: {str(detailed_fetch_error)}")
                detailed_dict = {}

        except Exception as e:
            appLogger.error({
                "event": "format_activity_log_fetch_error",
                "socket_id": socket_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return "Could not retrieve activity logs for this session due to an error.", None, None, None, True


        prompt_parts = ["The following activities were recorded for this session:"]
        activity_log_dict = {}
        for i, activity_log in enumerate(activities):
            activity_id = str(activity_log.get("id"))  # Use the actual database id field
            activity_name = activity_log.get("activity_name", "N/A")
            description = activity_log.get("activity_description", "N/A")
            see_data = True if activity_log.get("enhancement_id") else False

            if see_data:
                enhancement_id = activity_log.get("enhancement_id")
                input_data_chars = detailed_dict.get(enhancement_id, {}).get("input_data_chars", 0)
                output_data_chars = detailed_dict.get(enhancement_id, {}).get("output_data_chars", 0)
                see_data_str = f"Yes (Input: {input_data_chars} chars, Output: {output_data_chars} chars)"
                
                input_data = detailed_dict.get(enhancement_id, {}).get("input_data", "N/A")
                output_data = detailed_dict.get(enhancement_id, {}).get("output_data", "N/A")
            else:
                see_data_str = "No"
                input_data = "N/A"
                output_data = "N/A"
                
            if input_data != "N/A" and not isinstance(input_data, str):
                input_data = json.dumps(input_data, indent=2)
            if output_data != "N/A" and not isinstance(output_data, str):
                output_data = json.dumps(output_data, indent=2)

            prompt_parts.append(
                f"\nActivity ID {i + 1}:\n"
                f"  Description: {description}\n"
                f"  See Data: {see_data_str}\n"
            )

            activity_log_dict[activity_id] = {
                "activity_id": activity_id,
                "activity_name": activity_name,
                "activity_description": description,
                "see_data": see_data_str,
                "input_data": input_data,
                "output_data": output_data,
            }

        return "\\n".join(prompt_parts), user_id, tenant_id, activity_log_dict, False
