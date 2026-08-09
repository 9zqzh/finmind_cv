"""会话管理：每个登录用户独享一个 JwxtClient 实例，禁止全局共享 Cookie。"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from jwxtapi import GradeReport, JwxtClient

from app.config import Settings


@dataclass
class JwxtSession:
    """一次用户会话：绑定一个教务客户端实例。"""

    token: str
    client: JwxtClient
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    username: str | None = None
    # 缓存最近一次成绩列表，供"单科成绩明细"按 index 查询
    last_grade_report: GradeReport | None = None
    @property
    def is_logged_in(self) -> bool:
        return self.client.is_logged_in

    def touch(self) -> None:
        self.last_active = time.time()


class SessionManager:
    """内存会话管理器（原型阶段；后续可迁移 SQLite/Redis）。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions: dict[str, JwxtSession] = {}
        self._lock = threading.Lock()

    def create(self) -> JwxtSession:
        """创建会话：先拿验证码再登录，客户端此时尚未登录。"""
        self.purge_expired()
        token = secrets.token_urlsafe(24)
        client = JwxtClient(base_url=self._settings.jwxt_base_url)
        session = JwxtSession(token=token, client=client)
        with self._lock:
            self._sessions[token] = session
        return session

    def get(self, token: str | None) -> JwxtSession | None:
        """按 token 取会话；过期则清理并返回 None。"""
        if not token:
            return None
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if self._is_expired(session):
                self._sessions.pop(token, None)
                session.client.close()
                return None
        session.touch()
        return session

    def remove(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            session = self._sessions.pop(token, None)
        if session is not None:
            session.client.close()

    def purge_expired(self) -> None:
        with self._lock:
            expired = [t for t, s in self._sessions.items() if self._is_expired(s)]
            for token in expired:
                session = self._sessions.pop(token, None)
                if session is not None:
                    session.client.close()

    def _is_expired(self, session: JwxtSession) -> bool:
        ttl = self._settings.session_ttl_minutes * 60
        return time.time() - session.last_active > ttl
