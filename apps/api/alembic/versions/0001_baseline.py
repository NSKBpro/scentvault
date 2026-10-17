"""Baseline schema — the whole ScentVault database in one revision.

Replaces the old 0c986b1c8a50 / t012 chain and patch_db.py. Creates the
pgvector + pg_trgm extensions, every table, and the HNSW / trigram indexes.

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "accords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accords")),
        sa.UniqueConstraint("name", name=op.f("uq_accords_name")),
    )
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("name", name=op.f("uq_brands_name")),
    )
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("axis", sa.String(length=20), nullable=True),
        sa.CheckConstraint(
            "axis IS NULL OR axis IN ('woody', 'citrus', 'aromatic', 'oriental', 'fresh', 'floral')",
            name=op.f("ck_families_axis"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_families")),
        sa.UniqueConstraint("name", name=op.f("uq_families_name")),
    )
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=60), server_default="Other", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
        sa.UniqueConstraint("name", name=op.f("uq_notes_name")),
    )
    op.create_table(
        "occasions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_occasions")),
        sa.UniqueConstraint("name", name=op.f("uq_occasions_name")),
    )
    op.create_table(
        "retailers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retailers")),
        sa.UniqueConstraint("name", name=op.f("uq_retailers_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=10), server_default="user", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "fragrances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("concentration", sa.String(length=20), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=False),
        sa.Column("sillage", sa.String(length=20), nullable=True),
        sa.Column("release_year", sa.SmallInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("longevity_hours", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("discontinued", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("season_spring", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("season_summer", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("season_fall", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("season_winter", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "concentration IN ('EDT', 'EDP', 'Parfum', 'Extrait', 'Cologne', 'Elixir', 'Body Mist', 'Hair Mist')",
            name=op.f("ck_fragrances_concentration"),
        ),
        sa.CheckConstraint(
            "gender IN ('Masculine', 'Feminine', 'Unisex')", name=op.f("ck_fragrances_gender")
        ),
        sa.CheckConstraint(
            "sillage IS NULL OR sillage IN ('Intimate', 'Soft', 'Moderate', 'Strong', 'Enormous')",
            name=op.f("ck_fragrances_sillage"),
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_fragrances_brand_id_brands"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fragrances")),
        sa.UniqueConstraint("brand_id", "name", "concentration", name="uq_fragrances_brand_name_conc"),
    )
    op.create_index(op.f("ix_fragrances_brand_id"), "fragrances", ["brand_id"], unique=False)
    op.create_index(
        "ix_fragrances_name_lower", "fragrances", [sa.literal_column("lower(name)")], unique=False
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('price_alert', 'running_low', 'neglected', 'system')",
            name=op.f("ck_notifications_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_dedupe"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"], unique=False)
    op.create_table(
        "pick_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("pick_date", sa.Date(), nullable=False),
        sa.Column("occasion", sa.String(length=20), nullable=True),
        sa.Column("collection_item_id", sa.Integer(), nullable=True),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('shown', 'accepted')", name=op.f("ck_pick_events_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_pick_events_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pick_events")),
    )
    op.create_index("ix_pick_events_user_date", "pick_events", ["user_id", "pick_date"], unique=False)
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "user_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expo_push_token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_devices_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_devices")),
        sa.UniqueConstraint("expo_push_token", name=op.f("uq_user_devices_expo_push_token")),
    )
    op.create_index(op.f("ix_user_devices_user_id"), "user_devices", ["user_id"], unique=False)
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("gender_preference", sa.String(length=10), server_default="Any", nullable=False),
        sa.Column("notify_price_alerts", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notify_running_low", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notify_neglected", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "gender_preference IN ('Masculine', 'Feminine', 'Unisex', 'Any')",
            name=op.f("ck_user_preferences_gender_preference"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_preferences_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_preferences")),
    )
    op.create_table(
        "fragrance_accords",
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("accord_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["accord_id"],
            ["accords.id"],
            name=op.f("fk_fragrance_accords_accord_id_accords"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_accords_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fragrance_id", "accord_id", name=op.f("pk_fragrance_accords")),
    )
    op.create_index(op.f("ix_fragrance_accords_accord_id"), "fragrance_accords", ["accord_id"], unique=False)
    op.create_table(
        "fragrance_embeddings",
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
        sa.Column("text_input", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_embeddings_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fragrance_id", name=op.f("pk_fragrance_embeddings")),
    )
    op.create_table(
        "fragrance_families",
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_fragrance_families_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_families_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fragrance_id", "family_id", name=op.f("pk_fragrance_families")),
    )
    op.create_index(
        op.f("ix_fragrance_families_family_id"), "fragrance_families", ["family_id"], unique=False
    )
    op.create_table(
        "fragrance_notes",
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("prominence", sa.SmallInteger(), server_default="3", nullable=False),
        sa.CheckConstraint("position IN ('top', 'heart', 'base')", name=op.f("ck_fragrance_notes_position")),
        sa.CheckConstraint("prominence BETWEEN 1 AND 5", name=op.f("ck_fragrance_notes_prominence")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_notes_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["note_id"], ["notes.id"], name=op.f("fk_fragrance_notes_note_id_notes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("fragrance_id", "note_id", "position", name=op.f("pk_fragrance_notes")),
    )
    op.create_index(op.f("ix_fragrance_notes_note_id"), "fragrance_notes", ["note_id"], unique=False)
    op.create_table(
        "fragrance_occasions",
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("occasion_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_occasions_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["occasion_id"],
            ["occasions.id"],
            name=op.f("fk_fragrance_occasions_occasion_id_occasions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fragrance_id", "occasion_id", name=op.f("pk_fragrance_occasions")),
    )
    op.create_index(
        op.f("ix_fragrance_occasions_occasion_id"), "fragrance_occasions", ["occasion_id"], unique=False
    )
    op.create_table(
        "fragrance_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("size_ml", sa.Integer(), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=False),
        sa.CheckConstraint("price_usd >= 0", name=op.f("ck_fragrance_prices_price_nonneg")),
        sa.CheckConstraint("size_ml > 0", name=op.f("ck_fragrance_prices_size_positive")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_prices_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fragrance_prices")),
        sa.UniqueConstraint("fragrance_id", "size_ml", name="uq_fragrance_prices_size"),
    )
    op.create_index(
        op.f("ix_fragrance_prices_fragrance_id"), "fragrance_prices", ["fragrance_id"], unique=False
    )
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("size_ml", sa.Integer(), nullable=True),
        sa.Column("target_price", sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_price > 0", name=op.f("ck_price_alerts_target_positive")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_price_alerts_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_price_alerts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_alerts")),
        sa.UniqueConstraint(
            "user_id",
            "fragrance_id",
            "size_ml",
            name="uq_price_alerts_target",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(op.f("ix_price_alerts_fragrance_id"), "price_alerts", ["fragrance_id"], unique=False)
    op.create_index(op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False)
    op.create_table(
        "price_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("retailer_id", sa.Integer(), nullable=False),
        sa.Column("size_ml", sa.Integer(), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=False),
        sa.Column("product_url", sa.String(length=1000), nullable=True),
        sa.Column("is_sale", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("price_usd >= 0", name=op.f("ck_price_logs_price_nonneg")),
        sa.CheckConstraint("size_ml > 0", name=op.f("ck_price_logs_size_positive")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_price_logs_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name=op.f("fk_price_logs_retailer_id_retailers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_logs")),
    )
    op.create_index(
        "ix_price_logs_frag_size_time", "price_logs", ["fragrance_id", "size_ml", "logged_at"], unique=False
    )
    op.create_index(op.f("ix_price_logs_logged_at"), "price_logs", ["logged_at"], unique=False)
    op.create_index(op.f("ix_price_logs_retailer_id"), "price_logs", ["retailer_id"], unique=False)
    op.create_table(
        "user_collection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="own", nullable=False),
        sa.Column("bottle_type", sa.String(length=10), server_default="full", nullable=False),
        sa.Column("size_ml", sa.Integer(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("rating", sa.Numeric(precision=2, scale=1, asdecimal=False), nullable=True),
        sa.Column("remaining_pct", sa.SmallInteger(), server_default="100", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("sold_price", sa.Numeric(precision=10, scale=2, asdecimal=False), nullable=True),
        sa.Column("sold_at", sa.Date(), nullable=True),
        sa.Column("client_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "bottle_type IN ('full', 'decant', 'sample', 'tester')",
            name=op.f("ck_user_collection_bottle_type"),
        ),
        sa.CheckConstraint(
            "status IN ('own', 'wishlist', 'tried', 'finished', 'sold', 'gifted')",
            name=op.f("ck_user_collection_status"),
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0.5 AND rating <= 5)", name=op.f("ck_user_collection_rating")
        ),
        sa.CheckConstraint("remaining_pct BETWEEN 0 AND 100", name=op.f("ck_user_collection_remaining")),
        sa.CheckConstraint("size_ml IS NULL OR size_ml > 0", name=op.f("ck_user_collection_size_positive")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_user_collection_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_collection_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_collection")),
        sa.UniqueConstraint("user_id", "client_ref", name="uq_user_collection_client_ref"),
    )
    op.create_index(
        op.f("ix_user_collection_fragrance_id"), "user_collection", ["fragrance_id"], unique=False
    )
    op.create_index(op.f("ix_user_collection_user_id"), "user_collection", ["user_id"], unique=False)
    op.create_index(
        "uq_user_collection_active",
        "user_collection",
        ["user_id", "fragrance_id", "size_ml", "bottle_type"],
        unique=True,
        postgresql_where=sa.text("status IN ('own', 'wishlist', 'tried')"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "wear_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("collection_item_id", sa.Integer(), nullable=True),
        sa.Column("fragrance_id", sa.Integer(), nullable=False),
        sa.Column("worn_on", sa.Date(), nullable=False),
        sa.Column("sprays", sa.SmallInteger(), nullable=True),
        sa.Column("occasion", sa.String(length=40), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("compliment", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("client_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sprays IS NULL OR sprays BETWEEN 0 AND 50", name=op.f("ck_wear_logs_sprays")),
        sa.ForeignKeyConstraint(
            ["collection_item_id"],
            ["user_collection.id"],
            name=op.f("fk_wear_logs_collection_item_id_user_collection"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_wear_logs_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_wear_logs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wear_logs")),
        sa.UniqueConstraint("user_id", "client_ref", name="uq_wear_logs_client_ref"),
    )
    op.create_index(
        op.f("ix_wear_logs_collection_item_id"), "wear_logs", ["collection_item_id"], unique=False
    )
    op.create_index(op.f("ix_wear_logs_fragrance_id"), "wear_logs", ["fragrance_id"], unique=False)
    op.create_index("ix_wear_logs_user_day", "wear_logs", ["user_id", "worn_on"], unique=False)
    op.execute(
        "CREATE INDEX ix_fragrance_embeddings_hnsw ON fragrance_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute("CREATE INDEX ix_fragrances_name_trgm ON fragrances USING gin (lower(name) gin_trgm_ops)")
    op.execute("CREATE INDEX ix_brands_name_trgm ON brands USING gin (lower(name) gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_brands_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fragrances_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fragrance_embeddings_hnsw")
    op.drop_index("ix_wear_logs_user_day", table_name="wear_logs")
    op.drop_index(op.f("ix_wear_logs_fragrance_id"), table_name="wear_logs")
    op.drop_index(op.f("ix_wear_logs_collection_item_id"), table_name="wear_logs")
    op.drop_table("wear_logs")
    op.drop_index(
        "uq_user_collection_active",
        table_name="user_collection",
        postgresql_where=sa.text("status IN ('own', 'wishlist', 'tried')"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_index(op.f("ix_user_collection_user_id"), table_name="user_collection")
    op.drop_index(op.f("ix_user_collection_fragrance_id"), table_name="user_collection")
    op.drop_table("user_collection")
    op.drop_index(op.f("ix_price_logs_retailer_id"), table_name="price_logs")
    op.drop_index(op.f("ix_price_logs_logged_at"), table_name="price_logs")
    op.drop_index("ix_price_logs_frag_size_time", table_name="price_logs")
    op.drop_table("price_logs")
    op.drop_index(op.f("ix_price_alerts_user_id"), table_name="price_alerts")
    op.drop_index(op.f("ix_price_alerts_fragrance_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index(op.f("ix_fragrance_prices_fragrance_id"), table_name="fragrance_prices")
    op.drop_table("fragrance_prices")
    op.drop_index(op.f("ix_fragrance_occasions_occasion_id"), table_name="fragrance_occasions")
    op.drop_table("fragrance_occasions")
    op.drop_index(op.f("ix_fragrance_notes_note_id"), table_name="fragrance_notes")
    op.drop_table("fragrance_notes")
    op.drop_index(op.f("ix_fragrance_families_family_id"), table_name="fragrance_families")
    op.drop_table("fragrance_families")
    op.drop_table("fragrance_embeddings")
    op.drop_index(op.f("ix_fragrance_accords_accord_id"), table_name="fragrance_accords")
    op.drop_table("fragrance_accords")
    op.drop_table("user_preferences")
    op.drop_index(op.f("ix_user_devices_user_id"), table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_pick_events_user_date", table_name="pick_events")
    op.drop_table("pick_events")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_fragrances_name_lower", table_name="fragrances")
    op.drop_index(op.f("ix_fragrances_brand_id"), table_name="fragrances")
    op.drop_table("fragrances")
    op.drop_table("users")
    op.drop_table("retailers")
    op.drop_table("occasions")
    op.drop_table("notes")
    op.drop_table("families")
    op.drop_table("brands")
    op.drop_table("accords")
