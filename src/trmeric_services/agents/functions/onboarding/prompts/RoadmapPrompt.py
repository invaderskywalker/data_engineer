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

class RoadmapGenerator():
    def __init__(self, llm: LLMClient, integrationInfo: dict, clarifying_information: str, clarifying_count: int):
        self.llm = llm
        self.integrationInfo = integrationInfo
        self.clarifying_information = clarifying_information
        self.clarifying_count = clarifying_count
        self.system_prompt = self.system()
        self.clarifying_section_prompt = self.clarifying_section()
        
        if self.clarifying_count > 3:
             return

    @activity("onboarding::roadmaps::generate_roadmaps_from_integration_data")
    def generateRoadmaps(self, user_id):
        record("description", "User's confirmed sources are used, parsed, and formatted to create roadmaps. Look here to identify how the user's barebones input information was transformed into a full Trmeric roadmap.")
        formattedIntegrationInformation = ""
        for integration in self.integrationInfo:
            formattedIntegrationInformation += f"{integration}: {self.integrationInfo[integration]}\n"

        user = formattedIntegrationInformation
        record("input_data", user)
        
        if self.clarifying_information:
            user += f"\n\nHere is some clarifying information that you have obtained through follow up questions, keep this in mind: {self.clarifying_information}"

        response = self.llm.runV2(
            ChatCompletion(system=self.system_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o", max_tokens=16384, temperature=0.3),
            "roadmap_creation"
        )
        print("generateRoadmaps output ", response)
        # Regular expression to capture JSON objects, including nested ones

        json_pattern = r'\{(?:[^{}]++|(?R))*\}'
        try:
            matches = re.findall(json_pattern, response, re.DOTALL)
        except re.error as e:
            print(f"Regex error: {e}")

        roadmaps = []
        for match in matches:
            try:
                # Attempt to load the match as JSON
                roadmap = json.loads(match)
                roadmaps.append(roadmap)
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e} for match: {match}")
                continue

        if self.clarifying_section_prompt:
            roadmap_info = str([json.dumps(roadmap, indent=4) for roadmap in roadmaps])
            self.clarifying_section_prompt = self.clarifying_section_prompt + roadmap_info
            response = self.llm.run(
            ChatCompletion(system=self.clarifying_section_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini", max_tokens=1000, temperature=0.3),
            "clarifying_question_roadmap_creation"
            )
            response = extract_json_after_llm(response)
            response = response["clarifying_question"]
            if response != "no question":    
                record("void_activity", True)
                return {"clarifying_question": ask_clarifying_question(clarifying_question=response, integrations=True, creation_type="Roadmap")}
            
        record("output_data", roadmaps)
        return roadmaps
    
    def system(self):
        return """
        You are a setup assistant for Turmeric, a B2B SaaS company, helping onboard a customer onto a platform where they can track their business/strategic roadmaps and projects.

        We have given the user the ability to integrate with one or more integrations, and we have parsed the information from those integrations (e.g., Jira, Google Drive, Slack, or direct file uploads). 
        Your job is to take that information, analyze trends in their projects and data, and determine the company’s various roadmaps.

        Do not limit yourself in the number of roadmaps created. Make logical decisions based on the information provided. 
        If the data suggests 10 separate projects, create an individual roadmap for each. Examples of roadmap titles might include: "Improve the sales pipeline by 20 percent by end of quarter" or "Integrate Generative AI into the QA platform."

        Roadmaps represent future projects the company plans to execute soon. Extract detailed data from the provided documents and structure it properly.

        Some JSON fields will include a `source` section, listing where the data originated as a list of strings (e.g., "Link: Company Website A", "Jira Project X", "Slack Channel Z"). If you, Tango, infer a value, add "Tango" as the source. 
        Sources are required for accuracy tracking—do not invent them beyond user-provided data or "Tango."  DO NOT create roadmaps based off the tango memory insights provided to you. This is not a source for the project.

        Your response should follow this JSON structure:

        ```json
        [
            {
                "title": "<name of the roadmap>",
                "description": "<if available in doc exact copy that or if not available then add detailed summary of the roadmap’s purpose and key elements>",
                "source_description": ["<Source 1>", ...],
                "objectives": "<primary goals of this roadmap>",
                "source_objectives": ["<Source 1>", ...],
                "scope": [
                    {
                        "name": "<scope from doc>",
                        "selected": true
                    }, ...
                ],
                "priority": <integer (1: High, 2: Medium, 3: Low)>,
                "key_results": [
                    {
                        "name": "<key result from doc>",
                        "baseline_value": "<progress indicator, e.g., 'target' or '85%'>"
                    }, ...
                ],
                "source_key_results": ["<Source 1>", ...],
                "start_date": "<roadmap start date>",
                "source_start_date": ["<Source 1>", "<Source 2>", ...],
                "end_date": "<roadmap end date>",
                "source_end_date": ["<Source 1>", "<Source 2>", ...],
                "source_team": ["<Source 1>", "<Source 2>", ...],
                "type": <integer (1: Program, 2: Project, 3: Enhancement)>,
                "org_strategy_align": "<exactly from doc, comma separated and properly formated strings>",
                "source_org_strategy_align": ["<Source 1>", "<Source 2>", ...],
                "budget": <integer budget amount>,
                "source_budget": ["<Source 1>", "<Source 2>", ...],
                "constraints": [
                    {
                        "name": "<constraint from doc>",
                        "type": <integer (1: Cost, 2: Resource, 3: Risk, 4: Scope, 5: Quality, 6: Time)>
                    }, ...
                ],
                "source_constraints": ["<Source 1>", "<Source 2>", ...],
                "min_time_value": <integer if mentioned>,
                "source_min_time_value": ["<Source 1>", ...],
                "min_time_value_type": <integer (1: days, 2: weeks, 3: months, 4: years) if mentioned>,
                "business_sponsor_lead": [{"name": ""}], // <source only from provided doc>,
                "roadmap_portfolio": "<only from doc>",
                "team": [
                    {
                        "name": "<only non-labour team if present in doc. Do not put business lead here>",
                        "estimate_value": <integer monetary amount>,
                        "labour_type": 2
                    }, ...
                ],
            },
            ...
        ]
        ```

        You must always provide `title`, `description`, `objectives`, `key_results`, `start_date`, `end_date`, and `scope` (at least an empty list if no scope is found). Infer `type`, `priority`, and `team` labour type if not provided, using reasonable defaults. 
        Other fields are optional and can be omitted if data is unavailable. For non-labour estimates in `team`, include all fields (`name`, `estimate_value`, `labour_type`) or skip the entry entirely.
        """
                
    
    def clarifying_section(self):
        ret_str =  """
        Below, you will be shown a series of roadmaps, each with a set of fields that have been filled in. Your responsibility is to determine whether further clarfying information is needed for each roadmap."""
        
        if self.clarifying_information: ret_str += f"You can assume that the following information has already been retrieved from asking clarifying questions: {self.clarifying_information}. Pay specific attention to this information. If you are asked to not ask any clarifying questions here, or to move on with creation, then do not ask the questions."
        
        ret_str += """
        If there are fields from the above prompt that you are unsure about or did not receive information for, you should ask clarifying questions to get more information. Ask only about the following categories if they are not found:
        
        - key results
        - constraints
        - minimum time to completion
        
        However, DO NOT ask questions about things you have already asked clarifying questions for. Also, DO NOT ask clarifying questions for the following fields:
       
        - Budget
        
        Be very specific in your questions, and ask for the information that you need. For example, you could ask: "What are the key performance indicators for this roadmap X?" or "Who are the team members for roadmap Y?". You may ask mulitiple questions in the same string.
        
        Every time you ask a clarifying question, you must explicitly mention which roadmap you are asking about.
        
        If you have a clarifying question, return only the question and nothing else in this format. If you have multiple clarifying questions, make sure to ask them ALL in the same string".:
        
        ```json
        {
            "clarifying_question": "(Insert your clarifying question here)"
        }
        ```
        
        If you do not have a clarifying question and the projects shown are acceptable or you have been instructed to move on, return this:
        
        ```json
        {
            "clarifying_question": "no question"
        }
        ```
        
        The roadmaps to look through are below:
        """
        
        return ret_str
