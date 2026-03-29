from src.trmeric_services.agents.core.agent_functions import AgentFunction
from .portfolio_analyst import portfolio_analyst
from src.trmeric_database.dao import PortfolioDao
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
import json
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from collections import defaultdict
from src.trmeric_services.agents.apis.portfolio_api.PortfolioApiService import PortfolioApiService
from src.trmeric_services.journal.Activity import activity_log

from src.trmeric_services.agents.prompts.agents.portfolio import analyze_portfolio_initiatives

def portfolio_review(
    tenantID: int,
    userID: int,
    eligibleProjects: list[int],
    portfolio_ids=[],
    start_date='',
    end_date='',
    socketio=None,
    client_id=None,
    llm=None, 
    base_agent=None,
    **kwargs
):
    debugLogger.info(f"Incoming Data in portfolio review -- {portfolio_ids}, {start_date}, {end_date}")
    sender = kwargs.get("step_sender")
    
    no_portfolio_selected = True
    if portfolio_ids:
        if len(portfolio_ids) == 1:
            no_portfolio_selected = False
            
    debugLogger.info(f"Selected Portfolio: {no_portfolio_selected}")
    if no_portfolio_selected:
        portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=userID, tenant_id=tenantID)
        portfolio_id_title = [{"id": p["id"], "title": p["title"], "label": p["title"], "preprend": "Selected portfolio: "} for p in portfolios]
        yield f"""Please select a portfolio from the list of portfolios.

```json
{{
    "cta_buttons": {json.dumps(portfolio_id_title, indent=8)}
}}
``` 
"""
        return
    
    
    socketio.emit(
        "portfolio_agent",
        {
            "event": "portfolio_selected",
            "data": portfolio_ids[0],
        },
        room=client_id
    )
    
    if start_date and end_date:
        pass
    else:
        yield f"""Could you specify the review period?

```json
{{
    "date_signals": [
        "start_date", "end_date"
    ],
    "label": "Select Date"
}}
``` 
"""
        return
    
    socketio.emit(
        "portfolio_agent",
        {
            "event": "dates_selected",
            "data": {
                "start_date": start_date,
                "end_date": end_date
            },
        },
        room=client_id
    )
    
    debugLogger.info(f"Selected Portfolio: {portfolio_ids}")
    review_data = PortfolioApiService().fetchSpendBycategory(
        tenant_id=tenantID, 
        applicable_projects=eligibleProjects, 
        portfolio_ids=portfolio_ids,
        start_date=start_date,
        end_date=end_date
    )
    review_data = review_data.get("table_data")
    # Fields to remove from projects
    fields_to_remove = ['scope_status_comments', 'delivery_status_comments', 'spend_status_comments']

    portfolio_detail = PortfolioDao.fetchPortfolioById(id=portfolio_ids[0])
    # Loop through archived_projects and ongoing_projects to remove specified fields
    for project_list in [review_data['archived_projects'], review_data['ongoing_projects']]:
        for project in project_list:
            for field in fields_to_remove:
                project.pop(field, None)
    

    prompt = analyze_portfolio_initiatives(portfolio_data=review_data, time_frame=f"Start Date: {start_date}, End Date: {end_date}", portfolio_name=portfolio_detail)
    print("debug ----- ", prompt.formatAsString())
    
    model_opts_1 = ModelOptions(
        model="gpt-4.1",
        max_tokens=16000,
        temperature=0
    )
    response = llm.run(
        prompt, 
        model_opts_1, 
        'agent::portfolio_agent::create_review_date', 
        {
            "tenant_id": tenantID,
            "user_id": userID
        },
        socketio=socketio,client_id=client_id
    )
    # print("agent::portfolio_agent::create_review_date ========", response)
    response = extract_json_after_llm(response,step_sender=sender)
    
    titles = []
    portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=userID, tenant_id=tenantID)
    for portfolio in portfolios:
        if portfolio['id'] in portfolio_ids:
            portfolio_title = portfolio['title']
            titles.append(portfolio_title)
            
    # Cap review_data to first 3 items for logging
    capped_review_data = {}
    for key, value in review_data.items():
        if isinstance(value, list) and len(value) > 3:
            capped_review_data[key] = value[:3] + ["..."]
        else:
            capped_review_data[key] = value
    
    activity_log(
        tenant_id=tenantID, 
        user_id=userID,
        agent_or_workflow_name="portfolio_agent::portfolio_review",
        description=f"The user has requested that the the portfolio agent review the portfolio(s) {str(titles)} for the period {start_date} to {end_date}",
        input_data={
            "portfolio_ids": portfolio_ids,
            "start_date": start_date,
            "end_date": end_date,
            "review_data": capped_review_data
        },
        output_data=response
    )
    
    titles = []
    portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=userID, tenant_id=tenantID)
    for portfolio in portfolios:
        if portfolio['id'] in portfolio_ids:
            portfolio_title = portfolio['title']
            titles.append(portfolio_title)
            
    # Cap review_data to first 3 items for logging
    capped_review_data = {}
    for key, value in review_data.items():
        if isinstance(value, list) and len(value) > 3:
            capped_review_data[key] = value[:3] + ["..."]
        else:
            capped_review_data[key] = value
    
    activity_log(
        tenant_id=tenantID, 
        user_id=userID,
        agent_or_workflow_name="portfolio_agent::portfolio_review",
        description=f"The user has requested that the the portfolio agent review the portfolio(s) {str(titles)} for the period {start_date} to {end_date}",
        input_data={
            "portfolio_ids": portfolio_ids,
            "start_date": start_date,
            "end_date": end_date,
            "review_data": capped_review_data
        },
        output_data=response
    )
    
    response["counts"] = {
        "ongoing_projects": len(review_data['ongoing_projects']),
        "archived_projects": len(review_data['archived_projects']),
        "future_projects": len(review_data['future_projects']),
    }
    response["dates"] = {
        "start_date": start_date,
        "end_date": end_date
    }
    response["portfolio"] = portfolio_detail
    
    health = {
        "on_track": 0,
        "at_risk": 0,
        "compromised": 0
    }
    for p in review_data['ongoing_projects']:
        if (
            p.get("delivery_status") == "no_update" \
            or p.get("spend_status") == "no_update" \
            or p.get("scope_status") == "no_update"
        ):
            health["no_update"] += 1
            
        elif (
            p.get("delivery_status") == "compromised" \
            or p.get("spend_status") == "compromised" \
            or p.get("scope_status") == "compromised"
        ):
            health["compromised"] += 1
            
        elif  (
            p.get("delivery_status") == "at_risk" \
            or p.get("spend_status") == "at_risk" \
            or p.get("scope_status") == "at_risk"
        ):
            health["at_risk"] += 1
            
        else:
            health["on_track"] += 1
            
    response["health"] = health
    
    
    # print("--debug response", response)
    response = parse_ampere_projects(response,portfolio_ids,tenant_id=tenantID)
    
    socketio.emit(
        "portfolio_agent",
        {
            "event": "portfolio_review_data",
            "data": response,
        },
        room=client_id
    )
    yield """Review data created

```json
{
    "cta_buttons": [
        {
            "label": "Review Data",
            "action": "review_portfolio_data_begin"
        }
    ]
}
```
"""
    
    

