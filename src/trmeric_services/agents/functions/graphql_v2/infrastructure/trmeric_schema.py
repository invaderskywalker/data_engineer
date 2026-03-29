"""
TrmericGraph Consolidated Schema Definition

Single source of truth for all TigerGraph schemas used in graphql_v2.
Consolidates the schema_registry.py format into a unified module.

Provides:
- PROJECT_SCHEMA: Complete project entity schema with all vertices
- ROADMAP_SCHEMA: Complete roadmap entity schema with all vertices
- Pattern/Template/Analysis schemas
- GSQL schema creation scripts
- Utility functions for schema introspection
"""

from typing import Dict, List, Any

# Import existing model classes
from ..models.graph_schema import GraphSchema, SchemaEntity
from ..models.privacy_models import PrivacyConfig, PrivacyScope


INT_FIELDS = {
    "company_size", "employees", "adoption_count", "template_adoption_count", "avg_project_duration",
    "project_duration_avg", "tenant_id",
    # ProjectScore fields
    "project_id", "roadmap_id", "core_score", "on_time_score", "on_scope_score", "on_budget_score",
    "risk_management_score", "team_health_score", "confidence_overall",
    "confidence_status_fields", "confidence_milestones", "confidence_comments",
    "confidence_risks", "confidence_team_data", "data_completeness_pct",
    "milestone_avg_delay_days", "milestone_completed_count", "complication_blocker_count",
    "maturity_score", "retrospective_score", "value_realization_score",
    "min_score", "max_score", "score_sample_size",
    # RoadmapScore fields
    "roadmap_id_score", "core_score_roadmap",
    "strategic_clarity_score", "okr_quality_score", "scope_and_constraints_score",
    "resource_financial_score", "solution_readiness_score",
    "confidence_core_fields", "confidence_okr_completeness",
    "confidence_scope_coverage", "confidence_financial_data", "confidence_alignment_signal",
    # Cross-score linking fields (RoadmapScore ↔ ProjectScore)
    "roadmap_plan_score", "execution_plan_delta", "linked_project_count", "avg_linked_project_score",
    # PortfolioPattern fields
    "portfolio_id", "workflow_pattern_count", "roadmap_pattern_count", "project_pattern_count",
    "total_execution_count", "execution_coverage_pct", "median_score",
    # CustomerPattern fields
    "portfolio_count", "total_roadmap_patterns", "total_project_patterns",
    "portfolios_with_execution"
}

DOUBLE_FIELDS = {
    "revenue", "it_budget", "budget", "planned_spend", "planned_spend_amount",
    "actual_spend", "actual_spend_amount", "validity_score", "llm_confidence",
    "execution_velocity_score", "milestone_duration_avg", "avg_milestone_velocity",
    "confidence_score", "support_score", "avg_velocity", "portfolio_diversity_score",
    "tech_breadth_score", "template_success_rate", "execution_risk_score",
    "delivery_success_score", "milestone_adherence_score", "value_probability",
    "completion_percentage", "weight",
    "total_external_spend", "target_value", "baseline_value", "current_value",
    # ProjectScore fields
    "milestone_on_time_ratio", "complication_resolution_rate",
    # Pattern score fields
    "avg_score", "score_variance",
    # PortfolioPattern fields
    "avg_core_score", "score_variance_across_patterns", "avg_on_time_score",
    "avg_on_scope_score", "avg_on_budget_score", "avg_risk_management_score",
    "avg_team_health_score", "avg_quality_score",
    # CustomerPattern fields
    "org_avg_execution_score", "org_avg_on_time_score", "org_avg_on_scope_score",
    "org_avg_on_budget_score", "org_avg_risk_score"
}

# Attributes that should be LIST<STRING> in GSQL
LIST_STRING_FIELDS = {
    "regulatory_requirements", "dev_methodology", "work_type_distribution",
    "technologies_used", "team_roles", "key_technologies", "team_composition",
    "dev_methodology_dist", "key_risk_mitigations", "key_milestones", "key_kpis",
    "constraints", "project_ids", "learning_areas", "preferred_workflows",
    "most_common_kpis", "common_challenges", "portfolio_pattern_adoption",
    # Roadmap Pattern specific
    "common_scopes", "common_priorities", "common_statuses", "roadmap_ids",
    "solution_themes", "solution_approaches", "solution_success_criteria",
    "team_allocations", "resource_distribution", "expected_outcomes_summary",
    "delivery_themes", "delivery_approaches", "delivery_success_criteria",
    "state_transition_history", "typical_state_flow", "stage_duration_insights",
    # PortfolioPattern specific
    "top_performing_pattern_ids", "dimensions_with_sufficient_data", "missing_dimensions",
    "dimension_strength_ranking", "recommended_actions", "cross_pattern_insights",
    # CustomerPattern specific
    "key_capabilities", "capability_gaps", "strategic_recommendations",
    "top_technologies", "emerging_risks", "investment_priorities"
}

# Attributes that should be LIST<DOUBLE>
LIST_DOUBLE_FIELDS = {"avg_delay_distribution"}

# Attributes that should be BOOL in GSQL
BOOL_FIELDS = {"approved"}



# ─── Project Template Schema ───────────────────────────────────────────────────

