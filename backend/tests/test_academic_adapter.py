"""Findpapers 学术适配层测试（全部使用伪造对象，不访问网络）。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import time

import pytest
from findpapers import ConnectorError, InvalidParameterError, QueryValidationError

from app.adapters import academic as academic_adapter
from app.schemas.common import INVALID_PARAM, UPSTREAM_ERROR, ApiError


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "findpapers_databases": "arxiv,pubmed,semantic_scholar",
        "findpapers_request_timeout_seconds": 10.0,
        "findpapers_search_timeout_seconds": 30.0,
        "findpapers_max_retries": 1,
        "findpapers_rate_limit_retries": 0,
        "findpapers_ieee_api_token": "",
        "findpapers_scopus_api_token": "",
        "findpapers_pubmed_api_token": "",
        "findpapers_openalex_api_token": "",
        "findpapers_semantic_scholar_api_token": "",
        "findpapers_wos_api_token": "",
        "findpapers_email": "",
        "findpapers_proxy": "",
        "findpapers_ssl_verify": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _use_settings(monkeypatch, **overrides) -> SimpleNamespace:
    settings = _settings(**overrides)
    monkeypatch.setattr(academic_adapter, "get_settings", lambda: settings)
    return settings


def _paper(
    title: str,
    *,
    abstract: str = "摘要",
    found_in: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        authors=[SimpleNamespace(name="作者甲"), {"name": "作者乙"}],
        abstract=abstract,
        publication_date=date(2024, 5, 1),
        found_in=found_in or ["arxiv"],
        url=f"https://example.org/{title}",
        pdf_url=f"https://example.org/{title}.pdf",
    )


def _result(
    papers: list[SimpleNamespace],
    *,
    databases: list[str] | None = None,
    failed_databases: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        query="deep learning",
        papers=papers,
        databases=databases or ["arxiv", "semantic_scholar"],
        failed_databases=failed_databases or [],
    )


def test_get_engine_passes_findpapers_settings(monkeypatch) -> None:
    settings = _settings(
        findpapers_request_timeout_seconds=7.5,
        findpapers_max_retries=2,
        findpapers_rate_limit_retries=0,
        findpapers_ieee_api_token=" ieee ",
        findpapers_scopus_api_token="",
        findpapers_pubmed_api_token="pubmed",
        findpapers_openalex_api_token="openalex",
        findpapers_semantic_scholar_api_token="semantic-scholar",
        findpapers_wos_api_token="wos",
        findpapers_email="paper@example.edu",
        findpapers_proxy="http://127.0.0.1:7890",
        findpapers_ssl_verify=False,
    )
    captured: dict = {}

    def fake_engine(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    academic_adapter.reset_engine()
    monkeypatch.setattr(academic_adapter, "get_settings", lambda: settings)
    monkeypatch.setattr(academic_adapter.findpapers, "Engine", fake_engine)

    assert academic_adapter.get_engine() is academic_adapter.get_engine()
    assert captured["ieee_api_key"] == "ieee"
    assert captured["scopus_api_key"] is None
    assert captured["semantic_scholar_api_key"] == "semantic-scholar"
    assert captured["proxy"] == "http://127.0.0.1:7890"
    assert captured["ssl_verify"] is False
    assert academic_adapter.ConnectorBase._timeout == 7.5
    assert academic_adapter.ConnectorBase._max_retries == 2
    assert academic_adapter.ConnectorBase._max_rate_limit_retries == 0
    academic_adapter.reset_engine()


def test_enabled_databases_are_normalized_and_deduplicated() -> None:
    settings = _settings(findpapers_databases=" arxiv, PUBMED,arxiv ")
    assert academic_adapter.get_enabled_databases(settings) == ["arxiv", "pubmed"]


@pytest.mark.parametrize("value", ["", "arxiv,unknown"])
def test_enabled_databases_reject_invalid_configuration(value: str) -> None:
    with pytest.raises(ApiError) as excinfo:
        academic_adapter.get_enabled_databases(
            _settings(findpapers_databases=value)
        )
    assert excinfo.value.status_code == 500


def test_key_required_database_must_have_key() -> None:
    with pytest.raises(ApiError) as excinfo:
        academic_adapter.get_enabled_databases(
            _settings(findpapers_databases="arxiv,openalex")
        )
    assert excinfo.value.status_code == 500
    assert "openalex" in excinfo.value.message

    assert academic_adapter.get_enabled_databases(
        _settings(
            findpapers_databases="arxiv,openalex",
            findpapers_openalex_api_token="free-key",
        )
    ) == ["arxiv", "openalex"]


def test_shape_search_result_keeps_compatible_fields() -> None:
    data = academic_adapter.shape_search_result(
        _result([_paper("论文一", found_in=["arxiv", "semantic_scholar"])])
    )
    assert data["query"] == "deep learning"
    assert data["total"] == 1
    first = data["results"][0]
    assert first["title"] == "论文一"
    assert first["authors"] == ["作者甲", "作者乙"]
    assert first["year"] == 2024
    assert first["source"] == "arxiv, semantic_scholar"
    assert first["url"].startswith("https://")
    assert first["pdf_url"].endswith(".pdf")
    assert first["abstract"] == "摘要"


def test_shape_search_result_truncates_and_reports_deduplicated_total() -> None:
    papers = [_paper(f"论文{i}") for i in range(20)]
    data = academic_adapter.shape_search_result(_result(papers))
    assert len(data["results"]) == academic_adapter.SEARCH_MAX_ITEMS
    assert data["total"] == 20


def test_shape_search_result_clips_abstract_and_reports_partial_failures() -> None:
    data = academic_adapter.shape_search_result(
        _result([_paper("长摘要", abstract="字" * 500)], failed_databases=["pubmed"])
    )
    abstract = data["results"][0]["abstract"]
    assert len(abstract) <= academic_adapter.ABSTRACT_LIMIT + 3
    assert abstract.endswith("...")
    assert data["platform_messages"] == ["pubmed：搜索失败"]


def test_translate_findpapers_error_codes() -> None:
    assert (
        academic_adapter.translate_findpapers_error(QueryValidationError("查询无效")).code
        == INVALID_PARAM
    )
    assert (
        academic_adapter.translate_findpapers_error(InvalidParameterError("平台无效")).code
        == INVALID_PARAM
    )
    assert (
        academic_adapter.translate_findpapers_error(ConnectorError("连接失败")).code
        == UPSTREAM_ERROR
    )


class _FakeEngine:
    def __init__(self, result: SimpleNamespace | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def search(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_search_uses_configured_databases_by_default(monkeypatch) -> None:
    fake = _FakeEngine(_result([_paper("论文一")]))
    _use_settings(monkeypatch)
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    data = await academic_adapter.search_academic_resources("deep learning")

    query, kwargs = fake.calls[0]
    assert query == "deep learning"
    assert kwargs == {
        "databases": ["arxiv", "pubmed", "semantic_scholar"],
        "max_papers_per_database": 5,
        "num_workers": academic_adapter.SEARCH_WORKERS,
        "show_progress": False,
        "enrichment_databases": [],
    }
    assert data["results"][0]["title"] == "论文一"


@pytest.mark.asyncio
async def test_search_passes_boolean_query_sources_and_limit(monkeypatch) -> None:
    fake = _FakeEngine(_result([_paper("论文一")]))
    _use_settings(
        monkeypatch,
        findpapers_databases="openalex,pubmed",
        findpapers_openalex_api_token="free-key",
    )
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    await academic_adapter.search_academic_resources(
        "[deep learning] AND [medical imaging]",
        sources=["openalex", "pubmed"],
        max_results=3,
    )

    query, kwargs = fake.calls[0]
    assert query == "[deep learning] AND [medical imaging]"
    assert kwargs["databases"] == ["openalex", "pubmed"]
    assert kwargs["max_papers_per_database"] == 3


@pytest.mark.asyncio
async def test_search_translates_connector_error(monkeypatch) -> None:
    fake = _FakeEngine(ConnectorError("连接超时"))
    _use_settings(monkeypatch)
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert excinfo.value.status_code == 502


@pytest.mark.asyncio
async def test_search_rejects_disabled_database(monkeypatch) -> None:
    fake = _FakeEngine(_result([]))
    _use_settings(monkeypatch)
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意", sources=["openalex"])
    assert excinfo.value.code == INVALID_PARAM
    assert excinfo.value.status_code == 400
    assert fake.calls == []


@pytest.mark.asyncio
async def test_search_rejects_empty_sources(monkeypatch) -> None:
    fake = _FakeEngine(_result([]))
    _use_settings(monkeypatch)
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意", sources=[])
    assert excinfo.value.status_code == 400
    assert fake.calls == []


@pytest.mark.asyncio
async def test_search_timeout_is_mapped_to_gateway_timeout(monkeypatch) -> None:
    fake = _FakeEngine(_result([_paper("太迟")]))
    original_search = fake.search

    def slow_search(query: str, **kwargs):
        time.sleep(0.05)
        return original_search(query, **kwargs)

    fake.search = slow_search
    _use_settings(monkeypatch, findpapers_search_timeout_seconds=0.01)
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: fake)

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert excinfo.value.status_code == 504


@pytest.mark.asyncio
async def test_search_all_databases_failed_is_upstream_error(monkeypatch) -> None:
    failed = _result(
        [],
        databases=["arxiv", "openalex"],
        failed_databases=["arxiv", "openalex"],
    )
    _use_settings(monkeypatch, findpapers_databases="arxiv,openalex", findpapers_openalex_api_token="key")
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: _FakeEngine(failed))

    with pytest.raises(ApiError) as excinfo:
        await academic_adapter.search_academic_resources("任意")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert "arxiv" in excinfo.value.message


@pytest.mark.asyncio
async def test_search_true_empty_result_is_not_an_error(monkeypatch) -> None:
    empty = _result([], databases=["arxiv"], failed_databases=[])
    _use_settings(monkeypatch, findpapers_databases="arxiv")
    monkeypatch.setattr(academic_adapter, "get_engine", lambda: _FakeEngine(empty))

    data = await academic_adapter.search_academic_resources("不存在的主题")
    assert data["total"] == 0
    assert data["results"] == []
