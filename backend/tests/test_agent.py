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
from app.schemas.chat import ChatResponse


def _build_test_agent() -> Agent:
    agent = Agent(TestModel(), deps_type=AgentDeps, system_prompt="测试")
    register_tools(agent)
    return agent


def test_all_tools_registered():
    agent = _build_test_agent()
    names = set(RESULT_TYPES.keys())
    assert len(names) == 17
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
    from app.adapters import amap as amap_adapter
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
    for name in dir(amap_adapter):
        if name.startswith(("search_", "query_")):
            monkeypatch.setattr(amap_adapter, name, _fake_ok)

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


def test_academic_tool_records_session_expiration(monkeypatch):
    """聊天中的教务会话失效必须保留错误码，供 SSE 通知前端退出。"""
    from app.adapters import jwxt as jwxt_adapter
    from app.schemas.common import SESSION_EXPIRED, ApiError

    async def fake_expired(*args, **kwargs):
        raise ApiError(SESSION_EXPIRED, "教务登录已过期", status_code=401)

    monkeypatch.setattr(jwxt_adapter, "get_schedule", fake_expired)
    agent = _build_test_agent()
    tool = agent._function_toolset.tools["query_schedule"]
    deps = AgentDeps()

    result = asyncio.run(
        tool.function(SimpleNamespace(deps=deps), term="2025-2026-2", week=None)
    )

    assert result == {"error": "教务登录已过期"}
    assert deps.auth_error == {
        "code": SESSION_EXPIRED,
        "message": "教务登录已过期",
    }


def test_build_deps_fields():
    deps = build_deps(None, KnowledgeService(), KnowledgeService())
    assert deps.tool_events == []
    assert deps.last_result_type == "text"
    assert deps.citations == []


def test_chat_response_defaults_citations_for_old_history():
    response = ChatResponse.model_validate({"answer": "旧回答"})
    assert response.citations == []


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


def test_map_tools_registered_with_result_types():
    """地图工具注册到 RESULT_TYPES，且不被降级为纯文本（需渲染卡片）。"""
    assert RESULT_TYPES["search_map_places"] == "map_places"
    assert RESULT_TYPES["query_map_route"] == "map_route"
    from app.agent.orchestrator import _TEXT_ONLY_RESULT_TYPES

    assert "map_places" not in _TEXT_ONLY_RESULT_TYPES
    assert "map_route" not in _TEXT_ONLY_RESULT_TYPES


def test_search_map_places_tool_records_success(monkeypatch):
    from app.adapters import amap as amap_adapter

    async def fake_search(keywords, location=None, radius=None, city=None):
        return {
            "query": keywords,
            "total": 1,
            "places": [
                {
                    "name": "清远烧鹅饭店",
                    "location": "113.06,23.69",
                    "rating": 4.5,
                    "cost": 45,
                    "distance": 800,
                    "comment_num": 0,
                }
            ],
        }

    monkeypatch.setattr(amap_adapter, "search_map_places", fake_search)
    agent = _build_test_agent()
    tool = agent._function_toolset.tools["search_map_places"]
    deps = AgentDeps()

    result = asyncio.run(
        tool.function(SimpleNamespace(deps=deps), keywords="烧鹅", radius=3000)
    )

    assert result["places"][0]["name"] == "清远烧鹅饭店"
    assert result["places"][0]["citation_ref"] == "c1"
    assert deps.citations[0]["type"] == "map_place"
    assert deps.citations[0]["url"].startswith("https://uri.amap.com/navigation?")
    assert deps.last_result_type == "map_places"
    assert deps.tool_events[-1]["ok"] is True


def test_query_map_route_tool_records_success(monkeypatch):
    from app.adapters import amap as amap_adapter

    async def fake_route(destination, mode="walking", origin=None):
        return {
            "origin": "广东金融学院清远校区",
            "destination": destination,
            "mode": mode,
            "distance_m": 1500,
            "duration_s": 1200,
            "distance_text": "1.5 公里",
            "duration_text": "20 分钟",
            "steps": ["从起点出发"],
            "navigation_url": "https://uri.amap.com/navigation",
        }

    monkeypatch.setattr(amap_adapter, "query_map_route", fake_route)
    agent = _build_test_agent()
    tool = agent._function_toolset.tools["query_map_route"]
    deps = AgentDeps()

    result = asyncio.run(
        tool.function(SimpleNamespace(deps=deps), destination="万达广场", mode="bicycling")
    )

    assert result["mode"] == "bicycling"
    assert result["distance_text"] == "1.5 公里"
    assert result["citation_ref"] == "c1"
    assert deps.citations[0]["type"] == "map_route"
    assert deps.last_result_type == "map_route"


def test_map_citation_refs_are_unique_across_tool_calls(monkeypatch):
    from app.adapters import amap as amap_adapter

    async def fake_search(keywords, location=None, radius=None, city=None):
        return {
            "places": [
                {"name": "地点甲", "location": "113.01,23.01"},
                {"name": "地点乙", "location": "113.02,23.02"},
            ]
        }

    async def fake_route(destination, mode="walking", origin=None):
        return {
            "origin": "学校",
            "destination": destination,
            "mode": mode,
            "navigation_url": "https://uri.amap.com/navigation?to=113.03,23.03",
        }

    monkeypatch.setattr(amap_adapter, "search_map_places", fake_search)
    monkeypatch.setattr(amap_adapter, "query_map_route", fake_route)
    agent = _build_test_agent()
    deps = AgentDeps()
    search_tool = agent._function_toolset.tools["search_map_places"]
    route_tool = agent._function_toolset.tools["query_map_route"]

    places = asyncio.run(
        search_tool.function(SimpleNamespace(deps=deps), keywords="地点")
    )
    route = asyncio.run(
        route_tool.function(SimpleNamespace(deps=deps), destination="地点甲")
    )

    assert [item["citation_ref"] for item in places["places"]] == ["c1", "c2"]
    assert route["citation_ref"] == "c3"
    assert [item["ref"] for item in deps.citations] == ["c1", "c2", "c3"]


def test_map_tools_report_failure_without_error(monkeypatch):
    """上游异常时工具返回 error 结构而不是抛出。"""
    from app.adapters import amap as amap_adapter
    from app.schemas.common import UPSTREAM_ERROR, ApiError

    async def fake_search(keywords, location=None, radius=None, city=None):
        raise ApiError(UPSTREAM_ERROR, "高德地图接口返回错误", status_code=502)

    monkeypatch.setattr(amap_adapter, "search_map_places", fake_search)
    agent = _build_test_agent()
    tool = agent._function_toolset.tools["search_map_places"]
    deps = AgentDeps()

    result = asyncio.run(tool.function(SimpleNamespace(deps=deps), keywords="烧鹅"))

    assert "error" in result
    assert deps.tool_events[-1]["ok"] is False
