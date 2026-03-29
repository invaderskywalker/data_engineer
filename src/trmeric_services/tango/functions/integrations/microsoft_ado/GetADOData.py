from src.trmeric_integrations.MicrosoftAdo.Api import AzureDevOpsAPI
from src.trmeric_services.tango.functions.Types import TangoFunction

def get_project_information(api:AzureDevOpsAPI, project_id, **kwargs):
    return api.get_project_info(project_id)

GET_ADO_PROJECT_DATA = TangoFunction(
name="get_ado_project_data",
description="gets descriptions of a project along with theitsir corresponding issues as well",
args=[
    {
        "name": "project_id",
        "type": "str",
        "description": "The project to get issues for",
    },
],
return_description="Returns information on epics and sprints for a project",
function=get_project_information,
func_type="ado",
integration="ado"
)

