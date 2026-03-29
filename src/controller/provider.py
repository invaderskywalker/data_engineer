from flask import jsonify, request  # type: ignore
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.provider.ProviderService import ProviderService
import traceback


class ProviderController:
    def __init__(self):
        self.providerServices = ProviderService()

    def updateOpportunity(self):
        """
        This function is to fetch the win theme and win strategy by providers for an opportunity.

        Returns:
        - The response for the provided prompt
        """
        try:
            keyWord = request.json.get("key_word") or None
            opportunityId = request.json.get("opportunity_id") or None
            providerId = request.decoded.get("provider_id")
            external_customer_id = request.json.get(
                "external_customer_id") or -1

            create_new = request.json.get("create_new") or None
            description_while_create = request.json.get("opp_desc") or None
            win_theme_while_create = request.json.get("win_themes") or None
            win_strategy = request.json.get("win_strategy") or None

            response = self.providerServices.opportunityUpdateCreate(
                opportunityId=opportunityId,
                keyWord=keyWord,
                providerId=providerId,
                oppDesc=description_while_create,
                winTheme=win_theme_while_create,
                win_strategy=win_strategy,
                external_customer_id=external_customer_id,
                log_input=request.decoded
            )

            # if (create_new != ""):
            #     response = self.providerServices.opportunityUpdateCreate(
            #         opportunityId=opportunityId,
            #         keyWord=keyWord,
            #         providerId=providerId,
            #         oppDesc=description_while_create,
            #         winTheme=win_theme_while_create
            #     )
            # else:
            #     response = self.providerServices.opportunityUpdate(
            #         opportunityId=opportunityId,
            #         keyWord=keyWord,
            #         providerId=providerId,

            #     )

            return jsonify({"status": "success", "data": response}), 200

        except Exception as e:
            appLogger.error(
                {"event": "tango_provider_opportunity_update",
                    "error": str(e), "traceback": traceback.format_exc()}
            )
            return jsonify({"error": "Internal Server Error"}), 500


    def enhanceQuantumData(self):
        try:
            category = request.json.get("category", "") or ""
            if (category == ""):
                raise Exception("category missing")
            
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            rough_text = request.json.get("text", "") or ""
            
            log_info = {
                "tenant_id": tenant_id,
                "user_id": user_id
            }
            print("--debug [Self]", self,log_info)
            print("--debug text", rough_text)
                        
            
            response = self.providerServices.quantumTangoAssist(
                text=rough_text, 
                category=category, 
                logInfo=log_info
            )
            print("\n\n--debug response", response)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error(
                {"event": "bbdbTextEnhancement",
                    "error": str(e), "traceback": traceback.format_exc()}
            )
            return jsonify({"error": "Internal Server Error"}), 500
        
            