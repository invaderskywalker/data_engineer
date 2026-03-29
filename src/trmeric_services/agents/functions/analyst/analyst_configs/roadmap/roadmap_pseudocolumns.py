from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import RoadmapDao,PortfolioDao


# Parent Table: roadmap_roadmap
# linked tables: roadmap_roadmap
    # -annualcashinflow y
    # -category y
    # -constraints  y 
    # -estimate y
    # -kpi  y
    # -orgstrategyalign y
    # -portfolio  y
    # -scope  
    # LATER# -businessmember , # -ideamap
    

def get_roadmap_kpis(roadmap_id):
    
    result = RoadmapDao.fetchRoadmapKpis(roadmap_id)
    result_str = ""
    for i in range(len(result)):
        kpi = result[i]["name"]
        baseline_value = result[i]["baseline_value"]
        result_str += f"{i + 1}. {kpi} - Baseline Value: {baseline_value}\n"
    return result_str
    
    
def get_roadmap_scope(roadmap_id):
    
    scope = RoadmapDao.fetchRoadmapScope(roadmap_id)
    return scope
    
def get_roadmap_teams(roadmap_id):
    
    result = RoadmapDao.fetchTeamDataRoadmap(roadmap_id)
    result_str = ""
    for i in range(len(result)):
        name = result[i]["name"]
        description = result[i]["description"]
        estimate_value = result[i]["estimate_value"]
        
        result_str += f"{i + 1}. Team Member: {name} - Description: {description}, Estimate Value: {estimate_value}\n"
    return result_str    

def get_roadmap_cashflow(roadmap_id):
    
    result = RoadmapDao.fetchRoadmapCashInflow(roadmap_id)
    
    result_str = ""
    for i in range(len(result)):
        cash = result[i]["cash_inflow"]
        period = result[i]["time_period"]
        category = result[i]["category"]
        justification = result[i]["justification_text"]
        
        result_str += f"{i + 1}. Cash Flow: {category} - Amount: {cash}, Period: {period}, Justification: {justification}\n"
    return result_str
    
def get_roadmap_constraints(roadmap_id):
    
    # "tag""" "<1- Cost, 2 Resource, 3 Risk, 4 Scope, 5 Quality, 6 Time>"
    result = RoadmapDao.fetchRoadmapConstraints(roadmap_id)
    type_mapping = {
        1: "Cost",
        2: "Resource",
        3: "Risk",
        4: "Scope",
        5: "Quality",
        6: "Time"
    }
    
    result_str = ""
    for i in range(len(result)):
        description = result[i]["name"]
        type_id = result[i]["type"]
        
        type_name = type_mapping.get(type_id, "Unknown") if type_id else "N/A"
        result_str += f"{i + 1}. Constraint: {description} - Type: {type_name}\n"
        
    return result_str

def get_roadmap_orgstrategy(tenant_id):
    
    result = RoadmapDao.fetchAllOrgstategyAlignmentTitles(tenant_id)
    
    result_str = ""
    for i in range(len(result)):
        title = result[i]
        result_str += f"{i + 1}. Strategy Alignment: {title}\n"
        
    return result_str    


def get_roadmap_category(tenant_id):
    
    result = RoadmapDao.fetchRoadmapCategory(tenant_id)
    
    result_str = ""
    for i in range(len(result)):
        name = result[i]["title"]
        result_str += f"{i + 1}. Category: {name}\n"
    return result_str    

    
    
    

PSEUDO_COLUMNS = [
    {"name": "key performance indicators", "type": "list", "description": "list of strings of the KPIs for a roadmap with their baseline values. KPIs are also called key results", "pseudocolumn": True, "params": [("roadmap_id", "id")], "function": get_roadmap_kpis},
    {"name": "scope", "type": "list", "description": "detailed scope indicators of roadmap","pseudocolumn": True, "params": [("roadmap_id", "id")], "function": get_roadmap_scope},
    {"name": "team details", "type": "list", "description": "list of strings representing the teams and its member details of roadmap","pseudocolumn": True, "params": [("roadmap_id", "id")], "function": get_roadmap_teams},
    {"name": "cash inflow", "type": "list", "description": "list of cash inflow details of roadmap","pseudocolumn": True, "params": [("roadmap_id", "id")], "function": get_roadmap_cashflow},
    {"name": "constraints", "type": "list", "description": "list of constraints of roadmap","pseudocolumn": True, "params": [("roadmap_id", "id")], "function": get_roadmap_constraints},
    {"name": "organization strategy alignments", "type": "list","description": "list of strings of the org strategy aligns of a roadmap.","pseudocolumn": True, "params": [("tenant_id", "tenant_id")], "function": get_roadmap_orgstrategy},
    {"name": "category", "type": "list", "description": "list of categories of roadmap","pseudocolumn": True, "params": [("tenant_id", "tenant_id")], "function": get_roadmap_category},
]