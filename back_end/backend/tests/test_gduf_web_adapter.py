"""学院官网适配层测试（使用伪造客户端，不请求真实官网）。"""

from __future__ import annotations

from datetime import date

import pytest
from gduf_web_api import GdufError, InvalidPageError, NetworkError, ParseError
from gduf_web_api.models import ArticleSummary, PageResult

from app.adapters import gduf_web as gduf_adapter
from app.schemas.common import INVALID_PARAM, PARSE_ERROR, UPSTREAM_ERROR


def _article(title: str, published_at: date | None = None, summary: str | None = None) -> ArticleSummary:
    return ArticleSummary(
        title=title,
        url=f"https://ai.gduf.edu.cn/{title}",
        published_at=published_at,
        summary=summary,
    )


def _page(items: list[ArticleSummary], total: int | None = None) -> PageResult:
    return PageResult(
        items=tuple(items),
        page=1,
        total_pages=1,
        total_items=total if total is not None else len(items),
        source_url="https://ai.gduf.edu.cn/search",
    )


# ---- shape_search_result：结构整形与上下文裁剪 ----


def test_shape_search_result_keeps_core_fields() -> None:
    page = _page(
        [_article("学院新闻一", date(2026, 3, 1), "这是摘要"), _article("通知二")]
    )
    data = gduf_adapter.shape_search_result("新闻", page)
    assert data["query"] == "新闻"
    assert data["total"] == 2
    assert data["message"] == ""
    assert len(data["results"]) == 2
    first = data["results"][0]
    assert first["title"] == "学院新闻一"
    assert first["published_at"] == "2026-03-01"
    assert first["summary"] == "这是摘要"
    assert first["url"].startswith("https://")
    # 无日期的条目 published_at 应为 None 而非报错
    assert data["results"][1]["published_at"] is None


def test_shape_search_result_truncates_to_max_items() -> None:
    page = _page([_article(f"条目{i}") for i in range(25)], total=25)
    data = gduf_adapter.shape_search_result("测试", page)
    assert len(data["results"]) == gduf_adapter.SEARCH_MAX_ITEMS
    assert data["total"] == 25  # total 反映真实总数，不受裁剪影响


def test_shape_search_result_empty_gives_friendly_message() -> None:
    data = gduf_adapter.shape_search_result("不存在的词", _page([]))
    assert data["results"] == []
    assert data["message"]  # 空结果时返回友好提示而非空列表


# ---- 错误映射 ----


def test_translate_gduf_error_codes() -> None:
    assert gduf_adapter.translate_gduf_error(InvalidPageError("页码无效")).code == INVALID_PARAM
    assert gduf_adapter.translate_gduf_error(ParseError("结构不匹配")).code == PARSE_ERROR
    assert gduf_adapter.translate_gduf_error(NetworkError("连接失败")).code == UPSTREAM_ERROR
    assert gduf_adapter.translate_gduf_error(GdufError("其他")).code == UPSTREAM_ERROR


# ---- search_website：异常透传 + 客户端调用 ----


@pytest.mark.asyncio
async def test_search_website_shapes_and_forwards_keyword(monkeypatch) -> None:
    captured: dict = {}

    def fake_search_ai(keyword, page, *, client=None):
        captured.update(keyword=keyword, page=page, client=client)
        return _page([_article("人工智能专业介绍")])

    monkeypatch.setattr(gduf_adapter, "search_ai", fake_search_ai)
    monkeypatch.setattr(gduf_adapter, "get_client", lambda: object())

    data = await gduf_adapter.search_website("人工智能", page=2)
    assert captured["keyword"] == "人工智能"
    assert captured["page"] == 2
    assert data["results"][0]["title"] == "人工智能专业介绍"


@pytest.mark.asyncio
async def test_search_website_translates_network_error(monkeypatch) -> None:
    def fake_search_ai(keyword, page, *, client=None):
        raise NetworkError("连接超时")

    monkeypatch.setattr(gduf_adapter, "search_ai", fake_search_ai)
    monkeypatch.setattr(gduf_adapter, "get_client", lambda: object())

    from app.schemas.common import ApiError

    with pytest.raises(ApiError) as excinfo:
        await gduf_adapter.search_website("任意")
    assert excinfo.value.code == UPSTREAM_ERROR