PROJECT_TEMPLATE_SCHEMA = GraphSchema(
    entity_type="ProjectTemplate",
    vertices={
        "ProjectTemplate": SchemaEntity(
            name="ProjectTemplate",
            attributes=[
                "id", "tenant_id", "name", "title", "description", "start_date", "end_date", 
                "project_type", "sdlc_method", "state", "project_category",
                "delivery_status", "scope_status", "spend_status",
                "objectives", "org_strategy_align", "total_external_spend"
            ],
            privacy_config=PrivacyConfig(
                public_fields={"id", "state", "delivery_status", "scope_status", "spend_status", "project_type", "project_category"},
                private_fields={"tenant_id", "title", "description", "start_date", "end_date", "sdlc_method", "objectives", "org_strategy_align", "total_external_spend"},
                anonymized_fields={"title", "description", "objectives"}
            ),
            description="Template for a project execution workflow"
        ),
        "TemplatePortfolio": SchemaEntity(
            name="TemplatePortfolio",
            attributes=["id", "tenant_id", "name", "title", "description"],
            privacy_config=PrivacyConfig(
                public_fields={"id"},
                private_fields={"tenant_id", "title"},
                anonymized_fields={"title"}
            ),
            description="Portfolio grouping for templates"
        ),
        "TemplateMilestone": SchemaEntity(
            name="TemplateMilestone",
            attributes=[
                "id", "tenant_id", "name", "description", "planned_spend", "actual_spend",
                "target_date", "actual_date", "comments",
                "status_value", "milestone_type", "due_date", "status", "completion_percentage", "weight", "phase"
            ],
            privacy_config=PrivacyConfig(
                public_fields={"id", "milestone_type", "status_value", "status", "completion_percentage", "weight", "phase"},
                private_fields={"tenant_id", "name", "planned_spend", "actual_spend", "target_date", "actual_date", "comments", "due_date"},
                anonymized_fields={"name", "comments"}
            ),
            description="Milestone definition within a template"
        ),
        "TemplateStatus": SchemaEntity(
            name="TemplateStatus",
            attributes=["id", "tenant_id", "name", "status_type", "status_value", "comments", "created_date"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "status_type", "status_value", "created_date"},
                private_fields={"tenant_id", "comments"},
                anonymized_fields={"comments"}
            ),
            description="Status definition for template"
        ),
        "TemplateTechnology": SchemaEntity(
            name="TemplateTechnology",
            attributes=["id", "tenant_id", "name", "category", "version", "license_type", "approved"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name", "category"},
                private_fields={"tenant_id", "version", "license_type", "approved"},
                anonymized_fields=set()
            ),
            description="Technology stack for template"
        ),
        "TemplateKeyResult": SchemaEntity(
            name="TemplateKeyResult",
            attributes=["id", "tenant_id", "name", "description", "target_value", "current_value", "unit", "frequency", "owner"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "unit", "frequency"},
                private_fields={"tenant_id", "name", "description", "target_value", "current_value", "owner"},
                anonymized_fields={"name"}
            ),
            description="KPI definition for template"
        ),
        "TemplateProjectType": SchemaEntity(
            name="TemplateProjectType",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="Project type classification for template"
        ),
        "TemplateSdlcMethod": SchemaEntity(
            name="TemplateSdlcMethod",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="SDLC methodology for template"
        ),
        "TemplateProjectCategory": SchemaEntity(
            name="TemplateProjectCategory",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="Category classification for template"
        ),
        "TemplateProjectLocation": SchemaEntity(
            name="TemplateProjectLocation",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="Location context for template"
        ),
    },
    edges={
        "hasTemplatePortfolio": {"from": "ProjectTemplate", "to": "TemplatePortfolio"},
        "hasTemplateMilestone": {"from": "ProjectTemplate", "to": "TemplateMilestone"},
        "hasTemplateStatus": {"from": "ProjectTemplate", "to": "TemplateStatus"},
        "hasTemplateTechnology": {"from": "ProjectTemplate", "to": "TemplateTechnology"},
        "hasTemplateKeyResult": {"from": "ProjectTemplate", "to": "TemplateKeyResult"},
        "hasTemplateProjectType": {"from": "ProjectTemplate", "to": "TemplateProjectType"},
        "hasTemplateSdlcMethod": {"from": "ProjectTemplate", "to": "TemplateSdlcMethod"},
        "hasTemplateProjectCategory": {"from": "ProjectTemplate", "to": "TemplateProjectCategory"},
        "hasTemplateProjectLocation": {"from": "ProjectTemplate", "to": "TemplateProjectLocation"},
    }
)

# ─── Roadmap Template Schema ──────────────────────────────────────────────────

