"""对话路由：Agent 统一入口。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import build_deps, run_chat, run_chat_stream
from app.api.deps import (
    get_conversation_manager,
    get_information,
    get_knowledge,
    get_required_session,
)
from app.db import get_db
from app.knowledge import KnowledgeService
from app.schemas.common import ok
from app.schemas.requests import ChatRequest
from app.services.conversation import ConversationManager
from app.services.session import JwxtSession

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
    conversations: ConversationManager = Depends(get_conversation_manager),
    knowledge: KnowledgeService = Depends(get_knowledge),
    information: KnowledgeService = Depends(get_information),
):
    """发送自然语言问题，返回文本回答与可选结构化结果。"""
    conversation = await conversations.get_or_create(
        db, session.user_id, payload.conversation_id, payload.message
    )
    deps = build_deps(session, knowledge, information)
    response = await run_chat(
        payload.message, deps, session=session, memory=conversation
    )
    return ok(response.model_dump())


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
    conversations: ConversationManager = Depends(get_conversation_manager),
    knowledge: KnowledgeService = Depends(get_knowledge),
    information: KnowledgeService = Depends(get_information),
):
    """流式对话：逐步推送思考内容、工具调用与最终回答（SSE 格式）。"""
    conversation = await conversations.get_or_create(
        db, session.user_id, payload.conversation_id, payload.message
    )
    deps = build_deps(session, knowledge, information)

    async def event_stream():
        try:
            async for event in run_chat_stream(
                payload.message, deps, memory=conversation
            ):
                ev_type = event["type"]
                if ev_type == "thinking":
                    yield f"event: thinking\ndata: {json.dumps(event['content'], ensure_ascii=False)}\n\n"
                elif ev_type == "tool_call":
                    yield f"event: tool_call\ndata: {json.dumps({'tool_name': event['tool_name']}, ensure_ascii=False)}\n\n"
                elif ev_type == "tool_result":
                    yield f"event: tool_result\ndata: {json.dumps({'tool_name': event['tool_name']}, ensure_ascii=False)}\n\n"
                elif ev_type == "text":
                    yield f"event: text\ndata: {json.dumps(event['content'], ensure_ascii=False)}\n\n"
                elif ev_type == "done":
                    yield f"event: done\ndata: {json.dumps(event['chat'], ensure_ascii=False)}\n\n"
                elif ev_type == "error":
                    error_payload = {
                        "message": event["message"],
                        **({"code": event["code"]} if event.get("code") else {}),
                    }
                    yield f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
