from __future__ import annotations

import base64
from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest

import gduf_web_api as api
from gduf_web_api import (
    GdufClient,
    InvalidPageError,
    NetworkError,
    ParseError,
    UnsupportedSourceError,
)


@pytest.mark.parametrize(
    ("category", "path"),
    [
        ("xyxw", "/jxky/xyxw.htm"),
        ("xshuhd", "/xshd1.htm"),
        ("xshenghd", "/xshd.htm"),
        ("tzgg", "/tzgg.htm"),
    ],
)
def test_article_routes_and_models(
    client: GdufClient,
    request_log: list[httpx.Request],
    category: str,
    path: str,
) -> None:
    result = client.get_articles(category)

    assert request_log[-1].url.path == path
    assert result.page == 1
    assert result.total_items == 31
    assert result.total_pages == 3
    assert result.items[0].title == "学院新闻标题"
    assert result.items[0].published_at == date(2026, 7, 8)
    assert result.items[0].category == category
    assert result.to_dict()["items"][0]["published_at"] == "2026-07-08"


def test_reverse_pagination_and_page_validation(
    client: GdufClient, request_log: list[httpx.Request]
) -> None:
    result = client.get_articles("xyxw", 2)

    assert [request.url.path for request in request_log] == [
        "/jxky/xyxw.htm",
        "/jxky/xyxw/2.htm",
    ]
    assert result.page == 2
    assert result.items[0].title == "中间页新闻"

    with pytest.raises(InvalidPageError):
        client.get_articles("xyxw", 4)
    for invalid in (0, -1, True):
        with pytest.raises(InvalidPageError):
            client.get_articles("xyxw", invalid)


@pytest.mark.parametrize(
    ("category", "path"),
    [("xyld", "/xygk/xyld.htm"), ("zrjs", "/xygk/zrjs.htm"), ("jfry", "/xygk/jfry.htm")],
)
def test_people_routes(
    client: GdufClient,
    request_log: list[httpx.Request],
    category: str,
    path: str,
) -> None:
    result = client.get_people(category)
    assert request_log[-1].url.path == path
    assert len(result.items) == 2
    assert result.items[0].image_url.startswith("https://ai.gduf.edu.cn/")
    if category == "xyld":
        assert result.items[0].name == "何飞"
        assert result.items[0].role == "党总支书记"
        assert result.items[0].group == "党委"
        assert result.items[0].responsibility == "负责党务工作。"
    else:
        assert result.items[0].name == "廖文辉"
        assert result.items[0].role == "教授"


@pytest.mark.parametrize(
    ("category", "path"),
    [
        ("xyjj", "/xygk/xyjj.htm"),
        ("jgsz", "/xygk/jgsz.htm"),
        ("jsjkxyjs", "/zyjx/jsjkxyjs.htm"),
        ("rjgc", "/zyjx/rjgc.htm"),
        ("sjkxydsjjs", "/zyjx/sjkxydsjjs.htm"),
        ("yytjx", "/zyjx/yytjx.htm"),
        ("rgzn", "/zyjx/rgzn.htm"),
    ],
)
def test_static_content_routes(
    client: GdufClient,
    request_log: list[httpx.Request],
    category: str,
    path: str,
) -> None:
    result = client.get_content(category)
    assert request_log[-1].url.path == path
    assert result.title == "计算机科学与技术"
    assert result.category == category
    assert result.kind == "static"
    assert "学制：四年" in result.content_text  # noqa: RUF001
    assert "script" not in result.content_html
    assert "style=" not in result.content_html
    assert result.attachments == ("https://ai.gduf.edu.cn/files/plan.pdf",)


def test_home_aggregation_and_deduplication(client: GdufClient) -> None:
    home = client.get_home()
    assert len(home.xyxw) == 1
    assert home.xshuhd[0].summary == "报告摘要"
    assert home.xshenghd[0].title == "学生比赛"
    assert home.tzgg[0].published_at == date(2026, 6, 4)


