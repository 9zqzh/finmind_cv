"""临时四轮对话记忆测试（使用 PydanticAI TestModel，不依赖真实模型与密钥）。"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.test import TestModel

from app.agent import orchestrator
from app.agent.orchestrator import HISTORY_MAX_TURNS, _load_history, run_chat, run_chat_stream
from app.agent.tools import AgentDeps
from app.config import Settings
from app.services.conversation import ConversationManager, ConversationMemory, ConversationTurn
from app.services.session import JwxtSession


def _fake_session() -> JwxtSession:
    """构造一个不连接真实教务客户端的登录会话对象。"""
    return JwxtSession(token="login-token", client=None)  # type: ignore[arg-type]


def _fake_deps() -> AgentDeps:
    return AgentDeps(session=None, knowledge=None, information=None)


@pytest.fixture
def test_agent(monkeypatch):
    """把全局 Agent 替换为 TestModel，避免真实模型调用。"""

    def fake_get_agent(settings=None) -> Agent:
        return Agent(TestModel())

    monkeypatch.setattr(orchestrator, "get_agent", fake_get_agent)


def _history_text(memory: ConversationMemory) -> str:
    return ModelMessagesTypeAdapter.dump_json(_load_history(memory)).decode()


@pytest.mark.asyncio
async def test_guest_and_logged_in_chat_share_the_same_temporary_memory(test_agent):
    memory = ConversationMemory(conversation_id="page-1")

    guest = await run_chat("我今天有什么课？", _fake_deps(), memory=memory)
    logged_in = await run_chat(
        "那明天呢？", _fake_deps(), session=_fake_session(), memory=memory
    )

    assert guest.conversation_id == "page-1"
    assert logged_in.conversation_id == "page-1"
    assert len(memory.chat_history) == 2
    assert "我今天有什么课？" in _history_text(memory)
    assert "那明天呢？" in _history_text(memory)


@pytest.mark.asyncio
async def test_history_keeps_exactly_the_latest_four_turns(test_agent):
    memory = ConversationMemory(conversation_id="page-1")
    for index in range(HISTORY_MAX_TURNS + 2):
        await run_chat(f"第 {index} 轮问题", _fake_deps(), memory=memory)

    assert HISTORY_MAX_TURNS == 4
    assert len(memory.chat_history) == 4
    history = _history_text(memory)
    assert "第 0 轮问题" not in history
    assert "第 1 轮问题" not in history
    assert "第 2 轮问题" in history
    assert "第 5 轮问题" in history


@pytest.mark.asyncio
async def test_conversations_are_isolated(test_agent):
    first = ConversationMemory(conversation_id="page-1")
    second = ConversationMemory(conversation_id="page-2")

    await run_chat("第一位用户的问题", _fake_deps(), memory=first)
    await run_chat("第二位用户的问题", _fake_deps(), memory=second)

    assert "第一位用户的问题" in _history_text(first)
    assert "第一位用户的问题" not in _history_text(second)
    assert "第二位用户的问题" not in _history_text(first)


@pytest.mark.asyncio
async def test_streaming_chat_saves_a_completed_turn(test_agent):
    memory = ConversationMemory(conversation_id="page-1")

    events = [
        event
        async for event in run_chat_stream("流式问题", _fake_deps(), memory=memory)
    ]

    assert any(event["type"] == "done" for event in events)
    done_event = next(event for event in events if event["type"] == "done")
    assert done_event["chat"]["conversation_id"] == "page-1"
    assert len(memory.chat_history) == 1
    assert "流式问题" in _history_text(memory)

    await run_chat("普通接口追问", _fake_deps(), memory=memory)
    assert len(memory.chat_history) == 2
    assert "普通接口追问" in _history_text(memory)


def test_expired_conversation_is_recreated_without_history():
    manager = ConversationManager(Settings(session_ttl_minutes=1))
    original = manager.get_or_create("page-1")
    assert original is not None
    original.chat_history.append(ConversationTurn(model_messages_json="[]"))
    original.last_active = 0

    recreated = manager.get_or_create("page-1")

    assert recreated is not None
    assert recreated is not original
    assert recreated.chat_history == []


@pytest.mark.asyncio
async def test_corrupted_history_degrades_to_a_new_turn(test_agent):
    memory = ConversationMemory(conversation_id="page-1")
    await run_chat("第一轮", _fake_deps(), memory=memory)
    memory.chat_history[0].model_messages_json = "{invalid-json"

    response = await run_chat("第二轮", _fake_deps(), memory=memory)

    assert response.answer
    assert len(memory.chat_history) == 1
    assert "第二轮" in _history_text(memory)
