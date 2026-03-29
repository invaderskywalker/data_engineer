from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from datetime import date, datetime
import time
import numpy as np
from decimal import Decimal
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.graphql_v2.analysis.pattern_generator import BasePatternGenerator, PATTERN_CATEGORY_TAXONOMY
from src.trmeric_api.logging.AppLogger import appLogger

def safe_float(value):
    """Convert value to float, handling Decimal and other numeric types."""
    if value is None:
        return float('nan')
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')

class ProjectPatternGenerator(BasePatternGenerator):
    """Pattern generator for project entities."""
    
    def _extract_cluster_features(self, cluster: List[Dict]) -> Dict[str, Any]:
        """Extract project-specific features."""
        return {
            # Core dimensional features (matching roadmap structure)
            "portfolios": [str(pf.get("name") or "Unknown") for p in cluster for pf in p.get("portfolios", []) if pf],
            "kpis": [str(k.get("kpi_name") or "Unknown") for p in cluster for k in p.get("key_results", []) if k],
            "entity_ids": [str(p.get("project_id")) for p in cluster if p.get("project_id")],
            
            # Project-specific: risks (vs roadmap constraints)
            "risks": [str(r.get("description") or "Unknown") for p in cluster for r in p.get("risks", []) if r],
            
            # Project-specific: team roles (vs roadmap labour_types)
            "roles": [str(t.get("role") or "Unknown") for p in cluster for t in p.get("team", []) if t],
            
            # Project-specific: technologies (roadmaps don't have this)
            "technologies": [str(t.get("name") or "Unknown") for p in cluster for t in p.get("technologies", []) if t],
            
            # Project-specific: milestones (roadmaps don't have this)
            "milestones": [str(m.get("milestone_name") or "Unknown") for p in cluster for m in p.get("milestones", []) if m],
            
            # Project-specific: type classifications (single values per project)
            "project_types": [str(pt.get("name") or "Unknown") for p in cluster for pt in p.get("project_types", []) if pt],
            "sdlc_methods": [str(sm.get("name") or "Unknown") for p in cluster for sm in p.get("sdlc_methods", []) if sm],
            "categories": [str(cat.get("name") or "Unknown") for p in cluster for cat in p.get("categories", []) if cat],
            
            # Project-specific: status fields
            "project_states": [str(s.get("status") or "Unknown") for p in cluster for s in p.get("statuses", []) if s],
            "delivery_statuses": [str(p.get("delivery_status") or "Unknown") for p in cluster if p.get("delivery_status")],
            "scope_statuses": [str(p.get("scope_status") or "Unknown") for p in cluster if p.get("scope_status")],
            "spend_statuses": [str(p.get("spend_status") or "Unknown") for p in cluster if p.get("spend_status")],
            
            # Project-specific: locations (roadmaps don't have this)
            "locations": [str(loc.get("name") or "Unknown") for p in cluster for loc in p.get("locations", []) if loc],
        }
    
    def _get_entity_type_label(self) -> str:
        return "projects"
    
    def _get_entity_id_key(self) -> str:
        return "project_id"
    
    def _get_entity_count_key(self) -> str:
        return "project_count"
    
    def _get_pattern_vertex_type(self) -> str:
        return "ProjectPattern"
    
    def _get_composed_of_pattern_edge(self) -> str:
        return "composedOfProjectPattern"
    
    def _get_derived_from_portfolio_edge(self) -> str:
        return "derivedFromProjectPortfolio"
    
    def _get_relevant_to_industry_edge(self) -> str:
        return "relevantToProjectIndustry"
    
    def explain_cluster(self, cluster: List[Dict], cluster_idx: int, portfolio_name: str) -> Dict[str, Any]:
        """Explain why project entities were clustered together."""
        if not cluster:
            return {"explanation": "", "llm_confidence": 0.0}

        features = self._extract_cluster_features(cluster)
        entity_label = self._get_entity_type_label()
        
        # Pre-format the lists to avoid f-string issues and filter None values
        entity_ids_str = ', '.join(str(x) for x in features['entity_ids'] if x)
        portfolios_str = ', '.join(str(x) for x in set(features['portfolios']) if x)
        technologies_str = ', '.join(str(x) for x in set(features['technologies']) if x)
        kpis_str = ', '.join(str(x) for x in set(features['kpis']) if x)
        milestones_str = ', '.join(str(x) for x in set(features['milestones']) if x)
        risks_str = ', '.join(str(x) for x in set(features['risks']) if x)
        roles_str = ', '.join(str(x) for x in set(features['roles']) if x)
        project_types_str = ', '.join(str(x) for x in set(features['project_types']) if x)
        sdlc_methods_str = ', '.join(str(x) for x in set(features['sdlc_methods']) if x)
        categories_str = ', '.join(str(x) for x in set(features['categories']) if x)
        project_states_str = ', '.join(str(x) for x in set(features['project_states']) if x)
        delivery_statuses_str = ', '.join(str(x) for x in set(features['delivery_statuses']) if x)
        locations_str = ', '.join(str(x) for x in set(features['locations']) if x)

        system_prompt = f"""
            You are an AI that explains why a group of {entity_label} were clustered together in the {portfolio_name} portfolio.
            Given:
            - {entity_label.capitalize()} IDs: {entity_ids_str}
            - Portfolios: {portfolios_str}
            - Technologies: {technologies_str}
            - KPIs/Key Results: {kpis_str}
            - Milestones: {milestones_str}
            - Risks: {risks_str}
            - Team Roles: {roles_str}
            - Project Types: {project_types_str}
            - SDLC Methods: {sdlc_methods_str}
            - Categories: {categories_str}
            - Project States: {project_states_str}
            - Delivery Status: {delivery_statuses_str}
            - Locations: {locations_str}

            Provide:
            1. A detailed explanation of shared characteristics across ALL dimensions (portfolios, technologies, KPIs, milestones, risks, roles, project types, SDLC methods, categories, project states, delivery status, locations).
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
        """Generate template and pattern names for project clusters."""
        print(f"DEBUG: generate_workflow_and_template_names called for cluster {cluster_idx}")
        try:
            entity_label = self._get_entity_type_label()
            entity_count_key = self._get_entity_count_key()
            
            velocity = cluster_data.get('velocity_score', 0)
            value_realization = cluster_data.get('value_realization_score', 0)
            print(f"DEBUG: velocity={velocity} ({type(velocity)}), value_realization={value_realization} ({type(value_realization)})")
            
            # Build detailed statistics for prompt
            project_count = cluster_data.get(entity_count_key, 0)
            avg_duration = cluster_data.get('avg_project_duration', 0)
            avg_kpi_count = cluster_data.get('avg_kpi_count', 0)
            avg_team_size = cluster_data.get('avg_team_size', 0)
            avg_risk_count = cluster_data.get('avg_risk_count', 0)
            
            # Extract portfolio details with percentages
            portfolio_details = []
            for p in cluster_data.get('key_portfolios', []):
                portfolio_details.append(f"{p.get('portfolio', 'Unknown')} ({p.get('count', 0)}/{project_count} projects = {p.get('percentage', 0)}%)")
            
            # Extract project type distribution
            type_details = []
            for t in cluster_data.get('project_type_distribution', []):
                type_details.append(f"{t.get('type', 'Unknown')}: {t.get('count', 0)}/{project_count} projects ({t.get('percentage', 0)}%)")
            
            # Extract SDLC method distribution
            sdlc_details = []
            for s in cluster_data.get('sdlc_method_distribution', []):
                sdlc_details.append(f"{s.get('method', 'Unknown')}: {s.get('count', 0)}/{project_count} projects ({s.get('percentage', 0)}%)")
            
            # Extract status distribution
            status_details = []
            for s in cluster_data.get('status_distribution', []):
                status_details.append(f"{s.get('status', 'Unknown')}: {s.get('count', 0)}/{project_count} projects ({s.get('percentage', 0)}%)")
            
            # Extract delivery status distribution
            delivery_details = []
            for d in cluster_data.get('delivery_status_distribution', []):
                delivery_details.append(f"{d.get('status', 'Unknown')}: {d.get('count', 0)}/{project_count} projects ({d.get('percentage', 0)}%)")
            
            # Extract team composition
            team_details = []
            for t in cluster_data.get('team_composition', []):
                team_details.append(f"{t.get('category', 'Unknown')}: {t.get('percentage', 0)}% of total team members")
            
            # Get delivery patterns (project equivalent of solution themes)
            delivery_themes = cluster_data.get('delivery_themes', [])
            delivery_approaches = cluster_data.get('delivery_approaches', [])
            delivery_criteria = cluster_data.get('delivery_success_criteria', [])
            delivery_narrative = cluster_data.get('delivery_narrative', '')
            
            # Get technologies
            technologies = [t.get('technology', 'Unknown') for t in cluster_data.get('key_technologies', []) if t]
            
            system_prompt = f"""You are an expert Enterprise Architect creating reusable project templates and patterns based on analyzed data.

═══════════════════════════════════════════════════════════════════
CLUSTER ANALYSIS SUMMARY:
═══════════════════════════════════════════════════════════════════

Portfolio: {portfolio_name}
Projects Analyzed: {project_count}
Cluster Quality Score: {silhouette_score:.3f}
Velocity Score: {velocity:.3f}
Value Realization Score: {value_realization:.3f}

Portfolio Distribution:
{chr(10).join(portfolio_details) if portfolio_details else 'No portfolio data'}

