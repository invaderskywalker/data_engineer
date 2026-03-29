from src.trmeric_services.tango.functions.Types import TangoFunction
from src.database.Database import db_instance
from datetime import datetime
import json
import re

def infer_category(key_results, value_realized):
    """Infer project/roadmap category based on Key Results and Business Value."""
    key_results_str = " ".join(key_results).lower() if key_results else ""

    # Handle value_realized based on its type
    if isinstance(value_realized, list):
        value_strings = []
        for item in value_realized:
            if isinstance(item, dict):
                value_strings.append(item.get('description', str(item)))
            else:
                value_strings.append(str(item))
        value_realized_str = " ".join(value_strings).lower()
    elif isinstance(value_realized, str):
        value_realized_str = value_realized.lower()
    else:
        value_realized_str = ""

    combined_text = f"{key_results_str} {value_realized_str}"

    revenue_keywords = r"revenue|sales|income|stream|profit|market|share|growth"
    cost_keywords = r"cost|saving|efficiency|optimization|streamline|reduce|operational"
    risk_keywords = r"compliance|security|risk|continuity|safety|audit|regulatory"
    customer_keywords = r"customer|satisfaction|retention|acquisition|nps|experience|loyalty"

    if re.search(revenue_keywords, combined_text):
        return "Revenue Impact"
    elif re.search(cost_keywords, combined_text):
        return "Cost Efficiency"
    elif re.search(risk_keywords, combined_text):
        return "Risk Mitigation"
    elif re.search(customer_keywords, combined_text):
        return "Customer Experience"
    else:
        return "Uncategorized"

def getCompletedProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids=None):
    portfolio_filter = ""
    if portfolio_ids:
        portfolio_ids_str = ",".join(map(str, portfolio_ids))
        portfolio_filter = f"AND wpport.portfolio_id IN ({portfolio_ids_str})"

    query = f"""
        SELECT 
            wp.id AS "Project ID",
            wp.title AS "Project Title",
            TO_CHAR(wp.archived_on, 'YYYY-MM-DD') AS "Closure Date",
            COALESCE(ARRAY_AGG(DISTINCT wpkpi.name) FILTER (WHERE wpkpi.name IS NOT NULL), ARRAY['No results provided']::text[]) AS "Key Results",
            COALESCE(wpvr.key_result_analysis::text, 'Not specified') AS "Business Value",
            COALESCE(pp.title, 'Unknown Portfolio') AS "Portfolio",
            'Completed' AS "Status"
        FROM 
            workflow_project AS wp
        LEFT JOIN 
            workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id
        LEFT JOIN 
            workflow_projectvaluerealization AS wpvr ON wpvr.project_id = wp.id
        LEFT JOIN 
            workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
        LEFT JOIN 
            projects_portfolio AS pp ON wpport.portfolio_id = pp.id
        WHERE 
            wp.tenant_id_id = {tenantID}
            AND wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
            AND wp.archived_on IS NOT NULL
            {portfolio_filter}
        GROUP BY 
            wp.id, wp.title, wp.archived_on, wpvr.key_result_analysis, pp.title
        ORDER BY 
            wp.archived_on DESC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def getOngoingProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids=None):
    portfolio_filter = ""
    if portfolio_ids:
        portfolio_ids_str = ",".join(map(str, portfolio_ids))
        portfolio_filter = f"AND wpport.portfolio_id IN ({portfolio_ids_str})"

    query = f"""
        SELECT 
            wp.id AS "Project ID",
            wp.title AS "Project Title",
            TO_CHAR(wp.created_on, 'YYYY-MM-DD') AS "Start Date",
            COALESCE(ARRAY_AGG(DISTINCT wpkpi.name) FILTER (WHERE wpkpi.name IS NOT NULL), ARRAY['No results provided']::text[]) AS "Key Results",
            COALESCE(wpvr.key_result_analysis::text, 'Not specified') AS "Business Value",
            COALESCE(pp.title, 'Unknown Portfolio') AS "Portfolio",
            'Ongoing' AS "Status"
        FROM 
            workflow_project AS wp
        LEFT JOIN 
            workflow_projectkpi AS wpkpi ON wpkpi.project_id = wp.id
        LEFT JOIN 
            workflow_projectvaluerealization AS wpvr ON wpvr.project_id = wp.id
        LEFT JOIN 
            workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
        LEFT JOIN 
            projects_portfolio AS pp ON wpport.portfolio_id = pp.id
        WHERE 
            wp.tenant_id_id = {tenantID}
            AND wp.archived_on IS NULL
            AND wp.parent_id IS NOT NULL
            {portfolio_filter}
        GROUP BY 
            wp.id, wp.title, wp.created_on, wpvr.key_result_analysis, pp.title
        ORDER BY 
            wp.created_on DESC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def getIntakeProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids=None):
    portfolio_filter = ""
    if portfolio_ids:
        portfolio_ids_str = ",".join(map(str, portfolio_ids))
        portfolio_filter = f"AND rp.portfolio_id IN ({portfolio_ids_str})"

    query = f"""
        SELECT 
            rr.title AS "Project Title",
            TO_CHAR(rr.created_on, 'YYYY-MM-DD') AS "Created Date",
            TO_CHAR(rr.budget, '$999,999,999') AS "Budget",
            COALESCE(json_agg(DISTINCT pp.title) FILTER (WHERE pp.title IS NOT NULL), '["Unknown Portfolio"]'::json) AS "Associated Portfolios",
            COALESCE(json_agg(DISTINCT rrkpi.name) FILTER (WHERE rrkpi.name IS NOT NULL), '["No results provided"]'::json) AS "Key Results",
            'Intake' AS "Status"
        FROM 
            roadmap_roadmap AS rr
        LEFT JOIN 
            roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
        LEFT JOIN 
            projects_portfolio AS pp ON rp.portfolio_id = pp.id
        LEFT JOIN 
            roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
        WHERE 
            rr.tenant_id = {tenantID}
            AND rr.created_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
            AND rr.current_state = 0
            {portfolio_filter}
        GROUP BY 
            rr.title, rr.created_on, rr.budget
        ORDER BY 
            rr.created_on DESC;
    """
    return db_instance.retrieveSQLQueryOld(query)


