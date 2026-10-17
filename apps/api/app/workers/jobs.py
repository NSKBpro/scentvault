"""Background jobs. The same functions run in the arq worker or inline (InlineQueue).

Every job gets ``ctx["resources"]`` and opens its own DB session.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.session import get_sessionmaker
from app.models import CollectionItem
from app.repositories.catalog import CatalogRepository
from app.resources import Resources
from app.services.alerts import AlertService
from app.services.embedding.service import EmbeddingService
from app.services.notifications import NotificationService

logger = logging.getLogger(__name__)


def _res(ctx: dict[str, Any]) -> Resources:
    return ctx["resources"]


async def embed_fragrances(ctx: dict[str, Any], ids: list[int]) -> dict[str, int]:
    async with get_sessionmaker()() as s:
        return await EmbeddingService(s, _res(ctx).embedder).generate_many(ids)


async def regenerate_embeddings(ctx: dict[str, Any], only_missing: bool = False) -> dict[str, int]:
    async with get_sessionmaker()() as s:
        ids = await CatalogRepository(s).fragrance_ids_needing_embedding(only_missing)
        logger.info("Regenerating %d embeddings (only_missing=%s)", len(ids), only_missing)
        return await EmbeddingService(s, _res(ctx).embedder).generate_many(ids)


async def check_price_alerts(ctx: dict[str, Any], fragrance_id: int | None = None) -> int:
    async with get_sessionmaker()() as s:
        return await AlertService(s, _res(ctx).push).check(fragrance_id=fragrance_id)


async def running_low(ctx: dict[str, Any], collection_item_id: int) -> None:
    async with get_sessionmaker()() as s:
        item = await s.get(CollectionItem, collection_item_id)
        if item is not None:
            await NotificationService(s, _res(ctx).push).maybe_running_low(item)


async def daily_maintenance(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily: re-check every alert, send neglected-bottle nudges, embed anything missing."""
    async with get_sessionmaker()() as s:
        alerts = await AlertService(s, _res(ctx).push).check()
        neglected = await NotificationService(s, _res(ctx).push).neglected_nudges()
    emb = await regenerate_embeddings(ctx, only_missing=True)
    return {"alerts": alerts, "neglected": neglected, "embedded": emb["succeeded"]}


JOBS = {
    "embed_fragrances": embed_fragrances,
    "regenerate_embeddings": regenerate_embeddings,
    "check_price_alerts": check_price_alerts,
    "running_low": running_low,
    "daily_maintenance": daily_maintenance,
}
