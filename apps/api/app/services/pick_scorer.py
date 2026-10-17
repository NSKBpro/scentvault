"""Daily-pick scoring — pure functions, no I/O, unit-tested directly.

Each candidate gets a score from weighted signals; every signal that moved
the score produces a human-readable reason chip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.core.config import PickWeights
from app.core.constants import FRESH_KEYWORDS, PICK_OCCASION_MATCHES, WARM_KEYWORDS

HOT_C = 24.0
WARM_C = 18.0
COLD_C = 10.0


@dataclass
class Candidate:
    collection_item_id: int
    fragrance_id: int
    name: str
    brand: str
    rating: float | None = None
    remaining_pct: int = 100
    is_favorite: bool = False
    sillage: str | None = None
    seasons: set[str] = field(default_factory=set)  # {"Spring", ...}
    occasions: set[str] = field(default_factory=set)  # catalog occasion names
    traits: set[str] = field(default_factory=set)  # lower-case families + accords
    last_worn_on: date | None = None


@dataclass
class Context:
    today: date
    season: str
    occasion: str
    temp_c: float | None = None
    is_rainy: bool = False
    condition: str | None = None


@dataclass
class Chip:
    label: str
    kind: str
    positive: bool
    weight: float


@dataclass
class Scored:
    candidate: Candidate
    score: float
    chips: list[Chip]


def _matches(traits: set[str], keywords: tuple[str, ...]) -> bool:
    return any(k in t for t in traits for k in keywords)


def score(c: Candidate, ctx: Context, w: PickWeights) -> Scored:
    chips: list[Chip] = []

    def add(value: float, label: str, kind: str) -> None:
        if abs(value) > 1e-9:
            chips.append(Chip(label, kind, value > 0, value))

    # Rating
    if c.rating is not None:
        add((float(c.rating) - 3.0) * w.rating, f"You rated it {float(c.rating):g}★", "rating")

    # Season
    if c.seasons:
        if ctx.season in c.seasons:
            add(w.season, f"Made for {ctx.season.lower()}", "season")
        else:
            add(-w.season * 0.5, f"More of a {'/'.join(sorted(c.seasons)).lower()} scent", "season")

    # Weather
    fresh = _matches(c.traits, FRESH_KEYWORDS)
    warm = _matches(c.traits, WARM_KEYWORDS)
    if ctx.temp_c is not None:
        t = round(ctx.temp_c)
        wx = f"{t}°C" + (" and rainy" if ctx.is_rainy else "")
        if ctx.temp_c >= HOT_C:
            if fresh and not warm:
                add(w.temperature, f"{wx} — fresh suits the heat", "weather")
            elif warm and not fresh:
                add(-w.temperature, f"Heavy for {t}°C", "weather")
            if c.sillage in ("Strong", "Enormous"):
                add(-w.temperature * 0.4, "Loud sillage in the heat", "weather")
        elif ctx.temp_c <= COLD_C:
            if warm:
                add(w.temperature, f"{wx} — warm notes shine", "weather")
            elif fresh:
                add(-w.temperature * 0.5, f"Light for {t}°C", "weather")
        elif ctx.temp_c >= WARM_C and fresh:
            add(w.temperature * 0.5, f"{wx} — mild and fresh", "weather")
        elif warm and ctx.is_rainy:
            add(w.temperature * 0.5, f"{wx} — cosy weather", "weather")

    # Occasion
    wanted = PICK_OCCASION_MATCHES.get(ctx.occasion, (ctx.occasion,))
    if c.occasions & set(wanted):
        add(w.occasion, f"Good for {ctx.occasion.lower()}", "occasion")
    if ctx.occasion in ("Office", "Gym") and c.sillage in ("Strong", "Enormous"):
        add(-w.occasion * 0.6, f"Strong sillage for the {ctx.occasion.lower()}", "occasion")
    if ctx.occasion in ("Date Night", "Evening") and c.sillage in ("Strong", "Enormous"):
        add(w.occasion * 0.3, "Projects well", "occasion")

    # Rotation and recency
    if c.last_worn_on is None:
        add(w.rotation * w.rotation_cap_days, "Not worn yet", "rotation")
    else:
        days = (ctx.today - c.last_worn_on).days
        if days <= 0:
            add(-w.recent_penalty, "Worn today", "recent")
        elif days == 1:
            add(-w.yesterday_penalty, "Worn yesterday", "recent")
        elif days <= 3:
            add(-w.recent_penalty, f"Worn {days} days ago", "recent")
        else:
            bonus = w.rotation * min(days, w.rotation_cap_days)
            label = f"Not worn in {days // 7} weeks" if days >= 14 else f"Not worn in {days} days"
            add(bonus, label, "rotation")

    if c.remaining_pct < 10:
        add(-w.low_remaining_penalty, f"Only {c.remaining_pct}% left", "low")
    if c.is_favorite:
        add(w.favorite, "A favourite", "favorite")

    total = round(sum(ch.weight for ch in chips), 3)
    chips.sort(key=lambda ch: -abs(ch.weight))
    return Scored(c, total, chips)


def rank(candidates: list[Candidate], ctx: Context, w: PickWeights, top: int = 3) -> list[Scored]:
    scored = [score(c, ctx, w) for c in candidates]
    scored.sort(key=lambda s: (-s.score, -(s.candidate.rating or 0), s.candidate.name))
    return scored[:top]
