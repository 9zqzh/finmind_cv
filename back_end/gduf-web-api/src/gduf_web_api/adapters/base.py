"""Internal adapter contract."""

from __future__ import annotations

from typing import Protocol

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


class SourceAdapter(Protocol):
    code: str

    def get_home(self) -> AiHome: ...

    def get_articles(self, category: str, page: int = 1) -> PageResult[ArticleSummary]: ...

    def get_people(self, category: str, page: int = 1) -> PageResult[PersonSummary]: ...

    def get_content(self, category: str) -> ContentDetail: ...

    def get_detail(self, item_or_url: ArticleSummary | PersonSummary | str) -> ContentDetail: ...

    def search(self, keyword: str, page: int = 1) -> PageResult[ArticleSummary]: ...


class CompetitionSourceAdapter(Protocol):
    """Contract for public competition-information platforms."""

    code: str

    def get_competitions(
        self,
        *,
        year: int | None = None,
        status: str | None = None,
        category: str | None = None,
        department: str | None = None,
        keyword: str | None = None,
    ) -> ListResult[CompetitionSummary]: ...

    def get_competition_detail(
        self, competition_or_id: CompetitionSummary | str
    ) -> CompetitionDetail: ...

    def get_notices(self, limit: int = 20) -> ListResult[Notice]: ...

    def get_clubs(self) -> ListResult[ClubSummary]: ...
