from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError
from langchain_core.tools import tool as lc_tool
from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from typing import Any, Callable, Sequence

from src.setting.config import settings


class BedrockService:
    def __init__(
        self,
        model_id: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.model_id = model_id or settings.MODEL_ID
        self.region_name = region_name or settings.AWS_REGION
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)
        self.temperature = settings.TEMPERATURE
        self.max_tokens = settings.MAX_TOKENS
    def _build_message(self, role: str, text: str) -> dict[str, Any]:
        return {
            "role": role,
            "content": [{"text": text}],
        }

    def converse(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        tool_config: dict[str, Any] | None = None,
        additional_model_request_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conversation = messages[:] if messages else []
        conversation.append(self._build_message("user", user_message))

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": conversation,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        if tool_config:
            request["toolConfig"] = tool_config

        if additional_model_request_fields:
            request["additionalModelRequestFields"] = additional_model_request_fields

        try:
            response = self.client.converse(**request)
            return response
        except ClientError as exc:
            raise RuntimeError(
                f"Bedrock converse failed for model '{self.model_id}': "
                f"{exc.response['Error'].get('Message', str(exc))}"
            ) from exc

    def converse_text(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        tool_config: dict[str, Any] | None = None,
        additional_model_request_fields: dict[str, Any] | None = None,
    ) -> str:
        response = self.converse(
            user_message=user_message,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_config=tool_config,
            additional_model_request_fields=additional_model_request_fields,
        )

        content = response.get("output", {}).get("message", {}).get("content", [])
        text_parts = [item["text"] for item in content if "text" in item]
        return "\n".join(text_parts).strip()

    def converse_stream(
        self,
        *,
        user_message: str,
        system_prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        tool_config: dict[str, Any] | None = None,
        additional_model_request_fields: dict[str, Any] | None = None,
    ):
        conversation = messages[:] if messages else []
        conversation.append(self._build_message("user", user_message))

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": conversation,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        if tool_config:
            request["toolConfig"] = tool_config

        if additional_model_request_fields:
            request["additionalModelRequestFields"] = additional_model_request_fields

        try:
            response = self.client.converse_stream(**request)
            for event in response.get("stream", []):
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        yield delta["text"]
        except ClientError as exc:
            raise RuntimeError(
                f"Bedrock converse_stream failed for model '{self.model_id}': "
                f"{exc.response['Error'].get('Message', str(exc))}"
            ) from exc

    def converse_structured(
        self,
        *,
        user_message: str,
        json_schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
        system_prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        additional_model_request_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conversation = messages[:] if messages else []
        conversation.append(self._build_message("user", user_message))

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": conversation,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": schema_name,
                            "description": schema_description,
                            "inputSchema": {"json": json_schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": schema_name}},
            },
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        if additional_model_request_fields:
            request["additionalModelRequestFields"] = additional_model_request_fields

        try:
            response = self.client.converse(**request)
            content = response.get("output", {}).get("message", {}).get("content", [])
            for item in content:
                if "toolUse" in item:
                    return item["toolUse"]["input"]
            raise RuntimeError("Bedrock did not return a tool use response")
        except ClientError as exc:
            raise RuntimeError(
                f"Bedrock structured converse failed for model '{self.model_id}': "
                f"{exc.response['Error'].get('Message', str(exc))}"
            ) from exc
        
    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        content = response.get("output", {}).get("message", {}).get("content", [])
        text_parts = [item["text"] for item in content if "text" in item]
        return "\n".join(text_parts).strip()

    @staticmethod
    def pretty_response(response: dict[str, Any]) -> str:
        return json.dumps(response, indent=2, default=str)
    


    def get_llm(self) -> ChatBedrockConverse:
        return ChatBedrockConverse(
            model_id=self.model_id,
            region_name=self.region_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )



    def create_agent(
        self,
        *,
        tool_defs: Sequence[dict[str, Any]],
        system_prompt: str,
    ):
        llm = self.get_llm()

        return create_agent(
            model=llm,
            tools=tool_defs,
            system_prompt=system_prompt,
        )

    def invoke_agent(
        self,
        *,
        user_query: str,
        tool_defs: Sequence[dict[str, Any]],
        system_prompt: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        agent = self.create_agent(
            tool_defs=tool_defs,
            system_prompt=system_prompt,
        )

        input_messages = messages[:] if messages else []
        input_messages.append(
            {
                "role": "user",
                "content": user_query,
            }
        )

        return agent.invoke({"messages": input_messages})

    @staticmethod
    def extract_text(agent_response: dict[str, Any]) -> str:
        messages = agent_response.get("messages", [])
        if not messages:
            return ""

        last_message = messages[-1]

        content = getattr(last_message, "content", "")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []

            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

            return "\n".join(part for part in text_parts if part).strip()

        return str(content).strip()