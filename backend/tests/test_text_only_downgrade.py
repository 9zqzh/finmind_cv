"""纯文本降级测试：特定工具的结构化数据不得发往前端展示层。"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.agent import orchestrator
from app.agent.orchestrator import _TEXT_ONLY_RESULT_TYPES, run_chat
from app.agent.tools import AgentDeps


@pytest.fixture
def test_agent(monkeypatch):
    """把全局 Agent 替换为 TestModel，避免真实模型调用。"""

    def fake_get_agent(settings=None) -> Agent:
        return Agent(TestModel())

    monkeypatch.setattr(orchestrator, "get_agent", fake_get_agent)


def _deps_with_tool_result(tool: str, result_type: str, data: dict) -> AgentDeps:
    """模拟一次工具成功调用后的 deps 状态。"""
    deps = AgentDeps(session=None, knowledge=None, information=None)
    deps.tool_events.append({"tool": tool, "result_type": result_type, "ok": True})
    deps.last_result_type = result_type
    deps.last_data = data
    return deps


@pytest.mark.asyncio
async def test_empty_classrooms_data_not_sent_to_frontend(test_agent):
    """query_empty_classrooms 的结构化结果必须降级为纯文本，data 为 None。"""
    raw = {"term": "2026-2027-1", "free_count": 2, "free_classrooms": ["1-401", "1-402"]}
    deps = _deps_with_tool_result("query_empty_classrooms", "empty_classrooms", raw)
    response = await run_chat("周三下午有哪些空教室？", deps)
    assert response.result_type == "text"
    assert response.data is None
    assert response.sources == []


@pytest.mark.asyncio
async def test_knowledge_and_information_still_downgraded(test_agent):
    """知识库/资讯检索的降级行为保持不变。"""
    assert {"knowledge", "information"} <= _TEXT_ONLY_RESULT_TYPES
    deps = _deps_with_tool_result("search_knowledge", "knowledge", {"chunks": ["原文"]})
    response = await run_chat("缓考怎么申请？", deps)
    assert response.result_type == "text"
    assert response.data is None


@pytest.mark.asyncio
async def test_competition_results_downgraded(test_agent):
    """竞赛列表、详情、通知与社团的结构化结果必须降级为纯文本，data 为 None。"""
    assert {
        "competition",
        "competition_detail",
        "competition_notice",
        "competition_club",
    } <= _TEXT_ONLY_RESULT_TYPES
    raw = {"total": 1, "results": [{"title": "软件设计大赛", "status": "registration_open"}]}
    deps = _deps_with_tool_result("query_competitions", "competition", raw)
    response = await run_chat("最近有什么竞赛可以参加？", deps)
    assert response.result_type == "text"
    assert response.data is None

    detail = {"competition": {"title": "软件设计大赛"}, "timeline": []}
    deps = _deps_with_tool_result("query_competition_detail", "competition_detail", detail)
    response = await run_chat("这个比赛怎么报名？", deps)
    assert response.result_type == "text"
    assert response.data is None

    notices = {"total": 1, "results": [{"title": "关于举办大赛的通知"}]}
    deps = _deps_with_tool_result("query_competition_notices", "competition_notice", notices)
    response = await run_chat("竞赛平台有什么新通知？", deps)
    assert response.result_type == "text"
    assert response.data is None

    clubs = {"total": 1, "results": [{"name": "算法竞赛社团"}]}
    deps = _deps_with_tool_result("query_competition_clubs", "competition_club", clubs)
    response = await run_chat("学院有哪些竞赛社团？", deps)
    assert response.result_type == "text"
    assert response.data is None


@pytest.mark.asyncio
async def test_structured_cards_keep_data(test_agent):
    """课表/成绩等卡片类结果不受影响，data 原样返回。"""
    raw = {"term": "2026-2027-1", "items": []}
    deps = _deps_with_tool_result("query_schedule", "schedule", raw)
    response = await run_chat("我今天有什么课？", deps)
    assert response.result_type == "schedule"
    assert response.data == raw
