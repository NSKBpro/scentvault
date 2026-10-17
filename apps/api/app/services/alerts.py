"""Wishlist price alerts: CRUD and the check that turns price logs into notifications."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import currency
from app.core.config import get_settings
from app.core.errors import Conflict, Invalid, NotFound
from app.models import Brand, Fragrance, PriceAlert, UserPreferences
from app.schemas.alerts import AlertIn
from app.services.notifications import NotificationService
from app.services.prices import PriceService
from app.services.push import PushClient

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, session: AsyncSession, push: PushClient | None = None):
        self.s = session
        self.prices = PriceService(session)
        self.notifications = NotificationService(session, push)
        self.settings = get_settings()

    async def _out(self, a: PriceAlert) -> dict[str, Any]:
        name, brand = await self.prices.fragrance_label(a.fragrance_id)
        best_usd = await self.prices.latest_price_usd(a.fragrance_id, a.size_ml)
        return {
            "id": a.id,
            "fragrance_id": a.fragrance_id,
            "fragrance_name": name,
            "brand_name": brand,
            "size_ml": a.size_ml,
            "target_price": a.target_price,
            "currency": a.currency,
            "active": a.active,
            "last_notified_at": a.last_notified_at,
            "best_price_usd": best_usd,
            "best_price": currency.from_usd(best_usd, a.currency),
            "created_at": a.created_at,
        }

    async def list_alerts(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self.s.execute(
            select(PriceAlert).where(PriceAlert.user_id == user_id).order_by(PriceAlert.created_at.desc())
        )
        return [await self._out(a) for a in rows.scalars()]

    async def _get(self, user_id: uuid.UUID, alert_id: int) -> PriceAlert:
        a = await self.s.scalar(
            select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id)
        )
        if a is None:
            raise NotFound("Alert")
        return a

    async def create(self, user_id: uuid.UUID, data: AlertIn, default_currency: str) -> dict[str, Any]:
        if not await self.s.get(Fragrance, data.fragrance_id):
            raise NotFound("Fragrance")
        try:
            cur = currency.normalize(data.currency or default_currency)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        a = PriceAlert(
            user_id=user_id,
            fragrance_id=data.fragrance_id,
            size_ml=data.size_ml,
            target_price=data.target_price,
            currency=cur,
        )
        self.s.add(a)
        try:
            await self.s.commit()
        except IntegrityError as exc:
            await self.s.rollback()
            raise Conflict("You already have an alert for this fragrance and size") from exc
        # A price may already be below target.
        await self.check(fragrance_id=a.fragrance_id, alert_ids=[a.id])
        await self.s.refresh(a)
        return await self._out(a)

    async def update(self, user_id: uuid.UUID, alert_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        a = await self._get(user_id, alert_id)
        if fields.get("currency"):
            try:
                fields["currency"] = currency.normalize(fields["currency"])
            except ValueError as exc:
                raise Invalid(str(exc)) from exc
        for k, v in fields.items():
            if v is not None or k == "size_ml":
                setattr(a, k, v)
        if "target_price" in fields or fields.get("active"):
            a.last_notified_at = None  # new target → allow a fresh notification
        try:
            await self.s.commit()
        except IntegrityError as exc:
            await self.s.rollback()
            raise Conflict("You already have an alert for this fragrance and size") from exc
        await self.check(fragrance_id=a.fragrance_id, alert_ids=[a.id])
        await self.s.refresh(a)
        return await self._out(a)

    async def delete(self, user_id: uuid.UUID, alert_id: int) -> None:
        a = await self._get(user_id, alert_id)
        await self.s.delete(a)
        await self.s.commit()

    # ── The check ────────────────────────────────────────────────────
    async def check(self, fragrance_id: int | None = None, alert_ids: list[int] | None = None) -> int:
        """Notify every active alert whose latest price is at/below target (7-day cooldown per alert).

        Called on every new price log (for that fragrance) and daily by the worker (all alerts)."""
        cooldown = datetime.now(UTC) - timedelta(days=self.settings.ALERT_COOLDOWN_DAYS)
        stmt = (
            select(PriceAlert)
            .outerjoin(UserPreferences, UserPreferences.user_id == PriceAlert.user_id)
            .where(
                PriceAlert.active.is_(True),
                (PriceAlert.last_notified_at.is_(None)) | (PriceAlert.last_notified_at < cooldown),
                (UserPreferences.notify_price_alerts.is_(None))
                | (UserPreferences.notify_price_alerts.is_(True)),
            )
        )
        if fragrance_id is not None:
            stmt = stmt.where(PriceAlert.fragrance_id == fragrance_id)
        if alert_ids:
            stmt = stmt.where(PriceAlert.id.in_(alert_ids))
        alerts = list((await self.s.execute(stmt)).scalars())
        sent = 0
        for a in alerts:
            best_usd = await self.prices.latest_price_usd(a.fragrance_id, a.size_ml)
            if best_usd is None:
                continue
            best = currency.from_usd(best_usd, a.currency) or 0
            if best > a.target_price:
                continue
            row = (
                await self.s.execute(
                    select(Fragrance.name, Brand.name).join(Brand).where(Fragrance.id == a.fragrance_id)
                )
            ).one()
            size = f" {a.size_ml} ml" if a.size_ml else ""
            a.last_notified_at = datetime.now(UTC)
            await self.s.commit()
            await self.notifications.notify(
                a.user_id,
                "price_alert",
                f"Price drop: {row[1]} {row[0]}",
                f"Now {best:.2f} {a.currency}{size} — at or below your {a.target_price:.2f} {a.currency} target.",
                {"fragrance_id": a.fragrance_id, "alert_id": a.id, "price": best, "currency": a.currency},
            )
            sent += 1
        return sent
