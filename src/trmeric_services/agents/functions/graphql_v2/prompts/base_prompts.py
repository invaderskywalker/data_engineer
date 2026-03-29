"""
Prompt Templates for GraphQL V2 Agents

Centralized location for all LLM prompts to enable easy versioning,
A/B testing, and maintenance.
"""

from typing import Dict, Any
from datetime import datetime
import json


class BasePrompts:
    """Base prompt templates reusable across all agents"""
    
    # Few-shot examples for intelligent query planning
    PLANNING_FEW_SHOT_EXAMPLES = """
## Few-Shot Examples of Query Planning

### Example 1: Technology Filter
**User Query:** "Show me all projects using AI technology"
**Understanding:** User wants projects filtered by a related Technology entity
**Plan:**
```json
{
    "vertices_to_query": ["Project", "Technology"],
    "edges_to_query": ["hasTechnology"],
    "entity_ids": [],
    "attributes_to_query": {},
    "filters": {"Technology": {"name": "AI"}},
    "planning_rationale": "Query all accessible projects and traverse hasTechnology edges to find those connected to AI technology. The filter ensures only AI technology is matched."
}
```

### Example 2: Multiple Criteria
**User Query:** "Find projects in the Agile methodology within the Transformation category"
**Understanding:** User wants projects filtered by two criteria: SDLC methodology and category
**Plan:**
```json
{
    "vertices_to_query": ["Project", "SdlcMethod", "ProjectCategory"],
    "edges_to_query": ["hasSdlcMethod", "hasProjectCategory"],
    "entity_ids": [],
    "attributes_to_query": {},
    "filters": {
        "SdlcMethod": {"name": "Agile"},
        "ProjectCategory": {"name": "Transformation"}
    },
    "planning_rationale": "Query projects with filters on two related entities. The system will find projects where hasSdlcMethod points to Agile AND hasProjectCategory points to Transformation."
}
```

### Example 3: Status/State Filter
**User Query:** "Find projects currently in Discovery phase"
**Understanding:** User wants to filter by project status/phase
**Plan:**
```json
{
    "vertices_to_query": ["Project", "Status"],
    "edges_to_query": ["hasStatus"],
    "entity_ids": [],
    "attributes_to_query": {},
    "filters": {"Status": {"name": "Discovery"}},
    "planning_rationale": "Query projects and traverse hasStatus edge to filter by Discovery phase."
}
```

### Example 4: Location Filter
**User Query:** "What projects are located in North America?"
**Understanding:** User wants projects filtered by geographic location
**Plan:**
```json
{
    "vertices_to_query": ["Project", "ProjectLocation"],
    "edges_to_query": ["hasProjectLocation"],
    "entity_ids": [],
    "attributes_to_query": {},
    "filters": {"ProjectLocation": {"name": "North America"}},
    "planning_rationale": "Query all projects and filter by those connected to North America location via hasProjectLocation edge."
}
```

### Example 5: Pattern/Analytics Query
**User Query:** "What technologies are most commonly used across projects?"
**Understanding:** User wants aggregate analysis across all projects
**Plan:**
```json
{
    "vertices_to_query": ["Project", "Technology"],
    "edges_to_query": ["hasTechnology"],
    "entity_ids": [],
    "attributes_to_query": {"Technology": ["name", "id"], "Project": ["id"]},
    "filters": {},
    "planning_rationale": "Query all projects and all their related technologies to analyze distribution. This is an analytics query looking for patterns across the dataset."
}
```
"""
    
    @staticmethod
    def get_planning_prompt(
        entity_type: str,
        query: str,
        schema: Dict[str, Any],
        user_context: str,
        eligible_entity_ids: list,
        current_date: str = None
    ) -> str:
        """
        Generate planning prompt for query intent detection.
        
        Args:
            entity_type: Type of entity ("Project", "Roadmap", etc.)
            query: User's natural language query
            schema: Graph schema dictionary
            user_context: User's context (role, permissions, etc.)
            eligible_entity_ids: List of entity IDs user has access to
            current_date: Current date string
            
        Returns:
            Formatted planning prompt with few-shot examples
        """
        current_date = current_date or datetime.now().date().isoformat()
        
        return f"""
You are an intelligent query planner for a {entity_type} management graph database using GSQL.

**User Query:** "{query}"
**Current Date:** {current_date}
**User Context:** {user_context}
**Accessible {entity_type} IDs:** {eligible_entity_ids[:50]}  # Show first 50 for context

### Graph Schema
{json.dumps(schema, indent=2)}

{BasePrompts.PLANNING_FEW_SHOT_EXAMPLES}

### Task
Your job is to understand the user's intent and plan which vertices, edges, and attributes to query from the graph.

**Step-by-step approach:**

1. **Understand Intent**: What is the user trying to accomplish?
   - Filtering by a specific criterion? (e.g., "projects using React")
   - Looking for multiple criteria? (e.g., "Agile AND Transformation")
   - Analyzing patterns/trends? (e.g., "most common technologies")
   - Status/phase related? (e.g., "currently in progress")

2. **Identify Required Vertices**: Which vertex types are needed to answer this?
   - The primary entity ({entity_type})
   - Related entities to filter/join on (e.g., Technology, Status, Portfolio)

3. **Identify Required Edges**: Which edges connect the vertices?
   - Look at schema for edge relationships

4. **Extract Entity IDs**: Which specific {entity_type} IDs does the user want?
   - If specific IDs mentioned, extract them
   - Otherwise leave empty to query all accessible IDs

5. **Identify Filters**: What are the dynamic filters based on the user's query?
   - Parse the query for keywords indicating filters
   - Map them to vertex attributes
   - Example: "using React" → filters.Technology.name = "React"

6. **Select Attributes**: Which attributes should be returned?
   - Usually empty to return all attributes for the main entity
   - Can be specific if user asks for particular fields

### Output Format (JSON)
```json
{{
    "vertices_to_query": ["Project", "Technology", ...],
    "edges_to_query": ["hasTechnology", ...],
    "entity_ids": ["2473", "2474", ...] or [],
    "attributes_to_query": {{}} or {{"Project": ["id", "title"], ...}},
    "filters": {{
        "Technology": {{"name": "React"}},
        "Status": {{"name": "Active"}},
        ...
    }} or {{}},
    "planning_rationale": "Explanation of your planning decisions",
    "clarification_needed": false,
    "clarification_message": null
}}
```

**Important Guidelines:**
- Be generous with filter identification - if it could be a filter, include it
- If `entity_ids` is empty, the system will query ALL accessible {entity_type} IDs
- Empty dict for `attributes_to_query` means "return all attributes"
- Look at the few-shot examples above for patterns similar to the user's query
- Consider synonyms: "in progress" = filtering by Status, "with X" = filtering by edge, etc.
- Be specific in your rationale for debugging and transparency
"""
    
    @staticmethod
    def get_formatting_prompt(
        query: str,
        query_results: Dict[str, Any],
        user_context: str
    ) -> str:
        """
        Generate formatting prompt for result presentation.
        
        Args:
            query: Original user query
            query_results: Raw query results from graph
            user_context: User's context
            
        Returns:
            Formatted prompt for result formatting
        """
        return f"""
You are a senior analyst helping to present graph query results.

**User Query:** "{query}"
**User Context:** {user_context}

**Query Results:**
{json.dumps(query_results, indent=2)}

### Task
Transform these raw graph results into a clear, executive-level markdown response.

### Guidelines
1. **Understand Intent**: What is the user trying to learn?
2. **Structure Logically**: Group related information together
3. **Highlight Key Insights**: What are the most important findings?
4. **Use Tables**: Present structured data in markdown tables
5. **Be Concise**: Focus on actionable insights, not just data dump
6. **Role-Aware**: Adapt language to the user's role (from context)

### Output Format (Markdown)

## Analysis: [Query Summary]

### Key Insights
- [3-5 bullet points with main takeaways]

### Detailed Findings
[Tables, lists, or structured data presentation]

### Recommendations
[If applicable, suggest next steps or actions]

### Summary
[Brief conclusion]

**Important:**
- Use clear headings
- Format numbers for readability (e.g., "$1,234,567")
- Highlight outliers or notable patterns
- Keep technical jargon minimal
"""
