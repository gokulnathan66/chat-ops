from __future__ import annotations

from langchain.tools import tool

from src.schema.config import SemanticSearchInput
from src.services.embedding import EmbeddingService
from src.services.qdrant import QdrantService
from src.setting.config import settings


class RAGToolService:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.qdrant_service = QdrantService()

    def search(self, query: str, top_k: int = 5, tags: list[str] | None = None) -> list[dict]:
        query_vector = self.embedding_service.embed_query(query)
        return self.qdrant_service.semantic_search(
            query_vector=query_vector,
            top_k=top_k or settings.top_k,
            tags=tags,
        )


rag_tool_service = RAGToolService()


@tool("semantic_document_search", args_schema=SemanticSearchInput)
def semantic_document_search(query: str, top_k: int = 5, tags: list[str] | None = None) -> list[dict]:
    """Search indexed documents from Qdrant using semantic search"""
    return rag_tool_service.search(query=query, top_k=top_k, tags=tags)


