
from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.api.types.TabularData import TabularData
from requests.auth import HTTPBasicAuth
from src.trmeric_services.tango.functions.Types import ApiMetadata
from src.trmeric_integrations.Slack.Api import SlackAPI
from src.trmeric_services.tango.functions.integrations.slack.GetSlackData import (
    READ_CHANNEL_HISTORY, READ_DM_HISTORY, SEND_CHANNEL_MESSAGE, SEND_DM, LIST_CHANNELS)



class SlackIntegration(TangoIntegration):
    """
    This is a class to represent the integration of Slack.
    """

    def __init__(self, userID: int, tenantID: int, metadata: ApiMetadata = None):
        super().__init__("slack", [SEND_DM, READ_DM_HISTORY, SEND_CHANNEL_MESSAGE, READ_CHANNEL_HISTORY, LIST_CHANNELS], userID, tenantID, True)
        self.api = SlackAPI(userID, tenantID, metadata)

    def initializeIntegration(self):
        """
        Initializes the integration with Slack.
        """
        users = self.api.list_all_users()
        user_description = "These are the users that you can DM or reach out to"
        
        channels = self.api.list_channels()
        channel_description = "These are the channels that you can access and read through"
        
        dms = self.api.list_direct_messages()
        dm_description = "These are the direct messages that you can access and read through"
        
        if users is not None:
            userData = TangoIntegrationData(users, user_description)
            self.addIntegrationData(userData)
        
        if channels is not None:
            channelData = TangoIntegrationData(channels, channel_description)
            self.addIntegrationData(channelData)
        
        if dms is not None:
            dmData = TangoIntegrationData(dms, dm_description)
            self.addIntegrationData(dmData)