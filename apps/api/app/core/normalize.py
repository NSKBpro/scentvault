"""Lenient parsing of catalog vocab from CSV imports and the legacy database."""

from __future__ import annotations

import math
import re

from app.core.constants import CONCENTRATIONS, GENDERS, SILLAGES

_CONC_ALIASES = {
    "eau de toilette": "EDT",
    "edt": "EDT",
    "toilette": "EDT",
    "eau de parfum": "EDP",
    "edp": "EDP",
    "parfum": "Parfum",
    "perfume": "Parfum",
    "pure parfum": "Parfum",
    "extrait": "Extrait",
    "extrait de parfum": "Extrait",
    "extract": "Extrait",
    "cologne": "Cologne",
    "eau de cologne": "Cologne",
    "edc": "Cologne",
    "elixir": "Elixir",
    "body mist": "Body Mist",
    "mist": "Body Mist",
    "hair mist": "Hair Mist",
}
_GENDER_ALIASES = {
    "masculine": "Masculine",
    "male": "Masculine",
    "men": "Masculine",
    "man": "Masculine",
    "m": "Masculine",
    "pour homme": "Masculine",
    "feminine": "Feminine",
    "female": "Feminine",
    "women": "Feminine",
    "woman": "Feminine",
    "f": "Feminine",
    "pour femme": "Feminine",
    "unisex": "Unisex",
    "u": "Unisex",
    "shared": "Unisex",
}
_SILLAGE_ALIASES = {
    "intimate": "Intimate",
    "weak": "Intimate",
    "soft": "Soft",
    "light": "Soft",
    "moderate": "Moderate",
    "medium": "Moderate",
    "strong": "Strong",
    "heavy": "Strong",
    "enormous": "Enormous",
    "beast": "Enormous",
}
_POSITION_ALIASES = {
    "top": "top",
    "head": "top",
    "heart": "heart",
    "middle": "heart",
    "mid": "heart",
    "base": "base",
    "bottom": "base",
}


def _key(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower().replace("_", " "))


def concentration(v: object, default: str | None = None) -> str | None:
    k = _key(v)
    if not k:
        return default
    for c in CONCENTRATIONS:
        if k == c.lower():
            return c
    return _CONC_ALIASES.get(k, default)


def gender(v: object, default: str | None = None) -> str | None:
    k = _key(v)
    if not k:
        return default
    for g in GENDERS:
        if k == g.lower():
            return g
    return _GENDER_ALIASES.get(k, default)


def sillage(v: object, default: str | None = None) -> str | None:
    k = _key(v)
    if not k:
        return default
    for s in SILLAGES:
        if k == s.lower():
            return s
    return _SILLAGE_ALIASES.get(k, default)


def position(v: object) -> str | None:
    return _POSITION_ALIASES.get(_key(v))


def prominence(v: object) -> int:
    """Old data used 1–5 and 0–100 scales; fold both into 1–5 (50 → 3)."""
    try:
        n = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 3
    if n > 5:
        n = 1 + min(n, 100) / 100 * 4
    return int(min(5, max(1, math.floor(n + 0.5))))


AXIS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "woody": ("wood", "chypre", "moss", "leather", "oud", "vetiver", "cedar", "sandal"),
    "citrus": ("citrus", "hesperid", "cologne"),
    "aromatic": ("aromatic", "fougère", "fougere", "herb", "lavender"),
    "oriental": ("oriental", "amber", "spic", "gourmand", "balsam", "vanilla", "resin", "tobacco", "sweet"),
    "fresh": ("fresh", "aquatic", "marine", "ozon", "green", "water"),
    "floral": ("floral", "rose", "flower", "powder", "fruity", "white floral", "iris"),
}


def axis_for_family(name: str) -> str | None:
    low = name.lower()
    for axis, kws in AXIS_KEYWORDS.items():
        if any(k in low for k in kws):
            return axis
    return None
