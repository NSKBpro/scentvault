"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.alerts import Notification, PriceAlert
from app.models.base import Base
from app.models.catalog import (
    Accord,
    Brand,
    Family,
    Fragrance,
    FragranceEmbedding,
    FragranceNote,
    FragrancePrice,
    Note,
    Occasion,
    PriceLog,
    Retailer,
    fragrance_accords,
    fragrance_families,
    fragrance_occasions,
)
from app.models.collection import CollectionItem, PickEvent, WearLog
from app.models.user import RefreshToken, User, UserDevice, UserPreferences

__all__ = [
    "Accord",
    "Base",
    "Brand",
    "CollectionItem",
    "Family",
    "Fragrance",
    "FragranceEmbedding",
    "FragranceNote",
    "FragrancePrice",
    "Note",
    "Notification",
    "Occasion",
    "PickEvent",
    "PriceAlert",
    "PriceLog",
    "RefreshToken",
    "Retailer",
    "User",
    "UserDevice",
    "UserPreferences",
    "WearLog",
    "fragrance_accords",
    "fragrance_families",
    "fragrance_occasions",
]
