"""流式聊天路由回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import chat as chat_api
from app.schemas.requests import ChatRequest


class _ConversationManager:
    async def get_or_create(self, db, user_id, conversation_id, message):
        return {"message": message}


@pytest.mark.asyncio
async def test_chat_stream_does_not_shadow_request_payload(monkeypatch):
    """错误事件的临时数据不能遮蔽外层 ChatRequest。"""
    received_messages: list[str] = []

    async def fake_run_chat_stream(message, deps, memory):
        received_messages.append(message)
        yield {"type": "error", "message": "上游失败", "code": "UPSTREAM_ERROR"}

    monkeypatch.setattr(chat_api, "build_deps", lambda *args: object())
    monkeypatch.setattr(chat_api, "run_chat_stream", fake_run_chat_stream)

    response = await chat_api.chat_stream(
        payload=ChatRequest(message="测试问题"),
        session=SimpleNamespace(user_id=uuid4()),
        db=None,
        conversations=_ConversationManager(),
        knowledge=None,
        information=None,
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in chunks
    )

    assert received_messages == ["测试问题"]
    assert "event: error" in body
    assert "UPSTREAM_ERROR" in body
    assert "cannot access local variable 'payload'" not in body
