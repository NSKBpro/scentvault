"""Catalog queries (SQLAlchemy 2.0 select())."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import Select, and_, delete, exists, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Accord,
    Brand,
    Family,
    Fragrance,
    FragranceEmbedding,
    FragranceNote,
    FragrancePrice,
    Note,
    Occasion,
    PriceLog,
    fragrance_accords,
    fragrance_families,
    fragrance_occasions,
)

MissingKind = Literal[
    "notes", "image", "prices", "embedding", "stale_embedding", "families", "description", "stale_prices"
]
FragranceSort = Literal["newest", "name", "brand", "year", "updated"]

STALE_PRICE_DAYS = 30


@dataclass
class FragranceFilters:
    search: str | None = None
    brand_id: int | None = None
    family_id: int | None = None
    accord_id: int | None = None
    occasion_id: int | None = None
    concentration: str | None = None
    gender: str | None = None
    missing: MissingKind | None = None
    include_discontinued: bool = True
    ids: list[int] | None = None


def _missing_clause(kind: MissingKind) -> Any:
    F = Fragrance
    emb = FragranceEmbedding
    if kind == "notes":
        return ~exists().where(FragranceNote.fragrance_id == F.id)
    if kind == "image":
        return or_(F.image_url.is_(None), F.image_url == "")
    if kind == "prices":
        return ~exists().where(FragrancePrice.fragrance_id == F.id)
    if kind == "embedding":
        return ~exists().where(emb.fragrance_id == F.id)
    if kind == "stale_embedding":
        return exists().where(emb.fragrance_id == F.id, emb.generated_at < F.updated_at)
    if kind == "families":
        return ~exists().where(fragrance_families.c.fragrance_id == F.id)
    if kind == "description":
        return or_(F.description.is_(None), F.description == "")
    if kind == "stale_prices":
        cutoff = datetime.now(UTC) - timedelta(days=STALE_PRICE_DAYS)
        latest = select(func.max(PriceLog.logged_at)).where(PriceLog.fragrance_id == F.id).scalar_subquery()
        return or_(latest.is_(None), latest < cutoff)
    raise ValueError(kind)


def _apply_filters(stmt: Select[Any], f: FragranceFilters) -> Select[Any]:
    F = Fragrance
    if f.search:
        term = f"%{f.search.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(F.name).like(term), func.lower(Brand.name).like(term)))
    if f.brand_id:
        stmt = stmt.where(F.brand_id == f.brand_id)
    if f.family_id:
        stmt = stmt.where(
            exists().where(
                fragrance_families.c.fragrance_id == F.id, fragrance_families.c.family_id == f.family_id
            )
        )
    if f.accord_id:
        stmt = stmt.where(
            exists().where(
                fragrance_accords.c.fragrance_id == F.id, fragrance_accords.c.accord_id == f.accord_id
            )
        )
    if f.occasion_id:
        stmt = stmt.where(
            exists().where(
                fragrance_occasions.c.fragrance_id == F.id, fragrance_occasions.c.occasion_id == f.occasion_id
            )
        )
    if f.concentration:
        stmt = stmt.where(F.concentration == f.concentration)
    if f.gender:
        stmt = stmt.where(F.gender == f.gender)
    if f.missing:
        stmt = stmt.where(_missing_clause(f.missing))
    if not f.include_discontinued:
        stmt = stmt.where(F.discontinued.is_(False))
    if f.ids is not None:
        stmt = stmt.where(F.id.in_(f.ids or [-1]))
    return stmt


class CatalogRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    # ── Fragrance list ───────────────────────────────────────────────
    async def list_fragrances(
        self, f: FragranceFilters, sort: FragranceSort, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        F = Fragrance
        base = select(F.id).join(Brand, Brand.id == F.brand_id)
        base = _apply_filters(base, f)
        total = await self.s.scalar(select(func.count()).select_from(base.subquery())) or 0

        note_count = (
            select(func.count()).where(FragranceNote.fragrance_id == F.id).correlate(F).scalar_subquery()
        )
        min_price = (
            select(func.min(FragrancePrice.price_usd))
            .where(FragrancePrice.fragrance_id == F.id)
            .scalar_subquery()
        )
        sizes = (
            select(func.array_agg(FragrancePrice.size_ml.distinct()))
            .where(FragrancePrice.fragrance_id == F.id)
            .scalar_subquery()
        )
        families = (
            select(func.array_agg(Family.name))
            .select_from(fragrance_families.join(Family, Family.id == fragrance_families.c.family_id))
            .where(fragrance_families.c.fragrance_id == F.id)
            .scalar_subquery()
        )
        has_emb = exists().where(FragranceEmbedding.fragrance_id == F.id)

        order: list[Any] = {  # type: ignore[assignment]
            "newest": [F.created_at.desc(), F.id.desc()],
            "name": [func.lower(F.name), F.id],
            "brand": [func.lower(Brand.name), func.lower(F.name)],
            "year": [F.release_year.desc().nulls_last(), func.lower(F.name)],
            "updated": [F.updated_at.desc(), F.id.desc()],
        }[sort]

        stmt: Select[Any] = select(  # type: ignore[assignment]
            F.id,
            F.name,
            F.brand_id,
            Brand.name.label("brand_name"),
            F.concentration,
            F.gender,
            F.release_year,
            F.image_url,
            F.discontinued,
            F.created_at,
            has_emb.label("has_embedding"),
            note_count.label("note_count"),
            min_price.label("min_price_usd"),
            sizes.label("sizes_ml"),
            families.label("families"),
        ).join(Brand, Brand.id == F.brand_id)
        stmt = _apply_filters(stmt, f).order_by(*order).offset((page - 1) * size).limit(size)
        rows = []
        for r in (await self.s.execute(stmt)).mappings():
            d = dict(r)
            d["sizes_ml"] = sorted(d["sizes_ml"] or [])
            d["families"] = sorted(d["families"] or [])
            rows.append(d)
        return rows, total

    async def get_fragrance(self, fragrance_id: int) -> Fragrance | None:
        stmt = (
            select(Fragrance)
            .options(
                selectinload(Fragrance.brand),
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.families),
                selectinload(Fragrance.accords),
                selectinload(Fragrance.occasions),
                selectinload(Fragrance.prices),
            )
            .where(Fragrance.id == fragrance_id)
            .execution_options(populate_existing=True)
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def has_embedding(self, fragrance_id: int) -> bool:
        return bool(
            await self.s.scalar(select(exists().where(FragranceEmbedding.fragrance_id == fragrance_id)))
        )

    async def exists(self, fragrance_id: int) -> bool:
        return bool(await self.s.scalar(select(exists().where(Fragrance.id == fragrance_id))))

    async def replace_relations(
        self,
        fragrance_id: int,
        notes: list[tuple[int, str, int]],
        family_ids: list[int],
        accord_ids: list[int],
        occasion_ids: list[int],
        prices: list[tuple[int, float]],
    ) -> None:
        s = self.s
        await s.execute(delete(FragranceNote).where(FragranceNote.fragrance_id == fragrance_id))
        await s.execute(delete(FragrancePrice).where(FragrancePrice.fragrance_id == fragrance_id))
        for table in (fragrance_families, fragrance_accords, fragrance_occasions):
            await s.execute(delete(table).where(table.c.fragrance_id == fragrance_id))
        seen: set[tuple[int, str]] = set()
        note_rows = []
        for note_id, position, prominence in notes:
            if (note_id, position) in seen:
                continue
            seen.add((note_id, position))
            note_rows.append(
                {
                    "fragrance_id": fragrance_id,
                    "note_id": note_id,
                    "position": position,
                    "prominence": prominence,
                }
            )
        if note_rows:
            await s.execute(insert(FragranceNote), note_rows)
        price_map = dict(prices)  # last one per size wins
        if price_map:
            await s.execute(
                insert(FragrancePrice),
                [
                    {"fragrance_id": fragrance_id, "size_ml": sz, "price_usd": p}
                    for sz, p in price_map.items()
                ],
            )
        for table, col, ids in (
            (fragrance_families, "family_id", family_ids),
            (fragrance_accords, "accord_id", accord_ids),
            (fragrance_occasions, "occasion_id", occasion_ids),
        ):
            uniq = list(dict.fromkeys(ids))
            if uniq:
                await s.execute(insert(table), [{"fragrance_id": fragrance_id, col: i} for i in uniq])

    async def count_missing_ids(self, model: type, ids: list[int]) -> list[int]:
        if not ids:
            return []
        found = set((await self.s.execute(select(model.id).where(model.id.in_(ids)))).scalars())  # type: ignore[attr-defined]
        return [i for i in dict.fromkeys(ids) if i not in found]

    # ── Lookups ──────────────────────────────────────────────────────
    async def list_lookup(
        self, kind: str, page: int, size: int, search: str | None, category: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        model, count_expr = self._lookup_model(kind)
        conds: list[Any] = []
        if search:
            conds.append(func.lower(model.name).like(f"%{search.strip().lower()}%"))
        if category and model is Note:
            conds.append(Note.category == category)
        total = await self.s.scalar(select(func.count()).select_from(model).where(*conds)) or 0
        cols: list[Any] = [model]
        if count_expr is not None:
            cols.append(count_expr.label("fragrance_count"))
        q = select(*cols).where(*conds).order_by(func.lower(model.name)).offset((page - 1) * size).limit(size)
        out = []
        for row in (await self.s.execute(q)).all():
            obj = row[0]
            d = {c.key: getattr(obj, c.key) for c in model.__table__.columns}
            if count_expr is not None:
                d["fragrance_count"] = row[1] or 0
            out.append(d)
        return out, total

    def _lookup_model(self, kind: str) -> tuple[Any, Any]:
        if kind == "brands":
            return Brand, select(func.count()).where(Fragrance.brand_id == Brand.id).scalar_subquery()
        if kind == "families":
            return Family, (
                select(func.count()).where(fragrance_families.c.family_id == Family.id).scalar_subquery()
            )
        if kind == "accords":
            return Accord, (
                select(func.count()).where(fragrance_accords.c.accord_id == Accord.id).scalar_subquery()
            )
        if kind == "occasions":
            return Occasion, (
                select(func.count()).where(fragrance_occasions.c.occasion_id == Occasion.id).scalar_subquery()
            )
        if kind == "notes":
            return Note, None
        raise ValueError(kind)

    async def note_categories(self) -> list[str]:
        rows = await self.s.execute(select(Note.category).distinct().order_by(Note.category))
        return [r for r in rows.scalars() if r]

    async def fragrance_ids_needing_embedding(self, only_missing: bool) -> list[int]:
        stmt = select(Fragrance.id).order_by(Fragrance.id)
        if only_missing:
            stmt = stmt.where(or_(_missing_clause("embedding"), _missing_clause("stale_embedding")))
        return list((await self.s.execute(stmt)).scalars())


def name_conflict_filter(model: Any, name: str, exclude_id: int | None = None) -> Any:
    clause = func.lower(model.name) == name.strip().lower()
    if exclude_id is not None:
        clause = and_(clause, model.id != exclude_id)
    return clause
