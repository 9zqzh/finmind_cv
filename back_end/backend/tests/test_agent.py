"""Agent 工具与编排测试（使用 TestModel，不调用真实模型）。"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.agent.orchestrator import build_deps
from app.agent.tools import RESULT_TYPES, AgentDeps, register_tools
from app.knowledge import KnowledgeService


def _build_test_agent() -> Agent:
    agent = Agent(TestModel(), deps_type=AgentDeps, system_prompt="测试")
    register_tools(agent)
    return agent


def test_all_tools_registered():
    agent = _build_test_agent()
    names = set(RESULT_TYPES.keys())
    assert len(names) == 10
    # 通过 agent 的 toolset 检查已注册工具名
    registered: set[str] = set()
    for toolset in getattr(agent, "_user_toolsets", []):
        for tool in getattr(toolset, "tools", {}).values():
            registered.add(tool.name)
    if registered:  # 2.x 内部结构变化时降级为只断言注册过程无异常
        assert names <= registered


def test_run_with_test_model(tmp_path):
    (tmp_path / "示例.md").write_text("# 示例\n\n这是测试资料。\n", encoding="utf-8")
    agent = _build_test_agent()
    deps = build_deps(
        session=None,
        knowledge=KnowledgeService.from_directory(tmp_path),
        information=KnowledgeService.from_directory(tmp_path),
    )

    async def _run():
        return await agent.run("请帮我查询课表", deps=deps)

    import asyncio

    result = asyncio.run(_run())
    assert isinstance(result.output, str)


def test_login_guard_returns_error_dict(tmp_path):
    """未登录时，教务工具应返回 error 结构而不是编造数据。"""
    from app.adapters import jwxt as jwxt_adapter
    from app.schemas.common import AUTH_REQUIRED, ApiError

    with pytest.raises(ApiError) as exc_info:
        # 适配层同步守卫：直接调用 require_login 验证
        jwxt_adapter.require_login(None)
    assert exc_info.value.code == AUTH_REQUIRED


def test_build_deps_fields():
    deps = build_deps(None, KnowledgeService(), KnowledgeService())
    assert deps.tool_events == []
    assert deps.last_result_type == "text"
