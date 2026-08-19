"""HTTP 接口基础测试（不依赖真实教务系统与模型）。"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.main import app
from app.models import Base


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("api-db") / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    os.environ["SESSION_ENCRYPTION_KEYS"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    os.environ["APP_ENV"] = "test"
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
