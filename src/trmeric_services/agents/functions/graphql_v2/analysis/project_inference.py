"""
Project Inference Engine

LLM-based project pattern matching and generation advice.
Takes minimal project information (name, description) and:
1. Retrieves project patterns from TigerGraph database
2. Uses LLM to match against patterns
3. Generates advice based on matching patterns

Similar to roadmap_inference.py but adapted for ProjectTemplate schema.
ProjectTemplate uses delivery_status, scope_status, spend_status instead of "solution".
"""

from typing import Dict, List, Any, Optional
import os
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient, ModelOptions
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger
from ..infrastructure import GraphConnector, GraphConnectorConfig
import json
import traceback


def get_project_patterns_from_graph(
    graph_connector: GraphConnector,
    tenant_id: int,
    limit: int = 10,
    scope_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve project patterns from TigerGraph database.
    
    Queries the ProjectPattern vertices that contain pattern attributes
    (delivery themes, approaches, KPIs, milestones, etc.) for project generation.
    
    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: REQUIRED tenant ID for filtering
        limit: Maximum number of patterns to retrieve
        scope_filter: Optional filter for pattern scope (workflow, portfolio, customer)
        
    Returns:
        List of project patterns from the database (filtered by tenant_id)
    """
    if not tenant_id:
        raise ValueError("tenant_id is REQUIRED for get_project_patterns_from_graph")
    
    try:
        # Ensure we're connected
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_project_patterns_from_graph",
                "error": "Failed to connect to graph",
                "tenant_id": tenant_id
            })
            return []
        
        # Use GraphConnector's connection to fetch ProjectPattern vertices (filtered by tenant_id)
        patterns = graph_connector.get_vertices("ProjectPattern", tenant_id=tenant_id, limit=limit)
        
        appLogger.info({
            "event": "get_project_patterns_from_graph",
            "query": "fetch_patterns",
            "vertex_type": "ProjectPattern",
            "tenant_id": tenant_id,
            "limit": limit,
            "status": "executed",
            "patterns_retrieved": len(patterns) if patterns else 0
        })
        
        # Convert TigerGraph vertex format to list of dicts
        patterns_list = []
        
        # getVertices returns a list of vertex dicts
        if isinstance(patterns, list):
            for pattern_vertex in patterns:
                if isinstance(pattern_vertex, dict):
                    # Extract vertex ID and attributes
                    vertex_id = pattern_vertex.get("v_id", "")
                    attributes = pattern_vertex.get("attributes", {})
                    
                    # Filter by scope if specified
                    pattern_scope = attributes.get("scope", "")
                    if scope_filter and pattern_scope != scope_filter:
                        continue
                    
                    pattern_dict = {
                        "id": vertex_id,
                        "name": attributes.get("name", ""),
                        "description": attributes.get("description", ""),
                        "explanation": attributes.get("explanation", ""),
                        "category": attributes.get("category", ""),
                        "scope": pattern_scope,
                        "confidence_score": attributes.get("confidence_score", 0.0),
                        "support_score": attributes.get("support_score", 0.0),
                        "created_at": attributes.get("created_at", ""),
                        "summary_period": attributes.get("summary_period", ""),
                        # Project-specific pattern fields
                        "project_ids": attributes.get("project_ids", []),
                        "avg_project_duration": attributes.get("avg_project_duration", 0),
                        "avg_milestone_velocity": attributes.get("avg_milestone_velocity", 0.0),
                        "budget_band": attributes.get("budget_band", ""),
                        "key_technologies": attributes.get("key_technologies", []),
                        "team_composition": attributes.get("team_composition", []),
                        "dev_methodology_dist": attributes.get("dev_methodology_dist", []),
                        "work_type_distribution": attributes.get("work_type_distribution", []),
                        "milestone_adherence_score": attributes.get("milestone_adherence_score", 0.0),
                        "delivery_success_score": attributes.get("delivery_success_score", 0.0),
                        "key_risk_mitigations": attributes.get("key_risk_mitigations", []),
                        "key_milestones": attributes.get("key_milestones", []),
                        "key_kpis": attributes.get("key_kpis", []),
                        "constraints": attributes.get("constraints", []),
                        "delivery_themes": attributes.get("delivery_themes", []),
                        "delivery_approaches": attributes.get("delivery_approaches", []),
                        "delivery_success_criteria": attributes.get("delivery_success_criteria", []),
                        "delivery_narrative": attributes.get("delivery_narrative", ""),
                        "strategic_focus": attributes.get("strategic_focus", ""),
                        "maturity_level": attributes.get("maturity_level", ""),
                        "implementation_complexity": attributes.get("implementation_complexity", ""),
                        "governance_model": attributes.get("governance_model", ""),
                    }
                    
                    patterns_list.append(pattern_dict)
        
        return patterns_list
        
    except Exception as e:
        appLogger.error({
            "event": "get_project_patterns_from_graph",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def get_project_templates_from_graph(
    graph_connector: GraphConnector,
    tenant_id: int,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Retrieve ProjectTemplate vertices from TigerGraph.
    
    ProjectTemplates are reusable project execution workflows that can guide
    new project creation with best practices.
    
    Args:
        graph_connector: Connected GraphConnector instance
        tenant_id: REQUIRED tenant ID for filtering
        limit: Maximum number of templates to retrieve
        
    Returns:
        List of project templates with their metadata (filtered by tenant_id)
    """
    if not tenant_id:
        raise ValueError("tenant_id is REQUIRED for get_project_templates_from_graph")
    
    try:
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_project_templates_from_graph",
                "error": "Failed to connect to graph",
                "tenant_id": tenant_id
            })
            return []
        
        # Fetch ProjectTemplate vertices (filtered by tenant_id)
        templates = graph_connector.get_vertices("ProjectTemplate", tenant_id=tenant_id, limit=limit)
        
        appLogger.info({
            "event": "get_project_templates_from_graph",
            "vertex_type": "ProjectTemplate",
            "tenant_id": tenant_id,
            "limit": limit,
            "templates_retrieved": len(templates) if templates else 0
        })
        
        templates_list = []
        
        # getVertices returns a list of vertex dicts
        if isinstance(templates, list):
            for template_vertex in templates:
                if isinstance(template_vertex, dict):
                    # Extract vertex ID and attributes
                    template_id = template_vertex.get("v_id", "")
                    attributes = template_vertex.get("attributes", {})
                    
                    template_dict = {
                        "id": template_id,
                        "name": attributes.get("name", ""),
                        "title": attributes.get("title", ""),
                        "description": attributes.get("description", ""),
                        "project_type": attributes.get("project_type", ""),
                        "sdlc_method": attributes.get("sdlc_method", ""),
                        "state": attributes.get("state", ""),
                        "project_category": attributes.get("project_category", ""),
                        "objectives": attributes.get("objectives", []),
                        "org_strategy_align": attributes.get("org_strategy_align", ""),
                        "delivery_status": attributes.get("delivery_status", ""),
                        "scope_status": attributes.get("scope_status", ""),
                        "spend_status": attributes.get("spend_status", ""),
                        "start_date": attributes.get("start_date", ""),
                        "end_date": attributes.get("end_date", ""),
                        "total_external_spend": attributes.get("total_external_spend", 0.0),
                    }
                    
                    templates_list.append(template_dict)
        
        return templates_list
        
    except Exception as e:
        appLogger.error({
            "event": "get_project_templates_from_graph",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def match_project_patterns(
    project_name: str,
    project_description: str,
    patterns: List[Dict[str, Any]],
    llm: Optional[ChatGPTClient] = None
) -> Dict[str, Any]:
    """
    Use LLM to match a project against available patterns from TigerGraph.
    
    Args:
        project_name: Name of the project
        project_description: Description of the project
        patterns: List of ProjectPattern vertices from TigerGraph to match against
        llm: Optional LLM client (creates one if not provided)
        
    Returns:
        Matched pattern with confidence score
    """
    if not patterns:
        return {
            "matched_pattern_index": None,
            "confidence_score": 0.0,
            "message": "No patterns available for matching"
        }
    
    if llm is None:
        llm = ChatGPTClient()
    
    try:
        # Format patterns for LLM analysis with indexes
        patterns_with_index = []
        for idx, p in enumerate(patterns[:10]):  # Limit to 10 patterns for LLM processing
            patterns_with_index.append({
                "index": idx,
                "name": p.get("name", ""),
                "description": p.get("description", ""),
                "explanation": p.get("explanation", ""),
                "category": p.get("category", ""),
                "scope": p.get("scope", ""),
                "confidence_score": p.get("confidence_score", 0.0),
                "support_score": p.get("support_score", 0.0),
                "delivery_themes": p.get("delivery_themes", []),
                "delivery_approaches": p.get("delivery_approaches", []),
                "delivery_narrative": p.get("delivery_narrative", "")[:300],
                "key_kpis": p.get("key_kpis", []),
                "key_milestones": p.get("key_milestones", []),
                "common_sdlc_methods": p.get("common_sdlc_methods", []),
                "common_project_types": p.get("common_project_types", []),
                "team_composition": p.get("team_composition", [])
            })
        
        patterns_str = json.dumps(patterns_with_index, indent=2)
        
        project_str = json.dumps({
            "name": project_name,
            "description": project_description
        })
        
        system_prompt = """
        You are an expert project management advisor. Your task is to match a given project 
        against a list of PATTERNS from our knowledge base and identify the most similar one.
        
        These patterns are ProjectPattern vertices in TigerGraph that represent
        common execution patterns across multiple successful projects.
        
        Consider:
        - Semantic similarity in name and description
        - Matching category and project type
        - Relevance of delivery themes and approaches
        - Alignment with KPIs and milestones
        - Applicable SDLC methodology
        - Pattern confidence and support scores (higher is better)
        
        Return a JSON object with:
        - matched_pattern_index: INDEX (0, 1, 2, etc.) of the best matching pattern, or null if no good match
        - confidence_score: 0.0-1.0 confidence in the match
        - reasoning: Brief explanation of why this pattern was selected
        - similarity_factors: List of factors that contribute to the match
        
        If no good match exists (confidence < 0.4), set matched_pattern_index to null.
        """
        
        user_prompt = f"""
        Match this new project against the existing patterns in our knowledge base:
        
        INPUT PROJECT:
        {project_str}
        
        AVAILABLE PATTERNS FROM KNOWLEDGE BASE:
        {patterns_str}
        
        Return as JSON:
        {{
            "matched_pattern_index": 0-9 or null,
            "confidence_score": 0.0-1.0,
            "reasoning": "explanation",
            "similarity_factors": ["factor1", "factor2", ...]
        }}
        """
        
        chat_completion = ChatCompletion(
            system=system_prompt,
            prev=[],
            user=user_prompt
        )
        
        model_options = ModelOptions(model="gpt-4o", max_tokens=500, temperature=0.3)
        response = llm.run(chat_completion, model_options, "match_project_patterns")
        
        # Parse LLM response
        match_result = extract_json_after_llm(response)
        
        if match_result:
            return {
                "matched_pattern_index": match_result.get("matched_pattern_index"),
                "confidence_score": match_result.get("confidence_score", 0.0),
                "reasoning": match_result.get("reasoning", ""),
                "similarity_factors": match_result.get("similarity_factors", [])
            }
        else:
            return {
                "matched_pattern_index": None,
                "confidence_score": 0.0,
                "message": "Failed to parse LLM response"
            }
            
    except Exception as e:
        appLogger.error({
            "event": "match_project_patterns",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return {
            "matched_pattern_index": None,
            "confidence_score": 0.0,
            "message": str(e)
        }


def get_templates_for_pattern(
    graph_connector: GraphConnector,
    pattern_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieve ProjectTemplate vertices connected to a pattern via the
    supportedByProjectTemplate edge in TigerGraph.
    
    This uses the graph edge relationship rather than a template_id attribute,
    as defined in trmeric_schema.py:
    - supportedByProjectTemplate: FROM ProjectPattern TO ProjectTemplate
    
    Args:
        graph_connector: Connected GraphConnector instance
        pattern_id: The ID of the ProjectPattern vertex
        
    Returns:
        List of project templates connected to this pattern
    """
    if not pattern_id:
        return []
    
    try:
        if not graph_connector.ensure_connected():
            appLogger.error({
                "event": "get_templates_for_pattern",
                "error": "Failed to connect to graph"
            })
            return []
        
        # Use getEdges to traverse the supportedByProjectTemplate edge
        # from the pattern to find connected templates
        edges = graph_connector.get_edges(
            sourceVertexType="ProjectPattern",
            sourceVertexId=pattern_id,
            edgeType="supportedByProjectTemplate"
        )
        
        appLogger.info({
            "event": "get_templates_for_pattern",
            "pattern_id": pattern_id,
            "edge_type": "supportedByProjectTemplate",
            "edges_found": len(edges) if edges else 0
        })
        
        if not edges:
            return []
        
        templates_list = []
        
        # Extract target template IDs from edges and fetch full template data
        for edge in edges:
            if isinstance(edge, dict):
                # Get the target vertex ID (the template)
                target_id = edge.get("to_id") or edge.get("t_id")
                if target_id:
                    # Fetch the full template vertex
                    try:
                        template_vertex = graph_connector.get_vertices_by_id(
                            "ProjectTemplate",
                            [target_id]
                        )
                        
                        if template_vertex and isinstance(template_vertex, list) and len(template_vertex) > 0:
                            tv = template_vertex[0]
                            if isinstance(tv, dict):
                                attributes = tv.get("attributes", {})
                                templates_list.append({
                                    "id": target_id,
                                    "name": attributes.get("name", ""),
                                    "title": attributes.get("title", ""),
                                    "description": attributes.get("description", ""),
                                    "project_type": attributes.get("project_type", ""),
                                    "sdlc_method": attributes.get("sdlc_method", ""),
                                    "state": attributes.get("state", ""),
                                    "project_category": attributes.get("project_category", ""),
                                    "objectives": attributes.get("objectives", []),
                                    "org_strategy_align": attributes.get("org_strategy_align", ""),
                                    "delivery_status": attributes.get("delivery_status", ""),
                                    "scope_status": attributes.get("scope_status", ""),
                                    "spend_status": attributes.get("spend_status", ""),
                                    "start_date": attributes.get("start_date", ""),
                                    "end_date": attributes.get("end_date", ""),
                                    "total_external_spend": attributes.get("total_external_spend", 0.0),
                                })
                    except Exception as e:
                        appLogger.warning({
                            "event": "get_templates_for_pattern",
                            "template_id": target_id,
                            "error": str(e)
                        })
                        continue
        
        appLogger.info({
            "event": "get_templates_for_pattern",
            "pattern_id": pattern_id,
            "templates_retrieved": len(templates_list)
        })
        
        return templates_list
        
    except Exception as e:
        appLogger.error({
            "event": "get_templates_for_pattern",
            "pattern_id": pattern_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return []


def infer_project(
    project_name: str,
    project_description: str,
    tenant_id: int,
    is_provider: bool = False,
    model_options: Optional[ModelOptions] = None,
    graph_connector: Optional[GraphConnector] = None,
    graphname: str = "",
) -> Dict[str, Any]:
    """
    Generate project creation guidance using LLM pattern matching.
    
    This is the main entry point for project inference. It:
    1. Retrieves project patterns and templates from the graph
    2. Uses LLM to match the input project against these patterns
    3. Returns guidance with best practices and recommendations
    
    Args:
        project_name: Name of the project being created
        project_description: Description of the project
        tenant_id: Tenant ID for access control
        is_provider: Whether this is a provider project
        model_options: LLM model configuration
        graph_connector: GraphConnector instance (creates new one if not provided)
        graphname: Graph name to use (required if graph_connector not provided)
        
    Returns:
        Dictionary containing:
        - matching_patterns: Relevant patterns for this project
        - matching_templates: Relevant templates for this project
        - inference_guidance: LLM-generated guidance text
        - recommended_sdlc: Recommended SDLC methodology
        - recommended_type: Recommended project type
        - estimated_duration: Estimated project duration
        - key_risk_areas: Identified risk areas
        - success_factors: Critical success factors
        - team_composition: Recommended team structure
        - delivery_themes: Key delivery themes from patterns
        - delivery_approaches: Proven delivery approaches
        - delivery_success_criteria: Success criteria
    """
    result = {
        "project_name": project_name,
        "project_description": project_description,
        "matching_patterns": [],
        "matching_templates": [],
        "match_info": {},  # Pattern matching details (confidence, reasoning, similarity_factors)
        "inference_guidance": "",
        "recommended_sdlc": "",
        "recommended_type": "",
        "estimated_duration": "",
        "key_risk_areas": [],
        "success_factors": [],
        "team_composition": [],
        "delivery_themes": [],
        "delivery_approaches": [],
        "delivery_success_criteria": [],
    }
    
    try:
        # Initialize graph connector if not provided
        if graph_connector is None:
            # Derive environment-aware graphname if not provided
            if not graphname:
                env = os.getenv("ENVIRONMENT", None)
                if env and (env == "dev" or env == "qa" or env == "prod"):
                    graphname = f"g_{env}_{tenant_id}"
                else:
                    graphname = None
            config = GraphConnectorConfig.from_env(graphname)
            graph_connector = GraphConnector(config)
        
        # Retrieve patterns from graph
        patterns = get_project_patterns_from_graph(graph_connector, tenant_id=tenant_id, limit=10)
        
        if not patterns:
            appLogger.info({
                "event": "infer_project",
                "status": "no_patterns_found",
                "project_name": project_name
            })
            return result
        
        # Step 1: Match patterns to find the best one
        llm = ChatGPTClient()
        if model_options is None:
            model_options = ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.3)
        
        match_result = match_project_patterns(project_name, project_description, patterns, llm)
        
        # Step 2: Extract matched pattern
        matched_pattern_index = match_result.get("matched_pattern_index")
        confidence_score = match_result.get("confidence_score", 0.0)
        
        matched_pattern = None
        if matched_pattern_index is not None and confidence_score >= 0.3:
            if isinstance(matched_pattern_index, int) and 0 <= matched_pattern_index < len(patterns):
                matched_pattern = patterns[matched_pattern_index]
        
        if not matched_pattern:
            appLogger.warning({
                "event": "infer_project",
                "status": "no_pattern_match",
                "project_name": project_name,
                "confidence": confidence_score
            })
            return result
        
        # Step 3: Use only the matched pattern for template retrieval and guidance
        result["matching_patterns"] = [matched_pattern]
        
        # Add match info for consistency with roadmap_inference
        result["match_info"] = {
            "confidence_score": confidence_score,
            "reasoning": match_result.get("reasoning", ""),
            "similarity_factors": match_result.get("similarity_factors", [])
        }
        
        # Fetch templates associated with the matched pattern via graph edge
        # Uses supportedByProjectTemplate edge: ProjectPattern -> ProjectTemplate
        templates = get_templates_for_pattern(graph_connector, matched_pattern.get("id"))
        result["matching_templates"] = templates
        
        prompt_text = _build_project_inference_prompt(
            project_name=project_name,
            project_description=project_description,
            patterns=[matched_pattern],  # Only pass the matched pattern
            templates=templates,
            is_provider=is_provider,
            confidence_score=confidence_score,
            match_reasoning=match_result.get("reasoning", "")
        )
        
        # Call LLM to generate guidance
        # Create ChatCompletion for guidance generation
        guidance_chat = ChatCompletion(
            system="You are an expert project management advisor providing actionable guidance based on pattern matching.",
            prev=[],
            user=prompt_text
        )
        
        response = llm.run(
            guidance_chat,
            model_options,
            "project_inference::infer_project"
        )
        
        # Extract guidance from LLM response
        guidance_json = extract_json_after_llm(response)
        
        appLogger.info({
            "event": "infer_project_llm_response",
            "response_length": len(response),
            "parsed_json_type": str(type(guidance_json)),
            "has_guidance": bool(guidance_json and guidance_json.get("guidance"))
        })
        
        # Extract project names from pattern for pattern_reference
        project_names = []
        pattern_name = ""
        pattern_id = ""
        if matched_pattern:
            project_ids = matched_pattern.get("project_ids", [])
            project_names = [f"Project {pid}" for pid in project_ids]
            pattern_name = matched_pattern.get("name", "")
            pattern_id = matched_pattern.get("id", "")
        
        # Populate results from guidance
        if guidance_json and isinstance(guidance_json, dict):
            result["inference_guidance"] = guidance_json.get("guidance", "")
            result["recommended_sdlc"] = guidance_json.get("recommended_sdlc", "")
            result["recommended_type"] = guidance_json.get("recommended_project_type", "")
            result["estimated_duration"] = guidance_json.get("estimated_duration", "")
            result["key_risk_areas"] = guidance_json.get("key_risk_areas", [])
            result["success_factors"] = guidance_json.get("success_factors", [])
            result["team_composition"] = guidance_json.get("recommended_team_composition", [])
            result["delivery_themes"] = guidance_json.get("delivery_themes", [])
            result["delivery_approaches"] = guidance_json.get("delivery_approaches", [])
            result["delivery_success_criteria"] = guidance_json.get("delivery_success_criteria", [])
            # Add dimension_guidance (similar to roadmap_inference structure)
            result["dimension_guidance"] = guidance_json.get("dimension_guidance", {})
        
        # Add pattern_reference (similar to roadmap_inference structure)
        result["pattern_reference"] = {
            "pattern_id": pattern_id,
            "pattern_name": pattern_name,
            "project_count": len(project_names),
            "project_names": project_names,
            "project_ids": matched_pattern.get("project_ids", []) if matched_pattern else []
        }
        
        appLogger.info({
            "event": "infer_project",
            "status": "success",
            "project_name": project_name,
            "patterns_matched": len(patterns),
            "templates_matched": len(templates)
        })
        
    except Exception as e:
        appLogger.error({
            "event": "infer_project",
            "error": str(e),
            "traceback": traceback.format_exc()
        })
    
    return result


def _build_project_inference_prompt(
    project_name: str,
    project_description: str,
    patterns: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
    is_provider: bool,
    confidence_score: float = 0.0,
    match_reasoning: str = ""
) -> str:
    """
    Build the LLM prompt for project pattern matching and inference.
    
    Uses similar structure to roadmap inference but adapted for project attributes:
    - SDLC methodology instead of roadmap type
    - Delivery status/scope/spend status instead of solution
    - Project-specific success criteria
    
    Args:
        project_name: Name of the project
        project_description: Description of the project
        patterns: List containing the matched pattern(s)
        templates: List of templates associated with the pattern
        is_provider: Whether this is a provider project
        confidence_score: Confidence of the pattern match (0.0-1.0)
        match_reasoning: Reasoning for why this pattern was matched
    """
    
    # Format the matched pattern for the prompt
    patterns_section = ""
    project_names = []
    project_names_str = "N/A"
    if patterns:
        pattern = patterns[0]  # We only have one matched pattern
        project_ids = pattern.get('project_ids', [])
        project_names = [f"Project {pid}" for pid in project_ids]
        project_names_str = ", ".join(project_names) if project_names else "N/A"
        
        patterns_section = f"""## MATCHED PATTERN

**Pattern Name:** {pattern.get('name', 'Unknown')}

**Match Confidence:** {confidence_score*100:.1f}%

**Match Reasoning:** {match_reasoning}

**Based on Projects:** {project_names_str}

**Pattern Details:**
- Category: {pattern.get('category', 'N/A')}
- Explanation: {pattern.get('explanation', 'N/A')[:500]}
- SDLC Methods Used: {', '.join(pattern.get('dev_methodology_dist', []))}
- Average Duration: {pattern.get('avg_project_duration', 'N/A')} days
- Budget Band: {pattern.get('budget_band', 'N/A')}
- Delivery Themes: {', '.join(pattern.get('delivery_themes', [])[:5])}
- Key Success Criteria: {', '.join(pattern.get('delivery_success_criteria', [])[:5])}
- Work Type Distribution: {', '.join(pattern.get('work_type_distribution', [])[:3])}
- Team Composition: {', '.join(pattern.get('team_composition', [])[:3])}
- Key Technologies: {', '.join(pattern.get('key_technologies', [])[:5])}
- Key Milestones: {', '.join(str(m) for m in pattern.get('key_milestones', [])[:5])}
- Key KPIs: {', '.join(pattern.get('key_kpis', [])[:5])}
- Key Risk Mitigations: {', '.join(pattern.get('key_risk_mitigations', [])[:3])}
- Strategic Focus: {pattern.get('strategic_focus', 'N/A')}
- Maturity Level: {pattern.get('maturity_level', 'N/A')}
- Implementation Complexity: {pattern.get('implementation_complexity', 'N/A')}
- Governance Model: {pattern.get('governance_model', 'N/A')}
"""
    
    # Format templates for the prompt
    templates_section = ""
    if templates:
        templates_section = "## SUPPORTING TEMPLATES\n\n"
        for i, template in enumerate(templates, 1):
            templates_section += f"""**Template {i}: {template.get('title', template.get('name', 'Unknown'))}**
- Project Type: {template.get('project_type', 'N/A')}
- SDLC Method: {template.get('sdlc_method', 'N/A')}
- State: {template.get('state', 'N/A')}
- Category: {template.get('project_category', 'N/A')}
- Objectives: {template.get('objectives', 'N/A')}
- Delivery Status Pattern: {template.get('delivery_status', 'N/A')}
- Scope Status: {template.get('scope_status', 'N/A')}
- Spend Status: {template.get('spend_status', 'N/A')}

"""
    
    prompt = f"""You are an expert project management and delivery advisor helping teams create well-structured projects.

## NEW PROJECT REQUEST

**Project Name:** {project_name}

**Description:** {project_description}

**Project Type:** {'Provider' if is_provider else 'Internal'}

{patterns_section}

{templates_section}

## ANALYSIS TASK

Based on the matched pattern from {project_names_str} and supporting templates, provide expert guidance on how to structure and execute this project.

CRITICAL: In ALL guidance fields, you MUST cite the specific project names: **[{project_names_str}]**

For each dimension guidance, write 2-3 concise Markdown bullet points. Each bullet must:
- Start with a **bold header** naming specific projects: **[{project_names_str}]**
- Cite specific data from the pattern
- Explain the approach or outcome in 10-20 words

Provide your analysis in the following JSON format:

{{
  "guidance": "<7-10 sentence guidance starting with 'Based on [{project_names_str}], the most effective approach...' Include specific recommendations citing the projects>",
  "recommended_sdlc": "<SDLC methodology (Agile, Waterfall, Hybrid). Cite [{project_names_str}] usage>",
  "recommended_project_type": "<Project type (Build, Run, Transform, Enhance, Optimize)>",
  "estimated_duration": "<Duration based on [{project_names_str}] average>",
  "key_risk_areas": ["<Risk with mitigation from [{project_names_str}]>", "..."],
  "success_factors": ["<Factor citing [{project_names_str}]>", "..."],
  "recommended_team_composition": ["<Role from [{project_names_str}]>", "..."],
  "delivery_themes": ["<Theme from [{project_names_str}]>", "..."],
  "delivery_approaches": ["<Approach from [{project_names_str}]>", "..."],
  "delivery_success_criteria": ["<Criterion from [{project_names_str}]>", "..."],
  "dimension_guidance": {{
    "sdlc": "**[{project_names_str}]**: <methodology used>\\n**[{project_names_str}]**: <why it worked>",
    "timeline": "**[{project_names_str}]**: <duration and phases>\\n**[{project_names_str}]**: <milestone patterns>",
    "objectives": "**[{project_names_str}]**: <key KPIs tracked>\\n**[{project_names_str}]**: <strategic focus>",
    "technology": "**[{project_names_str}]**: <key technologies used>",
    "team": "**[{project_names_str}]**: <team composition>\\n**[{project_names_str}]**: <role distribution>",
    "risks": "**[{project_names_str}]**: <key risk mitigations>\\n**[{project_names_str}]**: <governance model>"
  }}
}}

Make sure EVERY field references [{project_names_str}] explicitly."""
    
    return prompt

