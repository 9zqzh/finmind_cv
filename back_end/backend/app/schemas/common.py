"""统一响应结构与错误码约定（见《技术选型与五人分工规划》5.2 节）。"""

from __future__ import annotations

from typing import Any

# ---- 错误码常量 ----
AUTH_REQUIRED = "AUTH_REQUIRED"
AUTH_CAPTCHA_INVALID = "AUTH_CAPTCHA_INVALID"
AUTH_FAILED = "AUTH_FAILED"
SESSION_EXPIRED = "SESSION_EXPIRED"
UPSTREAM_ERROR = "UPSTREAM_ERROR"
PARSE_ERROR = "PARSE_ERROR"
KNOWLEDGE_NOT_FOUND = "KNOWLEDGE_NOT_FOUND"
NOT_FOUND = "NOT_FOUND"
MODEL_ERROR = "MODEL_ERROR"
INVALID_PARAM = "INVALID_PARAM"


class ApiError(Exception):
    """业务异常：由全局异常处理器转换为统一失败响应。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def ok(data: Any = None, message: str | None = None) -> dict[str, Any]:
    """成功响应包装。"""
    return {"success": True, "data": data, "message": message}


def fail(code: str, message: str) -> dict[str, Any]:
    """失败响应包装。"""
    return {"success": False, "data": None, "message": message, "code": code}
