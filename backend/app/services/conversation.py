"""Persistent conversation loading, ownership checks, and turn storage."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ConversationTurn as ConversationTurnModel
from app.schemas.common import NOT_FOUND, ApiError


@dataclass
class ConversationTurn:
    model_messages_json: str
    created_at: float = 0


@dataclass
class ConversationMemory:
    conversation_id: str
    chat_history: list[ConversationTurn] = field(default_factory=list)
    _db: AsyncSession | None = field(default=None, repr=False)
    _conversation_uuid: uuid.UUID | None = field(default=None, repr=False)
    _user_id: uuid.UUID | None = field(default=None, repr=False)
    _new_title: str | None = field(default=None, repr=False)

    async def save(
        self,
        user_message: str,
        model_messages_json: str,
        response_json: dict[str, Any],
    ) -> None:
        self.chat_history.append(ConversationTurn(model_messages_json=model_messages_json))
        if len(self.chat_history) > 4:
            del self.chat_history[:-4]
        if self._db is None or self._conversation_uuid is None:
            return
        conversation = await self._db.scalar(
            select(Conversation).where(Conversation.id == self._conversation_uuid).with_for_update()
        )
        if conversation is None:
            if self._user_id is None or self._new_title is None:
                raise ApiError(NOT_FOUND, "会话不存在", 404)
            conversation = Conversation(
                id=self._conversation_uuid,
                user_id=self._user_id,
                title=self._new_title,
            )
            self._db.add(conversation)
            await self._db.flush()
        last_position = await self._db.scalar(
            select(func.max(ConversationTurnModel.position)).where(
                ConversationTurnModel.conversation_id == conversation.id
            )
        )
        self._db.add(
            ConversationTurnModel(
                conversation_id=conversation.id,
                position=(last_position or 0) + 1,
                user_message=user_message,
                response_json=response_json,
                model_messages_json=json.loads(model_messages_json),
            )
        )
        conversation.updated_at = datetime.now(timezone.utc)
        await self._db.commit()


class ConversationManager:
    async def get_or_create(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        first_message: str,
    ) -> ConversationMemory:
        if conversation_id is None:
            title = re.sub(r"\s+", " ", first_message).strip()[:30] or "新对话"
            new_id = uuid.uuid4()
            return ConversationMemory(
                conversation_id=str(new_id),
                _db=db,
                _conversation_uuid=new_id,
                _user_id=user_id,
                _new_title=title,
            )
        else:
            conversation = await db.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id, Conversation.user_id == user_id
                )
            )
            if conversation is None:
                raise ApiError(NOT_FOUND, "会话不存在", 404)

        rows = list(
            (
                await db.scalars(
                    select(ConversationTurnModel)
                    .where(ConversationTurnModel.conversation_id == conversation.id)
                    .order_by(ConversationTurnModel.position.desc())
                    .limit(4)
                )
            ).all()
        )
        rows.reverse()
        await db.commit()
        return ConversationMemory(
            conversation_id=str(conversation.id),
            chat_history=[
                ConversationTurn(json.dumps(row.model_messages_json, ensure_ascii=False)) for row in rows
            ],
            _db=db,
            _conversation_uuid=conversation.id,
            _user_id=user_id,
        )

    async def list(self, db: AsyncSession, user_id: uuid.UUID, page: int, page_size: int):
        items = list(
            (
                await db.scalars(
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        total = await db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        return items, int(total or 0)

    async def detail(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        before_position: int | None,
        limit: int,
    ):
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        if conversation is None:
            raise ApiError(NOT_FOUND, "会话不存在", 404)
        conditions = [ConversationTurnModel.conversation_id == conversation.id]
        if before_position is not None:
            conditions.append(ConversationTurnModel.position < before_position)
        rows = list(
            (
                await db.scalars(
                    select(ConversationTurnModel)
                    .where(*conditions)
                    .order_by(ConversationTurnModel.position.desc())
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        rows.reverse()
        return conversation, rows, has_more

    async def delete(
        self, db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        result = await db.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        if result.rowcount == 0:
            await db.rollback()
            raise ApiError(NOT_FOUND, "会话不存在", 404)
        await db.commit()
