"""Admin dashboard stats/work queues and catalog import/export."""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import normalize
from app.core.errors import Invalid
from app.models import Brand, Fragrance, User
from app.repositories.catalog import _missing_clause

logger = logging.getLogger(__name__)

QUEUES: list[tuple[str, str]] = [
    ("embedding", "Missing embedding"),
    ("stale_embedding", "Embedding out of date"),
    ("notes", "No notes"),
    ("families", "No family"),
    ("image", "No image"),
    ("prices", "No reference price"),
    ("stale_prices", "No price logged in 30 days"),
]

EXPORT_QUERIES: dict[str, str] = {
    "brands": "SELECT id, name, country, website_url, logo_url, description, created_at FROM brands ORDER BY id",
    "notes": "SELECT id, name, category, description FROM notes ORDER BY id",
    "families": "SELECT id, name, axis, description FROM families ORDER BY id",
    "accords": "SELECT id, name FROM accords ORDER BY id",
    "occasions": "SELECT id, name FROM occasions ORDER BY id",
    "retailers": "SELECT id, name, website_url, country, created_at FROM retailers ORDER BY id",
    "fragrances": """
        SELECT f.id, f.name, b.name AS brand_name, f.concentration, f.gender, f.sillage, f.release_year,
               f.longevity_hours, f.season_spring, f.season_summer, f.season_fall, f.season_winter,
               f.image_url, f.discontinued, f.description, f.created_at, f.updated_at
        FROM fragrances f JOIN brands b ON b.id = f.brand_id ORDER BY f.id""",
    "fragrance_notes": """
        SELECT f.id AS fragrance_id, f.name AS fragrance_name, n.name AS note_name, fn.position, fn.prominence
        FROM fragrance_notes fn JOIN fragrances f ON f.id = fn.fragrance_id JOIN notes n ON n.id = fn.note_id
        ORDER BY f.id, fn.position""",
    "fragrance_families": """
        SELECT f.id AS fragrance_id, f.name AS fragrance_name, fam.name AS family_name
        FROM fragrance_families ff JOIN fragrances f ON f.id = ff.fragrance_id
        JOIN families fam ON fam.id = ff.family_id ORDER BY f.id""",
    "fragrance_accords": """
        SELECT f.id AS fragrance_id, f.name AS fragrance_name, a.name AS accord_name
        FROM fragrance_accords fa JOIN fragrances f ON f.id = fa.fragrance_id JOIN accords a ON a.id = fa.accord_id
        ORDER BY f.id""",
    "fragrance_occasions": """
        SELECT f.id AS fragrance_id, f.name AS fragrance_name, o.name AS occasion_name
        FROM fragrance_occasions fo JOIN fragrances f ON f.id = fo.fragrance_id
        JOIN occasions o ON o.id = fo.occasion_id ORDER BY f.id""",
    "fragrance_prices": """
        SELECT f.id AS fragrance_id, f.name AS fragrance_name, fp.size_ml, fp.price_usd
        FROM fragrance_prices fp JOIN fragrances f ON f.id = fp.fragrance_id ORDER BY f.id, fp.size_ml""",
    "price_logs": """
        SELECT pl.id, f.name AS fragrance_name, b.name AS brand_name, r.name AS retailer_name, pl.size_ml,
               pl.price_usd, pl.is_sale, pl.product_url, pl.logged_at
        FROM price_logs pl JOIN fragrances f ON f.id = pl.fragrance_id JOIN brands b ON b.id = f.brand_id
        JOIN retailers r ON r.id = pl.retailer_id ORDER BY pl.logged_at DESC""",
}

# Columns for the catalog CSV used by import (also what `catalog` export produces).
IMPORT_COLUMNS = [
    "name",
    "brand_name",
    "concentration",
    "gender",
    "sillage",
    "release_year",
    "longevity_hours",
    "top_notes",
    "heart_notes",
    "base_notes",
    "families",
    "accords",
    "occasions",
    "seasons",
    "prices",
    "image_url",
    "discontinued",
    "description",
]