def getProjectStatusCounts(tenantID, last_quarter_start, last_quarter_end, portfolio_ids=None):
    portfolio_filter_completed = ""
    portfolio_filter_ongoing = ""
    portfolio_filter_intake = ""
    if portfolio_ids:
        portfolio_ids_str = ",".join(map(str, portfolio_ids))
        portfolio_filter_completed = f"AND wpport.portfolio_id IN ({portfolio_ids_str})"
        portfolio_filter_ongoing = f"AND wpport.portfolio_id IN ({portfolio_ids_str})"
        portfolio_filter_intake = f"AND rp.portfolio_id IN ({portfolio_ids_str})"

    query = f"""
        SELECT 
            'Completed Last Quarter' AS "Status",
            COUNT(DISTINCT wp.id) AS "Number of Projects",
            COALESCE(ARRAY_AGG(DISTINCT pp.title) FILTER (WHERE pp.title IS NOT NULL), ARRAY['Unknown Portfolio']::text[]) AS "Portfolios",
            COALESCE(STRING_AGG(DISTINCT wpvr.key_result_analysis::text, '; '), 'No impact specified') AS "Key Business Impact"
        FROM 
            workflow_project AS wp
        LEFT JOIN 
            workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
        LEFT JOIN 
            projects_portfolio AS pp ON wpport.portfolio_id = pp.id
        LEFT JOIN 
            workflow_projectvaluerealization AS wpvr ON wpvr.project_id = wp.id
        WHERE 
            wp.tenant_id_id = {tenantID}
            AND wp.archived_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
            AND wp.archived_on IS NOT NULL
            {portfolio_filter_completed}
        GROUP BY 1

        UNION

        SELECT 
            'In Execution' AS "Status",
            COUNT(DISTINCT wp.id) AS "Number of Projects",
            COALESCE(ARRAY_AGG(DISTINCT pp.title) FILTER (WHERE pp.title IS NOT NULL), ARRAY['Unknown Portfolio']::text[]) AS "Portfolios",
            COALESCE(STRING_AGG(DISTINCT wpvr.key_result_analysis::text, '; '), 'No impact specified') AS "Key Business Impact"
        FROM 
            workflow_project AS wp
        LEFT JOIN 
            workflow_projectportfolio AS wpport ON wp.id = wpport.project_id
        LEFT JOIN 
            projects_portfolio AS pp ON wpport.portfolio_id = pp.id
        LEFT JOIN 
            workflow_projectvaluerealization AS wpvr ON wpvr.project_id = wp.id
        WHERE 
            wp.tenant_id_id = {tenantID}
            AND wp.archived_on IS NULL
            AND wp.parent_id IS NOT NULL
            {portfolio_filter_ongoing}
        GROUP BY 1

        UNION

        SELECT 
            'Intake Projects' AS "Status",
            COUNT(DISTINCT rr.id) AS "Number of Projects",
            COALESCE(ARRAY_AGG(DISTINCT pp.title) FILTER (WHERE pp.title IS NOT NULL), ARRAY['Unknown Portfolio']::text[]) AS "Portfolios",
            COALESCE(STRING_AGG(DISTINCT rrkpi.name, '; '), 'No impact specified') AS "Key Business Impact"
        FROM 
            roadmap_roadmap AS rr
        LEFT JOIN 
            roadmap_roadmapportfolio AS rp ON rr.id = rp.roadmap_id
        LEFT JOIN 
            projects_portfolio AS pp ON rp.portfolio_id = pp.id
        LEFT JOIN 
            roadmap_roadmapkpi AS rrkpi ON rr.id = rrkpi.roadmap_id
        WHERE 
            rr.tenant_id = {tenantID}
            AND rr.created_on BETWEEN '{last_quarter_start}' AND '{last_quarter_end}'
            AND rr.current_state IN (0,1)
            {portfolio_filter_intake}
        GROUP BY 1;
    """
    return db_instance.retrieveSQLQueryOld(query)



