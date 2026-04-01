from __future__ import annotations

from src.states.config import GraphState
from src.services.bedrock import BedrockConverseService
from typing import Literal
from langgraph.types import Command

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


bedrock_service = BedrockConverseService()


def intent_node(state: GraphState) -> Command[Literal["general", "tools"]]:
    query = state.get("user_query", "").strip()

    result = bedrock_service.converse_structured(
        system_prompt="You are an intent router for a LangGraph-based RAG system.",
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