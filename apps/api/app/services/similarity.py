"""Similar fragrances, dupes (price per ml), personal recommendations."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFound
from app.repositories.catalog import CatalogRepository
from app.repositories.vectors import VectorFilters, VectorRepository
from app.services.embedding.provider import EmbeddingProvider, to_pgvector


def parse_vector(raw: str) -> np.ndarray:
    return np.array([float(x) for x in raw.strip("[]").split(",")], dtype=np.float32)


def genders_for(pref: str | None) -> list[str] | None:
    """A gender preference keeps that gender plus unisex; 'Any' means no filter."""
    if not pref or pref == "Any":
        return None
    return [pref, "Unisex"] if pref != "Unisex" else ["Unisex", "Masculine", "Feminine"]


class SimilarityService:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None):
        self.s = session
        self.provider = provider
        self.vectors = VectorRepository(session)
        self.catalog = CatalogRepository(session)
        self.settings = get_settings()

    async def _vec_or_404(self, fragrance_id: int) -> str | None:
        vec = await self.vectors.get_embedding(fragrance_id)
        if vec is None and not await self.catalog.exists(fragrance_id):
            raise NotFound("Fragrance")
        return vec

    async def similar(self, fragrance_id: int, limit: int) -> list[dict[str, Any]]:
        vec = await self._vec_or_404(fragrance_id)
        if vec is None:
            return []
        return await self.vectors.nearest(vec, limit, VectorFilters(exclude_ids=[fragrance_id]))

    async def dupes(self, fragrance_id: int, limit: int) -> list[dict[str, Any]]:
        vec = await self._vec_or_404(fragrance_id)
        if vec is None:
            return []
        ppm = await self.vectors.min_price_per_ml(fragrance_id)
        if ppm is None:
            return []
        return await self.vectors.dupes(
            fragrance_id,
            vec,
            ppm,
            limit=limit,
            min_similarity=self.settings.DUPE_MIN_SIMILARITY,
            max_price_ratio=self.settings.DUPE_MAX_PRICE_RATIO,
        )

    async def search_text(
        self, query: str, limit: int, flt: VectorFilters | None = None
    ) -> list[dict[str, Any]]:
        assert self.provider is not None
        vec = await self.provider.encode(query)
        return await self.vectors.nearest(to_pgvector(vec), limit, flt)

    # ── Recommendations ──────────────────────────────────────────────
    async def preference_vector(self, user_id: uuid.UUID) -> str | None:
        rows = await self.vectors.preference_rows(str(user_id))
        if not rows:
            return None
        weights = np.array([w for _, w in rows], dtype=np.float32)
        mat = np.stack([parse_vector(e) for e, _ in rows])
        composite = (mat * weights[:, None]).sum(axis=0) / weights.sum()
        norm = float(np.linalg.norm(composite))
        if norm == 0:
            return None
        return to_pgvector((composite / norm).tolist())

    async def recommend(
        self, user_id: uuid.UUID, limit: int, gender_pref: str | None
    ) -> list[dict[str, Any]]:
        vec = await self.preference_vector(user_id)
        if vec is None:
            return []
        recs = await self.vectors.nearest(
            vec,
            limit,
            VectorFilters(
                exclude_user_collection=str(user_id),
                genders=genders_for(gender_pref),
                include_discontinued=False,
            ),
        )
        if recs:
            await self._explain(user_id, recs)
        return recs

    async def _explain(self, user_id: uuid.UUID, recs: list[dict[str, Any]]) -> None:
        """Shared notes / accords / families between each rec and the user's liked bottles."""
        liked = await self.s.execute(
            text("""
                SELECT 'note' AS kind, n.name FROM user_collection uc
                  JOIN fragrance_notes fn ON fn.fragrance_id = uc.fragrance_id JOIN notes n ON n.id = fn.note_id
                  WHERE uc.user_id = :uid AND (uc.rating >= 4 OR uc.is_favorite)
                UNION
                SELECT 'accord', a.name FROM user_collection uc
                  JOIN fragrance_accords fa ON fa.fragrance_id = uc.fragrance_id JOIN accords a ON a.id = fa.accord_id
                  WHERE uc.user_id = :uid AND (uc.rating >= 4 OR uc.is_favorite)
                UNION
                SELECT 'family', fam.name FROM user_collection uc
                  JOIN fragrance_families ff ON ff.fragrance_id = uc.fragrance_id
                  JOIN families fam ON fam.id = ff.family_id
                  WHERE uc.user_id = :uid AND (uc.rating >= 4 OR uc.is_favorite)
            """),
            {"uid": str(user_id)},
        )
        mine: dict[str, set[str]] = {"note": set(), "accord": set(), "family": set()}
        for kind, name in liked.tuples():
            mine[kind].add(name)
        ids = [r["fragrance_id"] for r in recs]
        theirs_rows = await self.s.execute(
            text("""
                SELECT fn.fragrance_id, 'note' AS kind, n.name FROM fragrance_notes fn
                  JOIN notes n ON n.id = fn.note_id WHERE fn.fragrance_id = ANY(:ids)
                UNION
                SELECT fa.fragrance_id, 'accord', a.name FROM fragrance_accords fa
                  JOIN accords a ON a.id = fa.accord_id WHERE fa.fragrance_id = ANY(:ids)
                UNION
                SELECT ff.fragrance_id, 'family', fam.name FROM fragrance_families ff
                  JOIN families fam ON fam.id = ff.family_id WHERE ff.fragrance_id = ANY(:ids)
            """),
            {"ids": ids},
        )
        theirs: dict[int, dict[str, set[str]]] = {}
        for fid, kind, name in theirs_rows.tuples():
            theirs.setdefault(fid, {"note": set(), "accord": set(), "family": set()})[kind].add(name)
        for r in recs:
            t = theirs.get(r["fragrance_id"], {"note": set(), "accord": set(), "family": set()})
            r["shared_notes"] = sorted(t["note"] & mine["note"])
            r["shared_accords"] = sorted(t["accord"] & mine["accord"])
            r["shared_families"] = sorted(t["family"] & mine["family"])
            bits = []
            if r["shared_notes"]:
                n = len(r["shared_notes"])
                bits.append(f"{n} note{'s' if n != 1 else ''} you love ({', '.join(r['shared_notes'][:3])})")
            if r["shared_accords"]:
                bits.append(f"{', '.join(r['shared_accords'][:2])} accord")
            if r["shared_families"] and not bits:
                bits.append(f"your taste for {', '.join(r['shared_families'][:2])}")
            r["reason"] = ("Shares " + " and ".join(bits)) if bits else "Close to your overall taste"

    async def collection_dupes(self, user_id: uuid.UUID, limit: int) -> list[dict[str, Any]]:
        """Best cheaper alternative for each owned/wishlisted fragrance that has a price."""
        rows = await self.s.execute(
            text("""
                SELECT DISTINCT ON (uc.fragrance_id) uc.fragrance_id, f.name, b.name AS brand
                FROM user_collection uc JOIN fragrances f ON f.id = uc.fragrance_id JOIN brands b ON b.id = f.brand_id
                WHERE uc.user_id = :uid AND uc.status IN ('own', 'wishlist')
                  AND EXISTS (SELECT 1 FROM fragrance_prices fp WHERE fp.fragrance_id = uc.fragrance_id)
            """),
            {"uid": str(user_id)},
        )
        out: list[dict[str, Any]] = []
        for fid, name, brand in rows.tuples():
            found = await self.dupes(fid, 1)
            if found:
                d = found[0]
                out.append(
                    {
                        "original_id": fid,
                        "original_name": name,
                        "original_brand": brand,
                        "original_price_per_ml_usd": d["original_price_per_ml_usd"],
                        "dupe": d,
                    }
                )
        out.sort(key=lambda x: (-x["dupe"]["savings_pct"], -x["dupe"]["similarity_pct"]))
        return out[:limit]
