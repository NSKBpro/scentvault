from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import AdminUser, CurrentUser, Prefs, ResourcesDep, SessionDep, limiter
from app.core.config import get_settings
from app.core.constants import PickOccasion
from app.repositories.vectors import VectorFilters
from app.schemas.ai import (
    AIExplainIn,
    AIExplainOut,
    AISearchIn,
    AISearchOut,
    EmbedQueryIn,
    FragranceMatch,
    OllamaHealth,
    RecommendationItem,
)
from app.schemas.wear import DailyPickOut, PickAcceptIn, WearOut
from app.services.ai_search import AISearchService
from app.services.daily_pick import DailyPickService
from app.services.similarity import SimilarityService

router = APIRouter(prefix="/ai", tags=["ai"])
AI_LIMIT = get_settings().RATE_LIMIT_AI


@router.post("/search", response_model=AISearchOut)
@limiter.limit(AI_LIMIT)
async def ai_search(
    request: Request,
    data: AISearchIn,
    session: SessionDep,
    res: ResourcesDep,
    user: CurrentUser,
    prefs: Prefs,
) -> Any:
    """Natural-language search. Returns results right away; pass ``explain=true`` to wait for
    the advisor's paragraph, or fetch it afterwards from ``POST /ai/explain``."""
    svc = AISearchService(session, res.embedder, res.llm, prefs.currency, prefs.gender_preference)
    return await svc.search(data.query, data.limit, data.explain)


@router.post("/explain", response_model=AIExplainOut)
@limiter.limit(AI_LIMIT)
async def ai_explain(
    request: Request, data: AIExplainIn, session: SessionDep, res: ResourcesDep, user: CurrentUser
) -> AIExplainOut:
    text, source = await AISearchService(session, res.embedder, res.llm).explain(
        data.query, data.fragrance_ids
    )
    return AIExplainOut(explanation=text, source=source)


@router.post("/embed-query", response_model=list[FragranceMatch])
@limiter.limit(AI_LIMIT)
async def embed_query(
    request: Request, data: EmbedQueryIn, session: SessionDep, res: ResourcesDep, user: CurrentUser
) -> Any:
    """Raw semantic search: embed the text and return the nearest fragrances (no parsing, no LLM)."""
    return await SimilarityService(session, res.embedder).search_text(data.text, data.limit, VectorFilters())


@router.get("/recommend", response_model=list[RecommendationItem])
async def recommend(
    session: SessionDep, user: CurrentUser, prefs: Prefs, limit: int = Query(10, ge=1, le=50)
) -> Any:
    """From your bottles rated 4★+ or marked favourite. Empty list until there is enough to go on."""
    return await SimilarityService(session).recommend(user.id, limit, prefs.gender_preference)


@router.get("/daily-pick", response_model=DailyPickOut)
async def daily_pick(
    session: SessionDep,
    res: ResourcesDep,
    user: CurrentUser,
    prefs: Prefs,
    occasion: PickOccasion | None = None,
) -> Any:
    """Top 3 bottles for today with reason chips (weather, occasion, rotation, rating)."""
    return await DailyPickService(session, user.id, prefs, res.weather, res.llm).get(occasion)


@router.post("/daily-pick/accept", response_model=WearOut, status_code=201)
async def accept_pick(
    data: PickAcceptIn, session: SessionDep, res: ResourcesDep, user: CurrentUser, prefs: Prefs
) -> Any:
    """'Wear this' — logs a wear for the chosen pick and records which suggestion was taken."""
    wear, bottle = await DailyPickService(session, user.id, prefs, res.weather, res.llm).accept(data)
    if bottle is not None and bottle.remaining_pct <= get_settings().RUNNING_LOW_PCT:
        await res.queue.enqueue("running_low", bottle.id)
    return wear


@router.get("/health", response_model=OllamaHealth)
async def ai_health(res: ResourcesDep, _: AdminUser) -> Any:
    return await res.llm.health()
