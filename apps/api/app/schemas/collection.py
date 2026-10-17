from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from app.core.constants import BottleType, CollectionStatus
from app.schemas.common import Schema


def _half_step(v: float | None) -> float | None:
    if v is None:
        return v
    if round(v * 2) != v * 2:
        raise ValueError("rating must be in steps of 0.5")
    return v


class CollectionItemIn(Schema):
    fragrance_id: int
    status: CollectionStatus = "own"
    bottle_type: BottleType = "full"
    size_ml: int | None = Field(default=None, gt=0, le=1000)
    purchase_price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    purchase_date: dt.date | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5)
    remaining_pct: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)
    is_favorite: bool = False
    source: str | None = Field(default=None, max_length=120)
    client_ref: str | None = Field(default=None, max_length=64)

    _r = field_validator("rating")(classmethod(lambda cls, v: _half_step(v)))


class CollectionItemUpdate(Schema):
    """PATCH semantics: only fields present in the request body change."""

    status: CollectionStatus | None = None
    bottle_type: BottleType | None = None
    size_ml: int | None = Field(default=None, gt=0, le=1000)
    purchase_price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    purchase_date: dt.date | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5)
    remaining_pct: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)
    is_favorite: bool | None = None
    source: str | None = Field(default=None, max_length=120)
    sold_price: float | None = Field(default=None, ge=0)
    sold_at: dt.date | None = None

    _r = field_validator("rating")(classmethod(lambda cls, v: _half_step(v)))


class SellIn(Schema):
    sold_price: float | None = Field(default=None, ge=0)
    sold_at: dt.date | None = None
    gifted: bool = False


class CollectionItemOut(Schema):
    id: int
    fragrance_id: int
    status: CollectionStatus
    bottle_type: BottleType
    size_ml: int | None
    purchase_price: float | None
    currency: str
    purchase_date: dt.date | None
    rating: float | None
    remaining_pct: int
    notes: str | None
    is_favorite: bool
    source: str | None
    sold_price: float | None
    sold_at: dt.date | None
    client_ref: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    fragrance_name: str
    brand_name: str
    concentration: str
    gender: str
    image_url: str | None
    families: list[str]
    wear_count: int
    last_worn_on: dt.date | None


class CollectionStats(Schema):
    owned_count: int
    wishlist_count: int
    tried_count: int
    archived_count: int
    bottles_ml: int
    spent: float  # in `currency`, owned bottles only
    estimated_value_usd: float | None
    avg_rating: float | None
    currency: str


class ScentDNA(Schema):
    woody: int
    citrus: int
    aromatic: int
    oriental: int
    fresh: int
    floral: int
    based_on: int  # number of bottles that fed the radar
