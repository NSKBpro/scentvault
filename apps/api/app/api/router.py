"""One api_router; every sub-router mounts here and the app mounts it under API_PREFIX."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai,
    alerts,
    auth,
    catalog,
    collection,
    deals,
    fragrances,
    prices,
    system,
    wears,
)

api_router = APIRouter()
for r in (
    system.router,
    auth.router,
    auth.me_router,
    catalog.router,
    catalog.admin,
    fragrances.router,
    ai.router,
    collection.router,
    wears.router,
    alerts.router,
    alerts.notifications,
    deals.router,
    prices.router,
    admin.router,
):
    api_router.include_router(r)