ROADMAP_TEMPLATE_SCHEMA = GraphSchema(
    entity_type="RoadmapTemplate",
    vertices={
        "RoadmapTemplate": SchemaEntity(
            name="RoadmapTemplate",
            attributes=[
                "id", "tenant_id", "name", "title", "description", "objectives", "start_date",
                "end_date", "budget", "category", "org_strategy_align",
                "priority", "current_state", "roadmap_type", "status", "visibility", "solution",
                "version", "owner_id", "strategic_goal", "time_horizon", "review_cycle", "tags",
                "created_at", "updated_at", "template_source", "adoption_count", "validity_score"
            ],
            privacy_config=PrivacyConfig(
                public_fields={"id", "category", "start_date", "end_date", "priority", "current_state", "roadmap_type", "version", "time_horizon", "review_cycle", "adoption_count", "validity_score"},
                private_fields={"tenant_id", "title", "description", "objectives", "budget", "org_strategy_align", "owner_id", "strategic_goal", "tags", "created_at", "updated_at", "template_source", "solution"},
                anonymized_fields={"title", "description", "objectives"}
            ),
            description="Template for a strategic roadmap"
        ),
        "TemplateConstraint": SchemaEntity(
            name="TemplateConstraint",
            attributes=["id", "tenant_id", "name", "description", "constraint_type", "impact_level", "status"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "constraint_type", "impact_level", "status"},
                private_fields={"tenant_id", "name", "description"},
                anonymized_fields={"name", "description"}
            ),
            description="Constraint definition for roadmap template"
        ),
        "TemplateRoadmapKeyResult": SchemaEntity(
            name="TemplateRoadmapKeyResult",
            attributes=["id", "tenant_id", "name", "description", "baseline_value", "target_value"],
            privacy_config=PrivacyConfig(
                public_fields={"id"},
                private_fields={"tenant_id", "name", "description", "baseline_value", "target_value"},
                anonymized_fields={"name", "description"}
            ),
            description="Key result definition for roadmap template"
        ),
        "TemplateTeam": SchemaEntity(
            name="TemplateTeam",
            attributes=[
                "id", "tenant_id", "name", "unit", "unit_type", "labour_type",
                "description", "start_date", "end_date", "location",
                "allocation", "total_estimated_hours", "total_estimated_cost"
            ],
            privacy_config=PrivacyConfig(
                public_fields={"id", "unit_type", "labour_type", "location"},
                private_fields={"tenant_id", "name", "unit", "description", "start_date", "end_date", "allocation", "total_estimated_hours", "total_estimated_cost"},
                anonymized_fields={"name", "unit", "description"}
            ),
            description="Team resource definition for roadmap template"
        ),
        "TemplateScope": SchemaEntity(
            name="TemplateScope",
            attributes=["id", "tenant_id", "name", "description", "priority", "status", "complexity"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "priority", "status", "complexity"},
                private_fields={"tenant_id", "name", "description"},
                anonymized_fields={"name", "description"}
            ),
            description="Scope definition for roadmap template"
        ),
        "TemplatePriority": SchemaEntity(
            name="TemplatePriority",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="Priority level for roadmap template"
        ),
        "TemplateRoadmapStatus": SchemaEntity(
            name="TemplateRoadmapStatus",
            attributes=["id", "tenant_id", "name"],
            privacy_config=PrivacyConfig(
                public_fields={"id", "name"},
                private_fields={"tenant_id"},
                anonymized_fields=set()
            ),
            description="Status definition for roadmap template"
        ),
        "TemplateSolution": SchemaEntity(
            name="TemplateSolution",
            attributes=[
                "id", "tenant_id", "title", "description", "solution_approach", "expected_outcomes",
                "implementation_steps", "success_criteria", "created_at", "updated_at"
            ],
            privacy_config=PrivacyConfig(
                public_fields={"id", "title"},
                private_fields={"tenant_id", "description", "solution_approach", "expected_outcomes", "implementation_steps", "success_criteria", "created_at", "updated_at"},
                anonymized_fields={"description", "solution_approach", "expected_outcomes", "implementation_steps", "success_criteria"}
            ),
            description="Solution definition for roadmap template"
        ),
        "TemplatePortfolio": SchemaEntity(
            name="TemplatePortfolio",
            attributes=["id", "tenant_id", "name", "title", "description"],
            privacy_config=PrivacyConfig(
                public_fields={"id"},
                private_fields={"tenant_id", "title", "name", "description"},
                anonymized_fields={"title", "name", "description"}
            ),
            description="Portfolio grouping for roadmap templates"
        ),
    },
    edges={
        "hasRoadmapTemplatePortfolio": {"from": "RoadmapTemplate", "to": "TemplatePortfolio"},
        "hasTemplateConstraint": {"from": "RoadmapTemplate", "to": "TemplateConstraint"},
        "hasTemplateRoadmapKeyResult": {"from": "RoadmapTemplate", "to": "TemplateRoadmapKeyResult"},
        "hasTemplateTeam": {"from": "RoadmapTemplate", "to": "TemplateTeam"},
        "hasTemplateScope": {"from": "RoadmapTemplate", "to": "TemplateScope"},
        "hasTemplatePriority": {"from": "RoadmapTemplate", "to": "TemplatePriority"},
        "hasTemplateRoadmapStatus": {"from": "RoadmapTemplate", "to": "TemplateRoadmapStatus"},
        "hasTemplateSolution": {"from": "RoadmapTemplate", "to": "TemplateSolution"},
        "hasTemplateMilestone": {"from": "RoadmapTemplate", "to": "TemplateMilestone"},
    }
)

# ─── Cross-Cutting Entities ───────────────────────────────────────────────────

CROSS_CUTTING_VERTICES = {
    "Customer": SchemaEntity(
        name="Customer",
        attributes=["id", "tenant_id", "name", "company_size", "location", "revenue", "employees", "it_budget", "created_date"],
        privacy_config=PrivacyConfig(
            public_fields={"id", "company_size", "location"},
            private_fields={"tenant_id", "name", "revenue", "employees", "it_budget", "created_date"},
            anonymized_fields={"name", "location"}
        ),
        description="Customer entity"
    ),
    "Industry": SchemaEntity(
        name="Industry",
        attributes=["id", "tenant_id", "name", "regulatory_requirements"],
        privacy_config=PrivacyConfig(
            public_fields={"id", "name"},
            private_fields={"tenant_id", "regulatory_requirements"},
            anonymized_fields=set()
        ),
        description="Industry classification"
    ),
    "IndustrySector": SchemaEntity(
        name="IndustrySector",
        attributes=["id", "tenant_id", "name", "description"],
        privacy_config=PrivacyConfig(
            public_fields={"id", "name"},
            private_fields={"tenant_id", "description"},
            anonymized_fields=set()
        ),
        description="Industry sector classification"
    ),
}

# ─── Pattern & Analysis Entities ──────────────────────────────────────────────

