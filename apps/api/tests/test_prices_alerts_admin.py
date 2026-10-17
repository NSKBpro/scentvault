from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

from conftest import API, fragrance_id
from sqlalchemy import text

from app.db.session import get_sessionmaker


async def _retailer(client, admin) -> int:  # type: ignore[no-untyped-def]
    rs = (await client.get(f"{API}/prices/retailers")).json()
    return next(r["id"] for r in rs if r["name"] == "Notino")


async def test_price_log_history_and_drops_per_size(client, admin):
    h = admin["headers"]
    fid = await fragrance_id(client, "Explorer")
    rid = await _retailer(client, admin)
    for size, price in ((100, 70), (100, 68), (60, 55)):
        r = await client.post(
            f"{API}/prices/admin/logs",
            headers=h,
            json={"fragrance_id": fid, "retailer_id": rid, "size_ml": size, "price_usd": price},
        )
        assert r.status_code == 201, r.text
    latest = await client.post(
        f"{API}/prices/admin/logs",
        headers=h,
        json={"fragrance_id": fid, "retailer_id": rid, "size_ml": 100, "price_usd": 49, "is_sale": True},
    )
    assert latest.json()["fragrance"]["brand_name"] == "Montblanc"

    hist = (
        await client.get(f"{API}/fragrances/{fid}/price-history")
    ).json()  # public now (was admin-only → 403)
    s100 = next(s for s in hist["series"] if s["size_ml"] == 100)
    assert s100["latest_usd"] == 49 and s100["lowest_usd"] == 49 and s100["msrp_usd"] == 70
    assert len(s100["points"]) == 3

    drops = (await client.get(f"{API}/deals/price-drops")).json()
    d = next(x for x in drops if x["fragrance_id"] == fid)
    assert d["size_ml"] == 100 and d["previous_avg_usd"] == 69.0 and d["drop_pct"] == 29.0
    assert d["history"][-1] == 49.0
    # The 60 ml price (55) is not compared against 100 ml prices.
    assert not any(x["fragrance_id"] == fid and x["size_ml"] == 60 for x in drops)

    logs = (await client.get(f"{API}/prices/admin/logs", headers=h, params={"fragrance_id": fid})).json()
    assert logs["total"] == 4
    assert (await client.get(f"{API}/prices/admin/logs/today-count", headers=h)).json()["count"] >= 4


async def test_price_alert_fires_once_with_cooldown(client, admin, user, drain, resources):
    h = user["headers"]
    fid = await fragrance_id(client, "Grey Vetiver")
    await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "status": "wishlist"})
    await client.post(
        f"{API}/me/devices",
        headers=h,
        json={"expo_push_token": "ExponentPushToken[test-123]", "platform": "android"},
    )
    r = await client.post(
        f"{API}/alerts",
        headers=h,
        json={"fragrance_id": fid, "size_ml": 100, "target_price": 150, "currency": "EUR"},
    )
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["best_price"] is None and alert["currency"] == "EUR"
    assert (
        await client.post(
            f"{API}/alerts", headers=h, json={"fragrance_id": fid, "size_ml": 100, "target_price": 1}
        )
    ).status_code == 409

    rid = await _retailer(client, admin)
    before = len(resources.push.sent)
    # 170 USD ≈ 156 EUR → above target, no alert
    await client.post(
        f"{API}/prices/admin/logs",
        headers=admin["headers"],
        json={"fragrance_id": fid, "retailer_id": rid, "size_ml": 100, "price_usd": 170},
    )
    await drain()
    assert not [
        n
        for n in (await client.get(f"{API}/notifications", headers=h)).json()["items"]
        if n["kind"] == "price_alert"
    ]
    # 150 USD = 138 EUR → below target
    await client.post(
        f"{API}/prices/admin/logs",
        headers=admin["headers"],
        json={"fragrance_id": fid, "retailer_id": rid, "size_ml": 100, "price_usd": 150},
    )
    await drain()
    inbox = (await client.get(f"{API}/notifications", headers=h)).json()["items"]
    hits = [n for n in inbox if n["kind"] == "price_alert"]
    assert len(hits) == 1 and "138.00 EUR" in hits[0]["body"]
    sent = resources.push.sent[before:]
    assert sent and sent[-1]["to"] == "ExponentPushToken[test-123]"

    # Another drop within 7 days doesn't spam.
    await client.post(
        f"{API}/prices/admin/logs",
        headers=admin["headers"],
        json={"fragrance_id": fid, "retailer_id": rid, "size_ml": 100, "price_usd": 140},
    )
    await drain()
    assert (
        len(
            [
                n
                for n in (await client.get(f"{API}/notifications", headers=h)).json()["items"]
                if n["kind"] == "price_alert"
            ]
        )
        == 1
    )

    listed = (await client.get(f"{API}/alerts", headers=h)).json()
    assert listed[0]["best_price_usd"] == 140 and listed[0]["last_notified_at"]
    # Changing the target re-arms it immediately.
    upd = await client.patch(f"{API}/alerts/{alert['id']}", headers=h, json={"target_price": 130})
    assert upd.status_code == 200
    assert (
        len(
            [
                n
                for n in (await client.get(f"{API}/notifications", headers=h)).json()["items"]
                if n["kind"] == "price_alert"
            ]
        )
        == 2
    )
    assert (await client.delete(f"{API}/alerts/{alert['id']}", headers=h)).status_code == 204


