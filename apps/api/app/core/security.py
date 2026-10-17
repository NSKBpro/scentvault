"""Password hashing and JWT access tokens.

Refresh tokens are opaque random strings stored hashed (see AuthService).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


async def hash_password_async(password: str) -> str:
    """bcrypt is deliberately slow; keep it off the event loop."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(password: str, hashed: str) -> bool:
    return await anyio.to_thread.run_sync(verify_password, password, hashed)


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    s = get_settings()
    minutes = expires_minutes or s.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM), minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
