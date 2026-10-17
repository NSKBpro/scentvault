"""Catalog: brands, notes, families, accords, occasions, fragrances, prices."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CONCENTRATIONS, GENDERS, NOTE_POSITIONS, RADAR_AXES, SILLAGES, sql_in
from app.models.base import Base, created_at_col, updated_at_col

fragrance_families = Table(
    "fragrance_families",
    Base.metadata,
    Column("fragrance_id", ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True),
    Column("family_id", ForeignKey("families.id", ondelete="CASCADE"), primary_key=True, index=True),
)
fragrance_accords = Table(
    "fragrance_accords",
    Base.metadata,
    Column("fragrance_id", ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True),
    Column("accord_id", ForeignKey("accords.id", ondelete="CASCADE"), primary_key=True, index=True),
)
fragrance_occasions = Table(
    "fragrance_occasions",
    Base.metadata,
    Column("fragrance_id", ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True),
    Column("occasion_id", ForeignKey("occasions.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    country: Mapped[str | None] = mapped_column(String(100))
    website_url: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    fragrances: Mapped[list[Fragrance]] = relationship(back_populates="brand")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(60), default="Other", server_default="Other")
    description: Mapped[str | None] = mapped_column(Text)


class Family(Base):
    __tablename__ = "families"
    __table_args__ = (CheckConstraint(f"axis IS NULL OR axis IN {sql_in(RADAR_AXES)}", name="axis"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Which Scent-DNA radar axis this family feeds. Replaces keyword matching.
    axis: Mapped[str | None] = mapped_column(String(20))


class Accord(Base):
    __tablename__ = "accords"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Occasion(Base):
    __tablename__ = "occasions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Retailer(Base):
    __tablename__ = "retailers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    website_url: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at_col()


class Fragrance(Base):
    __tablename__ = "fragrances"
    __table_args__ = (
        UniqueConstraint("brand_id", "name", "concentration", name="uq_fragrances_brand_name_conc"),
        CheckConstraint(f"concentration IN {sql_in(CONCENTRATIONS)}", name="concentration"),
        CheckConstraint(f"gender IN {sql_in(GENDERS)}", name="gender"),
        CheckConstraint(f"sillage IS NULL OR sillage IN {sql_in(SILLAGES)}", name="sillage"),
        Index("ix_fragrances_name_lower", func.lower(Column("name", String))),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # RESTRICT: deleting a brand that still has fragrances is refused, not cascaded.
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="RESTRICT"), index=True)
    concentration: Mapped[str] = mapped_column(String(20))
    gender: Mapped[str] = mapped_column(String(20))
    sillage: Mapped[str | None] = mapped_column(String(20))
    release_year: Mapped[int | None] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text)
    longevity_hours: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(500))
    discontinued: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    season_spring: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    season_summer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    season_fall: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    season_winter: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    brand: Mapped[Brand] = relationship(back_populates="fragrances")
    notes: Mapped[list[FragranceNote]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan", order_by="FragranceNote.position"
    )
    families: Mapped[list[Family]] = relationship(secondary=fragrance_families, order_by="Family.name")
    accords: Mapped[list[Accord]] = relationship(secondary=fragrance_accords, order_by="Accord.name")
    occasions: Mapped[list[Occasion]] = relationship(secondary=fragrance_occasions, order_by="Occasion.name")
    prices: Mapped[list[FragrancePrice]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan", order_by="FragrancePrice.size_ml"
    )
    embedding: Mapped[FragranceEmbedding | None] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan", uselist=False
    )


class FragranceNote(Base):
    __tablename__ = "fragrance_notes"
    __table_args__ = (
        CheckConstraint(f"position IN {sql_in(NOTE_POSITIONS)}", name="position"),
        CheckConstraint("prominence BETWEEN 1 AND 5", name="prominence"),
    )
    fragrance_id: Mapped[int] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[str] = mapped_column(String(10), primary_key=True)
    prominence: Mapped[int] = mapped_column(SmallInteger, default=3, server_default="3")

    fragrance: Mapped[Fragrance] = relationship(back_populates="notes")
    note: Mapped[Note] = relationship(lazy="joined")


class FragrancePrice(Base):
    """Reference (MSRP) price per size."""

    __tablename__ = "fragrance_prices"
    __table_args__ = (
        UniqueConstraint("fragrance_id", "size_ml", name="uq_fragrance_prices_size"),
        CheckConstraint("size_ml > 0", name="size_positive"),
        CheckConstraint("price_usd >= 0", name="price_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"), index=True)
    size_ml: Mapped[int] = mapped_column(Integer)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))

    fragrance: Mapped[Fragrance] = relationship(back_populates="prices")


class PriceLog(Base):
    """A price spotted at a retailer at a point in time."""

    __tablename__ = "price_logs"
    __table_args__ = (
        Index("ix_price_logs_frag_size_time", "fragrance_id", "size_ml", "logged_at"),
        CheckConstraint("size_ml > 0", name="size_positive"),
        CheckConstraint("price_usd >= 0", name="price_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"))
    retailer_id: Mapped[int] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"), index=True)
    size_ml: Mapped[int] = mapped_column(Integer)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    product_url: Mapped[str | None] = mapped_column(String(1000))
    is_sale: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    fragrance: Mapped[Fragrance] = relationship()
    retailer: Mapped[Retailer] = relationship()


class FragranceEmbedding(Base):
    __tablename__ = "fragrance_embeddings"
    fragrance_id: Mapped[int] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    embedding = mapped_column(Vector(384), nullable=False)
    text_input: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fragrance: Mapped[Fragrance] = relationship(back_populates="embedding")
