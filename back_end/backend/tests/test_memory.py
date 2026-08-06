"""对话多轮记忆测试（使用 PydanticAI TestModel，不依赖真实模型与密钥）。"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.agent import orchestrator
from app.agent.orchestrator import HISTORY_MAX_TURNS, run_chat
from app.agent.tools import AgentDeps
from app.services.session import JwxtSession


def _fake_session() -> JwxtSession:
    """构造一个不连接真实教务客户端的会话对象。"""
    return JwxtSession(token="test-token", client=None)  # type: ignore[arg-type]


def _fake_deps() -> AgentDeps:
    return AgentDeps(session=None, knowledge=None, information=None)


@pytest.fixture
def test_agent(monkeypatch):
    """把全局 Agent 替换为 TestModel，避免真实模型调用。"""

    def fake_get_agent(settings=None) -> Agent:
        return Agent(TestModel())

    monkeypatch.setattr(orchestrator, "get_agent", fake_get_agent)


@pytest.mark.asyncio
async def test_chat_history_accumulates_across_turns(test_agent):
    session = _fake_session()
    first = await run_chat("我今天有什么课？", _fake_deps(), session=session)
    assert first.conversation_id == "test-token"
    assert len(session.chat_history) == 1

    second = await run_chat("那明天呢？", _fake_deps(), session=session)
    assert second.conversation_id == "test-token"
    assert len(session.chat_history) == 2

    # 第二轮保存的模型消息必须包含第一轮的提问（证明历史被传入并累积）
    assert "我今天有什么课？" in session.chat_history[1].model_messages_json
    assert "那明天呢？" in session.chat_history[1].model_messages_json


@pytest.mark.asyncio
async def test_history_sliding_window_trims_old_turns(test_agent):
    session = _fake_session()
    for i in range(HISTORY_MAX_TURNS + 3):
        await run_chat(f"第 {i} 轮问题", _fake_deps(), session=session)
    assert len(session.chat_history) == HISTORY_MAX_TURNS
    # 最早的轮次已被丢弃
    assert "第 0 轮问题" not in session.chat_history[0].user_message


@pytest.mark.asyncio
async def test_chat_without_session_has_no_memory(test_agent):
    response = await run_chat("你好", _fake_deps(), session=None)
    assert response.conversation_id is None


@pytest.mark.asyncio
async def test_corrupted_history_degrades_gracefully(test_agent):
    session = _fake_session()
    await run_chat("第一轮", _fake_deps(), session=session)
    # 人为破坏序列化数据，模拟版本升级导致的不兼容
    session.chat_history[0].model_messages_json = "{invalid-json"
    response = await run_chat("第二轮", _fake_deps(), session=session)
    assert response.answer  # 本轮仍正常返回
    # 损坏历史被清空后重新记录本轮
    assert len(session.chat_history) == 1
    assert session.chat_history[0].user_message == "第二轮"
