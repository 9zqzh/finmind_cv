"""Embedding provider contracts and an OpenAI-compatible HTTP adapter."""

from __future__ import annotations

import time
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
        batch_size: int = 10,
        retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.endpoint = self._endpoint(base_url)
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.batch_size = max(batch_size, 1)
        # 网络抖动/服务端 5xx 时的重试次数（指数退避，初退 1s 递增）
        self.retries = max(retries, 0)
        # 测试注入用：默认为 None 走真实网络
        self.transport = transport

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._request(list(texts[start : start + self.batch_size])))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._request([text])
        if not vectors:
            raise EmbeddingProviderError("embedding provider returned no vector")
        return vectors[0]

    def _request(self, inputs: list[str]) -> list[list[float]]:
        """带指数退避重试的嵌入请求：超时/连接错误/5xx 可重试，其余直接失败。"""
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._request_once(inputs)
            except EmbeddingProviderError:
                raise
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                # HTTPStatusError 只有 5xx 才值得重试（4xx 是参数/密钥问题）
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise EmbeddingProviderError(f"embedding request failed: {exc}") from exc
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2**attempt)  # 1s / 2s / 4s 指数退避
        raise EmbeddingProviderError(f"embedding request failed after retries: {last_exc}") from last_exc

    def _request_once(self, inputs: list[str]) -> list[list[float]]:
        try:
            with httpx.Client(transport=self.transport) as client:
                response = client.post(
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
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            # 响应结构/解析异常：重试无意义，直接包装为业务错误
            raise EmbeddingProviderError(f"embedding response is invalid: {exc}") from exc

    @staticmethod
    def _endpoint(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        return normalized if normalized.endswith("/embeddings") else f"{normalized}/embeddings"
