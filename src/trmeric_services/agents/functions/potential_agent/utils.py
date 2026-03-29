from rapidfuzz import process, fuzz
from src.trmeric_database.dao import AuthDao,PortfolioDao, TenantDao, RoadmapDao
from functools import wraps
from typing import Callable, Generator, Any
import json

# Global registry: maps action name -> handler function
ACTION_REGISTRY = {}
CONTEXT_BUILDERS = {}


def register_action(action_name: str):
    """Decorator to register a function as handler for a specific action."""
    def decorator(func: Callable):
        ACTION_REGISTRY[action_name] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_action_handler(action: str):
    return ACTION_REGISTRY.get(action) or ACTION_REGISTRY.get("analyze_potential")




def register_context_builder(action_name: str):
    def decorator(func):
        CONTEXT_BUILDERS[action_name] = func
        return func
    return decorator

def build_context_for_action(action: str, tenant_id: int, user_id: int, eligible_projects: list) -> dict:
    builder = CONTEXT_BUILDERS.get(action, lambda **_: {
        "context_string": "No specific context available for this action.",
        "portfolio_info": None,
        "team_info": None,
        "resources_info": None,
        "projects_info": None,
        "roadmap_info": None,
    })

    result = builder(
        tenant_id=tenant_id,
        user_id=user_id,
        eligible_projects=eligible_projects
    )
    # Ensure all keys exist
    # print("--debug CONTEXT_BUILDERS--------", CONTEXT_BUILDERS, "\n----result-----", result)
    defaults = {
        "portfolio_info": None,
        "team_info": None,
        "resources_info": None,
        "projects_info": None,
        "roadmap_info": None,
        "context_string": ""
    }
    defaults.update(result)
    return defaults







PRIMARY_SKILLS = ["ERP", "Data & Analytics", "AI", "CRM", "Cloud & DevOps", "Infrastructure Management",
"Automation", "Integration", "Security", "Business Apps", "Project Management", "Quality Assurance",
"Business Analyst", "App Development", "UX","Other"
]

def restriction_msg(resource_name: str, portfolio_names: list[str], type: str = 'assign'):
    portfolio_list = ', '.join(portfolio_names)
    return {
        "assign": (
            f"🔒 You don’t have permission to assign or modify {resource_name}, "
            f"as this resource is part of portfolio(s): {portfolio_list}, which are outside your access scope."
        ),
        "details": (
            f"🔒 You don’t have permission to update {resource_name}’s details, "
            f"as this resource is part of portfolio(s): {portfolio_list}, which are outside your access scope."
        )
    }.get(type, "🔒You’re not authorized to perform this action.")



def restrict_check(user_id:int,tenant_id:int,resource_data:list[dict],responses:list,type:str = 'assign'):

    ####### If the current user_id has ORG_RESOURCE_MANAGER access then only he can make updates
    #### Additionally if the current_user_id has any portfolio access matching to the resources' ones whom it's going to make update
    try:
        # user_role = AuthDao.fetchRoleOfUserInTenant(user_id = user_id)
        # print("--debug user_role--------", user_role)

        all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id)
        portfolio_id_title_mapping = {}
        for p in all_portfolios:
            portfolio_id_title_mapping[p.get('id')] = p.get('title')

        # print("\n--debug portfolio_id_title_mapping------", portfolio_id_title_mapping)
        
        user_portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id,tenant_id=tenant_id)

        user_portfolios = [{'id': p.get('id'),'title':p.get('title')} for p in user_portfolios if len(user_portfolios)>0]
        # user_portfolios = [{'id': 246, 'title': 'AI'}]
        # print("--debug user_portfolio_ids-------", user_portfolios)

        ## Now fetch all the portfolio the resource is part of whom the user is wishing to make update
        resource_id_name_mapping  = {}
        for r in resource_data:
            resource_id_name_mapping[r.get('id')] = r.get('name')

        print("\n---debug resource_id_name_mapping------ ", resource_id_name_mapping)

        resource_ids = [r.get('id') for r in resource_data if r.get('id') is not None]

        #Get all the org teams this resource is part of & all the portfolio_ids these org_teams are mapped to
        resource_details = TenantDao.getOrgTeamsAndPortfolioDetailsForResources(resource_ids = resource_ids,tenant_id=tenant_id)
        print("--debug resource_details---------", resource_details)

        resource_ids_to_restrict = []
        for details in resource_details:
            resource_id = details.get("resource_id")
            # resource_name = resource_data.get("resource")
            org_team_ids = details.get("resource_group_ids",{}) or {}
            portfolio_ids = details.get("portfolio_ids",{}) or {}
            print("--debug resource_id---", resource_id)
            print("   orgteam ids: ", org_team_ids, "\nPortfolio_ids: ", portfolio_ids)

            ##Check if any user_portfolio_ids matches with portfolio_ids or not
            ##If none is matching then can't make update to this resource
            common_portfolio = False
            for user_portfolio in user_portfolios:
                if user_portfolio.get('id') in portfolio_ids:
                    common_portfolio = True
                    break
            
            if not common_portfolio: ## no matching portfolios
                resource_ids_to_restrict.append(resource_id)
                resource_name = resource_id_name_mapping.get(str(resource_id)) or resource_id_name_mapping.get(resource_id, "Unknown Resource")
                portfolio_names = [portfolio_id_title_mapping.get(pid, str(pid)) for pid in portfolio_ids]

                message = restriction_msg(resource_name,portfolio_names,type=type)
                responses.append(message)
                # responses.append(f"You don’t have permission to modify {resource_name} — they belong to {', '.join(portfolio_names)} portfolio(s) outside your access.")

                # responses.append(f"{resource_id} resource belongs to {portfolio_ids} which is beyond your restriction.")

        print("--debug resource_id to restrict-------", resource_ids_to_restrict)
        print("--debug resource_data before----------1", resource_data)
        ##Filter resource_data
        # resource_data = [d for d in resource_data if d.get('id') not in resource_ids_to_restrict and d.get('id') is not None]
        resource_data = [
            d for d in resource_data
            if int(d.get('id')) not in resource_ids_to_restrict and d.get('id') is not None
        ]
        return resource_data
    except Exception as e:
        print("--debug error in check------", str(e))
        return []



