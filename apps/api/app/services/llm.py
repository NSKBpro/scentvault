"""Async Ollama client. Every caller has a non-LLM fallback, so failures
return ``None`` instead of raising."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.enabled = settings.OLLAMA_ENABLED
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(settings.OLLAMA_TIMEOUT, connect=3.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def health(self) -> dict[str, Any]:
        if self.enabled:
            try:
                r = await self._http.get("/api/tags", timeout=3.0)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    hint = (
                        None if any(m.startswith(self.model) for m in models) else f"ollama pull {self.model}"
                    )
                    return {
                        "status": "connected",
                        "base_url": self.base_url,
                        "models": models,
                        "default_model": self.model,
                        "hint": hint,
                    }
            except (httpx.HTTPError, ValueError):
                pass
        return {
            "status": "disabled" if not self.enabled else "unavailable",
            "base_url": self.base_url,
            "models": [],
            "default_model": self.model,
            "hint": None if not self.enabled else "Start Ollama with: ollama serve",
        }

    async def generate(
        self, prompt: str, *, system: str = "", temperature: float = 0.7, json_mode: bool = False
    ) -> str | None:
        if not self.enabled:
            return None
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            body["system"] = system
        if json_mode:
            body["format"] = "json"
        try:
            r = await self._http.post("/api/generate", json=body)
            r.raise_for_status()
            return (r.json().get("response") or "").strip() or None
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("Ollama unavailable (%s); using fallback", type(exc).__name__)
            return None

    async def stream(self, prompt: str, *, system: str = "", temperature: float = 0.7) -> AsyncIterator[str]:
        if not self.enabled:
            return
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            body["system"] = system
        try:
            async with self._http.stream("POST", "/api/generate", json=body) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
        except (httpx.HTTPError, ValueError):
            return
