"""Findpapers 学术资源适配层：隔离第三方模型与 Agent 工具。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, TypeVar

import findpapers
from findpapers import (
    ConnectorError,
    FindpapersError,
    InvalidParameterError,
    QueryValidationError,
    UnsupportedQueryError,
)
from findpapers.connectors.connector_base import ConnectorBase

from app.config import Settings, get_settings
from app.schemas.common import INVALID_PARAM, UPSTREAM_ERROR, ApiError

T = TypeVar("T")

SEARCH_MAX_ITEMS = 8
ABSTRACT_LIMIT = 200
SEARCH_WORKERS = 4
SUPPORTED_DATABASES = frozenset(
    {"arxiv", "openalex", "pubmed", "semantic_scholar", "ieee", "scopus", "wos"}
)
KEY_REQUIRED_DATABASES = {
    "openalex": "findpapers_openalex_api_token",
    "ieee": "findpapers_ieee_api_token",
    "scopus": "findpapers_scopus_api_token",
    "wos": "findpapers_wos_api_token",
}

_engine: findpapers.Engine | None = None


def _optional(value: str) -> str | None:
    value = value.strip()
    return value or None


def _configure_findpapers_transport(settings: Settings) -> None:
    """配置固定版本 Findpapers 未公开为 Engine 参数的请求边界。"""
    ConnectorBase._timeout = settings.findpapers_request_timeout_seconds
    ConnectorBase._max_retries = settings.findpapers_max_retries
    ConnectorBase._max_rate_limit_retries = settings.findpapers_rate_limit_retries


def get_enabled_databases(settings: Settings | None = None) -> list[str]:
    """解析、校验配置的 Findpapers 数据库白名单。"""
    settings = settings or get_settings()
    databases = list(
        dict.fromkeys(
            part.strip().lower()
            for part in settings.findpapers_databases.split(",")
            if part.strip()
        )
    )
    if not databases:
        raise ApiError(
            INVALID_PARAM,
            "FINDPAPERS_DATABASES 至少启用一个数据源",
            status_code=500,
        )
    unknown = sorted(set(databases) - SUPPORTED_DATABASES)
    if unknown:
        raise ApiError(
            INVALID_PARAM,
            f"FINDPAPERS_DATABASES 包含未知数据源：{'、'.join(unknown)}",
            status_code=500,
        )
    missing_keys = [
        database
        for database in databases
        if database in KEY_REQUIRED_DATABASES
        and not _optional(str(getattr(settings, KEY_REQUIRED_DATABASES[database])))
    ]
    if missing_keys:
        raise ApiError(
            INVALID_PARAM,
            f"已启用但未配置 API Key 的数据源：{'、'.join(missing_keys)}",
            status_code=500,
        )
    return databases


def _resolve_databases(settings: Settings, sources: list[str] | None) -> list[str]:
    enabled = get_enabled_databases(settings)
    if sources is None:
        return enabled
    requested = list(
        dict.fromkeys(source.strip().lower() for source in sources if source.strip())
    )
    if not requested:
        raise ApiError(INVALID_PARAM, "sources 至少包含一个数据源", status_code=400)
    disabled = sorted(set(requested) - set(enabled))
    if disabled:
        raise ApiError(
            INVALID_PARAM,
            f"请求的数据源未在 FINDPAPERS_DATABASES 中启用：{'、'.join(disabled)}",
            status_code=400,
        )
    return requested


def get_engine() -> findpapers.Engine:
    """获取共享的 Findpapers Engine，并注入项目统一配置。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _configure_findpapers_transport(settings)
        _engine = findpapers.Engine(
            ieee_api_key=_optional(settings.findpapers_ieee_api_token),
            scopus_api_key=_optional(settings.findpapers_scopus_api_token),
            pubmed_api_key=_optional(settings.findpapers_pubmed_api_token),
            openalex_api_key=_optional(settings.findpapers_openalex_api_token),
            semantic_scholar_api_key=_optional(
                settings.findpapers_semantic_scholar_api_token
            ),
            wos_api_key=_optional(settings.findpapers_wos_api_token),
            email=_optional(settings.findpapers_email),
            proxy=_optional(settings.findpapers_proxy),
            ssl_verify=settings.findpapers_ssl_verify,
        )
    return _engine


def reset_engine() -> None:
    """重置共享 Engine（供配置切换和测试使用）。"""
    global _engine
    _engine = None


