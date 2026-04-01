from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.setting.config import settings


class BedrockConverseService:
    def __init__(
        self,
        model_id: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.model_id = model_id or settings.bedrock_model_id
        self.region_name = region_name or settings.aws_region
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)

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
        top_p: float = 0.9,
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
                "topP": top_p,
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
        top_p: float = 0.9,
        max_tokens: int = 1024,
        tool_config: dict[str, Any] | None = None,
        additional_model_request_fields: dict[str, Any] | None = None,
    ) -> str:
        response = self.converse(
            user_message=user_message,
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
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
        top_p: float = 0.9,
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
                "topP": top_p,
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

    def converse_with_tools(
        self,
        *,
        user_message: str,
        tool_config: dict[str, Any],
        tool_handlers: dict[str, Any],
        system_prompt: str | None = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            self._build_message("user", user_message)
        ]

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": messages,
            "toolConfig": tool_config,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p,
            },
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        try:
            response = self.client.converse(**request)
        except ClientError as exc:
            raise RuntimeError(
                f"Initial Bedrock tool call failed: "
                f"{exc.response['Error'].get('Message', str(exc))}"
            ) from exc

        messages.append(response["output"]["message"])
        stop_reason = response.get("stopReason")

        while stop_reason == "tool_use":
            tool_requests = response["output"]["message"]["content"]

            for item in tool_requests:
                if "toolUse" not in item:
                    continue

                tool_use = item["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]

                if tool_name not in tool_handlers:
                    tool_result = {
                        "toolUseId": tool_use_id,
                        "status": "error",
                        "content": [{"text": f"No handler found for tool '{tool_name}'"}],
                    }
                else:
                    try:
                        result = tool_handlers[tool_name](tool_input)
                        tool_result = {
                            "toolUseId": tool_use_id,
                            "content": [{"json": result}],
                        }
                    except Exception as exc:
                        tool_result = {
                            "toolUseId": tool_use_id,
                            "status": "error",
                            "content": [{"text": str(exc)}],
                        }

                messages.append(
                    {
                        "role": "user",
                        "content": [{"toolResult": tool_result}],
                    }
                )

            try:
                response = self.client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    toolConfig=tool_config,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                        "topP": top_p,
                    },
                    **({"system": [{"text": system_prompt}]} if system_prompt else {}),
                )
            except ClientError as exc:
                raise RuntimeError(
                    f"Follow-up Bedrock tool call failed: "
                    f"{exc.response['Error'].get('Message', str(exc))}"
                ) from exc

            messages.append(response["output"]["message"])
            stop_reason = response.get("stopReason")

        return {
            "messages": messages,
            "response": response,
            "text": self.extract_text(response),
        }

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
        top_p: float = 0.9,
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
                "topP": top_p,
            },
            "outputConfig": {
                "textFormat": {
                    "type": "json_schema",
                    "structure": {
                        "jsonSchema": {
                            "name": schema_name,
                            "description": schema_description,
                            "schema": json.dumps(json_schema),
                        }
                    },
                }
            },
        }

        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        if additional_model_request_fields:
            request["additionalModelRequestFields"] = additional_model_request_fields

        try:
            response = self.client.converse(**request)
            content = response.get("output", {}).get("message", {}).get("content", [])
            text_parts = [item["text"] for item in content if "text" in item]
            raw_text = "\n".join(text_parts).strip()
            return json.loads(raw_text)
        except ClientError as exc:
            raise RuntimeError(
                f"Bedrock structured converse failed for model '{self.model_id}': "
                f"{exc.response['Error'].get('Message', str(exc))}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Bedrock returned invalid structured JSON output") 
        
    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        content = response.get("output", {}).get("message", {}).get("content", [])
        text_parts = [item["text"] for item in content if "text" in item]
        return "\n".join(text_parts).strip()

    @staticmethod
    def pretty_response(response: dict[str, Any]) -> str:
        return json.dumps(response, indent=2, default=str)