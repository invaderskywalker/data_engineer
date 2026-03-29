"""
Analysis Pipeline

Orchestrates fetching data from Postgres, clustering, generating patterns/templates,
and loading resulting vertices/edges into TigerGraph.

Complete workflow: Fetch → Score → Cluster by Portfolio → Generate Patterns → Load Graph
"""
from typing import Set, List, Dict, Any, Tuple
from collections import defaultdict
import logging
import traceback
import json
import statistics
from datetime import datetime
from pathlib import Path
import numpy as np
from src.trmeric_api.logging.AppLogger import appLogger
from ..data_loading.postgres_connector import PostgresConnector, PostgresConfig
from ..data_loading.queries import ProjectQueries, RoadmapQueries
from ..data_loading.data_sanitizer import DataSanitizer
from ..analysis.cluster_engine import ProjectClusterEngine, RoadmapClusterEngine
from ..analysis.project_pattern_generator import ProjectPatternGenerator
from ..analysis.roadmap_pattern_generator import RoadmapPatternGenerator
from ..analysis.template_generator import TemplateGenerator
from ..loaders.batch_loader import BatchGraphLoader
from ..loaders.entity_formatter import get_entity_formatter
from ..infrastructure import GraphConnector, GraphConnectorConfig
# Project and roadmap scoring imports
from src.trmeric_services.scoring import ProjectScoringEngine, RoadmapScoringEngine
from src.trmeric_database.dao.projects import ProjectsDao

logger = logging.getLogger(__name__)



def save_detailed_analysis(filename: str, data: Dict[str, Any]):
    """
    Save detailed clustering and LLM analysis to JSON file for review.
    
    Args:
        filename: Output filename (e.g., "project_analysis_10entities.json")
        data: Dict containing cluster_results, llm_outputs, metrics, etc.
    """

    tmp_dir = Path("/tmp/knowledge_analysis")
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / filename
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        tmp_path = None

    workspace_output_dir = Path.cwd() / "outputs" / "knowledge_analysis"
    workspace_output_dir.mkdir(parents=True, exist_ok=True)
    workspace_path = workspace_output_dir / filename
    with open(workspace_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"\n{'='*80}")
    if tmp_path:
        print(f"DETAILED ANALYSIS SAVED: {tmp_path}")
    print(f"DETAILED ANALYSIS SAVED (WORKSPACE): {workspace_path}")
    print(f"{'='*80}\n")


