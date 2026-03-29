from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ASK_CLARIFY_QUESTION
from src.trmeric_services.tango.functions.integrations.general.FollowUpQuestionFunction import ANSWER_FOLLOW_UP
# from src.trmeric_services.tango.functions.integrations.general.QueryTrmericDocsFunction import QUERY_TRMERIC_DOCS
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration


class GeneralIntegration(TangoIntegration):
    """
    This is the class for the general integration, where users are able to query the Trmeric Database for it's best practices and also just ask follow-ups, etc.
    
    This includes accessing our Trmeric Vector Searcher to query the best practices documents.
    """

    def __init__(self, userID: int, tenantID: int, metadata: dict):
        functions = [
            # QUERY_TRMERIC_DOCS, 
            ASK_CLARIFY_QUESTION, ANSWER_FOLLOW_UP]
        # We always want this integration to be enabled.
        super().__init__("Best Practices", functions, userID, tenantID, True)

    def initializeIntegration(self):
        """
        Initializes the integration with all the relevant informatioon and data.
        """
        pass