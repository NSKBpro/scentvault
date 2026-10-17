"""Public per-fragrance endpoints: similar, dupes, price history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.ai import DupeItem, FragranceMatch
from app.schemas.prices import PriceHistoryOut
from app.services.prices import PriceService
from app.services.similarity import SimilarityService

router = APIRouter(prefix="/fragrances", tags=["fragrances"])


@router.get("/{fragrance_id}/similar", response_model=list[FragranceMatch])
async def similar(fragrance_id: int, session: SessionDep, limit: int = Query(10, ge=1, le=50)) -> Any:
    return await SimilarityService(session).similar(fragrance_id, limit)


@router.get("/{fragrance_id}/dupes", response_model=list[DupeItem])
async def dupes(fragrance_id: int, session: SessionDep, limit: int = Query(10, ge=1, le=50)) -> Any:
    """Cheaper alternatives: ≥ DUPE_MIN_SIMILARITY similar and cheaper per ml by DUPE_MAX_PRICE_RATIO."""
    return await SimilarityService(session).dupes(fragrance_id, limit)


@router.get("/{fragrance_id}/price-history", response_model=PriceHistoryOut)
async def price_history(fragrance_id: int, session: SessionDep, days: int = Query(365, ge=7, le=3650)) -> Any:
    return await PriceService(session).history(fragrance_id, days)
