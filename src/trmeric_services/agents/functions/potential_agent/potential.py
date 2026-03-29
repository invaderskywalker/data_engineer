import json
import time
import traceback
from .utils import *
from .prompts import *
from datetime import datetime, timezone
from src.trmeric_utils.json_parser import *
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_api.logging.AppLogger import appLogger
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes
from src.trmeric_database.dao import ProjectsDao,TangoDao,TenantDao, FileDao
from src.trmeric_s3.s3 import S3Service
from .actions.upload_data import process_items_from_sheet
from src.trmeric_services.tango.sessions.InsertTangoData import TangoDataInserter




class Potential:
    def __init__(self):
        
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4.1",
            max_tokens=12000,
            temperature=0.1
        )
        
       
    def get_potential_metrics(self, resources, tenant_id, user_id, cache_days=10):
        """
        Get potential metrics for the provided resources grouped by skill mapping
        """
        # print("--debug get_potential_metrics_v2----------", tenant_id, user_id, len(resources))
        try:
            
            skill_group = group_resources_by_skills(resources)
            # print("---debug skill_group-----", skill_group)
            
            cached_insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=tenant_id, user_id=user_id, key=f"potential_skill_insights_{tenant_id}")
            if not cached_insights or (cached_insights and cached_insights[0]["created_date"] and
                (datetime.now(timezone.utc) - datetime.fromisoformat(cached_insights[0]["created_date"])).days > cache_days
            ):
                
                prompt = potentialSkillMappingPrompt(skill_group)
                # print("--debug portfolioInsightsPrompt------", prompt.formatAsString())
                response = self.llm.run(prompt, self.modelOptions, 'potential::skill_insights', logInDb={'tenant_id': tenant_id, 'user_id': user_id})
                skill_insights = extract_json_after_llm(response)
                
                TangoDao.upsertTangoState(
                    tenant_id=tenant_id, user_id=user_id, key=f"potential_skill_insights_{tenant_id}",
                    value=json.dumps(skill_insights), session_id=None
                )
            else:
                appLogger.info({"event": "get_potential_metrics", "msg": "Insights already there", "tenant_id": tenant_id,"user_id":user_id})
                skill_insights = json.loads(cached_insights[0]["value"])
            
            result = {"skill_insights": skill_insights.get("insights", [])}
            return result
        
        except Exception as e:
            print("--deubg get_potential_metrics_v2----------",str(e))
            appLogger.error({"event":"get_potential_metrics","error":str(e),"tenant_id":tenant_id,"user_id":user_id,"traceback":traceback.format_exc()})
            return []
    
    
        
    def create_potential_insights(self,tenant_id, user_id,cache_days = 10):
        
        """Create potential insights based on the capacity resources after every 2days"""
        
        print("--deubug create_potential_insights----------",tenant_id,user_id)
        try:
            
            insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=tenant_id, user_id=user_id,key=f"potential_insights_{tenant_id}")
            if len(insights)==0 or (len(insights)>0 and insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(insights[0]["created_date"])).days > cache_days):
                
                print("--debug [Trigger Again] create_potential_insights----------")
                all_resources = ProjectsDao.getCapacityPlannerResources(tenant_id)
                internal_resources = [internal_resource for internal_resource in all_resources.get("internal_resources", []) if internal_resource["is_active"] == True][:100]
                external_resources = all_resources.get("external_resources", [])
                
                prompt = potentialInsightsPrompt(
                    internal_resources = json.dumps(internal_resources),
                    external_resources = json.dumps(external_resources)
                )
                # print("Potential Insights Prompt: ", prompt.formatAsString())
                response = self.llm.run(prompt, self.modelOptions,'potential::tango_insights',logInDb={'tenant_id':tenant_id,'user_id':user_id})
                insights = extract_json_after_llm(response)
                
                # print("\n\n\nPotential Insights Response: ", insights)
                result = insights.get("insights", [])
                TangoDao.upsertTangoState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    key=f"potential_insights_{tenant_id}",
                    value=json.dumps(result),
                    session_id=None
                )
                return result
            else:
                print("----------------")
                insights_val = insights[0]["value"]
                created_date = insights[0]["created_date"]
                print("--debug insight already there------", len(insights_val))
                
                appLogger.info({"event":"create_potential_insights","msg":"Insights already there","created_date":created_date,"tenant_id":tenant_id})
                return json.loads(insights_val)
            
        except Exception as e:
            appLogger.error(f"Error in create_potential_insights: {str(e)}",traceback.format_exc())
            return []
        
        
    # resource_id insights: oneliner insights
    def create_resource_insights(self,resource_id,resource_info,tenant_id,user_id,cache_days=5):
        """Create resource insights for potential profile page"""
        try:
            
            insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=tenant_id, user_id=user_id,key=f"resource_insights_{tenant_id}_{resource_id}")
            if len(insights)==0 or (len(insights)>0 and insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(insights[0]["created_date"])).days > cache_days):
            
                prompt = resourceInsightsPrompt(data = json.dumps(resource_info))
                response = self.llm.run(prompt, self.modelOptions,'potential::resource_insights',logInDb={'tenant_id':tenant_id,'user_id':user_id})
                insights = extract_json_after_llm(response)
                    
                # print("\n\n\Resource Insights Response: ", insights)
                result = insights.get("insights", [])
                
                TangoDao.upsertTangoState(
                    tenant_id=tenant_id,user_id=user_id,
                    key=f"resource_insights_{tenant_id}_{resource_id}",
                    value=json.dumps(result), 
                    session_id=None
                )
                return result
            
            else:
                insights_val = insights[0]["value"]
                created_date = insights[0]["created_date"]
                # print("--debug insight already there------", len(insights_val))
                
                appLogger.info({"event":"create_resource_insights","msg":"Insights present","created_date":created_date,"resource_id":resource_id,"tenant_id":tenant_id})
                return json.loads(insights_val)
            
        except Exception as e:
            appLogger.error({"event":"create_resource_insights","error":str(e),"traceback":traceback.format_exc()})
            return {}
    
    
    
    
    def upload_potential_data(
        self,
        tenantID=None,
        userID=None,
        sessionID=None,
        llm=None,
        model_opts=None,
        logInfo=None,
        socketio=None,
        client_id=None,
        **kwargs
    ):
        data = kwargs.get("data",{}) or {}
        sender = kwargs.get("steps_sender",None) or None
        print("--debug upload_potential_data----", tenantID,userID,sessionID, data)
        file_id = data.get("file_id")
        # session_id = data.get("session_id")
        
        tangoDataInserter = TangoDataInserter(user_id=userID,session_id=sessionID)

        print("--debug session_id----", sessionID)
        ## if not present.. inform
        if not file_id:
            sender.sendError(key="No files present",function="upload_potential_data")
            return
        
        key = f"POTENTIAL_DATA_SHEET_{tenantID}"
        files = FileDao.FilesUploadedInS3ForKey(key=key)
        template_file_id = None
        
        tangoDataInserter.addUserMessage(message="Uploading my potential data")
        # for f in files:
        f = files[0]
        print("\n\n--debug file----", f)
        sender.sendSteps(key = "Reading the file",val=False)
        
        if f.get("file_id") == file_id:
            template_file_id = f.get("s3_key")
        
        if not template_file_id:
            ### upload again.. was not ab le to read
            print("--error------------",template_file_id)
            sender.sendError(key="File not found",function="upload_potential_data")
            return
        
        file_content = S3Service().download_file_as_text(s3_key=template_file_id)
        if file_content is None:
            print(f"Failed to download or process file {template_file_id}")
            return None

        # Save the file content (assuming it's CSV)
        file_name = f"output_{file_id}.csv"
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"\n\nCSV file saved as output_{file_id}.csv")
            # return file_content
        except Exception as e:
            print(f"Error saving CSV file: {e}")
            return None
        
        sender.sendSteps(key = "Reading the file",val=True,delay=1)
        
        results=process_items_from_sheet(
                file_path=file_name,
                tenant_id=tenantID,
                user_id=userID,
                llm=llm,
                model_opts=model_opts,
                logInfo=logInfo,
                socketio=socketio,
                client_id=client_id,
                sender=sender
            )
        
        for result in results:
            if "error" in result:
                print(f"Error: {result['error']}")
                socketio.emit("agent_chat_user", f"Error in uploading data: {result['error']}. Please retry", room=client_id)
                
                socketio.emit("agent_chat_user", "<end>", room=client_id)
                socketio.emit("agent_chat_user", "<<end>>", room=client_id)
                return
            else:
                print(f"Processed/Inserted row {result.get('row')}: {result.get('status')}")
        
        socketio.sleep(seconds = 1)
        message = "✅ Resources are added successfully"
        tangoDataInserter.addTangoCode('')
        tangoDataInserter.addTangoData('')
        tangoDataInserter.addTangoResponse(message)

        socketio.emit("agent_chat_user", "✅ Resources are added successfully", room=client_id)
        
        socketio.emit("agent_chat_user", "<end>", room=client_id)
        socketio.emit("agent_chat_user", "<<end>>", room=client_id)
        return 
    
    
           
    
