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

class ProjectGenerator():
    def __init__(self, llm: LLMClient, integrationInfo: dict, clarifying_information: str, clarifying_count: int):
        self.llm = llm
        self.integrationInfo = integrationInfo
        self.clarifying_information = clarifying_information
        self.clarifying_count = clarifying_count
        self.system_prompt = self.system()
        self.clarifying_section_prompt = self.clarifying_section()
        
        if self.clarifying_count > 3:
             self.clarifying_section_prompt = None
        
    @activity("onboarding::projects::generate_projects_from_integration_data")
    def generateProjects(self, user_id):
        record("description", "User's confirmed sources are used, parsed, and formatted to create projects. Look here to identify how the user's barebones input information was transformed into a full Trmeric project.")
        formattedIntegrationInformation = ""
        for integration in self.integrationInfo:
            formattedIntegrationInformation += f"{integration}: {self.integrationInfo[integration]}\n"

        user = formattedIntegrationInformation
        record("input_data", user)
        if self.clarifying_information:
            user += f"Here is some clarifying information that you have obtained through follow up questions, keep this in mind: {self.clarifying_information}"

        response = self.llm.runV2(
            ChatCompletion(system=self.system_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini", max_tokens=16384, temperature=0.3),
            "project_creation"
        )
        # Regular expression to capture JSON objects, including nested ones

        json_pattern = r'\{(?:[^{}]++|(?R))*\}'
        try:
            matches = re.findall(json_pattern, response, re.DOTALL)
        except re.error as e:
            print(f"Regex error: {e}")

        projects = []
        for match in matches:
            try:
                # Attempt to load the match as JSON
                project = json.loads(match)
                projects.append(project)
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e} for match: {match}")
                continue
            
        if self.clarifying_section_prompt:
            project_info = str([json.dumps(project, indent=4) for project in projects])
            self.clarifying_section_prompt = self.clarifying_section_prompt + project_info
            response = self.llm.run(
            ChatCompletion(system=self.clarifying_section_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o-mini", max_tokens=1000, temperature=0.3),
            "clarifying_question_project_creation"
            )
            print(response)
            response = extract_json_after_llm(response)
            response = response["clarifying_question"]
            if response != "no question":    
                record("void_activity", True)
                return {"clarifying_question": ask_clarifying_question(clarifying_question=response, integrations=True, creation_type = "Project")}
        
        record("output_data", projects)

        return projects

    def system(self):
        return """
        You are a setup assistant for Trmeric, a B2B SAAS company, helping a company onboard a customer onto a platform where they can keep track of their business/strategic  projects. 

        We have given the user the ability to integrate with one or more integrations, and we have parsed the information form that integration (Jira, Google Drive, Slack, etc.). 

        Projects are the individual tasks that need to be completed to achieve a goal. 

        Given this, your job is to look at the information from the integrations, create a list of projects with their descriptions and other information.

        Do not limit yourself in the number of projects that are created. Just make the logical decision based on the information that you have.
        
        Again if you see any number of projects, up to around 50, create them and attempt to name them exactly as you found it in the reference text.

        For example, your projects could look something like (this information of course would have to be based on the text that you are analyzing - you can't just make up projects):
        - Build a LLM Copilot for the discovery phase employees
        - Enable service providers to generate images for their products
        - etc

        Along with the names of the projects, you must also provide a description, a set of KPIs, the tech stack required for the project, a project lead (if possible), team members, a list of updates on the project, and a list of actions for the project. For each of these fields, if you can't find the information, just leave it blank. (empty string or empty list, etc)

        Some pieces of the json will be followed by a source section. Here, you should add where this data came from. This will be a list of strings, of each of the sources.
        For example, a source could be "Link: Company Website A", "Link: Social Media B", "Uploaded Document C", ..., "Jira Project X", "Office Document Y", or "Slack Channel Z". 
        The single exception is if you, Tango, have taken a guess to fill something in. In this case, add "Tango" as a reference. DO NOT create projects based off the tango memory insights provided to you. This is not a source for the project.
        Source is used to track accuracy by citing your sources. This is a necessary component.

        Your response should look like the following:

        ```json
        [
            {
                "state": <State of the project: ONLY either "Build", "Design", "Discovery", or "Complete">,
                "title": "<Provide the full name of the project here>",
                "description": "<Provide a detailed and comprehensive description of the project, including goals, objectives, and overall purpose>",
                "source_description": ["<Source 1 for description above>", "<Source 2 for description above>", ...],
                "objectives": "<Provide a STRING NOT ARRAY of objectives for the project>",
                "source_objectives": ["<Source 1 for objectives above>", "<Source 2 for objectives above>", ...],
                "total_external_spend": "<Provide the total external spend for the project only as an integer>",
                "source_total_external_spend": ["<Source 1 for total external spend above>", "<Source 2 for total external spend above>", ...],
                "technology_stack": "<Comma-separated string of technologies used in the project>",
                "source_tech_stack": ["<Source 1 for tech stack above>", "<Source 2 for tech stack above>", ...],
                "project_location": "<comma-separated string of only: "USA", "Europe", "Latin America", "India", "Middle East", "Africa", "APAC">",
                "source_project_location": ["<Source 1 for project location above>", "<Source 2 for project location above>", ...],
                "project_type": "<string of either 'Transform', 'Run', or 'Innovate'>",
                "project_category": "<Provide the category of the project such as Data Science, etc..>",
                "internal_project": <true or false (depending on whether or not there are external partners) >,
                "start_date": "<Provide the start date of the project in a string of 'YYYY-MM-DD'>",
                "source_start_date": ["<Source 1 for start date above>", "<Source 2 for start date above>", ...],
                "end_date": "<Provide the end date of the project in a string of 'YYYY-MM-DD'>",
                "source_end_date": ["<Source 1 for end date above>", "<Source 2 for end date above>", ...],
                "scope": "<Comma separated string of scopes for the project>",
                "sdlc_method": "<Provide the SDLC methodology used in the project, choose out of: "Agile", "Waterfall", "Hybrid">",
                "kpi": [
                    {
                        "name": "<String of key performance indicator 1 relevant to the project>"
                    },
                    {
                        "name": "<String of key performance indicator 2 relevant to the project>"
                    }, 
                    ...
                ],
                "source_kpi": ["<Source 1 for KPIs above>", "<Source 2 for KPIs above>", ...],
                "
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
                        "source_milestones": ["<Source 1 for milestones above>", "<Source 2 for milestones above>", ...]
                    }
                ], ...
            },
            {
                <Other Projects>
            }
        ] 
        ```
        
        For each project you must at least provide the following fields:
        - state (Either "Build", "Design", "Discovery", or "Complete")
        - title
        - description
        - objectives
        - sdlc_method (Either "Agile", "Waterfall", or "Hybrid")
        - project_type (Either "Transform", "Run", or "Innovate")
        
        Other fields are optional and can be left out of the json object if you can't find the information.
        
        If you want to add milestones, but don't have a team name, go ahead and create a reasonable sounding team name. 
        
        If not provided, do not make guesses about the budget, team members, or project lead. If you can't find the information, leave it blank.
        
        Also, do not make up sources for the source categories. These should strictly only be Tango or the explicitly shown user-provided sources.

        KPIs are key performance indicators that are used to measure the success of a project. For example, if you are building a website, a KPI could be the number of users that visit the website.

        For above reference, examples of tech_stack could be ["Python", "Django", "React", "PostgreSQL"]. The default value for target_date should be today's date:""" +  str(todays_date) + """
        ...
        """

    def clarifying_section(self):
        ret_str =  """
        Below, you will be shown a series of projects, each with a set of fields that have been filled in. Your responsibility is to determine whether further clarfying information is needed for each project."""
        
        if self.clarifying_information: ret_str += f"You can assume that the following information has already been retrieved from asking clarifying questions: {self.clarifying_information}. Pay specific attention to this information. If you are asked to not ask any clarifying questions here, or to move on with creation, then do not ask the questions."
        
        ret_str += """
        If there are fields from the above prompt that you are unsure about or did not receive information for, you should ask clarifying questions to get more information. Ask only about the following categories if they are not found:
        
        
        However, DO NOT ask questions about things you have already asked clarifying questions for. Also, DO NOT ask clarifying questions for the following fields:
       
        - Budget
        - Project Lead
        - Team Members
        - KPIs
        - Tech Stack
        - Scope Milestones
        
        Be very specific in your questions, and ask for the information that you need. For example, you could ask: "What are the key performance indicators for this project X?" or "Who are the team members for project Y?". You may ask mulitiple questions in the same string.
        
        Every time you ask a clarifying question, you must explicitly mention which project you are asking about.
        
        If you have a clarifying question, return only the question and nothing else in this format. If you have multiple questions, make sure to ask them ALL in the same string:
        
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
        
        The projects to look through are below:
        """
        
        return ret_str