PATTERN_VERTICES = {
    "ProjectPattern": SchemaEntity(
        name="ProjectPattern",
        attributes=[
            "id", "tenant_id", "scope", "category", "name", "description", "explanation",
            "confidence_score", "support_score", "created_at", "summary_period",
            "avg_project_duration", "avg_milestone_velocity", "budget_band",
            "key_technologies", "team_composition", "dev_methodology_dist",
            "work_type_distribution", "milestone_adherence_score", "delivery_success_score",
            "key_risk_mitigations", "key_milestones", "key_kpis", "project_ids", "constraints",
            "delivery_themes", "delivery_approaches", "delivery_success_criteria", "delivery_narrative",
            "strategic_focus", "maturity_level", "implementation_complexity", "governance_model",
            # Scoring analytics fields
            "avg_score", "score_variance", "min_score", "max_score", "score_sample_size",
            "score_strengths", "score_weaknesses"
        ],
        privacy_config=PrivacyConfig(
            public_fields={"id", "scope", "category", "name", "confidence_score", "support_score", "created_at", "summary_period", "avg_score", "score_variance"},
            private_fields={
                "tenant_id", "description", "explanation", "avg_project_duration", "avg_milestone_velocity", "budget_band",
                "key_technologies", "team_composition", "dev_methodology_dist", "work_type_distribution",
                "milestone_adherence_score", "delivery_success_score", "key_risk_mitigations", "key_milestones", "key_kpis", "project_ids", "constraints",
                "delivery_themes", "delivery_approaches", "delivery_success_criteria", "delivery_narrative",
                "strategic_focus", "maturity_level", "implementation_complexity", "governance_model",
                "min_score", "max_score", "score_sample_size", "score_strengths", "score_weaknesses"
            },
            anonymized_fields={"name", "description", "explanation", "delivery_narrative", "score_strengths", "score_weaknesses"}
        ),
        description="Pattern derived from Project entities"
    ),
    "ProjectScore": SchemaEntity(
        name="ProjectScore",
        attributes=[
            # Identifiers
            "id", "project_id", "roadmap_id", "tenant_id", "project_title", "project_status",
            # Scope (workflow-level vs portfolio-level)
            "scope",
            # Core scores (0-100)
            "core_score", "on_time_score", "on_scope_score", "on_budget_score",
            "risk_management_score", "team_health_score",
            # Dimension explanations
            "on_time_explanation", "on_scope_explanation", "on_budget_explanation",
            "risk_management_explanation", "team_health_explanation",
            # LLM explanation (flattened as string)
            "llm_explanation",
            # Confidence (flattened)
            "confidence_overall", "confidence_interpretation",
            "confidence_status_fields", "confidence_milestones", "confidence_comments",
            "confidence_risks", "confidence_team_data", "data_completeness_pct",
            # Signals (flattened)
            "milestone_pattern", "milestone_on_time_ratio", "milestone_avg_delay_days",
            "milestone_completed_count", "complication_pattern", "complication_blocker_count",
            "complication_resolution_rate",
            # Maturity (nullable for active projects)
            "maturity_score", "maturity_label", "retrospective_score", "value_realization_score",
            # Metadata
            "created_at", "scoring_version",
            # Cross-score alignment (populated during Roadmap pipeline run)
            "roadmap_plan_score", "execution_plan_delta", "execution_plan_alignment"
        ],
        privacy_config=PrivacyConfig(
            public_fields={"id", "project_status", "core_score", "scope", "confidence_overall", "confidence_interpretation", "scoring_version", "created_at"},
            private_fields={
                "project_id", "roadmap_id", "tenant_id", "project_title",
                "on_time_score", "on_scope_score", "on_budget_score", "risk_management_score", "team_health_score",
                "on_time_explanation", "on_scope_explanation", "on_budget_explanation",
                "risk_management_explanation", "team_health_explanation", "llm_explanation",
                "confidence_status_fields", "confidence_milestones", "confidence_comments",
                "confidence_risks", "confidence_team_data", "data_completeness_pct",
                "milestone_pattern", "milestone_on_time_ratio", "milestone_avg_delay_days",
                "milestone_completed_count", "complication_pattern", "complication_blocker_count",
                "complication_resolution_rate",
                "maturity_score", "maturity_label", "retrospective_score", "value_realization_score",
                "roadmap_plan_score", "execution_plan_delta", "execution_plan_alignment"
            },
            anonymized_fields={"project_title", "on_time_explanation", "on_scope_explanation", "on_budget_explanation",
                              "risk_management_explanation", "team_health_explanation", "llm_explanation"}
        ),
        description="Project scoring snapshot with dimension scores, confidence, signals, and LLM explanations"
    ),
    "RoadmapScore": SchemaEntity(
        name="RoadmapScore",
        attributes=[
            # Identifiers
            "id", "roadmap_id", "tenant_id", "roadmap_title", "roadmap_state",
            # Scope (workflow-level vs portfolio-level)
            "scope",
            # Core score (0-100, weighted blend of 5 dimensions)
            "core_score",
            # Dimension blended scores (0-100)
            "strategic_clarity_score", "okr_quality_score", "scope_and_constraints_score",
            "resource_financial_score", "solution_readiness_score",
            # Dimension explanations
            "strategic_clarity_explanation", "okr_quality_explanation",
            "scope_and_constraints_explanation", "resource_financial_explanation",
            "solution_readiness_explanation",
            # LLM explanation (flattened as string)
            "llm_explanation",
            # Confidence (flattened)
            "confidence_overall", "confidence_interpretation",
            "confidence_core_fields", "confidence_okr_completeness",
            "confidence_scope_coverage", "confidence_financial_data",
            "confidence_alignment_signal", "data_completeness_pct",
            # Signals (flattened)
            "planning_depth_pattern", "planning_depth_description",
            "financial_rationale_pattern", "financial_rationale_description",
            # Metadata
            "created_at", "scoring_version", "roadmap_type",
            # Cross-score aggregates (populated during Roadmap pipeline run)
            "linked_project_count", "avg_linked_project_score"
        ],
        privacy_config=PrivacyConfig(
            public_fields={"id", "roadmap_state", "core_score", "scope", "confidence_overall", "confidence_interpretation", "scoring_version", "created_at"},
            private_fields={
                "roadmap_id", "tenant_id", "roadmap_title", "roadmap_type",
                "strategic_clarity_score", "okr_quality_score", "scope_and_constraints_score",
                "resource_financial_score", "solution_readiness_score",
                "strategic_clarity_explanation", "okr_quality_explanation",
                "scope_and_constraints_explanation", "resource_financial_explanation",
                "solution_readiness_explanation", "llm_explanation",
                "confidence_core_fields", "confidence_okr_completeness",
                "confidence_scope_coverage", "confidence_financial_data",
                "confidence_alignment_signal", "data_completeness_pct",
                "planning_depth_pattern", "planning_depth_description",
                "financial_rationale_pattern", "financial_rationale_description",
                "linked_project_count", "avg_linked_project_score"
            },
            anonymized_fields={"roadmap_title", "strategic_clarity_explanation", "okr_quality_explanation",
                              "scope_and_constraints_explanation", "resource_financial_explanation",
                              "solution_readiness_explanation", "llm_explanation"}
        ),
        description="Roadmap data quality scoring snapshot with dimension scores, confidence, signals, and LLM explanations"
    ),
    "RoadmapPattern": SchemaEntity(
        name="RoadmapPattern",
        attributes=[
            "id", "tenant_id", "scope", "category", "name", "description", "explanation",
            "confidence_score", "support_score", "created_at", "summary_period",
            "avg_milestone_velocity", "budget_band",
            "key_milestones", "key_kpis", "constraints", "roadmap_ids",
            "key_technologies", "key_risk_mitigations",
            # Roadmap specific fields for comprehensive pattern knowledge
            "common_scopes", "common_priorities", "common_statuses",
            "solution_themes", "solution_approaches", "solution_success_criteria", "solution_narrative",
            "team_allocations", "resource_distribution", "expected_outcomes_summary",
            # Strategic and Governance fields
            "strategic_focus", "maturity_level", "implementation_complexity", "governance_model",
            # Timeline/state transition insights (from authorization_approval_request)
            "state_transition_history", "typical_state_flow", "stage_duration_insights", "avg_days_per_stage",
            # Scoring analytics fields (same as ProjectPattern)
            "avg_score", "score_variance", "min_score", "max_score", "score_sample_size",
            "score_strengths", "score_weaknesses"
        ],
        privacy_config=PrivacyConfig(
            public_fields={"id", "scope", "category", "name", "confidence_score", "support_score", "created_at", "summary_period", "strategic_focus", "maturity_level", "implementation_complexity", "governance_model", "typical_state_flow", "avg_days_per_stage", "avg_score", "score_variance"},
            private_fields={"tenant_id", "description", "explanation", "avg_milestone_velocity", "budget_band", "key_milestones", "key_kpis", "constraints", "roadmap_ids", "common_scopes", "common_priorities", "common_statuses", "solution_themes", "solution_approaches", "solution_success_criteria", "solution_narrative", "team_allocations", "resource_distribution", "expected_outcomes_summary", "state_transition_history", "stage_duration_insights", "min_score", "max_score", "score_sample_size", "score_strengths", "score_weaknesses"},
            anonymized_fields={"name", "description", "explanation", "solution_themes", "solution_approaches", "solution_narrative", "score_strengths", "score_weaknesses"}
        ),
        description="Pattern derived from Roadmap entities"
    ),
    "PortfolioPattern": SchemaEntity(
        name="PortfolioPattern",
        attributes=[
            # Core identity
            "id", "tenant_id", "portfolio_id", "portfolio_name", "created_at", "updated_at",
            # Aggregation metadata
            "workflow_pattern_count", "roadmap_pattern_count", "project_pattern_count",
            "aggregation_method",
            # LLM-generated core fields
            "name", "category", "description", "explanation",
            "strategic_focus", "maturity_level", "implementation_complexity", "governance_model",
            # Categorical aggregations (LIST<STRING>)
            "key_technologies", "team_composition", "dev_methodology_dist", "work_type_distribution",
            "key_risk_mitigations", "key_milestones", "key_kpis", "constraints",
            "solution_themes", "solution_approaches", "delivery_themes", "delivery_approaches",
            # Execution score aggregations
            "total_execution_count", "execution_coverage_pct",
            "avg_core_score", "score_variance_across_patterns",
            "min_score", "max_score", "median_score",
            "avg_on_time_score", "avg_on_scope_score", "avg_on_budget_score",
            "avg_risk_management_score", "avg_team_health_score",
            "top_performing_pattern_ids", "dimension_strength_ranking",
            # Data quality indicators
            "overall_confidence_level", "avg_quality_score",
            "dimensions_with_sufficient_data", "missing_dimensions",
            # LLM insight fields
            "portfolio_summary", "execution_insights",
            "strength_narrative", "weakness_narrative",
            "recommended_actions", "cross_pattern_insights",
            "solution_delivery_narrative"
        ],
        privacy_config=PrivacyConfig(
            public_fields={
                "id", "portfolio_id", "category", "created_at", "updated_at",
                "workflow_pattern_count", "roadmap_pattern_count", "project_pattern_count",
                "aggregation_method", "strategic_focus", "maturity_level",
                "implementation_complexity", "governance_model", "execution_coverage_pct",
                "avg_core_score", "overall_confidence_level"
            },
            private_fields={
                "tenant_id", "portfolio_name", "name", "description", "explanation",
                "key_technologies", "team_composition", "dev_methodology_dist", "work_type_distribution",
                "key_risk_mitigations", "key_milestones", "key_kpis", "constraints",
                "solution_themes", "solution_approaches", "delivery_themes", "delivery_approaches",
                "total_execution_count", "score_variance_across_patterns",
                "min_score", "max_score", "median_score",
                "avg_on_time_score", "avg_on_scope_score", "avg_on_budget_score",
                "avg_risk_management_score", "avg_team_health_score",
                "top_performing_pattern_ids", "dimension_strength_ranking",
                "avg_quality_score", "dimensions_with_sufficient_data", "missing_dimensions",
                "portfolio_summary", "execution_insights", "strength_narrative", "weakness_narrative",
                "recommended_actions", "cross_pattern_insights", "solution_delivery_narrative"
            },
            anonymized_fields={
                "portfolio_name", "name", "description", "explanation", "portfolio_summary",
                "execution_insights", "strength_narrative", "weakness_narrative",
                "recommended_actions", "cross_pattern_insights", "solution_delivery_narrative"
            }
        ),
        description="Portfolio-level aggregation pattern with LLM-generated insights and execution score analysis"
    ),
    "CustomerPattern": SchemaEntity(
        name="CustomerPattern",
        attributes=[
            # Core identity
            "id", "tenant_id", "customer_id", "customer_name",
            "industry", "industry_sector",
            "created_at", "updated_at",
            # Aggregation metadata
            "portfolio_count", "total_roadmap_patterns", "total_project_patterns",
            "portfolios_with_execution",
            # LLM-generated strategic content
            "name", "executive_summary", "strategic_direction",
            "organizational_maturity", "capability_landscape",
            "innovation_profile", "risk_landscape",
            "investment_thesis", "competitive_positioning",
            # SWOT narratives
            "strength_narrative", "weakness_narrative",
            "opportunity_narrative", "threat_narrative",
            # Cross-portfolio intelligence
            "cross_portfolio_synergies", "portfolio_health_summary",
            # LLM-generated lists
            "key_capabilities", "capability_gaps", "strategic_recommendations",
            "top_technologies", "emerging_risks", "investment_priorities",
            # Aggregated execution metrics
            "org_avg_execution_score", "org_avg_on_time_score",
            "org_avg_on_scope_score", "org_avg_on_budget_score",
            "org_avg_risk_score",
            "execution_maturity",
        ],
        privacy_config=PrivacyConfig(
            public_fields={
                "id", "customer_id", "created_at", "updated_at",
                "portfolio_count", "organizational_maturity",
                "org_avg_execution_score", "execution_maturity"
            },
            private_fields={
                "tenant_id", "customer_name", "industry", "industry_sector",
                "total_roadmap_patterns", "total_project_patterns", "portfolios_with_execution",
                "name", "executive_summary", "strategic_direction",
                "capability_landscape", "innovation_profile", "risk_landscape",
                "investment_thesis", "competitive_positioning",
                "strength_narrative", "weakness_narrative",
                "opportunity_narrative", "threat_narrative",
                "cross_portfolio_synergies", "portfolio_health_summary",
                "key_capabilities", "capability_gaps", "strategic_recommendations",
                "top_technologies", "emerging_risks", "investment_priorities",
                "org_avg_on_time_score", "org_avg_on_scope_score",
                "org_avg_on_budget_score", "org_avg_risk_score"
            },
            anonymized_fields={
                "customer_name", "name", "executive_summary", "strategic_direction",
                "capability_landscape", "innovation_profile", "risk_landscape",
                "investment_thesis", "competitive_positioning",
                "strength_narrative", "weakness_narrative",
                "opportunity_narrative", "threat_narrative",
                "cross_portfolio_synergies", "portfolio_health_summary"
            }
        ),
        description="Organization-level strategic pattern synthesized from all portfolio patterns via LLM analysis"
    ),
}

