"""
Portfolio Pattern Aggregator

Aggregates workflow-level patterns (scope="workflow") into portfolio-level patterns.
Runs as a post-processing step after pattern generation is complete.

For each TemplatePortfolio in the graph, queries the workflow-level RoadmapPattern 
and ProjectPattern vertices connected to it, enriches with execution scores from 
ProjectScore vertices, then uses LLM to generate a PortfolioPattern with synthesized 
insights, recommendations, and statistical aggregations.
"""

import traceback
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import Counter

from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from ..infrastructure.graph_connector import GraphConnector


class PortfolioPatternAggregator:
    """
    Aggregates workflow-level patterns into portfolio-level analytical summaries.
    
    Called from controller with:
        aggregator = PortfolioPatternAggregator(graph_connector, tenant_id, llm_client)
        result = aggregator.aggregate_all_portfolios()
    """
    
    def __init__(self, graph_connector: GraphConnector, tenant_id: int, llm_client, customer_id: str = None, industry_id: str = None):
        self.graph = graph_connector
        self.tenant_id = tenant_id
        self.llm = llm_client
        self.graph_name = f"g_dev_{tenant_id}"
        self.customer_id = customer_id
        self.industry_id = industry_id

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def aggregate_all_portfolios(self) -> Dict[str, Any]:
        """
        Main entry point. Discovers all TemplatePortfolio vertices for the tenant,
        then generates a PortfolioPattern for each one.
        
        Returns:
            Dict with vertices, edges, and metadata for BatchGraphLoader.
        """
        appLogger.info({
            "event": "portfolio_aggregation_start",
            "tenant_id": self.tenant_id
        })

        # 1. Discover all portfolios for this tenant
        portfolios = self._get_all_portfolios()

        if not portfolios:
            appLogger.info({"event": "portfolio_aggregation_no_portfolios", "tenant_id": self.tenant_id})
            return {
                "vertices": {},
                "edges": {},
                "metadata": {"status": "no_portfolios", "portfolios_processed": 0}
            }

        appLogger.info({
            "event": "portfolio_aggregation_portfolios_found",
            "count": len(portfolios),
            "tenant_id": self.tenant_id
        })

        # 2. Aggregate each portfolio
        all_vertices = {}
        all_edges = {}
        successful = []
        skipped = []

        for portfolio in portfolios:
            portfolio_id = portfolio["id"]
            portfolio_name = portfolio["name"]

            try:
                result = self._aggregate_single_portfolio(portfolio_id, portfolio_name)

                if result["metadata"]["status"] == "no_patterns":
                    skipped.append({"portfolio_id": portfolio_id, "reason": "no_workflow_patterns"})
                    continue

                # Merge vertices and edges
                for vtype, vlist in result["vertices"].items():
                    all_vertices.setdefault(vtype, []).extend(vlist)
                for etype, elist in result["edges"].items():
                    all_edges.setdefault(etype, []).extend(elist)

                successful.append({
                    "portfolio_id": portfolio_id,
                    "portfolio_name": portfolio_name,
                    "portfolio_pattern_id": result["metadata"]["portfolio_pattern_id"],
                    "workflow_patterns_aggregated": result["metadata"]["workflow_pattern_count"]
                })

            except Exception as e:
                appLogger.error({
                    "event": "portfolio_aggregation_error",
                    "portfolio_id": portfolio_id,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                skipped.append({"portfolio_id": portfolio_id, "reason": f"error: {str(e)}"})

        appLogger.info({
            "event": "portfolio_aggregation_complete",
            "tenant_id": self.tenant_id,
            "successful": len(successful),
            "skipped": len(skipped)
        })

        return {
            "vertices": all_vertices,
            "edges": all_edges,
            "metadata": {
                "status": "success",
                "portfolios_processed": len(successful),
                "portfolios_skipped": len(skipped),
                "total_portfolios": len(portfolios),
                "successful_portfolios": successful,
                "skipped_portfolios": skipped
            }
        }

    # ──────────────────────────────────────────────────────────────
    # SINGLE PORTFOLIO AGGREGATION
    # ──────────────────────────────────────────────────────────────

    def _aggregate_single_portfolio(self, portfolio_id: str, portfolio_name: str) -> Dict[str, Any]:
        """Aggregate workflow patterns for one portfolio into a PortfolioPattern vertex."""

        # 1. Get workflow patterns connected to this portfolio
        roadmap_patterns = self._get_workflow_patterns("RoadmapPattern", "derivedFromRoadmapPortfolio", portfolio_id)
        project_patterns = self._get_workflow_patterns("ProjectPattern", "derivedFromProjectPortfolio", portfolio_id)

        if not roadmap_patterns and not project_patterns:
            return {"vertices": {}, "edges": {}, "metadata": {"status": "no_patterns"}}

        appLogger.info({
            "event": "portfolio_patterns_found",
            "portfolio_id": portfolio_id,
            "roadmap_patterns": len(roadmap_patterns),
            "project_patterns": len(project_patterns)
        })

        # 2. Enrich PROJECT patterns with execution scores
        # Roadmap patterns don't inherently have execution data — projects do.
        # If a roadmap connects to a project, that project is in the portfolio too,
        # so execution data is captured via project patterns.
        project_patterns = self._enrich_project_patterns_with_scores(project_patterns)

        # 3. LLM: Generate portfolio metadata (with execution context)
        metadata = self._generate_metadata(roadmap_patterns, project_patterns, portfolio_name)

        # 4. LLM: Generate categorical attributes
        attributes = self._generate_attributes(roadmap_patterns, project_patterns)

        # 5. LLM: Generate strategic narratives + execution insights
        execution_analysis = self._analyze_portfolio(roadmap_patterns, project_patterns, portfolio_name)

        # 6. Statistical aggregations (only from project patterns — the execution source of truth)
        numeric_metrics = self._aggregate_numeric_metrics(project_patterns)

        # 7. Build PortfolioPattern vertex
        pattern_id = f"portfolio_pattern_{self.tenant_id}_{portfolio_id}_{int(datetime.now().timestamp())}"

        vertex_attrs = self._build_vertex_attrs(
            pattern_id, portfolio_id, portfolio_name,
            roadmap_patterns, project_patterns,
            metadata, attributes, execution_analysis, numeric_metrics
        )

        vertices = {"PortfolioPattern": [(pattern_id, vertex_attrs)]}

        # 8. Build edges
        edges = self._build_edges(pattern_id, portfolio_id, roadmap_patterns, project_patterns)

        return {
            "vertices": vertices,
            "edges": edges,
            "metadata": {
                "status": "success",
                "portfolio_pattern_id": pattern_id,
                "workflow_pattern_count": len(roadmap_patterns) + len(project_patterns)
            }
        }

    # ──────────────────────────────────────────────────────────────
    # GRAPH QUERIES
    # ──────────────────────────────────────────────────────────────

    def _get_all_portfolios(self) -> List[Dict[str, Any]]:
        """Get all TemplatePortfolio vertices for this tenant."""
        try:
            raw = self.graph.get_vertices("TemplatePortfolio", tenant_id=self.tenant_id, limit=1000)
            result = []
            for vertex in raw:
                if isinstance(vertex, dict):
                    attrs = vertex.get("attributes", {})
                    result.append({
                        "id": vertex.get("v_id", vertex.get("id", "")),
                        "name": attrs.get("name", "Unknown Portfolio"),
                    })
            return result
        except Exception as e:
            appLogger.error({"event": "get_all_portfolios_error", "error": str(e)})
            return []

    def _get_workflow_patterns(self, pattern_type: str, edge_type: str, portfolio_id: str) -> List[Dict]:
        """
        Get workflow-level patterns connected to a portfolio via the given edge type.
        Uses get_vertices + scope filter since we can't traverse edges directly by target.
        """
        try:
            raw = self.graph.get_vertices(pattern_type, tenant_id=self.tenant_id, limit=10000)
            patterns = []

            for vertex in raw:
                if isinstance(vertex, dict):
                    attrs = vertex.get("attributes", {})
                    if attrs.get("scope") != "workflow":
                        continue

                    vid = vertex.get("v_id", vertex.get("id", ""))

                    # Check if this pattern has an edge to the target portfolio
                    try:
                        edges = self.graph.get_edges(
                            source_vertex_type=pattern_type,
                            source_vertex_id=vid,
                            edge_type=edge_type,
                            tenant_id=self.tenant_id
                        )
                        connected = any(
                            (e.get("to_id") or e.get("t_id")) == portfolio_id
                            for e in (edges or []) if isinstance(e, dict)
                        )
                    except Exception:
                        connected = False

                    if not connected:
                        continue

                    patterns.append(self._extract_pattern_attrs(vid, attrs, pattern_type))

            return patterns

        except Exception as e:
            appLogger.error({
                "event": "get_workflow_patterns_error",
                "pattern_type": pattern_type,
                "portfolio_id": portfolio_id,
                "error": str(e)
            })
            return []

    def _extract_pattern_attrs(self, vid: str, attrs: dict, pattern_type: str) -> Dict:
        """Extract relevant attributes from a pattern vertex into a flat dict."""
        base = {
            "id": vid,
            "name": attrs.get("name", ""),
            "description": attrs.get("description", ""),
            "explanation": attrs.get("explanation", ""),
            "category": attrs.get("category", ""),
            "scope": attrs.get("scope", ""),
            "confidence_score": attrs.get("confidence_score", 0.0),
            "support_score": attrs.get("support_score", 0.0),
            "key_milestones": attrs.get("key_milestones", []),
            "key_kpis": attrs.get("key_kpis", []),
            "constraints": attrs.get("constraints", []),
            "strategic_focus": attrs.get("strategic_focus", ""),
            "maturity_level": attrs.get("maturity_level", ""),
            "implementation_complexity": attrs.get("implementation_complexity", ""),
            "governance_model": attrs.get("governance_model", ""),
        }

        if pattern_type == "RoadmapPattern":
            base.update({
                "roadmap_ids": attrs.get("roadmap_ids", []),
                "solution_themes": attrs.get("solution_themes", []),
                "solution_approaches": attrs.get("solution_approaches", []),
                "team_allocations": attrs.get("team_allocations", []),
                "resource_distribution": attrs.get("resource_distribution", {}),
                "key_technologies": attrs.get("key_technologies", []),
            })
        elif pattern_type == "ProjectPattern":
            base.update({
                "project_ids": attrs.get("project_ids", []),
                "key_technologies": attrs.get("key_technologies", []),
                "team_composition": attrs.get("team_composition", []),
                "dev_methodology_dist": attrs.get("dev_methodology_dist", []),
                "work_type_distribution": attrs.get("work_type_distribution", []),
                "key_risk_mitigations": attrs.get("key_risk_mitigations", []),
                "delivery_themes": attrs.get("delivery_themes", []),
                "delivery_approaches": attrs.get("delivery_approaches", []),
            })

        return base

    # ──────────────────────────────────────────────────────────────
    # EXECUTION SCORE ENRICHMENT
    # ──────────────────────────────────────────────────────────────

    def _enrich_project_patterns_with_scores(self, project_patterns: List[Dict]) -> List[Dict]:
        """
        Enrich project patterns with execution data from ProjectScore vertices.
        
        Edge direction: ProjectScore → ProjectPattern (scoreBelongsToPattern)
        Since we can't traverse backwards, we query all ProjectScores for the tenant
        and build a reverse lookup to match scores to their patterns.
        """
        if not project_patterns:
            return project_patterns

        try:
            # Build reverse lookup: pattern_id → [ProjectScore vertices]
            pattern_id_set = {p["id"] for p in project_patterns}
            all_scores = self.graph.get_vertices("ProjectScore", tenant_id=self.tenant_id, limit=10000)
            
            # For each score, check which pattern it belongs to via scoreBelongsToPattern edge
            pattern_to_scores = {}
            for score in all_scores:
                score_id = score.get("v_id") or score.get("id", "")
                try:
                    edges = self.graph.get_edges(
                        source_vertex_type="ProjectScore",
                        source_vertex_id=score_id,
                        edge_type="scoreBelongsToPattern",
                        tenant_id=self.tenant_id
                    )
                    if edges:
                        for edge in edges:
                            target_id = edge.get("to_id") or edge.get("t_id", "")
                            if target_id in pattern_id_set:
                                pattern_to_scores.setdefault(target_id, []).append(score)
                except Exception:
                    continue

            appLogger.info({
                "event": "execution_score_mapping",
                "total_scores": len(all_scores),
                "patterns_with_scores": len(pattern_to_scores),
                "total_project_patterns": len(project_patterns)
            })

            # Enrich each pattern
            for pattern in project_patterns:
                pid = pattern["id"]
                scores = pattern_to_scores.get(pid, [])
                if scores:
                    pattern["execution_data"] = self._aggregate_scores(scores)
                else:
                    pattern["execution_data"] = {"execution_count": 0}

        except Exception as e:
            appLogger.error({
                "event": "enrich_project_scores_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            for pattern in project_patterns:
                pattern.setdefault("execution_data", {"execution_count": 0})

        return project_patterns

    def _aggregate_scores(self, scores: list) -> Dict[str, Any]:
        """Aggregate ProjectScore vertex data into execution metrics."""
        if not scores:
            return {"execution_count": 0}

        def safe_mean(key):
            vals = []
            for s in scores:
                attrs = s.get("attributes", s) if isinstance(s, dict) else {}
                v = attrs.get(key, 0)
                if v and v > 0:
                    vals.append(float(v))
            return statistics.mean(vals) if vals else 0.0

        return {
            "execution_count": len(scores),
            "avg_core_score": safe_mean("core_score"),
            "avg_on_time": safe_mean("on_time_score"),
            "avg_on_scope": safe_mean("on_scope_score"),
            "avg_on_budget": safe_mean("on_budget_score"),
            "avg_risk_mgmt": safe_mean("risk_management_score"),
            "avg_team_health": safe_mean("team_health_score"),
            "avg_quality": safe_mean("data_completeness_pct"),
        }

    # ──────────────────────────────────────────────────────────────
    # LLM GENERATION
    # ──────────────────────────────────────────────────────────────

    def _generate_metadata(self, roadmap_patterns: List[Dict], project_patterns: List[Dict], portfolio_name: str) -> Dict:
        """LLM: Generate portfolio metadata — the strategic identity of this portfolio."""
        context = self._build_pattern_summary(roadmap_patterns, project_patterns)

        system_prompt = f"""You are a strategic portfolio analyst generating an executive-level portfolio summary.

Portfolio: {portfolio_name}
Workflow Patterns: {len(roadmap_patterns)} roadmap (strategic plans) + {len(project_patterns)} project (execution clusters)

Roadmap patterns represent how work is planned and structured.
Project patterns represent how work is actually delivered and executed.
Together they reveal the portfolio's strategic intent AND operational reality.

Return JSON with:
- name: Action-oriented portfolio name (5-10 words, e.g. "Enterprise Data Platform Modernization")
- category: Strategic category (e.g. "Digital Transformation", "Operational Excellence", "Risk & Compliance")
- description: 2-3 sentences describing what this portfolio delivers and why it matters to the business
- explanation: 4-5 sentences explaining strategic alignment, key capabilities being built, and expected business outcomes
- portfolio_summary: Executive summary (3-4 sentences) a C-suite leader would read — focus on business value, investment themes, and organizational impact
- strategic_focus: Primary strategic focus area (e.g. "Operational Efficiency", "Revenue Growth", "Risk Mitigation")
- maturity_level: One of "Emerging", "Developing", "Mature", "Optimizing" — based on pattern complexity and execution evidence
- implementation_complexity: One of "Low", "Medium", "High", "Very High"
- governance_model: One of "Centralized", "Federated", "Decentralized", "Hybrid"
"""

        try:
            chat = ChatCompletion(system=system_prompt, prev=[], user=f"Pattern Data:\n{context}\n\nGenerate the portfolio metadata as JSON.")
            response = self.llm.run(chat, ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2), "portfolio::generate_metadata")
            return extract_json_after_llm(response)
        except Exception as e:
            appLogger.error({"event": "portfolio_metadata_llm_error", "error": str(e)})
            return {
                "name": f"{portfolio_name} Portfolio Pattern",
                "category": "Mixed",
                "description": f"Aggregated pattern for {portfolio_name}",
                "explanation": f"Contains {len(roadmap_patterns)} roadmap and {len(project_patterns)} project patterns.",
                "portfolio_summary": "",
                "strategic_focus": "",
                "maturity_level": "",
                "implementation_complexity": "",
                "governance_model": ""
            }

    def _generate_attributes(self, roadmap_patterns: List[Dict], project_patterns: List[Dict]) -> Dict:
        """LLM: Synthesize categorical attributes with business-value framing."""
        # Collect raw lists from all patterns
        collected = {
            "key_technologies": [], "team_composition": [], "dev_methodology_dist": [],
            "work_type_distribution": [], "key_risk_mitigations": [], "key_milestones": [],
            "key_kpis": [], "constraints": [], "solution_themes": [], "solution_approaches": [],
            "delivery_themes": [], "delivery_approaches": []
        }

        for rp in roadmap_patterns:
            for key in ["key_technologies", "key_milestones", "key_kpis", "constraints", "solution_themes", "solution_approaches"]:
                collected[key].extend(rp.get(key, []))

        for pp in project_patterns:
            for key in ["key_technologies", "team_composition", "dev_methodology_dist", "work_type_distribution",
                         "key_risk_mitigations", "key_milestones", "key_kpis", "constraints",
                         "delivery_themes", "delivery_approaches"]:
                collected[key].extend(pp.get(key, []))

        system_prompt = """You are a portfolio analyst synthesizing operational attributes from workflow patterns.

Your role is to consolidate, prioritize, and frame these attributes for business decision-making.
Deduplicate similar items. Prioritize by frequency AND strategic importance.
Frame items in business language, not just technical terms.

Return JSON with these list fields (3-8 items each, concise descriptions):
- key_technologies: Core tech capabilities powering this portfolio
- team_composition: Key roles and team structures involved
- dev_methodology_dist: Development/delivery methodologies in use
- work_type_distribution: Types of work being done (Build, Run, Enhance, Transform)
- key_risk_mitigations: Top risk mitigation strategies
- key_milestones: Critical milestones across the portfolio
- key_kpis: Business-outcome KPIs (quantifiable where possible)
- constraints: Key constraints and dependencies
- solution_themes: Primary solution patterns being applied
- solution_approaches: How solutions are being implemented
- delivery_themes: How work is being delivered
- delivery_approaches: Specific delivery tactics
- solution_delivery_narrative: 3-4 sentence narrative connecting how the portfolio's solution approach drives business outcomes through its delivery model
"""

        user_prompt = "\n".join(f"{k}: {v}" for k, v in collected.items())

        try:
            chat = ChatCompletion(system=system_prompt, prev=[], user=f"Raw pattern data:\n{user_prompt}\n\nSynthesize as JSON.")
            response = self.llm.run(chat, ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2), "portfolio::generate_attributes")
            return extract_json_after_llm(response)
        except Exception as e:
            appLogger.error({"event": "portfolio_attributes_llm_error", "error": str(e)})
            # Fallback: frequency-based top items
            return {k: [item for item, _ in Counter(v).most_common(5)] for k, v in collected.items()}

    def _analyze_portfolio(self, roadmap_patterns: List[Dict], project_patterns: List[Dict], portfolio_name: str) -> Dict:
        """
        LLM: Generate strategic narratives + execution insights for the portfolio.
        
        ALWAYS generates strength/weakness narratives regardless of execution data.
        - With execution data: narratives are grounded in measured performance
        - Without execution data: narratives are derived from pattern attributes
          (technologies, methodologies, team composition, strategic alignment)
        """
        # Gather execution data from project patterns (the source of truth for execution)
        exec_data = [p["execution_data"] for p in project_patterns 
                     if p.get("execution_data", {}).get("execution_count", 0) > 0]
        has_execution = len(exec_data) > 0

        # Build execution context if available
        exec_context = ""
        sufficient, missing = [], []
        confidence = "LOW"
        avg_quality = 0.0

        if has_execution:
            total_execs = sum(ed["execution_count"] for ed in exec_data)
            avg_core = statistics.mean([ed["avg_core_score"] for ed in exec_data if ed.get("avg_core_score")])

            dimensions = {"on_time": "avg_on_time", "on_scope": "avg_on_scope", "on_budget": "avg_on_budget",
                           "risk_mgmt": "avg_risk_mgmt", "team_health": "avg_team_health"}
            dim_avgs = {}
            for dim, key in dimensions.items():
                vals = [ed[key] for ed in exec_data if ed.get(key, 0) > 0]
                if vals:
                    dim_avgs[dim] = round(statistics.mean(vals), 1)
                    (sufficient if len(vals) >= len(exec_data) * 0.5 else missing).append(dim)
                else:
                    missing.append(dim)

            avg_quality = statistics.mean([ed["avg_quality"] for ed in exec_data if ed.get("avg_quality", 0) > 0]) if any(ed.get("avg_quality", 0) > 0 for ed in exec_data) else 0.0
            confidence = "HIGH" if total_execs >= 20 else ("MEDIUM" if total_execs >= 10 else "LOW")

            exec_context = f"""

EXECUTION PERFORMANCE DATA (from {len(exec_data)}/{len(project_patterns)} project patterns with scores):
  Total Project Executions: {total_execs}
  Average Core Score: {avg_core:.1f}/100
  Dimension Averages: {dim_avgs}
  Patterns with Execution Data: {len(exec_data)}/{len(project_patterns)} project patterns ({int(len(exec_data)/max(1,len(project_patterns))*100)}%)
  Data Quality: {avg_quality:.1f}%
  Confidence Level: {confidence}"""
        else:
            missing = ["on_time", "on_scope", "on_budget", "risk_management", "team_health"]

        # Build pattern context for narrative generation
        pattern_descriptions = []
        for rp in roadmap_patterns:
            desc = f"Roadmap: {rp.get('name', '')} ({rp.get('category', '')}) - {rp.get('description', '')[:120]}"
            pattern_descriptions.append(desc)
        for pp in project_patterns:
            ed = pp.get("execution_data", {})
            exec_note = ""
            if ed.get("execution_count", 0) > 0:
                exec_note = f" | Score: {ed.get('avg_core_score', 0):.0f}/100 ({ed['execution_count']} executions)"
            desc = f"Project: {pp.get('name', '')} ({pp.get('category', '')}) - {pp.get('description', '')[:120]}{exec_note}"
            pattern_descriptions.append(desc)

        patterns_text = "\n".join(f"  {i+1}. {d}" for i, d in enumerate(pattern_descriptions))

        system_prompt = f"""You are a strategic portfolio analyst for "{portfolio_name}".

You must generate insights about this portfolio's strengths, weaknesses, and recommended actions.
You have {len(roadmap_patterns)} roadmap patterns (strategic plans) and {len(project_patterns)} project patterns (execution clusters).

{'IMPORTANT: Real execution performance data is available — ground your analysis in these measured results.' if has_execution else 'NOTE: No execution performance data is available yet. Base your analysis on the pattern attributes: technologies, methodologies, team structures, strategic focus, complexity, and risk factors.'}

Return JSON with ALL of these fields (every field must have substantive content, never empty strings):
- narrative: 3-4 sentence executive insight on portfolio health and trajectory
- strengths: 2-3 sentences on what this portfolio does well (based on {'execution scores and' if has_execution else ''} pattern attributes like technologies, methodologies, team composition)
- weaknesses: 2-3 sentences on gaps, risks, or underperforming areas
- actions: List of 3-5 specific, actionable recommendations (1-2 sentences each) that would improve portfolio outcomes
"""

        user_prompt = f"""Portfolio Patterns:
{patterns_text}
{exec_context}

Generate strategic analysis as JSON. Every field must have substantive content."""

        try:
            chat = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
            response = self.llm.run(chat, ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2), "portfolio::analyze_execution")
            result = extract_json_after_llm(response)
            result.update({
                "confidence_level": confidence,
                "avg_quality_score": avg_quality,
                "sufficient_dimensions": sufficient,
                "missing_dimensions": missing
            })
            return result
        except Exception as e:
            appLogger.error({"event": "portfolio_analysis_llm_error", "error": str(e)})
            return {
                "narrative": f"Portfolio '{portfolio_name}' contains {len(roadmap_patterns)} roadmap and {len(project_patterns)} project patterns.",
                "strengths": f"The portfolio demonstrates structured planning with {len(roadmap_patterns)} roadmap patterns.",
                "weaknesses": "Further execution data collection needed for quantitative performance assessment.",
                "confidence_level": confidence, "avg_quality_score": avg_quality,
                "sufficient_dimensions": sufficient, "missing_dimensions": missing,
                "actions": ["Expand execution monitoring to increase performance visibility across the portfolio."]
            }

    # ──────────────────────────────────────────────────────────────
    # STATISTICAL AGGREGATION
    # ──────────────────────────────────────────────────────────────

    def _aggregate_numeric_metrics(self, all_patterns: List[Dict]) -> Dict[str, Any]:
        """Calculate weighted averages and statistics for execution scores from project patterns."""
        # Only project patterns have execution data (roadmaps don't execute directly)
        with_exec = [p for p in all_patterns if p.get("execution_data", {}).get("execution_count", 0) > 0]

        if not with_exec:
            return {
                "total_execution_count": 0, "execution_coverage_pct": 0,
                "avg_core_score": 0.0, "score_variance_across_patterns": 0.0,
                "min_score": 0, "max_score": 0, "median_score": 0,
                "avg_on_time_score": 0.0, "avg_on_scope_score": 0.0, "avg_on_budget_score": 0.0,
                "avg_risk_management_score": 0.0, "avg_team_health_score": 0.0,
                "top_performing_pattern_ids": [], "dimension_strength_ranking": []
            }

        total_execs = sum(p["execution_data"]["execution_count"] for p in with_exec)
        coverage = int((len(with_exec) / len(all_patterns)) * 100) if all_patterns else 0

        def weighted_avg(key):
            wsum = sum(p["execution_data"].get(key, 0) * p["execution_data"]["execution_count"]
                       for p in with_exec if p["execution_data"].get(key) is not None)
            wtotal = sum(p["execution_data"]["execution_count"]
                         for p in with_exec if p["execution_data"].get(key) is not None)
            return wsum / wtotal if wtotal > 0 else 0.0

        core_scores = [p["execution_data"]["avg_core_score"] for p in with_exec if p["execution_data"].get("avg_core_score")]

        dim_scores = {
            "on_time": weighted_avg("avg_on_time"),
            "on_scope": weighted_avg("avg_on_scope"),
            "on_budget": weighted_avg("avg_on_budget"),
            "risk_management": weighted_avg("avg_risk_mgmt"),
            "team_health": weighted_avg("avg_team_health"),
        }
        dim_ranking = sorted([k for k, v in dim_scores.items() if v > 0], key=lambda k: dim_scores[k], reverse=True)

        top_sorted = sorted(with_exec, key=lambda p: p["execution_data"].get("avg_core_score", 0), reverse=True)

        return {
            "total_execution_count": total_execs,
            "execution_coverage_pct": coverage,
            "avg_core_score": weighted_avg("avg_core_score"),
            "score_variance_across_patterns": statistics.variance(core_scores) if len(core_scores) > 1 else 0.0,
            "min_score": int(min(core_scores)) if core_scores else 0,
            "max_score": int(max(core_scores)) if core_scores else 0,
            "median_score": int(statistics.median(core_scores)) if core_scores else 0,
            "avg_on_time_score": dim_scores["on_time"],
            "avg_on_scope_score": dim_scores["on_scope"],
            "avg_on_budget_score": dim_scores["on_budget"],
            "avg_risk_management_score": dim_scores["risk_management"],
            "avg_team_health_score": dim_scores["team_health"],
            "top_performing_pattern_ids": [p["id"] for p in top_sorted[:3]],
            "dimension_strength_ranking": dim_ranking
        }

    # ──────────────────────────────────────────────────────────────
    # VERTEX + EDGE BUILDERS
    # ──────────────────────────────────────────────────────────────

    def _build_vertex_attrs(
        self, pattern_id, portfolio_id, portfolio_name,
        roadmap_patterns, project_patterns,
        metadata, attributes, execution_analysis, numeric_metrics
    ) -> Dict[str, Any]:
        """Assemble all attributes for the PortfolioPattern vertex."""
        return {
            # Core identity
            "id": pattern_id,
            "tenant_id": self.tenant_id,
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            # Aggregation metadata
            "workflow_pattern_count": len(roadmap_patterns) + len(project_patterns),
            "roadmap_pattern_count": len(roadmap_patterns),
            "project_pattern_count": len(project_patterns),
            "aggregation_method": "weighted_llm_analysis",
            # LLM-generated metadata
            "name": metadata.get("name", ""),
            "category": metadata.get("category", ""),
            "description": metadata.get("description", ""),
            "explanation": metadata.get("explanation", ""),
            "strategic_focus": metadata.get("strategic_focus", ""),
            "maturity_level": metadata.get("maturity_level", ""),
            "implementation_complexity": metadata.get("implementation_complexity", ""),
            "governance_model": metadata.get("governance_model", ""),
            # Categorical attributes
            "key_technologies": attributes.get("key_technologies", []),
            "team_composition": attributes.get("team_composition", []),
            "dev_methodology_dist": attributes.get("dev_methodology_dist", []),
            "work_type_distribution": attributes.get("work_type_distribution", []),
            "key_risk_mitigations": attributes.get("key_risk_mitigations", []),
            "key_milestones": attributes.get("key_milestones", []),
            "key_kpis": attributes.get("key_kpis", []),
            "constraints": attributes.get("constraints", []),
            "solution_themes": attributes.get("solution_themes", []),
            "solution_approaches": attributes.get("solution_approaches", []),
            "delivery_themes": attributes.get("delivery_themes", []),
            "delivery_approaches": attributes.get("delivery_approaches", []),
            # Execution scores
            **numeric_metrics,
            # Data quality
            "overall_confidence_level": execution_analysis.get("confidence_level", ""),
            "avg_quality_score": execution_analysis.get("avg_quality_score", 0.0),
            "dimensions_with_sufficient_data": execution_analysis.get("sufficient_dimensions", []),
            "missing_dimensions": execution_analysis.get("missing_dimensions", []),
            # LLM insights
            "portfolio_summary": metadata.get("portfolio_summary", ""),
            "execution_insights": execution_analysis.get("narrative", ""),
            "strength_narrative": execution_analysis.get("strengths", ""),
            "weakness_narrative": execution_analysis.get("weaknesses", ""),
            "recommended_actions": execution_analysis.get("actions", []),
            "cross_pattern_insights": [],  # Populated from metadata if present
            "solution_delivery_narrative": attributes.get("solution_delivery_narrative", ""),
        }

    def _build_edges(self, pattern_id: str, portfolio_id: str, roadmap_patterns: List[Dict], project_patterns: List[Dict]) -> Dict[str, List[Tuple]]:
        """Build edge tuples connecting PortfolioPattern to workflow patterns and portfolio."""
        edges = {
            "aggregatesRoadmapWorkflow": [(pattern_id, rp["id"]) for rp in roadmap_patterns],
            "aggregatesProjectWorkflow": [(pattern_id, pp["id"]) for pp in project_patterns],
            "summarizesPortfolio": [(pattern_id, str(portfolio_id))],
            "hasPortfolioSummary": [(str(portfolio_id), pattern_id)],
        }
        # Link PortfolioPattern to Customer and Industry if available
        if self.customer_id:
            edges["belongsToCustomer"] = [(pattern_id, self.customer_id)]
        if self.industry_id:
            edges["relevantToIndustry"] = [(pattern_id, self.industry_id)]
        return edges

    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────

    def _build_pattern_summary(self, roadmap_patterns: List[Dict], project_patterns: List[Dict]) -> str:
        """Build a rich summarized text of patterns for LLM context."""
        lines = [f"ROADMAP PATTERNS ({len(roadmap_patterns)}) — Strategic plans and initiatives:"]
        for i, rp in enumerate(roadmap_patterns[:10], 1):
            name = rp.get('name', 'Unnamed')
            category = rp.get('category', '')
            desc = rp.get('description', '')[:100]
            focus = rp.get('strategic_focus', '')
            techs = ', '.join(rp.get('key_technologies', [])[:3])
            lines.append(f"  {i}. {name} [{category}]")
            if desc:
                lines.append(f"     {desc}")
            if focus:
                lines.append(f"     Focus: {focus}")
            if techs:
                lines.append(f"     Tech: {techs}")
        if len(roadmap_patterns) > 10:
            lines.append(f"  ... and {len(roadmap_patterns) - 10} more")

        lines.append(f"\nPROJECT PATTERNS ({len(project_patterns)}) — Execution clusters with performance data:")
        for i, pp in enumerate(project_patterns[:10], 1):
            name = pp.get('name', 'Unnamed')
            category = pp.get('category', '')
            desc = pp.get('description', '')[:100]
            techs = ', '.join(pp.get('key_technologies', [])[:3])
            ed = pp.get("execution_data", {})
            exec_info = ""
            if ed.get("execution_count", 0) > 0:
                exec_info = f" | Score: {ed.get('avg_core_score', 0):.0f}/100 ({ed['execution_count']} executions)"
            lines.append(f"  {i}. {name} [{category}]{exec_info}")
            if desc:
                lines.append(f"     {desc}")
            if techs:
                lines.append(f"     Tech: {techs}")
        if len(project_patterns) > 10:
            lines.append(f"  ... and {len(project_patterns) - 10} more")

        return "\n".join(lines)
