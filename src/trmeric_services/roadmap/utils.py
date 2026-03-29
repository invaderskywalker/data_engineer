from bs4 import BeautifulSoup
from datetime import datetime
from src.trmeric_database.dao import TenantDao
from src.trmeric_utils.helper.common import allowed_tenants

DEMAND_CATEGORY_TENANTS = allowed_tenants(dev=[776],qa=[237],prod=[227])

def portfolio_role_grp_fxn(bench_by_portfolio_dict:dict, roadmap_portfolios_lower:list,bench_by_portfolio:list):
    """
    Group roles by portfolio from the given list of roles with portfolio information.
    """
    similar_portfolios_roles = {}
    different_portfolios_roles = {}
    for portfolio_lower, role_list in bench_by_portfolio_dict.items():
        # Check if this portfolio matches any roadmap portfolio (exact or substring)
        is_similar = (
            portfolio_lower in roadmap_portfolios_lower or
            any(rp in portfolio_lower or portfolio_lower in rp for rp in roadmap_portfolios_lower)
        )
        
        if is_similar:
            original_portfolio_name = next(
                row['portfolio'] or 'Unassigned' 
                for row in bench_by_portfolio 
                if (row['portfolio'] or 'Unassigned').lower().strip() == portfolio_lower
            )
            similar_portfolios_roles[original_portfolio_name] = role_list
        else:
            original_portfolio_name = next(
                row['portfolio'] or 'Unassigned' 
                for row in bench_by_portfolio 
                if (row['portfolio'] or 'Unassigned').lower().strip() == portfolio_lower
            )
            different_portfolios_roles[original_portfolio_name] = role_list
    
    return similar_portfolios_roles, different_portfolios_roles


def compute_demand_estimation_inputs(tenant_id: int,roadmap_id: int,roadmap_start_date: str,roadmap_end_date:str,roadmap_portfolios: list[str]):
    try:
        print("--debug in compute_demand_estimation_inputs---", tenant_id,"roadmap_id:", roadmap_id,
            " timeline: ", roadmap_start_date, " to ", roadmap_end_date," portfolios:", roadmap_portfolios)

        # 1. Total bench strength per role + portfolio
        bench_by_portfolio = TenantDao.getTotalRoleCountByPortfolio(tenant_id)
        print("\n\n--debug in bench_by_portfolio---", bench_by_portfolio[:2])
        # 2. All current allocations with timelines (excluding current roadmap)
        allocations = TenantDao.getAllRoadmapsEstimationDetailsForTenant(tenant_id, exclude_roadmap_id=roadmap_id)

        # print("\n\n--debug in demandallocations---", allocations[:2])

        total_bench = {}  # role -> total count
        bench_by_portfolio_dict = {}  # portfolio_lower -> [ {role, count} ]

        for row in bench_by_portfolio:
            role = row['role']
            portfolio = row['portfolio'] or 'Unassigned'
            count = row.get('headcount',0) or 0
            country = row.get("country",None) or None
            
            total_bench[role] = total_bench.get(role, 0) + count
            
            pl = portfolio.lower().strip()
            if pl not in bench_by_portfolio_dict:
                bench_by_portfolio_dict[pl] = []

            # bench_by_portfolio_dict[pl].append({"role": role, "count": count, "country": country})
            item = {"role": role, "count": count}
            if country is not None and str(country).strip() not in ['', 'None', 'null']:
                item["country"] = str(country).strip()

            bench_by_portfolio_dict[pl].append(item)

        # 3. Compute truly available roles for THIS timeline
        demand_start = datetime.strptime(roadmap_start_date, "%Y-%m-%d")
        demand_end = datetime.strptime(roadmap_end_date, "%Y-%m-%d")

        print("\n\n--debug demand timeline---", demand_start, " to ", demand_end)
        truly_available = {}
        blocked_breakdown = {}  # role -> list of conflicting demands (optional)

        for role in total_bench:
            total = total_bench[role]
            blocked = 0

            for alloc in allocations:
                if alloc['role'] != role:
                    continue
                alloc_start = datetime.strptime(alloc['start_date'], "%Y-%m-%d")
                alloc_end = datetime.strptime(alloc['end_date'], "%Y-%m-%d")

                # Overlap check
                if demand_start < alloc_end and demand_end > alloc_start:
                    blocked += alloc['allocated_count']

            available = max(0, total - blocked)
            truly_available[role] = available

            if blocked > 0:
                blocked_breakdown[role] = blocked

        # 4. Split bench into same vs different portfolio
        roadmap_portfolios_lower = [p.lower() for p in (roadmap_portfolios or []) if p]
        print("\n\n--debug roadmap_portfolios_lower---", roadmap_portfolios_lower)
       
        roles_in_similar_portfolio, roles_outside_portfolio = portfolio_role_grp_fxn(
            bench_by_portfolio_dict,roadmap_portfolios_lower,bench_by_portfolio
        )
        result ={
            # "total_bench_strength": total_bench,
            "truly_available_roles": truly_available,                    
            # "blocked_due_to_timeline_overlap": blocked_breakdown,
            
            "roles_in_similar_portfolio": roles_in_similar_portfolio,    
            "roles_in_different_portfolio": roles_outside_portfolio,    
        }
        # save_as_json(result,f"demandestimation_{roadmap_id}.json")
        return result
    except Exception as e:
        print("--debug ERROR!!!!!!! in compute_demand_estimation_inputs---", str(e))
        return {}







