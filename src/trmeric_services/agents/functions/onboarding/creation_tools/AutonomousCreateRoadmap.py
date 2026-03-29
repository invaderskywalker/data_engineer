import re
import os
import datetime
import requests, json
from src.trmeric_database.dao import TenantDao
from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.agents.functions.onboarding.utils.enhance import CreationEnhancer
from src.trmeric_services.agents.functions.onboarding.utils.core import OnboardingAgentUtils
from src.trmeric_services.journal.Activity import activity, record
from src.trmeric_services.agents.prompts.agents.resource_planning_agent import suggest_project_role_prompt, suggest_project_role_promptV2
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient

class RoadmapAgent:
    def __init__(self):
        self.create_roadmap_url = os.getenv(
            "DJANGO_BACKEND_URL") + "api/roadmap/tango/create"
        self.onboarding_agent_utils = OnboardingAgentUtils()
        self.llm = ChatGPTClient()


    def format_json_for_roadmap(self, input_json, suggested_roles, roadmap_role_thought, userId, tenantId):
        # Extract fields from input JSON with defaults
        title = input_json.get('title', '')
        description = input_json.get('description', '')
        objectives = input_json.get('objectives', '')
        scopes = input_json.get('scope_item', [])  # Expecting enhanced output format
        priority = input_json.get('priority', 2)
        roadmap_type = input_json.get('type', 2)
        budget = input_json.get('budget', 0)
        org_strategy_align = input_json.get('org_strategy_align', '')
        constraints = input_json.get('constraints', [])
        team = input_json.get('team', [])
        key_results = input_json.get('key_results', [])
        category = input_json.get('roadmap_capabilities', '')
        min_time_value = input_json.get('min_time_value', 0)
        min_time_value_type = input_json.get('min_time_value_type', 1)
        start_date = input_json.get('start_date', '')
        end_date = input_json.get('end_date', '')
        portfolio = input_json.get('portfolio', {})  # Expecting enhanced output format
        portfolios = [portfolio]
        business_sponsor_lead = input_json.get('business_sponsor_lead', [])
        
        tango_analysis = {
            "thought_process_behind_labor_team": roadmap_role_thought,
            "thought_process_behind_non_labor_team": input_json.get('thought_process_behind_non_labor_team', '')
        }
        
        # Process suggested roles
        processed_roles = []
        for role in suggested_roles:
            processed_roles.extend(self.onboarding_agent_utils.transform_role_data(role))
        
        # Append processed_roles to the team
        team.extend(processed_roles)

        # Transform scopes: "scopes" -> "scope", "scope" -> "name"
        transformed_scope = [
            {"name": f'{item.get("name")}\n {item.get("combined_details_out_of_scope_in_markdown_format")}', "selected": True}
            for item in scopes
        ]
        
        transformed_bu_leads = [
            {"sponsor_first_name": item}
            for item in business_sponsor_lead
        ]

        # Transform key_results: "key_results" -> "kpi", "key_result" -> "name"
        transformed_kpi = [
            {"name": item["key_result"], "baseline_value": item["baseline_value"]}
            for item in key_results
        ]

        # Transform constraints: "constraint" -> "name"
        transformed_constraints = [
            {"name": item["constraint"], "type": item["type"]}
            for item in constraints
        ]

        # Transform portfolios: "portfolios" -> "portfolio_list", "id" -> "portfolio"
        # transformed_portfolio_list = [
        #     {"portfolio": item["id"], "name": item["name"]}
        #     for item in portfolios
        # ]
        transformed_portfolio_list = []
        for item in portfolios:
            if isinstance(item["id"], int) or isinstance(item["id"], float):
                transformed_portfolio_list.append({"portfolio": item["id"], "name": item["name"]})
            else:
                try:
                    _id = int(item["id"])
                    transformed_portfolio_list.append({"portfolio": _id, "name": item["name"]})
                except Exception as e:
                    print("wrong here --", e)
                    
                
        
        
        labour_budget = self.onboarding_agent_utils.calculate_labour_budget_from_roles(suggested_roles)
        non_labour_budget = self.onboarding_agent_utils.calculate_non_labour_budget_from_team(team)
        budget = labour_budget + non_labour_budget

        # Formatted JSON for POST request
        formatted_json = {
            "title": title,
            "description": description,
            "objectives": objectives,
            "scope": transformed_scope,  # Updated field name and structure
            "type": roadmap_type,
            "priority": priority,
            "start_date": start_date,
            "end_date": end_date,
            "budget": budget,
            "min_time_value": min_time_value,
            "min_time_value_type": min_time_value_type,
            "kpi": transformed_kpi,  # Updated field name and structure
            "constraints": transformed_constraints,  # Updated structure
            "team": team,  # Includes processed roles
            "suggested_roles": suggested_roles,
            "portfolio_list": transformed_portfolio_list,  # Updated field name and structure
            "portfolio_business_data": {},
            "category": category,
            "org_strategy_align": org_strategy_align,
            "business_case": None,
            "idea_list": [],
            "user_id": userId,
            "tenant_id": tenantId,
            "tango_analysis": tango_analysis,
            "portfolio_business_data": transformed_bu_leads
        }

        return formatted_json

    def format_json_for_roadmap_source(self, input_json):
        key_results = input_json.get('key_results', [])
        start_date = None
        end_date = None
        portfolio_list = []
        portfolio_business_data = {}
        idea_list = []
        business_case = None
        
        # Formatted JSON for POST request

        input_json["kpi"] = key_results
        input_json.pop('key_results', None)

        input_json["start_date"] = start_date
        input_json["end_date"] = end_date
        input_json["portfolio_list"] = portfolio_list
        input_json["portfolio_business_data"] = portfolio_business_data
        input_json["idea_list"] = idea_list
        input_json["business_case"] = business_case

        return input_json

    @activity("onboarding::roadmap::enhance_roadmap")
    def enhance_roadmap(self, llm, input_json, source, tenant_id, user_id):
        record("user_id", user_id)
        record("input_data", input_json)        
        record("description", "Takes the Tango JSON created for a user from their sources, and enhances it using Tango and web information.")
        enhancer = CreationEnhancer(llm=llm, input_data=input_json, enhance_type="roadmap", source=source, tenant_id=tenant_id, user_id=user_id)
        enhanced_json, enhanced_json_source = enhancer.enhance_roadmap()
        record("output_data", enhanced_json_source)
        return enhanced_json, enhanced_json_source

    def create_roadmap(self, tenant_id, user_id, input_json, llm, source = True, string_return = False):
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Save input JSON locally for debugging
        roadmap_title = input_json.get('title', 'Unnamed roadmap')
        
        input_json, input_json_source = self.enhance_roadmap(llm, input_json, source, tenant_id = tenant_id, user_id = user_id)
        appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_enhanced", "roadmap_title": roadmap_title})
        
        #### all roles in tenant ####
        all_roles = TenantDao.getDistinctAvailableRoles(tenant_id=tenant_id)
        
        #### I have the roadmaps full data for this customer and 
        #### required team roles also i have here from this data i created. in team array
        #### now I have to check the team resources avaialble
        #### by checking the old roadmaps created and not converted to project and project not ended
        all_roles_count_master_data = TenantDao.getRoleCountForTenant(tenant_id=tenant_id)

        #summation of all roles count for all roadmaps for a tenant
        all_roles_consumed_for_tenant = TenantDao.getAllRoadmapsRoleCountForTenant(tenant_id=tenant_id)
        
        #calculate Available Roles
        available_roles = self.onboarding_agent_utils.calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant)
        print("--debug available_roles---", available_roles)
        
        
        role_prompt = suggest_project_role_promptV2(input_json, all_roles, available_roles)
        # print("--debug role_prompt---", role_prompt.formatAsString())
       
        suggested_roles = llm.run(
            role_prompt, 
            ModelOptions(model="gpt-4o", max_tokens=16384, temperature=0.6),
            'agent::resource_planning_agent', 
            logInDb= {"tenant_id": tenant_id, "user_id": user_id}
        )
        print("--roadmap suggested roles--", suggested_roles)
        suggested_roles_json = extract_json_after_llm(suggested_roles)
        roadmap_role_thought = suggested_roles_json.get("thought_process_behind_the_above_list", "")
        suggested_roles_json = suggested_roles_json.get("recommended_project_roles", []) or []
        
        appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_roles_done", "roadmap_title": roadmap_title})
        request_data = self.format_json_for_roadmap(input_json, suggested_roles_json, roadmap_role_thought, userId=user_id, tenantId=tenant_id)
        
        
        request_data_source = self.format_json_for_roadmap_source(input_json=input_json_source)
        
        del request_data["suggested_roles"]
        # request_data["budget"] = 0
        
        
        
        print("debug --- roadmap finalrequest data", json.dumps(request_data, indent=4))
        
        response = requests.post(
            self.create_roadmap_url, headers=headers, json=request_data, timeout=4)

        # Print the response (status code and content)
        print("Status Code:", response.status_code)
        print("Response Content:", response.text)
        print("Request Data source:", request_data_source)
        
        ret_val = f"""
            Success or failure of this method
            Please analyse from this Response status: {response.status_code}
            and Response Text:  {response.text}
            
            If there is an error in creating the roadmap then respond with a meaningful response to the user
            
            Highlight the roadmap title
            
            And if this was a success. 
            Please provide the hyperlink to this project to the user 
            link should be like this - /actionhub/edit-roadmap/<project_id_check_from_response>
        """
        
        if string_return:
            return ret_val
        
        if response.status_code != 201:
            request_data_source = None
            
        appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_complete", "roadmap_title": roadmap_title})
        return (request_data_source, ret_val)



    def create_roadmap_from_text_input(self, tenant_id, user_id, input_data, llm, return_response=False, extra_data={}, source = True, string_return = False):
        headers = {
            'Content-Type': 'application/json'
        }
        

        enhancer = CreationEnhancer(llm = llm, input_data = {}, enhance_type="roadmap", source = source,  tenant_id = tenant_id, user_id = user_id)
        input_json = enhancer.enhance_roadmap_new(input_data, False)
        print("roadmap input json --- ", input_json)

        # all_roles = TenantDao.getDistinctAvailableRoles(tenant_id=tenant_id)
        
        # #### I have the roadmaps full data for this customer and 
        # #### required team roles also i have here from this data i created. in team array
        # #### now I have to check the team resources avaialble
        # #### by checking the old roadmaps created and not converted to project and project not ended
        # all_roles_count_master_data = TenantDao.getRoleCountForTenant(tenant_id=tenant_id)

        # #summation of all roles count for all roadmaps for a tenant
        # all_roles_consumed_for_tenant = TenantDao.getAllRoadmapsRoleCountForTenant(tenant_id=tenant_id)
        
        # #calculate Available Roles
        # available_roles = self.onboarding_agent_utils.calculate_available_roles(all_roles_count_master_data, all_roles_consumed_for_tenant)
        # print("--debug available_roles---", available_roles)
        
        
        # role_prompt = suggest_project_role_promptV2(input_json, all_roles, available_roles, '')
        # # print("--debug role_prompt---", role_prompt.formatAsString())
       
        # suggested_roles = self.llm.run(
        #     role_prompt, 
        #     ModelOptions(model="gpt-4.1", max_tokens=16384, temperature=0.1),
        #     'agent::resource_planning_agent', 
        #     logInDb= {"tenant_id": tenant_id, "user_id": user_id}
        # )
        # # print("--roadmap suggested roles--", suggested_roles)
        # suggested_roles_json = extract_json_after_llm(suggested_roles)
        # roadmap_role_thought = suggested_roles_json.get("thought_process_behind_the_above_list", "")
        # suggested_roles_json = suggested_roles_json.get("recommended_project_roles", []) or []
        
        # appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_roles_done", "roadmap_title": roadmap_title})
        request_data = self.format_json_for_roadmap(input_json, suggested_roles=[], roadmap_role_thought="", userId=user_id, tenantId=tenant_id)
        if "category" in extra_data:
            request_data["category"] += ", ".join(extra_data.get("category"))
        # if "title" in extra_data:
        #     request_data["title"] = extra_data.get("title")
            
        
        
        # del request_data["suggested_roles"]
        
        print("debug --- roadmap finalrequest data", json.dumps(request_data, indent=4))
        
        response = requests.post(
            self.create_roadmap_url, 
            headers=headers, 
            json=request_data, 
            timeout=4
        )

        # Print the response (status code and content)
        print("Status Code:", response.status_code)
        print("Response Content:", response.text)
        # print("Request Data source:", request_data_source)
        # if return_response:
        #     return response
        
        ret_val = f"""
            Success or failure of this method
            Please analyse from this Response status: {response.status_code}
            and Response Text:  {response.text}
            
            If there is an error in creating the roadmap then respond with a meaningful response to the user
            
            Highlight the roadmap title
            
            And if this was a success. 
            Please provide the hyperlink to this project to the user 
            link should be like this - /actionhub/edit-roadmap/<project_id_check_from_response>
        """
        
        # if string_return:
        #     return ret_val
        
        # if response.status_code != 201:
        #     request_data_source = None
            
        # appLogger.info({"event":"onboarding:roadmap","msg": "roadmap_complete", "roadmap_title": roadmap_title})
        return ret_val
