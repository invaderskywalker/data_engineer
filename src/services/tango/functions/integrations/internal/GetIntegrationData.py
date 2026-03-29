# from src.trmeric_integrations.Jira.Api import JiraAPI
from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_ml.utils.ChunkText import chunkTextForLLM
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_database.dao import TangoDao, IntegrationDao
# from openai import OpenAI
import json
import os
import traceback
from src.trmeric_database.Database import db_instance
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandlerV2 import SQLHandlerV2


# TODO: need to migrate this to a the summarize service to resuse it.

# def chunk_data(data, chunk_size):
#     for i in range(0, len(data), chunk_size):
#         yield data[i:i + chunk_size]


# def llm_process(chunk, message):
#     modelOptions = ModelOptions(
#         model="gpt-4o",
#         max_tokens=4096,
#         temperature=0
#     )
#     openai = OpenAI(api_key=os.getenv("OPENAI_KEY"))
#     response = openai.chat.completions.create(
#         model=modelOptions.model,
#         messages=[
#             {
#                 "role": "system",
#                 "content": """
#                 You have a very important job.
#                     Job description
#                     - Summarize given data in a way so that no key data poitn is missed and the understand of the data becomes more clear.
#                     - Important - the data points provided should remain as it is.
#                     - but still it should be compressed
#                     - extract important data as per the user question
#                 """
#             },
#             {
#                 "role": "user",
#                 "content": f"""
#                 You have to output within token limit for this jira data:
#                 {chunk}

#                 Extract data as per the user query: {message}
#                 """
#             },
#         ],
#         max_tokens=modelOptions.max_tokens,
#         temperature=modelOptions.temperature,
#         stream=False,
#     ).choices[0].message.content
#     return response


# def summarizer(large_data, message):
#     print("in summarizer -------", message)
#     ###
#     chunk_size = 40000
#     summaries = []

#     for chunk in chunk_data(large_data, chunk_size):
#         print("running summary -------")
#         result = llm_process(chunk, message)  # Process each chunk with the LLM
#         summaries.append(result)
#         print("summary of chunk -------")
#         print(result)

#     return " <separator> ".join(summaries)

def get_jira_summary_data(
    tenantID: int,
    userID: int,
    project_id=None
):
    try:
        print("get_jira_summary_data debug -- ", tenantID, userID, project_id)
        integrations_mapping = IntegrationDao.fetchIntegrationMappingForTenantAndUser(tenant_id=tenantID, user_id=userID, integration_type='jira')
        unique_project_ids = []
        for mapping in integrations_mapping:
            print("mapping -- ", mapping)
            if (str(mapping.get("trmeric_project_id")) != str(project_id)):
                continue
            print("mapping -2- ", mapping)
            metadata = mapping.get("metadata") or None
            if not metadata:
                continue
            module = metadata.get("module") or None
            if not module:
                continue
            
            key_id = []
            # print("debug -- ", module )
            if (module == "v1"):
                key = metadata.get("key") or None
                key_id.append(key)
            if (module == "v2"):
                key = metadata.get("key") or None
                key_id.append(key.split("-")[0])
            if (module == "v4"):
                for epic in metadata.get("epics", []) or []:
                    key_id.append(epic["key"].split("-")[0])
                    
            # unique_keys = set(key_id)
            unique_project_ids.append(key_id)
        
        print("debug 000 ",  unique_project_ids)
        if (len(unique_project_ids) == 0):
            return []
        
        key = "JIRA_ANALYSIS_"+ unique_project_ids[0][0]
        return str(TangoDao.fetchTangoIntegrationAnalysisDataForTenantForProject(tenant_id=tenantID, key=key))
    except Exception as e:
        print("error occured here---- ", e)
        

