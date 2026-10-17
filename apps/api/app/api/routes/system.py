from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import ResourcesDep, SessionDep
from app.core import constants
from app.core.config import get_settings
from app.schemas.admin import HealthOut, MetaOut

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
async def health(session: SessionDep, res: ResourcesDep) -> HealthOut:
    try:
        await session.execute(text("SELECT 1"))
        db = "connected"
    except Exception as exc:  # pragma: no cover - reported, not raised
        db = f"error: {type(exc).__name__}"
    return HealthOut(
        status="online" if db == "connected" else "degraded",
        version=get_settings().VERSION,
        database=db,
        embedding_provider=res.embedder.name,
        job_queue=res.queue.name,
    )


@router.get("/meta", response_model=MetaOut)
async def meta() -> MetaOut:
    s = get_settings()
    return MetaOut(
        concentrations=list(constants.CONCENTRATIONS),
        genders=list(constants.GENDERS),
        sillages=list(constants.SILLAGES),
        note_positions=list(constants.NOTE_POSITIONS),
        radar_axes=list(constants.RADAR_AXES),
        collection_statuses=list(constants.COLLECTION_STATUSES),
        bottle_types=list(constants.BOTTLE_TYPES),
        pick_occasions=list(constants.PICK_OCCASIONS),
        currencies=dict(s.CURRENCY_RATES),
        ml_per_spray=s.ML_PER_SPRAY,
    )