def translate_findpapers_error(exc: FindpapersError) -> ApiError:
    """把 Findpapers 异常转换为项目统一的 ApiError。"""
    if isinstance(
        exc, (QueryValidationError, UnsupportedQueryError, InvalidParameterError)
    ):
        return ApiError(INVALID_PARAM, str(exc), status_code=400)
    if isinstance(exc, ConnectorError):
        return ApiError(UPSTREAM_ERROR, f"学术平台请求失败：{exc}", status_code=502)
    return ApiError(UPSTREAM_ERROR, f"学术资源检索失败：{exc}", status_code=502)


async def run_findpapers(func: Callable[[], T], timeout_seconds: float) -> T:
    """在线程中执行同步 Findpapers 调用，并统一转换异常。"""
    try:
        return await asyncio.wait_for(asyncio.to_thread(func), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise ApiError(
            UPSTREAM_ERROR,
            f"学术资源检索超过 {timeout_seconds:g} 秒，已停止等待",
            status_code=504,
        ) from exc
    except FindpapersError as exc:
        raise translate_findpapers_error(exc) from exc


def _author_name(author: Any) -> str:
    if isinstance(author, dict):
        return str(author.get("name") or "").strip()
    return str(getattr(author, "name", author) or "").strip()


def _publication_year(publication_date: Any) -> int | None:
    if isinstance(publication_date, (date, datetime)):
        return publication_date.year
    if publication_date:
        try:
            return int(str(publication_date)[:4])
        except ValueError:
            pass
    return None


def _source_names(paper: Any) -> list[str]:
    values = getattr(paper, "found_in", None) or []
    return sorted({str(value).strip() for value in values if str(value).strip()})


def shape_search_result(result: Any) -> dict[str, Any]:
    """把 SearchResult 精简为供模型总结的兼容结构。"""
    papers = list(getattr(result, "papers", None) or [])
    items: list[dict[str, Any]] = []
    for paper in papers[:SEARCH_MAX_ITEMS]:
        abstract = " ".join(str(getattr(paper, "abstract", None) or "").split())
        if len(abstract) > ABSTRACT_LIMIT:
            abstract = abstract[:ABSTRACT_LIMIT] + "..."
        authors = [
            name
            for name in (
                _author_name(author)
                for author in (getattr(paper, "authors", None) or [])
            )
            if name
        ]
        items.append(
            {
                "title": str(getattr(paper, "title", "")),
                "authors": authors,
                "year": _publication_year(getattr(paper, "publication_date", None)),
                "source": ", ".join(_source_names(paper)),
                "url": getattr(paper, "url", None),
                "pdf_url": getattr(paper, "pdf_url", None),
                "abstract": abstract,
            }
        )

    failed_databases = list(getattr(result, "failed_databases", None) or [])
    return {
        "query": str(getattr(result, "query", "")),
        "total": len(papers),
        "results": items,
        "platform_messages": [
            f"{database}：搜索失败" for database in failed_databases
        ],
    }


def _all_databases_failed(result: Any) -> bool:
    if getattr(result, "papers", None):
        return False
    databases = set(getattr(result, "databases", None) or [])
    failed = set(getattr(result, "failed_databases", None) or [])
    return bool(databases) and databases <= failed


async def search_academic_resources(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """使用 Findpapers 跨平台搜索论文与文献。"""
    settings = get_settings()
    databases = _resolve_databases(settings, sources)
    engine = get_engine()
    result = await run_findpapers(
        lambda: engine.search(
            query,
            databases=databases,
            max_papers_per_database=max_results,
            num_workers=SEARCH_WORKERS,
            show_progress=False,
            enrichment_databases=[],
        ),
        timeout_seconds=settings.findpapers_search_timeout_seconds,
    )
    if _all_databases_failed(result):
        failed = "、".join(getattr(result, "failed_databases", None) or [])
        raise ApiError(
            UPSTREAM_ERROR,
            f"学术平台请求全部失败：{failed}",
            status_code=502,
        )
    return shape_search_result(result)


__all__ = [
    "ABSTRACT_LIMIT",
    "SEARCH_MAX_ITEMS",
    "get_engine",
    "get_enabled_databases",
    "reset_engine",
    "search_academic_resources",
    "shape_search_result",
    "translate_findpapers_error",
]
