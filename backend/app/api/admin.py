"""Authenticated administration APIs for users, grants, conversations, and audits."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminContext, get_required_admin, get_required_super_admin
from app.config import get_settings
from app.db import get_db
from app.models import AdminGrant, AuditLog, AuthSession, Conversation, ConversationTurn, User
from app.schemas.common import CONFLICT, INVALID_PARAM, NOT_FOUND, ApiError, ok
from app.services.admin import add_audit_event, write_audit_safely

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminGrantRequest(BaseModel):
    student_number: str = Field(min_length=4, max_length=64, pattern=r"^[0-9]+$")


@router.get("/admins")
async def list_admins(
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    initial = get_settings().initial_admin_student_number.strip()
    grants = list((await db.scalars(select(AdminGrant).order_by(AdminGrant.created_at))).all())
    items = [{
        "student_number": initial,
        "is_super_admin": True,
        "granted_by_student_number": None,
        "created_at": None,
    }]
    items.extend({
        "student_number": grant.student_number,
        "is_super_admin": False,
        "granted_by_student_number": grant.granted_by_student_number,
        "created_at": grant.created_at,
    } for grant in grants if grant.student_number != initial)
    return ok({"items": items, "can_manage": admin.is_super_admin})


@router.post("/admins")
async def grant_admin(
    payload: AdminGrantRequest,
    request: Request,
    admin: AdminContext = Depends(get_required_super_admin),
    db: AsyncSession = Depends(get_db),
):
    student_number = payload.student_number.strip()
    if student_number == get_settings().initial_admin_student_number.strip():
        await write_audit_safely(
            db, request, event_type="admin.grant", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_student_number=student_number, target_type="admin_grant",
            error_code=CONFLICT,
        )
        raise ApiError(CONFLICT, "该学号已经是初始管理员", 409)
    existing = await db.scalar(
        select(AdminGrant).where(AdminGrant.student_number == student_number)
    )
    if existing is not None:
        await write_audit_safely(
            db, request, event_type="admin.grant", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_student_number=student_number, target_type="admin_grant",
            error_code=CONFLICT,
        )
        raise ApiError(CONFLICT, "该学号已经是管理员", 409)
    grant = AdminGrant(
        student_number=student_number,
        granted_by_user_id=admin.session.user_id,
        granted_by_student_number=admin.session.username or "",
    )
    db.add(grant)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await write_audit_safely(
            db, request, event_type="admin.grant", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_student_number=student_number, target_type="admin_grant",
            error_code=CONFLICT,
        )
        raise ApiError(CONFLICT, "该学号已经是管理员", 409) from exc
    add_audit_event(
        db,
        request,
        "admin.grant",
        True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_student_number=student_number,
        target_type="admin_grant",
        target_id=str(grant.id),
    )
    await db.commit()
    return ok({"student_number": student_number, "is_super_admin": False})


@router.delete("/admins/{student_number}")
async def revoke_admin(
    student_number: str,
    request: Request,
    admin: AdminContext = Depends(get_required_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if student_number == get_settings().initial_admin_student_number.strip():
        await write_audit_safely(
            db, request, event_type="admin.revoke", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_student_number=student_number, target_type="admin_grant",
            error_code=INVALID_PARAM,
        )
        raise ApiError(INVALID_PARAM, "初始管理员不能被取消", 400)
    grant = await db.scalar(
        select(AdminGrant).where(AdminGrant.student_number == student_number)
    )
    if grant is None:
        await write_audit_safely(
            db, request, event_type="admin.revoke", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_student_number=student_number, target_type="admin_grant",
            error_code=NOT_FOUND,
        )
        raise ApiError(NOT_FOUND, "管理员授权不存在", 404)
    await db.delete(grant)
    add_audit_event(
        db,
        request,
        "admin.revoke",
        True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_student_number=student_number,
        target_type="admin_grant",
        target_id=str(grant.id),
    )
    await db.commit()
    return ok({"student_number": student_number, "revoked": True})


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=64),
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    del admin
    now = datetime.now(timezone.utc)
    filters = [User.student_number.ilike(f"%{q.strip()}%")] if q.strip() else []
    last_active = (
        select(func.max(AuthSession.last_active_at))
        .where(AuthSession.user_id == User.id)
        .correlate(User).scalar_subquery()
    )
    active_sessions = (
        select(func.count(AuthSession.id))
        .where(
            AuthSession.user_id == User.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        ).correlate(User).scalar_subquery()
    )
    conversation_count = (
        select(func.count(Conversation.id))
        .where(Conversation.user_id == User.id)
        .correlate(User).scalar_subquery()
    )
    rows = (await db.execute(
        select(User, last_active, active_sessions, conversation_count)
        .where(*filters)
        .order_by(User.last_login_at.desc(), User.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    total = await db.scalar(select(func.count()).select_from(User).where(*filters))
    return ok({
        "items": [{
            "id": user.id,
            "student_number": user.student_number,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "last_active_at": active,
            "has_active_session": bool(active_count),
            "conversation_count": int(conversations or 0),
        } for user, active, active_count, conversations in rows],
        "page": page, "page_size": page_size, "total": int(total or 0),
    })


@router.get("/users/{user_id}/conversations")
async def list_user_conversations(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    del admin
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(NOT_FOUND, "用户不存在", 404)
    filters = [Conversation.user_id == user_id]
    items = list((await db.scalars(
        select(Conversation).where(*filters)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all())
    total = await db.scalar(select(func.count()).select_from(Conversation).where(*filters))
    return ok({
        "user": {"id": user.id, "student_number": user.student_number},
        "items": [{
            "id": item.id, "title": item.title,
            "created_at": item.created_at, "updated_at": item.updated_at,
        } for item in items],
        "page": page, "page_size": page_size, "total": int(total or 0),
    })


@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: UUID,
    request: Request,
    before_position: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(Conversation, User).join(User, User.id == Conversation.user_id)
        .where(Conversation.id == conversation_id)
    )).first()
    if row is None:
        raise ApiError(NOT_FOUND, "会话不存在", 404)
    conversation, owner = row
    conditions = [ConversationTurn.conversation_id == conversation_id]
    if before_position is not None:
        conditions.append(ConversationTurn.position < before_position)
    turns = list((await db.scalars(
        select(ConversationTurn).where(*conditions)
        .order_by(ConversationTurn.position.desc()).limit(limit + 1)
    )).all())
    has_more = len(turns) > limit
    turns = list(reversed(turns[:limit]))
    await write_audit_safely(
        db, request, event_type="admin.conversation.view", success=True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_student_number=owner.student_number,
        target_type="conversation", target_id=str(conversation_id),
    )
    return ok({
        "user": {"id": owner.id, "student_number": owner.student_number},
        "conversation": {
            "id": conversation.id, "title": conversation.title,
            "created_at": conversation.created_at, "updated_at": conversation.updated_at,
        },
        "turns": [{
            "id": turn.id, "position": turn.position,
            "user_message": turn.user_message, "response": turn.response_json,
            "created_at": turn.created_at,
        } for turn in turns],
        "has_more": has_more,
    })


@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = Query(None, max_length=64),
    success: bool | None = Query(None),
    student_number: str | None = Query(None, max_length=64),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    del admin
    conditions = []
    if event_type:
        conditions.append(AuditLog.event_type == event_type)
    if success is not None:
        conditions.append(AuditLog.success == success)
    if student_number:
        pattern = f"%{student_number.strip()}%"
        conditions.append(or_(
            AuditLog.actor_student_number.ilike(pattern),
            AuditLog.target_student_number.ilike(pattern),
        ))
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)
    items = list((await db.scalars(
        select(AuditLog).where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all())
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    return ok({
        "items": [{
            "id": item.id, "event_type": item.event_type, "success": item.success,
            "actor_student_number": item.actor_student_number,
            "target_student_number": item.target_student_number,
            "target_type": item.target_type, "target_id": item.target_id,
            "error_code": item.error_code, "ip_address": item.ip_address,
            "user_agent": item.user_agent, "details": item.details_json,
            "created_at": item.created_at,
        } for item in items],
        "page": page, "page_size": page_size, "total": int(total or 0),
    })
