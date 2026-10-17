from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.ai import CollectionDupe
from app.schemas.prices import PriceDropOut
from app.services.prices import PriceService
from app.services.similarity import SimilarityService

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/price-drops", response_model=list[PriceDropOut])
async def price_drops(
    session: SessionDep,
    min_drop_pct: float = Query(5.0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Latest price per fragrance *and size* vs. the previous five logs (or the reference price)."""
    return await PriceService(session).price_drops(min_drop_pct, limit, days)


@router.get("/dupes-for-collection", response_model=list[CollectionDupe])
async def dupes_for_collection(
    session: SessionDep, user: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> Any:
    return await SimilarityService(session).collection_dupes(user.id, limit)
