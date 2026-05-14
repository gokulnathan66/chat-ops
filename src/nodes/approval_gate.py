from __future__ import annotations

from langfuse import observe
from langgraph.types import Command

from src.services.conversation import ConversationService
from src.states.config import GraphState

conversation_svc = ConversationService()


@observe()
def approval_gate_node(state: GraphState) -> Command:
    session_id = state["session_id"]
    turn_n = state["turn"]
    payload = state.get("action_payload") or {}

    action_description = payload.get("action_description", "the requested action")
    action_type = payload.get("action_type", "unknown")
    risk_level = payload.get("risk_level", "medium")

    message = (
        f"Your request to \"{action_description}\" requires supervisor authorization before I can proceed. "
        "A reviewer has been notified and will approve or decline shortly. "
        "You'll see the outcome here once a decision is made."
    )

    conversation_svc.write_turn(
        session_id=session_id,
        turn_n=turn_n,
        data={
            "user_query": state["user_query"],
            "ai_response": message,
            "intent": "approval_required",
            "route": "approval_required",
            "retrieved_docs": [],
            "token_usage": {"input": 0, "output": 0},
            "latency_ms": 0,
        },
    )

    conversation_svc.mark_approval_pending(session_id)

    conversation_svc.write_hitl(
        session_id=session_id,
        trigger="approval_required",
        scores={},
        extras={
            "hitl_type": "approval",
            "turn_n": str(turn_n),
            "action_type": action_type,
            "action_description": action_description,
            "risk_level": risk_level,
        },
    )

    return Command(
        update={
            "message": message,
            "route": "approval_required",
            "retrieved_docs": [],
            "token_usage": {"input": 0, "output": 0},
            "latency_ms": 0,
        },
        goto="__end__",
    )
