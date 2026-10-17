"""ScentVault API — application factory.

uvicorn app.main:app --reload --port 8004
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import limiter
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.resources import Resources, build_resources

logger = logging.getLogger("app")


def create_app(settings: Settings | None = None, resources: Resources | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        res = resources or await build_resources(settings)
        app.state.resources = res
        if settings.EMBEDDING_WARMUP and not settings.is_test:
            try:
                await res.embedder.warmup()  # load the model now, not on the first request
            except Exception:
                logger.exception("Embedding model warm-up failed; it will load on first use")
        logger.info(
            "ScentVault API ready (embeddings=%s, jobs=%s, llm=%s)",
            res.embedder.name,
            res.queue.name,
            "on" if res.llm.enabled else "off",
        )
        try:
            yield
        finally:
            if resources is None:
                await res.aclose()
                await dispose_engine()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.API_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"status": "online", "docs": f"{settings.API_PREFIX}/docs"}

    return app


app = create_app()
