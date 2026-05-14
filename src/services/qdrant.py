from __future__ import annotations

import contextlib
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    MatchAny,
    PointStruct,
    VectorParams,
)

from src.setting.config import settings


class QdrantService:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.QDRANT_HOST,
            api_key=settings.QDRANT_API_KEY,
        )

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(settings.QDRANT_COLLECTION):
            self.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.embedding_size,
                    distance=Distance.COSINE,
                ),
            )

        index_fields = {
            "doc_id": "keyword",
            "chunk_id": "keyword",
            "text": "text",
            "source": "keyword",
            "title": "text",
            "url_or_file_path": "keyword",
            "tags": "keyword",
            "created_at": "datetime",
            "section": "keyword",
        }

        for field_name, field_schema in index_fields.items():
            with contextlib.suppress(Exception):
                self.client.create_payload_index(
                    collection_name=settings.QDRANT_COLLECTION,
                    field_name=field_name,
                    field_schema=field_schema,
                )

    @staticmethod
    def sha256_hexdigest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def build_doc_id(self, text: str, source_uri: str) -> str:
        return self.sha256_hexdigest(f"{source_uri}:{text}")

    def build_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        return f"{doc_id}:{chunk_index}"

    def build_point_id(self, chunk_id: str) -> str:
        digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
        return str(uuid.UUID(bytes=digest[:16]))

    def build_points(
        self,
        *,
        full_text: str,
        chunks: list[str],
        vectors: list[list[float]],
        source: str,
        title: str,
        url_or_file_path: str,
        tags: list[str] | None = None,
        section_prefix: str = "section",
    ) -> tuple[str, list[PointStruct]]:
        tags = tags or []
        doc_id = self.build_doc_id(full_text, url_or_file_path)
        created_at = datetime.now(UTC).isoformat()
        points: list[PointStruct] = []

        for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False)):
            chunk_id = self.build_chunk_id(doc_id, idx)
            point_id = self.build_point_id(chunk_id)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "text": chunk,
                        "source": source,
                        "title": title,
                        "url_or_file_path": url_or_file_path,
                        "tags": tags,
                        "created_at": created_at,
                        "section": f"{section_prefix}_{idx + 1}",
                    },
                )
            )

        return doc_id, points

    def upsert_points(self, points: list[PointStruct]) -> None:
        if not points:
            return
        self.ensure_collection()
        self.client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=points,
            wait=True,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        """Return one record per unique doc_id with metadata and chunk count."""
        self.ensure_collection()
        seen: dict[str, dict[str, Any]] = {}
        offset = None

        while True:
            results, next_offset = self.client.scroll(
                collection_name=settings.QDRANT_COLLECTION,
                scroll_filter=None,
                limit=250,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in results:
                p = point.payload or {}
                doc_id = p.get("doc_id")
                if not doc_id:
                    continue
                if doc_id not in seen:
                    seen[doc_id] = {
                        "doc_id": doc_id,
                        "title": p.get("title", ""),
                        "source": p.get("source", ""),
                        "url_or_file_path": p.get("url_or_file_path", ""),
                        "tags": p.get("tags", []),
                        "created_at": p.get("created_at", ""),
                        "chunk_count": 0,
                    }
                seen[doc_id]["chunk_count"] += 1

            if next_offset is None:
                break
            offset = next_offset

        return sorted(seen.values(), key=lambda d: d["created_at"], reverse=True)

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all points belonging to a doc_id. Returns count deleted."""
        self.ensure_collection()
        self.client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            wait=True,
        )
        return 0

    def semantic_search(
        self,
        *,
        query_vector: list[float],
        top_k: int,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        query_filter = None

        if tags:
            query_filter = Filter(
                must=[FieldCondition(key="tags", match=MatchAny(any=tags))]
            )

        result = self.client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "id": point.id,
                "score": point.score,
                "doc_id": point.payload.get("doc_id"),
                "chunk_id": point.payload.get("chunk_id"),
                "text": point.payload.get("text"),
                "source": point.payload.get("source"),
                "title": point.payload.get("title"),
                "url_or_file_path": point.payload.get("url_or_file_path"),
                "tags": point.payload.get("tags", []),
                "created_at": point.payload.get("created_at"),
                "section": point.payload.get("section"),
            }
            for point in result.points
        ]