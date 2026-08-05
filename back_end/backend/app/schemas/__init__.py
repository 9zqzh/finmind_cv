"""schemas 包：请求/响应模型与统一错误码。"""

from app.schemas.chat import ChatResponse, ResultType, ToolCallInfo
from app.schemas.common import (
    AUTH_CAPTCHA_INVALID,
    AUTH_FAILED,
    AUTH_REQUIRED,
    INVALID_PARAM,
    KNOWLEDGE_NOT_FOUND,
    MODEL_ERROR,
    PARSE_ERROR,
    SESSION_EXPIRED,
    UPSTREAM_ERROR,
    ApiError,
    fail,
    ok,
)
from app.schemas.requests import ChatRequest, LoginRequest

__all__ = [
    "AUTH_CAPTCHA_INVALID",
    "AUTH_FAILED",
    "AUTH_REQUIRED",
    "INVALID_PARAM",
    "KNOWLEDGE_NOT_FOUND",
    "MODEL_ERROR",
    "PARSE_ERROR",
    "SESSION_EXPIRED",
    "UPSTREAM_ERROR",
    "ApiError",
    "ChatRequest",
    "ChatResponse",
    "LoginRequest",
    "ResultType",
    "ToolCallInfo",
    "fail",
    "ok",
]