def extract_text_from_html(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)

def parse_roadmap_details(roadmap_details: dict) -> dict:

    """Strips HTML from scope & solution fields and extracts structured information."""
    if not roadmap_details:
        return {}

    result = {}
    raw = roadmap_details.copy()
    try:
        for k,v in raw.items():
            if isinstance(v, str):
                v = v.strip()
            if v in ["", None,' ']:
                continue
            result[k] = v

        scope_html_list: list[str] = raw.get("scope", [])
        scope_html = scope_html_list[0] if scope_html_list else ""
        if scope_html:
            result["scope"] = extract_text_from_html(scope_html)

        solution_html: str = raw.get("solution", "")
        if solution_html:
            result["solution"] = extract_text_from_html(solution_html)

        result = {k: v for k, v in result.items() if v not in ["", None, [], {},[None]]}
        return result
    except Exception as e:
        print("--debug error in parse_roadmap_details", str(e))
        return roadmap_details



def parse_auditlog_response(data):
  #check for duplicate header entries & sort by time desc
  unique_headers = set()
  logs = []
  for entry in data:
      header = entry.get('header','') or None
      if header and header.lower() not in unique_headers:
          unique_headers.add(header.lower())
          logs.append(entry)

  logs = sorted(logs, key=lambda x: datetime.fromisoformat(x.get('time','')),reverse=True)
  return logs



