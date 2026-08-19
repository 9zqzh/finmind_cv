"""模块级便捷函数：不管理客户端生命周期的单次搜索入口。"""

from __future__ import annotations

from academic_api.client import AcademicClient
from academic_api.models import AcademicSearchResult


def search_academic(
    query: str,
    *,
    sources: list[str] | None = None,
    max_results: int = 10,
    client: AcademicClient | None = None,
    proxy: str | None = None,
) -> AcademicSearchResult:
    """搜索学术资源（跨平台聚合）。

    Args:
        query: 搜索关键词。
        sources: 平台标识列表，None 为全部平台。
        max_results: 每平台最大条目数。
        client: 复用的 AcademicClient；None 时临时创建并自动关闭。
        proxy: 仅在临时创建客户端时生效的代理地址。
    """
    if isinstance(client, AcademicClient):
        return client.search(query, sources=sources, max_results=max_results)
    with AcademicClient(proxy=proxy) as temp:
        return temp.search(query, sources=sources, max_results=max_results)
