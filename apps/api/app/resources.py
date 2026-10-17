"""Long-lived resources shared by the API and the worker.

Built once in the FastAPI lifespan (or the arq ``on_startup``) and handed to
services through dependencies — the composition root of the app.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.services.embedding.provider import EmbeddingProvider, build_provider
from app.services.llm import OllamaClient
from app.services.push import PushClient
from app.services.weather import WeatherClient
from app.workers.queue import InlineQueue, JobQueue, build_queue

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    settings: Settings
    embedder: EmbeddingProvider
    llm: OllamaClient
    weather: WeatherClient
    push: PushClient
    queue: JobQueue

    async def aclose(self) -> None:
        await self.queue.aclose()
        await self.llm.aclose()
        await self.weather.aclose()
        await self.push.aclose()


async def build_resources(
    settings: Settings,
    *,
    queue: JobQueue | None = None,
    embedder: EmbeddingProvider | None = None,
    llm: OllamaClient | None = None,
    weather: WeatherClient | None = None,
    push: PushClient | None = None,
) -> Resources:
    res = Resources(
        settings=settings,
        embedder=embedder or build_provider(settings),
        llm=llm or OllamaClient(settings),
        weather=weather or WeatherClient(settings),
        push=push or PushClient(settings),
        queue=queue or await build_queue(settings),
    )
    if isinstance(res.queue, InlineQueue):
        res.queue.resources = res
    return res
