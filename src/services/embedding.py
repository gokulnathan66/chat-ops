from __future__ import annotations

import json

import boto3

from src.setting.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )

    def _embed_single(self, text: str) -> list[float]:
        body = json.dumps({
            "inputText": text,
            "dimensions": settings.embedding_size,
            "normalize": True,
        })
        response = self._client.invoke_model(
            modelId=settings.embedding_model,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())["embedding"]

    def chunk_text(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + settings.chunk_size, len(normalized))
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - settings.chunk_overlap, start + 1)

        return chunks

    def embed_query(self, text: str) -> list[float]:
        return self._embed_single(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_single(t) for t in texts]