async def test_neglected_nudges(client, user, resources):
    from app.services.notifications import NotificationService

    h = user["headers"]
    fid = await fragrance_id(client, "Interlude Man")
    item = (
        await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100})
    ).json()
    async with get_sessionmaker()() as s:
        await s.execute(
            text("UPDATE user_collection SET created_at = :d WHERE id = :i"),
            {"d": datetime.now(UTC) - timedelta(days=90), "i": item["id"]},
        )
        await s.commit()
        sent = await NotificationService(s).neglected_nudges()
        again = await NotificationService(s).neglected_nudges()
    assert sent >= 1 and again == 0  # one per bottle per month
    inbox = (await client.get(f"{API}/notifications", headers=h)).json()["items"]
    assert any(n["kind"] == "neglected" and "Interlude" in n["title"] for n in inbox)


async def test_admin_stats_and_users(client, admin, user):
    h = admin["headers"]
    s = (await client.get(f"{API}/admin/stats", headers=h)).json()
    assert s["counts"]["fragrances"] >= 24 and {q["key"] for q in s["queues"]} >= {
        "embedding",
        "image",
        "notes",
    }
    users = (await client.get(f"{API}/admin/users", headers=h, params={"search": user["email"][:12]})).json()
    assert users["total"] == 1
    uid = users["items"][0]["id"]
    r = await client.put(f"{API}/admin/users/{uid}", headers=h, json={"display_name": "Renamed"})
    assert r.json()["display_name"] == "Renamed"
    me = (await client.get(f"{API}/auth/me", headers=h)).json()
    assert (await client.delete(f"{API}/admin/users/{me['id']}", headers=h)).status_code == 422


async def test_export_and_import_roundtrip(client, admin, drain):
    h = admin["headers"]
    r = await client.get(f"{API}/admin/export", headers=h, params={"tables": "catalog,price_logs,fragrances"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(zf.namelist()) == {"catalog.csv", "price_logs.csv", "fragrances.csv"}
    assert "Sauvage" in zf.read("catalog.csv").decode()

    csv_text = (
        "name,brand_name,concentration,gender,top_notes,base_notes,families,accords,seasons,prices\n"
        "Imported One,New Test House,eau de parfum,men,Bergamot;Brand New Note,Musk,Citrus;Weird Family,Citrus,Summer;Spring,50:60;100:90\n"
        "Sauvage,Dior,EDT,Masculine,,,,,,\n"
        ",Nobody,EDP,Unisex,,,,,,\n"
        "Imported Two,New Test House,EDT,f,Lemon,,,,winter,\n"
    )
    pre = await client.post(
        f"{API}/admin/import/preview",
        headers=h,
        files={"file": ("cat.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    assert pre.status_code == 200, pre.text
    p = pre.json()
    assert p["total_rows"] == 4 and p["error_rows"] == 2 and p["warning_rows"] == 2
    first = p["rows"][0]["data"]
    assert (
        first["concentration"] == "EDP"
        and first["gender"] == "Masculine"
        and first["prices"] == [[50, 60.0], [100, 90.0]]
    )

    conf = await client.post(
        f"{API}/admin/import/confirm", headers=h, json={"session_data": p["session_data"]}
    )
    assert conf.json() == {"inserted": 2, "skipped": 0, "errors": [], "embeddings_queued": 2}
    await drain()
    one = (await client.get(f"{API}/catalog/fragrances", params={"search": "Imported One"})).json()["items"][
        0
    ]
    assert one["brand_name"] == "New Test House" and one["has_embedding"] and one["sizes_ml"] == [50, 100]
    # Replaying the same session skips instead of failing (unique constraint + savepoints).
    again = await client.post(
        f"{API}/admin/import/confirm", headers=h, json={"session_data": p["session_data"]}
    )
    assert again.json()["inserted"] == 0 and again.json()["skipped"] == 2

    bad = json.dumps(
        [
            {"name": "Broken", "brand_name": "X", "concentration": "NOPE", "gender": "Unisex"},
            {"name": "Fine After Broken", "brand_name": "X", "concentration": "EDT", "gender": "Unisex"},
        ]
    )
    res = (await client.post(f"{API}/admin/import/confirm", headers=h, json={"session_data": bad})).json()
    assert res["inserted"] == 1 and len(res["errors"]) == 1, res  # one bad row no longer aborts the rest
