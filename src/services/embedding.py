from __future__ import annotations

import json
import logging
import time

import boto3
from botocore.exceptions import ClientError

from src.setting.config import settings

logger = logging.getLogger(__name__)

_MAX_EMBED_RETRIES = 3
_EMBED_BACKOFF_BASE = 1.0


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
        last_exc: Exception | None = None
        for attempt in range(_MAX_EMBED_RETRIES):
            try:
                response = self._client.invoke_model(
                    modelId=settings.embedding_model,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                return json.loads(response["body"].read())["embedding"]
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in ("ModelErrorException", "ThrottlingException", "ServiceUnavailableException"):
                    last_exc = exc
                    wait = _EMBED_BACKOFF_BASE * (2 ** attempt)
                    logger.warning("Bedrock embed attempt %d/%d failed (%s) — retrying in %.1fs", attempt + 1, _MAX_EMBED_RETRIES, code, wait)
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Embedding failed after {_MAX_EMBED_RETRIES} attempts") from last_exc

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