def find_best_resource_match(target_name: str, resource_data: list, cutoff: int = 80):
    """
    Safely fuzzy-match a human name against resource_data.
    Returns the best matching resource dict or None.
    """

    if not target_name:
        return None

    target_name = target_name.strip()

    # Build clean name list + parallel resource index
    choices = []
    valid_resources = []

    for r in resource_data:
        fn = (r.get("first_name") or "").strip()
        ln = (r.get("last_name") or "").strip()
        full = f"{fn} {ln}".strip()

        if full:  # skip empty / None
            choices.append(full)
            valid_resources.append(r)

    if not choices:
        return None

    # Fuzzy match (list-based → never crashes)
    match = process.extractOne(target_name, choices, scorer=fuzz.WRatio, score_cutoff=cutoff)
    print("--debug match---------", match)
    if not match:
        # Try to find exact or close match
        print("--debug fallback--------------")
        for r in resource_data:
            full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip().lower()
            if target_name in full_name or full_name in target_name:
                valid_resources.append(r)
        return valid_resources

    best_name = match[0]
    idx = choices.index(best_name)

    return valid_resources[idx]















def clean_and_merge_fields(obj):
    """
    Recursively clean null/empty fields and merge name parts
    (first/last and leader_first/leader_last).
    Handles nested lists/dicts gracefully.
    """
    if isinstance(obj, dict):
        # Merge normal name
        first = (obj.get("first_name") or "").strip()
        last = (obj.get("last_name") or "").strip()
        merged_name = " ".join(p for p in [first, last] if p)

        # Merge leader name
        leader_first = (obj.get("leader_first_name") or "").strip()
        leader_last = (obj.get("leader_last_name") or "").strip()
        merged_leader_name = " ".join(p for p in [leader_first, leader_last] if p)

        new_obj = {}
        for k, v in obj.items():
            if k in ("first_name", "last_name", "leader_first_name", "leader_last_name"):
                continue  # skip name parts — we'll add merged ones later

            cleaned_value = clean_and_merge_fields(v)

            # keep only non-empty values
            if cleaned_value not in (None, "", [], {}) and not (
                isinstance(cleaned_value, str) and cleaned_value.strip() == ""
            ):
                new_obj[k] = cleaned_value

        # Add merged names if available
        if merged_name:
            new_obj["name"] = merged_name
        if merged_leader_name:
            new_obj["leader_name"] = merged_leader_name

        return new_obj

    elif isinstance(obj, list):
        cleaned_list = [clean_and_merge_fields(v) for v in obj]
        return [v for v in cleaned_list if v not in (None, "", [], {})]

    else:
        return obj























def group_resources_by_skills(resources):
    grouped_resources = {}
    # print("--debug group_resources_by_skills------", resources[:2])
    
    for resource in resources:
        # Ensure primary_skill and id exist in the resource
        if 'primary_skill' not in resource or 'id' not in resource:
            print(f"Warning: Skipping resource due to missing primary_skill or id: {resource}")
            continue
        
        primary_skill = resource['primary_skill']
        resource_id = resource['id']
        
        # Initialize the skill group if it doesn't exist
        if primary_skill not in grouped_resources:
            grouped_resources[primary_skill] = []
        
        # Only add the resource if its ID hasn't been seen for this primary_skill
        if all(r['id'] != resource_id for r in grouped_resources[primary_skill]):
            grouped_resources[primary_skill].append({
                'id': resource['id'],  # Include id to avoid downstream issues
                'name': resource['first_name'] + ' ' + resource['last_name'],
                'description': resource['description'],
                'availability': resource['availability_time'],
                # 'allocation': resource['allocation'],
                'skills': resource['skills'],
                'external': resource['is_external'],
                'organization_team': resource['org_team']
            })
    
    # Limit each group to 40 resources
    result = {primary_skill: group[:60] for primary_skill, group in grouped_resources.items()}
    # print("---debug skill_group-----", result)
    return result


