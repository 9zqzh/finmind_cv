"""评委演示模式（DEMO_MODE）测试：共享会话回退、管理接口与登出保护。"""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.main import app
from app.models import AuthSession, Base, DemoSession, User
from app.services.session import JwxtSession

DEMO_STUDENT = "20268888"
SUPER_STUDENT = "20260001"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("demo-db") / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    os.environ["SESSION_ENCRYPTION_KEYS"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    os.environ["APP_ENV"] = "test"
    os.environ["INITIAL_ADMIN_STUDENT_NUMBER"] = SUPER_STUDENT
    os.environ["DEMO_MODE"] = "true"
    get_settings.cache_clear()

    async def prepare_database():
        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare_database())
    with TestClient(app) as test_client:
        yield test_client
    os.environ.pop("DEMO_MODE", None)
    get_settings.cache_clear()


class _FakeClient:
    is_logged_in = True

    def get_cookies(self) -> dict[str, str]:
        return {}

    def close(self):
        pass


def _seed_demo_session(token: str, student_number: str) -> None:
    """写入用户、持久会话记录、共享会话记录并注入内存会话缓存。"""

    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    async def seed():
        async with app.state.db_sessions() as db:
            user = await db.scalar(select(User).where(User.student_number == student_number))
            if user is None:
                user = User(student_number=student_number)
                db.add(user)
                await db.flush()
            existing = await db.scalar(
                select(AuthSession).where(AuthSession.token_hash == _hash(token))
            )
            if existing is None:
                db.add(
                    AuthSession(
                        user_id=user.id,
                        token_hash=_hash(token),
                        encrypted_cookies="not-used-in-tests",
                        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                    )
                )
            demo = await db.scalar(select(DemoSession).limit(1))
            cipher = app.state.sessions._cipher
            if demo is None:
                demo = DemoSession()
                db.add(demo)
            demo.encrypted_token = cipher.encrypt({"demo_token": token})
            demo.username = student_number
            await db.commit()

    asyncio.run(seed())
    app.state.sessions._sessions[token] = JwxtSession(
        token=token,
        client=_FakeClient(),
        username=student_number,
        persistent=True,
    )


def _seed_logged_in(token: str, student_number: str) -> dict[str, str]:
    """仅注入一个已登录的持久会话（用于管理员操作）。"""
    _seed_demo_session("demo-shared-token-0001", DEMO_STUDENT)  # 确保共享会话存在
    user = None

    async def seed():
        nonlocal user
        async with app.state.db_sessions() as db:
            user = await db.scalar(select(User).where(User.student_number == student_number))
            if user is None:
                user = User(student_number=student_number)
                db.add(user)
                await db.commit()
                await db.refresh(user)

    asyncio.run(seed())
    app.state.sessions._sessions[token] = JwxtSession(
        token=token,
        client=_FakeClient(),
        username=student_number,
        user_id=user.id,
    )
    return {"X-Session-Token": token}


def test_demo_status_without_shared_session_keeps_logged_out(client):
    # 先清掉共享会话，验证未配置时演示模式仍返回未登录
    client.delete("/api/admin/demo-session", headers=_seed_logged_in("super-token-0001", SUPER_STUDENT))
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["logged_in"] is False
    assert body["demo_mode"] is True


def test_demo_mode_falls_back_to_shared_session(client):
    _seed_demo_session("demo-shared-token-0001", DEMO_STUDENT)

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["logged_in"] is True
    assert body["username"] == DEMO_STUDENT
    assert body["demo_mode"] is True

    # 个人数据接口不再要求登录（用无副作用的对话历史接口验证）
    conversations = client.get("/api/conversations")
    assert conversations.status_code == 200


def test_demo_logout_does_not_destroy_shared_session(client):
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["data"]["logged_out"] is True

    status = client.get("/api/auth/status")
    assert status.json()["data"]["logged_in"] is True
    assert status.json()["data"]["username"] == DEMO_STUDENT


def test_demo_session_admin_api_requires_super_admin(client):
    # 未登录：401（演示回退的共享会话不是管理员身份）
    assert client.get("/api/admin/demo-session").status_code == 401

    # 先由超级管理员把普通管理员授权出来
    super_headers = _seed_logged_in("super-token-0001", SUPER_STUDENT)
    assert client.post(
        "/api/admin/admins",
        headers=super_headers,
        json={"student_number": "20260002"},
    ).status_code == 200

    # 普通管理员：GET 可以（仅查看），POST 需要超级管理员 → 403
    normal_headers = _seed_logged_in("normal-token-0001", "20260002")
    assert client.get("/api/admin/demo-session", headers=normal_headers).status_code == 200
    assert client.post(
        "/api/admin/demo-session",
        headers=normal_headers,
        json={"token": "demo-shared-token-0001"},
    ).status_code == 403

    # 超级管理员：可以查看、设置、清除
    listed = client.get("/api/admin/demo-session", headers=super_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["configured"] is True
    assert listed.json()["data"]["username"] == DEMO_STUDENT

    set_ok = client.post(
        "/api/admin/demo-session",
        headers=super_headers,
        json={"token": "demo-shared-token-0001"},
    )
    assert set_ok.status_code == 200
    assert set_ok.json()["data"]["username"] == DEMO_STUDENT

    cleared = client.delete("/api/admin/demo-session", headers=super_headers)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["cleared"] is True

    after = client.get("/api/admin/demo-session", headers=super_headers)
    assert after.json()["data"]["configured"] is False

    # 恢复共享会话，避免影响同模块后续用例
    client.post(
        "/api/admin/demo-session",
        headers=super_headers,
        json={"token": "demo-shared-token-0001"},
    )


def test_demo_session_admin_rejects_invalid_token(client):
    super_headers = _seed_logged_in("super-token-0001", SUPER_STUDENT)
    response = client.post(
        "/api/admin/demo-session",
        headers=super_headers,
        json={"token": "invalid-token-not-in-cache"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PARAM"
