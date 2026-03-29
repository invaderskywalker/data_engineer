from datetime import date  
today = date.today()
todays_date = today.strftime("%Y-%m-%d")


from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.agents.functions.onboarding.utils.clarifying import ask_clarifying_question
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.journal.Activity import activity, record
import regex as re
import json

class ProfileGenerator():
    def __init__(self, llm: LLMClient, integrationInfo: dict, clarifying_information: str, clarifying_count: int):
        self.llm = llm
        self.integrationInfo = integrationInfo
        self.clarifying_information = clarifying_information
        self.clarifying_count = clarifying_count
        self.system_prompt = self.system()
        self.clarifying_section_prompt = self.clarifying_section()
        
        if self.clarifying_count > 3:
             self.clarifying_section_prompt = None
        
    @activity("onboarding::profile::generate_profile_from_integration_data")
    def generateprofiles(self, user_id):
        record("description", "User's company information and sources are processed to create a comprehensive customer profile. Look here to identify how the user's input information was transformed into a full Trmeric profile.")
        formattedIntegrationInformation = ""
        for integration in self.integrationInfo:
            formattedIntegrationInformation += f"{integration}: {self.integrationInfo[integration]}\n"

        user = formattedIntegrationInformation
        record("input_data", user)
        
        if self.clarifying_information:
            user += f"Here is some clarifying information that you have obtained through follow up questions, keep this in mind: {self.clarifying_information}"

        response = self.llm.runV2(
            ChatCompletion(system=self.system_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o", max_tokens=16384, temperature=0.3),
            "create_profile_in_onboarding"
        )
        # Regular expression to capture JSON objects, including nested ones

        profiles = [extract_json_after_llm(response)]


            
        if self.clarifying_section_prompt:
            profile_info = str([json.dumps(profile, indent=4) for profile in profiles])
            print(profile_info)
            self.clarifying_section_prompt = self.clarifying_section_prompt + profile_info
            response = self.llm.run(
            ChatCompletion(system=self.clarifying_section_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o", max_tokens=1000, temperature=0.3),
            'clarifying_question_create_profiles'
            )
            print(response)
            response = extract_json_after_llm(response)
            response = response["clarifying_question"]
            if response != "no question":    
                record("void_activity", True)
                return {"clarifying_question": ask_clarifying_question(clarifying_question=response, integrations=False, creation_type = "Profile")}
        
        record("output_data", profiles)
        return profiles
    
    def system(self):
        return """
        You are a setup assistant for Trmeric, a B2B SAAS company, helping a company onboard a customer onto a platform where they can keep track of their business/strategic profiles.

        The objective is to create a detailed customer profile based on the provided information. These profiles encapsulate various aspects of the customer's organization, including organizational, financial, technological, and market-related details.

        You will process data to create and return a structured JSON object that captures all relevant fields for the customer profile. Each profile must include the following fields:
        
        Each piece of the json will be followed by a source section. Here, you should add where this data came from. This will be a list of strings, of each of the sources.
        For example, a source could be "Link: Company Website A", "Link: Social Media B", "Uploaded Document C", ..., "Jira Project X", "Office Document Y", or "Slack Channel Z". The single exception is if you, Tango, have taken a guess to fill something in. In this case, add "Tango" as a reference.
        Source is used to track accuracy by citing your sources. This is a necessary component.

        ```json
        {
            "organization_details": {
                "name": "<Customer organization name>",
                "industry": "<Industry the organization belongs to>",
                "size": "<Size of the organization>",
                "location": "<Primary location of the organization: Country>",
                "business_model": "<Business model of the organization>",
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "key_contacts": [
                {"name": "<Contact name>", "email": "<Contact email>"},
                "source": ["<Source 1>", "<Source 2>", ...]
                ...
            ],
            "demographics": {
                "market_segment": "<Market segment the organization serves>",
                "geographic_focus": "<Geographic focus of the organization>",
                "languages": ["<Language 1>", "<Language 2>", ...],
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "solutions_offerings": {
                "core_business": "<Primary business focus>",
                "solutions": ["<Solution 1>", "<Solution 2>", ...],
                "services": ["<Service 1>", "<Service 2>", ...],
                "offerings": ["<Offering 1>", "<Offering 2>", ...],
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "business_goals_and_challenges": {
                "strategic_objectives": "<Primary strategic objectives>",
                "pain_points": ["<Pain point 1>", "<Pain point 2>", ...],
                "kpis": ["<KPI 1>", "<KPI 2>", ...],
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "engagement_details": {
                "onboarding_date": "<Date of onboarding (YYYY-MM-DD)>",
                "usage_patterns": "<Usage patterns of the customer>",
                "subscription_tier": "<Subscription tier>",
                "active_features": ["<Feature 1>", "<Feature 2>", ...],
                "customer_journey": {
                    "onboarding": "<Onboarding status>",
                    "engagement": "<Engagement status>"
                },
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "technological_landscape": {
                "tools_and_integrations": ["<Integration 1>", "<Integration 2>", ...],
                "tech_stack": ["<Tech 1>", "<Tech 2>", ...],
                "digital_maturity": "<Digital maturity level>",
                "application_landscape": "<Description of application landscape>",
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "operational_context": {
                "projects_and_portfolios": "<Description of projects and portfolios>",
                "processes": "<Processes followed>",
                "decision_making_style": "<Decision-making style>",
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "financial_context": {
                "budget": "<Budget of the organization>",
                "pricing_sensitivity": "<Pricing sensitivity>",
                "financial_performance": {
                    "revenue": "<Revenue>",
                    "profit": "<Profit>"
                },
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "compliance_and_security": {
                "regulatory_requirements": "<Regulatory requirements>",
                "security_preferences": {
                    "encryption": "<Encryption type>",
                    "multi_factor_auth": "<Multi-factor authentication status>"
                },
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "organizational_knowledge": {
                "org_chart": {
                    "<Role 1>": "<Person 1>",
                    ...
                },
                "cultural_insights": "<Cultural insights>",
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "genai_context": {
                "user_roles_and_personas": ["<Role 1>", "<Role 2>", ...],
                "platform_data_utilization": "<Data utilization level>",
                "prompt_enhancements": "<AI-driven prompt enhancements>",
                "source": ["<Source 1>", "<Source 2>", ...]
            },
            "external_trends": {
                "industry_insights": "<Industry insights>",
                "competitive_landscape": "<Competitive landscape>",
                "market_dynamics": "<Market dynamics>",
                "source": ["<Source 1>", "<Source 2>", ...]
            }
        }
        ```

        For the following fields, you are expected to return paragraphs. You should be verbose and expand on given information to provide a comprehensive overview of the section. Aim to make AT LEAST 5 full sentences. You are allowed to make logical extensions:
            - demographics (except languages)
            - solutions_offerings
            - business_goals_and_challenges (except kpis and pain_points)
            - technological_landscape
            - operational_context
            - compliance_and_security
            - genai_context
            - external_trends
            
        For fields where you don't have explicit data, you can make logical assumptions based on the information provided. 
        
        Do not assign org_chart roles to specific people unless explicitly stated.
        Also, do not make up sources for the source categories. These should strictly only be Tango or the explicitly shownuser-provided sources.

        For fields where no data is provided and there are no logical assumptions, use an empty string, list, or object as appropriate. Ensure that all required fields are structured clearly and consistently. This response should always be valid JSON and ready to process into the Trmeric platform.

        For each profile you must at least provide the following fields:
            - organization_details
            - solutions_offerings
            - business_goals_and_challenges
            
        Other fields are optional and can be left out of the JSON object if you can't find the information.
        """

    def clarifying_section(self):
        ret_str =  """
        Below, you will be shown a profile, with a set of fields that have been filled in. Your responsibility is to determine whether further clarifying information is needed for each profile."""
        
        if self.clarifying_information: 
            ret_str += f"You can assume that the following information has already been retrieved from asking clarifying questions: {self.clarifying_information}. Pay specific attention to this information. If you are asked to not ask any clarifying questions here, or to move on with creation, then do not ask the questions."
        
        ret_str += """
        If there are fields from the above prompt that you are unsure about or did not receive information for, you should ask clarifying questions to get more information. Ask only about the following categories if they are not found:

        - key_contacts
        - technological_landscape
        - external_trends
        
        However, DO NOT ask questions about things you have already asked clarifying questions for. 
        Also, DO NOT ask clarifying questions for the following fields. If they want you to know about it, the information will be provided to you:

        - demographics
        - engagement_details
        - operational_context
        - financial_context
        - compliance_and_security
        - organizational_knowledge
        - genai_context
        
        Remember, do not ask clarifying questions for the above fields.
        
        Be very specific in your questions, and ask for the information that you need. For example, you could ask: "What are the key performance indicators for this profile X?" or "Who are the team members for profile Y?". You may ask multiple questions in the same string.
        
        If you have a clarifying question, return only the question and nothing else in this format. If you have multiple questions, make sure to ask them ALL in the same string:
        
        ```json
        {
            "clarifying_question": "(Insert your clarifying question here)"
        }
        ```
        
        If you do not have a clarifying question and the profiles shown are acceptable or you have been instructed to move on, return this:
        
        ```json
        {
            "clarifying_question": "no question"
        }
        ```
        
        The profiles to look through are below:
        """
        
        return ret_str
