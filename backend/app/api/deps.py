"""FastAPI dependencies for database, sessions, and shared services."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.jwxt import require_login
from app.db import get_db
from app.knowledge import KnowledgeService
from app.services.conversation import ConversationManager
from app.services.session import JwxtSession, SessionManager

SESSION_HEADER = "X-Session-Token"


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
    try:
        yield session
    finally:
        if session.is_logged_in:
            await manager.sync_cookies(session, db)
