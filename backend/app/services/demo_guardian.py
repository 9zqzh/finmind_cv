"""共享会话守护：周期性验证并自动恢复评委演示模式的共享教务会话。

设计要点：
- 纯 asyncio 后台任务，随 FastAPI lifespan 启动/取消，不引入额外调度依赖；
- 每 DEMO_GUARD_INTERVAL_MINUTES 分钟检查一次：
  * 共享会话有效 → 仅刷新状态（评委真实访问时本就会同步 Cookie 续期）；
  * 共享会话缺失/失效且配置了 DEMO_ACCOUNT_* → 自动重登恢复：
    获取验证码 → ddddocr 本地识别 → 登录 → 更新共享会话，无需人工干预；
- OCR 识别失败自动重试（DEMO_RELOGIN_MAX_ATTEMPTS 次）；
- 未安装 ddddocr 或未配置账号凭据时降级为"仅检测 + 状态记录"；
- 运行状态保存在内存（app.state.guardian.status），管理台可查询；
- 单次检查失败仅记录日志，不中断后续调度。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import threading
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters import jwxt as jwxt_adapter
from app.config import Settings
from app.services.session import SessionManager

logger = logging.getLogger(__name__)

_CODE_PATTERN = re.compile(r"[^0-9a-zA-Z]")


class DemoGuardian:
    """后台守护：验证共享会话有效性，失效时用 OCR 自动重登恢复。"""

    def __init__(self, settings: Settings, sessions: SessionManager) -> None:
        self._settings = settings
        self._sessions = sessions
        self._ocr = None
        self._ocr_lock = threading.Lock()
        self.status: dict = {
            "enabled": bool(settings.demo_mode),
            "configured": bool(
                settings.demo_account_student_number.strip()
                and settings.demo_account_password.strip()
            ),
            "ocr_available": False,
            "last_check_at": None,
            "last_check_ok": None,
            "last_recover_at": None,
            "recover_count": 0,
            "last_error": None,
        }

    # ---- OCR ----

    def _load_ocr(self):
        """延迟加载 ddddocr（模型加载较慢且依赖较重，未安装时降级）。"""
        if self._ocr is not None:
            return self._ocr
        with self._ocr_lock:
            if self._ocr is not None:
                return self._ocr
            try:
                import ddddocr  # 仅 demo 依赖，未安装时自动降级

                self._ocr = ddddocr.DdddOcr(show_ad=False)
                self.status["ocr_available"] = True
                logger.info("ddddocr 验证码识别已就绪（共享会话自动恢复可用）")
            except Exception as exc:  # pragma: no cover - 依赖缺失时的降级路径
                self.status["ocr_available"] = False
                logger.warning("ddddocr 不可用，共享会话自动恢复降级：%s", exc)
        return self._ocr

    def _recognize_captcha(self, image_base64: str) -> str | None:
        ocr = self._load_ocr()
        if ocr is None:
            return None
        try:
            image = base64.b64decode(image_base64)
            code = _CODE_PATTERN.sub("", str(ocr.classification(image)))
            return code[:4] if code else None
        except Exception:  # pragma: no cover - OCR 引擎异常
            logger.exception("验证码识别失败")
            return None

    # ---- 自动重登 ----

    async def _auto_relogin(self, db: AsyncSession) -> str | None:
        """用共享账号凭据 + OCR 验证码自动重登，返回新会话令牌；全部失败返回 None。"""
        username = self._settings.demo_account_student_number.strip()
        password = self._settings.demo_account_password
        attempts = max(self._settings.demo_relogin_max_attempts, 1)
        for attempt in range(1, attempts + 1):
            session = self._sessions.create()
            try:
                captcha = await jwxt_adapter.get_captcha(session)
                code = self._recognize_captcha(captcha["image_base64"])
                if not code:
                    logger.warning("自动重登第 %d 次：验证码识别结果为空", attempt)
                    continue
                await jwxt_adapter.login(
                    session, username, password, code
                )
                await self._sessions.persist_login(session, db)
                logger.info("自动重登成功（第 %d 次尝试）：%s", attempt, username)
                return session.token
            except Exception as exc:
                logger.warning("自动重登第 %d 次失败：%s", attempt, exc)
            finally:
                if not session.persistent:
                    await self._sessions.remove(session.token, db)
        return None

    # ---- 检查与恢复 ----

    async def check_and_recover(self, db: AsyncSession) -> None:
        """执行一次检查：有效则记录状态；失效则尝试自动恢复。"""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.status["last_check_at"] = now

        demo = await self._sessions.get_demo_session(db)
        if demo is not None and demo.is_logged_in:
            self.status["last_check_ok"] = True
            self.status["last_error"] = None
            return

        self.status["last_check_ok"] = False
        if not self.status["configured"]:
            self.status["last_error"] = "共享会话失效且未配置 DEMO_ACCOUNT_*，无法自动恢复"
            return
        if not self.status["ocr_available"] and self._load_ocr() is None:
            self.status["last_error"] = "共享会话失效且 ddddocr 未安装，无法自动识别验证码"
            return

        token = await self._auto_relogin(db)
        if token:
            updated = await self._sessions.set_demo_session(token, db)
            if updated is not None:
                self.status["last_recover_at"] = now
                self.status["recover_count"] += 1
                self.status["last_error"] = None
                logger.info("共享会话已自动恢复：%s", updated.username)
                return
        self.status["last_error"] = "自动重登失败（验证码识别或登录错误，已重试）"

    # ---- 后台循环 ----

    async def _loop(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        interval = max(self._settings.demo_guard_interval_minutes, 1) * 60
        while True:
            started = time.monotonic()
            try:
                async with session_factory() as db:
                    await self.check_and_recover(db)
            except Exception:
                logger.exception("共享会话守护检查失败，等待下一周期")
            await asyncio.sleep(max(interval - (time.monotonic() - started), 1.0))


def start_guardian(
    settings: Settings,
    sessions: SessionManager,
    session_factory: async_sessionmaker[AsyncSession],
) -> DemoGuardian:
    """创建守护对象并启动后台任务（DEMO_MODE 关闭时不启动循环）。"""
    guardian = DemoGuardian(settings, sessions)
    if not settings.demo_mode:
        logger.info("评委演示模式未开启（DEMO_MODE=false），共享会话守护未启动")
        return guardian
    guardian._task = asyncio.create_task(  # type: ignore[attr-defined]
        guardian._loop(session_factory), name="demo-guardian"
    )
    return guardian


async def stop_guardian(guardian: DemoGuardian | None) -> None:
    """取消守护后台任务并等待退出。"""
    task = getattr(guardian, "_task", None)
    if task is None or task.cancelled():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
