"""gduf-academic-api：学术资源聚合检索客户端（arXiv、Semantic Scholar 等）。"""

from academic_api.api import search_academic
from academic_api.client import AcademicClient
from academic_api.errors import (
    AcademicError,
    NetworkError,
    ParseError,
    UnsupportedPlatformError,
    ValidationError,
)
from academic_api.models import AcademicResource, AcademicSearchResult
from academic_api.platforms import list_platforms

__version__ = "0.1.0"

__all__ = [
    "AcademicClient",
    "AcademicError",
    "AcademicResource",
    "AcademicSearchResult",
    "NetworkError",
    "ParseError",
    "UnsupportedPlatformError",
    "ValidationError",
    "list_platforms",
    "search_academic",
]
