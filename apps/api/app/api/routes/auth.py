from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, ResourcesDep, SessionDep, limiter
from app.core.config import get_settings
from app.schemas.auth import (
    DeviceIn,
    LoginIn,
    PreferencesOut,
    PreferencesUpdate,
    ProfileUpdate,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)
from app.schemas.common import Message
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])
LOGIN_LIMIT = get_settings().RATE_LIMIT_LOGIN


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limiter.limit(LOGIN_LIMIT)
async def register(request: Request, data: RegisterIn, session: SessionDep) -> TokenPair:
    return await AuthService(session).register(data.email, data.password, data.display_name)


@router.post(
    "/login", response_model=TokenPair, summary="Login (form) — used by the Swagger 'Authorize' button"
)
@limiter.limit(LOGIN_LIMIT)
async def login_form(
    request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> TokenPair:
    return await AuthService(session).login(form.username, form.password)


@router.post("/login/json", response_model=TokenPair)
@limiter.limit(LOGIN_LIMIT)
async def login_json(request: Request, data: LoginIn, session: SessionDep) -> TokenPair:
    return await AuthService(session).login(data.email, data.password)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(request: Request, data: RefreshIn, session: SessionDep) -> TokenPair:
    return await AuthService(session).refresh(data.refresh_token)


@router.post("/logout", response_model=Message)
async def logout(user: CurrentUser, session: SessionDep, data: RefreshIn | None = None) -> Message:
    """Revokes the given refresh token, or every token of the user when none is given."""
    await AuthService(session).logout(data.refresh_token if data else None, user.id)
    return Message(detail="Signed out")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(data: ProfileUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await AuthService(session).update_profile(user, data))


@me_router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(user: CurrentUser, session: SessionDep) -> PreferencesOut:
    return PreferencesOut.model_validate(await AuthService(session).preferences(user.id))


@me_router.patch("/preferences", response_model=PreferencesOut)
async def update_preferences(
    data: PreferencesUpdate, user: CurrentUser, session: SessionDep, res: ResourcesDep
) -> PreferencesOut:
    prefs = await AuthService(session).update_preferences(user.id, data, res.weather)
    return PreferencesOut.model_validate(prefs)


@me_router.post("/devices", response_model=Message, status_code=status.HTTP_201_CREATED)
async def register_device(data: DeviceIn, user: CurrentUser, session: SessionDep) -> Message:
    await AuthService(session).register_device(user.id, data.expo_push_token, data.platform)
    return Message(detail="Device registered")


@me_router.delete("/devices", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(token: str, user: CurrentUser, session: SessionDep) -> Response:
    await AuthService(session).remove_device(user.id, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