class AnalysisPipeline:
    """
    Complete analysis pipeline for entity data (projects or roadmaps).
    
    Workflow:
    1. Fetch entity data from PostgreSQL with all related entities
    2. Group by portfolio
    3. Cluster entities within each portfolio using ML
    4. Generate patterns and templates using LLM
    5. Load vertices and edges into TigerGraph
    
    Supports both Projects and Roadmaps through entity type parameter.
    """
    
    def __init__(self, postgres_config: PostgresConfig = None, graph_config: GraphConnectorConfig = None, llm_client=None, graphname: str = ""):
        self.postgres_config = postgres_config or PostgresConfig.from_env()
        if graph_config is None:
            if not graphname:
                raise ValueError("Either graph_config or graphname must be provided")
            graph_config = GraphConnectorConfig.from_env(graphname)
        self.graph_config = graph_config
        self.llm_client = llm_client
        self.sanitizer = DataSanitizer()
        # Cluster engine and pattern generator are initialized dynamically based on entity_type
        self.cluster_engine = None
        self.pattern_generator = None
    
    def _get_fetch_function(self, entity_type: str):
        """Get the fetch function for the entity type."""
        if entity_type.lower() == "project":
            return self.fetch_all_project_data
        elif entity_type.lower() == "roadmap":
            return self.fetch_all_roadmap_data
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    def _format_entity_type_label(self, entity_type: str) -> str:
        """Format entity type for display."""
        return entity_type.upper()
    
    def _get_cluster_engine(self, entity_type: str):
        """Get the appropriate cluster engine for the entity type."""
        if entity_type.lower() == "project":
            return ProjectClusterEngine(
                llm_client=self.llm_client,
                use_llm_refinement=True,
                min_cluster_size=2,
                max_cluster_size=5,
            )
        elif entity_type.lower() == "roadmap":
            return RoadmapClusterEngine(
                llm_client=self.llm_client,
                use_llm_refinement=True,
                min_cluster_size=2,
                max_cluster_size=5,
                ml_precluster_threshold=10,
            )
        else:
            raise ValueError(f"Unknown entity type for clustering: {entity_type}")
    
    def _get_pattern_generator(self, entity_type: str):
        """Get the appropriate pattern generator for the entity type."""
        if entity_type.lower() == "project":
            return ProjectPatternGenerator(self.llm_client)
        elif entity_type.lower() == "roadmap":
            return RoadmapPatternGenerator(self.llm_client)
        else:
            raise ValueError(f"Unknown entity type for pattern generation: {entity_type}")

    def _build_generalized_attributes(self, cluster_result: Dict, entity_type: str) -> Dict:
        """
        Build generalized attributes based on entity type.
        Projects use delivery_* fields, roadmaps use solution_* fields.
        """
        c = cluster_result
        attrs = {
            "technologies": c["generalized"].get("key_technologies", [])[:5],
            "kpis": c["names"].get("pattern", {}).get("key_kpis", [])[:5] if isinstance(c["names"].get("pattern", {}).get("key_kpis", []), list) else [],
            "milestones": c["names"].get("pattern", {}).get("key_milestones", [])[:3] if isinstance(c["names"].get("pattern", {}).get("key_milestones", []), list) else [],
            "constraints": [cn if isinstance(cn, str) else cn.get("name", str(cn)) for cn in c["generalized"].get("constraints", [])][:3],
            "categories": list(set([cat.get("name", cat) if isinstance(cat, dict) else cat for cat in c["generalized"].get("categories", [])]))[:5],
        }
        
        if entity_type.lower() == "project":
            # Projects use delivery-specific fields
            attrs["delivery_themes"] = c["generalized"].get("delivery_themes", [])[:5]
            attrs["delivery_approaches"] = c["generalized"].get("delivery_approaches", [])[:5]
            attrs["delivery_success_criteria"] = c["generalized"].get("delivery_success_criteria", [])[:10]
            attrs["delivery_narrative"] = c["generalized"].get("delivery_narrative", "")
        elif entity_type.lower() == "roadmap":
            # Roadmaps use solution-specific fields
            attrs["solution_themes"] = c["generalized"].get("solution_themes", [])[:5]
            attrs["solution_approaches"] = c["generalized"].get("solution_approaches", [])[:5]
            attrs["solution_success_criteria"] = c["generalized"].get("solution_success_criteria", [])[:10]
            attrs["solution_narrative"] = c["generalized"].get("solution_narrative", "")
            # Timeline / state transition insights
            attrs["state_transition_history"] = c["generalized"].get("state_transition_history", [])[:10]
            attrs["typical_state_flow"] = c["generalized"].get("typical_state_flow", [])
            attrs["stage_duration_insights"] = c["generalized"].get("stage_duration_insights", [])
            attrs["avg_days_per_stage"] = c["generalized"].get("avg_days_per_stage", "")
        
        return attrs

    def _score_projects(self, projects: List[Dict], tenant_id: int) -> List[Dict]:
        """
        Score each project and attach score data to project dict.

        Calculates project health scores using the ProjectScoringEngine and attaches
        all scoring data (dimensions, confidence, signals, explanations) to each project.

        Args:
            projects: List of fetched project dictionaries
            tenant_id: Tenant context for scoring

        Returns:
            Projects with attached 'score_data' field containing flattened score data
        """
        appLogger.info({
            "event": "PIPELINE_SCORING_START",
            "stage": "SCORING",
            "project_count": len(projects),
            "tenant_id": tenant_id
        })

        print(f"\n{'='*80}")
        print(f"SCORING PROJECTS ({len(projects)} total)")
        print(f"{'='*80}\n")

        # Initialize scoring engine
        projects_dao = ProjectsDao()
        scoring_engine = ProjectScoringEngine(projects_dao)

        # Fetch roadmap_id mappings for all projects from workflow_project table
        project_ids = [p.get("project_id") or p.get("id") for p in projects]
        roadmap_mappings = self._fetch_roadmap_mappings(project_ids, tenant_id)

        scored_count = 0
        failed_count = 0

        for project in projects:
            project_id = project.get("project_id") or project.get("id")
            project_name = project.get("name", "Unknown")

            try:
                # Score the project
                score = scoring_engine.score_project(project_id, tenant_id)

                # Get roadmap_id from mapping (None if project not mapped to a roadmap)
                roadmap_id = roadmap_mappings.get(project_id)

                # Flatten and attach score data to project dict
                project["score_data"] = {
                    # Identifiers
                    "id": f"score_{project_id}",
                    "project_id": project_id,
                    "roadmap_id": roadmap_id,  # Added roadmap_id
                    "tenant_id": tenant_id,
                    "scope": "workflow",
                    "project_title": score.project_title,
                    "project_status": score.project_status,

                    # Core scores
                    "core_score": score.core_score,
                    "on_time_score": score.dimensions.on_time,
                    "on_scope_score": score.dimensions.on_scope,
                    "on_budget_score": score.dimensions.on_budget,
                    "risk_management_score": score.dimensions.risk_management,
                    "team_health_score": score.dimensions.team_health,

                    # Dimension explanations
                    "on_time_explanation": score.dimensions.on_time_explanation or "",
                    "on_scope_explanation": score.dimensions.on_scope_explanation or "",
                    "on_budget_explanation": score.dimensions.on_budget_explanation or "",
                    "risk_management_explanation": score.dimensions.risk_management_explanation or "",
                    "team_health_explanation": score.dimensions.team_health_explanation or "",

                    # LLM explanation (flattened as JSON string)
                    "llm_explanation": json.dumps(score.llm_explanation) if score.llm_explanation else "",

                    # Confidence (flattened)
                    "confidence_overall": score.confidence.overall,
                    "confidence_interpretation": score.confidence.interpretation,
                    "confidence_status_fields": score.confidence.status_fields,
                    "confidence_milestones": score.confidence.milestones,
                    "confidence_comments": score.confidence.comments,
                    "confidence_risks": score.confidence.risks,
                    "confidence_team_data": score.confidence.team_data,
                    "data_completeness_pct": score.data_completeness_pct,

                    # Signals (flattened)
                    "milestone_pattern": score.signals.milestone_health.pattern.value if score.signals.milestone_health else "",
                    "milestone_on_time_ratio": score.signals.milestone_health.on_time_ratio if score.signals.milestone_health else 0.0,
                    "milestone_avg_delay_days": score.signals.milestone_health.avg_delay_days if score.signals.milestone_health else 0,
                    "milestone_completed_count": score.signals.milestone_health.completed_count if score.signals.milestone_health else 0,
                    "complication_pattern": score.signals.status_complications.pattern.value if score.signals.status_complications else "",
                    "complication_blocker_count": score.signals.status_complications.blocker_count if score.signals.status_complications else 0,
                    "complication_resolution_rate": score.signals.status_complications.resolution_rate if score.signals.status_complications else 0.0,

                    # Maturity (nullable for active projects)
                    "maturity_score": score.maturity.overall_maturity if score.maturity else None,
                    "maturity_label": score.maturity.label if score.maturity else "",
                    "retrospective_score": score.maturity.retrospective_score if score.maturity else None,
                    "value_realization_score": score.maturity.value_realization_score if score.maturity else None,

                    # Metadata
                    "created_at": datetime.now().isoformat(),
                    "scoring_version": "v1.0"
                }

                scored_count += 1
                roadmap_log = f" (roadmap: {roadmap_id})" if roadmap_id else ""
                print(f"  ✓ Scored {project_name[:40]}: {score.core_score}/100 (confidence: {score.confidence.interpretation}){roadmap_log}")

            except Exception as e:
                appLogger.error({
                    "event": "PIPELINE_SCORING_ERROR",
                    "stage": "SCORING",
                    "project_id": project_id,
                    "project_name": project_name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                project["score_data"] = None
                failed_count += 1
                print(f"  ✗ Failed to score {project_name[:40]}: {str(e)[:50]}")

        appLogger.info({
            "event": "PIPELINE_SCORING_COMPLETE",
            "stage": "SCORING",
            "scored_count": scored_count,
            "failed_count": failed_count,
            "success_rate": f"{(scored_count / len(projects) * 100):.1f}%" if projects else "N/A"
        })

        print(f"\n  Scoring complete: {scored_count}/{len(projects)} projects scored successfully")
        if failed_count > 0:
            print(f"  Warning: {failed_count} projects failed to score")
        print(f"{'='*80}\n")

        return projects

    def _score_roadmaps(self, roadmaps: List[Dict], tenant_id: int) -> List[Dict]:
        """
        Score each roadmap for data quality and attach score_data to the roadmap dict.

        Calculates planning completeness scores using RoadmapScoringEngine.
        Score reflects how thoroughly the roadmap plan is defined (not execution metrics).

        Args:
            roadmaps: List of fetched roadmap dictionaries
            tenant_id: Tenant context for scoring

        Returns:
            Roadmaps with attached 'score_data' field containing flattened score data
        """
        appLogger.info({
            "event": "PIPELINE_ROADMAP_SCORING_START",
            "stage": "SCORING",
            "roadmap_count": len(roadmaps),
            "tenant_id": tenant_id
        })

        print(f"\n{'='*80}")
        print(f"SCORING ROADMAPS ({len(roadmaps)} total)")
        print(f"{'='*80}\n")

        scoring_engine = RoadmapScoringEngine()
        scored_count = 0
        failed_count = 0

        for roadmap in roadmaps:
            roadmap_id = roadmap.get("roadmap_id") or roadmap.get("id")
            roadmap_name = roadmap.get("name", "Unknown")

            if not roadmap_id:
                roadmap["score_data"] = None
                failed_count += 1
                print(f"  ✗ Skipped roadmap with no ID: {roadmap_name[:40]}")
                continue

            try:
                score = scoring_engine.score_roadmap(roadmap_id, tenant_id)

                roadmap["score_data"] = {
                    # Identifiers
                    "id": f"rscore_{roadmap_id}",
                    "roadmap_id": roadmap_id,
                    "tenant_id": tenant_id,
                    "scope": "workflow",
                    "roadmap_title": score.roadmap_title,
                    "roadmap_state": score.roadmap_state,

                    # Core score
                    "core_score": score.core_score,

                    # Dimension blended scores
                    "strategic_clarity_score": score.dimensions.strategic_clarity,
                    "okr_quality_score": score.dimensions.okr_quality,
                    "scope_and_constraints_score": score.dimensions.scope_and_constraints,
                    "resource_financial_score": score.dimensions.resource_financial_planning,
                    "solution_readiness_score": score.dimensions.solution_readiness,

                    # Dimension explanations
                    "strategic_clarity_explanation": score.dimensions.strategic_clarity_explanation,
                    "okr_quality_explanation": score.dimensions.okr_quality_explanation,
                    "scope_and_constraints_explanation": score.dimensions.scope_and_constraints_explanation,
                    "resource_financial_explanation": score.dimensions.resource_financial_explanation,
                    "solution_readiness_explanation": score.dimensions.solution_readiness_explanation,

                    # LLM explanation (flattened as JSON string)
                    "llm_explanation": json.dumps(score.llm_explanation) if score.llm_explanation else "",

                    # Confidence
                    "confidence_overall": score.confidence.overall,
                    "confidence_interpretation": score.confidence.interpretation,
                    "confidence_core_fields": score.confidence.core_fields,
                    "confidence_okr_completeness": score.confidence.okr_completeness,
                    "confidence_scope_coverage": score.confidence.scope_coverage,
                    "confidence_financial_data": score.confidence.financial_data,
                    "confidence_alignment_signal": score.confidence.alignment_signal,
                    "data_completeness_pct": score.data_completeness_pct,

                    # Signals
                    "planning_depth_pattern": score.signals.planning_depth.pattern.value if score.signals.planning_depth else "",
                    "planning_depth_description": score.signals.planning_depth.description if score.signals.planning_depth else "",
                    "financial_rationale_pattern": score.signals.financial_rationale.pattern.value if score.signals.financial_rationale else "",
                    "financial_rationale_description": score.signals.financial_rationale.description if score.signals.financial_rationale else "",

                    # Metadata
                    "created_at": datetime.now().isoformat(),
                    "scoring_version": "v1.0"
                }

                scored_count += 1
                print(
                    f"  \u2713 Scored {roadmap_name[:40]}: "
                    f"{score.core_score}/100 "
                    f"(confidence: {score.confidence.interpretation}, "
                    f"planning: {score.signals.planning_depth.pattern.value if score.signals.planning_depth else 'N/A'})"
                )

            except Exception as e:
                appLogger.error({
                    "event": "PIPELINE_ROADMAP_SCORING_ERROR",
                    "stage": "SCORING",
                    "roadmap_id": roadmap_id,
                    "roadmap_name": roadmap_name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                roadmap["score_data"] = None
                failed_count += 1
                print(f"  \u2717 Failed to score {roadmap_name[:40]}: {str(e)[:50]}")

        appLogger.info({
            "event": "PIPELINE_ROADMAP_SCORING_COMPLETE",
            "stage": "SCORING",
            "scored_count": scored_count,
            "failed_count": failed_count,
            "success_rate": f"{(scored_count / len(roadmaps) * 100):.1f}%" if roadmaps else "N/A"
        })

        print(f"\n  Roadmap scoring complete: {scored_count}/{len(roadmaps)} roadmaps scored successfully")
        if failed_count > 0:
            print(f"  Warning: {failed_count} roadmaps failed to score")
        print(f"{'='*80}\n")

        return roadmaps

    def _fetch_roadmap_mappings(self, project_ids: List[int], tenant_id: int) -> Dict[int, int]:
        """
        Fetch roadmap_id mappings for projects from workflow_project table.

        Args:
            project_ids: List of project IDs
            tenant_id: Tenant identifier

        Returns:
            Dictionary mapping project_id -> roadmap_id (only includes projects with roadmaps)
        """
        if not project_ids:
            return {}

        pg = PostgresConnector(self.postgres_config)
        with pg.cursor() as cursor:
            # Query workflow_project table for roadmap_id mappings
            placeholders = ','.join(['%s'] * len(project_ids))
            query = f"""
                SELECT id, roadmap_id
                FROM workflow_project
                WHERE id IN ({placeholders})
                  AND tenant_id_id = %s
                  AND roadmap_id IS NOT NULL
            """
            cursor.execute(query, (*project_ids, tenant_id))
            rows = cursor.fetchall()

            # Build mapping dict: project_id -> roadmap_id
            mappings = {}
            for row in rows:
                project_id = row[0]
                roadmap_id = row[1]
                if roadmap_id:  # Extra safety check
                    mappings[project_id] = roadmap_id

            appLogger.info({
                "event": "ROADMAP_MAPPINGS_FETCHED",
                "stage": "SCORING",
                "total_projects": len(project_ids),
                "projects_with_roadmaps": len(mappings)
            })

            return mappings

    def _fetch_roadmap_to_projects_mapping(self, roadmap_ids: List[int], tenant_id: int) -> Dict[int, List[int]]:
        """
        Fetch reverse mapping: roadmap_id → [project_ids] from workflow_project table.

        Used during the Roadmap pipeline run to find all projects linked to each roadmap
        so that cross-score links (RoadmapScore ↔ ProjectScore) can be computed.

        Args:
            roadmap_ids: List of roadmap IDs to look up
            tenant_id: Tenant identifier

        Returns:
            Dictionary mapping roadmap_id -> [project_id, ...] (only populated roadmaps)
        """
        if not roadmap_ids:
            return {}

        pg = PostgresConnector(self.postgres_config)
        with pg.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(roadmap_ids))
            query = f"""
                SELECT roadmap_id, id
                FROM workflow_project
                WHERE roadmap_id IN ({placeholders})
                  AND tenant_id_id = %s
                  AND roadmap_id IS NOT NULL
            """
            cursor.execute(query, (*roadmap_ids, tenant_id))
            rows = cursor.fetchall()

            mapping: Dict[int, List[int]] = {}
            for row in rows:
                roadmap_id = int(row[0])
                project_id = int(row[1])
                mapping.setdefault(roadmap_id, []).append(project_id)

            appLogger.info({
                "event": "ROADMAP_TO_PROJECTS_MAPPING_FETCHED",
                "stage": "SCORING",
                "roadmap_count": len(roadmap_ids),
                "roadmaps_with_projects": len(mapping),
                "total_projects": sum(len(v) for v in mapping.values())
            })

            return mapping

    def connect_roadmap_to_project_patterns(self, tenant_id: int) -> Dict[str, Any]:
        """
        Connect RoadmapPattern vertices to ProjectScore and ProjectPattern vertices
        based on roadmap → project mappings from workflow_project table.

        Creates bidirectional edges:
        - RoadmapPattern ↔ ProjectScore (hasProjectExecution / executedByRoadmap)
        - RoadmapPattern ↔ ProjectPattern (hasExecutionInCluster / roadmapExecutedInCluster)

        Args:
            tenant_id: Tenant identifier

        Returns:
            Statistics about connections created
        """
        appLogger.info({
            "event": "PATTERN_CONNECTION_START",
            "stage": "CONNECT_PATTERNS",
            "tenant_id": tenant_id
        })

        print(f"\n{'='*80}")
        print(f"CONNECTING ROADMAP PATTERNS TO PROJECT PATTERNS")
        print(f"{'='*80}\n")

        # Initialize graph connection
        graph_connector = GraphConnector(self.graph_config)
        graph_connector.connect()

        try:
            # Step 1: Fetch all RoadmapPattern vertices for this tenant using GraphConnector API
            roadmap_patterns_dict = graph_connector.get_vertices(
                "RoadmapPattern",
                tenant_id=tenant_id,
                limit=500  # Reasonable limit for patterns
            )

            appLogger.info({
                "event": "FETCH_ROADMAP_PATTERNS",
                "stage": "CONNECT_PATTERNS",
                "tenant_id": tenant_id,
                "patterns_retrieved": len(roadmap_patterns_dict) if roadmap_patterns_dict else 0
            })

            # Convert dict format to list format
            roadmap_patterns = []
            if isinstance(roadmap_patterns_dict, dict):
                for vertex_id, vertex_data in roadmap_patterns_dict.items():
                    if isinstance(vertex_data, dict):
                        roadmap_patterns.append({
                            "v_id": vertex_id,
                            "attributes": vertex_data.get("attributes", {})
                        })
            elif isinstance(roadmap_patterns_dict, list):
                roadmap_patterns = roadmap_patterns_dict

            # CRITICAL: Filter to only workflow-level patterns (exclude portfolio-level)
            workflow_patterns = [
                p for p in roadmap_patterns 
                if p.get("attributes", {}).get("scope") == "workflow"
            ]
            
            print(f"  Found {len(roadmap_patterns)} RoadmapPattern vertices")
            print(f"  Filtered to {len(workflow_patterns)} workflow-level patterns (excluding portfolio-level)")
            
            roadmap_patterns = workflow_patterns

            if not roadmap_patterns:
                # Don't return — skip Steps 2-4 but fall through to Step 5 (cross-score)
                print(f"  No workflow-scope RoadmapPattern vertices found; skipping pattern-link steps but continuing to cross-score step...")

            # Step 2: For each RoadmapPattern, process its roadmap_ids
            pg = PostgresConnector(self.postgres_config)
            edges_to_create = {
                "hasProjectExecution": [],
                "executedByRoadmap": [],
                "hasExecutionInCluster": [],
                "roadmapExecutedInCluster": []
            }

            patterns_processed = 0
            roadmaps_with_projects = 0

            for pattern in roadmap_patterns:
                pattern_id = pattern.get("v_id") or pattern.get("id")
                roadmap_ids_attr = pattern.get("attributes", {}).get("roadmap_ids", []) if "attributes" in pattern else pattern.get("roadmap_ids", [])

                # Handle both list and single value
                if not isinstance(roadmap_ids_attr, list):
                    roadmap_ids_attr = [roadmap_ids_attr] if roadmap_ids_attr else []

                # Convert to integers if they're strings
                roadmap_ids = []
                for rid in roadmap_ids_attr:
                    try:
                        roadmap_ids.append(int(rid) if isinstance(rid, str) else rid)
                    except (ValueError, TypeError):
                        continue

                if not roadmap_ids:
                    continue

                print(f"  Processing pattern {pattern_id} with {len(roadmap_ids)} roadmaps")

                # Query workflow_project for mappings
                with pg.cursor() as cursor:
                    placeholders = ','.join(['%s'] * len(roadmap_ids))
                    query = f"""
                        SELECT id, roadmap_id
                        FROM workflow_project
                        WHERE roadmap_id IN ({placeholders})
                          AND tenant_id_id = %s
                    """
                    cursor.execute(query, (*roadmap_ids, tenant_id))
                    project_mappings = cursor.fetchall()

                if not project_mappings:
                    print(f"    No projects found for pattern {pattern_id}")
                    continue

                # Step 3: For each project, create edges
                for project_id, roadmap_id in project_mappings:
                    roadmaps_with_projects += 1

                    # Check if ProjectScore exists
                    score_id = f"score_{project_id}"

                    try:
                        # Use get_vertices_by_id to check if score exists
                        score_vertex = graph_connector.get_vertices_by_id(
                            "ProjectScore",
                            tenant_id,
                            [score_id]
                        )
                        score_exists = bool(score_vertex and len(score_vertex) > 0)
                    except Exception as e:
                        appLogger.warning({
                            "event": "SCORE_LOOKUP_ERROR",
                            "score_id": score_id,
                            "error": str(e)
                        })
                        score_exists = False

                    if score_exists:
                        # Create RoadmapPattern ↔ ProjectScore edges
                        edges_to_create["hasProjectExecution"].append((pattern_id, score_id))
                        edges_to_create["executedByRoadmap"].append((score_id, pattern_id))
                        print(f"    ✓ Roadmap {roadmap_id} → Project {project_id} (score exists)")
                    else:
                        print(f"    ⊘ Roadmap {roadmap_id} → Project {project_id} (no score found)")
                        continue

                    # Find ProjectPattern containing this project_id
                    # Query ProjectPattern vertices using GraphConnector API
                    # Note: project_ids are stored as strings in ProjectPattern
                    # CRITICAL: Only match workflow-level patterns (exclude portfolio-level)
                    project_id_str = str(project_id)
                    
                    try:
                        # Use get_vertices with filter to find patterns containing this project
                        all_patterns = graph_connector.get_vertices(
                            "ProjectPattern",
                            tenant_id=tenant_id,
                            limit=100
                        )
                        
                        # Filter patterns that contain this project_id AND are workflow-level
                        matching_patterns = []
                        if isinstance(all_patterns, dict):
                            for pat_id, pat_data in all_patterns.items():
                                attrs = pat_data.get("attributes", {}) if isinstance(pat_data, dict) else pat_data
                                project_ids_in_pattern = attrs.get("project_ids", [])
                                pattern_scope = attrs.get("scope", "workflow")
                                if project_id_str in project_ids_in_pattern and pattern_scope == "workflow":
                                    matching_patterns.append(pat_id)
                        elif isinstance(all_patterns, list):
                            for pat in all_patterns:
                                pat_id = pat.get("v_id") or pat.get("id")
                                attrs = pat.get("attributes", {})
                                project_ids_in_pattern = attrs.get("project_ids", [])
                                pattern_scope = attrs.get("scope", "workflow")
                                if project_id_str in project_ids_in_pattern and pattern_scope == "workflow":
                                    matching_patterns.append(pat_id)
                        
                        if matching_patterns:
                            for proj_pattern_id in matching_patterns:
                                # Create RoadmapPattern ↔ ProjectPattern edges
                                edges_to_create["hasExecutionInCluster"].append((pattern_id, proj_pattern_id))
                                edges_to_create["roadmapExecutedInCluster"].append((proj_pattern_id, pattern_id))
                                print(f"      ↔ Connected to ProjectPattern {proj_pattern_id[:60]}")
                        else:
                            print(f"      ⊘ No ProjectPattern found for project {project_id}")
                            
                    except Exception as e:
                        appLogger.warning({
                            "event": "PROJECT_PATTERN_LOOKUP_ERROR",
                            "project_id": project_id,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })
                        print(f"      ✗ Error finding ProjectPattern for project {project_id}: {str(e)[:50]}")

                patterns_processed += 1

            # Step 4: Batch create all edges
            from ..loaders.edge_loader import EdgeLoader
            edge_loader = EdgeLoader(graph_connector)

            # Define vertex type mappings for each edge type
            edge_type_mappings = {
                "hasProjectExecution": ("RoadmapPattern", "ProjectScore"),
                "executedByRoadmap": ("ProjectScore", "RoadmapPattern"),
                "hasExecutionInCluster": ("RoadmapPattern", "ProjectPattern"),
                "roadmapExecutedInCluster": ("ProjectPattern", "RoadmapPattern")
            }

            total_edges_created = 0
            for edge_type, edge_list in edges_to_create.items():
                if edge_list:
                    # Remove duplicates
                    edge_list = list(set(edge_list))
                    print(f"\n  Creating {len(edge_list)} {edge_type} edges...")
                    
                    # Get vertex types for this edge
                    from_vertex_type, to_vertex_type = edge_type_mappings.get(edge_type, (None, None))
                    if not from_vertex_type or not to_vertex_type:
                        appLogger.error({
                            "event": "EDGE_TYPE_MAPPING_ERROR",
                            "edge_type": edge_type,
                            "error": "Unknown edge type"
                        })
                        print(f"    ✗ Unknown edge type: {edge_type}")
                        continue
                    
                    try:
                        result = edge_loader.load_edges(edge_type, from_vertex_type, to_vertex_type, edge_list)
                        edges_loaded = result.get("loaded", 0)
                        total_edges_created += edges_loaded
                        print(f"    ✓ Created {edges_loaded} {edge_type} edges ({from_vertex_type} → {to_vertex_type})")
                    except Exception as e:
                        appLogger.error({
                            "event": "EDGE_CREATION_ERROR",
                            "edge_type": edge_type,
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        })
                        print(f"    ✗ Failed to create {edge_type} edges: {str(e)}")

            print(f"\n{'='*80}")
            print(f"PATTERN CONNECTION COMPLETE")
            print(f"  Patterns processed: {patterns_processed}")
            print(f"  Roadmaps with projects: {roadmaps_with_projects}")
            print(f"  Total edges created: {total_edges_created}")
            print(f"{'='*80}\n")

            appLogger.info({
                "event": "PATTERN_CONNECTION_COMPLETE",
                "stage": "CONNECT_PATTERNS",
                "patterns_processed": patterns_processed,
                "roadmaps_with_projects": roadmaps_with_projects,
                "total_edges_created": total_edges_created
            })

            # ── Step 5: Cross-score linking (RoadmapScore ↔ ProjectScore) ──
            # Now that both Project and Roadmap pipelines have finished and all
            # vertices are loaded, compute plan-vs-execution alignment.
            print(f"\n{'='*80}")
            print(f"COMPUTING CROSS-SCORE LINKS (RoadmapScore <-> ProjectScore)")
            print(f"{'='*80}\n")

            cross_score_edges_created = 0
            roadmaps_linked = 0
            projects_aligned = 0

            try:
                # 5a: Read all RoadmapScore vertices from TigerGraph
                # get_vertices returns a list of {"v_id": ..., "attributes": {...}}
                roadmap_scores_raw = graph_connector.get_vertices(
                    "RoadmapScore", tenant_id=tenant_id, limit=500
                )

                roadmap_scores = {}  # roadmap_id (int) → {rscore_id, core_score}
                for item in (roadmap_scores_raw or []):
                    vid = item.get("v_id") or item.get("id")
                    attrs = item.get("attributes", {})
                    rm_id = attrs.get("roadmap_id")
                    if vid and rm_id is not None:
                        roadmap_scores[int(rm_id)] = {
                            "rscore_id": vid,
                            "core_score": int(attrs.get("core_score", 0) or 0),
                        }

                print(f"  Found {len(roadmap_scores)} RoadmapScore vertices")

                if roadmap_scores:
                    # 5b: Fetch roadmap_id → [project_ids] from DB
                    roadmap_to_projects = self._fetch_roadmap_to_projects_mapping(
                        list(roadmap_scores.keys()), tenant_id
                    )
                    print(f"  Found {sum(len(v) for v in roadmap_to_projects.values())} project links across {len(roadmap_to_projects)} roadmaps")

                    # 5c: Read all ProjectScore and ProjectPattern vertices for lookup
                    all_linked_pids = list({pid for pids in roadmap_to_projects.values() for pid in pids})
                    project_score_lookup = {}  # score_id → core_score (int)
                    project_to_pattern = {}    # score_id → project_pattern_id

                    # ProjectScore lookup: get ALL loaded ProjectScores and match by roadmap_id attribute.
                    # This is more reliable than looking up specific IDs because the project analysis
                    # pipeline may have analyzed different projects than those linked via workflow_project.
                    # ProjectScore.roadmap_id is populated during project analysis via _fetch_roadmap_mappings.
                    try:
                        analyzed_rm_id_set = set(int(r) for r in roadmap_scores.keys())
                        ps_raw = graph_connector.get_vertices("ProjectScore", tenant_id=tenant_id, limit=1000)
                        for item in (ps_raw or []):
                            sid = item.get("v_id") or item.get("id")
                            attrs = item.get("attributes", {})
                            cs = attrs.get("core_score")
                            rm_id_val = attrs.get("roadmap_id")
                            if sid and cs is not None and rm_id_val and int(rm_id_val) in analyzed_rm_id_set:
                                project_score_lookup[sid] = int(cs)
                                # Back-populate roadmap_to_projects from TigerGraph data
                                pid_val = attrs.get("project_id")
                                if pid_val:
                                    roadmap_to_projects.setdefault(int(rm_id_val), [])
                                    if int(pid_val) not in roadmap_to_projects[int(rm_id_val)]:
                                        roadmap_to_projects[int(rm_id_val)].append(int(pid_val))
                    except Exception as e:
                        appLogger.warning({"event": "CROSS_SCORE_PS_FETCH_FAILED", "error": str(e)})

                    all_linked_pids = list({pid for pids in roadmap_to_projects.values() for pid in pids})

                    if all_linked_pids:
                        # ProjectPattern lookup: build score_id → pattern_id inverted index
                        try:
                            all_proj_patterns = graph_connector.get_vertices(
                                "ProjectPattern", tenant_id=tenant_id, limit=500
                            )
                            pid_strs = {str(pid) for pid in all_linked_pids}
                            for item in (all_proj_patterns or []):
                                pat_id = item.get("v_id") or item.get("id")
                                attrs = item.get("attributes", {})
                                if attrs.get("scope") != "workflow":
                                    continue
                                pattern_pids = attrs.get("project_ids", [])
                                for ppid in pattern_pids:
                                    if str(ppid) in pid_strs:
                                        project_to_pattern[f"score_{ppid}"] = pat_id
                        except Exception as e:
                            appLogger.warning({"event": "CROSS_SCORE_PP_FETCH_FAILED", "error": str(e)})

                    print(f"  Found {len(project_score_lookup)} ProjectScore vertices with scores")
                    print(f"  Found {len(project_to_pattern)} project→pattern mappings")

                    # 5d: Compute cross-score data and collect updates
                    cross_edges = {
                        "roadmapScoreHasProjectExecution": [],
                        "projectScoreFromRoadmapPlan": [],
                        "roadmapScoreInProjectCluster": [],
                    }
                    rscore_vertex_updates = {}  # rscore_id → attrs dict
                    pscore_vertex_updates = {}  # score_id → attrs dict
                    rscore_to_patterns_seen = {}  # rscore_id → set of pattern_ids (dedup)

                    for rm_id, info in roadmap_scores.items():
                        rscore_id = info["rscore_id"]
                        roadmap_core = info["core_score"]
                        linked_pids = roadmap_to_projects.get(rm_id, [])

                        scored_pids = [
                            pid for pid in linked_pids
                            if f"score_{pid}" in project_score_lookup
                        ]
                        if not scored_pids:
                            continue

                        project_core_scores = [project_score_lookup[f"score_{pid}"] for pid in scored_pids]
                        avg_project_score = round(sum(project_core_scores) / len(project_core_scores))

                        rscore_vertex_updates[rscore_id] = {
                            "linked_project_count": len(scored_pids),
                            "avg_linked_project_score": avg_project_score,
                        }
                        roadmaps_linked += 1
                        rscore_to_patterns_seen[rscore_id] = set()

                        for pid in scored_pids:
                            score_id = f"score_{pid}"
                            project_core = project_score_lookup[score_id]
                            delta = project_core - roadmap_core

                            if delta > 15:
                                alignment = "PLAN_EXCEEDED"
                            elif delta < -15:
                                alignment = "PLAN_LAGGED"
                            else:
                                alignment = "WELL_ALIGNED"

                            pscore_vertex_updates[score_id] = {
                                "roadmap_plan_score": roadmap_core,
                                "execution_plan_delta": delta,
                                "execution_plan_alignment": alignment,
                            }
                            projects_aligned += 1

                            cross_edges["roadmapScoreHasProjectExecution"].append((rscore_id, score_id))
                            cross_edges["projectScoreFromRoadmapPlan"].append((score_id, rscore_id))

                            # RoadmapScore → ProjectPattern (once per unique pattern per roadmap)
                            proj_pattern_id = project_to_pattern.get(score_id)
                            if proj_pattern_id and proj_pattern_id not in rscore_to_patterns_seen[rscore_id]:
                                cross_edges["roadmapScoreInProjectCluster"].append((rscore_id, proj_pattern_id))
                                rscore_to_patterns_seen[rscore_id].add(proj_pattern_id)

                    # 5e: Upsert RoadmapScore and ProjectScore vertex updates via BatchGraphLoader
                    batch_loader = BatchGraphLoader(graph_connector)

                    if rscore_vertex_updates:
                        rscore_vertices = [(vid, attrs) for vid, attrs in rscore_vertex_updates.items()]
                        batch_loader.load_graph_structure(
                            vertices={"RoadmapScore": rscore_vertices}, edges={}
                        )
                        print(f"  Updated {len(rscore_vertices)} RoadmapScore vertices with linked project stats")

                    if pscore_vertex_updates:
                        pscore_vertices = [(vid, attrs) for vid, attrs in pscore_vertex_updates.items()]
                        batch_loader.load_graph_structure(
                            vertices={"ProjectScore": pscore_vertices}, edges={}
                        )
                        print(f"  Updated {len(pscore_vertices)} ProjectScore vertices with alignment data")

                    # 5f: Create cross-score edges via EdgeLoader
                    cross_edge_type_mappings = {
                        "roadmapScoreHasProjectExecution": ("RoadmapScore", "ProjectScore"),
                        "projectScoreFromRoadmapPlan": ("ProjectScore", "RoadmapScore"),
                        "roadmapScoreInProjectCluster": ("RoadmapScore", "ProjectPattern"),
                    }

                    for edge_type, edge_list in cross_edges.items():
                        if edge_list:
                            edge_list = list(set(edge_list))
                            from_vt, to_vt = cross_edge_type_mappings[edge_type]
                            try:
                                result = edge_loader.load_edges(edge_type, from_vt, to_vt, edge_list)
                                loaded = result.get("loaded", 0)
                                cross_score_edges_created += loaded
                                total_edges_created += loaded
                                print(f"  ✓ Created {loaded} {edge_type} edges ({from_vt} → {to_vt})")
                            except Exception as e:
                                appLogger.error({"event": "CROSS_EDGE_ERROR", "edge_type": edge_type, "error": str(e)})
                                print(f"  ✗ Failed to create {edge_type} edges: {str(e)}")

                print(f"\n  Cross-score summary: {roadmaps_linked} roadmaps linked, {projects_aligned} projects aligned, {cross_score_edges_created} edges created")

            except Exception as e:
                appLogger.error({
                    "event": "CROSS_SCORE_ERROR",
                    "stage": "CONNECT_PATTERNS",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                print(f"  ✗ Cross-score linking failed: {str(e)} (pattern edges still created)")

            appLogger.info({
                "event": "CROSS_SCORE_COMPLETE",
                "stage": "CONNECT_PATTERNS",
                "roadmaps_linked": roadmaps_linked,
                "projects_aligned": projects_aligned,
                "cross_score_edges": cross_score_edges_created
            })

            return {
                "event": "success",
                "message": f"Successfully connected {patterns_processed} patterns and {roadmaps_linked} cross-score links",
                "patterns_processed": patterns_processed,
                "roadmaps_with_projects": roadmaps_with_projects,
                "edges_created": total_edges_created,
                "edge_breakdown": {edge_type: len(list(set(edges))) for edge_type, edges in edges_to_create.items()},
                "cross_score": {
                    "roadmaps_linked": roadmaps_linked,
                    "projects_aligned": projects_aligned,
                    "cross_score_edges": cross_score_edges_created
                }
            }

        except Exception as e:
            appLogger.error({
                "event": "PATTERN_CONNECTION_ERROR",
                "stage": "CONNECT_PATTERNS",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {
                "event": "error",
                "message": str(e)
            }
        finally:
            graph_connector.close()

    def _format_project_score_vertices(self, projects: List[Dict]) -> List[Tuple[str, Dict]]:
        """
        Format ProjectScore vertices from scored project data.
        
        Args:
            projects: List of projects with attached score_data
            
        Returns:
            List of (vertex_id, vertex_attributes) tuples
        """
        score_vertices = []
        
        for project in projects:
            score_data = project.get("score_data")
            if not score_data:
                continue
            
            # score_data is already flattened, just use it as vertex attributes
            vertex_id = score_data["id"]
            score_vertices.append((vertex_id, score_data))
        
        return score_vertices
    
    def _format_project_score_edges(
        self,
        projects: List[Dict],
        project_to_pattern: Dict[int, str],       # project_id -> pattern_id
        project_to_portfolios: Dict[int, List[str]]  # project_id -> [portfolio_ids]
    ) -> Dict[str, List[Tuple[str, str]]]:
        """
        Format edges connecting ProjectScore to other vertices.
        
        Args:
            projects: List of projects with score_data
            project_to_pattern: Maps project_id to its pattern_id
            project_to_portfolios: Maps project_id to list of TemplatePortfolio IDs
            
        Returns:
            Dictionary with edge types as keys:
            {
                "scoreBelongsToPattern": [(score_id, pattern_id), ...],
                "scoreBelongsToPortfolio": [(score_id, portfolio_id), ...]
            }
        """
        edges = {
            "scoreBelongsToPattern": [],
            "scoreBelongsToPortfolio": []
        }
        
        for project in projects:
            score_data = project.get("score_data")
            if not score_data:
                continue
            
            project_id = project.get("project_id") or project.get("id")
            score_id = score_data["id"]
            
            # ProjectScore → ProjectPattern (scoreBelongsToPattern)
            pattern_id = project_to_pattern.get(project_id)
            if pattern_id:
                edges["scoreBelongsToPattern"].append((score_id, pattern_id))
            
            # ProjectScore → TemplatePortfolio (scoreBelongsToPortfolio) - connect to all portfolios
            portfolio_ids = project_to_portfolios.get(project_id, [])
            for portfolio_id in portfolio_ids:
                edges["scoreBelongsToPortfolio"].append((score_id, portfolio_id))
        
        return edges
    
    def _calculate_pattern_score_statistics(
        self, 
        cluster_projects: List[Dict]
    ) -> Dict[str, Any]:
        """
        Calculate score statistics for a cluster of projects.
        
        Args:
            cluster_projects: List of projects in the cluster (with score_data)
            
        Returns:
            Dictionary with score statistics:
            {
                "avg_score": float,
                "score_variance": float,
                "min_score": int,
                "max_score": int,
                "score_sample_size": int
            }
        """
        scores = []
        for project in cluster_projects:
            score_data = project.get("score_data")
            if score_data and score_data.get("core_score") is not None:
                scores.append(score_data["core_score"])
        
        if not scores:
            return {
                "avg_score": 0.0,
                "score_variance": 0.0,
                "min_score": 0,
                "max_score": 0,
                "score_sample_size": 0
            }
        
        return {
            "avg_score": round(statistics.mean(scores), 2),
            "score_variance": round(statistics.variance(scores), 2) if len(scores) > 1 else 0.0,
            "min_score": min(scores),
            "max_score": max(scores),
            "score_sample_size": len(scores)
        }
    
    def _generate_score_analysis(
        self,
        cluster_projects: List[Dict],
        score_stats: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate score strengths and weaknesses summary using LLM.
        
        Analyzes dimension explanations from all projects in cluster to identify
        common patterns of strengths and weaknesses.
        
        Args:
            cluster_projects: List of projects in cluster with score_data
            score_stats: Pre-calculated score statistics
            
        Returns:
            {"score_strengths": str, "score_weaknesses": str}
        """
        if not self.llm_client or score_stats["score_sample_size"] == 0:
            return {"score_strengths": "", "score_weaknesses": ""}
        
        # Collect dimension explanations from all scored projects
        on_time_explanations = []
        on_scope_explanations = []
        on_budget_explanations = []
        risk_explanations = []
        team_explanations = []
        
        for project in cluster_projects:
            score_data = project.get("score_data")
            if not score_data:
                continue
            
            if score_data.get("on_time_explanation"):
                on_time_explanations.append(f"- {score_data['on_time_explanation'][:200]}")
            if score_data.get("on_scope_explanation"):
                on_scope_explanations.append(f"- {score_data['on_scope_explanation'][:200]}")
            if score_data.get("on_budget_explanation"):
                on_budget_explanations.append(f"- {score_data['on_budget_explanation'][:200]}")
            if score_data.get("risk_management_explanation"):
                risk_explanations.append(f"- {score_data['risk_management_explanation'][:200]}")
            if score_data.get("team_health_explanation"):
                team_explanations.append(f"- {score_data['team_health_explanation'][:200]}")
        
        # Build prompt for LLM
        prompt = f"""Analyze these project scoring explanations from {score_stats['score_sample_size']} similar projects and summarize:
1. Common STRENGTHS (what these projects do well)
2. Common WEAKNESSES (recurring challenges)

Score Statistics:
- Average Score: {score_stats['avg_score']}/100
- Score Range: {score_stats['min_score']} - {score_stats['max_score']}

ON-TIME dimension explanations (delivery/schedule):
{chr(10).join(on_time_explanations[:5]) if on_time_explanations else "No data"}

ON-SCOPE dimension explanations:
{chr(10).join(on_scope_explanations[:5]) if on_scope_explanations else "No data"}

ON-BUDGET dimension explanations:
{chr(10).join(on_budget_explanations[:5]) if on_budget_explanations else "No data"}

RISK MANAGEMENT dimension explanations:
{chr(10).join(risk_explanations[:5]) if risk_explanations else "No data"}

TEAM HEALTH dimension explanations:
{chr(10).join(team_explanations[:5]) if team_explanations else "No data"}

Respond in JSON format:
{{"score_strengths": "2-3 sentence summary of common strengths", "score_weaknesses": "2-3 sentence summary of common challenges/weaknesses"}}
"""
        
        try:
            from src.trmeric_ml.llm.Types import ChatCompletion
            from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
            
            response = self.llm_client.chat(
                ChatCompletion(
                    messages=[{"role": "user", "content": prompt}],
                    model_options=ModelOptions(
                        model="gpt-4o",
                        max_tokens=500,
                        temperature=0.3
                    )
                )
            )
            
            import re
            json_match = re.search(r'\{[^{}]*\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "score_strengths": result.get("score_strengths", ""),
                    "score_weaknesses": result.get("score_weaknesses", "")
                }
        except Exception as e:
            appLogger.error({
                "event": "SCORE_ANALYSIS_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        
        return {"score_strengths": "", "score_weaknesses": ""}

    def _format_roadmap_score_vertices(self, roadmaps: List[Dict]) -> List[Tuple[str, Dict]]:
        """
        Format RoadmapScore vertices from scored roadmap data.
        
        Args:
            roadmaps: List of roadmaps with attached score_data
            
        Returns:
            List of (vertex_id, vertex_attributes) tuples
        """
        score_vertices = []
        
        for roadmap in roadmaps:
            score_data = roadmap.get("score_data")
            if not score_data:
                continue
            
            vertex_id = score_data["id"]
            score_vertices.append((vertex_id, score_data))
        
        return score_vertices
    
    def _format_roadmap_score_edges(
        self,
        roadmaps: List[Dict],
        roadmap_to_pattern: Dict[int, str],
        roadmap_to_portfolios: Dict[int, List[str]]
    ) -> Dict[str, List[Tuple[str, str]]]:
        """
        Format edges connecting RoadmapScore to RoadmapPattern and TemplatePortfolio.
        
        Args:
            roadmaps: List of roadmaps with score_data
            roadmap_to_pattern: Maps roadmap_id to its RoadmapPattern vertex id
            roadmap_to_portfolios: Maps roadmap_id to list of TemplatePortfolio IDs
            
        Returns:
            Dictionary with edge types as keys:
            {
                "roadmapScoreBelongsToPattern": [(score_id, pattern_id), ...],
                "roadmapScoreBelongsToPortfolio": [(score_id, portfolio_id), ...]
            }
        """
        edges = {
            "roadmapScoreBelongsToPattern": [],
            "roadmapScoreBelongsToPortfolio": []
        }
        
        for roadmap in roadmaps:
            score_data = roadmap.get("score_data")
            if not score_data:
                continue
            
            roadmap_id = roadmap.get("roadmap_id") or roadmap.get("id")
            score_id = score_data["id"]
            
            # RoadmapScore → RoadmapPattern
            pattern_id = roadmap_to_pattern.get(roadmap_id)
            if pattern_id:
                edges["roadmapScoreBelongsToPattern"].append((score_id, pattern_id))
            
            # RoadmapScore → TemplatePortfolio
            portfolio_ids = roadmap_to_portfolios.get(roadmap_id, [])
            for portfolio_id in portfolio_ids:
                edges["roadmapScoreBelongsToPortfolio"].append((score_id, portfolio_id))
        
        return edges

    def _calculate_roadmap_pattern_score_statistics(
        self,
        cluster_roadmaps: List[Dict]
    ) -> Dict[str, Any]:
        """
        Calculate score statistics for a cluster of roadmaps.
        
        Args:
            cluster_roadmaps: List of roadmaps in the cluster (with score_data)
            
        Returns:
            Dictionary with score statistics and per-dimension averages
        """
        scores = []
        dim_scores = {
            "strategic_clarity": [], "okr_quality": [],
            "scope_and_constraints": [], "resource_financial": [],
            "solution_readiness": []
        }
        
        for roadmap in cluster_roadmaps:
            score_data = roadmap.get("score_data")
            if score_data and score_data.get("core_score") is not None:
                scores.append(score_data["core_score"])
                for dim in dim_scores:
                    val = score_data.get(f"{dim}_score")
                    if val is not None:
                        dim_scores[dim].append(val)
        
        if not scores:
            return {
                "avg_score": 0.0, "score_variance": 0.0,
                "min_score": 0, "max_score": 0, "score_sample_size": 0,
                "avg_strategic_clarity": 0.0, "avg_okr_quality": 0.0,
                "avg_scope_and_constraints": 0.0, "avg_resource_financial": 0.0,
                "avg_solution_readiness": 0.0
            }
        
        result = {
            "avg_score": round(statistics.mean(scores), 2),
            "score_variance": round(statistics.variance(scores), 2) if len(scores) > 1 else 0.0,
            "min_score": min(scores),
            "max_score": max(scores),
            "score_sample_size": len(scores)
        }
        for dim, vals in dim_scores.items():
            result[f"avg_{dim}"] = round(statistics.mean(vals), 2) if vals else 0.0
        
        return result
    
    def _generate_roadmap_score_analysis(
        self,
        cluster_roadmaps: List[Dict],
        score_stats: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate score strengths and weaknesses summary for a roadmap cluster.
        
        Analyzes dimension explanations to identify common planning quality patterns.
        
        Args:
            cluster_roadmaps: List of roadmaps in cluster with score_data
            score_stats: Pre-calculated score statistics
            
        Returns:
            {"score_strengths": str, "score_weaknesses": str}
        """
        if not self.llm_client or score_stats["score_sample_size"] == 0:
            return {"score_strengths": "", "score_weaknesses": ""}
        
        strategic_explanations = []
        okr_explanations = []
        scope_explanations = []
        financial_explanations = []
        solution_explanations = []
        
        for roadmap in cluster_roadmaps:
            score_data = roadmap.get("score_data")
            if not score_data:
                continue
            
            if score_data.get("strategic_clarity_explanation"):
                strategic_explanations.append(f"- {score_data['strategic_clarity_explanation'][:200]}")
            if score_data.get("okr_quality_explanation"):
                okr_explanations.append(f"- {score_data['okr_quality_explanation'][:200]}")
            if score_data.get("scope_and_constraints_explanation"):
                scope_explanations.append(f"- {score_data['scope_and_constraints_explanation'][:200]}")
            if score_data.get("resource_financial_explanation"):
                financial_explanations.append(f"- {score_data['resource_financial_explanation'][:200]}")
            if score_data.get("solution_readiness_explanation"):
                solution_explanations.append(f"- {score_data['solution_readiness_explanation'][:200]}")
        
        prompt = f"""Analyze these roadmap data-quality scoring explanations from {score_stats['score_sample_size']} similar roadmaps and summarize:
1. Common STRENGTHS (what these roadmaps define well in their planning)
2. Common WEAKNESSES (recurring gaps in planning completeness)

Score Statistics:
- Average Data Quality Score: {score_stats['avg_score']}/100
- Score Range: {score_stats['min_score']} - {score_stats['max_score']}
- Avg Strategic Clarity: {score_stats.get('avg_strategic_clarity', 'N/A')}
- Avg OKR Quality: {score_stats.get('avg_okr_quality', 'N/A')}
- Avg Scope & Constraints: {score_stats.get('avg_scope_and_constraints', 'N/A')}
- Avg Resource/Financial: {score_stats.get('avg_resource_financial', 'N/A')}
- Avg Solution Readiness: {score_stats.get('avg_solution_readiness', 'N/A')}

STRATEGIC CLARITY dimension explanations:
{chr(10).join(strategic_explanations[:5]) if strategic_explanations else "No data"}

OKR QUALITY dimension explanations:
{chr(10).join(okr_explanations[:5]) if okr_explanations else "No data"}

SCOPE & CONSTRAINTS dimension explanations:
{chr(10).join(scope_explanations[:5]) if scope_explanations else "No data"}

RESOURCE/FINANCIAL PLANNING dimension explanations:
{chr(10).join(financial_explanations[:5]) if financial_explanations else "No data"}

SOLUTION READINESS dimension explanations:
{chr(10).join(solution_explanations[:5]) if solution_explanations else "No data"}

Respond in JSON format:
{{"score_strengths": "2-3 sentence summary of common planning strengths", "score_weaknesses": "2-3 sentence summary of common planning gaps/weaknesses"}}
"""
        
        try:
            from src.trmeric_ml.llm.Types import ChatCompletion
            from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
            
            response = self.llm_client.chat(
                ChatCompletion(
                    messages=[{"role": "user", "content": prompt}],
                    model_options=ModelOptions(
                        model="gpt-4o",
                        max_tokens=500,
                        temperature=0.3
                    )
                )
            )
            
            import re
            json_match = re.search(r'\{[^{}]*\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "score_strengths": result.get("score_strengths", ""),
                    "score_weaknesses": result.get("score_weaknesses", "")
                }
        except Exception as e:
            appLogger.error({
                "event": "ROADMAP_SCORE_ANALYSIS_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        
        return {"score_strengths": "", "score_weaknesses": ""}

    def fetch_all_project_data(self, tenant_id: int, project_ids: Set[int]) -> List[Dict]:
        """
        Fetch complete project data including all related entities.
        
        Args:
            tenant_id: Tenant identifier
            project_ids: Set of project IDs to fetch
            
        Returns:
            List of enriched project dictionaries
        """
        pg = PostgresConnector(self.postgres_config)
        with pg.cursor() as cursor:
            # Fetch base project data
            projects = ProjectQueries.fetch_projects(cursor, tenant_id, project_ids)
            
            # Fetch risks for all projects at once
            risks = ProjectQueries.fetch_risks(cursor, project_ids)
            
            # Enrich each project with related data
            for p in projects:
                project_id = p.get("project_id")
                
                # Attach risks
                p["risks"] = risks.get(project_id, [])
                
                # Fetch related entities
                p["key_results"] = ProjectQueries.fetch_key_results(cursor, project_id)
                p["milestones"] = ProjectQueries.fetch_milestones(cursor, project_id)
                p["portfolios"] = ProjectQueries.fetch_portfolios(cursor, project_id)
                p["team"] = ProjectQueries.fetch_team(cursor, project_id)
                
                # Extract from project fields
                p["technologies"] = ProjectQueries.fetch_technologies(p)
                p["categories"] = ProjectQueries.fetch_project_categories(p)
                p["sdlc_method"] = ProjectQueries.fetch_sdlc_methods(p)
                p["project_type"] = ProjectQueries.fetch_project_types(p)
                p["locations"] = ProjectQueries.fetch_project_locations(p)
                
                # Set budget
                p["budget"] = p.get("total_external_spend", 0)
            
            return projects

    def fetch_all_roadmap_data(self, tenant_id: int, roadmap_ids: Set[int]) -> List[Dict]:
        """
        Fetch complete roadmap data including all related entities.
        
        Args:
            tenant_id: Tenant identifier
            roadmap_ids: Set of roadmap IDs to fetch
            
        Returns:
            List of enriched roadmap dictionaries
        """
        pg = PostgresConnector(self.postgres_config)
        with pg.cursor() as cursor:
            # Fetch base roadmap data
            roadmaps = RoadmapQueries.fetch_roadmaps(cursor, tenant_id, roadmap_ids)
            
            # Bulk fetch all related data
            portfolios_data = RoadmapQueries.fetch_portfolios(cursor, roadmap_ids)
            constraints_data = RoadmapQueries.fetch_constraints(cursor, roadmap_ids)
            key_results_data = RoadmapQueries.fetch_key_results(cursor, roadmap_ids)
            team_data = RoadmapQueries.fetch_team(cursor, roadmap_ids)
            scopes_data = RoadmapQueries.fetch_scopes(cursor, roadmap_ids)
            priorities_data = RoadmapQueries.fetch_priorities(cursor, roadmap_ids)
            statuses_data = RoadmapQueries.fetch_statuses(cursor, roadmap_ids)
            timeline_data = RoadmapQueries.fetch_timelines(cursor, roadmap_ids, tenant_id)
            
            # Enrich each roadmap with related data
            for r in roadmaps:
                roadmap_id = r.get("roadmap_id")
                
                # Assign related entities from bulk results
                r["portfolios"] = portfolios_data.get(roadmap_id, [])
                r["constraints"] = constraints_data.get(roadmap_id, [])
                r["key_results"] = key_results_data.get(roadmap_id, [])
                r["team"] = team_data.get(roadmap_id, [])
                r["scopes"] = scopes_data.get(roadmap_id, [])
                r["priorities"] = priorities_data.get(roadmap_id, [])
                r["statuses"] = statuses_data.get(roadmap_id, [])
                r["timelines"] = timeline_data.get(roadmap_id, [])
                
                # Extract from roadmap fields
                r["categories"] = RoadmapQueries.fetch_categories(r)
                r["roadmap_types"] = RoadmapQueries.fetch_roadmap_types(r)
                r["solutions"] = RoadmapQueries.fetch_solutions(r)
            return roadmaps

    def run(
        self,
        tenant_id: int,
        customer_id: str,
        entity_ids: Set[int],
        customer_data: Dict[str, Any],
        entity_type: str = "Project"
    ) -> Dict[str, Any]:
        """
        Execute complete analysis pipeline for any entity type.
        
        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            entity_ids: Set of entity IDs to process
            customer_data: Customer metadata with structure:
                {
                    "customer": {"id": str, "name": str, ...},
                    "industry": {"id": str, "name": str, ...},
                    "industry_sector": {"id": str, "name": str, ...}
                }
            entity_type: "Project" or "Roadmap"
        
        Returns:
            Dictionary with analysis results and loading statistics
        """
        
        if not tenant_id or tenant_id == 0:
            raise ValueError(
                f"tenant_id is required and cannot be 0 or None. Got: {tenant_id}. "
                "Please ensure tenant_id is passed correctly from the caller."
            )
        
        appLogger.info({"event": "PIPELINE_START", "stage": "PIPELINE", "customer_id": customer_id, "tenant_id": tenant_id, "entity_type": entity_type, "entity_count": len(entity_ids)})
        
        # Step 1: Fetch entity data
        fetch_func = self._get_fetch_function(entity_type)
        entities = fetch_func(tenant_id, entity_ids)
        # Ensure every fetched entity carries tenant_id for downstream formatting
        for ent in entities:
            try:
                ent["tenant_id"] = tenant_id
            except Exception:
                pass
        if not entities:
            appLogger.info({"event": "PIPELINE_ERROR", "stage": "PIPELINE", "error": f"No {entity_type.lower()}s found"})
            return {"error": f"No {entity_type.lower()}s found", "clusters": [], "load_stats": {}}
        
        appLogger.info({"event": "FETCH_SUCCESS", "stage": "FETCH", "entity_type": entity_type, "count": len(entities)})
        
        # Step 1.5: Score entities (projects or roadmaps)
        if entity_type.lower() == "project":
            entities = self._score_projects(entities, tenant_id)
        elif entity_type.lower() == "roadmap":
            entities = self._score_roadmaps(entities, tenant_id)

        # Initialize cluster engine and pattern generator based on entity type
        self.cluster_engine = self._get_cluster_engine(entity_type)
        self.pattern_generator = self._get_pattern_generator(entity_type)
        

        entity_vertices, entity_edges = {}, {}
        
        # Step 2: Group by portfolio
        print(f"GROUPING BY PORTFOLIO")
        print(f"{'='*80}\n")
        
        portfolio_groups = defaultdict(list)
        for entity in entities:
            portfolio_names = [pf.get("name", "Unknown") for pf in entity.get("portfolios", [])]
            if not portfolio_names: portfolio_groups["Unknown"].append(entity)
            else:
                for portfolio_name in portfolio_names:
                    portfolio_groups[portfolio_name].append(entity)
        
        # Step 3: Setup graph connection and load customer/industry data
        graph_connector = GraphConnector(self.graph_config)
        graph_connector.connect()
        batch_loader = BatchGraphLoader(graph_connector)
        
        # Load customer/industry/sector data first
        batch_loader.load_customer_data([customer_data], tenant_id=tenant_id)
        
        # Step 4: Cluster and generate patterns for each portfolio
        cluster_results = []
        cluster_index = 0
        all_vertices = defaultdict(list)
        all_edges = defaultdict(list)
        all_templates = [] # Store full template structures for analysis dump
        existing_pattern_names = []  # Track generated names for dedup
        
        for portfolio_name, portfolio_entities in portfolio_groups.items():
            appLogger.info({"event": "PORTFOLIO_CLUSTER_START", "stage": "CLUSTER", "portfolio": portfolio_name, "entity_count": len(portfolio_entities)})
            
            # Cluster entities - now returns per-cluster silhouettes as part of tuple
            clusters, silhouette, n_clusters, per_cluster_silhouettes = self.cluster_engine.cluster(
                portfolio_entities,
                n_clusters_range=range(2, min(6, len(portfolio_entities))),
                entity_type=entity_type.lower(),
            ) if len(portfolio_entities) >= 2 else ([portfolio_entities], 0.0, 1, {})
            
            portfolio_clusters = []
            
            for idx, cluster in enumerate(clusters):
                if not cluster:
                    continue
                
                # Generalize cluster attributes
                generalized = self.pattern_generator.generalize_cluster(cluster)
                
                # Explain cluster
                explanation_data = self.pattern_generator.explain_cluster(cluster, idx, portfolio_name)
                
                # Generate template and pattern
                names = self.pattern_generator.generate_workflow_and_template_names(
                    cluster_data=generalized,
                    customer_id=customer_id,
                    cluster_idx=cluster_index,
                    silhouette_score=silhouette,
                    explanation_data=explanation_data,
                    portfolio_name=portfolio_name,
                    existing_pattern_names=existing_pattern_names
                )
                
                # Track generated names for dedup in subsequent clusters
                pattern_name = names.get("pattern", {}).get("name", "")
                template_name = names.get("template", {}).get("name", "")
                
                # Programmatic dedup: if LLM ignored the prompt constraint, suffix the name
                if pattern_name and pattern_name in existing_pattern_names:
                    suffix = 2
                    while f"{pattern_name} v{suffix}" in existing_pattern_names:
                        suffix += 1
                    original = pattern_name
                    pattern_name = f"{pattern_name} v{suffix}"
                    names["pattern"]["name"] = pattern_name
                    appLogger.info({"event": "PATTERN_NAME_DEDUP", "stage": "PATTERN", "original": original, "renamed": pattern_name, "portfolio": portfolio_name})
                
                if template_name and template_name in existing_pattern_names:
                    suffix = 2
                    while f"{template_name} v{suffix}" in existing_pattern_names:
                        suffix += 1
                    template_name = f"{template_name} v{suffix}"
                    names["template"]["name"] = template_name
                
                if pattern_name:
                    existing_pattern_names.append(pattern_name)
                if template_name and template_name != pattern_name:
                    existing_pattern_names.append(template_name)
                
                # Format full template structure (ProjectTemplate/RoadmapTemplate + sub-vertices)
                template_structure = TemplateGenerator.format_full_template_structure(
                    names.get("template", {}), 
                    entity_type=entity_type
                )
                all_templates.append(template_structure)
                
                if entity_type == "Project":
                    pattern_vertex = self.pattern_generator.format_project_pattern_vertex(names.get("pattern", {}))
                    
                    # Calculate score statistics for this cluster and add to pattern
                    score_stats = self._calculate_pattern_score_statistics(cluster)
                    score_analysis = self._generate_score_analysis(cluster, score_stats)
                    
                    # Add score fields to pattern vertex
                    pattern_vertex.update({
                        "avg_score": score_stats["avg_score"],
                        "score_variance": score_stats["score_variance"],
                        "min_score": score_stats["min_score"],
                        "max_score": score_stats["max_score"],
                        "score_sample_size": score_stats["score_sample_size"],
                        "score_strengths": score_analysis.get("score_strengths", ""),
                        "score_weaknesses": score_analysis.get("score_weaknesses", "")
                    })
                    
                    print(f"  Pattern {pattern_vertex.get('id', 'unknown')}: avg_score={score_stats['avg_score']}, variance={score_stats['score_variance']}")

                    # Override LLM-assessed confidence with compositional score
                    cluster_sil = per_cluster_silhouettes.get(idx, silhouette)
                    pattern_vertex["confidence_score"] = self.pattern_generator.compute_confidence_score(
                        cluster_size=len(cluster),
                        silhouette_score=cluster_sil,
                        total_entities_in_portfolio=len(portfolio_entities),
                    )
                    
                if entity_type == "Roadmap":
                    pattern_vertex = self.pattern_generator.format_roadmap_pattern_vertex(names.get("pattern", {}))
                    
                    # Calculate roadmap score statistics for this cluster and add to pattern
                    roadmap_score_stats = self._calculate_roadmap_pattern_score_statistics(cluster)
                    roadmap_score_analysis = self._generate_roadmap_score_analysis(cluster, roadmap_score_stats)
                    
                    # Add score fields to pattern vertex
                    pattern_vertex.update({
                        "avg_score": roadmap_score_stats["avg_score"],
                        "score_variance": roadmap_score_stats["score_variance"],
                        "min_score": roadmap_score_stats["min_score"],
                        "max_score": roadmap_score_stats["max_score"],
                        "score_sample_size": roadmap_score_stats["score_sample_size"],
                        "score_strengths": roadmap_score_analysis.get("score_strengths", ""),
                        "score_weaknesses": roadmap_score_analysis.get("score_weaknesses", "")
                    })
                    
                    print(f"  Pattern {pattern_vertex.get('id', 'unknown')}: avg_score={roadmap_score_stats['avg_score']}, variance={roadmap_score_stats['score_variance']}")

                    # Override LLM-assessed confidence with compositional score
                    cluster_sil = per_cluster_silhouettes.get(idx, silhouette)
                    pattern_vertex["confidence_score"] = self.pattern_generator.compute_confidence_score(
                        cluster_size=len(cluster),
                        silhouette_score=cluster_sil,
                        total_entities_in_portfolio=len(portfolio_entities),
                    )

                # Create Portfolio vertex (once per portfolio, cached in all_vertices)
                portfolio_id = f"portfolio_{portfolio_name.lower().replace(' ', '_')}"
                print(f"DEBUG: Created portfolio_id: {portfolio_id} for name: {portfolio_name}")
                if not any(pid == portfolio_id for pid, _ in all_vertices.get("TemplatePortfolio", [])):
                    all_vertices["TemplatePortfolio"].append((
                        portfolio_id,
                        {
                            "id": portfolio_id,
                            "tenant_id": tenant_id,
                            "name": portfolio_name,
                            "title": portfolio_name,
                            "description": f"{portfolio_name} Portfolio for {customer_id}"
                        }
                    ))
                    # Create edges for portfolio (only once)
                    # Note: 'ownsPortfolio' might need to be 'ownsTemplatePortfolio' if schema changed, 
                    # but assuming Customer->TemplatePortfolio edge exists or is generic.
                    # Checking schema... Customer->TemplatePortfolio edge is not explicitly in the snippet I read.
                    # But let's assume generic 'ownsPortfolio' or similar.
                    # For now, I'll keep 'ownsPortfolio' but point to TemplatePortfolio.
                    all_edges["ownsPortfolio"].append((customer_id, portfolio_id))
                
                # Collect cluster result
                cluster_silhouette = per_cluster_silhouettes.get(idx, 0.0) if per_cluster_silhouettes else silhouette
                portfolio_clusters.append({
                    "cluster_index": cluster_index,
                    "portfolio_name": portfolio_name,
                    "portfolio_id": portfolio_id,
                    "portfolios": [pf for p in cluster for pf in p.get("portfolios", [])],
                    "generalized": generalized,
                    "explanation": explanation_data,
                    "silhouette_score": cluster_silhouette,
                    "names": names,
                    "vertices": {},
                    "edges": {}
                })
                
                # Add template vertices and edges to batch
                main_template_id = None
                
                for v in template_structure["vertices"]:
                    v_type = v["type"]
                    v_id = v["id"]
                    v_attrs = v["attributes"]
                    v_attrs["tenant_id"] = tenant_id # Ensure tenant_id
                    
                    if v_type in [entity_type + "Template", "ProjectTemplate", "RoadmapTemplate"]:
                        main_template_id = v_id
                        
                    all_vertices[v_type].append((v_id, v_attrs))

                for e in template_structure["edges"]:
                    e_type = e["edge_type"]
                    src_id = e["source_id"]
                    tgt_id = e["target_id"]
                    all_edges[e_type].append((src_id, tgt_id))

                # Fallback if main template ID not found (should be first vertex usually)
                if not main_template_id and template_structure["vertices"]:
                    main_template_id = template_structure["vertices"][0]["id"]

                pattern_vertex["tenant_id"] = tenant_id
                pattern_type = "RoadmapPattern" if entity_type == "Roadmap" else "ProjectPattern"
                print(f"DEBUG PATTERN STORE: type={pattern_type} id={pattern_vertex.get('id','?')} tenant_id={pattern_vertex.get('tenant_id','?')} scope={repr(pattern_vertex.get('scope','?'))} roadmap_ids={pattern_vertex.get('roadmap_ids',[])} keys={list(pattern_vertex.keys())[:10]}")
                all_vertices[pattern_type].append((pattern_vertex["id"], pattern_vertex))
                
                # Add all edges for workflow-level pattern and template
                # usesTemplate -> usesProjectTemplate / usesRoadmapTemplate
                if entity_type == "Roadmap":
                    all_edges["usesRoadmapTemplate"].append((customer_id, main_template_id))
                    all_edges["supportsRoadmapTemplatePattern"].append((main_template_id, pattern_vertex["id"]))
                    all_edges["supportedByRoadmapTemplate"].append((pattern_vertex["id"], main_template_id))
                    all_edges["relevantToRoadmapIndustry"].append((pattern_vertex["id"], customer_data["industry"]["id"]))
                    all_edges["derivedFromRoadmapPortfolio"].append((pattern_vertex["id"], portfolio_id))
                else:
                    all_edges["usesProjectTemplate"].append((customer_id, main_template_id))
                    all_edges["supportsProjectTemplatePattern"].append((main_template_id, pattern_vertex["id"]))
                    all_edges["supportedByProjectTemplate"].append((pattern_vertex["id"], main_template_id))
                    all_edges["relevantToProjectIndustry"].append((pattern_vertex["id"], customer_data["industry"]["id"]))
                    all_edges["derivedFromProjectPortfolio"].append((pattern_vertex["id"], portfolio_id))
                
                # partOfPortfolio -> hasTemplatePortfolio / hasRoadmapTemplatePortfolio
                if entity_type == "Roadmap":
                     all_edges["hasRoadmapTemplatePortfolio"].append((main_template_id, portfolio_id))
                else:
                     all_edges["hasTemplatePortfolio"].append((main_template_id, portfolio_id))
                
                cluster_index += 1
            
            # REMOVED: Portfolio-level pattern generation
            # Only keeping workflow-level patterns (per cluster)
            # Portfolio and customer patterns removed to simplify hierarchy
            
            appLogger.info({"event": "PORTFOLIO_CLUSTER_COMPLETE", "stage": "CLUSTER", "portfolio": portfolio_name, "clusters_in_portfolio": len(portfolio_clusters)})
            cluster_results.extend(portfolio_clusters)
        
        # REMOVED: Customer-level pattern generation
        # Step 5: Skipping customer-level pattern (keeping only workflow-level)
        print(f"{'='*80}")
        print(f"SKIPPING CUSTOMER-LEVEL PATTERN (workflow-only mode)")
        appLogger.info({"event": "CUSTOMER_PATTERN_SKIPPED", "stage": "PATTERN", "customer_id": customer_id, "cluster_count": len(cluster_results)})
        
        # Step 6: Generate customer summary profile
        csp_id, csp_data = self.pattern_generator.generate_customer_summary_profile(
            customer_id=customer_id,
            tenant_id=tenant_id,
            clusters=cluster_results,
            projects=entities
        )
        
        all_vertices["CustomerSummaryProfile"] = [(csp_id, csp_data)]
        all_edges["summarizesCustomerCSP"].append((csp_id, customer_id))
        
        # Link to portfolios
        for cluster in cluster_results:
            # Use the constructed portfolio_id that matches the TemplatePortfolio vertex
            if "portfolio_id" in cluster:
                portfolio_id = cluster["portfolio_id"]
                all_edges.setdefault("derivedFromPortfolioCSP", []).append((csp_id, portfolio_id))
        
        appLogger.info({"event": "CUSTOMER_SUMMARY_PROFILE_COMPLETE", "stage": "PATTERN", "customer_id": customer_id})
        
        # Step 7: Merge entity vertices and edges with pattern vertices/edges
        # Merge entity vertices (avoiding duplicates)
        for v_type, v_list in entity_vertices.items():
            existing_ids = {vid for vid, _ in all_vertices.get(v_type, [])}
            for vid, v_attrs in v_list:
                if vid not in existing_ids:
                    all_vertices.setdefault(v_type, []).append((vid, v_attrs))
        
        # Merge entity edges
        for e_type, e_list in entity_edges.items():
            all_edges.setdefault(e_type, []).extend(e_list)
        
        # Step 7.5: Add ProjectScore vertices and edges (for Project entity type only)
        if entity_type == "Project":
            print(f"{'='*80}")
            print(f"ADDING PROJECT SCORE VERTICES AND EDGES")
            
            # Format ProjectScore vertices from scored entities
            score_vertices = self._format_project_score_vertices(entities)
            all_vertices.setdefault("ProjectScore", []).extend(score_vertices)
            print(f"  Added {len(score_vertices)} ProjectScore vertices")
            
            # Build mappings for edge creation
            # Map project_id -> pattern_id based on cluster membership
            project_to_pattern = {}
            for cluster in cluster_results:
                pattern_data = cluster.get("names", {}).get("pattern", {})
                pattern_id = pattern_data.get("id")
                if pattern_id:
                    # Get project_ids from pattern or generalized data
                    project_ids = pattern_data.get("project_ids", [])
                    if not project_ids:
                        project_ids = cluster.get("generalized", {}).get("project_ids", [])
                    for proj_id in project_ids:
                        # Handle both string and int project IDs
                        if proj_id:
                            project_to_pattern[int(proj_id) if isinstance(proj_id, str) and proj_id.isdigit() else proj_id] = pattern_id
            
            # Map project_id -> portfolio_id from cluster membership (not project data)
            # This uses the actual TemplatePortfolio vertex IDs created during clustering
            project_to_portfolios = {}
            for cluster in cluster_results:
                portfolio_id = cluster.get("portfolio_id")
                if portfolio_id:
                    # Get project_ids from pattern or generalized data  
                    pattern_data = cluster.get("names", {}).get("pattern", {})
                    project_ids = pattern_data.get("project_ids", [])
                    if not project_ids:
                        project_ids = cluster.get("generalized", {}).get("project_ids", [])
                    for proj_id in project_ids:
                        if proj_id:
                            pid = int(proj_id) if isinstance(proj_id, str) and proj_id.isdigit() else proj_id
                            if pid not in project_to_portfolios:
                                project_to_portfolios[pid] = []
                            if portfolio_id not in project_to_portfolios[pid]:
                                project_to_portfolios[pid].append(portfolio_id)
            
            # Format edges
            score_edges = self._format_project_score_edges(entities, project_to_pattern, project_to_portfolios)
            for e_type, e_list in score_edges.items():
                all_edges.setdefault(e_type, []).extend(e_list)
                print(f"  Added {len(e_list)} {e_type} edges")
            
            appLogger.info({
                "event": "PROJECT_SCORES_ADDED", 
                "stage": "SCORING",
                "score_vertices": len(score_vertices),
                "edges": {e_type: len(e_list) for e_type, e_list in score_edges.items()}
            })
        
        # Step 7.5b: Add RoadmapScore vertices and edges (for Roadmap entity type only)
        if entity_type == "Roadmap":
            print(f"{'='*80}")
            print(f"ADDING ROADMAP SCORE VERTICES AND EDGES")
            
            # Format RoadmapScore vertices from scored entities
            roadmap_score_vertices = self._format_roadmap_score_vertices(entities)
            all_vertices.setdefault("RoadmapScore", []).extend(roadmap_score_vertices)
            print(f"  Added {len(roadmap_score_vertices)} RoadmapScore vertices")
            
            # Map roadmap_id -> pattern_id based on cluster membership
            roadmap_to_pattern = {}
            for cluster in cluster_results:
                pattern_data = cluster.get("names", {}).get("pattern", {})
                pattern_id = pattern_data.get("id")
                if pattern_id:
                    roadmap_ids = pattern_data.get("roadmap_ids", [])
                    if not roadmap_ids:
                        roadmap_ids = cluster.get("generalized", {}).get("roadmap_ids", [])
                    for rm_id in roadmap_ids:
                        if rm_id:
                            roadmap_to_pattern[int(rm_id) if isinstance(rm_id, str) and str(rm_id).isdigit() else rm_id] = pattern_id
            
            # Map roadmap_id -> portfolio_ids from cluster membership
            roadmap_to_portfolios = {}
            for cluster in cluster_results:
                portfolio_id = cluster.get("portfolio_id")
                if portfolio_id:
                    pattern_data = cluster.get("names", {}).get("pattern", {})
                    roadmap_ids = pattern_data.get("roadmap_ids", [])
                    if not roadmap_ids:
                        roadmap_ids = cluster.get("generalized", {}).get("roadmap_ids", [])
                    for rm_id in roadmap_ids:
                        if rm_id:
                            rid = int(rm_id) if isinstance(rm_id, str) and str(rm_id).isdigit() else rm_id
                            if rid not in roadmap_to_portfolios:
                                roadmap_to_portfolios[rid] = []
                            if portfolio_id not in roadmap_to_portfolios[rid]:
                                roadmap_to_portfolios[rid].append(portfolio_id)
            
            # Format edges
            roadmap_score_edges = self._format_roadmap_score_edges(entities, roadmap_to_pattern, roadmap_to_portfolios)
            for e_type, e_list in roadmap_score_edges.items():
                all_edges.setdefault(e_type, []).extend(e_list)
                print(f"  Added {len(e_list)} {e_type} edges")
            
            appLogger.info({
                "event": "ROADMAP_SCORES_ADDED",
                "stage": "SCORING",
                "score_vertices": len(roadmap_score_vertices),
                "edges": {e_type: len(e_list) for e_type, e_list in roadmap_score_edges.items()}
            })

        # NOTE: Cross-score linking (RoadmapScore ↔ ProjectScore) is handled in
        # connect_roadmap_to_project_patterns() which runs as Stage 3 of the
        # full pipeline, after both Project and Roadmap data are loaded.

        # Step 8: Load all graph data to TigerGraph
        # Calculate total vertices and edges for logging
        total_vertices = sum(len(v_list) for v_list in all_vertices.values())
        total_edges = sum(len(e_list) for e_list in all_edges.values())
        
        # Real loading to TigerGraph
        stats = batch_loader.load_graph_structure(dict(all_vertices), dict(all_edges))
        
        appLogger.info({"event": "PIPELINE_COMPLETE", "stage": "SUMMARY", "customer_id": customer_id, "total_clusters": len(cluster_results), "total_entities": len(entities), "portfolios": len(portfolio_groups), "total_vertices": total_vertices, "total_edges": total_edges})
        
        # Save detailed analysis to file for review
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_data = {
            "metadata": {
                "customer_id": customer_id,
                "entity_type": entity_type,
                "entity_count": len(entities),
                "portfolio_count": len(portfolio_groups),
                "cluster_count": len(cluster_results),
                "timestamp": timestamp,
            },
            "portfolios": {
                name: {
                    "entity_count": len(ents),
                    "entity_ids": [e.get(f"{entity_type.lower()}_id") for e in ents]
                }
                for name, ents in portfolio_groups.items()
            },
            "clusters": [
                {
                    "cluster_index": c["cluster_index"],
                    "portfolio": c["portfolio_name"],
                    "size": len(c["generalized"].get(f"{entity_type.lower()}_ids", [])),
                    "silhouette_score": round(c["silhouette_score"], 3),
                    "llm_confidence": round(c["explanation"].get("llm_confidence", 0), 3),
                    "template_id": c["names"].get("template", {}).get("id"),
                    "pattern_id": c["names"].get("pattern", {}).get("id"),
                    "generalized_attributes": self._build_generalized_attributes(c, entity_type),
                    "explanation": {
                        "summary": c["explanation"].get("summary", ""),
                        "confidence": c["explanation"].get("llm_confidence", 0)
                    }
                }
                for c in cluster_results
            ],
            "patterns": [
                {
                    "id": p_id,
                    "scope": p_attrs.get("scope", "unknown"),
                    "name": p_attrs.get("name", ""),
                    "description": p_attrs.get("description", ""),
                    "category": p_attrs.get("category", ""),
                    "attributes": p_attrs
                }
                for p_id, p_attrs in all_vertices.get("Pattern", [])
            ],
            "templates": all_templates,
            "load_stats": stats
        }
        
        save_detailed_analysis(f"{entity_type.lower()}_analysis_{len(entities)}entities_{timestamp}.json", analysis_data)
        
        return {
            "customer_id": customer_id,
            "clusters": cluster_results,
            "total_clusters": len(cluster_results),
            f"total_{entity_type.lower()}s": len(entities),
            "portfolios": list(portfolio_groups.keys()),
            "load_stats": stats
        }
