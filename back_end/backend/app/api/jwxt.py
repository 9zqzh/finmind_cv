"""教务查询路由：课表、教室课表、成绩、培养方案。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.adapters import jwxt as jwxt_adapter
from app.api.deps import get_required_session
from app.schemas.common import ok
from app.services.session import JwxtSession

router = APIRouter(prefix="/api", tags=["jwxt"])


@router.get("/schedule")
async def schedule(
    term: str = Query(..., description="学期，如 2025-2026-1"),
    week: int | None = Query(default=None, ge=1, le=30, description="教学周次"),
    session: JwxtSession = Depends(get_required_session),
):
    """查询个人课表。"""
    return ok(await jwxt_adapter.get_schedule(session, term, week))


@router.get("/classroom-schedule")
async def classroom_schedule(
    term: str = Query(..., description="学期，如 2025-2026-1"),
    campus: str = Query(default="", description="校区代码"),
    building: str = Query(default="", description="教学楼代码"),
    start_week: int | None = Query(default=None, ge=1, le=30),
    end_week: int | None = Query(default=None, ge=1, le=30),
    session: JwxtSession = Depends(get_required_session),
):
    """查询教室课表。"""
    return ok(
        await jwxt_adapter.get_classroom_schedule(
            session, term, campus=campus, building=building,
            start_week=start_week, end_week=end_week,
        )
    )


@router.get("/grades")
async def grades(
    term: str | None = Query(default=None, description="按学期过滤，可为空"),
    session: JwxtSession = Depends(get_required_session),
):
    """查询成绩列表与学分/绩点统计。"""
    return ok(await jwxt_adapter.get_grades(session, term))


@router.get("/grades/{index}/detail")
async def grade_detail(
    index: int,
    session: JwxtSession = Depends(get_required_session),
):
    """查询单科成绩明细（index 来自成绩列表）。"""
    return ok(await jwxt_adapter.get_grade_detail(session, index))


@router.get("/training-plan")
async def training_plan(
    session: JwxtSession = Depends(get_required_session),
):
    """查询培养方案课程列表。"""
    return ok(await jwxt_adapter.get_training_plan(session))
