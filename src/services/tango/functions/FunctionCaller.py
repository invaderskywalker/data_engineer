from src.ml.llm.models import OpenAIClient
import re
from src.ml.llm.Types import ModelOptions
from src.services.tango.types.TangoConversation import TangoConversation
from src.database.Database import TrmericDatabase
from src.services.tango.functions.Executor import Executor
from src.services.tango.prompts.CodeGenerationTemplate import (
    getCodeGenerationPrompt,
)
from src.services.tango.sessions.InsertTangoData import TangoDataInserter
from src.services.tango.types.TangoIntegration import TangoIntegration


class TangoFunctionCaller:
    """_summary_"""

    def __init__(
        self,
        llm: OpenAIClient,
        dataInserter: TangoDataInserter,
        integrations: list[TangoIntegration]
    ):
        self.llm = llm
        self.modelOptions = ModelOptions(
            model="gpt-4o", max_tokens=1500, temperature=0.5 #changed model but not in use
        )
        self.tangoDataInserter = dataInserter
        self.integrations = integrations
        self.eligibleFunctions = []
        for integration in integrations:
            self.eligibleFunctions.extend(integration.functions)

    def chatPrompt(self,
        conversation: TangoConversation,
        PII_TEXT_FOR_LLM,
        systemMessage = None,
    ):
        prompt = getCodeGenerationPrompt(conversation, self.integrations, PII_TEXT_FOR_LLM, systemMessage)
        return prompt
        
    def handleQuery(
        self,
        conversation: TangoConversation,
        database: TrmericDatabase,
        userId,
        tenantId,
        PII_TEXT_FOR_LLM,
        actual_user_message,
        systemMessage = None,
        userMessage = None,
        llmResponse=None,
        socketio=None, 
        client_id=None
    ):
        # prompt = getCodeGenerationPrompt(
        #     conversation, self.integrations, PII_TEXT_FOR_LLM, systemMessage)
        # print("debug --- prompt -- ", prompt.formatAsString())
        # print("------------------")
        # # later change to debug
        # appLogger.info({
        #     "function": "LLM_1_PROMPT",
        #     "prompt": prompt.formatAsString()
        # })
        # llmResponse = self.llm.run(
        #     prompt,
        #     self.modelOptions,
        #     function_name="tango_level_1",
        #     logInDb={
        #         "tenant_id": tenantId,
        #         "user_id": userId
        #     }
        # )
        # print("response of first llm -- ", llmResponse)
        thought = self.parseModelThought(llmResponse)
        response = self.parseModelResponse(llmResponse)

        # if ("autonomous_create_project" in thought):
        #     print("rerunning tango since autonomous_create_project detected")
        #     conversation.conversation.pop()
        #     conversation.add_user_message(actual_user_message, datetime)
        #     prompt = getCodeGenerationPrompt(
        #         conversation, self.integrations, PII_TEXT_FOR_LLM)
        #     llmResponse = self.llm.run(prompt, self.modelOptions, None)
        #     response = self.parseModelResponse(llmResponse)

        self.tangoDataInserter.addTangoCode(llmResponse)

        executor = Executor(
            conversation, 
            database, 
            self.llm, 
            userId, 
            tenantId, 
            self.integrations, 
            self.eligibleFunctions, 
            actual_user_message=actual_user_message, 
            socketio=socketio, 
            client_id=client_id
        )
        execution = executor.execute(response)
        # self.tangoDataInserter.addTangoData(execution)
        return thought, execution

    def handlePinboardQuery(
        self,
        generatedCode,
        conversation: TangoConversation,
        database: TrmericDatabase,
        userId,
        tenantId,
        # eligibleProjects,
        PII_TEXT_FOR_LLM
    ):
        self.tangoDataInserter.addTangoCode(generatedCode)
        response = self.parseModelResponse(generatedCode)

        thought = self.parseModelThought(generatedCode)
        executor = Executor(
            conversation, database, self.llm, userId, tenantId, self.integrations, self.eligibleFunctions
        )
        execution = executor.execute(response)
        self.tangoDataInserter.addTangoData(execution)
        return thought, execution

    def parseModelThought(self, response):
        pattern = r"Thought: (.*?)\n```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        else:

            return None

    def parseModelResponse(self, response):
        pattern = r"```[a-zA-Z0-9]*\n(.*?)\n```"
        match = re.search(pattern, response, re.DOTALL)

        if match:
            return match.group(1)
        else:
            return None

    def formatData(self, execution: list):
        formattedString = ""
        for data in execution:
            formattedString += f"\n\n{data}"
        return formattedString
