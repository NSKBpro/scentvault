"""Similarity, recommendations, AI search, embeddings."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import Schema


class FragranceMatch(Schema):
    fragrance_id: int
    name: str
    brand_name: str
    concentration: str
    gender: str
    image_url: str | None
    similarity_pct: float
    min_price_usd: float | None
    families: list[str] = []


class DupeItem(FragranceMatch):
    """A cheaper alternative. Prices are compared per ml so sizes are fair."""

    size_ml: int
    price_usd: float
    price_per_ml_usd: float
    original_price_per_ml_usd: float
    savings_pct: float


class RecommendationItem(FragranceMatch):
    shared_notes: list[str] = []
    shared_accords: list[str] = []
    shared_families: list[str] = []
    reason: str


class CollectionDupe(Schema):
    original_id: int
    original_name: str
    original_brand: str
    original_price_per_ml_usd: float
    dupe: DupeItem


class EmbedQueryIn(Schema):
    text: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class AIIntent(Schema):
    notes: list[str] | None = None
    season: str | None = None
    occasion: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    gender: str | None = None
    mood: list[str] | None = None
    exclude_notes: list[str] | None = None
    search_text: str
    parsed_by: str = "rules"


class AISearchIn(Schema):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=20)
    # False = return results immediately; fetch the explanation via /ai/explain.
    explain: bool = False


class AISearchResult(FragranceMatch):
    top_notes: list[str] = []
    heart_notes: list[str] = []
    base_notes: list[str] = []
    accords: list[str] = []


class AISearchOut(Schema):
    intent: AIIntent
    results: list[AISearchResult]
    explanation: str | None
    timing_ms: dict[str, int]


class AIExplainIn(Schema):
    query: str = Field(min_length=2, max_length=500)
    fragrance_ids: list[int] = Field(min_length=1, max_length=10)


class AIExplainOut(Schema):
    explanation: str
    source: str  # "llm" | "template"


class OllamaHealth(Schema):
    status: str
    base_url: str
    models: list[str]
    default_model: str
    hint: str | None = None


class EmbeddingStatus(Schema):
    total_fragrances: int
    with_embedding: int
    missing: int
    stale: int
    other_model: int
    coverage_pct: float
    provider: str
    model_version: str
    last_generated_at: str | None
    job_queue: str


class EmbeddingGenerateIn(Schema):
    fragrance_id: int


class EmbeddingRegenerateIn(Schema):
    only_missing: bool = False


class EmbeddingResult(Schema):
    fragrance_id: int
    text_input: str
    model_version: str
    generated_at: str