def view_value_snapshot_last_quarter(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    last_quarter_start: str,
    last_quarter_end: str,
    portfolio_ids: list[int] = None,
    **kwargs
):
    print("in view_value_snapshot_last_quarter ", eligibleProjects, tenantID, userID, last_quarter_start, last_quarter_end, portfolio_ids)

    # Validate date parameters
    try:
        datetime.strptime(last_quarter_start, '%Y-%m-%d')
        datetime.strptime(last_quarter_end, '%Y-%m-%d')
    except ValueError:
        return "Error: last_quarter_start and last_quarter_end must be in YYYY-MM-DD format."

    # Validate portfolio_ids
    if portfolio_ids and not all(isinstance(pid, int) for pid in portfolio_ids):
        return "Error: portfolio_ids must be a list of integers."

    # Fetch data with portfolio filter
    completed_projects = getCompletedProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids)
    ongoing_projects = getOngoingProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids)
    intake_projects = getIntakeProjectsValue(tenantID, last_quarter_start, last_quarter_end, portfolio_ids)
    status_counts = getProjectStatusCounts(tenantID, last_quarter_start, last_quarter_end, portfolio_ids)

    
    # Prepare data for LLM
    categorized_data = {
        "completed_projects": completed_projects,
        "ongoing_projects": ongoing_projects,
        "intake_projects": intake_projects,
        "status_counts": status_counts,
        # "categories": categories
    }
    
    def preprocess_snapshot_data(snapshot_data):
        cleaned_data = snapshot_data.copy()
        for section in ["completed_projects", "ongoing_projects", "intake_projects"]:
            for project in cleaned_data.get(section, []):
                if project.get("Key Results") is None or not project.get("Key Results"):
                    project["Key Results"] = ["No results provided"]
                if project.get("Business Value") is None:
                    project["Business Value"] = "Not specified"
                if project.get("Portfolio") is None:
                    project["Portfolio"] = "Unknown Portfolio"
                if section == "intake_projects" and (project.get("Associated Portfolios") is None or not project.get("Associated Portfolios")):
                    project["Associated Portfolios"] = ["Unknown Portfolio"]
        for status in cleaned_data.get("status_counts", []):
            if status.get("Portfolios") is None or not status.get("Portfolios"):
                status["Portfolios"] = ["Unknown Portfolio"]
            if status.get("Key Business Impact") is None:
                status["Key Business Impact"] = "No impact specified"
        # debugLogger.info(f"Preprocessed snapshot_data: {json.dumps(cleaned_data.get('completed_projects', [])[:2], indent=2)}")
        return cleaned_data

    data = preprocess_snapshot_data(categorized_data)
    response = json.dumps(data, indent=2)
    return response

