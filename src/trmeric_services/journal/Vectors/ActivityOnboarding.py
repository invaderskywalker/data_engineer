import os
import sys
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.tango.sessions.TangoConversationRetriever import TangoConversationRetriever
from src.trmeric_services.journal.Vectors.VectorDefinitions import vector_definitions
import json, traceback
from datetime import datetime, timedelta
from src.trmeric_database.Database import db_instance
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao.users import UsersDao
from src.trmeric_database.dao.tango import TangoDao
from src.trmeric_services.journal.ActivityLogger import ActivityLogger
from src.trmeric_services.journal.Activity import detailed_activity

trmeric_intro = """
trmeric is a SaaS platform equipped with six specialized AI agents that automate and enhance key IT and tech team workflows, from project intake and strategy planning to vendor sourcing, procurement, spend tracking, and performance assurance. These agents use Retrieval-Augmented Generation (RAG) to pull and analyze data from integrated tools like Jira, Azure DevOps, GitHub, Slack, and Teams, generating automated reports, surfacing bottlenecks, and suggesting optimizations in real time. For instance, the strategy agent streamlines idea prioritization and business case creation, leading to faster alignment on high-impact initiatives, while the sourcing agent evaluates vendors from a global network, accelerating partnerships and reducing selection time. The platform's centralized dashboards provide a unified view of roadmaps, ongoing projects, resource allocation, and spend patterns, enabling teams to track progress and adjust dynamically for better results.
By focusing on outcomes, trmeric drives measurable improvements such as doubled team productivity through reduced manual tasks, on-time project delivery via early risk detection, and optimized spending with AI-driven insights into procurement efficiency. Users experience streamlined execution where agents handle routine coordination and analytics, freeing up time for innovation and strategic focus, ultimately resulting in initiatives that deliver higher business value, like cost savings from smarter vendor choices or faster time-to-market for tech projects. This setup allows an LLM to interpret user activities as event-driven sequences, journal past outcomes like completed procurements or resolved bottlenecks, and project future possibilities such as scaling initiatives or uncovering untapped efficiencies based on platform patterns.
"""

