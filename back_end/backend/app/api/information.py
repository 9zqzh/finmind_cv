"""学院资讯API路由。"""

from __future__ import annotations

from fastapi import APIRouter

from app.adapters.gduf_web import get_homepage_info
from app.schemas.common import ok

router = APIRouter(prefix="/api", tags=["information"])


@router.get("/information/home")
async def information_home():
    """获取学院首页资讯（学院新闻、学术活动、学生活动、通知公告）。"""
    data = await get_homepage_info()
    return ok(data)