"""arq worker entry point:  ``arq app.workers.arq_worker.WorkerSettings``."""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.resources import build_resources
from app.workers.jobs import JOBS, daily_maintenance
from app.workers.queue import InlineQueue


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    settings = get_settings()
    # Inside the worker, jobs that enqueue more jobs just run them inline.
    res = await build_resources(settings, queue=InlineQueue())
    if settings.EMBEDDING_WARMUP:
        await res.embedder.warmup()
    ctx["resources"] = res


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["resources"].aclose()
    await dispose_engine()


class WorkerSettings:
    functions = list(JOBS.values())
    cron_jobs = [cron(daily_maintenance, hour={6}, minute={15}, run_at_startup=False)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    max_jobs = 4
    job_timeout = 1800
