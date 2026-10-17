"""Catalog business rules: fragrances, lookups, retailers."""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Invalid, NotFound
from app.models import Accord, Brand, Family, Fragrance, Note, Occasion, Retailer
from app.repositories.catalog import CatalogRepository, FragranceFilters, FragranceSort, name_conflict_filter
from app.schemas.catalog import FragranceDetail, FragranceIn, FragranceListItem
from app.schemas.common import Page, RefOut
from app.workers.queue import JobQueue

LOOKUP_MODELS: dict[str, Any] = {
    "brands": Brand,
    "notes": Note,
    "families": Family,
    "accords": Accord,
    "occasions": Occasion,
}
SINGULAR = {
    "brands": "Brand",
    "notes": "Note",
    "families": "Family",
    "accords": "Accord",
    "occasions": "Occasion",
}


def to_detail(f: Fragrance, has_embedding: bool) -> FragranceDetail:
    return FragranceDetail(
        id=f.id,
        name=f.name,
        brand=RefOut(id=f.brand.id, name=f.brand.name),
        brand_id=f.brand_id,
        concentration=f.concentration,
        gender=f.gender,
        sillage=f.sillage,  # type: ignore[arg-type]
        release_year=f.release_year,
        description=f.description,
        longevity_hours=f.longevity_hours,
        image_url=f.image_url,
        discontinued=f.discontinued,
        season_spring=f.season_spring,
        season_summer=f.season_summer,
        season_fall=f.season_fall,
        season_winter=f.season_winter,
        notes=[
            {
                "note_id": n.note_id,
                "name": n.note.name,
                "category": n.note.category,
                "position": n.position,
                "prominence": n.prominence,
            }
            for n in sorted(
                f.notes,
                key=lambda n: (("top", "heart", "base").index(n.position), -n.prominence, n.note.name),
            )
        ],
        families=[RefOut(id=x.id, name=x.name) for x in f.families],
        accords=[RefOut(id=x.id, name=x.name) for x in f.accords],
        occasions=[RefOut(id=x.id, name=x.name) for x in f.occasions],
        prices=[{"id": p.id, "size_ml": p.size_ml, "price_usd": p.price_usd} for p in f.prices],
        has_embedding=has_embedding,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


class CatalogService:
    def __init__(self, session: AsyncSession, queue: JobQueue | None = None):
        self.s = session
        self.repo = CatalogRepository(session)
        self.queue = queue

    # ── Fragrances ───────────────────────────────────────────────────
    async def list_fragrances(
        self, filters: FragranceFilters, sort: FragranceSort, page: int, size: int
    ) -> Page[FragranceListItem]:
        rows, total = await self.repo.list_fragrances(filters, sort, page, size)
        return Page[FragranceListItem](
            items=[FragranceListItem(**r) for r in rows], total=total, page=page, size=size
        )

    async def get_detail(self, fragrance_id: int) -> FragranceDetail:
        f = await self.repo.get_fragrance(fragrance_id)
        if f is None:
            raise NotFound("Fragrance")
        return to_detail(f, await self.repo.has_embedding(fragrance_id))

    async def _validate_refs(self, data: FragranceIn) -> None:
        if not await self.s.get(Brand, data.brand_id):
            raise Invalid(f"Brand {data.brand_id} does not exist")
        for model, ids, label in (
            (Note, [n.note_id for n in data.notes], "note"),
            (Family, data.family_ids, "family"),
            (Accord, data.accord_ids, "accord"),
            (Occasion, data.occasion_ids, "occasion"),
        ):
            missing = await self.repo.count_missing_ids(model, ids)
            if missing:
                raise Invalid(f"Unknown {label} id(s): {', '.join(map(str, missing))}")

    async def _save(self, f: Fragrance, data: FragranceIn) -> None:
        for field in (
            "name",
            "brand_id",
            "concentration",
            "gender",
            "sillage",
            "release_year",
            "description",
            "longevity_hours",
            "image_url",
            "discontinued",
            "season_spring",
            "season_summer",
            "season_fall",
            "season_winter",
        ):
            setattr(f, field, getattr(data, field))
        f.name = f.name.strip()
        try:
            self.s.add(f)
            await self.s.flush()
            await self.repo.replace_relations(
                f.id,
                [(n.note_id, n.position, n.prominence) for n in data.notes],
                data.family_ids,
                data.accord_ids,
                data.occasion_ids,
                [(p.size_ml, p.price_usd) for p in data.prices],
            )
            f.updated_at = func.now()  # relations changed → embedding is stale
            await self.s.commit()
        except IntegrityError as exc:
            await self.s.rollback()
            raise Conflict("A fragrance with this brand, name and concentration already exists") from exc

    async def _queue_embedding(self, fragrance_id: int) -> None:
        if self.queue is not None:
            await self.queue.enqueue("embed_fragrances", [fragrance_id])

    async def create_fragrance(self, data: FragranceIn) -> FragranceDetail:
        await self._validate_refs(data)
        f = Fragrance()
        await self._save(f, data)
        await self._queue_embedding(f.id)
        return await self.get_detail(f.id)

    async def update_fragrance(self, fragrance_id: int, data: FragranceIn) -> FragranceDetail:
        f = await self.s.get(Fragrance, fragrance_id)
        if f is None:
            raise NotFound("Fragrance")
        await self._validate_refs(data)
        await self._save(f, data)
        await self._queue_embedding(fragrance_id)
        return await self.get_detail(fragrance_id)

    async def delete_fragrance(self, fragrance_id: int) -> None:
        res = await self.s.execute(
            delete(Fragrance).where(Fragrance.id == fragrance_id).returning(Fragrance.id)
        )
        if res.scalar_one_or_none() is None:
            raise NotFound("Fragrance")
        await self.s.commit()

    # ── Lookups (brands, notes, families, accords, occasions) ────────
    async def list_lookup(
        self, kind: str, page: int, size: int, search: str | None, category: str | None = None
    ):
        rows, total = await self.repo.list_lookup(kind, page, size, search, category)
        return rows, total

    async def _get_lookup(self, kind: str, item_id: int) -> Any:
        obj = await self.s.get(LOOKUP_MODELS[kind], item_id)
        if obj is None:
            raise NotFound(SINGULAR[kind])
        return obj

    async def _ensure_unique(self, kind: str, name: str, exclude_id: int | None = None) -> None:
        model = LOOKUP_MODELS[kind]
        if await self.s.scalar(select(model.id).where(name_conflict_filter(model, name, exclude_id))):
            raise Conflict(f"{SINGULAR[kind]} '{name.strip()}' already exists")

    async def create_lookup(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_unique(kind, data["name"])
        data["name"] = data["name"].strip()
        obj = LOOKUP_MODELS[kind](**data)
        self.s.add(obj)
        await self.s.commit()
        return await self.lookup_out(kind, obj.id)

    async def update_lookup(self, kind: str, item_id: int, data: dict[str, Any]) -> dict[str, Any]:
        obj = await self._get_lookup(kind, item_id)
        if data.get("name"):
            await self._ensure_unique(kind, data["name"], exclude_id=item_id)
            data["name"] = data["name"].strip()
        for k, v in data.items():
            if k == "name" and not v:
                continue
            setattr(obj, k, v)
        await self.s.commit()
        return await self.lookup_out(kind, item_id)

    async def delete_lookup(self, kind: str, item_id: int) -> None:
        obj = await self._get_lookup(kind, item_id)
        if kind == "brands":
            n = await self.s.scalar(select(func.count()).where(Fragrance.brand_id == item_id))
            if n:
                raise Conflict(f"Brand has {n} fragrance(s); move or delete them first")
        await self.s.delete(obj)
        await self.s.commit()

    async def lookup_out(self, kind: str, item_id: int) -> dict[str, Any]:
        model, count_expr = self.repo._lookup_model(kind)
        cols = [model] + ([count_expr.label("fragrance_count")] if count_expr is not None else [])
        row = (await self.s.execute(select(*cols).where(model.id == item_id))).one()
        d = {c.key: getattr(row[0], c.key) for c in model.__table__.columns}
        if count_expr is not None:
            d["fragrance_count"] = row[1] or 0
        return d

    async def import_notes_csv(self, raw: bytes) -> dict[str, Any]:
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or "name" not in [h.strip().lower() for h in reader.fieldnames]:
            raise Invalid("CSV must have a 'name' column (and optionally 'category', 'description')")
        existing = {n.lower() for n in (await self.s.execute(select(Note.name))).scalars()}
        inserted = skipped = 0
        errors: list[str] = []
        for i, row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            name = row.get("name", "")
            if not name:
                errors.append(f"Row {i}: missing name")
                continue
            if name.lower() in existing:
                skipped += 1
                continue
            self.s.add(
                Note(
                    name=name,
                    category=row.get("category") or "Other",
                    description=row.get("description") or None,
                )
            )
            existing.add(name.lower())
            inserted += 1
        await self.s.commit()
        return {"inserted": inserted, "skipped": skipped, "errors": errors[:50]}

    # ── Retailers ────────────────────────────────────────────────────
    async def list_retailers(self) -> list[Retailer]:
        return list((await self.s.execute(select(Retailer).order_by(func.lower(Retailer.name)))).scalars())

    async def save_retailer(self, data: dict[str, Any], retailer_id: int | None = None) -> Retailer:
        if await self.s.scalar(
            select(Retailer.id).where(name_conflict_filter(Retailer, data["name"], retailer_id))
        ):
            raise Conflict(f"Retailer '{data['name']}' already exists")
        r: Retailer | None
        if retailer_id is None:
            r = Retailer(**data)
            self.s.add(r)
        else:
            r = await self.s.get(Retailer, retailer_id)
            if r is None:
                raise NotFound("Retailer")
            for k, v in data.items():
                setattr(r, k, v)
        await self.s.commit()
        await self.s.refresh(r)
        return r

    async def delete_retailer(self, retailer_id: int) -> None:
        r = await self.s.get(Retailer, retailer_id)
        if r is None:
            raise NotFound("Retailer")
        await self.s.delete(r)
        await self.s.commit()
