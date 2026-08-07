from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from gduf_web_api import GdufClient

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def request_log() -> list[httpx.Request]:
    return []


@pytest.fixture
def transport(request_log: list[httpx.Request]) -> httpx.MockTransport:
    article_roots = {"/jxky/xyxw.htm", "/xshd1.htm", "/xshd.htm", "/tzgg.htm"}
    content_paths = {
        "/xygk/xyjj.htm",
        "/xygk/jgsz.htm",
        "/zyjx/jsjkxyjs.htm",
        "/zyjx/rjgc.htm",
        "/zyjx/sjkxydsjjs.htm",
        "/zyjx/yytjx.htm",
        "/zyjx/rgzn.htm",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        request_log.append(request)
        path = request.url.path
        if request.url.host == "ai-data-competitions.cn":
            if path == "/api/competitions":
                name = "aijspt_competitions.json"
                content_type = "application/json"
            elif path == "/api/notices/published":
                name = "aijspt_notices.json"
                content_type = "application/json"
            elif path == "/clubs":
                name = "aijspt_clubs.html"
                content_type = "text/html; charset=utf-8"
            elif path == "/competitions/3c3f766f-684f-46cb-b265-a686a9f3738b":
                name = "aijspt_detail.html"
                content_type = "text/html; charset=utf-8"
            else:
                return httpx.Response(404, request=request)
            return httpx.Response(
                200,
                text=fixture_text(name),
                headers={"content-type": content_type},
                request=request,
            )
        if request.method == "POST" and path == "/search.jsp":
            return httpx.Response(200, text=fixture_text("search.html"), request=request)
        if path == "/":
            name = "home.html"
        elif path in article_roots:
            name = "article_list_first.html"
        elif re_page_path(path):
            name = "article_list_middle.html"
        elif path == "/xygk/xyld.htm":
            name = "leader_list.html"
        elif path in {"/xygk/zrjs.htm", "/xygk/jfry.htm"}:
            name = "staff_list.html"
        elif path in content_paths:
            name = "static_content.html"
        elif path.startswith("/info/"):
            name = "detail.html"
        else:
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            text=fixture_text(name),
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )

    return httpx.MockTransport(handler)


def re_page_path(path: str) -> bool:
    return path.endswith("/2.htm") and not path.startswith("/info/")


@pytest.fixture
def client(transport: httpx.MockTransport) -> Iterator[GdufClient]:
    with GdufClient(transport=transport, retries=0) as active:
        yield active
