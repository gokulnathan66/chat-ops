from __future__ import annotations

from langfuse import observe
from langgraph.types import Command

from src.services.conversation import ConversationService
from src.states.config import GraphState

conversation_svc = ConversationService()

_ESCALATION_MESSAGE = (
    "I wasn't able to give you a confident answer to that. "
    "I've connected you with a human agent who will review your question and respond shortly. "
    "Please wait — you'll see their reply here."
)


@observe()
def hitl_escalate_node(state: GraphState) -> Command:
    session_id = state["session_id"]
    turn_n = state["turn"]

    conversation_svc.write_turn(
        session_id=session_id,
        turn_n=turn_n,
        data={
            "user_query": state["user_query"],
            "ai_response": _ESCALATION_MESSAGE,
            "intent": "escalate",
            "route": "escalate",
            "retrieved_docs": [],
            "token_usage": {"input": 0, "output": 0},
            "latency_ms": 0,
        },
    )

    conversation_svc.mark_hitl_pending(session_id)

    conversation_svc.write_hitl(
        session_id=session_id,
        trigger="bot_escalation",
        scores={},
        extras={
            "hitl_type": "escalation",
            "turn_n": str(turn_n),
            "reason": state.get("reason", ""),
        },
    )

    return Command(
        update={
            "message": _ESCALATION_MESSAGE,
            "route": "escalate",
            "retrieved_docs": [],
            "token_usage": {"input": 0, "output": 0},
            "latency_ms": 0,
        },
        goto="__end__",
    )
