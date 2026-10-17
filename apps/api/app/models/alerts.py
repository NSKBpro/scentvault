"""Wishlist price alerts and in-app notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import NOTIFICATION_KINDS, sql_in
from app.models.base import Base, created_at_col
from app.models.catalog import Fragrance


class PriceAlert(Base):
    __tablename__ = "price_alerts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "fragrance_id",
            "size_ml",
            name="uq_price_alerts_target",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("target_price > 0", name="target_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"), index=True)
    size_ml: Mapped[int | None] = mapped_column(Integer)
    target_price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    fragrance: Mapped[Fragrance] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(f"kind IN {sql_in(NOTIFICATION_KINDS)}", name="kind"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        # Same nudge (e.g. "running low: bottle 12") is only created once.
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
