from __future__ import annotations

import logging

from app.core.config import get_settings


def configure_logging() -> None:
    level = get_settings().LOG_LEVEL.upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
