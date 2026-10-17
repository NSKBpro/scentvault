"""In-app notifications + Expo push fan-out, and the nudges that create them."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFound
from app.models import Brand, CollectionItem, Fragrance, Notification, UserDevice, UserPreferences, WearLog
from app.services.push import PushClient

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession, push: PushClient | None = None):
        self.s = session
        self.push = push
        self.settings = get_settings()

    async def notify(
        self,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str,
        payload: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> int | None:
        """Create a notification (skipped if dedupe_key was already used) and push it."""
        stmt = pg_insert(Notification).values(
            user_id=user_id, kind=kind, title=title, body=body, payload=payload or {}, dedupe_key=dedupe_key
        )
        if dedupe_key:
            stmt = stmt.on_conflict_do_nothing(constraint="uq_notifications_dedupe")
        new_id = await self.s.scalar(stmt.returning(Notification.id))
        await self.s.commit()
        if new_id is None:
            return None
        if self.push is not None:
            tokens = list(
                (
                    await self.s.execute(
                        select(UserDevice.expo_push_token).where(UserDevice.user_id == user_id)
                    )
                ).scalars()
            )
            dead = await self.push.send(
                tokens, title, body, {"notification_id": new_id, "kind": kind, **(payload or {})}
            )
            if dead:
                await self.s.execute(delete(UserDevice).where(UserDevice.expo_push_token.in_(dead)))
                await self.s.commit()
        return new_id

    # ── Inbox ────────────────────────────────────────────────────────
    async def inbox(self, user_id: uuid.UUID, unread_only: bool, limit: int) -> dict[str, Any]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        items = (
            (
                await self.s.execute(
                    stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        unread = (
            await self.s.scalar(
                select(func.count()).where(Notification.user_id == user_id, Notification.read_at.is_(None))
            )
            or 0
        )
        return {"items": items, "unread": unread}

    async def mark_read(self, user_id: uuid.UUID, notification_id: int) -> Notification:
        n = await self.s.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        if n is None:
            raise NotFound("Notification")
        if n.read_at is None:
            n.read_at = datetime.now(UTC)
            await self.s.commit()
        return n

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        res = await self.s.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        await self.s.commit()
        return res.rowcount or 0  # type: ignore[attr-defined]

    # ── Nudges ───────────────────────────────────────────────────────
    async def _prefs(self, user_id: uuid.UUID) -> UserPreferences | None:
        return await self.s.get(UserPreferences, user_id)

    async def maybe_running_low(self, item: CollectionItem) -> None:
        if item.status != "own" or item.remaining_pct > self.settings.RUNNING_LOW_PCT:
            return
        prefs = await self._prefs(item.user_id)
        if prefs is not None and not prefs.notify_running_low:
            return
        name = await self._name(item.fragrance_id)
        await self.notify(
            item.user_id,
            "running_low",
            f"Running low: {name}",
            f"About {item.remaining_pct}% left. Time to restock or enjoy the last sprays.",
            {"collection_item_id": item.id, "fragrance_id": item.fragrance_id},
            dedupe_key=f"running_low:{item.id}",
        )

    async def neglected_nudges(self, today: date | None = None) -> int:
        """Monthly nudge per owned bottle not worn in NEGLECTED_DAYS (and owned at least that long)."""
        today = today or datetime.now(UTC).date()
        cutoff = today - timedelta(days=self.settings.NEGLECTED_DAYS)
        last = (
            select(WearLog.collection_item_id, func.max(WearLog.worn_on).label("last"))
            .group_by(WearLog.collection_item_id)
            .subquery()
        )
        rows = await self.s.execute(
            select(CollectionItem, last.c.last, Fragrance.name, Brand.name)
            .join(Fragrance, Fragrance.id == CollectionItem.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
            .outerjoin(last, last.c.collection_item_id == CollectionItem.id)
            .outerjoin(UserPreferences, UserPreferences.user_id == CollectionItem.user_id)
            .where(
                CollectionItem.status == "own",
                func.coalesce(UserPreferences.notify_neglected, True).is_(True),
                func.date(CollectionItem.created_at) <= cutoff,
                (last.c.last.is_(None)) | (last.c.last <= cutoff),
            )
        )
        sent = 0
        for item, last_worn, fname, bname in rows.tuples():
            days = (today - last_worn).days if last_worn else None
            body = (
                f"Not worn in {days} days — give it a spin this week?"
                if days
                else "You haven't logged a wear yet — give it a spin this week?"
            )
            created = await self.notify(
                item.user_id,
                "neglected",
                f"{bname} {fname} misses you",
                body,
                {"collection_item_id": item.id, "fragrance_id": item.fragrance_id},
                dedupe_key=f"neglected:{item.id}:{today:%Y-%m}",
            )
            sent += 1 if created else 0
        return sent

    async def _name(self, fragrance_id: int) -> str:
        row = (
            await self.s.execute(
                select(Brand.name, Fragrance.name)
                .join(Brand, Brand.id == Fragrance.brand_id)
                .where(Fragrance.id == fragrance_id)
            )
        ).one()
        return f"{row[0]} {row[1]}"
