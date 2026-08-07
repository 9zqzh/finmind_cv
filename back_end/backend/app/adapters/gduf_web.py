"""学院官网适配层：隔离 gduf_web_api 与 Agent 工具。

职责（与 adapters/jwxt.py 保持一致的三段式）：
1. 把 gduf_web_api 的异常映射为统一错误码（ApiError）。
2. 把 gduf_web_api 的 dataclass 模型转换为可 JSON 序列化的 dict。
3. 同步 httpx 调用统一包装为 async（asyncio.to_thread），避免阻塞事件循环。

与教务系统不同，学院官网内容为公开页面、无需登录，因此不复用 JwxtSession，
而是在模块内维护一个共享的 GdufClient 以复用连接。
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
