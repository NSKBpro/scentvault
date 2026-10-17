from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import AdminUser, ResourcesDep, SessionDep
from app.repositories.catalog import FragranceFilters, FragranceSort, MissingKind
from app.schemas.ai import EmbeddingGenerateIn, EmbeddingRegenerateIn, EmbeddingResult, EmbeddingStatus
from app.schemas.catalog import (
    AccordOut,
    BrandIn,
    BrandOut,
    BrandUpdate,
    EmbeddingTextPreview,
    FamilyIn,
    FamilyOut,
    FragranceDetail,
    FragranceIn,
    FragranceListItem,
    FragrancePreviewIn,
    NamedIn,
    NoteImportResult,
    NoteIn,
    NoteOut,
    NoteUpdate,
    OccasionOut,
)
from app.schemas.common import JobAccepted, Page
from app.services.catalog import CatalogService
from app.services.embedding.service import EmbeddingService

router = APIRouter(prefix="/catalog", tags=["catalog"])
admin = APIRouter(prefix="/catalog/admin", tags=["catalog-admin"])

MAX_PAGE = 500


# ── Fragrances (public) ─────────────────────────────────────────────
@router.get("/fragrances", response_model=Page[FragranceListItem])
async def list_fragrances(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = Query(None, max_length=100, description="Matches fragrance or brand name"),
    brand_id: int | None = None,
    family_id: int | None = None,
    accord_id: int | None = None,
    occasion_id: int | None = None,
    concentration: str | None = None,
    gender: str | None = None,
    missing: MissingKind | None = Query(None, description="Admin work-queue filter"),
    include_discontinued: bool = True,
    sort: FragranceSort = "newest",
) -> Page[FragranceListItem]:
    flt = FragranceFilters(
        search=search,
        brand_id=brand_id,
        family_id=family_id,
        accord_id=accord_id,
        occasion_id=occasion_id,
        concentration=concentration,
        gender=gender,
        missing=missing,
        include_discontinued=include_discontinued,
    )
    return await CatalogService(session).list_fragrances(flt, sort, page, size)


@router.get("/fragrances/{fragrance_id}", response_model=FragranceDetail)
async def get_fragrance(fragrance_id: int, session: SessionDep) -> FragranceDetail:
    return await CatalogService(session).get_detail(fragrance_id)


# ── Lookups (public lists) ──────────────────────────────────────────
def _page(result: tuple[list[dict[str, Any]], int], page: int, size: int) -> dict[str, Any]:
    rows, total = result
    return {"items": rows, "total": total, "page": page, "size": size}


@router.get("/brands", response_model=Page[BrandOut])
async def list_brands(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = None,
) -> Any:
    return _page(await CatalogService(session).list_lookup("brands", page, size, search), page, size)


@router.get("/notes", response_model=Page[NoteOut])
async def list_notes(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = None,
    category: str | None = None,
) -> Any:
    return _page(await CatalogService(session).list_lookup("notes", page, size, search, category), page, size)


@router.get("/notes/categories", response_model=list[str])
async def note_categories(session: SessionDep) -> list[str]:
    return await CatalogService(session).repo.note_categories()


@router.get("/families", response_model=Page[FamilyOut])
async def list_families(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = None,
) -> Any:
    return _page(await CatalogService(session).list_lookup("families", page, size, search), page, size)


@router.get("/accords", response_model=Page[AccordOut])
async def list_accords(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = None,
) -> Any:
    return _page(await CatalogService(session).list_lookup("accords", page, size, search), page, size)


@router.get("/occasions", response_model=Page[OccasionOut])
async def list_occasions(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_PAGE),
    search: str | None = None,
) -> Any:
    return _page(await CatalogService(session).list_lookup("occasions", page, size, search), page, size)


# ── Fragrances (admin) ──────────────────────────────────────────────
@admin.post("/fragrances", response_model=FragranceDetail, status_code=status.HTTP_201_CREATED)
async def create_fragrance(
    data: FragranceIn, session: SessionDep, res: ResourcesDep, _: AdminUser
) -> FragranceDetail:
    return await CatalogService(session, res.queue).create_fragrance(data)


@admin.post("/fragrances/embedding-preview", response_model=EmbeddingTextPreview)
async def embedding_preview(
    data: FragrancePreviewIn, session: SessionDep, res: ResourcesDep, _: AdminUser
) -> EmbeddingTextPreview:
    """The exact text the embedding model will see for this (unsaved) form."""
    return EmbeddingTextPreview(text=await EmbeddingService(session, res.embedder).preview(data))


