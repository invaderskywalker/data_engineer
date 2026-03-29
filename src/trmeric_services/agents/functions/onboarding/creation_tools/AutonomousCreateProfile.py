import requests
import json
import os
from src.trmeric_services.agents.functions.onboarding.utils.enhance import CreationEnhancer
from src.trmeric_services.journal.Activity import activity, record

class ProfileAgent:
    def __init__(self):
        self.create_profile_url = os.getenv(
            "DJANGO_BACKEND_URL") + "api/customer/internal/create"
    
    def format_json_for_profile(self, input_json, userId, tenantId):
        # Extracting and structuring data based on the updated fields
        formatted_json = {
            "user_id": userId,
            "tenant_id": tenantId,
            "profile_data":{
                "organization_details": {
                    "name": input_json.get("organization_details", {}).get("name", ""),
                    "industry": input_json.get("organization_details", {}).get("industry", ""),
                    "size": input_json.get("organization_details", {}).get("size", ""),
                    "location": input_json.get("organization_details", {}).get("location", ""),
                    "business_model": input_json.get("organization_details", {}).get("business_model", "")
                },
                "key_contacts": input_json.get("key_contacts", []),
                "demographics": {
                    "market_segment": input_json.get("demographics", {}).get("market_segment", ""),
                    "geographic_focus": input_json.get("demographics", {}).get("geographic_focus", ""),
                    "languages": input_json.get("demographics", {}).get("languages", [])
                },
                "solutions_offerings": {
                    "core_business": input_json.get("solutions_offerings", {}).get("core_business", ""),
                    "solutions": input_json.get("solutions_offerings", {}).get("solutions", []),
                    "services": input_json.get("solutions_offerings", {}).get("services", []),
                    "offerings": input_json.get("solutions_offerings", {}).get("offerings", [])
                },
                "business_goals_and_challenges": {
                    "strategic_objectives": input_json.get("business_goals_and_challenges", {}).get("strategic_objectives", ""),
                    "pain_points": input_json.get("business_goals_and_challenges", {}).get("pain_points", []),
                    "kpis": input_json.get("business_goals_and_challenges", {}).get("kpis", [])
                },
                "engagement_details": {
                    "onboarding_date": input_json.get("engagement_details", {}).get("onboarding_date", ""),
                    "usage_patterns": input_json.get("engagement_details", {}).get("usage_patterns", ""),
                    "subscription_tier": input_json.get("engagement_details", {}).get("subscription_tier", ""),
                    "active_features": input_json.get("engagement_details", {}).get("active_features", []),
                    "customer_journey": input_json.get("engagement_details", {}).get("customer_journey", {})
                },
                "technological_landscape": {
                    "tools_and_integrations": input_json.get("technological_landscape", {}).get("tools_and_integrations", []),
                    "tech_stack": input_json.get("technological_landscape", {}).get("tech_stack", []),
                    "digital_maturity": input_json.get("technological_landscape", {}).get("digital_maturity", ""),
                    "application_landscape": input_json.get("technological_landscape", {}).get("application_landscape", "")
                },
                "operational_context": {
                    "projects_and_portfolios": input_json.get("operational_context", {}).get("projects_and_portfolios", ""),
                    "processes": input_json.get("operational_context", {}).get("processes", ""),
                    "decision_making_style": input_json.get("operational_context", {}).get("decision_making_style", "")
                },
                "financial_context": {
                    "budget": input_json.get("financial_context", {}).get("budget", ""),
                    "pricing_sensitivity": input_json.get("financial_context", {}).get("pricing_sensitivity", ""),
                    "financial_performance": input_json.get("financial_context", {}).get("financial_performance", {})
                },
                "compliance_and_security": {
                    "regulatory_requirements": input_json.get("compliance_and_security", {}).get("regulatory_requirements", ""),
                    "security_preferences": input_json.get("compliance_and_security", {}).get("security_preferences", {})
                },
                "organizational_knowledge": {
                    "org_chart": input_json.get("organizational_knowledge", {}).get("org_chart", {}),
                    "cultural_insights": input_json.get("organizational_knowledge", {}).get("cultural_insights", "")
                },
                "genai_context": {
                    "user_roles_and_personas": input_json.get("genai_context", {}).get("user_roles_and_personas", []),
                    "platform_data_utilization": input_json.get("genai_context", {}).get("platform_data_utilization", ""),
                    "prompt_enhancements": input_json.get("genai_context", {}).get("prompt_enhancements", "")
                },
                "external_trends": {
                    "industry_insights": input_json.get("external_trends", {}).get("industry_insights", ""),
                    "competitive_landscape": input_json.get("external_trends", {}).get("competitive_landscape", ""),
                    "market_dynamics": input_json.get("external_trends", {}).get("market_dynamics", "")
                }
            }
        }
        return formatted_json
    
    def format_json_for_profile_source(self, input_json, userId, tenantId):
        formatted_json = {
            "profile_data":{
                "organization_details": {
                    "name": input_json.get("organization_details", {}).get("name", ""),
                    "industry": input_json.get("organization_details", {}).get("industry", ""),
                    "size": input_json.get("organization_details", {}).get("size", ""),
                    "location": input_json.get("organization_details", {}).get("location", ""),
                    "business_model": input_json.get("organization_details", {}).get("business_model", ""),
                    "source": input_json.get("organization_details", {}).get("source", [])
                },
                "key_contacts": input_json.get("key_contacts", []),
                "demographics": {
                    "market_segment": input_json.get("demographics", {}).get("market_segment", ""),
                    "geographic_focus": input_json.get("demographics", {}).get("geographic_focus", ""),
                    "languages": input_json.get("demographics", {}).get("languages", []),
                    "source": input_json.get("demographics", {}).get("source", [])
                },
                "solutions_offerings": {
                    "core_business": input_json.get("solutions_offerings", {}).get("core_business", ""),
                    "solutions": input_json.get("solutions_offerings", {}).get("solutions", []),
                    "services": input_json.get("solutions_offerings", {}).get("services", []),
                    "offerings": input_json.get("solutions_offerings", {}).get("offerings", []),
                    "source": input_json.get("solutions_offerings", {}).get("source", [])
                },
                "business_goals_and_challenges": {
                    "strategic_objectives": input_json.get("business_goals_and_challenges", {}).get("strategic_objectives", ""),
                    "pain_points": input_json.get("business_goals_and_challenges", {}).get("pain_points", []),
                    "kpis": input_json.get("business_goals_and_challenges", {}).get("kpis", []),
                    "source": input_json.get("business_goals_and_challenges", {}).get("source", [])
                },
                "engagement_details": {
                    "onboarding_date": input_json.get("engagement_details", {}).get("onboarding_date", ""),
                    "usage_patterns": input_json.get("engagement_details", {}).get("usage_patterns", ""),
                    "subscription_tier": input_json.get("engagement_details", {}).get("subscription_tier", ""),
                    "active_features": input_json.get("engagement_details", {}).get("active_features", []),
                    "customer_journey": input_json.get("engagement_details", {}).get("customer_journey", {}),
                    "source": input_json.get("engagement_details", {}).get("source", [])
                },
                "technological_landscape": {
                    "tools_and_integrations": input_json.get("technological_landscape", {}).get("tools_and_integrations", []),
                    "tech_stack": input_json.get("technological_landscape", {}).get("tech_stack", []),
                    "digital_maturity": input_json.get("technological_landscape", {}).get("digital_maturity", ""),
                    "application_landscape": input_json.get("technological_landscape", {}).get("application_landscape", ""),
                    "source": input_json.get("technological_landscape", {}).get("source", [])
                },
                "operational_context": {
                    "projects_and_portfolios": input_json.get("operational_context", {}).get("projects_and_portfolios", ""),
                    "processes": input_json.get("operational_context", {}).get("processes", ""),
                    "decision_making_style": input_json.get("operational_context", {}).get("decision_making_style", ""),
                    "source": input_json.get("operational_context", {}).get("source", [])
                },
                "financial_context": {
                    "budget": input_json.get("financial_context", {}).get("budget", ""),
                    "pricing_sensitivity": input_json.get("financial_context", {}).get("pricing_sensitivity", ""),
                    "financial_performance": input_json.get("financial_context", {}).get("financial_performance", {}),
                    "source": input_json.get("financial_context", {}).get("source", [])
                },
                "compliance_and_security": {
                    "regulatory_requirements": input_json.get("compliance_and_security", {}).get("regulatory_requirements", ""),
                    "security_preferences": input_json.get("compliance_and_security", {}).get("security_preferences", {}),
                    "source": input_json.get("compliance_and_security", {}).get("source", [])
                },
                "organizational_knowledge": {
                    "org_chart": input_json.get("organizational_knowledge", {}).get("org_chart", {}),
                    "cultural_insights": input_json.get("organizational_knowledge", {}).get("cultural_insights", ""),
                    "source": input_json.get("organizational_knowledge", {}).get("source", [])
                },
                "genai_context": {
                    "user_roles_and_personas": input_json.get("genai_context", {}).get("user_roles_and_personas", []),
                    "platform_data_utilization": input_json.get("genai_context", {}).get("platform_data_utilization", ""),
                    "prompt_enhancements": input_json.get("genai_context", {}).get("prompt_enhancements", ""),
                    "source": input_json.get("genai_context", {}).get("source", [])
                },
                "external_trends": {
                    "industry_insights": input_json.get("external_trends", {}).get("industry_insights", ""),
                    "competitive_landscape": input_json.get("external_trends", {}).get("competitive_landscape", ""),
                    "market_dynamics": input_json.get("external_trends", {}).get("market_dynamics", ""),
                    "source": input_json.get("external_trends", {}).get("source", [])
                }
            }
        }
        return formatted_json

    @activity("onboarding::profile::enhance_profile")
    def enhance_profile(self, llm, input_json, user_id, tenant_id):
        record("input_data", input_json)
        record("description", "Takes the Tango JSON created for a user from their sources, and enhances it using Tango and web information.")
        enhanced_json, enhanced_json_source = CreationEnhancer(llm=llm, input_data=input_json, enhance_type="profile", user_id=user_id, tenant_id=tenant_id).enhance()
        record("output_data", enhanced_json_source)
        return enhanced_json, enhanced_json_source

    def create_profile(self, tenant_id, user_id, input_json, llm):
        headers = {
            'Content-Type': 'application/json'
        }

        print("Input JSON before enhancing", json.dumps(input_json, indent=4))
        response, source_repsonse = self.enhance_profile(llm, input_json, user_id, tenant_id)
        print("Input JSON after enhancing", json.dumps(input_json, indent=4))

        # Format the input JSON using the helper function
        request_data = self.format_json_for_profile(
            response, userId=user_id, tenantId=tenant_id)
        
        request_data_source = self.format_json_for_profile_source(
            source_repsonse, userId=user_id, tenantId=tenant_id)
        
        # Debug output
        print("Request Data:", json.dumps(request_data, indent=4))
        
        response = requests.post(
            self.create_profile_url, headers=headers, json=request_data, timeout=4
        )

        print("Status Code:", response.status_code)
        print("Response Content:", response.text)
        print(json.dumps(request_data_source, indent=4))
        
        ret_val = f"""
            Success or failure of this method
            Please analyse from this Response status: {response.status_code}
            and Response Text:  {response.text}
            
            If there is an error in creating the profile then respond with a meaningful response to the user
            
            Highlight the profile title
        """
        
        if response.status_code != 201:
            request_data = None

        return (request_data_source, ret_val)
