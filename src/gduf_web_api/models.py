"""Typed response models shared by all website sources."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


class JsonModel:
    """Mixin that converts a response model into JSON-compatible values."""

    def to_dict(self) -> dict[str, Any]:
        value = _json_value(self)
        return cast(dict[str, Any], value)


@dataclass(frozen=True, slots=True)
class ArticleSummary(JsonModel):
    """A single article-like item from a list or search result."""

    title: str
    url: str
    published_at: date | None = None
    summary: str | None = None
    image_url: str | None = None
    category: str | None = None
    source: str = "ai"


@dataclass(frozen=True, slots=True)
class PersonSummary(JsonModel):
    """A leader, teacher, or support staff member."""

    name: str
    url: str
    role: str | None = None
    responsibility: str | None = None
    image_url: str | None = None
    group: str | None = None
    source: str = "ai"


@dataclass(frozen=True, slots=True)
class PageResult(JsonModel, Generic[T]):
    """A page of source-controlled results."""

    items: tuple[T, ...]
    page: int
    total_pages: int
    total_items: int
    source_url: str


@dataclass(frozen=True, slots=True)
class ListResult(JsonModel, Generic[T]):
    """An unpaginated collection returned by a source."""

    items: tuple[T, ...]
    total_items: int
    source_url: str


@dataclass(frozen=True, slots=True)
class ContentDetail(JsonModel):
    """Normalized content from an article, profile, or static page."""

    title: str
    url: str
    content_text: str
    content_html: str
    images: tuple[str, ...] = ()
    attachments: tuple[str, ...] = ()
    published_at: date | None = None
    attribution: str | None = None
    view_count: int | None = None
    previous_url: str | None = None
    next_url: str | None = None
    category: str | None = None
    kind: str = "content"
    source: str = "ai"


@dataclass(frozen=True, slots=True)
class AiHome(JsonModel):
    """The four public information blocks shown on the AI college home page."""

    xyxw: tuple[ArticleSummary, ...]
    xshuhd: tuple[ArticleSummary, ...]
    xshenghd: tuple[ArticleSummary, ...]
    tzgg: tuple[ArticleSummary, ...]
    source_url: str


@dataclass(frozen=True, slots=True)
class CompetitionSummary(JsonModel):
    """A competition published by the AI college competition platform."""

    id: str
    title: str
    url: str
    category: str
    competition_year: int
    recognition: str
    status: str
    summary: str
    department: str
    registration_mode: str
    max_team_size: int
    max_advisors: int
    registration_start_at: datetime | None = None
    registration_end_at: datetime | None = None
    event_start_at: datetime | None = None
    event_end_at: datetime | None = None
    official_url: str | None = None
    wechat_article_url: str | None = None
    cta_type: str | None = None
    cta_label_override: str | None = None
    source: str = "aijspt"


@dataclass(frozen=True, slots=True)
class CompetitionTimelineItem(JsonModel):
    """A date or phase shown in a competition timeline."""

    date: str
    label: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CompetitionFaq(JsonModel):
    """A question and answer published on a competition detail page."""

    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class ResourceLink(JsonModel):
    """A titled attachment or related page."""

    title: str
    url: str


@dataclass(frozen=True, slots=True)
class CompetitionDetail(JsonModel):
    """Rich public information for one competition."""

    competition: CompetitionSummary
    description_text: str
    description_html: str
    location: str | None = None
    highlights: tuple[str, ...] = ()
    sub_tracks: tuple[str, ...] = ()
    timeline: tuple[CompetitionTimelineItem, ...] = ()
    faqs: tuple[CompetitionFaq, ...] = ()
    attachments: tuple[ResourceLink, ...] = ()
    related_questions: tuple[ResourceLink, ...] = ()
    experience_articles: tuple[ResourceLink, ...] = ()
    source: str = "aijspt"

    @property
    def id(self) -> str:
        return self.competition.id

    @property
    def title(self) -> str:
        return self.competition.title

    @property
    def url(self) -> str:
        return self.competition.url


@dataclass(frozen=True, slots=True)
class Notice(JsonModel):
    """A public platform-wide or competition-specific notice."""

    id: str
    title: str
    content: str
    priority: str
    delivery_scope: str
    allow_popup: bool
    published_at: datetime
    competition_id: str | None = None
    competition_title: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    source: str = "aijspt"


@dataclass(frozen=True, slots=True)
class ClubSummary(JsonModel):
    """A student competition club shown on the platform."""

    slug: str
    name: str
    direction: str
    slogan: str
    description: str
    url: str
    source: str = "aijspt"
