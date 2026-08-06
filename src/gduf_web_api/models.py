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

