"""Application settings — the single source of configuration.

Every module reads config through ``get_settings()``; nothing calls
``os.getenv`` directly. Values come from environment variables or ``.env``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class PickWeights(BaseSettings):
    """Daily-pick scoring weights. Tunable via env, e.g. PICK_WEIGHT_RATING=1.5."""

    model_config = SettingsConfigDict(env_prefix="PICK_WEIGHT_", extra="ignore")

    rating: float = 1.0  # per star above 3
    season: float = 1.5
    temperature: float = 1.5
    occasion: float = 1.5
    rotation: float = 0.12  # per day since last wear, capped
    rotation_cap_days: int = 21
    recent_penalty: float = 4.0  # worn in the last 3 days
    yesterday_penalty: float = 100.0  # never repeat yesterday
    low_remaining_penalty: float = 0.75  # under 10 %
    favorite: float = 0.5


class Settings(BaseSettings):
    # Root .env (shared with docker compose) first, then apps/api/.env overrides it.
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "ScentVault API"
    VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"
    API_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(..., description="postgresql+asyncpg://user:pass@host:5432/db")
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5

    # Security — JWT_SECRET is required and has no default on purpose.
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS: comma-separated list in env. Never "*" (credentials are allowed).
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Rate limits (slowapi syntax)
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_AI: str = "20/minute"
    RATE_LIMIT_ENABLED: bool = True

    # Redis / background jobs. When Redis is unreachable, jobs run in-process.
    REDIS_URL: str = "redis://localhost:6379/0"
    JOB_QUEUE: Literal["auto", "arq", "inline"] = "auto"

    # Embeddings
    EMBEDDING_PROVIDER: Literal["auto", "sentence-transformers", "hashing"] = "auto"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_WARMUP: bool = True

    # LLM (Ollama, optional — everything has a fallback)
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: float = 30.0

    # Weather (Open-Meteo — free, no key)
    WEATHER_ENABLED: bool = True
    WEATHER_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_BASE_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_CACHE_MINUTES: int = 30

    # Push notifications (Expo)
    PUSH_ENABLED: bool = True
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"

    # Money. Catalog prices are stored in USD; these rates convert for display.
    # Override with CURRENCY_RATES='{"EUR":0.92,"RSD":108}'.
    DEFAULT_CURRENCY: str = "EUR"
    CURRENCY_RATES: dict[str, float] = {"USD": 1.0, "EUR": 0.92, "RSD": 108.0, "GBP": 0.79}

    # Domain tuning
    ML_PER_SPRAY: float = 0.1
    ALERT_COOLDOWN_DAYS: int = 7
    RUNNING_LOW_PCT: int = 15
    NEGLECTED_DAYS: int = 60
    DUPE_MIN_SIMILARITY: float = 0.75
    DUPE_MAX_PRICE_RATIO: float = 0.6

    pick: PickWeights = Field(default_factory=PickWeights)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list) and "*" in v:
            raise ValueError("CORS_ORIGINS may not contain '*' (credentials are enabled)")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        if v.lower().startswith(("change-me", "changeme", "secret")):
            raise ValueError("JWT_SECRET looks like a placeholder; generate one with `openssl rand -hex 32`")
        return v

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
