from typing import TypedDict, NotRequired


class GraphState(TypedDict):
    name: str
    user_query: str
    intent: NotRequired[str]
    route: NotRequired[str]
    confidence: NotRequired[float]
    message: NotRequired[str]