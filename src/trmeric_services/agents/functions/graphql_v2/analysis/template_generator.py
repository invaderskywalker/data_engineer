"""
Template Generator

Helper utilities for formatting template and pattern metadata into graph vertex dictionaries.
Converts internal data structures to TigerGraph vertex format.
Entity-specific template generators for projects and roadmaps.
"""
from typing import Dict, Any, List, Tuple
from abc import ABC, abstractmethod
import uuid
import time

# Import schema definitions for vertex types
from src.trmeric_services.agents.functions.graphql_v2.infrastructure.trmeric_schema import (
    PROJECT_TEMPLATE_SCHEMA,
    ROADMAP_TEMPLATE_SCHEMA
)


class BaseTemplateGenerator(ABC):
    """Base class for entity-specific template formatting."""
    
    @abstractmethod
    def format_template_vertex(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, Any]:
        """Format template data for entity type."""
        pass

    @abstractmethod
    def format_full_template_structure(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, List[Dict]]:
        """
        Format full template structure including main vertex and related sub-vertices.
        Returns a dictionary with 'vertices' and 'edges'.
        """
        pass


class ProjectTemplateGenerator(BaseTemplateGenerator):
    """Template formatter for project-based templates."""
    
    def format_template_vertex(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, Any]:
        """
        Format project template data for TigerGraph ProjectTemplate vertex.
        """
        tpl_id = template_data.get("id") or f"{prefix}_{hash(str(template_data))}"
        # Map to ProjectTemplate schema (17 attributes)
        return {
            "id": tpl_id,
            "tenant_id": template_data.get("tenant_id", template_data.get("customer_id", "")),
            "name": template_data.get("name", ""),
            "title": template_data.get("title", template_data.get("name", "")),
            "description": template_data.get("description", ""),
            "start_date": template_data.get("start_date", ""),
            "end_date": template_data.get("end_date", ""),
            "project_type": template_data.get("project_type", ""),
            "sdlc_method": template_data.get("sdlc_method", ""),
            "state": template_data.get("state", ""),
            "project_category": template_data.get("project_category", ""),
            "delivery_status": template_data.get("delivery_status", ""),
            "scope_status": template_data.get("scope_status", ""),
            "spend_status": template_data.get("spend_status", ""),
            "objectives": template_data.get("objectives", ""),
            "org_strategy_align": str(template_data.get("org_strategy_align", "")),
            "total_external_spend": template_data.get("total_external_spend", 0.0)
        }

    def format_full_template_structure(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, List[Dict]]:
        """
        Generate full graph structure for a Project Template.
        """
        vertices = []
        edges = []
        
        # 1. Main ProjectTemplate Vertex
        main_vertex = self.format_template_vertex(template_data, prefix)
        main_id = main_vertex["id"]
        vertices.append({"type": "ProjectTemplate", "id": main_id, "attributes": main_vertex})
        
        # 2. TemplateMilestones
        milestones = template_data.get("milestones", [])
        # If milestones are strings (from LLM), convert to dicts
        if milestones and isinstance(milestones[0], str):
             milestones = [{"name": m, "status": "Planned"} for m in milestones]
             
        for i, ms in enumerate(milestones):
            ms_id = f"{main_id}_ms_{i}"
            ms_attrs = {
                "id": ms_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": ms.get("name", f"Milestone {i+1}"),
                "description": ms.get("description", ""),
                "due_date": ms.get("due_date", ""),
                "status": ms.get("status", "Planned"),
                "completion_percentage": ms.get("completion_percentage", 0.0),
                "weight": ms.get("weight", 0.0),
                "milestone_type": ms.get("milestone_type", "Standard"),
                "phase": ms.get("phase", "")
            }
            vertices.append({"type": "TemplateMilestone", "id": ms_id, "attributes": ms_attrs})
            edges.append({
                "source_type": "ProjectTemplate", "source_id": main_id,
                "target_type": "TemplateMilestone", "target_id": ms_id,
                "edge_type": "hasTemplateMilestone", "attributes": {}
            })

        # 3. TemplateTechnology
        technologies = template_data.get("technologies_used", [])
        if not technologies:
            tech_stack = template_data.get("technology_stack", "")
            if tech_stack:
                technologies = [t.strip() for t in tech_stack.split(",") if t.strip()]
        # technologies might be list of dicts from generalize_cluster: {"technology": name, ...}
        for i, tech in enumerate(technologies):
            tech_name = tech.get("technology") if isinstance(tech, dict) else tech
            if not tech_name: continue
            
            tech_id = f"{main_id}_tech_{i}"
            tech_attrs = {
                "id": tech_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": tech_name,
                "category": tech.get("category", "General") if isinstance(tech, dict) else "General",
                "version": tech.get("version", "") if isinstance(tech, dict) else "",
                "license_type": "Unknown",
                "approved": True
            }
            vertices.append({"type": "TemplateTechnology", "id": tech_id, "attributes": tech_attrs})
            edges.append({
                "source_type": "ProjectTemplate", "source_id": main_id,
                "target_type": "TemplateTechnology", "target_id": tech_id,
                "edge_type": "hasTemplateTechnology", "attributes": {}
            })

        # 4. TemplateTeam (Roles)
        team_roles = template_data.get("team_roles", [])
        # If not found, try team_composition from generalize_cluster
        if not team_roles:
            team_roles = template_data.get("team_composition", [])
        # team_roles might be list of dicts or strings
        for i, role in enumerate(team_roles):
            role_name = role.get("category") if isinstance(role, dict) else role # generalize_cluster uses 'category' for role name in team_composition_dist
            if not role_name: continue
            
            team_id = f"{main_id}_team_{i}"
            team_attrs = {
                "id": team_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": role_name, # Using role name as team name for template
                "description": f"Role: {role_name}",
                "member_count": role.get("count", 1) if isinstance(role, dict) else 1,
                "location": "Remote",
                "skills": []
            }
            vertices.append({"type": "TemplateTeam", "id": team_id, "attributes": team_attrs})
            edges.append({
                "source_type": "ProjectTemplate", "source_id": main_id,
                "target_type": "TemplateTeam", "target_id": team_id,
                "edge_type": "hasTemplateTeam", "attributes": {}
            })

        # 5. TemplateKeyResult
        kpis = template_data.get("key_kpis", [])
        # If not found, try objectives array from LLM output
        if not kpis:
            objectives = template_data.get("objectives", [])
            if objectives and isinstance(objectives, list):
                kpis = objectives if (objectives and isinstance(objectives[0], dict)) else [{"name": obj} for obj in objectives]
        if kpis and isinstance(kpis[0], str):
            kpis = [{"name": k} for k in kpis]
            
        for i, kpi in enumerate(kpis):
            kpi_name = kpi.get("name")
            if not kpi_name: continue
            
            kpi_id = f"{main_id}_kpi_{i}"
            kpi_attrs = {
                "id": kpi_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": kpi_name,
                "description": kpi.get("description", ""),
                "target_value": kpi.get("target_value", 0.0),
                "current_value": 0.0,
                "unit": kpi.get("unit", ""),
                "frequency": "Monthly",
                "owner": "Project Manager"
            }
            vertices.append({"type": "TemplateKeyResult", "id": kpi_id, "attributes": kpi_attrs})
            edges.append({
                "source_type": "ProjectTemplate", "source_id": main_id,
                "target_type": "TemplateKeyResult", "target_id": kpi_id,
                "edge_type": "hasTemplateKeyResult", "attributes": {}
            })

        return {"vertices": vertices, "edges": edges}


