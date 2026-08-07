"""Adapter for the AI college competition and Q&A platform."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse
from uuid import UUID

from bs4 import BeautifulSoup, Tag

from gduf_web_api.errors import ParseError
from gduf_web_api.models import (
    ClubSummary,
    CompetitionDetail,
    CompetitionFaq,
    CompetitionSummary,
    CompetitionTimelineItem,
    ListResult,
    Notice,
    ResourceLink,
)

if TYPE_CHECKING:
    from gduf_web_api.client import GdufClient

BASE_URL = "https://ai-data-competitions.cn/"
_DETAIL_PATH_RE = re.compile(
    r"^/competitions/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/?$"
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\u200b", "").split())
    return cleaned or None


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not (cleaned := _clean_text(value)):
        raise ParseError(f"aijspt field {field!r} must be a non-empty string")
    return cleaned


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParseError(f"aijspt field {field!r} must be a string or null")
    return _clean_text(value)


def _required_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParseError(f"aijspt field {field!r} must be an integer")
    return value


def _parse_datetime(value: Any, field: str, *, required: bool = False) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ParseError(f"aijspt field {field!r} must be an ISO datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ParseError(f"invalid aijspt datetime in {field!r}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ParseError(f"aijspt datetime in {field!r} must include a timezone")
    return parsed


def _absolute(page_url: str, value: str | None) -> str | None:
    if not value or value.lower().startswith(("javascript:", "data:")):
        return None
    return urljoin(page_url, value)


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


class AijsptAdapter:
    """Read public JSON endpoints and server-rendered pages from AIJSPT."""

    code = "aijspt"

    def __init__(self, client: GdufClient) -> None:
        self._client = client
        self._competition_cache: tuple[tuple[CompetitionSummary, ...], str] | None = None

    def _json_object(
        self, url: str, *, params: dict[str, str | int] | None = None
    ) -> tuple[dict[str, Any], str]:
        text, response_url = self._client._request_text("GET", url, params=params)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseError(f"invalid JSON returned by {response_url}") from exc
        if not isinstance(value, dict):
            raise ParseError(f"JSON returned by {response_url} must be an object")
        return value, response_url

    @staticmethod
    def _parse_competition(value: Any) -> CompetitionSummary:
        if not isinstance(value, dict):
            raise ParseError("aijspt competition entry must be an object")
        competition_id = _required_text(value.get("id"), "id")
        try:
            UUID(competition_id)
        except ValueError as exc:
            raise ParseError(f"invalid aijspt competition id: {competition_id!r}") from exc
        return CompetitionSummary(
            id=competition_id,
            title=_required_text(value.get("title"), "title"),
            url=urljoin(BASE_URL, f"competitions/{competition_id}"),
            category=_required_text(value.get("category"), "category"),
            competition_year=_required_int(value.get("competitionYear"), "competitionYear"),
            recognition=_required_text(value.get("recognition"), "recognition"),
            status=_required_text(value.get("status"), "status"),
            summary=_required_text(value.get("summary"), "summary"),
            department=_required_text(value.get("department"), "department"),
            registration_mode=_required_text(value.get("registrationMode"), "registrationMode"),
            max_team_size=_required_int(value.get("maxTeamSize"), "maxTeamSize"),
            max_advisors=_required_int(value.get("maxAdvisors"), "maxAdvisors"),
            registration_start_at=_parse_datetime(
                value.get("registrationStartAt"), "registrationStartAt"
            ),
            registration_end_at=_parse_datetime(
                value.get("registrationEndAt"), "registrationEndAt"
            ),
            event_start_at=_parse_datetime(value.get("eventStartAt"), "eventStartAt"),
            event_end_at=_parse_datetime(value.get("eventEndAt"), "eventEndAt"),
            official_url=_optional_text(value.get("officialUrl"), "officialUrl"),
            wechat_article_url=_optional_text(value.get("wechatArticleUrl"), "wechatArticleUrl"),
            cta_type=_optional_text(value.get("ctaType"), "ctaType"),
            cta_label_override=_optional_text(value.get("ctaLabelOverride"), "ctaLabelOverride"),
        )

    def _all_competitions(self) -> tuple[tuple[CompetitionSummary, ...], str]:
        if self._competition_cache is not None:
            return self._competition_cache
        payload, response_url = self._json_object(urljoin(BASE_URL, "api/competitions"))
        raw_items = payload.get("competitions")
        if not isinstance(raw_items, list):
            raise ParseError("aijspt competitions response is missing a list")
        items = tuple(self._parse_competition(item) for item in raw_items)
        self._competition_cache = (items, response_url)
        return items, response_url

    def get_competitions(
        self,
        *,
        year: int | None = None,
        status: str | None = None,
        category: str | None = None,
        department: str | None = None,
        keyword: str | None = None,
    ) -> ListResult[CompetitionSummary]:
        if year is not None:
            _positive_int(year, "year")
        normalized_filters: dict[str, str] = {}
        for name, value in (
            ("status", status),
            ("category", category),
            ("department", department),
            ("keyword", keyword),
        ):
            if value is not None:
                if not isinstance(value, str) or not (cleaned := _clean_text(value)):
                    raise ValueError(f"{name} cannot be empty")
                normalized_filters[name] = cleaned

        items, source_url = self._all_competitions()
        selected: list[CompetitionSummary] = []
        for item in items:
            if year is not None and item.competition_year != year:
                continue
            if "status" in normalized_filters and item.status != normalized_filters["status"]:
                continue
            if "category" in normalized_filters and item.category != normalized_filters["category"]:
                continue
            if (
                "department" in normalized_filters
                and item.department != normalized_filters["department"]
            ):
                continue
            if "keyword" in normalized_filters:
                needle = normalized_filters["keyword"].casefold()
                if needle not in f"{item.title}\n{item.summary}".casefold():
                    continue
            selected.append(item)
        return ListResult(tuple(selected), len(selected), source_url)

    @staticmethod
    def _normalize_competition_id(
        competition_or_id: CompetitionSummary | str,
    ) -> tuple[str, CompetitionSummary | None]:
        if isinstance(competition_or_id, CompetitionSummary):
            if competition_or_id.source != "aijspt":
                raise ValueError("competition must belong to the aijspt source")
            return competition_or_id.id, competition_or_id
        if not isinstance(competition_or_id, str) or not competition_or_id.strip():
            raise ValueError("competition_or_id must be a competition, UUID, or detail URL")
        value = competition_or_id.strip()
        try:
            return str(UUID(value)), None
        except ValueError:
            pass
        parsed = urlparse(urljoin(BASE_URL, value))
        if parsed.scheme not in {"http", "https"} or parsed.hostname != "ai-data-competitions.cn":
            raise ValueError("competition detail URL must belong to ai-data-competitions.cn")
        match = _DETAIL_PATH_RE.fullmatch(parsed.path)
        if match is None:
            raise ValueError("competition detail URL must identify one competition")
        return str(UUID(match.group(1))), None

    def _find_competition(self, competition_id: str) -> CompetitionSummary:
        items, _ = self._all_competitions()
        for item in items:
            if item.id == competition_id:
                return item
        raise ValueError(f"unknown aijspt competition id: {competition_id}")

    @staticmethod
    def _clean_html(tag: Tag, page_url: str) -> tuple[str, str]:
        fragment_soup = BeautifulSoup(str(tag), "html.parser")
        fragment = fragment_soup.find()
        if not isinstance(fragment, Tag):
            raise ParseError("aijspt detail content could not be normalized")
        for unwanted in fragment.select("script, style, noscript"):
            unwanted.decompose()
        for node in fragment.find_all(True):
            for attribute in tuple(node.attrs):
                if attribute.lower().startswith("on") or attribute.lower() == "style":
                    del node.attrs[attribute]
            if node.name == "img":
                src = _absolute(page_url, str(node.get("src") or ""))
                if src:
                    node["src"] = src
                elif "src" in node.attrs:
                    del node.attrs["src"]
            elif node.name == "a":
                href = _absolute(page_url, str(node.get("href") or ""))
                if href:
                    node["href"] = href
                elif "href" in node.attrs:
                    del node.attrs["href"]
        return fragment.get_text("\n", strip=True), fragment.decode_contents(formatter="html")

    @staticmethod
    def _card(soup: BeautifulSoup, *titles: str) -> Tag | None:
        expected = set(titles)
        for title in soup.select("[data-slot='card-title']"):
            if _clean_text(title.get_text(" ", strip=True)) in expected:
                card = title.find_parent(attrs={"data-slot": "card"})
                if isinstance(card, Tag):
                    return card
        return None

    @classmethod
    def _timeline(cls, soup: BeautifulSoup) -> tuple[CompetitionTimelineItem, ...]:
        card = cls._card(soup, "时间安排")
        content = card.select_one("[data-slot='card-content']") if card else None
        if not isinstance(content, Tag):
            return ()
        items: list[CompetitionTimelineItem] = []
        for row in content.select(":scope > div"):
            children = [child for child in row.find_all(recursive=False) if isinstance(child, Tag)]
            if len(children) < 2:
                continue
            date_value = _clean_text(children[0].get_text(" ", strip=True))
            paragraphs = children[1].find_all("p")
            label = _clean_text(
                paragraphs[0].get_text(" ", strip=True)
                if paragraphs
                else children[1].get_text(" ", strip=True)
            )
            description = (
                _clean_text(paragraphs[1].get_text(" ", strip=True))
                if len(paragraphs) > 1
                else None
            )
            if date_value and label:
                items.append(CompetitionTimelineItem(date_value, label, description))
        return tuple(items)

    @classmethod
    def _faqs(cls, soup: BeautifulSoup) -> tuple[CompetitionFaq, ...]:
        card = cls._card(soup, "常见问题")
        if card is None:
            return ()
        items: list[CompetitionFaq] = []
        for row in card.select("[data-slot='accordion-item']"):
            question_node = row.select_one("[data-slot='accordion-trigger']")
            answer_node = row.select_one("[data-slot='accordion-content']")
            question = (
                _clean_text(question_node.get_text(" ", strip=True)) if question_node else None
            )
            answer = _clean_text(answer_node.get_text(" ", strip=True)) if answer_node else None
            if question and answer:
                items.append(CompetitionFaq(question, answer))
        return tuple(items)

    @classmethod
    def _links(cls, soup: BeautifulSoup, *titles: str) -> tuple[ResourceLink, ...]:
        card = cls._card(soup, *titles)
        if card is None:
            return ()
        links: list[ResourceLink] = []
        seen: set[str] = set()
        for anchor in card.select("[data-slot='card-content'] a[href]"):
            url = _absolute(BASE_URL, str(anchor.get("href")))
            title = _clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
            if url and title and url not in seen:
                seen.add(url)
                links.append(ResourceLink(title, url))
        return tuple(links)

    @classmethod
    def _text_items(cls, soup: BeautifulSoup, *titles: str) -> tuple[str, ...]:
        card = cls._card(soup, *titles)
        if card is None:
            return ()
        content = card.select_one("[data-slot='card-content']")
        if not isinstance(content, Tag):
            return ()
        values: list[str] = []
        for node in content.select("li, [data-slot='badge']"):
            value = _clean_text(node.get_text(" ", strip=True))
            if value and value not in values:
                values.append(value)
        return tuple(values)

    def get_competition_detail(
        self, competition_or_id: CompetitionSummary | str
    ) -> CompetitionDetail:
        competition_id, supplied = self._normalize_competition_id(competition_or_id)
        competition = supplied or self._find_competition(competition_id)
        html, response_url = self._client._request_text("GET", competition.url)
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        if not isinstance(heading, Tag):
            raise ParseError("aijspt competition detail heading not found")
        title = _clean_text(heading.get_text(" ", strip=True))
        if title != competition.title:
            raise ParseError("aijspt competition detail does not match the requested competition")
        description = (
            heading.parent.select_one(".prose") if isinstance(heading.parent, Tag) else None
        )
        if not isinstance(description, Tag):
            description_soup = BeautifulSoup(
                f"<div><p>{competition.summary}</p></div>", "html.parser"
            )
            description = description_soup.div
        if not isinstance(description, Tag):
            raise ParseError("aijspt competition description not found")
        description_text, description_html = self._clean_html(description, response_url)

        location = None
        location_label = soup.find(string=lambda value: value and value.strip() == "地点与归属")
        if location_label and isinstance(location_label.parent, Tag):
            value_container = location_label.parent.parent
            if isinstance(value_container, Tag):
                paragraphs = value_container.find_all("p", recursive=False)
                if len(paragraphs) > 1:
                    combined = _clean_text(paragraphs[1].get_text(" ", strip=True))
                    if combined:
                        location = combined.rsplit("·", 1)[-1].strip()

        return CompetitionDetail(
            competition=competition,
            description_text=description_text,
            description_html=description_html,
            location=location,
            highlights=self._text_items(soup, "比赛亮点", "赛事亮点"),
            sub_tracks=self._text_items(soup, "子赛项", "子赛道"),
            timeline=self._timeline(soup),
            faqs=self._faqs(soup),
            attachments=self._links(soup, "附件", "相关附件", "比赛附件"),
            related_questions=self._links(soup, "问答讨论"),
            experience_articles=self._links(soup, "经验文章"),
        )

    def get_notices(self, limit: int = 20) -> ListResult[Notice]:
        _positive_int(limit, "limit")
        payload, response_url = self._json_object(
            urljoin(BASE_URL, "api/notices/published"), params={"limit": limit}
        )
        raw_items = payload.get("notices")
        if not isinstance(raw_items, list):
            raise ParseError("aijspt notices response is missing a list")
        items: list[Notice] = []
        for value in raw_items:
            if not isinstance(value, dict):
                raise ParseError("aijspt notice entry must be an object")
            published_at = _parse_datetime(value.get("publishedAt"), "publishedAt", required=True)
            if published_at is None:
                raise ParseError("aijspt notice publishedAt is required")
            allow_popup = value.get("allowPopup")
            if not isinstance(allow_popup, bool):
                raise ParseError("aijspt field 'allowPopup' must be a boolean")
            items.append(
                Notice(
                    id=_required_text(value.get("id"), "id"),
                    competition_id=_optional_text(value.get("competitionId"), "competitionId"),
                    competition_title=_optional_text(
                        value.get("competitionTitle"), "competitionTitle"
                    ),
                    title=_required_text(value.get("title"), "title"),
                    content=_required_text(value.get("content"), "content"),
                    priority=_required_text(value.get("priority"), "priority"),
                    delivery_scope=_required_text(value.get("deliveryScope"), "deliveryScope"),
                    allow_popup=allow_popup,
                    published_at=published_at,
                    expires_at=_parse_datetime(value.get("expiresAt"), "expiresAt"),
                    updated_at=_parse_datetime(value.get("updatedAt"), "updatedAt"),
                )
            )
        return ListResult(tuple(items), len(items), response_url)

    def get_clubs(self) -> ListResult[ClubSummary]:
        html, response_url = self._client._request_text("GET", urljoin(BASE_URL, "clubs"))
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("#clubs-overview")
        if container is None:
            raise ParseError("aijspt club overview not found")
        items: list[ClubSummary] = []
        seen_slugs: set[str] = set()
        # 注意：线上页面是 Next.js 流式渲染，部分社团卡片被注入在 #clubs-overview
        # 容器之外（template 兄弟节点），因此按整页扫描 article 并以
        # “链接指向 /clubs/{slug}” 作为社团卡片特征，再按 slug 去重。
        for card in soup.select("article"):
            heading = card.find("h3")
            anchor = card.find("a", href=True)
            paragraphs = card.find_all("p", recursive=False)
            badge = card.select_one("[data-slot='badge']")
            if not isinstance(heading, Tag) or not isinstance(anchor, Tag) or len(paragraphs) < 2:
                continue
            url = _absolute(response_url, str(anchor.get("href")))
            if not url:
                continue
            path = urlparse(url).path.rstrip("/")
            if not path.startswith("/clubs/"):
                continue
            slug = path.rsplit("/", 1)[-1]
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            items.append(
                ClubSummary(
                    slug=slug,
                    name=_required_text(heading.get_text(" ", strip=True), "club.name"),
                    direction=_required_text(
                        badge.get_text(" ", strip=True) if badge else None, "club.direction"
                    ),
                    slogan=_required_text(paragraphs[0].get_text(" ", strip=True), "club.slogan"),
                    description=_required_text(
                        paragraphs[1].get_text(" ", strip=True), "club.description"
                    ),
                    url=url,
                )
            )
        if not items:
            raise ParseError("aijspt club overview contains no clubs")
        return ListResult(tuple(items), len(items), response_url)