RETURN_DESCRIPTION = """
    
"""

ARGUMENTS = [
    {
        "name": "portfolio_ids",
        "type": "int[]",
        "description": "The portfolio_id(s) that the user wants to get insight on. Do not fil any potyfolio by yourself only when user selects."
    },
    {
        "name": "start_date",
        "type": "str",
        "description": "The start date user selected"
    },
    {
        "name": "end_date",
        "type": "str",
        "description": "The end date user selected"
    },
]

PORTFOLIO_REVIEW = AgentFunction(
    name="portfolio_review",
    description="",
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=portfolio_review,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)




def parse_ampere_projects(response, portfolio_ids, tenant_id):
    print("--deugg parse_ampere_projects------- came", tenant_id)
    dev_portfolios = [155, 156]
    prod_portfolios = [37, 38, 39, 42, 90]
    
    # Check if tenant_id and portfolio_ids meet the conditions
    #for dev
    # if tenant_id not in [625, "625"] or portfolio_ids[0] not in dev_portfolios:
    #     print(f"\n--debug parse_ampere_projects: Invalid tenant_id {tenant_id} or portfolio_id {portfolio_ids[0]} not in {dev_portfolios}")
    #     return response  
    
    # for prod
    if tenant_id not in [66, "66"] or portfolio_ids[0] not in prod_portfolios:
        print(f"\n--debug parse_ampere_projects: Invalid tenant_id {tenant_id} or portfolio_id {portfolio_ids[0]} not in {prod_portfolios}")
        return response
    
    print("\n--debug parse_ampere_projects, portfolio_id---", portfolio_ids)
    portfolio_id = portfolio_ids[0]
    res = PortfolioDao.getPortfolioNameById(portfolio_id=portfolio_id, tenant_id=tenant_id)
    # print("\n\n--------res----", res)
    portfolio_name = res[0]["title"].lower()
    
    # print("\n\n--name--------", portfolio_name, "\n", response["key_highlights"])
    # Retrieve ongoing and closed projects from MAPPING
    ongoing_projects = MAPPING.get(portfolio_name, {}).get("ongoing_projects", [])
    closed_projects = MAPPING.get(portfolio_name, {}).get("closed_projects", [])
    
    print("\n\n\n\n----------debug ---ongoing---", ongoing_projects)
    if "key_highlights" not in response:
        response["key_highlights"] = [
            {"header": "Ongoing Initiatives", "supporting_detail": "", "projects": []},
            {"header": "Closed Initiatives", "supporting_detail": "", "projects": []}
        ]
    
    for highlight in response["key_highlights"]:
        if highlight["header"] == "Ongoing Initiatives":
            # highlight["supporting_detail"] = f"Total of {len(ongoing_projects)} projects ongoing; top 5 listed by business impact."
            highlight["projects"] = ongoing_projects  # Limit to top 5
        elif highlight["header"] == "Closed Initiatives":
            # highlight["supporting_detail"] = f"Total of {len(closed_projects)} projects closed; top 5 listed by business impact."
            highlight["projects"] = closed_projects  # Limit to top 5
    
    # print("\n\n\n\n\n00--debug response after-----", response)
    return response


