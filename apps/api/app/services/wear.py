"""Wear log (scent of the day) and wear statistics."""

from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import currency
from app.core.clock import user_today
from app.core.config import get_settings
from app.core.errors import Invalid, NotFound
from app.models import Brand, CollectionItem, Fragrance, WearLog
from app.schemas.wear import WearIn

# Below this many wears, cost per wear is an estimate from the bottle size.
MIN_REAL_WEARS = 5
ESTIMATE_SPRAYS_PER_WEAR = 4


def _wear_out(
    w: WearLog, fragrance_name: str, brand_name: str, remaining: int | None = None
) -> dict[str, Any]:
    d = {c.key: getattr(w, c.key) for c in WearLog.__table__.columns if c.key != "user_id"}
    d.update(fragrance_name=fragrance_name, brand_name=brand_name, remaining_pct=remaining)
    return d


class WearService:
    def __init__(
        self, session: AsyncSession, user_id: uuid.UUID, tz: str | None = None, user_currency: str = "EUR"
    ):
        self.s = session
        self.user_id = user_id
        self.tz = tz
        self.currency = user_currency
        self.settings = get_settings()

    async def _resolve(self, data: WearIn) -> tuple[CollectionItem | None, int]:
        if data.collection_item_id is not None:
            item = await self.s.scalar(
                select(CollectionItem).where(
                    CollectionItem.id == data.collection_item_id, CollectionItem.user_id == self.user_id
                )
            )
            if item is None:
                raise NotFound("Collection item")
            if data.fragrance_id is not None and data.fragrance_id != item.fragrance_id:
                raise Invalid("fragrance_id does not match the collection item")
            return item, item.fragrance_id
        assert data.fragrance_id is not None
        if not await self.s.get(Fragrance, data.fragrance_id):
            raise NotFound("Fragrance")
        # Link to the owned bottle of that fragrance with the most left, if any.
        item = await self.s.scalar(
            select(CollectionItem)
            .where(
                CollectionItem.user_id == self.user_id,
                CollectionItem.fragrance_id == data.fragrance_id,
                CollectionItem.status == "own",
            )
            .order_by(CollectionItem.remaining_pct.desc())
            .limit(1)
        )
        return item, data.fragrance_id

    async def log(self, data: WearIn) -> tuple[dict[str, Any], CollectionItem | None, bool]:
        """Returns (wear, bottle, created)."""
        if data.client_ref:
            existing = await self.s.scalar(
                select(WearLog).where(WearLog.user_id == self.user_id, WearLog.client_ref == data.client_ref)
            )
            if existing:
                return await self._out(existing), None, False
        item, fragrance_id = await self._resolve(data)
        today = user_today(self.tz)
        worn_on = data.worn_on or today
        if worn_on > today + timedelta(days=1):
            raise Invalid("worn_on cannot be in the future")
        w = WearLog(
            user_id=self.user_id,
            collection_item_id=item.id if item else None,
            fragrance_id=fragrance_id,
            worn_on=worn_on,
            sprays=data.sprays,
            occasion=data.occasion,
            temp_c=data.temp_c,
            note=data.note,
            compliment=data.compliment,
            client_ref=data.client_ref,
        )
        self.s.add(w)
        remaining = None
        if item is not None:
            if data.adjust_remaining and data.sprays and item.size_ml:
                used_pct = data.sprays * self.settings.ML_PER_SPRAY / item.size_ml * 100
                item.remaining_pct = max(0, round(item.remaining_pct - used_pct))
            remaining = item.remaining_pct
        await self.s.commit()
        return await self._out(w, remaining), item, True

    async def _out(self, w: WearLog, remaining: int | None = None) -> dict[str, Any]:
        row = (
            await self.s.execute(
                select(Fragrance.name, Brand.name)
                .join(Brand, Brand.id == Fragrance.brand_id)
                .where(Fragrance.id == w.fragrance_id)
            )
        ).one()
        return _wear_out(w, row[0], row[1], remaining)

    async def delete(self, wear_id: int) -> None:
        w = await self.s.scalar(select(WearLog).where(WearLog.id == wear_id, WearLog.user_id == self.user_id))
        if w is None:
            raise NotFound("Wear")
        await self.s.delete(w)
        await self.s.commit()

    async def list_wears(
        self,
        date_from: date | None,
        date_to: date | None,
        collection_item_id: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(WearLog, Fragrance.name, Brand.name)
            .join(Fragrance, Fragrance.id == WearLog.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
            .where(WearLog.user_id == self.user_id)
        )
        if date_from:
            stmt = stmt.where(WearLog.worn_on >= date_from)
        if date_to:
            stmt = stmt.where(WearLog.worn_on <= date_to)
        if collection_item_id:
            stmt = stmt.where(WearLog.collection_item_id == collection_item_id)
        rows = await self.s.execute(
            stmt.order_by(WearLog.worn_on.desc(), WearLog.created_at.desc()).limit(limit)
        )
        return [_wear_out(w, fn, bn) for w, fn, bn in rows.tuples()]

    async def worn_today(self) -> list[int]:
        rows = await self.s.execute(
            select(WearLog.collection_item_id).where(
                WearLog.user_id == self.user_id,
                WearLog.worn_on == user_today(self.tz),
                WearLog.collection_item_id.is_not(None),
            )
        )
        return sorted({r for r in rows.scalars() if r is not None})

    # ── Stats ────────────────────────────────────────────────────────
    def cost_per_wear(self, item: CollectionItem, wear_count: int) -> tuple[float | None, bool]:
        if item.purchase_price is None:
            return None, False
        price = currency.convert(item.purchase_price, item.currency, self.currency) or 0.0
        if wear_count >= MIN_REAL_WEARS:
            return round(price / wear_count, 2), False
        if not item.size_ml:
            return (round(price / wear_count, 2), False) if wear_count else (None, False)
        est_wears = item.size_ml / (self.settings.ML_PER_SPRAY * ESTIMATE_SPRAYS_PER_WEAR)
        return round(price / est_wears, 2), True

    async def stats(self) -> dict[str, Any]:
        today = user_today(self.tz)
        per_item = await self.s.execute(
            select(
                CollectionItem, Fragrance.name, Brand.name, func.count(WearLog.id), func.max(WearLog.worn_on)
            )
            .join(Fragrance, Fragrance.id == CollectionItem.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
            .outerjoin(WearLog, WearLog.collection_item_id == CollectionItem.id)
            .where(CollectionItem.user_id == self.user_id, CollectionItem.status.in_(("own", "finished")))
            .group_by(CollectionItem.id, Fragrance.name, Brand.name)
        )
        bottles: list[dict[str, Any]] = []
        owned_items: list[tuple[CollectionItem, int]] = []
        for item, fname, bname, count, last in per_item.tuples():
            cpw, est = self.cost_per_wear(item, count)
            bottles.append(
                {
                    "collection_item_id": item.id,
                    "fragrance_id": item.fragrance_id,
                    "fragrance_name": fname,
                    "brand_name": bname,
                    "wear_count": count,
                    "last_worn_on": last,
                    "days_since_worn": (today - last).days if last else None,
                    "cost_per_wear": cpw,
                    "cost_per_wear_is_estimate": est,
                    "currency": self.currency,
                    "_status": item.status,
                    "_created": item.created_at.date(),
                }
            )
            if item.status == "own":
                owned_items.append((item, count))

        totals = (
            await self.s.execute(
                select(
                    func.count(),
                    func.count(WearLog.worn_on.distinct()),
                    func.count(WearLog.fragrance_id.distinct()),
                    func.count().filter(WearLog.compliment.is_(True)),
                ).where(WearLog.user_id == self.user_id)
            )
        ).one()

        month_start = date(today.year, today.month, 1)
        first_month = (month_start.replace(day=1) - timedelta(days=330)).replace(day=1)
        month = func.to_char(WearLog.worn_on, literal_column("'YYYY-MM'"))
        per_month_rows = await self.s.execute(
            select(month, func.count())
            .where(WearLog.user_id == self.user_id, WearLog.worn_on >= first_month)
            .group_by(month)
        )
        counts_by_month: dict[str, int] = dict(per_month_rows.tuples().all())
        months: list[dict[str, Any]] = []
        cursor = first_month
        while cursor <= month_start:
            key = cursor.strftime("%Y-%m")
            months.append({"month": key, "wears": counts_by_month.get(key, 0)})
            cursor = (cursor + timedelta(days=32)).replace(day=1)

        # Rotation spread: normalised entropy of the last 90 days of wears over owned bottles.
        recent = await self.s.execute(
            select(WearLog.collection_item_id, func.count())
            .where(
                WearLog.user_id == self.user_id,
                WearLog.worn_on >= today - timedelta(days=90),
                WearLog.collection_item_id.in_([i.id for i, _ in owned_items] or [-1]),
            )
            .group_by(WearLog.collection_item_id)
        )
        rc = [c for _, c in recent.tuples()]
        spread = 0.0
        if len(owned_items) > 1 and sum(rc) > 0:
            total = sum(rc)
            entropy = -sum((c / total) * math.log(c / total) for c in rc if c)
            spread = round(entropy / math.log(len(owned_items)), 3)

        owned = [b for b in bottles if b["_status"] == "own"]
        neglect = self.settings.NEGLECTED_DAYS
        shelf = [
            b
            for b in owned
            if (b["days_since_worn"] is not None and b["days_since_worn"] >= neglect)
            or (b["last_worn_on"] is None and (today - b["_created"]).days >= neglect)
        ]
        shelf.sort(key=lambda b: -(b["days_since_worn"] if b["days_since_worn"] is not None else 10_000))

        def clean(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]

        most = sorted(
            [b for b in owned if b["wear_count"]], key=lambda b: (-b["wear_count"], b["fragrance_name"])
        )
        least = sorted(
            owned, key=lambda b: (b["wear_count"], b["last_worn_on"] or date.min, b["fragrance_name"])
        )
        return {
            "total_wears": totals[0],
            "days_logged": totals[1],
            "distinct_fragrances": totals[2],
            "rotation_spread": spread,
            "most_worn": clean(most[:5]),
            "least_worn": clean(least[:5]),
            "shelf_time": clean(shelf),
            "per_bottle": clean(sorted(bottles, key=lambda b: b["fragrance_name"])),
            "per_month": months,
            "compliments": totals[3],
        }
