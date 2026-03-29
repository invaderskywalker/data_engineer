from src.trmeric_integrations.Slack.Api import SlackAPI
from src.trmeric_services.tango.functions.Types import TangoFunction

def send_direct_message(api: SlackAPI, user_id: str, message: str):
    api.send_direct_message(user_id, message)
    return "Direct message has been sent. Check your Slack account."

def read_direct_message_history(api: SlackAPI, dm_channel_id: str):
    return str(api.read_direct_message_history(dm_channel_id))

def send_channel_message(api: SlackAPI, channel_id: str, message: str):
    api.send_channel_message(channel_id, message)
    return "Channel message has been sent. Check your Slack account."

def read_channel_history(api: SlackAPI, channel_id: str):
    return str(api.read_channel_history(channel_id))

def list_channels(api: SlackAPI):
    return api.channel_result.getColumn('channel_name')


SEND_DM = TangoFunction(
    name="send_slack_dm",
    description="Sends a direct message to a specific user on Slack",
    args=[
        {
            "name": "user_id",
            "description": "The Slack user ID to send the message to",
            "type": "str"
        },
        {
            "name": "message",
            "description": "The message to send to the user",
            "type": "str"
        }
    ],
    return_description="confirmation of direct message sent",
    func_type="slack",
    function=send_direct_message,
    integration="slack",
    active=True
)

READ_DM_HISTORY = TangoFunction(
    name="read_slack_dm_history",
    description="Retrieves the message history of a specific direct message channel",
    args=[
        {
            "name": "dm_channel_id",
            "description": "The Slack DM channel ID to read the history from",
            "type": "str"
        }
    ],
    return_description="confirmation of DM history retrieval",
    func_type="slack",
    function=read_direct_message_history,
    integration="slack"
)

SEND_CHANNEL_MESSAGE = TangoFunction(
    name="send_slack_channel_message",
    description="Sends a message to a specific channel on Slack",
    args=[
        {
            "name": "channel_id",
            "description": "The Slack channel ID to send the message to",
            "type": "str"
        },
        {
            "name": "message",
            "description": "The message to send to the channel",
            "type": "str"
        }
    ],
    return_description="confirmation of channel message sent",
    func_type="slack",
    function=send_channel_message,
    integration="slack",
    active=True
)

READ_CHANNEL_HISTORY = TangoFunction(
    name="read_slack_channel_history",
    description="Retrieves the message history of a specific Slack channel",
    args=[
        {
            "name": "channel_id",
            "description": "The Slack channel ID to read the history from",
            "type": "str"
        }
    ],
    return_description="confirmation of channel history retrieval",
    func_type="slack",
    function=read_channel_history,
    integration="slack"
)

LIST_CHANNELS = TangoFunction(
    name="list_slack_channels",
    description="Lists all the channels available on Slack",
    args=[],
    return_description="List of all the channels available on Slack",
    func_type="slack",
    function=list_channels,
    integration="slack"
)