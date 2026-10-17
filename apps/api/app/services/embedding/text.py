"""Deterministic text template for fragrance embeddings.

Sections without data are omitted; every list is sorted, so the same
fragrance always produces the same text (stored as ``text_input``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmbeddingSource:
    families: list[str] = field(default_factory=list)
    top: list[str] = field(default_factory=list)
    heart: list[str] = field(default_factory=list)
    base: list[str] = field(default_factory=list)
    accords: list[str] = field(default_factory=list)
    seasons: list[str] = field(default_factory=list)
    occasions: list[str] = field(default_factory=list)
    sillage: str | None = None
    longevity_hours: float | None = None
    gender: str | None = None


SEASON_ORDER = ("Spring", "Summer", "Fall", "Winter")


def build_embedding_text(src: EmbeddingSource) -> str:
    parts: list[str] = []
    fams = sorted(src.families)
    parts.append(f"{' '.join(fams)} fragrance." if fams else "Fragrance.")
    for label, notes in (("Top", src.top), ("Heart", src.heart), ("Base", src.base)):
        if notes:
            parts.append(f"{label} notes: {', '.join(sorted(notes))}.")
    if src.accords:
        parts.append(f"Accords: {', '.join(sorted(src.accords))}.")
    best_for = [s for s in SEASON_ORDER if s in src.seasons] + sorted(src.occasions)
    if best_for:
        parts.append(f"Best for: {', '.join(best_for)}.")
    if src.sillage:
        parts.append(f"Sillage: {src.sillage}.")
    if src.longevity_hours is not None:
        h = float(src.longevity_hours)
        parts.append(f"Longevity: {int(h) if h == int(h) else round(h, 1)} hours.")
    return " ".join(parts)


def source_from_fragrance(f) -> EmbeddingSource:  # type: ignore[no-untyped-def]
    """Build from a Fragrance ORM object with notes/families/accords/occasions loaded."""
    src = EmbeddingSource(
        families=[x.name for x in f.families],
        accords=[x.name for x in f.accords],
        occasions=[x.name for x in f.occasions],
        sillage=f.sillage,
        longevity_hours=f.longevity_hours,
        gender=f.gender,
    )
    for fn in f.notes:
        getattr(src, fn.position).append(fn.note.name)
    src.seasons = [
        s
        for s, on in zip(
            SEASON_ORDER, (f.season_spring, f.season_summer, f.season_fall, f.season_winter), strict=True
        )
        if on
    ]
    return src
