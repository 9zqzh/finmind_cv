"""教务系统适配层：隔离 jwxtapi 与 HTTP 路由 / Agent 工具。

职责：
1. 把 jwxtapi 的异常映射为统一错误码（ApiError）。
2. 把 jwxtapi 的 dataclass 模型转换为可 JSON 序列化的 dict。
3. 同步客户端调用统一包装为 async（asyncio.to_thread），避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Callable, TypeVar

from jwxtapi import (
    AuthenticationError,
    CaptchaError,
    Grade,
    JwxtError,
    ParseError,
    RequestError,
    SessionExpiredError,
    ValidationError,
)

from app.schemas.common import (
    AUTH_CAPTCHA_INVALID,
    AUTH_FAILED,
    AUTH_REQUIRED,
    INVALID_PARAM,
    PARSE_ERROR,
    SESSION_EXPIRED,
    UPSTREAM_ERROR,
    ApiError,
)
from app.services.session import JwxtSession

T = TypeVar("T")


def translate_jwxt_error(exc: JwxtError) -> ApiError:
    """把教务包异常转换为带统一错误码的 ApiError。"""
    if isinstance(exc, CaptchaError):
        return ApiError(AUTH_CAPTCHA_INVALID, str(exc), status_code=400)
    if isinstance(exc, AuthenticationError):
        return ApiError(AUTH_FAILED, str(exc), status_code=401)
    if isinstance(exc, SessionExpiredError):
        return ApiError(SESSION_EXPIRED, str(exc), status_code=401)
    if isinstance(exc, ParseError):
        return ApiError(PARSE_ERROR, str(exc), status_code=502)
    if isinstance(exc, ValidationError):
        return ApiError(INVALID_PARAM, str(exc), status_code=400)
    if isinstance(exc, RequestError):
        return ApiError(UPSTREAM_ERROR, f"教务系统请求失败：{exc}", status_code=502)
    return ApiError(UPSTREAM_ERROR, f"教务系统异常：{exc}", status_code=502)


async def run_jwxt(func: Callable[[], T]) -> T:
    """在线程中执行同步教务调用，并统一转换异常。"""
    try:
        return await asyncio.to_thread(func)
    except JwxtError as exc:
        raise translate_jwxt_error(exc) from exc


def require_login(session: JwxtSession | None) -> JwxtSession:
    """登录守卫：个人数据查询必须先登录。"""
    if session is None or not session.is_logged_in:
        raise ApiError(
            AUTH_REQUIRED, "尚未登录教务系统，请先登录后再查询个人数据", status_code=401
        )
    return session


# ---- 业务方法（供路由与 Agent 工具复用） ----


async def get_captcha(session: JwxtSession) -> dict[str, Any]:
    captcha = await run_jwxt(session.client.get_captcha)
    return {
        "image_base64": base64.b64encode(captcha.content).decode("ascii"),
        "content_type": captcha.content_type,
    }


async def login(
    session: JwxtSession, username: str, password: str, captcha: str
) -> dict[str, Any]:
    result = await run_jwxt(
        lambda: session.client.login(username, password, captcha)
    )
    session.username = result.username
    return {"username": result.username, "success": result.success}


async def logout(session: JwxtSession) -> None:
    await run_jwxt(session.client.logout)


async def get_schedule(
    session: JwxtSession, term: str, week: int | None = None
) -> dict[str, Any]:
    require_login(session)
    schedule = await run_jwxt(lambda: session.client.get_schedule(term, week))
    return schedule.to_dict()


async def get_classroom_schedule(
    session: JwxtSession,
    term: str,
    campus: str = "",
    building: str = "",
    start_week: int | None = None,
    end_week: int | None = None,
    start_period: int | None = None,
    end_period: int | None = None,
) -> dict[str, Any]:
    require_login(session)
    schedule = await run_jwxt(
        lambda: session.client.get_classroom_schedule(
            term=term,
            campus=campus,
            building=building,
            start_week=start_week,
            end_week=end_week,
            start_period=start_period,
            end_period=end_period,
        )
    )
    return schedule.to_dict()


async def get_grades(session: JwxtSession, term: str | None = None) -> dict[str, Any]:
    """查询成绩列表；term 传入时按学期过滤条目。"""
    require_login(session)
    report = await run_jwxt(lambda: session.client.get_grades())
    session.last_grade_report = report
    data = report.to_dict()
    if term:
        data["items"] = [g for g in data["items"] if g["term"] == term]
    return data


async def get_grade_detail(session: JwxtSession, index: int) -> dict[str, Any]:
    """按成绩列表中的 index 查询单科明细。"""
    require_login(session)
    report = session.last_grade_report
    if report is None:
        raise ApiError(
            INVALID_PARAM,
            "请先查询成绩列表，再查询单科成绩明细",
            status_code=400,
        )
    grade: Grade | None = next(
        (g for g in report.items if g.index == index), None
    )
    if grade is None:
        raise ApiError(INVALID_PARAM, f"成绩列表中没有 index={index} 的记录", status_code=404)
    if not grade.has_detail:
        raise ApiError(INVALID_PARAM, f"《{grade.course_name}》没有可用的成绩明细", status_code=400)
    detail = await run_jwxt(lambda: session.client.get_grade_detail(grade))
    return detail.to_dict()


async def get_training_plan(session: JwxtSession) -> dict[str, Any]:
    require_login(session)
    plan = await run_jwxt(lambda: session.client.get_training_plan())
    return plan.to_dict()
