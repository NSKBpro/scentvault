"""Currency conversion with static, configurable rates (USD base)."""

from __future__ import annotations

from app.core.config import get_settings


def rates() -> dict[str, float]:
    return dict(get_settings().CURRENCY_RATES)


def normalize(code: str | None) -> str:
    code = (code or get_settings().DEFAULT_CURRENCY).upper()
    if code not in rates():
        raise ValueError(f"Unsupported currency {code}; supported: {', '.join(sorted(rates()))}")
    return code


def to_usd(amount: float | None, currency: str) -> float | None:
    if amount is None:
        return None
    return float(amount) / rates()[normalize(currency)]


def from_usd(amount_usd: float | None, currency: str) -> float | None:
    if amount_usd is None:
        return None
    return round(float(amount_usd) * rates()[normalize(currency)], 2)


def convert(amount: float | None, src: str, dst: str) -> float | None:
    if amount is None:
        return None
    return from_usd(to_usd(amount, src), dst)
