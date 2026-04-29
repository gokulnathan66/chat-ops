import time

from langfuse import observe
from langgraph.types import Command

from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.services.prompt import prompt_service
from src.states.config import GraphState

bedrock_service = BedrockService()
conversation_svc = ConversationService()

_FALLBACK_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Answer clearly and concisely. "
    "Do not fabricate financial figures or company-specific facts."
)


def _get_system_prompt() -> str:
    try:
        return prompt_service.render("general_assistant")
    except Exception:
        return _FALLBACK_SYSTEM_PROMPT


@observe()
def general_node(state: GraphState) -> Command:
    user_query = state.get("user_query", "").strip()

    start = time.time()
    response = bedrock_service.converse(
        user_message=user_query,
        system_prompt=_get_system_prompt(),
        temperature=0.3,
        max_tokens=1024,
    )
    latency_ms = (time.time() - start) * 1000

    # Extract text from the full converse response
    content = response.get("output", {}).get("message", {}).get("content", [])
    response_text = "\n".join(item["text"] for item in content if "text" in item).strip()

    token_usage = response.get("usage", {})

    conversation_svc.write_turn(
        session_id=state["session_id"],
        turn_n=state["turn"],
        data={
            "user_query": user_query,
            "ai_response": response_text,
            "intent": state.get("intent", "general"),
            "route": "general",
            "retrieved_docs": [],
            "token_usage": {
                "input": token_usage.get("inputTokens", 0),
                "output": token_usage.get("outputTokens", 0),
            },
            "latency_ms": latency_ms,
        },
    )

    return Command(
        update={"message": response_text},
        goto="__end__",
    )
