from typing import NotRequired, TypedDict


class GraphState(TypedDict):
    name: str
    user_query: str
    session_id: str
    turn: int
    intent: NotRequired[str]
    route: NotRequired[str]
    confidence: NotRequired[float]
    message: NotRequired[str]
    retrieved_docs: NotRequired[list[dict]]
    token_usage: NotRequired[dict]
    latency_ms: NotRequired[float]
    reason: NotRequired[str]
