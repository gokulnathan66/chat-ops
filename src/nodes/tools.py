from __future__ import annotations

import time

from langgraph.types import Command
from langfuse import observe

from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.states.config import GraphState
from src.tools.rag import semantic_document_search


bedrock_service = BedrockService()
conversation_svc = ConversationService()

TOOL_DEFS = [semantic_document_search]

SYSTEM_PROMPT = "You are a helpful assistant. Use tools when needed."


def _extract_retrieved_docs(response) -> list[dict]:
    docs = []
    for msg in getattr(response, "messages", []):
        content = getattr(msg, "content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    for item in block.get("content", []):
                        if isinstance(item, dict) and item.get("type") == "text":
                            docs.append({"text_snippet": item["text"][:200]})
    return docs


def _extract_token_usage(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return {
            "input": getattr(usage, "input_tokens", 0),
            "output": getattr(usage, "output_tokens", 0),
        }
    return {"input": 0, "output": 0}


@observe()
def tools_node(state: GraphState):
    messages = state.get("messages", [])
    user_query = state.get("user_query", "").strip()

    start = time.time()
    response = bedrock_service.invoke_agent(
        user_query=user_query,
        tool_defs=TOOL_DEFS,
        system_prompt=SYSTEM_PROMPT,
        messages=messages,
    )
    latency_ms = (time.time() - start) * 1000

    text = bedrock_service.extract_text(response)
    retrieved_docs = _extract_retrieved_docs(response)
    token_usage = _extract_token_usage(response)

    conversation_svc.write_turn(
        session_id=state["session_id"],
        turn_n=state["turn"],
        data={
            "user_query": state["user_query"],
            "ai_response": text,
            "intent": state.get("intent", "tools"),
            "route": "tools",
            "retrieved_docs": retrieved_docs,
            "token_usage": token_usage,
            "latency_ms": latency_ms,
        },
    )

    return Command(
        update={
            "message": text,
            "retrieved_docs": retrieved_docs,
            "token_usage": token_usage,
            "latency_ms": latency_ms,
        },
        goto="__end__",
    )