# ─── GSQL Edge Definitions ────────────────────────────────────────────────────

EDGE_DEFINITIONS = {
    # Cross-cutting foundation
    "belongsToSector": "CREATE DIRECTED EDGE belongsToSector (FROM Industry, TO IndustrySector)",
    "belongsToIndustry": "CREATE DIRECTED EDGE belongsToIndustry (FROM Customer, TO Industry)",
    "ownsPortfolio": "CREATE DIRECTED EDGE ownsPortfolio (FROM Customer, TO TemplatePortfolio)",
    
    # Project Score edges (ProjectScore belongs to patterns and portfolios)
    "scoreBelongsToPattern": "CREATE DIRECTED EDGE scoreBelongsToPattern (FROM ProjectScore, TO ProjectPattern)",
    "scoreBelongsToPortfolio": "CREATE DIRECTED EDGE scoreBelongsToPortfolio (FROM ProjectScore, TO TemplatePortfolio)",
    
    # Roadmap Score edges (RoadmapScore belongs to patterns and portfolios)
    "roadmapScoreBelongsToPattern": "CREATE DIRECTED EDGE roadmapScoreBelongsToPattern (FROM RoadmapScore, TO RoadmapPattern)",
    "roadmapScoreBelongsToPortfolio": "CREATE DIRECTED EDGE roadmapScoreBelongsToPortfolio (FROM RoadmapScore, TO TemplatePortfolio)",

    # Cross-score edges (RoadmapScore <-> ProjectScore — plan quality vs execution quality)
    "roadmapScoreHasProjectExecution": "CREATE DIRECTED EDGE roadmapScoreHasProjectExecution (FROM RoadmapScore, TO ProjectScore)",
    "projectScoreFromRoadmapPlan": "CREATE DIRECTED EDGE projectScoreFromRoadmapPlan (FROM ProjectScore, TO RoadmapScore)",
    "roadmapScoreInProjectCluster": "CREATE DIRECTED EDGE roadmapScoreInProjectCluster (FROM RoadmapScore, TO ProjectPattern)",
    
    # Project Template sub-entity edges
    "hasTemplatePortfolio": "CREATE DIRECTED EDGE hasTemplatePortfolio (FROM ProjectTemplate, TO TemplatePortfolio)",
    "hasTemplateMilestone": "CREATE DIRECTED EDGE hasTemplateMilestone (FROM ProjectTemplate, TO TemplateMilestone | FROM RoadmapTemplate, TO TemplateMilestone)",
    "hasTemplateStatus": "CREATE DIRECTED EDGE hasTemplateStatus (FROM ProjectTemplate, TO TemplateStatus)",
    "hasTemplateTechnology": "CREATE DIRECTED EDGE hasTemplateTechnology (FROM ProjectTemplate, TO TemplateTechnology)",
    "hasTemplateKeyResult": "CREATE DIRECTED EDGE hasTemplateKeyResult (FROM ProjectTemplate, TO TemplateKeyResult)",
    "hasTemplateProjectType": "CREATE DIRECTED EDGE hasTemplateProjectType (FROM ProjectTemplate, TO TemplateProjectType)",
    "hasTemplateSdlcMethod": "CREATE DIRECTED EDGE hasTemplateSdlcMethod (FROM ProjectTemplate, TO TemplateSdlcMethod)",
    "hasTemplateProjectCategory": "CREATE DIRECTED EDGE hasTemplateProjectCategory (FROM ProjectTemplate, TO TemplateProjectCategory)",
    "hasTemplateProjectLocation": "CREATE DIRECTED EDGE hasTemplateProjectLocation (FROM ProjectTemplate, TO TemplateProjectLocation)",
    
    # Roadmap Template sub-entity edges
    "hasRoadmapTemplatePortfolio": "CREATE DIRECTED EDGE hasRoadmapTemplatePortfolio (FROM RoadmapTemplate, TO TemplatePortfolio)",
    "hasTemplateConstraint": "CREATE DIRECTED EDGE hasTemplateConstraint (FROM RoadmapTemplate, TO TemplateConstraint)",
    "hasTemplateRoadmapKeyResult": "CREATE DIRECTED EDGE hasTemplateRoadmapKeyResult (FROM RoadmapTemplate, TO TemplateRoadmapKeyResult)",
    "hasTemplateTeam": "CREATE DIRECTED EDGE hasTemplateTeam (FROM RoadmapTemplate, TO TemplateTeam)",
    "hasTemplateScope": "CREATE DIRECTED EDGE hasTemplateScope (FROM RoadmapTemplate, TO TemplateScope)",
    "hasTemplatePriority": "CREATE DIRECTED EDGE hasTemplatePriority (FROM RoadmapTemplate, TO TemplatePriority)",
    "hasTemplateRoadmapStatus": "CREATE DIRECTED EDGE hasTemplateRoadmapStatus (FROM RoadmapTemplate, TO TemplateRoadmapStatus)",
    "hasTemplateSolution": "CREATE DIRECTED EDGE hasTemplateSolution (FROM RoadmapTemplate, TO TemplateSolution)",
    
    # Customer uses Templates
    "usesProjectTemplate": "CREATE DIRECTED EDGE usesProjectTemplate (FROM Customer, TO ProjectTemplate)",
    "usesRoadmapTemplate": "CREATE DIRECTED EDGE usesRoadmapTemplate (FROM Customer, TO RoadmapTemplate)",
    
    # Pattern <-> Template bidirectional edges
    "supportedByProjectTemplate": "CREATE DIRECTED EDGE supportedByProjectTemplate (FROM ProjectPattern, TO ProjectTemplate)",
    "supportedByRoadmapTemplate": "CREATE DIRECTED EDGE supportedByRoadmapTemplate (FROM RoadmapPattern, TO RoadmapTemplate)",
    "supportsProjectTemplatePattern": "CREATE DIRECTED EDGE supportsProjectTemplatePattern (FROM ProjectTemplate, TO ProjectPattern)",
    "supportsRoadmapTemplatePattern": "CREATE DIRECTED EDGE supportsRoadmapTemplatePattern (FROM RoadmapTemplate, TO RoadmapPattern)",
    
    # Entity-specific Pattern edges (used by pattern generators and pipeline)
    "relevantToProjectIndustry": "CREATE DIRECTED EDGE relevantToProjectIndustry (FROM ProjectPattern, TO Industry)",
    "relevantToRoadmapIndustry": "CREATE DIRECTED EDGE relevantToRoadmapIndustry (FROM RoadmapPattern, TO Industry)",
    "composedOfProjectPattern": "CREATE DIRECTED EDGE composedOfProjectPattern (FROM ProjectPattern, TO ProjectPattern)",
    "derivedFromProjectPortfolio": "CREATE DIRECTED EDGE derivedFromProjectPortfolio (FROM ProjectPattern, TO TemplatePortfolio)",
    "derivedFromRoadmapPortfolio": "CREATE DIRECTED EDGE derivedFromRoadmapPortfolio (FROM RoadmapPattern, TO TemplatePortfolio)",
    "aggregatesRoadmapPattern": "CREATE DIRECTED EDGE aggregatesRoadmapPattern (FROM RoadmapPattern, TO RoadmapPattern)",
    
    # RoadmapPattern <-> ProjectScore bidirectional edges (for roadmap-to-project execution tracking)
    "hasProjectExecution": "CREATE DIRECTED EDGE hasProjectExecution (FROM RoadmapPattern, TO ProjectScore)",
    "executedByRoadmap": "CREATE DIRECTED EDGE executedByRoadmap (FROM ProjectScore, TO RoadmapPattern)",

    # RoadmapPattern <-> ProjectPattern bidirectional edges (for roadmap-to-project cluster connections)
    "hasExecutionInCluster": "CREATE DIRECTED EDGE hasExecutionInCluster (FROM RoadmapPattern, TO ProjectPattern)",
    "roadmapExecutedInCluster": "CREATE DIRECTED EDGE roadmapExecutedInCluster (FROM ProjectPattern, TO RoadmapPattern)",
    
    # PortfolioPattern aggregation edges (connects to workflow-level patterns)
    "aggregatesRoadmapWorkflow": "CREATE DIRECTED EDGE aggregatesRoadmapWorkflow (FROM PortfolioPattern, TO RoadmapPattern)",
    "aggregatesProjectWorkflow": "CREATE DIRECTED EDGE aggregatesProjectWorkflow (FROM PortfolioPattern, TO ProjectPattern)",
    "summarizesPortfolio": "CREATE DIRECTED EDGE summarizesPortfolio (FROM PortfolioPattern, TO TemplatePortfolio)",
    "belongsToCustomer": "CREATE DIRECTED EDGE belongsToCustomer (FROM PortfolioPattern, TO Customer)",
    "relevantToIndustry": "CREATE DIRECTED EDGE relevantToIndustry (FROM PortfolioPattern, TO Industry)",
    "hasPortfolioSummary": "CREATE DIRECTED EDGE hasPortfolioSummary (FROM TemplatePortfolio, TO PortfolioPattern)",
    
    # CustomerPattern aggregation edges
    "customerPatternAggregatesPortfolio": "CREATE DIRECTED EDGE customerPatternAggregatesPortfolio (FROM CustomerPattern, TO PortfolioPattern)",
    "customerPatternForCustomer": "CREATE DIRECTED EDGE customerPatternForCustomer (FROM CustomerPattern, TO Customer)",
    "hasCustomerPattern": "CREATE DIRECTED EDGE hasCustomerPattern (FROM Customer, TO CustomerPattern)",
}


