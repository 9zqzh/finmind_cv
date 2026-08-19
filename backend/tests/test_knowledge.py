"""知识库检索测试。"""

from __future__ import annotations

import json
import sys

import httpx
import pytest

from app.knowledge import KnowledgeService
from app.knowledge.chroma_store import ChromaVectorStore
from app.knowledge.embeddings import (
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
)


def _prepare(tmp_path):
    (tmp_path / "学院简介.md").write_text(
        "# 学院简介\n\n大数据与人工智能学院成立于 2018 年，设有计算机科学与技术专业。\n",
        encoding="utf-8",
    )
    (tmp_path / "缓考制度.md").write_text(
        "# 缓考申请\n\n学生因疾病无法参加期末考试的，可申请缓考。\n",
        encoding="utf-8",
    )
    (tmp_path / "竞赛.json").write_text(
        json.dumps(
            [
                {
                    "title": "数学建模竞赛",
                    "time": "每年 9 月",
                    "description": "三人一组完成建模论文",
                }
            ]
        ),
        encoding="utf-8",
    )
    return KnowledgeService.from_directory(tmp_path)


def test_load_chunks(tmp_path):
    service = _prepare(tmp_path)
    assert len(service.chunks) >= 3


def test_search_hit(tmp_path):
    service = _prepare(tmp_path)
    results = service.search("缓考怎么申请", top_k=3)
    assert results
    assert results[0].source == "缓考制度.md"


def test_loads_original_resource_path(tmp_path):
    (tmp_path / "重修流程.md").write_text(
        "# 重修流程\n\n> 来源文件：resources/办事流程/重修流程.pdf\n\n课程重修申请流程。",
        encoding="utf-8",
    )
    service = KnowledgeService.from_directory(tmp_path)

    results = service.search("重修申请", top_k=3)

    assert results
    assert results[0].resource_path == "办事流程/重修流程.pdf"


def test_search_json_record(tmp_path):
    service = _prepare(tmp_path)
    results = service.search("数学建模", top_k=3)
    assert results
    assert results[0].title == "数学建模竞赛"


def test_search_miss(tmp_path):
    service = _prepare(tmp_path)
    assert service.search("完全不相关的查询内容xyz", top_k=3) == []


def test_missing_directory(tmp_path):
    service = KnowledgeService.from_directory(tmp_path / "不存在")
    assert service.chunks == []


class FakeEmbeddingProvider:
    def embed_documents(self, texts):
        return [[float("缓考" in text), float("重修" in text)] for text in texts]

    def embed_query(self, text):
        return [float("缓考" in text), float("重修" in text)]


class FakeCollection:
    def __init__(self):
        self.rows = []

    def count(self):
        return len(self.rows)

    def get(self, include=None):
        return {
            "ids": [row["id"] for row in self.rows],
            "metadatas": [row["metadata"] for row in self.rows],
        }

    def delete(self, ids):
        self.rows = [row for row in self.rows if row["id"] not in ids]

    def add(self, *, ids, documents, metadatas, embeddings):
        # 模拟真实 Chroma 的 upsert 语义：相同 id 覆盖旧数据
        for identifier, document, metadata, embedding in zip(
            ids, documents, metadatas, embeddings
        ):
            replaced = False
            for row in self.rows:
                if row["id"] == identifier:
                    row["document"] = document
                    row["metadata"] = metadata
                    row["embedding"] = embedding
                    replaced = True
                    break
            if not replaced:
                self.rows.append(
                    {
                        "id": identifier,
                        "document": document,
                        "metadata": metadata,
                        "embedding": embedding,
                    }
                )

    def query(self, *, query_embeddings, n_results, include):
        query = query_embeddings[0]
        ranked = sorted(
            self.rows,
            key=lambda row: sum(
                (left - right) ** 2
                for left, right in zip(query, row["embedding"])
            ),
        )[:n_results]
        distances = [
            sum((left - right) ** 2 for left, right in zip(query, row["embedding"]))
            for row in ranked
        ]
        return {
            "documents": [[row["document"] for row in ranked]],
            "metadatas": [[row["metadata"] for row in ranked]],
            "distances": [distances],
        }


