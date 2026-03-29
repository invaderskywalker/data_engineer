from src.trmeric_services.provider.prompts.Prompts import (
    getWinStrategyPrompt,
    getWinThemePrompt,
    # getBBDBTextEnhancementPrompt,
    get_quantum_assist_prompt
)
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
from src.trmeric_services.provider.prompts.Queries import fetchProviderInfoForOpportunity
from src.trmeric_database.Database import db_instance
from src.trmeric_database.models.Opportunity import Opportunity
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import CustomerDao,TangoDao
from src.trmeric_services.provider.quantum.utils import *


class ProviderService:
    def __init__(self):
        self.database = db_instance
        self.llm = ChatGPTClient()
        self.modelOptionsFast = ModelOptions(
            model="gpt-4o", max_tokens=4000, temperature=0.3
        )

    # def opportunityUpdate(
    #     self, opportunityId, keyWord, providerId
    # ):
    #     """
    #     This function is to fetch the win theme and win strategy by providers for an opportunity.

    #     Args:
    #     - opportunityId: The id of the opportunity
    #     - keyWord: The keyword to fetch
    #     - providerId: The id of the provider

    #     Returns:
    #     - The response for the given keyword
    #     """
    #     providerData = fetchProviderInfoForOpportunity(
    #         self.database, providerId)
    #     opportunityData = (
    #         Opportunity.select(Opportunity.description)
    #         .where(Opportunity.id == opportunityId)
    #         .get()
    #     )

    #     opportunityDescription = opportunityData.description
    #     opportunityWinTheme = opportunityData.win_theme
    #     prompt = None
    #     if keyWord == "win_theme":
    #         prompt = getWinThemePrompt(
    #             providerData=providerData,
    #             description=opportunityDescription,
    #             # outputFormat=None,
    #         )
    #     else:
    #         prompt = getWinStrategyPrompt(
    #             providerData=providerData,
    #             description=opportunityDescription,
    #             winTheme=opportunityWinTheme,
    #             # outputFormat=None,
    #         )
    #     modelOptions = ModelOptions(
    #         model="gpt-4-turbo", max_tokens=4000, temperature=0.3
    #     )

    #     response = self.llm.run(prompt, modelOptions, None)
    #     res2 = extract_json_after_llm(response)
    #     print("res2", res2)
    #     if keyWord == "win_theme":
    #         return res2["win_themes"]

    #     if keyWord == "win_stratergy":
    #         return res2["win_strategy"]

    #     return ""
    #     # return response.get(keyWord, "No response found")

    def opportunityUpdateCreate(
        self, opportunityId, keyWord, providerId, oppDesc, winTheme, win_strategy, external_customer_id, log_input=None
    ):
        # print("debug --opportunityUpdateCreate--", opportunityId, keyWord, providerId)
        providerData = fetchProviderInfoForOpportunity(
            self.database, providerId)

        customerData = "Not Provided"
        if external_customer_id > 0:
            customerData = CustomerDao.getCustomerDataForProvider(
                external_customer_id)

        print("debug customerData", customerData)

        opportunityDescription = oppDesc
        opportunityWinTheme = winTheme
        prompt = None
        if keyWord == "win_theme":
            prompt = getWinThemePrompt(
                providerData=providerData,
                description=opportunityDescription,
                winTheme=winTheme,
                customerData=customerData
            )
        else:
            prompt = getWinStrategyPrompt(
                providerData=providerData,
                description=opportunityDescription,
                winTheme=opportunityWinTheme,
                win_strategy=win_strategy,
                customerData=customerData
            )
        modelOptions = ModelOptions(
            model="gpt-4-turbo", max_tokens=4000, temperature=0.3
        )

        response = self.llm.run(
            prompt,
            modelOptions,
            'opportunityUpdateCreate_' + keyWord,
            logInDb=log_input
        )
        res2 = extract_json_after_llm(response)
        print("res2", res2)
        if keyWord == "win_theme":
            return res2["win_themes"]

        if keyWord == "win_stratergy":
            return res2["win_strategy"]

        return ""







    def quantumTangoAssist(self, text, category, logInfo):
        
        tenant_id = logInfo.get("tenant_id")
        user_id = logInfo.get("user_id")
        print("\n\n--debug enhanceQuantumData------", category, tenant_id, user_id,logInfo)
        
        quantum_context = TangoDao.fetchLatestTangoStateForKeyForTenantAndUser(
            tenant_id= tenant_id,
            user_id= user_id,
            key=f"quantum_input_context_{tenant_id}"
        )
        print("\n\n--debug [QTA] quantum_context", len(quantum_context))
        
        prompt = get_quantum_assist_prompt(category,text,quantum_context)
        # print("\n\n--debug [QTA] prompt", prompt.formatAsString())
        
        # if prompt_func is None:
        #     print(f"No prompt function defined for category: {category}")
        #     return {"error": "No prompt function defined", "category": category}
        # prompt = prompt_func()
        # prompt = getBBDBTextEnhancementPrompt(text, category,quantum_context)
        response = self.llm.run(
            prompt,
            self.modelOptionsFast,
            'quantumTangoAssist::update::section::' + category,
            logInDb=logInfo
        )
        res2 = extract_json_after_llm(response)
        # print("--debug res2", res2)
        result = self.parse_response(category,res2)
        
        return result
    
    
    
    def parse_response(self,category,result):
        
        
        if category == "service_catalog":
            tools_and_accelerators = result.get("tools_and_accelerators",[])
            if len(tools_and_accelerators)>0:
                for item in tools_and_accelerators:
                    item["type"] = map_tool_type(item["type"])
            # print("--debug res22222", tools_and_accelerators)
            return tools_and_accelerators
        
        
        return result
        
            