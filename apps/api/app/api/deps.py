"""FastAPI dependencies — the wiring between HTTP and services."""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserPreferences
from app.resources import Resources

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{get_settings().API_PREFIX}/auth/login", auto_error=False)

limiter = Limiter(
    key_func=get_remote_address, enabled=get_settings().RATE_LIMIT_ENABLED, headers_enabled=False
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_resources(request: Request) -> Resources:
    return request.app.state.resources  # type: ignore[no-any-return]


ResourcesDep = Annotated[Resources, Depends(get_resources)]


async def get_current_user(session: SessionDep, token: Annotated[str | None, Depends(oauth2)]) -> User:
    if not token:
        raise Unauthorized("Not authenticated")
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Could not validate credentials") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise Unauthorized("Could not validate credentials")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise Forbidden("Admin privileges required")
    return user


AdminUser = Annotated[User, Depends(get_admin)]


async def get_prefs(user: CurrentUser, session: SessionDep) -> UserPreferences:
    from app.services.auth import AuthService

    return await AuthService(session).preferences(user.id)


Prefs = Annotated[UserPreferences, Depends(get_prefs)]
