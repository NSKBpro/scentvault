"""Embedding providers.

* ``SentenceTransformerProvider`` — the real model (all-MiniLM-L6-v2, 384-d).
  Needs the optional ``ml`` extra (``pip install -e .[ml]``).
* ``HashingProvider`` — deterministic feature-hashing fallback with the same
  dimension. No dependencies, instant, good enough for tests and for running
  the app without torch; similarity quality is much lower.

``encode`` is always async and runs the model in a worker thread, so the
event loop is never blocked.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Protocol

import anyio
import numpy as np

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    name: str
    model_version: str
    dim: int

    async def encode(self, text: str) -> list[float]: ...
    async def encode_many(self, texts: list[str]) -> list[list[float]]: ...
    async def warmup(self) -> None: ...


class HashingProvider:
    name = "hashing"

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.model_version = f"hashing-v1-{dim}"

    _token = re.compile(r"[a-zà-ÿ0-9]+")

    def _features(self, text: str) -> list[str]:
        low = text.lower()
        words = self._token.findall(low)
        feats = list(words)
        feats += [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
        # Phrases between punctuation ("tonka bean", "white musk") as whole features.
        feats += [p.strip() for p in re.split(r"[.,;:]", low) if 0 < len(p.strip().split()) <= 3]
        return feats

    def _encode_sync(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for f in self._features(text):
            h = hashlib.blake2b(f.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.tolist()

    async def encode(self, text: str) -> list[float]:
        return self._encode_sync(text)

    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        return [self._encode_sync(t) for t in texts]

    async def warmup(self) -> None:
        return None


class SentenceTransformerProvider:
    name = "sentence-transformers"

    def __init__(self, model_name: str, dim: int = 384):
        self.model_version = model_name
        self.dim = dim
        self._model = None
        self._lock = anyio.Lock()

    def _load(self):  # type: ignore[no-untyped-def]
        from sentence_transformers import SentenceTransformer

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:  # pragma: no cover
            device = "cpu"
        t0 = time.perf_counter()
        model = SentenceTransformer(self.model_version, device=device)
        logger.info("Loaded %s on %s in %.1fs", self.model_version, device, time.perf_counter() - t0)
        return model

    async def _get(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            async with self._lock:
                if self._model is None:
                    self._model = await anyio.to_thread.run_sync(self._load)
        return self._model

    async def encode(self, text: str) -> list[float]:
        return (await self.encode_many([text]))[0]

    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        model = await self._get()

        def run() -> list[list[float]]:
            arr = model.encode(texts, normalize_embeddings=True, batch_size=32)
            return [row.astype(np.float32).tolist() for row in arr]

        out = await anyio.to_thread.run_sync(run)
        if out and len(out[0]) != self.dim:
            raise RuntimeError(f"Model returned {len(out[0])}-d vectors, expected {self.dim}")
        return out

    async def warmup(self) -> None:
        await self._get()


def build_provider(settings: Settings) -> EmbeddingProvider:
    choice = settings.EMBEDDING_PROVIDER
    if choice in ("auto", "sentence-transformers"):
        try:
            import sentence_transformers  # noqa: F401

            return SentenceTransformerProvider(settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM)
        except ImportError:
            if choice == "sentence-transformers":
                raise
            logger.warning(
                "sentence-transformers is not installed; using the hashing embedder. "
                "Install the 'ml' extra for real semantic similarity."
            )
    return HashingProvider(settings.EMBEDDING_DIM)


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in vec) + "]"
