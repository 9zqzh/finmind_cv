"""Chroma persistence for already-created knowledge chunks."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.knowledge.service import Chunk

# 索引重建时单次写入的切片数：避免一次性提交超大请求，
# 也保证中途失败时已写入的批次不丢失（不会出现先清空后重建的空索引）
REBUILD_BATCH_SIZE = 100


@dataclass(frozen=True)
class VectorHit:
    text: str
    source: str
    title: str
    resource_path: str | None
    distance: float


class ChromaVectorStore:
    """Small adapter that keeps Chroma details out of the knowledge service."""

    def __init__(
        self,
        persist_dir: str | Path,
        collection_name: str,
        *,
        client: Any | None = None,
        host: str = "",
        port: int = 8001,
    ) -> None:
        if client is None:
            import chromadb

            if host:
                client = chromadb.HttpClient(host=host, port=port)
            else:
                Path(persist_dir).mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self.collection.count()

    def rebuild(self, chunks: list["Chunk"], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts must match")
        if not chunks:
            if self.count:
                self.collection.delete(ids=self.collection.get()["ids"])
            return
        occurrences: dict[str, int] = defaultdict(int)
        ids: list[str] = []
        for chunk in chunks:
            base_id = self._chunk_id(chunk)
            occurrence = occurrences[base_id]
            ids.append(base_id if occurrence == 0 else f"{base_id}-{occurrence}")
            occurrences[base_id] += 1
        # 分批写入；chunk_id 不变的内容按 upsert 覆盖，避免重复
        for start in range(0, len(chunks), REBUILD_BATCH_SIZE):
            end = min(start + REBUILD_BATCH_SIZE, len(chunks))
            self.collection.add(
                ids=ids[start:end],
                documents=[chunk.text for chunk in chunks[start:end]],
                metadatas=[self._metadata(chunk) for chunk in chunks[start:end]],
                embeddings=embeddings[start:end],
            )
        # 只清理本次不再存在的旧条目（如源文件被删除），已失效数据不残留
        new_ids = set(ids)
        stale = [
            old_id
            for old_id in self.collection.get()["ids"]
            if old_id not in new_ids
        ]
        if stale:
            self.collection.delete(ids=stale)

    def search(self, embedding: list[float], top_k: int) -> list[VectorHit]:
        if not self.count:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(max(top_k, 1), self.count),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[VectorHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            metadata = metadata or {}
            hits.append(
                VectorHit(
                    text=str(document),
                    source=str(metadata.get("source", "")),
                    title=str(metadata.get("title", "")),
                    resource_path=metadata.get("resource_path") or None,
                    distance=float(distance),
                )
            )
        return hits

    @staticmethod
    def _metadata(chunk: "Chunk") -> dict[str, str]:
        return {
            "source": chunk.source,
            "title": chunk.title,
            "resource_path": chunk.resource_path or "",
        }

    @staticmethod
    def _chunk_id(chunk: "Chunk") -> str:
        value = "\0".join(
            [chunk.source, chunk.title, chunk.resource_path or "", chunk.text]
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
