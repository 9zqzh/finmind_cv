"""Typed access to public Guangdong University of Finance website content."""

from gduf_web_api.api import (
    get_ai_detail,
    get_ai_home,
    get_ai_jfry,
    get_ai_jgsz,
    get_ai_jsjkxyjs,
    get_ai_rgzn,
    get_ai_rjgc,
    get_ai_sjkxydsjjs,
    get_ai_tzgg,
    get_ai_xshenghd,
    get_ai_xshuhd,
    get_ai_xyjj,
    get_ai_xyld,
    get_ai_xyxw,
    get_ai_yytjx,
    get_ai_zrjs,
    search_ai,
)
from gduf_web_api.client import GdufClient
from gduf_web_api.errors import (
    GdufError,
    InvalidPageError,
    NetworkError,
    ParseError,
    UnsupportedSourceError,
)
from gduf_web_api.models import AiHome, ArticleSummary, ContentDetail, PageResult, PersonSummary

__version__ = "0.1.0"

__all__ = [
    "AiHome",
    "ArticleSummary",
    "ContentDetail",
    "GdufClient",
    "GdufError",
    "InvalidPageError",
    "NetworkError",
    "PageResult",
    "ParseError",
    "PersonSummary",
    "UnsupportedSourceError",
    "get_ai_detail",
    "get_ai_home",
    "get_ai_jfry",
    "get_ai_jgsz",
    "get_ai_jsjkxyjs",
    "get_ai_rgzn",
    "get_ai_rjgc",
    "get_ai_sjkxydsjjs",
    "get_ai_tzgg",
    "get_ai_xshenghd",
    "get_ai_xshuhd",
    "get_ai_xyjj",
    "get_ai_xyld",
    "get_ai_xyxw",
    "get_ai_yytjx",
    "get_ai_zrjs",
    "search_ai",
]

