from pydantic import BaseModel, Field
from typing import Literal, Optional
from typing import Any



class SemanticSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    top_k: int = Field(default=5, description="Number of results to return")
    tags: list[str] | None = Field(default=None, description="Optional tag filters")


class IntentRoute(BaseModel):
    intent: Literal["retrieval", "general_chat", "greeting", "fallback"] = Field(
        description="Detected user intent"
    )
    route: Literal["rag_node", "chat_node", "fallback_node"] = Field(
        description="Next node to execute in the graph"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the routing decision"
    )
    reason: str = Field(
        description="Short explanation for why this route was chosen"
    )


class GraphInvokeRequest(BaseModel):
    user_query: str = Field(..., description="User input for the graph")
    messages: list[dict[str, Any]] = Field(default_factory=list)
    message: str = Field(default="")
    session_id: Optional[str] = None
    turn: int = 1


class GraphInvokeResponse(BaseModel):
    result: dict[str, Any]
