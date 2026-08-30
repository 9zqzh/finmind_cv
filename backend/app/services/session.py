"""Persistent login sessions backed by PostgreSQL with an in-process client cache."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from jwxtapi import GradeReport, JwxtClient, RequestError, SessionExpiredError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AuthSession, DemoSession, User
from app.schemas.common import UPSTREAM_ERROR, ApiError
from app.services.crypto import CookieCipher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_today() -> date:
    """Business day used by the China-based application for daily active users."""
    return datetime.now(timezone(timedelta(hours=8))).date()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass
class JwxtSession:
    """One isolated upstream client and its persisted identity."""

    token: str
    client: JwxtClient
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    username: str | None = None
    user_id: uuid.UUID | None = None
    persistent: bool = False
    via_demo: bool = False
    last_grade_report: GradeReport | None = None

    @property
    def is_logged_in(self) -> bool:
        return self.client.is_logged_in

    def touch(self) -> None:
        self.last_active = time.time()


class SessionManager:
    """Keeps captcha clients in memory and authenticated sessions in the database."""

    def __init__(self, settings: Settings, cipher: CookieCipher) -> None:
        self._settings = settings
        self._cipher = cipher
        self._sessions: dict[str, JwxtSession] = {}
        self._lock = threading.Lock()

    def create(self) -> JwxtSession:
        self.purge_expired_captcha_sessions()
        token = secrets.token_urlsafe(32)
        session = JwxtSession(token=token, client=JwxtClient(base_url=self._settings.jwxt_base_url))
        with self._lock:
            self._sessions[token] = session
        return session

    async def get(self, token: str | None, db: AsyncSession) -> JwxtSession | None:
        if not token:
            return None
        with self._lock:
            cached = self._sessions.get(token)
        if cached is not None:
            if not cached.persistent and self._captcha_expired(cached):
                await self.remove(token, db)
                return None
            if cached.persistent and not cached.is_logged_in:
                await self.remove(token, db)
                return None
            cached.touch()
            if cached.persistent and not await self._renew(token, cached, db):
                return None
            return cached

        record = await self._active_record(token, db)
        if record is None:
            return None
        try:
            cookies = self._cipher.decrypt(record.encrypted_cookies)
        except ValueError:
            record.revoked_at = _utcnow()
            await db.commit()
            return None

        client = JwxtClient(base_url=self._settings.jwxt_base_url)
        try:
            await asyncio.to_thread(client.restore_session, cookies)
        except SessionExpiredError:
            record.revoked_at = _utcnow()
            await db.commit()
            client.close()
            return None
        except RequestError as exc:
            client.close()
            raise ApiError(UPSTREAM_ERROR, f"教务系统会话验证失败：{exc}", 502) from exc

        if self._cipher.needs_rotation(record.encrypted_cookies):
            record.encrypted_cookies = self._cipher.rotate(record.encrypted_cookies)
        session = JwxtSession(
            token=token,
            client=client,
            username=record.user.student_number,
            user_id=record.user_id,
            persistent=True,
        )
        with self._lock:
            existing = self._sessions.setdefault(token, session)
        if existing is not session:
            client.close()
            session = existing
        await self._renew(token, session, db)
        return session

    async def persist_login(self, session: JwxtSession, db: AsyncSession) -> None:
        if not session.username or not session.client.is_logged_in:
            raise ValueError("only authenticated sessions can be persisted")
        now = _utcnow()
        today = local_today()
        user = await db.scalar(select(User).where(User.student_number == session.username))
        if user is None:
            user = User(
                student_number=session.username,
                last_login_at=now,
                visit_count=1,
                last_visit_on=today,
            )
            db.add(user)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                user = await db.scalar(select(User).where(User.student_number == session.username))
                if user is None:
                    raise
                await db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(last_login_at=now)
                )
                await self._mark_daily_visit(user.id, today, db)
        else:
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(last_login_at=now)
            )
            await self._mark_daily_visit(user.id, today, db)
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=_token_hash(session.token),
                encrypted_cookies=self._cipher.encrypt(session.client.get_cookies()),
                last_active_at=now,
                expires_at=now + timedelta(days=self._settings.login_session_ttl_days),
            )
        )
        await db.commit()
        session.user_id = user.id
        session.persistent = True

    async def record_daily_visit(self, session: JwxtSession, db: AsyncSession) -> bool:
        """Count at most one authenticated visit per user per Shanghai calendar day."""
        if session.user_id is None or not session.is_logged_in:
            return False
        changed = await self._mark_daily_visit(session.user_id, local_today(), db)
        await db.commit()
        return changed

    async def _mark_daily_visit(
        self, user_id: uuid.UUID, today: date, db: AsyncSession
    ) -> bool:
        result = await db.execute(
            update(User)
            .where(
                User.id == user_id,
                (User.last_visit_on.is_(None)) | (User.last_visit_on < today),
            )
            .values(
                last_visit_on=today,
                visit_count=User.visit_count + 1,
            )
        )
        return bool(result.rowcount)

    async def sync_cookies(self, session: JwxtSession, db: AsyncSession) -> None:
        if not session.persistent:
            return
        record = await db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(session.token)))
        if record is not None and record.revoked_at is None:
            record.encrypted_cookies = self._cipher.encrypt(session.client.get_cookies())
            await db.commit()

    async def remove(self, token: str | None, db: AsyncSession) -> None:
        if not token:
            return
        with self._lock:
            session = self._sessions.pop(token, None)
        if session is not None:
            session.client.close()
        record = await db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        if record is not None and record.revoked_at is None:
            record.revoked_at = _utcnow()
            record.encrypted_cookies = ""
            await db.commit()

    async def get_demo_session(self, db: AsyncSession) -> JwxtSession | None:
        """Resolve the shared judge-demo session, or None when not configured.

        The stored token is encrypted with the same cipher as cookies; the
        resolved session is marked ``via_demo`` so callers can tell requests
        that fall back to the shared session from real user sessions.
        """
        record = await db.scalar(select(DemoSession).limit(1))
        if record is None:
            return None
        try:
            token = self._cipher.decrypt(record.encrypted_token)["demo_token"]
        except (ValueError, KeyError):
            return None
        session = await self.get(token, db)
        if session is not None and session.is_logged_in:
            session.via_demo = True
            return session
        return None

    async def set_demo_session(self, token: str, db: AsyncSession) -> JwxtSession | None:
        """Persist an authenticated persistent session as the shared demo session."""
        session = await self.get(token, db)
        if session is None or not session.is_logged_in or not session.persistent:
            return None
        record = await db.scalar(select(DemoSession).limit(1))
        if record is None:
            record = DemoSession()
            db.add(record)
        record.encrypted_token = self._cipher.encrypt({"demo_token": token})
        record.username = session.username or ""
        await db.commit()
        session.via_demo = True
        return session

    async def clear_demo_session(self, db: AsyncSession) -> bool:
        """Remove the shared demo session; returns True when one existed."""
        record = await db.scalar(select(DemoSession).limit(1))
        if record is None:
            return False
        await db.delete(record)
        await db.commit()
        return True

    def purge_expired_captcha_sessions(self) -> None:
        with self._lock:
            expired = [
                token for token, session in self._sessions.items()
                if not session.persistent and self._captcha_expired(session)
            ]
            sessions = [self._sessions.pop(token) for token in expired]
        for session in sessions:
            session.client.close()

    async def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.client.close()

    async def _active_record(self, token: str, db: AsyncSession) -> AuthSession | None:
        record = await db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == _token_hash(token),
                AuthSession.revoked_at.is_(None),
            )
        )
        if record is not None and _aware(record.expires_at) <= _utcnow():
            record.revoked_at = _utcnow()
            record.encrypted_cookies = ""
            await db.commit()
            return None
        if record is not None:
            await db.refresh(record, attribute_names=["user"])
        return record

    async def _renew(self, token: str, session: JwxtSession, db: AsyncSession) -> bool:
        now = _utcnow()
        record = await db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == _token_hash(token), AuthSession.revoked_at.is_(None)
            )
        )
        if record is None or _aware(record.expires_at) <= now:
            if record is not None:
                record.revoked_at = now
                record.encrypted_cookies = ""
                await db.commit()
            with self._lock:
                self._sessions.pop(token, None)
            session.client.close()
            return False
        record.last_active_at = now
        record.expires_at = now + timedelta(days=self._settings.login_session_ttl_days)
        await db.commit()
        return True

    def _captcha_expired(self, session: JwxtSession) -> bool:
        return time.time() - session.last_active > self._settings.session_ttl_minutes * 60
