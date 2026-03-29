import json
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao.tango import TangoDao
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.ActivityLogger import ActivityLogger
from src.trmeric_services.journal.Vectors.VectorDefinitions import vector_definitions

class VectorCategorizer:
    """Categorizes session activities by their impact on different vectors"""
    
    def categorize_activities(self, session_id: str, activities: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Analyze activities and assign each to one or more vectors
        Returns: {vector_name: [activities]} mapping
        """
        if not activities:
            return {}
        
        # Prepare smart vector context for LLM prompt with business focus
        vector_context = {}
        for vector_name, definition in vector_definitions.items():
            vector_context[vector_name] = {
                "business_focus": definition.get("short_description", ""),
                "key_responsibilities": definition.get("introduction", "").split("KEY RESPONSIBILITIES:")[1].split("Success is measured by:")[0].strip() if "KEY RESPONSIBILITIES:" in definition.get("introduction", "") else "",
                "success_metrics": definition.get("introduction", "").split("Success is measured by:")[1].strip() if "Success is measured by:" in definition.get("introduction", "") else "",
                "json_schema": definition.get("json_schema", {}),
                "special_notes": definition.get("special_notes", "")
            }

        activities_text = self._format_full_activities_for_llm(activities)

        system_prompt = f"""
You are an expert at analyzing user activities and categorizing them by their impact on organizational transformation vectors. You need to assign each activity to one or more vectors based on their transformational business impact and the specific capabilities each vector delivers.

VECTOR DEFINITIONS (Business Context & Success Metrics):
{json.dumps(vector_context, indent=2)}

ASSIGNMENT RULES:
1. Focus on BUSINESS IMPACT: Consider which business capabilities and KPIs each activity impacts
2. Match activities to vectors based on SUCCESS METRICS: Map activities to vectors whose success metrics they influence
3. Consider KEY RESPONSIBILITIES: Activities should align with the specific responsibilities of each vector
4. Most activities should be assigned to a vector, though there may be exceptions for purely administrative tasks
5. Activities can impact multiple vectors (30% of cases) when they deliver cross-cutting business value
6. Look at activity name, description, input data, and output data for business transformation indicators
7. Prioritize vectors based on PRIMARY business impact, then consider secondary impacts

Return a JSON object mapping each vector name to an array of activity IDs that impact that vector:
{{
    "value_vector": ["1"],
    "strategy_planning_vector": ["1", "2"],
    "execution_vector": ["5", "4"],
    "portfolio_management_vector": ["3"],
    "learning_vector": ["1"]
}}

IMPORTANT: 
- Use activity IDs as strings (e.g., "1", "2", "3")
- An activity can appear in multiple vectors if it has multiple impacts
- Do not leave any meaningful activity uncategorized
- Consider the full context of what each activity accomplishes
"""
        
        user_message = f"Analyze and categorize these session activities by their vector impacts:\n\n{activities_text}"
        
        try:
            llm = ChatGPTClient()
            response = llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_message),
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2),
                "vector_business_categorization"
            )
            
            vector_assignments = extract_json_after_llm(response)
            
            # Convert activity IDs back to full activity objects
            vector_groups = {}
            for vector_name, activity_ids in vector_assignments.items():
                if vector_name in vector_definitions:  # Validate vector name
                    vector_groups[vector_name] = []
                    for activity_id in activity_ids:
                        try:
                            activity_index = int(activity_id) - 1
                            if 0 <= activity_index < len(activities):
                                vector_groups[vector_name].append(activities[activity_index])
                        except (ValueError, IndexError):
                            continue
            
            return vector_groups
            
        except Exception as e:
            appLogger.error({
                "event": "vector_categorization_error",
                "session_id": session_id,
                "error": str(e)
            })
            return {}
    
    def _format_activities_for_llm(self, activities: List[Dict]) -> str:
        """Format activities for LLM processing with previews"""
        formatted = []
        for i, activity in enumerate(activities, 1):
            activity_text = f"Activity {i}:\n"
            activity_text += f"  Name: {activity.get('agent_or_workflow_name', 'N/A')}\n"
            activity_text += f"  Description: {activity.get('description', 'N/A')}\n"
            
            # Include input/output data previews
            if activity.get('input_data'):
                preview = str(activity['input_data'])[:150]
                activity_text += f"  Input: {preview}...\n"
                    
            if activity.get('output_data'):
                preview = str(activity['output_data'])[:150]
                activity_text += f"  Output: {preview}...\n"
                    
            formatted.append(activity_text)
        
        return "\n".join(formatted)
    
    def _format_full_activities_for_llm(self, activities: List[Dict]) -> str:
        """Format complete activities for LLM processing with full data"""
        formatted = []
        for i, activity in enumerate(activities, 1):
            activity_text = f"=== Activity {i} (ID: {i}) ===\n"
            activity_text += f"Name: {activity.get('agent_or_workflow_name', 'N/A')}\n"
            activity_text += f"Description: {activity.get('description', 'N/A')}\n"
            
            # Include full input data
            if activity.get('input_data'):
                activity_text += f"Input Data:\n{str(json.dumps(activity['input_data'], indent=2))[:250]}\n"
            
            # Include full output data  
            if activity.get('output_data'):
                activity_text += f"Output Data:\n{str(json.dumps(activity['output_data'], indent=2))[:250]}\n"
            
            # Include any additional metadata
            if activity.get('status'):
                activity_text += f"Status: {activity['status']}\n"
            if activity.get('metrics'):
                activity_text += f"Metrics: {json.dumps(activity['metrics'], indent=2)}\n"
            
            formatted.append(activity_text)
        
        return "\n\n".join(formatted)


class VectorEntry:
    """Represents a single vector state entry"""
    
    def __init__(self, 
                 entry_id: str,
                 session_id: str,
                 vector_name: str,
                 activities: List[Dict],
                 transformation_data: Dict,
                 created_date: datetime = None):
        self.entry_id = entry_id
        self.session_id = session_id
        self.vector_name = vector_name
        self.activities = activities
        self.transformation_data = transformation_data
        self.created_date = created_date or datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "entry_id": str(self.entry_id),
            "session_id": self.session_id,
            "vector_name": self.vector_name,
            "activities": self.activities,
            "transformation_data": self.transformation_data,
            "created_date": self.created_date.isoformat()
        }


class VectorAnalyzer:
    """Analyzes activities and creates vector transformation data using vector definitions"""
    
    def analyze_vector_activities(self, vector_name: str, activities: List[Dict]) -> Dict:
        """
        Analyze activities for a specific vector and create transformation data
        following the exact JSON schema from vector_definitions
        """
        if not activities or vector_name not in vector_definitions:
            return {}
        
        vector_def = vector_definitions[vector_name]
        schema = vector_def["json_schema"]
        introduction = vector_def["introduction"]
        
        # Get special notes if they exist
        special_notes = vector_def.get("special_notes", "")
        
        # Prepare complete activities data for analysis
        activities_data = self._format_complete_activities(activities)
        
        system_prompt = f"""{introduction}

You are analyzing session activities to create a comprehensive transformation analysis for the {vector_name.upper()}. 

CRITICAL REQUIREMENTS:
1. Follow the JSON schema EXACTLY - every field is required
2. Use specific, concrete examples from the actual activity data provided
3. Focus on BUSINESS IMPACT and quantifiable outcomes
4. Align analysis with the success metrics for this vector
5. Use executive-level language focusing on strategic value
6. Return ONLY valid JSON matching the schema format precisely

JSON SCHEMA TO FOLLOW:
{json.dumps(schema, indent=2)}

{special_notes if special_notes else ""}

BUSINESS-FOCUSED ANALYSIS GUIDELINES:
- "narrative": Write a compelling 2-3 sentence executive summary of business transformation delivered
- Focus on quantifiable business outcomes and KPIs where possible
- Demonstrate alignment with vector success metrics and key responsibilities
- Use professional language suitable for executive reporting
- Emphasize strategic value and competitive advantages gained
- Connect transformation to organizational capability enhancement

CRITICAL ANTI-FABRICATION RULES:
- NEVER invent percentages, metrics, or numbers not present in the actual activity data
- Use actual counts from the data (e.g., "15 projects enhanced") not fabricated percentages
- If schema asks for percentages but no baseline exists, describe capabilities established instead
- Use "enabled tracking of X" rather than "X% improvement" when no measurable baseline available
- DO NOT create realistic-sounding but fake metrics - stick to what the data actually shows
- All other fields: Follow the schema exactly, using concrete examples from the data
- Use professional, business-focused language
- Quantify impacts where possible
- Be specific about capabilities and improvements delivered

COMPLETE ACTIVITY DATA:
{activities_data}

Create a comprehensive {vector_name} transformation analysis that demonstrates the value and capabilities Trmeric delivered through these activities. Return ONLY the JSON object."""
        
        user_message = f"Analyze these activities and create a detailed {vector_name} transformation analysis following the exact JSON schema."
        
        try:
            llm = ChatGPTClient()
            response = llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_message),
                ModelOptions(model="gpt-4o", max_tokens=4000, temperature=0.3),
                f"vector_business_analysis_{vector_name}"
            )
            
            transformation_data = extract_json_after_llm(response)
            
            # Validate that we got the expected schema fields
            if isinstance(transformation_data, dict) and "narrative" in transformation_data:
                return transformation_data
            else:
                appLogger.warning(f"Invalid transformation data structure for {vector_name}")
                return None
            
        except Exception as e:
            appLogger.error({
                "event": "vector_analysis_error",
                "vector_name": vector_name,
                "error": str(e)
            })
            return None
    
    def _format_complete_activities(self, activities: List[Dict]) -> str:
        """Format complete activity data for detailed analysis"""
        formatted_activities = []
        
        for i, activity in enumerate(activities, 1):
            activity_section = f"=== ACTIVITY {i} ===\n"
            activity_section += f"Agent/Workflow: {activity.get('agent_or_workflow_name', 'Unknown')}\n"
            activity_section += f"Description: {activity.get('description', 'No description')}\n"
            
            # Include complete input data
            if activity.get('input_data'):
                activity_section += f"\nINPUT DATA:\n{json.dumps(activity['input_data'], indent=2, ensure_ascii=False)}\n"
            
            # Include complete output data
            if activity.get('output_data'):
                activity_section += f"\nOUTPUT DATA:\n{json.dumps(activity['output_data'], indent=2, ensure_ascii=False)}\n"
            
            # Include status and metrics if available
            if activity.get('status'):
                activity_section += f"\nStatus: {activity['status']}\n"
            
            if activity.get('metrics'):
                activity_section += f"\nMetrics: {json.dumps(activity['metrics'], indent=2)}\n"
            
            # Include any other relevant fields
            for key, value in activity.items():
                if key not in ['agent_or_workflow_name', 'description', 'input_data', 'output_data', 'status', 'metrics']:
                    activity_section += f"{key}: {value}\n"
            
            formatted_activities.append(activity_section)
        
        return "\n\n".join(formatted_activities)

    

class VectorStateManager:
    """Manages vector state processing and storage - simplified core workflow"""
    
    def __init__(self, user_id: int, tenant_id: int):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.categorizer = VectorCategorizer()
        self.analyzer = VectorAnalyzer()

    def process_session_end(self, session_id: str, activity_data: List[Dict] = None):
        """
        Main workflow: Process activities from a completed session into vector entries
        
        Args:
            session_id: The session ID
            activity_data: Required activity data - list of activity dictionaries
        """
        try:
            appLogger.info({
                "event": "vector_processing_start",
                "session_id": session_id,
                "tenant_id": self.tenant_id,
                "user_id": self.user_id
            })
            
            # Validate input
            if not activity_data:
                appLogger.info({
                    "event": "vector_processing_skipped_no_data",
                    "session_id": session_id
                })
                return
                
            if not isinstance(activity_data, list) or len(activity_data) == 0:
                appLogger.info({
                    "event": "vector_processing_skipped_empty_activities",
                    "session_id": session_id
                })
                return
            
            # Small, non-verbose log for processing start
            appLogger.info({
                "event": "vector_processing_running",
                "session_id": session_id,
                "activity_count": len(activity_data)
            })
            
            # Step 1: Categorize activities by vector
            vector_groups = self.categorizer.categorize_activities(session_id, activity_data)
            if not vector_groups:
                appLogger.info({
                    "event": "vector_processing_no_categorization",
                    "session_id": session_id
                })
                return
            
            # Step 2: Create vector entries for each affected vector
            entries_created = 0
            for vector_name, activities in vector_groups.items():
                if not activities:
                    appLogger.debug(f"Skipping {vector_name} (no activities)")
                    continue
                try:
                    appLogger.info({
                        "event": "creating_vector_entry",
                        "vector_name": vector_name,
                        "activity_count": len(activities)
                    })
                    
                    # Step 3: Analyze activities to create transformation data
                    transformation_data = self.analyzer.analyze_vector_activities(vector_name, activities)
                    activity_id_arr = [activity.get('id') for activity in activities]
                    # Step 4: Create and store vector entry
                    vector_entry = VectorEntry(
                        entry_id=str(uuid.uuid4()),
                        session_id=session_id,
                        vector_name=vector_name,
                        activities=activity_id_arr,
                        transformation_data=transformation_data
                    )
                    
                    # Step 5: Store entry
                    self.store_vector_entry(vector_entry)
                    entries_created += 1
                    appLogger.info({
                        "event": "vector_entry_created",
                        "vector_name": vector_name,
                        "entry_id": vector_entry.entry_id
                    })
                    
                except Exception as e:
                    appLogger.error({
                        "event": "vector_entry_creation_error",
                        "session_id": session_id,
                        "vector_name": vector_name,
                        "error": str(e)
                    })
            
            appLogger.info({
                "event": "vector_processing_complete",
                "session_id": session_id,
                "entries_created": entries_created,
                "vectors_processed": list(vector_groups.keys())
            })
            
        except Exception as e:
            appLogger.error({
                "event": "process_session_end_error",
                "session_id": session_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    
    def store_vector_entry(self, vector_entry: VectorEntry):
        """Store vector entry in database using existing activity tables"""
        try:
            # Store as special activity type with vector prefix
            activity_key = f"vector_entry_{vector_entry.vector_name}_{vector_entry.entry_id}"
            
            # Prepare data for storage
            entry_data = vector_entry.to_dict()
            input_data = ActivityLogger._prepare_value_for_json_column(entry_data)
            output_data = ActivityLogger._prepare_value_for_json_column(vector_entry.transformation_data)
            
            TangoDao.insertTangoActivity(
                socket_id=vector_entry.session_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                agent_or_workflow_name=activity_key,
                input_data=input_data,
                output_data=output_data,
                status="success",
                metrics=ActivityLogger._prepare_value_for_json_column({
                    "vector_name": vector_entry.vector_name,
                    "activity_count": len(vector_entry.activities),
                    "tenant_id": self.tenant_id
                })
            )
            
            appLogger.info({
                "event": "vector_entry_stored",
                "entry_id": vector_entry.entry_id,
                "vector_name": vector_entry.vector_name,
                "session_id": vector_entry.session_id
            })
            
        except Exception as e:
            appLogger.error({
                "event": "store_vector_entry_error",
                "entry_id": vector_entry.entry_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise

    def get_vector_entries(self, vector_name: str, days: int = 7) -> List['VectorEntry']:
        """
        Retrieve vector entries for a specific vector within a time period
        
        Args:
            vector_name: The vector category name
            days: Number of days to look back
            
        Returns:
            List of VectorEntry objects
        """
        try:
            # Calculate date threshold with timezone awareness
            date_threshold = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Build SQL query to fetch vector entries
            query = f"""
                SELECT id, session_id, agent_or_workflow_name, input_data, output_data, created_date, metrics
                FROM tango_activitylog
                WHERE user_id = {self.user_id}
                AND tenant_id = {self.tenant_id}
                AND agent_or_workflow_name LIKE 'vector_entry_{vector_name}_%'
                AND created_date >= '{date_threshold.isoformat()}'
                ORDER BY created_date DESC
            """
            
            results = db_instance.retrieveSQLQueryOld(query)
            
            # Convert database results to VectorEntry objects
            vector_entries = []
            for result in results:
                try:
                    # Parse the stored entry data
                    input_data = json.loads(result['input_data']) if result['input_data'] else {}
                    output_data = json.loads(result['output_data']) if result['output_data'] else {}
                    
                    # Extract entry ID from agent_or_workflow_name
                    entry_id = result['agent_or_workflow_name'].split('_')[-1]
                    
                    # Create VectorEntry object
                    vector_entry = VectorEntry(
                        entry_id=entry_id,
                        session_id=input_data.get('session_id', result['session_id']),
                        vector_name=input_data.get('vector_name', vector_name),
                        activities=input_data.get('activities', []),
                        transformation_data=output_data,
                        created_date=result['created_date'] if isinstance(result['created_date'], datetime) else datetime.fromisoformat(str(result['created_date']).replace('Z', '+00:00'))
                    )
                    
                    # Add additional properties for easier access
                    vector_entry.activity_ids = input_data.get('activities', [])
                    vector_entry.narrative_paragraph = output_data.get('narrative', '')
                    
                    vector_entries.append(vector_entry)
                    
                except Exception as e:
                    appLogger.warning({
                        "event": "vector_entry_parsing_error",
                        "result_id": result.get('id'),
                        "error": str(e)
                    })
                    continue
            
            return vector_entries
            
        except Exception as e:
            appLogger.error({
                "event": "get_vector_entries_error",
                "vector_name": vector_name,
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "error": str(e)
            })
            return []