MAPPING = {
    "product engineering": {
        "ongoing_projects": [
            "Document Publishing - OCPLM Team",
            "Integration from NS to PLM inventory quantities / Cross Reference Build",
            "Integration to NetSuite Item Group - OCPLM Team",
            "BOM Manager Enhancements - OCPLM Team",
            "Deviation Record Changes - OCPLM"
        ],
        "closed_projects": [
            "Patching OCPLM 25B Release",
            "Updates to Change Order Attributes to the more modern EFF",
            "OCPLM Work Instruction Test Program UI Changes",
            "Item Groups Changes in Netsuite - UI",
            "OCPLM NetSuite Integration Changes -OCPLM"
        ]
    },
    "supply planning": {
        "ongoing_projects": [
            "Maestro periodic upgrade, Change management - ITGC",
            "OCPLM -> Maestro BOM Integration to Rapid",
            "Automated NetSuite -> Rapid Work Order detail Integration",
            "Transfer Order details Integration from NetSuite to Maestro KTBE",
            "FG inventory Projection"
        ],
        "closed_projects": [
            "Rapid Response Logical Access Control Implementation (ITGC)",
            "NPI parts, BOM and demand forecast capture in Maestro",
            "Update NetSuite saved searches to integrate OnHand inventory into Maestro",
            "Integrate Purchase Contracts data from NetSuite to Maestro",
            "Integrate Mfg PO data from NetSuite to Maestro"
        ]
    },
    "finance": {
        "ongoing_projects": [
            "Explore the feasibility and process of creating a split period for pre and post deal close reporting, and eventually modifying Ampere's fiscal year-end from 31 Dec to 31 Mar",
            "Enforcing class on transactions - NetSuite Financial Reporting Enhancement - ITBS-62747",
            "Adjustment Book to enable IFRS adjustments - ITBS-62785",
            "Remove Edit Access After Bill Approval - ITBS-62600",
            "Integrate NetSuite with RAMP, the new Corp Credit Card Program - ITBS-62837"
        ],
        "closed_projects": [
            "NetSuite Income Statement - ITBS-62175",
            "Customized Approval Workflows for Purchase Contracts and Manufacturing Purchase Orders - ITBS-62583",
            "Custom PO approval workflow updates - ITBS-62089 - ITBS-62460 - ITBS-61710",
            "Vendor Sensitive Data Control Enhancement - ITBS-58696",
            "NetSuite Expense Report Optimization - Expense Report Improvements - ITBS-60558"
        ]
    },
    "manufacturing & supply chain": {
        "ongoing_projects": [
            "Tallify Banshee BUMP, PROBE and DIE SORT Business Process",
            "Update BOOMI for FT40",
            "RMA Automation Project",
            "Enable WIP and Routing in NetSuite",
            "Sales Order email message automated after SO# fulfillment"
        ],
        "closed_projects": [
            "Gross Inventory B2B Phase-2 : Build Banshee-8 ATE step in B2B",
            "Gross Inventory B2B Phase-2 :Build SLT step in B2B",
            "Mfg PO Form Customization",
            "Mfg PO -Work Instruction CSV Export",
            "NETSUITE RMA Approvals - enable \"Submit for Approval\" button",
            "Salto.io Testing and Implementation"
        ]
    },
    "web development": {
        "ongoing_projects": [
            "Recommendation Engine Revision – Phase 2 – Ampere",
            "Move UAW Infrastructure under Ampere Subscription on Azure – Ampere",
            "Develop an Automated Regression Test Suite – Ampere",
            "Create a Web Analytics Dashboard – Ampere",
            "Strapi Component Enhancements and Cleanup – KTBE – Ampere"
        ],
        "closed_projects": [
            "Strapi Versioning to enable content staging - Web Development",
            "Resource Library - Web Development",
            "Content recommendation based on user browsing - Web Development",
            "Define and improve web dev collaboration process with Mary's team - Ampere",
            "Component Library Cleanup- Wave 1 - Web Development",
            "Migration of web forms from Eloqua to Salesforce"
        ]
    },
    
    
    
    #for dev comment in prod
    # "erp": {
    #     "ongoing_projects": [
    #         "Tallify Banshee BUMP, PROBE and DIE SORT Business Process",
    #         "Update BOOMI for FT40",
    #         "RMA Automation Project",
    #         "Enable WIP and Routing in NetSuite",
    #         "Sales Order email message automated after SO# fulfillment"
    #     ],
    #     "closed_projects": [
    #         "Gross Inventory B2B Phase-2 : Build Banshee-8 ATE step in B2B",
    #         "Gross Inventory B2B Phase-2 :Build SLT step in B2B",
    #         "Mfg PO Form Customization",
    #         "Mfg PO -Work Instruction CSV Export",
    #         "NETSUITE RMA Approvals - enable \"Submit for Approval\" button",
    #         "Salto.io Testing and Implementation"
    #     ]
    # },
    # "crm": {
    #     "ongoing_projects": [
    #         "Tallify Banshee BUMP, PROBE and DIE SORT Business Process",
    #         "Update BOOMI for FT40",
    #         "RMA Automation Project",
    #         "Enable WIP and Routing in NetSuite",
    #         "Sales Order email message automated after SO# fulfillment"
    #     ],
    #     "closed_projects": [
    #         "Gross Inventory B2B Phase-2 : Build Banshee-8 ATE step in B2B",
    #         "Gross Inventory B2B Phase-2 :Build SLT step in B2B",
    #         "Mfg PO Form Customization",
    #         "Mfg PO -Work Instruction CSV Export",
    #         "NETSUITE RMA Approvals - enable \"Submit for Approval\" button",
    #         "Salto.io Testing and Implementation"
    #     ]
    # }
}
