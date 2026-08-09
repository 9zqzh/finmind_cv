"""学院官网适配层：隔离 gduf_web_api 与 Agent 工具。

职责（与 adapters/jwxt.py 保持一致的三段式）：
1. 把 gduf_web_api 的异常映射为统一错误码（ApiError）。
2. 把 gduf_web_api 的 dataclass 模型转换为可 JSON 序列化的 dict。
3. 同步 httpx 调用统一包装为 async（asyncio.to_thread），避免阻塞事件循环。

与教务系统不同，学院官网与竞赛平台内容均为公开页面、无需登录，因此不复用
JwxtSession，而是在模块内维护一个共享的 GdufClient 以复用连接。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

from gduf_web_api import (
    GdufClient,
    GdufError,
    InvalidPageError,
    NetworkError,
    ParseError,
    get_aijspt_bslb,
    get_aijspt_bsxq,
    get_aijspt_stlb,
    get_aijspt_tzgg,
    get_ai_detail,
    search_ai,
)

from app.schemas.common import (
    INVALID_PARAM,
    PARSE_ERROR,
    UPSTREAM_ERROR,
    ApiError,
)

T = TypeVar("T")

# 搜索结果单次返回给模型的最大条目数，控制上下文窗口占用
SEARCH_MAX_ITEMS = 10

# 竞赛列表/通知单次返回给模型的最大条目数
COMPETITION_MAX_ITEMS = 10

# 比赛摘要与通知正文的截断长度，避免长文本挤占上下文
SUMMARY_LIMIT = 200

# 官网页面详情正文的截断长度（详情是用户主动要求查看的内容，比摘要保留更多）
DETAIL_CONTENT_LIMIT = 1500

# 官网公开内容无需鉴权，进程内复用同一客户端以减少建连开销
_client: GdufClient | None = None


def get_client() -> GdufClient:
    """获取共享的官网客户端（懒加载，关闭后自动重建）。"""
    global _client
    if _client is None or _client.is_closed:
        _client = GdufClient(timeout=15.0, retries=2)
    return _client


def reset_client() -> None:
    """关闭并重置共享客户端（供测试或应用关闭时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None


def translate_gduf_error(exc: GdufError) -> ApiError:
    """把官网包异常转换为带统一错误码的 ApiError。"""
    if isinstance(exc, InvalidPageError):
        return ApiError(INVALID_PARAM, str(exc), status_code=400)
    if isinstance(exc, ParseError):
        return ApiError(PARSE_ERROR, f"学院官网页面解析失败：{exc}", status_code=502)
    if isinstance(exc, NetworkError):
        return ApiError(UPSTREAM_ERROR, f"学院官网请求失败：{exc}", status_code=502)
    return ApiError(UPSTREAM_ERROR, f"学院官网异常：{exc}", status_code=502)


async def run_gduf(func: Callable[[], T]) -> T:
    """在线程中执行同步官网调用，并统一转换异常。"""
    try:
        return await asyncio.to_thread(func)
    except GdufError as exc:
        raise translate_gduf_error(exc) from exc
    except ValueError as exc:
        # 竞赛平台对无效的比赛 ID/URL 抛 ValueError，归一为参数错误
        raise ApiError(INVALID_PARAM, f"参数不合法：{exc}", status_code=400) from exc


def shape_search_result(keyword: str, page_result) -> dict[str, Any]:
    """把 PageResult[ArticleSummary] 精简为供模型总结的紧凑结构。

    只保留标题/链接/日期/摘要，且截断到 SEARCH_MAX_ITEMS 条，避免大量
    结构化数据挤占上下文窗口。
    """
    items = [
        {
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "summary": item.summary,
        }
        for item in page_result.items[:SEARCH_MAX_ITEMS]
    ]
    return {
        "query": keyword,
        "total": page_result.total_items,
        "page": page_result.page,
        "total_pages": page_result.total_pages,
        "results": items,
        "message": (
            "官网没有找到与该关键词相关的内容，建议换个关键词再试。"
            if not items
            else ""
        ),
    }


async def search_website(keyword: str, page: int = 1) -> dict[str, Any]:
    """关键词搜索学院官网公开内容（新闻、通知、活动、师资、专业介绍等）。"""
    client = get_client()
    page_result = await run_gduf(lambda: search_ai(keyword, page, client=client))
    return shape_search_result(keyword, page_result)


def shape_content_detail(detail) -> dict[str, Any]:
    """把 ContentDetail 精简为供模型总结的紧凑结构（正文按需截断）。"""
    content = (detail.content_text or "").strip()
    return {
        "title": detail.title,
        "url": detail.url,
        "published_at": detail.published_at.isoformat() if detail.published_at else None,
        "category": detail.category,
        "content": content[:DETAIL_CONTENT_LIMIT],
        "attachments": list(detail.attachments),
    }


async def get_website_detail(url: str) -> dict[str, Any]:
    """获取学院官网某个页面的正文内容（新闻/通知全文、教师个人主页、专业介绍等）。"""
    client = get_client()
    detail = await run_gduf(lambda: get_ai_detail(url, client=client))
    return shape_content_detail(detail)


# ---- 竞赛平台（aijspt）业务方法 ----


