"""Embedding provider contracts and an OpenAI-compatible HTTP adapter."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import httpx


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


class EmbeddingProvider(Protocol):
    """Generate document and query embeddings for the vector store."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class OpenAICompatibleEmbeddingProvider:
    """Call an embedding API that implements the OpenAI /embeddings shape."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint = self._endpoint(base_url)
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._request(list(texts))

    def embed_query(self, text: str) -> list[float]:
        vectors = self._request([text])
        if not vectors:
            raise EmbeddingProviderError("embedding provider returned no vector")
        return vectors[0]

    def _request(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": inputs},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("data")
            if not isinstance(items, list):
                raise EmbeddingProviderError("embedding response has no data list")
            ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
            vectors = [item.get("embedding") for item in ordered]
            if any(not isinstance(vector, list) for vector in vectors):
                raise EmbeddingProviderError("embedding response contains an invalid vector")
            return vectors
        except EmbeddingProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            raise EmbeddingProviderError(f"embedding request failed: {exc}") from exc

    @staticmethod
    def _endpoint(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        return normalized if normalized.endswith("/embeddings") else f"{normalized}/embeddings"
