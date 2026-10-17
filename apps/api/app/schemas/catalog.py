from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.constants import Concentration, Gender, NotePosition, RadarAxis, Sillage
from app.schemas.common import RefOut, Schema


# ── Brands ──────────────────────────────────────────────────────────
class BrandIn(Schema):
    name: str = Field(min_length=1, max_length=200)
    country: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    description: str | None = None


class BrandUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    description: str | None = None


class BrandOut(Schema):
    id: int
    name: str
    country: str | None
    website_url: str | None
    logo_url: str | None
    description: str | None
    created_at: datetime
    fragrance_count: int = 0


# ── Notes ───────────────────────────────────────────────────────────
class NoteIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="Other", max_length=60)
    description: str | None = None


class NoteUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=60)
    description: str | None = None


class NoteOut(Schema):
    id: int
    name: str
    category: str
    description: str | None


class NoteImportResult(Schema):
    inserted: int
    skipped: int
    errors: list[str]


# ── Families / accords / occasions ──────────────────────────────────
class FamilyIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    axis: RadarAxis | None = None


class FamilyOut(Schema):
    id: int
    name: str
    description: str | None
    axis: RadarAxis | None
    fragrance_count: int = 0


class NamedIn(Schema):
    name: str = Field(min_length=1, max_length=120)


class AccordOut(Schema):
    id: int
    name: str
    fragrance_count: int = 0


class OccasionOut(Schema):
    id: int
    name: str
    fragrance_count: int = 0


# ── Retailers ───────────────────────────────────────────────────────
class RetailerIn(Schema):
    name: str = Field(min_length=1, max_length=200)
    website_url: str | None = None
    country: str | None = None


class RetailerOut(Schema):
    id: int
    name: str
    website_url: str | None
    country: str | None
    created_at: datetime


# ── Fragrances ──────────────────────────────────────────────────────
class FragranceNoteIn(Schema):
    note_id: int
    position: NotePosition
    prominence: int = Field(default=3, ge=1, le=5)


class FragranceNoteOut(Schema):
    note_id: int
    name: str
    category: str
    position: NotePosition
    prominence: int


class FragrancePriceIn(Schema):
    size_ml: int = Field(gt=0, le=1000)
    price_usd: float = Field(ge=0)


class FragrancePriceOut(Schema):
    id: int
    size_ml: int
    price_usd: float


class FragranceIn(Schema):
    name: str = Field(min_length=1, max_length=200)
    brand_id: int
    concentration: Concentration
    gender: Gender
    sillage: Sillage | None = "Moderate"
    release_year: int | None = Field(default=None, ge=1700, le=2100)
    description: str | None = None
    longevity_hours: float | None = Field(default=None, ge=0, le=48)
    image_url: str | None = None
    discontinued: bool = False
    season_spring: bool = False
    season_summer: bool = False
    season_fall: bool = False
    season_winter: bool = False
    notes: list[FragranceNoteIn] = []
    family_ids: list[int] = []
    accord_ids: list[int] = []
    occasion_ids: list[int] = []
    prices: list[FragrancePriceIn] = []


class FragranceListItem(Schema):
    """Light row for lists and pickers — no nested relations."""

    id: int
    name: str
    brand_id: int
    brand_name: str
    concentration: Concentration
    gender: Gender
    release_year: int | None
    image_url: str | None
    discontinued: bool
    has_embedding: bool
    note_count: int
    min_price_usd: float | None
    sizes_ml: list[int]
    families: list[str]
    created_at: datetime


class FragranceDetail(Schema):
    id: int
    name: str
    brand: RefOut
    brand_id: int
    concentration: Concentration
    gender: Gender
    sillage: Sillage | None
    release_year: int | None
    description: str | None
    longevity_hours: float | None
    image_url: str | None
    discontinued: bool
    season_spring: bool
    season_summer: bool
    season_fall: bool
    season_winter: bool
    notes: list[FragranceNoteOut]
    families: list[RefOut]
    accords: list[RefOut]
    occasions: list[RefOut]
    prices: list[FragrancePriceOut]
    has_embedding: bool
    created_at: datetime
    updated_at: datetime


class FragrancePreviewIn(Schema):
    """Same shape as FragranceIn, but nothing is required: the admin form previews while you type."""

    sillage: str | None = None
    longevity_hours: float | None = None
    season_spring: bool = False
    season_summer: bool = False
    season_fall: bool = False
    season_winter: bool = False
    notes: list[FragranceNoteIn] = []
    family_ids: list[int] = []
    accord_ids: list[int] = []
    occasion_ids: list[int] = []


class EmbeddingTextPreview(Schema):
    text: str
