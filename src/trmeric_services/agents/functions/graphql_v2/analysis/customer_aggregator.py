"""
CustomerPattern Aggregator

Synthesizes all PortfolioPattern vertices for a tenant into a single
CustomerPattern — the apex vertex in the knowledge graph hierarchy.

Hierarchy:
    CustomerPattern (1 per tenant — org-level strategic intelligence)
      └── PortfolioPattern (1 per portfolio)
            ├── RoadmapPattern (strategic plans)
            └── ProjectPattern (execution patterns)
                  └── ProjectScore (execution data)

The CustomerPattern is primarily LLM-generated strategic content:
  - Executive summary, strategic direction, SWOT analysis
  - Cross-portfolio synergies, capability landscape
  - Investment priorities and recommendations
  - Aggregated execution metrics from all portfolios
"""

import traceback
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from ..infrastructure.graph_connector import GraphConnector


class CustomerPatternAggregator:
    """Aggregates PortfolioPatterns into a single CustomerPattern vertex."""

    def __init__(
        self,
        graph_connector: GraphConnector,
        tenant_id: int,
        llm_client,
        customer_data: Dict[str, Any]
    ):
        self.graph = graph_connector
        self.tenant_id = tenant_id
        self.llm = llm_client
        self.customer_data = customer_data
        self.graph_name = f"g_dev_{tenant_id}"

    def aggregate(self) -> Dict[str, Any]:
        """
        Main entry. Reads all PortfolioPatterns, synthesizes a single CustomerPattern.

        Returns:
            {
                "vertices": {vertex_type: [(id, attrs), ...]},
                "edges": {edge_type: [(from_id, to_id), ...]},
                "metadata": {...}
            }
        """
        try:
            portfolio_patterns = self._get_portfolio_patterns()

            if not portfolio_patterns:
                return {
                    "vertices": {},
                    "edges": {},
                    "metadata": {"status": "no_portfolio_patterns"}
                }

            appLogger.info({
                "event": "customer_aggregation_start",
                "tenant_id": self.tenant_id,
                "portfolio_pattern_count": len(portfolio_patterns),
            })

            # 1. LLM: Strategic synthesis
            strategic_content = self._generate_strategic_content(portfolio_patterns)

            # 2. LLM: SWOT analysis
            swot = self._generate_swot(portfolio_patterns)

            # 3. LLM: Capabilities and recommendations
            capabilities = self._generate_capabilities(portfolio_patterns)

            # 4. Aggregate numeric metrics from portfolio patterns
            metrics = self._aggregate_metrics(portfolio_patterns)

            # 5. Build vertex
            customer_info = self.customer_data.get("customer", {})
            industry_info = self.customer_data.get("industry", {})
            sector_info = self.customer_data.get("industry_sector", {})
            customer_id = customer_info.get("id", f"tenant_{self.tenant_id}")

            pattern_id = f"customer_pattern_{self.tenant_id}_{int(datetime.now().timestamp())}"

            vertex_attrs = {
                # Core identity
                "id": pattern_id,
                "tenant_id": self.tenant_id,
                "customer_id": customer_id,
                "customer_name": customer_info.get("name", ""),
                "industry": industry_info.get("name", industry_info.get("id", "")),
                "industry_sector": sector_info.get("name", sector_info.get("id", "")),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                # Aggregation metadata
                "portfolio_count": len(portfolio_patterns),
                "total_roadmap_patterns": sum(
                    p.get("roadmap_pattern_count", 0) for p in portfolio_patterns
                ),
                "total_project_patterns": sum(
                    p.get("project_pattern_count", 0) for p in portfolio_patterns
                ),
                "portfolios_with_execution": sum(
                    1 for p in portfolio_patterns if p.get("total_execution_count", 0) > 0
                ),
                # LLM strategic content
                "name": strategic_content.get("name", ""),
                "executive_summary": strategic_content.get("executive_summary", ""),
                "strategic_direction": strategic_content.get("strategic_direction", ""),
                "organizational_maturity": strategic_content.get("organizational_maturity", ""),
                "capability_landscape": strategic_content.get("capability_landscape", ""),
                "innovation_profile": strategic_content.get("innovation_profile", ""),
                "risk_landscape": strategic_content.get("risk_landscape", ""),
                "investment_thesis": strategic_content.get("investment_thesis", ""),
                "competitive_positioning": strategic_content.get("competitive_positioning", ""),
                # SWOT
                "strength_narrative": swot.get("strengths", ""),
                "weakness_narrative": swot.get("weaknesses", ""),
                "opportunity_narrative": swot.get("opportunities", ""),
                "threat_narrative": swot.get("threats", ""),
                # Cross-portfolio
                "cross_portfolio_synergies": strategic_content.get("cross_portfolio_synergies", ""),
                "portfolio_health_summary": strategic_content.get("portfolio_health_summary", ""),
                # Capability lists
                "key_capabilities": capabilities.get("key_capabilities", []),
                "capability_gaps": capabilities.get("capability_gaps", []),
                "strategic_recommendations": capabilities.get("strategic_recommendations", []),
                "top_technologies": capabilities.get("top_technologies", []),
                "emerging_risks": capabilities.get("emerging_risks", []),
                "investment_priorities": capabilities.get("investment_priorities", []),
                # Execution metrics
                **metrics,
            }

            vertices = {"CustomerPattern": [(pattern_id, vertex_attrs)]}

            # 6. Build edges
            edges = self._build_edges(pattern_id, customer_id, portfolio_patterns)

            appLogger.info({
                "event": "customer_aggregation_complete",
                "pattern_id": pattern_id,
                "portfolio_count": len(portfolio_patterns),
            })

            return {
                "vertices": vertices,
                "edges": edges,
                "metadata": {
                    "status": "success",
                    "customer_pattern_id": pattern_id,
                    "portfolio_count": len(portfolio_patterns),
                }
            }

        except Exception as e:
            appLogger.error({
                "event": "customer_aggregation_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return {
                "vertices": {},
                "edges": {},
                "metadata": {"status": "error", "error": str(e)}
            }

    # ──────────────────────────────────────────────────────────────
    # GRAPH QUERIES
    # ──────────────────────────────────────────────────────────────

    def _get_portfolio_patterns(self) -> List[Dict[str, Any]]:
        """Fetch all PortfolioPattern vertices for this tenant."""
        try:
            raw = self.graph.get_vertices("PortfolioPattern", tenant_id=self.tenant_id, limit=1000)
            patterns = []
            for vertex in raw:
                if isinstance(vertex, dict):
                    attrs = vertex.get("attributes", {})
                    attrs["_vertex_id"] = vertex.get("v_id", vertex.get("id", ""))
                    patterns.append(attrs)
            return patterns
        except Exception as e:
            appLogger.error({"event": "get_portfolio_patterns_error", "error": str(e)})
            return []

    # ──────────────────────────────────────────────────────────────
    # LLM GENERATION
    # ──────────────────────────────────────────────────────────────

    def _generate_strategic_content(self, portfolio_patterns: List[Dict]) -> Dict[str, Any]:
        """Generate the core strategic content — executive summary, direction, positioning."""
        portfolio_summaries = self._build_portfolio_summaries(portfolio_patterns)
        customer_name = self.customer_data.get("customer", {}).get("name", "the organization")
        industry = self.customer_data.get("industry", {}).get("name", "their industry")

        system_prompt = f"""You are a Chief Strategy Officer analyzing the complete project and roadmap 
landscape of {customer_name}, operating in the {industry} industry.

You have visibility into ALL portfolios across the organization. Each portfolio has been 
analyzed into a PortfolioPattern that summarizes its strategic themes, execution performance, 
and capability focus. Your task is to synthesize these into an organization-level strategic assessment.

Think about:
- What is the overall strategic direction emerging from all portfolios?
- How mature is the organization in executing its strategy?  
- What capabilities are being built, and where are the gaps?
- Where should investment be directed for maximum impact?
- What cross-portfolio synergies exist that leadership should capitalize on?"""

        user_prompt = f"""Analyze these {len(portfolio_patterns)} portfolio patterns and produce a strategic assessment.

{portfolio_summaries}

Return a JSON object with these fields:
{{
    "name": "A strategic title for this organization's overall pattern (e.g., 'Digital-First Operational Transformation Leader')",
    "executive_summary": "2-3 paragraph C-suite summary of the organization's entire project/roadmap landscape. Cover the strategic posture, key strengths, areas needing attention, and overall trajectory.",
    "strategic_direction": "Where the organization is heading based on all its portfolios. What themes dominate? What transformation journey is underway?",
    "organizational_maturity": "One of: Emerging, Developing, Established, Optimizing. Brief justification.",
    "capability_landscape": "What core capabilities are being built across all portfolios? What is the organization becoming good at?",
    "innovation_profile": "How innovative is the organization? Is it pushing boundaries or catching up? Are there pockets of innovation?",
    "risk_landscape": "Overall risk posture across all portfolios. What systemic risks emerge from the pattern analysis?",
    "investment_thesis": "Where and why should the organization invest? What's the ROI story across portfolios?",
    "competitive_positioning": "How is the organization positioning itself in its industry based on its portfolio of initiatives?",
    "cross_portfolio_synergies": "Specific opportunities where portfolios could work together or share capabilities for greater impact.",
    "portfolio_health_summary": "Brief health assessment of each portfolio (1-2 sentences each)."
}}"""

        try:
            response = self.llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
                ModelOptions(model="gpt-4o-mini", max_tokens=4000, temperature=0.4),
                function_name="customer_strategic_content"
            )
            return extract_json_after_llm(response) or {}
        except Exception as e:
            appLogger.error({"event": "strategic_content_error", "error": str(e)})
            return {}

    def _generate_swot(self, portfolio_patterns: List[Dict]) -> Dict[str, Any]:
        """Generate SWOT analysis across all portfolios."""
        portfolio_summaries = self._build_portfolio_summaries(portfolio_patterns)
        customer_name = self.customer_data.get("customer", {}).get("name", "the organization")
        industry = self.customer_data.get("industry", {}).get("name", "their industry")

        system_prompt = f"""You are a strategic analyst performing a SWOT analysis for {customer_name} 
in the {industry} industry. Base your analysis on the portfolio pattern data provided — these 
represent real project execution and roadmap planning data, not hypotheticals."""

        user_prompt = f"""Based on these {len(portfolio_patterns)} portfolio patterns, produce a SWOT analysis.

{portfolio_summaries}

Return a JSON object:
{{
    "strengths": "3-4 paragraph narrative on the organization's key strengths as demonstrated by portfolio execution and planning data. Be specific — reference actual patterns and scores.",
    "weaknesses": "3-4 paragraph narrative on weaknesses and areas needing improvement. Ground this in the execution data and portfolio gaps.",
    "opportunities": "3-4 paragraph narrative on growth opportunities the organization should pursue based on its current capabilities and market position.",
    "threats": "3-4 paragraph narrative on risks and threats that could undermine the organization's strategic initiatives."
}}"""

        try:
            response = self.llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
                ModelOptions(model="gpt-4o-mini", max_tokens=3000, temperature=0.4),
                function_name="customer_swot"
            )
            return extract_json_after_llm(response) or {}
        except Exception as e:
            appLogger.error({"event": "swot_error", "error": str(e)})
            return {}

    def _generate_capabilities(self, portfolio_patterns: List[Dict]) -> Dict[str, Any]:
        """Generate capability lists and recommendations."""
        portfolio_summaries = self._build_portfolio_summaries(portfolio_patterns)
        customer_name = self.customer_data.get("customer", {}).get("name", "the organization")

        system_prompt = f"""You are a technology and strategy advisor for {customer_name}. 
Analyze their portfolio patterns to identify capabilities, gaps, and strategic recommendations.
Be concrete and actionable — this is for executive decision-making."""

        user_prompt = f"""Based on these {len(portfolio_patterns)} portfolio patterns, identify capabilities and recommendations.

{portfolio_summaries}

Return a JSON object with arrays of strings:
{{
    "key_capabilities": ["capability 1", "capability 2", ...],
    "capability_gaps": ["gap 1", "gap 2", ...],
    "strategic_recommendations": ["recommendation 1", "recommendation 2", ...],
    "top_technologies": ["tech 1", "tech 2", ...],
    "emerging_risks": ["risk 1", "risk 2", ...],
    "investment_priorities": ["priority 1", "priority 2", ...]
}}

Guidelines:
- key_capabilities: 5-8 core capabilities demonstrated across portfolios
- capability_gaps: 3-5 critical gaps that limit the organization
- strategic_recommendations: 5-7 actionable recommendations for leadership
- top_technologies: 5-8 most impactful technologies across all portfolios
- emerging_risks: 3-5 risks that could materialize based on pattern analysis
- investment_priorities: 4-6 areas deserving increased investment"""

        try:
            response = self.llm.run(
                ChatCompletion(system=system_prompt, prev=[], user=user_prompt),
                ModelOptions(model="gpt-4o-mini", max_tokens=2000, temperature=0.3),
                function_name="customer_capabilities"
            )
            return extract_json_after_llm(response) or {}
        except Exception as e:
            appLogger.error({"event": "capabilities_error", "error": str(e)})
            return {}

    # ──────────────────────────────────────────────────────────────
    # METRICS AGGREGATION
    # ──────────────────────────────────────────────────────────────

    def _aggregate_metrics(self, portfolio_patterns: List[Dict]) -> Dict[str, Any]:
        """Aggregate execution scores across all portfolios."""
        with_scores = [
            p for p in portfolio_patterns
            if p.get("total_execution_count", 0) > 0
        ]

        if not with_scores:
            return {
                "org_avg_execution_score": 0.0,
                "org_avg_on_time_score": 0.0,
                "org_avg_on_scope_score": 0.0,
                "org_avg_on_budget_score": 0.0,
                "org_avg_risk_score": 0.0,
                "execution_maturity": "Insufficient Data",
            }

        def weighted_avg(field: str) -> float:
            total_weight = 0
            weighted_sum = 0.0
            for p in with_scores:
                weight = p.get("total_execution_count", 1)
                value = p.get(field, 0) or 0
                weighted_sum += value * weight
                total_weight += weight
            return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

        avg_exec = weighted_avg("avg_core_score")

        # Derive execution maturity from avg score
        if avg_exec >= 80:
            maturity = "Optimizing"
        elif avg_exec >= 65:
            maturity = "Established"
        elif avg_exec >= 45:
            maturity = "Developing"
        else:
            maturity = "Emerging"

        return {
            "org_avg_execution_score": avg_exec,
            "org_avg_on_time_score": weighted_avg("avg_on_time_score"),
            "org_avg_on_scope_score": weighted_avg("avg_on_scope_score"),
            "org_avg_on_budget_score": weighted_avg("avg_on_budget_score"),
            "org_avg_risk_score": weighted_avg("avg_risk_management_score"),
            "execution_maturity": maturity,
        }

    # ──────────────────────────────────────────────────────────────
    # EDGE BUILDERS
    # ──────────────────────────────────────────────────────────────

    def _build_edges(
        self,
        pattern_id: str,
        customer_id: str,
        portfolio_patterns: List[Dict]
    ) -> Dict[str, List[Tuple[str, str]]]:
        """Build edges connecting CustomerPattern to PortfolioPatterns and Customer vertex."""
        portfolio_ids = [
            p.get("_vertex_id", p.get("id", ""))
            for p in portfolio_patterns
            if p.get("_vertex_id") or p.get("id")
        ]

        return {
            "customerPatternAggregatesPortfolio": [
                (pattern_id, pid) for pid in portfolio_ids
            ],
            "customerPatternForCustomer": [(pattern_id, customer_id)],
            "hasCustomerPattern": [(customer_id, pattern_id)],
        }

    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────

    def _build_portfolio_summaries(self, portfolio_patterns: List[Dict]) -> str:
        """Build rich text summary of all portfolio patterns for LLM context."""
        lines = []
        for i, p in enumerate(portfolio_patterns, 1):
            name = p.get("name", "Unnamed Portfolio Pattern")
            portfolio_name = p.get("portfolio_name", "Unknown")
            category = p.get("category", "")
            description = p.get("description", "")[:200]
            explanation = p.get("explanation", "")[:200]
            maturity = p.get("maturity_level", "")
            complexity = p.get("implementation_complexity", "")
            strategic_focus = p.get("strategic_focus", "")
            governance = p.get("governance_model", "")

            roadmap_count = p.get("roadmap_pattern_count", 0)
            project_count = p.get("project_pattern_count", 0)
            exec_count = p.get("total_execution_count", 0)
            avg_core = p.get("avg_core_score", 0)
            coverage = p.get("execution_coverage_pct", 0)

            techs = p.get("key_technologies", [])
            tech_str = ", ".join(techs[:5]) if techs else "N/A"

            strength = p.get("strength_narrative", "")[:150]
            weakness = p.get("weakness_narrative", "")[:150]
            summary = p.get("portfolio_summary", "")[:200]

            lines.append(f"""
PORTFOLIO {i}: {name}
  Portfolio: {portfolio_name} | Category: {category}
  Maturity: {maturity} | Complexity: {complexity} | Governance: {governance}
  Strategic Focus: {strategic_focus}
  Patterns: {roadmap_count} roadmap, {project_count} project
  Execution: {exec_count} scores, {avg_core:.0f}/100 avg, {coverage}% coverage
  Technologies: {tech_str}
  Description: {description}
  Summary: {summary}
  Strengths: {strength}
  Weaknesses: {weakness}""")

        return "\n".join(lines)
