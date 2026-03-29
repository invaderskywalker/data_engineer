import os
import re
import json
import time
import datetime
import traceback
from openai import OpenAI
from abc import ABC, abstractmethod
from src.trmeric_utils.json_parser import *
from src.trmeric_ws import SocketStepsSender
from src.trmeric_ml.llm.Types import ModelOptions,ModelOptions2
from src.trmeric_services.chat_service.utils import *
from src.trmeric_services.chat_service.Prompts import *
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import TangoDao,RoadmapDao
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.helper.file_analyser import FileAnalyzer
from src.trmeric_services.journal.Activity import detailed_activity, activity, record


class ChatService(ABC):
    @abstractmethod
    def start_session(self, chat, **kwargs:dict):
        pass

    @abstractmethod
    def generate_next_question(self, chat, **kwargs:dict):
        pass
    
    @abstractmethod
    def fetchPrefilledRoadmapOrProjectData(self, chat, socketio, client_id, step_sender, **kwargs:dict):
        pass

class Chat_V2:
    def __init__(self,request_info,chat_type,session_id="",temperature=0,service: ChatService=None):
        
        self.messages = []
        self.dbMessages = []
        self.service = service
        self.chat_type = chat_type
        self.session_id = session_id
        self.user_id = request_info.get("user_id")
        self.tenant_id = request_info.get("tenant_id")
        self.is_provider = request_info.get("tenant_type", False)

        self.userName = request_info.get("username")
        self.name = request_info.get("first_name", "") or "Welcome"

        self.provider_info = {}
        if self.is_provider == "provider":
            self.provider_info["provider_id"] = request_info.get("provider_id", "")
            self.provider_info["provider_name"] = request_info.get("provider_name", "")

        self.temperature = temperature
        self.openai = OpenAI(api_key=os.getenv("OPENAI_KEY"))
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        self.log_info = {"tenant_id": self.tenant_id, "user_id": self.user_id}

        self.role = None
        self.roadmapInfo = None
        self.roadmapContext = None
        self.all_portfolios = []
        self.user_portfolios = []
        self.context = self.update_persona_data()
        # save_as_json(self.context, f"debug_chat_context_{self.tenant_id}_{self.user_id}.json")

        self.modelOptions = ModelOptions(model="gpt-4.1", max_tokens=12000, temperature=0)
        self.modelOptions1 = ModelOptions(model="gpt-4o", max_tokens=4096, temperature=0.2)
        self.modelOptions2 = ModelOptions(model="gpt-4.1", max_tokens=8000, temperature=0.1)
        self.modelOptions3 = ModelOptions2(model="gpt-5.1",max_output_tokens=6000, temperature=0.1)

        self.file_analyzer = FileAnalyzer(tenant_id = self.tenant_id)
        if chat_type == 1:
            self._fetchRoadmapDataIfRoadmapAttached()
            

    def update_persona_data(self):
        try:
            if self.provider_info:
                ##provider context
                return self.provider_info

            return get_consolidated_persona_context_utils(
                tenant_id = self.tenant_id,
                user_id = self.user_id,
                chat_type = self.chat_type
            )

        except Exception as e:
            appLogger.error({"event":"update_persona_data", "error":str(e), "traceback": traceback.format_exc() })
            return {"tenant_info": "", "persona": "", "org_alignment": ""}
        
    
    def start_session(self, **kwargs:dict):
        systemMessage = self.service.start_session(self,**kwargs)
        userMessage = {
            "role": "user",
            "content": "Please start asking from the first question.",
            "username": self.userName,
            "time": datetime.datetime.now().isoformat(),
        }
        if self.chat_type == 6:
            userMessage = {
                "role": "user",
                "content": "Please start asking from the first question. Important: 1. Careful with mermaid structure, it should be parsable properly and heirarcical structure not plain, should have a root",
                "username": self.userName,
                "time": datetime.datetime.now().isoformat(),
            }

        self.dbMessages.append(systemMessage)
        self.dbMessages.append(userMessage)

    def generate_next_question(self, key=None, **kwargs:dict):
        print("debug---generateNextQuestion--", self.chat_type, len(self.getConvMessagesArr()), "is roadmapInfo None: ", self.roadmapInfo)
        try:
            messages = self.getConvMessagesArr()
            last_message = ""
            if len(messages) > 0:
                last_message = messages[len(messages) - 1]
            if len(messages) == 2 and self.roadmapInfo is None:
                return self.service.generate_next_question(self,**kwargs)
            
            # print("debug---generateNextQuestion-- 2", self.chat_type, len(self.getConvMessagesArr()))
            # response = self.openai.chat.completions.create(
            #     model=self.modelOptions.model,
            #     messages=self.getConvMessagesArr(),
            #     max_tokens=self.modelOptions.max_tokens,
            #     temperature=self.modelOptions.temperature,
            #     stream=False,
            # )
            response = self.openai.chat.completions.create(
                model=self.modelOptions3.model,
                messages=self.getConvMessagesArr(),
                max_completion_tokens=self.modelOptions3.max_output_tokens,
                temperature=self.modelOptions3.temperature,
                stream=False,
            )
            try:
                TangoDao.createEntryInStats(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    function_name="generateNextQuestion_" + str(self.chat_type),
                    model_name=response.model,
                    total_tokens=response.usage.total_tokens,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            except Exception as e:
                appLogger.error({"event": "error_in_storing_stats", "error": e, "traceback": traceback.format_exc()})
            output = response.choices[0].message.content
            output_json = extract_json_after_llm(output)

            if key:
                output_json["key"] = key

            if "agent_tip" in output_json:
                output_json["hint"] = output_json["agent_tip"]
                output_json.pop("agent_tip", None)
            return json.dumps(output_json)
        except Exception as e:
            print(f"error occurred in generateNextQuestion: {e}", traceback.format_exc())
            raise e

    def fetchPrefilledRoadmapOrProjectData(self, socketio, client_id,**kwargs):
        # print("--debug in fetchPrefilledRoadmapOrProjectData---33 ", kwargs)
        agent = agentNameMapping(self.chat_type)
        entity = agent.split('_')[0]
        step_sender = SocketStepsSender(agent_name=agent, socketio=socketio, client_id=client_id)
        print("--debug qna fetched--- for ", entity, "\nAgent: ", agent)


        TangoDao.insertTangoState(tenant_id=self.tenant_id, user_id=self.user_id,
            key=f"create_{entity}_conv", 
            value= f""""{entity} Creation Conv:\n {json.dumps(self.fetchOnlyQna())}""",
            session_id=self.session_id
        )
        appLogger.info({"event":"fetchPrefilledRoadmapOrProjectData","status": "qna_fetched","tenant_id":self.tenant_id,"user_id":self.user_id,"chatType":entity})

        if self.chat_type in CANVAS_CHATTYPES:
            return self.service.fetchPrefilledRoadmapOrProjectData(self, socketio, client_id, step_sender=step_sender,**kwargs)
        else:
            messages = self.service.fetchPrefilledRoadmapOrProjectData(self, socketio, client_id, step_sender=step_sender)

            response = self.openai.chat.completions.create(
                model=self.modelOptions3.model,
                messages=messages,
                max_completion_tokens=self.modelOptions3.max_output_tokens,
                temperature=self.modelOptions3.temperature,
                stream=False,
            )
            try:
                TangoDao.createEntryInStats(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    function_name=f"fetchPrefilledRoadmapOrProjectData_{entity}",
                    model_name=response.model,
                    total_tokens=response.usage.total_tokens,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            except Exception as e:
                appLogger.error({"event": "error_in_storing_stats","error": str(e),"traceback": traceback.format_exc()})

            output = response.choices[0].message.content
            return extract_json_after_llm(output,step_sender=step_sender)


    def _fetchRoadmapDataIfRoadmapAttached(self):
        info = RoadmapDao.getRoadmapIdToAttachedProject(self.session_id)
        roadmap_id = info[0]["roadmap_id"] if len(info) > 0 else None
        print("--------------------_fetchRoadmapDataIfRoadmapAttached-----------------------", roadmap_id, info)

        if roadmap_id is None:
            pass
        else:
            roadmapInfo = RoadmapDao.getRoadmapInfo(self.session_id)[0]
            KPIsOfRoadmap = RoadmapDao.getKpiOfRoadmapInfo(self.session_id)
            data = {
                "description": roadmapInfo["description"],
                "objectives": roadmapInfo["objectives"],
                "kpis": KPIsOfRoadmap,
                "start_date": roadmapInfo["start_date"],
                "end_date": roadmapInfo["end_date"],
                "budget": str(roadmapInfo["budget"]) + " USD",
            }
            self.roadmapInfo = data

    def fetchOnlyQna(self):
        try:
            result = []
            for i, msg in enumerate(self.getConvMessagesArr(True)):
                if i == 0 or i == 1:
                    continue
                temp = {}
                if msg["role"] == "assistant":
                    try:
                        response_json = json.loads(msg["content"])
                    except Exception as e:
                        try:
                            response_json = json.loads(extract_json_data(msg["content"]))
                        except Exception as e1:
                            extract_json = extract_json_v2(msg["content"])
                            # print("--debug extract_json", extract_json)
                            response_json = json.loads(extract_json)
                    temp["question"] = response_json["question"]
                    result.append(temp)
                else:
                    temp["answer"] = msg["content"]
                    result.append(temp)
            return result
        except Exception as e:
            raise e

    def parseMessagesAndReturn(self, only_question=False):
        try:
            answer_pattern = re.compile(r"Important: Remeber to read through all the info.*", re.DOTALL | re.IGNORECASE)
            result = []
            # print("\n\n--debug parseMessagesAndReturn--------", self.getConvMessagesArr())

            for i, msg in enumerate(self.getConvMessagesArr(True)):
                if i == 0 or i == 1:
                    continue
                if i % 2 == 0:
                    temp = {}
                    response_json = extract_json_after_llm(msg["content"])
                    # try:
                    #     response_json = json.loads(msg["content"])
                    # except Exception as e:
                    #     try:
                    #         response_json = extract_json_after_llm(msg["content"])
                    #     except Exception as e1:
                    #         try:
                    #             print("parseMessagesAndReturn error 2", e1, i, msg)
                    #             extract_json = extract_json_v2(msg["content"])
                    #             response_json = json.loads(extract_json)
                    #         except Exception as e2:
                    #             print("parseMessagesAndReturn error 2", e1)
                    #             try:
                    #                 extracted_json = extract_json_data_v2(msg["content"])
                    #                 response_json = json.loads(extracted_json)
                    #             except Exception as e3:
                    #                 print("parse error 3", e3)
                    if only_question:
                        temp["question"] = response_json["question"]
                    else:
                        temp["question"] = response_json
                        temp["question"]["id"] = i // 2 + 1
                        temp["answer"] = ""
                    result.append(temp)
                if i % 2 == 1:
                    temp = result[-1]
                    temp2 = re.sub(answer_pattern, "", msg["content"])
                    temp["answer"] = temp2
            return result
        except Exception as e:
            raise e

    def getConvMessagesArr(self, ignore_any_model_type=False):
        msgs = []
        for msg in self.dbMessages:
            msgs.append({"role": msg["role"], "content": msg["content"]})
        return msgs

    def getMessages(self):
        return json.dumps(self.dbMessages)

    def setMessagesFromDB(self, messages):
        self.dbMessages = messages

    def addUserMessage(self, content):
        userMessage = {
            "role": "user",
            "content": content,
            "username": self.userName,
            "time": datetime.datetime.now().isoformat(),
        }
        print("self.dbMessages addUserMessage", len(self.dbMessages))
        self.dbMessages.append(userMessage)

    def addAssistantMessage(self, content):
        systemMessage = {
            "role": "assistant",
            "content": content,
            "username": "Tango",
            "time": datetime.datetime.now().isoformat(),
        }
        self.dbMessages.append(systemMessage)


    def getConvUploadedFiles(self):
        # extract all the s3_keys of files from question
        files = []
        try:
            for i, msg in enumerate(self.getConvMessagesArr(True)):
                if i == 0 or i == 1:
                    continue
                temp = {}
                if msg["role"] == "assistant":
                    try:
                        response_json = json.loads(msg["content"])
                    except Exception as e:
                        try:
                            response_json = json.loads(extract_json_data(msg["content"]))
                        except Exception as e1:
                            extract_json = extract_json_v2(msg["content"])
                            # print("--debug extract_json", extract_json)
                            response_json = json.loads(extract_json)

                    if "key" in response_json:
                        temp["key"] = response_json["key"]
                        files.append(temp)
            return files
        except Exception as e:
            appLogger.error({"event": "getConvUploadedFiles", "error": str(e), "traceback": traceback.format_exc()})
            print("\n---error here getConvUploadedFiles-----", str(e))
            raise e
    
    @activity("discovery_session_create_brief")
    def createProjectBrief(self, companyName):
        record("description", "Generating project brief for a provider based on user's answers during the chat session.")
        record("user_id", self.user_id)
        company_name_hash = "COMPANY_NAME_HASH"
        qna = self.fetchOnlyQna()
        record("input_data", qna)
        if self.roadmapInfo is not None:
            messages = [
                {
                    "role": "user",
                    "content": createProjectBriefCreationPromptV4(
                        self.roadmapInfo, qna, company_name_hash
                    ),
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": createProjectBriefCreationPromptV3(qna, company_name_hash),
                }
            ]
        response = self.openai.chat.completions.create(
            model=self.modelOptions.model,
            messages=messages,
            max_tokens=self.modelOptions.max_tokens,
            temperature=self.modelOptions.temperature,
            stream=False,
        )
        try:
            TangoDao.createEntryInStats(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                function_name="createProjectBrief",
                model_name=response.model,
                total_tokens=response.usage.total_tokens,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens
            )
        except Exception as e:
            appLogger.error({
                "event": "error_in_storing_stats",
                "error": e,
                "traceback": traceback.format_exc()
            })
        output_ = response.choices[0].message.content
        output_ = output_.replace(company_name_hash, companyName)
        output = extract_json_after_llm(output_)
        response = {}
        parsedResult = []
        for key, value in output.items():
            temp = {}
            temp["title"] = key
            temp["value"] = value
            parsedResult.append(temp)
        response["project_brief"] = parsedResult
        return response
