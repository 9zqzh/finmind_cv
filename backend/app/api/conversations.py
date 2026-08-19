"""Authenticated conversation history endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_conversation_manager, get_required_session
from app.db import get_db
from app.schemas.common import ok
from app.schemas.conversation import (
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    StoredTurn,
)
from app.services.conversation import ConversationManager
from app.services.session import JwxtSession

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _summary(item) -> ConversationSummary:
    return ConversationSummary.model_validate(item, from_attributes=True)


@router.get("")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
    manager: ConversationManager = Depends(get_conversation_manager),
):
    items, total = await manager.list(db, session.user_id, page, page_size)
    payload = ConversationList(
        items=[_summary(item) for item in items], page=page, page_size=page_size, total=total
    )
    return ok(payload.model_dump(mode="json"))


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    before_position: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
    manager: ConversationManager = Depends(get_conversation_manager),
):
    conversation, turns, has_more = await manager.detail(
        db, session.user_id, conversation_id, before_position, limit
    )
    payload = ConversationDetail(
        conversation=_summary(conversation),
        turns=[
            StoredTurn(
                id=turn.id,
                position=turn.position,
                user_message=turn.user_message,
                response=turn.response_json,
                created_at=turn.created_at,
            )
            for turn in turns
        ],
        has_more=has_more,
    )
    return ok(payload.model_dump(mode="json"))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    session: JwxtSession = Depends(get_required_session),
    db: AsyncSession = Depends(get_db),
    manager: ConversationManager = Depends(get_conversation_manager),
):
    await manager.delete(db, session.user_id, conversation_id)
    return ok({"deleted": True})
