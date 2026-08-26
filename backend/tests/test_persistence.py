from __future__ import annotations

import uuid
import hashlib

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sqlalchemy import select

from app.config import Settings
from app.models import AdminGrant, AuthSession, Base, User
from app.services.admin import resolve_admin_role
from app.services.conversation import ConversationManager
from app.services.crypto import CookieCipher
from app.services.session import JwxtSession, SessionManager


def test_cookie_cipher_round_trip_and_rotation():
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_cipher = CookieCipher([old_key])
    encrypted = old_cipher.encrypt({"JSESSIONID": "secret"})

    rotating_cipher = CookieCipher([new_key, old_key])
    assert rotating_cipher.needs_rotation(encrypted) is True
    rotated = rotating_cipher.rotate(encrypted)
    assert rotating_cipher.decrypt(rotated) == {"JSESSIONID": "secret"}
    assert rotating_cipher.needs_rotation(rotated) is False


def test_cookie_cipher_rejects_missing_keys_and_corrupt_data():
    with pytest.raises(ValueError):
        CookieCipher([])
    cipher = CookieCipher([Fernet.generate_key().decode()])
    with pytest.raises(ValueError):
        cipher.decrypt("not-a-fernet-token")


@pytest.mark.asyncio
async def test_conversations_are_owned_paginated_and_cascade_deleted(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'db.sqlite3').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    manager = ConversationManager()

    async with factory() as db:
        first_user = User(student_number="20260001")
        second_user = User(student_number="20260002")
        db.add_all([first_user, second_user])
        await db.commit()

        memory = await manager.get_or_create(db, first_user.id, None, "  第一段   对话  ")
        await memory.save("问题", "[]", {"answer": "回答", "intent": "chat"})
        items, total = await manager.list(db, first_user.id, 1, 20)
        assert total == 1
        assert items[0].title == "第一段 对话"

        conversation_id = uuid.UUID(memory.conversation_id)
        conversation, turns, has_more = await manager.detail(
            db, first_user.id, conversation_id, None, 50
        )
        assert conversation.id == conversation_id
        assert turns[0].position == 1
        assert turns[0].response_json["answer"] == "回答"
        assert has_more is False

        with pytest.raises(Exception) as error:
            await manager.detail(db, second_user.id, conversation_id, None, 50)
        assert getattr(error.value, "status_code", None) == 404

        await manager.delete(db, first_user.id, conversation_id)
        _, total = await manager.list(db, first_user.id, 1, 20)
        assert total == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_login_session_is_hashed_encrypted_and_restorable(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.is_logged_in = False
            self.cookies = {"JSESSIONID": "upstream-secret"}
            self.closed = False

        def get_cookies(self):
            return dict(self.cookies)

        def restore_session(self, cookies):
            self.cookies = dict(cookies)
            self.is_logged_in = True
            return True

        def close(self):
            self.closed = True

    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'sessions.sqlite3').as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cipher = CookieCipher([Fernet.generate_key().decode()])
    settings = Settings(_env_file=None, LOGIN_SESSION_TTL_DAYS=7)
    manager = SessionManager(settings, cipher)
    client = FakeClient()
    client.is_logged_in = True
    login = JwxtSession(token="raw-browser-token", client=client, username="20260003")

    async with factory() as db:
        await manager.persist_login(login, db)
        record = await db.scalar(select(AuthSession))
        user = await db.scalar(select(User).where(User.student_number == "20260003"))
        assert user is not None
        assert user.visit_count == 1
        assert record.token_hash == hashlib.sha256(b"raw-browser-token").hexdigest()
        assert "upstream-secret" not in record.encrypted_cookies
        assert cipher.decrypt(record.encrypted_cookies)["JSESSIONID"] == "upstream-secret"

        second_login = JwxtSession(
            token="second-browser-token",
            client=client,
            username="20260003",
        )
        await manager.persist_login(second_login, db)
        await db.refresh(user)
        assert user.visit_count == 2
        assert user.last_login_at is not None

    monkeypatch.setattr("app.services.session.JwxtClient", FakeClient)
    restored_manager = SessionManager(settings, cipher)
    async with factory() as db:
        restored = await restored_manager.get("raw-browser-token", db)
        assert restored is not None
        assert restored.username == "20260003"
        assert restored.client.is_logged_in is True
        assert restored.client.cookies["JSESSIONID"] == "upstream-secret"

    await restored_manager.close()
    await manager.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_roles_require_initial_config_and_support_pre_authorization(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'admin.sqlite3').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        db.add(AdminGrant(
            student_number="20260002",
            granted_by_student_number="20260001",
        ))
        await db.commit()

        disabled = await resolve_admin_role(
            db, Settings(_env_file=None, INITIAL_ADMIN_STUDENT_NUMBER=""), "20260002"
        )
        assert disabled.is_admin is False

        settings = Settings(_env_file=None, INITIAL_ADMIN_STUDENT_NUMBER="20260001")
        initial = await resolve_admin_role(db, settings, "20260001")
        ordinary = await resolve_admin_role(db, settings, "20260002")
        assert initial.is_super_admin is True
        assert ordinary.is_admin is True
        assert ordinary.is_super_admin is False

    await engine.dispose()
