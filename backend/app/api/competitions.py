"""竞赛信息代理路由（转发外部 API 以绕过浏览器 CORS 限制）。"""

from __future__ import annotations

import httpx

from fastapi import APIRouter

from app.schemas.common import UPSTREAM_ERROR, ApiError, ok

router = APIRouter(prefix="/api", tags=["competitions"])

COMPETITION_API = "https://ai-data-competitions.cn/api/competitions"
NOTICES_API = "https://ai-data-competitions.cn/api/notices/published"
CLUBS_API = "https://ai-data-competitions.cn/api/clubs"


@router.get("/competitions/list")
async def competition_list():
    """获取比赛列表。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(COMPETITION_API)
        if resp.status_code != 200:
            raise ApiError(UPSTREAM_ERROR, "获取竞赛列表失败")
        return ok(resp.json())


@router.get("/competitions/notices")
async def competition_notices(limit: int = 20):
    """获取竞赛平台公告通知。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(NOTICES_API, params={"limit": limit})
        if resp.status_code != 200:
            raise ApiError(UPSTREAM_ERROR, "获取公告通知失败")
        return ok(resp.json())


@router.get("/competitions/clubs")
async def competition_clubs():
    """获取竞赛社团列表。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(CLUBS_API)
        if resp.status_code != 200:
            raise ApiError(UPSTREAM_ERROR, "获取竞赛社团失败")
        return ok(resp.json())