def format_json_for_roadmap(canvas_result, roles_result,budget, team):
        """Format the combined results into the required JSON structure."""
        
        #team & budget: combined labor and non-labor
        
        # Canvas data
        roadmap_name = canvas_result.get("roadmap_name", "")
        description = canvas_result.get("description", "")
        objectives = canvas_result.get("objectives", "")
        scope_item = canvas_result.get("scope_item", [])
        start_date = canvas_result.get("start_date", "")
        end_date = canvas_result.get("end_date", "")
        min_time_value = canvas_result.get("min_time_value", 0)
        min_time_value_type = canvas_result.get("min_time_value_type", 1)
        key_results = canvas_result.get("key_results", [])
        constraints = canvas_result.get("constraints", [])
        # non_labour_team = canvas_result.get("non_labour_team", [])
        roadmap_category = canvas_result.get("roadmap_category", [])
        org_strategy_align = canvas_result.get("org_strategy_align", [])
        portfolio = canvas_result.get("portfolio", [])
        last_updated = canvas_result.get("last_updated", "")

        # Thought processes from canvas
        thought_process_objectives = canvas_result.get("thought_process_behind_objectives", "")
        thought_process_scope = canvas_result.get("thought_process_behind_scope", "")
        thought_process_key_results = canvas_result.get("thought_process_behind_key_results", "")
        thought_process_timeline = canvas_result.get("thought_process_behind_timeline", "")
        thought_process_non_labor = canvas_result.get("thought_process_behind_non_labor_team", "")
        thought_process_portfolio = canvas_result.get("thought_process_behind_portfolio", "")
        thought_process_constraints = canvas_result.get("thought_process_behind_constraints", "")
        thought_process_behind_org_strategy_align = canvas_result.get("thought_process_behind_org_strategy_align", "")
        thought_process_category = canvas_result.get("thought_process_behind_roadmap_category", "")

        # Roles data
        # suggested_roles = roles_result.get("suggested_roles", [])
        # processed_roles = roles_result.get("processed_roles", [])
        roadmap_role_thought = roles_result.get("roadmap_role_thought", "")

        # Tango analysis
        tango_analysis = {
            "thought_process_behind_labor_team": roadmap_role_thought,
            "thought_process_behind_non_labor_team": thought_process_non_labor,
            "thought_process_behind_timeline": thought_process_timeline,
            "thought_process_behind_objectives": thought_process_objectives,
            "thought_process_behind_scope": thought_process_scope,
            "thought_process_behind_key_results": thought_process_key_results,
            "thought_process_behind_portfolio": thought_process_portfolio,
            "thought_process_behind_constraints": thought_process_constraints,
            "thought_process_behind_org_strategy_align": thought_process_behind_org_strategy_align,
            "thought_process_behind_category": thought_process_category
        }

        return {
            "title": roadmap_name,
            "description": description,
            "objectives": objectives,
            "scope": scope_item,
            # "type": "Roadmap",
            # "priority": "High",
            "start_date": start_date,
            "end_date": end_date,
            "budget": budget,
            "min_time_value": min_time_value,
            "min_time_value_type": min_time_value_type,
            "kpi": key_results,
            "constraints": constraints,
            "team": team,
            "portfolio_list": portfolio,
            "category": roadmap_category,
            "org_strategy_align": org_strategy_align,
            # "business_case": None,
            "tango_analysis": tango_analysis,
            "last_updated": last_updated
        }

          
    
    


EY_SHEET_DATA = {
    
  "Area/Region": {
    "Americas": ["BBC"],
    "Asia-Pacific": ["Africa"],
    "EMEIA": ["ASEAN"],
    "Global": ["Asia-Pacific"],
    "Unassigned": [
      "Canada", "CESA", "EMEIA", "Europe West", "EY Caribbean", "GDS", "Global", "Greater China",
      "IND", "Israel", "Japan", "Korea", "Latin America North", "Latin America South", "MENA",
      "Nordics", "Oceania", "UK and Ireland", "United States", "Other", "Luxembourg"
    ]
  },
  "Platform": [
    "CH Inventx Cloud", "Client Owned", "CT Platform", "D365",
    "Document Intelligence for Contract Review", "Document Intelligence for Transactions",
    "ET Azure", "ET Compute Services", "EY Predictive Intelligence for data driven VAT",
    "O365", "PEGA", "SaaS", "SAP", "SAP Others", "SAP Platform",
    "Search in Document Intelligence", "ServiceNow", "SharePoint", "Desktop Solution",
    "TBD", "Trusted Data Fabric"
  ],
  "Service Lines": {
    "Assurance": ["Audit Technology"],
    "Consulting": ["Brand Marketing and Communications", "Other Consulting"],
    "Global Markets": ["Business Consulting", "Global Markets"],
    "Strategy and Transactions": [
      "Business Operations", "Capital Transformation",
      "Corporate Finance Strategy", "Transaction Diligence", "Transaction Tax"
    ],
    "Tax": ["Business Tax Services", "Indirect Tax", "International Tax and Transaction Services", "Tax Technology Transformation", "Transaction Tax"],
    "Transformation Zone": ["Capital Transformation", "Transformation Zone"],
    "Unassigned": [
      "Cross Sub Service Line", "CT Engineering", "Enterprise Technology", "FAAS", "Forensics",
      "Global Compliance & Reporting", "Global Industries", "Global Managed Services",
      "Information Security", "Knowledge", "Law", "People Advisory Services",
      "Practice Management", "Regulatory & Compliance", "Talent", "Technology Consulting"
    ]
  },
  "Funding Business Sector": {
    "Funding Source": [
      "Area or Direct Country or Member Firm", "Client Sponsored or Engagement", "CT Global or Shared", "Executive Layer"
    ],
    "Business Sector": [
      "All Sectors", "Advanced Manufacturing & Mobility", "Banking & Capital Markets",
      "Consumer", "Financial Services", "Government & Public Sector",
      "Health Sciences & Wellness", "Insurance", "Internal", "Mining & Metals",
      "Oil & Gas", "Power & Utilities", "Private Equity",
      "Real Estate Hospitality & Construction", "Technology, Media & Telecommunications",
      "Wealth & Asset Management"
    ]
  }
}




