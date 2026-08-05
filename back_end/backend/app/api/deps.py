"""FastAPI 依赖注入：会话、知识库等共享对象的获取方式。"""

from __future__ import annotations

from fastapi import Header, Request

from app.adapters.jwxt import require_login
from app.knowledge import KnowledgeService
from app.services.session import JwxtSession, SessionManager

SESSION_HEADER = "X-Session-Token"


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.sessions


def get_knowledge(request: Request) -> KnowledgeService:
    return request.app.state.knowledge


def get_information(request: Request) -> KnowledgeService:
    return request.app.state.information


def get_optional_session(
    request: Request,
    x_session_token: str | None = Header(default=None, alias=SESSION_HEADER),
) -> JwxtSession | None:
    """从请求头取会话；无效或过期返回 None。"""
    return get_session_manager(request).get(x_session_token)


def get_required_session(
    request: Request,
    x_session_token: str | None = Header(default=None, alias=SESSION_HEADER),
) -> JwxtSession:
    """取已登录会话，否则抛 AUTH_REQUIRED。"""
    session = get_session_manager(request).get(x_session_token)
    return require_login(session)
