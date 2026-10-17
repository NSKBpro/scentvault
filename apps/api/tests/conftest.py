"""Test fixtures: a real Postgres (pgvector) database built by the Alembic baseline.

Set TEST_DATABASE_URL to point somewhere else; the database is wiped at the start.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://scentvault:scentvault@localhost:5432/scentvault_test"
)
os.environ.update(
    DATABASE_URL=os.environ["TEST_DATABASE_URL"],
    ENVIRONMENT="test",
    JWT_SECRET="test-" + "x" * 40,
    JOB_QUEUE="inline",
    EMBEDDING_PROVIDER="hashing",
    OLLAMA_ENABLED="false",
    PUSH_ENABLED="false",
    RATE_LIMIT_ENABLED="false",
    DEFAULT_CURRENCY="EUR",
    WEATHER_CACHE_MINUTES="0",
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.resources import Resources, build_resources  # noqa: E402
from app.services.weather import WeatherClient  # noqa: E402
from app.workers.queue import InlineQueue  # noqa: E402
from seeds.run import seed_demo, seed_reference  # noqa: E402

API = "/api"


class FakeWeather:
    """Controls what Open-Meteo 'returns' in tests."""

    def __init__(self) -> None:
        self.temp_c = 14.0
        self.code = 61  # rain

    def handler(self, request: httpx.Request) -> httpx.Response:
        if "geocoding" in str(request.url):
            name = request.url.params.get("name", "")
            if name.lower() == "atlantis":
                return httpx.Response(200, json={"results": []})
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "name": name.title(),
                            "latitude": 45.25,
                            "longitude": 19.84,
                            "timezone": "Europe/Belgrade",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": self.temp_c,
                    "apparent_temperature": self.temp_c - 1,
                    "weather_code": self.code,
                }
            },
        )


def _alembic_upgrade() -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def _database() -> AsyncIterator[None]:
    get_settings.cache_clear()
    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(text("DROP SCHEMA public CASCADE"))
        await s.execute(text("CREATE SCHEMA public"))
        await s.commit()
    await dispose_engine()
    # Alembic runs its own event loop; do it in a thread so it doesn't clash with ours.
    import anyio

    await anyio.to_thread.run_sync(_alembic_upgrade)
    async with get_sessionmaker()() as s:
        await seed_reference(s)
        await seed_demo(s)
    yield
    await dispose_engine()


@pytest.fixture(scope="session")
def weather() -> FakeWeather:
    return FakeWeather()


@pytest.fixture(scope="session")
async def resources(_database: None, weather: FakeWeather) -> AsyncIterator[Resources]:
    settings = get_settings()
    queue = InlineQueue()
    wc = WeatherClient(settings, transport=httpx.MockTransport(weather.handler))
    res = await build_resources(settings, queue=queue, weather=wc)
    await res.queue.enqueue("regenerate_embeddings", False)  # type: ignore[union-attr]
    await queue.drain()
    yield res
    await res.aclose()


@pytest.fixture(scope="session")
async def client(resources: Resources) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(get_settings(), resources)
    app.state.resources = resources  # ASGITransport doesn't run the lifespan
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def drain(resources: Resources):  # type: ignore[no-untyped-def]
    async def _drain() -> None:
        await resources.queue.drain()  # type: ignore[attr-defined]

    return _drain


async def _register(client: httpx.AsyncClient, **extra: Any) -> dict[str, Any]:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(f"{API}/auth/register", json={"email": email, "password": "password123", **extra})
    assert r.status_code == 201, r.text
    data = r.json()
    data["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
    data["email"] = email
    return data


@pytest.fixture
async def user(client: httpx.AsyncClient) -> dict[str, Any]:
    """A fresh user per test (isolated collection)."""
    return await _register(client)


@pytest.fixture
async def other_user(client: httpx.AsyncClient) -> dict[str, Any]:
    return await _register(client)


@pytest.fixture(scope="session")
async def admin(client: httpx.AsyncClient) -> dict[str, Any]:
    data = await _register(client)
    async with get_sessionmaker()() as s:
        await s.execute(text("UPDATE users SET role = 'admin' WHERE email = :e"), {"e": data["email"]})
        await s.commit()
    return data


async def fragrance_id(client: httpx.AsyncClient, name: str) -> int:
    r = await client.get(f"{API}/catalog/fragrances", params={"search": name, "size": 5})
    items = [i for i in r.json()["items"] if i["name"].lower() == name.lower()]
    assert items, f"{name} not in catalog"
    return int(items[0]["id"])
