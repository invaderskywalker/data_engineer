"""
Entity Formatter - Generic converter from database records to graph vertices

Converts project/roadmap database records into TigerGraph vertex + edge structures.
Supports both Projects and Roadmaps with entity-specific field mappings.
"""

from typing import Dict, List, Tuple, Any
from abc import ABC, abstractmethod
from collections import defaultdict
import logging
import traceback
from src.trmeric_api.logging.AppLogger import appLogger

logger = logging.getLogger(__name__)


class BaseEntityFormatter(ABC):
    """Base class for entity formatters (projects, roadmaps, etc.)."""
    
    @abstractmethod
    def get_entity_type(self) -> str:
        """Return vertex type name (e.g., 'Project', 'Roadmap')."""
        pass
    
    @abstractmethod
    def format_entity_vertex(self, entity: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Format entity record into (vertex_id, vertex_attributes) tuple.
        
        Returns:
            (entity_id, attributes_dict)
        """
        pass
    
    @abstractmethod
    def format_related_vertices_and_edges(
        self, 
        entity: Dict[str, Any]
    ) -> Tuple[Dict[str, List], Dict[str, List]]:
        """
        Format related entities (Portfolio, Milestone, etc.) into vertices and edges.
        
        Returns:
            (vertices_dict, edges_dict) where:
            - vertices_dict: {vertex_type: [(id, attrs), ...]}
            - edges_dict: {edge_type: [(from_id, to_id), ...]}
        """
        pass


class ProjectEntityFormatter(BaseEntityFormatter):
    """Formats project database records into graph structure."""
    
    def _extract_string(self, value) -> str:
        """Safely extract a string from value which may be str, list, or dict.

        - If list: take first element and recurse
        - If dict: try common keys 'name','type','value' then stringify
        - Otherwise: str(value)
        """
        if value is None:
            return ""
        if isinstance(value, list):
            if not value:
                return ""
            return self._extract_string(value[0])
        if isinstance(value, dict):
            for k in ("name", "type", "value", "project_type", "sdlc_method"):
                if k in value and value[k] is not None:
                    return str(value[k])
            # Fallback to string representation
            return str(value)
        return str(value)

    def _slugify(self, value) -> str:
        """Create a lowercase slug from value (letters/numbers and underscores).

        Returns 'unknown' when no usable content found.
        """
        raw = self._extract_string(value)
        if not raw:
            return "unknown"
        s = raw.strip().lower()
        s = s.replace(" ", "_")
        import re
        s = re.sub(r"[^a-z0-9_]+", "", s)
        return s or "unknown"
    
    def get_entity_type(self) -> str:
        return "ProjectTemplate"
    
    def format_entity_vertex(self, project: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Format project record into ProjectTemplate vertex."""
        try:
            project_id = str(project.get("project_id"))
            logger.debug(f"Formatting project vertex: {project_id}")
            
            # Skip projects with no name (likely data integrity issue)
            if not project.get("name"):
                logger.warning(f"⚠ SKIPPING PROJECT {project_id} - no title/name found in database")
                print(f"\n⚠ SKIPPING PROJECT {project_id} - no title/name found\n")
                return None
            
            attributes = {
                "id": project_id,
                "tenant_id": project.get("tenant_id", ""),
                "name": project.get("name", "Unknown"),
                "title": project.get("name", "Unknown"), 
                "description": project.get("description", ""),
                "start_date": self._format_date(project.get("start_date")),
                "end_date": self._format_date(project.get("end_date")),
                "state": project.get("project_state", "Unknown"),
                "delivery_status": project.get("delivery_status", ""),
                "scope_status": project.get("scope_status", ""),
                "spend_status": project.get("spend_status", ""),
                "objectives": project.get("project_objectives", ""),
                "total_external_spend": project.get("total_external_spend", 0.0)
            }
            return (project_id, attributes)
        except Exception as e:
            logger.error(f"Error formatting project vertex: {str(e)}")
            appLogger.error({
                "event": "format_project_vertex_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "project_id": project.get("project_id"),
                "project_keys": list(project.keys()) if isinstance(project, dict) else str(type(project))
            })
            raise
    
    def format_related_vertices_and_edges(
        self, 
        project: Dict[str, Any]
    ) -> Tuple[Dict[str, List], Dict[str, List]]:
        """Format project's related entities (TemplatePortfolio, TemplateMilestone, etc.)."""
        try:
            project_id = str(project.get("project_id"))
            logger.debug(f"Formatting related entities for project: {project_id}")
            
            vertices = defaultdict(list)
            edges = defaultdict(list)
        
            # TemplatePortfolios
            for portfolio in project.get("portfolios", []):
                portfolio_id = str(portfolio.get("id") or portfolio.get("portfolio_id", "unknown"))
                if portfolio_id != "unknown" and not any(pid == portfolio_id for pid, _ in vertices.get("TemplatePortfolio", [])):
                    vertices["TemplatePortfolio"].append((
                            portfolio_id,
                            {
                                "id": portfolio_id,
                                "tenant_id": project.get("tenant_id", ""),
                                "title": portfolio.get("name", "Unknown"),
                                "name": portfolio.get("name", "Unknown"),
                            }
                        ))
                if portfolio_id != "unknown":
                    edges["hasTemplatePortfolio"].append((project_id, portfolio_id))
        
            # TemplateMilestones
            for milestone in project.get("milestones", []):
                milestone_id = str(milestone.get("id") or milestone.get("milestone_id", "unknown"))
                if milestone_id != "unknown" and not any(mid == milestone_id for mid, _ in vertices.get("TemplateMilestone", [])):
                    vertices["TemplateMilestone"].append((
                        milestone_id,
                        {
                            "id": milestone_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": milestone.get("milestone_name", "Unknown"),
                            "description": milestone.get("description", ""),
                            "target_date": self._format_date(milestone.get("target_date")),
                            "actual_date": self._format_date(milestone.get("actual_date")),
                        }
                    ))
                if milestone_id != "unknown":
                    edges["hasTemplateMilestone"].append((project_id, milestone_id))
        
            # TemplateStatus
            if project.get("delivery_status"):
                status_id = f"status_{project_id}"
                if not any(sid == status_id for sid, _ in vertices.get("TemplateStatus", [])):
                    vertices["TemplateStatus"].append((
                        status_id,
                        {
                            "id": status_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": project.get("delivery_status", ""),
                            "status_type": "delivery",
                        }
                    ))
                edges["hasTemplateStatus"].append((project_id, status_id))
        
            # TemplateTechnologies
            for tech in project.get("technologies", []):
                tech_id = str(tech.get("tech_id") or tech.get("id") or tech.get("technology_id", "unknown"))
                if tech_id != "unknown" and not any(tid == tech_id for tid, _ in vertices.get("TemplateTechnology", [])):
                    vertices["TemplateTechnology"].append((
                        tech_id,
                        {
                            "id": tech_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": tech.get("name", "Unknown"),
                        }
                    ))
                if tech_id != "unknown":
                    edges["hasTemplateTechnology"].append((project_id, tech_id))
        
            # TemplateKeyResults (KPIs)
            for kr in project.get("key_results", []):
                kr_id = str(kr.get("kpi_id") or kr.get("id") or kr.get("key_result_id", "unknown"))
                if kr_id != "unknown" and not any(krid == kr_id for krid, _ in vertices.get("TemplateKeyResult", [])):
                    vertices["TemplateKeyResult"].append((
                        kr_id,
                        {
                            "id": kr_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": kr.get("kpi_name") or kr.get("name", "Unknown"),
                            "baseline_value": kr.get("baseline_value", ""),
                        }
                    ))
                if kr_id != "unknown":
                    edges["hasTemplateKeyResult"].append((project_id, kr_id))
        
            # TemplateProjectType
            for ptype in project.get("project_type", []):
                if not ptype:
                    continue
                pt_id = str(ptype.get("project_type_id") or ptype.get("id") or self._slugify(ptype.get("name", "unknown")))
                if pt_id != "unknown" and not any(ptid == pt_id for ptid, _ in vertices.get("TemplateProjectType", [])):
                    vertices["TemplateProjectType"].append((
                        pt_id,
                        {
                            "id": pt_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": ptype.get("name", "Unknown"),
                        }
                    ))
                if pt_id != "unknown":
                    edges["hasTemplateProjectType"].append((project_id, pt_id))
        
            # TemplateProjectCategory
            for category in project.get("categories", []):
                raw_cat_name = category.get("name", "unknown") if isinstance(category, dict) else category
                cat_slug = self._slugify(raw_cat_name)
                cat_id = str(category.get("project_category_id") or category.get("id") or f"cat_{cat_slug}")
                if not any(catid == cat_id for catid, _ in vertices.get("TemplateProjectCategory", [])):
                    vertices["TemplateProjectCategory"].append((
                        cat_id,
                        {
                            "id": cat_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": self._extract_string(raw_cat_name) or "Unknown",
                        }
                    ))
                edges["hasTemplateProjectCategory"].append((project_id, cat_id))
        
            # TemplateSdlcMethod
            for sdlc in project.get("sdlc_method", []):
                if not sdlc:
                    continue
                sdlc_id = str(sdlc.get("sdlc_method_id") or sdlc.get("id") or self._slugify(sdlc.get("name", "unknown")))
                if sdlc_id != "unknown" and not any(sid == sdlc_id for sid, _ in vertices.get("TemplateSdlcMethod", [])):
                    vertices["TemplateSdlcMethod"].append((
                        sdlc_id,
                        {
                            "id": sdlc_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": sdlc.get("name", "Unknown"),
                        }
                    ))
                if sdlc_id != "unknown":
                    edges["hasTemplateSdlcMethod"].append((project_id, sdlc_id))
        
            # TemplateProjectLocation
            for location in project.get("locations", []):
                loc_id = str(location.get("project_location_id") or location.get("id") or location.get("location_id", "unknown"))
                if loc_id != "unknown" and not any(locid == loc_id for locid, _ in vertices.get("TemplateProjectLocation", [])):
                    vertices["TemplateProjectLocation"].append((
                        loc_id,
                        {
                            "id": loc_id,
                            "tenant_id": project.get("tenant_id", ""),
                            "name": location.get("name", "Unknown"),
                        }
                    ))
                if loc_id != "unknown":
                    edges["hasTemplateProjectLocation"].append((project_id, loc_id))
        
            return (dict(vertices), dict(edges))
            
        except Exception as e:
            logger.error(f"Error formatting related entities for project {project_id}: {str(e)}")
            appLogger.error({
                "event": "format_related_entities_error",
                "entity_type": "Project",
                "project_id": project_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "project_keys": list(project.keys()) if isinstance(project, dict) else str(type(project))
            })
            raise
    
    @staticmethod
    def _format_date(date_obj) -> str:
        """Convert date object to ISO format string."""
        if not date_obj:
            return ""
        if isinstance(date_obj, str):
            return date_obj
        try:
            return date_obj.strftime("%Y-%m-%d")
        except:
            return ""


class RoadmapEntityFormatter(BaseEntityFormatter):
    """Formats roadmap database records into graph structure."""
    
    def get_entity_type(self) -> str:
        return "RoadmapTemplate"
    
    def format_entity_vertex(self, roadmap: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Format roadmap record into RoadmapTemplate vertex."""
        roadmap_id = str(roadmap.get("roadmap_id"))
        
        attributes = {
            "id": roadmap_id,
            "tenant_id": roadmap.get("tenant_id", ""),
            "name": roadmap.get("name", "Unknown"),
            "title": roadmap.get("name", "Unknown"), # Added title
            "description": roadmap.get("description", ""),
            "start_date": self._format_date(roadmap.get("start_date")),
            "end_date": self._format_date(roadmap.get("end_date")),
            "status": roadmap.get("status", "draft"),
            "visibility": roadmap.get("visibility", "internal"),
            "objectives": roadmap.get("roadmap_objectives", ""),
            "solution": roadmap.get("solution", ""),  # Include solution field for semantic analysis
            "budget": roadmap.get("budget", 0.0), # Added budget
            "category": roadmap.get("category", ""), # Added category
            "priority": roadmap.get("priority", ""), # Added priority
            "current_state": roadmap.get("current_state", ""), # Added current_state
            "roadmap_type": roadmap.get("roadmap_type", ""), # Added roadmap_type
            "org_strategy_align": roadmap.get("org_strategy_align", 0.0), # Added org_strategy_align
        }
        return (roadmap_id, attributes)
    
    def format_related_vertices_and_edges(
        self, 
        roadmap: Dict[str, Any]
    ) -> Tuple[Dict[str, List], Dict[str, List]]:
        """Format roadmap's related entities (TemplatePortfolio, TemplateConstraint, TemplateRoadmapKeyResult, etc.)."""
        roadmap_id = str(roadmap.get("roadmap_id"))
        vertices = defaultdict(list)
        edges = defaultdict(list)
        
        # TemplatePortfolios
        for portfolio in roadmap.get("portfolios", []):
            portfolio_id = str(portfolio.get("id") or portfolio.get("portfolio_id", "unknown"))
            if portfolio_id != "unknown" and not any(pid == portfolio_id for pid, _ in vertices.get("TemplatePortfolio", [])):
                vertices["TemplatePortfolio"].append((
                    portfolio_id,
                    {
                        "id": portfolio_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "title": portfolio.get("name", "Unknown"),
                        "name": portfolio.get("name", "Unknown"),
                    }
                ))
            if portfolio_id != "unknown":
                edges["hasRoadmapTemplatePortfolio"].append((roadmap_id, portfolio_id))
        
        # TemplateConstraints
        for constraint in roadmap.get("constraints", []):
            constraint_id = str(constraint.get("id") or constraint.get("constraint_id", "unknown"))
            if constraint_id != "unknown" and not any(cid == constraint_id for cid, _ in vertices.get("TemplateConstraint", [])):
                vertices["TemplateConstraint"].append((
                    constraint_id,
                    {
                        "id": constraint_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": constraint.get("constraint_name") or constraint.get("name", "Unknown"),
                        "description": constraint.get("description", ""),
                        "constraint_type": constraint.get("constraint_type", ""),
                    }
                ))
            if constraint_id != "unknown":
                edges["hasTemplateConstraint"].append((roadmap_id, constraint_id))
        
        # TemplateRoadmapKeyResults
        for kr in roadmap.get("key_results", []):
            kr_id = str(kr.get("kpi_id") or kr.get("id") or kr.get("key_result_id", "unknown"))
            if kr_id != "unknown" and not any(krid == kr_id for krid, _ in vertices.get("TemplateRoadmapKeyResult", [])):
                vertices["TemplateRoadmapKeyResult"].append((
                    kr_id,
                    {
                        "id": kr_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": kr.get("kpi_name") or kr.get("name", "Unknown"),
                        "description": kr.get("description", ""),
                        "baseline_value": kr.get("baseline_value", ""),
                        "target_value": "",
                    }
                ))
            if kr_id != "unknown":
                edges["hasTemplateRoadmapKeyResult"].append((roadmap_id, kr_id))
        
        # TemplateTeam
        for team in roadmap.get("team", []):
            team_id = str(team.get("id") or team.get("team_id", "unknown"))
            if team_id != "unknown" and not any(tmid == team_id for tmid, _ in vertices.get("TemplateTeam", [])):
                vertices["TemplateTeam"].append((
                    team_id,
                    {
                        "id": team_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": team.get("team_name") or team.get("name", "Unknown"),
                        "labour_type": team.get("labour_type", ""),
                        "unit": team.get("team_unit_size", ""),
                    }
                ))
            if team_id != "unknown":
                edges["hasTemplateTeam"].append((roadmap_id, team_id))
        
        # TemplateScopes
        for scope in roadmap.get("scopes", []):
            scope_id = str(scope.get("id") or scope.get("scope_id", "unknown"))
            if scope_id != "unknown" and not any(scid == scope_id for scid, _ in vertices.get("TemplateScope", [])):
                vertices["TemplateScope"].append((
                    scope_id,
                    {
                        "id": scope_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": scope.get("scope_name") or scope.get("name", "Unknown"),
                        "description": scope.get("description", ""),
                    }
                ))
            if scope_id != "unknown":
                edges["hasTemplateScope"].append((roadmap_id, scope_id))
        
        # TemplatePriorities
        for priority in roadmap.get("priorities", []):
            priority_id = str(priority.get("id") or priority.get("priority_id", "unknown"))
            if priority_id != "unknown" and not any(prid == priority_id for prid, _ in vertices.get("TemplatePriority", [])):
                vertices["TemplatePriority"].append((
                    priority_id,
                    {
                        "id": priority_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": priority.get("name", "Unknown"),
                        "level": priority.get("level", ""),
                    }
                ))
            if priority_id != "unknown":
                edges["hasTemplatePriority"].append((roadmap_id, priority_id))
        
        # TemplateRoadmapStatus
        for status in roadmap.get("statuses", []):
            status_id = str(status.get("id") or status.get("status_id", "unknown"))
            if status_id != "unknown" and not any(stid == status_id for stid, _ in vertices.get("TemplateRoadmapStatus", [])):
                vertices["TemplateRoadmapStatus"].append((
                    status_id,
                    {
                        "id": status_id,
                        "tenant_id": roadmap.get("tenant_id", ""),
                        "name": status.get("name", "Unknown"),
                        "description": status.get("description", ""),
                    }
                ))
            if status_id != "unknown":
                edges["hasTemplateRoadmapStatus"].append((roadmap_id, status_id))
        
        return (dict(vertices), dict(edges))
    
    @staticmethod
    def _format_date(date_obj) -> str:
        """Convert date object to ISO format string."""
        if not date_obj:
            return ""
        if isinstance(date_obj, str):
            return date_obj
        try:
            return date_obj.strftime("%Y-%m-%d")
        except:
            return ""


def get_entity_formatter(entity_type: str) -> BaseEntityFormatter:
    """Factory function to get appropriate formatter for entity type."""
    try:
        logger.info(f"Getting entity formatter for type: {entity_type} (type: {type(entity_type)})")
        appLogger.info({
            "event": "get_entity_formatter",
            "entity_type": entity_type,
            "entity_type_class": str(type(entity_type))
        })
        
        formatters = {
            "Project": ProjectEntityFormatter(),
            "Roadmap": RoadmapEntityFormatter(),
        }
        
        # Check if entity_type is a list (common error)
        if isinstance(entity_type, list):
            error_msg = f"entity_type is a list {entity_type}, expected string"
            logger.error(error_msg)
            appLogger.error({
                "event": "get_entity_formatter_error",
                "error": "entity_type_is_list",
                "entity_type_value": str(entity_type),
                "entity_type_class": str(type(entity_type))
            })
            # Try to use first element if it's a single-element list
            if len(entity_type) == 1:
                entity_type = entity_type[0]
                logger.info(f"Extracted entity_type from list: {entity_type}")
            else:
                raise TypeError(f"entity_type must be a string, got list: {entity_type}")
        
        formatter = formatters.get(entity_type)
        
        if formatter is None:
            error_msg = f"No formatter found for entity_type: {entity_type}"
            logger.error(error_msg)
            appLogger.error({
                "event": "get_entity_formatter_error",
                "error": "formatter_not_found",
                "entity_type": entity_type,
                "available_formatters": list(formatters.keys())
            })
            raise ValueError(f"Unknown entity_type: {entity_type}. Available: {list(formatters.keys())}")
        
        logger.info(f"Successfully got formatter: {type(formatter).__name__}")
        return formatter
        
    except Exception as e:
        logger.error(f"Error in get_entity_formatter: {str(e)}")
        appLogger.error({
            "event": "get_entity_formatter_critical_error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "entity_type": str(entity_type),
            "entity_type_class": str(type(entity_type))
        })
        raise

