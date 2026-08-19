"""学术资源平台适配层：隔离 academic_api 与 Agent 工具。

职责（与 adapters/jwxt.py、adapters/gduf_web.py 保持一致的三段式）：
1. 把 academic_api 的异常映射为统一错误码（ApiError）。
2. 把 academic_api 的 dataclass 模型转换为可 JSON 序列化的 dict。
3. 同步 httpx 调用统一包装为 async（asyncio.to_thread），避免阻塞事件循环。

学术平台为公开 API、无需登录，模块内维护共享 AcademicClient 复用连接；
境外平台访问不稳定时可通过 ACADEMIC_PROXY 环境变量配置代理。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

from academic_api import (
    AcademicClient,
    AcademicError,
    AcademicSearchResult,
    NetworkError,
    ParseError,
    ValidationError,
)

from app.config import get_settings
from app.schemas.common import (
    INVALID_PARAM,
    PARSE_ERROR,
    UPSTREAM_ERROR,
    ApiError,
)

T = TypeVar("T")

# 搜索结果单次返回给模型的最大条目数，控制上下文窗口占用
SEARCH_MAX_ITEMS = 8
# 摘要进入模型上下文的最大字符数
ABSTRACT_LIMIT = 200

_client: AcademicClient | None = None


def get_client() -> AcademicClient:
    """获取共享的学术资源客户端（懒加载，代理取 ACADEMIC_PROXY 配置）。"""
    global _client
    if _client is None or _client.is_closed:
        settings = get_settings()
        proxy = settings.academic_proxy.strip() or None
        _client = AcademicClient(timeout=25.0, proxy=proxy)
    return _client


def reset_client() -> None:
    """关闭并重置共享客户端（供测试或应用关闭时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None


def translate_academic_error(exc: AcademicError) -> ApiError:
    """把学术包异常转换为带统一错误码的 ApiError。"""
    if isinstance(exc, ValidationError):
        return ApiError(INVALID_PARAM, str(exc), status_code=400)
    if isinstance(exc, ParseError):
        return ApiError(PARSE_ERROR, f"学术平台响应解析失败：{exc}", status_code=502)
    if isinstance(exc, NetworkError):
        return ApiError(UPSTREAM_ERROR, f"学术平台请求失败：{exc}", status_code=502)
    return ApiError(UPSTREAM_ERROR, f"学术资源检索失败：{exc}", status_code=502)


async def run_academic(func: Callable[[], T]) -> T:
    """在线程中执行同步学术 API 调用，并统一转换异常。"""
    try:
        return await asyncio.to_thread(func)
    except AcademicError as exc:
        raise translate_academic_error(exc) from exc


def shape_search_result(result: AcademicSearchResult) -> dict[str, Any]:
    """把 AcademicSearchResult 精简为供模型总结的紧凑结构。

    只保留标题/作者/年份/链接/下载入口，摘要进一步压缩，
    截断到 SEARCH_MAX_ITEMS 条，避免大量结构化数据挤占上下文窗口。
    """
    items = []
    for item in result.items[:SEARCH_MAX_ITEMS]:
        abstract = " ".join(item.abstract.split())
        if len(abstract) > ABSTRACT_LIMIT:
            abstract = abstract[:ABSTRACT_LIMIT] + "..."
        items.append(
            {
                "title": item.title,
                "authors": item.authors,
                "year": item.published_year,
                "source": item.source,
                "url": item.url,
                "pdf_url": item.pdf_url,
                "abstract": abstract,
            }
        )
    return {
        "query": result.query,
        "total": result.total,
        "results": items,
        "platform_messages": result.messages,
    }


async def search_academic_resources(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """跨平台搜索学术资源（arXiv、Semantic Scholar 等）。"""
    client = get_client()
    result = await run_academic(
        lambda: client.search(query, sources=sources, max_results=max_results)
    )
    return shape_search_result(result)
