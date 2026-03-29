"""
Project-specific prompt customizations
"""

from .base_prompts import BasePrompts


class ProjectPrompts(BasePrompts):
    """Prompts specific to Project entity queries"""
    
    PROJECT_FEW_SHOT_EXAMPLES = """
### Project Query Examples

**Example: Technology Stack Query**
User: "Show me projects using React and Node.js"
→ Understand: User wants projects filtered by multiple technologies
→ vertices: ["Project", "Technology"]
→ edges: ["hasTechnology"]
→ filters: {{"Technology": {{"name": "React"}}}}, can query separately for Node.js
→ Note: Consider whether to join multiple technology filters or use separate queries

**Example: SDLC + Category Query**
User: "Find Agile projects in our Transformation category"
→ Understand: User wants projects filtered by methodology AND category
→ vertices: ["Project", "SdlcMethod", "ProjectCategory"]
→ edges: ["hasSdlcMethod", "hasProjectCategory"]
→ filters: {{"SdlcMethod": {{"name": "Agile"}}, "ProjectCategory": {{"name": "Transformation"}}}}

**Example: Multi-criteria Query**
User: "Show high-spend projects in North America using modern technologies"
→ Understand: User wants projects filtered by spend level, location, and tech
→ vertices: ["Project", "ProjectLocation", "Technology"]
→ edges: ["hasProjectLocation", "hasTechnology"]
→ Approach: Query projects with location filter, then get associated technologies
→ Additional filtering: Might need attribute-level filtering on spend

**Example: Portfolio Composition**
User: "What's in our CRM portfolio?"
→ Understand: User wants projects in a specific portfolio
→ vertices: ["Project", "Portfolio"]
→ edges: ["hasPortfolio"]
→ filters: {{"Portfolio": {{"title": "CRM"}}}}

**Example: Status-based Query**
User: "Show projects currently in Planning phase"
→ Understand: User wants projects filtered by current status/phase
→ vertices: ["Project", "Status"]
→ edges: ["hasStatus"]
→ filters: {{"Status": {{"name": "Planning"}}}}
"""
    
    @staticmethod
    def get_entity_mapping_hints() -> str:
        """
        Return entity-specific mapping hints for the planner.
        
        Returns:
            Markdown string with mapping examples
        """
        return f"""
### Project-Specific Term Mappings

Common query patterns:
- "project details" → `Project` vertex
- "portfolio" → `Portfolio` vertex via `hasPortfolio` edge
- "milestones" → `Milestone` vertex via `hasMilestone` edge
- "status" or "project status" → `Status` vertex via `hasStatus` edge
- "technologies", "tech stack", "tools" → `Technology` vertex via `hasTechnology` edge
- "KPIs", "key results", "metrics" → `KeyResult` vertex via `hasKeyResult` edge
- "project type" → `ProjectType` vertex via `hasProjectType` edge
- "SDLC", "methodology", "development method" → `SdlcMethod` vertex via `hasSdlcMethod` edge
- "category" → `ProjectCategory` vertex via `hasProjectCategory` edge
- "location" → `ProjectLocation` vertex via `hasProjectLocation` edge

{ProjectPrompts.PROJECT_FEW_SHOT_EXAMPLES}
"""
