"""Authenticated encryption for persisted upstream cookies."""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CookieCipher:
    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("SESSION_ENCRYPTION_KEYS must contain at least one Fernet key")
        try:
            self._fernets = [Fernet(key.encode()) for key in keys]
        except (TypeError, ValueError) as exc:
            raise ValueError("SESSION_ENCRYPTION_KEYS contains an invalid Fernet key") from exc
        self._cipher = MultiFernet(self._fernets)

    def encrypt(self, cookies: dict[str, str]) -> str:
        payload = json.dumps(cookies, ensure_ascii=False, separators=(",", ":")).encode()
        return self._cipher.encrypt(payload).decode()

    def decrypt(self, token: str) -> dict[str, str]:
        try:
            value = json.loads(self._cipher.decrypt(token.encode()).decode())
        except (InvalidToken, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("stored cookies cannot be decrypted") from exc
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in value.items()
        ):
            raise ValueError("stored cookies have an invalid format")
        return value

    def needs_rotation(self, token: str) -> bool:
        try:
            self._fernets[0].decrypt(token.encode())
            return False
        except InvalidToken:
            self._cipher.decrypt(token.encode())
            return True

    def rotate(self, token: str) -> str:
        return self._cipher.rotate(token.encode()).decode()
