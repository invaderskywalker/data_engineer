from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat


def enhanceDescriptionPromptProvider(
    name, desc,org_strategy=None
) -> ChatCompletion:
    print("debug enhanceDescriptionPromptProvider ", name, desc)
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        A rough project description is provided by the customer for the project name: {name}
        <rough_description>
        {desc}
        <rough_description>

        <list_of_org_strategies>
            {org_strategy}
        </list_of_org_strategies>
        
        Your job is to -
        1. enhance this rough project description - Please generate a detailed and contextual project description. Ensure that the description reflects the unique aspects of the project, including its objectives, challenges, and key deliverables, making it highly relevant to the scope of work outlined.
            Make sure that you give importance to the project name or project <rough_description> and use <org_info> only as a reference point  to understand the customer context.
        2. create enhanced objective of this project - Please outline the specific objectives of the project based on the provided project scope. Ensure the objectives are clear, concise, and directly aligned with the project’s goals, highlighting the key outcomes expected.
        3. Create project Capabiltities for this project. Highlight key capabilities required for this project, tailored to the industry, domain, broader technology areas and functionality aligned to the project description or scope for eg.. Data analytics, ERP, CRM, Supply chain management, Cloud, Integration, AI, Infrastructure Management etc as few examples
        4. tech_stack - create key technologies involved to execute the project scope/ project description like SAP, Salesforce, Python, React, Nodejs, Docker, Java etc 
        5. choose project type and stage for the project from the list, give 1-2 line desc on org strategy alignment
        6. team_name - give a short but innovative names to teams
        7. job_roles_required - make it very contextual to the scope of the project, make sure to list all roles required to execute the project
        8. Choose the `org_strategy_align` for this project **STRICTLY** from <list_of_org_strategies>

        
        
        Make sure it is aligned with the project name and <rough_description>
        
        Output in Json Format:
        ```json
            {{
                enhanced_description: '', // text
                enhanced_objective: '', // text
                project_capabilities: [], // array of string which represent capability, return only upto 3
                tech_stack: [], // array of string which represent tech, return only upto 5
                sdlc_methodology: '', // one of Agile, Waterfall, Hybrid -  derive this based on how project described in enhanced_description are typically executed across industries. for example - SAP projects follow Waterfall, Product development is done through Agile etc
                team_name: '', // only 1 team name - required for completion of this project
                job_roles_required: [], // upto 5
                project_type: '', // one of Run, Transform, Innovate - look at the enhanced_description and identify what type of project is this. For example support related projects are of project_type Run, AI based projects typically are Innovate project_type etc
                project_stage: '',  //choose one from (Discovery, Design, Build, Complete)
                org_strategy_align: '', // Alignment with org strategy or empty from <list_of_org_strategies>
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def enhanceProjectObjectivePromptProvider(
    name, desc,  project_objective
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        A project name and description  and a rough project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <rough_project_objective>
            {project_objective}
            <rough_project_objective>
        
        Your job is to enhance this rough_project_objective
        
        Output in Json Format:
        ```json
            {{
                enhanced_objective: '',
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createKeyResultsPromptProvider(
    name, desc, project_objective
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation
  
        A project name and description  and a project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
        
        Your job is to create Key results for this project.
        
        Output in Json Format:
        ```json
            {{
                key_results: [], // array of string which represent key results. return only upto 3 key results
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createProjectCapabilitiesPromptProvider(
    name, desc,  project_objective, project_key_results
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation
        
        A project name and description  and a project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
            
            
            <project_key_results>
            {project_key_results}
            <project_key_results>
        
        Your job is to create project Capabiltities for this project.
        which is defined as Creating broad technology, domain, functional capabilities aligned to the project description or scope for eg.. Data analytics, ERP, CRM, Supply chain management, Cloud, Integration, AI, Infrastructure Management etc as few examples
        
        Output in Json Format:
        ```json
            {{
                project_capabilities: [], // array of string which represent capability, return only upto 3
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def findTechStackPromptProvider(
    name, desc, project_objective, project_key_results, project_capabilities
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        A project name and description  and a project objective are provided by the customer:
            <project_name>
            {desc}
            <project_name>
            
            <project_description>
            {desc}
            <project_description>
            
            <project_objective>
            {project_objective}
            <project_objective>
            
            
            <project_key_results>
            {project_key_results}
            <project_key_results>
            
            <project_capabilities>
            {project_capabilities}
            <project_capabilities>
        
        Your job is to list down the tech stack required to finish this project
        
        Only return tech stack terms like python, java
        Output in Json Format:
        ```json
            {{
                tech_stack: [], // array of string which represent tech, return only upto 5
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )
