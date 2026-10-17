"""Price logs, price history, price drops, and the alert check hook."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Invalid, NotFound
from app.models import Brand, Fragrance, FragrancePrice, PriceLog, Retailer
from app.schemas.prices import PriceLogIn

logger = logging.getLogger(__name__)


def log_out(p: PriceLog) -> dict[str, Any]:
    return {
        "id": p.id,
        "fragrance_id": p.fragrance_id,
        "retailer_id": p.retailer_id,
        "size_ml": p.size_ml,
        "price_usd": p.price_usd,
        "product_url": p.product_url,
        "is_sale": p.is_sale,
        "logged_at": p.logged_at,
        "fragrance": {"id": p.fragrance.id, "name": p.fragrance.name, "brand_name": p.fragrance.brand.name},
        "retailer": {"id": p.retailer.id, "name": p.retailer.name},
    }


def _with_rel() -> Any:
    return select(PriceLog).options(
        selectinload(PriceLog.fragrance).selectinload(Fragrance.brand), selectinload(PriceLog.retailer)
    )


class PriceService:
    def __init__(self, session: AsyncSession):
        self.s = session

    # ── Admin log CRUD ───────────────────────────────────────────────
    async def list_logs(
        self,
        page: int,
        size: int,
        fragrance_id: int | None,
        retailer_id: int | None,
        date_from: date | None,
        date_to: date | None,
        is_sale: bool | None,
    ) -> tuple[list[dict[str, Any]], int]:
        conds = []
        if fragrance_id:
            conds.append(PriceLog.fragrance_id == fragrance_id)
        if retailer_id:
            conds.append(PriceLog.retailer_id == retailer_id)
        if date_from:
            conds.append(PriceLog.logged_at >= datetime.combine(date_from, datetime.min.time(), UTC))
        if date_to:
            conds.append(
                PriceLog.logged_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), UTC)
            )
        if is_sale is not None:
            conds.append(PriceLog.is_sale.is_(is_sale))
        total = await self.s.scalar(select(func.count()).select_from(PriceLog).where(*conds)) or 0
        rows = await self.s.execute(
            _with_rel()
            .where(*conds)
            .order_by(PriceLog.logged_at.desc(), PriceLog.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return [log_out(p) for p in rows.scalars()], total

    async def today_count(self) -> int:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.s.scalar(select(func.count()).where(PriceLog.logged_at >= start)) or 0

    async def recent(self, limit: int) -> list[dict[str, Any]]:
        rows = await self.s.execute(
            _with_rel().order_by(PriceLog.logged_at.desc(), PriceLog.id.desc()).limit(limit)
        )
        return [log_out(p) for p in rows.scalars()]

    async def get_log(self, log_id: int) -> dict[str, Any]:
        p = (await self.s.execute(_with_rel().where(PriceLog.id == log_id))).scalar_one_or_none()
        if p is None:
            raise NotFound("Price log")
        return log_out(p)

    async def create_log(self, data: PriceLogIn) -> dict[str, Any]:
        if not await self.s.get(Fragrance, data.fragrance_id):
            raise Invalid("Fragrance not found")
        if not await self.s.get(Retailer, data.retailer_id):
            raise Invalid("Retailer not found")
        p = PriceLog(**data.model_dump())
        self.s.add(p)
        await self.s.commit()
        return await self.get_log(p.id)

    async def update_log(self, log_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        p = await self.s.get(PriceLog, log_id)
        if p is None:
            raise NotFound("Price log")
        for k, v in fields.items():
            if v is not None:
                setattr(p, k, v)
        await self.s.commit()
        return await self.get_log(log_id)

    async def delete_log(self, log_id: int) -> None:
        p = await self.s.get(PriceLog, log_id)
        if p is None:
            raise NotFound("Price log")
        await self.s.delete(p)
        await self.s.commit()

    # ── Public history ───────────────────────────────────────────────
    async def history(self, fragrance_id: int, days: int = 365) -> dict[str, Any]:
        if not await self.s.get(Fragrance, fragrance_id):
            raise NotFound("Fragrance")
        since = datetime.now(UTC) - timedelta(days=days)
        rows = await self.s.execute(
            select(PriceLog.size_ml, PriceLog.price_usd, PriceLog.logged_at, Retailer.name, PriceLog.is_sale)
            .join(Retailer, Retailer.id == PriceLog.retailer_id)
            .where(PriceLog.fragrance_id == fragrance_id, PriceLog.logged_at >= since)
            .order_by(PriceLog.size_ml, PriceLog.logged_at)
        )
        msrp = dict(
            (
                await self.s.execute(
                    select(FragrancePrice.size_ml, FragrancePrice.price_usd).where(
                        FragrancePrice.fragrance_id == fragrance_id
                    )
                )
            )
            .tuples()
            .all()
        )
        series: dict[int, list[dict[str, Any]]] = {}
        for size, price, at, retailer, sale in rows.tuples():
            series.setdefault(size, []).append(
                {"price_usd": price, "logged_at": at, "retailer_name": retailer, "is_sale": sale}
            )
        out = []
        for size in sorted(set(series) | set(msrp)):
            pts = series.get(size, [])
            prices = [p["price_usd"] for p in pts]
            out.append(
                {
                    "size_ml": size,
                    "msrp_usd": msrp.get(size),
                    "latest_usd": prices[-1] if prices else None,
                    "lowest_usd": min(prices) if prices else None,
                    "highest_usd": max(prices) if prices else None,
                    "average_usd": round(sum(prices) / len(prices), 2) if prices else None,
                    "points": pts,
                }
            )
        return {"fragrance_id": fragrance_id, "series": out}

    # ── Deals ────────────────────────────────────────────────────────
    async def price_drops(self, min_drop_pct: float, limit: int, days: int = 30) -> list[dict[str, Any]]:
        """Latest price per (fragrance, size) in the last `days`, compared with the average of the
        previous five logs for that size — or the reference price when there is no history yet."""
        rows = await self.s.execute(
            text("""
                WITH ranked AS (
                    SELECT pl.*, ROW_NUMBER() OVER (PARTITION BY pl.fragrance_id, pl.size_ml
                                                    ORDER BY pl.logged_at DESC, pl.id DESC) AS rn
                    FROM price_logs pl
                ),
                latest AS (SELECT * FROM ranked WHERE rn = 1 AND logged_at >= now() - make_interval(days => :days)),
                prev AS (
                    SELECT fragrance_id, size_ml, AVG(price_usd)::float AS avg_prev
                    FROM ranked WHERE rn BETWEEN 2 AND 6 GROUP BY fragrance_id, size_ml
                ),
                cmp AS (
                    SELECT l.*, COALESCE(p.avg_prev, fp.price_usd::float) AS baseline
                    FROM latest l
                    LEFT JOIN prev p ON p.fragrance_id = l.fragrance_id AND p.size_ml = l.size_ml
                    LEFT JOIN fragrance_prices fp ON fp.fragrance_id = l.fragrance_id AND fp.size_ml = l.size_ml
                )
                SELECT c.fragrance_id, f.name AS fragrance_name, b.name AS brand_name, f.concentration, f.image_url,
                       c.size_ml, c.price_usd::float AS current_price_usd, ROUND(c.baseline::numeric, 2)::float
                       AS previous_avg_usd,
                       ROUND(((c.baseline - c.price_usd) / c.baseline * 100)::numeric, 1)::float AS drop_pct,
                       ROUND((c.baseline - c.price_usd)::numeric, 2)::float AS drop_amount_usd,
                       r.name AS retailer_name, c.product_url, c.logged_at,
                       ARRAY(SELECT h.price_usd::float FROM (
                           SELECT price_usd, logged_at FROM price_logs
                           WHERE fragrance_id = c.fragrance_id AND size_ml = c.size_ml
                           ORDER BY logged_at DESC LIMIT 10) h ORDER BY h.logged_at) AS history
                FROM cmp c
                JOIN fragrances f ON f.id = c.fragrance_id
                JOIN brands b ON b.id = f.brand_id
                JOIN retailers r ON r.id = c.retailer_id
                WHERE c.baseline IS NOT NULL AND c.baseline > 0 AND c.price_usd < c.baseline
                  AND (c.baseline - c.price_usd) / c.baseline * 100 >= :min_drop
                ORDER BY drop_pct DESC
                LIMIT :lim
            """),
            {"days": days, "min_drop": min_drop_pct, "lim": limit},
        )
        return [dict(r) for r in rows.mappings()]

    async def latest_price_usd(self, fragrance_id: int, size_ml: int | None) -> float | None:
        """Lowest of the latest price per size (or for one size), last 30 days."""
        sql = """
            SELECT MIN(price_usd)::float FROM (
                SELECT DISTINCT ON (size_ml) size_ml, price_usd FROM price_logs
                WHERE fragrance_id = :fid AND logged_at >= now() - interval '30 days'
                  AND (CAST(:size AS int) IS NULL OR size_ml = CAST(:size AS int))
                ORDER BY size_ml, logged_at DESC, id DESC
            ) t
        """
        return await self.s.scalar(text(sql), {"fid": fragrance_id, "size": size_ml})

    async def fragrance_label(self, fragrance_id: int) -> tuple[str, str]:
        row = (
            await self.s.execute(
                select(Fragrance.name, Brand.name).join(Brand).where(Fragrance.id == fragrance_id)
            )
        ).one()
        return row[0], row[1]
