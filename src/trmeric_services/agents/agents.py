from src.trmeric_services.agents.core import AgentRegistry, ExecutionManager, BaseAgent
from src.trmeric_services.tango.sessions.InsertTangoData import TangoDataInserter
from src.trmeric_services.agents.classes import ALL_AGENTS, NORMAL_USE_AGENTS
import datetime
from src.trmeric_services.tango.utils.InitializeIntegrations import createIntegrationsAgent
from src.trmeric_services.tango.utils.FetchAvailableIntegrations import fetchAvailableIntegrations
from src.trmeric_services.agents.functions.service_assurance import update_project_status, update_status_milestone_risk, create_service_assurance_report, create_review_report_for_project, update_status_milestone_risk, update_status_basic_data, update_status_milestone_risk_v2
from src.trmeric_services.agents.functions.capacity_planner import capacity_planner, resource_allocator
from src.trmeric_services.agents.functions.onboarding.capacity import capacity_uploaded_files_url
from src.trmeric_services.agents.functions.onbaording_v2 import onboarding_controller, OnboardingV2Controller, fetch_states, discrad_progress, save_progress, onboarding_controller_v3, fetch_states_v3
from src.trmeric_services.agents.functions.value_realization import value_realization
from src.trmeric_utils.knowledge.TangoMemory import TangoMem
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_integrations.IntegrationRetriever import retrieveIntegrations, updateIntegrationswithSessionID
import traceback
from src.trmeric_ws.helper import SocketStepsSender
from src.trmeric_services.roadmap.controller import RoadmapController
from src.trmeric_services.phoenix import AgentV1Handler
from src.trmeric_services.agents_v2.runner import AgentsRunner
from src.controller.qna import QnaController
from threading import Thread
import threading
import time
import json

from src.trmeric_services.project.projectService import ProjectService

from src.trmeric_services.agents.functions.roadmap_agent.update_actions import update_roadmap_dates_fn, update_roadmap_portfolio_ranks_fn, update_roadmap_ranks_fn
from src.trmeric_services.agents.functions.businesscase_agent.agent import business_case_from_template_create, retrigger_financial
from src.trmeric_services.agents.functions.solution_agent.agent import solution_create_for_roadmap, solution_from_template_create
from src.trmeric_services.provider.quantum.actions import process_uploaded_doc
from src.trmeric_services.agents.functions.integration_agent.actions import run_cron_for_tenants
from src.trmeric_services.agents.functions.potential_agent import Potential
from src.trmeric_services.agents.functions.roadmap_agent.roadmap_schedule_review import roadmap_schedule_review_fn



