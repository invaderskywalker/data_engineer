"""
Roadmap-specific prompt customizations
"""

from .base_prompts import BasePrompts


class RoadmapPrompts(BasePrompts):
    """Prompts specific to Roadmap entity queries"""
    
    ROADMAP_FEW_SHOT_EXAMPLES = """
### Roadmap Query Examples

**Example: Priority Filter**
User: "Show me strategic roadmaps"
→ Understand: "Strategic" maps to high priority/importance
→ vertices: ["Roadmap", "RoadmapPriority"]
→ edges: ["hasRoadmapPriority"]
→ filters: {{"RoadmapPriority": {{"name": "Strategic"}}}}

**Example: Status/State Query**
User: "Which roadmaps are currently in execution?"
→ Understand: User wants roadmaps in specific state
→ vertices: ["Roadmap", "RoadmapStatus"]
→ edges: ["hasRoadmapStatus"]
→ filters: {{"RoadmapStatus": {{"name": "Execution"}}}}

**Example: Constraint-based Query**
User: "Show roadmaps with budget constraints"
→ Understand: User wants roadmaps that have constraints of type "budget"
→ vertices: ["Roadmap", "RoadmapConstraint"]
→ edges: ["hasRoadmapConstraint"]
→ filters: {{"RoadmapConstraint": {{"constraint_type": "budget"}}}}

**Example: Team Composition Query**
User: "Show roadmaps with team allocations"
→ Understand: User wants roadmaps and their associated teams
→ vertices: ["Roadmap", "RoadmapTeam"]
→ edges: ["hasRoadmapTeam"]
→ filters: {{}} (no filter, just show relationships)

**Example: Scope Query**
User: "Find roadmaps with enterprise scope"
→ Understand: User wants roadmaps filtered by scope level
→ vertices: ["Roadmap", "RoadmapScope"]
→ edges: ["hasRoadmapScope"]
→ filters: {{"RoadmapScope": {{"scope_level": "Enterprise"}}}}

**Example: Visibility Query**
User: "Show me all confidential roadmaps"
→ Understand: User wants roadmaps filtered by visibility/access level
→ vertices: ["Roadmap"]
→ Approach: Filter on Roadmap.visibility or similar attribute directly
→ Note: Might be attribute-level filtering if visibility is on Roadmap vertex
"""
    
    @staticmethod
    def get_entity_mapping_hints() -> str:
        """
        Return entity-specific mapping hints for the planner.
        
        Returns:
            Markdown string with mapping examples
        """
        return f"""
### Roadmap-Specific Term Mappings

Common query patterns:
- "roadmap details", "roadmap objectives" → `Roadmap` vertex
- "portfolio" → `Portfolio` vertex via `hasRoadmapPortfolio` edge
- "constraints" → `RoadmapConstraint` vertex via `hasRoadmapConstraint` edge
- "key results", "KPIs" → `RoadmapKeyResult` vertex via `hasRoadmapKeyResult` edge
- "team", "resources" → `RoadmapTeam` vertex via `hasRoadmapTeam` edge
- "scope" → `RoadmapScope` vertex via `hasRoadmapScope` edge
- "priority" → `RoadmapPriority` vertex via `hasRoadmapPriority` edge
- "status" → `RoadmapStatus` vertex via `hasRoadmapStatus` edge

Synonym mapping:
- "strategic", "important", "critical" → High priority
- "in progress", "executing", "active" → Execution state
- "confidential", "restricted", "private" → Visibility/access level
- "enterprise", "company-wide" → Scope level

{RoadmapPrompts.ROADMAP_FEW_SHOT_EXAMPLES}
"""
