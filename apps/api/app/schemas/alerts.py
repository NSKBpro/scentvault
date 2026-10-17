from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.constants import NotificationKind
from app.schemas.common import Schema


class AlertIn(Schema):
    fragrance_id: int
    size_ml: int | None = Field(default=None, gt=0, le=1000)
    target_price: float = Field(gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class AlertUpdate(Schema):
    target_price: float | None = Field(default=None, gt=0)
    size_ml: int | None = Field(default=None, gt=0, le=1000)
    active: bool | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class AlertOut(Schema):
    id: int
    fragrance_id: int
    fragrance_name: str
    brand_name: str
    size_ml: int | None
    target_price: float
    currency: str
    active: bool
    last_notified_at: datetime | None
    best_price_usd: float | None  # latest price across matching sizes
    best_price: float | None  # same, converted to the alert currency
    created_at: datetime


class NotificationOut(Schema):
    id: int
    kind: NotificationKind
    title: str
    body: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationPage(Schema):
    items: list[NotificationOut]
    unread: int
