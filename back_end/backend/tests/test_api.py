"""HTTP 接口基础测试（不依赖真实教务系统与模型）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


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
    response = client.get("/api/knowledge/search", params={"q": "缓考"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["results"]


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
