"""
Pattern Generator

LLM-based pattern and template generation ported from analysis.py.
Generates workflow patterns, portfolio patterns, and customer patterns using LLM.
Refactored to support multiple entity types (projects, roadmaps, etc.) with entity-specific extractors.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple

# Fixed category taxonomy — LLM must pick from these, not invent new ones.
# This ensures patterns across tenants use a consistent, searchable vocabulary.
PATTERN_CATEGORY_TAXONOMY = [
    "digital_transformation",
    "cloud_infrastructure",
    "data_analytics",
    "security_compliance",
    "customer_experience",
    "operational_efficiency",
    "product_development",
    "enterprise_integration",
    "ai_ml_automation",
    "workforce_modernization",
    "supply_chain_logistics",
    "financial_management",
    "risk_governance",
    "sustainability_esg",
    "platform_engineering",
]

class BasePatternGenerator(ABC):
    """Base class for pattern generation with entity-agnostic LLM logic."""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.entities = []  # Cache for generalize_cluster
    
    @staticmethod
    def compute_confidence_score(
        cluster_size: int,
        silhouette_score: float,
        total_entities_in_portfolio: int = 0,
        data_completeness: float = 1.0,
    ) -> float:
        """Compute a compositional confidence score from real signals instead of LLM self-assessment.
        
        Components (weights sum to 1.0):
          - cluster_size_signal (0.30): Penalise singletons, reward 3-5 entity clusters
          - silhouette_signal   (0.30): ML cluster cohesion (-1..1 mapped to 0..1)
          - representativeness   (0.20): Fraction of portfolio entities covered
          - data_completeness    (0.20): Fraction of fields that were non-empty
        
        Returns:
            float in [0.0, 1.0]
        """
        # Cluster size signal: 1 entity -> 0.1, 2 -> 0.5, 3 -> 0.8, 4-5 -> 1.0, 6+ taper
        size_map = {1: 0.1, 2: 0.5, 3: 0.8, 4: 1.0, 5: 1.0}
        if cluster_size <= 5:
            size_signal = size_map.get(cluster_size, 0.1)
        else:
            size_signal = max(0.5, 1.0 - (cluster_size - 5) * 0.1)  # taper for mega-clusters
        
        # Silhouette signal: map from [-1, 1] to [0, 1]
        sil = max(-1.0, min(1.0, silhouette_score))
        sil_signal = (sil + 1.0) / 2.0
        
        # Representativeness: what fraction of the portfolio does this cluster cover
        if total_entities_in_portfolio > 0:
            coverage = cluster_size / total_entities_in_portfolio
            # Sweet spot is 20-40% of portfolio; penalise both <10% and >60%
            if coverage <= 0.4:
                repr_signal = min(1.0, coverage / 0.3)
            else:
                repr_signal = max(0.3, 1.0 - (coverage - 0.4) * 1.5)
        else:
            repr_signal = 0.5  # unknown
        
        confidence = (
            0.30 * size_signal +
            0.30 * sil_signal +
            0.20 * repr_signal +
            0.20 * data_completeness
        )
        return round(min(1.0, max(0.0, confidence)), 3)

    @abstractmethod
    def _extract_cluster_features(self, cluster: List[Dict]) -> Dict[str, Any]:
        """Extract entity-specific features from cluster for LLM prompts."""
        pass
    
    @abstractmethod
    def _get_entity_type_label(self) -> str:
        """Return the entity type label (e.g., 'project', 'roadmap')."""
        pass
    
    @abstractmethod
    def _get_entity_id_key(self) -> str:
        """Return the ID key for this entity type (e.g., 'project_id', 'roadmap_id')."""
        pass
    
    @abstractmethod
    def _get_entity_count_key(self) -> str:
        """Return the count key for this entity type (e.g., 'project_count', 'roadmap_count')."""
        pass
    @abstractmethod
    def _get_pattern_vertex_type(self) -> str:
        """Return the vertex type for patterns (e.g., 'ProjectPattern', 'RoadmapPattern')."""
        pass
    
    @abstractmethod
    def _get_composed_of_pattern_edge(self) -> str:
        """Return the edge type for pattern composition (e.g., 'composedOfProjectPattern', 'aggregatesRoadmapPattern')."""
        pass
    
    @abstractmethod
    def _get_derived_from_portfolio_edge(self) -> str:
        """Return the edge type for pattern -> portfolio derivation (e.g., 'derivedFromProjectPortfolio', 'derivedFromRoadmapPortfolio')."""
        pass
    
    @abstractmethod
    def _get_relevant_to_industry_edge(self) -> str:
        """Return the edge type for pattern -> industry relevance (e.g., 'relevantToProjectIndustry', 'relevantToRoadmapIndustry')."""
        pass




    @staticmethod
    def format_project_pattern_vertex(pattern_data: Dict) -> Dict[str, Any]:
        """
        Format pattern data for ProjectPattern vertex.
        Maps pattern attributes to ProjectPattern schema fields.
        """
        pid = pattern_data.get("id") or f"pattern_{hash(str(pattern_data))}"
        return {
            "id": pid,
            "tenant_id": pattern_data.get("tenant_id", pattern_data.get("customer_id", "")),
            "scope": pattern_data.get("scope", "workflow"),
            "category": pattern_data.get("category", ""),
            "name": pattern_data.get("name", ""),
            "description": pattern_data.get("description", ""),
            "explanation": pattern_data.get("explanation", ""),
            "confidence_score": pattern_data.get("confidence_score", 0.0),
            "support_score": pattern_data.get("support_score", 0.0),
            "created_at": pattern_data.get("created_at", ""),
            "summary_period": pattern_data.get("summary_period", ""),
            "avg_project_duration": pattern_data.get("avg_project_duration", 0.0),
            "avg_milestone_velocity": pattern_data.get("avg_milestone_velocity", 0.0),
            "budget_band": pattern_data.get("budget_band", ""),
            "key_technologies": pattern_data.get("key_technologies", []),
            "team_composition": pattern_data.get("team_composition", []),
            "dev_methodology_dist": pattern_data.get("dev_methodology_dist", []),
            "work_type_distribution": pattern_data.get("work_type_distribution", []),
            "milestone_adherence_score": pattern_data.get("milestone_adherence_score", 0.0),
            "delivery_success_score": pattern_data.get("delivery_success_score", 0.0),
            "key_risk_mitigations": pattern_data.get("key_risk_mitigations", []),
            "key_milestones": pattern_data.get("key_milestones", []),
            "key_kpis": pattern_data.get("key_kpis", []),
            "project_ids": pattern_data.get("project_ids", []),
            "delivery_themes": pattern_data.get("delivery_themes", []),
            "delivery_approaches": pattern_data.get("delivery_approaches", []),
            "delivery_success_criteria": pattern_data.get("delivery_success_criteria", []),
            "delivery_narrative": pattern_data.get("delivery_narrative", ""),
            "strategic_focus": pattern_data.get("strategic_focus", ""),
            "maturity_level": pattern_data.get("maturity_level", ""),
            "implementation_complexity": pattern_data.get("implementation_complexity", ""),
            "governance_model": pattern_data.get("governance_model", "")
        }

    @staticmethod
    def format_roadmap_pattern_vertex(pattern_data: Dict) -> Dict[str, Any]:
        """
        Format pattern data for RoadmapPattern vertex.
        Maps pattern attributes to RoadmapPattern schema fields.
        """
        pid = pattern_data.get("id") or f"pattern_{hash(str(pattern_data))}"
        return {
            "id": pid,
            "tenant_id": pattern_data.get("tenant_id", pattern_data.get("customer_id", "")),
            "scope": pattern_data.get("scope") or "workflow",  # Treat empty string as missing
            "category": pattern_data.get("category", ""),
            "name": pattern_data.get("name", ""),
            "description": pattern_data.get("description", ""),
            "explanation": pattern_data.get("explanation", ""),
            "confidence_score": pattern_data.get("confidence_score", 0.0),
            "support_score": pattern_data.get("support_score", 0.0),
            "created_at": pattern_data.get("created_at", ""),
            "summary_period": pattern_data.get("summary_period", ""),
            "avg_milestone_velocity": pattern_data.get("avg_milestone_velocity", 0.0),
            "budget_band": pattern_data.get("budget_band", ""),
            "key_milestones": pattern_data.get("key_milestones", []),
            "key_kpis": pattern_data.get("key_kpis", []),
            "constraints": pattern_data.get("constraints", []),
            "roadmap_ids": pattern_data.get("roadmap_ids", []),
            "key_technologies": pattern_data.get("key_technologies", []),
            "key_risk_mitigations": pattern_data.get("key_risk_mitigations", []),
            "common_scopes": pattern_data.get("common_scopes", []),
            "common_priorities": pattern_data.get("common_priorities", []),
            "common_statuses": pattern_data.get("common_statuses", []),
            "solution_themes": pattern_data.get("solution_themes", []),
            "solution_approaches": pattern_data.get("solution_approaches", []),
            "solution_success_criteria": pattern_data.get("solution_success_criteria", []),
            "solution_narrative": pattern_data.get("solution_narrative", ""),
            "team_allocations": pattern_data.get("team_allocations", []),
            "resource_distribution": pattern_data.get("resource_distribution", []),
            "expected_outcomes_summary": pattern_data.get("expected_outcomes_summary", []),
            "strategic_focus": pattern_data.get("strategic_focus", ""),
            "maturity_level": pattern_data.get("maturity_level", ""),
            "implementation_complexity": pattern_data.get("implementation_complexity", ""),
            "governance_model": pattern_data.get("governance_model", ""),
            "state_transition_history": pattern_data.get("state_transition_history", []),
            "typical_state_flow": pattern_data.get("typical_state_flow", []),
            "stage_duration_insights": pattern_data.get("stage_duration_insights", []),
            "avg_days_per_stage": pattern_data.get("avg_days_per_stage", "")
        }
