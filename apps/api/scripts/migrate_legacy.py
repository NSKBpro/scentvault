"""Copy data from the pre-2.0 ScentVault database into a fresh 2.0 database.

The old database was shaped by hand (two forked migrations + patch_db.py), so this
script reads it defensively: it checks which tables/columns exist and normalises
values on the way in.

    # 1. new, empty database at the baseline schema
    alembic upgrade head
    # 2. copy (source = old DB, target = DATABASE_URL from .env unless --target is given)
    python -m scripts.migrate_legacy --source postgresql://scentvault:password@localhost:5432/scentvault_legacy

What it does
* Keeps ids, so links between rows survive.
* Users keep their passwords (bcrypt hashes are compatible) and get default preferences.
* Families get a Scent-DNA radar axis guessed from their name (editable in admin).
* Prominence values on the old 0–100 scale are folded into 1–5.
* Embeddings are copied when they were made by the same model; otherwise the
  API's daily job (or admin → Embeddings → Regenerate) rebuilds them.
* Collection prices are tagged USD (the old app only knew dollars).

It refuses to run into a target that already has fragrances unless --force.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.core import normalize
from app.core.constants import COLLECTION_STATUSES


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _half(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return min(5.0, max(0.5, round(f * 2) / 2))


@dataclass
class Report:
    copied: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, table: str, n: int = 1) -> None:
        self.copied[table] = self.copied.get(table, 0) + n

    def skip(self, table: str, why: str) -> None:
        self.skipped[table] = self.skipped.get(table, 0) + 1
        if len(self.notes) < 200:
            self.notes.append(f"{table}: {why}")

    def print(self) -> None:
        print("\nCopied:")
        for t, n in self.copied.items():
            print(f"  {t:<22} {n}")
        if self.skipped:
            print("Skipped:")
            for t, n in self.skipped.items():
                print(f"  {t:<22} {n}")
            print("Details:")
            for note in self.notes:
                print(f"  - {note}")


class LegacyMigrator:
    def __init__(self, src: asyncpg.Connection, dst: asyncpg.Connection, model_version: str):
        self.src = src
        self.dst = dst
        self.model_version = model_version
        self.r = Report()
        self.cols: dict[str, set[str]] = {}

    async def load_schema(self) -> None:
        rows = await self.src.fetch(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        )
        for row in rows:
            self.cols.setdefault(row["table_name"], set()).add(row["column_name"])

    def has(self, table: str, *columns: str) -> bool:
        return table in self.cols and all(c in self.cols[table] for c in columns)

    async def rows(self, table: str, order: str = "") -> list[asyncpg.Record]:
        if table not in self.cols:
            return []
        return list(
            await self.src.fetch(f'SELECT * FROM "{table}" {order}')
        )  # table names come from our list

    @staticmethod
    def g(row: asyncpg.Record, key: str, default: Any = None) -> Any:
        return row[key] if key in row.keys() else default  # noqa: SIM118 (Record `in` checks values)

    # ── Steps ────────────────────────────────────────────────────────
    async def run(self) -> Report:
        await self.load_schema()
        async with self.dst.transaction():
            await self.brands()
            await self.simple(
                "notes",
                ["id", "name", "category", "description"],
                fix=lambda d: {**d, "category": d.get("category") or "Other"},
            )
            await self.families()
            await self.simple("accords", ["id", "name"])
            await self.simple("occasions", ["id", "name"])
            await self.retailers()
            await (
                self.reset_sequences()
            )  # rows created from here on (e.g. occasions from tags) need fresh ids
            frag_ids = await self.fragrances()
            await self.fragrance_notes(frag_ids)
            await self.joins(frag_ids)
            await self.prices(frag_ids)
            await self.price_logs(frag_ids)
            await self.embeddings(frag_ids)
            user_ids = await self.users()
            await self.collection(user_ids, frag_ids)
            await self.reset_sequences()
        return self.r

    async def simple(self, table: str, columns: list[str], fix: Any = None) -> None:
        seen: set[str] = set()
        for row in await self.rows(table, "ORDER BY id"):
            d = {c: self.g(row, c) for c in columns}
            if fix:
                d = fix(d)
            key = (d["name"] or "").strip().lower()
            if not key or key in seen:
                self.r.skip(table, f"duplicate or empty name {d['name']!r} (id {d['id']})")
                continue
            seen.add(key)
            d["name"] = d["name"].strip()
            cols = ", ".join(d)
            vals = ", ".join(f"${i + 1}" for i in range(len(d)))
            await self.dst.execute(f"INSERT INTO {table} ({cols}) VALUES ({vals})", *d.values())
            self.r.add(table)

    async def brands(self) -> None:
        await self.simple(
            "brands",
            ["id", "name", "country", "website_url", "logo_url", "description", "created_at"],
            fix=lambda d: {**d, "created_at": _utc(d.get("created_at"))},
        )

    async def families(self) -> None:
        # Newer DBs: `families` is the family table. Older ones called it `fragrance_families`
        # (with a name column) — only use that when `families` doesn't exist.
        table = (
            "families"
            if "families" in self.cols
            else ("fragrance_families" if self.has("fragrance_families", "name") else None)
        )
        if not table:
            return
        seen: set[str] = set()
        for row in await self.rows(table, "ORDER BY id"):
            name = (row["name"] or "").strip()
            if not name or name.lower() in seen:
                self.r.skip("families", f"duplicate or empty {name!r}")
                continue
            seen.add(name.lower())
            await self.dst.execute(
                "INSERT INTO families (id, name, description, axis) VALUES ($1, $2, $3, $4)",
                row["id"],
                name,
                self.g(row, "description"),
                normalize.axis_for_family(name),
            )
            self.r.add("families")
        missing_axis = await self.dst.fetch("SELECT name FROM families WHERE axis IS NULL")
        if missing_axis:
            self.r.notes.append(
                "families without a radar axis (set one in admin → Families): "
                + ", ".join(r["name"] for r in missing_axis)
            )

    async def retailers(self) -> None:
        await self.simple(
            "retailers",
            ["id", "name", "website_url", "country", "created_at"],
            fix=lambda d: {**d, "created_at": _utc(d.get("created_at"))},
        )

    async def fragrances(self) -> dict[int, int]:
        """Returns legacy id → new id (duplicates collapse onto the first row)."""
        brand_ids = {r["id"] for r in await self.dst.fetch("SELECT id FROM brands")}
        seen: dict[tuple[int, str, str], int] = {}
        mapping: dict[int, int] = {}
        for row in await self.rows("fragrances", "ORDER BY id"):
            fid = row["id"]
            if row["brand_id"] not in brand_ids:
                self.r.skip("fragrances", f"id {fid}: brand {row['brand_id']} missing")
                continue
            conc = normalize.concentration(row["concentration"])
            if conc is None:
                self.r.notes.append(f"fragrance {fid}: concentration {row['concentration']!r} → EDP")
                conc = "EDP"
            gender = normalize.gender(row["gender"], default="Unisex")
            name = (row["name"] or "").strip()
            key = (row["brand_id"], name.lower(), conc)
            if key in seen:
                mapping[fid] = seen[key]
                self.r.skip("fragrances", f"id {fid} duplicates id {seen[key]} ({name}, {conc}); merged")
                continue
            created = _utc(self.g(row, "created_at"))
            lon = self.g(row, "longevity_hours")
            await self.dst.execute(
                """INSERT INTO fragrances (id, name, brand_id, concentration, gender, sillage, release_year,
                       description, longevity_hours, image_url, discontinued, season_spring, season_summer,
                       season_fall, season_winter, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16)""",
                fid,
                name,
                row["brand_id"],
                conc,
                gender,
                normalize.sillage(self.g(row, "sillage"), default="Moderate"),
                self.g(row, "release_year"),
                self.g(row, "description"),
                float(lon) if lon is not None else None,
                self.g(row, "image_url"),
                bool(self.g(row, "discontinued", False)),
                *(bool(self.g(row, f"season_{s}", False)) for s in ("spring", "summer", "fall", "winter")),
                created,
            )
            seen[key] = fid
            mapping[fid] = fid
            self.r.add("fragrances")
        # Legacy `occasion_tags` arrays → occasions, for fragrances that had no join rows.
        if self.has("fragrances", "occasion_tags"):
            occ = {r["name"].lower(): r["id"] for r in await self.dst.fetch("SELECT id, name FROM occasions")}
            joined = (
                {r["fragrance_id"] for r in await self.rows("fragrance_occasions")}
                if "fragrance_occasions" in self.cols
                else set()
            )
            for row in await self.rows("fragrances"):
                tags = self.g(row, "occasion_tags") or []
                if row["id"] in joined or row["id"] not in mapping or not tags:
                    continue
                for tag in tags:
                    tag = str(tag).strip()
                    if not tag:
                        continue
                    if tag.lower() not in occ:
                        occ[tag.lower()] = await self.dst.fetchval(
                            "INSERT INTO occasions (name) VALUES ($1) RETURNING id", tag
                        )
                    await self.dst.execute(
                        "INSERT INTO fragrance_occasions VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        mapping[row["id"]],
                        occ[tag.lower()],
                    )
                    self.r.add("occasions_from_tags")
        return mapping

    async def fragrance_notes(self, frag: dict[int, int]) -> None:
        notes = {r["id"] for r in await self.dst.fetch("SELECT id FROM notes")}
        for row in await self.rows("fragrance_notes"):
            pos = normalize.position(self.g(row, "position", "heart")) or "heart"
            fid = frag.get(row["fragrance_id"])
            if fid is None or row["note_id"] not in notes:
                self.r.skip(
                    "fragrance_notes", f"orphan row fragrance {row['fragrance_id']} note {row['note_id']}"
                )
                continue
            res = await self.dst.execute(
                "INSERT INTO fragrance_notes (fragrance_id, note_id, position, prominence) VALUES ($1,$2,$3,$4) "
                "ON CONFLICT DO NOTHING",
                fid,
                row["note_id"],
                pos,
                normalize.prominence(self.g(row, "prominence", 3)),
            )
            if res.endswith("1"):
                self.r.add("fragrance_notes")

    async def joins(self, frag: dict[int, int]) -> None:
        async def copy(src_table: str, dst_table: str, col: str, valid: set[int]) -> None:
            if not self.has(src_table, "fragrance_id", col):
                return
            for row in await self.rows(src_table):
                fid = frag.get(row["fragrance_id"])
                if fid is None or row[col] not in valid:
                    self.r.skip(dst_table, f"orphan row {dict(row)}")
                    continue
                res = await self.dst.execute(
                    f"INSERT INTO {dst_table} (fragrance_id, {col}) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    fid,
                    row[col],
                )
                if res.endswith("1"):
                    self.r.add(dst_table)

        fams = {r["id"] for r in await self.dst.fetch("SELECT id FROM families")}
        accs = {r["id"] for r in await self.dst.fetch("SELECT id FROM accords")}
        occs = {r["id"] for r in await self.dst.fetch("SELECT id FROM occasions")}
        # The join table is `fragrance_families` in newer DBs and `fragrance_families_map` in older ones.
        await copy("fragrance_families", "fragrance_families", "family_id", fams)
        await copy("fragrance_families_map", "fragrance_families", "family_id", fams)
        await copy("fragrance_accords", "fragrance_accords", "accord_id", accs)
        await copy("fragrance_occasions", "fragrance_occasions", "occasion_id", occs)
        # Oldest schema stored accords as free text.
        if self.has("fragrance_accords", "accord_name"):
            names = {r["name"].lower(): r["id"] for r in await self.dst.fetch("SELECT id, name FROM accords")}
            for row in await self.rows("fragrance_accords"):
                nm = (row["accord_name"] or "").strip()
                fid = frag.get(row["fragrance_id"])
                if not nm or fid is None:
                    continue
                if nm.lower() not in names:
                    names[nm.lower()] = await self.dst.fetchval(
                        "INSERT INTO accords (name) VALUES ($1) RETURNING id", nm
                    )
                await self.dst.execute(
                    "INSERT INTO fragrance_accords VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    fid,
                    names[nm.lower()],
                )
                self.r.add("fragrance_accords")

    async def prices(self, frag: dict[int, int]) -> None:
        for row in await self.rows("fragrance_prices", "ORDER BY id"):
            fid = frag.get(row["fragrance_id"])
            size = self.g(row, "size_ml")
            price = self.g(row, "price_usd")
            if fid is None or not size or size <= 0 or price is None or price < 0:
                self.r.skip("fragrance_prices", f"invalid row {dict(row)}")
                continue
            res = await self.dst.execute(
                "INSERT INTO fragrance_prices (fragrance_id, size_ml, price_usd) VALUES ($1,$2,$3) "
                "ON CONFLICT (fragrance_id, size_ml) DO NOTHING",
                fid,
                int(size),
                float(price),
            )
            if res.endswith("1"):
                self.r.add("fragrance_prices")
            else:
                self.r.skip("fragrance_prices", f"fragrance {fid}: second price for {size} ml ignored")

    async def price_logs(self, frag: dict[int, int]) -> None:
        retailers = {r["id"] for r in await self.dst.fetch("SELECT id FROM retailers")}
        for row in await self.rows("price_logs", "ORDER BY id"):
            fid = frag.get(row["fragrance_id"])
            if fid is None or row["retailer_id"] not in retailers or not self.g(row, "size_ml"):
                self.r.skip("price_logs", f"orphan or sizeless row id {row['id']}")
                continue
            await self.dst.execute(
                "INSERT INTO price_logs (fragrance_id, retailer_id, size_ml, price_usd, product_url, is_sale, logged_at) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7)",
                fid,
                row["retailer_id"],
                int(row["size_ml"]),
                float(row["price_usd"]),
                self.g(row, "product_url"),
                bool(self.g(row, "is_sale", False)),
                _utc(self.g(row, "logged_at")),
            )
            self.r.add("price_logs")
        # price_entries had no size: only usable when the fragrance has exactly one known size.
        if "price_entries" in self.cols:
            sizes: dict[int, list[int]] = {}
            for r in await self.dst.fetch("SELECT fragrance_id, size_ml FROM fragrance_prices"):
                sizes.setdefault(r["fragrance_id"], []).append(r["size_ml"])
            for row in await self.rows("price_entries"):
                fid = frag.get(row["fragrance_id"])
                known = sizes.get(fid or -1, [])
                if fid is None or row["retailer_id"] not in retailers or len(known) != 1:
                    self.r.skip("price_entries", f"id {row['id']}: size unknown, not migrated")
                    continue
                await self.dst.execute(
                    "INSERT INTO price_logs (fragrance_id, retailer_id, size_ml, price_usd, logged_at) VALUES ($1,$2,$3,$4,$5)",
                    fid,
                    row["retailer_id"],
                    known[0],
                    float(row["price_usd"]),
                    _utc(self.g(row, "spotted_at")),
                )
                self.r.add("price_logs (from price_entries)")

    async def embeddings(self, frag: dict[int, int]) -> None:
        if not self.has("fragrance_embeddings", "fragrance_id", "embedding"):
            return
        rows = await self.src.fetch(
            "SELECT fragrance_id, embedding::text AS emb, text_input, model_version, "
            + (
                "generated_at"
                if self.has("fragrance_embeddings", "generated_at")
                else "now() AS generated_at"
            )
            + " FROM fragrance_embeddings"
        )
        for row in rows:
            fid = frag.get(row["fragrance_id"])
            if fid is None or fid != row["fragrance_id"]:
                continue
            if row["model_version"] != self.model_version or row["emb"].count(",") != 383:
                self.r.skip(
                    "fragrance_embeddings",
                    f"fragrance {fid}: model {row['model_version']!r} — will be regenerated",
                )
                continue
            await self.dst.execute(
                "INSERT INTO fragrance_embeddings (fragrance_id, embedding, text_input, model_version, generated_at) "
                "VALUES ($1, $2::vector, $3, $4, $5) ON CONFLICT DO NOTHING",
                fid,
                row["emb"],
                row["text_input"] or "",
                row["model_version"],
                _utc(row["generated_at"]),
            )
            self.r.add("fragrance_embeddings")
        # Copied vectors must not look out of date: stale = generated_at < fragrance.updated_at.
        await self.dst.execute(
            "UPDATE fragrances f SET updated_at = LEAST(f.updated_at, e.generated_at) "
            "FROM fragrance_embeddings e WHERE e.fragrance_id = f.id"
        )

    async def users(self) -> set[Any]:
        ids: set[Any] = set()
        seen: set[str] = set()
        for row in await self.rows("users", "ORDER BY created_at"):
            email = (row["email"] or "").strip().lower()
            if not email or email in seen:
                self.r.skip("users", f"duplicate or empty email {row['email']!r}")
                continue
            seen.add(email)
            role = "admin" if (self.g(row, "role") or "").lower() == "admin" else "user"
            created = _utc(self.g(row, "created_at"))
            await self.dst.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, created_at, updated_at) "
                "VALUES ($1,$2,$3,$4,$5,$6,$6)",
                row["id"],
                email,
                row["password_hash"],
                self.g(row, "display_name"),
                role,
                created,
            )
            await self.dst.execute(
                "INSERT INTO user_preferences (user_id, currency) VALUES ($1, $2)",
                row["id"],
                os.environ.get("DEFAULT_CURRENCY", "EUR"),
            )
            ids.add(row["id"])
            self.r.add("users")
        return ids

    async def collection(self, users: set[Any], frag: dict[int, int]) -> None:
        for row in await self.rows("user_collection", "ORDER BY id"):
            fid = frag.get(row["fragrance_id"])
            if fid is None or row["user_id"] not in users:
                self.r.skip("user_collection", f"id {row['id']}: orphan")
                continue
            status = (self.g(row, "status") or "own").strip().lower()
            if status not in COLLECTION_STATUSES:
                self.r.notes.append(f"collection {row['id']}: status {status!r} → own")
                status = "own"
            size = self.g(row, "size_ml")
            size = int(size) if size and size > 0 else None
            remaining = self.g(row, "remaining_pct")
            remaining = 100 if remaining is None else max(0, min(100, int(remaining)))
            if status in ("finished", "sold", "gifted"):
                remaining = 0
            price = self.g(row, "purchase_price")
            created = _utc(self.g(row, "created_at"))
            try:
                async with self.dst.transaction():  # savepoint: a duplicate bottle can't abort the run
                    await self.dst.execute(
                        "INSERT INTO user_collection (id, user_id, fragrance_id, status, bottle_type, size_ml, "
                        "purchase_price, currency, rating, remaining_pct, created_at, updated_at) "
                        "VALUES ($1,$2,$3,$4,'full',$5,$6,'USD',$7,$8,$9,$9)",
                        row["id"],
                        row["user_id"],
                        fid,
                        status,
                        size,
                        float(price) if price is not None else None,
                        _half(self.g(row, "rating")),
                        remaining,
                        created,
                    )
                self.r.add("user_collection")
            except asyncpg.UniqueViolationError:
                self.r.skip("user_collection", f"id {row['id']}: same bottle already copied")

    async def reset_sequences(self) -> None:
        for table in (
            "brands",
            "notes",
            "families",
            "accords",
            "occasions",
            "retailers",
            "fragrances",
            "fragrance_prices",
            "price_logs",
            "user_collection",
        ):
            await self.dst.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
            )


async def migrate(
    source_url: str, target_url: str, force: bool = False, model_version: str = "all-MiniLM-L6-v2"
) -> Report:
    src = await asyncpg.connect(_dsn(source_url))
    dst = await asyncpg.connect(_dsn(target_url))
    try:
        if not await dst.fetchval("SELECT to_regclass('public.fragrances') IS NOT NULL"):
            raise SystemExit("Target has no schema yet — run `alembic upgrade head` against it first.")
        existing = await dst.fetchval("SELECT COUNT(*) FROM fragrances")
        if existing and not force:
            raise SystemExit(
                f"Target already has {existing} fragrances. Use --force to copy anyway (ids may clash)."
            )
        return await LegacyMigrator(src, dst, model_version).run()
    finally:
        await src.close()
        await dst.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="old database URL (postgresql://…)")
    ap.add_argument("--target", help="new database URL (default: DATABASE_URL from settings/.env)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    target = args.target
    model = "all-MiniLM-L6-v2"
    if not target:
        from app.core.config import get_settings

        s = get_settings()
        target, model = s.DATABASE_URL, s.EMBEDDING_MODEL
    report = asyncio.run(migrate(args.source, target, args.force, model))
    report.print()
    print("\nDone. Start the API and open admin → Embeddings to regenerate anything missing.")


if __name__ == "__main__":
    main()
