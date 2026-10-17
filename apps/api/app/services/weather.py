"""Open-Meteo weather + geocoding (free, no API key), cached in memory."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# WMO weather codes → short label. https://open-meteo.com/en/docs
WMO = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow",
    80: "Showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}
RAINY = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


@dataclass
class Weather:
    city: str
    temp_c: float
    feels_like_c: float | None
    condition: str
    is_rainy: bool
    source: str = "open-meteo"


@dataclass
class GeoResult:
    name: str
    latitude: float
    longitude: float
    timezone: str | None


class WeatherClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.enabled = settings.WEATHER_ENABLED
        self.forecast_url = settings.WEATHER_BASE_URL
        self.geo_url = settings.GEOCODING_BASE_URL
        self.ttl = settings.WEATHER_CACHE_MINUTES * 60
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0), transport=transport)
        self._cache: dict[tuple[float, float], tuple[float, Weather]] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    async def geocode(self, city: str) -> GeoResult | None:
        if not self.enabled or not city.strip():
            return None
        try:
            r = await self._http.get(self.geo_url, params={"name": city, "count": 1, "format": "json"})
            r.raise_for_status()
            results = r.json().get("results") or []
        except (httpx.HTTPError, ValueError):
            logger.info("Geocoding failed for %r", city)
            return None
        if not results:
            return None
        top = results[0]
        return GeoResult(top["name"], float(top["latitude"]), float(top["longitude"]), top.get("timezone"))

    async def current(self, city: str, lat: float, lon: float) -> Weather | None:
        if not self.enabled:
            return None
        key = (round(lat, 2), round(lon, 2))
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        try:
            r = await self._http.get(
                self.forecast_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,weather_code",
                },
            )
            r.raise_for_status()
            cur = r.json()["current"]
        except (httpx.HTTPError, ValueError, KeyError):
            logger.info("Weather lookup failed for %s", city)
            return None
        code = int(cur.get("weather_code", 0))
        w = Weather(
            city=city,
            temp_c=float(cur["temperature_2m"]),
            feels_like_c=float(cur["apparent_temperature"])
            if cur.get("apparent_temperature") is not None
            else None,
            condition=WMO.get(code, "Unknown"),
            is_rainy=code in RAINY,
        )
        self._cache[key] = (time.monotonic(), w)
        return w
