"""操作手册管理路由：查看手册、触发半自动进化、审核草稿。

安全说明：管理接口通过 X-Admin-Token 请求头校验 ADMIN_TOKEN；
原型阶段 ADMIN_TOKEN 留空时不校验，生产部署必须配置。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.evolution import build_evolution_service
from app.agent.playbook import get_playbook_store
from app.config import get_settings
from app.db import get_db
from app.schemas.common import AUTH_REQUIRED, MODEL_ERROR, NOT_FOUND, ApiError, ok

router = APIRouter(prefix="/api/admin/playbooks", tags=["playbooks"])

ADMIN_TOKEN_HEADER = "X-Admin-Token"


def require_admin(
    x_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> None:
    """管理员令牌校验；ADMIN_TOKEN 未配置时放行（仅限原型阶段）。"""
    settings = get_settings()
    expected = settings.admin_token.strip()
    if expected and x_admin_token != expected:
        raise ApiError(AUTH_REQUIRED, "管理接口令牌无效", status_code=401)


@router.get("", dependencies=[Depends(require_admin)])
async def list_playbooks():
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


@router.post("/evolve", dependencies=[Depends(require_admin)])
async def evolve(db: AsyncSession = Depends(get_db)):
    """触发一次进化流水线：分析高频问题簇并为达标簇生成待审草稿。"""
    service = build_evolution_service(db)
    try:
        result = await service.run()
    except RuntimeError as exc:
        raise ApiError(MODEL_ERROR, f"模型未配置或调用失败：{exc}", status_code=502) from exc
    return ok(result)


@router.get("/drafts", dependencies=[Depends(require_admin)])
async def list_drafts(db: AsyncSession = Depends(get_db)):
    """列出全部待审草稿。"""
    service = build_evolution_service(db)
    return ok({"drafts": service.list_drafts()})


@router.post("/drafts/{draft_id}/approve", dependencies=[Depends(require_admin)])
async def approve_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    """审核通过：草稿转为正式手册（source=auto）并立即生效。"""
    service = build_evolution_service(db)
    try:
        entry = service.approve_draft(draft_id)
    except FileNotFoundError as exc:
        raise ApiError(NOT_FOUND, str(exc), status_code=404) from exc
    return ok({"id": entry.id, "title": entry.title, "keywords": entry.keywords})


@router.post("/drafts/{draft_id}/reject", dependencies=[Depends(require_admin)])
async def reject_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    """审核拒绝：删除草稿。"""
    service = build_evolution_service(db)
    try:
        service.reject_draft(draft_id)
    except FileNotFoundError as exc:
        raise ApiError(NOT_FOUND, str(exc), status_code=404) from exc
    return ok({"id": draft_id, "rejected": True})