class FakeChromaClient:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, *, name, metadata):
        return self.collection


def _vector_store():
    return ChromaVectorStore("unused", "knowledge_test", client=FakeChromaClient())


def test_chroma_store_uses_http_client_when_host_is_configured(monkeypatch):
    client = FakeChromaClient()
    captured = {}

    class FakeChromaModule:
        @staticmethod
        def HttpClient(*, host, port):
            captured.update(host=host, port=port)
            return client

    monkeypatch.setitem(sys.modules, "chromadb", FakeChromaModule)

    store = ChromaVectorStore("unused", "knowledge_http_test", host="127.0.0.1", port=8001)

    assert store.collection is client.collection
    assert captured == {"host": "127.0.0.1", "port": 8001}


def test_chunk_ids_are_stable_and_metadata_is_preserved(tmp_path):
    service = _prepare(tmp_path)
    first = [ChromaVectorStore._chunk_id(chunk) for chunk in service.chunks]
    second = [ChromaVectorStore._chunk_id(chunk) for chunk in service.chunks]
    assert first == second

    store = _vector_store()
    store.rebuild(service.chunks, [[1.0, 0.0]] * len(service.chunks))
    item = store.collection.get(include=["metadatas"])["metadatas"][0]
    assert {"source", "title", "resource_path"} <= set(item)


