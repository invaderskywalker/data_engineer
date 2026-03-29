# pylint: disable=missing-module-docstring

from abc import ABC, abstractmethod
from src.trmeric_services.tango.types.TangoConversation import TangoConversation
from src.trmeric_database.Database import db_instance
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_database.dao import ProjectsDao
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.agents.prompts import blueprint_creation_prompt, next_step_finder_prompt, plan_functions_prompt, next_step_finder_prompt_v2, blueprint_creation_prompt_v2, blueprint_creation_prompt_v3
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import PortfolioDao, AuthDao, TangoDao, RoadmapDao, CustomerDao, UsersDao, FileDao, IdeaDao, TenantDaoV2
import traceback
from src.trmeric_services.tango.functions.integrations.internal.GetIntegrationData import list_jira_projects, get_jira_data
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.tango.sessions.TangoConversationRetriever import (
    TangoConversationRetriever,
)
import json
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_services.agents.core.agent_functions import AgentFunction


class BaseAgent():
    def __init__(self, log_info = None):
        """_summary_

        Args:
            user_id (str): _description_
            tenant_id (int): _description_
            session_id (str): _description_
        """
        self.log_info = log_info
        self.tenant_id = self.log_info.get("tenant_id")
        self.user_id = self.log_info.get("user_id")
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.4
        )
        
        self.modelOptionsMore = ModelOptions(
            model="gpt-4o",
            max_tokens=12000,
            temperature=0.2
        )
        
        self.modelOptions41 = ModelOptions(
            model="gpt-4.1",
            max_tokens=16000,
            temperature=0.2
        )
        
        self.fastModelOptions = ModelOptions(
            model="gpt-4o-mini",
            max_tokens=4096,
            temperature=0.4
        )
        
        self.conversation = TangoConversation(
            user_id=self.log_info.get("user_id"), 
            session_id=self.log_info.get("session_id"),
            tenant_id=self.log_info.get("tenant_id")
        )
        self.eligible_projects = ProjectsDao.FetchAvailableProject(tenant_id=self.log_info.get("tenant_id"), user_id=self.log_info.get("user_id"))
        self.archived_projects = ProjectsDao.FetchEligibleProjectsForVRAgent(tenant_id=self.log_info.get("tenant_id"), user_id=self.log_info.get("user_id"))

        # print("self.eligible_projects, self.archived_projects", self.eligible_projects, self.archived_projects)

        self.eligible_project_id_and_names = ProjectsDao.fetchProjectsIdAndTItle(project_ids=self.eligible_projects)
        self.archived_project_id_and_names = ProjectsDao.fetchProjectsIdAndTItle(project_ids=self.archived_projects)
        
        self.context_string = f"""
            These are the projects that the user has access to:
            All the projects which are currently active : {json.dumps(self.eligible_project_id_and_names, indent=2)}
            All the projects including archived ones **only to be used for Value Realization agent**: {self.archived_project_id_and_names}
        """
        
        
        roadmap_arr = RoadmapDao.fetchEligibleRoadmapList(tenant_id=self.log_info.get("tenant_id"), user_id=self.log_info.get("user_id"))
        
        self.context_string += f"""
        All roadmap and tenant of this customer: {roadmap_arr}
        """
        
        
        project_arr = ProjectsDao.fetchProjectIdTitleAndPortfolio(
            tenant_id=self.log_info.get("tenant_id"),
            project_ids = self.eligible_projects
        )
        
        ideas = IdeaDao.fetchIdeasDataWithProjectionAttrs(
            projection_attrs=["id", "title"],
            tenant_id=self.log_info.get("tenant_id"),
            user_id=self.log_info.get("user_id"), 
        )
        
        self.project_and_roadmap_context_string = f"""
            These are the projects that the user has access to:
            ------------------
            All the projects which are currently active : {json.dumps(project_arr, indent=2)}
            -----------------
            All roadmaps of this customer: {json.dumps(roadmap_arr, indent=2)}
            -----------------
            All ideas of this customer: {json.dumps(ideas, indent=2)}
        """
        
        self.roadmap_context_string = f"""
            -----------------
            All roadmap and tenant of this customer: {json.dumps(roadmap_arr, indent=2)}
        """

        self.program_list = f"""
            All program list for this customer: {json.dumps(ProjectsDao.fetchAllProgramFortenant(tenant_id=self.log_info.get("tenant_id")))}
        """
        
        sessionID = self.log_info.get("session_id")
        userID = self.log_info.get("user_id")
        
        self.current_session_uploaded_files = f"""
            Files uploaded by customer in this chat session.
            
            Details:
            ----------------------
            {FileDao.FilesUploadedInS3ForSession(sessionID)}
            ----------------------
        """
        
        self.templates = f"""
            Templates stored by customer in Trmeric.
            Details:
            ----------------------
            {TenantDaoV2.fetch_saved_templates(
                    projection_attrs=["id", "caetgory"],
                    category = None,
                    tenant_id = self.tenant_id,
                    only_active = True,
                    order_clause = None,
                    limit = 100,
                )}
            ----------------------
        """
        
        
        
        role_of_user = AuthDao.fetchRoleOfUserInTenant(user_id=self.log_info.get("user_id"))
        all_roles_in_trmeric_for_tenant = AuthDao.fetchAllRolesInTrmericForTenant(tenant_id=self.log_info.get("tenant_id"))
        self.context_string += f"Role of this User in Trmeric Platform: {role_of_user}"
        self.org_role_user = f"Role of this User in Trmeric Platform: {role_of_user}. All user distinct roles in trmeric are- {all_roles_in_trmeric_for_tenant}"
        # portfolio_data = PortfolioDao.fetchPortfolioDetailsForApplicableProjectsForUser(tenant_id=self.log_info.get("tenant_id"), projects_list=self.eligible_projects, projects_needed=False)
        # portfolio_data = PortfolioDao.fetchApplicablePortfolios(user_id=self.log_info.get("user_id"), tenant_id=self.log_info.get("tenant_id"))
        from src.trmeric_services.agents import PortfolioApiService
        portfolio_data = PortfolioApiService().get_portfolio_context_of_user(user_id=self.log_info.get("user_id"), tenant_id=self.log_info.get("tenant_id"))
        self.context_string += f"""
            So, these are the portfolios that the user has access to:
            {portfolio_data}
        """
        # self.context_string += f"""
        #     All Portfolios of custoemr:::: 
        #     {PortfolioDao.fetchPortfoliosOfTenant(tenant_id=self.log_info.get("tenant_id"))}
        # """
        self.org_info_string = ""
        self.user_info_string = f"""
            these are the portfolios that the user has access to:
            {portfolio_data}
        """
        customer_info = CustomerDao.FetchCustomerOrgDetailInfo(tenant_id=self.log_info.get("tenant_id"))
        user_designation_info = UsersDao.fetchUserDesignation(user_id=self.log_info.get("user_id"))
        if (len(customer_info)>0):
            self.org_info_string += f"""
                This customer Org Info gathered by Trmeric is:
                {customer_info[0].get("org_info")}
            """
            self.user_info_string += f"Role of this User in his Org: {user_designation_info}."
            
        
        # roadmap_basic_info = RoadmapDao.fetchRoadmapList(self.tenant_id)
        # self.context_string += f"""
        #     All roadmaps: id, title and portfolio.
        #     that are already planned in this org are listed below: 
        #     {roadmap_basic_info}
        # """
        
        self.integration_info_string = ""
        
        try:
            integrations_with_projects = IntegrationService().fetchIntegrationListForUser(self.tenant_id, self.user_id, skip=True)
            self.integration_info_string += json.dumps(integrations_with_projects)
            # if integrations_with_projects is not None:
            #     if len(integrations_with_projects)> 0:
                    # self.integration_info_string += f"""
                    #     Trmeric Projects mapped with jira projects/initiative/epic
                    #     {integrations_with_projects}
                    # """
                    # summary_analysis_of_projects = TangoDao.fetchTangoIntegrationKeyAnalysisDataForTenant(tenant_id=self.tenant_id)
                    # self.integration_info_string += f"""
                    #     We already have stored summarized analysis 
                    #     for sprints of these jira projects for this user.
                    #     **Very important** - use exact names from this list for the argument 
                    #     summary_analysis_of_which_jira_projects for the function get_jira_data.
                        
                    #     {summary_analysis_of_projects}
                    # """
        except Exception as e:
            appLogger.error({
                "function": "BaseAgent_initializeIntegration_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }) 
        
    def refresh_conversation(self):
        pass
        # chats = TangoConversationRetriever().fetchChatBySessionAndUserID(
        #     sessionID=self.log_info.get("session_id"), 
        #     userID=self.log_info.get("user_id")
        # )
        # self.set_conversation(conversation=chats)
        
    def set_conversation(self, conversation: TangoConversation):
        self.conversation = conversation
        
    def stream_llm_response(self, chat):
        for chunk in self.llm.runWithStreaming(chat, self.modelOptions, "agent::stream_llm_response", self.log_info):
            yield chunk
    
    def _create_blueprint(self, data, agents_prompt, conv):
        try:
            llm_prompt = blueprint_creation_prompt(conv=conv, agent_descriptions=agents_prompt, primary_agent_prompt=data)
            print("debug -- _create_blueprint ", llm_prompt.formatAsString())
            primary_agent_response = self.llm.run(llm_prompt, self.modelOptions , 'agent::_create_blueprint', self.log_info)
            print("debug -- _create_blueprint ", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            return result
        except Exception as e:
            print("error in _create_blueprint", e, traceback.format_exc())
            return []
        
    def create_blueprint(self, agents_prompt, conv):
        try:
            llm_prompt = blueprint_creation_prompt_v3(conv=conv, agent_descriptions=agents_prompt)
            primary_agent_response = self.llm.run(llm_prompt, self.modelOptions , 'agent::create_blueprint', self.log_info)
            print("debug -- _create_blueprint ", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            return result
        except Exception as e:
            print("error in _create_blueprint", e, traceback.format_exc())
            return []
        
    def create_blueprint_v3(self, agents_prompt, user_context, integrations=None, user_id = None):
        try:
            conv = self.conversation.format_conversation()
            context = self.context_string
            llm_prompt = blueprint_creation_prompt_v3(conv=conv, agent_descriptions=agents_prompt, context=context, user_context=user_context, integrations=integrations)
            # print("debug -- create_blueprint_v3 prompt ", llm_prompt.formatAsString())
            primary_agent_response = self.llm.run(llm_prompt, self.modelOptions , 'agent::create_blueprint', self.log_info, memory = user_id, web=False)
            print("debug -- create_blueprint_v3 ", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            return result
        except Exception as e:
            print("error in _create_blueprint", e, traceback.format_exc())
            return []
        
    def _create_next_step(self, data, steps_executed_already, agents_prompt, conv):
        try:
            llm_prompt = next_step_finder_prompt(steps_executed_already=steps_executed_already, agents=agents_prompt, conversation=conv, data_from_current_agent=data)
            # print("debug -- _create_next_step ", llm_prompt.formatAsString())
            primary_agent_response = self.llm.run(llm_prompt, self.modelOptions , 'agent::_create_next_step', self.log_info)
            print("debug -- _create_next_step_output ", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            return result
        except Exception as e:
            print("error in _create_next_step", e, traceback.format_exc())
            return {}
        
    def create_next_step(self, steps_executed_already, agents_prompt, conv):
        try:
            llm_prompt = next_step_finder_prompt_v2(steps_executed_already=steps_executed_already, agents=agents_prompt, conversation=conv)
            # print("debug -- _create_next_step ", llm_prompt.formatAsString())
            primary_agent_response = self.llm.run(llm_prompt, self.modelOptions , 'agent::_create_next_step', self.log_info)
            print("debug -- _create_next_step_output ", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            return result
        except Exception as e:
            print("error in _create_next_step", e, traceback.format_exc())
            return {}
    
    def plan_functions(self, data, agents_prompt, conv, user_context, agent_name):
        prompt = plan_functions_prompt(data, agents_prompt, conv, user_context, agent_name)
        response = self.llm.run(prompt, self.modelOptions, "agent::plan_functions", self.log_info)
        print("_plan_functions ", prompt.formatAsString())
        print("_plan_functions response", response)
        response_json = extract_json_after_llm(response)
        return response_json
    
    def expose_data(self):
        """
        Exposes agent-specific data for use by other agents or blueprint creation.
        Override this in derived agents.
        """
        return {}
    
    def fetch_data_for_blueprint_creation(self):
        pass
        
        
    def generate_response_prompt(self, analysis_results):
        return ""
        
    @abstractmethod
    def action_function_getter(self, action:str):
        pass
    
    @classmethod
    @abstractmethod
    def register_action_functions(self,action_name: str,agent_function: AgentFunction):
        """
        Registers action functions for the agent.
        
        Args:
            action_map (dict): A dictionary mapping action names to their corresponding functions.
        """
        pass
    
    

    