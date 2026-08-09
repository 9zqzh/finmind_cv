"""对话路由：Agent 统一入口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.orchestrator import build_deps, run_chat, run_chat_stream
from app.api.deps import (
    get_information,
    get_knowledge,
    get_optional_conversation,
    get_optional_session,
)
from app.knowledge import KnowledgeService
from app.schemas.common import ok
from app.schemas.requests import ChatRequest
from app.services.conversation import ConversationMemory
from app.services.session import JwxtSession

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    session: JwxtSession | None = Depends(get_optional_session),
    conversation: ConversationMemory | None = Depends(get_optional_conversation),
    knowledge: KnowledgeService = Depends(get_knowledge),
    information: KnowledgeService = Depends(get_information),
):
    """发送自然语言问题，返回文本回答与可选结构化结果。"""
    deps = build_deps(session, knowledge, information)
    response = await run_chat(
        payload.message, deps, session=session, memory=conversation
    )
    return ok(response.model_dump())


import json
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    session: JwxtSession | None = Depends(get_optional_session),
    conversation: ConversationMemory | None = Depends(get_optional_conversation),
    knowledge: KnowledgeService = Depends(get_knowledge),
    information: KnowledgeService = Depends(get_information),
):
    """流式对话：逐步推送思考内容、工具调用与最终回答（SSE 格式）。"""
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
                    yield f"event: error\ndata: {json.dumps(event['message'], ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps(str(exc), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
