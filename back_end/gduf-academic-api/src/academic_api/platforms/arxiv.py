"""arXiv 平台适配器：基于官方公开 Atom API，无需密钥。

API 文档：https://info.arxiv.org/help/api/basics.html
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from academic_api.errors import NetworkError, ParseError
from academic_api.models import AcademicResource
from academic_api.platforms import register
from academic_api.platforms.base import BasePlatform

API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


@register
class ArxivPlatform(BasePlatform):
    """arXiv：CS/AI 领域核心预印本平台，论文全文开放获取。"""

    name = "arxiv"
    display_name = "arXiv"

    def search(self, query: str, max_results: int = 10) -> list[AcademicResource]:
        self._validate_query(query)
        params = {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            response = self._client.get(API_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise NetworkError(f"arXiv API 请求失败：{exc}") from exc
        return self.parse_response(response.text)

    def parse_response(self, xml_text: str) -> list[AcademicResource]:
        """解析 Atom XML 响应；结构异常时抛 ParseError。"""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ParseError(f"arXiv 响应不是合法的 Atom XML：{exc}") from exc

        results: list[AcademicResource] = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            title = self._clip(entry.findtext(f"{ATOM_NS}title", ""), 300)
            abstract = self._clip(entry.findtext(f"{ATOM_NS}summary", ""), self.ABSTRACT_LIMIT)
            if not title:
                continue

            authors: list[str] = []
            for author in entry.findall(f"{ATOM_NS}author"):
                name = author.findtext(f"{ATOM_NS}name", "").strip()
                if name:
                    authors.append(name)

            url = ""
            pdf_url: str | None = None
            for link in entry.findall(f"{ATOM_NS}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                elif link.get("rel") == "alternate":
                    url = link.get("href") or ""
            if not url:
                url = entry.findtext(f"{ATOM_NS}id", "")

            published = entry.findtext(f"{ATOM_NS}published", "")
            year: int | None = None
            if len(published) >= 4 and published[:4].isdigit():
                year = int(published[:4])

            results.append(
                AcademicResource(
                    title=title,
                    authors=authors[: self.MAX_AUTHORS],
                    abstract=abstract,
                    url=url,
                    source=self.name,
                    pdf_url=pdf_url,
                    published_year=year,
                    doi=entry.findtext(f"{ARXIV_NS}doi"),
                    venue="arXiv",
                )
            )
        return results
