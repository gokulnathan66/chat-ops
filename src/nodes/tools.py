from __future__ import annotations

import time

from langchain_core.messages import AIMessage, ToolMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langgraph.types import Command

from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.services.prompt import prompt_service
from src.states.config import GraphState
from src.tools.rag import semantic_document_search

bedrock_service = BedrockService()
conversation_svc = ConversationService()

TOOL_DEFS = [semantic_document_search]

_FALLBACK_SYSTEM_PROMPT = (
    "You are a helpful financial analyst assistant. "
    "Use the semantic_document_search tool to retrieve relevant documents before answering."
)


def _get_system_prompt() -> str:
    try:
        return prompt_service.render("rag_assistant")
    except Exception:
        return _FALLBACK_SYSTEM_PROMPT


def _extract_retrieved_docs(response: dict) -> list[dict]:
    docs = []
    for msg in response.get("messages", []):
        if isinstance(msg, ToolMessage):
            content = msg.content
            if isinstance(content, str):
                docs.append({"text_snippet": content[:200]})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        docs.append({"text_snippet": item.get("text", "")[:200]})
    return docs


def _extract_token_usage(response: dict) -> dict:
    for msg in reversed(response.get("messages", [])):
        if isinstance(msg, AIMessage):
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                return {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                }
    return {"input": 0, "output": 0}


@observe()
def tools_node(state: GraphState):
    user_query = state.get("user_query", "").strip()

    start = time.time()
    langfuse_handler = CallbackHandler()
    response = bedrock_service.invoke_agent(
        user_query=user_query,
        tool_defs=TOOL_DEFS,
        system_prompt=_get_system_prompt(),
        messages=[],
        callbacks=[langfuse_handler],
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
    conversation_svc.write_cost(state["session_id"], token_usage, bedrock_service.model_id)

    return Command(
        update={
            "message": text,
            "retrieved_docs": retrieved_docs,
            "token_usage": token_usage,
            "latency_ms": latency_ms,
        },
        goto="__end__",
    )
