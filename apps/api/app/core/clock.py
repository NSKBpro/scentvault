"""Time helpers. "Today" is the user's local date, not the server's."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def now_utc() -> datetime:
    return datetime.now(UTC)


def user_today(tz: str | None) -> date:
    if tz:
        try:
            return datetime.now(ZoneInfo(tz)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return datetime.now(UTC).date()


def season_for(d: date, latitude: float | None = None) -> str:
    """Meteorological season; flipped for the southern hemisphere."""
    seasons = [
        "Winter",
        "Winter",
        "Spring",
        "Spring",
        "Spring",
        "Summer",
        "Summer",
        "Summer",
        "Fall",
        "Fall",
        "Fall",
        "Winter",
    ]
    s = seasons[d.month - 1]
    if latitude is not None and latitude < 0:
        s = {"Winter": "Summer", "Summer": "Winter", "Spring": "Fall", "Fall": "Spring"}[s]
    return s
