from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminUser, ResourcesDep, SessionDep
from app.schemas.catalog import RetailerIn, RetailerOut
from app.schemas.common import CountOut, Page
from app.schemas.prices import PriceLogIn, PriceLogOut, PriceLogUpdate
from app.services.catalog import CatalogService
from app.services.prices import PriceService

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/retailers", response_model=list[RetailerOut])
async def list_retailers(session: SessionDep) -> Any:
    return await CatalogService(session).list_retailers()


@router.post("/admin/retailers", response_model=RetailerOut, status_code=status.HTTP_201_CREATED)
async def create_retailer(data: RetailerIn, session: SessionDep, _: AdminUser) -> Any:
    return await CatalogService(session).save_retailer(data.model_dump())


@router.put("/admin/retailers/{retailer_id}", response_model=RetailerOut)
async def update_retailer(retailer_id: int, data: RetailerIn, session: SessionDep, _: AdminUser) -> Any:
    return await CatalogService(session).save_retailer(data.model_dump(), retailer_id)


@router.delete("/admin/retailers/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retailer(retailer_id: int, session: SessionDep, _: AdminUser) -> Response:
    await CatalogService(session).delete_retailer(retailer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/logs", response_model=Page[PriceLogOut])
async def list_logs(
    session: SessionDep,
    _: AdminUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    fragrance_id: int | None = None,
    retailer_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    is_sale: bool | None = None,
) -> Any:
    items, total = await PriceService(session).list_logs(
        page, size, fragrance_id, retailer_id, date_from, date_to, is_sale
    )
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/admin/logs/today-count", response_model=CountOut)
async def today_count(session: SessionDep, _: AdminUser) -> CountOut:
    return CountOut(count=await PriceService(session).today_count())


@router.get("/admin/logs/recent", response_model=list[PriceLogOut])
async def recent_logs(session: SessionDep, _: AdminUser, limit: int = Query(20, ge=1, le=100)) -> Any:
    return await PriceService(session).recent(limit)


@router.post("/admin/logs", response_model=PriceLogOut, status_code=status.HTTP_201_CREATED)
async def create_log(data: PriceLogIn, session: SessionDep, res: ResourcesDep, _: AdminUser) -> Any:
    """Log a price. Triggers the wishlist-alert check for that fragrance."""
    out = await PriceService(session).create_log(data)
    await res.queue.enqueue("check_price_alerts", data.fragrance_id)
    return out


@router.put("/admin/logs/{log_id}", response_model=PriceLogOut)
async def update_log(
    log_id: int, data: PriceLogUpdate, session: SessionDep, res: ResourcesDep, _: AdminUser
) -> Any:
    out = await PriceService(session).update_log(log_id, data.model_dump(exclude_unset=True))
    await res.queue.enqueue("check_price_alerts", out["fragrance_id"])
    return out


@router.delete("/admin/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(log_id: int, session: SessionDep, _: AdminUser) -> Response:
    await PriceService(session).delete_log(log_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
