"""Generate, store and report fragrance embeddings."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models import Accord, Family, Note, Occasion
from app.repositories.catalog import CatalogRepository
from app.repositories.vectors import VectorRepository
from app.schemas.catalog import FragranceIn, FragrancePreviewIn
from app.services.embedding.provider import EmbeddingProvider, to_pgvector
from app.services.embedding.text import EmbeddingSource, build_embedding_text, source_from_fragrance

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider):
        self.s = session
        self.provider = provider
        self.catalog = CatalogRepository(session)
        self.vectors = VectorRepository(session)

    async def generate(self, fragrance_id: int, *, commit: bool = True) -> dict[str, Any]:
        f = await self.catalog.get_fragrance(fragrance_id)
        if f is None:
            raise NotFound("Fragrance")
        text_input = build_embedding_text(source_from_fragrance(f))
        vec = await self.provider.encode(text_input)
        generated_at = await self.vectors.upsert(
            fragrance_id, to_pgvector(vec), text_input, self.provider.model_version
        )
        if commit:
            await self.s.commit()
        return {
            "fragrance_id": fragrance_id,
            "text_input": text_input,
            "model_version": self.provider.model_version,
            "generated_at": generated_at.isoformat(),
        }

    async def generate_many(self, ids: list[int], batch_size: int = 32) -> dict[str, int]:
        ok = failed = 0
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            texts: list[tuple[int, str]] = []
            for fid in batch:
                f = await self.catalog.get_fragrance(fid)
                if f is None:
                    failed += 1
                    continue
                texts.append((fid, build_embedding_text(source_from_fragrance(f))))
            if not texts:
                continue
            try:
                vecs = await self.provider.encode_many([t for _, t in texts])
                for (fid, t), v in zip(texts, vecs, strict=True):
                    await self.vectors.upsert(fid, to_pgvector(v), t, self.provider.model_version)
                await self.s.commit()
                ok += len(texts)
            except Exception:
                await self.s.rollback()
                failed += len(texts)
                logger.exception("Embedding batch failed (%s…)", texts[0][0])
            self.s.expunge_all()
        logger.info("Embedded %d fragrances (%d failed)", ok, failed)
        return {"succeeded": ok, "failed": failed}

    async def preview(self, data: FragranceIn | FragrancePreviewIn) -> str:
        async def names(model: Any, ids: list[int]) -> dict[int, str]:
            if not ids:
                return {}
            rows = await self.s.execute(select(model.id, model.name).where(model.id.in_(ids)))
            return dict(rows.tuples().all())

        note_names = await names(Note, [n.note_id for n in data.notes])
        src = EmbeddingSource(
            families=list((await names(Family, data.family_ids)).values()),
            accords=list((await names(Accord, data.accord_ids)).values()),
            occasions=list((await names(Occasion, data.occasion_ids)).values()),
            sillage=data.sillage,
            longevity_hours=data.longevity_hours,
            seasons=[
                s
                for s, on in (
                    ("Spring", data.season_spring),
                    ("Summer", data.season_summer),
                    ("Fall", data.season_fall),
                    ("Winter", data.season_winter),
                )
                if on
            ],
        )
        for n in data.notes:
            if n.note_id in note_names:
                getattr(src, n.position).append(note_names[n.note_id])
        return build_embedding_text(src)

    async def status(self, queue_name: str) -> dict[str, Any]:
        r = await self.vectors.status(self.provider.model_version)
        total = int(r["total"] or 0)
        with_emb = int(r["with_embedding"] or 0)
        last = r["last_generated_at"]
        return {
            "total_fragrances": total,
            "with_embedding": with_emb,
            "missing": total - with_emb,
            "stale": int(r["stale"] or 0),
            "other_model": int(r["other_model"] or 0),
            "coverage_pct": round(with_emb / total * 100, 1) if total else 100.0,
            "provider": self.provider.name,
            "model_version": self.provider.model_version,
            "last_generated_at": last.isoformat() if last else None,
            "job_queue": queue_name,
        }
