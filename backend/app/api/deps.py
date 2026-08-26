"""FastAPI dependencies for database, sessions, and shared services."""

from __future__ import annotations

from collections.abc import AsyncIterator

from dataclasses import dataclass

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.jwxt import require_login
from app.config import get_settings
from app.db import get_db
from app.knowledge import KnowledgeService
from app.services.conversation import ConversationManager
from app.services.session import JwxtSession, SessionManager
from app.services.admin import resolve_admin_role
from app.schemas.common import FORBIDDEN, ApiError

SESSION_HEADER = "X-Session-Token"


@dataclass(frozen=True)
class AdminContext:
    session: JwxtSession
    is_super_admin: bool


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.sessions


def get_conversation_manager(request: Request) -> ConversationManager:
    return request.app.state.conversations


def get_knowledge(request: Request) -> KnowledgeService:
    return request.app.state.knowledge


def get_information(request: Request) -> KnowledgeService:
    return request.app.state.information


async def get_optional_session(
    request: Request,
    x_session_token: str | None = Header(default=None, alias=SESSION_HEADER),
    db: AsyncSession = Depends(get_db),
) -> AsyncIterator[JwxtSession | None]:
    manager = get_session_manager(request)
    session = await manager.get(x_session_token, db)
    if session is not None and session.is_logged_in:
        await manager.record_daily_visit(session, db)
    try:
        yield session
    finally:
        if session is not None and session.is_logged_in:
            await manager.sync_cookies(session, db)


async def get_required_session(
    request: Request,
    x_session_token: str | None = Header(default=None, alias=SESSION_HEADER),
    db: AsyncSession = Depends(get_db),
) -> AsyncIterator[JwxtSession]:
    manager = get_session_manager(request)
    session = require_login(await manager.get(x_session_token, db))
    await manager.record_daily_visit(session, db)
    try:
        yield session
    finally:
        if session.is_logged_in:
            await manager.sync_cookies(session, db)


async def get_required_admin(
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
) -> AdminContext:
    role = await resolve_admin_role(db, get_settings(), session.username)
    if not role.is_admin:
        raise ApiError(FORBIDDEN, "当前用户没有管理后台权限", status_code=403)
    return AdminContext(session=session, is_super_admin=role.is_super_admin)


async def get_required_super_admin(
    admin: AdminContext = Depends(get_required_admin),
) -> AdminContext:
    if not admin.is_super_admin:
        raise ApiError(FORBIDDEN, "仅初始管理员可以分配管理员", status_code=403)
    return admin
