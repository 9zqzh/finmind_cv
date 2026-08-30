"""共享会话守护（DemoGuardian）测试：有效性检查、OCR 自动重登与降级路径。"""

from __future__ import annotations

import asyncio
import base64
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.adapters import jwxt as jwxt_adapter
from app.config import get_settings
from app.main import app
from app.models import Base
from app.services.demo_guardian import DemoGuardian

SHARED = "20268888"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("guardian-db") / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    os.environ["SESSION_ENCRYPTION_KEYS"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    os.environ["APP_ENV"] = "test"
    os.environ["INITIAL_ADMIN_STUDENT_NUMBER"] = "20260001"
    os.environ["DEMO_MODE"] = "true"
    os.environ["DEMO_ACCOUNT_STUDENT_NUMBER"] = SHARED
    os.environ["DEMO_ACCOUNT_PASSWORD"] = "demo-password"
    os.environ["DEMO_GUARD_INTERVAL_MINUTES"] = "1"
    os.environ["DEMO_RELOGIN_MAX_ATTEMPTS"] = "2"
    get_settings.cache_clear()

    async def prepare_database():
        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare_database())
    with TestClient(app) as test_client:
        yield test_client
    for key in (
        "DEMO_MODE", "DEMO_ACCOUNT_STUDENT_NUMBER", "DEMO_ACCOUNT_PASSWORD",
        "DEMO_GUARD_INTERVAL_MINUTES", "DEMO_RELOGIN_MAX_ATTEMPTS",
    ):
        os.environ.pop(key, None)
    get_settings.cache_clear()


class _FakeClient:
    is_logged_in = True

    def get_cookies(self) -> dict[str, str]:
        return {}

    def close(self):
        pass


class _FakeOcr:
    def __init__(self, code: str | None):
        self.code = code

    def classification(self, image: bytes) -> str:
        return self.code or ""


def _make_guardian(client) -> DemoGuardian:
    return DemoGuardian(get_settings(), app.state.sessions)


def _stub_jwxt(client, *, captcha_ok: bool = True, login_ok: bool = True):
    """把教务适配层的验证码/登录桩化为可预测的流程。"""

    async def fake_get_captcha(session):
        return {
            "image_base64": base64.b64encode(b"fake-image").decode("ascii"),
            "content_type": "image/jpeg",
        }

    async def fake_login(session, username, password, captcha):
        if not captcha_ok:
            raise RuntimeError("captcha unavailable")
        if not login_ok:
            raise RuntimeError("login rejected")
        session.client = _FakeClient()
        session.username = username

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(jwxt_adapter, "get_captcha", fake_get_captcha)
    monkeypatch.setattr(jwxt_adapter, "login", fake_login)
    return monkeypatch


def test_guardian_keeps_valid_session(client):
    from tests.test_demo_mode import _seed_demo_session

    _seed_demo_session("guardian-shared-token-01", SHARED)
    guardian = _make_guardian(client)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(guardian, "_load_ocr", lambda: _FakeOcr("ab12"))

    async def run():
        async with app.state.db_sessions() as db:
            await guardian.check_and_recover(db)

    asyncio.run(run())
    assert guardian.status["last_check_ok"] is True
    assert guardian.status["recover_count"] == 0
    # 共享会话未被改动，仍可正常回退
    status = client.get("/api/auth/status").json()["data"]
    assert status["logged_in"] is True
    assert status["username"] == SHARED
    monkeypatch.undo()


def test_guardian_auto_relogin_after_expiry(client):
    # 先清掉既有共享会话，模拟失效
    async def clear():
        async with app.state.db_sessions() as db:
            await app.state.sessions.clear_demo_session(db)

    asyncio.run(clear())
    monkeypatch = _stub_jwxt(client)
    guardian = _make_guardian(client)
    monkeypatch2 = pytest.MonkeyPatch()
    monkeypatch2.setattr(guardian, "_load_ocr", lambda: _FakeOcr("xy34"))

    async def run():
        async with app.state.db_sessions() as db:
            await guardian.check_and_recover(db)

    asyncio.run(run())
    assert guardian.status["last_check_ok"] is False  # 检查时共享会话已失效
    assert guardian.status["recover_count"] == 1
    assert guardian.status["last_error"] is None
    # 恢复后访客免登录可用
    status = client.get("/api/auth/status").json()["data"]
    assert status["logged_in"] is True
    assert status["username"] == SHARED
    monkeypatch.undo()
    monkeypatch2.undo()


def test_guardian_retries_and_fails_without_ocr(client):
    asyncio.run(client_delete_demo())
    monkeypatch = _stub_jwxt(client)
    guardian = _make_guardian(client)
    # OCR 始终识别为空 → 重试后失败
    monkeypatch2 = pytest.MonkeyPatch()
    monkeypatch2.setattr(guardian, "_load_ocr", lambda: _FakeOcr(None))

    async def run():
        async with app.state.db_sessions() as db:
            await guardian.check_and_recover(db)

    asyncio.run(run())
    assert guardian.status["recover_count"] == 0
    assert guardian.status["last_check_ok"] is False
    assert "自动重登失败" in (guardian.status["last_error"] or "")
    status = client.get("/api/auth/status").json()["data"]
    assert status["logged_in"] is False
    monkeypatch.undo()
    monkeypatch2.undo()


def test_guardian_without_credentials_only_warns(client):
    asyncio.run(client_delete_demo())
    monkeypatch = _stub_jwxt(client)
    guardian = _make_guardian(client)
    guardian.status["configured"] = False  # 模拟未配置 DEMO_ACCOUNT_*

    async def run():
        async with app.state.db_sessions() as db:
            await guardian.check_and_recover(db)

    asyncio.run(run())
    assert guardian.status["last_check_ok"] is False
    assert "未配置 DEMO_ACCOUNT_*" in (guardian.status["last_error"] or "")
    assert guardian.status["recover_count"] == 0
    monkeypatch.undo()


async def client_delete_demo():
    async with app.state.db_sessions() as db:
        await app.state.sessions.clear_demo_session(db)
