"""学术资源客户端异常体系。

与 gduf_web_api / jwxtapi 保持一致：包内只抛领域异常，
由上层适配层（backend/app/adapters/academic.py）统一映射为 ApiError。
"""

from __future__ import annotations


class AcademicError(Exception):
    """学术资源客户端基础异常。"""


class ValidationError(AcademicError):
    """参数校验失败（如空关键词、未知平台名）。"""


class NetworkError(AcademicError):
    """网络请求失败（超时、连接错误、HTTP 错误状态）。"""


class ParseError(AcademicError):
    """响应解析失败（XML/JSON 结构异常）。"""


class UnsupportedPlatformError(AcademicError):
    """请求了未注册的平台。"""
