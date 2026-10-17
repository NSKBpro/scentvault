from __future__ import annotations

from datetime import date, timedelta

from conftest import API, fragrance_id

from app.core.clock import user_today
from app.core.config import PickWeights
from app.services.pick_scorer import Candidate, Context, rank, score

W = PickWeights()


# ── Scorer unit tests (pure) ────────────────────────────────────────
def cand(name: str, **kw) -> Candidate:  # type: ignore[no-untyped-def]
    return Candidate(collection_item_id=hash(name) % 1000, fragrance_id=1, name=name, brand="B", **kw)


def test_hot_day_prefers_fresh_cold_day_prefers_warm() -> None:
    fresh = cand("Fresh", traits={"citrus", "aquatic"}, seasons={"Summer"})
    warm = cand("Warm", traits={"amber", "vanilla"}, seasons={"Winter"})
    hot = Context(today=date(2026, 7, 10), season="Summer", occasion="Casual", temp_c=31)
    cold = Context(today=date(2026, 1, 10), season="Winter", occasion="Casual", temp_c=2, is_rainy=True)
    assert rank([fresh, warm], hot, W)[0].candidate.name == "Fresh"
    assert rank([fresh, warm], cold, W)[0].candidate.name == "Warm"
    chips = score(warm, cold, W).chips
    assert any("2°C and rainy" in c.label for c in chips)


def test_never_repeats_yesterday_even_if_best() -> None:
    today = date(2026, 10, 17)
    star = cand("Star", rating=5, is_favorite=True, last_worn_on=today - timedelta(days=1))
    ok = cand("Ok", rating=3, last_worn_on=today - timedelta(days=20))
    ctx = Context(today=today, season="Fall", occasion="Office")
    top = rank([star, ok], ctx, W)
    assert top[0].candidate.name == "Ok"
    assert any(c.label == "Worn yesterday" and not c.positive for c in top[1].chips)


def test_occasion_and_sillage() -> None:
    loud = cand("Loud", sillage="Enormous", occasions={"Evening"})
    office = cand("Office", sillage="Soft", occasions={"Office"})
    assert (
        rank([loud, office], Context(date(2026, 10, 14), "Fall", "Office"), W)[0].candidate.name == "Office"
    )
    assert (
        rank([loud, office], Context(date(2026, 10, 17), "Fall", "Date Night"), W)[0].candidate.name == "Loud"
    )


def test_rotation_bonus_and_low_level() -> None:
    today = date(2026, 10, 17)
    neglected = cand("Neglected", last_worn_on=today - timedelta(days=30))
    recent = cand("Recent", last_worn_on=today - timedelta(days=5), remaining_pct=5)
    top = rank([recent, neglected], Context(today, "Fall", "Casual"), W)
    assert top[0].candidate.name == "Neglected"
    assert any("weeks" in c.label for c in top[0].chips)
    assert any("5% left" in c.label for c in top[1].chips)


# ── Wear log API ────────────────────────────────────────────────────
async def _own(client, h, name, **kw):  # type: ignore[no-untyped-def]
    fid = await fragrance_id(client, name)
    r = await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_log_wear_updates_remaining_stats_and_cost_per_wear(client, user):
    h = user["headers"]
    item = await _own(client, h, "Bleu de Chanel", purchase_price=150, currency="EUR")
    r = await client.post(
        f"{API}/wears",
        headers=h,
        json={"collection_item_id": item["id"], "sprays": 10, "occasion": "Office", "compliment": True},
    )
    assert r.status_code == 201, r.text
    wear = r.json()
    assert wear["remaining_pct"] == 99  # 10 sprays × 0.1 ml of 100 ml
    assert wear["fragrance_name"] == "Bleu de Chanel" and wear["worn_on"] == user_today(None).isoformat()

    stats = (await client.get(f"{API}/wears/stats", headers=h)).json()
    assert stats["total_wears"] == 1 and stats["compliments"] == 1
    b = next(x for x in stats["per_bottle"] if x["collection_item_id"] == item["id"])
    assert b["wear_count"] == 1 and b["days_since_worn"] == 0
    assert b["cost_per_wear_is_estimate"] is True and b["cost_per_wear"] == 0.6  # 150 / (100 / 0.4)

    for i in range(1, 6):  # enough wears → real cost per wear
        d = (user_today(None) - timedelta(days=i)).isoformat()
        await client.post(f"{API}/wears", headers=h, json={"collection_item_id": item["id"], "worn_on": d})
    b = next(
        x
        for x in (await client.get(f"{API}/wears/stats", headers=h)).json()["per_bottle"]
        if x["collection_item_id"] == item["id"]
    )
    assert b["cost_per_wear_is_estimate"] is False and b["cost_per_wear"] == 25.0

    listed = (
        await client.get(
            f"{API}/wears", headers=h, params={"from": (user_today(None) - timedelta(days=2)).isoformat()}
        )
    ).json()
    assert len(listed) == 3
    assert (await client.delete(f"{API}/wears/{listed[0]['id']}", headers=h)).status_code == 204


async def test_wear_by_fragrance_links_owned_bottle_and_is_idempotent(client, user):
    h = user["headers"]
    item = await _own(client, h, "Oud Wood")
    body = {"fragrance_id": item["fragrance_id"], "client_ref": "offline-wear-1"}
    a = await client.post(f"{API}/wears", headers=h, json=body)
    b = await client.post(f"{API}/wears", headers=h, json=body)
    assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    assert a.json()["collection_item_id"] == item["id"]
    future = (user_today(None) + timedelta(days=5)).isoformat()
    assert (
        await client.post(f"{API}/wears", headers=h, json={**body, "client_ref": None, "worn_on": future})
    ).status_code == 422


async def test_running_low_creates_one_notification(client, user, drain):
    h = user["headers"]
    item = await _own(client, h, "Khamrah")
    await client.patch(f"{API}/collection/{item['id']}", headers=h, json={"remaining_pct": 12})
    await drain()
    await client.patch(f"{API}/collection/{item['id']}", headers=h, json={"remaining_pct": 10})
    await drain()
    inbox = (await client.get(f"{API}/notifications", headers=h)).json()
    low = [n for n in inbox["items"] if n["kind"] == "running_low"]
    assert len(low) == 1 and "Khamrah" in low[0]["title"] and inbox["unread"] >= 1
    read = await client.post(f"{API}/notifications/{low[0]['id']}/read", headers=h)
    assert read.json()["read_at"] is not None


# ── Daily pick API ──────────────────────────────────────────────────
async def test_daily_pick_with_weather_and_accept(client, user, weather):
    h = user["headers"]
    assert (await client.get(f"{API}/ai/daily-pick", headers=h)).json()["picks"] == []
    await client.patch(f"{API}/me/preferences", headers=h, json={"city": "Novi Sad"})
    fresh = await _own(client, h, "Light Blue Pour Homme", rating=4)
    warm = await _own(client, h, "Spicebomb Extreme", rating=4)
    await _own(client, h, "Explorer", rating=3)

    weather.temp_c, weather.code = 32.0, 0
    hot = (await client.get(f"{API}/ai/daily-pick", headers=h, params={"occasion": "Casual"})).json()
    assert hot["weather"]["temp_c"] == 32.0 and hot["weather"]["condition"] == "Clear"
    assert len(hot["picks"]) == 3 and hot["picks"][0]["collection_item_id"] == fresh["id"]
    assert hot["sentence_source"] == "template" and hot["sentence"]
    assert hot["picks"][0]["reasons"]

    weather.temp_c, weather.code = 1.0, 61
    cold = (await client.get(f"{API}/ai/daily-pick", headers=h, params={"occasion": "Evening"})).json()
    assert cold["picks"][0]["collection_item_id"] == warm["id"]
    assert cold["weather"]["is_rainy"] is True

    acc = await client.post(
        f"{API}/ai/daily-pick/accept",
        headers=h,
        json={"collection_item_id": warm["id"], "rank": 1, "occasion": "Evening", "sprays": 4},
    )
    assert acc.status_code == 201 and acc.json()["temp_c"] == 1.0
    again = (await client.get(f"{API}/ai/daily-pick", headers=h, params={"occasion": "Evening"})).json()
    assert warm["id"] in again["worn_today"]
    assert again["picks"][0]["collection_item_id"] != warm["id"]  # worn today drops it
    weather.temp_c, weather.code = 14.0, 61