Project Type Distribution:
{chr(10).join(type_details) if type_details else 'No type data'}

SDLC Method Distribution:
{chr(10).join(sdlc_details) if sdlc_details else 'No SDLC data'}

Status Distribution:
{chr(10).join(status_details) if status_details else 'No status data'}

Delivery Status Distribution:
{chr(10).join(delivery_details) if delivery_details else 'No delivery status data'}

Team Composition:
{chr(10).join(team_details) if team_details else 'No team data'}

Average Metrics:
- Duration: {avg_duration} days
- KPIs per project: {avg_kpi_count}
- Team size: {avg_team_size} members
- Risks per project: {avg_risk_count}

═══════════════════════════════════════════════════════════════════
KEY RESULTS (KPIs) - {len(cluster_data.get('key_results', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {kpi}" for kpi in cluster_data.get('key_results', [])[:8]]) if cluster_data.get('key_results') else 'No KPIs'}

═══════════════════════════════════════════════════════════════════
MILESTONES - {len(cluster_data.get('milestones', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {milestone}" for milestone in cluster_data.get('milestones', [])[:8]]) if cluster_data.get('milestones') else 'No milestones'}

═══════════════════════════════════════════════════════════════════
RISKS - {len(cluster_data.get('constraints', []))} identified:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {risk}" for risk in cluster_data.get('constraints', [])[:8]]) if cluster_data.get('constraints') else 'No risks'}

═══════════════════════════════════════════════════════════════════
TECHNOLOGIES - {len(technologies)} identified:
═══════════════════════════════════════════════════════════════════
{', '.join(technologies[:10]) if technologies else 'No technologies'}

═══════════════════════════════════════════════════════════════════
DELIVERY THEMES:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {theme}" for theme in delivery_themes]) if delivery_themes else 'No delivery themes'}

═══════════════════════════════════════════════════════════════════
DELIVERY APPROACHES:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {approach}" for approach in delivery_approaches]) if delivery_approaches else 'No delivery approaches'}

═══════════════════════════════════════════════════════════════════
SUCCESS CRITERIA:
═══════════════════════════════════════════════════════════════════
{chr(10).join([f"• {crit}" for crit in delivery_criteria[:5]]) if delivery_criteria else 'No success criteria'}

═══════════════════════════════════════════════════════════════════
DELIVERY NARRATIVE:
═══════════════════════════════════════════════════════════════════
{delivery_narrative[:1500] if delivery_narrative else 'No narrative available'}

═══════════════════════════════════════════════════════════════════
CLUSTER EXPLANATION:
═══════════════════════════════════════════════════════════════════
{explanation_data.get('explanation', 'No explanation available')}

═══════════════════════════════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════════════════════════════

Generate a **ProjectTemplate** and **ProjectPattern** based on this rich data.

**REQUIREMENTS:**

1. Names and Titles:
   - Must be professional, industry-standard
   - Reflect the actual patterns seen in the data
   - Reference the dominant characteristics (e.g., if 3/4 projects are "Agile", name should reflect that)
   - MUST be unique{f' — the following names are already taken and MUST NOT be reused: {chr(10).join("     • " + n for n in existing_pattern_names)}' if existing_pattern_names else ''}

2. Descriptions:
   - Incorporate SPECIFIC data from the analysis above
   - Reference frequencies, percentages, and actual examples
   - Use the Delivery Narrative as foundation
   - Mention which capabilities/patterns appear in X out of Y projects
   - Include technology stacks and approaches

3. Objectives (for template):
   - Must be SPECIFIC and MEASURABLE
   - Derived from the KPIs and Success Criteria
   - Reference the value realization score and velocity metrics
   - Example: "Achieve 95% deployment success rate (based on {project_count} projects with {value_realization:.2f} realization score)"

4. Dates:
   - start_date and end_date should reflect the average project start/end dates in the cluster
   - Format: YYYY-MM-DD (e.g., "2025-01-15")
   - If most projects are in Q1 2025, use appropriate dates based on duration

5. Metadata Fields:
   - Choose values based on the MAJORITY pattern in the data
   - If 75% projects are Agile, template sdlc_method = Agile
   - If most projects are Standard type, use Standard
   - Duration should reflect average duration
   - org_strategy_align: numeric score from 0.0-1.0 based on strategic alignment
   - total_external_spend: numeric value in currency (e.g., 250000.0) derived from budget data

5. Pattern Description:
   - 2-4 paragraphs minimum
   - Start with business context
   - Detail technical approaches with specificity
   - Reference delivery themes and approaches
   - Mention governance, team structure, and risks
   - Include success metrics and outcomes

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
═══════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no markdown, no explanations):

{{
    "template": {{
        "name": "Template name reflecting dominant pattern",
        "title": "Same or slight variation",
        "description": "2-3 paragraph description with specific data references (e.g., 'Based on analysis of {project_count} projects where 75% use technology X...')",
        "objectives": [
            "Specific objective with metric (from KPIs/success criteria)",
            "Another specific objective",
            "..."
        ],
        "start_date": "YYYY-MM-DD format based on average project start",
        "end_date": "YYYY-MM-DD format based on average project end",
        "project_type": "Type based on majority",
        "sdlc_method": "SDLC method based on majority",
        "state": "State based on status distribution",
        "delivery_status": "Delivery status based on distribution",
        "scope_status": "On Track/At Risk/etc",
        "spend_status": "On Budget/Over Budget/etc",
        "project_category": "Category1, Category2",
        "project_location": "Location based on data",
        "technology_stack": "Tech1, Tech2, Tech3",
        "org_strategy_align": "numeric value 0.0-1.0",
        "total_external_spend": "numeric value based on budget data",
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

        system_prompt = system_prompt
        try:
            chat_completion = ChatCompletion(system=system_prompt, prev=[], user="Generate names and metadata.")
            response = self.llm.run(chat_completion, ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1), 'analysis::generate_template')
            result = extract_json_after_llm(response)
            
            # Post-process template: fill in all required fields for ProjectTemplate schema
            if "template" not in result:
                result["template"] = {}
            
            template = result["template"]
            # Extract tenant_id from cluster_data or fallback to a default (should always be in cluster_data if properly passed)
            tenant_id_for_id = cluster_data.get("tenant_id", "unknown")
            template.setdefault("id", f"tpl_{tenant_id_for_id}_{customer_id}_{cluster_idx}_{hash(str(template)) % 10000}")
            template.setdefault("tenant_id", cluster_data.get("tenant_id", customer_id))
            template.setdefault("name", template.get("name", ""))
            template.setdefault("title", template.get("title", template.get("name", "")))
            template.setdefault("description", template.get("description", ""))
            template.setdefault("objectives", template.get("objectives", []))
            template.setdefault("start_date", "")
            template.setdefault("end_date", "")
            template.setdefault("project_type", template.get("project_type", ""))
            template.setdefault("sdlc_method", template.get("sdlc_method", ""))
            template.setdefault("state", template.get("state", ""))
            template.setdefault("project_category", template.get("project_category", ""))
            template.setdefault("delivery_status", template.get("delivery_status", ""))
            template.setdefault("scope_status", template.get("scope_status", ""))
            template.setdefault("spend_status", template.get("spend_status", ""))
            template.setdefault("project_location", template.get("project_location", ""))
            template.setdefault("technology_stack", template.get("technology_stack", ""))
            template.setdefault("tags", template.get("tags", []))
            template.setdefault("org_strategy_align", 0.0)
            template.setdefault("total_external_spend", 0.0)
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
            pattern.setdefault("name", result["pattern"].get("name", "Unnamed Pattern"))
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
            pattern.setdefault("scope", "workflow")
            pattern.setdefault("confidence_score", explanation_data.get("llm_confidence", 0.0))
            pattern.setdefault("support_score", silhouette_score)
            pattern.setdefault("key_milestones", cluster_data.get("key_milestones", []))
            pattern.setdefault("key_kpis", cluster_data.get("key_results", []))
            pattern.setdefault("key_risk_mitigations", cluster_data.get("constraints", []))
            pattern.setdefault("avg_project_duration", cluster_data.get("avg_project_duration", 0))
            pattern.setdefault("avg_milestone_velocity", cluster_data.get("velocity_score", 0.0))
            pattern["budget_band"] = cluster_data.get("budget_band", "")
            pattern.setdefault("milestone_adherence_score", cluster_data.get("milestone_adherence_score", 0.0))
            pattern.setdefault("delivery_success_score", cluster_data.get("delivery_success_score", 0.0))
            pattern.setdefault("created_at", str(datetime.now().date()))
            pattern.setdefault("explanation", explanation_data.get("explanation", ""))
            pattern.setdefault("summary_period", cluster_data.get("summary_period", f"{datetime.now().year}-Q{(datetime.now().month-1)//3 + 1}"))
            
            # Project-specific fields
            pattern["key_technologies"] = [t["technology"] for t in cluster_data.get("key_technologies", [])]
            pattern["team_composition"] = [t["category"] for t in cluster_data.get("team_composition", [])]
            pattern["dev_methodology_dist"] = [m["methodology"] for m in cluster_data.get("dev_methodology_dist", [])]
            pattern["work_type_distribution"] = [w["type"] for w in cluster_data.get("work_type_distribution", [])]
            
            entity_ids_key = self._get_entity_id_key().replace('_id', '_ids')
            pattern[entity_ids_key] = cluster_data.get(entity_ids_key, [])
            
            return result
        except Exception as e:
            print(f"LLM error in generate_workflow_and_template_names: {e}")
            return {"template": {}, "pattern": {}}
    
    def generalize_cluster(self, cluster: List[Dict], min_freq: float = 0.4) -> Dict:
        """
        Generalize cluster attributes to create schema-aligned metadata with project-by-project attribution.
        """
        if not cluster:
            return {}

        tech_counter = Counter([t["name"] for p in cluster for t in p.get("technologies", [])])
        category_counter = Counter([c["name"] for p in cluster for c in p.get("categories", [])])
        portfolio_counter = Counter([pf.get("name", "") for p in cluster for pf in p.get("portfolios", [])])
        status_counter = Counter([s.get("status", "Unknown") for p in cluster for s in p.get("statuses", []) if s])
        delivery_status_counter = Counter([p.get("delivery_status", "Unknown") for p in cluster if p.get("delivery_status")])
        
        sdlc_method_counter = Counter([
            p.get("sdlc_method", [{"name": "Unknown"}])[0].get("name", "Unknown") if p.get("sdlc_method") else "Unknown"
            for p in cluster
        ])
        project_type_counter = Counter([
            p.get("project_type", [{"name": "Unknown"}])[0].get("name", "Unknown") if p.get("project_type") else "Unknown"
            for p in cluster
        ])
        team_roles_counter = Counter([t.get("role", "Unknown") for p in cluster for t in p.get("team", [])])
        milestone_durations, project_durations, kpi_success_rates, budgets, risk_scores, team_sizes = [], [], [], [], [], []
        kpi_counts, risk_counts = [], []

        total_projects = len(cluster)
        min_count = total_projects * min_freq

        # Compute resource and team composition
        resource_distribution = Counter()
        team_composition = Counter()
        total_team_members = sum(len(p.get("team", [])) for p in cluster)
        
        for project in cluster:
            for member in project.get("team", []):
                role = member.get("role", "Unknown")
                resource_distribution[role] += 1
                team_composition[role] += 1
            
            # Gather metrics
            kpi_count = len(project.get("key_results", []))
            kpi_counts.append(kpi_count)
            
            risk_count = len(project.get("risks", []))
            risk_counts.append(risk_count)

        team_composition_dist = [
            {"category": k, "percentage": round((v / total_team_members) * 100, 2)}
            for k, v in team_composition.items()
            if total_team_members > 0
        ]

        work_type_dist = [
            {"type": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in project_type_counter.items()
        ]

        tech_weightage = [
            {"technology": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in tech_counter.items()
            if v >= min_count
        ]

        methodology_dist = [
            {"methodology": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in sdlc_method_counter.items()
        ]

        for project in cluster:
            for ms in project.get("milestones", []):
                duration = ms.get("duration_days", 0)
                if duration:
                    milestone_durations.append(duration)

            start_date = project.get("start_date")
            end_date = project.get("end_date")
            if start_date and end_date:
                try:
                    duration = (np.datetime64(end_date) - np.datetime64(start_date)).astype(int)
                    project_durations.append(duration)
                except Exception:
                    pass

            for kpi in project.get("key_results", []):
                kpi_success_rates.append(kpi.get("success_rate", 0.0))

            budget = project.get("budget", project.get("total_external_spend", 0)) or 0
            if budget:
                budgets.append(budget)

            risks = project.get("risks", [])
            if risks:
                risk_score = np.nanmean([
                    (r.get("impact", 1) if isinstance(r.get("impact", 1), (int, float)) else 1) *
                    (1 if r.get("status") in ["Active", "Escalated"] else 0.5 if r.get("status") == "Monitoring" else 0)
                    for r in risks
                ])
                risk_scores.append(risk_score)

            team_sizes.append(len(project.get("team", [])))

        avg_milestone_duration = np.nanmean(milestone_durations) if milestone_durations else 0
        velocity_score = 1 / avg_milestone_duration if avg_milestone_duration > 0 else 0
        avg_project_duration = int(np.nanmean(project_durations)) if project_durations else 0
        avg_kpi_count = round(np.nanmean(kpi_counts), 2) if kpi_counts else 0
        avg_team_size = int(np.nanmean(team_sizes)) if team_sizes else 5
        avg_risk_count = round(np.nanmean(risk_counts), 2) if risk_counts else 0
        value_realization_score = np.nanmean(kpi_success_rates) if kpi_success_rates else 0
        avg_budget = np.nanmean(budgets) if budgets else 0
        avg_risk_score = np.nanmean(risk_scores) if risk_scores else 0
        milestone_adherence_score = np.nanmean([
            1 if m.get("status") == "Completed" else 0
            for p in cluster for m in p.get("milestones", [])
        ]) if any(p.get("milestones") for p in cluster) else 0
        delivery_success_score = value_realization_score
        avg_team_duration = int(np.nanmean(team_sizes)) if team_sizes else 5

        team_structure = "matrix" if len(portfolio_counter) > 1 else "flat"
        budget_band = "50k-100k" if avg_budget < 100000 else "100k-500k" if avg_budget < 500000 else "500k+"

        # LLM for generalized KPIs, milestones, risks with PROJECT-BY-PROJECT ATTRIBUTION
        all_kpis = [str(k.get("kpi_name") or "Unknown") for p in cluster for k in p.get("key_results", []) if k]
        all_milestones = [str(m.get("milestone_name") or "Unknown") for p in cluster for m in p.get("milestones", []) if m]
        all_risks = [str(r.get("description") or "Unknown") for p in cluster for r in p.get("risks", []) if r]
        
        entity_label = self._get_entity_type_label()
        
        # Extract project objectives (text field, not structured scopes)
        all_objectives = [p.get("project_objectives", "") for p in cluster if p.get("project_objectives")]
        
        # Build detailed project-by-project breakdown with attribution
        project_details = []
        
        print(f"[DEBUG] Extracting detailed information from cluster with {total_projects} projects")
        
        for i, project in enumerate(cluster):
            project_name = project.get("name") or f"Project {project.get('project_id', i)}"
            project_id = project.get("project_id", i)
            
            # Extract all relevant fields with attribution
            project_kpis = [k.get("kpi_name") for k in project.get("key_results", []) if k and k.get("kpi_name")]
            project_milestones = [m.get("milestone_name") for m in project.get("milestones", []) if m and m.get("milestone_name")]
            project_risks = [r.get("description") for r in project.get("risks", []) if r and r.get("description")]
            project_portfolios = [p.get("name") for p in project.get("portfolios", []) if p and p.get("name")]
            project_categories = [c.get("name") for c in project.get("categories", []) if c and c.get("name")]
            project_types = [t.get("name") for t in project.get("project_types", []) if t and t.get("name")]
            project_techs = [t.get("name") for t in project.get("technologies", []) if t and t.get("name")]
            project_sdlc = [s.get("name") for s in project.get("sdlc_methods", []) if s and s.get("name")]
            
            status = project.get("statuses", [{}])[0].get("status", "Unknown") if project.get("statuses") else "Unknown"
            delivery_status = project.get("delivery_status", "Unknown")
            
            objectives = project.get("project_objectives") or ""
            
            # Build detailed project entry
            detail_parts = [f"## Project: '{project_name}' (ID: {project_id})"]
            
            if objectives:
                detail_parts.append(f"   Objectives: {objectives[:300]}")
            
            if project_kpis:
                detail_parts.append(f"   KPIs ({len(project_kpis)}): {', '.join(project_kpis[:5])}")
            
            if project_milestones:
                detail_parts.append(f"   Milestones ({len(project_milestones)}): {', '.join(project_milestones[:5])}")
            
            if project_risks:
                detail_parts.append(f"   Risks ({len(project_risks)}): {', '.join(project_risks[:5])}")
            
            if project_portfolios:
                detail_parts.append(f"   Portfolios: {', '.join(project_portfolios)}")
            
            if project_categories:
                detail_parts.append(f"   Categories: {', '.join(project_categories)}")
            
            if project_types:
                detail_parts.append(f"   Types: {', '.join(project_types)}")
            
            if project_sdlc:
                detail_parts.append(f"   SDLC Methods: {', '.join(project_sdlc)}")
            
            if project_techs:
                detail_parts.append(f"   Technologies ({len(project_techs)}): {', '.join(project_techs[:5])}")
            
            detail_parts.append(f"   Status: {status} | Delivery: {delivery_status}")
            
            project_details.append("\n".join(detail_parts))

        print(f"[DEBUG] Collected detailed information from {total_projects} projects")
        
        # Build comprehensive context with project details
        detailed_projects_context = "\n\n".join(project_details)
        
        # Build frequency analysis for prompt
        kpi_freq = Counter(all_kpis)
        milestone_freq = Counter(all_milestones)
        risk_freq = Counter(all_risks)
        
        kpi_analysis = []
        for kpi, count in kpi_freq.most_common(10):
            pct = round((count / total_projects) * 100, 1)
            kpi_analysis.append(f"{kpi} ({count}/{total_projects} projects = {pct}%)")
        
        milestone_analysis = []
        for milestone, count in milestone_freq.most_common(10):
            pct = round((count / total_projects) * 100, 1)
            milestone_analysis.append(f"{milestone} ({count}/{total_projects} projects = {pct}%)")
        
        risk_analysis = []
        for risk, count in risk_freq.most_common(10):
            pct = round((count / total_projects) * 100, 1)
            risk_analysis.append(f"{risk} ({count}/{total_projects} projects = {pct}%)")
        
        system_prompt = f"""You are an expert Delivery Manager and Business Analyst specializing in enterprise project pattern recognition.

Your task is to analyze {total_projects} projects and synthesize their patterns into actionable, reusable templates.

═══════════════════════════════════════════════════════════════════
DETAILED PROJECT BREAKDOWN (With Attribution):
═══════════════════════════════════════════════════════════════════

{detailed_projects_context}

═══════════════════════════════════════════════════════════════════
FREQUENCY ANALYSIS:
═══════════════════════════════════════════════════════════════════

KPIs Across Projects:
{chr(10).join(kpi_analysis) if kpi_analysis else 'No KPIs found'}

Milestones Across Projects:
{chr(10).join(milestone_analysis) if milestone_analysis else 'No milestones found'}

Risks Across Projects:
{chr(10).join(risk_analysis) if risk_analysis else 'No risks found'}

Portfolio Distribution: {', '.join([f"{k} ({v} projects)" for k, v in portfolio_counter.most_common(5)])}
Project Type Distribution: {', '.join([f"{k} ({v} projects)" for k, v in project_type_counter.most_common()])}
SDLC Method Distribution: {', '.join([f"{k} ({v} projects)" for k, v in sdlc_method_counter.most_common()])}
Status Distribution: {', '.join([f"{k} ({v} projects)" for k, v in status_counter.most_common()])}
Delivery Status Distribution: {', '.join([f"{k} ({v} projects)" for k, v in delivery_status_counter.most_common()])}

═══════════════════════════════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════════════════════════════

Synthesize this information into generalized patterns. BE SPECIFIC and reference projects by name.

1. **Generalized KPIs** (3-5):
   - Create generalized KPI categories that represent the patterns you see
   - Example: "Customer Satisfaction Score (seen in 3/4 projects: Project A, B, C)"
   - Focus on KPIs that appear in at least {min_count} projects or represent key patterns

2. **Generalized Milestones** (3-5):
   - Identify milestone themes that span multiple projects
   - Example: "MVP Release (Project X releases Q2, Project Y releases Q3)"
   - Group similar milestones into broader categories

3. **Generalized Risks** (3-5):
   - Extract common risk patterns
   - Example: "Resource Availability Constraints (mentioned in Project A, B, D)"
   - Include specific examples from projects

4. **Team Structure Patterns** (3-5 categories):
   - Identify common team composition patterns
   - Reference which projects use which team structures

5. **Technology Stacks** (5-7):
   - List technologies with project attribution
   - Example: "React.js (used by Project A, C, D)"

6. **Delivery Themes** (3-5) - CRITICAL:
   - Major delivery or architectural themes with SPECIFIC project references
   - Example: "Cloud-Native Microservices Architecture (implemented in Project A with AWS, Project C with Azure)"
   - Example: "Data Migration & Integration (Project B migrates from Oracle, Project D from SQL Server)"
   - BE DETAILED about technologies, approaches, and which projects use them

7. **Delivery Approaches** (3-5) - CRITICAL:
   - Specific implementation strategies with project attribution
   - Example: "Phased Rollout Approach: Project A does regional pilots first; Project C uses feature flags for gradual release"
   - Include technical details and project names

8. **Delivery Success Criteria** (3-5):
   - Measurable outcomes that multiple projects target
   - Reference which projects define which success criteria

9. **Delivery Narrative** (2-4 paragraphs) - CRITICAL:
   Write a comprehensive synthesis that:
   - Opens with the common business problem these projects address
   - Details specific delivery patterns with project attribution (e.g., "Project X and Project Y both implement...")
   - Describes technology choices, integration approaches, and delivery methodologies used across projects
   - References specific technologies and their usage patterns
   - Explains delivery phases and expected outcomes
   - Concludes with success patterns and lessons learned
   
   Be RICH and DESCRIPTIVE. Include project names throughout.

10. **Inferred Technologies** (5-7):
    - List technologies/tools already extracted with project attribution

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
═══════════════════════════════════════════════════════════════════

Return ONLY valid JSON (no markdown, no explanations):

{{
    "kpis": ["KPI name with context", ...],
    "milestones": ["Milestone theme with details", ...],
    "constraints": ["Risk pattern with examples", ...],
    "team_names": ["Team category", ...],
    "technologies": ["Technology (Project A, B)", ...],
    "delivery_themes": ["Delivery theme with project references", ...],
    "delivery_approaches": ["Implementation strategy with specific project examples", ...],
    "delivery_success_criteria": ["Measurable outcome with project attribution", ...],
    "delivery_narrative": "Multi-paragraph synthesis with specific project references throughout..."
}}"""
        
        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generalize and give template fields for kpis, milestones, risks, delivery patterns, and other fields that you feel you have the ability to enter"
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::generalize_cluster'
            )
            
            # LOG: LLM raw response
            appLogger.info({"event": "GENERALIZE_LLM_RAW_RESPONSE", "stage": "PATTERN", "response_length": len(response), "response_preview": response[:150] if response else ""})
            
            llm_result = extract_json_after_llm(response)
            print(llm_result)
            
            # LOG: LLM parsed output
            appLogger.info({"event": "GENERALIZE_LLM_OUTPUT", "stage": "PATTERN", "parsed_successfully": True, "llm_kpis": llm_result.get("kpis", []), "llm_kpi_count": len(llm_result.get("kpis", [])), "llm_milestones": llm_result.get("milestones", []), "llm_milestone_count": len(llm_result.get("milestones", [])), "llm_constraints": llm_result.get("constraints", []), "llm_constraint_count": len(llm_result.get("constraints", [])), "llm_delivery_themes": llm_result.get("delivery_themes", []), "llm_delivery_approaches": llm_result.get("delivery_approaches", []), "llm_delivery_narrative": llm_result.get("delivery_narrative", "")[:200]})
        except Exception as e:
            print(f"LLM error in generalize_cluster: {e}")
            appLogger.info({"event": "GENERALIZE_LLM_ERROR", "stage": "PATTERN", "error_message": str(e), "error_type": type(e).__name__})
            llm_result = {"kpis": [], "milestones": [], "constraints": [], "delivery_themes": [], "delivery_approaches": [], "delivery_success_criteria": [], "delivery_narrative": ""}

        milestone_durations, project_durations, kpi_success_rates, budgets, risk_scores, team_sizes = [], [], [], [], [], []

        total_projects = len(cluster)
        min_count = total_projects * min_freq

        # Compute resource and team composition
        resource_distribution = Counter()
        team_composition = Counter()
        total_team_members = sum(len(p.get("team", [])) for p in cluster)
        
        for project in cluster:
            for member in project.get("team", []):
                role = member.get("role", "Unknown")
                resource_distribution[role] += 1
                team_composition[role] += 1

        team_composition_dist = [
            {"category": k, "percentage": round((v / total_team_members) * 100, 2)}
            for k, v in team_composition.items()
            if total_team_members > 0
        ]

        work_type_dist = [
            {"type": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in project_type_counter.items()
        ]

        tech_weightage = [
            {"technology": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in tech_counter.items()
            if v >= min_count
        ]

        methodology_dist = [
            {"methodology": k, "count": v, "percentage": round((v / total_projects) * 100, 2)}
            for k, v in sdlc_method_counter.items()
        ]

        for project in cluster:
            for ms in project.get("milestones", []):
                duration = ms.get("duration_days", 0)
                if duration:
                    milestone_durations.append(duration)

            start_date = project.get("start_date")
            end_date = project.get("end_date")
            if start_date and end_date:
                try:
                    duration = (np.datetime64(end_date) - np.datetime64(start_date)).astype(int)
                    project_durations.append(duration)
                except Exception:
                    pass

            for kpi in project.get("key_results", []):
                kpi_success_rates.append(kpi.get("success_rate", 0.0))

            budget = project.get("budget", project.get("total_external_spend", 0)) or 0
            if budget:
                budgets.append(budget)

            risks = project.get("risks", [])
            if risks:
                risk_score = np.nanmean([
                    (r.get("impact", 1) if isinstance(r.get("impact", 1), (int, float)) else 1) *
                    (1 if r.get("status") in ["Active", "Escalated"] else 0.5 if r.get("status") == "Monitoring" else 0)
                    for r in risks
                ])
                risk_scores.append(risk_score)

            team_sizes.append(len(project.get("team", [])))

        avg_milestone_duration = np.nanmean(milestone_durations) if milestone_durations else 0
        velocity_score = 1 / avg_milestone_duration if avg_milestone_duration > 0 else 0
        avg_project_duration = int(np.nanmean(project_durations)) if project_durations else 0
        value_realization_score = np.nanmean(kpi_success_rates) if kpi_success_rates else 0
        avg_budget = np.nanmean(budgets) if budgets else 0
        avg_risk_score = np.nanmean(risk_scores) if risk_scores else 0
        milestone_adherence_score = np.nanmean([
            1 if m.get("status") == "Completed" else 0
            for p in cluster for m in p.get("milestones", [])
        ]) if any(p.get("milestones") for p in cluster) else 0
        delivery_success_score = value_realization_score
        avg_team_duration = int(np.nanmean(team_sizes)) if team_sizes else 5

        team_structure = "matrix" if len(portfolio_counter) > 1 else "flat"
        budget_band = "50k-100k" if avg_budget < 100000 else "100k-500k" if avg_budget < 500000 else "500k+"

        # LLM for generalized KPIs, milestones, constraints
        all_kpis = [str(k.get("kpi_name") or "Unknown") for p in cluster for k in p.get("key_results", []) if k]
        all_milestones = [str(m.get("milestone_name") or "Unknown") for p in cluster for m in p.get("milestones", []) if m]
        all_risks = [str(r.get("description") or "Unknown") for p in cluster for r in p.get("risks", []) if r]
        
        entity_label = self._get_entity_type_label()
        
        # Filter out None values and convert to strings for joining
        kpis_str = ', '.join(str(x) for x in set(all_kpis) if x)
        milestones_str = ', '.join(str(x) for x in set(all_milestones) if x)
        portfolios_str = ', '.join(str(x) for x in set(portfolio_counter.keys()) if x)
        team_roles_str = ', '.join(str(x) for x in set(team_roles_counter.keys()) if x)
        risks_str = ', '.join(str(x) for x in set(all_risks) if x)
        
        system_prompt = f"""
            Generalize KPIs, milestones, and constraints for business {entity_label}.
            Given:
            - KPIs: {kpis_str}
            - Milestones: {milestones_str}
            - Portfolios: {portfolios_str}
            - {entity_label.capitalize()}: {total_projects}
            - Team Roles: {team_roles_str}
            - Risks: {risks_str}
            
            Suggest:
            - 2-3 generalized KPI names.
            - 2-3 generalized milestone names.
            - 2-3 generalized constraint themes.
            Return as JSON: 
            ```json
            {{ "kpis": [], "milestones": [], "constraints": [] }}
            ```
        """
        
        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generalize KPIs, milestones, and constraints."
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::generalize_cluster'
            )
            
            # LOG: LLM raw response
            appLogger.info({"event": "GENERALIZE_LLM_RAW_RESPONSE", "stage": "PATTERN", "response_length": len(response), "response_preview": response[:150] if response else ""})
            
            llm_result = extract_json_after_llm(response)
            
            # LOG: LLM parsed output
            appLogger.info({"event": "GENERALIZE_LLM_OUTPUT", "stage": "PATTERN", "parsed_successfully": True, "llm_kpis": llm_result.get("kpis", []), "llm_kpi_count": len(llm_result.get("kpis", [])), "llm_milestones": llm_result.get("milestones", []), "llm_milestone_count": len(llm_result.get("milestones", [])), "llm_constraints": llm_result.get("constraints", []), "llm_constraint_count": len(llm_result.get("constraints", []))})
        except Exception as e:
            print(f"LLM error in generalize_cluster: {e}")
            appLogger.info({"event": "GENERALIZE_LLM_ERROR", "stage": "PATTERN", "error_message": str(e), "error_type": type(e).__name__})
            llm_result = {"kpis": [], "milestones": [], "constraints": []}

        end_dates = [np.datetime64(p.get("end_date")) for p in cluster if p.get("end_date")]
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

        entity_id_key = self._get_entity_id_key()
        entity_count_key = self._get_entity_count_key()
        entity_ids_key = entity_id_key.replace('_id', '_ids')  # e.g., project_id -> project_ids
        
        # Extract tenant_id from first entity in cluster (should be same for all entities)
        tenant_id = cluster[0].get("tenant_id") if cluster else None
        
        return {
            "tenant_id": tenant_id,  # CRITICAL: Must propagate tenant_id for downstream pattern generation
            "technologies": [k for k, v in tech_counter.items() if v >= min_count],
            "key_results": llm_result.get("kpis", []),
            "milestones": llm_result.get("milestones", []),
            "categories": [k for k, v in category_counter.items() if v >= min_count],
            "portfolios": [k for k, v in portfolio_counter.items() if v >= min_count],
            entity_count_key: total_projects,
            entity_ids_key: [p.get(entity_id_key) for p in cluster],
            "velocity_score": velocity_score,
            "avg_milestone_duration": avg_milestone_duration,
            "avg_project_duration": avg_project_duration,
            "avg_kpi_count": avg_kpi_count,
            "avg_team_size": avg_team_size,
            "avg_risk_count": avg_risk_count,
            "team_structure": team_structure,
            "dev_methodology_dist": methodology_dist,
            "work_type_distribution": work_type_dist,
            "project_type_distribution": work_type_dist,  # alias for compatibility
            "sdlc_method_distribution": methodology_dist,  # alias for compatibility
            "status_distribution": [{"status": k, "count": v, "percentage": round((v/total_projects)*100, 2)} for k, v in status_counter.items()],
            "delivery_status_distribution": [{"status": k, "count": v, "percentage": round((v/total_projects)*100, 2)} for k, v in delivery_status_counter.items()],
            "budget_band": budget_band,
            "value_realization_score": value_realization_score,
            "milestone_adherence_score": milestone_adherence_score,
            "delivery_success_score": delivery_success_score,
            "avg_team_duration": avg_team_duration,
            "team_composition": team_composition_dist,
            "key_technologies": tech_weightage,
            "key_portfolios": [{"portfolio": k, "count": v, "percentage": round((v/total_projects)*100, 2)} for k, v in portfolio_counter.most_common(5)],
            "resource_distribution": dict(resource_distribution),
            "constraints": llm_result.get("constraints", []),
            # New delivery-specific fields (project equivalent of roadmap solution fields)
            "delivery_themes": llm_result.get("delivery_themes", []),
            "delivery_approaches": llm_result.get("delivery_approaches", []),
            "delivery_success_criteria": llm_result.get("delivery_success_criteria", []),
            "delivery_narrative": llm_result.get("delivery_narrative", ""),
            "summary_period": summary_period,
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
        """Generate portfolio-level Pattern node (scope=portfolio).
        
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
        vertices = defaultdict(list)
        edges = defaultdict(list)

        portfolio_pattern_id = f"pattern_{tenant_id}_{customer_id}_{portfolio_id}_portfolio"

        # Calculate aggregates with safe empty list handling
        duration_values = [
            safe_float(c["generalized"]["avg_project_duration"])
            for c in clusters if c["generalized"].get("avg_project_duration") is not None
        ]
        duration_values = [v for v in duration_values if not np.isnan(v)]
        avg_project_duration = np.nanmean(duration_values) if duration_values else 0.0
        
        velocity_values = [
            safe_float(c["generalized"]["velocity_score"])
            for c in clusters if c["generalized"].get("velocity_score") is not None
        ]
        velocity_values = [v for v in velocity_values if not np.isnan(v)]
        avg_milestone_velocity = np.nanmean(velocity_values) if velocity_values else 0.0
        
        adherence_values = [
            safe_float(c["generalized"]["milestone_adherence_score"])
            for c in clusters if c["generalized"].get("milestone_adherence_score") is not None
        ]
        adherence_values = [v for v in adherence_values if not np.isnan(v)]
        milestone_adherence_score = np.nanmean(adherence_values) if adherence_values else 0.0
        
        success_values = [
            safe_float(c["generalized"]["delivery_success_score"])
            for c in clusters if c["generalized"].get("delivery_success_score") is not None
        ]
        success_values = [v for v in success_values if not np.isnan(v)]
        delivery_success_score = np.nanmean(success_values) if success_values else 0.0
        
        confidence_values = [c["explanation"]["llm_confidence"] for c in clusters if c["explanation"].get("llm_confidence")]
        confidence_score = np.nanmean(confidence_values) if confidence_values else 0.0
        
        support_values = [c["silhouette_score"] for c in clusters if c.get("silhouette_score") is not None]
        support_score = np.nanmean(support_values) if support_values else 0.0

        # Aggregate categorical attributes (with safe .get() for entity-agnostic support)
        all_technologies = [t for c in clusters for t in c["generalized"].get("key_technologies", [])]
        all_portfolios = [p for c in clusters for p in c["generalized"].get("key_portfolios", [])]
        all_team_compositions = [t for c in clusters for t in c["generalized"].get("team_composition", [])]
        all_work_types = [w for c in clusters for w in c["generalized"].get("work_type_distribution", [])]
        all_methodologies = [m for c in clusters for m in c["generalized"].get("dev_methodology_dist", [])]
        all_priority_dists = [p for c in clusters for p in c["generalized"].get("priority_distribution", [])]
        all_status_dists = [s for c in clusters for s in c["generalized"].get("status_distribution", [])]
        all_risk_mitigations = [r for c in clusters for r in c["names"]["pattern"].get("risk_mitigations", [])]
        all_milestones = [m for c in clusters for m in c["names"]["pattern"].get("key_milestones", [])]
        all_scopes = [s for c in clusters for s in c["names"]["pattern"].get("key_scopes", [])]
        all_kpis = [k for c in clusters for k in c["names"]["pattern"].get("key_kpis", [])]
        all_constraints = [c for c in clusters for c in c["generalized"].get("constraints", [])]
        
        # Extract entity IDs dynamically based on entity type
        entity_ids_key = self._get_entity_id_key().replace('_id', '_ids')  # e.g., project_id -> project_ids
        all_entity_ids = [str(eid) for c in clusters for eid in c["generalized"].get(entity_ids_key, [])]

        # Technology/Portfolio weightage (projects use technologies, roadmaps use portfolios)
        if all_technologies:
            tech_counts = Counter(t.get("technology") for t in all_technologies if t.get("technology"))
            total_tech = sum(t.get("count", 1) for t in all_technologies)
            key_technologies = [
                {"technology": k, "count": v, "percentage": round((v / total_tech) * 100, 2) if total_tech > 0 else 0}
                for k, v in tech_counts.items() if v >= len(clusters) * 0.5
            ]
        else:
            key_technologies = []
        
        if all_portfolios:
            portfolio_counts = Counter(p.get("portfolio") for p in all_portfolios if p.get("portfolio"))
            total_portfolio = sum(p.get("count", 1) for p in all_portfolios)
            key_portfolios = [
                {"portfolio": k, "count": v, "percentage": round((v / total_portfolio) * 100, 2) if total_portfolio > 0 else 0}
                for k, v in portfolio_counts.items() if v >= len(clusters) * 0.5
            ]
        else:
            key_portfolios = []

        team_counts = Counter(t.get("category") for t in all_team_compositions if t.get("category"))
        team_composition = [k for k, v in team_counts.items() if v >= len(clusters) * 0.5]

        work_type_counts = Counter(w.get("type") for w in all_work_types if w.get("type"))
        work_type_distribution = [k for k, v in work_type_counts.items() if v >= len(clusters) * 0.5]

        methodology_counts = Counter(m.get("methodology") for m in all_methodologies if m.get("methodology"))
        dev_methodology_dist = [k for k, v in methodology_counts.items() if v >= len(clusters) * 0.5]
        
        priority_counts = Counter(p.get("priority") for p in all_priority_dists if p.get("priority"))
        priority_distribution = [k for k, v in priority_counts.items() if v >= len(clusters) * 0.5]
        
        status_counts = Counter(s.get("status") for s in all_status_dists if s.get("status"))
        status_distribution = [k for k, v in status_counts.items() if v >= len(clusters) * 0.5]

        constraint_counter = Counter(all_constraints)
        constraints = [k for k, v in constraint_counter.most_common(3)]

        key_risk_mitigations = [k for k, v in Counter(all_risk_mitigations).most_common(3)]
        key_milestones = [k for k, v in Counter(all_milestones).most_common(3)]
        key_scopes = [k for k, v in Counter(all_scopes).most_common(3)]
        key_kpis = [k for k, v in Counter(all_kpis).most_common(3)]

        budgets = [c["generalized"].get("budget_band") for c in clusters if c["generalized"].get("budget_band")]
        budget_band = Counter(budgets).most_common(1)[0][0] if budgets else "50k-100k"

        summary_periods = [c["generalized"].get("summary_period") for c in clusters]
        summary_period = Counter(summary_periods).most_common(1)[0][0] if summary_periods else \
                        f"{datetime.now().year}-Q{(datetime.now().month-1)//3 + 1}"

        # Build entity-agnostic context
        context_parts = []
        if all_technologies:
            context_parts.append(f"- Technologies: {', '.join(set(t.get('technology', '') for t in all_technologies if t.get('technology')))}")
        if all_portfolios:
            context_parts.append(f"- Portfolios: {', '.join(set(p.get('portfolio', '') for p in all_portfolios if p.get('portfolio')))}")
        if all_kpis:
            context_parts.append(f"- KPIs: {', '.join(set(all_kpis))}")
        if all_milestones:
            context_parts.append(f"- Milestones: {', '.join(set(all_milestones))}")
        if all_scopes:
            context_parts.append(f"- Scopes: {', '.join(set(all_scopes))}")
        if all_risk_mitigations:
            context_parts.append(f"- Risk Mitigations: {', '.join(set(all_risk_mitigations))}")
        if all_team_compositions:
            context_parts.append(f"- Team Composition: {', '.join(set(t.get('category', '') for t in all_team_compositions if t.get('category')))}")
        if all_methodologies:
            context_parts.append(f"- Methodologies: {', '.join(set(m.get('methodology', '') for m in all_methodologies if m.get('methodology')))}")
        if priority_distribution:
            context_parts.append(f"- Priorities: {', '.join(priority_distribution)}")
        if status_distribution:
            context_parts.append(f"- Statuses: {', '.join(status_distribution)}")
        if all_constraints:
            context_parts.append(f"- Constraints: {', '.join(set(all_constraints))}")
        
        context_str = '\n            '.join(context_parts)
        
        system_prompt = f"""
            Generate a name, description, category, and explanation for a portfolio-level pattern in the {portfolio_name} portfolio.
            Given:
            {context_str}
            - Clusters: {len(clusters)}
            Provide:
            - Name for the pattern (e.g., "Retail Fulfillment Optimization").
            - Description summarizing the pattern.
            - Category (e.g., "fulfillment_optimization").
            - Detailed explanation of common execution traits.
            Return as JSON: 
            ```json
            {{ "name": "<text>", "description": "<text>", "category": "<text>", "explanation": "<text>" }}
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
        except Exception as e:
            print(f"LLM error in generate_portfolio_pattern: {e}")
            name = "Portfolio Pattern"
            description = "Failed to generate description."
            category = portfolio_name.lower().replace(" ", "_")
            explanation = "Failed to generate explanation."

        vertices["ProjectPattern"].append((
            portfolio_pattern_id,
            {
                "id": portfolio_pattern_id,
                "tenant_id": tenant_id,
                "scope": "portfolio",
                "category": category,
                "name": name,
                "description": description,
                "explanation": explanation,
                "confidence_score": round(confidence_score, 3),
                "support_score": round(support_score, 3),
                "created_at": str(date.today()),
                "summary_period": summary_period,
                "avg_project_duration": int(avg_project_duration) if not np.isnan(avg_project_duration) else 0,
                "avg_milestone_velocity": round(avg_milestone_velocity, 3) if not np.isnan(avg_milestone_velocity) else 0.0,
                "budget_band": budget_band,
                "key_technologies": [t["technology"] for t in key_technologies],
                "team_composition": team_composition,
                "dev_methodology_dist": dev_methodology_dist,
                "work_type_distribution": work_type_distribution,
                "milestone_adherence_score": round(milestone_adherence_score, 3) if not np.isnan(milestone_adherence_score) else 0.0,
                "delivery_success_score": round(delivery_success_score, 3) if not np.isnan(delivery_success_score) else 0.0,
                "key_risk_mitigations": key_risk_mitigations,
                "key_milestones": key_milestones,
                "key_kpis": key_kpis,
                "project_ids": list(set(all_entity_ids)),
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
        """Generate customer-level Pattern node (scope=customer).
        
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
        print(f"[DEBUG] Clusters received: {len(clusters)} clusters")
        vertices = defaultdict(list)
        edges = defaultdict(list)

        customer_pattern_id = f"pattern_{tenant_id}_{customer_id}_customer"

        # Extract portfolio patterns with detailed logging
        print(f"[DEBUG] Extracting portfolio patterns from {len(clusters)} clusters...")
        portfolio_patterns = []
        for idx, c in enumerate(clusters):
            print(f"[DEBUG] Cluster {idx}: type={type(c)}, keys={list(c.keys()) if isinstance(c, dict) else 'NOT_A_DICT'}")
            if not isinstance(c, dict):
                print(f"[WARNING] Cluster {idx} is not a dict, skipping: {c}")
                continue
            
            vertices_data = c.get("vertices", {})
            print(f"[DEBUG] Cluster {idx} vertices type: {type(vertices_data)}, keys: {list(vertices_data.keys()) if isinstance(vertices_data, dict) else 'NOT_A_DICT'}")
            
            pattern_vertex_type = self._get_pattern_vertex_type()
            print(f"[DEBUG] Looking for pattern vertex type: {pattern_vertex_type}")
            
            patterns_in_cluster = vertices_data.get(pattern_vertex_type, []) if isinstance(vertices_data, dict) else []
            print(f"[DEBUG] Cluster {idx} has {len(patterns_in_cluster)} patterns of type {pattern_vertex_type}")
            
            for p_idx, p in enumerate(patterns_in_cluster):
                print(f"[DEBUG] Cluster {idx}, Pattern {p_idx}: type={type(p)}, is_tuple={isinstance(p, tuple)}, len={len(p) if isinstance(p, (tuple, list)) else 'N/A'}")
                if isinstance(p, tuple) and len(p) >= 2:
                    print(f"[DEBUG] Cluster {idx}, Pattern {p_idx}[1]: type={type(p[1])}, is_dict={isinstance(p[1], dict)}")
                    if isinstance(p[1], dict):
                        scope = p[1].get("scope", "NO_SCOPE")
                        print(f"[DEBUG] Cluster {idx}, Pattern {p_idx} scope: {scope}")
                        if scope == "portfolio":
                            portfolio_patterns.append(p)
                    else:
                        print(f"[WARNING] Cluster {idx}, Pattern {p_idx}[1] is not a dict: {p[1]}")
                else:
                    print(f"[WARNING] Cluster {idx}, Pattern {p_idx} invalid structure: {p}")
        
        print(f"[DEBUG] Total portfolio patterns extracted: {len(portfolio_patterns)}")
        portfolio_pattern_data = [p[1] for p in portfolio_patterns if isinstance(p, tuple) and len(p) >= 2 and isinstance(p[1], dict)]
        print(f"[DEBUG] Valid portfolio pattern data: {len(portfolio_pattern_data)} items")
        
        # Extract entity IDs dynamically
        entity_ids_key = self._get_entity_id_key().replace('_id', '_ids')
        all_entity_ids = [
            str(eid) for c in clusters
            for eid in c.get("generalized", {}).get(entity_ids_key, [])
        ]

        # Safely compute averages, handling empty lists
        durations = [p["avg_project_duration"] for p in portfolio_pattern_data if p.get("avg_project_duration")]
        avg_project_duration = np.nanmean(durations) if durations else 0.0
        
        velocities = [p["avg_milestone_velocity"] for p in portfolio_pattern_data if p.get("avg_milestone_velocity")]
        avg_milestone_velocity = np.nanmean(velocities) if velocities else 0.0
        
        adherences = [p["milestone_adherence_score"] for p in portfolio_pattern_data if p.get("milestone_adherence_score")]
        milestone_adherence_score = np.nanmean(adherences) if adherences else 0.0
        
        successes = [p["delivery_success_score"] for p in portfolio_pattern_data if p.get("delivery_success_score")]
        delivery_success_score = np.nanmean(successes) if successes else 0.0
        confidence_score = np.nanmean([p["confidence_score"] for p in portfolio_pattern_data]) if portfolio_pattern_data else 0.0
        support_score = np.nanmean([p["support_score"] for p in portfolio_pattern_data]) if portfolio_pattern_data else 0.0

        # Extract all entity-specific and shared fields with safe access
        print(f"[DEBUG] Extracting fields from {len(portfolio_pattern_data)} portfolio patterns...")
        try:
            all_technologies = [t for p in portfolio_pattern_data for t in p.get("key_technologies", [])]
            print(f"[DEBUG] Extracted {len(all_technologies)} technologies, sample: {all_technologies[:2] if all_technologies else 'EMPTY'}")
        except Exception as e:
            print(f"[ERROR] Failed to extract technologies: {e}")
            all_technologies = []
        
        try:
            all_portfolios = [port for p in portfolio_pattern_data for port in p.get("key_portfolios", [])]
            print(f"[DEBUG] Extracted {len(all_portfolios)} portfolios, sample: {all_portfolios[:2] if all_portfolios else 'EMPTY'}")
        except Exception as e:
            print(f"[ERROR] Failed to extract portfolios: {e}")
            all_portfolios = []
        
        print(f"[DEBUG] Extracting remaining fields...")
        try:
            all_team_compositions = [t for p in portfolio_pattern_data for t in p.get("team_composition", [])]
            print(f"[DEBUG] Team compositions: {len(all_team_compositions)}")
        except Exception as e:
            print(f"[ERROR] team_composition: {e}")
            all_team_compositions = []
        
        try:
            all_work_types = [w for p in portfolio_pattern_data for w in p.get("work_type_distribution", [])]
            print(f"[DEBUG] Work types: {len(all_work_types)}")
        except Exception as e:
            print(f"[ERROR] work_type_distribution: {e}")
            all_work_types = []
        
        all_methodologies = [m for p in portfolio_pattern_data for m in p.get("dev_methodology_dist", [])]
        all_priority_dists = [pr for p in portfolio_pattern_data for pr in p.get("priority_distribution", [])]
        all_status_dists = [st for p in portfolio_pattern_data for st in p.get("status_distribution", [])]
        all_risk_mitigations = [r for p in portfolio_pattern_data for r in p.get("key_risk_mitigations", [])]
        all_milestones = [m for p in portfolio_pattern_data for m in p.get("key_milestones", [])]
        all_scopes = [s for p in portfolio_pattern_data for s in p.get("key_scopes", [])]
        all_kpis = [k for p in portfolio_pattern_data for k in p.get("key_kpis", [])]
        all_constraints = [c for p in portfolio_pattern_data for c in p.get("constraints", [])]
        print(f"[DEBUG] Extracted basic fields successfully")
        
        # Extract delivery-specific fields (project equivalent of roadmap solution fields)
        print(f"[DEBUG] Extracting delivery fields...")
        all_delivery_themes = [t for p in portfolio_pattern_data for t in p.get("delivery_themes", [])]
        all_delivery_approaches = [a for p in portfolio_pattern_data for a in p.get("delivery_approaches", [])]
        all_delivery_success_criteria = [c for p in portfolio_pattern_data for c in p.get("delivery_success_criteria", [])]
        all_delivery_narratives = [n for p in portfolio_pattern_data if (n := p.get("delivery_narrative", ""))]
        print(f"[DEBUG] Delivery fields extracted: themes={len(all_delivery_themes)}, approaches={len(all_delivery_approaches)}, criteria={len(all_delivery_success_criteria)}")
        
        # Process project-specific fields if present
        print(f"[DEBUG] Processing technologies...")
        key_technologies = []
        if all_technologies:
            try:
                print(f"[DEBUG] Tech items sample (first 3): {all_technologies[:3]}")
                tech_counts = Counter(t for t in all_technologies)
                print(f"[DEBUG] Tech counts created: {len(tech_counts)} unique items")
                total_tech = len(all_technologies)
                key_technologies = [
                    {"technology": k, "count": v, "percentage": round((v / total_tech) * 100, 2)}
                    for k, v in tech_counts.items() if v >= len(portfolio_pattern_data) * 0.5
                ]
                print(f"[DEBUG] Key technologies processed: {len(key_technologies)}")
            except Exception as e:
                print(f"[ERROR] Processing technologies: {e}")
                import traceback
                traceback.print_exc()

        # Process roadmap-specific fields if present
        print(f"[DEBUG] Processing portfolios...")
        key_portfolios = []
        if all_portfolios:
            try:
                print(f"[DEBUG] Portfolio items sample (first 3): {all_portfolios[:3]}")
                portfolio_counts = Counter(p.get("portfolio") if isinstance(p, dict) else p for p in all_portfolios if p)
                print(f"[DEBUG] Portfolio counts created: {len(portfolio_counts)} unique items")
                total_portfolios = len(all_portfolios)
                key_portfolios = [
                    {"portfolio": k, "count": v, "percentage": round((v / total_portfolios) * 100, 2) if total_portfolios > 0 else 0}
                    for k, v in portfolio_counts.items() if k and v >= len(portfolio_pattern_data) * 0.5
                ]
                print(f"[DEBUG] Key portfolios processed: {len(key_portfolios)}")
            except Exception as e:
                print(f"[ERROR] Processing portfolios: {e}")
                import traceback
                traceback.print_exc()

        print(f"[DEBUG] Processing team and methodology counts...")
        team_counts = Counter(t for t in all_team_compositions if t)
        team_composition = [k for k, v in team_counts.items() if v >= len(portfolio_pattern_data) * 0.5]

        work_type_counts = Counter(w for w in all_work_types if w)
        work_type_distribution = [k for k, v in work_type_counts.items() if v >= len(portfolio_pattern_data) * 0.5]

        methodology_counts = Counter(m for m in all_methodologies if m)
        dev_methodology_dist = [k for k, v in methodology_counts.items() if v >= len(portfolio_pattern_data) * 0.5]

        print(f"[DEBUG] Processing priority and status distributions...")
        priority_counts = Counter(p.get("priority") if isinstance(p, dict) else p for p in all_priority_dists if p)
        priority_distribution = [k for k, v in priority_counts.items() if k and v >= len(portfolio_pattern_data) * 0.5]

        status_counts = Counter(s.get("status") if isinstance(s, dict) else s for s in all_status_dists if s)
        status_distribution = [k for k, v in status_counts.items() if k and v >= len(portfolio_pattern_data) * 0.5]

        print(f"[DEBUG] Processing constraints and key fields...")
        constraint_counter = Counter(all_constraints)
        constraints = [k for k, v in constraint_counter.most_common(3)]

        key_risk_mitigations = [k for k, v in Counter(all_risk_mitigations).most_common(3)]
        key_milestones = [k for k, v in Counter(all_milestones).most_common(3)]
        key_scopes = [k for k, v in Counter(all_scopes).most_common(3)]
        key_kpis = [k for k, v in Counter(all_kpis).most_common(3)]
        
        # Aggregate delivery fields (project equivalent of roadmap solution fields)
        print(f"[DEBUG] Aggregating delivery fields...")
        delivery_theme_counts = Counter(all_delivery_themes)
        delivery_approach_counts = Counter(all_delivery_approaches)
        delivery_criteria_counts = Counter(all_delivery_success_criteria)
        
        key_delivery_themes = [k for k, v in delivery_theme_counts.most_common(5) if k]
        key_delivery_approaches = [k for k, v in delivery_approach_counts.most_common(5) if k]
        key_delivery_criteria = [k for k, v in delivery_criteria_counts.most_common(10) if k]
        print(f"[DEBUG] Delivery aggregation complete")

        print(f"[DEBUG] Extracting budget and summary period from clusters...")
        budgets = [c["generalized"].get("budget_band") for c in clusters if c["generalized"].get("budget_band")]
        budget_band = Counter(budgets).most_common(1)[0][0] if budgets else "50k-100k"

        summary_periods = [c["generalized"].get("summary_period") for c in clusters]
        summary_period = Counter(summary_periods).most_common(1)[0][0] if summary_periods else \
                        f"{datetime.now().year}-Q{(datetime.now().month-1)//3 + 1}"
        print(f"[DEBUG] Budget band: {budget_band}, Summary period: {summary_period}")

        # Build entity-agnostic context
        print(f"[DEBUG] Building context for LLM...")
        context_parts = []
        try:
            if all_technologies:
                print(f"[DEBUG] Building tech context from {len(all_technologies)} items...")
                tech_strings = []
                for idx, t in enumerate(all_technologies):
                    if idx < 3:  # Debug first 3
                        print(f"[DEBUG] Tech item {idx}: type={type(t)}, value={t}")
                    if isinstance(t, dict) and t.get('technology'):
                        tech_strings.append(t.get('technology'))
                    elif isinstance(t, str):
                        tech_strings.append(t)
                context_parts.append(f"- Technologies: {', '.join(set(tech_strings))}")
                print(f"[DEBUG] Tech context built with {len(tech_strings)} items")
        except Exception as e:
            print(f"[ERROR] Building tech context: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            if all_portfolios:
                print(f"[DEBUG] Building portfolio context from {len(all_portfolios)} items...")
                portfolio_strings = []
                for idx, p in enumerate(all_portfolios):
                    if idx < 3:  # Debug first 3
                        print(f"[DEBUG] Portfolio item {idx}: type={type(p)}, value={p}")
                    if isinstance(p, dict) and p.get('portfolio'):
                        portfolio_strings.append(p.get('portfolio'))
                    elif isinstance(p, str):
                        portfolio_strings.append(p)
                context_parts.append(f"- Portfolios: {', '.join(set(portfolio_strings))}")
                print(f"[DEBUG] Portfolio context built with {len(portfolio_strings)} items")
        except Exception as e:
            print(f"[ERROR] Building portfolio context: {e}")
            import traceback
            traceback.print_exc()
        
        if all_kpis:
            context_parts.append(f"- KPIs: {', '.join(set(all_kpis))}")
        if all_milestones:
            context_parts.append(f"- Milestones: {', '.join(set(all_milestones))}")
        if all_scopes:
            context_parts.append(f"- Scopes: {', '.join(set(all_scopes))}")
        if all_risk_mitigations:
            context_parts.append(f"- Risk Mitigations: {', '.join(set(all_risk_mitigations))}")
        
        try:
            if all_team_compositions:
                print(f"[DEBUG] Building team context from {len(all_team_compositions)} items...")
                team_strings = []
                for t in all_team_compositions:
                    if isinstance(t, dict) and t.get('category'):
                        team_strings.append(t.get('category'))
                    elif isinstance(t, str):
                        team_strings.append(t)
                context_parts.append(f"- Team Composition: {', '.join(set(team_strings))}")
        except Exception as e:
            print(f"[ERROR] Building team context: {e}")
        
        try:
            if all_methodologies:
                print(f"[DEBUG] Building methodology context from {len(all_methodologies)} items...")
                method_strings = []
                for m in all_methodologies:
                    if isinstance(m, dict) and m.get('methodology'):
                        method_strings.append(m.get('methodology'))
                    elif isinstance(m, str):
                        method_strings.append(m)
                context_parts.append(f"- Methodologies: {', '.join(set(method_strings))}")
        except Exception as e:
            print(f"[ERROR] Building methodology context: {e}")
        
        if priority_distribution:
            context_parts.append(f"- Priorities: {', '.join(priority_distribution)}")
        if status_distribution:
            context_parts.append(f"- Statuses: {', '.join(status_distribution)}")
        if all_constraints:
            context_parts.append(f"- Constraints: {', '.join(set(all_constraints))}")
        if key_delivery_themes:
            context_parts.append(f"- Delivery Themes: {', '.join(set(key_delivery_themes))}")
        if key_delivery_approaches:
            context_parts.append(f"- Delivery Approaches: {', '.join(set(key_delivery_approaches))}")
        if key_delivery_criteria:
            context_parts.append(f"- Delivery Success Criteria: {', '.join(set(key_delivery_criteria))}")
        
        print(f"[DEBUG] Context built with {len(context_parts)} parts")
        context_str = '\n            '.join(context_parts)
        
        system_prompt = f"""
            Generate a name, description, category, and explanation for a customer-level pattern for {customer_id}.
            Given:
            {context_str}
            Provide:
            - Name for the pattern (e.g., "Megamart Execution Strategy").
            - Description summarizing the pattern.
            - Category (e.g., "retail_execution").
            - Detailed explanation of common execution traits across portfolios.
            Return as JSON: 
            ```json
            {{ "name": "<text>", "description": "<text>", "category": "<text>", "explanation": "<text>" }}
            ```
        """
        
        try:
            chat_completion = ChatCompletion(
                system=system_prompt,
                prev=[],
                user="Generate customer pattern metadata."
            )
            response = self.llm.run(
                chat_completion,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
                'analysis::customer_pattern'
            )
            llm_result = extract_json_after_llm(response)
            name = llm_result.get("name", "Customer Pattern")
            description = llm_result.get("description", "No description generated.")
            category = llm_result.get("category", customer_id.lower())
            explanation = llm_result.get("explanation", "No explanation generated.")
        except Exception as e:
            print(f"LLM error in generate_customer_pattern: {e}")
            name = "Customer Pattern"
            description = "Failed to generate description."
            category = customer_id.lower()
            explanation = "Failed to generate explanation."

        # Build entity-agnostic pattern data
        pattern_data = {
            "id": customer_pattern_id,
            "tenant_id": tenant_id,
            "scope": "customer",
            "category": category,
            "name": name,
            "description": description,
            "explanation": explanation,
            "confidence_score": round(confidence_score, 2),
            "support_score": round(support_score, 2),
            "created_at": str(date.today()),
            "avg_project_duration": int(avg_project_duration) if not np.isnan(avg_project_duration) else 0,
            "avg_milestone_velocity": round(avg_milestone_velocity, 2) if not np.isnan(avg_milestone_velocity) else 0.0,
            "budget_band": budget_band,
            "milestone_adherence_score": round(milestone_adherence_score, 2) if not np.isnan(milestone_adherence_score) else 0.0,
            "delivery_success_score": round(delivery_success_score, 2) if not np.isnan(delivery_success_score) else 0.0,
            "key_risk_mitigations": key_risk_mitigations,
            "key_kpis": key_kpis,
            "constraints": constraints,
            "summary_period": summary_period,
            entity_ids_key: list(set(all_entity_ids)),
        }
        
        # Add entity-specific fields conditionally
        if key_technologies:
            pattern_data["key_technologies"] = [t["technology"] for t in key_technologies]
        if key_portfolios:
            pattern_data["key_portfolios"] = [p["portfolio"] for p in key_portfolios]
        if team_composition:
            pattern_data["team_composition"] = team_composition
        if dev_methodology_dist:
            pattern_data["dev_methodology_dist"] = dev_methodology_dist
        if work_type_distribution:
            pattern_data["work_type_distribution"] = work_type_distribution
        if priority_distribution:
            pattern_data["priority_distribution"] = priority_distribution
        if status_distribution:
            pattern_data["status_distribution"] = status_distribution
        if key_milestones:
            pattern_data["key_milestones"] = key_milestones
        if key_scopes:
            pattern_data["key_scopes"] = key_scopes
        if key_delivery_themes:
            pattern_data["key_delivery_themes"] = key_delivery_themes
        if key_delivery_approaches:
            pattern_data["key_delivery_approaches"] = key_delivery_approaches
        if key_delivery_criteria:
            pattern_data["key_delivery_criteria"] = key_delivery_criteria
        
        vertices[self._get_pattern_vertex_type()].append((customer_pattern_id, pattern_data))

        # Customer pattern aggregates portfolio patterns (composedOfProjectPattern)
        for p in portfolio_patterns:
            portfolio_pattern_id = p[0]
            edges[self._get_composed_of_pattern_edge()].append((customer_pattern_id, portfolio_pattern_id))
        
        edges[self._get_relevant_to_industry_edge()].append((customer_pattern_id, industry_id))
        # Note: There is no Pattern -> Customer edge in schema (removed summarizes edge)

        return vertices, edges
    
    def generate_customer_summary_profile(
        self,
        customer_id: str,
        tenant_id: int,
        clusters: List[Dict],
        projects: List[Dict]
    ) -> tuple[str, Dict]:
        """Generate CustomerSummaryProfile vertex based on cluster data.
        
        Args:
            customer_id: Customer identifier
            tenant_id: Tenant identifier (REQUIRED - will error if not provided)
            clusters: List of cluster data dictionaries
            projects: List of project dictionaries
            
        Returns:
            Tuple of (profile_id, profile_data dict)
            
        Raises:
            ValueError: If tenant_id is not provided or is 0
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for generate_customer_summary_profile and cannot be 0 or None")
        print(f"Generating CustomerSummaryProfile for {customer_id} (tenant_id={tenant_id})")
        
        velocity_vals = [
            safe_float(c["generalized"].get("velocity_score", 0))
            for c in clusters if c["generalized"].get("velocity_score") is not None
        ]
        velocity_vals = [v for v in velocity_vals if not np.isnan(v)]
        avg_velocity = np.nanmean(velocity_vals) if velocity_vals else 0.0
        
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
            safe_float(c["generalized"].get("delivery_success_score", 0))
            for c in clusters if c["generalized"].get("delivery_success_score") is not None
        ]
        template_success_vals = [v for v in template_success_vals if not np.isnan(v)]
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

        execution_risk_score = safe_float(avg_velocity) * 0.3 + safe_float(template_success_rate) * 0.7
        execution_risk_score = 0.0 if np.isnan(execution_risk_score) else execution_risk_score

        profile_id = f"csp_{customer_id}"
        return profile_id, {
            "id": profile_id,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "avg_velocity": round(safe_float(avg_velocity), 2),
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

