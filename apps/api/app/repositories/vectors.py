"""pgvector queries — the only place with raw SQL for vector operators.

Similarity % = (1 − cosine distance) × 100.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_MATCH_COLUMNS = """
    f.id AS fragrance_id, f.name, b.name AS brand_name, f.concentration, f.gender, f.image_url,
    ROUND(((1 - (e.embedding <=> CAST(:vec AS vector))) * 100)::numeric, 1)::float AS similarity_pct,
    (SELECT MIN(fp.price_usd)::float FROM fragrance_prices fp WHERE fp.fragrance_id = f.id) AS min_price_usd,
    COALESCE((SELECT array_agg(fam.name ORDER BY fam.name) FROM fragrance_families ff
              JOIN families fam ON fam.id = ff.family_id WHERE ff.fragrance_id = f.id), '{}') AS families
"""


@dataclass
class VectorFilters:
    exclude_ids: list[int] = field(default_factory=list)
    exclude_user_collection: str | None = None  # user id
    genders: list[str] | None = None
    include_discontinued: bool = True
    season: str | None = None
    occasion: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    exclude_notes: list[str] | None = None


class VectorRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_embedding(self, fragrance_id: int) -> str | None:
        return await self.s.scalar(
            text("SELECT embedding::text FROM fragrance_embeddings WHERE fragrance_id = :fid"),
            {"fid": fragrance_id},
        )

    async def upsert(self, fragrance_id: int, vec: str, text_input: str, model_version: str) -> datetime:
        now = datetime.now(UTC)
        await self.s.execute(
            text("""
                INSERT INTO fragrance_embeddings (fragrance_id, embedding, text_input, model_version, generated_at)
                VALUES (:fid, CAST(:vec AS vector), :txt, :mv, :now)
                ON CONFLICT (fragrance_id) DO UPDATE SET embedding = EXCLUDED.embedding,
                    text_input = EXCLUDED.text_input, model_version = EXCLUDED.model_version,
                    generated_at = EXCLUDED.generated_at
            """),
            {"fid": fragrance_id, "vec": vec, "txt": text_input, "mv": model_version, "now": now},
        )
        return now

    async def nearest(self, vec: str, limit: int, flt: VectorFilters | None = None) -> list[dict[str, Any]]:
        flt = flt or VectorFilters()
        where = ["TRUE"]
        params: dict[str, Any] = {"vec": vec, "lim": limit}
        if flt.exclude_ids:
            where.append("f.id <> ALL(:exclude_ids)")
            params["exclude_ids"] = flt.exclude_ids
        if flt.exclude_user_collection:
            where.append(
                "NOT EXISTS (SELECT 1 FROM user_collection uc WHERE uc.user_id = CAST(:uid AS uuid) "
                "AND uc.fragrance_id = f.id)"
            )
            params["uid"] = flt.exclude_user_collection
        if flt.genders:
            where.append("f.gender = ANY(:genders)")
            params["genders"] = flt.genders
        if not flt.include_discontinued:
            where.append("f.discontinued = false")
        if flt.season in ("Spring", "Summer", "Fall", "Winter"):
            where.append(f"f.season_{flt.season.lower()} = true")  # whitelisted above
        if flt.occasion:
            where.append(
                "EXISTS (SELECT 1 FROM fragrance_occasions fo JOIN occasions o ON o.id = fo.occasion_id "
                "WHERE fo.fragrance_id = f.id AND lower(o.name) = lower(:occasion))"
            )
            params["occasion"] = flt.occasion
        if flt.budget_max is not None:
            where.append(
                "EXISTS (SELECT 1 FROM fragrance_prices fp WHERE fp.fragrance_id = f.id "
                "AND fp.price_usd <= :bmax)"
            )
            params["bmax"] = flt.budget_max
        if flt.budget_min is not None:
            where.append(
                "EXISTS (SELECT 1 FROM fragrance_prices fp WHERE fp.fragrance_id = f.id "
                "AND fp.price_usd >= :bmin)"
            )
            params["bmin"] = flt.budget_min
        if flt.exclude_notes:
            where.append(
                "NOT EXISTS (SELECT 1 FROM fragrance_notes fn JOIN notes n ON n.id = fn.note_id "
                "WHERE fn.fragrance_id = f.id AND lower(n.name) = ANY(:xnotes))"
            )
            params["xnotes"] = [n.lower() for n in flt.exclude_notes]
        sql = f"""
            SELECT {_MATCH_COLUMNS}
            FROM fragrance_embeddings e
            JOIN fragrances f ON f.id = e.fragrance_id
            JOIN brands b ON b.id = f.brand_id
            WHERE {" AND ".join(where)}
            ORDER BY e.embedding <=> CAST(:vec AS vector)
            LIMIT :lim
        """
        rows = await self.s.execute(text(sql), params)
        return [dict(r) for r in rows.mappings()]

    async def min_price_per_ml(self, fragrance_id: int) -> float | None:
        v = await self.s.scalar(
            text("SELECT MIN(price_usd / size_ml)::float FROM fragrance_prices WHERE fragrance_id = :fid"),
            {"fid": fragrance_id},
        )
        return float(v) if v is not None else None

    async def dupes(
        self,
        fragrance_id: int,
        vec: str,
        original_ppm: float,
        *,
        limit: int,
        min_similarity: float,
        max_price_ratio: float,
    ) -> list[dict[str, Any]]:
        """Similar fragrances whose cheapest price per ml is below ratio × the original's."""
        rows = await self.s.execute(
            text(f"""
                WITH cheapest AS (
                    SELECT DISTINCT ON (fragrance_id) fragrance_id, size_ml, price_usd::float AS price_usd,
                           (price_usd / size_ml)::float AS ppm
                    FROM fragrance_prices
                    ORDER BY fragrance_id, price_usd / size_ml, size_ml DESC
                )
                SELECT {_MATCH_COLUMNS}, c.size_ml, c.price_usd, ROUND(c.ppm::numeric, 4)::float AS price_per_ml_usd
                FROM fragrance_embeddings e
                JOIN fragrances f ON f.id = e.fragrance_id
                JOIN brands b ON b.id = f.brand_id
                JOIN cheapest c ON c.fragrance_id = f.id
                WHERE f.id <> :fid
                  AND (1 - (e.embedding <=> CAST(:vec AS vector))) >= :min_sim
                  AND c.ppm < :max_ppm
                ORDER BY e.embedding <=> CAST(:vec AS vector)
                LIMIT :lim
            """),
            {
                "fid": fragrance_id,
                "vec": vec,
                "min_sim": min_similarity,
                "max_ppm": original_ppm * max_price_ratio,
                "lim": limit,
            },
        )
        out = []
        for r in rows.mappings():
            d = dict(r)
            d["original_price_per_ml_usd"] = round(original_ppm, 4)
            d["savings_pct"] = (
                round((1 - d["price_per_ml_usd"] / original_ppm) * 100, 0) if original_ppm else 0.0
            )
            out.append(d)
        return out

    async def preference_rows(self, user_id: str) -> list[tuple[str, float]]:
        """(embedding, weight) for liked bottles: rating ≥ 4 weighs (rating − 3); favourites +0.5."""
        rows = await self.s.execute(
            text("""
                SELECT e.embedding::text AS emb,
                       MAX(GREATEST(COALESCE(uc.rating, 0) - 3, 0) + CASE WHEN uc.is_favorite THEN 0.5 ELSE 0 END)
                         AS w
                FROM user_collection uc
                JOIN fragrance_embeddings e ON e.fragrance_id = uc.fragrance_id
                WHERE uc.user_id = CAST(:uid AS uuid)
                  AND uc.status IN ('own', 'tried', 'finished')
                  AND (uc.rating >= 4 OR uc.is_favorite)
                GROUP BY e.fragrance_id, e.embedding
            """),
            {"uid": user_id},
        )
        return [(r.emb, float(r.w)) for r in rows if r.w and r.w > 0]

    async def status(self, current_model: str) -> dict[str, Any]:
        r = (
            (
                await self.s.execute(
                    text("""
                SELECT (SELECT COUNT(*) FROM fragrances) AS total,
                       COUNT(e.fragrance_id) AS with_embedding,
                       COUNT(*) FILTER (WHERE e.generated_at < f.updated_at) AS stale,
                       COUNT(*) FILTER (WHERE e.model_version <> :mv) AS other_model,
                       MAX(e.generated_at) AS last_generated_at
                FROM fragrance_embeddings e JOIN fragrances f ON f.id = e.fragrance_id
            """),
                    {"mv": current_model},
                )
            )
            .mappings()
            .one()
        )
        return dict(r)
