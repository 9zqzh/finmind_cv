"""Administrator role resolution and structured audit helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AdminGrant, AuditLog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminRole:
    is_admin: bool
    is_super_admin: bool


async def resolve_admin_role(
    db: AsyncSession, settings: Settings, student_number: str | None
) -> AdminRole:
    initial = settings.initial_admin_student_number.strip()
    if not initial or not student_number:
        return AdminRole(False, False)
    if student_number == initial:
        return AdminRole(True, True)
    grant = await db.scalar(
        select(AdminGrant.id).where(AdminGrant.student_number == student_number)
    )
    return AdminRole(grant is not None, False)


def request_audit_fields(request: Request) -> dict[str, str | None]:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return {
        "ip_address": forwarded or (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent", "")[:512] or None,
    }


def add_audit_event(
    db: AsyncSession,
    request: Request,
    event_type: str,
    success: bool,
    *,
    actor_user_id: uuid.UUID | None = None,
    actor_student_number: str | None = None,
    target_student_number: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        event_type=event_type,
        success=success,
        actor_user_id=actor_user_id,
        actor_student_number=actor_student_number,
        target_student_number=target_student_number,
        target_type=target_type,
        target_id=target_id,
        error_code=error_code,
        details_json=details or {},
        **request_audit_fields(request),
    )
    db.add(event)
    return event


async def write_audit_safely(db: AsyncSession, request: Request, **values: Any) -> None:
    """Write an audit event without replacing the original request outcome on failure."""
    try:
        add_audit_event(db, request, **values)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("审计日志写入失败：%s", values.get("event_type"))
