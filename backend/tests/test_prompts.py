"""Agent 系统提示词构建测试。"""

from __future__ import annotations

from datetime import date

from app.agent.prompts import build_system_prompt
from app.config import Settings


def test_system_prompt_injects_enabled_academic_databases() -> None:
    settings = Settings(
        _env_file=None,
        FINDPAPERS_DATABASES="arxiv,openalex,pubmed",
        FINDPAPERS_OPENALEX_API_TOKEN="test-key",
    )

    prompt = build_system_prompt(date(2026, 8, 23), settings=settings)

    assert "今天是 2026-08-23（星期日）" in prompt
    assert "当前启用的学术搜索平台：arxiv、openalex、pubmed" in prompt
    assert "sources 只能从这些平台中选择" in prompt


def test_system_prompt_uses_safe_default_academic_databases() -> None:
    settings = Settings(_env_file=None)

    prompt = build_system_prompt(date(2026, 8, 23), settings=settings)

    assert "当前启用的学术搜索平台：arxiv、pubmed、semantic_scholar" in prompt
    assert "openalex、" not in prompt.split("## 你的能力", 1)[0]