RETURN_DESCRIPTION = """
This function returns a Business Value Report in JSON format for the specified quarter, covering:
*** Business Value from completed and ongoing projects, categorized by Revenue, Cost, Risk, and Customer Experience based on inferred categories from Key Results
*** Expected value from intake projects (roadmaps), similarly categorized
*** Project status overview and executive summary
*** Filters results by portfolio_ids if provided, using the workflow_projectportfolio table for projects
Data is formatted for executive stakeholders.
"""

ARGUMENTS = [
    {
        "name": "last_quarter_start",
        "type": "str",
        "description": "Start date of the quarter in YYYY-MM-DD format.",
        "conditional": "required",
    },
    {
        "name": "last_quarter_end",
        "type": "str",
        "description": "End date of the quarter in YYYY-MM-DD format.",
        "conditional": "required",
    },
    {
        "name": "portfolio_ids",
        "type": "list[int]",
        "description": "List of portfolio IDs to filter projects and roadmaps. Optional.",
        "conditional": "optional",
    },
]

VIEW_VALUE_SNAPSHOT_LAST_QUARTER = TangoFunction(
    name="view_value_snapshot_last_quarter",
    description="""
    A function that returns a Business Value Report for the specified quarter in JSON format.
    Triggered when the question is related to value delivered or expected from completed, ongoing, and intake projects.
    Infers categories (Revenue, Cost, Risk, Customer) from Key Results and formats data for executive stakeholders.
    Supports filtering by portfolio_ids using the workflow_projectportfolio table for projects.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=view_value_snapshot_last_quarter,
    func_type="sql",
    integration="trmeric"
)



# Process data for categories
    # categories = {
    #     "Revenue Impact": {"projects": [], "summary": ""},
    #     "Cost Efficiency": {"projects": [], "summary": ""},
    #     "Risk Mitigation": {"projects": [], "summary": ""},
    #     "Customer Experience": {"projects": [], "summary": ""}
    # }

    # # Categorize completed projects
    # for project in completed_projects:
    #     category = infer_category(
    #         key_results=project.get("Key Results", []),
    #         value_realized=project.get("Business Value", "")
    #     )
    #     if category in categories:
    #         project["Status"] = "Completed"
    #         categories[category]["projects"].append(project)
    #         if project["Business Value"]:
    #             categories[category]["summary"] += f"Project {project['Project Title']} achieved {project['Business Value']}. "

    # # Categorize ongoing projects
    # for project in ongoing_projects:
    #     category = infer_category(
    #         key_results=project.get("Key Results", []),
    #         value_realized=project.get("Business Value", "")
    #     )
    #     if category in categories:
    #         project["Status"] = "Ongoing"
    #         categories[category]["projects"].append(project)

    # # Categorize intake projects
    # for roadmap in intake_projects:
    #     category = infer_category(
    #         key_results=roadmap.get("Key Results", []),
    #         value_realized=roadmap.get("Budget", "")
    #     )
    #     if category in categories:
    #         roadmap["Status"] = "Intake"
    #         categories[category]["projects"].append(roadmap)