def test_vector_search_uses_embedding_provider(tmp_path):
    service = _prepare(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()
    results = service.search("缓考", top_k=1)
    assert service.vector_enabled is True
    assert results[0].source == "缓考制度.md"


def test_missing_embedding_uses_keyword_search(tmp_path):
    service = _prepare(tmp_path)
    assert service.vector_enabled is False
    assert service.search("缓考怎么申请", top_k=1)[0].source == "缓考制度.md"


def test_vector_failure_falls_back_to_keyword(tmp_path):
    class BrokenProvider(FakeEmbeddingProvider):
        def embed_query(self, text):
            raise RuntimeError("embedding unavailable")

    service = _prepare(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()
    service.embedding_provider = BrokenProvider()
    results = service.search("缓考怎么申请", top_k=1)
    # 单次失败仅本轮回退，不永久关闭向量检索
    assert service.vector_enabled is True
    assert results[0].source == "缓考制度.md"


def test_vector_failure_recovers_on_next_call(tmp_path):
    class BrokenProvider(FakeEmbeddingProvider):
        def embed_query(self, text):
            raise RuntimeError("embedding unavailable")

    service = _prepare(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()
    service.embedding_provider = BrokenProvider()
    assert service.search("缓考怎么申请", top_k=1)[0].source == "缓考制度.md"
    # 嵌入服务恢复后，下一轮仍走混合检索（向量 + 关键词）
    service.embedding_provider = FakeEmbeddingProvider()
    assert service.search("缓考怎么申请", top_k=1)[0].source == "缓考制度.md"
    assert service.vector_enabled is True


class DistantEmbeddingProvider(FakeEmbeddingProvider):
    """查询向量远离所有文档：向量分贴近 0。"""

    def embed_query(self, text):
        return [100.0, 100.0]


class NearEmbeddingProvider(FakeEmbeddingProvider):
    """查询向量紧贴缓考文档（[1, 0]），与任何关键词无关。"""

    def embed_query(self, text):
        return [1.0, 0.0]


def test_keyword_miss_with_low_vector_score_returns_empty(tmp_path):
    """关键词零命中且向量分低于置信门槛时，视为未检索到。"""
    service = _prepare(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()
    service.embedding_provider = DistantEmbeddingProvider()
    assert service.search("完全不相关的查询xyz", top_k=3) == []


def test_keyword_miss_with_high_vector_score_returns_results(tmp_path):
    """关键词零命中但向量分达到置信门槛时，返回纯向量结果。"""
    service = _prepare(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()
    service.embedding_provider = NearEmbeddingProvider()
    results = service.search("与关键词无关的查询", top_k=3)
    assert results
    assert results[0].source == "缓考制度.md"


def test_hybrid_search_fuses_vector_and_keyword(tmp_path):
    (tmp_path / "缓考制度.md").write_text(
        "# 缓考申请\n\n学生因疾病无法参加期末考试的，可申请缓考。\n",
        encoding="utf-8",
    )
    (tmp_path / "重修流程.md").write_text(
        "# 重修流程\n\n课程重修申请流程，需要填写申请表。\n",
        encoding="utf-8",
    )
    service = KnowledgeService.from_directory(tmp_path)
    service.vector_store = _vector_store()
    service.embedding_provider = FakeEmbeddingProvider()
    service._build_vector_index()

    results = service.search("缓考重修", top_k=2)
    sources = {result.source for result in results}
    # 双路都命中的候选参与 RRF 融合，两条路径的结果都应出现
    assert sources == {"缓考制度.md", "重修流程.md"}
    # 第一名融合分归一化为 1.0，且所有分数落在 0-1 区间
    assert results[0].score == 1.0
    assert all(0.0 <= result.score <= 1.0 for result in results)


def test_long_paragraph_chunking_with_overlap(tmp_path):
    (tmp_path / "长文.md").write_text(
        "# 长文\n\n" + "字" * 1000 + "\n",
        encoding="utf-8",
    )
    service = KnowledgeService.from_directory(tmp_path)
    chunks = [c.text for c in service.chunks if c.source == "长文.md"]
    # 1000 字符按 400 切、步长 350，应产生 3 个切片
    assert len(chunks) == 3
    # 相邻切片存在重叠：后一片开头内容应出现在前一片中
    assert chunks[1][:20] in chunks[0]
    assert chunks[2][:20] in chunks[1]


def test_rebuild_removes_stale_entries(tmp_path):
    service = _prepare(tmp_path)
    store = _vector_store()
    store.rebuild(service.chunks, [[1.0, 0.0]] * len(service.chunks))
    assert store.count == len(service.chunks)
    # 文档缩减后重建，旧条目（如被删除的源文件）应被清理
    smaller = service.chunks[:1]
    store.rebuild(smaller, [[1.0, 0.0]])
    assert store.count == 1


# ---------- Embedding 请求重试 ----------


def _embedding_provider(handler, retries: int = 2) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        "https://example.invalid/v1",
        "test-key",
        "text-embedding-v4",
        retries=retries,
        transport=httpx.MockTransport(handler),
    )


def _ok_response() -> httpx.Response:
    return httpx.Response(
        200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
    )


def test_embedding_retries_on_transient_failure():
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        if len(attempts) < 3:
            raise httpx.ConnectError("temporary network error")
        return _ok_response()

    provider = _embedding_provider(handler)
    assert provider.embed_query("hello") == [0.1, 0.2]
    assert len(attempts) == 3  # 初次 + 2 次重试


def test_embedding_gives_up_after_all_retries():
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        raise httpx.ConnectError("service down")

    provider = _embedding_provider(handler, retries=1)
    with pytest.raises(EmbeddingProviderError):
        provider.embed_query("hello")
    assert len(attempts) == 2  # 初次 + 1 次重试后放弃


def test_embedding_does_not_retry_on_4xx():
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        return httpx.Response(400, json={"error": "invalid api key"})

    provider = _embedding_provider(handler)
    with pytest.raises(EmbeddingProviderError):
        provider.embed_query("hello")
    assert len(attempts) == 1  # 参数/密钥错误不重试


def test_embedding_retries_on_5xx():
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.path)
        if len(attempts) < 2:
            return httpx.Response(503, json={"error": "overloaded"})
        return _ok_response()

    provider = _embedding_provider(handler)
    assert provider.embed_query("hello") == [0.1, 0.2]
    assert len(attempts) == 2
