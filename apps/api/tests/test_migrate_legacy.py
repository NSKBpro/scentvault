"""The legacy migration, run against a replica of the old schema with tricky data."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import anyio
import asyncpg
import bcrypt
import pytest
from alembic import command
from alembic.config import Config

from scripts.migrate_legacy import migrate

BASE = os.environ["TEST_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
ADMIN = BASE.rsplit("/", 1)[0] + "/postgres"
LEGACY_DB, TARGET_DB = "sv_legacy_replica", "sv_migrate_target"


def url(db: str) -> str:
    return BASE.rsplit("/", 1)[0] + f"/{db}"


async def _recreate(db: str) -> None:
    conn = await asyncpg.connect(ADMIN)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{db}"')
    finally:
        await conn.close()


def _upgrade(target: str) -> None:
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", target.replace("postgresql://", "postgresql+asyncpg://"))
    command.upgrade(cfg, "head")


@pytest.fixture
async def legacy() -> str:
    await _recreate(LEGACY_DB)
    conn = await asyncpg.connect(url(LEGACY_DB))
    try:
        await conn.execute((Path(__file__).parent / "fixtures" / "legacy_schema.sql").read_text())
        await conn.execute("""
            INSERT INTO brands (id, name, country) VALUES (1, 'Dior', 'France'), (2, 'Armaf', 'UAE'), (3, 'Empty House', NULL);
            INSERT INTO notes (id, name, category) VALUES (1, 'Bergamot', 'Citrus'), (2, 'Ambroxan', NULL), (3, 'Birch', 'Smoky');
            INSERT INTO families (id, name) VALUES (1, 'Fougère'), (2, 'Leather'), (3, 'Weird Stuff');
            INSERT INTO accords (id, name) VALUES (1, 'Fresh Spicy'), (2, 'Smoky');
            INSERT INTO occasions (id, name) VALUES (1, 'Office');
            INSERT INTO retailers (id, name) VALUES (1, 'Notino');
            INSERT INTO fragrances (id, brand_id, name, concentration, gender, sillage, longevity_hours, season_summer,
                                    occasion_tags, discontinued)
              VALUES (10, 1, 'Sauvage', 'EDT', 'Masculine', 'strong', 8.5, true, NULL, false),
                     (11, 2, 'Club de Nuit Intense', 'eau de toilette', 'men', NULL, NULL, NULL, ARRAY['Evening','Office'], NULL),
                     (12, 1, 'Sauvage', 'edt', 'Male', NULL, NULL, NULL, NULL, NULL),
                     (13, 1, 'Mystery', 'Hair Perfume Thing', 'women', NULL, NULL, NULL, NULL, NULL);
            INSERT INTO fragrance_notes VALUES (10, 1, 'top', 50), (10, 2, 'BASE', 5), (11, 3, 'middle', 90), (10, 99, 'top', 3);
            INSERT INTO fragrance_families VALUES (10, 1), (11, 2), (11, 3);
            INSERT INTO fragrance_accords VALUES (10, 1), (11, 2), (12, 1);
            INSERT INTO fragrance_occasions VALUES (10, 1);
            INSERT INTO fragrance_prices (fragrance_id, size_ml, price_usd) VALUES (10, 100, 125), (10, 100, 130), (11, 105, 35);
            INSERT INTO price_logs (fragrance_id, retailer_id, size_ml, price_usd, is_sale) VALUES (10, 1, 100, 99, true);
            INSERT INTO price_entries (fragrance_id, retailer_id, price_usd, spotted_at) VALUES (11, 1, 33, now());
        """)
        vec = "[" + ",".join(["0.05"] * 384) + "]"
        await conn.execute(
            "INSERT INTO fragrance_embeddings (fragrance_id, embedding, text_input, model_version) "
            "VALUES (10, $1::vector, 'Fougère fragrance.', 'all-MiniLM-L6-v2'), (11, $1::vector, 'x', 'old-model')",
            vec,
        )
        uid_admin, uid_user = uuid.uuid4(), uuid.uuid4()
        h = bcrypt.hashpw(b"oldpassword1", bcrypt.gensalt()).decode()  # same format passlib produced
        await conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, role) VALUES ($1, 'Mihajlo@Example.com', $3, 'M', 'admin'),"
            " ($2, 'friend@example.com', $3, NULL, NULL)",
            uid_admin,
            uid_user,
            h,
        )
        await conn.execute(
            "INSERT INTO user_collection (user_id, fragrance_id, size_ml, purchase_price, rating, remaining_pct, status)"
            " VALUES ($1, 10, 100, 120, 4.3, 80, 'own'), ($1, 11, NULL, NULL, 0, NULL, 'wishlist'),"
            " ($2, 12, 100, 90, 5, 150, 'weird'), ($2, 10, 100, 95, NULL, 50, 'own')",
            uid_admin,
            uid_user,
        )
    finally:
        await conn.close()
    return url(LEGACY_DB)


async def test_migrate_legacy_replica(legacy, client):
    await _recreate(TARGET_DB)
    await anyio.to_thread.run_sync(_upgrade, url(TARGET_DB))
    report = await migrate(legacy, url(TARGET_DB))

    dst = await asyncpg.connect(url(TARGET_DB))
    try:
        frags = {r["id"]: r for r in await dst.fetch("SELECT * FROM fragrances")}
        assert set(frags) == {10, 11, 13}  # 12 was a duplicate of 10 and got merged
        assert frags[11]["concentration"] == "EDT" and frags[11]["gender"] == "Masculine"
        assert frags[10]["sillage"] == "Strong" and frags[13]["concentration"] == "EDP"
        assert frags[13]["gender"] == "Feminine"
        axes = dict(await dst.fetch("SELECT name, axis FROM families"))
        assert axes == {"Fougère": "aromatic", "Leather": "woody", "Weird Stuff": None}
        notes = {
            (r["fragrance_id"], r["note_id"]): r for r in await dst.fetch("SELECT * FROM fragrance_notes")
        }
        assert notes[(10, 1)]["prominence"] == 3 and notes[(10, 2)]["position"] == "base"
        assert notes[(11, 3)]["position"] == "heart" and notes[(11, 3)]["prominence"] == 5
        assert (10, 99) not in notes
        assert (
            await dst.fetchval("SELECT COUNT(*) FROM fragrance_accords WHERE fragrance_id = 10") == 1
        )  # 12→10 deduped
        occ = {
            r["name"]
            for r in await dst.fetch(
                "SELECT o.name FROM fragrance_occasions fo JOIN occasions o ON o.id = fo.occasion_id WHERE fo.fragrance_id = 11"
            )
        }
        assert occ == {"Evening", "Office"}  # from the legacy occasion_tags array
        assert await dst.fetchval("SELECT price_usd FROM fragrance_prices WHERE fragrance_id = 10") == 125
        logs = await dst.fetch("SELECT * FROM price_logs ORDER BY fragrance_id")
        assert [(r["fragrance_id"], r["size_ml"]) for r in logs] == [
            (10, 100),
            (11, 105),
        ]  # price_entry got its only size
        emb = await dst.fetch("SELECT fragrance_id FROM fragrance_embeddings")
        assert [r["fragrance_id"] for r in emb] == [10]  # other-model vector dropped (will regenerate)
        stale = await dst.fetchval(
            "SELECT COUNT(*) FROM fragrance_embeddings e JOIN fragrances f ON f.id = e.fragrance_id WHERE e.generated_at < f.updated_at"
        )
        assert stale == 0
        users = {r["email"]: r for r in await dst.fetch("SELECT * FROM users")}
        assert (
            users["mihajlo@example.com"]["role"] == "admin" and users["friend@example.com"]["role"] == "user"
        )
        assert await dst.fetchval("SELECT COUNT(*) FROM user_preferences") == 2
        bottles = await dst.fetch("SELECT * FROM user_collection ORDER BY id")
        assert (
            len(bottles) == 3
        )  # friend's 'Sauvage edt' (12) merged into 10 and clashed with their other 100 ml
        first = bottles[0]
        assert first["rating"] == 4.5 and first["currency"] == "USD" and first["bottle_type"] == "full"
        wish = bottles[1]
        assert wish["rating"] is None and wish["remaining_pct"] == 100
        assert (
            bottles[2]["status"] == "own" and bottles[2]["remaining_pct"] == 100
        )  # 150 clamped, 'weird' → own
        # Sequences continue after the copied ids.
        new_id = await dst.fetchval("INSERT INTO brands (name) VALUES ('After Migration') RETURNING id")
        assert new_id == 4
        assert bcrypt.checkpw(b"oldpassword1", users["friend@example.com"]["password_hash"].encode())
    finally:
        await dst.close()
    assert report.copied["fragrances"] == 3
    with pytest.raises(SystemExit):
        await migrate(legacy, url(TARGET_DB))  # refuses a non-empty target
