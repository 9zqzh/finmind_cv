"""学术资源数据模型（纯 dataclass，可 JSON 序列化前置）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AcademicResource:
    """单条学术资源（论文/文献）。"""

    title: str
    authors: list[str]
    abstract: str
    url: str
    source: str
    pdf_url: str | None = None
    published_year: int | None = None
    citation_count: int | None = None
    doi: str | None = None
    venue: str | None = None


@dataclass
class AcademicSearchResult:
    """跨平台聚合搜索结果。"""

    query: str
    total: int
    items: list[AcademicResource] = field(default_factory=list)
    # 各平台成功/失败情况说明（便于上层组织提示）
    messages: list[str] = field(default_factory=list)
