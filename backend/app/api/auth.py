"""认证路由：验证码、登录、退出、登录状态。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.adapters import jwxt as jwxt_adapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session, get_session_manager
from app.db import get_db
from app.schemas.common import AUTH_REQUIRED, ApiError, ok
from app.schemas.requests import LoginRequest
from app.services.session import JwxtSession, SessionManager

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/captcha")
async def get_captcha(manager: SessionManager = Depends(get_session_manager)):
    """获取验证码：创建会话并返回 base64 图片与 session_token。"""
    session = manager.create()
    try:
        data = await jwxt_adapter.get_captcha(session)
    except ApiError:
        manager.remove(session.token)
        raise
    return ok({"session_token": session.token, **data})


@router.post("/login")
async def login(
    payload: LoginRequest,
    manager: SessionManager = Depends(get_session_manager),
    db: AsyncSession = Depends(get_db),
):
    """使用学号、密码、验证码登录教务系统。"""
    session = await manager.get(payload.session_token, db)
    if session is None:
        raise ApiError(
            AUTH_REQUIRED,
            "会话不存在或已过期，请重新获取验证码",
            status_code=401,
        )
    data = await jwxt_adapter.login(
        session, payload.username, payload.password, payload.captcha
    )
    await manager.persist_login(session, db)
    return ok({"session_token": session.token, **data})


@router.post("/logout")
async def logout(
    request: Request,
    session: JwxtSession | None = Depends(get_optional_session),
    db: AsyncSession = Depends(get_db),
):
    """退出登录并销毁会话。"""
    if session is not None:
        if session.is_logged_in:
            await jwxt_adapter.logout(session)
        await get_session_manager(request).remove(session.token, db)
    return ok({"logged_out": True})


@router.get("/status")
async def status(session: JwxtSession | None = Depends(get_optional_session)):
    """查询当前登录状态。"""
    if session is None:
        return ok({"logged_in": False, "username": None})
    return ok({"logged_in": session.is_logged_in, "username": session.username})