def groupSolutionsDeliveredByPortfolio(solutions_delivered, portfolios,limit=20):
    """
    Group solutions_delivered by portfolio and filter by the provided portfolios list.
    """
    if portfolios is None or len(solutions_delivered) == 0:
        print("debug error in inputs-------", portfolios, len(solutions_delivered))
        return {}
      
    print("groupSolutionsDeliveredByPortfolio ", portfolios)
    portfolio_names = set(portfolio["name"].lower() for portfolio in portfolios) or {"none"}
    print("\n\n--debug groupSolutionsDeliveredByPortfolio------------Portfolios:", portfolio_names)
    

    grouped_solutions = {}
    # Group solutions by portfolio
    for solution in solutions_delivered:
        portfolio = solution.get("portfoloio", "").lower()
        sol_delivered = solution.get("solution_delivered", "") or ""
        functional_req = solution.get("functional_requirements", "") or ""
        technical_req = solution.get("technical_requirements", "") or ""
        
        if len(sol_delivered) == 0 and len(functional_req) == 0 and len(technical_req) == 0:
            continue
        
        if portfolio in portfolio_names:
            if portfolio not in grouped_solutions:
                grouped_solutions[portfolio] = []
            grouped_solutions[portfolio].append({
              "solution_delivered": sol_delivered,
              "functional_req": functional_req,
              "technical_req": technical_req
            })
    
    for portfolio in grouped_solutions:
       grouped_solutions[portfolio] = grouped_solutions[portfolio][:limit]
    
    # print("\n\n\nGrouped Solutions:", grouped_solutions)
    return grouped_solutions



