from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.setting.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

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
        model = self._get_model()
        vector = model.encode([text], normalize_embeddings=True)[0]
        return vector.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]