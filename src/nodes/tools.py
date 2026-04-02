from __future__ import annotations

from src.services.bedrock import BedrockService
from src.states.config import GraphState
from src.tools.rag import semantic_document_search


bedrock_service = BedrockService()

TOOL_DEFS = [ semantic_document_search]

SYSTEM_PROMPT = "You are a helpful assistant. Use tools when needed."


def tools_node(state: GraphState):
    messages = state.get("messages", [])
    user_query = state.get("user_query", "").strip()

    response = bedrock_service.invoke_agent(
        user_query=user_query,
        tool_defs=TOOL_DEFS,
        system_prompt=SYSTEM_PROMPT,
        messages=messages,
    )

    text = bedrock_service.extract_text(response)

    return {
        "messages": response.get("messages", []),
        "message": text,
        "stop_reason": "end",
    }