# Skill group
SKILL_MAP = {
  "ERP": ["SAP (FI/CO, MM, SD, PP, HCM)","Oracle ERP (E-Business Suite, Fusion, NetSuite)","Microsoft Dynamics 365 Finance & Operations","ERP Implementation & Customization","ERP Reporting & Data Migration"],
  "Data & Analytics": ["Data Engineering (ETL, Data Pipelines, Warehousing)","Business Intelligence (Power BI, Tableau, Qlik)","Advanced Analytics & Forecasting","Big Data Platforms (Databricks, Hadoop, Spark)","Data Governance & Master Data Management"],
  "AI": ["Machine Learning (ML) Engineering","Natural Language Processing (NLP)","Computer Vision","Generative AI (LLMs, Prompt Engineering, Fine-tuning)","MLOps & Model Deployment"],
  "CRM": ["Salesforce (Sales, Service, Marketing Clouds)","Microsoft Dynamics 365 CRM","SAP Customer Experience (C4C, Hybris)","CRM Integration & Customization","CRM Analytics & Customer Journey Mapping"],
  "Cloud & DevOps": ["Cloud Platforms (AWS, Azure, GCP)","CI/CD & Release Management","Infrastructure as Code (Terraform, Ansible, ARM)","Containerization & Orchestration (Docker, Kubernetes)","Monitoring & Observability (Prometheus, Grafana, ELK)"],
  
  "Infrastructure Management": ["Network Administration (LAN, WAN, VPN, Firewalls)","Server & Storage Management","Virtualization (VMware, Hyper-V)","End-User Computing & Device Management","IT Service Management (ITIL, ServiceNow)"],
  "Automation": ["RPA (UiPath, Automation Anywhere, Blue Prism)","IT Process Automation (Ansible, Puppet, Chef)","Test Automation (Selenium, Cypress, Playwright)","Workflow Automation (Power Automate, Zapier)","Infrastructure Automation (Terraform, CloudFormation)"],
  "Integration": ["API Management (MuleSoft, Apigee, Kong)","ESB (Dell Boomi, TIBCO, IBM Integration Bus)","Event Streaming & Messaging (Kafka, RabbitMQ)","Cloud Integration (iPaaS, Azure Logic Apps)","B2B/EDI Integration"],
  "Security": ["Identity & Access Management (Okta, Azure AD, Ping)","Application Security (AppSec, DevSecOps)","Network & Infrastructure Security","Cloud Security & Compliance","Threat Detection & Incident Response (SIEM, SOC)"],
  "Business Apps": ["CPQ Platforms (Salesforce CPQ, Apttus, Oracle CPQ)","HR & HCM Apps (Workday, SuccessFactors)","Finance & Accounting Apps (BlackLine, Coupa)","Collaboration Apps (O365, Google Workspace)","Supply Chain & Procurement Apps"],
  "Project Management": ["Agile (Scrum, Kanban, SAFe)","Waterfall & Hybrid Methodologies","PM Tools (Jira, MS Project, Smartsheet)","Portfolio & Program Management (PPM)","Risk & Change Management"],
  
  "Quality Assurance": ["Manual Testing (Functional, Regression, UAT)","Test Automation Frameworks","Performance & Load Testing (JMeter, LoadRunner)","Security Testing","QA Tools & Management (TestRail, Zephyr)"],
  "Business Analyst": ["Requirements Gathering & Documentation","Process Modeling & Mapping (BPMN, Visio)","Functional Specification & User Stories","Data Analysis & Reporting","Domain-Specific BA (ERP, CRM, Finance, Supply Chain)"],
  "App Development": ["Frontend Development (React, Angular, Vue)","Backend Development (Java, .NET, Python, Node.js)","Mobile Development (iOS, Android, Flutter, React Native)","Full Stack Development","API & Microservices Development"],
  "UX": ["UX Research & User Testing","Wireframing & Prototyping (Figma, Sketch, XD)","Interaction Design","UI Development & Design Systems","Accessibility & Usability Standards"],
  "Other": [
    "Blockchain & Distributed Ledger Technology",
    "Internet of Things (IoT) Development & Integration",
    "Augmented Reality (AR) & Virtual Reality (VR) Development",
    "Low-Code/No-Code Platforms (OutSystems, Mendix, Appian)",
    "Geographic Information Systems (GIS) & Spatial Analysis",
    "Digital Twin Technology",
    "Quantum Computing Fundamentals",
    "Robotics & Embedded Systems",
    "Change Management & Organizational Transformation",
    "Sustainability & ESG (Environmental, Social, Governance) Analytics"
  ]
  
}
