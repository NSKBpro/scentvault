"""Domain vocabularies.

These are the single source of truth: the DB uses VARCHAR + CHECK constraints
built from them, Pydantic schemas use the Literal types, and the clients get
them through the generated api-types package and ``GET /api/meta``.
"""

from __future__ import annotations

from typing import Literal, get_args

Concentration = Literal["EDT", "EDP", "Parfum", "Extrait", "Cologne", "Elixir", "Body Mist", "Hair Mist"]
Gender = Literal["Masculine", "Feminine", "Unisex"]
Sillage = Literal["Intimate", "Soft", "Moderate", "Strong", "Enormous"]
NotePosition = Literal["top", "heart", "base"]
RadarAxis = Literal["woody", "citrus", "aromatic", "oriental", "fresh", "floral"]
CollectionStatus = Literal["own", "wishlist", "tried", "finished", "sold", "gifted"]
BottleType = Literal["full", "decant", "sample", "tester"]
PickOccasion = Literal["Office", "Date Night", "Casual", "Gym", "Evening"]
GenderPreference = Literal["Masculine", "Feminine", "Unisex", "Any"]
Role = Literal["user", "admin"]
NotificationKind = Literal["price_alert", "running_low", "neglected", "system"]

CONCENTRATIONS: tuple[str, ...] = get_args(Concentration)
GENDERS: tuple[str, ...] = get_args(Gender)
SILLAGES: tuple[str, ...] = get_args(Sillage)
NOTE_POSITIONS: tuple[str, ...] = get_args(NotePosition)
RADAR_AXES: tuple[str, ...] = get_args(RadarAxis)
COLLECTION_STATUSES: tuple[str, ...] = get_args(CollectionStatus)
BOTTLE_TYPES: tuple[str, ...] = get_args(BottleType)
PICK_OCCASIONS: tuple[str, ...] = get_args(PickOccasion)
GENDER_PREFERENCES: tuple[str, ...] = get_args(GenderPreference)
ROLES: tuple[str, ...] = get_args(Role)
NOTIFICATION_KINDS: tuple[str, ...] = get_args(NotificationKind)

# Statuses that count as "on the shelf" for stats, Scent DNA and picks.
SHELF_STATUSES = ("own",)
# Statuses that inform taste (Scent DNA, recommendations).
TASTE_STATUSES = ("own", "tried", "finished")
ARCHIVE_STATUSES = ("finished", "sold", "gifted")

# Catalog occasion names that satisfy each daily-pick occasion.
PICK_OCCASION_MATCHES: dict[str, tuple[str, ...]] = {
    "Office": ("Office", "Daily"),
    "Date Night": ("Date Night", "Evening", "Special Event"),
    "Casual": ("Casual", "Daily", "Beach"),
    "Gym": ("Gym", "Sport", "Casual"),
    "Evening": ("Evening", "Special Event", "Date Night"),
}

# Families/accords that suit warm vs. cold weather (lower-case keywords).
FRESH_KEYWORDS = ("citrus", "aquatic", "fresh", "green", "marine", "ozonic", "aromatic", "fougère", "fougere")
WARM_KEYWORDS = ("oriental", "amber", "gourmand", "woody", "leather", "spicy", "vanilla", "oud", "balsamic")


def sql_in(values: tuple[str, ...]) -> str:
    """Render a tuple as a SQL IN-list literal for CHECK constraints."""
    return "(" + ", ".join("'" + v.replace("'", "''") + "'" for v in values) + ")"
