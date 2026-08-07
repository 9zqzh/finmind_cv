"""平台注册表与统一客户端测试（使用 httpx MockTransport，不发起真实请求）。"""

from __future__ import annotations

import httpx
import pytest

from academic_api import AcademicClient, AcademicError, ValidationError, list_platforms
from academic_api.errors import UnsupportedPlatformError
from academic_api.platforms import get_platform

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new simple network architecture, the Transformer,
based solely on attention mechanisms.</summary>
    <published>2017-06-12T17:57:34Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/1706.03762v7"/>
    <link title="pdf" rel="related" type="application/pdf" href="http://arxiv.org/pdf/1706.03762v7"/>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/0000.00001v1</id>
    <title>无链接条目</title>
    <summary>该条目没有 alternate 链接，应回退使用 id。</summary>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>
"""

S2_JSON = """{
  "total": 2,
  "data": [
    {
      "title": "Deep Residual Learning for Image Recognition",
      "authors": [{"name": "Kaiming He"}, {"name": "Xiangyu Zhang"}],
      "abstract": "Deeper neural networks are harder to train.",
      "url": "https://www.semanticscholar.org/paper/abc",
      "openAccessPdf": {"url": "https://arxiv.org/pdf/1512.03385"},
      "year": 2015,
      "citationCount": 190000,
      "externalIds": {"DOI": "10.1109/CVPR.2016.90"},
      "venue": "CVPR"
    },
    {
      "title": null,
      "authors": [],
      "abstract": null,
      "url": null,
      "year": null,
      "citationCount": null
    }
  ]
}"""


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---- 注册表 ----


def test_list_platforms_includes_phase_one() -> None:
    assert list_platforms() == ["arxiv", "semantic_scholar"]


def test_get_platform_unknown_raises() -> None:
    with pytest.raises(UnsupportedPlatformError):
        get_platform("ieee", _mock_client(lambda request: httpx.Response(200)))


# ---- arXiv 解析 ----


def test_arxiv_parse_extracts_fields() -> None:
    from academic_api.platforms.arxiv import ArxivPlatform

    platform = ArxivPlatform(_mock_client(lambda request: httpx.Response(200)))
    items = platform.parse_response(ARXIV_XML)
    assert len(items) == 2

    first = items[0]
    assert first.title == "Attention Is All You Need"
    assert first.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert first.url == "http://arxiv.org/abs/1706.03762v7"
    assert first.pdf_url == "http://arxiv.org/pdf/1706.03762v7"
    assert first.published_year == 2017
    assert first.doi == "10.48550/arXiv.1706.03762"
    assert first.source == "arxiv"
    assert "Transformer" in first.abstract

    # 无 alternate 链接时回退使用 entry id
    assert items[1].url == "http://arxiv.org/abs/0000.00001v1"
    assert items[1].pdf_url is None


def test_arxiv_parse_invalid_xml_raises() -> None:
    from academic_api.errors import ParseError
    from academic_api.platforms.arxiv import ArxivPlatform

    platform = ArxivPlatform(_mock_client(lambda request: httpx.Response(200)))
    with pytest.raises(ParseError):
        platform.parse_response("<not-valid-xml")


# ---- Semantic Scholar 解析 ----


def test_semantic_scholar_parse_extracts_fields() -> None:
    from academic_api.platforms.semantic_scholar import SemanticScholarPlatform

    platform = SemanticScholarPlatform(
        _mock_client(lambda request: httpx.Response(200))
    )
    items = platform.parse_response(S2_JSON)
    # 无标题条目应被过滤
    assert len(items) == 1
    item = items[0]
    assert item.title == "Deep Residual Learning for Image Recognition"
    assert item.authors == ["Kaiming He", "Xiangyu Zhang"]
    assert item.pdf_url == "https://arxiv.org/pdf/1512.03385"
    assert item.published_year == 2015
    assert item.citation_count == 190000
    assert item.doi == "10.1109/CVPR.2016.90"
    assert item.venue == "CVPR"
    assert item.source == "semantic_scholar"


def test_semantic_scholar_parse_invalid_json_raises() -> None:
    from academic_api.errors import ParseError
    from academic_api.platforms.semantic_scholar import SemanticScholarPlatform

    platform = SemanticScholarPlatform(
        _mock_client(lambda request: httpx.Response(200))
    )
    with pytest.raises(ParseError):
        platform.parse_response("not json")
    with pytest.raises(ParseError):
        platform.parse_response('{"foo": 1}')


# ---- 统一客户端聚合 ----


def _handler(request: httpx.Request) -> httpx.Response:
    if "arxiv.org" in str(request.url):
        return httpx.Response(200, text=ARXIV_XML)
    if "semanticscholar.org" in str(request.url):
        return httpx.Response(200, text=S2_JSON)
    return httpx.Response(404)


def test_client_search_aggregates_all_platforms() -> None:
    client = AcademicClient(transport=httpx.MockTransport(_handler))
    result = client.search("attention", max_results=5)
    assert result.total == 3  # arXiv 2 条 + Semantic Scholar 1 条
    sources = {item.source for item in result.items}
    assert sources == {"arxiv", "semantic_scholar"}
    assert any("arXiv" in message for message in result.messages)
    client.close()


def test_client_search_partial_failure_keeps_other_platform() -> None:
    def failing_arxiv(request: httpx.Request) -> httpx.Response:
        if "arxiv.org" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, text=S2_JSON)

    client = AcademicClient(transport=httpx.MockTransport(failing_arxiv))
    result = client.search("resnet")
    # arXiv 失败不影响 Semantic Scholar 结果
    assert result.total == 1
    assert result.items[0].source == "semantic_scholar"
    assert any("arxiv 检索失败" in message for message in result.messages)
    client.close()


def test_client_search_all_failed_raises() -> None:
    handler = lambda request: httpx.Response(500)  # noqa: E731
    client = AcademicClient(transport=httpx.MockTransport(handler))
    with pytest.raises(AcademicError):
        client.search("任何关键词")
    client.close()


def test_client_search_validates_inputs() -> None:
    client = AcademicClient(transport=httpx.MockTransport(_handler))
    with pytest.raises(ValidationError):
        client.search("   ")
    with pytest.raises(ValidationError):
        client.search("query", sources=["not_a_platform"])
    with pytest.raises(ValidationError):
        client.search("query", max_results=0)
    with pytest.raises(ValidationError):
        client.search("query", max_results=999)
    client.close()