# ─── GSQL Schema Creation ────────────────────────────────────────────────────

def get_schema_creation_script() -> str:
    """Get complete GSQL schema creation script"""
    vertex_defs_dict = {}  # Use dict to avoid duplicates
    
    # Project Template vertices
    for vertex in PROJECT_TEMPLATE_SCHEMA.vertices.values():
        vertex_def = _get_gsql_vertex_definition(vertex.name, vertex)
        vertex_defs_dict[vertex.name] = vertex_def
    
    # Roadmap Template vertices
    for vertex in ROADMAP_TEMPLATE_SCHEMA.vertices.values():
        vertex_def = _get_gsql_vertex_definition(vertex.name, vertex)
        vertex_defs_dict[vertex.name] = vertex_def  # Overwrites duplicate if exists
    
    # Pattern vertices
    for name, vertex in PATTERN_VERTICES.items():
        vertex_def = _get_gsql_vertex_definition(name, vertex)
        vertex_defs_dict[name] = vertex_def
    
    # Cross-cutting vertices
    for name, vertex in CROSS_CUTTING_VERTICES.items():
        vertex_def = _get_gsql_vertex_definition(name, vertex)
        vertex_defs_dict[name] = vertex_def
    
    # Edge definitions
    edge_defs = "\n".join(EDGE_DEFINITIONS.values())
    
    return "\n".join(vertex_defs_dict.values()) + "\n" + edge_defs