def _ser(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    return "" if v is None else v


def _split(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").replace("|", ";").split(";") if x.strip()]


def _bool(v: Any) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "x")


def _int(v: Any) -> int | None:
    try:
        return int(float(v)) if str(v).strip() else None
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(v) if str(v).strip() else None
    except (TypeError, ValueError):
        return None


class _RowCheck:
    """Collects validation messages for one CSV row; status escalates ok → warning → error."""

    def __init__(self) -> None:
        self.msgs: list[str] = []
        self.status = "ok"

    def warn(self, m: str) -> None:
        self.msgs.append(m)
        if self.status == "ok":
            self.status = "warning"

    def err(self, m: str) -> None:
        self.msgs.append(m)
        self.status = "error"


class AdminService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def stats(self) -> dict[str, Any]:
        counts_row = (
            (
                await self.s.execute(
                    text("""
            SELECT (SELECT COUNT(*) FROM fragrances) AS fragrances, (SELECT COUNT(*) FROM brands) AS brands,
                   (SELECT COUNT(*) FROM notes) AS notes, (SELECT COUNT(*) FROM families) AS families,
                   (SELECT COUNT(*) FROM accords) AS accords, (SELECT COUNT(*) FROM occasions) AS occasions,
                   (SELECT COUNT(*) FROM retailers) AS retailers, (SELECT COUNT(*) FROM price_logs) AS price_logs,
                   (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM user_collection) AS collection_items,
                   (SELECT COUNT(*) FROM wear_logs) AS wears, (SELECT COUNT(*) FROM price_alerts
                    WHERE active) AS active_alerts
        """)
                )
            )
            .mappings()
            .one()
        )
        queues = []
        for key, label in QUEUES:
            clause = _missing_clause(key)  # type: ignore[arg-type]
            n = await self.s.scalar(select(func.count()).select_from(Fragrance).where(clause)) or 0
            items = []
            if n:
                rows = await self.s.execute(
                    select(Fragrance.id, Fragrance.name, Brand.name)
                    .join(Brand, Brand.id == Fragrance.brand_id)
                    .where(clause)
                    .order_by(Fragrance.updated_at.desc())
                    .limit(5)
                )
                items = [{"id": i, "name": nm, "brand_name": b, "detail": None} for i, nm, b in rows.tuples()]
            queues.append({"key": key, "label": label, "count": n, "items": items})
        qmap = {q["key"]: q["count"] for q in queues}
        week_ago = datetime.now(UTC) - timedelta(days=7)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        new_users = await self.s.scalar(select(func.count()).where(User.created_at >= week_ago)) or 0
        logs_today = await self.s.scalar(
            text("SELECT COUNT(*) FROM price_logs WHERE logged_at >= :t"), {"t": today}
        )
        return {
            "counts": dict(counts_row),
            "embeddings_missing": qmap["embedding"],
            "embeddings_stale": qmap["stale_embedding"],
            "new_users_7d": new_users,
            "price_logs_today": logs_today or 0,
            "queues": queues,
        }

    # ── Export ───────────────────────────────────────────────────────
    async def export_zip(self, fmt: str, tables: list[str] | None) -> tuple[bytes, str]:
        if fmt not in ("csv", "json"):
            raise Invalid("format must be csv or json")
        names = tables or [*EXPORT_QUERIES, "catalog"]
        unknown = [t for t in names if t not in EXPORT_QUERIES and t != "catalog"]
        if unknown:
            raise Invalid(f"Unknown tables: {', '.join(unknown)}")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                if name == "catalog":
                    cols, rows = IMPORT_COLUMNS, await self._catalog_rows()
                else:
                    res = await self.s.execute(text(EXPORT_QUERIES[name]))
                    cols = list(res.keys())
                    rows = [[_ser(v) for v in r] for r in res.all()]
                if fmt == "csv":
                    out = io.StringIO()
                    w = csv.writer(out)
                    w.writerow(cols)
                    w.writerows(rows)
                    zf.writestr(f"{name}.csv", out.getvalue())
                else:
                    zf.writestr(
                        f"{name}.json",
                        json.dumps([dict(zip(cols, r, strict=True)) for r in rows], indent=2, default=str),
                    )
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return buf.getvalue(), f"scentvault_export_{stamp}.zip"

    async def _catalog_rows(self) -> list[list[Any]]:
        """One row per fragrance in the import format — a round-trippable catalog backup."""
        res = await self.s.execute(
            text("""
            SELECT f.name, b.name, f.concentration, f.gender, f.sillage, f.release_year, f.longevity_hours,
              (SELECT string_agg(n.name, ';' ORDER BY fn.prominence DESC, n.name) FROM fragrance_notes fn
                 JOIN notes n ON n.id = fn.note_id WHERE fn.fragrance_id = f.id AND fn.position = 'top'),
              (SELECT string_agg(n.name, ';' ORDER BY fn.prominence DESC, n.name) FROM fragrance_notes fn
                 JOIN notes n ON n.id = fn.note_id WHERE fn.fragrance_id = f.id AND fn.position = 'heart'),
              (SELECT string_agg(n.name, ';' ORDER BY fn.prominence DESC, n.name) FROM fragrance_notes fn
                 JOIN notes n ON n.id = fn.note_id WHERE fn.fragrance_id = f.id AND fn.position = 'base'),
              (SELECT string_agg(x.name, ';' ORDER BY x.name) FROM fragrance_families j
                 JOIN families x ON x.id = j.family_id WHERE j.fragrance_id = f.id),
              (SELECT string_agg(x.name, ';' ORDER BY x.name) FROM fragrance_accords j
                 JOIN accords x ON x.id = j.accord_id WHERE j.fragrance_id = f.id),
              (SELECT string_agg(x.name, ';' ORDER BY x.name) FROM fragrance_occasions j
                 JOIN occasions x ON x.id = j.occasion_id WHERE j.fragrance_id = f.id),
              concat_ws(';', CASE WHEN f.season_spring THEN 'Spring' END, CASE WHEN f.season_summer THEN 'Summer' END,
                        CASE WHEN f.season_fall THEN 'Fall' END, CASE WHEN f.season_winter THEN 'Winter' END),
              (SELECT string_agg(fp.size_ml || ':' || fp.price_usd, ';' ORDER BY fp.size_ml) FROM fragrance_prices fp
                 WHERE fp.fragrance_id = f.id),
              f.image_url, f.discontinued, f.description
            FROM fragrances f JOIN brands b ON b.id = f.brand_id ORDER BY b.name, f.name
        """)
        )
        return [[_ser(v) for v in r] for r in res.all()]

    # ── Import ───────────────────────────────────────────────────────
    async def _lookup(self, table: str) -> dict[str, int]:
        rows = await self.s.execute(text(f"SELECT lower(name), id FROM {table}"))  # table is a constant
        return dict(rows.tuples().all())

    async def import_preview(self, raw: bytes) -> dict[str, Any]:
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or not {"name", "brand_name"} <= {
            h.strip().lower() for h in reader.fieldnames
        }:
            raise Invalid(
                f"CSV needs at least 'name' and 'brand_name' columns. Supported: {', '.join(IMPORT_COLUMNS)}"
            )
        brands = await self._lookup("brands")
        notes = await self._lookup("notes")
        families = await self._lookup("families")
        accords = await self._lookup("accords")
        occasions = await self._lookup("occasions")
        existing = {
            (b.lower(), n.lower(), c)
            for n, b, c in (
                await self.s.execute(select(Fragrance.name, Brand.name, Fragrance.concentration).join(Brand))
            ).tuples()
        }
        seen_in_file: set[tuple[str, str, str]] = set()
        rows_out, valid = [], []
        for i, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
            chk = _RowCheck()
            warn, err = chk.warn, chk.err
            name, brand = row.get("name", ""), row.get("brand_name", "")
            if not name:
                err("Missing name")
            if not brand:
                err("Missing brand_name")
            conc = normalize.concentration(row.get("concentration"))
            if conc is None:
                conc = "EDP"
                warn(f"Concentration '{row.get('concentration', '')}' not recognised — using EDP")
            gen = normalize.gender(row.get("gender"))
            if gen is None:
                gen = "Unisex"
                if row.get("gender"):
                    warn(f"Gender '{row['gender']}' not recognised — using Unisex")
            sil = normalize.sillage(row.get("sillage"), default="Moderate")
            key = (brand.lower(), name.lower(), conc)
            if key in existing:
                err(f"{brand} {name} ({conc}) already exists")
            elif key in seen_in_file:
                err("Duplicate of an earlier row in this file")
            seen_in_file.add(key)
            if brand and brand.lower() not in brands:
                warn(f"New brand '{brand}' will be created")
            note_map: dict[str, list[str]] = {}
            for pos in ("top", "heart", "base"):
                names = _split(row.get(f"{pos}_notes"))
                new = [n for n in names if n.lower() not in notes]
                if new:
                    warn(f"New notes: {', '.join(new)}")
                note_map[pos] = names
            fam, acc, occ = (
                _split(row.get("families")),
                _split(row.get("accords")),
                _split(row.get("occasions")),
            )
            for label, vals, lk in (
                ("families", fam, families),
                ("accords", acc, accords),
                ("occasions", occ, occasions),
            ):
                new = [v for v in vals if v.lower() not in lk]
                if new:
                    warn(f"New {label}: {', '.join(new)}")
            seasons = {s.capitalize() for s in _split(row.get("seasons"))}
            seasons |= {"Fall"} if "Autumn" in seasons else set()
            prices = []
            for p in _split(row.get("prices")):
                try:
                    sz, pr = p.split(":")
                    prices.append([int(float(sz)), float(pr)])
                except ValueError:
                    warn(f"Couldn't read price '{p}' (use size:price, e.g. 100:150)")
            data = {
                "name": name,
                "brand_name": brand,
                "concentration": conc,
                "gender": gen,
                "sillage": sil,
                "release_year": _int(row.get("release_year")),
                "longevity_hours": _float(row.get("longevity_hours")),
                "notes": note_map,
                "families": fam,
                "accords": acc,
                "occasions": occ,
                "season_spring": "Spring" in seasons or _bool(row.get("season_spring")),
                "season_summer": "Summer" in seasons or _bool(row.get("season_summer")),
                "season_fall": "Fall" in seasons or _bool(row.get("season_fall")),
                "season_winter": "Winter" in seasons or _bool(row.get("season_winter")),
                "prices": prices,
                "image_url": row.get("image_url") or None,
                "discontinued": _bool(row.get("discontinued")),
                "description": row.get("description") or None,
            }
            rows_out.append({"row_number": i, "data": data, "status": chk.status, "messages": chk.msgs})
            if chk.status != "error":
                valid.append(data)
        return {
            "total_rows": len(rows_out),
            "valid_rows": sum(r["status"] == "ok" for r in rows_out),
            "warning_rows": sum(r["status"] == "warning" for r in rows_out),
            "error_rows": sum(r["status"] == "error" for r in rows_out),
            "rows": rows_out,
            "session_data": json.dumps(valid),
        }

    async def _find_or_create(
        self, table: str, name: str, cache: dict[str, int], extra: dict[str, Any] | None = None
    ) -> int:
        key = name.lower()
        if key in cache:
            return cache[key]
        cols = {"name": name, **(extra or {})}
        names = ", ".join(cols)
        vals = ", ".join(f":{c}" for c in cols)
        new_id = await self.s.scalar(
            text(f"INSERT INTO {table} ({names}) VALUES ({vals}) RETURNING id"), cols
        )
        cache[key] = int(new_id)  # type: ignore[arg-type]
        return cache[key]

    async def import_confirm(self, session_data: str, skip_errors: bool) -> tuple[dict[str, Any], list[int]]:
        try:
            items = json.loads(session_data)
            assert isinstance(items, list)
        except (json.JSONDecodeError, AssertionError) as exc:
            raise Invalid("Invalid session data — run the preview again") from exc
        caches = {t: await self._lookup(t) for t in ("brands", "notes", "families", "accords", "occasions")}
        inserted = skipped = 0
        errors: list[str] = []
        new_ids: list[int] = []
        for item in items:
            label = f"{item.get('brand_name', '?')} {item.get('name', '?')}"
            try:
                async with self.s.begin_nested():  # one savepoint per row: a bad row can't poison the rest
                    brand_id = await self._find_or_create("brands", item["brand_name"], caches["brands"])
                    fid = await self.s.scalar(
                        text("""
                        INSERT INTO fragrances (name, brand_id, concentration, gender, sillage, release_year,
                            longevity_hours, season_spring, season_summer, season_fall, season_winter,
                            image_url, discontinued, description)
                        VALUES (:name, :brand_id, :concentration, :gender, :sillage, :release_year, :longevity_hours,
                            :season_spring, :season_summer, :season_fall, :season_winter, :image_url,
                            :discontinued, :description)
                        ON CONFLICT ON CONSTRAINT uq_fragrances_brand_name_conc DO NOTHING
                        RETURNING id"""),
                        {
                            k: item.get(k)
                            for k in (
                                "name",
                                "concentration",
                                "gender",
                                "release_year",
                                "longevity_hours",
                                "image_url",
                                "description",
                            )
                        }
                        | {
                            k: bool(item.get(k))
                            for k in (
                                "season_spring",
                                "season_summer",
                                "season_fall",
                                "season_winter",
                                "discontinued",
                            )
                        }
                        | {"sillage": item.get("sillage") or "Moderate", "brand_id": brand_id},
                    )
                    if fid is None:
                        skipped += 1
                        continue
                    for pos, names in (item.get("notes") or {}).items():
                        for rank, n in enumerate(names):
                            nid = await self._find_or_create(
                                "notes", n, caches["notes"], {"category": "Other"}
                            )
                            await self.s.execute(
                                text(
                                    "INSERT INTO fragrance_notes (fragrance_id, note_id, position, prominence) "
                                    "VALUES (:f, :n, :p, :pr) ON CONFLICT DO NOTHING"
                                ),
                                {"f": fid, "n": nid, "p": pos, "pr": max(1, 5 - rank)},
                            )
                    for table, join, col, names in (
                        ("families", "fragrance_families", "family_id", item.get("families") or []),
                        ("accords", "fragrance_accords", "accord_id", item.get("accords") or []),
                        ("occasions", "fragrance_occasions", "occasion_id", item.get("occasions") or []),
                    ):
                        for n in names:
                            extra = {"axis": normalize.axis_for_family(n)} if table == "families" else None
                            xid = await self._find_or_create(table, n, caches[table], extra)
                            await self.s.execute(
                                text(
                                    f"INSERT INTO {join} (fragrance_id, {col}) VALUES (:f, :x) ON CONFLICT DO NOTHING"
                                ),
                                {"f": fid, "x": xid},
                            )
                    for size, price in item.get("prices") or []:
                        await self.s.execute(
                            text(
                                "INSERT INTO fragrance_prices (fragrance_id, size_ml, price_usd) VALUES (:f, :s, :p) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {"f": fid, "s": size, "p": price},
                        )
                new_ids.append(int(fid))
                inserted += 1
            except Exception as exc:  # row-level failure; savepoint already rolled back
                for c in caches.values():  # created-then-rolled-back ids may be in the caches
                    c.clear()
                caches = {t: await self._lookup(t) for t in caches}
                errors.append(f"{label}: {str(exc).splitlines()[0][:200]}")
                if not skip_errors:
                    await self.s.rollback()
                    raise Invalid(f"Import stopped at {label}: {errors[-1]}") from exc
        await self.s.commit()
        return {
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "embeddings_queued": len(new_ids),
        }, new_ids
