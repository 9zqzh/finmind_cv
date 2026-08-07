"""学院官网适配层测试（使用伪造客户端，不请求真实官网）。"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from gduf_web_api import GdufError, InvalidPageError, NetworkError, ParseError
from gduf_web_api.models import (
    ArticleSummary,
    ClubSummary,
    CompetitionDetail,
    CompetitionSummary,
    CompetitionTimelineItem,
    ListResult,
    Notice,
    PageResult,
    ResourceLink,
)

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


# ---- 竞赛平台（aijspt）：整形与裁剪 ----


def _competition(title: str = "软件设计大赛", summary: str = "比赛简介") -> CompetitionSummary:
    return CompetitionSummary(
        id="uuid-1",
        title=title,
        url="https://ai-data-competitions.cn/competitions/uuid-1",
        category="软件设计类",
        competition_year=2026,
        recognition="省级",
        status="registration_open",
        summary=summary,
        department="大数据与人工智能学院",
        registration_mode="线上报名",
        max_team_size=5,
        max_advisors=2,
        registration_start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        registration_end_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def _competition_list(items: list[CompetitionSummary]) -> ListResult:
    return ListResult(
        items=tuple(items),
        total_items=len(items),
        source_url="https://ai-data-competitions.cn/api/competitions",
    )


def test_shape_competition_list_keeps_core_fields() -> None:
    data = gduf_adapter.shape_competition_list(_competition_list([_competition()]))
    assert data["total"] == 1
    assert data["message"] == ""
    first = data["results"][0]
    assert first["title"] == "软件设计大赛"
    assert first["year"] == 2026
    assert first["status"] == "registration_open"
    assert first["registration_end_at"].startswith("2026-04-01")
    assert first["summary"] == "比赛简介"


def test_shape_competition_list_truncates_and_trims_summary() -> None:
    long_summary = "长" * (gduf_adapter.SUMMARY_LIMIT + 50)
    items = [_competition(f"比赛{i}") for i in range(15)] + [_competition("长摘要", long_summary)]
    data = gduf_adapter.shape_competition_list(_competition_list(items))
    assert len(data["results"]) == gduf_adapter.COMPETITION_MAX_ITEMS
    assert data["total"] == 16  # total 反映真实总数，不受裁剪影响


def test_shape_competition_list_empty_gives_friendly_message() -> None:
    data = gduf_adapter.shape_competition_list(_competition_list([]))
    assert data["results"] == []
    assert data["message"]


def test_shape_competition_detail_keeps_timeline_and_attachments() -> None:
    detail = CompetitionDetail(
        competition=_competition(),
        description_text="比赛详细介绍",
        description_html="<p>比赛详细介绍</p>",
        location="线上",
        highlights=("省级认定",),
        timeline=(CompetitionTimelineItem(date="2026-04-01", label="报名截止"),),
        attachments=(ResourceLink(title="参赛手册", url="https://example.cn/handbook.pdf"),),
    )
    data = gduf_adapter.shape_competition_detail(detail)
    assert data["competition"]["title"] == "软件设计大赛"
    assert data["location"] == "线上"
    assert data["highlights"] == ["省级认定"]
    assert data["timeline"][0]["label"] == "报名截止"
    assert data["attachments"][0]["title"] == "参赛手册"
    assert data["description"] == "比赛详细介绍"


def test_shape_notice_and_club_lists() -> None:
    notices = ListResult(
        items=(
            Notice(
                id="n1",
                title="报名开始",
                content="报名已开始",
                priority="high",
                delivery_scope="all",
                allow_popup=True,
                published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ),
        total_items=1,
        source_url="https://ai-data-competitions.cn/api/notices/published",
    )
    data = gduf_adapter.shape_notice_list(notices)
    assert data["results"][0]["title"] == "报名开始"
    assert data["results"][0]["published_at"].startswith("2026-03-01")

    clubs = ListResult(
        items=(
            ClubSummary(
                slug="club-a",
                name="智能算法社",
                direction="算法",
                slogan="以赛促学",
                description="社团简介",
                url="https://ai-data-competitions.cn/clubs/club-a",
            ),
        ),
        total_items=1,
        source_url="https://ai-data-competitions.cn/clubs",
    )
    data = gduf_adapter.shape_club_list(clubs)
    assert data["results"][0]["name"] == "智能算法社"
    assert gduf_adapter.shape_notice_list(ListResult(items=(), total_items=0, source_url="x"))["message"]
    assert gduf_adapter.shape_club_list(ListResult(items=(), total_items=0, source_url="x"))["message"]


# ---- 竞赛平台：参数转发与异常转换 ----


@pytest.mark.asyncio
async def test_get_competitions_forwards_filters(monkeypatch) -> None:
    captured: dict = {}

    def fake_bslb(*, year=None, status=None, category=None, department=None, keyword=None, client=None):
        captured.update(
            year=year, status=status, category=category,
            department=department, keyword=keyword, client=client,
        )
        return _competition_list([_competition()])

    monkeypatch.setattr(gduf_adapter, "get_aijspt_bslb", fake_bslb)
    monkeypatch.setattr(gduf_adapter, "get_client", lambda: object())

    data = await gduf_adapter.get_competitions(year=2026, status="registration_open", keyword="软件")
    assert captured["year"] == 2026
    assert captured["status"] == "registration_open"
    assert captured["keyword"] == "软件"
    assert data["results"][0]["title"] == "软件设计大赛"


@pytest.mark.asyncio
async def test_get_competition_detail_translates_error(monkeypatch) -> None:
    def fake_bsxq(competition_or_id, *, client=None):
        raise NetworkError("连接失败")

    monkeypatch.setattr(gduf_adapter, "get_aijspt_bsxq", fake_bsxq)
    monkeypatch.setattr(gduf_adapter, "get_client", lambda: object())

    from app.schemas.common import ApiError

    with pytest.raises(ApiError) as excinfo:
        await gduf_adapter.get_competition_detail("uuid-1")
    assert excinfo.value.code == UPSTREAM_ERROR
