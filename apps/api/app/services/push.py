"""Expo push notifications. Best-effort: failures are logged, never raised."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class PushClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.enabled = settings.PUSH_ENABLED
        self.url = settings.EXPO_PUSH_URL
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0), transport=transport)
        self.sent: list[dict[str, Any]] = []  # kept for tests / debugging

    async def aclose(self) -> None:
        await self._http.aclose()

    async def send(
        self, tokens: list[str], title: str, body: str, data: dict[str, Any] | None = None
    ) -> list[str]:
        """Send to Expo; returns tokens Expo reported as no longer registered."""
        if not tokens:
            return []
        messages = [
            {"to": t, "title": title, "body": body, "data": data or {}, "sound": "default"} for t in tokens
        ]
        self.sent.extend(messages)
        if not self.enabled:
            return []
        try:
            r = await self._http.post(self.url, json=messages, headers={"Accept": "application/json"})
            r.raise_for_status()
            tickets = r.json().get("data", [])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Expo push failed: %s", exc)
            return []
        dead: list[str] = []
        for token, ticket in zip(tokens, tickets, strict=False):
            if (
                ticket.get("status") == "error"
                and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered"
            ):
                dead.append(token)
        return dead
