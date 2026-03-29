import sys
import os
import datetime
from src.trmeric_services.tango.types.TangoConversation import TangoConversation
from src.trmeric_database.Database import db_instance, TrmericDatabase
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_services.tango.functions.FunctionCaller import TangoFunctionCaller
from src.trmeric_services.tango.prompts.TangoResponse import getTangoPrompt
from src.trmeric_services.tango.sessions.InsertTangoData import TangoDataInserter
from src.trmeric_services.tango.sessions.TangoConversationRetriever import (
    TangoConversationRetriever,
)
from src.trmeric_services.tango.utils.InitializeIntegrations import createIntegrations
from src.trmeric_services.tango.utils.FetchAvailableIntegrations import fetchAvailableIntegrations
from src.trmeric_utils.PresidioAnonymizer import PresidioAnonymizer
from src.trmeric_utils.fuzzySearch import *
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_database.dao.roadmap import RoadmapDao
from fuzzywuzzy import fuzz
import re
import uuid
from src.trmeric_api.types.TabularData import TabularData
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
import traceback
import time 
from src.trmeric_services.tango.prompts.CodeGenerationTemplate import getCodeGenerationPrompt
from src.trmeric_utils.anonymizer import Anonymizer
from src.trmeric_ml.llm.Types import ChatCompletion



