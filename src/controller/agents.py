from src.trmeric_services.tango.sessions.InsertTangoData import TangoDataInserter
from src.trmeric_services.tango.sessions.SessionManager import TangoSessionManager
from src.trmeric_services.tango.sessions.TangoConversationRetriever import TangoConversationRetriever
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.agents import PortfolioApiService
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_api.logging.TimingLogger import start_timer, stop_timer, log_event_start
from src.trmeric_api.logging.CreateLogResponse import createLogResponseBody
from flask import Flask, Response, jsonify, request
from src.trmeric_api.logging.LogResponseInfo import logResponseInfo
from src.trmeric_database.dao import PortfolioDao, ProjectsDao, TenantDao, TangoDao, RoadmapDao, FileDao
from src.trmeric_services.agents.session.session_manager import AgentSessionManager
from src.trmeric_services.agents.functions.onboarding.transition import retrieveLatestStates
from src.trmeric_api.logging.ProgramState import ProgramState
from src.trmeric_s3.s3 import S3Service
import time
import datetime
import threading
import traceback
import json
from src.trmeric_services.agents.precache import PortfolioReview
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents_v2.config import CONFIG_MAP
from src.trmeric_utils.regex import UUID_REGEX



class AgentsController:
    def __init__(self):
        self.portfolio_agent_service = PortfolioApiService()
        self.agent_session_manager = AgentSessionManager()

    def getPortfolioListWithBudget(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            # print("debug ---###--- ", portfolios)

            applicable_projects = ProjectsDao.fetchAllProjectsForTenant(tenant_id=tenant_id)

            portfolio_ids = [p['id'] for p in portfolios]  # Extracting portfolio ids
            spend_by_portfolio = self.portfolio_agent_service.fetch_actual_planned_spend_by_portfolio(tenant_id=tenant_id, applicable_projects=applicable_projects, portfolio_ids=portfolio_ids)

            data = spend_by_portfolio["graph_data"]
            # extra_data = spend_by_portfolio["extra_data"]
            # print("spend by portfolio --- ", spend_by_portfolio)
            combined_data = []

            # Fill data for portfolios present in spend data
            for i in range(len(data["categories"])):
                portfolio_data = {
                    "title": data["categories"][i],
                    "actual": data["actual"][i],
                    "planned": data["planned"][i],
                    "budget": data["planned"][i],
                    # "is_test_data": data.get
                    # "project_count": portfolio_info.get("project_count", 0) or 0,
                    # "roadmap_count": portfolio_info.get("roadmap_count", 0) or 0,
                }

                portfolio_info = next(
                    (portfolio for portfolio in portfolios if portfolio['title'] == portfolio_data["title"]), None)

                # print("debug portfolio info -- ", portfolio_info)
                if portfolio_info:
                    portfolio_data.update(
                        {
                            "id": portfolio_info["id"],
                            "portfolio_id": portfolio_info["id"],
                            "portfolio_leader_first_name": portfolio_info["portfolio_leader_first_name"],
                            "portfolio_leader_last_name": portfolio_info["portfolio_leader_last_name"],
                            "project_count": portfolio_info.get("project_count", 0) or 0,
                            "roadmap_count": portfolio_info.get("roadmap_count", 0) or 0,
                            "is_test_data": True if portfolio_info.get("is_test_data") == 'true' else False,
                        }
                    )

                combined_data.append(portfolio_data)
                
            # print("debug combined_data info -- ", combined_data)

            for portfolio in portfolios:
                if portfolio['title'] not in data["categories"]:
                    combined_data.append(
                        {
                            "title": portfolio["title"],
                            "actual": 0,
                            "planned": 0,
                            "budget": 0,
                            "is_test_data": True if portfolio.get("is_test_data") == "true"  else False,
                            "id": portfolio["id"],
                            "portfolio_id": portfolio["id"],
                            "portfolio_leader_first_name": portfolio["portfolio_leader_first_name"],
                            "portfolio_leader_last_name": portfolio["portfolio_leader_last_name"],
                            "project_count": portfolio.get("project_count", 0) or 0,
                            "roadmap_count": portfolio.get("roadmap_count", 0) or 0,
                        }
                    )

            return jsonify({"data": combined_data})

        except Exception as e:
            appLogger.error({"event": "getPortfoliosBudget",
                            "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": f"Internal Server Error + {str(e)}"}), 500

    def getProjectsReviewData(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            applicable_projects = ProjectsDao.FetchAvailableProject(tenant_id=tenant_id, user_id=user_id)
            archived_projects = ProjectsDao.FetchArchivedProjects(tenant_id=tenant_id)
            future_projects = RoadmapDao.fetchRoadmapDetailsV2FOrPortfolioReview(tenant_id)
            future_ids = [r["id"] for r in future_projects]
            data = PortfolioReview(tenant_id=tenant_id, user_id=user_id, init=False).fetchPortfolioReviewForProjects(applicable_projects, archived_projects, future_ids)
            return jsonify({"data": data})

        except Exception as e:
            appLogger.error({"event": "getProjectsReviewData",
                            "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": f"Internal Server Error + {str(e)}"}), 500

    def getAgentResponseForCategory(self, category):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            portfolio_ids = request.args.get("portfolio_ids")
            if portfolio_ids:
                # portfolio_ids = portfolio_ids.split(",")
                portfolio_ids = [id for id in portfolio_ids.split(",") if id]
        
            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            children_map = self.portfolio_agent_service.get_subportfolios_mapping(portfolios)
            # print("--debug getPortfolioListWithBudgetInHierarchy mapping-----", children_map)

            # all_portfolio_ids = portfolio_ids.copy()  # Start with root IDs
            # for portfolio_id in portfolio_ids:
            #     portfolio_id_int = int(portfolio_id)
            #     if portfolio_id_int in children_map:
            #         all_portfolio_ids.extend(str(child_id) for child_id in children_map[portfolio_id_int])
        
            
            all_portfolio_ids = set()

            def dfs(pid):
                all_portfolio_ids.add(pid)
                for child_id in children_map.get(pid, []):
                    if child_id not in all_portfolio_ids:
                        dfs(child_id)

            for pid in portfolio_ids:
                dfs(int(pid))  # ensure type matches children_map keys

            all_portfolio_ids = sorted(all_portfolio_ids)
                            
            
            
            portfolio_ids = sorted(list(dict.fromkeys(all_portfolio_ids)))
            # print("tenant id , category", tenant_id, category, portfolio_ids)

            applicable_projects = sorted(ProjectsDao.FetchAvailableProject(tenant_id=tenant_id, user_id=user_id))

            # print("getAgentResponseForCategory projects ", applicable_projects)
            
            result = {}
            start = time.time()
            # print("---portolio api_start-----", category)
            if category == "org_strategy":
                
                org_strategy_to_projects_mapping = self.portfolio_agent_service.get_projects_vs_org_strategy(project_ids=applicable_projects, portfolio_ids=portfolio_ids)
                org_strategy_to_projects_mapping_future = self.portfolio_agent_service.get_projects_vs_org_strategy_future(tenant_id=tenant_id, portfolio_ids=portfolio_ids)

                result = {
                    "org_strategy_to_projects_mapping": org_strategy_to_projects_mapping,
                    "org_strategy_to_projects_mapping_future": org_strategy_to_projects_mapping_future,
                }
                return jsonify({"data": result})
            
            elif category == "spend_by_category_ongoing":
                spend_by_category = self.portfolio_agent_service.fetchSpendBycategoryNew(
                    tenant_id, 
                    applicable_projects, 
                    portfolio_ids=portfolio_ids,
                    ongoing=True
                )
                result = {
                    "spend_by_category": spend_by_category,
                }
                return jsonify({"data": result})
            
            
            elif category == "spend_by_category":
                spend_by_category = self.portfolio_agent_service.fetchSpendBycategoryNew(
                    tenant_id, 
                    applicable_projects, 
                    portfolio_ids=portfolio_ids
                )
                result = {
                    "spend_by_category": spend_by_category,
                }
                return jsonify({"data": result})
            
            # spend_by_category = self.portfolio_agent_service.fetchSpendBycategory(
            #     tenant_id, applicable_projects, portfolio_ids=portfolio_ids)
            spend_vs_actual = self.portfolio_agent_service.fetchSpendVsActual(tenant_id, applicable_projects, portfolio_ids=portfolio_ids, ongoing=True)
            spend_by_portfolio = self.portfolio_agent_service.fetch_actual_planned_spend_by_portfolio(tenant_id, applicable_projects, portfolio_ids=portfolio_ids, ongoing=True)

            health_status_of_projects_by_portfolio = self.portfolio_agent_service.get_health_of_projects_status_by_portfolio(tenant_id, applicable_projects, portfolio_ids)
            health_status_comparison_this_week_to_previous = self.portfolio_agent_service.fetch_health_of_projects_last_week_and_current(tenant_id, applicable_projects, portfolio_ids)

            elapsed_time = time.time()-start
            print("---portolio api_end-----",category, elapsed_time)
            result = {
                "spend_vs_actual": spend_vs_actual,
                "spend_by_portfolio": spend_by_portfolio,
                "health_status_of_projects_by_portfolio": health_status_of_projects_by_portfolio,
                "health_status_comparison_this_week_to_previous": health_status_comparison_this_week_to_previous,
            }

            return jsonify({"data": result}), 200
        except Exception as e:
            appLogger.error({"event": "getAgentResponseForCategory","error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": f"Internal Server Error + {str(e)}"}), 500



    def getPortfolioAgentInsightsForCategory(self, category):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            portfolio_ids = request.args.get("portfolio_ids")
            if portfolio_ids:
                # portfolio_ids = portfolio_ids.split(",")
                portfolio_ids = [id for id in portfolio_ids.split(",") if id]
                
            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            children_map = self.portfolio_agent_service.get_subportfolios_mapping(portfolios)
            # print("--debug getPortfolioListWithBudgetInHierarchy mapping-----", children_map)

            # all_portfolio_ids = portfolio_ids.copy()  # Start with root IDs
            # for portfolio_id in portfolio_ids:
            #     portfolio_id_int = int(portfolio_id)
            #     if portfolio_id_int in children_map:
            #         all_portfolio_ids.extend(str(child_id) for child_id in children_map[portfolio_id_int])
            
            # # Remove duplicates while preserving order
            # portfolio_ids = list(dict.fromkeys(all_portfolio_ids))
            all_portfolio_ids = set()

            def dfs(pid):
                all_portfolio_ids.add(pid)
                for child_id in children_map.get(pid, []):
                    if child_id not in all_portfolio_ids:
                        dfs(child_id)

            for pid in portfolio_ids:
                dfs(int(pid))  # ensure type matches children_map keys

            all_portfolio_ids = sorted(all_portfolio_ids)
            portfolio_ids = sorted(list(dict.fromkeys(all_portfolio_ids)))

            print("tenant id , categoruy", tenant_id, user_id, category, portfolio_ids)

            applicable_projects = ProjectsDao.FetchAvailableProject(tenant_id=tenant_id, user_id=user_id)
            result = []
            if category == "spend_by_category":
                result = self.portfolio_agent_service.createSpendByCategoryInsight(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "spend_and_actual_by_portfolio":
                result = self.portfolio_agent_service.createActualAndPlannedByPortfolioInsight(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "spend_and_actual_month_wise":
                result = self.portfolio_agent_service.createPlannedVsActualInsight(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "overall_success_rate":
                result = self.portfolio_agent_service.createOverallSuccessRate(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "overall_success_rate_by_type":
                result = self.portfolio_agent_service.performance_by_type(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "health_status_by_portfolio":
                result = self.portfolio_agent_service.status_by_portfolio(tenant_id, user_id, portfolio_ids, applicable_projects)
            elif category == "impact_analysis":
                result = self.portfolio_agent_service.impact_analysis(tenant_id, user_id, portfolio_ids, applicable_projects)
            return jsonify({"data": result})
        except Exception as e:
            appLogger.error({"event": "getPortfolioAgentInsightsForCategory", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def getRecentSpendAnalysis(self):
        try:
            user_id = request.decoded.get("user_id")
            analysis_array = TangoDao.fetchTangoStates(user_id, 'SPEND_EVALUATION_FINISHED')
            if len(analysis_array) > 0:
                analysis = analysis_array[0]
                # print(analysis)
                return json.loads(analysis["value"])
            return jsonify({"error": "No recent spend analysis found"})
        except Exception as e:
            appLogger.error({"event": "getRecentSpendAnalysis", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    # def send_mail(self):
    #     try:
    #         user_mail = request.form.get("user_mail")
    #         # to_email = request.form.get("to")
    #         to_email = None
    #         subject = request.form.get("subject")
    #         body = request.form.get("body")
    #         file = request.files.get("file")

    #         # # Prepare email
    #         msg = Message(subject, sender=user_mail, recipients=[to_email])
    #         msg.body = body

    #         # Attach file if provided
    #         if file:
    #             filename = secure_filename(file.filename)
    #             msg.attach(filename, file.content_type, file.read())
    #         # mail.send(msg)
    #         mail.send(msg)
    #         return jsonify({"message": "Email sent successfully!"})

    #     except Exception as e:
    #         appLogger.error({
    #             "event": "error in sending mail",
    #             "error": e,
    #             "traceback": traceback.format_exc()
    #         })
    #         return jsonify({"error": str(e)}), 500

    def agents_chat(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            message = request.json.get("message")
            session_id = request.json.get("session_id")
            metadata = request.json.get("metadata", None)
            print("debug agents_chat --- ", tenant_id, user_id, message, metadata)

            agent_conversation = self.agent_session_manager.get_instance(session_id, tenant_id, user_id, metadata=metadata)

            startTime = time.time()
            responseInfo = createLogResponseBody()

            def generate_and_log(userMessage, metadata):
                stringData = ""
                for chunk in agent_conversation.handle_user_query(userMessage, metadata):
                    stringData += chunk
                    yield chunk
                threading.Thread(target=self.summarizeChats, args=(session_id, user_id, tenant_id)).start()
                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo, args=(responseInfo,)).start()

            return Response(
                generate_and_log(message, metadata),
                content_type="text/plain; charset=utf-8",
                status=200,
                headers={"Transfer-Encoding": "chunked"},
            )
        except Exception as e:
            appLogger.error({"event": "portfolio_agent_chat", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def summarizeChats(self, sessionID, userID, tenantID, summarizer_rate=2):
        try:
            query = (
                TangoConversationRetriever.select()
                .where((TangoConversationRetriever.session_id == sessionID + "combined") & (TangoConversationRetriever.created_by_id == userID))
                .order_by(TangoConversationRetriever.created_date.desc())
            )
            query = list(query.dicts())
        except Exception as e:
            query = []

        user_messages_count = 0
        query_filtered = []
        for row in query:
            if row["type"] == 1:
                user_messages_count += 1
            if user_messages_count <= (summarizer_rate + 1):
                if row["type"] == 1:
                    query_filtered.append(row["message"])
                if row["type"] == 3:
                    query_filtered.append(row["message"])
                if row["type"] == 5:
                    query_filtered.append(row["message"])

        summary = None
        found_summary = False
        for row in query:
            if row["type"] == 7:
                summary = row["message"]
                found_summary = True
            if found_summary:
                break

        print("--number of user messages", user_messages_count)
        if user_messages_count % summarizer_rate == 0 and user_messages_count > 0:
            print(b"---summarizing---")
            print(f'tenant_id: {tenantID}, user_id: {userID}')
            # create large data using all of the last 5 user message, tango message, tango code and tango data
            try:
                large_data = "\n".join([str(x) for x in query_filtered[::-1]])

                if not summary:
                    new_summary = SummarizerService(logInfo={"tenant_id": tenantID, "user_id": userID}).summarizer(
                        large_data=large_data,
                        message='''You will be provided a conversation between chatbot and user.
                                It will include user query, chatbot reply, chatbot generated code and chatbot retrieved data.
                                Your job is to summarize this conversation and only keep important points from the chat
                                and it will be used for the chatbot to make further decisions.
                                ''',
                        identifier='chat',
                    )

                else:
                    new_summary = SummarizerService(logInfo={"tenant_id": tenantID, "user_id": userID}).summarizer(
                        large_data=large_data,
                        message=f'''You will be provided a conversation between chatbot and user.
                                It will include user query, chatbot reply, chatbot generated code and chatbot retrieved data.
                                The previous conversation before the 2 most recent chats that you are being shown had already been summarized here: {summary}. 
                                Your job is to modify the currently existing summary just provided and include the new conversation that you are being shown.
                                Your job is to summarize this conversation and only keep important points from the chat
                                and it will be used for the chatbot to make further decisions.
                                ''',
                        identifier='chat',
                    )
            except Exception as e:
                import traceback

                print(traceback.format_exc())
                new_summary = None

            print("finished summarizing")
            summary = new_summary

            # use insert chat to add summary
            dataInsertionInstance = TangoDataInserter(userID, sessionID)
            dataInsertionInstance.addTangoSummary(summary)

    def onboarding_agents_chat_socket(self, tenant_id, user_id, message, session_id, metadata, socketio, client_id):
        try:
            # integrations = createIntegrations(
            #     fetchAvailableIntegrations(user_id), user_id, tenant_id, session_id)

            # print(integrations)

            agent_conversation = self.agent_session_manager.get_instance(
                session_id,
                tenant_id,
                user_id,
                metadata=metadata,
                # integrations=integrations,
                agent='onboarding_agent',
                socketio=socketio,
            )

            startTime = time.time()
            responseInfo = createLogResponseBody()

            def generate_and_log(userMessage):
                stringData = ""
                for chunk in agent_conversation.handle_user_query(userMessage):
                    stringData += chunk
                    socketio.emit("tango_chat_onboarding", chunk, room=client_id)
                socketio.emit("tango_chat_onboarding", "<end>", room=client_id)
                stateData = retrieveLatestStates(session_id, tenant_id)
                socketio.emit("tango_states_onboarding", stateData, room=client_id)
                socketio.emit("tango_states_onboarding", "<end>", room=client_id)
                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo, args=(responseInfo,)).start()

            return Response(
                generate_and_log(message),
                content_type="text/plain; charset=utf-8",
                status=200,
                headers={"Transfer-Encoding": "chunked"},
            )
        except Exception as e:
            appLogger.error({"event": "portfolio_agent_chat", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def agents_chat_socket(self, tenant_id, user_id, message, session_id, metadata, socketio, client_id):
        try:
            print("in agents_chat_socket 1")
            agent_conversation = self.agent_session_manager.get_instance(session_id, tenant_id, user_id, metadata=metadata, agent=None, socketio=socketio, client_id=client_id)
            print("in agents_chat_socket 2")

            startTime = time.time()
            responseInfo = createLogResponseBody()

            def generate_and_log(userMessage, metadata):
                stringData = ""
                for chunk in agent_conversation.handle_user_query(userMessage, metadata):
                    if chunk:
                        stringData += chunk
                        socketio.emit("tango_agent_response", chunk, room=client_id)

                socketio.emit("tango_agent_response", "<end>", room=client_id)
                socketio.emit("tango_agent_response", "<<end>>", room=client_id)
                responseInfo["duration"] = time.time() - startTime
                threading.Thread(target=logResponseInfo, args=(responseInfo,)).start()

            return Response(
                generate_and_log(message, metadata),
                content_type="text/plain; charset=utf-8",
                status=200,
                headers={"Transfer-Encoding": "chunked"},
            )
        except Exception as e:
            appLogger.error({"event": "agents_chat_socket", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error"}), 500

    def agents_project_retro_v2(self, project_id, key, tenant_id, user_id, message, session_id, metadata, socketio, client_id):
        try:
            print("--debug inside agents_project_retro_v2")

            startTime = time.time()
            responseInfo = createLogResponseBody()

            data = self.retro_service.runV2(
                project_id,
                tenant_id,
                user_id,
                key,
                socketio,
                client_id=client_id,
            )
            appLogger.info({"event": "retro::end", "key": key, "tenant_id": tenant_id, "project_id": project_id, "data": data})

        except Exception as e:
            appLogger.error({"event": "agents_project_retro", "error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": "Internal Server Error","message": str(e)}), 500

    def service_assurance_agent_comm(self, tenant_id, user_id, socketio, client_id, requestBody, session_id):
        agent_conversation = self.agent_session_manager.get_instance(session_id, tenant_id, user_id, metadata='', agent="service_assurance_agent", socketio=socketio, client_id=client_id)
        print(
            "debug -- service_assurance_agent_comm",
        )
        # if requestBody["key"] == 'update_done':
        # first update all projects
        # fetch from requestBody["data"]
        data = requestBody["data"]
        # socketio.emit
        # socketio.emit("agent_hide_status_update_ui", '', room=client_id)
        # socketio.emit("show_agent_bot", '', room=client_id)

        agent_conversation.handle_agent(agent="service_assurance_agent", action=requestBody["key"], data=data, socketio=socketio, client_id=client_id)

        # agent_conversation.add_agent_control_message(message="")
        # ## and pass to update status function
        # update
        #     pass
        # else:
        #     raise "Unknown"

    def general_agent_conv(self, tenant_id, user_id, socketio, client_id, requestBody, session_id):
        log_event_start("CONTROLLER_GENERAL_AGENT", tenant_id=tenant_id, user_id=user_id, session_id=session_id, agent=requestBody.get("agent", "unknown"))
        overall_timer = start_timer("general_agent_controller_execution", tenant_id=tenant_id, user_id=user_id, session_id=session_id)

        try:
            print("--debug requestBody main", requestBody)

            agent_name = requestBody.get("agent", None)
            if not agent_name:
                agent_name = requestBody.get("agent_name", None)
                
            action = requestBody.get("action")
            get_instance_timer = start_timer("get_agent_instance_controller", tenant_id=tenant_id, user_id=user_id, agent=agent_name)

            # session_id =requestBody.get("session_id")
            print("--debug session_id: ", session_id, action, agent_name)
            programstate= ProgramState.get_instance(user_id)
            programstate.set("current_agent", agent_name)
            programstate.set("session_id", session_id)
            print("set program state session_id to ", session_id)
            agent_conversation = self.agent_session_manager.get_instance(
                session_id,
                tenant_id,
                user_id,
                metadata='',
                agent=agent_name,
                socketio=socketio,
                client_id=client_id
            )

            stop_timer(get_instance_timer)

            message = requestBody.get("message")
            metadata = requestBody.get("metadata",{}) or None
            print("--debug requestBody action33", agent_name, action, metadata)

            if action:
                action_timer = start_timer("handle_agent_action_controller", action=action, agent=agent_name)

                data = requestBody.get("data")
                print("--debug requestBody action55",agent_name, action, "data ", data)
                
                # agent_conversation.handle_agent(
                #     agent=agent_name,
                #     action=action,
                #     data=data,
                #     socketio=socketio,
                #     client_id=client_id,
                #     metadata={"tenant_id": tenant_id, "user_id": user_id, "session_id": session_id, "request_body": requestBody},
                #     message=message,
                # )
                
                agent_conversation.handle_agent2(
                    agent=agent_name,
                    action=action,
                    data=data,
                    socketio=socketio,
                    client_id=client_id,
                    metadata={"tenant_id": tenant_id, "user_id": user_id, "session_id": session_id, "request_body": requestBody},
                    message=message
                )

                stop_timer(action_timer)
            
            else:
                data = json.dumps(requestBody.get("data"))

                lmessage = f"""
                    message: {message} 
                    Data: {data}
                """
                print("--debug lmessage", agent_name,  lmessage)
                text = ''
                
                if agent_name in ["trucible", "tango"]:
                    try:
                        print("--debug message", agent_name,  message)
                        agent_conversation.tangoDataInserter.addUserMessage(message=message)
                        agent_conversation.base_agent.conversation.add_user_message(message, datetime)
                        print("--debug message 2", agent_name)
                        agent_conversation.agents_v2_handler.run(agent_name, message)
                    except Exception as e:
                        print("error her e", e, traceback.format_exc())
                    return 
                    
                    

                if agent_name == 'value_realization_agent':
                    text = "Initiate Value Realization"

                    if len(agent_conversation.base_agent.conversation.conversation) == 0:
                        agent_conversation.tangoDataInserter.addUserMessage(message=text)
                        agent_conversation.base_agent.conversation.add_user_message(lmessage, datetime)
                    else:
                        agent_conversation.tangoDataInserter.addUserMessage(message=message)
                        agent_conversation.base_agent.conversation.add_user_message(message, datetime)

                    appLogger.info({"event": "general_agent_conv", "status": "value_realization_agent::start",
                                   "tenant_id": tenant_id, "user_id": user_id})

                else:
                    # agent_conversation.tangoDataInserter.addUserMessage(
                    #     message=message
                    # )
                    
                    
                    if agent_name == "analyst":
                        msg_handler = TangoDao.handleEditOrRegenerateMsg(user_id,session_id,metadata)
                        recent_queries = TangoDao.fetchTangoStatesForUserIdbyKey(
                            user_id=user_id,
                            key=f"query_history"
                        )
                        
                        
                        if len(agent_conversation.base_agent.conversation.conversation) == 0 and message == "" and len(recent_queries) == 0:
                            message += "Suggest the next best actions to get started with trmeric"
                        elif len(agent_conversation.base_agent.conversation.conversation) == 0 and message == "":
                            message += "Let's start with a playback and then suggest the next best actions."
                        else:
                            agent_conversation.tangoDataInserter.addUserMessage(
                                message=message
                            )
                            
                        print("debiug -0---- ", message)
                            
                        agent_conversation.base_agent.conversation.add_user_message(
                            message, 
                            datetime
                        )
                    else:
                        # agent_conversation.tangoDataInserter.addUserMessage(
                        #     message=message
                        # )
                        
                        if data:
                            if agent_name == "potential_agent":
                                agent_conversation.tangoDataInserter.addUserMessage(
                                    message=message
                                )
                            agent_conversation.base_agent.conversation.add_user_message(
                                lmessage, datetime)
                        else:
                            agent_conversation.base_agent.conversation.add_user_message(
                                message, datetime)

                if agent_name == 'onboarding_agent':
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        socketio.emit("tango_chat_onboarding", chunk, room=client_id)

                    socketio.emit("tango_chat_onboarding", "<end>", room=client_id)
                    socketio.emit("tango_chat_onboarding", "<<end>>", room=client_id)

                elif agent_name == "customer_success_agent":
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass

                elif agent_name == "integration_agent":
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass
                    
                # elif agent_name == "project_creation_agent":
                #     for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                #         pass

                elif agent_name == "analyst":
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass
                    
                elif agent_name == "quantum_agent":
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass
                
                elif agent_name == "potential_agent":
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass
                
                
                elif agent_name == "roadmap_agent":
                    agent_conversation.tangoDataInserter.addUserMessage(
                                    message=message
                                )
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        pass

                else:
                    for chunk in agent_conversation.execution_manager.execute_alpha(user_context=''):
                        # if agent_name != 'resource_planning_agent':
                        socketio.emit("agent_chat_user", chunk, room=client_id)

                    socketio.emit("agent_chat_user", "<end>", room=client_id)
                    socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        except Exception as e:
            print("error occured in general_agent_conv ", e)
            appLogger.error({"event": "general_agent_conv", "error": e, "traceback": traceback.format_exc()})
        finally:
            stop_timer(overall_timer)

    def handle_custom_agent_v1(self, tenant_id, user_id, socketio, client_id, requestBody, session_id):
        try:
            print("--debug requestBody", requestBody)

            agent_name = requestBody.get("agent")
            action = requestBody.get("action")
            sendMini = requestBody.get("sendMini") or True
            agent_conversation = self.agent_session_manager.get_instance(session_id, tenant_id, user_id, metadata='', agent=agent_name, socketio=socketio, client_id=client_id)

            message = requestBody.get("message")
            data = json.dumps(requestBody.get("data"))

            agent_conversation.base_agent.conversation.add_user_message(message, datetime)
            agent_conversation.tangoDataInserter.addUserMessage(message=message)
            agent_conversation.agents_v1_handler.execute(agent_name, '', sendMini)
            threading.Thread(target=self.summarizeChats, args=(session_id, user_id, tenant_id)).start()
        except Exception as e:
            print("error occured in handle_custom_agent_v1 ", e)
            appLogger.error({
                "event": "handle_custom_agent_v1",
                "error": e,
                "traceback": traceback.format_exc()
            })


    def fetchFileUploadedInAgent(self):
        tenant_id = request.decoded.get("tenant_id")
        user_id = request.decoded.get("user_id")
        
        agent_name = request.args.get("agent_name")
        roadmap_id = request.args.get("roadmap_id")

        # Optional: handle missing param
        if not agent_name:
            return {"error": "agent_name query param is required"}, 400
        
        agent_name = agent_name.strip().lower()
        AGENTS = [
            "trucible",
            "tango",
            "roadmap_solution_agent"
        ]
        if agent_name not in AGENTS:
            return {"error": "invalid agent_name"}, 400
        
        _type = agent_name.upper()
        if agent_name == "roadmap_solution_agent":
            _type = f"solution_template_{tenant_id}_{roadmap_id}".upper()
            
        files = FileDao.FileUploadedInType(_type=_type, user_id=user_id)
        for f in files:
            f["url"] = S3Service().generate_presigned_url(f["s3_key"])
            
        return {
            "status": "success",
            "data": files
        }


    def fetchStateFromAgent(self):
        user_id = request.decoded.get("user_id")
        tenant_id = request.decoded.get("tenant_id")
        state = request.args.get("state") or 'tango_ppt_structure'
        session_id = request.args.get("session_id")
                
        if session_id and not UUID_REGEX.match(session_id):
            return {"error": "invalid session_id"}, 400
        
        
        if '_auditlog' in state:
            result = TangoDao.fetchTangoStatesTenant(
                tenant_id=tenant_id,
                key=state,
                _limit=1
            )
        else:
            result = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(
                session_id=session_id,
                user_id=user_id,
                key=state
            )
        res = {}
        if result:
            res = extract_json_after_llm(result[0]['value'])
            
        return {
            "status": "success",
            "data": res
        }
        
    def fetchScheduleAgentChatFull(self):
        user_id = request.decoded.get("user_id")
        tenant_id = request.decoded.get("tenant_id")
        session_id = request.args.get("session_id")
                
        if session_id and not UUID_REGEX.match(session_id):
            return {"error": "invalid session_id"}, 400
        
        scheduled = {}
        schedules = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
            session_id=session_id,
            user_id=user_id, 
            key="roadmap_agent_schedule_created"
        )
        if (schedules and len(schedules) > 0):
            scheduled = json.loads(schedules[0].get("value"))
          
        return {
            "status": "success",
            "data": {
                "scheduled": scheduled
            }
        }
    
            
    def getPortfolioListWithBudgetInHierarchy(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
            # print("debug ---###--- ", portfolios)
            
            applicable_projects = ProjectsDao.fetchAllProjectsForTenant(tenant_id=tenant_id)

            portfolio_ids = [p['id'] for p in portfolios]  # Extracting portfolio ids
            spend_by_portfolio = self.portfolio_agent_service.fetch_actual_planned_spend_by_portfolio(tenant_id=tenant_id, applicable_projects=applicable_projects, portfolio_ids=portfolio_ids)

            data = spend_by_portfolio["graph_data"]
            # extra_data = spend_by_portfolio["extra_data"]
            # print("spend by portfolio --- ", spend_by_portfolio)
            combined_data = []

            # Fill data for portfolios present in spend data
            for i in range(len(data["categories"])):
                portfolio_data = {
                    "title": data["categories"][i],
                    "actual": data["actual"][i],
                    "planned": data["planned"][i],
                    "budget": data["planned"][i],
                    # "project_count": portfolio_info.get("project_count", 0) or 0,
                    # "roadmap_count": portfolio_info.get("roadmap_count", 0) or 0,
                }

                portfolio_info = next(
                    (portfolio for portfolio in portfolios if portfolio['title'] == portfolio_data["title"]), None)

                # print("debug portfolio info -- ", portfolio_info)
                if portfolio_info:
                    portfolio_data.update(
                        {
                            "id": portfolio_info["id"],
                            "portfolio_id": portfolio_info["id"],
                            "portfolio_leader_first_name": portfolio_info["portfolio_leader_first_name"],
                            "portfolio_leader_last_name": portfolio_info["portfolio_leader_last_name"],
                            "project_count": portfolio_info.get("project_count", 0) or 0,
                            "roadmap_count": portfolio_info.get("roadmap_count", 0) or 0,
                            "parent_id": portfolio_info.get("parent_id"),
                        }
                    )

                combined_data.append(portfolio_data)
                
            # print("debug combined_data info -- ", combined_data)

            for portfolio in portfolios:
                if portfolio['title'] not in data["categories"]:
                    combined_data.append(
                        {
                            "title": portfolio["title"],
                            "actual": 0,
                            "planned": 0,
                            "budget": 0,
                            "id": portfolio["id"],
                            "portfolio_id": portfolio["id"],
                            "portfolio_leader_first_name": portfolio["portfolio_leader_first_name"],
                            "portfolio_leader_last_name": portfolio["portfolio_leader_last_name"],
                            "project_count": portfolio.get("project_count", 0) or 0,
                            "roadmap_count": portfolio.get("roadmap_count", 0) or 0,
                            "parent_id": portfolio["parent_id"],
                        }
                    )
              
            # print("&***")      
            # print(json.dumps(portfolios, indent= 2))

            # print("&***")      
            # print(json.dumps(combined_data, indent= 2))


            # Build hierarchy
            children_map = self.portfolio_agent_service.get_subportfolios_mapping(portfolios)
            # print("--debug getPortfolioListWithBudgetInHierarchy mapping-----", children_map)
            
            id_to_node = {p['id']: p.copy() for p in combined_data}
            # Build set of IDs that are children of some other portfolio
            child_ids = {p['id'] for p in combined_data if p['parent_id'] in id_to_node}

            # Roots are portfolios that are NOT a child of any other portfolio in combined_data
            roots = [node for node_id, node in id_to_node.items() if node_id not in child_ids]

            # roots = [id_to_node[p['id']] for p in combined_data]
            # print("\n\n---debug Root portfolios-------", roots)
        
            tree = [
                self.portfolio_agent_service.build_hierarchy(
                        node_id=root['id'],
                        children_map = children_map,
                        id_to_node = id_to_node,
                        level = 1,
                        params = [{"key":"expanded","value":True},{"key":"selected","value":True}]
                    )
                    for root in roots
                ]
            # tree.sort(key=lambda x: x['title'])

            def aggregate(node):
                if not node['children']:
                    return
                for child in node['children']:
                    aggregate(child)
                    node['actual'] += child['actual']
                    node['planned'] += child['planned']
                    node['budget'] += child['budget']
                    node['project_count'] += child['project_count']
                    node['roadmap_count'] += child['roadmap_count']

            for root in tree:
                aggregate(root)

            # with open("portfolio1.json","w") as f:
            #     json.dump(tree,f, indent=4)
            
            return jsonify({"data": tree}), 200

        except Exception as e:
            appLogger.error({"event": "getPortfoliosBudget","error": e, "traceback": traceback.format_exc()})
            return jsonify({"error": f"Internal Server Error + {str(e)}"}), 500
        
        
        
    

                
    
        
#     {
#     id: 'supply-chain',
#     title: 'Supply Chain & Manufacturing',
#     icon: '🚚',
#     level: 1,
#     expanded: false,
#     actual: 0,
#     budget: 724540,
#     planned: 724540,
#     portfolio_id: 155,
#     portfolio_leader_first_name: '',
#     portfolio_leader_last_name: '',
#     project_count: 1,
#     roadmap_count: 15,
#     selected: false,
#     children: [
#       {
#         id: 'procurement',
#         title: 'Procurement Systems',
#         icon: '🛒',
#         level: 2,
#         actual: 0,
#         budget: 724540,
#         planned: 724540,
#         portfolio_id: 155,
#         portfolio_leader_first_name: '',
#         portfolio_leader_last_name: '',
#         project_count: 1,
#         roadmap_count: 15,
#         selected: true,
#         children: [],
#       }
#     ],
#   },