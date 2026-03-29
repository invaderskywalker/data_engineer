from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from datetime import date
from src.trmeric_database.dao.customer import CustomerDao
from src.trmeric_database.dao import IdeaDao, RoadmapDao
from src.trmeric_services.phoenix.nodes.web_search import WebSearchNode
import json
import re
import datetime
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient


today = date.today()
todays_date = today.strftime("%Y-%m-%d")
types = ["profile", "project", "roadmap"]

class CreationEnhancer:
    def __init__(self, llm: LLMClient, input_data, enhance_type: str, source: bool = True, **kwargs):
        self.llm = llm or ChatGPTClient()
        self.tenant_id = kwargs.get("tenant_id")
        self.user_id = kwargs.get("user_id")
        self.org_aligns = ", ".join([entry["title"] for entry in RoadmapDao.fetchOrgStrategyAlignMentOfTenant(self.tenant_id)])
        self.templates = {
            "profile": self.profile_template(),
            "project": self.project_template(),
            "roadmap": self.roadmap_template()
        }
        self.enhance_type = enhance_type
        self.template = self.templates[enhance_type]
        self.input_data = input_data
        self.source = source
        
        

    def profile_template(self):
        return """
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
                ...
            ],
            "source_key_contacts": ["<Source 1>", "<Source 2>", ...],
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
            
        For fields where you don't have explicit data, you can make logical assumptions based on the information provided. Do not assign org_chart roles to specific people unless explicitly stated.
        Also, do not make up sources for the source categories. These should strictly only be Tango or the explicitly shownuser-provided sources.
        For fields where no data is provided and there are no logical assumptions, use an empty string, list, or object as appropriate. Ensure that all required fields are structured clearly and consistently. This response should always be valid JSON and ready to process into the Trmeric platform.
        """

    def project_template(self):
        return """
        ```json
        {
            "state": <State of the project: ONLY either "Build", "Design", "Discovery", or "Complete">,
            "title": "<Provide the full name of the project here>",
            "description": "<Provide a detailed and comprehensive description of the project, including goals, objectives, and overall purpose>",
            "source_description": ["<Source 1 for description above>", "<Source 2 for description above>", ...],
            "objectives": "<Provide a string of objectives for the project>",
            "source_objectives": ["<Source 1 for objectives above>", "<Source 2 for objectives above>", ...],
            "total_external_spend": "<Provide the total external spend for the project only as an integer>",
            "source_total_external_spend": ["<Source 1 for total external spend above>", "<Source 2 for total external spend above>", ...],
            "technology_stack": "<Comma-separated list of technologies used in the project>",
            "source_tech_stack": ["<Source 1 for tech stack above>", "<Source 2 for tech stack above>", ...],
            "project_location": "<comma-separated string of only: "USA", "Europe", "Latin America", "India", "Middle East", "Africa", "APAC">",
            "source_project_location": ["<Source 1 for project location above>", "<Source 2 for project location above>", ...],
            "project_type": "<string of either 'Transform', 'Run', or 'Innovate'>",
            "project_category": "<Provide the category of the project such as Data Science, etc..>",
            "internal_project": <true or false (depending on whether or not there are external partners) >,
            "start_date": "<Provide the start date of the project in a string of 'YYYY-MM-DD'>",
            "source_start_date": ["<Source 1 for start date above>", "<Source 2 for start date above>", ...]
            "end_date": "<Provide the end date of the project in a string of 'YYYY-MM-DD'>",
            "source_end_date": ["<Source 1 for end date above>", "<Source 2 for end date above>", ...],
            "scope": "<Comma separated string of scopes for the project>",
            "sdlc_method": "<Provide the SDLC methodology used in the project, choose out of: "Agile", "Waterfall", "Hybrid">",
            "org_strategy_align": "<Provide a string from the options: {""" + self.org_aligns + """} >", 
            "kpi": [
                {
                    "name": "<String of key performance indicator 1 relevant to the project>"
                },
                {
                    "name": "<String of key performance indicator 2 relevant to the project>"
                }, 
                ...
            ],
            "source_kpi": ["<Source 1 for KPIs above>", "<Source 2 for KPIs above>", ...]",
            "portfolio_list": [{portfolio: <portfolio_id>}, {portfolio: <portfolio_id>}, ...],
            "team": [
                {
                    "name": "<Name of the Team>",
                    "milestones": [
                        {
                            "name": "<Name of the Scope Milestone>",
                            "type": 2,
                            "target_date": "<Target Date of the Milestone in a string of 'YYYY-MM-DD'>",
                        },
                        {
                            <other Scope Milestones>
                        },
                        {
                            "name": "<Name of the Spend Milestone>",
                            "type": 3,
                            "planned_spend": "<Planned Spend for the Milestone only as an integer>",
                            "target_date": "<Target Date of the Milestone in a string of 'YYYY-MM-DD'>"
                        },
                        {
                            <other Spend Milestones>
                        }
                    ],
                    "source_milestones": ["<Source 1 for milestones above>", "<Source 2 for milestones above>", ...],
                }
            ], ...
        }
        ```

        Here are some important rules you must follow: 
        
        1. KPIs are key performance indicators that are used to measure the success of a project. For example, if you are building a website, a KPI could be the number of users that visit the website.
        2. For Portfolios, you can ONLY choose exact strings of the provided portfolios listed below. DO NOT create new ones and if you are not sure, leave no entries in the portfolio_list.
        3. For above reference, examples of tech_stack could be "Python, Django, React, PostgreSQL". 
        4. The default value for target_date should be today's date:""" + str(todays_date) + """
        5. Do not make up sources for the source categories. These should strictly only be Tango or the explicitly shown user-provided sources.
        6. If you are given options in the above prompt, ONLY choose from them. For example, stage can only be one of "Build", "Design", "Discovery", or "Complete".
        7. As you enhance now, if tech stack, milestones, or kpis are not provided, you can make reasonable assumptions and fill in these sections based on what they could be.
        """

    def roadmap_template(self):
        return """
        ```json
        {
            "title": "<name of the roadmap>",
            "description": "<detailed summary of the roadmap’s purpose, scope, and key components, e.g., 'Automate QA testing with AI to improve efficiency'>",
            "source_description": ["<Source 1, e.g., 'Jira Project X' or 'Tango'>", ...],
            "objectives": "<descriptive primary goals, e.g., 'Reduce testing time by 20% through AI-driven automation across regression suites'>",
            "source_objectives": ["<Source 1>", ...],
            "scopes": [
                {
                    "scope": "<descriptive deliverables>",
                    "selected": true
                },...
            ],
            "portfolio": "<portfolio name, e.g., 'QA Platform' or 'Sales Division'>",
            "source_portfolio": ["<Source 1>", ...],
            "priority": <integer: 1=High, 2=Medium, 3=Low>,
            "key_results": [
                {
                    "key_result": "<descriptive measurable outcome or target>",
                    "baseline_value": "<specific target, e.g., '95%', '50ms', 'target'>"
                }, ...
            ],
            "source_key_results": ["<Source 1>", ...],
            "start_date": "<YYYY-MM-DD, e.g., '2025-04-01'>",
            "source_start_date": ["<Source 1>", ...],
            "end_date": "<YYYY-MM-DD, e.g., '2025-09-01'>",
            "source_end_date": ["<Source 1>", ...],
            "team": [
                {
                    "name": "<non-labor resource, e.g., 'AWS Cloud Hosting for AI models'>",
                    "estimate_value": <integer: cost in monetary units, e.g., 20000>,
                    "labour_type": 2
                }, ...
            ],
            "thought_process_behind_non_labor_team": "", // make it descriptive so that we can understand why you suggested and why you presented with estimated value
            "source_team": ["<Source 1>", ...],
            "type": <integer: 1=Program, 2=Project, 3=Enhancement>,
            "org_strategy_align": "<exact text from input aligning with org strategy, max 250 chars, e.g., 'Supports goal to enhance testing speed'>",
            "source_org_strategy_align": ["<Source 1>", ...],
            "constraints": [
                {
                    "constraint": "<descriptive limit, e.g., 'Budget restricted to $100k due to fiscal year-end'>",
                    "type": <integer: 1=Cost, 2=Resource, 3=Risk, 4=Scope, 5=Quality, 6=Time>
                }, ...
            ],
            "source_constraints": ["<Source 1>", ...],
            "min_time_value": <integer: min time post-release, e.g., 3>,
            "source_min_time_value": ["<Source 1>", ...],
            "min_time_value_type": <integer: 1=days, 2=weeks, 3=months, 4=years>,
            "portfolios": [{
                "id": "",// id of applicable portfolio from doc
                "name": "", // name of aplicable portfolio from doc
            }],
            "business_sponsor_lead": [],
        }
        ```
        """

    def system_prompt(self, enhance_type, input_data, template):
        if enhance_type == "roadmap":
            system = f"""
        ROLE: You’re a business planning expert tasked with transforming a roadmap into a detailed, executable plan. Your mission is to make it vivid, professional, and bulletproof.

        MISSION:
        Enhance the roadmap’s fields (`title`, `description`, `objectives`, `scope`, `key_results`, `start_date`, `end_date`, `priority`, `type`, `team`, `budget`, `constraints`, `org_strategy_align`, `portfolio`) using:
        - Provided roadmap data (<current_roadmap>)
        - Web search data (<web_search>)
        - Customer context (if available)
        - DO NOT USE Tango Memory Insights to create new projects or roadmaps.
        Overthink every field—pack it with specifics, metrics, tasks, and justification. Don’t alter the core meaning, only enrich it.

        ENHANCEMENT RULES:
        - **Description**: Craft a rich, vivid summary with tools, outcomes, and key components (e.g., "Leverage AI analytics to cut QA errors"). Retain all key details from the input description—don’t omit anything critical.
        - **Objectives**: Make descriptive and actionable, adding execution context (e.g., "Reduce testing time by 20% via AI automation across regression suites").
        - **Scope**: Create rich and multiple scope items, detailed deliverables and boundaries after analyzing execution steps (e.g., "Develop AI test generation integrated with CI/CD, excludes legacy UI upgrades").
        - **Key Results**: Create rich and multiple key result items, measurable outcomes with specific, post-completion targets (e.g., "Achieve 95% defect detection with AI tools by project end"). Tie to objectives and scope.
        - **Constraints**: Enhance with concise, relevant context from input or web data (e.g., "Budget capped at $100k due to fiscal limits, per Gartner 2023"). Avoid speculative additions.
        - **Team**: Include *only non-labor costs* (`labour_type: 2`). Replace labor-like entries with specific resources (e.g., "Software License" instead of "Team"). Suggest items from web data or project needs.
        - **Thought Process Behind Non-Labor Team**: Write a detailed, plain-text explanation justifying each non-labor resource (e.g., "AWS Hosting ($20k) for scalable AI, per industry benchmarks; Training Software ($5k) for staff adoption, tied to scope"). Cite sources and project relevance.
        - **Budget**: Do not generate unless if already provided
        - **Reasoning**: Cite sources (e.g., "Gartner 2023"), explain trade-offs (e.g., "Cut scope to fit budget").
        - **Integrity**: Use only provided data or web search—don’t invent unsourced info.
        - **Output Format**: STRICTLY ADHERE TO THE TEMPLATE GIVEN BELOW. Do not alter the structure or keys. 

        OUTPUT:
        Return a JSON matching the input format, with enriched values. Keep all keys intact.

        INPUT DATA:
        <current_roadmap>
        {input_data}
        <current_roadmap>

        WEB SEARCH DATA:
        <web_search>
        {template}
        <web_search>
        """
        elif enhance_type == "project":
            system = f"""
            ROLE: You’re a project management expert tasked with transforming a project description into a detailed, well-structured project plan.

            MISSION:
            Enhance the project's fields (`state`, `title`, `description`, `objectives`, `total_external_spend`, `technology_stack`, `project_location`, `project_type`, `project_category`, `internal_project`, `start_date`, `end_date`, `sdlc_method`, `kpi`, `team`) using:
            - Provided project data (<current_project>)
            - Web search data (<web_search>)
            - Customer context (if available)
            Overthink every field—pack it with specifics, metrics, tasks, and justification. Don’t alter the core meaning, only enrich it.

            ENHANCEMENT RULES:
            - **Description**: Craft a rich, vivid summary of the project, including goals, objectives, and overall purpose.
            - **Objectives**: Make descriptive and actionable, adding execution context.
            - **Technology Stack**: If not provided, suggest a relevant tech stack based on the project description and web search.
            - **KPIs**: If not provided, suggest relevant key performance indicators to measure project success.
            - **Team & Milestones**: If not provided, create a sample team with relevant scope and spend milestones. Default target_date for milestones should be today's date: {todays_date}.
            - **Dates**: Ensure start and end dates are logical.
            - **Budget**: Do not change any existing values of budget

            STYLE:
            - Smart and professional.
            - Provide clear and concise information.

            OUTPUT:
            Return a JSON matching the input format, with enriched values. Keep all keys intact.

            INPUT DATA:
            <current_project>
            {input_data}
            <current_project>

            WEB SEARCH DATA:
            <web_search>
            {template}
            <web_search>
            """
        elif enhance_type == "profile":
            system = f"""
            ROLE: You are a business analyst expert tasked with creating a comprehensive and detailed customer profile.

            MISSION:
            Enhance the customer profile's fields using provided data and web search data. The fields are: `organization_details`, `key_contacts`, `demographics`, `solutions_offerings`, `business_goals_and_challenges`, `engagement_details`, `technological_landscape`, `operational_context`, `financial_context`, `compliance_and_security`, `organizational_knowledge`, `genai_context`, `external_trends`.

            ENHANCEMENT RULES:
            - For the following fields, you are expected to return paragraphs. You should be verbose and expand on given information to provide a comprehensive overview of the section. Aim to make AT LEAST 5 full sentences. You are allowed to make logical extensions:
                - `demographics` (except languages)
                - `solutions_offerings`
                - `business_goals_and_challenges` (except kpis and pain_points)
                - `technological_landscape`
                - `operational_context`
                - `compliance_and_security`
                - `genai_context`
                - `external_trends`
            - For fields where you don't have explicit data, you can make logical assumptions based on the information provided.
            - Do not assign `org_chart` roles to specific people unless explicitly stated.
            - For fields where no data is provided and there are no logical assumptions, use an empty string, list, or object as appropriate.

            STYLE:
            - Professional and detailed.
            - Ensure that all required fields are structured clearly and consistently.

            OUTPUT:
            Return a valid JSON matching the input format, ready to process into the Trmeric platform.

            INPUT DATA:
            <current_profile>
            {input_data}
            <current_profile>

        WEB SEARCH DATA:
        <web_search>
        {template}
        <web_search>
        """
        elif enhance_type == "project":
            system = f"""
            ROLE: You’re a project management expert tasked with transforming a project description into a detailed, well-structured project plan.

            MISSION:
            Enhance the project's fields (`state`, `title`, `description`, `objectives`, `total_external_spend`, `technology_stack`, `project_location`, `project_type`, `project_category`, `internal_project`, `start_date`, `end_date`, `sdlc_method`, `kpi`, `team`) using:
            - Provided project data (<current_project>)
            - Web search data (<web_search>)
            - Customer context (if available)
            Overthink every field—pack it with specifics, metrics, tasks, and justification. Don’t alter the core meaning, only enrich it.

            ENHANCEMENT RULES:
            - **Description**: Craft a rich, vivid summary of the project, including goals, objectives, and overall purpose.
            - **Objectives**: Make descriptive and actionable, adding execution context.
            - **Technology Stack**: If not provided, suggest a relevant tech stack based on the project description and web search.
            - **KPIs**: If not provided, suggest relevant key performance indicators to measure project success.
            - **Team & Milestones**: If not provided, create a sample team with relevant scope and spend milestones. Default target_date for milestones should be today's date: {todays_date}.
            - **Dates**: Ensure start and end dates are logical.
            - **Budget**: Do not change any existing values of budget

            STYLE:
            - Smart and professional.
            - Provide clear and concise information.

            OUTPUT:
            Return a JSON matching the input format, with enriched values. Keep all keys intact.

            INPUT DATA:
            <current_project>
            {input_data}
            <current_project>

            WEB SEARCH DATA:
            <web_search>
            {template}
            <web_search>
            """
        elif enhance_type == "profile":
            system = f"""
            ROLE: You are a business analyst expert tasked with creating a comprehensive and detailed customer profile.

            MISSION:
            Enhance the customer profile's fields using provided data and web search data. The fields are: `organization_details`, `key_contacts`, `demographics`, `solutions_offerings`, `business_goals_and_challenges`, `engagement_details`, `technological_landscape`, `operational_context`, `financial_context`, `compliance_and_security`, `organizational_knowledge`, `genai_context`, `external_trends`.

            ENHANCEMENT RULES:
            - For the following fields, you are expected to return paragraphs. You should be verbose and expand on given information to provide a comprehensive overview of the section. Aim to make AT LEAST 5 full sentences. You are allowed to make logical extensions:
                - `demographics` (except languages)
                - `solutions_offerings`
                - `business_goals_and_challenges` (except kpis and pain_points)
                - `technological_landscape`
                - `operational_context`
                - `compliance_and_security`
                - `genai_context`
                - `external_trends`
            - For fields where you don't have explicit data, you can make logical assumptions based on the information provided.
            - Do not assign `org_chart` roles to specific people unless explicitly stated.
            - For fields where no data is provided and there are no logical assumptions, use an empty string, list, or object as appropriate.

            STYLE:
            - Professional and detailed.
            - Ensure that all required fields are structured clearly and consistently.

            OUTPUT:
            Return a valid JSON matching the input format, ready to process into the Trmeric platform.

            INPUT DATA:
            <current_profile>
            {input_data}
            <current_profile>

            WEB SEARCH DATA:
            <web_search>
            {template}
            <web_search>
            """
        else:
            system = ""

        if self.source:
            system += f"""
        SOURCE RULES:
        - Each enriched field must include a `source_*` list (e.g., `source_description`).
        - Sources: Use provided ones (e.g., "Jira Project X") or "Tango" for guesses. Append "Tango" to existing sources if enhanced.
        - Never invent sources beyond what’s given or "Tango."
        - Example: `source_budget`: ["Jira Project X", "Tango"] if adjusted with web data.
        """

        return system

    def web_search_roadmap(self):
        system = f"""
        Your task is to analyze the provided roadmap (future project) and generate web search questions to enhance it with actionable, industry-specific context. The goal is to make the roadmap detailed, executable, and optimized by enriching key fields.

        ### Steps:
        1. **Identify the Theme**: Examine the roadmap data (title, description, objectives, etc.) to determine its theme or industry (e.g., tech, healthcare, marketing). If unclear, infer a theme from clues or default to a general business context.
        2. **Select Fields to Enhance**: Based on the theme, pick 5 key fields to enrich from this list:
        - `scope`: Define boundaries, deliverables, or inclusions/exclusions.
        - `constraints`: Identify limits (cost, time, resources, risks).
        - `key_results`: Specify measurable outcomes or success metrics.
        - `team`: Determine optimal roles or non-labor resources.
        - `budget`: Estimate costs or benchmarks.
        Prioritize fields most impactful to the theme and execution.
        3. **Generate Questions**: Create 1-2 specific questions per field to search the web for insights, benchmarks, or best practices. Add 2 general questions for broader context (e.g., trends, risks). Cap at 10 questions total.

        ### Guidelines:
        - Questions must be concise, theme-specific, and web-searchable (e.g., "What are typical budget constraints for AI integration in SaaS?").
        - Avoid vague questions (e.g., "What’s this about?").
        - Focus on execution-ready details (metrics, examples, trade-offs).

        ### Output:
        Return your questions in this JSON format:
        ```json
        {{
            "theme": "<Identified theme or industry>",
            "fields": ["scope", "constraints", "key_results", "team", "budget"],
            "web_queries": [
                "<query for scope>",
                "<query for constraints>",
                "<query for key_results>",
                "<query for team>",
                "<query for budget>",
                "<General query 1>",
                "<General query 2>"
            ]
        }}
        ```
        """

        user = f"""
        Here is the roadmap to enhance:
        {self.input_data}
        """

        response = self.llm.run(
            ChatCompletion(system=system, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini",
                         max_tokens=4000, temperature=0.3),
            "web_search_questions_roadmap_onboarding"
        )

        result = extract_json_after_llm(response)
        questions = result.get("web_queries", [])
        output_text = """To enhance the roadmap with rich, actionable context, here’s the web search data:"""
        data = WebSearchNode().run_and_format(questions, output_text)
        return data

    def web_search_project(self):
        system = f"""
        Your task is to look at the provided project which needs to be enhanced. You will be helping to provide a better project by enhancing certain fields.
        You will attempt to enhance the following fields:
        
        - description
        - objectives
        - technology_stack
        - kpi

        Your method of enhancement will be by providing questions we can ask the internet to get relevant context of what might fill in here.
        Along these lines, you should also as questions (not just for the above fields) that might help generally with the project, if it is industry context, or other relevant information.
        Please return your question in a json format:
        ```json
        {{
            "questions": ["<Question 1>", "<Question 2>", ...]
        }}
        ```
        
        Limit yourself to about 3 questions maximum.
        """

        user = f"""
        Here is the project that you should help enhance:
        {self.input_data}
        """

        response = self.llm.run(
            ChatCompletion(system=system, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini",
                         max_tokens=4000, temperature=0.3),
            "web_search_questions_project_onboarding"
        )

        questions = extract_json_after_llm(response).get("questions")
        data = WebSearchNode().run_and_format(questions)
        return data

    def web_search_profile(self):
        system = f"""
        Your task is to look at the provided profile which needs to be enhanced. You will be helping to provide a better profile by enhancing certain fields.
        You will attempt to enhance the following fields:
        
        - organization_details
        - solutions_offerings
        - business_goals_and_challenges
        - technological_landscape
        - operational_context
        - financial_context
        - compliance_and_security
        - external_trends (IMPORTANT)

        Your method of enhancement will be by providing questions we can ask the internet to get relevant context of what might fill in here.
        Along these lines, you should also as questions (not just for the above fields) that might help generally with the profile, if it is industry context, or other relevant information.
        Please return your question in a json format:
        ```json
        {{
            "questions": ["<Question 1>", "<Question 2>", ...]
        }}
        ```
        
        Limit yourself to about 30 questions maximum.
        """

        user = f"""
        Here is the profile that you should help enhance:
        {self.input_data}
        """

        response = self.llm.run(
            ChatCompletion(system=system, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini",
                         max_tokens=4000, temperature=0.3),
            "web_search_questions_profile_onboarding"
        )

        questions = extract_json_after_llm(response).get("questions")
        data = WebSearchNode().run_and_format(questions)
        return data

    def enhance(self):
        try:
            if self.tenant_id:
                customer_data = ""
                customer_info = CustomerDao.FetchCustomerOrgDetailInfo(
                    tenant_id=self.tenant_id)
                if (len(customer_info) > 0):
                    self.org_info_string = f"""
                        The customer that is creating this roadmap has the following org info:
                        {customer_info[0].get("org_info")}
                    """
                customer_data += self.org_info_string

                defaultStrategy = IdeaDao.fetchDefaultIdeasStrategy(
                    tenant_id=self.tenant_id)
                if (len(defaultStrategy) > 0):
                    self.default_strategy_string = f"""
                        The customer that is creating this roadmap has the following default organizational strategies:
                        {defaultStrategy} \n\n
                    """
                else:
                    self.default_strategy_string = "The customer has not provided default organizational strategies. \n\n "

                all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(
                    tenant_id=self.tenant_id)
                
                if self.org_aligns:
                    customer_data += f"""
                        The customer that is creating this roadmap has the following organizational strategy alignments:
                        {self.org_aligns} \n\n
                    """

                customer_data += self.default_strategy_string
                if all_portfolios: customer_data += f"""
                    <all_available_portfolios_of_this_tenant>
                    {all_portfolios}
                    <all_available_portfolios_of_this_tenant>
                """
                print("--debug customer_data---------", customer_data)
                self.templates[self.enhance_type] += ("\n\n" + customer_data)

            if self.enhance_type == "roadmap":
                print("--debug calling websearch---------")
                self.templates["roadmap"] += ("\n\n" +
                                              self.web_search_roadmap())

            elif self.enhance_type == "project":
                self.templates["project"] += ("\n\n" +
                                              self.web_search_project())

            elif self.enhance_type == "profile":
                self.templates["profile"] += ("\n\n" +
                                              self.web_search_profile())

        except:
            import traceback
            print(traceback.print_exc())
            pass

        # print("roadmap_template---", self.templates["roadmap"])
        prompt = self.system_prompt(
            self.enhance_type, self.input_data, self.templates[self.enhance_type])

        response = self.llm.run(
            ChatCompletion(system=prompt, prev=[
            ], user=f"Please enhance the given {self.enhance_type} information"),
            ModelOptions(model="gpt-4o-mini",
                         max_tokens=16384, temperature=0.3),
            'enhance_roadmap_onboarding' if self.enhance_type == "roadmap" else 'enhance_project_onboarding' if self.enhance_type == "project" else 'enhance_profile_onboarding'
        )
        

        source_response = extract_json_after_llm(response)
        
        if self.enhance_type == "project":
            name = self.input_data.get("title", "")
            description = self.input_data.get("description", "")
            objectives = self.input_data.get("objectives", "")
            key_results = ProjectService().createKeyResults(self.tenant_id, project_name = name, project_description = description, project_objective = str(objectives), is_provider=False, web=False)["key_results"]
            print("debug key_results --- ", key_results)
            kpi = [{"name": key_result} for key_result in key_results]
            source_response["kpi"] = kpi
            
        # clean data for api
        def remove_source(item):
            if isinstance(item, dict):
                return {k: remove_source(v) for k, v in item.items() if (k != "source" or not k.startswith("source_"))}
            elif isinstance(item, list):
                return [remove_source(i) for i in item]
            return item
        response = remove_source(source_response)

        return (response, source_response)

    def enhance_roadmap(self, get_web=True):
        # template = self.templates[self.enhance_type]

        details = ""

        customer_info = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=self.tenant_id)
        if (len(customer_info) > 0):
            details += f"""
                <customer_info>
                The customer that is creating this roadmap has the following org info:
                {customer_info[0].get("org_info")}
                <customer_info>
            """

        all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(
            tenant_id=self.tenant_id)

        # self.templates["roadmap"] += self.default_strategy_string
        details += f"""
            <all_available_portfolios_of_this_tenant>
            {all_portfolios}
            <all_available_portfolios_of_this_tenant>
        """

        if get_web:
            details += ("\n\n" + self.web_search_roadmap())
            
        chat_completion = self.enhance_roadmap_prompt(self.input_data, details)
        # print("debug prompt ---- ", chat_completion.formatAsString())
        response = self.llm.run(
            chat_completion,
            ModelOptions(model="gpt-4o-mini",
                         max_tokens=16384, temperature=0.3),
            'enhance_roadmap'
        )

        source_response = extract_json_after_llm(response)

        # clean data for api
        def remove_source(item):
            if isinstance(item, dict):
                return {k: remove_source(v) for k, v in item.items() if (k != "source" or not k.startswith("source_"))}
            elif isinstance(item, list):
                return [remove_source(i) for i in item]
            return item
        response = remove_source(source_response)

        return (response, source_response)

    def enhance_roadmap_prompt(self, input_data, details):
        systemPrompt = f"""
        **This roadmap’s ready to roll—let’s make it epic!**

        ROLE: You’re a business planning genius tasked with transforming raw roadmap data for a future project into a vivid, professional, 
        and executable masterpiece. Your mission is to enhance every detail, ensuring it’s rich, detailed, and bulletproof for project execution.

        MISSION:
        Enhance the provided roadmap JSON for a future project, enriching all fields to match the structure in the template below. Use:
            1. INPUT DATA:
                <current_roadmap> {input_data} </current_roadmap>
            2. ADDITIONAL CONTEXT:
                <details> {details} </details>
            
        - User-input roadmap data (<current_roadmap>)
        - Additional context from the details string (<details>)
        - Web search data (embedded in <details>)
        Examine every field—pack it with specifics, metrics, tasks, and justification. Preserve the core meaning of the input data, enrich it with actionable depth, and never omit critical input details.

        ### Template
        ```json
        {{
            "title": "<name of the roadmap>",
            "description": "Original Description: <original description of the <current_roadmap> > \n\n  Enhanced Description : <enhanced description of the original roadmap’s description purpose, scope, and key components, preserving all key points from input data>
                e.g., \"Original Description: Process Mining to gain insights for process automation on sub-processes. Enhanced Description: Implement process mining analytics to identify inefficiencies and automate subprocesses within the supply chain, aiming for a 20% reduction in cycle time and enhanced operational efficiency.\",
        
            "source_description": ["<Source 1, e.g., 'Input' or 'Tango'>", ...],
            "objectives": "<descriptive primary goals with execution context, e.g., 'Reduce testing time by 20% through AI-driven automation across regression suites'>"
            ,
            "source_objectives": ["<Source 1>", ...],
            "scope_item": [ //Render a single scope item in array combining all the details
                {{
                    "name": "<single scope item with precise and descriptive scope defining a specific scope of work and the detailed requirements related to the scope, e.g., 'Develop and integrate process mining analytics into supply chain workflows.', '>",
                    "combined_details_out_of_scope_in_markdown_format": "<Single scope item in Markdown-formatted string combining all specifics: requirements, constraints, risks and dependencies and out of scope, e.g., '## Details\\nIntegrate AI tool with Jenkins for automated test execution; targets 500 test cases/sprint."## Requirements\n- Implement process mining to analyze sub-processes within the supply chain.\n- Develop real-time analytics dashboards for process visibility and optimization.\n- Ensure seamless integration with existing supply chain management platforms.\n\n## Constraints\n- Availability of high-quality, structured process data for analysis.\n- Adherence to data privacy and security regulations.\n- Limited IT infrastructure scalability for processing high-volume transaction data.\n\n## Risks and Dependencies\n- **Data Quality Risks**: Incomplete or inconsistent data may lead to inaccurate process insights.\n- **Business Adoption Risks**: Resistance from business units in adopting process automation changes.\n- **Technology Dependencies**: Successful integration depends on existing supply chain management system capabilities.\n- **Operational Risks**: Potential misalignment between process mining insights and current business workflows.\n- **Implementation Risk**: Delays in data collection and integration could impact the project timeline.\n\n## Out of Scope\n- Full-scale supply chain transformation beyond process mining insights.\n- End-to-end automation of all sub-processes without human intervention.\n- Custom development of new ERP functionalities or major system overhauls."

                }}
            ],
            "priority": <integer: 1=High, 2=Medium, 3=Low>,
            "key_results": [
                {{
                    "key_result": "<rich, measurable outcome with combined context, e.g., 'Achieve a 20% reduction in manual interventions across key subprocesses by leveraging process mining.'>",
                    "baseline_value": "<numerical or measurable target only, e.g., '20%'>"
                }}, ...
            ],
            "source_key_results": ["<Source 1>", ...],
            "start_date": "<YYYY-MM-DD, e.g., '2025-04-01'>",
            "source_start_date": ["<Source 1>", ...],
            "end_date": "<YYYY-MM-DD, e.g., '2025-09-01'>",
            "source_end_date": ["<Source 1>", ...],
        
            "team": [
                {{
                    "name": "<only specific non-labor resource that are relevant to <current_roadmap>, such as Hardware costs, software costs, licensing cost etc., eg. 'Process Mining Software Licensing','Cloud Infrastructure for Data Processing'>",
                    "estimate_value": <integer: total cost in USD, e.g., 20000>,
                    "labour_type": 2
                }}, ...
            ],
            "thought_process_behind_non_labor_team": "<MARKDOWN FORMAT: Detailed analysis in bullet points explaining why each non-labor resource was chosen and why its price is justified,
                e.g., '- **Process Mining Software Licensing ($50k)**: Essential for analyzing supply chain workflows; aligns with market pricing trends.\n- **Cloud Infrastructure ($30k)**: Supports high-volume process data analysis to enable automation opportunities.",'>",
            
            "source_team": ["<Source 1>", ...],
            "type": <integer: 1=Program, 2=Project, 3=Enhancement>,
            "org_strategy_align": "<exact text from input e.g., '"Financial Targets; Nextgen Technology"'>",
            "source_org_strategy_align": ["<Source 1>", ...],
            
            "constraints": [
                {{
                    "constraint": "<rich, contextual limitation or constraint across dimensions such as Resource, Scope , Quality, Technology, Complexities around integrations, external factors, Cost etc. , 
                    e.g.,'Availability of high-quality process data may impact mining effectiveness.' , 'Integration with existing supply chain systems may require additional IT support.'>",
                    "type": <integer: 1=Cost, 2=Resource, 3=Risk, 4=Scope, 5=Quality, 6=Time>
                }}, ...
            ],
            
            "source_constraints": ["<Source 1>", ...],
            "min_time_value": <integer: min time to realize the business value delivered post-release of the <current_roadmap>, e.g., 3>,
            "source_min_time_value": ["<Source 1>", ...],
            "min_time_value_type": <integer: 1=days, 2=weeks, 3=months, 4=years>,
            
            "portfolio": {{
                "id": "<id of the portfolio found from doc>",
                "name": "<name of the portfolio from doc>"
            }},
            "source_portfolio": ["<Source 1>", ...],
            "business_sponsor_lead": ["<name or role, e.g., 'Jane Doe, CFO'>", ...],
            "roadmap_capabilities": "<comma separated values, should include technical, business, functional capabilites that are part of this <current_roadmap>
                    e.g. "Process Mining, Supply Chain Optimization, Data Analytics, Workflow Automation">"
        }}
        ```

         ### Enhancement Rules
            - **Title**: Retain the title as in <input_data>.
            
            - **Description**: Enhance the input description by preserving all key points and adding depth with purpose, scope, and key components from <details>. 
            (e.g., Input: 'Process Mining to gain insights for process automation on sub-processes' becomes 'Original Description: Process Mining to gain insights for process automation on sub-processes.\n\nEnhanced Description: Implement process mining analytics to identify inefficiencies and automate subprocesses within the supply chain, aiming for a 20% reduction in cycle time and enhanced operational efficiency.'). Do not rewrite or omit original intent—build on it.
            
            - **Objectives**: Make descriptive and actionable, adding execution context (e.g., "Reduce supply chain cycle time by 20% through process mining and automation of key subprocesses"). Incorporate customer goals from <details>.
            
            - **Scope Item**: Given the project description, generate a comprehensive and well-structured scope breakdown into detailed scope item, ensuring clarity, completeness, and alignment with objectives. 
                - **Name**: A precise and descriptive title that clearly defines a specific scope of work (e.g., "Develop and integrate process mining analytics into supply chain workflows").
                - **combined_details_out_of_scope_in_markdown_format**: A Markdown-formatted string consolidating all specifics into a structured, actionable breakdown:
                    - **Details**: Capture key requirements, dependencies, constraints, and expected outcomes (e.g., "Integrate process mining tools with existing supply chain systems to analyze subprocesses").
                    - **Requirements**: List specific needs (e.g., "- Implement process mining to analyze sub-processes within the supply chain.").
                    - **Constraints**: Highlight limitations (e.g., "- Availability of high-quality, structured process data for analysis.").
                    - **Risks and Dependencies**: Identify risks and dependencies (e.g., "- **Data Quality Risks**: Incomplete or inconsistent data may lead to inaccurate process insights.\n- **Technology Dependencies**: Relies on existing supply chain management system capabilities.").
                    - **Out of Scope**: Define exclusions (e.g., "- Full-scale supply chain transformation beyond process mining insights.").
                    - Format as a single Markdown string with sections (e.g., `## Details\n<content>\n## Requirements\n<list>\n## Constraints\n<list>\n## Risks and Dependencies\n<list>\n## Out of Scope\n<list>`). Avoid vague descriptions—ensure specificity and traceability to objectives.
                - Ensure the scope comprehensively covers technical, functional, and operational dimensions, using <details> and <current_roadmap> for depth, and aligns with roadmap objectives and key results.
            
            - **Key Results**: Generate multiple, rich, measurable outcomes with specific post-completion targets. Combine descriptive context from the input with `baseline_value`, keeping `baseline_value` as a numerical or measurable target only:
                - **key_result**: Enhance by integrating context (e.g., Input: "Reduce manual interventions" with "20%" becomes "Achieve a 20% reduction in manual interventions across key subprocesses by leveraging process mining").
                - **baseline_value**: Retain only the numerical or measurable component (e.g., "20%"). If no numerical value exists, use a target metric from the input or <details> (e.g., "80%"). Tie to objectives, scope items, and customer priorities from <details>. Only add new results if explicitly supported by input or <details>.
            
            - **Priority**: Retain input value (1=High, 2=Medium, 3=Low) unless <details> justifies a change.
            - **Team**: Include *only non-labor costs* (`labour_type: 2`) from input or <details> (e.g., "Process Mining Software Licensing"). Remove any labor costs if present in input. Preserve input entries unless <details> justifies additions.
            
            - **Thought Process Behind Non-Labor Team**: Provide a detailed Markdown analysis for each non-labor resource:
                - **Why Chosen**: Link to project needs or customer goals from input or <details> (e.g., "Essential for analyzing supply chain workflows").
                - **Why This Price**: Justify with evidence from <details> or reasoning tied to input (e.g., "Aligns with market pricing trends").
                - Format: "- **<Resource Name> ($<Cost>)**: <Why chosen>. <Why this price>." (e.g., "- **Process Mining Software Licensing ($50k)**: Essential for analyzing supply chain workflows; aligns with market pricing trends.").
            
            - **Type**: Retain input value (1=Program, 2=Project, 3=Enhancement) unless <details> suggests otherwise.
            - **Org Strategy Align**: Use exact input text (e.g., "Financial Targets; Nextgen Technology"), no rephrasing. Align with customer org info from <details> if provided.
            - **Constraints**: Enhance with concise, relevant context from input or <details>. Add multiple constraints if applicable, avoiding speculation. Assign a type (1=Cost, 2=Resource, 3=Risk, 4=Scope, 5=Quality, 6=Time) (e.g., "Availability of high-quality process data may impact mining effectiveness" with type 2). Provide reasoning for each constraint (e.g., "From <details>: Customer noted data challenges").
            - **Start/End Dates**: Retain input dates unless <details> provides a conflicting timeline, in YYYY-MM-DD (e.g., "2025-04-01").
            
            - **Min Time Value/Type**: Infer post-release duration (e.g., 3 months) if missing, aligning with project scale from input or <details>. Use type (1=days, 2=weeks, 3=months, 4=years).
            - **Portfolio**: Extract portfolio entries with `id` and `name` from <details> or use input if <details> lacks ID.
            - **Business Sponsor Lead**: Extract names/roles from input or <details> (e.g., "Jane Doe, CFO"), preserving input structure.
            - **Roadmap Capabilities**: List technical, business, and functional capabilities from input or <details> (e.g., "Process Mining, Supply Chain Optimization, Data Analytics, Workflow Automation").
            
            - **Reasoning**: Cite sources (e.g., "Input", "<details>", "Web: Gartner 2023"), explain trade-offs, and avoid unsourced assumptions.
            
            - **Integrity**: Use only input data, <details>, or web search—do not invent unsourced info or assume constraints without evidence.

        ### Source Rules
        - Each enriched field must include a `source_*` list (e.g., `source_description`).
        - Use "Input" for user JSON, "Customer Info" for customer data from <details>, "Portfolios" for portfolio data, "Web" for web search, or "Tango" for inferences. Append to existing sources if enhanced.
        - Example: `source_budget`: ["Input", "Web", "Tango"] if adjusted with web data.

        """

        userPrompt = f"""
            Please enhance the given roadmap information for a future project. Use the user-input JSON in <current_roadmap> as the base, and enrich it with the additional context provided in <details>. Return a single JSON matching the template format, 
            with enriched values for all fields, including arrays like `scope_items`, `key_results`, `constraints`, and `team`. 
            - For `scope_items`, generate a comprehensive and well-structured breakdown with multiple detailed entries, each including `name` and `combined_details_out_of_scope_in_markdown_format`, where the latter consolidates all specifics 
              (details, requirements, constraints, risks and dependencies, and out of scope) into a single Markdown-formatted string with clear sections, ensuring clarity and alignment with objectives. 
            - For `key_results`, provide rich, measurable outcomes with `baseline_value` as a numerical or measurable target only (e.g., percentages, dates). 
            
            Preserve the original description in the `description` field (enhancing, not rewriting it), and only add constraints or team costs explicitly supported by input or <details>—no unsolicited assumptions.
        """

        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)

    def enhance_roadmap_new(self, input_data, get_web=True):
        details = ""

        customer_info = CustomerDao.FetchCustomerOrgDetailInfo(
            tenant_id=self.tenant_id)
        if (len(customer_info) > 0):
            details += f"""
                <customer_info>
                The customer that is creating this roadmap has the following org info:
                {customer_info[0].get("org_info")}
                <customer_info>
            """

        all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(
            tenant_id=self.tenant_id)

        # self.templates["roadmap"] += self.default_strategy_string
        details += f"""
            <all_available_portfolios_of_this_tenant>
            {all_portfolios}
            <all_available_portfolios_of_this_tenant>
        """

        if get_web:
            details += ("\n\n" + self.web_search_roadmap())
            
        chat_completion = self.enhance_roadmap_prompt_new(input_data, details)
        # print("debug -- ", chat_completion.formatAsString())
        response = self.llm.run(
            chat_completion,
            ModelOptions(
                model="gpt-4.1",
                max_tokens=16384, 
                temperature=0.3
            ),
            None
        )

        source_response = extract_json_after_llm(response)

        # clean data for api
        def remove_source(item):
            if isinstance(item, dict):
                return {k: remove_source(v) for k, v in item.items() if (k != "source" or not k.startswith("source_"))}
            elif isinstance(item, list):
                return [remove_source(i) for i in item]
            return item
        response = remove_source(source_response)

        return response

    def enhance_roadmap_prompt_new(self, conversation_text, details):
        systemPrompt = f"""
        **Craft a Roadmap from Provided data!**

        ROLE: You’re a strategic business planning expert tasked with transforming a conversation (e.g., ideation session) into a detailed, professional, and executable roadmap for a future project. Your mission is to analyze the conversation text, extract key themes, objectives, and constraints, and create a vivid roadmap that aligns with organizational needs, ensuring it’s actionable and bulletproof for execution.

        MISSION:
        Create a roadmap JSON from the provided conversation text and additional context, matching the structure in the template below. Use:
            1. INPUT DATA:
                <conversation_text> {conversation_text} </conversation_text>
            2. ADDITIONAL CONTEXT:
                <details> {details} </details>
        
        - **Conversation Text**: A text string capturing a user’s conversation (e.g., ideation on process automation, strategies, or business goals).
        - **Additional Context**: Includes customer org info, portfolio data, and optional web search results from <details>.
        
        Analyze the conversation to identify the roadmap’s theme (e.g., process automation, GenAI transformation), objectives, and scope. Enrich all fields with actionable details, metrics, and justifications, preserving the conversation’s intent. Use <details> to add depth from customer goals, portfolio alignment, or web insights. Avoid inventing unsourced info.

        ### Template
        ```json
        {{
            "title": "<Title based on the title of Jira issue from data>",
            "description": "<Enriched description with purpose, scope, and key components>",
            "objectives": "<Primary goals with execution context, e.g., 'Reduce supply chain cycle time by 20% through process mining and automation'>",
            "priority": <integer: 1=High, 2=Medium, 3=Low>,
            "key_results": [
                {{
                    "key_result": "<Measurable outcome, e.g., 'Achieve 20% reduction in manual interventions via process mining'>",
                    "baseline_value": "<Numerical target, e.g., '20%'>"
                }}
            ],
            "start_date": "<YYYY-MM-DD, e.g., '2025-07-01'>",
            "end_date": "<YYYY-MM-DD, e.g., '2026-01-01'>",
            "type": <integer: 1=Program, 2=Project, 3=Enhancement>,
            "org_strategy_align": "<Text from conversation or details, e.g., 'Operational Efficiency; Nextgen Technology'>",
            "constraints": [
                {{
                    "constraint": "<Limitation, e.g., 'Limited high-quality process data may impact analytics'>",
                    "type": <integer: 1=Cost, 2=Resource, 3=Risk, 4=Scope, 5=Quality, 6=Time>
                }}
            ],
            "min_time_value": <integer: e.g., 3>,
            "min_time_value_type": <integer: 1=days, 2=weeks, 3=months, 4=years>,
            "portfolio": {{
                "id": "<Portfolio ID from details>",
                "name": "<Portfolio name from details>"
            }},
            "roadmap_capabilities": "<Comma-separated capabilities, e.g., 'Process Mining, Data Analytics, Workflow Automation'>"
        }}
        ```

        ### Enhancement Rules
        - **Title**: Retain the title as in <input_data>.
        - **Description**: Create a nice description of the roadmap, from all the data that is provided to you.
        - **Objectives**: Make descriptive and actionable, adding execution context (e.g., "Reduce supply chain cycle time by 20% through process mining and automation of key subprocesses"). Incorporate customer goals from <details>.
        - **Priority**: Set based on conversation urgency (e.g., ‘urgent’ in conversation → 1=High) or <details> (e.g., customer priority). Default to 2=Medium if unclear.
        - **Key Results**: Generate 2-4 measurable outcomes tied to objectives (e.g., ‘Reduce manual interventions by 20%’ with `baseline_value: '20%'`). Use conversation metrics or infer from <details> (e.g., industry benchmarks).
        - **Start/End Dates**: Infer realistic dates from conversation or <details> (e.g., 6-month project starting ‘2025-07-01’). Default to 6-12 months if unspecified.
        - **Type**: Set based on scale (1=Program for large initiatives, 2=Project for standard, 3=Enhancement for small changes). Infer from conversation or <details>.
        - **Org Strategy Align**: Extract from conversation (e.g., ‘efficiency’ → ‘Operational Efficiency’) or <details>.
        - **Constraints**: Generate 2-4 constraints from conversation or <details> (e.g., ‘Limited process data’, type 2=Resource). Assign types (1=Cost, 2=Resource, 3=Risk, 4=Scope, 5=Quality, 6=Time).
        - **Min Time Value/Type**: Infer post-release value realization (e.g., 3 months) from conversation or <details>. Default to 3=months if unclear.
        - **Portfolio**: Extract from <details> (e.g., portfolio ID/name). Default to generic portfolio if missing (e.g., {{"id": "default", "name": "General Initiatives"}}).
        - **Roadmap Capabilities**: List capabilities from conversation or <details> (e.g., ‘Process Mining, Data Analytics’). Align with theme.
        - **Reasoning**: For each field, base enhancements on conversation, <details>, or industry benchmarks. Avoid assumptions without evidence.
        - **Integrity**: Use only <conversation_text> and <details>. No unsourced info.

        ### Output
        Return a single JSON matching the template, with enriched fields based on <conversation_text> and <details>. Ensure all arrays (e.g., `scope_item`, `key_results`, `constraints`, `team`) are populated with detailed, actionable entries. Exclude any `source_*` fields.
        """

        userPrompt = f"""
        Create a roadmap from the provided conversation text and additional context. Use the <conversation_text> as the primary input to identify the roadmap’s theme, objectives, and scope. Enrich with <details> (e.g., customer org info, portfolios, web insights) to add depth, ensuring alignment with customer goals. Return a single JSON matching the template, with comprehensive scope items, measurable key results, and actionable constraints. Preserve the conversation’s intent, avoid unsolicited assumptions, and exclude all `source_*` fields.
        
        Note:: Roadmap means future project.
        Today's date: {todays_date}
        """

        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)
    