"""学术资源平台适配器基类。

新增平台只需：在 platforms/ 下创建模块，继承 BasePlatform 并用 @register 装饰。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from academic_api.errors import ValidationError
from academic_api.models import AcademicResource


class BasePlatform(ABC):
    """平台适配器抽象基类：每个子类对接一个学术资源平台。"""

    # 子类必须定义的平台标识（小写下划线，如 "arxiv"）
    name: str = ""
    # 平台展示名（如 "arXiv"）
    display_name: str = ""

    # 摘要截断长度，控制上下文占用
    ABSTRACT_LIMIT = 500
    # 作者列表最大保留数
    MAX_AUTHORS = 5

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> list[AcademicResource]:
        """按关键词搜索平台资源；实现方应只抛领域异常（NetworkError/ParseError）。"""

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        """规范化空白并在超长时截断。"""
        text = " ".join(text.split())
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def _validate_query(self, query: str) -> None:
        if not query or not query.strip():
            raise ValidationError("搜索关键词不能为空")
