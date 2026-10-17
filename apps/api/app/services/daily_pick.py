"""Daily pick: weather + occasion + rotation aware, top 3 with reason chips.

The LLM only turns the top pick's chips into one sentence, and that sentence
is rejected unless it names the picked fragrance (no hallucinated bottles).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import season_for, user_today
from app.core.config import get_settings
from app.core.errors import NotFound
from app.models import CollectionItem, Fragrance, PickEvent, UserPreferences
from app.repositories.collection import CollectionRepository
from app.schemas.wear import PickAcceptIn, WearIn
from app.services.llm import OllamaClient
from app.services.pick_scorer import Candidate, Context, Scored, rank
from app.services.wear import WearService
from app.services.weather import Weather, WeatherClient

logger = logging.getLogger(__name__)

PICK_SYSTEM = (
    "You are a personal fragrance advisor. Write ONE warm sentence (max 30 words) recommending the "
    "fragrance named in the prompt for today, using only the reasons given. Never mention any other fragrance."
)


def default_occasion(d: date) -> str:
    return "Office" if d.weekday() < 5 else "Casual"


class DailyPickService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        prefs: UserPreferences,
        weather: WeatherClient | None,
        llm: OllamaClient | None,
    ):
        self.s = session
        self.user_id = user_id
        self.prefs = prefs
        self.weather = weather
        self.llm = llm
        self.settings = get_settings()

    async def _weather(self) -> Weather | None:
        p = self.prefs
        if self.weather and p.city and p.latitude is not None and p.longitude is not None:
            return await self.weather.current(p.city, p.latitude, p.longitude)
        return None

    async def _candidates(self) -> list[Candidate]:
        items = (
            (
                await self.s.execute(
                    select(CollectionItem)
                    .options(
                        selectinload(CollectionItem.fragrance).selectinload(Fragrance.families),
                        selectinload(CollectionItem.fragrance).selectinload(Fragrance.accords),
                        selectinload(CollectionItem.fragrance).selectinload(Fragrance.occasions),
                        selectinload(CollectionItem.fragrance).selectinload(Fragrance.brand),
                    )
                    .where(
                        CollectionItem.user_id == self.user_id,
                        CollectionItem.status == "own",
                        CollectionItem.remaining_pct > 0,
                    )
                )
            )
            .scalars()
            .all()
        )
        last = await CollectionRepository(self.s).last_worn_by_item(self.user_id)
        out = []
        for it in items:
            f = it.fragrance
            seasons = {
                s
                for s, on in (
                    ("Spring", f.season_spring),
                    ("Summer", f.season_summer),
                    ("Fall", f.season_fall),
                    ("Winter", f.season_winter),
                )
                if on
            }
            out.append(
                Candidate(
                    collection_item_id=it.id,
                    fragrance_id=f.id,
                    name=f.name,
                    brand=f.brand.name,
                    rating=it.rating,
                    remaining_pct=it.remaining_pct,
                    is_favorite=it.is_favorite,
                    sillage=f.sillage,
                    seasons=seasons,
                    occasions={o.name for o in f.occasions},
                    traits={x.name.lower() for x in f.families} | {x.name.lower() for x in f.accords},
                    last_worn_on=last.get(it.id),
                )
            )
        return out

    async def _sentence(self, top: Scored, ctx: Context) -> tuple[str, str]:
        c = top.candidate
        positives = [ch.label for ch in top.chips if ch.positive][:3]
        fallback = f"{c.brand} {c.name}" + (
            f" — {', '.join(positives).lower()}." if positives else " is a solid pick today."
        )
        if not self.llm:
            return fallback, "template"
        prompt = (
            f"Fragrance: {c.brand} {c.name}\nOccasion: {ctx.occasion}\nSeason: {ctx.season}\n"
            f"Reasons: {'; '.join(positives) or 'versatile choice'}"
        )
        text = await self.llm.generate(prompt, system=PICK_SYSTEM, temperature=0.6)
        if text:
            text = text.strip().strip('"').strip()
            name_hit = c.name.lower().split()[0] in text.lower() or c.brand.lower().split()[0] in text.lower()
            if name_hit and len(text) < 400:
                return text, "llm"
            logger.info("Discarded pick sentence that didn't name %s %s", c.brand, c.name)
        return fallback, "template"

    async def get(self, occasion: str | None, top: int = 3) -> dict[str, Any]:
        today = user_today(self.prefs.timezone)
        occ = occasion or default_occasion(today)
        season = season_for(today, self.prefs.latitude)
        wx = await self._weather()
        ctx = Context(
            today=today,
            season=season,
            occasion=occ,
            temp_c=wx.temp_c if wx else None,
            is_rainy=wx.is_rainy if wx else False,
            condition=wx.condition if wx else None,
        )
        cands = await self._candidates()
        worn_today = await WearService(self.s, self.user_id, self.prefs.timezone).worn_today()
        if not cands:
            return {
                "date": today,
                "occasion": occ,
                "season": season,
                "weather": wx.__dict__ if wx else None,
                "picks": [],
                "sentence": None,
                "sentence_source": "none",
                "worn_today": worn_today,
            }
        ranked = rank(cands, ctx, self.settings.pick, top=top)
        sentence, source = await self._sentence(ranked[0], ctx)
        picks = [
            {
                "rank": i + 1,
                "collection_item_id": r.candidate.collection_item_id,
                "fragrance_id": r.candidate.fragrance_id,
                "fragrance_name": r.candidate.name,
                "brand_name": r.candidate.brand,
                "concentration": "",
                "image_url": None,
                "remaining_pct": r.candidate.remaining_pct,
                "score": r.score,
                "reasons": [
                    {"label": ch.label, "kind": ch.kind, "positive": ch.positive} for ch in r.chips[:4]
                ],
                "last_worn_on": r.candidate.last_worn_on,
            }
            for i, r in enumerate(ranked)
        ]
        await self._fill_display(picks)
        await self._log_shown(today, occ, picks)
        return {
            "date": today,
            "occasion": occ,
            "season": season,
            "weather": wx.__dict__ if wx else None,
            "picks": picks,
            "sentence": sentence,
            "sentence_source": source,
            "worn_today": worn_today,
        }

    async def _fill_display(self, picks: list[dict[str, Any]]) -> None:
        rows = await self.s.execute(
            select(Fragrance.id, Fragrance.concentration, Fragrance.image_url).where(
                Fragrance.id.in_([p["fragrance_id"] for p in picks])
            )
        )
        info = {i: (c, img) for i, c, img in rows.tuples()}
        for p in picks:
            p["concentration"], p["image_url"] = info.get(p["fragrance_id"], ("", None))

    async def _log_shown(self, today: date, occ: str, picks: list[dict[str, Any]]) -> None:
        exists = await self.s.scalar(
            select(PickEvent.id)
            .where(
                PickEvent.user_id == self.user_id,
                PickEvent.kind == "shown",
                PickEvent.pick_date == today,
                PickEvent.occasion == occ,
            )
            .limit(1)
        )
        if exists:
            return
        self.s.add(
            PickEvent(
                user_id=self.user_id,
                kind="shown",
                pick_date=today,
                occasion=occ,
                payload={
                    "picks": [
                        {
                            "collection_item_id": p["collection_item_id"],
                            "rank": p["rank"],
                            "score": p["score"],
                        }
                        for p in picks
                    ]
                },
            )
        )
        await self.s.commit()

    async def accept(self, data: PickAcceptIn) -> tuple[dict[str, Any], CollectionItem | None]:
        item = await self.s.scalar(
            select(CollectionItem).where(
                CollectionItem.id == data.collection_item_id, CollectionItem.user_id == self.user_id
            )
        )
        if item is None:
            raise NotFound("Collection item")
        today = user_today(self.prefs.timezone)
        wx = await self._weather()
        wear, bottle, _ = await WearService(
            self.s, self.user_id, self.prefs.timezone, self.prefs.currency
        ).log(
            WearIn(
                collection_item_id=item.id,
                sprays=data.sprays,
                occasion=data.occasion,
                temp_c=wx.temp_c if wx else None,
            )
        )
        self.s.add(
            PickEvent(
                user_id=self.user_id,
                kind="accepted",
                pick_date=today,
                occasion=data.occasion,
                collection_item_id=item.id,
                rank=data.rank,
                payload={"wear_id": wear["id"]},
            )
        )
        await self.s.commit()
        return wear, bottle
