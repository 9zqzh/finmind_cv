"""Internal adapter contract."""

from __future__ import annotations

from typing import Protocol

from gduf_web_api.models import (
    AiHome,
    ArticleSummary,
    ContentDetail,
    PageResult,
    PersonSummary,
)


class SourceAdapter(Protocol):
    code: str

    def get_home(self) -> AiHome: ...

    def get_articles(self, category: str, page: int = 1) -> PageResult[ArticleSummary]: ...

    def get_people(self, category: str, page: int = 1) -> PageResult[PersonSummary]: ...

    def get_content(self, category: str) -> ContentDetail: ...

    def get_detail(self, item_or_url: ArticleSummary | PersonSummary | str) -> ContentDetail: ...

    def search(self, keyword: str, page: int = 1) -> PageResult[ArticleSummary]: ...

