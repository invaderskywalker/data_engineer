import boto3
import json
from src.ml.llm.Client import LLMClient


class Bedrock(LLMClient):
    def __init__(self, region_name="us-east-1"):
        self.client = boto3.client("bedrock-runtime", region_name=region_name)

    @staticmethod
    def parseInputToLLamaFormat(input_json):
        prompt_string = ""
        for _msg in input_json:
            if _msg["role"] == "system":
                prompt_string += "system\n\n" + _msg["content"] + "\n"
            elif _msg["role"] == "user":
                prompt_string += "user\n\n" + _msg["content"] + "\n"
            elif _msg["role"] == "assistant":
                prompt_string += "assistant\n\n" + _msg["content"] + "\n"
        prompt_string += "assistant"
        return prompt_string

    def run_bedrock(self, arr):
        # prompt = chat.formatAsString()
        prompt_string = self.parseInputToLLamaFormat(arr)
        body = json.dumps(
            {
                "prompt": prompt_string,
                "max_gen_len": 2048,
                "temperature": 0,
            }
        ).encode()
        response = self.client.invoke_model(
            body=body,
            modelId="meta.llama3-70b-instruct-v1:0",
            accept="application/json",
            contentType="application/json",
        )
        response_body = json.loads(response["body"].read())
        return response_body["generation"]
