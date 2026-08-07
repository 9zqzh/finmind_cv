"""Semantic Scholar 平台适配器：基于官方公开 Graph API，无需密钥即可使用。

API 文档：https://api.semanticscholar.org/api-docs/
注意：无密钥限流约 100 次/5 分钟，超出时返回 429，此处统一映射为 NetworkError。
"""

from __future__ import annotations

import httpx

from academic_api.errors import NetworkError, ParseError
from academic_api.models import AcademicResource
from academic_api.platforms import register
from academic_api.platforms.base import BasePlatform

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# 只取组织回复所需的字段，减少响应体积
_FIELDS = "title,authors,abstract,url,openAccessPdf,year,citationCount,externalIds,venue"


@register
class SemanticScholarPlatform(BasePlatform):
    """Semantic Scholar：跨学科论文检索，附引用数与开放获取 PDF 链接。"""

    name = "semantic_scholar"
    display_name = "Semantic Scholar"

    def search(self, query: str, max_results: int = 10) -> list[AcademicResource]:
        self._validate_query(query)
        params = {
            "query": query,
            "limit": str(min(max(max_results, 1), 100)),
            "fields": _FIELDS,
        }
        try:
            response = self._client.get(API_URL, params=params)
            if response.status_code == 429:
                raise NetworkError("Semantic Scholar 请求过于频繁（429 限流），请稍后再试")
            response.raise_for_status()
        except NetworkError:
            raise
        except httpx.HTTPError as exc:
            raise NetworkError(f"Semantic Scholar API 请求失败：{exc}") from exc
        return self.parse_response(response.text)

    def parse_response(self, json_text: str) -> list[AcademicResource]:
        """解析 JSON 响应；结构异常时抛 ParseError。"""
        import json

        try:
            payload = json.loads(json_text)
        except ValueError as exc:
            raise ParseError(f"Semantic Scholar 响应不是合法 JSON：{exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ParseError("Semantic Scholar 响应缺少 data 数组")

        results: list[AcademicResource] = []
        for paper in payload["data"]:
            if not isinstance(paper, dict):
                continue
            title = self._clip(str(paper.get("title") or ""), 300)
            if not title:
                continue

            authors = [
                str(author.get("name")).strip()
                for author in paper.get("authors") or []
                if isinstance(author, dict) and author.get("name")
            ]

            open_access = paper.get("openAccessPdf")
            pdf_url = None
            if isinstance(open_access, dict):
                pdf_url = open_access.get("url")

            external_ids = paper.get("externalIds")
            doi = None
            if isinstance(external_ids, dict):
                doi = external_ids.get("DOI")

            year = paper.get("year")
            citation_count = paper.get("citationCount")

            results.append(
                AcademicResource(
                    title=title,
                    authors=authors[: self.MAX_AUTHORS],
                    abstract=self._clip(
                        str(paper.get("abstract") or ""), self.ABSTRACT_LIMIT
                    ),
                    url=str(paper.get("url") or ""),
                    source=self.name,
                    pdf_url=pdf_url,
                    published_year=year if isinstance(year, int) else None,
                    citation_count=(
                        citation_count if isinstance(citation_count, int) else None
                    ),
                    doi=doi,
                    venue=(str(paper.get("venue")) if paper.get("venue") else None),
                )
            )
        return results
