from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_services.tango.prompts.Examples import ORG_INFO_EXAMPLE
def getCompanyDetailsPrompt(company_name, company_website) -> ChatCompletion:
    prompt = f"""

        You are an expert agent tasked with building a detailed **Persona** and context for a company based on its name and website.
        The persona should include specific, structured information about the company, its offerings, core business, details, 
        strategic goals, business service lines, and industry domain specialization. 
    
        Also you need to generate the context **Org Info** as given below. This should include all relevant publicly available website links that has more details about the company and the relevant 
        IT technology landscape details if it exists for the customer in public domain.

        Use publicly available information from the company website and other credible sources to populate the following 
        JSON structure in output format.

        ### Input Details:
        - **Company Name**: {company_name}
        - **Company Website**: {company_website}

        Here are some examples of how the output json for **Persona and Org Info** will look like: {ORG_INFO_EXAMPLE}

       ### Required Information:
        1. **Persona**:
        - CEO and CIO of the company.
        - A list of the company's offerings.
        - Core business summary.
        - General company details (name, primary location, and industries served).
        - Strategic goals of the organization.
        - Business service lines.
        - Industry domain specialization.

        2. **Org Info**:
        - Official website of the company.
        - Other relevant websites to refer to for insights, products, news, or investor relations.
        - Organization's technology landscape, including tools, platforms, and frameworks used.

        ### Output format: 
        Please ensure all fields are populated with accurate, publicly available information and maintain strict adherence to the format.

        ```json
        {{
            "persona": {{
                "ceo": "Provide CEO Name Here",
                "cio": "Provide CIO Name Here",
                "offerings": [
                        "List the offerings"
                ],
                "core_business": "Summarize core business",
                "company_details": {{
                    "name": "Provide company name",
                    "location": "Primary location or 'Global' if applicable",
                    "industries_served": "List of industries served"
                }},
                "strategic_goals": [
                "List strategic goals"
                ],
                "business_service_lines": [
                    "List service lines"
                ],
                "industry_domain_specialization": "Describe industry specialization"
            }},

            "org_info": {{
                "company_website": "Provide official website URL",
                "other_sites_to_refer": ["List other websites for reference"],
                "organization_tech_landscape": [
                    "List tools, platforms, and frameworks"
                ]
            }}
        }}
        ```

    """

    return ChatCompletion(
        system = "You are a company searching analyst",
        prev = [],
        user = prompt
    )