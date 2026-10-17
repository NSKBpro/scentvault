"""Authentication, profile, preferences, devices, admin user management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import currency
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, Invalid, NotFound, Unauthorized
from app.core.security import (
    create_access_token,
    hash_password_async,
    hash_token,
    new_refresh_token,
    verify_password_async,
)
from app.models import CollectionItem, RefreshToken, User, UserDevice, UserPreferences
from app.schemas.auth import PreferencesUpdate, ProfileUpdate, TokenPair, UserOut
from app.services.weather import WeatherClient


class AuthService:
    def __init__(self, session: AsyncSession):
        self.s = session
        self.settings = get_settings()

    async def _by_email(self, email: str) -> User | None:
        return await self.s.scalar(select(User).where(func.lower(User.email) == email.lower()))

    async def _issue(self, user: User) -> TokenPair:
        access, expires_in = create_access_token(str(user.id), user.role)
        refresh = new_refresh_token()
        self.s.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh),
                expires_at=datetime.now(UTC) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        await self.s.commit()
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
            user=UserOut.model_validate(user),
        )

    async def register(self, email: str, password: str, display_name: str | None) -> TokenPair:
        if await self._by_email(email):
            raise Conflict("Email already registered")
        user = User(
            email=email.lower(),
            password_hash=await hash_password_async(password),
            display_name=display_name,
            role="user",
        )
        self.s.add(user)
        await self.s.flush()
        self.s.add(UserPreferences(user_id=user.id, currency=self.settings.DEFAULT_CURRENCY))
        return await self._issue(user)

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self._by_email(email)
        if user is None or not await verify_password_async(password, user.password_hash):
            raise Unauthorized("Incorrect email or password")
        return await self._issue(user)

    async def refresh(self, token: str) -> TokenPair:
        """Rotate: the presented token is revoked and a new pair issued.

        Re-use of an already-revoked token revokes every token of that user
        (it was probably stolen)."""
        row = await self.s.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
        now = datetime.now(UTC)
        if row is None:
            raise Unauthorized("Invalid refresh token")
        if row.revoked_at is not None:
            await self.s.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await self.s.commit()
            raise Unauthorized("Refresh token already used; please sign in again")
        if row.expires_at < now:
            raise Unauthorized("Refresh token expired")
        row.revoked_at = now
        user = await self.s.get(User, row.user_id)
        if user is None:
            raise Unauthorized("User no longer exists")
        return await self._issue(user)

    async def logout(self, token: str | None, user_id: uuid.UUID) -> None:
        stmt = update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        if token:
            stmt = stmt.where(RefreshToken.token_hash == hash_token(token))
        await self.s.execute(stmt.values(revoked_at=datetime.now(UTC)))
        # Housekeeping: drop long-dead tokens.
        await self.s.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC) - timedelta(days=7))
        )
        await self.s.commit()

    async def update_profile(self, user: User, data: ProfileUpdate) -> User:
        if data.display_name is not None:
            user.display_name = data.display_name.strip() or None
        if data.new_password:
            if not data.current_password or not await verify_password_async(
                data.current_password, user.password_hash
            ):
                raise Forbidden("Current password is incorrect")
            user.password_hash = await hash_password_async(data.new_password)
            await self.s.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
        await self.s.commit()
        return user

    # ── Preferences ─────────────────────────────────────────────────
    async def preferences(self, user_id: uuid.UUID) -> UserPreferences:
        prefs = await self.s.get(UserPreferences, user_id)
        if prefs is None:
            prefs = UserPreferences(user_id=user_id, currency=self.settings.DEFAULT_CURRENCY)
            self.s.add(prefs)
            await self.s.commit()
            await self.s.refresh(prefs)
        return prefs

    async def update_preferences(
        self, user_id: uuid.UUID, data: PreferencesUpdate, weather: WeatherClient | None
    ) -> UserPreferences:
        prefs = await self.preferences(user_id)
        fields = data.model_dump(exclude_unset=True)
        if "currency" in fields and fields["currency"]:
            try:
                fields["currency"] = currency.normalize(fields["currency"])
            except ValueError as exc:
                raise Invalid(str(exc)) from exc
        if "city" in fields:
            city = (fields.pop("city") or "").strip()
            if not city:
                prefs.city = prefs.latitude = prefs.longitude = None
            elif city.lower() != (prefs.city or "").lower() or prefs.latitude is None:
                geo = await weather.geocode(city) if weather else None
                if geo is None:
                    raise Invalid(f"Couldn't find a city called '{city}'")
                prefs.city, prefs.latitude, prefs.longitude = geo.name, geo.latitude, geo.longitude
                if geo.timezone and "timezone" not in fields:
                    prefs.timezone = geo.timezone
        for k, v in fields.items():
            if v is not None:
                setattr(prefs, k, v)
        await self.s.commit()
        await self.s.refresh(prefs)
        return prefs

    # ── Devices ─────────────────────────────────────────────────────
    async def register_device(self, user_id: uuid.UUID, token: str, platform: str | None) -> None:
        dev = await self.s.scalar(select(UserDevice).where(UserDevice.expo_push_token == token))
        if dev is None:
            self.s.add(UserDevice(user_id=user_id, expo_push_token=token, platform=platform))
        else:  # token moved to another account on the same phone
            dev.user_id, dev.platform, dev.last_seen_at = user_id, platform, datetime.now(UTC)
        await self.s.commit()

    async def remove_device(self, user_id: uuid.UUID, token: str) -> None:
        await self.s.execute(
            delete(UserDevice).where(UserDevice.user_id == user_id, UserDevice.expo_push_token == token)
        )
        await self.s.commit()


class AdminUserService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list_users(
        self, page: int, size: int, search: str | None, role: str | None
    ) -> tuple[list[dict[str, Any]], int]:
        conds = []
        if search:
            term = f"%{search.lower()}%"
            conds.append(or_(func.lower(User.email).like(term), func.lower(User.display_name).like(term)))
        if role:
            conds.append(User.role == role)
        total = await self.s.scalar(select(func.count()).select_from(User).where(*conds)) or 0
        cnt = select(func.count()).where(CollectionItem.user_id == User.id).scalar_subquery()
        rows = await self.s.execute(
            select(User, cnt.label("c"))
            .where(*conds)
            .order_by(User.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return [self._out(u, c) for u, c in rows.all()], total

    @staticmethod
    def _out(u: User, count: int = 0) -> dict[str, Any]:
        return {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "created_at": u.created_at,
            "collection_count": count or 0,
        }

    async def create(self, email: str, password: str, display_name: str | None, role: str) -> dict[str, Any]:
        if await self.s.scalar(select(User.id).where(func.lower(User.email) == email.lower())):
            raise Conflict("Email already registered")
        u = User(
            email=email.lower(),
            password_hash=await hash_password_async(password),
            display_name=display_name,
            role=role,
        )
        self.s.add(u)
        await self.s.flush()
        self.s.add(UserPreferences(user_id=u.id, currency=get_settings().DEFAULT_CURRENCY))
        await self.s.commit()
        return self._out(u)

    async def update(self, user_id: uuid.UUID, data: dict[str, Any], acting: User) -> dict[str, Any]:
        u = await self.s.get(User, user_id)
        if u is None:
            raise NotFound("User")
        if data.get("email") and data["email"].lower() != u.email:
            if await self.s.scalar(select(User.id).where(func.lower(User.email) == data["email"].lower())):
                raise Conflict("Email already in use")
            u.email = data["email"].lower()
        if data.get("display_name") is not None:
            u.display_name = data["display_name"] or None
        if data.get("role"):
            if u.id == acting.id and data["role"] != "admin":
                raise Invalid("You cannot remove your own admin role")
            u.role = data["role"]
        if data.get("password"):
            u.password_hash = await hash_password_async(data["password"])
        await self.s.commit()
        cnt = await self.s.scalar(select(func.count()).where(CollectionItem.user_id == u.id)) or 0
        return self._out(u, cnt)

    async def delete(self, user_id: uuid.UUID, acting: User) -> None:
        if user_id == acting.id:
            raise Invalid("You cannot delete your own account here")
        u = await self.s.get(User, user_id)
        if u is None:
            raise NotFound("User")
        await self.s.delete(u)
        await self.s.commit()
