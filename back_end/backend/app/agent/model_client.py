"""DeepSeek（OpenAI 兼容）模型客户端封装。

使用 OpenAIChatModel + 自定义 AsyncOpenAI 客户端，模型名与地址全部可配置。
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import Settings, get_settings

_MODEL_CACHE: dict[tuple[str, str, str], OpenAIChatModel] = {}


def build_model(settings: Settings | None = None) -> OpenAIChatModel:
    """构建 DeepSeek 兼容模型实例（按 基础地址+模型名 缓存）。"""
    settings = settings or get_settings()
    if not settings.model_configured:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写密钥"
        )
    extra_body_key = json.dumps(
        settings.deepseek_extra_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    cache_key = (
        settings.deepseek_base_url,
        settings.deepseek_model,
        extra_body_key,
    )
    if cache_key not in _MODEL_CACHE:
        client = AsyncOpenAI(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            timeout=settings.agent_timeout_seconds,
        )
        _MODEL_CACHE[cache_key] = OpenAIChatModel(
            settings.deepseek_model,
            provider=OpenAIProvider(openai_client=client),
            settings=(
                {"extra_body": settings.deepseek_extra_body}
                if settings.deepseek_extra_body
                else None
            ),
        )
    return _MODEL_CACHE[cache_key]
