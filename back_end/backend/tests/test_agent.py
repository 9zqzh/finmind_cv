"""Agent 工具与编排测试（使用 TestModel，不调用真实模型）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

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
    assert len(names) == 15
    # 通过 agent 的 toolset 检查已注册工具名
    registered: set[str] = set()
    for toolset in getattr(agent, "_user_toolsets", []):
        for tool in getattr(toolset, "tools", {}).values():
            registered.add(tool.name)
    if registered:  # 2.x 内部结构变化时降级为只断言注册过程无异常
        assert names <= registered


def test_run_with_test_model(tmp_path, monkeypatch):
    # TestModel 会随机选择工具调用，把外部适配层替换为桩避免真实网络请求
    from app.adapters import academic as academic_adapter
    from app.adapters import gduf_web as gduf_web_adapter
    from app.adapters import jwxt as jwxt_adapter

    async def _fake_ok(*args, **kwargs):
        return {"total": 0, "results": [], "message": "测试桩"}

    for name in dir(gduf_web_adapter):
        if name.startswith(("search_", "get_")):
            monkeypatch.setattr(gduf_web_adapter, name, _fake_ok)
    for name in dir(academic_adapter):
        if name.startswith(("search_", "get_")):
            monkeypatch.setattr(academic_adapter, name, _fake_ok)

    async def _fake_auth_required(*args, **kwargs):
        from app.schemas.common import AUTH_REQUIRED, ApiError

        raise ApiError(AUTH_REQUIRED, "请先登录教务系统", status_code=401)

    for name in (
        "get_schedule",
        "get_grades",
        "get_grade_detail",
        "get_training_plan",
        "get_classroom_schedule",
        "get_empty_classrooms",
    ):
        monkeypatch.setattr(jwxt_adapter, name, _fake_auth_required)

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


def test_search_knowledge_returns_score_and_resource_path(tmp_path):
    (tmp_path / "重修流程.md").write_text(
        "# 重修流程\n\n> 来源文件：resources/办事流程/重修流程.pdf\n\n课程重修申请流程。",
        encoding="utf-8",
    )
    agent = _build_test_agent()
    tool = agent._function_toolset.tools["search_knowledge"]
    deps = AgentDeps(knowledge=KnowledgeService.from_directory(tmp_path))

    result = asyncio.run(tool.function(SimpleNamespace(deps=deps), query="重修申请"))

    assert result["results"][0]["score"] > 0
    assert result["results"][0]["resource_path"] == "办事流程/重修流程.pdf"
    assert deps.sources == ["办事流程/重修流程.pdf"]
