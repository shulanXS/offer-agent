import hashlib
import math
import re
from abc import ABC, abstractmethod

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]{1,4}")


class EmbeddingService(ABC):
    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingService(EmbeddingService):
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = TOKEN_RE.findall((text or "").lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % self.dimension
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            weight = 1.0 + (len(token) / 10.0)
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(self, model_name: str) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY 未配置，无法使用 OpenAI Embeddings")
        self._embeddings = OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            model=model_name or "text-embedding-3-small",
        )
        self.dimension = settings.rag_embedding_dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, item)) for item in self._embeddings.embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(map(float, self._embeddings.embed_query(text)))


def create_embedding_service() -> EmbeddingService:
    provider = (settings.rag_embedding_provider or "local").strip().lower()
    if provider == "openai":
        return OpenAIEmbeddingService(settings.rag_embedding_model)
    return DeterministicEmbeddingService(settings.rag_embedding_dimension)
