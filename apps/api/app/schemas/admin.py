from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from app.core.constants import Role
from app.schemas.common import Schema


class WorkQueueItem(Schema):
    id: int
    name: str
    brand_name: str
    detail: str | None = None


class WorkQueue(Schema):
    key: str
    label: str
    count: int
    items: list[WorkQueueItem]


class AdminStats(Schema):
    counts: dict[str, int]
    embeddings_missing: int
    embeddings_stale: int
    new_users_7d: int
    price_logs_today: int
    queues: list[WorkQueue]


class AdminUserCreate(Schema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    role: Role = "user"


class AdminUserUpdate(Schema):
    email: EmailStr | None = None
    display_name: str | None = None
    role: Role | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserOut(Schema):
    id: uuid.UUID
    email: str
    display_name: str | None
    role: Role
    created_at: datetime
    collection_count: int = 0


class ImportPreviewRow(Schema):
    row_number: int
    data: dict[str, Any]
    status: str  # ok | warning | error
    messages: list[str]


class ImportPreviewOut(Schema):
    total_rows: int
    valid_rows: int
    warning_rows: int
    error_rows: int
    rows: list[ImportPreviewRow]
    session_data: str


class ImportConfirmIn(Schema):
    session_data: str
    skip_errors: bool = True


class ImportConfirmOut(Schema):
    inserted: int
    skipped: int
    errors: list[str]
    embeddings_queued: int


class HealthOut(Schema):
    status: str
    version: str
    database: str
    embedding_provider: str
    job_queue: str


class MetaOut(Schema):
    concentrations: list[str]
    genders: list[str]
    sillages: list[str]
    note_positions: list[str]
    radar_axes: list[str]
    collection_statuses: list[str]
    bottle_types: list[str]
    pick_occasions: list[str]
    currencies: dict[str, float]
    ml_per_spray: float
