from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import AdminUser, ResourcesDep, SessionDep
from app.schemas.admin import (
    AdminStats,
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    ImportConfirmIn,
    ImportConfirmOut,
    ImportPreviewOut,
)
from app.schemas.common import Page
from app.services.admin import AdminService
from app.services.auth import AdminUserService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def stats(session: SessionDep, _: AdminUser) -> Any:
    """Counts plus work queues (missing notes / image / prices / embeddings, stale prices)."""
    return await AdminService(session).stats()


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    session: SessionDep,
    _: AdminUser,
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=200),
    search: str | None = None,
    role: str | None = None,
) -> Any:
    items, total = await AdminUserService(session).list_users(page, size, search, role)
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: AdminUserCreate, session: SessionDep, _: AdminUser) -> Any:
    return await AdminUserService(session).create(data.email, data.password, data.display_name, data.role)


@router.put("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID, data: AdminUserUpdate, session: SessionDep, admin: AdminUser
) -> Any:
    return await AdminUserService(session).update(user_id, data.model_dump(exclude_unset=True), admin)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep, admin: AdminUser) -> Response:
    await AdminUserService(session).delete(user_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "ZIP of CSV/JSON files"}},
)
async def export(
    session: SessionDep,
    _: AdminUser,
    format: str = Query("csv", pattern="^(csv|json)$"),
    tables: str | None = Query(None, description="Comma list; default = everything incl. 'catalog'"),
) -> Response:
    data, name = await AdminService(session).export_zip(
        format, [t.strip() for t in tables.split(",")] if tables else None
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/import/preview", response_model=ImportPreviewOut)
async def import_preview(session: SessionDep, _: AdminUser, file: UploadFile = File(...)) -> Any:
    return await AdminService(session).import_preview(await file.read())


@router.post("/import/confirm", response_model=ImportConfirmOut)
async def import_confirm(data: ImportConfirmIn, session: SessionDep, res: ResourcesDep, _: AdminUser) -> Any:
    out, new_ids = await AdminService(session).import_confirm(data.session_data, data.skip_errors)
    if new_ids:
        await res.queue.enqueue("embed_fragrances", new_ids)
    return out
