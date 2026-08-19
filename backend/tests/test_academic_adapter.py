"""学术资源适配层测试（使用伪造客户端，不发起真实请求）。"""

from __future__ import annotations

import pytest
from academic_api import (
    AcademicError,
    AcademicResource,
    AcademicSearchResult,
    NetworkError,
    ParseError,
    ValidationError,
)

from app.adapters import academic as academic_adapter
from app.schemas.common import INVALID_PARAM, PARSE_ERROR, UPSTREAM_ERROR, ApiError


def _item(title: str, source: str = "arxiv", abstract: str = "摘要") -> AcademicResource:
    return AcademicResource(
        title=title,
        authors=["作者甲", "作者乙"],
        abstract=abstract,
        url=f"https://example.org/{title}",
        source=source,
        pdf_url=f"https://example.org/{title}.pdf",
        published_year=2024,
    )


def _result(items: list[AcademicResource]) -> AcademicSearchResult:
    return AcademicSearchResult(
        query="深度学习",
        total=len(items),
        items=items,
        messages=[f"ok:{len(items)}"],
    )


# ---- shape_search_result：结构整形与上下文裁剪 ----


def test_shape_search_result_keeps_core_fields() -> None:
    data = academic_adapter.shape_search_result(_result([_item("论文一")]))
    assert data["query"] == "深度学习"
    assert data["total"] == 1
    first = data["results"][0]
    assert first["title"] == "论文一"
    assert first["authors"] == ["作者甲", "作者乙"]
    assert first["year"] == 2024
    assert first["source"] == "arxiv"
    assert first["url"].startswith("https://")
    assert first["pdf_url"].endswith(".pdf")
    assert first["abstract"] == "摘要"
    assert data["platform_messages"] == ["ok:1"]


def test_shape_search_result_truncates_to_max_items() -> None:
    items = [_item(f"论文{i}") for i in range(20)]
    data = academic_adapter.shape_search_result(_result(items))
    assert len(data["results"]) == academic_adapter.SEARCH_MAX_ITEMS
    assert data["total"] == 20  # total 反映真实总数，不受裁剪影响


def test_shape_search_result_clips_long_abstract() -> None:
    long_abstract = "字" * 500
    data = academic_adapter.shape_search_result(
        _result([_item("长摘要", abstract=long_abstract)])
    )
    abstract = data["results"][0]["abstract"]
    assert len(abstract) <= academic_adapter.ABSTRACT_LIMIT + 3
    assert abstract.endswith("...")


# ---- 错误映射 ----


def test_translate_academic_error_codes() -> None:
    assert (
        academic_adapter.translate_academic_error(ValidationError("关键词为空")).code
        == INVALID_PARAM
    )
    assert (
        academic_adapter.translate_academic_error(ParseError("结构异常")).code
        == PARSE_ERROR
    )
    assert (
        academic_adapter.translate_academic_error(NetworkError("连接失败")).code
        == UPSTREAM_ERROR
    )
    assert (
        academic_adapter.translate_academic_error(AcademicError("其他")).code
        == UPSTREAM_ERROR
    )


# ---- search_academic_resources：客户端调用与异常透传 ----


class _FakeClient:
    """记录调用参数的伪造客户端。"""

    def __init__(self, result: AcademicSearchResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple] = []

    def search(self, query, *, sources=None, max_results=10):
        self.calls.append((query, sources, max_results))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.mark.asyncio
async def test_search_academic_resources_shapes_result(monkeypatch) -> None:
    fake = _FakeClient(_result([_item("论文一", source="semantic_scholar")]))
    monkeypatch.setattr(academic_adapter, "get_client", lambda: fake)

    data = await academic_adapter.search_academic_resources(
        "深度学习", sources=["semantic_scholar"], max_results=3
    )
    assert fake.calls == [("深度学习", ["semantic_scholar"], 3)]
    assert data["results"][0]["title"] == "论文一"
    assert data["results"][0]["source"] == "semantic_scholar"


@pytest.mark.asyncio
async def test_search_academic_resources_translates_network_error(monkeypatch) -> None:
    fake = _FakeClient(NetworkError("连接超时"))
    monkeypatch.setattr(academic_adapter, "get_client", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert excinfo.value.status_code == 502


@pytest.mark.asyncio
async def test_search_academic_resources_translates_validation_error(monkeypatch) -> None:
    fake = _FakeClient(ValidationError("未知平台"))
    monkeypatch.setattr(academic_adapter, "get_client", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意", sources=["ieee"])
    assert excinfo.value.code == INVALID_PARAM
