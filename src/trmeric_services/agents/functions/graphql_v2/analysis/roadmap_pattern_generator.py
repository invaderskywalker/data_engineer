from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from datetime import date, datetime
import time
from abc import ABC, abstractmethod
import numpy as np
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.graphql_v2.analysis.pattern_generator import BasePatternGenerator, PATTERN_CATEGORY_TAXONOMY

class RoadmapPatternGenerator(BasePatternGenerator):
    """Pattern generator for roadmap entities."""
    
    def _extract_cluster_features(self, cluster: List[Dict]) -> Dict[str, Any]:
        """Extract roadmap-specific features."""
        return {
            "portfolios": [str(p.get("name") or "Unknown") for r in cluster for p in r.get("portfolios", []) if p],
            "kpis": [str(k.get("kpi_name") or "Unknown") for r in cluster for k in r.get("key_results", []) if k],
            "scopes": [str(s.get("scope_name") or "Unknown") for r in cluster for s in r.get("scopes", []) if s],
            "entity_ids": [str(r.get("roadmap_id")) for r in cluster if r.get("roadmap_id")],
            "constraints": [str(c.get("constraint_name") or "Unknown") for r in cluster for c in r.get("constraints", []) if c],
            # Roadmaps use team_name and labour_type instead of role
            "team_names": [str(t.get("team_name") or "Unknown") for r in cluster for t in r.get("team", []) if t],
            "labour_types": [str(t.get("labour_type") or "Unknown") for r in cluster for t in r.get("team", []) if t],
        }
    
    def _get_entity_type_label(self) -> str:
        return "roadmaps"
    
    def _get_entity_id_key(self) -> str:
        return "roadmap_id"
    
    def _get_entity_count_key(self) -> str:
        return "roadmap_count"
    
    def _get_pattern_vertex_type(self) -> str:
        return "RoadmapPattern"
    
    def _get_composed_of_pattern_edge(self) -> str:
        return "aggregatesRoadmapPattern"
    
    def _get_derived_from_portfolio_edge(self) -> str:
        return "derivedFromRoadmapPortfolio"
    
    def _get_relevant_to_industry_edge(self) -> str:
        return "relevantToRoadmapIndustry"
    
    def explain_cluster(self, cluster: List[Dict], cluster_idx: int, portfolio_name: str) -> Dict[str, Any]:
        """Explain why roadmap entities were clustered together."""
        if not cluster:
            return {"explanation": "", "llm_confidence": 0.0}

        features = self._extract_cluster_features(cluster)
        entity_label = self._get_entity_type_label()
        
        # Pre-format the lists to avoid f-string issues and filter None values
        entity_ids_str = ', '.join(str(x) for x in features['entity_ids'] if x)
        portfolios_str = ', '.join(str(x) for x in set(features['portfolios']) if x)
        kpis_str = ', '.join(str(x) for x in set(features['kpis']) if x)
        scopes_str = ', '.join(str(x) for x in set(features['scopes']) if x)
        constraints_str = ', '.join(str(x) for x in set(features['constraints']) if x)
        team_names_str = ', '.join(str(x) for x in set(features['team_names']) if x)
        labour_types_str = ', '.join(str(x) for x in set(features['labour_types']) if x)

        system_prompt = f"""
            You are an AI that explains why a group of {entity_label} were clustered together in the {portfolio_name} portfolio.
            Given:
            - {entity_label.capitalize()} IDs: {entity_ids_str}
            - Portfolios: {portfolios_str}
            - KPIs: {kpis_str}
            - Scopes: {scopes_str}
            - Constraints: {constraints_str}
            - Team Names: {team_names_str}
            - Labour Types: {labour_types_str}

            Provide:
            1. A detailed explanation of shared characteristics (portfolios, KPIs, scopes, constraints, team composition).
            2. A brief summary (1-2 sentences) capturing the essence of this cluster.
            3. A confidence score (0.0-1.0) for your explanation.
            Return as JSON: 
            ```json
            {{"explanation": "<detailed text>", "summary": "<1-2 sentence summary>", "llm_confidence": <float> }}
            ```
        """

        try:
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user="Explain cluster.")
            response = self.llm.run(chat_completion, ModelOptions(model="gpt-4o", max_tokens=1500, temperature=0.1), 'analysis::explain_cluster')
            return extract_json_after_llm(response)
        except Exception as e:
            print(f"LLM error in explain_cluster: {e}")
            return {"explanation": "Failed to generate explanation.", "summary": "", "llm_confidence": 0.0}

    def generate_workflow_and_template_names(self, cluster_data: Dict, customer_id: str, cluster_idx: int, silhouette_score: float, explanation_data: Dict, portfolio_name: str, existing_pattern_names: list = None) -> Dict:
        """Generate template and pattern names for roadmap clusters."""
        print(f"DEBUG: generate_workflow_and_template_names called for cluster {cluster_idx}")
        try:
            entity_label = self._get_entity_type_label()
            entity_count_key = self._get_entity_count_key()
            
            velocity = cluster_data.get('velocity_score', 0)
            value_realization = cluster_data.get('value_realization_score', 0)
            print(f"DEBUG: velocity={velocity} ({type(velocity)}), value_realization={value_realization} ({type(value_realization)})")
            
            # Build detailed statistics for prompt
            roadmap_count = cluster_data.get(entity_count_key, 0)
            avg_duration = cluster_data.get('avg_roadmap_duration', 0)
            avg_kpi_count = cluster_data.get('avg_kpi_count', 0)
            avg_team_size = cluster_data.get('avg_team_size', 0)
            avg_constraint_count = cluster_data.get('avg_constraint_count', 0)
            
            # Extract portfolio details with percentages
            portfolio_details = []
            for p in cluster_data.get('key_portfolios', []):
                portfolio_details.append(f"{p.get('portfolio', 'Unknown')} ({p.get('count', 0)}/{roadmap_count} roadmaps = {p.get('percentage', 0)}%)")
            
            # Extract priority distribution
            priority_details = []
            for p in cluster_data.get('priority_distribution', []):
                priority_details.append(f"{p.get('priority', 'Unknown')}: {p.get('count', 0)}/{roadmap_count} roadmaps ({p.get('percentage', 0)}%)")
            
            # Extract status distribution
            status_details = []
            for s in cluster_data.get('status_distribution', []):
                status_details.append(f"{s.get('status', 'Unknown')}: {s.get('count', 0)}/{roadmap_count} roadmaps ({s.get('percentage', 0)}%)")
            
            # Extract roadmap type distribution
            type_details = []
            for t in cluster_data.get('roadmap_type_distribution', []):
                type_details.append(f"{t.get('type', 'Unknown')}: {t.get('count', 0)}/{roadmap_count} roadmaps ({t.get('percentage', 0)}%)")
            
            # Extract team composition
            team_details = []
            for t in cluster_data.get('team_composition', []):
                team_details.append(f"{t.get('category', 'Unknown')}: {t.get('percentage', 0)}% of total team members")
            
            # Get solution themes and approaches with richness
            solution_themes = cluster_data.get('solution_themes', [])
            solution_approaches = cluster_data.get('solution_approaches', [])
            solution_criteria = cluster_data.get('solution_success_criteria', [])
            solution_narrative = cluster_data.get('solution_narrative', '')
            
            # Get technologies
            technologies = [t.get('technology', 'Unknown') for t in cluster_data.get('key_technologies', []) if t]
            
            system_prompt = f"""You are an expert Enterprise Architect creating reusable roadmap templates and patterns based on analyzed data.

═══════════════════════════════════════════════════════════════════
CLUSTER ANALYSIS SUMMARY:
═══════════════════════════════════════════════════════════════════

Portfolio: {portfolio_name}
Roadmaps Analyzed: {roadmap_count}
Cluster Quality Score: {silhouette_score:.3f}
Velocity Score: {velocity:.3f}
Value Realization Score: {value_realization:.3f}

Portfolio Distribution:
{chr(10).join(portfolio_details) if portfolio_details else 'No portfolio data'}

Priority Distribution:
{chr(10).join(priority_details) if priority_details else 'No priority data'}

Status Distribution:
{chr(10).join(status_details) if status_details else 'No status data'}

Roadmap Type Distribution:
{chr(10).join(type_details) if type_details else 'No type data'}

Team Composition:
{chr(10).join(team_details) if team_details else 'No team data'}

Average Metrics:
- Duration: {avg_duration} days
- KPIs per roadmap: {avg_kpi_count}
- Team size: {avg_team_size} members
- Constraints per roadmap: {avg_constraint_count}

═══════════════════════════════════════════════════════════════════
KEY RESULTS (KPIs) - {len(cluster_data.get('key_results', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {kpi}" for kpi in cluster_data.get('key_results', [])[:8]]) if cluster_data.get('key_results') else 'No KPIs'}

═══════════════════════════════════════════════════════════════════
SCOPES - {len(cluster_data.get('scopes', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {scope}" for scope in cluster_data.get('scopes', [])[:8]]) if cluster_data.get('scopes') else 'No scopes'}

═══════════════════════════════════════════════════════════════════
CONSTRAINTS - {len(cluster_data.get('constraints', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {constr}" for constr in cluster_data.get('constraints', [])[:8]]) if cluster_data.get('constraints') else 'No constraints'}

═══════════════════════════════════════════════════════════════════
SOLUTION THEMES:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {theme}" for theme in solution_themes]) if solution_themes else 'No solution themes'}

═══════════════════════════════════════════════════════════════════
SOLUTION APPROACHES:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {approach}" for approach in solution_approaches]) if solution_approaches else 'No solution approaches'}

═══════════════════════════════════════════════════════════════════
SUCCESS CRITERIA:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {crit}" for crit in solution_criteria[:5]]) if solution_criteria else 'No success criteria'}

═══════════════════════════════════════════════════════════════════
INFERRED TECHNOLOGIES:
═══════════════════════════════════════════════════════════════════
{', '.join(technologies[:10]) if technologies else 'No technologies inferred'}

═══════════════════════════════════════════════════════════════════
SOLUTION NARRATIVE:
═══════════════════════════════════════════════════════════════════
{solution_narrative[:1500] if solution_narrative else 'No narrative available'}

═══════════════════════════════════════════════════════════════════
CLUSTER EXPLANATION:
═══════════════════════════════════════════════════════════════════
{explanation_data.get('explanation', 'No explanation available')}

═══════════════════════════════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════════════════════════════

Generate a **RoadmapTemplate** and **RoadmapPattern** based on this rich data.

**REQUIREMENTS:**

1. Names and Titles:
   - Must be professional, industry-standard
   - Reflect the actual patterns seen in the data
   - Reference the dominant characteristics (e.g., if 3/4 roadmaps are "Strategic", name should reflect that)
   - MUST be unique{f' — the following names are already taken and MUST NOT be reused: {chr(10).join("     • " + n for n in existing_pattern_names)}' if existing_pattern_names else ''}

2. Descriptions:
   - Incorporate SPECIFIC data from the analysis above
   - Reference frequencies, percentages, and actual examples
   - Use the Solution Narrative as foundation
   - Mention which capabilities/patterns appear in X out of Y roadmaps
   - Include technology stacks and approaches

3. Objectives (for template):
   - Must be SPECIFIC and MEASURABLE
   - Derived from the KPIs and Success Criteria
   - Reference the value realization score and velocity metrics
   - Example: "Achieve 95% deployment success rate (based on {roadmap_count} roadmaps with {value_realization:.2f} realization score)"

4. Dates and Timeline:
   - start_date and end_date should reflect average roadmap timeline (format: YYYY-MM-DD)
   - time_horizon should be in "N days" format reflecting average duration
   - org_strategy_align: numeric score 0.0-1.0 based on strategic alignment data

5. Metadata Fields:
   - Choose values based on the MAJORITY pattern in the data
   - If 75% roadmaps are High priority, template priority = High
   - If most roadmaps are Strategic type, use Strategic
   - budget: numeric value based on aggregate roadmap budgets (or 0.0 if not available)
   - owner_id and strategic_goal: populate from cluster data if available, else leave empty
   - All fields should reflect actual data, not defaults

5. Pattern Description:
   - 2-4 paragraphs minimum
   - Start with business context
   - Detail technical approaches with specificity
   - Reference solution themes and approaches
   - Mention governance, team structure, and constraints
   - Include success metrics and outcomes

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
═══════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no markdown, no explanations):

{{
    "template": {{
        "name": "Template name reflecting dominant pattern",
        "title": "Same or slight variation",
        "description": "2-3 paragraph description with specific data references (e.g., 'Based on analysis of {roadmap_count} roadmaps where 75% use technology X...')",
        "objectives": [
            "Specific objective with metric (from KPIs/success criteria)",
            "Another specific objective",
            "..."
        ],
        "start_date": "YYYY-MM-DD format based on average roadmap start",
        "end_date": "YYYY-MM-DD format based on average roadmap end",
        "budget": "numeric value from roadmap budget data or 0.0",
        "category": "Category from roadmap types",
        "org_strategy_align": "numeric value 0.0-1.0 based on strategic alignment",
        "priority": "Priority level (High/Medium/Low) based on majority",
        "current_state": "State (Active/Draft/etc) based on status distribution",
        "roadmap_type": "Type (Strategic/Operational/etc) based on majority",
        "status": "Status based on distribution",
        "visibility": "Internal/Public/etc",
        "solution": "1-2 sentence summary of solution narrative",
        "owner_id": "owner id if available, else empty string",
        "strategic_goal": "strategic goal if available, else empty string",
        "time_horizon": "N days based on avg duration",
        "review_cycle": "Quarterly/Monthly/etc",
        "tags": ["tag1", "tag2", "..."]
    }},
    "pattern": {{
        "name": "Pattern name",
        "description": "Multi-paragraph detailed description with data references, frequencies, and specific examples from the analysis",
        "category": "MUST be one of: {', '.join(PATTERN_CATEGORY_TAXONOMY)}",
        "strategic_focus": "Focus area",
        "maturity_level": "Maturity",
        "implementation_complexity": "Complexity level",
        "governance_model": "Governance approach"
    }}
}}"""
        except Exception as e:
            print(f"ERROR constructing system_prompt in generate_workflow_and_template_names: {e}")
            raise e

        try:
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user="Generate names and metadata.")
            response = self.llm.run(chat_completion, ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1), 'analysis::generate_template')
            result = extract_json_after_llm(response)
            
            # Post-process template: fill in all required fields for RoadmapTemplate schema
            if "template" not in result:
                result["template"] = {}
            
            template = result["template"]
            # Extract tenant_id from cluster_data or fallback to a default (should always be in cluster_data if properly passed)
            tenant_id_for_id = cluster_data.get("tenant_id", "unknown")
            template.setdefault("id", f"tpl_{tenant_id_for_id}_{customer_id}_{cluster_idx}_{hash(str(template)) % 10000}")
            template.setdefault("tenant_id", cluster_data.get("tenant_id", customer_id))
            template.setdefault("name", template.get("name", ""))
            template.setdefault("title", template.get("title", template.get("name", "")))
            
            # Enhance description with pattern-based context
            base_description = template.get("description", "")
            description_enhancements = []
            
            # Add portfolio and roadmap context
            if cluster_data.get("roadmap_count", 0) > 0:
                description_enhancements.append(
                    f"Based on analysis of {cluster_data.get('roadmap_count', 1)} roadmap(s) with proven execution patterns."
                )
            
            # Add key technologies if available
            technologies = [t.get('technology', '') for t in cluster_data.get('key_technologies', []) if t.get('technology')]
            if technologies:
                tech_str = ', '.join(technologies[:5])
                description_enhancements.append(f"Leverages technologies including: {tech_str}")
            
            # Add team composition context
            team_comp = cluster_data.get('team_composition', [])
            if team_comp:
                team_roles = [f"{t.get('category', '')} ({t.get('percentage', 0)}%)" for t in team_comp[:3] if t.get('category')]
                if team_roles:
                    description_enhancements.append(f"Team structure: {', '.join(team_roles)}")
            
            # Add KPI/objective context
            if cluster_data.get('key_results', []):
                kpi_sample = cluster_data['key_results'][:2]
                kpi_str = ', '.join(kpi_sample)
                description_enhancements.append(f"Key objectives include: {kpi_str}")
            
            # Combine base description with enhancements
            if description_enhancements:
                enhanced_description = base_description + "\n\n" + "\n".join(description_enhancements)
            else:
                enhanced_description = base_description
            
            template.setdefault("description", enhanced_description)
            template.setdefault("objectives", template.get("objectives", []))
            template.setdefault("start_date", "")
            template.setdefault("end_date", "")
            template.setdefault("budget", 0.0)
            template.setdefault("category", template.get("category", ""))
            template.setdefault("org_strategy_align", "")
            template.setdefault("priority", template.get("priority", ""))
            template.setdefault("current_state", template.get("current_state", ""))
            template.setdefault("roadmap_type", template.get("roadmap_type", ""))
            template.setdefault("status", template.get("status", ""))
            template.setdefault("visibility", template.get("visibility", ""))
            
            # Build comprehensive solution field from cluster data (not just LLM one-liner)
            solution_parts = []
            
            # Add solution narrative if available
            if cluster_data.get("solution_narrative"):
                solution_parts.append(cluster_data["solution_narrative"][:1000])
            
            # Add solution themes with context
            themes = cluster_data.get("solution_themes", [])
            if themes:
                themes_str = ", ".join(themes[:3])
                solution_parts.append(f"Key Solution Themes: {themes_str}")
            
            # Add solution approaches with context
            approaches = cluster_data.get("solution_approaches", [])
            if approaches:
                approaches_str = ", ".join(approaches[:3])
                solution_parts.append(f"Proven Approaches: {approaches_str}")
            
            # Add success criteria with context
            criteria = cluster_data.get("solution_success_criteria", [])
            if criteria:
                criteria_str = ", ".join(criteria[:3])
                solution_parts.append(f"Success Criteria: {criteria_str}")
            
            # Build comprehensive solution field
            if solution_parts:
                template_solution = " | ".join(solution_parts)
            else:
                template_solution = template.get("solution", "Roadmap implementation driven by proven patterns and best practices.")
            
            template.setdefault("solution", template_solution)
            template.setdefault("version", "1.0")
            template.setdefault("owner_id", "")
            template.setdefault("strategic_goal", "")
            template.setdefault("time_horizon", template.get("time_horizon", ""))
            template.setdefault("review_cycle", template.get("review_cycle", ""))
            template.setdefault("tags", template.get("tags", []))
            template.setdefault("created_at", str(int(time.time())))
            template.setdefault("updated_at", str(int(time.time())))
            template.setdefault("template_source", "Pattern Analysis")
            template.setdefault("adoption_count", 0)
            template.setdefault("validity_score", 0.0)
            
            # Post-process pattern: fill in all required fields
            if "pattern" not in result:
                result["pattern"] = {}
            
            pattern = result["pattern"]
            # Extract tenant_id from cluster_data (CRITICAL: must be present for tenant isolation)
            tenant_id_for_pattern = cluster_data.get("tenant_id", "unknown")
            pattern.setdefault("id", f"pattern_{tenant_id_for_pattern}_{customer_id}_{cluster_idx}_{hash(str(pattern)) % 10000}")
            pattern.setdefault("tenant_id", cluster_data.get("tenant_id", customer_id))
            pattern.setdefault("name", result["pattern"].get("name", ""))
            pattern.setdefault("description", result["pattern"].get("description", ""))
            pattern.setdefault("category", result["pattern"].get("category", ""))
            # Normalize category to taxonomy — if LLM returned something not in the list, find closest match
            if pattern.get("category") and pattern["category"] not in PATTERN_CATEGORY_TAXONOMY:
                cat_lower = pattern["category"].lower().replace(" ", "_").replace("-", "_")
                matched = next((t for t in PATTERN_CATEGORY_TAXONOMY if t in cat_lower or cat_lower in t), None)
                if matched:
                    pattern["category"] = matched
                else:
                    pattern["category"] = "digital_transformation"  # safe default
            pattern["scope"] = "workflow"  # Always force "workflow" — LLM may return empty string
            pattern.setdefault("confidence_score", explanation_data.get("llm_confidence", 0.0))
            pattern.setdefault("support_score", silhouette_score)
            pattern.setdefault("key_milestones", cluster_data.get("key_milestones", []))
            pattern.setdefault("key_kpis", cluster_data.get("key_results", []))
            pattern.setdefault("avg_milestone_velocity", cluster_data.get("velocity_score", 0.0))
            pattern["budget_band"] = cluster_data.get("budget_band", "")
            pattern.setdefault("constraints", cluster_data.get("constraints", []))
            pattern.setdefault("created_at", str(datetime.now().date()))
            pattern.setdefault("explanation", explanation_data.get("explanation", ""))
            pattern.setdefault("summary_period", cluster_data.get("summary_period", f"{datetime.now().year}-Q{(datetime.now().month-1)//3 + 1}"))
            
            # Roadmap-specific fields
            pattern["roadmap_ids"] = cluster_data.get("roadmap_ids", [])
            pattern["common_scopes"] = cluster_data.get("scopes", [])
            pattern["common_priorities"] = cluster_data.get("priorities", [])
            pattern["common_statuses"] = cluster_data.get("statuses", [])
            pattern["solution_themes"] = cluster_data.get("solution_themes", [])
            pattern["solution_approaches"] = cluster_data.get("solution_approaches", [])
            pattern["solution_success_criteria"] = cluster_data.get("solution_success_criteria", [])
            pattern["solution_narrative"] = cluster_data.get("solution_narrative", "")
            pattern["key_technologies"] = [t["technology"] for t in cluster_data.get("key_technologies", []) if isinstance(t, dict) and t.get("technology")]
            pattern["key_risk_mitigations"] = cluster_data.get("constraints", [])
            pattern["team_allocations"] = cluster_data.get("team_structure", [])
            pattern["resource_distribution"] = cluster_data.get("resource_distribution", [])
            pattern["expected_outcomes_summary"] = cluster_data.get("expected_outcomes_summary", [])
            
            # Strategic and Governance fields - use LLM values or empty strings
            pattern.setdefault("strategic_focus", result["pattern"].get("strategic_focus", ""))
            pattern.setdefault("maturity_level", result["pattern"].get("maturity_level", ""))
            pattern.setdefault("implementation_complexity", result["pattern"].get("implementation_complexity", ""))
            pattern.setdefault("governance_model", result["pattern"].get("governance_model", ""))
            
            pattern["state_transition_history"] = cluster_data.get("state_transition_history", [])
            pattern["typical_state_flow"] = cluster_data.get("typical_state_flow", [])
            pattern["stage_duration_insights"] = cluster_data.get("stage_duration_insights", [])
            pattern["avg_days_per_stage"] = cluster_data.get("avg_days_per_stage", "")
            
            # Set strategic_goal on template based on pattern's strategic_focus
            template.setdefault("strategic_goal", pattern.get("strategic_focus", ""))
            
            print(f"\nGenerated RoadmapPattern:")
            print(f"   Name: {pattern.get('name', 'N/A')}")
            print(f"   Category: {pattern.get('category', 'N/A')}")
            print(f"   Roadmap IDs: {len(pattern.get('roadmap_ids', []))}")
            print(f"   Milestones: {len(pattern.get('key_milestones', []))}")
            print(f"   KPIs: {len(pattern.get('key_kpis', []))}")
            print(f"   Timeline Entries: {len(pattern.get('state_transition_history', []))}")
            print(f"   Typical State Flow: {pattern.get('typical_state_flow', [])}")
            print(f"   Avg Days Per Stage: {pattern.get('avg_days_per_stage', 'N/A')}")
            print(f"\nGenerated RoadmapTemplate:")
            print(f"   Name: {template.get('name', 'N/A')}")
            print(f"   Strategic Goal: {template.get('strategic_goal', 'N/A')}")
            print(f"{'='*80}\n")
            
            return result
        except Exception as e:
            print(f"❌ LLM error in generate_workflow_and_template_names: {e}")
            return {"template": {}, "pattern": {}}
    
    def generalize_cluster(self, cluster: List[Dict], min_freq: float = 0.4) -> Dict:
        """
        Generalize roadmap cluster attributes to create schema-aligned metadata.
        Adapted from project generalization for roadmap-specific fields.
        """
        if not cluster:
            return {}

        # Roadmap-specific counters
        portfolio_counter = Counter([p.get("name") for r in cluster for p in r.get("portfolios", [])])
        category_counter = Counter([c.get("name") for r in cluster for c in r.get("categories", [])])
        constraint_counter = Counter([c.get("constraint_name") for r in cluster for c in r.get("constraints", [])])
        scope_counter = Counter([s.get("scope_name") for r in cluster for s in r.get("scopes", [])])
        priority_counter = Counter([
            r.get("priorities", [{"priority_level": "Unknown"}])[0].get("priority_level", "Unknown") for r in cluster
        ])
        status_counter = Counter([
            r.get("statuses", [{"status": "Unknown"}])[0].get("status", "Unknown") for r in cluster
        ])
        roadmap_type_counter = Counter([
            t.get("name", "Unknown") for r in cluster for t in r.get("roadmap_types", [])
        ])
        # For roadmaps, use team_name and labour_type instead of role
        team_names_counter = Counter([t.get("team_name", "Unknown") for r in cluster for t in r.get("team", [])])
        labour_types_counter = Counter([t.get("labour_type", "Unknown") for r in cluster for t in r.get("team", [])])

        roadmap_durations, kpi_counts, team_sizes, constraint_counts = [], [], [], []

        total_roadmaps = len(cluster)
        min_count = total_roadmaps * min_freq

        # ═══════════════════════════════════════════════════════════════════
        # TIMELINE / STATE TRANSITION AGGREGATION
        # ═══════════════════════════════════════════════════════════════════
        # Aggregate timeline data from roadmaps that have it
        all_timelines = []
        state_transitions = Counter()  # Track state->state transitions
        stage_durations = defaultdict(list)  # Track days per stage
        
        for roadmap in cluster:
            timelines = roadmap.get("timelines", [])
            if timelines:
                roadmap_name = roadmap.get("name") or f"Roadmap {roadmap.get('roadmap_id')}"
                for timeline_entry in timelines:
                    # Store with attribution
                    all_timelines.append(f"[{roadmap_name}]: {timeline_entry}")
                    
                    # Parse transitions and durations from natural language
                    # Format: "On 2024-01-15, moved from Draft to Intake, approved. (14 days in this stage)"
                    if "moved from" in timeline_entry and "to" in timeline_entry:
                        try:
                            parts = timeline_entry.split("moved from")[1].split(",")[0]
                            from_to = parts.split(" to ")
                            if len(from_to) == 2:
                                from_state = from_to[0].strip()
                                to_state = from_to[1].strip()
                                state_transitions[f"{from_state} → {to_state}"] += 1
                        except:
                            pass
                    
                    # Extract stage duration
                    if "days in this stage" in timeline_entry:
                        try:
                            days_part = timeline_entry.split("(")[1].split("days")[0].strip()
                            days = int(days_part)
                            # Extract current state for duration tracking
                            if "moved from" in timeline_entry:
                                parts = timeline_entry.split("moved from")[1].split(",")[0]
                                to_state = parts.split(" to ")[1].strip() if " to " in parts else "Unknown"
                                stage_durations[to_state].append(days)
                        except:
                            pass
        
        # Build typical state flow from most common transitions
        typical_state_flow = [t for t, _ in state_transitions.most_common(5)]
        
        # Calculate average days per stage
        stage_duration_insights = []
        avg_days_per_stage_parts = []
        for stage, durations in stage_durations.items():
            avg_days = int(sum(durations) / len(durations))
            stage_duration_insights.append(f"{stage}: avg {avg_days} days (from {len(durations)} roadmaps)")
            avg_days_per_stage_parts.append(f"{stage}={avg_days}d")
        
        avg_days_per_stage = ", ".join(avg_days_per_stage_parts) if avg_days_per_stage_parts else ""
        
        print(f"[DEBUG] Timeline aggregation: {len(all_timelines)} entries, {len(typical_state_flow)} state flows, {len(stage_duration_insights)} stage insights")

        # Compute team composition based on labour_type (not role, which doesn't exist for roadmaps)
        team_composition = Counter()
        total_team_members = sum(len(r.get("team", [])) for r in cluster)
        
        for roadmap in cluster:
            for member in roadmap.get("team", []):
                labour_type = member.get("labour_type", "Unknown")
                team_composition[labour_type] += 1

        team_composition_dist = [
            {"category": k, "percentage": round((v / total_team_members) * 100, 2)}
            for k, v in team_composition.items()
            if total_team_members > 0
        ]

        for roadmap in cluster:
            start_date = roadmap.get("start_date")
            end_date = roadmap.get("end_date")
            if start_date and end_date:
                try:
                    duration = (np.datetime64(end_date) - np.datetime64(start_date)).astype(int)
                    roadmap_durations.append(duration)
                except Exception:
                    pass

            kpi_count = len(roadmap.get("key_results", []))
            kpi_counts.append(kpi_count)

            team_size = len(roadmap.get("team", []))
            team_sizes.append(team_size)

            constraint_count = len(roadmap.get("constraints", []))
            constraint_counts.append(constraint_count)

        avg_roadmap_duration = int(np.nanmean(roadmap_durations)) if roadmap_durations else 0
        avg_kpi_count = round(np.nanmean(kpi_counts), 2) if kpi_counts else 0
        avg_team_size = int(np.nanmean(team_sizes)) if team_sizes else 5
        avg_constraint_count = round(np.nanmean(constraint_counts), 2) if constraint_counts else 0

        # LLM for generalized KPIs, scopes, constraints
        all_kpis = [str(k.get("kpi_name") or "Unknown") for r in cluster for k in r.get("key_results", []) if k]
        all_scopes = [str(s.get("scope_name") or "Unknown") for r in cluster for s in r.get("scopes", []) if s]
        all_constraints = [str(c.get("constraint_name") or "Unknown") for r in cluster for c in r.get("constraints", []) if c]
        
        entity_label = self._get_entity_type_label()
        
        # Filter out None values and convert to strings for joining
        kpis_str = ', '.join(str(x) for x in set(all_kpis) if x)
        scopes_str = ', '.join(str(x) for x in set(all_scopes) if x)
        portfolios_str = ', '.join(str(x) for x in set(portfolio_counter.keys()) if x)
        team_names_str = ', '.join(str(x) for x in set(team_names_counter.keys()) if x)
        labour_types_str = ', '.join(str(x) for x in set(labour_types_counter.keys()) if x)
        constraints_str = ', '.join(str(x) for x in set(all_constraints) if x)
        
        # Extract solution information with roadmap attribution
        roadmap_details = []
        all_solution_texts = []
        
        print(f"[DEBUG] Extracting detailed information from cluster with {len(cluster)} roadmaps")
        
        # Build detailed roadmap-by-roadmap breakdown with attribution
        for i, roadmap in enumerate(cluster):
            roadmap_name = roadmap.get("name") or f"Roadmap {roadmap.get('roadmap_id', i)}"
            roadmap_id = roadmap.get("roadmap_id", i)
            
            # Extract all relevant fields with attribution
            roadmap_kpis = [k.get("kpi_name") for k in roadmap.get("key_results", []) if k and k.get("kpi_name")]
            roadmap_scopes = [s.get("scope_name") for s in roadmap.get("scopes", []) if s and s.get("scope_name")]
            roadmap_constraints = [c.get("constraint_name") for c in roadmap.get("constraints", []) if c and c.get("constraint_name")]
            roadmap_portfolios = [p.get("name") for p in roadmap.get("portfolios", []) if p and p.get("name")]
            roadmap_categories = [c.get("name") for c in roadmap.get("categories", []) if c and c.get("name")]
            roadmap_types = [t.get("name") for t in roadmap.get("roadmap_types", []) if t and t.get("name")]
            
            priority = roadmap.get("priorities", [{}])[0].get("priority_level", "Unknown") if roadmap.get("priorities") else "Unknown"
            status = roadmap.get("statuses", [{}])[0].get("status", "Unknown") if roadmap.get("statuses") else "Unknown"
            
            solution_field = roadmap.get("solution")
            objectives = roadmap.get("roadmap_objectives") or roadmap.get("objectives")
            
            # Build detailed roadmap entry
            detail_parts = [f"## Roadmap: '{roadmap_name}' (ID: {roadmap_id})"]
            
            if objectives:
                detail_parts.append(f"   Objectives: {objectives[:300]}")
            
            if roadmap_kpis:
                detail_parts.append(f"   KPIs ({len(roadmap_kpis)}): {', '.join(roadmap_kpis[:5])}")
            
            if roadmap_scopes:
                detail_parts.append(f"   Scopes ({len(roadmap_scopes)}): {', '.join(roadmap_scopes[:5])}")
            
            if roadmap_constraints:
                detail_parts.append(f"   Constraints ({len(roadmap_constraints)}): {', '.join(roadmap_constraints[:5])}")
            
            if roadmap_portfolios:
                detail_parts.append(f"   Portfolios: {', '.join(roadmap_portfolios)}")
            
            if roadmap_categories:
                detail_parts.append(f"   Categories: {', '.join(roadmap_categories)}")
            
            if roadmap_types:
                detail_parts.append(f"   Types: {', '.join(roadmap_types)}")
            
            detail_parts.append(f"   Priority: {priority} | Status: {status}")
            
            if solution_field and solution_field.strip() and solution_field != "None":
                detail_parts.append(f"   Solution Details:\n   {solution_field[:800]}")
                all_solution_texts.append(f"[{roadmap_name}]: {solution_field}")
            
            roadmap_details.append("\n".join(detail_parts))

        print(f"[DEBUG] Collected {len(all_solution_texts)} solution texts from cluster")
        
        # Build comprehensive context with roadmap details
        detailed_roadmaps_context = "\n\n".join(roadmap_details)
        
        # Build frequency analysis for prompt
        kpi_freq = Counter(all_kpis)
        scope_freq = Counter(all_scopes)
        constraint_freq = Counter(all_constraints)
        
        kpi_analysis = []
        for kpi, count in kpi_freq.most_common(10):
            pct = round((count / total_roadmaps) * 100, 1)
            kpi_analysis.append(f"{kpi} ({count}/{total_roadmaps} roadmaps = {pct}%)")
        
        scope_analysis = []
        for scope, count in scope_freq.most_common(10):
            pct = round((count / total_roadmaps) * 100, 1)
            scope_analysis.append(f"{scope} ({count}/{total_roadmaps} roadmaps = {pct}%)")
        
        constraint_analysis = []
        for constr, count in constraint_freq.most_common(10):
            pct = round((count / total_roadmaps) * 100, 1)
            constraint_analysis.append(f"{constr} ({count}/{total_roadmaps} roadmaps = {pct}%)") 
        
        system_prompt = f"""You are an expert Solution Architect and Business Analyst specializing in enterprise roadmap pattern recognition.

Your task is to analyze {total_roadmaps} roadmaps and synthesize their patterns into actionable, reusable templates.

═══════════════════════════════════════════════════════════════════
DETAILED ROADMAP BREAKDOWN (With Attribution):
═══════════════════════════════════════════════════════════════════

{detailed_roadmaps_context}

═══════════════════════════════════════════════════════════════════
FREQUENCY ANALYSIS:
═══════════════════════════════════════════════════════════════════

KPIs Across Roadmaps:
{chr(10).join(kpi_analysis) if kpi_analysis else 'No KPIs found'}

Scopes Across Roadmaps:
{chr(10).join(scope_analysis) if scope_analysis else 'No scopes found'}

Constraints Across Roadmaps:
{chr(10).join(constraint_analysis) if constraint_analysis else 'No constraints found'}

Portfolio Distribution: {', '.join([f"{k} ({v} roadmaps)" for k, v in portfolio_counter.most_common(5)])}
Priority Distribution: {', '.join([f"{k} ({v} roadmaps)" for k, v in priority_counter.most_common()])}
Status Distribution: {', '.join([f"{k} ({v} roadmaps)" for k, v in status_counter.most_common()])}

═══════════════════════════════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════════════════════════════

Synthesize this information into generalized patterns. BE SPECIFIC and reference roadmaps by name.

1. **Generalized KPIs** (3-5):
   - Create generalized KPI categories that represent the patterns you see
   - Example: "Customer Satisfaction Score (seen in 3/4 roadmaps: Roadmap A, B, C)"
   - Focus on KPIs that appear in at least {min_count} roadmaps or represent key patterns

2. **Generalized Scopes** (3-5):
   - Identify scope themes that span multiple roadmaps
   - Example: "Cloud Infrastructure Modernization (Roadmap X implements AWS migration, Roadmap Y uses Azure)"
   - Group similar scopes into broader categories

3. **Generalized Constraints** (3-5):
   - Extract common constraint patterns
   - Example: "Regulatory Compliance Requirements (GDPR in Roadmap A, HIPAA in Roadmap B)"
   - Include specific examples from roadmaps

4. **Team Structure Patterns** (3-5 categories):
   - Identify common team composition patterns
   - Reference which roadmaps use which team structures

5. **Labour Type Categories** (3-5):
   - Generalize labour type patterns across roadmaps
   - Note frequency and distribution

6. **Solution Themes** (3-5) - CRITICAL:
   - Major architectural or strategic themes with SPECIFIC roadmap references
   - Example: "Event-Driven Microservices Architecture (implemented in Roadmap A with Kafka, Roadmap C with RabbitMQ)"
   - Example: "AI-Powered Customer Support (Roadmap B uses GPT-4, Roadmap D uses custom LLM)"
   - BE DETAILED about technologies, approaches, and which roadmaps use them

7. **Solution Approaches** (3-5) - CRITICAL:
   - Specific implementation strategies with roadmap attribution
   - Example: "Phased Migration Approach: Roadmap A migrates database first, then application layer; Roadmap C uses parallel deployment"
   - Include technical details and roadmap names

8. **Solution Success Criteria** (3-5):
   - Measurable outcomes that multiple roadmaps target
   - Reference which roadmaps define which success criteria

9. **Solution Narrative** (2-4 paragraphs) - CRITICAL:
   Write a comprehensive synthesis that:
   - Opens with the common business problem these roadmaps address
   - Details specific architectural patterns with roadmap attribution (e.g., "Roadmap X and Roadmap Y both implement...")
   - Describes data flows, integration points, and technical approaches used across roadmaps
   - References specific technologies and their usage patterns
   - Explains user experiences and expected outcomes
   - Concludes with success patterns and lessons learned
   
   Be RICH and DESCRIPTIVE. Include roadmap names throughout.

10. **Inferred Technologies** (5-7):
    - List technologies/tools with roadmap attribution
    - Example: "Kubernetes (used by Roadmap A, C, D)"

11. **Inferred Milestones** (5-7):
    - Key phases/milestones with frequency
    - Example: "MVP Launch (appears in 3/4 roadmaps)"

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
═══════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no markdown, no explanations):

{{
    "kpis": ["KPI name with context", ...],
    "scopes": ["Scope theme with details", ...],
    "constraints": ["Constraint pattern with examples", ...],
    "team_names": ["Team category", ...],
    "labour_types": ["Labour type category", ...],
    "solution_themes": ["Architectural theme with roadmap references", ...],
    "solution_approaches": ["Implementation strategy with specific roadmap examples", ...],
    "solution_success_criteria": ["Measurable outcome with roadmap attribution", ...],
    "solution_narrative": "Multi-paragraph synthesis with specific roadmap references throughout...",
    "technologies": ["Technology (Roadmap A, B)", ...],
    "milestones": ["Milestone name (X/Y roadmaps)", ...]
}}"""
        
        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generalize and give template fields for kpis, scopes, constraints, solutions, and other fields that you feel you have the ability to enter"
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::generalize_cluster'
            )
            llm_result = extract_json_after_llm(response)
            print(llm_result)
        except Exception as e:
            print(f"LLM error in generalize_cluster: {e}")
            llm_result = {"kpis": [], "scopes": [], "constraints": []}

        end_dates = [np.datetime64(r.get("end_date")) for r in cluster if r.get("end_date")]
        if not end_dates:
            now = datetime.now()
            quarter = (now.month-1)//3 + 1
            summary_period = f"{now.year}-Q{quarter}"
        else:
            max_date = max(end_dates)
            year = int(max_date.astype('datetime64[Y]').astype(int)) + 1970
            month = int(max_date.astype('datetime64[M]').astype(int)) % 12
            quarter = (month // 3) + 1
            summary_period = f"{year}-Q{quarter}"

        # Calculate additional metrics to match ProjectPatternGenerator
        velocity_score = 1 / avg_roadmap_duration if avg_roadmap_duration > 0 else 0
        team_structure = "matrix" if len(portfolio_counter) > 1 else "flat"
        
        # Value realization score (if KPIs have success rates)
        kpi_success_rates = []
        for roadmap in cluster:
            for kpi in roadmap.get("key_results", []):
                if "success_rate" in kpi:
                    kpi_success_rates.append(kpi.get("success_rate", 0.0))
        value_realization_score = np.nanmean(kpi_success_rates) if kpi_success_rates else 0
        delivery_success_score = value_realization_score
        
        # Weighted portfolio list (equivalent to key_technologies in projects)
        portfolio_weightage = [
            {"portfolio": k, "count": v, "percentage": round((v / sum(portfolio_counter.values())) * 100, 2)}
            for k, v in portfolio_counter.items()
            if v >= min_count
        ]
        
        # Priority and status distributions
        priority_dist = [
            {"priority": k, "count": v, "percentage": round((v / total_roadmaps) * 100, 2)}
            for k, v in priority_counter.items()
        ]
        
        status_dist = [
            {"status": k, "count": v, "percentage": round((v / total_roadmaps) * 100, 2)}
            for k, v in status_counter.items()
        ]
        
        roadmap_type_dist = [
            {"type": k, "count": v, "percentage": round((v / total_roadmaps) * 100, 2)}
            for k, v in roadmap_type_counter.items()
        ]
        
        # Resource distribution - use labour_type for roadmaps (no role field exists)
        resource_distribution = Counter()
        for roadmap in cluster:
            for member in roadmap.get("team", []):
                labour_type = member.get("labour_type", "Unknown")
                resource_distribution[labour_type] += 1

        # Use LLM to summarize solution themes if we have solution text
        solution_summary = {
            "themes": llm_result.get("solution_themes", []),  # Use LLM-extracted themes
            "approaches": llm_result.get("solution_approaches", []),  # Use LLM-extracted approaches
            "success_criteria": llm_result.get("solution_success_criteria", []),  # Use LLM-extracted criteria
            "narrative": llm_result.get("solution_narrative", "")
        }

        entity_id = self._get_entity_id_key()
        entity_count = self._get_entity_count_key()
        entity_ids_key = entity_id.replace('_id', '_ids')
        
        # Format inferred technologies for key_technologies structure
        inferred_technologies = [
            {"technology": t, "count": total_roadmaps, "percentage": 100.0} 
            for t in llm_result.get("technologies", [])
        ]

        return {
            "tenant_id": cluster[0].get("tenant_id") if cluster else None,  # CRITICAL: Must propagate tenant_id for downstream pattern generation
            "portfolios": [k for k, v in portfolio_counter.items() if v >= min_count],
            "key_portfolios": portfolio_weightage,
            "key_results": llm_result.get("kpis", []),
            "scopes": llm_result.get("scopes", []),
            "categories": [k for k, v in category_counter.items() if v >= min_count],
            "priorities": [k for k, v in priority_counter.items()],
            "statuses": [k for k, v in status_counter.items()],
            "roadmap_types": [k for k, v in roadmap_type_counter.items() if v >= min_count],
            entity_count: total_roadmaps,
            entity_ids_key: [r.get(entity_id) for r in cluster],
            "velocity_score": velocity_score,
            "avg_roadmap_duration": avg_roadmap_duration,
            "avg_kpi_count": avg_kpi_count,
            "avg_team_size": avg_team_size,
            "avg_constraint_count": avg_constraint_count,
            "team_structure": team_structure,
            "priority_distribution": priority_dist,
            "status_distribution": status_dist,
            "roadmap_type_distribution": roadmap_type_dist,
            "value_realization_score": value_realization_score,
            "delivery_success_score": delivery_success_score,
            "team_composition": team_composition_dist,
            "resource_distribution": dict(resource_distribution),
            "constraints": llm_result.get("constraints", []),
            "solution_themes": solution_summary["themes"],
            "solution_approaches": solution_summary["approaches"],
            "solution_success_criteria": solution_summary["success_criteria"],
            "solution_narrative": solution_summary["narrative"],
            "key_technologies": inferred_technologies,
            "milestones": llm_result.get("milestones", []),
            "key_milestones": llm_result.get("milestones", []), # Also populate key_milestones for pattern
            "summary_period": summary_period,
            "roadmap_ids": [r.get("roadmap_id") for r in cluster],
            "state_transition_history": all_timelines[:20],  # Limit to 20 most recent
            "typical_state_flow": typical_state_flow,
            "stage_duration_insights": stage_duration_insights,
            "avg_days_per_stage": avg_days_per_stage
        }

    
    def generate_portfolio_pattern(
        self,
        customer_id: str,
        tenant_id: int,
        portfolio_name: str,
        portfolio_id: str,
        clusters: List[Dict],
        industry_id: str
    ) -> tuple[Dict, Dict]:
        """Generate portfolio-level Pattern node for roadmaps (scope=portfolio).
        
        Args:
            customer_id: Customer identifier
            tenant_id: Tenant identifier (REQUIRED - will error if not provided)
            portfolio_name: Name of the portfolio
            portfolio_id: Portfolio vertex ID
            clusters: List of cluster data dictionaries
            industry_id: Industry vertex ID
            
        Returns:
            Tuple of (vertices dict, edges dict)
            
        Raises:
            ValueError: If tenant_id is not provided or is 0
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for generate_portfolio_pattern and cannot be 0 or None")
        print(f"Generating portfolio-level pattern for {portfolio_name} (tenant_id={tenant_id})")
        from collections import defaultdict
        vertices = defaultdict(list)
        edges = defaultdict(list)

        portfolio_pattern_id = f"pattern_{tenant_id}_{customer_id}_{portfolio_id}_portfolio"

        # Calculate aggregates with safe empty list handling
        duration_values = [
            c["generalized"].get("avg_roadmap_duration", 0)
            for c in clusters if c["generalized"].get("avg_roadmap_duration") and not np.isnan(c["generalized"].get("avg_roadmap_duration", 0))
        ]

        velocity_values = [
            c["generalized"].get("velocity_score", 0)
            for c in clusters if c["generalized"].get("velocity_score") and not np.isnan(c["generalized"].get("velocity_score", 0))
        ]
        avg_milestone_velocity = np.nanmean(velocity_values) if velocity_values else 0.0
        
        adherence_values = [
            c["generalized"].get("milestone_adherence_score", 0)
            for c in clusters if c["generalized"].get("milestone_adherence_score") and not np.isnan(c["generalized"].get("milestone_adherence_score", 0))
        ]
        milestone_adherence_score = np.nanmean(adherence_values) if adherence_values else 0.0
        
        success_values = [
            c["generalized"].get("delivery_success_score", 0)
            for c in clusters if c["generalized"].get("delivery_success_score") and not np.isnan(c["generalized"].get("delivery_success_score", 0))
        ]
        delivery_success_score = np.nanmean(success_values) if success_values else 0.0
        
        confidence_values = [c["explanation"].get("llm_confidence", 0) for c in clusters if c["explanation"].get("llm_confidence")]
        confidence_score = np.nanmean(confidence_values) if confidence_values else 0.0
        
        support_values = [c.get("silhouette_score", 0) for c in clusters if c.get("silhouette_score") is not None]
        support_score = np.nanmean(support_values) if support_values else 0.0

        # Aggregate categorical attributes
        all_portfolios = [p for c in clusters for p in c["generalized"].get("key_portfolios", [])]
        all_roadmap_ids = [str(rid) for c in clusters for rid in c["generalized"].get("roadmap_ids", [])]
        all_team_compositions = [t for c in clusters for t in c["generalized"].get("team_composition", [])]
        all_work_types = [w for c in clusters for w in c["generalized"].get("work_type_distribution", [])]
        all_methodologies = [m for c in clusters for m in c["generalized"].get("dev_methodology_dist", [])]
        all_kpis = [k for c in clusters for k in c["names"]["pattern"].get("key_kpis", [])]
        all_milestones = [m for c in clusters for m in c["names"]["pattern"].get("key_milestones", [])]
        all_scopes = [s for c in clusters for s in c["names"]["pattern"].get("key_scopes", [])]
        all_constraints = [c for c in clusters for c in c["generalized"].get("constraints", [])]
        
        # Aggregate solution information from clusters
        all_solution_themes = [t for c in clusters for t in c["generalized"].get("solution_themes", [])]
        all_solution_approaches = [a for c in clusters for a in c["generalized"].get("solution_approaches", [])]
        all_solution_success_criteria = [s for c in clusters for s in c["generalized"].get("solution_success_criteria", [])]
        
        solution_themes = [k for k, v in Counter(all_solution_themes).most_common(5) if k]
        solution_approaches = [k for k, v in Counter(all_solution_approaches).most_common(5) if k]
        solution_success_criteria = [k for k, v in Counter(all_solution_success_criteria).most_common(10) if k]

        # Aggregate technologies from clusters (key_technologies are dicts with "technology" key)
        all_technologies = [t for c in clusters for t in c["generalized"].get("key_technologies", [])]
        tech_names = [t.get("technology") if isinstance(t, dict) else t for t in all_technologies if t]
        aggregated_technologies = [k for k, v in Counter(tech_names).most_common(7) if k]

        portfolio_counts = Counter(p.get("portfolio") for p in all_portfolios if p.get("portfolio"))
        key_portfolios = [
            {"portfolio": k, "count": v, "percentage": round((v / sum(portfolio_counts.values())) * 100, 2)}
            for k, v in portfolio_counts.items() if v >= len(clusters) * 0.5
        ] if portfolio_counts else []

        team_counts = Counter(t.get("category") for t in all_team_compositions if t.get("category"))
        team_composition = [k for k, v in team_counts.items() if v >= len(clusters) * 0.5]

        work_type_counts = Counter(w.get("type") for w in all_work_types if w.get("type"))
        work_type_distribution = [k for k, v in work_type_counts.items() if v >= len(clusters) * 0.5]

        methodology_counts = Counter(m.get("methodology") for m in all_methodologies if m.get("methodology"))
        dev_methodology_dist = [k for k, v in methodology_counts.items() if v >= len(clusters) * 0.5]

        constraint_counter = Counter(all_constraints)
        constraints = [k for k, v in constraint_counter.most_common(3)]

        key_milestones = [k for k, v in Counter(all_milestones).most_common(3)]
        key_scopes = [k for k, v in Counter(all_scopes).most_common(3)]
        key_kpis = [k for k, v in Counter(all_kpis).most_common(3)]

        budgets = [c["generalized"].get("budget_band") for c in clusters if c["generalized"].get("budget_band")]
        budget_band = Counter(budgets).most_common(1)[0][0] if budgets else "50k-100k"

        summary_periods = [c["generalized"].get("summary_period", "") for c in clusters if c["generalized"].get("summary_period")]
        summary_period = Counter(summary_periods).most_common(1)[0][0] if summary_periods else \
                        f"{datetime.now().year}-Q{(datetime.now().month-1)//3 + 1}"

        # Build context
        context_parts = []
        if key_portfolios:
            context_parts.append(f"- Portfolios: {', '.join(set(p.get('portfolio', '') for p in key_portfolios if p.get('portfolio')))}")
        if all_kpis:
            context_parts.append(f"- KPIs: {', '.join(set(all_kpis))}")
        if all_milestones:
            context_parts.append(f"- Milestones: {', '.join(set(all_milestones))}")
        if all_scopes:
            context_parts.append(f"- Scopes: {', '.join(set(all_scopes))}")
        if all_team_compositions:
            context_parts.append(f"- Team Composition: {', '.join(set(t.get('category', '') for t in all_team_compositions if t.get('category')))}")
        if all_methodologies:
            context_parts.append(f"- Methodologies: {', '.join(set(m.get('methodology', '') for m in all_methodologies if m.get('methodology')))}")
        if all_constraints:
            context_parts.append(f"- Constraints: {', '.join(set(all_constraints))}")
        
        context_str = '\n            '.join(context_parts)
        
        system_prompt = f"""
            Generate a name, description, category, and explanation for a customer-level portfolio pattern in the {portfolio_name} portfolio.
            Given:
            {context_str}
            - Clusters: {len(clusters)}
            Provide:
            - Name for the pattern (e.g., "Enterprise Strategic Alignment").
            - Description summarizing the pattern.
            - Category (e.g., "strategic_alignment").
            - Detailed explanation of common portfolio traits.
            - Strategic Focus: Primary business driver (e.g., Efficiency, Growth, Risk, Innovation).
            - Maturity Level: Assessment of process maturity (Initial, Managed, Defined, Quantitatively Managed, Optimizing).
            - Implementation Complexity: Estimated difficulty (Low, Medium, High).
            - Governance Model: Recommended oversight (e.g., Lightweight, Steering Comm, PMO).
            
            Return as JSON: 
            ```json
            {{ 
                "name": "<text>", 
                "description": "<text>", 
                "category": "<text>", 
                "explanation": "<text>",
                "strategic_focus": "<text>",
                "maturity_level": "<text>",
                "implementation_complexity": "<text>",
                "governance_model": "<text>"
            }}
            ```
        """
        
        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generate portfolio pattern metadata."
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::portfolio_pattern'
            )
            llm_result = extract_json_after_llm(response)
            name = llm_result.get("name", "Portfolio Pattern")
            description = llm_result.get("description", "No description generated.")
            category = llm_result.get("category", portfolio_name.lower().replace(" ", "_"))
            explanation = llm_result.get("explanation", "No explanation generated.")
            strategic_focus = llm_result.get("strategic_focus", "Unknown")
            maturity_level = llm_result.get("maturity_level", "Defined")
            implementation_complexity = llm_result.get("implementation_complexity", "Medium")
            governance_model = llm_result.get("governance_model", "Standard")
        except Exception as e:
            print(f"LLM error in generate_portfolio_pattern: {e}")
            name = "Portfolio Pattern"
            description = "Failed to generate description."
            category = portfolio_name.lower().replace(" ", "_")
            explanation = "Failed to generate explanation."
            strategic_focus = "Unknown"
            maturity_level = "Defined"
            implementation_complexity = "Medium"
            governance_model = "Standard"

        vertices["RoadmapPattern"].append((
            portfolio_pattern_id,
            {
                "id": portfolio_pattern_id,
                "tenant_id": tenant_id,
                "scope": "portfolio",
                "category": category,
                "name": name,
                "description": description,
                "explanation": explanation,
                "confidence_score": round(confidence_score, 3) if not np.isnan(confidence_score) else 0.0,
                "support_score": round(support_score, 3) if not np.isnan(support_score) else 0.0,
                "created_at": str(date.today()),
                "summary_period": summary_period,
                "avg_milestone_velocity": round(avg_milestone_velocity, 3) if not np.isnan(avg_milestone_velocity) else 0.0,
                "budget_band": budget_band,
                "key_milestones": key_milestones,
                "key_kpis": key_kpis,
                "key_technologies": aggregated_technologies,
                "key_risk_mitigations": constraints,
                "constraints": constraints,
                "roadmap_ids": list(set(all_roadmap_ids)),
                "common_scopes": [],
                "common_priorities": [],
                "common_statuses": [],
                "solution_themes": solution_themes,
                "solution_approaches": solution_approaches,
                "solution_success_criteria": solution_success_criteria,
                "solution_narrative": "",
                "team_allocations": [],
                "resource_distribution": [],
                "expected_outcomes_summary": "",
                "strategic_focus": strategic_focus,
                "maturity_level": maturity_level,
                "implementation_complexity": implementation_complexity,
                "governance_model": governance_model
            },
        ))

        for cluster in clusters:
            wf_pattern_id = cluster["names"]["pattern"]["id"]
            edges[self._get_composed_of_pattern_edge()].append((portfolio_pattern_id, wf_pattern_id))
            edges[self._get_derived_from_portfolio_edge()].append((portfolio_pattern_id, portfolio_id))

        edges[self._get_relevant_to_industry_edge()].append((portfolio_pattern_id, industry_id))

        return vertices, edges
    
    def generate_customer_pattern(
        self,
        customer_id: str,
        tenant_id: int,
        clusters: List[Dict],
        industry_id: str
    ) -> tuple[Dict, Dict]:
        """Generate customer-level Pattern node for roadmaps (scope=customer).
        
        Args:
            customer_id: Customer identifier
            tenant_id: Tenant identifier (REQUIRED - will error if not provided)
            clusters: List of cluster data dictionaries
            industry_id: Industry vertex ID
            
        Returns:
            Tuple of (vertices dict, edges dict)
            
        Raises:
            ValueError: If tenant_id is not provided or is 0
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for generate_customer_pattern and cannot be 0 or None")
        print(f"Generating customer-level pattern for {customer_id} (tenant_id={tenant_id})")
        from collections import defaultdict
        vertices = defaultdict(list)
        edges = defaultdict(list)

        customer_pattern_id = f"pattern_{tenant_id}_{customer_id}_customer"

        # Aggregate portfolio patterns from clusters
        portfolio_patterns = [
            p for c in clusters
            for p in c.get("vertices", {}).get("RoadmapPattern", [])
            if p[1]["scope"] == "portfolio"
        ]

        if not portfolio_patterns:
            print(f"No portfolio patterns found for customer {customer_id}")
            return dict(vertices), dict(edges)

        # Extract common attributes from portfolio patterns
        confidence_scores = [p[1].get("confidence_score", 0) for p in portfolio_patterns]
        support_scores = [p[1].get("support_score", 0) for p in portfolio_patterns]
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
        avg_support = np.mean(support_scores) if support_scores else 0

        all_methodologies = []
        all_kpis = []
        all_milestones = []
        all_constraints = []
        all_categories = []
        all_roadmap_ids = []
        all_solution_themes = []
        all_solution_approaches = []
        all_solution_success_criteria = []

        for p in portfolio_patterns:
            p_data = p[1]
            all_methodologies.extend(p_data.get("dev_methodology_dist", []))
            all_kpis.extend(p_data.get("key_kpis", []))
            all_milestones.extend(p_data.get("key_milestones", []))
            all_constraints.extend(p_data.get("constraints", []))
            all_categories.append(p_data.get("category", ""))
            all_roadmap_ids.extend(p_data.get("roadmap_ids", []))
            all_solution_themes.extend(p_data.get("solution_themes", []))
            all_solution_approaches.extend(p_data.get("solution_approaches", []))
            all_solution_success_criteria.extend(p_data.get("solution_success_criteria", []))

        methodology_counts = Counter(all_methodologies)
        kpi_counts = Counter(all_kpis)
        milestone_counts = Counter(all_milestones)
        constraint_counts = Counter(all_constraints)
        
        solution_theme_counts = Counter(all_solution_themes)
        solution_approach_counts = Counter(all_solution_approaches)
        solution_criteria_counts = Counter(all_solution_success_criteria)

        key_methodologies = [k for k, v in methodology_counts.most_common(5)]
        key_kpis = [k for k, v in kpi_counts.most_common(5)]
        key_milestones = [k for k, v in milestone_counts.most_common(3)]
        key_constraints = [k for k, v in constraint_counts.most_common(3)]
        
        key_solution_themes = [k for k, v in solution_theme_counts.most_common(5) if k]
        key_solution_approaches = [k for k, v in solution_approach_counts.most_common(5) if k]
        key_solution_criteria = [k for k, v in solution_criteria_counts.most_common(10) if k]

        # Aggregate technologies from portfolio patterns
        all_technologies_raw = [t for p in portfolio_patterns for t in p[1].get("key_technologies", [])]
        key_technologies = [k for k, v in Counter(all_technologies_raw).most_common(7) if k]

        # Extract additional fields
        all_velocities = [p[1].get("avg_milestone_velocity", 0) for p in portfolio_patterns if p[1].get("avg_milestone_velocity")]
        avg_velocity = np.mean(all_velocities) if all_velocities else 0.0
        
        all_strategic_focus = [p[1].get("strategic_focus", "") for p in portfolio_patterns if p[1].get("strategic_focus")]
        strategic_focus_counts = Counter(all_strategic_focus)
        key_strategic_focus = [k for k, v in strategic_focus_counts.most_common(1) if k]

        # Build context from top patterns
        top_patterns = sorted(portfolio_patterns, key=lambda x: x[1].get("confidence_score", 0), reverse=True)[:3]
        context_parts = []
        for p in top_patterns:
            p_data = p[1]
            context_parts.append(f"- {p_data.get('name', 'Pattern')}: {p_data.get('description', '')}")

        context_str = '\n            '.join(context_parts) if context_parts else "No patterns found."

        system_prompt = f"""
            Generate a name, description, category, and explanation for a customer-level roadmap pattern.
            This pattern aggregates {len(portfolio_patterns)} portfolio-level patterns.
            Given patterns:
            {context_str}
            - Key KPIs: {', '.join(key_kpis) if key_kpis else 'N/A'}
            - Key Methodologies: {', '.join(key_methodologies) if key_methodologies else 'N/A'}
            Provide:
            - Name for the customer pattern (e.g., "Enterprise Transformation Roadmap").
            - Description summarizing the customer's roadmap execution style.
            - Category (e.g., "enterprise_transformation").
            - Detailed explanation of common traits.
            Return as JSON: 
            ```json
            {{ "name": "<text>", "description": "<text>", "category": "<text>", "explanation": "<text>" }}
            ```
        """

        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generate customer roadmap pattern metadata."
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::customer_pattern'
            )
            llm_result = extract_json_after_llm(response)
            name = llm_result.get("name", "Customer Roadmap Pattern")
            description = llm_result.get("description", "No description generated.")
            category = llm_result.get("category", "customer_roadmap_pattern")
            explanation = llm_result.get("explanation", "No explanation generated.")
        except Exception as e:
            print(f"LLM error in generate_customer_pattern: {e}")
            name = "Customer Roadmap Pattern"
            description = "Failed to generate description."
            category = "customer_roadmap_pattern"
            explanation = "Failed to generate explanation."

        # tenant_id is now passed as a parameter - no need to extract from clusters
        
        print(f"\n{'='*80}")
        print(f"CUSTOMER PATTERN CREATION")
        print(f"{'='*80}")
        print(f"Pattern ID: {customer_pattern_id}")
        print(f"Name: {name}")
        print(f"Category: {category}")
        print(f"Tenant ID: {tenant_id}")
        print(f"Aggregates {len(portfolio_patterns)} portfolio patterns")
        print(f"Confidence: {round(avg_confidence, 3)}, Support: {round(avg_support, 3)}")
        print(f"{'='*80}\n")

        vertices["RoadmapPattern"].append((
            customer_pattern_id,
            {
                "id": customer_pattern_id,
                "tenant_id": tenant_id,
                "scope": "customer",
                "category": category,
                "name": name,
                "description": description,
                "explanation": explanation,
                "confidence_score": round(avg_confidence, 3),
                "support_score": round(avg_support, 3),
                "created_at": str(date.today()),
                "summary_period": f"{date.today().year}-Q{(date.today().month-1)//3 + 1}",
                "avg_milestone_velocity": avg_velocity if avg_velocity > 0 else 0.0,
                "budget_band": "",
                "key_milestones": key_milestones,
                "key_kpis": key_kpis,
                "key_technologies": key_technologies,
                "key_risk_mitigations": key_constraints,
                "constraints": key_constraints,
                "roadmap_ids": list(set(all_roadmap_ids)),
                "common_scopes": [],
                "common_priorities": [],
                "common_statuses": [],
                "solution_themes": key_solution_themes,
                "solution_approaches": key_solution_approaches,
                "solution_success_criteria": key_solution_criteria,
                "solution_narrative": "",
                "team_allocations": [],
                "resource_distribution": [],
                "expected_outcomes_summary": [],
                "strategic_focus": key_strategic_focus[0] if key_strategic_focus else "",
                "maturity_level": "",
                "implementation_complexity": "",
                "governance_model": ""
            },
        ))

        # Connect to portfolio patterns
        for p in portfolio_patterns:
            portfolio_pattern_id = p[0]
            edges["aggregatesRoadmapPattern"].append((customer_pattern_id, portfolio_pattern_id))

        # Connect to industry
        edges["relevantToRoadmapIndustry"].append((customer_pattern_id, industry_id))

        return vertices, edges
    
    def generate_customer_summary_profile(
        self,
        customer_id: str,
        tenant_id: int,
        clusters: List[Dict],
        projects: List[Dict]
    ) -> tuple[str, Dict]:
        """Generate CustomerSummaryProfile vertex based on roadmap cluster data.
        
        Args:
            customer_id: Customer identifier
            tenant_id: Tenant identifier (REQUIRED - will error if not provided)
            clusters: List of cluster data dictionaries
            projects: List of roadmap dictionaries
            
        Returns:
            Tuple of (profile_id, profile_data dict)
            
        Raises:
            ValueError: If tenant_id is not provided or is 0
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for generate_customer_summary_profile and cannot be 0 or None")
        print(f"Generating CustomerSummaryProfile for {customer_id} (tenant_id={tenant_id})")
        
        avg_velocity = np.nanmean([
            c["generalized"].get("velocity_score", 0) for c in clusters
            if c["generalized"].get("velocity_score")
        ])
        portfolio_diversity_score = len(set(c.get("portfolio_name", "unknown") for c in clusters)) / max(1, len(clusters))
        
        # For roadmaps, get roadmap count
        roadmap_count_key = "roadmap_count"
        template_adoption_count = sum(c["generalized"].get(roadmap_count_key, 0) for c in clusters)
        
        # Calculate portfolio breadth
        all_portfolios = set(
            p.get("portfolio") if isinstance(p, dict) else p
            for c in clusters
            for p in c["generalized"].get("key_portfolios", [])
            if p
        )
        
        tech_breadth_score = len(all_portfolios) / max(1, template_adoption_count) if all_portfolios else 0.0
            
        learning_areas = ["Roadmap planning insights", "Portfolio coordination"]
        preferred_patterns = [c["names"]["pattern"]["id"] for c in clusters if c.get("names", {}).get("pattern", {}).get("id")]
        template_success_vals = [
            c["generalized"].get("delivery_success_score", 0) for c in clusters
            if c["generalized"].get("delivery_success_score")
        ]
        template_success_rate = np.nanmean(template_success_vals) if template_success_vals else 0.0
        most_common_kpis = Counter([
            k for c in clusters for k in c["generalized"].get("key_results", [])
        ]).most_common(3)
        most_common_kpis = [k[0] for k in most_common_kpis]

        portfolio_pattern_adoption = []
        for c in clusters:
            portfolio_id = c.get("portfolio_id", "unknown")
            portfolio_pattern_adoption.append(f"pattern_{customer_id}_{portfolio_id}_portfolio")
        portfolio_pattern_adoption.append(f"pattern_{customer_id}_customer")

        # Extract constraints from roadmaps
        all_constraints = []
        roadmap_ids_key = "roadmap_ids"
        
        for cluster in clusters:
            roadmap_ids = cluster.get("generalized", {}).get(roadmap_ids_key, [])
            for rid in roadmap_ids:
                matching_roadmaps = [p for p in projects if p.get("id") == rid]
                if matching_roadmaps:
                    constraints = matching_roadmaps[0].get("constraints", [])
                    if isinstance(constraints, list):
                        all_constraints.extend([c.get("description") if isinstance(c, dict) else str(c) for c in constraints if c])

        common_challenges = ["Unknown"] if not all_constraints else list(set(all_constraints))[:3]

        if all_constraints:
            system_prompt = f"""
                Summarize the following roadmap constraint descriptions into 2-3 common challenge themes.
                Constraints: {', '.join(set(all_constraints))}
                Suggest:
                - 2-3 challenge themes (e.g., "Resource Constraints", "Timeline Pressure", "Dependency Management").
                Return as JSON: 
                ```json
                {{ "challenges": [] }}
                ```
            """
            try:
                chat_completion = ChatCompletion(
                    system=system_prompt,
                    prev=[],
                    user="Summarize constraints into challenges."
                )
                response = self.llm.run(
                    chat_completion,
                    ModelOptions(model="gpt-4o", max_tokens=1500, temperature=0.1),
                    'analysis::customer_summary'
                )
                llm_result = extract_json_after_llm(response)
                common_challenges = llm_result.get("challenges", ["Unknown"])[:3]
            except Exception as e:
                print(f"LLM error in generate_customer_summary_profile: {e}")
                common_challenges = ["Unknown"]

        execution_risk_score = avg_velocity * 0.3 + template_success_rate * 0.7 if not np.isnan(avg_velocity) else 0.0
        execution_risk_score = 0.0 if np.isnan(execution_risk_score) else execution_risk_score

        profile_id = f"csp_{customer_id}"
        return profile_id, {
            "id": profile_id,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "avg_velocity": round(avg_velocity, 2) if not np.isnan(avg_velocity) else 0.0,
            "portfolio_diversity_score": round(portfolio_diversity_score, 2),
            "template_adoption_count": template_adoption_count,
            "tech_breadth_score": round(tech_breadth_score, 2),
            "learning_areas": learning_areas,
            "last_updated": str(date.today()),
            "preferred_workflows": preferred_patterns,
            "template_success_rate": round(template_success_rate, 2) if not np.isnan(template_success_rate) else 0.0,
            "most_common_kpis": most_common_kpis,
            "common_challenges": common_challenges,
            "portfolio_pattern_adoption": portfolio_pattern_adoption,
            "execution_risk_score": round(execution_risk_score, 2),
            "timestamp": int(time.time())
        }
