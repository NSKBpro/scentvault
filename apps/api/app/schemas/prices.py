from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import Schema


class PriceLogIn(Schema):
    fragrance_id: int
    retailer_id: int
    size_ml: int = Field(gt=0, le=1000)
    price_usd: float = Field(ge=0)
    product_url: str | None = None
    is_sale: bool = False


class PriceLogUpdate(Schema):
    price_usd: float | None = Field(default=None, ge=0)
    size_ml: int | None = Field(default=None, gt=0, le=1000)
    product_url: str | None = None
    is_sale: bool | None = None


class PriceLogFragrance(Schema):
    id: int
    name: str
    brand_name: str


class PriceLogRetailer(Schema):
    id: int
    name: str


class PriceLogOut(Schema):
    id: int
    fragrance_id: int
    retailer_id: int
    size_ml: int
    price_usd: float
    product_url: str | None
    is_sale: bool
    logged_at: datetime
    fragrance: PriceLogFragrance
    retailer: PriceLogRetailer


class PricePoint(Schema):
    price_usd: float
    logged_at: datetime
    retailer_name: str
    is_sale: bool


class PriceSeries(Schema):
    size_ml: int
    msrp_usd: float | None
    latest_usd: float | None
    lowest_usd: float | None
    highest_usd: float | None
    average_usd: float | None
    points: list[PricePoint]


class PriceHistoryOut(Schema):
    fragrance_id: int
    series: list[PriceSeries]


class PriceDropOut(Schema):
    fragrance_id: int
    fragrance_name: str
    brand_name: str
    concentration: str
    image_url: str | None
    size_ml: int
    current_price_usd: float
    previous_avg_usd: float
    drop_pct: float
    drop_amount_usd: float
    retailer_name: str
    product_url: str | None
    logged_at: datetime
    history: list[float]
