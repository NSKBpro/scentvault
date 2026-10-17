from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, Prefs, ResourcesDep, SessionDep
from app.schemas.alerts import AlertIn, AlertOut, AlertUpdate, NotificationOut, NotificationPage
from app.schemas.common import CountOut
from app.services.alerts import AlertService
from app.services.notifications import NotificationService

router = APIRouter(prefix="/alerts", tags=["alerts"])
notifications = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(session: SessionDep, user: CurrentUser) -> Any:
    return await AlertService(session).list_alerts(user.id)


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    data: AlertIn, session: SessionDep, res: ResourcesDep, user: CurrentUser, prefs: Prefs
) -> Any:
    """'Notify me below X' — fires immediately if a recent price is already at/below the target."""
    return await AlertService(session, res.push).create(user.id, data, prefs.currency)


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: int, data: AlertUpdate, session: SessionDep, res: ResourcesDep, user: CurrentUser
) -> Any:
    return await AlertService(session, res.push).update(
        user.id, alert_id, data.model_dump(exclude_unset=True)
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: int, session: SessionDep, user: CurrentUser) -> Response:
    await AlertService(session).delete(user.id, alert_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@notifications.get("", response_model=NotificationPage)
async def list_notifications(
    session: SessionDep, user: CurrentUser, unread_only: bool = False, limit: int = Query(50, ge=1, le=200)
) -> Any:
    return await NotificationService(session).inbox(user.id, unread_only, limit)


@notifications.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: int, session: SessionDep, user: CurrentUser) -> Any:
    return await NotificationService(session).mark_read(user.id, notification_id)


@notifications.post("/read-all", response_model=CountOut)
async def mark_all_read(session: SessionDep, user: CurrentUser) -> CountOut:
    return CountOut(count=await NotificationService(session).mark_all_read(user.id))