UPLOAD_POTENTIAL_DATA = AgentFunction(
    name="upload_potential_data",
    description="""
        This function is responsible uploading the resources data in capacity table for potential
    """,
    args=[],
    return_description="",
    function=Potential.upload_potential_data,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
) 
  
            
                
        
        
    # def get_potential_metrics(self, portfolios, tenantID, user_id, cache_days=1):
    #     """
    #     Get potential metrics for the provided portfolios by processing them and their projects concurrently
    #     """
    #     print("--debug get_potential_metrics_v2----------", tenant_id, user_id, len(portfolios))
    #     start = time.time()
    #     try:
    #         metrics = {"insights": [],"portfolio_resource_count": []}
            
    #         # Outer ThreadPoolExecutor to process portfolios concurrently
    #         with ThreadPoolExecutor(max_workers=min(5, len(portfolios))) as executor:
    #             futures = [executor.submit(self.process_portfolio, portfolio,tenant_id,user_id) for portfolio in portfolios]
    #             for future in as_completed(futures):
    #                 result = future.result()
    #                 if result:
    #                     metrics["portfolio_resource_count"].append({
    #                         "portfolio_id": result["portfolio_id"],
    #                         "portfolio_name": result["portfolio_name"],
    #                         "resource_count": result["resource_count"]
    #                     })
    #                     metrics["insights"].append({
    #                         "portfolio_title": result["portfolio_name"],
    #                         "resource_count": result["resource_count"],
    #                         "resources": result["resources"]
    #                     })
            
    #         total_resource_count = sum(portfolio["resource_count"] for portfolio in metrics["portfolio_resource_count"])
    #         print("\n\n\n--debug total_resource_count------ ", total_resource_count)
            
    #         all_resources = TenantDao.getResourceCapacityBasicInfo(tenant_id)
    #         unassigned_resources = len(all_resources) - total_resource_count
    #         # print("--debug resources---", all_resources," Unassigned resources: ", unassigned_resources)
            
    #         #Caching LLM insights
    #         cached_insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=tenant_id, user_id=user_id, key=f"potential_portfolio_insights_{tenant_id}")
            
    #         if not cached_insights or (
    #             cached_insights and cached_insights[0]["created_date"] and
    #             (datetime.now(timezone.utc) - datetime.fromisoformat(cached_insights[0]["created_date"])).days > cache_days
    #         ):
                
    #             insights = metrics.get("insights", [])
    #             insights.sort(key=lambda x: x["resource_count"], reverse=True)
                
    #             #Consider top3 for insights
    #             prompt = potentialPortfolioInsightsPrompt(insights[:3])
    #             # print("--debug portfolioInsightsPrompt------", prompt.formatAsString())
    #             response = self.llm.run(prompt, self.modelOptions, 'potential::portfolio_insights', logInDb={'tenant_id': tenant_id, 'user_id': user_id})
    #             portfolio_insights = extract_json_after_llm(response)
                
    #             TangoDao.insertTangoState(
    #                 tenant_id=tenant_id, user_id=user_id, key=f"potential_portfolio_insights_{tenant_id}",
    #                 value=json.dumps(portfolio_insights), session_id=None
    #             )
    #         else:
    #             appLogger.info({"event": "get_potential_metrics", "msg": "Insights already there", "tenant_id": tenant_id,"user_id":user_id})
    #             portfolio_insights = json.loads(cached_insights[0]["value"])
            
    #         result = {
    #             "total_resources": total_resource_count,
    #             "unassigned_resources": max(0,unassigned_resources),
    #             "portfolio_metrics": metrics["portfolio_resource_count"],
    #             "portfolio_insights": portfolio_insights.get("portfolio_insights", [])
    #         }
            
    #         elapsed_time = int(time.time() - start)
    #         print("\n\n\n-------debug get_potential_metrics_v2 time-------", elapsed_time)
    #         return result
        
    #     except Exception as e:
    #         print("--deubg get_potential_metrics_v2----------",str(e))
    #         appLogger.error({
    #             "event":"get_potential_metrics_v2","error":str(e),
    #             "tenant_id":tenant_id,"user_id":user_id,"traceback":traceback.format_exc()
    #         })
    #         return []
    
    
    
    
    
    
    
   
    # def process_project(self,project, portfolio_title):
    #     """
    #     Process a singleProject to fetch and count its team members.
    #     Returns:(resource_count, resources_dict)
    #     """
    #     try:
    #         id = project.get("project_id")
    #         title = project.get("project_title", "")
    #         project_resources = ProjectsDao.fetchProjectTeamDetails(project_id=id)
    #         team_members = project_resources.get("team_members", []) or []
            
    #         # print("--deubg process_project----", id,title,len(team_members))
    #         if not team_members:
    #             appLogger.info({"event": "process_project","msg":f"No resources found for project ID {id} in portfolio {portfolio_title}"})
    #             return 0, []
            
    #         # Filter active team members
    #         team_members = [member for member in team_members if member.get("name") and member.get("role") is not None]
    #         resource_count = len(team_members)
    #         # print("--debug resource in proj: ", id,"-",resource_count)
    #         resources = {"project_title": title, "team_members": team_members[:8]} if team_members else {}
    #         return resource_count, resources
        
    #     except Exception as e:
    #         appLogger.error({"event": "process_project","error":str(e),"project":project,"portfolio_title":portfolio_title,"traceback":traceback.format_exc()})
    #         return 0, []

    # def process_portfolio(self,portfolio,tenant_id,user_id):
    #     """
    #     Process a single portfolio, fetching its projects and their team members concurrently.
    #     """
    #     try:
    #         portfolio_id = portfolio.get("id")
    #         portfolio_title = portfolio.get("title")
    #         projects = PortfolioDao.fetchProjectIdsForPortfolio(portfolio_id)
            
    #         print("--deubg process_portfolio----", portfolio_id,portfolio_title,len(projects))
    #         resource_count = 0
    #         resources_list = []
            
    #         if len(projects) == 0:
    #             return {"portfolio_id":portfolio_id,"portfolio_name":portfolio_title,"resource_count":resource_count,"resources":[]}
            
    #         #Inner ThreadPoolExecutor to process projects concurrently
    #         with ThreadPoolExecutor(max_workers=min(8, len(projects))) as executor:
    #             futures = [executor.submit(self.process_project, project, portfolio_title) for project in projects]
    #             for future in as_completed(futures):
    #                 proj_resource_count, proj_resources = future.result()
    #                 resource_count += proj_resource_count
    #                 if proj_resources:
    #                     resources_list.append(proj_resources)
            
    #         appLogger.info({
    #             "event": "Potential Metrics","portfolio_id": portfolio_id,"portfolio_title": portfolio_title,
    #             "resource_count": resource_count,"tenant_id":tenant_id,"user_id":user_id
    #         })
            
    #         return {
    #             "portfolio_id": portfolio_id,
    #             "portfolio_name": portfolio_title,
    #             "resource_count": resource_count,
    #             "resources": resources_list[:10] 
    #         }
        
    #     except Exception as e:
    #         appLogger.error({"event":"process_portfolio","error":str(e),"tenant_id":tenant_id,"user_id":user_id,"traceback":traceback.format_exc()})
    #         return {}
        
        
        
        
    
    
    #Temp code:
    # def get_potential_metrics(self,portfolios, tenant_id, user_id,cache_days=1):
    #     """
    #         Get potential metrics for the provided portfolios. List the projects inside the portfolios.Then for each project, get the resources and their roles.
    #         Make a list of count of resources in each portfolio and its insights (based on availablility and other factors)
    #     """  
    #     print("--deubg get_potential_metrics----------",tenant_id,user_id,len(portfolios))      
    #     start = time.time()
    #     try:
    #         # {'id': 91, 'title': 'Customer Success', 'portfolio_leader_first_name': 'Debottam',#  'portfolio_leader_last_name': 'Datta','project_count': 12, 'roadmap_count': 89},
    #         metrics = {
    #             "insights": [],
    #             "portfolio_resource_count": []
    #         }
                
    #         for portfolio in portfolios:
                
    #             portfolio_id = portfolio.get("id")
    #             portfolio_title = portfolio.get("title")
    #             # portfolio_leader_first_name = portfolio.get("portfolio_leader_first_name", "")
    #             # portfolio_leader_last_name = portfolio.get("portfolio_leader_last_name", "")
                
    #             # print("--deubg portfolio_infos----",portfolio_id, portfolio_title, portfolio_leader_first_name, portfolio_leader_last_name)
    #             # Get resources, projects in the portfolio
    #             resource_count = 0
    #             projects = PortfolioDao.fetchProjectIdsForPortfolio(portfolio_id)
    #             # print(f"\n--debug projects in {portfolio_id}, {portfolio_title}----", len(projects))
                
    #             # Get resources in the projects
    #             resources = []
    #             for project in projects:
    #                 try:
    #                     id = project.get("project_id")
    #                     title = project.get("project_title", "")
    #                     project_resources = ProjectsDao.fetchProjectTeamDetails(project_id=id)
                        
    #                     #Query res:  'project_id': project_id,'pm': None,'team_members': []
    #                     # print(f"\n--debug project_resources in {id}----", len(project_resources.get("team_members", [])))
    #                     # project_manager = project_resources.get("pm", None) or None
    #                     team_members = project_resources.get("team_members", []) or []
    #                     if len(team_members)==0:
    #                         # print(f"No resources found for project ID {id} in portfolio {portfolio_title}")
    #                         appLogger.info(f"No resources found for project ID {id} in portfolio {portfolio_title}")
    #                         continue
                        
    #                     team_members = [member for member in team_members if member.get("name") != "" or None and member.get("role") is not None]  # Filter active members
    #                     resource_count += len(team_members)
                        
    #                     if len(team_members)>0:
    #                         resources.append({
    #                             "project_title": title,
    #                             # "project_manager": project_manager,
    #                             "team_members": team_members
    #                         })
                            
    #                 except Exception as e:
    #                     print(f"Error fetching resources for project{id} in portfolio {portfolio_title}: {str(e)}")
    #                     appLogger.error(f"Error fetching resources for project ID {id} in portfolio {portfolio_title}: {str(e)}", traceback.format_exc())
                
    #             appLogger.info({"event": "Potential Metrics", "portfolio_id": portfolio_id, "portfolio_title": portfolio_title, "resource_count": resource_count})
                
    #             metrics["portfolio_resource_count"].append({"portfolio_id": portfolio_id,"portfolio_name": portfolio_title,"resource_count":resource_count})
    #             metrics["insights"].append({"portfolio_title": portfolio_title, "resource_count": resource_count, "resources": resources[:8]})
                
                
    #         # with open("potential_metrics.json", "w") as f:
    #         #     json.dump(metrics, f, indent=4)
            
    #         total_resource_count = sum(portfolio["resource_count"] for portfolio in metrics["portfolio_resource_count"])
    #         print("\n\n\n--debug total_resource_count------ ", total_resource_count)
            
    #         cached_insights = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(tenant_id=tenant_id, user_id=user_id,key=f"potential_portfolio_insights_{tenant_id}")
    #         if len(cached_insights)==0 or (len(cached_insights)>0 and cached_insights[0]["created_date"] is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(cached_insights[0]["created_date"])).days > cache_days):
                
    #             insights = metrics.get("insights", []) or []
    #             prompt = potentialPortfolioInsightsPrompt(insights)
    #             # print("Potential Portfolio Insights Prompt: ", prompt.formatAsString())
                
    #             response = self.llm.run(prompt, self.modelOptions,'potential_portfolio_insights',logInDb={'tenant_id':tenant_id,'user_id':user_id})
    #             portfolio_insights = extract_json_after_llm(response)
                
    #             TangoDao.insertTangoState(tenant_id=tenant_id, user_id=user_id, key=f"potential_portfolio_insights_{tenant_id}", value=json.dumps(portfolio_insights), session_id=None)
            
    #         else:
    #             appLogger.info({"event":"get_potential_metrics","msg":"Insights already there","tenant_id":tenant_id})
    #             portfolio_insights = json.loads(cached_insights[0]["value"])
            
    #         result = {
    #             "total_resources": total_resource_count,
    #             "portfolio_metrics": metrics["portfolio_resource_count"],
    #             "portfolio_insights": portfolio_insights.get("portfolio_insights", [])
    #         }
    #         elapsed_time = int(time.time() - start)
    #         print("\n\n\n-------debug get_potential_metrics time-------", elapsed_time)
            
    #         # with open("potential_data.json", "w") as f:
    #         #     json.dump(result, f, indent=4)    
    #         return result
            
    #     except Exception as e:
    #         appLogger.error(f"Error in get_potential_metrics: {str(e)}",traceback.format_exc())
    #         return []

   

            
        