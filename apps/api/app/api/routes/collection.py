from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, Prefs, ResourcesDep, SessionDep
from app.core.config import get_settings
from app.schemas.ai import CollectionDupe
from app.schemas.collection import (
    CollectionItemIn,
    CollectionItemOut,
    CollectionItemUpdate,
    CollectionStats,
    ScentDNA,
    SellIn,
)
from app.services.collection import CollectionService
from app.services.similarity import SimilarityService

router = APIRouter(prefix="/collection", tags=["collection"])


def _svc(session: Any, user: Any, prefs: Any) -> CollectionService:
    return CollectionService(session, user.id, prefs.currency)


@router.get("", response_model=list[CollectionItemOut])
async def list_collection(
    session: SessionDep,
    user: CurrentUser,
    prefs: Prefs,
    status_: str | None = Query(
        None,
        alias="status",
        description="own | wishlist | tried | finished | sold | gifted, a comma list, "
        "or the groups 'active' / 'archive'",
    ),
    family: str | None = None,
    sort: str = Query(
        "date_desc", description="date_desc | alpha | rating | remaining | price | worn | last_worn"
    ),
) -> Any:
    return await _svc(session, user, prefs).list_items(status_, family, sort)


@router.post("", response_model=CollectionItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    data: CollectionItemIn, response: Response, session: SessionDep, user: CurrentUser, prefs: Prefs
) -> Any:
    """Idempotent when ``client_ref`` is set: replaying an offline add returns the original (200)."""
    item, created = await _svc(session, user, prefs).add(data)
    if not created:
        response.status_code = status.HTTP_200_OK
    return item


@router.get("/stats", response_model=CollectionStats)
async def stats(session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    return await _svc(session, user, prefs).stats()


@router.get("/scent-dna", response_model=ScentDNA)
async def scent_dna(session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    return await _svc(session, user, prefs).scent_dna()


@router.get("/dupes", response_model=list[CollectionDupe])
async def collection_dupes(
    session: SessionDep, user: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> Any:
    """Cheaper alternatives for bottles you own or want."""
    return await SimilarityService(session).collection_dupes(user.id, limit)


@router.get("/{item_id}", response_model=CollectionItemOut)
async def get_item(item_id: int, session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    return await _svc(session, user, prefs).get(item_id)


@router.patch("/{item_id}", response_model=CollectionItemOut)
async def update_item(
    item_id: int,
    data: CollectionItemUpdate,
    session: SessionDep,
    res: ResourcesDep,
    user: CurrentUser,
    prefs: Prefs,
) -> Any:
    out = await _svc(session, user, prefs).update(item_id, data)
    if (
        "remaining_pct" in data.model_fields_set
        and out["status"] == "own"
        and out["remaining_pct"] <= get_settings().RUNNING_LOW_PCT
    ):
        await res.queue.enqueue("running_low", item_id)
    return out


@router.post("/{item_id}/finish", response_model=CollectionItemOut)
async def finish_item(item_id: int, session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    """Mark the bottle empty: status → finished, remaining → 0."""
    return await _svc(session, user, prefs).finish(item_id)


@router.post("/{item_id}/sell", response_model=CollectionItemOut)
async def sell_item(item_id: int, data: SellIn, session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    return await _svc(session, user, prefs).sell(item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, session: SessionDep, user: CurrentUser, prefs: Prefs) -> Response:
    await _svc(session, user, prefs).delete(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