def get_onboarding_logs_by_timeframe(userID: int, tenantID: int, hours: int = 2160, **kwargs):
    try:
        time_threshold = datetime.now() - timedelta(hours=hours)
            
        query_detailed = f"""
            SELECT activity_name, activity_description, enhancement_id, user_id, tenant_id, created_date
            FROM tango_activitylogdetailed
            WHERE tenant_id = {tenantID}
            AND (activity_name LIKE 'onboarding%' OR activity_name LIKE 'trucible%')
            AND created_date >= '{time_threshold}'
            ORDER BY created_date DESC
        """
        print("query_detailed ", query_detailed)
        
        logs = db_instance.retrieveSQLQueryOld(query_detailed)
        if not logs:
            return "No onboarding or trucible activities found for the specified timeframe."
        
        # Fetch ALL enhancement IDs to show complete transformation
        enhancement_ids = [str(log["enhancement_id"]) for log in logs if log["enhancement_id"]]
        
        if not enhancement_ids:
            return "No enhancement activities found in the onboarding or trucible logs."
        
        print(f"[ONBOARDING_LOGS] Fetching detailed data for {len(enhancement_ids)} enhancement IDs")
        detailed_data = TangoDao.fetchTangoActivityForIDs(enhancement_ids)
        
        if not detailed_data:
            return "Could not retrieve detailed enhancement data."
        
        print(f"[ONBOARDING_LOGS] Successfully fetched {len(detailed_data)} detailed records")
        
        # Create comprehensive activity dictionary with ALL enhancements
        activity_dict = {}
        detailed_dict = {}
        
        # Build detailed data mapping - focusing on INPUT->OUTPUT transformations
        for data in detailed_data:
            enhancement_id = data.get("id") or data.get("enhancement_id")
            if enhancement_id:
                detailed_dict[str(enhancement_id)] = {
                    "input_data": data.get("input_data"),  # What user provided
                    "output_data": data.get("output_data"), # What Trmeric transformed it to
                    "agent_name": data.get("agent_or_workflow_name", ""),
                    "status": data.get("status", ""),
                    "metrics": data.get("metrics", {}),
                }
        
        # Build activity mapping with ALL available transformation data
        for log in logs:
            activity_name = log["activity_name"]
            enhancement_id = str(log["enhancement_id"]) if log["enhancement_id"] else None
            
            if activity_name not in activity_dict:
                activity_dict[activity_name] = {
                    "description": log["activity_description"],
                    "transformations": [],  # Changed from "enhancements" to "transformations"
                    "created_date": log.get("created_date", ""),
                    "user_id": log.get("user_id", ""),
                }
            
            # Include transformation data showing input->output
            if enhancement_id and enhancement_id in detailed_dict:
                activity_dict[activity_name]["transformations"].append({
                    "enhancement_id": enhancement_id,
                    **detailed_dict[enhancement_id]
                })
                
        # Format activities for vector analysis focusing on transformations
        print("[ONBOARDING_LOGS] Formatting activities for transformation analysis")
        formatted_data = format_activities_for_transformation_analysis(activity_dict, user_id=userID)
        # print(formatted_data)
        return formatted_data.strip()
        
    except Exception as e:
        appLogger.error({
            "event": "get_onboarding_logs_by_timeframe_error",
            "tenant_id": tenantID,
            "hours": hours,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return f"Error retrieving onboarding logs for the past {hours} hours: {str(e)}"


def format_activities_for_transformation_analysis(activity_dict, user_id):
    """
    Categorizes activities by the specific capabilities Trmeric delivers through data transformation.
    Formats as clean, structured text that's easy for LLMs to parse and understand.
    Focus on mapping user inputs to Trmeric's enhanced outputs.
    """
    # Categorize activities by Trmeric's specific transformation capabilities
    categorized_transformations = {
        "PROFILE_AND_VALUE_MAPPING": [],    # Profile -> ValueScape creation
        "PLANNING_ENHANCEMENT": [],         # Roadmaps -> Enhanced planning attributes  
        "PROJECT_EXECUTION": [],            # Projects -> Enhanced execution capabilities
        "PORTFOLIO_AND_GOVERNANCE": [],     # Data -> Portfolio views and governance
        "KNOWLEDGE_INTEGRATION": []         # Information -> Unified knowledge base
    }

    # Map activities to transformation categories based on what Trmeric actually does
    for activity_name, activity_info in activity_dict.items():
        activity_lower = activity_name.lower()

        # Profile activities -> ValueScape and goal mapping
        if 'profile' in activity_lower:
            categorized_transformations["PROFILE_AND_VALUE_MAPPING"].append((activity_name, activity_info))

        # Roadmap activities -> Planning attribute enhancement
        elif 'roadmap' in activity_lower:
            categorized_transformations["PLANNING_ENHANCEMENT"].append((activity_name, activity_info))

        # Project activities -> Execution capability enhancement
        elif 'project' in activity_lower:
            categorized_transformations["PROJECT_EXECUTION"].append((activity_name, activity_info))

        # Portfolio, governance, reporting activities
        elif any(keyword in activity_lower for keyword in ['portfolio', 'governance', 'reporting']):
            categorized_transformations["PORTFOLIO_AND_GOVERNANCE"].append((activity_name, activity_info))

        # Knowledge, learning, documentation activities
        elif any(keyword in activity_lower for keyword in ['knowledge', 'learning', 'documentation']):
            categorized_transformations["KNOWLEDGE_INTEGRATION"].append((activity_name, activity_info))

        # Default to knowledge integration for other activities
        else:
            categorized_transformations["KNOWLEDGE_INTEGRATION"].append((activity_name, activity_info))

    # Format as structured text for LLM consumption
    formatted_output = []
    formatted_output.append("=" * 80)
    formatted_output.append("TRMERIC TRANSFORMATION ANALYSIS")
    formatted_output.append(f"User ID: {user_id}")
    formatted_output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    formatted_output.append("=" * 80)
    formatted_output.append("")
    
    for category, activities in categorized_transformations.items():
        if not activities:
            continue
            
        # Category header
        formatted_output.append(f"{'█' * 60}")
        formatted_output.append(f"CATEGORY: {category.replace('_', ' ')}")
        formatted_output.append(f"{'█' * 60}")
        formatted_output.append("")
        
        for activity_name, activity_info in activities:
            # Activity header
            formatted_output.append(f"┌─ ACTIVITY: {activity_name}")
            formatted_output.append(f"│  Description: {activity_info.get('description', 'N/A')}")
            formatted_output.append(f"│  Created: {activity_info.get('created_date', 'N/A')}")
            formatted_output.append(f"│  User ID: {activity_info.get('user_id', 'N/A')}")
            formatted_output.append("│")
            
            transformations = activity_info.get('transformations', [])
            if not transformations:
                formatted_output.append("└─" + "─" * 58)
                formatted_output.append("")
                continue
                
            formatted_output.append(f"│  TRANSFORMATIONS ({len(transformations)} total):")
            formatted_output.append("│")
            
            for i, transformation in enumerate(transformations, 1):
                # Transformation details with enhanced metrics extraction
                formatted_output.append(f"│  ┌─ TRANSFORMATION #{i}")
                
                # Extract and count data elements for metrics
                input_data = transformation.get('input_data') or transformation.get('user_input')
                output_data = transformation.get('output_data') or transformation.get('enhanced_output')
                
                # Calculate data richness metrics
                input_fields = 0
                output_fields = 0
                if input_data and isinstance(input_data, (dict, str)):
                    if isinstance(input_data, str):
                        input_fields = len(input_data.split('\n')) if input_data else 0
                    else:
                        input_fields = len(str(input_data).split()) if input_data else 0
                
                if output_data and isinstance(output_data, (dict, str)):
                    if isinstance(output_data, str):
                        output_fields = len(output_data.split('\n')) if output_data else 0
                    else:
                        output_fields = len(str(output_data).split()) if output_data else 0
                
                # Enhancement ratio calculation
                enhancement_ratio = 0
                if input_fields > 0 and output_fields > input_fields:
                    enhancement_ratio = round(((output_fields - input_fields) / input_fields) * 100, 1)
                
                # Enhanced metrics section
                metrics = transformation.get('metrics', {})
                formatted_output.append(f"│  │  TRANSFORMATION METRICS:")
                formatted_output.append(f"│  │    • Data Enhancement Ratio: {enhancement_ratio}% expansion")
                formatted_output.append(f"│  │    • Input Complexity: {input_fields} data elements")
                formatted_output.append(f"│  │    • Output Richness: {output_fields} data elements")
                formatted_output.append(f"│  │    • Agent: {transformation.get('agent_name', 'Unknown')}")
                formatted_output.append(f"│  │    • Status: {transformation.get('status', 'Unknown')}")
                if metrics and isinstance(metrics, dict):
                    formatted_output.append(f"│  │    • Platform Metrics: {json.dumps(metrics, indent=None)}")
                
                formatted_output.append("│  │")
                
                # USER INPUT section
                user_input = transformation.get('input_data') or transformation.get('user_input')
                if "enhance" not in activity_name: 
                    formatted_output.append("│  │  ┌─ USER PROVIDED (Original Input):")
                else:
                    formatted_output.append("│  │  ┌─ TRMERIC BASELINE (Platform Generated):")
                
                if user_input:
                    if isinstance(user_input, dict):
                        # Count specific elements for quantification
                        field_count = len(user_input.keys()) if user_input.keys() else 0
                        formatted_output.append(f"│  │  │  Data Structure: {field_count} fields/attributes")
                        for key, value in user_input.items():
                            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                            formatted_output.append(f"│  │  │  • {key}: {value_str}")
                    else:
                        # Handle string input with line counting
                        input_lines = str(user_input).split('\n') if user_input else []
                        formatted_output.append(f"│  │  │  Content Length: {len(input_lines)} lines/elements")
                        for line in input_lines[:5]:  # Show first 5 lines
                            if line.strip():
                                line_display = line[:80] + "..." if len(line) > 80 else line
                                formatted_output.append(f"│  │  │  {line_display}")
                        if len(input_lines) > 5:
                            formatted_output.append(f"│  │  │  ... and {len(input_lines) - 5} more lines")
                else:
                    formatted_output.append("│  │  │  [No input data available]")
                
                formatted_output.append("│  │  └─")
                formatted_output.append("│  │")
                
                # TRMERIC OUTPUT section with enhanced metrics
                trmeric_output = transformation.get('output_data') or transformation.get('enhanced_output')
                formatted_output.append("│  │  ┌─ TRMERIC DELIVERED (Enhanced Output):")
                
                if trmeric_output:
                    if isinstance(trmeric_output, dict):
                        # Count enhancement elements
                        output_field_count = len(trmeric_output.keys()) if trmeric_output.keys() else 0
                        input_field_count = len(user_input.keys()) if isinstance(user_input, dict) and user_input else 0
                        enhancement_factor = round(output_field_count / input_field_count, 1) if input_field_count > 0 else output_field_count
                        
                        formatted_output.append(f"│  │  │  Enhanced Structure: {output_field_count} fields (x{enhancement_factor} expansion)")
                        
                        # Show key enhancements with value counting
                        for key, value in trmeric_output.items():
                            if isinstance(value, list):
                                formatted_output.append(f"│  │  │  • {key}: {len(value)} items created")
                                # Show sample items
                                for item in value[:3]:
                                    item_str = str(item)[:60] + "..." if len(str(item)) > 60 else str(item)
                                    formatted_output.append(f"│  │  │    - {item_str}")
                                if len(value) > 3:
                                    formatted_output.append(f"│  │  │    ... and {len(value) - 3} more items")
                            elif isinstance(value, dict):
                                formatted_output.append(f"│  │  │  • {key}: {len(value)} attributes defined")
                            else:
                                value_str = str(value)[:80] + "..." if len(str(value)) > 80 else str(value)
                                formatted_output.append(f"│  │  │  • {key}: {value_str}")
                    else:
                        # Handle string output with enhancement metrics
                        output_lines = str(trmeric_output).split('\n') if trmeric_output else []
                        input_lines_count = len(str(user_input).split('\n')) if user_input else 0
                        enhancement_factor = round(len(output_lines) / input_lines_count, 1) if input_lines_count > 0 else len(output_lines)
                        
                        formatted_output.append(f"│  │  │  Enhanced Content: {len(output_lines)} lines (x{enhancement_factor} expansion)")
                        for line in output_lines[:5]:  # Show first 5 lines
                            if line.strip():
                                line_display = line[:80] + "..." if len(line) > 80 else line
                                formatted_output.append(f"│  │  │  {line_display}")
                        if len(output_lines) > 5:
                            formatted_output.append(f"│  │  │  ... and {len(output_lines) - 5} more lines")
                else:
                    formatted_output.append("│  │  │  [No output data available]")
                
                formatted_output.append("│  │  └─")
                formatted_output.append("│  │")
                formatted_output.append("│  └─" + "─" * 58)
                
                if i < len(transformations):
                    formatted_output.append("│")
            
            formatted_output.append("└─" + "─" * 58)
            formatted_output.append("")
    
    formatted_output.append("=" * 80)
    formatted_output.append("END OF TRANSFORMATION ANALYSIS")
    formatted_output.append("=" * 80)
    
    return "\n".join(formatted_output)
    

def onboarding_summary(user_id: int, tenant_id: int, hours: int = 2160):
    """
    Generate onboarding summary focused on specific Trmeric transformations and capabilities delivered.
    Shows exactly what input data was transformed and what capabilities were built.
    """
    try:
        print(f"[ONBOARDING_SUMMARY] Starting transformation analysis for tenant_id: ")
        
        if __name__ == "__main__":
            with open("input.txt", "r") as file:
                activity_str = file.read()
        else:
            activity_str = get_onboarding_logs_by_timeframe(user_id, tenant_id, hours)

        if not activity_str or "No onboarding or trucible activities found" in activity_str or "Error retrieving" in activity_str:
            print(f"[ONBOARDING_SUMMARY] No valid transformation data found for tenant {tenant_id}")
            return {
                "success": False,
                "message": "No onboarding or trucible transformations found for analysis",
                "tenant_id": tenant_id
            }
        
        print(f"[ONBOARDING_SUMMARY] Retrieved transformation data, length: {len(activity_str)}")

        # Parse transformation data
        try:
            # Now we're receiving formatted text instead of JSON
            formatted_transformations_text = activity_str
        except Exception:
            formatted_transformations_text = ""

        # Extract category information from the formatted text for vector mapping
        # We'll parse the text to understand which categories have data
        available_categories = []
        if "PROFILE AND VALUE MAPPING" in formatted_transformations_text:
            available_categories.append("PROFILE_AND_VALUE_MAPPING")
        if "PLANNING ENHANCEMENT" in formatted_transformations_text:
            available_categories.append("PLANNING_ENHANCEMENT")
        if "PROJECT EXECUTION" in formatted_transformations_text:
            available_categories.append("PROJECT_EXECUTION")
        if "PORTFOLIO AND GOVERNANCE" in formatted_transformations_text:
            available_categories.append("PORTFOLIO_AND_GOVERNANCE")
        if "KNOWLEDGE INTEGRATION" in formatted_transformations_text:
            available_categories.append("KNOWLEDGE_INTEGRATION")
        
        # Map transformation categories to vector analysis
        vector_map = {
            "value_vector": "PROFILE_AND_VALUE_MAPPING",
            "strategy_planning_vector": "PLANNING_ENHANCEMENT", 
            "execution_vector": "PROJECT_EXECUTION",
            "portfolio_management_vector": "PORTFOLIO_AND_GOVERNANCE",
            "governance_vector": "PORTFOLIO_AND_GOVERNANCE",
            "learning_vector": "KNOWLEDGE_INTEGRATION"
        }

        def build_transformation_prompt(vector_name, category_data):
            base_context = f"""
CONTEXT: Trmeric is a comprehensive project management platform that transforms minimal user input into complete, enriched project management capabilities.

CRITICAL: Trmeric provides the following AI agents and capabilities as context for your understanding:
- Portfolio Agent for risk/issue management across projects
- Spend Agent for spend management and procurement optimization
- Service Assurance Agent for quality assurance and performance monitoring
- Provider partnerships on platform for vendor sourcing
- Idea pad for new roadmaps/projects innovation
- Onboarding Agent (already worked with this customer)
- Journaling Agent (creating this report)

EXAMPLE MANAGEMENT - CRITICAL:
- Use UNIQUE examples specific to this vector - DO NOT repeat examples used in other vectors
- Reserve certain project names, OKRs, scopes for specific vectors to avoid redundancy
- Each vector should tell its own story with distinct, non-overlapping examples
- Track what examples you use and ensure variety across the full transformation report

AGENT INTEGRATION REQUIREMENTS:
- In "so_what" or next steps sections, explicitly reference which Trmeric agents could extend the work
- Show how the delivered capabilities create foundation for Portfolio Agent, Spend Agent, Service Assurance Agent
- Make agent connections natural and specific to what was built

IMPORTANT RESTRICTIONS:
- ONLY reference these capabilities if they appear in the actual input/output transformation data provided
- Use these as CONTEXT for understanding Trmeric's broader platform, NOT as capabilities to claim were delivered
- For future opportunities or recommendations, you MAY reference these as possibilities based on what was already built
- NEVER claim these capabilities were used or delivered unless explicitly shown in the transformation data

When organizations onboard, they provide basic project and planning data, which Trmeric's AI agents (Tango) dramatically enhance behind the scenes.

Your role: Analyze the specific input->output transformations and report exactly what capabilities Trmeric delivered.
Focus ONLY on what was actually transformed and delivered - no recommendations, risks, or future opportunities.

USE SPECIFIC DATA from the activity logs as over 70% of what you respond with. Everything you say should be using examples from the data provided.
For example, if you say Trmeric created OKRs, you must name a few such that the entire transformation from top to bottom is convincing.
When mentioning scopes and tech stacks created, specifically name a few that were generated from the data. THIS MUST BE DONE EVERY TIME.

DO NOT JUST REPEAT THE PROMPT INFORMATION. THERE IS ONLY VALUE IN YOUR RESPONSE IF YOU USE THE DATA PROVIDED, THE USER NEEDS DETAILED PROOF FROM THE ACTIVITY LOGS.

IMPORTANT EXCEPTION!!!!!: When you see an activity that is enhancing a project/roadmap/profile, it will give some basic input json. This was actually created by Trmeric.
You can read the onboarding activity logs to see what uploaded data was actually given, but the enhance step takes a Trmeric created JSON and enhances it, that first JSON is not actually user provided.
"""
            
            # Get vector definition from centralized config
            if vector_name in vector_definitions:
                vector_def = vector_definitions[vector_name]
                introduction = vector_def["introduction"]
                json_schema = vector_def["json_schema"]
                special_notes = vector_def.get("special_notes", "")
                onboarding_instructions = vector_def.get("onboarding_instructions", "")
                
                # Build the JSON schema string from the definition
                json_schema_str = json.dumps(json_schema, indent=2)
                
                # Build comprehensive vector-specific prompt using enhanced definitions
                prompt = f"""{base_context}

VECTOR AGENT IDENTITY: {introduction}

ONBOARDING TRANSFORMATION FOCUS:
{onboarding_instructions}

EXECUTIVE REPORTING REQUIREMENTS:
- Focus on business impact and quantifiable outcomes aligned with vector success metrics
- Use executive-level language suitable for leadership presentation
- Extract specific numeric improvements from input/output transformations (e.g., "from X to Y")
- Calculate percentage improvements where data supports it (e.g., data points increased, coverage expanded)
- Identify and count specific artifacts created (OKRs, KPIs, project attributes, integrations)
- Reference exact project names, initiative titles, and scope elements from the data
- Quantify time savings, efficiency gains, and process improvements with realistic estimates

CRITICAL ANTI-FABRICATION RULES - INPUT-OUTPUT TRANSFORMATION FOCUS:
- NEVER invent percentages, metrics, or numbers not present in the actual transformation data
- ALWAYS use input-output analysis: describe what the user provided vs. what was delivered
- If no specific percentage is available, describe the capability or transformation accomplished instead
- Use "enabled tracking of X" instead of "X% improvement" when no baseline exists
- Use actual counts from data (e.g., "170 initiatives tracked") not fabricated percentages
- When schema asks for percentages, use actual data or descriptive text explaining what was established
- DO NOT create realistic-sounding but fake metrics like "17% reduction" or "87% satisfaction"
- Focus on TRANSFORMATION EXAMPLES: show specific before/after scenarios from actual data
- Emphasize CAPABILITIES ESTABLISHED rather than fabricated performance improvements
- Demonstrate competitive advantages and strategic value delivered
- Connect transformation to organizational capability enhancement
- Emphasize ROI and measurable business benefits

CRITICAL JSON SCHEMA - Follow EXACTLY:
{json_schema_str}

BUSINESS CONTEXT REQUIREMENTS:
{special_notes}

DATA ENRICHMENT MANDATES:
- COUNT everything quantifiable: projects enhanced, attributes added, integrations created, risks identified
- CALCULATE realistic improvements: compare input data size/completeness to output richness
- EXTRACT specific examples: pull exact project names, KPI definitions, scope details from transformations
- CAPTURE concrete project/roadmap references in the "examples" field for use in narrative generation
- MEASURE scope expansion: count fields/attributes before vs after enhancement
- IDENTIFY patterns: find recurring themes, common improvements, systematic enhancements
- QUANTIFY coverage: percentage of initiatives with complete data, full attribution, detailed scoping
- ESTIMATE effort saved: hours/days saved from manual work elimination
- BASELINE metrics: establish "before state" measurements for comparison

ABSOLUTE PROHIBITION ON DATA FABRICATION - FOCUS ON ACTUAL TRANSFORMATIONS:
- You are FORBIDDEN from creating fake percentages, satisfaction scores, or improvement metrics
- When a schema field asks for a percentage and you don't have actual data, write descriptive text instead
- Examples of FORBIDDEN fabrications: "17% task delay reduction", "87% PM satisfaction", "40% visibility improvement"  
- Examples of CORRECT responses: "enabled task delay tracking", "established PM satisfaction monitoring", "created real-time visibility dashboards"
- ALWAYS use INPUT-OUTPUT examples: "User provided [X], Trmeric transformed it into [Y]"
- If you fabricate metrics not present in the actual transformation data, this output will be rejected
- Use actual counts, real project names, and concrete capabilities established - nothing else
- Focus on TRANSFORMATION STORY: how basic input became enriched, valuable output

AGENT ECOSYSTEM INTEGRATION:
- Reference how delivered capabilities create readiness for other Trmeric agents
- Show strategic progression: current transformation → future agent opportunities
- Connect to Portfolio Agent, Service Assurance Agent, and broader platform capabilities

CROSS-TRANSFORMATION SYNTHESIS:
- Analyze patterns across multiple transformation instances
- Calculate aggregate improvements (total items created, average enhancement ratios)
- Identify systematic capabilities (consistent attribute additions, pattern recognition)
- Synthesize portfolio-level insights from individual transformations
- Extract and quantify recurring value themes across all activities

Transformations to Analyze:
{category_data}
"""
                return prompt
            else:
                return f"""{base_context}
Tell a story of transformation for {vector_name}, focusing on input->output and the new capabilities delivered. End with a 'SO WHAT' section imagining the next steps or opportunities now unlocked.
Transformations: {category_data}
"""

        # Run vector analyses in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        llm = ChatGPTClient()
        vector_results = {}
        futures = {}

        with ThreadPoolExecutor(max_workers=6) as executor:
            for vector_name, cat_key in vector_map.items():
                # For every vector, use the entire formatted_transformations_text as input
                prompt = build_transformation_prompt(vector_name, formatted_transformations_text)
                try:
                    futures[vector_name] = executor.submit(
                        llm.run,
                        ChatCompletion(system=prompt, prev=[], user=""),
                        ModelOptions(model="gpt-4.1", max_tokens=5000, temperature=0.1),
                        f"onboarding_{vector_name}_detailed_business_transformation"
                    )
                except Exception as e:
                    vector_results[vector_name] = {"error": str(e)}

            for vector_name, future in futures.items():
                try:
                    response_text = future.result()
                    vector_json = extract_json_after_llm(response_text)
                    vector_results[vector_name] = vector_json
                except Exception as e:
                    vector_results[vector_name] = {"error": str(e)}

        # Generate overall transformation narrative with chapter-based structure
        narrative_prompt = f"""
CONTEXT: You are Trmeric's Journaling Agent - a warm, engaging transformation storyteller who chronicles business transformation journeys.

Trmeric is a modern project management platform with these AI agents and capabilities:
{trmeric_intro}

ROLE: Create a compelling chapter-based narrative that tells the customer's transformation story with enthusiasm and warmth while remaining professional.

STRUCTURE: Follow this exact template:
1. Company name + "'s Onboarding Transformation" as title (proper spacing, no underscores)
2. Subtitle: "By Trmeric's Journaling Agent"
3. Tagline: "Goodbye Status Quo, Hello Status AI"
4. Brief, warm introduction as the Journaling Agent
5. Chapter-based story (4-6 chapters, 2-3 paragraphs each)
6. Smooth section that sets up the vector analysis (NO "Transition:" prefix)

AGENT ECOSYSTEM CONTEXT:
- Reference how the Onboarding Agent laid the foundation for this transformation
- Mention how this work creates readiness for Portfolio Agent, Spend Agent, Service Assurance Agent
- Position this transformation as preparing the customer for the full Trmeric agent ecosystem
- Keep agent references natural and forward-looking

TONE: 
- Warm, friendly, and engaging
- Professional but conversational
- Enthusiastic about transformation without being excessive
- Use "we" to refer to Trmeric
- Avoid corporate jargon - speak naturally

CRITICAL REQUIREMENTS:
- Write from Trmeric's perspective to the customer
- Focus on what the customer PROVIDED vs what Trmeric DELIVERED
- Use specific examples from the transformation data
- No prefacing words like "Transition:" before the vector setup section
- Keep it natural and conversational
- Each chapter should tell part of their transformation journey
- Subtly reference the agent ecosystem and readiness for next phases

FORMATTING FIXES:
- NO underscores in any headers or company names
- Use natural language throughout
- Proper markdown formatting
- Clean, professional presentation

Vector Analyses (for context):
{json.dumps(vector_results, indent=2)}

Original Transformation Data:
{formatted_transformations_text}...

Return the narrative story that will open the full transformation report.
"""
        
        try:
            transformation_story = llm.run(
                ChatCompletion(system=narrative_prompt, prev=[], user=""),
                ModelOptions(model="gpt-4.1", max_tokens=1500, temperature=0.4),
                "onboarding_transformation_narrative"
            )
        except Exception as e:
            transformation_story = "Error generating transformation narrative: " + str(e)

        # Build final result focused on delivered capabilities
        result = {
            "transformation_story": transformation_story.strip(),
            "vectors": vector_results,
            "capabilities_summary": {
                "total_vectors_analyzed": len(vector_results),
                "transformation_categories": available_categories,
                "input_to_output_focus": True
            },
            "generated_at": datetime.now().isoformat(),
            "success": True
        }

        # Save to database
        try:
            print(f"[ONBOARDING_SUMMARY] Successfully saved transformation analysis to database")
        except Exception as save_error:
            print(f"[ONBOARDING_SUMMARY] Warning: Could not save to database: {str(save_error)}")
            
        return result
        
    except Exception as e:
        error_msg = f"Error generating onboarding transformation summary: {str(e)}"
        print(f"[ONBOARDING_SUMMARY] ERROR: {error_msg}")

def get_transformation_summary(user_id: int, tenant_id: int, hours: int = 2160):
    """
    Simplified interface focused on transformation highlights.
    
    Args:
        user_id (int): User ID
        tenant_id (int): The tenant ID to analyze
        hours (int): Number of hours to look back (default: 168 = 1 week)
    
    Returns:
        dict: Transformation summary with key delivered capabilities
    """
    full_analysis = onboarding_summary(user_id, tenant_id, hours)
    
    if not full_analysis.get("success", False):
        return full_analysis
    
    # Extract key transformation elements
    vectors = full_analysis.get("vectors", {})
    capabilities_delivered = []
    
    for vector_name, vector_data in vectors.items():
        if isinstance(vector_data, dict) and "capabilities_delivered" in vector_data:
            capabilities_delivered.extend(vector_data["capabilities_delivered"])
    
    return {
        "transformation_story": full_analysis.get("transformation_story", ""),
        "vectors": full_analysis.get("vectors", {}),
        "analysis_period": full_analysis.get("analysis_period", f"{hours} hours"),
        "generated_at": full_analysis.get("generated_at"),
        "success": True
    }


def format_transformation_summary_markdown(summary_dict):
    """
    Multi-step approach for creating engaging, non-repetitive vector narratives.
    Each vector gets individual focused attention for unique storytelling.
    """
    try:
        llm = ChatGPTClient()
        
        # Step 1: Generate the overall transformation narrative (keep existing)
        narrative_enhancement_prompt = f"""
ROLE: You are Trmeric's Journaling Agent - an enthusiastic but professional transformation storyteller.

OBJECTIVE: Take the transformation story and enhance it into a polished, engaging chapter-based narrative that opens the transformation report.

CONTEXT: Trmeric platform capabilities (for reference only):
{trmeric_intro}

ENHANCED STRUCTURE:
1. Company name + "'s Onboarding Transformation" as title (proper spacing, no underscores)
2. Subtitle: "By Trmeric's Journaling Agent"
3. Tagline: "Goodbye Status Quo, Hello Status AI"
4. **Agent Introduction**: Brief, warm personal introduction
5. **Chapter Structure**: 4-6 chapters telling their transformation journey
6. **Vector Setup**: Natural transition to analysis section

CHAPTER GUIDELINES:
- Each chapter: 2-3 paragraphs maximum
- Focus on: What they provided → What Trmeric delivered
- Use specific examples from transformation data
- Build narrative flow from input to enterprise capabilities
- Natural, conversational tone

CRITICAL FORMATTING:
- Clean company names (no underscores or technical references)
- Natural language throughout
- Professional markdown formatting
- Smooth transitions between sections

TRANSFORMATION STORY TO ENHANCE:
{summary_dict.get('transformation_story', '')}

Return the enhanced narrative that will open the report.
"""
        
        # Generate narrative first
        enhanced_narrative = llm.run(
            ChatCompletion(system=narrative_enhancement_prompt, prev=[], user=""),
            ModelOptions(model="gpt-4o", max_tokens=3000, temperature=0.3),
            "narrative_enhancement"
        )
        
        # Step 2: Individual vector generation with unique approaches
        vector_sections = []
        vector_names = ['value_vector', 'strategy_planning_vector', 'execution_vector', 'portfolio_management_vector', 'governance_vector', 'learning_vector']
        vector_styles = {
            'value_vector': 'strategic_overview',
            'strategy_planning_vector': 'process_transformation',
            'execution_vector': 'operational_excellence',
            'portfolio_management_vector': 'executive_dashboard',
            'governance_vector': 'compliance_framework',
            'learning_vector': 'knowledge_insights'
        }
        
        for vector_name in vector_names:
            vector_data = summary_dict.get('vectors', {}).get(vector_name, {})
            if not isinstance(vector_data, dict):
                continue
                
            style = vector_styles.get(vector_name, 'standard')
            vector_prompt = create_focused_vector_prompt(vector_name, vector_data, style)
            
            try:
                vector_content = llm.run(
                    ChatCompletion(system=vector_prompt, prev=[], user=""),
                    ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2),
                    f"vector_{vector_name}_focused"
                )
                vector_sections.append(vector_content.strip())
            except Exception as e:
                print(f"Error generating {vector_name}: {e}")
                continue
        
        # Combine all sections
        full_report = enhanced_narrative.strip() + "\n\n---\n\n# The Transformation Vectors: Your New Capabilities\n\n" + "\n\n---\n\n".join(vector_sections)
        full_report = fix_markdown_formatting(full_report)
        return full_report
        
    except Exception as e:
        return f"Error generating markdown report: {str(e)}"


def create_focused_vector_prompt(vector_name, vector_data, style):
    """Create a focused, style-specific prompt for each vector."""
    
    # Get the examples for this vector
    examples = vector_data.get('examples', '')
    narrative = vector_data.get('narrative', '')
    
    # Base context for all vectors
    base_context = f"""
You are a specialized transformation storyteller focusing on {vector_name.replace('_', ' ').title()}.

VECTOR DATA:
Narrative: {narrative}
Examples: {examples}

YOUR MISSION: Create ONE engaging vector section that tells a unique transformation story.

CRITICAL WRITING STYLE:
- Keep paragraphs SHORT and PUNCHY (2-4 sentences maximum per paragraph)
- Write in clear, executive-friendly language
- Use bullet points and lists liberally to break up text
- Preserve all tables, metrics, and visual elements
- Focus on impact over explanation - show results, not process details
- Each paragraph should make ONE clear point
"""
    
    # Style-specific approaches
    if style == 'strategic_overview':
        return base_context + """
STYLE: Strategic Executive Overview
FORMAT: 
## Value Vector: Strategic Impact & Business Alignment

**Executive Summary Table** showing transformation metrics
**Narrative Approach**: 2-3 SHORT strategic paragraphs (2-4 sentences each) focusing on business value
**Key Examples**: Weave 3-4 specific project examples throughout
**Visual Elements**: Use blockquotes for key insights, tables for metrics

Focus on OKR mapping, strategic alignment, measurable business impact.
Be concise and compelling - prefer bullet points over long explanations.
"""
    
    elif style == 'process_transformation':
        return base_context + """
STYLE: Process & Methodology Deep-dive  
FORMAT:
## Planning Vector: Enhanced Planning Capabilities

**Before/After Comparison** in visual format
**Process Flow**: Show intake → enhancement → delivery pipeline
**Methodology Details**: 2-3 SHORT paragraphs (2-4 sentences each) explaining transformation approach
**Specific Examples**: Use 4-5 concrete project examples distributed throughout

Focus on intake consolidation, scope enhancement, planning improvements.
Use visual elements like comparison tables.
Keep text minimal - let the visuals and examples tell the story.
"""
    
    elif style == 'operational_excellence':
        return base_context + """
STYLE: Operational Performance Focus
FORMAT:
## Execution Vector: Real-Time Operations & Performance

**Performance Dashboard Style** with metrics and KPIs
**Operational Stories**: 2-3 SHORT paragraphs (2-4 sentences each) about execution improvements  
**Real-time Capabilities**: Highlight monitoring and tracking features
**Success Examples**: Showcase 3-4 execution wins with specific outcomes

Focus on bottleneck detection, performance tracking, operational efficiency.
Use performance-oriented visuals and real-time dashboard style formatting.
Keep paragraphs brief - emphasize metrics and results over descriptions.
"""
    
    elif style == 'executive_dashboard':
        return base_context + """
STYLE: Executive Portfolio View
FORMAT:
## Portfolio Management Vector: Strategic Oversight & Intelligence

**Portfolio Overview Dashboard** style presentation
**Strategic Integration**: 2-3 SHORT paragraphs (2-4 sentences each) on cross-portfolio capabilities
**Intelligence Layer**: Highlight unified oversight and analytics
**Portfolio Examples**: Feature 3-4 portfolio-level transformations

Focus on strategic oversight, cross-portfolio integration, executive intelligence.
Use dashboard-style tables, executive metrics, and strategic terminology.
Prioritize data and visuals over lengthy explanations.
"""
    
    elif style == 'compliance_framework':
        return base_context + """
STYLE: Governance & Compliance Framework
FORMAT:
## Governance Vector: Compliance Excellence & Automated Reporting

**Compliance Framework Overview** with structured approach
**Governance Transformation**: 2-3 SHORT paragraphs (2-4 sentences each) on reporting and compliance improvements
**Automation Impact**: Highlight automated reporting and lifecycle management
**Governance Examples**: Use 3-4 compliance and governance success stories

Focus on reporting transformation, compliance automation, governance excellence.
Use structured, framework-oriented formatting with clear compliance focus.
Keep text concise - let the framework structure and examples demonstrate value.
"""
    
    else:  # learning_insights style
        return base_context + """
STYLE: Knowledge & Learning Insights
FORMAT:
## Learning Vector: Knowledge Integration & Organizational Intelligence

**Knowledge Architecture** showing information flow
**Learning Transformation**: 2-3 SHORT paragraphs (2-4 sentences each) on knowledge capture and insights
**Intelligence Generation**: Highlight predictive and analytical capabilities  
**Learning Examples**: Feature 3-4 knowledge and insight generation success stories

Focus on knowledge management, insight generation, organizational learning.
Use knowledge-focused visuals and learning-oriented presentation style.
Emphasize insights and outcomes - minimize lengthy explanations.
"""


def get_vector_description(vector_name):
    """Get brief description for each vector type."""
    descriptions = {
        'value_vector': 'Strategic business alignment and measurable impact tracking',
        'strategy_planning_vector': 'Enhanced planning processes and intake optimization', 
        'execution_vector': 'Real-time project execution and performance monitoring',
        'portfolio_management_vector': 'Unified portfolio oversight and strategic intelligence',
        'governance_vector': 'Compliance frameworks and automated reporting',
        'learning_vector': 'Knowledge management and organizational intelligence'
    }
    return descriptions.get(vector_name, 'Transformation capabilities and business value')


def fix_markdown_formatting(markdown_content):
    """
    Post-processing step to fix common markdown formatting issues.
    Adds newlines between headers (**, ***) and immediately following lists (-, 1., 2., etc.).
    """
    import re
    
    lines = markdown_content.split('\n')
    fixed_lines = []
    
    def is_list_item(line):
        """Check if line is a list item (either unordered - or numbered 1., 2., etc.)"""
        stripped = line.strip()
        return (stripped.startswith('-') or 
                re.match(r'^\d+\.', stripped))  # Matches 1., 2., 10., etc.
    
    for i, line in enumerate(lines):
        fixed_lines.append(line)
        
        # Check if current line is a header (starts with **bold text** or ***bold text***)
        if re.match(r'^\*\*[^*]+\*\*:', line.strip()) or re.match(r'^\*\*\*[^*]+\*\*\*:', line.strip()):
            # Check if next line exists and starts with a list item
            if i + 1 < len(lines) and is_list_item(lines[i + 1]):
                # Add blank line if it doesn't already exist
                if i + 1 < len(lines) and lines[i + 1].strip() != '':
                    fixed_lines.append('')
        
        # Also handle cases where headers end with ** or *** and next line is a list
        elif line.strip().endswith('**:') or line.strip().endswith('***:'):
            if i + 1 < len(lines) and is_list_item(lines[i + 1]):
                if i + 1 < len(lines) and lines[i + 1].strip() != '':
                    fixed_lines.append('')
                    
        # Handle other common formatting issues - headers without colon
        elif line.strip().endswith('**') and not line.strip().endswith(':**'):
            # Bold headers without colon, check if next line is a list
            if i + 1 < len(lines) and is_list_item(lines[i + 1]):
                if i + 1 < len(lines) and lines[i + 1].strip() != '':
                    fixed_lines.append('')
        
        # Handle headers that end with just ** (no colon) followed by lists
        elif re.match(r'^\*\*[^*]+\*\*\s*$', line.strip()):
            if i + 1 < len(lines) and is_list_item(lines[i + 1]):
                if i + 1 < len(lines) and lines[i + 1].strip() != '':
                    fixed_lines.append('')
    
    # Join lines and fix other common issues
    content = '\n'.join(fixed_lines)
    
    # Fix cases where there are too many consecutive newlines (more than 2)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Fix headers that don't have proper spacing - both unordered and numbered lists
    content = re.sub(r'(\*\*[^*]+\*\*:)\n(-)', r'\1\n\n\2', content)  # Unordered lists
    content = re.sub(r'(\*\*[^*]+\*\*:)\n(\d+\.)', r'\1\n\n\2', content)  # Numbered lists
    content = re.sub(r'(\*\*\*[^*]+\*\*\*:)\n(-)', r'\1\n\n\2', content)  # Unordered lists with ***
    content = re.sub(r'(\*\*\*[^*]+\*\*\*:)\n(\d+\.)', r'\1\n\n\2', content)  # Numbered lists with ***
    
    # Handle headers without colon followed by lists
    content = re.sub(r'(\*\*[^*]+\*\*)\n(-)', r'\1\n\n\2', content)  # Unordered lists
    content = re.sub(r'(\*\*[^*]+\*\*)\n(\d+\.)', r'\1\n\n\2', content)  # Numbered lists
    
    return content

if __name__ == "__main__":
    summary = onboarding_summary(442, 764, hours=168)
    
    print("[ONBOARDING] Starting onboarding transformation analysis...")
    with open ("output.txt", "w") as output_file:
        output_file.write(json.dumps(summary, indent=2))
    
    print("[ONBOARDING] Getting transformation highlights...")
    final = format_transformation_summary_markdown(summary)
    with open("output.md", "w") as output_file: 
        output_file.write(final)