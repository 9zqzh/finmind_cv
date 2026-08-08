"""知识库检索测试。"""

from __future__ import annotations

import json

from app.knowledge.chroma_store import ChromaVectorStore
from app.knowledge import KnowledgeService


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
        self.rows.extend(
            {
                "id": identifier,
                "document": document,
                "metadata": metadata,
                "embedding": embedding,
            }
            for identifier, document, metadata, embedding in zip(
                ids, documents, metadatas, embeddings
            )
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
    assert service.vector_enabled is False
    assert results[0].source == "缓考制度.md"
