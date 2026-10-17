"""The user's shelf: bottles, wears, daily-pick events."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import BOTTLE_TYPES, COLLECTION_STATUSES, sql_in
from app.models.base import Base, created_at_col, updated_at_col
from app.models.catalog import Fragrance


class CollectionItem(Base):
    __tablename__ = "user_collection"
    __table_args__ = (
        CheckConstraint(f"status IN {sql_in(COLLECTION_STATUSES)}", name="status"),
        CheckConstraint(f"bottle_type IN {sql_in(BOTTLE_TYPES)}", name="bottle_type"),
        CheckConstraint("rating IS NULL OR (rating >= 0.5 AND rating <= 5)", name="rating"),
        CheckConstraint("remaining_pct BETWEEN 0 AND 100", name="remaining"),
        CheckConstraint("size_ml IS NULL OR size_ml > 0", name="size_positive"),
        # One active entry per (fragrance, size, bottle type); archived bottles don't block re-buying.
        Index(
            "uq_user_collection_active",
            "user_id",
            "fragrance_id",
            "size_ml",
            "bottle_type",
            unique=True,
            postgresql_where=text("status IN ('own', 'wishlist', 'tried')"),
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("user_id", "client_ref", name="uq_user_collection_client_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="own", server_default="own")
    bottle_type: Mapped[str] = mapped_column(String(10), default="full", server_default="full")
    size_ml: Mapped[int | None] = mapped_column(Integer)
    purchase_price: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    purchase_date: Mapped[date | None] = mapped_column(Date)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1, asdecimal=False))
    remaining_pct: Mapped[int] = mapped_column(SmallInteger, default=100, server_default="100")
    notes: Mapped[str | None] = mapped_column(Text)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source: Mapped[str | None] = mapped_column(String(120))
    sold_price: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False))
    sold_at: Mapped[date | None] = mapped_column(Date)
    # Client-generated id so an offline add replayed twice creates one row.
    client_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    fragrance: Mapped[Fragrance] = relationship()


class WearLog(Base):
    __tablename__ = "wear_logs"
    __table_args__ = (
        Index("ix_wear_logs_user_day", "user_id", "worn_on"),
        UniqueConstraint("user_id", "client_ref", name="uq_wear_logs_client_ref"),
        CheckConstraint("sprays IS NULL OR sprays BETWEEN 0 AND 50", name="sprays"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    collection_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_collection.id", ondelete="SET NULL"), index=True
    )
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"), index=True)
    worn_on: Mapped[date] = mapped_column(Date)
    sprays: Mapped[int | None] = mapped_column(SmallInteger)
    occasion: Mapped[str | None] = mapped_column(String(40))
    temp_c: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    compliment: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    client_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()

    fragrance: Mapped[Fragrance] = relationship()


class PickEvent(Base):
    """pick_shown / pick_accepted log — lets the scorer weights be fitted later."""

    __tablename__ = "pick_events"
    __table_args__ = (
        CheckConstraint("kind IN ('shown', 'accepted')", name="kind"),
        Index("ix_pick_events_user_date", "user_id", "pick_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    pick_date: Mapped[date] = mapped_column(Date)
    occasion: Mapped[str | None] = mapped_column(String(20))
    collection_item_id: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(SmallInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = created_at_col()