@admin.put("/fragrances/{fragrance_id}", response_model=FragranceDetail)
async def update_fragrance(
    fragrance_id: int, data: FragranceIn, session: SessionDep, res: ResourcesDep, _: AdminUser
) -> FragranceDetail:
    return await CatalogService(session, res.queue).update_fragrance(fragrance_id, data)


@admin.delete("/fragrances/{fragrance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fragrance(fragrance_id: int, session: SessionDep, _: AdminUser) -> Response:
    await CatalogService(session).delete_fragrance(fragrance_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Lookups (admin CRUD) ────────────────────────────────────────────
LookupKind = Literal["brands", "notes", "families", "accords", "occasions"]


def _register_lookup_crud(
    kind: LookupKind, create_model: type[BaseModel], update_model: type[BaseModel], out_model: type[BaseModel]
) -> None:
    singular = {
        "brands": "brand",
        "notes": "note",
        "families": "family",
        "accords": "accord",
        "occasions": "occasion",
    }[kind]

    async def create(data: create_model, session: SessionDep, _: AdminUser) -> Any:  # type: ignore[valid-type]
        return await CatalogService(session).create_lookup(kind, data.model_dump())  # type: ignore[attr-defined]

    async def update(item_id: int, data: update_model, session: SessionDep, _: AdminUser) -> Any:  # type: ignore[valid-type]
        return await CatalogService(session).update_lookup(kind, item_id, data.model_dump(exclude_unset=True))  # type: ignore[attr-defined]

    async def delete(item_id: int, session: SessionDep, _: AdminUser) -> Response:
        await CatalogService(session).delete_lookup(kind, item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Annotations are strings (postponed evaluation); point them at the real models.
    create.__annotations__["data"] = create_model
    update.__annotations__["data"] = update_model

    admin.add_api_route(
        f"/{kind}",
        create,
        methods=["POST"],
        response_model=out_model,
        status_code=201,
        name=f"create_{singular}",
        operation_id=f"create_{singular}",
    )
    admin.add_api_route(
        f"/{kind}/{{item_id}}",
        update,
        methods=["PUT"],
        response_model=out_model,
        name=f"update_{singular}",
        operation_id=f"update_{singular}",
    )
    admin.add_api_route(
        f"/{kind}/{{item_id}}",
        delete,
        methods=["DELETE"],
        status_code=204,
        name=f"delete_{singular}",
        operation_id=f"delete_{singular}",
    )


_register_lookup_crud("brands", BrandIn, BrandUpdate, BrandOut)
_register_lookup_crud("notes", NoteIn, NoteUpdate, NoteOut)
_register_lookup_crud("families", FamilyIn, FamilyIn, FamilyOut)
_register_lookup_crud("accords", NamedIn, NamedIn, AccordOut)
_register_lookup_crud("occasions", NamedIn, NamedIn, OccasionOut)


@admin.post("/notes/import", response_model=NoteImportResult)
async def import_notes(session: SessionDep, _: AdminUser, file: UploadFile = File(...)) -> Any:
    return await CatalogService(session).import_notes_csv(await file.read())


# ── Embeddings (admin) ──────────────────────────────────────────────
@admin.get("/embeddings/status", response_model=EmbeddingStatus)
async def embedding_status(session: SessionDep, res: ResourcesDep, _: AdminUser) -> Any:
    return await EmbeddingService(session, res.embedder).status(res.queue.name)


@admin.post("/embeddings/generate", response_model=EmbeddingResult)
async def generate_embedding(
    data: EmbeddingGenerateIn, session: SessionDep, res: ResourcesDep, _: AdminUser
) -> Any:
    """Embed one fragrance synchronously and return the text the model saw."""
    return await EmbeddingService(session, res.embedder).generate(data.fragrance_id)


@admin.post("/embeddings/regenerate", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def regenerate_embeddings(data: EmbeddingRegenerateIn, res: ResourcesDep, _: AdminUser) -> JobAccepted:
    job_id = await res.queue.enqueue("regenerate_embeddings", data.only_missing)
    scope = "missing or out-of-date" if data.only_missing else "all"
    return JobAccepted(
        status="queued",
        job_id=job_id,
        detail=f"Regenerating {scope} embeddings via the {res.queue.name} queue; "
        "watch progress on /catalog/admin/embeddings/status.",
    )
