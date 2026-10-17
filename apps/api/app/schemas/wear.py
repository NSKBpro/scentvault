from __future__ import annotations

import datetime as dt

from pydantic import Field, model_validator

from app.core.constants import PickOccasion
from app.schemas.common import Schema


class WearIn(Schema):
    collection_item_id: int | None = None
    fragrance_id: int | None = None
    worn_on: dt.date | None = None  # defaults to today in the user's timezone
    sprays: int | None = Field(default=None, ge=0, le=50)
    occasion: str | None = Field(default=None, max_length=40)
    temp_c: float | None = Field(default=None, ge=-60, le=60)
    note: str | None = Field(default=None, max_length=1000)
    compliment: bool = False
    client_ref: str | None = Field(default=None, max_length=64)
    # Lower the bottle's remaining % by sprays × ML_PER_SPRAY (an estimate).
    adjust_remaining: bool = True

    @model_validator(mode="after")
    def _target(self) -> WearIn:
        if self.collection_item_id is None and self.fragrance_id is None:
            raise ValueError("collection_item_id or fragrance_id is required")
        return self


class WearOut(Schema):
    id: int
    collection_item_id: int | None
    fragrance_id: int
    fragrance_name: str
    brand_name: str
    worn_on: dt.date
    sprays: int | None
    occasion: str | None
    temp_c: float | None
    note: str | None
    compliment: bool
    client_ref: str | None
    created_at: dt.datetime
    remaining_pct: int | None = None  # bottle level after this wear


class BottleWearStat(Schema):
    collection_item_id: int
    fragrance_id: int
    fragrance_name: str
    brand_name: str
    wear_count: int
    last_worn_on: dt.date | None
    days_since_worn: int | None
    cost_per_wear: float | None
    cost_per_wear_is_estimate: bool
    currency: str


class MonthCount(Schema):
    month: str  # YYYY-MM
    wears: int


class WearStats(Schema):
    total_wears: int
    days_logged: int
    distinct_fragrances: int
    rotation_spread: float  # 0..1, share of owned bottles worn in the last 90 days
    most_worn: list[BottleWearStat]
    least_worn: list[BottleWearStat]
    shelf_time: list[BottleWearStat]  # not worn for NEGLECTED_DAYS+
    per_bottle: list[BottleWearStat]
    per_month: list[MonthCount]
    compliments: int


# ── Daily pick ──────────────────────────────────────────────────────
class ReasonChip(Schema):
    label: str
    kind: str  # weather | season | occasion | rotation | rating | level | favorite
    positive: bool


class WeatherNow(Schema):
    city: str
    temp_c: float
    feels_like_c: float | None
    condition: str
    is_rainy: bool
    source: str


class PickItem(Schema):
    rank: int
    collection_item_id: int
    fragrance_id: int
    fragrance_name: str
    brand_name: str
    concentration: str
    image_url: str | None
    remaining_pct: int
    score: float
    reasons: list[ReasonChip]
    last_worn_on: dt.date | None


class DailyPickOut(Schema):
    date: dt.date
    occasion: PickOccasion
    season: str
    weather: WeatherNow | None
    picks: list[PickItem]
    sentence: str | None
    sentence_source: str  # llm | template | none
    worn_today: list[int]  # collection item ids already worn today


class PickAcceptIn(Schema):
    collection_item_id: int
    occasion: PickOccasion | None = None
    rank: int | None = Field(default=None, ge=1, le=10)
    sprays: int | None = Field(default=None, ge=0, le=50)