class Tango:

    def __init__(self, user_id: str, tenant_id: int, session_id: str, agent = None):
        """_summary_

        Args:
            user_id (str): _description_
            tenant_id (int): _description_
            session_id (str): _description_
        """
        self.user_id = user_id
        self.session_id = session_id
        self.conversation = TangoConversation(
            user_id, session_id, tenant_id=tenant_id)
        self.database = db_instance
        self.tangoDataInserter = TangoDataInserter(
            self.user_id, self.session_id)
        self.tenant_id = tenant_id
        self.llm = ChatGPTClient(self.user_id, self.tenant_id)
        
        self.anonymizer = Anonymizer(tenant_id=tenant_id, user_id=user_id)

        self.availableIntegrations = fetchAvailableIntegrations(self.user_id)
        print (self.availableIntegrations.getColumnNames())
        if agent == 'spend':
            self.availableIntegrations.filterColumns('integration_type', lambda x: x == 'trmeric' or x == 'jira')
        print (self.availableIntegrations.getRows())
        self.eligibleProjects = ProjectsDao.FetchAvailableProject(
            self.tenant_id, self.user_id)

        self.initializeUserIntegrations()

        ###
        self.fetchAndHashProjectNames()
        self.fetchAndHashRoadmapNames()
        self.fetchAndHashTeamMemberNames()
        ######

        self.functionCaller = TangoFunctionCaller(
            self.llm, self.tangoDataInserter, self.integrations
        )
        self.modelOptions = ModelOptions(
            model="gpt-4-turbo", max_tokens=4096, temperature=0.3
        )
        self.modelOptionsFast = ModelOptions(
            model="gpt-4o", max_tokens=4096, temperature=0.3
        )
        self.modelOptionsBig = ModelOptions(
            model="gpt-4.1", max_tokens=30000, temperature=0.1
        )
        self.pmInfo = ProjectsDao.FetchProjectManagerInfoForProjects(
            self.eligibleProjects)
        self.userMessageAnonymizer = PresidioAnonymizer()
        self.personNamesInQuery = []
        self.PII_TEXT_FOR_LLM = ""
        self.hashed_name_to_real_name = {}
        self.reverse_hashed_name_to_real_name = {}
        self.hashed_team_member_names_mapping = {}

    def fetchAndHashProjectNames(self):
        projectNames = ProjectsDao.FetchProjectNamesForIds(
            self.eligibleProjects)

        counter = 1
        temp = {}
        for project_data in projectNames:
            project_actual_name = project_data['project_title']
            hashed_name = f"PROJECT_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = project_actual_name
        # print("--fetchAndHashProjectNames---", temp)
        self.hashed_project_names_mapping = temp

    def fetchAndHashTeamMemberNames(self):
        teamMemberNames = ProjectsDao.FetchTeamMemberNames(
            self.eligibleProjects)

        counter = 1
        temp = {}
        for name in teamMemberNames:
            project_actual_name = name['member_name']
            hashed_name = f"TEAM_MEMBER_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = project_actual_name
        # print("--fetchAndHashTeamMemberNames---", temp)
        self.hashed_team_member_names_mapping = temp

    def fetchAndHashRoadmapNames(self):
        roadmapNames = RoadmapDao.FetchRoadmapNames(self.tenant_id)

        counter = 1
        temp = {}
        for roadmap_data in roadmapNames:
            roadmap_actual_name = roadmap_data['title']
            hashed_name = f"ROADMAP_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = roadmap_actual_name
        self.hashed_roadmap_names_mapping = temp

    def updateTextWithHashRoadmapNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_roadmap_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_roadmap_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def updateTextWithHashProjectNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_project_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_project_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def updateTextWithHashedTeamMemberNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_team_member_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_team_member_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def deanonymizeUserDataWithHashProjectNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_project_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text

    def deanonymizeUserDataWithHashRoadmapNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_roadmap_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text

    def deanonymizeTextWithTeamMemberNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_roadmap_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text

    def detectPII(self, text):
        # anonymizedText = self.userMessageAnonymizer.anonymizeString(text)
        # return anonymizedText
        return text
    
    def detectPersonInQuery(self):
        is_person = False
        for k, v in self.userMessageAnonymizer.deanonymizer_mapping.items():
            is_person = "PERSON" in k
            if "PERSON" in k:
                for key, value in v.items():
                    # print("--", key, value)
                    if ("PERSON" in key):
                        self.personNamesInQuery.append(value)
        return is_person

    def detectAndAnonymizePM(self):
        # pmInfo = ProjectsDao.FetchProjectManagerInfoForProjects(self.eligibleProjects)
        grouped_data = {}
        for item in self.pmInfo:
            pm_id = item['project_manager_id']
            first_name = item['first_name']
            last_name = item['last_name']

            if pm_id not in grouped_data:
                grouped_data[pm_id] = {
                    'name': first_name + " " + last_name,
                    'projects': []
                }
            grouped_data[pm_id]['projects'].append({
                "project_id": item['project_id'],
                "project_name": item['project_name'],
            })

        pm_mappings_list = []

        counter = 1
        for pm_id, pm_data in grouped_data.items():
            pm_name = pm_data['name']
            hashed_name = "PM_HASH_" + str(counter)
            pm_mapping = {
                'project_manager_id': pm_id,
                'project_manager_name': hashed_name,
                'projects': pm_data['projects']
            }
            pm_mappings_list.append(pm_mapping)
            counter = counter + 1
            self.hashed_name_to_real_name[hashed_name] = pm_name

        reverse_hashed_name_to_real_name = {
            v: k for k, v in self.hashed_name_to_real_name.items()}
        # print("**debug*** --- ", grouped_data, self.reverse_hashed_name_to_real_name)

        self.PII_TEXT_FOR_LLM += f"""
            List of all Project Manager names and their associated projects.
            Use this info if required for answering if required
            {pm_mappings_list}
            
            If you are responding with these project manager ids. also respond with their names 
        """

        if self.detectPersonInQuery():
            # find the pms of eligibble projects
            # and fetch their names
            # and compare with the current name in message
            # finding pms ---

            personNames1 = [name.lower() for name in self.personNamesInQuery]
            for pm_id, pm_data in grouped_data.items():
                pm_name = pm_data['name'].lower()
                for person_name in personNames1:
                    # print("debug -100--", person_name, pm_name)
                    score = fuzz.partial_ratio(pm_name, person_name)
                    if score >= 80:
                        # if person_name in pm_name:
                        print(f"Match found: {person_name} is in {pm_name}")
                        # if match found
                        self.PII_TEXT_FOR_LLM += f""" 
                            For data privacy reasons, we do not want to share any PII data to LLM.
                            So, we have scrubbed the name of Project Manager in user message 
                            So, we are supplying the project ids of the PM which the user is asking about
                            The project ids are: {pm_data["projects"]}
                            and the project manager id is : {pm_id}
                            and project manager name is : {reverse_hashed_name_to_real_name.get(pm_data['name'], "")}
                        """

    def chat(self, message: str, sessionId, systemMessage = None, socketio=None, client_id=None):
        start_time = time.time()
        randomId = uuid.uuid4()
        anonymizedText = self.detectPII(message)
        appLogger.info({
            "event": "tango_chat_v3",
            "step": "1",
            "user_orginal_message": message,
            "anonymized_message": anonymizedText,
            "randomId": randomId,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "sessionId": sessionId
        })
        # self.detectAndAnonymizePM()

        anonymizedText = self.updateTextWithHashProjectNames(anonymizedText)
        anonymizedText = fuzzy_match_and_replace_with_actual(
            text=anonymizedText, actual_names=self.hashed_project_names_mapping.values())
        anonymizedText = self.updateTextWithHashProjectNames(anonymizedText)
        
        # anonymizedText= self.anonymizer.anonymize(anonymizedText)

        self.PII_TEXT_FOR_LLM = self.updateTextWithHashProjectNames(
            self.PII_TEXT_FOR_LLM)
        
        # self.PII_TEXT_FOR_LLM = self.anonymizer.anonymize(self.PII_TEXT_FOR_LLM)

        self.conversation.add_user_message(anonymizedText, datetime)
        self.tangoDataInserter.addUserMessage(message)

        # appLogger.info({
        #     "event": "tango_chat_v3",
        #     "step": "2",
        #     "user_orginal_message": message,
        #     "anonymized_message": anonymizedText,
        #     "randomId": randomId,
        #     "tenant_id": self.tenant_id,
        #     "user_id": self.user_id,
        #     "sessionId": sessionId
        # })
        appLogger.info({
            "event": "tango_chat_v3_time_debug",
            "step": "1",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "execution_time": time.time() - start_time
        })
        test_buffer = ''
        try:
            prompt = self.functionCaller.chatPrompt(self.conversation, self.PII_TEXT_FOR_LLM)
            system = self.updateTextWithHashProjectNames(prompt.system)
            user = self.updateTextWithHashProjectNames(prompt.user)
            # system = self.anonymizer.anonymize(text=prompt.system)
            # user = self.anonymizer.anonymize(text=prompt.user)
            copyPrompt = ChatCompletion(system=system, prev=prompt.prev, user=user)
            # (self.conversation, self.integrations, self.PII_TEXT_FOR_LLM, systemMessage)

            # prompt = self.updateTextWithHashProjectNames(prompt.formatAsString())
            # print("debug --- prompt -- ", copyPrompt.formatAsString())
            
            llmResponse = self.llm.run(
                copyPrompt,
                self.modelOptions,
                function_name="tango_level_1",
                logInDb={
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                }
            )
            print("response of first llm -- ", llmResponse)
        
            thought, generatedData = self.functionCaller.handleQuery(
                self.conversation,
                self.database,
                self.user_id,
                self.tenant_id,
                self.PII_TEXT_FOR_LLM,
                message,
                systemMessage,
                None,
                llmResponse,
                socketio=socketio, 
                client_id=client_id
            )
            
            appLogger.info({
                "event": "tango_chat_v3_time_debug",
                "step": "2",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "execution_time": time.time() - start_time
            })
            # print("debug --- generatedData ", generatedData)

            generatedData = self.updateTextWithHashProjectNames(generatedData)
            generatedData = self.updateTextWithHashRoadmapNames(generatedData)
            generatedData = self.updateTextWithHashedTeamMemberNames(generatedData)
            
            # print("debug --- generatedData ", generatedData)


            # print("debug --- anonymisedConversation ", anonymisedConversation)

            anonymisedConversation = self.updateTextWithHashProjectNames(
                self.conversation.format_conversation())
            anonymisedConversation = self.updateTextWithHashRoadmapNames(
                anonymisedConversation)
            anonymisedConversation = self.updateTextWithHashedTeamMemberNames(
                anonymisedConversation)
            anonymisedConversation = self.conversation.format_conversation()
            
            # print("debug --- anonymisedConversation ", anonymisedConversation)

            
            # print("generated data -- ", generatedData)
            
            # generatedData = self.anonymizer.anonymize(str(generatedData))
            # anonymisedConversation = self.anonymizer.anonymize(self.conversation.format_conversation())
            
            
            
            

            appLogger.info({
                "event": "tango_chat_v3_intermediate",
                "step": "3",
                "user_orginal_message": message,
                "anonymized_message": anonymizedText,
                "thought": thought,
                "randomId": randomId,
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "sessionId": sessionId
            })


            # generatedData = SummarizerService({
            #     "tenant_id": self.tenant_id,
            #     "user_id": self.user_id
            # }).summarizer(
            #     generatedData, 
            #     f"""
            #     This data is obtained by using the thought: {thought}.
            #     Extract all key points and a general understanding of this data and always keep the thought in mind.
            #     """,
            #     "chat"
            # )

            appLogger.info({
                "event": "tango_chat_v3_time_debug",
                "step": "3",
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "execution_time": time.time() - start_time
            })

            print("data generated --- ")
            print(thought)
            print("end data generated ----")

            # print("summ data generated --- ")
            # print(generatedData)
            # print("summ end data generated----")
            
            if (self.tenant_id == '73' or self.tenant_id == '102' or self.tenant_id == '625'):
                self.PII_TEXT_FOR_LLM += f"""
                    All cash related data output in INR (₹). 
                    Never use USD for them. Because these are Indian Tenants.
                """
                
            # print("extra text  --- ",self.tenant_id, self.tenant_id == 681, self.tenant_id == '681',  self.PII_TEXT_FOR_LLM)

            # self.tangoDataInserter.addTangoData(generatedData)
            self.tangoDataInserter.addTangoData("")
            prompt = getTangoPrompt(
                anonymisedConversation, generatedData, thought, self.PII_TEXT_FOR_LLM)

            # print("output prompt -- ", prompt.formatAsString())
            buffer = ''

            for chunk in self.llm.runWithStreaming(
                prompt,
                self.modelOptionsBig,
                "tango_level_2",
                logInDb={
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                }
            ):
                pattern = r'PM_HASH_\d+'
                delimiters = r'[ ,.!?]'
                max_buffer_size = 100
                buffer += chunk
                test_buffer += chunk
                while re.search(delimiters, buffer) or len(buffer) > max_buffer_size:
                    delimiter_match = re.search(delimiters, buffer)
                    if delimiter_match:
                        end_pos = delimiter_match.end()
                        segment = buffer[:end_pos]
                        buffer = buffer[end_pos:]
                    else:
                        segment = buffer
                        buffer = ""

                    result = re.sub(pattern, lambda match: self.hashed_name_to_real_name.get(
                        match.group(0), match.group(0)), segment)
                    result = self.deanonymizeUserDataWithHashProjectNames(result)
                    result = self.deanonymizeUserDataWithHashRoadmapNames(result)
                    result = self.deanonymizeTextWithTeamMemberNames(result)
                    
                    # result = self.anonymizer.deanonymize(segment)
                    yield result
            if buffer:
                result = re.sub(pattern, lambda match: self.hashed_name_to_real_name.get(
                    match.group(0), match.group(0)), buffer)
                yield result
        except Exception as e:
            appLogger.error({
                "event": "tango_chat_v3_error",
                "step": "5",
                "user_orginal_message": message,
                "anonymized_message": anonymizedText,
                "response": test_buffer,
                "randomId": randomId,
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "error": e,
                "sessionId": sessionId,
                "traceback": traceback.format_exc()
            })
            if "context_length_exceeded" in str(e):
                test_buffer = "Context is too large. Please ask specific question. We are working to solve this issue"
            else:
                test_buffer = "Apologies!! some unknown error occured in processing this query.  "

            yield test_buffer

        # print("answer ------")
        # print(test_buffer)
        # appLogger.info({
        #     "event": "tango_chat_v3_response",
        #     "step": "4",
        #     "user_orginal_message": message,
        #     "anonymized_message": anonymizedText,
        #     "response": test_buffer,
        #     "randomId": randomId,
        #     "tenant_id": self.tenant_id,
        #     "user_id": self.user_id,
        # })

    def initializeUserIntegrations(self):
        self.integrations = createIntegrations(
            self.availableIntegrations, self.user_id, self.tenant_id,self.session_id)

    def runPinnedChat(self, message: str, beginId: int, endId: int, sessionId):
        chats = TangoConversationRetriever.fetchChatBetweenIndeces(
            beginId, endId)

        randomId = uuid.uuid4()
        anonymizedText = self.detectPII(message)
        appLogger.info({
            "event": "tango_chat_pin",
            "step": "1",
            "user_orginal_message": message,
            "anonymized_message": anonymizedText,
            "randomId": randomId,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "sessionId": sessionId
        })
        # self.detectAndAnonymizePM()

        anonymizedText = self.updateTextWithHashProjectNames(anonymizedText)
        anonymizedText = fuzzy_match_and_replace_with_actual(
            text=anonymizedText, actual_names=self.hashed_project_names_mapping.values())
        anonymizedText = self.updateTextWithHashProjectNames(anonymizedText)

        self.PII_TEXT_FOR_LLM = self.updateTextWithHashProjectNames(
            self.PII_TEXT_FOR_LLM)

        self.conversation.add_user_message(anonymizedText, datetime)
        self.tangoDataInserter.addUserMessage(message)

        appLogger.info({
            "event": "tango_chat_pin",
            "step": "2",
            "user_orginal_message": message,
            "anonymized_message": anonymizedText,
            "randomId": randomId,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "sessionId": sessionId
        })

        generatedCode = None
        for chat in chats:
            if chat["type"] == 5:
                generatedCode = chat["message"]

        test_buffer = ''
        try:

            thought, generatedData = self.functionCaller.handlePinboardQuery(
                generatedCode,
                self.conversation,
                self.database,
                self.user_id,
                self.tenant_id,
                # self.eligibleProjects,
                self.PII_TEXT_FOR_LLM
            )

            generatedData = self.updateTextWithHashProjectNames(generatedData)
            generatedData = self.updateTextWithHashRoadmapNames(generatedData)
            generatedData = self.updateTextWithHashedTeamMemberNames(
                generatedData)

            anonymisedConversation = self.updateTextWithHashProjectNames(
                self.conversation.format_conversation())
            anonymisedConversation = self.updateTextWithHashRoadmapNames(
                anonymisedConversation)
            anonymisedConversation = self.updateTextWithHashedTeamMemberNames(
                anonymisedConversation)

            appLogger.info({
                "event": "tango_chat_pin_intermediate",
                "step": "3",
                "user_orginal_message": message,
                "anonymized_message": anonymizedText,
                "thought": thought,
                "randomId": randomId,
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "sessionId": sessionId
            })
            
            # generatedData = SummarizerService({
            #     "tenant_id": self.tenant_id,
            #     "user_id": self.user_id
            # }).summarizer(
            #     generatedData, 
            #     f"""
            #     This data is obtained by using the thought: {thought}.
            #     Extract all key points and a general understanding of this data and always keep the thought in mind.
            #     """,
            #     "chat"
            # )
            
            if (self.tenant_id == '73' or self.tenant_id == '102' or self.tenant_id == '625'):
                self.PII_TEXT_FOR_LLM += f"""
                    All cash related data output in INR (₹). 
                    Never use USD for them. Because these are Indian Tenants.
                """
            
            print("data generated pin board --- ")
            print(thought)
            print("end data generated pin board----")

            prompt = getTangoPrompt(
                anonymisedConversation, generatedData, thought, self.PII_TEXT_FOR_LLM)

            buffer = ''
            test_buffer = ''
            for chunk in self.llm.runWithStreaming(
                prompt,
                self.modelOptionsBig,
                "tango_level_2",
                logInDb={
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id
                }
            ):
                pattern = r'PM_HASH_\d+'
                delimiters = r'[ ,.!?]'
                max_buffer_size = 100
                buffer += chunk
                test_buffer += chunk
                while re.search(delimiters, buffer) or len(buffer) > max_buffer_size:
                    delimiter_match = re.search(delimiters, buffer)
                    if delimiter_match:
                        end_pos = delimiter_match.end()
                        segment = buffer[:end_pos]
                        buffer = buffer[end_pos:]
                    else:
                        segment = buffer
                        buffer = ""

                    result = re.sub(pattern, lambda match: self.hashed_name_to_real_name.get(
                        match.group(0), match.group(0)), segment)
                    result = self.deanonymizeUserDataWithHashProjectNames(
                        result)
                    result = self.deanonymizeUserDataWithHashRoadmapNames(
                        result)
                    yield result
            if buffer:
                result = re.sub(pattern, lambda match: self.hashed_name_to_real_name.get(
                    match.group(0), match.group(0)), buffer)
                yield result
        except Exception as e:
            appLogger.error({
                "event": "tango_chat_pin_error",
                "step": "5",
                "user_orginal_message": message,
                "anonymized_message": anonymizedText,
                "response": test_buffer,
                "randomId": randomId,
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "error": e,
                "sessionId": sessionId,
                "traceback": traceback.format_exc()
            })
            if "context_length_exceeded" in str(e):
                test_buffer = "Context is too large. Please ask specific question. We are working to solve this issue"
            else:
                test_buffer = "Apologies!! some unknown error occured in processing this query.  "
            print(e)
            yield test_buffer

        # print("answer ------")
        # print(test_buffer)

        # appLogger.info({
        #     "event": "tango_chat_v3_response",
        #     "step": "4",
        #     "user_orginal_message": message,
        #     "anonymized_message": anonymizedText,
        #     "response": test_buffer,
        #     "randomId": randomId,
        #     "tenant_id": self.tenant_id,
        #     "user_id": self.user_id,
        # })

    def setConversation(self, conversation: TangoConversation):
        self.conversation = conversation
