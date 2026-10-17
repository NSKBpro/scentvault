"""Seed reference data (idempotent).

    python -m seeds.run                 # brands, notes, families (+ radar axis), accords, occasions, retailers
    python -m seeds.run --demo          # + ~24 well-known fragrances (approximate pyramids, for trying the app)
    python -m seeds.run --admin you@example.com --password '...'   # + create/promote an admin

Safe to run repeatedly: existing rows (matched case-insensitively by name) are left alone, except that
families without a radar axis get one.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.normalize import axis_for_family
from app.core.security import hash_password
from app.db.session import dispose_engine, get_sessionmaker
from app.models import (
    Accord,
    Brand,
    Family,
    Fragrance,
    FragranceNote,
    FragrancePrice,
    Note,
    Occasion,
    Retailer,
    User,
    UserPreferences,
)

DATA = Path(__file__).parent / "data"


def load(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


async def _existing(s: AsyncSession, model: Any) -> dict[str, Any]:
    rows = (await s.execute(select(model))).scalars().all()
    return {r.name.lower(): r for r in rows}


async def seed_reference(s: AsyncSession) -> dict[str, int]:
    added: dict[str, int] = {}

    async def upsert_named(model: Any, items: list[dict[str, Any]], key: str) -> None:
        have = await _existing(s, model)
        n = 0
        for it in items:
            if it["name"].lower() not in have:
                obj = model(**it)
                s.add(obj)
                have[it["name"].lower()] = obj
                n += 1
        added[key] = n

    await upsert_named(Brand, load("brands.json"), "brands")
    await upsert_named(Note, load("notes.json"), "notes")
    await upsert_named(Accord, [{"name": n} for n in load("accords.json")], "accords")
    await upsert_named(Occasion, [{"name": n} for n in load("occasions.json")], "occasions")
    await upsert_named(Retailer, load("retailers.json"), "retailers")
    await upsert_named(Family, load("families.json"), "families")
    await s.flush()
    # Families created elsewhere (admin, legacy import) get an axis guess if they have none.
    for fam in (await s.execute(select(Family).where(Family.axis.is_(None)))).scalars():
        fam.axis = axis_for_family(fam.name)
    await s.commit()
    return added


async def seed_demo(s: AsyncSession) -> int:
    brands = await _existing(s, Brand)
    notes = await _existing(s, Note)
    families = await _existing(s, Family)
    accords = await _existing(s, Accord)
    occasions = await _existing(s, Occasion)
    created = 0
    for d in load("demo_fragrances.json"):
        brand = brands.get(d["brand"].lower())
        if brand is None:
            brand = Brand(name=d["brand"])
            s.add(brand)
            await s.flush()
            brands[d["brand"].lower()] = brand
        exists = await s.scalar(
            select(Fragrance.id).where(
                Fragrance.brand_id == brand.id,
                func.lower(Fragrance.name) == d["name"].lower(),
                Fragrance.concentration == d["concentration"],
            )
        )
        if exists:
            continue
        f = Fragrance(
            name=d["name"],
            brand_id=brand.id,
            concentration=d["concentration"],
            gender=d["gender"],
            sillage=d.get("sillage"),
            release_year=d.get("release_year"),
            longevity_hours=d.get("longevity_hours"),
            **{f"season_{x.lower()}": True for x in d.get("seasons", [])},
        )
        f.families = [families[n.lower()] for n in d.get("families", []) if n.lower() in families]
        f.accords = [accords[n.lower()] for n in d.get("accords", []) if n.lower() in accords]
        f.occasions = [occasions[n.lower()] for n in d.get("occasions", []) if n.lower() in occasions]
        s.add(f)
        await s.flush()
        for pos in ("top", "heart", "base"):
            for rank, name in enumerate(d.get(pos, [])):
                note = notes.get(name.lower())
                if note is None:
                    note = Note(name=name, category="Other")
                    s.add(note)
                    await s.flush()
                    notes[name.lower()] = note
                s.add(
                    FragranceNote(
                        fragrance_id=f.id, note_id=note.id, position=pos, prominence=max(1, 5 - rank)
                    )
                )
        for size, price in d.get("prices", []):
            s.add(FragrancePrice(fragrance_id=f.id, size_ml=size, price_usd=price))
        created += 1
    await s.commit()
    return created


async def ensure_admin(s: AsyncSession, email: str, password: str | None) -> str:
    user = await s.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        if not password:
            raise SystemExit("New admin needs --password")
        user = User(
            email=email.lower(), password_hash=hash_password(password), role="admin", display_name="Admin"
        )
        s.add(user)
        await s.flush()
        s.add(UserPreferences(user_id=user.id))
        result = "created"
    else:
        user.role = "admin"
        if password:
            user.password_hash = hash_password(password)
        result = "promoted"
    await s.commit()
    return result


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="also add the demo fragrance catalog")
    ap.add_argument("--admin", metavar="EMAIL", help="create or promote this admin user")
    ap.add_argument("--password", help="password for --admin (required when creating)")
    args = ap.parse_args()
    async with get_sessionmaker()() as s:
        added = await seed_reference(s)
        print("Reference data added:", ", ".join(f"{k} {v}" for k, v in added.items()))
        if args.demo:
            print(f"Demo fragrances added: {await seed_demo(s)}")
        if args.admin:
            print(f"Admin {args.admin}: {await ensure_admin(s, args.admin, args.password)}")
    await dispose_engine()
    print(
        "Embeddings: run the API/worker — missing ones are generated by the daily job, or trigger "
        "'Regenerate missing' on the admin Embeddings page."
    )


if __name__ == "__main__":
    asyncio.run(main())
