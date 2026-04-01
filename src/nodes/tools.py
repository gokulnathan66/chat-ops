from src.tools.rag import run_bedrock_tool as semantic_document_search
from __future__ import annotations

from typing import Any

from states.config import GraphState

from states.config import GraphState
from src.services.bedrock import BedrockConverseService




TOOLS_REGISTRY = {
    "semantic_document_search": semantic_document_search,
}


bedrock_service = BedrockConverseService()


def tools_node(state: GraphState):
    messages = state.get("messages", [])
    user_query = state.get("user_query", "").strip()

    response = bedrock_service.converse(
        user_message=user_query,
        messages=messages,
        system_prompt="You are a helpful assistant. Use tools when needed.",
        tool_config=TOOLS_REGISTRY,
        temperature=0.2,
        max_tokens=1024,
    )

    assistant_message = response["output"]["message"]

    return {
        "messages": messages
        + [{"role": "user", "content": [{"text": user_query}]}]
        + [assistant_message],
        "message": bedrock_service.extract_text(response),
        "stop_reason": response.get("stopReason"),
    }
   