def get_jira_data(
    tenantID: int,
    userID: int,
    # if_user_wants_to_ask_question_on_summary_analysis_of_multi_projects_or_multi_sprints=False,
    summary_analysis_of_which_jira_projects=[],
    # details_analysis_required=True,
    project_id=None,
    user_query="",
    get_all_data=True,
    **kwargs
):
    print("get jira data ----- debug ", summary_analysis_of_which_jira_projects, project_id, user_query, get_all_data)
    result = ''
    
    
    try:
        if (project_id  ):
            # if not if_user_wants_to_ask_question_on_summary_analysis_of_multi_projects_or_multi_sprints:
            # if len(project_id) == 1:
                # raise "Error"
                print("debug in get_jira_data --- ", tenantID, userID, project_id)
                integrationService = IntegrationService()
                output = integrationService.fetchJiraAvailableDataV2(
                    tenant_id=tenantID,
                    user_id=userID,
                    project_id=project_id,
                    get_all_data=get_all_data
                )
                result += output
            # else:
            #     result += f"""
            #         Since you have not  asked question only for one project. SO, I ll give you the summary, I wont be able dig deeper. For me to dig deeper ask question only for a specific project.
            #     """
                    
            
        
        for item in summary_analysis_of_which_jira_projects:
            result += f"""
            Jira data on key metrics
            ------------------------------
            """
            key = "JIRA_ANALYSIS_"+ item
            result += str(TangoDao.fetchTangoIntegrationAnalysisDataForTenantForProject(tenant_id=tenantID, key=key))
            result += f"""
            ------------------------------
            """
        res = SummarizerService({
            "tenant_id": tenantID,
            "user_id": userID
        }).summarizer(result, user_query)

        return res
    except Exception as e:
        print("exception ,,, ", e, traceback.format_exc())
        return "Please limit your search to one project or please confirm if you want all integration analysis"
        
    
    


def get_smartsheet_data(
    tenantID: int,
    userID: int,
    project_id=None,
    user_query='',
    **kwargs
):
    print("debug in get_smartsheet_data --- ", tenantID, userID, project_id)
    integrationService = IntegrationService()
    result = integrationService.fetchSmartSheetData(
        tenant_id=tenantID,
        user_id=userID,
        project_id=project_id,
        # user_query=user_query,
    )
    return result
    # generatedData = SummarizerService({
    #     "tenant_id": tenantID,
    #     "user_id": userID,
    # }).summarizer(large_data=result, message=user_query, identifier='smartsheet')
    # # print("debug --get_smartsheet_data ", result,)
    # return generatedData


def get_github_data(
    tenantID: int,
    userID: int,
    project_id=None,
    user_query='',
    start_date=None,
    end_date = None,
    **kwargs
):
    print("debug in get_github_data --- ", tenantID, userID, project_id)
    
    
    # query = f"""
    #     SELECT value FROM tango_integrationsummary 
    #     where key like 'GITHUB_%' 
    #     and tenant_id = {tenantID} and user_id = {userID}
    #     order by created_date desc
    #     limit 1
    # """
    # res = db_instance.retrieveSQLQueryOld(query)
    # github_data = res[0]["value"]
    
    # with open('github.json', 'w') as file:
    #     json.dump(github_data, file, indent=4)    
    
    integrationService = IntegrationService()
    result = integrationService.fetchGithubData(
        tenant_id=tenantID,
        user_id=userID,
        project_id=project_id,
        start_date = start_date,
        end_date = end_date
    )
    # with open('github.json', 'w') as file:
    #     json.dump(result, file, indent=4)    
    
    generatedData = SummarizerService({
        "tenant_id": tenantID,
        "user_id": userID,
    }).summarizer(large_data=result, message=user_query, identifier='github')
    # print("debug --get_github_data ", result)
    return generatedData


def get_ado_data(
    tenantID: int,
    userID: int,
    project_id=None,
    **kwargs
):
    print("debug in get_ado_data --- ", tenantID, userID, project_id)
    integrationService = IntegrationService()
    result = integrationService.fetchAdoAvailableData(
        tenant_id=tenantID,
        user_id=userID,
        project_id=project_id
    )
    return result


def list_jira_projects(
    tenantID: int,
    userID: int,
    project_id=None,
    **kwargs
):
    print("debug list_jira_projects ", tenantID, userID)
    integrationService = IntegrationService()
    return integrationService.fetchJiraProjectsMapping(tenant_id=tenantID, user_id=userID)


def list_ado_projects(
    tenantID: int,
    userID: int,
    project_id=None,
    **kwargs
):
    print("debug list_ado_projects ", tenantID, userID)
    integrationService = IntegrationService()
    return integrationService.fetchAdoProjectsMapping(tenant_id=tenantID, user_id=userID)


