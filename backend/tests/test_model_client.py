"""模型客户端配置测试（不发送真实网络请求）。"""

from __future__ import annotations

from app.agent import model_client
from app.config import Settings


def test_build_model_passes_extra_body_to_pydantic_ai():
    model_client._MODEL_CACHE.clear()
    settings = Settings(
        _env_file=None,
        DEEPSEEK_API_KEY="test-key",
        DEEPSEEK_BASE_URL="https://example.com/v1",
        DEEPSEEK_MODEL="test-model",
        DEEPSEEK_EXTRA_BODY={
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
        },
    )

    model = model_client.build_model(settings)

    assert model.settings["extra_body"] == settings.deepseek_extra_body
    model_client._MODEL_CACHE.clear()


def test_extra_body_is_part_of_model_cache_key():
    model_client._MODEL_CACHE.clear()
    common = {
        "_env_file": None,
        "DEEPSEEK_API_KEY": "test-key",
        "DEEPSEEK_BASE_URL": "https://example.com/v1",
        "DEEPSEEK_MODEL": "test-model",
    }

    regular = model_client.build_model(
        Settings(**common, DEEPSEEK_EXTRA_BODY={"reasoning_effort": "high"})
    )
    strong = model_client.build_model(
        Settings(**common, DEEPSEEK_EXTRA_BODY={"reasoning_effort": "max"})
    )

    assert regular is not strong
    model_client._MODEL_CACHE.clear()
