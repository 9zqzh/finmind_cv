"""Adapter for the School of Big Data and Artificial Intelligence website."""

from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from gduf_web_api.errors import InvalidPageError, ParseError
from gduf_web_api.models import (
    AiHome,
    ArticleSummary,
    ContentDetail,
    PageResult,
    PersonSummary,
)

if TYPE_CHECKING:
    from gduf_web_api.client import GdufClient

BASE_URL = "https://ai.gduf.edu.cn/"

ARTICLE_PATHS = {
    "xyxw": "jxky/xyxw.htm",
    "xshuhd": "xshd1.htm",
    "xshenghd": "xshd.htm",
    "tzgg": "tzgg.htm",
}

PEOPLE_PATHS = {
    "xyld": "xygk/xyld.htm",
    "zrjs": "xygk/zrjs.htm",
    "jfry": "xygk/jfry.htm",
}

CONTENT_PATHS = {
    "xyjj": "xygk/xyjj.htm",
    "jgsz": "xygk/jgsz.htm",
    "jsjkxyjs": "zyjx/jsjkxyjs.htm",
    "rjgc": "zyjx/rjgc.htm",
    "sjkxydsjjs": "zyjx/sjkxydsjjs.htm",
    "yytjx": "zyjx/yytjx.htm",
    "rgzn": "zyjx/rgzn.htm",
}

_PAGE_RE = re.compile(r"共\s*(\d+)\s*条\s*(\d+)\s*/\s*(\d+)")
_DATE_RE = re.compile(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})")
_ATTACHMENT_RE = re.compile(
    r"\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z|txt|csv)(?:$|[?#])", re.IGNORECASE
)


def _validate_page(page: int) -> None:
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise InvalidPageError("page must be a positive integer")


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\u200b", "").split())
    return cleaned or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = _DATE_RE.search(value)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _absolute(page_url: str, value: str | None) -> str | None:
    if not value or value.lower().startswith(("javascript:", "data:")):
        return None
    return urljoin(page_url, value)


def _dedupe_articles(items: list[ArticleSummary]) -> tuple[ArticleSummary, ...]:
    found: dict[str, ArticleSummary] = {}
    for item in items:
        found.setdefault(item.url, item)
    return tuple(found.values())


def _split_person_title(display_name: str) -> tuple[str, str | None]:
    parenthesized = re.fullmatch(
        r"\s*(.+?)\s*[\uff08(]\s*(.+?)\s*[\uff09)]\s*", display_name
    )
    if parenthesized:
        return parenthesized.group(1).strip(), parenthesized.group(2).strip()
    parts = display_name.strip().split(maxsplit=1)
    return parts[0], parts[1] if len(parts) == 2 else None