def demand_type_prompt(tenant_id):
  
  if tenant_id in ["776", 776, "183", 183]: #EY tenants
    
    type_str = "<integer 4-New Development| 5-Enhancements or Upgrade| 6-Consume a Service| 7-Support a Pursuit| 8-Acquisition| 9-Global Product Adoption| 10-Innovation Request for NITRO| 11-Regional Product Adoption| 12-Client Deployment>"
    instructions = f"""
      - Completely new product, feature, or solution not existing today, any new development, new build → 4 (New Development).
      - Improvements, updates, or upgrades to an existing product or capability or solution, any enhancement, any improvement, any upgrade, or mention of a system from **Existing Customer Solutions** → 5 (Enhancements or Upgrade).                
      - Using or integrating an already available internal or external service without creating new capabilities, consume an existing service, use an service, integrate with any services → 6 (Consume a Service).                
      - Providing solutioning, technical, or functional support to win a new client opportunity or bid, support for new pursuit, client pitch → 7 (Support a Pursuit).                
      - Activities related to a merger, acquisition, or integration of acquired assets, any merger or acquisition related demand → 8 (Acquisition).                
      - Deploying an existing product or solution across multiple regions or globally, global adoption of a solution, global rollout of products → 9 (Global Product Adoption).                
      - Proposing experimental, pilot, POC or innovative solutions not currently in production, any innovation related work, any POC, any mention of “NITRO" → 10 (Innovation Request for NITRO).                
      - Deploying an existing product in a specific country or region only, regional adoption of a product or solution → 11 (Regional Product Adoption).                
      - Rolling out an existing product, service, or solution for a specific client or account, deployment activities for a client, rollout of features, product or solution to a specific client, support for client deployments→ 12 (Client Deployment).            
      - If a system from **Existing Customer Solutions** is mentioned (case-insensitive), prioritize type 5 (Enhancements or Upgrade) unless the context strongly suggests another type.            
      - If the context seems to fit more than one demand type, then choose the most specific category or the one that matches the most            
      - If you are not able to infer any demand type from the context only then, default to 4 (New Development) and flag the assumption in the output.
    """
  else:
      type_str = "<integer 1-Program| 2-Project| 3-Enhancement>"
      instructions = f"""
        -Program → A collection of related projects managed in a coordinated way to obtain benefits not available from managing them individually.
        -Project → Large body of work, cross-functional, delivering significant new capability or transformation.
        -Enhancement → Improvements, updates, or upgrades to an existing product or capability.
      """

  # elif tenant_id in [200,"200",160,"160",234,"234",232,"232", 209, "209"]:
    # type_str = "<integer 2-Project| 3-Enhancement| 13-Defect| 14-Change| 15-Epic| 16-Feature| 17-Story>"
    # instructions = f"""
    #   -Project → Large body of work, cross-functional, delivering significant new capability or transformation.
    #   -Enhancement → Small to medium improvements to existing functionality, optimizations, or UI/UX tweaks.
    #   -Defect → Bug, issue, or error that breaks functionality or causes incorrect results.
    #   -Change → Modification to an existing process, configuration, or system behavior (not necessarily a bug).
    #   -Epic → Large initiative that can be broken into multiple features or stories.
    #   -Feature → A specific functionality or capability requested, often part of an epic.
    #   -Story → A small, user-focused request, usually deliverable within a sprint.
    # """
  return type_str, instructions


def uploaded_files_prompt(files):
    
    if not files or not isinstance(files, list) or len(files) == 0:
        return None
    
    instructions =  f"""
        -**Files**: Take maximum inputs from uploaded files to enrich demand details. Extract relevant information that aligns with organizational goals and customer priorities.
        -These have been uploaded during the conversation to create to support the demand creation process.
        - Make sure to mark the file name(s) as refrences in the **Thought Process**
    """
    return instructions






#Business case
def calculateTotalLaborCost(team_data):
    """
    Algo -
    <labour_cost_calculation_formula> (identified by labour_type = "labour")
    Total Labour Cost =  
        if duration is calculated (using start_date and end_date):
            - Calculate duration in days, then convert to hours (assuming 8 hours/day, 20 days/month).
            - Apply allocation percentage to adjust effort.
            - cost = team_unit_size * duration_hours * labour_estimate_value * allocation
        Fallback to original logic if start_date/end_date are missing:
            if team_efforts == person_month:
                cost = team_unit_size * 20 * 8 * labour_estimate_value
            elif team_efforts == person_days:
                cost = team_unit_size * 8 * labour_estimate_value
    do this calculation for the effort period only, not annualized
    <labour_cost_calculation_formula>
    """
    # team_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id=roadmap_id)
    total_labor_cost = 0
    labor_cost_arr = []

    for data in team_data:
        # Get team name and labor type
        team_name = data.get("name", "")
        labor_type = data.get("labour_type", "")

        # Skip non-labor teams
        if labor_type != 1:
            continue

        # Get labor estimate value (hourly rate)
        value_ = data.get("estimate_value", "0")
        if value_ is None or value_ == "":
            value = 0
        else:
            value = int(value_)

        unit_size = data.get("unit", 1) or 1


        print("debug -- calculateTotalLaborCost ", unit_size, value_)
        # Get allocation (default to 100% if missing)
        allocation_ = data.get("allocation", "100%")
        if isinstance(allocation_, str) and "%" in allocation_:
            allocation = float(allocation_.replace("%", "")) / 100
        else:
            allocation = float(allocation_) / 100 if allocation_ else 1.0

        # Check for start_date and end_date
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date:
            try:
                # Parse dates
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                # Calculate duration in days
                duration_days = (end - start).days + 1  # Inclusive of end date
                # Convert to working hours (assuming 8 hours/day, 20 days/month)
                working_days = duration_days * (20 / 30.42)  # Approximate working days in a month
                duration_hours = working_days * 8
                # Calculate cost
                price = unit_size * duration_hours * value * allocation
            except ValueError as e:
                print(f"Error parsing dates for team {team_name}: {e}")
                price = 0
        else:
            # Fallback to original logic
            unit_type = data.get("team_efforts", "person_month")  # Default to person_month
            price = 0
            if unit_type == "person_month":
                price = unit_size * 20 * 8 * value
            elif unit_type == "person_days":
                price = unit_size * 8 * value
            # Apply allocation to fallback calculation
            price *= allocation

        if price > 0:
            labor_cost_arr.append({
                "name": team_name,
                "cost": round(price, 2)
            })
            total_labor_cost += price

    return f"""
        Labor cost per team - {labor_cost_arr}
        and Total Cost of Labor - {round(total_labor_cost, 2)}
    """
    

