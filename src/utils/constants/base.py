from typing import Dict



AUDIT_LOG_MAP: Dict[str, Dict] = {
    "id": {"table": "al", "column": "id"},
    "object_id": {"table": "al", "column": "object_id"},
    "model_name": {"table": "al", "column": "model_name"},
    "changes": {"table": "al", "column": "changes"},
    "action": {"table": "al", "column": "action"},
    "timestamp": {"table": "al", "column": "\"timestamp\""},
    "tenant_id": {"table": "al", "column": "tenant_id"},
    "user_id": {"table": "al", "column": "user_id"},
}


PORTFOLIO_ATTRIBUTE_MAP = {
    "id": {"table": "p", "column": "p.id"},
    "title": {"table": "p", "column": "p.title"},
    "industry": {"table": "p", "column": "p.industry"},
    "technology_stack": {"table": "p", "column": "p.technology_stack"},
    "description": {"table": "p", "column": "p.description"},
    "first_name": {"table": "p", "column": "p.first_name"},
    "last_name": {"table": "p", "column": "p.last_name"},
    "tagline": {"table": "p", "column": "p.tagline"},
    "business_goals": {"table": "p", "column": "p.business_goals"},

    "kpis": {
        "join": """
            LEFT JOIN projects_portfoliokpi AS k 
            ON k.portfolio_id = p.id
        """,
        "column": """
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'name', k.name,
                        'baseline_value', k.baseline_value
                    )
                ) FILTER (WHERE k.id IS NOT NULL),
                '[]'
            ) AS kpis
        """,
        "group_by": False
    },

    "budgets": {
        "join": """
            LEFT JOIN projects_portfoliobudget AS b 
            ON b.portfolio_id = p.id
        """,
        "column": """
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'value', b.value,
                        'project_type', b.project_type,
                        'start_date', b.start_date,
                        'end_date', b.end_date
                    )
                ) FILTER (WHERE b.id IS NOT NULL),
                '[]'
            ) AS budgets
        """,
        "group_by": False
    },

    "sponsors": {
        "join": """
            LEFT JOIN projects_portfoliobusiness AS s 
            ON s.portfolio_id = p.id
        """,
        "column": """
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'first_name', s.sponsor_first_name,
                        'last_name', s.sponsor_last_name,
                        'role', s.sponsor_role,
                        'bu_name', s.bu_name
                    )
                ) FILTER (WHERE s.id IS NOT NULL),
                '[]'
            ) AS sponsors
        """,
        "group_by": False
    },

    "strategic_priorities": {
        "join": """
            LEFT JOIN projects_portfolioorgstrategyalign AS pps 
            ON pps.portfolio_id = p.id
        """,
        "column": """
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'title', pps.title
                    )
                ) FILTER (WHERE pps.id IS NOT NULL),
                '[]'
            ) AS strategic_priorities
        """,
        "group_by": False
    },

}



def roadmap_type_mapping(type, reverse=False):
    """
    Maps roadmap type integers to strings or vice versa based on reverse flag.
    """
    mapping = {
        1: "Project",
        2: "Program",
        3: "Enhancement",
        4: "New Development",
        5: "Enhancements or Upgrade",
        6: "Consume a Service",
        7: "Support a Pursuit",
        8: "Acquisition",
        9: "Global Product Adoption",
        10: "Innovation Request for NITRO",
        11: "Regional Product Adoption",
        12: "Client Deployment",
        
        #for BHP tenant_id: 232 in QA
        13: "Defect",
        14: "Change",
        15: "Epic",
        16: "Feature",
        17: "Story"
    }
    
    if reverse:
        # Case-insensitive reverse lookup
        type = type.lower() if isinstance(type, str) else type
        reverse_mapping = {v.lower(): k for k, v in mapping.items()}
        return reverse_mapping.get(type) or 1
    else:
        # Forward lookup
        if type not in mapping:
            raise ValueError(f"No roadmap type found for ID: {type}")
        return mapping.get(type,"Project") or "Project"
    
    
def roadmap_constraint_type(type: str,reverse = False):
    mapping = {
        1: "Cost",
        2: "Resource",
        3: "Risk",
        4: "Scope",
        5: "Quality",
        6: "Time"
    }
    if reverse:
        type = type.lower()
        reverse_mapping = {v.lower(): k for k,v in mapping.items()}
        return reverse_mapping.get(type) or 1
    else:
        if type not in mapping:
            raise ValueError(f"No constraint type found: {type}")
        return mapping.get(type,"Cost") or "None"



def roadmap_state_mapping(value: int) -> str:
    mapping = {
        0: "Intake",
        1: "Approved",
        2: "Execution",
        3: "Archived",
        4: "Elaboration",
        5: "Solutioning",
        6: "Prioritize",
        99: "Hold",
        100: "Rejected",
        999: "Cancelled",
        200: "Draft",
    }
    return mapping.get(value, "Unknown") or 'Unknown'