class RoadmapTemplateGenerator(BaseTemplateGenerator):
    """Template formatter for roadmap-based templates."""
    
    def format_template_vertex(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, Any]:
        """
        Format roadmap template data for TigerGraph RoadmapTemplate vertex.
        """
        tpl_id = template_data.get("id") or f"{prefix}_{hash(str(template_data))}"
        # Map to RoadmapTemplate schema (27 attributes)
        return {
            "id": tpl_id,
            "tenant_id": template_data.get("tenant_id", template_data.get("customer_id", "")),
            "name": template_data.get("name", ""),
            "title": template_data.get("title", template_data.get("name", "")),
            "description": template_data.get("description", ""),
            "objectives": template_data.get("objectives", ""),
            "start_date": template_data.get("start_date", ""),
            "end_date": template_data.get("end_date", ""),
            "budget": template_data.get("budget", 0.0),
            "category": template_data.get("category", ""),
            "org_strategy_align": str(template_data.get("org_strategy_align", "")),
            "priority": template_data.get("priority", ""),
            "current_state": template_data.get("current_state", ""),
            "roadmap_type": template_data.get("roadmap_type", ""),
            "status": template_data.get("status", ""),
            "visibility": template_data.get("visibility", ""),
            "solution": template_data.get("solution", ""),
            "version": template_data.get("version", ""),
            "owner_id": template_data.get("owner_id", ""),
            "strategic_goal": template_data.get("strategic_goal", ""),
            "time_horizon": template_data.get("time_horizon", ""),
            "review_cycle": template_data.get("review_cycle", ""),
            "tags": template_data.get("tags", []),
            "created_at": template_data.get("created_at", str(int(time.time()))),
            "updated_at": template_data.get("updated_at", str(int(time.time()))),
            "template_source": template_data.get("template_source", "Pattern Analysis"),
            "adoption_count": template_data.get("adoption_count", 0),
            "validity_score": template_data.get("validity_score", 0.0)
        }

    def format_full_template_structure(self, template_data: Dict, prefix: str = "tpl") -> Dict[str, List[Dict]]:
        """
        Generate full graph structure for a Roadmap Template.
        """
        vertices = []
        edges = []
        
        # 1. Main RoadmapTemplate Vertex
        main_vertex = self.format_template_vertex(template_data, prefix)
        main_id = main_vertex["id"]
        vertices.append({"type": "RoadmapTemplate", "id": main_id, "attributes": main_vertex})
        
        # 2. TemplateMilestones (Roadmap milestones)
        milestones = template_data.get("milestones", [])
        if milestones and isinstance(milestones[0], str):
             milestones = [{"name": m, "status": "Planned"} for m in milestones]
             
        for i, ms in enumerate(milestones):
            ms_id = f"{main_id}_ms_{i}"
            ms_attrs = {
                "id": ms_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": ms.get("name", f"Milestone {i+1}"),
                "description": ms.get("description", ""),
                "due_date": ms.get("due_date", ""),
                "status": ms.get("status", "Planned"),
                "completion_percentage": ms.get("completion_percentage", 0.0),
                "weight": ms.get("weight", 0.0),
                "milestone_type": ms.get("milestone_type", "Strategic"),
                "phase": ms.get("phase", "")
            }
            vertices.append({"type": "TemplateMilestone", "id": ms_id, "attributes": ms_attrs})
            edges.append({
                "source_type": "RoadmapTemplate", "source_id": main_id,
                "target_type": "TemplateMilestone", "target_id": ms_id,
                "edge_type": "hasTemplateMilestone", "attributes": {}
            })

        # 3. TemplateScope (from scopes/technologies slot in old generator)
        scopes = template_data.get("technologies_used", []) # Mapped from scopes in old generator
        if not scopes: scopes = template_data.get("scopes", [])
        
        for i, scope in enumerate(scopes):
            scope_name = scope if isinstance(scope, str) else scope.get("name", "Unknown Scope")
            scope_id = f"{main_id}_scope_{i}"
            scope_attrs = {
                "id": scope_id,
                "tenant_id": main_vertex["tenant_id"],
                "name": scope_name,
                "description": f"Scope item: {scope_name}",
                "priority": "Medium",
                "status": "Planned",
                "complexity": "Medium"
            }
            vertices.append({"type": "TemplateScope", "id": scope_id, "attributes": scope_attrs})
            edges.append({
                "source_type": "RoadmapTemplate", "source_id": main_id,
                "target_type": "TemplateScope", "target_id": scope_id,
                "edge_type": "hasTemplateScope", "attributes": {}
            })

        # 4. TemplateConstraint (from constraints/team_roles slot in old generator)
        constraints = template_data.get("team_roles", []) # Mapped from constraints in old generator
        if not constraints: constraints = template_data.get("constraints", [])
        
        for i, constr in enumerate(constraints):
            constr_desc = constr if isinstance(constr, str) else constr.get("description", "Unknown Constraint")
            constr_id = f"{main_id}_constr_{i}"
            constr_attrs = {
                "id": constr_id,
                "tenant_id": main_vertex["tenant_id"],
                "description": constr_desc,
                "constraint_type": "General",
                "impact_level": "Medium",
                "status": "Active"
            }
            vertices.append({"type": "TemplateConstraint", "id": constr_id, "attributes": constr_attrs})
            edges.append({
                "source_type": "RoadmapTemplate", "source_id": main_id,
                "target_type": "TemplateConstraint", "target_id": constr_id,
                "edge_type": "hasTemplateConstraint", "attributes": {}
            })

        # 5. TemplateSolution
        solution_narrative = template_data.get("solution_narrative", "")
        solution_themes = template_data.get("solution_themes", [])
        solution_approaches = template_data.get("solution_approaches", [])
        solution_success_criteria = template_data.get("solution_success_criteria", [])
        
        if solution_narrative or solution_themes or solution_approaches:
            sol_id = f"{main_id}_sol"
            sol_attrs = {
                "id": sol_id,
                "tenant_id": main_vertex["tenant_id"],
                "title": f"Solution for {main_vertex['name']}",
                "description": solution_narrative,
                "solution_approach": "; ".join(solution_approaches) if isinstance(solution_approaches, list) else str(solution_approaches),
                "expected_outcomes": "; ".join(solution_themes) if isinstance(solution_themes, list) else str(solution_themes),
                "success_criteria": "; ".join(solution_success_criteria) if isinstance(solution_success_criteria, list) else str(solution_success_criteria),
                "implementation_steps": "", 
                "created_at": str(int(time.time())),
                "updated_at": str(int(time.time()))
            }
            vertices.append({"type": "TemplateSolution", "id": sol_id, "attributes": sol_attrs})
            edges.append({
                "source_type": "RoadmapTemplate", "source_id": main_id,
                "target_type": "TemplateSolution", "target_id": sol_id,
                "edge_type": "hasTemplateSolution", "attributes": {}
            })

        return {"vertices": vertices, "edges": edges}


class TemplateGenerator:
    """
    Static utility for formatting template and pattern vertices.
    Routes to entity-specific formatters.
    """

    @staticmethod
    def format_full_template_structure(template_data: Dict, entity_type: str = "Project", prefix: str = "tpl") -> Dict[str, List[Dict]]:
        """
        Format full template structure based on entity type.
        """
        if entity_type == "Roadmap":
            generator = RoadmapTemplateGenerator()
        else:
            generator = ProjectTemplateGenerator()
        
        return generator.format_full_template_structure(template_data, prefix)