def shape_competition_summary(item) -> dict[str, Any]:
    """把 CompetitionSummary 精简为供模型总结的紧凑结构。"""
    summary = (item.summary or "").strip()
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "category": item.category,
        "year": item.competition_year,
        "recognition": item.recognition,
        "status": item.status,
        "department": item.department,
        "max_team_size": item.max_team_size,
        "registration_start_at": (
            item.registration_start_at.isoformat() if item.registration_start_at else None
        ),
        "registration_end_at": (
            item.registration_end_at.isoformat() if item.registration_end_at else None
        ),
        "official_url": item.official_url,
        "summary": summary[:SUMMARY_LIMIT],
    }


def shape_competition_list(list_result) -> dict[str, Any]:
    """把 ListResult[CompetitionSummary] 精简为供模型总结的紧凑结构。"""
    items = [shape_competition_summary(item) for item in list_result.items[:COMPETITION_MAX_ITEMS]]
    return {
        "total": list_result.total_items,
        "results": items,
        "message": (
            "竞赛平台没有找到符合条件的比赛，建议放宽筛选条件或稍后再试。"
            if not items
            else ""
        ),
    }


def shape_competition_detail(detail) -> dict[str, Any]:
    """把 CompetitionDetail 精简为供模型总结的紧凑结构。"""
    competition = detail.competition
    description = (detail.description_text or "").strip()
    return {
        "competition": shape_competition_summary(competition),
        "location": detail.location,
        "highlights": list(detail.highlights),
        "sub_tracks": list(detail.sub_tracks),
        "timeline": [
            {"date": phase.date, "label": phase.label, "description": phase.description}
            for phase in detail.timeline
        ],
        "attachments": [{"title": link.title, "url": link.url} for link in detail.attachments],
        "description": description[: SUMMARY_LIMIT * 3],
    }


def shape_notice_list(list_result) -> dict[str, Any]:
    """把 ListResult[Notice] 精简为供模型总结的紧凑结构。"""
    items = [
        {
            "title": item.title,
            "content": (item.content or "").strip()[:SUMMARY_LIMIT],
            "priority": item.priority,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "competition_title": item.competition_title,
        }
        for item in list_result.items[:COMPETITION_MAX_ITEMS]
    ]
    return {
        "total": list_result.total_items,
        "results": items,
        "message": "竞赛平台当前没有公开通知。" if not items else "",
    }


def shape_club_list(list_result) -> dict[str, Any]:
    """把 ListResult[ClubSummary] 精简为供模型总结的紧凑结构。"""
    items = [
        {
            "name": item.name,
            "direction": item.direction,
            "slogan": item.slogan,
            "description": (item.description or "").strip()[:SUMMARY_LIMIT],
            "url": item.url,
        }
        for item in list_result.items[:COMPETITION_MAX_ITEMS]
    ]
    return {
        "total": list_result.total_items,
        "results": items,
        "message": "竞赛平台当前没有公开的社团信息。" if not items else "",
    }


def shape_article_summary(item) -> dict[str, Any]:
    """将 ArticleSummary 转换为可序列化 dict。"""
    return {
        "title": item.title or "",
        "url": item.url or "",
        "published_at": item.published_at,
        "summary": (item.summary or "")[:SUMMARY_LIMIT],
        "image_url": item.image_url,
        "category": item.category or "",
    }


async def get_homepage_info() -> dict[str, Any]:
    """获取学院首页资讯（学院新闻、学术活动、学生活动、通知公告）。"""
    client = get_client()
    home = await run_gduf(lambda: client.get_home(source="ai"))
    return {
        "xyxw": [shape_article_summary(a) for a in home.xyxw],
        "xshuhd": [shape_article_summary(a) for a in home.xshuhd],
        "xshenghd": [shape_article_summary(a) for a in home.xshenghd],
        "tzgg": [shape_article_summary(a) for a in home.tzgg],
    }


async def get_competitions(
    *,
    year: int | None = None,
    status: str | None = None,
    category: str | None = None,
    department: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    """查询竞赛平台的比赛列表（支持年份/状态/分类/学院/关键词筛选）。"""
    client = get_client()
    list_result = await run_gduf(
        lambda: get_aijspt_bslb(
            year=year,
            status=status,
            category=category,
            department=department,
            keyword=keyword,
            client=client,
        )
    )
    return shape_competition_list(list_result)


async def get_competition_detail(competition_or_id) -> dict[str, Any]:
    """查询单场比赛的详情（接受比赛对象、UUID、相对路径或同域 URL）。"""
    client = get_client()
    detail = await run_gduf(lambda: get_aijspt_bsxq(competition_or_id, client=client))
    return shape_competition_detail(detail)


async def get_competition_notices(limit: int = 20) -> dict[str, Any]:
    """查询竞赛平台的公开通知公告。"""
    client = get_client()
    list_result = await run_gduf(lambda: get_aijspt_tzgg(limit, client=client))
    return shape_notice_list(list_result)


async def get_competition_clubs() -> dict[str, Any]:
    """查询竞赛平台公开的学生竞赛社团概览。"""
    client = get_client()
    list_result = await run_gduf(lambda: get_aijspt_stlb(client=client))
    return shape_club_list(list_result)
