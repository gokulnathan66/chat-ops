from pydantic import BaseModel, Field

class SemanticSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    top_k: int = Field(default=5, description="Number of results to return")
    tags: list[str] | None = Field(default=None, description="Optional tag filters")
