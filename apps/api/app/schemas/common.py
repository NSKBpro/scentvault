from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    # Responses always include every field, so the generated TS types mark them required.
    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)


class Page[T](Schema):
    items: list[T]
    total: int
    page: int
    size: int


class Message(Schema):
    detail: str


class CountOut(Schema):
    count: int


class RefOut(Schema):
    id: int
    name: str


class JobAccepted(Schema):
    status: str
    detail: str
    job_id: str | None = None
