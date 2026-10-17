"""Background job queue.

* ``ArqQueue`` — jobs go to Redis and run in the ``arq`` worker process
  (``make worker``). This is the default when Redis is reachable.
* ``InlineQueue`` — jobs run as asyncio tasks inside the API process. Used
  when Redis is down (dev without Docker) and in tests; ``drain()`` waits
  for everything queued so far.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol

from app.core.config import Settings

if TYPE_CHECKING:
    from app.resources import Resources

logger = logging.getLogger(__name__)


class JobQueue(Protocol):
    name: str

    async def enqueue(self, job: str, *args: Any) -> str | None: ...
    async def aclose(self) -> None: ...


class InlineQueue:
    name = "inline"

    def __init__(self) -> None:
        self.resources: Resources | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    async def enqueue(self, job: str, *args: Any) -> str | None:
        from app.workers.jobs import JOBS

        if self.resources is None:
            raise RuntimeError("InlineQueue used before resources were attached")
        fn = JOBS[job]
        ctx = {"resources": self.resources}

        async def run() -> None:
            try:
                await fn(ctx, *args)  # type: ignore[operator]
            except Exception:
                logger.exception("Inline job %s failed", job)

        task = asyncio.create_task(run(), name=f"job:{job}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return None

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def aclose(self) -> None:
        await self.drain()


class ArqQueue:
    name = "arq"

    def __init__(self, pool: Any):
        self._pool = pool

    async def enqueue(self, job: str, *args: Any) -> str | None:
        j = await self._pool.enqueue_job(job, *args)
        return j.job_id if j else None

    async def aclose(self) -> None:
        await self._pool.aclose()


async def build_queue(settings: Settings) -> JobQueue:
    if settings.JOB_QUEUE == "inline":
        return InlineQueue()
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        rs = RedisSettings.from_dsn(settings.REDIS_URL)
        rs.conn_timeout = 2
        rs.conn_retries = 0
        pool = await asyncio.wait_for(create_pool(rs), timeout=3)
        await pool.ping()
        return ArqQueue(pool)
    except Exception as exc:
        if settings.JOB_QUEUE == "arq":
            raise
        logger.warning("Redis unavailable (%s); background jobs will run in-process", type(exc).__name__)
        return InlineQueue()
