"""操作手册管理路由：查看手册、触发半自动进化、审核草稿。

安全说明：所有管理接口复用已登录用户会话，并要求管理员授权。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.evolution import build_evolution_service
from app.agent.playbook import get_playbook_store
from app.api.deps import AdminContext, get_required_admin
from app.db import get_db
from app.schemas.common import AUTH_REQUIRED, MODEL_ERROR, NOT_FOUND, ApiError, ok
from app.services.admin import write_audit_safely

router = APIRouter(prefix="/api/admin/playbooks", tags=["playbooks"])

@router.get("")
async def list_playbooks(admin: AdminContext = Depends(get_required_admin)):
    """列出全部正式手册与命中统计。"""
    store = get_playbook_store()
    return ok(
        {
            "entries": [
                {
                    "id": e.id,
                    "title": e.title,
                    "keywords": e.keywords,
                    "source": e.source,
                    "instructions": e.instructions,
                }
                for e in store.entries
            ],
            "hit_stats": store.hit_stats(),
        }
    )


@router.post("/evolve")
async def evolve(
    request: Request,
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    """触发一次进化流水线：分析高频问题簇并为达标簇生成待审草稿。"""
    service = build_evolution_service(db)
    try:
        result = await service.run()
    except RuntimeError as exc:
        await write_audit_safely(
            db, request, event_type="playbook.evolve", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_type="playbook_evolution", error_code=MODEL_ERROR,
        )
        raise ApiError(MODEL_ERROR, f"模型未配置或调用失败：{exc}", status_code=502) from exc
    except Exception:
        await write_audit_safely(
            db, request, event_type="playbook.evolve", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_type="playbook_evolution", error_code="INTERNAL_ERROR",
        )
        raise
    await write_audit_safely(
        db, request, event_type="playbook.evolve", success=True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_type="playbook_evolution",
        details={"clusters_found": result.get("clusters_found", 0)},
    )
    return ok(result)


@router.get("/drafts")
async def list_drafts(
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出全部待审草稿。"""
    service = build_evolution_service(db)
    return ok({"drafts": service.list_drafts()})


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    request: Request,
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    """审核通过：草稿转为正式手册（source=auto）并立即生效。"""
    service = build_evolution_service(db)
    try:
        entry = service.approve_draft(draft_id)
    except FileNotFoundError as exc:
        await write_audit_safely(
            db, request, event_type="playbook.approve", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_type="playbook_draft", target_id=draft_id, error_code=NOT_FOUND,
        )
        raise ApiError(NOT_FOUND, str(exc), status_code=404) from exc
    await write_audit_safely(
        db, request, event_type="playbook.approve", success=True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_type="playbook_draft", target_id=draft_id,
        details={"title": entry.title},
    )
    return ok({"id": entry.id, "title": entry.title, "keywords": entry.keywords})


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    request: Request,
    admin: AdminContext = Depends(get_required_admin),
    db: AsyncSession = Depends(get_db),
):
    """审核拒绝：删除草稿。"""
    service = build_evolution_service(db)
    try:
        service.reject_draft(draft_id)
    except FileNotFoundError as exc:
        await write_audit_safely(
            db, request, event_type="playbook.reject", success=False,
            actor_user_id=admin.session.user_id,
            actor_student_number=admin.session.username,
            target_type="playbook_draft", target_id=draft_id, error_code=NOT_FOUND,
        )
        raise ApiError(NOT_FOUND, str(exc), status_code=404) from exc
    await write_audit_safely(
        db, request, event_type="playbook.reject", success=True,
        actor_user_id=admin.session.user_id,
        actor_student_number=admin.session.username,
        target_type="playbook_draft", target_id=draft_id,
    )
    return ok({"id": draft_id, "rejected": True})
