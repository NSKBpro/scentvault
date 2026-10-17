"""Queries for the user's shelf and wear log."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, CollectionItem, Family, Fragrance, WearLog, fragrance_families


def _families_subq() -> Any:
    return (
        select(func.array_agg(Family.name))
        .select_from(fragrance_families.join(Family, Family.id == fragrance_families.c.family_id))
        .where(fragrance_families.c.fragrance_id == CollectionItem.fragrance_id)
        .scalar_subquery()
    )


def _wear_count_subq() -> Any:
    return select(func.count()).where(WearLog.collection_item_id == CollectionItem.id).scalar_subquery()


def _last_worn_subq() -> Any:
    return (
        select(func.max(WearLog.worn_on))
        .where(WearLog.collection_item_id == CollectionItem.id)
        .scalar_subquery()
    )


class CollectionRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    def _base(self) -> Select[Any]:
        return (
            select(
                CollectionItem,
                Fragrance.name.label("fragrance_name"),
                Brand.name.label("brand_name"),
                Fragrance.concentration,
                Fragrance.gender,
                Fragrance.image_url,
                _families_subq().label("families"),
                _wear_count_subq().label("wear_count"),
                _last_worn_subq().label("last_worn_on"),
            )
            .join(Fragrance, Fragrance.id == CollectionItem.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
        )

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        item: CollectionItem = row[0]
        d = {c.key: getattr(item, c.key) for c in CollectionItem.__table__.columns}
        d.update(
            fragrance_name=row.fragrance_name,
            brand_name=row.brand_name,
            concentration=row.concentration,
            gender=row.gender,
            image_url=row.image_url,
            families=sorted(row.families or []),
            wear_count=row.wear_count or 0,
            last_worn_on=row.last_worn_on,
        )
        return d

    async def list(
        self,
        user_id: uuid.UUID,
        statuses: tuple[str, ...] | None = None,
        family: str | None = None,
        sort: str = "date_desc",
    ) -> list[dict[str, Any]]:
        stmt = self._base().where(CollectionItem.user_id == user_id)
        if statuses:
            stmt = stmt.where(CollectionItem.status.in_(statuses))
        if family:
            stmt = stmt.where(
                select(1)
                .select_from(fragrance_families.join(Family, Family.id == fragrance_families.c.family_id))
                .where(
                    fragrance_families.c.fragrance_id == CollectionItem.fragrance_id,
                    func.lower(Family.name) == family.lower(),
                )
                .exists()
            )
        order: list[Any] = {  # type: ignore[assignment]
            "alpha": [func.lower(Fragrance.name)],
            "rating": [CollectionItem.rating.desc().nulls_last(), func.lower(Fragrance.name)],
            "date_desc": [CollectionItem.created_at.desc(), CollectionItem.id.desc()],
            "remaining": [CollectionItem.remaining_pct.asc(), func.lower(Fragrance.name)],
            "price": [CollectionItem.purchase_price.desc().nulls_last()],
            "worn": [_wear_count_subq().desc(), func.lower(Fragrance.name)],
            "last_worn": [_last_worn_subq().asc().nulls_first(), func.lower(Fragrance.name)],
        }.get(sort, [CollectionItem.created_at.desc()])
        rows = await self.s.execute(stmt.order_by(*order))
        return [self._row(r) for r in rows.all()]

    async def get_out(self, user_id: uuid.UUID, item_id: int) -> dict[str, Any] | None:
        row = (
            await self.s.execute(
                self._base().where(CollectionItem.user_id == user_id, CollectionItem.id == item_id)
            )
        ).first()
        return self._row(row) if row else None

    async def get(self, user_id: uuid.UUID, item_id: int) -> CollectionItem | None:
        return await self.s.scalar(
            select(CollectionItem).where(CollectionItem.user_id == user_id, CollectionItem.id == item_id)
        )

    async def by_client_ref(self, user_id: uuid.UUID, client_ref: str) -> CollectionItem | None:
        return await self.s.scalar(
            select(CollectionItem).where(
                CollectionItem.user_id == user_id, CollectionItem.client_ref == client_ref
            )
        )

    async def last_worn_by_item(self, user_id: uuid.UUID) -> dict[int, date]:
        rows = await self.s.execute(
            select(WearLog.collection_item_id, func.max(WearLog.worn_on))
            .where(WearLog.user_id == user_id, WearLog.collection_item_id.is_not(None))
            .group_by(WearLog.collection_item_id)
        )
        return {i: d for i, d in rows.tuples().all() if i is not None}
