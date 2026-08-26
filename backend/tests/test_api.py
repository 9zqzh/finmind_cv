"""HTTP 接口基础测试（不依赖真实教务系统与模型）。"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.main import app
from app.models import AuditLog, Base, User
from app.services.session import JwxtSession


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("api-db") / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    os.environ["SESSION_ENCRYPTION_KEYS"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    os.environ["APP_ENV"] = "test"
    os.environ["INITIAL_ADMIN_STUDENT_NUMBER"] = "20260001"
    get_settings.cache_clear()

    async def prepare_database():
        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare_database())
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["service"] == "college-assistant-backend"


def test_auth_status_without_token(client):
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["data"]["logged_in"] is False


def test_chat_and_history_require_login(client):
    chat = client.post("/api/chat", json={"message": "第一轮"})
    history = client.get("/api/conversations")

    assert chat.status_code == 401
    assert history.status_code == 401
    assert chat.json()["code"] == "AUTH_REQUIRED"


def test_schedule_requires_login(client):
    response = client.get("/api/schedule", params={"term": "2025-2026-1"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "AUTH_REQUIRED"


def test_login_with_bad_token(client):
    response = client.post(
        "/api/auth/login",
        json={
            "session_token": "not-exists",
            "username": "20210000001",
            "password": "secret",
            "captcha": "1234",
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def _authenticated_headers(student_number: str) -> dict[str, str]:
    class FakeLoggedInClient:
        is_logged_in = True

        def close(self):
            pass

    token = f"test-token-{student_number}"

    async def seed():
        async with app.state.db_sessions() as db:
            user = await db.scalar(select(User).where(User.student_number == student_number))
            if user is None:
                user = User(student_number=student_number)
                db.add(user)
                await db.commit()
                await db.refresh(user)
        session = JwxtSession(
            token=token,
            client=FakeLoggedInClient(),
            username=student_number,
            user_id=user.id,
        )
        app.state.sessions._sessions[token] = session

    asyncio.run(seed())
    return {"X-Session-Token": token}


def test_admin_uses_user_session_and_super_admin_controls_grants(client):
    assert client.get("/api/admin/admins").status_code == 401

    normal_headers = _authenticated_headers("20260002")
    assert client.get("/api/admin/admins", headers=normal_headers).status_code == 403
    assert client.get("/api/auth/status", headers=normal_headers).status_code == 200
    assert client.get("/api/auth/status", headers=normal_headers).status_code == 200

    super_headers = _authenticated_headers("20260001")
    listed = client.get("/api/admin/admins", headers=super_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["is_super_admin"] is True

    granted = client.post(
        "/api/admin/admins",
        headers=super_headers,
        json={"student_number": "20260002"},
    )
    assert granted.status_code == 200
    users = client.get("/api/admin/users", headers=normal_headers)
    assert users.status_code == 200
    assert all("visit_count" in item for item in users.json()["data"]["items"])
    assert users.json()["data"]["daily_active_users"] >= 1
    normal_user = next(
        item for item in users.json()["data"]["items"]
        if item["student_number"] == "20260002"
    )
    assert normal_user["visit_count"] == 1

    exported = client.get(
        "/api/admin/users/export",
        headers=normal_headers,
        params={"q": "20260002"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.content.startswith(b"\xef\xbb\xbf")
    assert "20260002" in exported.content.decode("utf-8-sig")
    assert client.post(
        "/api/admin/admins",
        headers=normal_headers,
        json={"student_number": "20260003"},
    ).status_code == 403


def test_failed_login_audit_does_not_store_secrets(client):
    client.post(
        "/api/auth/login",
        json={
            "session_token": "missing-audit-token",
            "username": "20269999",
            "password": "must-never-be-stored",
            "captcha": "secret-captcha",
        },
    )

    async def read_event():
        async with app.state.db_sessions() as db:
            return await db.scalar(
                select(AuditLog)
                .where(AuditLog.actor_student_number == "20269999")
                .order_by(AuditLog.created_at.desc())
            )

    event = asyncio.run(read_event())
    assert event is not None
    assert event.event_type == "auth.login"
    assert event.success is False
    serialized = repr(event.details_json)
    assert "must-never-be-stored" not in serialized
    assert "secret-captcha" not in serialized


def test_knowledge_search_with_sample_data(client):
    response = client.get("/api/knowledge/search", params={"q": "课程重修"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["results"]
    assert body["data"]["results"][0]["resource_path"]


def test_knowledge_search_not_found(client):
    response = client.get(
        "/api/knowledge/search", params={"q": "完全无关的查询xyz123"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "KNOWLEDGE_NOT_FOUND"


def test_information_search_with_sample_data(client):
    response = client.get("/api/information/search", params={"q": "数学建模"})
    assert response.status_code == 200
    assert response.json()["data"]["results"]