GET_JIRA_DATA = TangoFunction(
    name="get_jira_data",
    description="If the user asks anything about sprints, look here. also if the user talks about jira, look here. for each of the trmeric project mapped to a jira project. this function will get the data from jira and present an abstract view as per the user wants.",
    args=[
        {
            "name": "summary_analysis_of_which_jira_projects",
            "type": "str[]",
            "description": "If user is asking question on analysis over multi epics, multi projects, multi sprints etc. list those jira project ids.",
        },
        # {
        #     "name": "details_analysis_required",
        #     "type": "boolean",
        #     "description": "Very important to pull detailed data for projects"
        # },
        {
            "name": "project_id",
            "type": "int[]",
            "description": """
                See this is important because it will help user to get detailed view of features/issues/stories/bugs etc
                from jira integration data. 
                The trmeric project ids which are linked with jira project, 
                epics or initiative or issues integration
                which the user is asking about. 
                If jira project keys/names are told find trmeric project ids from mapping
                otherwise pass all project ids
            """,
        },
        {
            "name": "user_query",
            "type": "str",
            "description": "Pass whole user query for the informatino extraction from jira data",
        },
    ],
    return_description="""
        Return data for Jira projects. 
        for each of the trmeric project mapped to a jira project. 
        this function will get the data from jira 
        and present a very detailed view as per the user query.
    """,
    function=get_jira_data,
    func_type="general",
    integration="trmeric"
)


LIST_JIRA_PROJECT_MAPPINGS = TangoFunction(
    name="list_jira_projects",
    description="""
    for each of the trmeric project mapped to a jira project. 
    this function will get the list of the mappings.
    user can also ask list my jira integrations then use this fn
    """,
    args=[
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The trmeric project ids that user wants to enquire about",
        },
    ],
    return_description="""Return list of for each of the trmeric project mapped to a jira project. 
    this function will get the list of the mappings.""",
    function=list_jira_projects,
    func_type="general",
    integration="trmeric"
)


LIST_ADO_PROJECT_MAPPINGS = TangoFunction(
    name="list_ado_projects",
    description="""
    for each of the trmeric project mapped to a ado project/board/team/epic level. 
    this function will get the list of the mappings.
    user can also ask list ado integrations then use this fn
    """,
    args=[
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The trmeric project ids that user wants to enquire about",
        },
    ],
    return_description="""Return list of for each of the trmeric project mapped to a ado project/board/epic. 
    this function will get the list of the mappings.""",
    function=list_ado_projects,
    func_type="general",
    integration="trmeric"
)

GET_ADO_DATA = TangoFunction(
    name="get_ado_data",
    description="for each of the trmeric project mapped to a ado project/epic/board. this function will get the data from ado and present an abstract view as per the user wants.",
    args=[
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The trmeric project ids that user wants to enquire about",
        },
    ],
    return_description="Return data for ADO projects. for each of the trmeric project mapped to a ado project. this function will get the data from ado and present an abstract view as per the user wants.",
    function=get_ado_data,
    func_type="general",
    integration="trmeric"
)


GET_SMART_SHEET_DATA = TangoFunction(
    name="get_smartsheet_data",
    description="""
        for each of the trmeric project mapped to a smartsheet project. 
        this function will get the data from smartsheet and present an abstract view as per the user wants.
    """,
    args=[
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The trmeric project ids that user wants to enquire about",
        },
        {
            "name": "user_query",
            "type": "str",
            "description": "What user wants to know from this smartsheet data for these projects",
        },
    ],
    return_description="""
    Return data for Smartsheet projects. 
    for each of the trmeric project mapped to a smartsheet project. 
    this function will get the data from smartsheet and present an abstract view as per the user wants.
    """,
    function=get_smartsheet_data,
    func_type="general",
    integration="trmeric"
)


GET_GITHUB_DATA = TangoFunction(
    name="get_github_data",
    description="""
        This function will be called whenever the user is querying about the information related to github.
        The user has done the Github integration on Trmeric Platform and the insights related to the integrated 
        Github organization, repositories are stored here in the Trmeric database as historical analysis
        
        The information consists of the work done by all the contributors in different repositories.
        It includes the total number of commits made, total Pull requests created,merged into base branch along with the Jira ticket values
        to track the complete workflow or a contributor's estimation in the organization.
    """,
    args=[
        {
            "name": "user_query",
            "type": "str",
            "description": "The information seeked on the github data",
        },
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The trmeric project ids that user wants to enquire about"
        },
        {
            "name": "start_date",
            "type": "str",
            "description": "The start date of the github integration data which user wants to query. Must be in the format 'YYYY-MM-DD'. Essentially, this is a range of dates that the user can choose"
        },
        {
            "name": "end_date",
            "type": "str",
            "description": "The end date of the github integration data which user wants to query. Must be in the format 'YYYY-MM-DD'. Essentially, this is a range of dates that the user can choose"
        }
    ],
    return_description="""
        Output to the best of the analysis of the overview of the contributors' work stored in the github integration data
        This function will get the data from github and present anabstract view as per the user wants.
    """,
    function=get_github_data,
    func_type="general",
    integration="trmeric"
)