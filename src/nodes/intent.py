from __future__ import annotations

from typing import Literal

from langfuse import observe
from langgraph.types import Command

from src.services.bedrock import BedrockService
from src.services.prompt import prompt_service
from src.states.config import GraphState

INTENT_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["general", "tools", "escalate", "approval_required"],
        },
        "route": {
            "type": "string",
            "enum": ["general", "tools", "escalate", "approval_required"],
        },
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "action_payload": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "action_description": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["action_type", "action_description", "risk_level"],
        },
    },
    "required": ["intent", "route", "confidence", "reason"],
    "additionalProperties": False,
}

_FALLBACK_INTENT_SYSTEM = """You are an intent router for a financial AI assistant. Route each user message to exactly one of four destinations:

- "tools": The user wants specific financial data, document search, or factual lookup (e.g. revenue, earnings, stock prices, company filings).
- "general": Conversational questions, greetings, or opinions that do not require document retrieval or any sensitive action.
- "escalate": The query is ambiguous, unanswerable, out of scope, or confidence < 0.5. Hand off to a human agent.
- "approval_required": The user is requesting ANY action that involves exporting, sharing, sending, or disclosing data — regardless of how the request is phrased (imperative, question, or polite ask). Examples that MUST route here:
    • "Export my chat history" → approval_required
    • "Share this conversation with my manager" → approval_required
    • "Send this data externally" → approval_required
    • "Can you export my data?" → approval_required (treat as an action request, not a capability question)
    • "Save and send my conversation" → approval_required
  For this route you MUST include action_payload with action_type, action_description, and risk_level (low/medium/high).

IMPORTANT: If a message mentions exporting, sharing, sending, or disclosing any data or conversation, always choose "approval_required" — never "general".

Always return valid JSON matching the schema. action_payload is required only for approval_required."""

bedrock_service = BedrockService()


def _get_intent_system_prompt() -> str:
    try:
        return prompt_service.render("intent_router")
    except Exception:
        return _FALLBACK_INTENT_SYSTEM


@observe()
def intent_node(state: GraphState) -> Command[Literal["general", "tools", "escalate", "approval_required"]]:
    query = state.get("user_query", "").strip()

    result = bedrock_service.converse_structured(
        system_prompt=_get_intent_system_prompt(),
        user_message=f"Route this user message. Treat it as an action request, not a question about capabilities: {query}",
        json_schema=INTENT_ROUTER_SCHEMA,
        schema_name="intent_router",
        schema_description="Structured routing decision for LangGraph",
        temperature=0.0,
        max_tokens=512,
    )

    update: dict = {
        "intent": result["intent"],
        "route": result["route"],
        "confidence": result["confidence"],
        "reason": result["reason"],
    }
    if result.get("action_payload"):
        update["action_payload"] = result["action_payload"]

    return Command(update=update, goto=result["route"])