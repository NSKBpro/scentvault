"""AI search: parse intent → embed → filtered vector search → (optional) explanation.

Results come back fast (no LLM on the hot path when ``explain=False``); the
explanation is a separate call so the app can show results immediately.
Works without Ollama: rule-based parsing + template explanation.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import currency
from app.repositories.vectors import VectorFilters
from app.services.embedding.provider import EmbeddingProvider
from app.services.llm import OllamaClient
from app.services.similarity import SimilarityService, genders_for

logger = logging.getLogger(__name__)

SEASONS = ("Spring", "Summer", "Fall", "Winter")
OCCASIONS = ("Office", "Date Night", "Casual", "Special Event", "Beach", "Evening", "Daily")
GENDERS = ("Masculine", "Feminine", "Unisex")

PARSE_SYSTEM = f"""You turn fragrance search requests into JSON. Extract only what is stated or clearly implied.
Fields (use null when absent):
- notes: list of fragrance notes (e.g. bergamot, vanilla, oud)
- season: one of {", ".join(SEASONS)}
- occasion: one of {", ".join(OCCASIONS)}
- budget_min, budget_max: numbers only (the user's currency)
- gender: one of {", ".join(GENDERS)}
- mood: list of vibe words (fresh, warm, cozy, dark, clean, sweet…)
- exclude_notes: notes the user does NOT want
- search_text: a short phrase of the scent descriptors, for semantic search
Respond with the JSON object only.
Example: "warm vanilla evening scent under 100, no patchouli" ->
{{"notes":["vanilla"],"season":null,"occasion":"Evening","budget_min":null,"budget_max":100,"gender":null,
"mood":["warm"],"exclude_notes":["patchouli"],"search_text":"warm vanilla evening fragrance"}}"""

EXPLAIN_SYSTEM = """You are ScentVault's fragrance advisor: friendly, concise, honest.
Explain in under 150 words, as flowing prose (no lists), why the listed fragrances fit the request.
Mention specific notes. Only talk about the fragrances listed; never invent others."""

_MOODS = (
    "fresh",
    "warm",
    "cozy",
    "sweet",
    "dark",
    "light",
    "clean",
    "spicy",
    "woody",
    "floral",
    "aquatic",
    "gourmand",
    "smoky",
    "powdery",
    "green",
    "citrus",
    "musky",
    "leathery",
    "fruity",
    "sexy",
    "elegant",
)
_OCC_WORDS = {
    "office": "Office",
    "work": "Office",
    "date": "Date Night",
    "casual": "Casual",
    "beach": "Beach",
    "evening": "Evening",
    "night out": "Evening",
    "daily": "Daily",
    "everyday": "Daily",
    "wedding": "Special Event",
    "special": "Special Event",
}


def rule_parse(q: str, known_notes: set[str]) -> dict[str, Any]:
    low = q.lower()
    out: dict[str, Any] = {
        "notes": None,
        "season": None,
        "occasion": None,
        "budget_min": None,
        "budget_max": None,
        "gender": None,
        "mood": None,
        "exclude_notes": None,
        "search_text": q.strip(),
        "parsed_by": "rules",
    }
    if m := re.search(r"(?:under|below|less than|max|<)\s*[$€£]?\s*(\d+)", low):
        out["budget_max"] = float(m.group(1))
    if m := re.search(r"[$€£]?(\d+)\s*(?:-|–|to)\s*[$€£]?(\d+)", low):
        out["budget_min"], out["budget_max"] = float(m.group(1)), float(m.group(2))
    for s in SEASONS:
        if s.lower() in low or (s == "Fall" and "autumn" in low):
            out["season"] = s
            break
    for word, occ in _OCC_WORDS.items():
        if re.search(rf"\b{re.escape(word)}", low):
            out["occasion"] = occ
            break
    if re.search(r"\b(masculine|for men|men's|male)\b", low):
        out["gender"] = "Masculine"
    elif re.search(r"\b(feminine|for women|women's|female)\b", low):
        out["gender"] = "Feminine"
    elif "unisex" in low:
        out["gender"] = "Unisex"
    excl: list[str] = []
    for m in re.finditer(r"\b(?:no|without|not|avoid)\s+([a-z][a-z \-]{1,30}?)(?=[,.;]|\band\b|$)", low):
        excl.append(m.group(1).strip())
    out["exclude_notes"] = excl or None
    excluded = " ".join(excl)
    found = [n for n in known_notes if re.search(rf"\b{re.escape(n)}\b", low) and n not in excluded]
    out["notes"] = sorted(found)[:8] or None
    moods = [w for w in _MOODS if re.search(rf"\b{w}", low)]
    out["mood"] = moods or None
    return out


class AISearchService:
    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider,
        llm: OllamaClient | None,
        user_currency: str = "USD",
        gender_pref: str | None = None,
    ):
        self.s = session
        self.provider = provider
        self.llm = llm
        self.currency = user_currency
        self.gender_pref = gender_pref
        self.sim = SimilarityService(session, provider)

    async def _known_notes(self) -> set[str]:
        rows = await self.s.execute(text("SELECT lower(name) FROM notes"))
        return set(rows.scalars())

    async def parse(self, query: str) -> dict[str, Any]:
        if self.llm is not None:
            raw = await self.llm.generate(
                f'Request: "{query}"', system=PARSE_SYSTEM, temperature=0.2, json_mode=True
            )
            if raw:
                try:
                    data = json.loads(raw)
                    intent = {
                        k: data.get(k)
                        for k in (
                            "notes",
                            "season",
                            "occasion",
                            "budget_min",
                            "budget_max",
                            "gender",
                            "mood",
                            "exclude_notes",
                        )
                    }
                    intent["search_text"] = (data.get("search_text") or query).strip()
                    intent["parsed_by"] = "llm"
                    return self._sanitize(intent)
                except (json.JSONDecodeError, AttributeError):
                    logger.info("LLM returned unparsable intent; falling back to rules")
        return self._sanitize(rule_parse(query, await self._known_notes()))

    @staticmethod
    def _sanitize(i: dict[str, Any]) -> dict[str, Any]:
        def str_list(v: Any) -> list[str] | None:
            if isinstance(v, str):
                v = [v]
            if not isinstance(v, list):
                return None
            items = [str(x).strip() for x in v if str(x).strip()]
            return items or None

        def num(v: Any) -> float | None:
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        i["notes"], i["mood"], i["exclude_notes"] = (
            str_list(i.get(k)) for k in ("notes", "mood", "exclude_notes")
        )
        i["season"] = i.get("season") if i.get("season") in SEASONS else None
        i["occasion"] = i.get("occasion") if i.get("occasion") in OCCASIONS else None
        i["gender"] = i.get("gender") if i.get("gender") in GENDERS else None
        i["budget_min"], i["budget_max"] = num(i.get("budget_min")), num(i.get("budget_max"))
        return i

    def _embed_text(self, intent: dict[str, Any]) -> str:
        bits = [intent["search_text"]]
        if intent.get("notes"):
            bits.append("Notes: " + ", ".join(intent["notes"]) + ".")
        if intent.get("mood"):
            bits.append(" ".join(intent["mood"]) + " fragrance.")
        return " ".join(bits)

    async def search(self, query: str, limit: int, explain: bool) -> dict[str, Any]:
        timing: dict[str, int] = {}
        t0 = time.perf_counter()
        intent = await self.parse(query)
        timing["parse"] = round((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        flt = VectorFilters(
            season=intent["season"],
            occasion=intent["occasion"],
            exclude_notes=intent["exclude_notes"],
            genders=[intent["gender"], "Unisex"]
            if intent["gender"] in ("Masculine", "Feminine")
            else genders_for(self.gender_pref),
            budget_min=currency.to_usd(intent["budget_min"], self.currency),
            budget_max=currency.to_usd(intent["budget_max"], self.currency),
            include_discontinued=False,
        )
        results = await self.sim.search_text(self._embed_text(intent), limit, flt)
        if not results and (flt.season or flt.occasion):
            # Filters too strict for the catalog: keep budget/gender/exclusions, relax the rest.
            flt.season = flt.occasion = None
            results = await self.sim.search_text(self._embed_text(intent), limit, flt)
        await self._enrich(results)
        timing["search"] = round((time.perf_counter() - t1) * 1000)

        explanation = None
        if explain:
            t2 = time.perf_counter()
            explanation, _ = await self.explain_results(query, results)
            timing["explain"] = round((time.perf_counter() - t2) * 1000)
        timing["total"] = round((time.perf_counter() - t0) * 1000)
        return {"intent": intent, "results": results, "explanation": explanation, "timing_ms": timing}

    async def _enrich(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        ids = [r["fragrance_id"] for r in rows]
        notes = await self.s.execute(
            text(
                "SELECT fn.fragrance_id, fn.position, n.name FROM fragrance_notes fn JOIN notes n ON n.id = fn.note_id "
                "WHERE fn.fragrance_id = ANY(:ids) ORDER BY fn.prominence DESC, n.name"
            ),
            {"ids": ids},
        )
        accords = await self.s.execute(
            text(
                "SELECT fa.fragrance_id, a.name FROM fragrance_accords fa JOIN accords a ON a.id = fa.accord_id "
                "WHERE fa.fragrance_id = ANY(:ids) ORDER BY a.name"
            ),
            {"ids": ids},
        )
        by_id = {r["fragrance_id"]: r for r in rows}
        for r in rows:
            r.update(top_notes=[], heart_notes=[], base_notes=[], accords=[])
        for fid, pos, name in notes.tuples():
            by_id[fid][f"{pos}_notes"].append(name)
        for fid, name in accords.tuples():
            by_id[fid]["accords"].append(name)

    async def explain(self, query: str, fragrance_ids: list[int]) -> tuple[str, str]:
        rows = await self.s.execute(
            text("""SELECT f.id AS fragrance_id, f.name, b.name AS brand_name, f.concentration, f.gender,
                    f.image_url, 0.0::float AS similarity_pct,
                    (SELECT MIN(price_usd)::float FROM fragrance_prices WHERE fragrance_id = f.id) AS min_price_usd
                    FROM fragrances f JOIN brands b ON b.id = f.brand_id WHERE f.id = ANY(:ids)"""),
            {"ids": fragrance_ids},
        )
        found = {r["fragrance_id"]: dict(r) for r in rows.mappings()}
        ordered = [found[i] for i in fragrance_ids if i in found]
        await self._enrich(ordered)
        return await self.explain_results(query, ordered)

    async def explain_results(self, query: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        if not results:
            return (
                "Nothing in the catalog matched that. Try fewer constraints or different words.",
                "template",
            )
        top = results[:5]
        if self.llm is not None:
            lines = []
            for i, r in enumerate(top, 1):
                notes = "; ".join(
                    f"{k.split('_')[0]}: {', '.join(r.get(k, [])[:5])}"
                    for k in ("top_notes", "heart_notes", "base_notes")
                    if r.get(k)
                )
                lines.append(f"{i}. {r['brand_name']} — {r['name']} ({r['concentration']}) | {notes}")
            prompt = f'The user asked: "{query}"\nMatches:\n' + "\n".join(lines)
            text_out = await self.llm.generate(prompt, system=EXPLAIN_SYSTEM, temperature=0.6)
            # Accept the LLM text only if it talks about at least one of our results.
            if text_out and any(r["name"].lower().split()[0] in text_out.lower() for r in top):
                return text_out, "llm"
        return self._template(query, top), "template"

    @staticmethod
    def _template(query: str, top: list[dict[str, Any]]) -> str:
        parts = []
        for r in top[:3]:
            notes = (r.get("top_notes") or [])[:2] + (r.get("base_notes") or [])[:2]
            detail = f" — {', '.join(notes).lower()}" if notes else ""
            parts.append(f"{r['brand_name']} {r['name']}{detail}")
        return f"Closest matches for “{query}”: " + "; ".join(parts) + "."
