"""Public conversation history response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.chat import ChatResponse


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    page: int
    page_size: int
    total: int


class StoredTurn(BaseModel):
    id: UUID
    position: int
    user_message: str
    response: ChatResponse
    created_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    turns: list[StoredTurn]
    has_more: bool