def _get_gsql_vertex_definition(vertex_name: str, schema_entity: SchemaEntity) -> str:
    """Generate GSQL vertex definition from SchemaEntity"""
    def fmt_attr(a: str) -> str:
        if a in INT_FIELDS:
            return f"{a} INT"
        if a in DOUBLE_FIELDS:
            return f"{a} DOUBLE"
        if a in BOOL_FIELDS:
            return f"{a} BOOL"
        if a in LIST_DOUBLE_FIELDS:
            return f"{a} LIST<DOUBLE>"
        if a in LIST_STRING_FIELDS:
            return f"{a} LIST<STRING>"
        # Default to STRING for any unrecognized attribute
        return f"{a} STRING"

    attrs_def = ",\n    ".join([fmt_attr(attr) for attr in schema_entity.attributes])

    return f"""CREATE VERTEX {vertex_name} (
    PRIMARY_ID id STRING,
    {attrs_def}
)"""


def get_graph_creation_script(graph_name: str = "TrmericGraph") -> str:
    """Get GSQL graph creation script"""
    all_vertices = []
    
    # Add all vertices
    all_vertices.extend(PROJECT_TEMPLATE_SCHEMA.vertices.keys())
    all_vertices.extend(ROADMAP_TEMPLATE_SCHEMA.vertices.keys())
    all_vertices.extend(PATTERN_VERTICES.keys())
    all_vertices.extend(CROSS_CUTTING_VERTICES.keys())
    
    # Remove duplicates (Portfolio appears in both Project and Roadmap)
    all_vertices = list(set(all_vertices))
    
    vertex_types = ", ".join(sorted(all_vertices))
    edge_types = ", ".join(sorted(EDGE_DEFINITIONS.keys()))
    
    return f"""CREATE GRAPH {graph_name} (
    {vertex_types},
    {edge_types}
)"""


