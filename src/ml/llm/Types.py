from dataclasses import dataclass
from enum import Enum

class ChatCompletion:
    def __init__(self, system: str, prev: list, user: str):
        self.system = system
        self.prev = prev
        self.user = user

    def format(self):
        return {"system": self.system, "prev": self.prev, "user": self.user}

    def formatAsString(self):

        previousMessagesStringified = ""
        for message in self.prev:
            previousMessagesStringified += f"""
            User: {message["user"]}
            Assistant: {message["assistant"]}
            """
        return f"""System: {self.system}
        {previousMessagesStringified}
        
        User: {self.user}
        Assistant: """


class ModelOptions:
    def __init__(self, model: str, max_tokens: int, temperature: float):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature



class TokenMode(Enum):
    LEGACY = "legacy"               # max_tokens
    COMPLETION_ONLY = "completion"  # max_completion_tokens


class APIType(Enum):
    CHAT = "chat"
    RESPONSES = "responses"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    token_mode: TokenMode
    api_type: APIType
    supports_temperature: bool


MODEL_REGISTRY = {
    "gpt-4.1": ModelSpec(name="gpt-4.1",token_mode=TokenMode.LEGACY,api_type=APIType.CHAT,supports_temperature=True,),
    "gpt-5.1": ModelSpec(name="gpt-5.1",token_mode=TokenMode.COMPLETION_ONLY,api_type=APIType.CHAT,  supports_temperature=True),
    "gpt-5.2": ModelSpec(name="gpt-5.2",token_mode=TokenMode.COMPLETION_ONLY,api_type=APIType.CHAT,   supports_temperature=True),
    "gpt-5.2-r": ModelSpec(name="gpt-5.2",token_mode=TokenMode.COMPLETION_ONLY,api_type=APIType.RESPONSES,  supports_temperature=False),
    "gpt-5.4": ModelSpec(
        name="gpt-5.4",
        token_mode=TokenMode.COMPLETION_ONLY,
        api_type=APIType.CHAT,
        supports_temperature=True,
    ),
}


@dataclass
class ModelOptions2:
    model: str
    max_output_tokens: int
    temperature: float = 0.0


class OpenAIParamBuilder:
    @staticmethod
    def build_chat_params(messages, options: ModelOptions2) -> dict:
        spec = MODEL_REGISTRY[options.model]

        params = {
            "model": spec.name,
            "messages": messages,
        }

        # Token handling
        if spec.token_mode == TokenMode.LEGACY:
            params["max_tokens"] = options.max_output_tokens
        else:
            params["max_completion_tokens"] = options.max_output_tokens

        if spec.supports_temperature:
            params["temperature"] = options.temperature

        return params




