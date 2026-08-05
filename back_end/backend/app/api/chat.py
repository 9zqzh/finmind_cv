"""对话路由：Agent 统一入口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.orchestrator import build_deps, run_chat
from app.api.deps import (
    get_information,
    get_knowledge,
    get_optional_session,
)
from app.knowledge import KnowledgeService
from app.schemas.common import ok
from app.schemas.requests import ChatRequest
from app.services.session import JwxtSession

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    session: JwxtSession | None = Depends(get_optional_session),
    knowledge: KnowledgeService = Depends(get_knowledge),
    information: KnowledgeService = Depends(get_information),
):
    """发送自然语言问题，返回文本回答与可选结构化结果。"""
    deps = build_deps(session, knowledge, information)
    response = await run_chat(payload.message, deps)
    return ok(response.model_dump())