def calculateTotalNonLaborCost(team_data):
      # team_data = RoadmapDao.fetchTeamDataRoadmap(roadmap_id=roadmap_id)
      total_non_labor_cost = 0
      non_labor_cost_arr = []
      for data in team_data:
          unit_size = data.get("unit", 0)
          unit_type = data.get("type", 0)
          value_ = data.get("estimate_value", '0')

          if value_ is None or value_ == '':
              value = 0
          else:
              value = int(value_)

          labor_type = data.get("labour_type", 0)

          if labor_type != 2:
              continue
          non_labor_cost_arr.append({
              "team_name": data.get("name", ""),
              "team_cost": value
          })
          total_non_labor_cost = total_non_labor_cost + value
      return f"""
          Non Labor cost per team - {non_labor_cost_arr}
          and Total Cost of Non Labor - {total_non_labor_cost}
      """


def demand_category_prompt(tenant_id:int):

    if tenant_id in DEMAND_CATEGORY_TENANTS:
        return f"""
        Select the most suitable 1- 3 categories within the `roadmap_category` array, exact same name(s) from these options:
            -New business initiative process & capability
            -Legal Regulatory & compliance
            -Arch & Tech change
            -Infra & Core services
            -Info Security
            -EOL - Infra / Application
        """
        
    else:
        return f"""
            - Generate 3-4 categories within the `roadmap_category` array, including:
            - Technical, business, and functional aspects (e.g., "Process Mining", "Supply Chain Optimization", "Data Analytics").
            - Only include a system from **Existing Customer Solutions** as an element in the `roadmap_category` array if explicitly mentioned in the conversation.
            - Tags mapped from user inputs in the conversation and Existing Customer Solutions to categories below:
            - For mapping tags:
            - Analyze the conversation and Existing Customer Solutions for mentions of regions, platforms, service lines, funding sources, or business sectors.
            - Map these mentions to the corresponding categories, which is provided as a JSON object in the input summary:
                - For "AreaRegion": If a term (e.g., "Africa") is in a list under a region (e.g., "Asia-Pacific"), use "AreaRegion: Asia-Pacific". Use "AreaRegion: Unassigned" if no match.
                - For "Platform": If a platform (e.g., a system from **Existing Customer Solutions**) is mentioned, use "Platform: [system name]".
                - For "ServiceLines": If a term (e.g., "Audit Technology") is in a list under a service line (e.g., "Assurance"), use "ServiceLines: Assurance - Audit Technology". Use "ServiceLines: Unassigned" if no match.
                - For "FundingBusinessSector": If a funding source (e.g., "Executive Layer") or business sector (e.g., "Financial Services") is mentioned, use "Funding Source: Executive Layer" or "Business Sector: Financial Services".
            - Examples: 
                - "This is for audit technology" → "ServiceLines: Assurance - Audit Technology".
                - "Asia-Pacific region" or "Africa" → "AreaRegion: Asia-Pacific".
                - "Enhancing [system name]" → "Platform: [system name]" and infer type 5 (Enhancements or Upgrade).
        """