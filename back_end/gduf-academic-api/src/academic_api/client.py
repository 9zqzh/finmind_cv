"""学术资源统一客户端：聚合调度各平台适配器，提供单一搜索入口。"""

from __future__ import annotations

import httpx

from academic_api.errors import AcademicError, ValidationError
from academic_api.models import AcademicResource, AcademicSearchResult
from academic_api.platforms import get_platform, list_platforms

DEFAULT_USER_AGENT = "gduf-academic-api/0.1 (+https://github.com/9zqzh/gduf-college-assistant)"


class AcademicClient:
    """聚合学术平台检索的同步客户端（公开 API，无需登录）。

    用法::

        with AcademicClient() as client:
            result = client.search("transformer")
    """

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        proxy: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValidationError("timeout 必须大于 0")
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            proxy=proxy,
            transport=transport,
        )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AcademicClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        max_results: int = 10,
    ) -> AcademicSearchResult:
        """跨平台搜索学术资源。

        Args:
            query: 搜索关键词。
            sources: 平台标识列表（如 ["arxiv"]）；None 表示搜索全部已注册平台。
            max_results: 每个平台返回的最大条目数（1-50）。

        Raises:
            ValidationError: 关键词为空、平台名未知或 max_results 越界。
            AcademicError: 所有平台均失败时抛出（附带各平台失败原因）。
        """
        if not query or not query.strip():
            raise ValidationError("搜索关键词不能为空")
        if not 1 <= max_results <= 50:
            raise ValidationError("max_results 必须在 1 到 50 之间")

        if sources is None:
            sources = list_platforms()
        unknown = [s for s in sources if s not in list_platforms()]
        if unknown:
            raise ValidationError(
                f"未知平台 {unknown}，可用平台：{list_platforms()}"
            )

        items: list[AcademicResource] = []
        messages: list[str] = []
        for source in sources:
            try:
                platform = get_platform(source, self._client)
                found = platform.search(query, max_results)
                items.extend(found)
                messages.append(f"{platform.display_name} 返回 {len(found)} 条")
            except AcademicError as exc:
                # 单平台失败不影响其他平台，记录原因供上层提示
                messages.append(f"{source} 检索失败：{exc}")

        if not items:
            detail = "；".join(messages) or "无可用平台"
            raise AcademicError(f"所有学术平台均未能返回结果（{detail}）")

        return AcademicSearchResult(
            query=query,
            total=len(items),
            items=items,
            messages=messages,
        )
