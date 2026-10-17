"""Collection rules: add/edit/finish/sell bottles, stats, Scent DNA."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import currency
from app.core.constants import ARCHIVE_STATUSES, RADAR_AXES, TASTE_STATUSES
from app.core.errors import Conflict, Invalid, NotFound
from app.models import CollectionItem, Fragrance
from app.repositories.collection import CollectionRepository
from app.schemas.collection import CollectionItemIn, CollectionItemUpdate, SellIn

STATUS_GROUPS: dict[str, tuple[str, ...]] = {
    "archive": ARCHIVE_STATUSES,
    "active": ("own", "wishlist", "tried"),
}


def _default_remaining(status: str) -> int:
    return 0 if status in ("finished", "sold", "gifted") else 100


class CollectionService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID, user_currency: str = "EUR"):
        self.s = session
        self.user_id = user_id
        self.currency = user_currency
        self.repo = CollectionRepository(session)

    def _cur(self, code: str | None) -> str:
        try:
            return currency.normalize(code or self.currency)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc

    async def list_items(self, status: str | None, family: str | None, sort: str) -> list[dict[str, Any]]:
        statuses: tuple[str, ...] | None = None
        if status:
            statuses = STATUS_GROUPS.get(status) or tuple(s.strip() for s in status.split(","))
        return await self.repo.list(self.user_id, statuses, family, sort)

    async def get(self, item_id: int) -> dict[str, Any]:
        out = await self.repo.get_out(self.user_id, item_id)
        if out is None:
            raise NotFound("Collection item")
        return out

    async def add(self, data: CollectionItemIn) -> tuple[dict[str, Any], bool]:
        """Returns (item, created). Replaying the same client_ref returns the original."""
        if data.client_ref:
            existing = await self.repo.by_client_ref(self.user_id, data.client_ref)
            if existing:
                return await self.get(existing.id), False
        if not await self.s.get(Fragrance, data.fragrance_id):
            raise NotFound("Fragrance")
        fields = data.model_dump()
        fields["currency"] = self._cur(data.currency)
        if fields["remaining_pct"] is None:
            fields["remaining_pct"] = _default_remaining(data.status)
        item = CollectionItem(user_id=self.user_id, **fields)
        self.s.add(item)
        try:
            await self.s.commit()
        except IntegrityError as exc:
            await self.s.rollback()
            raise Conflict("This bottle is already in your collection") from exc
        return await self.get(item.id), True

    async def _item(self, item_id: int) -> CollectionItem:
        item = await self.repo.get(self.user_id, item_id)
        if item is None:
            raise NotFound("Collection item")
        return item

    async def update(self, item_id: int, data: CollectionItemUpdate) -> dict[str, Any]:
        item = await self._item(item_id)
        fields = data.model_dump(exclude_unset=True)
        if "currency" in fields:
            fields["currency"] = self._cur(fields["currency"])
        for non_null in ("status", "bottle_type", "remaining_pct", "is_favorite", "currency"):
            if non_null in fields and fields[non_null] is None:
                fields.pop(non_null)
        new_status = fields.get("status")
        if new_status == "finished" and "remaining_pct" not in fields:
            fields["remaining_pct"] = 0
        if new_status in ("sold", "gifted") and item.sold_at is None and "sold_at" not in fields:
            fields["sold_at"] = date.today()
        for k, v in fields.items():
            setattr(item, k, v)
        try:
            await self.s.commit()
        except IntegrityError as exc:
            await self.s.rollback()
            raise Conflict("Another active entry already has this size and bottle type") from exc
        return await self.get(item_id)

    async def finish(self, item_id: int) -> dict[str, Any]:
        item = await self._item(item_id)
        item.status, item.remaining_pct = "finished", 0
        await self.s.commit()
        return await self.get(item_id)

    async def sell(self, item_id: int, data: SellIn) -> dict[str, Any]:
        item = await self._item(item_id)
        item.status = "gifted" if data.gifted else "sold"
        item.sold_price = None if data.gifted else data.sold_price
        item.sold_at = data.sold_at or date.today()
        await self.s.commit()
        return await self.get(item_id)

    async def delete(self, item_id: int) -> None:
        item = await self._item(item_id)
        await self.s.delete(item)
        await self.s.commit()

    # ── Stats ────────────────────────────────────────────────────────
    async def stats(self) -> dict[str, Any]:
        CI = CollectionItem
        counts = (
            await self.s.execute(
                select(
                    func.count().filter(CI.status == "own"),
                    func.count().filter(CI.status == "wishlist"),
                    func.count().filter(CI.status == "tried"),
                    func.count().filter(CI.status.in_(ARCHIVE_STATUSES)),
                    func.coalesce(func.sum(case((CI.status == "own", CI.size_ml), else_=0)), 0),
                    func.avg(CI.rating).filter(CI.status.in_(TASTE_STATUSES)),
                ).where(CI.user_id == self.user_id)
            )
        ).one()
        # "Spent" = what you paid for bottles you own (or owned), in your currency.
        spent_rows = await self.s.execute(
            select(CI.purchase_price, CI.currency).where(
                CI.user_id == self.user_id,
                CI.status.in_(("own", "finished", "sold", "gifted")),
                CI.purchase_price.is_not(None),
            )
        )
        spent = sum(currency.convert(p, c, self.currency) or 0 for p, c in spent_rows.tuples())
        # Estimated value of what's left: latest known price per ml × size × remaining.
        est = await self.s.scalar(
            text("""
                WITH ppm AS (
                    SELECT f.id AS fid, COALESCE(
                        (SELECT pl.price_usd / pl.size_ml FROM price_logs pl WHERE pl.fragrance_id = f.id
                         ORDER BY pl.logged_at DESC LIMIT 1),
                        (SELECT MIN(fp.price_usd / fp.size_ml) FROM fragrance_prices fp WHERE fp.fragrance_id = f.id)
                    ) AS v
                    FROM fragrances f
                )
                SELECT SUM(ppm.v * uc.size_ml * uc.remaining_pct / 100.0)::float
                FROM user_collection uc JOIN ppm ON ppm.fid = uc.fragrance_id
                WHERE uc.user_id = :uid AND uc.status = 'own' AND uc.size_ml IS NOT NULL AND ppm.v IS NOT NULL
            """),
            {"uid": str(self.user_id)},
        )
        return {
            "owned_count": counts[0],
            "wishlist_count": counts[1],
            "tried_count": counts[2],
            "archived_count": counts[3],
            "bottles_ml": int(counts[4] or 0),
            "spent": round(spent, 2),
            "estimated_value_usd": round(est, 2) if est is not None else None,
            "avg_rating": round(float(counts[5]), 1) if counts[5] is not None else None,
            "currency": self.currency,
        }

    async def scent_dna(self) -> dict[str, int]:
        """Share of each radar axis across liked/owned bottles, weighted by rating (unrated = 3)."""
        rows = await self.s.execute(
            text("""
                SELECT fam.axis, SUM(COALESCE(uc.rating, 3.0)) AS score
                FROM user_collection uc
                JOIN fragrance_families ff ON ff.fragrance_id = uc.fragrance_id
                JOIN families fam ON fam.id = ff.family_id
                WHERE uc.user_id = :uid AND uc.status IN ('own', 'tried', 'finished') AND fam.axis IS NOT NULL
                GROUP BY fam.axis
            """),
            {"uid": str(self.user_id)},
        )
        scores = {axis: 0.0 for axis in RADAR_AXES}
        for axis, score in rows.tuples():
            scores[axis] = float(score)
        based_on = (
            await self.s.scalar(
                select(func.count()).where(
                    CollectionItem.user_id == self.user_id, CollectionItem.status.in_(TASTE_STATUSES)
                )
            )
            or 0
        )
        top = max(scores.values()) or 1.0
        out = {k: round(v / top * 100) for k, v in scores.items()}
        out["based_on"] = based_on
        return out
