"""
Main Project Scoring Engine - orchestrates all calculations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from src.trmeric_database.dao import ProjectsDao
from .models import (
    ProjectScoringRequest,
    ProjectContext,
    DimensionScores,
    ProjectScore,
)
from .calculations import DimensionCalculations
from .confidence import ConfidenceCalculation
from .signals import SignalAnalysis
from .maturity import MaturityCalculation
from .explanation_generator import ScoringExplanationGenerator


class ProjectScoringEngine:
    """
    Main scoring engine.
    Takes project_id, returns complete ProjectScore object.
    """
    
    def __init__(self, projects_dao: ProjectsDao):
        """
        Initialize with ProjectsDao for data access.
        
        Args:
            projects_dao: DAO for fetching project data
        """
        self.dao = projects_dao
        self.maturity_calc = MaturityCalculation()  # Initialize maturity calculator (has LLM)
        self.explanation_gen = ScoringExplanationGenerator()  # Initialize explanation generator (has LLM)
    
    def score_project(self, project_id: int, tenant_id: int) -> ProjectScore:
        """
        Main entry point - score a single project.
        
        Args:
            project_id: ID of project to score
            tenant_id: Tenant context
        
        Returns:
            ProjectScore object with all scoring details
        
        Raises:
            ValueError: If project not found
        """
        # 1. Fetch all project data
        context = self._fetch_project_context(project_id, tenant_id)
        
        # 2. Calculate core scores (with explanations)
        on_time, on_time_explanation = DimensionCalculations.calculate_on_time(context)
        on_scope, on_scope_explanation = DimensionCalculations.calculate_on_scope(context)
        on_budget, on_budget_explanation = DimensionCalculations.calculate_on_budget(context)
        risk, risk_explanation = DimensionCalculations.calculate_risk_management(context)
        team, team_explanation = DimensionCalculations.calculate_team_health(context)
        
        core_score = DimensionCalculations.aggregate_core_score(
            on_time, on_scope, on_budget, risk, team
        )
        
        # 3. Calculate confidence
        confidence = ConfidenceCalculation.calculate_confidence(context)
        
        # 4. Analyze quality signals
        signals = SignalAnalysis.analyze_signals(context)
        
        # 5. Calculate maturity (if completed) - uses LLM for retrospective analysis
        maturity = self.maturity_calc.calculate_maturity_score(context)
        
        # 6. Build and return result
        return self._build_result(
            context=context,
            core_score=core_score,
            dimensions=DimensionScores(
                on_time=on_time,
                on_scope=on_scope,
                on_budget=on_budget,
                risk_management=risk,
                team_health=team,
                core_score=core_score,
                on_time_explanation=on_time_explanation,
                on_scope_explanation=on_scope_explanation,
                on_budget_explanation=on_budget_explanation,
                risk_management_explanation=risk_explanation,
                team_health_explanation=team_explanation
            ),
            confidence=confidence,
            signals=signals,
            maturity=maturity
        )
    
    def _fetch_project_context(self, project_id: int, tenant_id: int) -> ProjectContext:
        """
        Fetch all project data needed for scoring.
        
        Args:
            project_id: Project ID
            tenant_id: Tenant ID
        
        Returns:
            ProjectContext with all fetched data
        
        Raises:
            ValueError: If project not found
        """
        try:
            # Fetch core project - use FetchProjectDetails (PascalCase)
            project_results = self.dao.FetchProjectDetails(project_id)
            if not project_results or len(project_results) == 0:
                raise ValueError(f"Project {project_id} not found")
            project = project_results[0]
            
            # Determine project status (field name might be 'status', 'form_status', or similar)
            project_status = "active"  # default
            if project.get("archived_on"):
                project_status = "archived"
            elif project.get("current_stage") and "archive" in project.get("current_stage", "").lower():
                project_status = "completed"
            
            # Fetch statuses - takes single project_id, not list
            statuses = self.dao.fetchProjectStatuses(project_id)
            
            # Fetch milestones - returns dict with separated types
            milestones_data = self.dao.fetchProjectMilestones(project_id)
            # Flatten the structure into a list
            milestones = []
            if isinstance(milestones_data, dict):
                for scope_list in milestones_data.get("scope_milestones", []):
                    scope_list["type"] = 1  # Override type field to numeric
                    milestones.append(scope_list)
                for schedule_list in milestones_data.get("schedule_milestones", []):
                    schedule_list["type"] = 2
                    milestones.append(schedule_list)
                for spend_list in milestones_data.get("spend_milestones", []):
                    spend_list["type"] = 3
                    milestones.append(spend_list)
            
            # Fetch risks - use V2 which is more modern
            risks_raw = self.dao.fetchProjectsRisksV2([project_id])
            risks = risks_raw if risks_raw else []
            
            # Fetch team - takes single project_id, not list
            # Returns dict with structure: {project_id, project_title, pm, team_members}
            team_raw = self.dao.fetchProjectTeamDetails(project_id)
            team = []
            if team_raw and isinstance(team_raw, dict):
                # Extract team members from the dict
                team_members = team_raw.get("team_members", [])
                for member in team_members:
                    if isinstance(member, dict) and member.get("name"):
                        team.append({
                            "name": member.get("name"),
                            "role": member.get("role"),
                            "utilization": member.get("utilization", 50),
                            "is_external": member.get("is_external", False)
                        })
            
            # Fetch retro data (if completed)
            retro_data = None
            if project_status in ["completed", "archived"]:
                retro_query = self.dao.getProjectRetroInsightsV2([project_id], tenant_id)
                # This returns a query string, not results - need to execute it
                if retro_query:
                    try:
                        from src.trmeric_database.Database import db_instance
                        retro_results = db_instance.retrieveSQLQueryOld(retro_query)
                        if retro_results and len(retro_results) > 0:
                            retro_data = retro_results[0]
                    except:
                        retro_data = None
            
            # Fetch value realization (if completed)
            value_data = None
            if project_status in ["completed", "archived"]:
                value_realizations = self.dao.getProjectValueRealizations([project_id], tenant_id)
                if value_realizations:
                    value_data = self._parse_value_realizations(value_realizations)
            
            # Extract latest status values (scope, delivery, spend)
            # Queries are ordered by created_date DESC, so first entry per type is latest
            scope_status = 1  # default: on_track
            delivery_status = 1
            spend_status = 1
            status_comments = []
            found_types = set()
            
            if statuses:
                for status in statuses:
                    # Status type returned as string ("scope_status", "delivery_status", "spend_status")
                    status_type_str = status.get("type", "")
                    status_value_str = status.get("value", "on_track")
                    comment = status.get("comment")
                    
                    # Map string values back to integers
                    status_val = 1 if status_value_str == "on_track" else (2 if status_value_str == "at_risk" else 3)
                    
                    if comment:
                        status_comments.append(comment)
                    
                    # Only process first occurrence of each type (query is ordered by date desc)
                    if "scope" in status_type_str and "scope" not in found_types:
                        scope_status = status_val
                        found_types.add("scope")
                    elif "delivery" in status_type_str and "delivery" not in found_types:
                        delivery_status = status_val
                        found_types.add("delivery")
                    elif "spend" in status_type_str and "spend" not in found_types:
                        spend_status = status_val
                        found_types.add("spend")
            
            # Build context
            context = ProjectContext(
                project_id=project_id,
                project_title=project.get("title", ""),
                project_status=project_status,
                start_date=project.get("start_date"),
                end_date=project.get("end_date"),
                planned_end_date=project.get("end_date"),  # Using end_date as proxy for planned
                scope_status=scope_status,
                delivery_status=delivery_status,
                spend_status=spend_status,
                status_updates_count=len(statuses) if statuses else 0,
                milestones=milestones,
                risks=risks,
                team_members=team,
                status_comments=status_comments,
                retro_data=retro_data,
                value_realization_data=value_data
            )
            
            return context
        
        except Exception as e:
            import traceback
            raise ValueError(f"Error fetching project context for {project_id}: {str(e)}\n{traceback.format_exc()}")
    
    def _parse_value_realizations(self, value_realizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse value realization data into standardized format.
        
        Args:
            value_realizations: Raw value realization data from DAO
        
        Returns:
            Structured value data with KPIs
        """
        kpis = []
        
        for vr in value_realizations:
            kpi = {
                "title": vr.get("key_result", ""),
                "baseline_value": float(vr.get("baseline_value", 0)) if vr.get("baseline_value") else 0,
                "target_value": float(vr.get("planned_value", 0)) if vr.get("planned_value") else 0,
                "actual_value": float(vr.get("achieved_value", 0)) if vr.get("achieved_value") else 0,
            }
            kpis.append(kpi)
        
        return {"kpis": kpis}
    
    def _build_result(
        self,
        context: ProjectContext,
        core_score: int,
        dimensions: DimensionScores,
        confidence,
        signals,
        maturity
    ) -> ProjectScore:
        """
        Build final ProjectScore result object.
        
        Args:
            context: Project context
            core_score: Aggregated core score
            dimensions: Individual dimension scores
            confidence: Confidence breakdown
            signals: Quality signals
            maturity: Maturity score (None if active project)
        
        Returns:
            ProjectScore ready to serialize
        """
        # Convert dimensions to dict for LLM
        dimensions_dict = {
            'on_time': dimensions.on_time,
            'on_scope': dimensions.on_scope,
            'on_budget': dimensions.on_budget,
            'risk_management': dimensions.risk_management,
            'team_health': dimensions.team_health
        }
        
        # Generate LLM-based explanation with full project context
        llm_explanation = self.explanation_gen.generate_explanation(
            project_title=context.project_title,
            project_description=getattr(context, 'description', None) or getattr(context, 'project_description', None),
            core_score=core_score,
            dimensions=dimensions_dict,
            confidence=confidence.overall,
            project_status=context.project_status,
            scope_status=self._status_int_to_str(context.scope_status),
            delivery_status=self._status_int_to_str(context.delivery_status),
            spend_status=self._status_int_to_str(context.spend_status),
            status_comments=context.status_comments,
            milestones_data=context.milestones,
            risks_data=context.risks,
            team_data=context.team_members,
            signals=signals
        )
        
        result = ProjectScore(
            project_id=context.project_id,
            project_title=context.project_title,
            project_status=context.project_status,
            core_score=core_score,
            dimensions=dimensions,
            confidence=confidence,
            signals=signals,
            maturity=maturity,
            calculated_at=datetime.now(),
            data_completeness_pct=self._calculate_data_completeness(context),
            llm_explanation=llm_explanation
        )
        
        return result
    
    @staticmethod
    def _status_int_to_str(status_int: int) -> str:
        """Convert status integer to string."""
        status_map = {1: "On-Track", 2: "At-Risk", 3: "Compromised"}
        return status_map.get(status_int, "Unknown")
    
    def _calculate_data_completeness(self, context: ProjectContext) -> int:
        """
        Calculate overall data completeness percentage (0-100).
        
        Args:
            context: Project context
        
        Returns:
            Data completeness percentage
        """
        components = 0
        total = 6
        
        # Status data
        if context.status_updates_count > 0:
            components += 1
        
        # Milestones
        if len(context.milestones) > 0:
            components += 1
        
        # Risks
        if len(context.risks) > 0:
            components += 1
        
        # Team
        if len(context.team_members) > 0:
            components += 1
        
        # Status comments
        if len(context.status_comments) > 0:
            components += 1
        
        # Retro/Value for completed projects
        if context.project_status in ["completed", "archived"]:
            if context.retro_data or context.value_realization_data:
                components += 1
        else:
            components += 1  # Not applicable for active projects
        
        return int((components / total) * 100)