def test_detail_sanitizes_html_and_restricts_domain(client: GdufClient) -> None:
    detail = client.get_detail("/info/1056/1313.htm")
    assert detail.title == "测试文章"
    assert detail.published_at == date(2026, 7, 8)
    assert detail.attribution == "本站"
    assert detail.view_count == 260
    assert detail.images == ("https://ai.gduf.edu.cn/__local/picture.png",)
    assert detail.attachments == ("https://ai.gduf.edu.cn/files/data.xlsx",)
    assert detail.previous_url == "https://ai.gduf.edu.cn/info/1056/1314.htm"
    assert detail.next_url == "https://ai.gduf.edu.cn/info/1056/1312.htm"
    assert "onmouseover" not in detail.content_html
    assert "script" not in detail.content_html

    with pytest.raises(ValueError, match="must belong"):
        client.get_detail("https://example.com/private")


def test_search_protocol_and_results(
    client: GdufClient, request_log: list[httpx.Request]
) -> None:
    result = client.search("羽毛球", 2)
    request = request_log[-1]
    body = parse_qs(request.content.decode())

    assert request.method == "POST"
    assert request.url.params["currentnum"] == "2"
    assert body["_lucenesearchtype"] == ["2"]
    assert base64.b64decode(body["newskeycode2"][0]).decode() == "羽毛球"
    assert result.page == 2
    assert result.total_pages == 3
    assert result.items[0].title == "第一届 羽毛球 赛"

    with pytest.raises(ValueError, match="cannot be empty"):
        client.search("  ")


def test_public_helpers_reuse_a_client(client: GdufClient) -> None:
    assert api.get_ai_xyxw(client=client).items
    assert api.get_ai_xshuhd(client=client).items
    assert api.get_ai_xshenghd(client=client).items
    assert api.get_ai_tzgg(client=client).items
    assert api.get_ai_xyld(client=client).items
    assert api.get_ai_zrjs(client=client).items
    assert api.get_ai_jfry(client=client).items
    assert api.get_ai_xyjj(client=client).content_text
    assert api.get_ai_jgsz(client=client).content_text
    assert api.get_ai_jsjkxyjs(client=client).content_text
    assert api.get_ai_rjgc(client=client).content_text
    assert api.get_ai_sjkxydsjjs(client=client).content_text
    assert api.get_ai_yytjx(client=client).content_text
    assert api.get_ai_rgzn(client=client).content_text
    assert api.get_ai_home(client=client).xyxw
    assert api.search_ai("羽毛球", 2, client=client).items
    assert api.get_ai_detail("/info/1056/1313.htm", client=client).content_text


def test_error_boundaries() -> None:
    failing_transport = httpx.MockTransport(
        lambda request: httpx.Response(500, request=request)
    )
    with GdufClient(transport=failing_transport, retries=0) as client:
        with pytest.raises(NetworkError):
            client.get_home()
        with pytest.raises(UnsupportedSourceError):
            client.get_home("missing")
        with pytest.raises(ParseError):
            client.get_articles("missing")

    with pytest.raises(ValueError):
        GdufClient(timeout=0)
    with pytest.raises(ValueError):
        GdufClient(retries=-1)


def test_client_context_closes() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    client = GdufClient(transport=transport)
    with client:
        assert not client.is_closed
    assert client.is_closed
    with pytest.raises(NetworkError, match="already closed"):
        client.get_home()


def test_version_and_exports() -> None:
    assert api.__version__ == "0.1.1"
    expected = {
        "get_ai_xyxw",
        "get_ai_xshuhd",
        "get_ai_xshenghd",
        "get_ai_tzgg",
        "get_ai_xyjj",
        "get_ai_jgsz",
        "get_ai_xyld",
        "get_ai_zrjs",
        "get_ai_jfry",
        "get_ai_jsjkxyjs",
        "get_ai_rjgc",
        "get_ai_sjkxydsjjs",
        "get_ai_yytjx",
        "get_ai_rgzn",
        "search_ai",
        "get_ai_detail",
    }
    assert expected.issubset(api.__all__)