class AiAdapter:
    """Parse the current Visual SiteBuilder templates used by the AI college."""

    code = "ai"

    def __init__(self, client: GdufClient) -> None:
        self._client = client
        self._page_meta: dict[str, tuple[int, int]] = {}
        self._first_page: dict[str, tuple[BeautifulSoup, str]] = {}

    def _fetch(self, url: str) -> tuple[BeautifulSoup, str]:
        html, response_url = self._client._request_text("GET", url)
        return BeautifulSoup(html, "html.parser"), response_url

    @staticmethod
    def _pagination(soup: BeautifulSoup, item_count: int) -> tuple[int, int, int]:
        match = _PAGE_RE.search(soup.get_text(" ", strip=True))
        if not match:
            return item_count, 1, 1
        total_items, current_page, total_pages = (int(value) for value in match.groups())
        return total_items, current_page, total_pages

    def _paginated_page(
        self, category: str, path: str, page: int
    ) -> tuple[BeautifulSoup, str, int, int]:
        _validate_page(page)
        canonical_url = urljoin(BASE_URL, path)
        cached = self._page_meta.get(category)
        if cached is None:
            first_soup, first_url = self._fetch(canonical_url)
            total_items, _, total_pages = self._pagination(first_soup, 0)
            cached = (total_items, total_pages)
            self._page_meta[category] = cached
            self._first_page[category] = (first_soup, first_url)
        total_items, total_pages = cached
        if page > total_pages:
            raise InvalidPageError(
                f"page {page} is outside the available range 1..{total_pages} for {category}"
            )
        if page == 1:
            cached_page = self._first_page.pop(category, None)
            if cached_page is not None:
                return *cached_page, total_items, total_pages
            soup, response_url = self._fetch(canonical_url)
            return soup, response_url, total_items, total_pages
        path_without_suffix = path.removesuffix(".htm")
        suffix = total_pages - page + 1
        page_url = urljoin(BASE_URL, f"{path_without_suffix}/{suffix}.htm")
        soup, response_url = self._fetch(page_url)
        return soup, response_url, total_items, total_pages

    def get_articles(self, category: str, page: int = 1) -> PageResult[ArticleSummary]:
        try:
            path = ARTICLE_PATHS[category]
        except KeyError as exc:
            raise ParseError(f"unknown AI article category: {category!r}") from exc
        soup, response_url, cached_total, cached_pages = self._paginated_page(
            category, path, page
        )
        items = self._parse_article_list(soup, response_url, category)
        total_items, _, total_pages = self._pagination(soup, len(items))
        if total_pages == 1 and cached_pages > 1:
            total_items, total_pages = cached_total, cached_pages
        return PageResult(items, page, total_pages, total_items, response_url)

    def _parse_article_list(
        self, soup: BeautifulSoup, page_url: str, category: str
    ) -> tuple[ArticleSummary, ...]:
        container = soup.select_one(".dqlb")
        if container is None:
            raise ParseError(f"article list container not found for {category}")
        items: list[ArticleSummary] = []
        for row in container.select("li[id^='line_']"):
            anchor = row.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            item_url = _absolute(page_url, str(anchor.get("href")))
            title = _clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
            if not item_url or not title:
                continue
            date_node = row.find("b")
            image = row.find("img")
            summary_node = row.select_one(".summary, .txt p, .text p")
            items.append(
                ArticleSummary(
                    title=title,
                    url=item_url,
                    published_at=_parse_date(
                        date_node.get_text(" ", strip=True) if date_node else None
                    ),
                    summary=_clean_text(summary_node.get_text(" ", strip=True))
                    if summary_node
                    else None,
                    image_url=_absolute(page_url, str(image.get("src")))
                    if isinstance(image, Tag)
                    else None,
                    category=category,
                )
            )
        if not items:
            raise ParseError(f"no article items found for {category}")
        return _dedupe_articles(items)

    def get_people(self, category: str, page: int = 1) -> PageResult[PersonSummary]:
        try:
            path = PEOPLE_PATHS[category]
        except KeyError as exc:
            raise ParseError(f"unknown AI people category: {category!r}") from exc
        soup, response_url, cached_total, cached_pages = self._paginated_page(
            category, path, page
        )
        if category == "xyld":
            items = self._parse_leaders(soup, response_url)
        else:
            items = self._parse_staff(soup, response_url)
        total_items, _, total_pages = self._pagination(soup, len(items))
        if total_pages == 1 and cached_pages > 1:
            total_items, total_pages = cached_total, cached_pages
        return PageResult(items, page, total_pages, total_items, response_url)

    def _parse_staff(self, soup: BeautifulSoup, page_url: str) -> tuple[PersonSummary, ...]:
        container = soup.select_one(".img-lists")
        if container is None:
            raise ParseError("staff list container not found")
        items: list[PersonSummary] = []
        seen: set[str] = set()
        for row in container.select("li[id^='line_']"):
            anchor = row.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            url = _absolute(page_url, str(anchor.get("href")))
            display_name = _clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
            if not url or not display_name or url in seen:
                continue
            seen.add(url)
            name, role = _split_person_title(display_name)
            image = row.find("img")
            items.append(
                PersonSummary(
                    name=name,
                    role=role,
                    url=url,
                    image_url=_absolute(page_url, str(image.get("src")))
                    if isinstance(image, Tag)
                    else None,
                )
            )
        if not items:
            raise ParseError("no staff items found")
        return tuple(items)

    def _parse_leaders(self, soup: BeautifulSoup, page_url: str) -> tuple[PersonSummary, ...]:
        desktop = soup.select_one(".ld")
        if desktop is None:
            raise ParseError("leader list container not found")
        items: list[PersonSummary] = []
        seen: set[str] = set()
        group_names = ("党委", "行政")
        for group_index, group in enumerate(desktop.select(":scope > div")):
            group_name = group_names[group_index] if group_index < len(group_names) else None
            for row in group.select("ul.leader_group > li"):
                anchor = row.find("a", href=True)
                if not isinstance(anchor, Tag):
                    continue
                url = _absolute(page_url, str(anchor.get("href")))
                display_name = _clean_text(
                    str(anchor.get("title") or anchor.get_text(" ", strip=True))
                )
                if not url or not display_name or url in seen:
                    continue
                seen.add(url)
                name, role = _split_person_title(display_name)
                responsibility = None
                for table_row in row.select(".leader_info tr"):
                    if "工作内容" in table_row.get_text(" ", strip=True):
                        span = table_row.find("span")
                        responsibility = _clean_text(
                            span.get_text(" ", strip=True) if span else None
                        )
                        break
                image = row.find("img")
                items.append(
                    PersonSummary(
                        name=name,
                        role=role,
                        url=url,
                        responsibility=responsibility,
                        image_url=_absolute(page_url, str(image.get("src")))
                        if isinstance(image, Tag)
                        else None,
                        group=group_name,
                    )
                )
        if not items:
            raise ParseError("no leader items found")
        return tuple(items)

    def get_content(self, category: str) -> ContentDetail:
        try:
            path = CONTENT_PATHS[category]
        except KeyError as exc:
            raise ParseError(f"unknown AI content category: {category!r}") from exc
        soup, response_url = self._fetch(urljoin(BASE_URL, path))
        return self._parse_content(soup, response_url, category=category, kind="static")

    def get_detail(self, item_or_url: ArticleSummary | PersonSummary | str) -> ContentDetail:
        url = item_or_url if isinstance(item_or_url, str) else item_or_url.url
        parsed = urlparse(urljoin(BASE_URL, url))
        if parsed.scheme not in {"http", "https"} or parsed.hostname != "ai.gduf.edu.cn":
            raise ValueError("detail URL must belong to ai.gduf.edu.cn")
        normalized_url = parsed.geturl()
        soup, response_url = self._fetch(normalized_url)
        path_parts = PurePosixPath(parsed.path).parts
        person_columns = {"1044", "1091", "1092", "1093"}
        kind = "person" if person_columns.intersection(path_parts) else "article"
        return self._parse_content(soup, response_url, category=None, kind=kind)

    def _parse_content(
        self,
        soup: BeautifulSoup,
        page_url: str,
        *,
        category: str | None,
        kind: str,
    ) -> ContentDetail:
        title_node = soup.select_one(".xqnr_tit h2") or soup.select_one(".lm")
        if title_node is not None:
            title = _clean_text(title_node.get_text(" ", strip=True))
        else:
            raw_title = soup.title.get_text(" ", strip=True) if soup.title else ""
            title = _clean_text(raw_title.removesuffix("-大数据与人工智能学院"))
        body = (
            soup.select_one(".xqnr_nr [id^='vsb_content']")
            or soup.select_one(".xqnr_nr")
            or soup.select_one("[id^='vsb_content']")
        )
        if not title or body is None:
            raise ParseError("content title or body container not found")
        body_soup = BeautifulSoup(str(body), "html.parser")
        clean_body = body_soup.find()
        if not isinstance(clean_body, Tag):
            raise ParseError("content body could not be normalized")
        for unwanted in clean_body.select("script, style, noscript"):
            unwanted.decompose()
        images: list[str] = []
        attachments: list[str] = []
        for tag in clean_body.find_all(True):
            for attribute in tuple(tag.attrs):
                if attribute.lower().startswith("on") or attribute.lower() == "style":
                    del tag.attrs[attribute]
            if tag.name == "img":
                absolute_src = _absolute(page_url, str(tag.get("src") or ""))
                if absolute_src:
                    tag["src"] = absolute_src
                    if absolute_src not in images:
                        images.append(absolute_src)
            if tag.name == "a":
                absolute_href = _absolute(page_url, str(tag.get("href") or ""))
                if absolute_href:
                    tag["href"] = absolute_href
                    if _ATTACHMENT_RE.search(absolute_href) and absolute_href not in attachments:
                        attachments.append(absolute_href)
                elif "href" in tag.attrs:
                    del tag.attrs["href"]

        metadata_node = soup.select_one(".xqnr_tit p")
        metadata = metadata_node.get_text(" ", strip=True) if metadata_node else ""
        attribution_match = re.search(
            r"文章来源[\uff1a:]\s*(.+?)(?:\s+发布时间|$)", metadata
        )
        view_count = None
        view_node = metadata_node.find("span") if metadata_node else None
        if isinstance(view_node, Tag):
            digits = re.search(r"\d+", view_node.get_text(" ", strip=True))
            if digits:
                view_count = int(digits.group())
        previous_url = None
        next_url = None
        for row in soup.select(".sxfy li"):
            anchor = row.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            navigation_url = _absolute(page_url, str(anchor.get("href")))
            row_text = row.get_text(" ", strip=True)
            if row_text.startswith("上一条"):
                previous_url = navigation_url
            elif row_text.startswith("下一条"):
                next_url = navigation_url
        return ContentDetail(
            title=title,
            url=page_url,
            content_text=clean_body.get_text("\n", strip=True),
            content_html=clean_body.decode_contents(formatter="html"),
            images=tuple(images),
            attachments=tuple(attachments),
            published_at=_parse_date(metadata),
            attribution=_clean_text(attribution_match.group(1)) if attribution_match else None,
            view_count=view_count,
            previous_url=previous_url,
            next_url=next_url,
            category=category,
            kind=kind,
        )

    def get_home(self) -> AiHome:
        soup, response_url = self._fetch(BASE_URL)
        return AiHome(
            xyxw=self._parse_home_section(soup, response_url, "学院新闻", "xyxw"),
            xshuhd=self._parse_home_section(soup, response_url, "学术活动", "xshuhd"),
            xshenghd=self._parse_home_section(soup, response_url, "学生活动", "xshenghd"),
            tzgg=self._parse_home_section(soup, response_url, "通知公告", "tzgg"),
            source_url=response_url,
        )

    def _parse_home_section(
        self, soup: BeautifulSoup, page_url: str, heading: str, category: str
    ) -> tuple[ArticleSummary, ...]:
        title_node = next(
            (
                node
                for node in soup.select("div.title")
                if heading in node.get_text(" ", strip=True)
            ),
            None,
        )
        if title_node is None:
            raise ParseError(f"home section not found: {heading}")
        container = title_node.find_parent("div", class_="container") or title_node.parent
        if not isinstance(container, Tag):
            raise ParseError(f"home section container not found: {heading}")
        items: list[ArticleSummary] = []
        for anchor in container.select("a[href*='info/']"):
            href = _absolute(page_url, str(anchor.get("href")))
            if not href:
                continue
            title_element = anchor.find(["h3", "h2"])
            title = _clean_text(str(anchor.get("title") or ""))
            if not title and isinstance(title_element, Tag):
                title = _clean_text(title_element.get_text(" ", strip=True))
            if not title:
                image_for_alt = anchor.find("img", alt=True)
                title = (
                    _clean_text(str(image_for_alt.get("alt")))
                    if isinstance(image_for_alt, Tag)
                    else None
                )
            if not title:
                continue
            image = anchor.find("img")
            summary_node = anchor.select_one(".txt p, .text > p")
            published_at = None
            date_box = anchor.select_one(".date")
            if date_box:
                month = date_box.find("span")
                day = date_box.find("p")
                if month and day:
                    published_at = _parse_date(
                        f"{month.get_text(strip=True)}-{day.get_text(strip=True)}"
                    )
            if published_at is None:
                for span in anchor.find_all("span"):
                    published_at = _parse_date(span.get_text(" ", strip=True))
                    if published_at:
                        break
            items.append(
                ArticleSummary(
                    title=title,
                    url=href,
                    published_at=published_at,
                    summary=_clean_text(summary_node.get_text(" ", strip=True))
                    if summary_node
                    else None,
                    image_url=_absolute(page_url, str(image.get("src")))
                    if isinstance(image, Tag)
                    else None,
                    category=category,
                )
            )
        deduped = _dedupe_articles(items)
        if not deduped:
            raise ParseError(f"home section contains no articles: {heading}")
        return deduped

    def search(self, keyword: str, page: int = 1) -> PageResult[ArticleSummary]:
        _validate_page(page)
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("keyword cannot be empty")
        encoded = base64.b64encode(normalized_keyword.encode("utf-8")).decode("ascii")
        if page == 1:
            params: dict[str, str | int] = {"wbtreeid": "1001"}
            data = {
                "lucenenewssearchkeyword": encoded,
                "_lucenesearchtype": "1",
                "searchScope": "1",
            }
        else:
            params = {"wbtreeid": "1001", "searchScope": "1", "currentnum": page}
            data = {
                "newskeycode2": encoded,
                "_lucenesearchtype": "2",
                "topageurl": "/search.jsp?wbtreeid=1001&searchScope=1&currentnum=",
                "wbtreeid": "1001",
            }
        html, response_url = self._client._request_text(
            "POST", urljoin(BASE_URL, "search.jsp"), params=params, data=data
        )
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(".dqlb")
        if container is None:
            raise ParseError("search result container not found")
        items: list[ArticleSummary] = []
        for row in container.select("ul li"):
            anchor = row.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            item_url = _absolute(response_url, str(anchor.get("href")))
            title = _clean_text(anchor.get_text(" ", strip=True))
            if not item_url or not title:
                continue
            date_node = row.find("b")
            items.append(
                ArticleSummary(
                    title=title,
                    url=item_url,
                    published_at=_parse_date(
                        date_node.get_text(" ", strip=True) if date_node else None
                    ),
                    category="search",
                )
            )
        total_items, current_page, total_pages = self._pagination(soup, len(items))
        if page > total_pages and total_pages > 0:
            raise InvalidPageError(
                f"page {page} is outside the available search range 1..{total_pages}"
            )
        return PageResult(
            _dedupe_articles(items),
            current_page if total_pages > 1 else page,
            total_pages,
            total_items,
            response_url,
        )
