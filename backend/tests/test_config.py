"""配置读取测试。"""

from __future__ import annotations

from app.config import Settings


def test_embedding_key_file_is_used_without_exposing_key(tmp_path):
    key_file = tmp_path / "embedding-key.txt"
    key_file.write_text(
        "阿里云百炼嵌入模型 API key\n"
        "unit-test-embedding-key-1234567890\n"
        "https://example.com/compatible-mode/v1\n",
        encoding="utf-8",
    )

    settings = Settings(
        _env_file=None,
        EMBEDDING_BASE_URL="https://example.com/v1",
        EMBEDDING_API_KEY_FILE=str(key_file),
        EMBEDDING_MODEL="qwen3.7-text-embedding",
    )

    assert settings.embedding_configured is True
    assert settings.embedding_api_key_value == "unit-test-embedding-key-1234567890"


def test_model_extra_body_is_loaded_from_json_env(monkeypatch):
    monkeypatch.setenv(
        "DEEPSEEK_EXTRA_BODY",
        '{"thinking":{"type":"enabled"},"reasoning_effort":"max"}',
    )

    settings = Settings(_env_file=None)

    assert settings.deepseek_extra_body == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "max",
    }
