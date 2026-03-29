from datetime import date  
today = date.today()
todays_date = today.strftime("%Y-%m-%d")

from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
# from src.trmeric_services.agents.functions.onboarding.utils.clarifying import ask_clarifying_question
from src.trmeric_utils.json_parser import extract_json_after_llm
import regex as re
import json

class RoadmapGenerator():
    def __init__(self, llm: LLMClient, roadmap_info: str):
        self.llm = llm
        self.roadmap_info = roadmap_info
        self.system_prompt = self.system()
        self.general_info = roadmap_info.copy()
        self.general_info.pop("categories_breakdown")

        
    def generateRoadmaps(self, level, subsection = None):
        
        if level == "full":       
            user = f"""
            Given the following information, create the roadmap:
            {json.dumps(self.roadmap_info, indent=4)}
            """

        # if level == "category": sys_prompt = self.category()
        if level == "sub_category": 
            user = f"""
            Given the following information, create the roadmap:
            {json.dumps(subsection, indent=4)}. 
            
            Use the above information as the actual action for the roadmap creation. 
            As a general overview of the rest of the spend, this may be potentially useful info:
            {json.dumps(self.general_info, indent=4)}
            """

        print(self.system_prompt)
        print(user)
        response = self.llm.run(
            ChatCompletion(system=self.system_prompt, prev=[], user=user),
            ModelOptions(model="gpt-4o", max_tokens=16384, temperature=0.3),
            "spend_create_roadmap"
        )
        # Regular expression to capture JSON objects, including nested ones

        roadmap = extract_json_after_llm(response)
        print(roadmap)

        return roadmap
    
    def system(self):
        return """
        You are a setup assistant for Trmeric, a B2B SAAS company, helping a company onboard a customer onto a platform where they can keep track of their business/strategic roadmaps and projects. 
        Roadmaps are the high-level goals that the company is trying to achieve. These are strategies and big picture items that the company is trying to achieve.

        You are tasked with creating a roadmap for a company. You will be given a set of information that you will use to create a roadmap. You will need to provide a JSON object that contains the roadmap information.
        The roadmap will be around the spend evaluation of a company. You will be given a set of information that you will use to create a roadmap. 

        Your response should look like the following:

        ```json
        [
            {
                "title": "<name of the roadmap>",
                "description": "<detailed description of the roadmap, summarizing its purpose and key elements>",
                "objectives": "<primary objectives for this roadmap, briefly describing the main goals>",
                "scope": [
                    {
                        "name": "<name of the scope area>",
                        "selected": true
                    }
                    "<optional additional scope areas>"
                ],
                "priority": <integer value indicating the priority of this roadmap (1: Low, 2: Medium, 3: High)>,
                "key_results": [
                    {
                        "name": "<name of the key result>",
                        "baseline_value": <string Indicator of progress, something like "target" or "85%">,
                    },
                    "<additional key result if applicable>"
                ],
                "type": <integer value indicating the type of roadmap (1: Program, 2: Project, 3: Enhancement)>,
                "org_strategy_align": "<how this roadmap aligns with the organization's strategy>",
                "budget": <integer value indicating the budget allocated for this roadmap>,
                "team": [
                    {
                        "name": "<LABOUR ESTIMATES/COST: name of the team behind this work>",
                        "unit": <integer value indicating number of person days or person hours required. The type field decides which scale is used>
                        "type": <integer representing the type of unit used above (1: person days, 2: person months)>,
                        "estimate_value": <integer value representing the monetary amount estimated to fund this team>
                        "labour_type": 1
                    }, 
                    <additional labour estimates and costs in the form of teams>,
                    {
                        "name": "<NON LABOUR ESTIMATES/COST: name of the cost>",
                        "estimate_value": <integer value representing the monetary amount estimated to fund this cost>
                        "labour_type": 2
                    },
                    <additional non-labour estimates and costs in the form of costs>
                ],
                "constraints": [
                    {
                      "name": "<name of the constraint>",
                      "type": <type of constraint (1: Cost, 2: Resource, 3: Risk, 4: Scope, 5: Quality, 6: Time)>,  
                    },
                    "<additional constraints if applicable>"
                ],
                "category": "<category of the roadmap, e.g., 'IT Infrastructure', 'Product Development'>",
                "min_time_value": <integer value indicating the minimum time required for this roadmap>,
                "min_time_value_type": <integer representing unit of time for the minimum time value (1: days, 2: weeks, 3: months, 4: years)>, 
            }
            ...
        ]
        ```

        You must always provide at least roadmap, description, objectives, key_results, and scope. Also, if not provided infer the type, priority, and categorty of the roadmap.
        The other fields are optional and can be left blank if you can't find the information.
        If you add a labour or non labour estimate, make sure you estimate unit and type with value. Do not add an estimate with null values for its other fields.
        """
        
        
        