class AgentsHandler:
    def __init__(self, session_id, tenant_id, user_id, metadata, agent_name=None, socketio=None, client_id=None, **kwargs):
        self.agent_registry = AgentRegistry()
        self.metadata = metadata
        self.log_info = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata
        }
        self.qnaController = QnaController()
        self.roadmapController = RoadmapController()
        self.projectService = ProjectService()
        self.potentialService = Potential()
        
        self.base_agent = BaseAgent(self.log_info)
        self.integrations = []
        print("---AgentsHandler init ", agent_name)
        # if agent_name != "CustomAgentV1":
        if agent_name:
            self._register_agent_by_name(agent_name)
            self.integrations = retrieveIntegrations(tenant_id, user_id)
            self.integrations = updateIntegrationswithSessionID(
                self.integrations, session_id)
        else:
            self._register_all_agents(NORMAL_USE_AGENTS)
            self.integrations = createIntegrationsAgent(fetchAvailableIntegrations(
                user_id), user_id, tenant_id, session_id, selectOnlyFew=['jira'], forceJiraOld=True)
        self.tangoDataInserter = TangoDataInserter(user_id, session_id)
        self.socketio = socketio
        self.client_id = client_id
        self.sender = kwargs.get("socketSender") or None

        # threading.Thread(target=self.refresh_with_timeout, args=(
        #     user_id, tenant_id), daemon=True).start()
        # print("self.integrations ", self.integrations)

        self.execution_manager = ExecutionManager(
            self.agent_registry, self.base_agent, self.tangoDataInserter, self.integrations, self.log_info, socketio=socketio, client_id=client_id, step_sender=self.sender)
        self.agents_v1_handler = AgentV1Handler(
            self.base_agent, self.tangoDataInserter, self.log_info, socketio=socketio, client_id=client_id)
        
        self.agents_v2_handler = AgentsRunner(
            self.base_agent, 
            self.tangoDataInserter, 
            self.log_info, 
            socketio=socketio, 
            client_id=client_id
        )
        
        
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id

    # def refresh_with_timeout(self, user_id, tenant_id):
    #     tango_mem = TangoMem(user_id, tenant_id)
    #     thread = threading.Thread(
    #         target=tango_mem.refresh_memory, args=(100,), daemon=True)
    #     thread.start()
    #     thread.join(timeout=60)  # Wait for max 60 seconds


    def _register_agent_by_name(self, agent_name):
        """
        Registers a single agent by name and clears out other agents.

        Args:
            agent_name (str): The name of the agent to register.
        """
        # if agent_name in ["data_analyst", "planning_agent", "orion_planning", "orion", "orion_solutioning", "onboarding_v2"]:
        if agent_name in ["data_analyst", "planning_agent", "orion_planning", "orion", "orion_solutioning", "roadmap_creation_agent", "onboarding_v2", "trucible", "tango","mission_agent"]:
            return
        for agent in ALL_AGENTS:
            if agent.name == agent_name:
                agent_class = agent
                break
        if not agent_class:
            raise ValueError(
                f"Agent with name '{agent_name}' not found in registry.")

        self.agent_registry.register_agent(agent_class)

    def _register_agent(self, agent_class):
        """
        Registers an agent class in the registry.
        """
        self.agent_registry.register_agent(agent_class)

    def _register_all_agents(self, agent_classes):
        """
        Registers multiple agent classes directly.

        Args:
            agent_classes (list): List of agent classes to register.
        """
        for agent_class in agent_classes:
            self._register_agent(agent_class)

    def set_conversation(self, chats):
        """
        Store conversation history in the handler for use by agents.
        """
        self.base_agent.set_conversation(conversation=chats)
        # self.conversation = chats

    def handle_user_query(self, message: str, user_context='', agent_triggered=False, metadata=None):
        """
        Handles the user's query by generating and executing a plan.
        """
        print("debug - handle_user_query ", message, user_context)
        currentDate = datetime.datetime.now().date().isoformat()
        if agent_triggered and "my-projects" in user_context:
            self.base_agent.conversation.add_user_message(
                message,
                datetime
            )
        elif "my-projects" in user_context and message == "":
            self.base_agent.conversation.add_user_message(
                f"""
                    In the answer please tell how many projects I am managing.
                    
                    and comment on the my projects for example grouping them into good going projects or risky projects.
                    
                    tell me what project need most attention looking at all the attributes of the project data.
                    and find the most risky project.

                    Note: Focus on your tone and style of response.
                """,
                datetime
            )
        elif "edit-project-screen-one" in user_context and message == "":
            self.base_agent.conversation.add_user_message(
                f"""
                    Only focus in this project id for detailed analysis: 
                    the project id is written in {user_context} at the end in the format edit-project-screen-one/<project_id>
                    
                    You need to tell me in detail what is the risk in this project and how can I solve it. 
                    Use your external knowledge to 
                    suggest the best solution to the risks.
                    
                    Also look at todays date: {currentDate}
                    And analyse if I missed any timeline or I have not resolved any risk or milestone etc.
                    
                    Note: Focus on your tone and style of response.
                """,
                datetime
            )
        else:
            self.base_agent.conversation.add_user_message(message, datetime)
            self.tangoDataInserter.addUserMessage(message=message)

        # for chunk in self.execution_manager.execute_beta(user_context):
        #     yield chunk

        for chunk in self.execution_manager.execute_alpha(user_context):
            yield chunk

     
    ## To Generalize the agent handling function: Using all the params combined
    #######Edgecases
        # Service assurance Agent
        # if action == "open_project_review_ui":
        #     socketio.emit(
        #         "service_assurance_agent",
        #         {
        #             "event": "open_project_review_ui",
        #         },
        #         room=client_id
        #     )
        
        # EDGE CASES
        #Roadmap agent
        # -Creation agent
        # -Solution agent
        # -Roadmap agent
        
        #Service assurance agent
        # if action == "open_project_review_ui":
       
    
    def handle_agent2(self, agent: str, action: str, data, socketio, client_id, metadata, message='',**kwargs):
        
        """Handles an action for a given agent by finding and calling the appropriate AgentFunction."""
            
        print("data --- in metadata --- ", action, metadata, agent, message)
        appLogger.info({"event": f"handle_agent:{agent}", "action": action, "tenant_id": self.tenant_id})
           
        try:
            steps_sender_class = SocketStepsSender(agent_name=agent, socketio=socketio, client_id=client_id)
            
            ##Edge cases need to refractor or group internally
            if agent == "service_assurance_agent" and action == "open_project_review_ui":
                    socketio.emit("service_assurance_agent",{"event": "open_project_review_ui",},room=client_id)
            elif agent == "mission_agent":
                if action == "create_mission":
                    self.qnaController.fetchQnaChatPrefillSocketIO( 
                            socketio=socketio,
                            client_id=client_id,
                            metadata = metadata,
                            _type="mission",
                    )   
            
            elif agent not in [ "roadmap_creation_agent"]:
                
                # Retrieve agent class from registry
                agent_class = self.agent_registry.get_agent(agent)
                if not agent_class:
                    print("--deubg agent_class not found --- ", agent)
                    raise ValueError(f"Unknown agent: {agent}")
                agent_instance = agent_class(log_info=self.log_info)
                
                print("--debug agent_class----------", agent_instance,action)
                # agent_instance.register_action_functions("trigger_new_function", NEW_FUNCTION)  #Register a new function if needed
                
                # Find and execute the matching AgentFunction define in each individual agent class
                agent_action = agent_instance.action_function_getter(action)
                print("--deubg agent_action-----",agent_action)
                
                function = agent_action.get("function", None) or None
                name = agent_action.get("name",None) or None
                print("--debug function name --- ", name, function)
                
                if not function:
                    print("--deubg function not found --- ", action, agent)
                    raise ValueError(f"Unknown action '{action}' for agent '{agent}'")
                return function(
                    tenantID = self.tenant_id,
                    userID = self.user_id,
                    sessionID = self.session_id,
                    
                    llm = self.base_agent.llm,
                    model_opts = self.base_agent.modelOptions,
                    model_opts2 = self.base_agent.modelOptions41,
                    logInfo = self.log_info,
                    socketio=socketio,
                    client_id=client_id,
                    
                    data=data,
                    message=message,
                    metadata=metadata,
                    
                    integrations = self.integrations,
                    qna_controller=self.qnaController,
                    steps_sender=steps_sender_class,
                    eligibleProjects=self.base_agent.eligible_projects,
                    update_looks_good_to_user=True if action == "update_status_step2" else False,
                    base_agent = self.base_agent,
                    **kwargs
                )
                 
            elif agent == "roadmap_creation_agent":
                # controller setup
                self.roadmapController.roadmap_action_controller(
                    action = action,
                    data = data,
                    metadata = metadata,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    llm=self.execution_manager.llm,
                    logInfo= self.log_info,
                    model_opts=self.execution_manager.modelOptions,
                    qna_controller = self.qnaController,
                    socketio=socketio,
                    client_id=client_id,
                    step_sender = steps_sender_class,
                )   

            # elif agent == "portfolio_agent":
            #     if action == "create_portfolio":
            #         self.qnaController.fetchQnaChatPrefillSocketIO( 
            #                 socketio=socketio,
            #                 client_id=client_id,
            #                 metadata = metadata,
            #                 _type="portfolio",
            #                 # step_sender = step_sender
            #         )   
            
            # elif agent == "roadmap_solution_agent":
            #     print("data --- handle_agent-1 roadmap_solution_agent-- ", data, agent, action)
            #     if action == "create":
            #         print("data --- handle_agent-2-roadmap_solution_agent- ", self.session_id, data, agent, action)
            #         solution_from_template_create(
            #             tenantID=self.tenant_id,
            #             userID=self.user_id,
            #             llm=self.base_agent.llm,
            #             model_opts=self.base_agent.modelOptions,
            #             logInfo=self.log_info,
            #             socketio=socketio,
            #             client_id=self.client_id,
            #             data=data,
            #             steps_sender=steps_sender_class
            #         )
                    
            #     if action == "create_solution":
            #         print("data --- handle_agent-2-solution_create_for_roadmap- ", self.session_id, data, agent, action)
            #         solution_create_for_roadmap(
            #             tenantID=self.tenant_id,
            #             userID=self.user_id,
            #             llm=self.base_agent.llm,
            #             model_opts=self.base_agent.modelOptions,
            #             logInfo=self.log_info,
            #             socketio=socketio,
            #             client_id=self.client_id,
            #             data=data,
            #             steps_sender=steps_sender_class
            #         )
                    
            # elif agent == "roadmap_agent":
            #     print("here in roadmap agetn action ", action)
            #     match action:
            #         case "update_timeline":
            #             try:
            #                 update_roadmap_dates_fn(
            #                     tenant_id=self.tenant_id,
            #                     user_id=self.user_id,
            #                     llm=self.base_agent.llm,
            #                     model_opts=self.base_agent.modelOptions,
            #                     logInfo=self.log_info,
            #                     socketio=socketio,
            #                     client_id=client_id,
            #                     roadmap_data=data
            #                 )
            #             except Exception as e:
            #                 print("error ", e)
            #         case "update_rank":
            #             update_roadmap_ranks_fn(
            #                 tenant_id=self.tenant_id,
            #                 user_id=self.user_id,
            #                 llm=self.base_agent.llm,
            #                 model_opts=self.base_agent.modelOptions,
            #                 logInfo=self.log_info,
            #                 socketio=socketio,
            #                 client_id=client_id,
            #                 rank_data=data
            #             )
            #         case "update_portfolio_rank":
            #             update_roadmap_portfolio_ranks_fn(
            #                 tenant_id=self.tenant_id,
            #                 user_id=self.user_id,
            #                 llm=self.base_agent.llm,
            #                 model_opts=self.base_agent.modelOptions,
            #                 logInfo=self.log_info,
            #                 socketio=socketio,
            #                 client_id=self.client_id,
            #                 roadmap_data=data
            #             )
            #         case "roadmap_schedule_review":
            #               roadmap_schedule_review_fn(
            #                           tenantID=self.tenant_id,
            #                           userID=self.user_id,
            #                           edited_schedule=data,               #        <-- MUST be list of roadmaps with dates edited
            #                           #         last_user_message=self.last_message #        whatever user typed in chat (optional)
            #                           socketio=socketio,
            #                           client_id=self.client_id,
            #                           llm=self.base_agent.llm,
            #                           sessionID=self.session_id,
            #                           base_agent=self.base_agent
            #                       )
            
            # elif agent == "idea_ranking_agent":
            #     print("here in idea_ranking_agent action ", action)
            #     match action:
            #         case "update_rank":
            #             update_idea_ranks_fn(
            #                 tenant_id=self.tenant_id,
            #                 user_id=self.user_id,
            #                 llm=self.base_agent.llm,
            #                 model_opts=self.base_agent.modelOptions,
            #                 logInfo=self.log_info,
            #                 socketio=socketio,
            #                 client_id=client_id,
            #                 data=data
            #             )
            #         case "update_portfolio_rank":
            #             update_idea_portfolio_ranks_fn(
            #                 tenant_id=self.tenant_id,
            #                 user_id=self.user_id,
            #                 llm=self.base_agent.llm,
            #                 model_opts=self.base_agent.modelOptions,
            #                 logInfo=self.log_info,
            #                 socketio=socketio,
            #                 client_id=self.client_id,
            #                 data=data
            #             )
                    
            else:
                print("--debug no agent", agent,action)
                steps_sender_class.sendError(key=f"Unknown action '{action}' for agent '{agent}'",function="handle_agent2")
                
        except Exception as e:
            print(f"Error handling agent2 {agent} with action {action}: {e}")
            steps_sender_class.sendError(key=f"Error performing {action}",function="handle_agent2")
            appLogger.error({"event": "handle_agent_error", "agent": agent, "action": action, "error": str(e), "tenant_id": self.tenant_id})
            raise ValueError(f"Unknown action '{action}' for agent '{agent}'")
        
                    
   
   
   
    def handle_agent(
        self,
        agent,
        action,
        data,
        socketio,
        client_id,
        metadata,
        message='',
    ):
        print("data --- in meatadata--- ", action,  metadata, agent, message)
        appLogger.info({"event":f"handle_agent:{agent}","action":action,"tenant_id":self.tenant_id})
        steps_sender_class = self.sender
        # steps_sender_class = SocketStepsSender(agent_name= agent, socketio=socketio, client_id=client_id)
        
        match agent:
            #done
            case "service_assurance_agent":
                if action == "create_service_assurance_report":
                    create_service_assurance_report(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        eligibleProjects=self.base_agent.eligible_projects,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions,
                        socketio=socketio,
                        client_id=client_id,
                        project_id=data.get("project_id"),
                        step_sender = steps_sender_class
                    )

                if action == "create_project_review_screen":
                    create_review_report_for_project(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        eligibleProjects=self.base_agent.eligible_projects,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions2,
                        socketio=socketio,
                        client_id=client_id,
                        project_id=data.get("project_id"),
                        step_sender = steps_sender_class
                    )

                if action == "open_project_review_ui":
                    socketio.emit(
                        "service_assurance_agent",
                        {
                            "event": "open_project_review_ui",
                        },
                        room=client_id
                    )

                if action == "fetch_status_update_basic_data":
                    update_status_basic_data(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        eligibleProjects=self.base_agent.eligible_projects,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions,
                        socketio=socketio,
                        client_id=client_id,
                        project_id=data.get("project_id"),
                        step_sender = steps_sender_class
                    )

                if action == "update_status_step1":
                    update_status_milestone_risk_v2(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        eligibleProjects=self.base_agent.eligible_projects,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions,
                        socketio=socketio,
                        client_id=client_id,
                        project_id=data.get("project_id"),
                        project_name=data.get("project_name"),
                        sessionID=self.session_id,
                        logInfo=self.base_agent.log_info,
                        update_looks_good_to_user=False,
                        last_user_message="Message: " + message +
                        "\n\n" + "Data: " + json.dumps(data),
                        step_sender = steps_sender_class
                    )

                if action == "update_status_step2":
                    update_status_milestone_risk_v2(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        eligibleProjects=self.base_agent.eligible_projects,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions,
                        socketio=socketio,
                        client_id=client_id,
                        project_id=data.get("project_id"),
                        project_name=data.get("project_name"),
                        logInfo=self.base_agent.log_info,
                        update_looks_good_to_user=True,
                        last_user_message=message,
                        input_json=data,
                        step_sender = steps_sender_class
                    )

            #done
            case "resource_planning_agent":
                if action == "trigger_capacity_planner":
                    capacity_planner(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.execution_manager.llm,
                        logInfo=self.log_info,
                        model_opts=self.execution_manager.modelOptions,
                        socketio=socketio,
                        client_id=self.client_id,
                        project_id=data.get("project_id"),
                        team_id=data.get("team_id"),
                        sender = steps_sender_class
                    )

                if action == "trigger_resource_allocator":
                    resource_allocator(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions2,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        sessionID=self.session_id,
                        data = data,
                        sender = steps_sender_class
                    )

            case "roadmap_creation_agent":
                # controller setup
                self.roadmapController.roadmap_action_controller(
                    action = action,
                    data = data,
                    metadata = metadata,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    llm=self.execution_manager.llm,
                    logInfo= self.log_info,
                    model_opts=self.execution_manager.modelOptions,
                    qna_controller = self.qnaController,
                    socketio=socketio,
                    client_id=client_id,
                    step_sender = steps_sender_class
                )                
               
            #done     
            case "onboarding_agent":
                if action == "specific_capacity_creation":
                    # print("--debug requestbody------", metadata.get('request_body',{}))
                    request_body = metadata.get('request_body', {})
                    appLogger.info(
                        {"event": "capacity_file_url", "data": request_body})
                    capacity_uploaded_files_url(
                        # tenantID=self.tenant_id,
                        # userID=self.user_id,
                        integrations=self.integrations,
                        metadata=request_body.get("metadata", {}),
                        socketio=socketio,
                        client_id=client_id,
                        # sessionID=self.session_id,
                        # llm=self.execution_manager.llm,
                        # model_opts=self.execution_manager.modelOptions,
                        # logInfo=self.log_info,
                    )

            case "portfolio_agent":
                if action == "create_portfolio":
                    self.qnaController.fetchQnaChatPrefillSocketIO( 
                            socketio=socketio,
                            client_id=client_id,
                            metadata = metadata,
                            _type="portfolio",
                            # step_sender = step_sender
                    )
            
            case "quantum_agent":
                if action == "process_uploaded_doc":
                    process_uploaded_doc(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        data =data,
                        llm=self.execution_manager.llm,
                        model_opts=self.execution_manager.modelOptions2,
                        socketio=socketio,
                        client_id=client_id,
                        logInfo=self.log_info,
                        step_sender = steps_sender_class
                    )
                    
            case "roadmap_agent":
                print("here in roadmap agetn action ", action)
                match action:
                    case "update_timeline":
                        try:
                            update_roadmap_dates_fn(
                                tenant_id=self.tenant_id,
                                user_id=self.user_id,
                                llm=self.base_agent.llm,
                                model_opts=self.base_agent.modelOptions,
                                logInfo=self.log_info,
                                socketio=socketio,
                                client_id=client_id,
                                roadmap_data=data,
                                step_sender = steps_sender_class
                            )
                        except Exception as e:
                            print("error ", e)
                    case "update_rank":
                        update_roadmap_ranks_fn(
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=client_id,
                            rank_data=data,
                            step_sender = steps_sender_class
                        )
                    case "update_portfolio_rank":
                        update_roadmap_portfolio_ranks_fn(
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            roadmap_data=data,
                            step_sender = steps_sender_class
                        )
                    
            #done
            case "project_creation_agent":
                if action == "update_project_canvas":
                    self.projectService.updateProjectCanvas(
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            project_id = data.get("project_id"),
                            socketio=socketio,
                            client_id=client_id,
                            model_opts = self.execution_manager.modelOptions2,
                            logInfo = self.log_info,
                            step_sender = steps_sender_class
                        )
                    
                elif action == "fetch_scope_driveintegration":
                    self.projectService.fetchScopeFromIntegration(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        project_id = data.get("project_id"),
                        # docs =data.get("docs"),
                        socketio=socketio,
                        client_id=client_id,
                        logInfo = self.log_info,
                        key = data.get("s3_key"),
                        step_sender = steps_sender_class
                    )
                
                elif action == "tango_assist_project":
                    
                    def run_create_project():
                        result = self.projectService.createProjectV2(
                            tenant_id=self.tenant_id,
                            project_name=data.get("project_name", "Project"),
                            project_description=data.get("project_description", "Desc"),
                            is_provider = data.get("is_provider",False),
                            log_input=self.log_info,
                            step_sender = steps_sender_class
                        )
                        socketio.emit("project_creation_agent", {"event": "tango_assist", "data": result}, room=client_id)
                        return

                    thread = threading.Thread(target=run_create_project)
                    thread.start()

                    # Send periodic timelines while the thread runs
                    step_counter = 0
                    stages = ["Creating Overview", "Fetching Configuration"]
                    for stage in stages:
                        steps_sender_class.sendSteps(f"{stage}", False)
                        socketio.sleep(seconds=8)
                        step_counter += 1
                        
                    while thread.is_alive() and step_counter<len(stages):
                        steps_sender_class.sendSteps(f"{stages[step_counter % len(stages)]}", False)
                        socketio.sleep(seconds = 8)
                        step_counter += 1
                        


            case  "onboarding_v2":
                print("data --- handle_agent-1-- ", data, agent, action)
                if action == "chat_onboarding_v2":
                    print("data --- handle_agent-2-- ", data, agent, action)
                    try:
                        onboarding_controller(
                            tenantID=self.tenant_id,
                            userID=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            data=data
                        )

                        # print("data --- handle_agent-3-- ", data, agent, action)
                    except Exception as e:
                        print("error here , ", e, traceback.format_exc())

                elif action == "chat_onboarding_v3":
                    try:
                        onboarding_controller_v3(
                            tenantID=self.tenant_id,
                            userID=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            data=data
                        )

                        # print("data --- chat_onboarding_v3-3-- ",
                        #       data, agent, action)
                    except Exception as e:
                        print("error here , ", e, traceback.format_exc())

                elif action == "fetch_states_v3":
                    try:
                        fetch_states_v3(
                            tenantID=self.tenant_id,
                            userID=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            data=data
                        )

                        # print("data --- chat_onboarding_v3-3-- ",
                        #       data, agent, action)
                    except Exception as e:
                        print("error here , ", e, traceback.format_exc())

                elif action == "chat_onboarding_v3":
                    print("data --- handle_agent-3-- ", data, agent, action)
                    try:
                        onboarding_controller(
                            tenantID=self.tenant_id,
                            userID=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            data=data
                        )

                        print("data --- handle_agent-3-- ", data, agent, action)
                    except Exception as e:
                        print("error here , ", e, traceback.format_exc())

                elif action == "initiate_onboarding_v2":
                    print("data --- handle_agent-2initiate_onboarding_v2-- ",
                          data, agent, action)
                    try:
                        onboarding_controller(
                            tenantID=self.tenant_id,
                            userID=self.user_id,
                            llm=self.base_agent.llm,
                            model_opts=self.base_agent.modelOptions,
                            logInfo=self.log_info,
                            socketio=socketio,
                            client_id=self.client_id,
                            data=data,
                            initiate=True
                        )

                        print("data --- initiate_onboarding_v2-3-- ",
                              data, agent, action)
                    except Exception as e:
                        print("error here initiate_onboarding_v2 , ",
                              e, traceback.format_exc())

                if action == "fetch_states":
                    fetch_states(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        initiate=False
                    )

                if action == "discard_progress":
                    discrad_progress(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        initiate=False
                    )

                if action == "save_progress":
                    save_progress(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        initiate=False
                    )

            #done
            case  "business_template_agent":
                print("data --- handle_agent-1 business_template_agent-- ", data, agent, action)
                if action == "create_from_template":
                    print("data --- handle_agent-2-business_template_agent- ", self.session_id, data, agent, action)
                    business_case_from_template_create(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        steps_sender=steps_sender_class
                    )
                    
                if action == "retrigger_business_case":
                    print("data --- handle_agent-2-business_template_agent_retrigger_business_case- ", self.session_id, data, agent, action)
                    retrigger_financial(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        step_sender = steps_sender_class
                    )
                
            case  "roadmap_solution_agent":
                print("data --- handle_agent-1 roadmap_solution_agent-- ", data, agent, action)
                if action == "create":
                    print("data --- handle_agent-2-roadmap_solution_agent- ", self.session_id, data, agent, action)
                    solution_from_template_create(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        steps_sender=steps_sender_class
                    )
                  
                  
            case "integration_agent":
                if action == "cron_run_for_tenant":
                    run_cron_for_tenants(
                        tenantID=self.tenant_id,
                        userID=self.user_id,
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data
                    )
                    
            case "potential_agent":
                if action == "upload_data":
                    self.potentialService.upload_potential_data(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        session_id = metadata.get("session_id"),
                        llm=self.base_agent.llm,
                        model_opts=self.base_agent.modelOptions,
                        logInfo=self.log_info,
                        socketio=socketio,
                        client_id=self.client_id,
                        data=data,
                        sender=steps_sender_class
                    )
                    
        appLogger.info({"event":f"{action}_done","data":metadata,"user_id":self.user_id,"tenant_id":self.tenant_id})
                  
            
       