# ─── Edge Type Mapping ────────────────────────────────────────────────────────

def get_edge_type_mapping() -> Dict[str, List[Dict[str, str]]]:
    """
    Get edge type mapping (from -> to vertex types).
    
    Parses edge definitions to extract source and target vertex types.
    Used by batch loaders to validate and map edge relationships.
    
    Returns:
        Dictionary mapping edge_type -> List of {from: vertex_type, to: vertex_type}
    """
    mapping = {}
    for edge_name, edge_def in EDGE_DEFINITIONS.items():
        # Parse "CREATE DIRECTED EDGE edge_name (FROM SourceType, TO TargetType | FROM Source2, TO Target2)"
        try:
            # Extract content inside parentheses
            start_idx = edge_def.find("(") + 1
            end_idx = edge_def.rfind(")")
            content = edge_def[start_idx:end_idx]
            
            mapping[edge_name] = []
            
            # Split by pipe for multiple definitions
            pairs = content.split("|")
            
            for pair in pairs:
                # pair is like "FROM Source, TO Target"
                parts = pair.split(",")
                if len(parts) >= 2:
                    from_part = parts[0].strip() # "FROM Source"
                    to_part = parts[1].strip()   # "TO Target"
                    
                    from_type = from_part.replace("FROM ", "").strip()
                    to_type = to_part.replace("TO ", "").strip()
                    
                    mapping[edge_name].append({"from": from_type, "to": to_type})
        except Exception as e:
            print(f"Warning: Could not parse edge definition for {edge_name}: {e}")
            continue
    
    return mapping


# ─── Schema Introspection ────────────────────────────────────────────────────

def get_vertex_types() -> List[str]:
    """Get all vertex type names"""
    types = []
    types.extend(PROJECT_TEMPLATE_SCHEMA.vertices.keys())
    types.extend(ROADMAP_TEMPLATE_SCHEMA.vertices.keys())
    types.extend(PATTERN_VERTICES.keys())
    types.extend(CROSS_CUTTING_VERTICES.keys())
    return sorted(list(set(types)))  # Remove duplicates


def get_edge_types() -> List[str]:
    """Get all edge type names"""
    return sorted(list(EDGE_DEFINITIONS.keys()))


def get_vertex_privacy_config(vertex_type: str) -> PrivacyConfig:
    """Get privacy config for a vertex type"""
    # Check in all schemas
    if vertex_type in PROJECT_TEMPLATE_SCHEMA.vertices:
        return PROJECT_TEMPLATE_SCHEMA.vertices[vertex_type].privacy_config
    elif vertex_type in ROADMAP_TEMPLATE_SCHEMA.vertices:
        return ROADMAP_TEMPLATE_SCHEMA.vertices[vertex_type].privacy_config
    elif vertex_type in PATTERN_VERTICES:
        return PATTERN_VERTICES[vertex_type].privacy_config
    elif vertex_type in CROSS_CUTTING_VERTICES:
        return CROSS_CUTTING_VERTICES[vertex_type].privacy_config
    else:
        raise ValueError(f"Unknown vertex type: {vertex_type}")


def get_schema_summary() -> Dict[str, Any]:
    """Get schema summary with counts and breakdown"""
    return {
        "total_vertices": len(get_vertex_types()),
        "total_edges": len(EDGE_DEFINITIONS),
        "vertex_types": sorted(get_vertex_types()),
        "edge_types": sorted(get_edge_types()),
        "project_vertices": sorted(PROJECT_TEMPLATE_SCHEMA.vertices.keys()),
        "roadmap_vertices": sorted(ROADMAP_TEMPLATE_SCHEMA.vertices.keys()),
        "pattern_vertices": sorted(PATTERN_VERTICES.keys()),
        "cross_cutting_vertices": sorted(CROSS_CUTTING_VERTICES.keys()),
    }


