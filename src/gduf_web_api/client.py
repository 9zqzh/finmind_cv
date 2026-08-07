"""Shared synchronous HTTP client and source dispatch."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

import httpx

from gduf_web_api.errors import NetworkError, UnsupportedSourceError
from gduf_web_api.models import (
    AiHome,
    ArticleSummary,
    ClubSummary,
    CompetitionDetail,
    CompetitionSummary,
    ContentDetail,
    ListResult,
    Notice,
    PageResult,
    PersonSummary,
)

if TYPE_CHECKING:
    from gduf_web_api.adapters.base import CompetitionSourceAdapter, SourceAdapter

DEFAULT_USER_AGENT = "gduf-web-api/0.2.0 (+https://pypi.org/project/gduf-web-api/)"


class GdufClient:
    """Reusable synchronous client for registered GDÜF website sources."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.retries = retries
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent or DEFAULT_USER_AGENT},
            transport=transport,
        )
        from gduf_web_api.adapters.ai import AiAdapter
        from gduf_web_api.adapters.aijspt import AijsptAdapter

        self._adapters: dict[str, SourceAdapter] = {"ai": AiAdapter(self)}
        self._competition_adapters: dict[str, CompetitionSourceAdapter] = {
            "aijspt": AijsptAdapter(self)
        }

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GdufClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _adapter(self, source: str) -> SourceAdapter:
        try:
            return self._adapters[source]
        except KeyError as exc:
            raise UnsupportedSourceError(f"unsupported source: {source!r}") from exc

    def _competition_adapter(self, source: str) -> CompetitionSourceAdapter:
        try:
            return self._competition_adapters[source]
        except KeyError as exc:
            raise UnsupportedSourceError(f"unsupported competition source: {source!r}") from exc

    def _request_text(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> tuple[str, str]:
        if self.is_closed:
            raise NetworkError("the client is already closed")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._client.request(method, url, data=data, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable HTTP status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "charset=" not in content_type:
                    response.encoding = "utf-8"
                return response.text, str(response.url)
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = isinstance(exc, httpx.RequestError)
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    retryable = status == 429 or status >= 500
                if not retryable or attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
        raise NetworkError(f"failed to fetch {url}: {last_error}") from last_error

    def get_home(self, source: str = "ai") -> AiHome:
        return self._adapter(source).get_home()

    def get_articles(
        self, category: str, page: int = 1, *, source: str = "ai"
    ) -> PageResult[ArticleSummary]:
        return self._adapter(source).get_articles(category, page)

    def get_people(
        self, category: str, page: int = 1, *, source: str = "ai"
    ) -> PageResult[PersonSummary]:
        return self._adapter(source).get_people(category, page)

    def get_content(self, category: str, *, source: str = "ai") -> ContentDetail:
        return self._adapter(source).get_content(category)

    def get_detail(
        self,
        item_or_url: ArticleSummary | PersonSummary | str,
        *,
        source: str = "ai",
    ) -> ContentDetail:
        return self._adapter(source).get_detail(item_or_url)

    def search(
        self, keyword: str, page: int = 1, *, source: str = "ai"
    ) -> PageResult[ArticleSummary]:
        return self._adapter(source).search(keyword, page)

    def get_competitions(
        self,
        *,
        year: int | None = None,
        status: str | None = None,
        category: str | None = None,
        department: str | None = None,
        keyword: str | None = None,
        source: str = "aijspt",
    ) -> ListResult[CompetitionSummary]:
        return self._competition_adapter(source).get_competitions(
            year=year,
            status=status,
            category=category,
            department=department,
            keyword=keyword,
        )

    def get_competition_detail(
        self,
        competition_or_id: CompetitionSummary | str,
        *,
        source: str = "aijspt",
    ) -> CompetitionDetail:
        return self._competition_adapter(source).get_competition_detail(competition_or_id)

    def get_notices(self, limit: int = 20, *, source: str = "aijspt") -> ListResult[Notice]:
        return self._competition_adapter(source).get_notices(limit)

    def get_clubs(self, *, source: str = "aijspt") -> ListResult[ClubSummary]:
        return self._competition_adapter(source).get_clubs()
