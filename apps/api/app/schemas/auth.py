from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.constants import GenderPreference, Role
from app.schemas.common import Schema


class RegisterIn(Schema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class LoginIn(Schema):
    # Not EmailStr on purpose: logging in must never be stricter than the account that exists.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(Schema):
    refresh_token: str


class UserOut(Schema):
    id: uuid.UUID
    email: str
    display_name: str | None
    role: Role
    created_at: datetime


class TokenPair(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(Schema):
    display_name: str | None = Field(default=None, max_length=100)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class PreferencesOut(Schema):
    currency: str
    city: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    gender_preference: GenderPreference
    notify_price_alerts: bool
    notify_running_low: bool
    notify_neglected: bool


class PreferencesUpdate(Schema):
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    city: str | None = Field(default=None, max_length=120)
    gender_preference: GenderPreference | None = None
    timezone: str | None = Field(default=None, max_length=64)
    notify_price_alerts: bool | None = None
    notify_running_low: bool | None = None
    notify_neglected: bool | None = None


class DeviceIn(Schema):
    expo_push_token: str = Field(min_length=10, max_length=255)
    platform: str | None = Field(default=None, max_length=20)
