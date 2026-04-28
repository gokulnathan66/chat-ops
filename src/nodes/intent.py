from __future__ import annotations

from src.states.config import GraphState
from src.services.bedrock import BedrockService
from typing import Literal
from langgraph.types import Command
from langfuse import observe

INTENT_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["general", "tools"],
        },
        "route": {
            "type": "string",
            "enum": ["general", "tools"],
        },
        "confidence": {
            "type": "number",
        },
        "reason": {
            "type": "string",
        },
    },
    "required": ["intent", "route", "confidence", "reason"],
    "additionalProperties": False,
}


from src.services.prompt import prompt_service

bedrock_service = BedrockService()

_FALLBACK_INTENT_SYSTEM = "You are an intent router for a LangGraph-based RAG system."


def _get_intent_system_prompt() -> str:
    try:
        return prompt_service.render("intent_router")
    except Exception:
        return _FALLBACK_INTENT_SYSTEM


@observe()
def intent_node(state: GraphState) -> Command[Literal["general", "tools"]]:
    query = state.get("user_query", "").strip()

    result = bedrock_service.converse_structured(
        system_prompt=_get_intent_system_prompt(),
        user_message=f"Classify this query for routing: {query}",
        json_schema=INTENT_ROUTER_SCHEMA,
        schema_name="intent_router",
        schema_description="Structured routing decision for LangGraph",
        temperature=0.0,
        max_tokens=256,
    )

    return Command(
        update={
            "intent": result["intent"],
            "route": result["route"],
            "confidence": result["confidence"],
            "reason": result["reason"],
        },
        goto=result["route"],
    )