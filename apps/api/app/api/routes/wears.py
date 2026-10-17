from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, Prefs, ResourcesDep, SessionDep
from app.core.config import get_settings
from app.schemas.wear import WearIn, WearOut, WearStats
from app.services.wear import WearService

router = APIRouter(prefix="/wears", tags=["wears"])


@router.post("", response_model=WearOut, status_code=status.HTTP_201_CREATED)
async def log_wear(
    data: WearIn, response: Response, session: SessionDep, res: ResourcesDep, user: CurrentUser, prefs: Prefs
) -> Any:
    """Log a wear. More than one per day is fine. Idempotent with ``client_ref``."""
    wear, bottle, created = await WearService(session, user.id, prefs.timezone, prefs.currency).log(data)
    if not created:
        response.status_code = status.HTTP_200_OK
    elif (
        bottle is not None
        and bottle.status == "own"
        and bottle.remaining_pct <= get_settings().RUNNING_LOW_PCT
    ):
        await res.queue.enqueue("running_low", bottle.id)
    return wear


@router.get("", response_model=list[WearOut])
async def list_wears(
    session: SessionDep,
    user: CurrentUser,
    prefs: Prefs,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    collection_item_id: int | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> Any:
    return await WearService(session, user.id, prefs.timezone).list_wears(
        date_from, date_to, collection_item_id, limit
    )


@router.get("/stats", response_model=WearStats)
async def wear_stats(session: SessionDep, user: CurrentUser, prefs: Prefs) -> Any:
    return await WearService(session, user.id, prefs.timezone, prefs.currency).stats()


@router.delete("/{wear_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wear(wear_id: int, session: SessionDep, user: CurrentUser) -> Response:
    await WearService(session, user.id).delete(wear_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
