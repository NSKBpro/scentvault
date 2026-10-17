from __future__ import annotations

from conftest import API, fragrance_id


async def test_search_add_rate_flow(client, user):
    """The core mobile loop that used to return 'No fragrances found'."""
    h = user["headers"]
    found = (await client.get(f"{API}/catalog/fragrances", params={"search": "bleu", "size": 30})).json()[
        "items"
    ]
    assert found and found[0]["brand_name"] == "Chanel"
    r = await client.post(
        f"{API}/collection",
        headers=h,
        json={
            "fragrance_id": found[0]["id"],
            "size_ml": 100,
            "purchase_price": 120,
            "currency": "EUR",
            "purchase_date": "2026-09-01",
            "bottle_type": "full",
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["fragrance_name"] == "Bleu de Chanel" and item["brand_name"] == "Chanel"
    assert item["remaining_pct"] == 100 and item["families"]
    r = await client.patch(
        f"{API}/collection/{item['id']}", headers=h, json={"rating": 4.5, "notes": "Signature"}
    )
    assert r.json()["rating"] == 4.5 and r.json()["notes"] == "Signature"
    assert (
        await client.patch(f"{API}/collection/{item['id']}", headers=h, json={"rating": 4.3})
    ).status_code == 422


async def test_duplicates_and_multiple_sizes(client, user):
    h = user["headers"]
    fid = await fragrance_id(client, "Sauvage")
    a = await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100})
    assert a.status_code == 201
    assert (
        await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100})
    ).status_code == 409
    # Same fragrance as a 10 ml decant is a separate bottle.
    b = await client.post(
        f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 10, "bottle_type": "decant"}
    )
    assert b.status_code == 201
    items = (await client.get(f"{API}/collection", headers=h)).json()
    assert len([i for i in items if i["fragrance_id"] == fid]) == 2
    # Finishing the bottle frees the slot, so a re-buy is allowed.
    await client.post(f"{API}/collection/{a.json()['id']}/finish", headers=h)
    assert (
        await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100})
    ).status_code == 201


async def test_offline_replay_is_idempotent(client, user):
    h = user["headers"]
    fid = await fragrance_id(client, "Khamrah")
    body = {"fragrance_id": fid, "size_ml": 100, "client_ref": "phone-abc-1"}
    first = await client.post(f"{API}/collection", headers=h, json=body)
    again = await client.post(f"{API}/collection", headers=h, json=body)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"]


async def test_finish_sell_and_archive_filters(client, user):
    h = user["headers"]
    ids = []
    for name in ("Explorer", "Santal 33", "Light Blue"):
        fid = await fragrance_id(client, name)
        ids.append(
            (
                await client.post(f"{API}/collection", headers=h, json={"fragrance_id": fid, "size_ml": 100})
            ).json()["id"]
        )
    fin = (await client.post(f"{API}/collection/{ids[0]}/finish", headers=h)).json()
    assert fin["status"] == "finished" and fin["remaining_pct"] == 0
    sold = (await client.post(f"{API}/collection/{ids[1]}/sell", headers=h, json={"sold_price": 150})).json()
    assert sold["status"] == "sold" and sold["sold_price"] == 150 and sold["sold_at"]
    gift = (await client.post(f"{API}/collection/{ids[2]}/sell", headers=h, json={"gifted": True})).json()
    assert gift["status"] == "gifted" and gift["sold_price"] is None
    archive = (await client.get(f"{API}/collection", headers=h, params={"status": "archive"})).json()
    assert {i["id"] for i in archive} == set(ids)
    assert (await client.get(f"{API}/collection", headers=h, params={"status": "own"})).json() == []


async def test_isolation_between_users(client, user, other_user):
    fid = await fragrance_id(client, "Oud Wood")
    item = (
        await client.post(f"{API}/collection", headers=user["headers"], json={"fragrance_id": fid})
    ).json()
    assert (
        await client.patch(
            f"{API}/collection/{item['id']}", headers=other_user["headers"], json={"rating": 1}
        )
    ).status_code == 404
    assert (
        await client.delete(f"{API}/collection/{item['id']}", headers=other_user["headers"])
    ).status_code == 404
    assert (await client.delete(f"{API}/collection/{item['id']}", headers=user["headers"])).status_code == 204


async def test_stats_spent_counts_owned_only_in_user_currency(client, user):
    h = user["headers"]
    a = await fragrance_id(client, "Layton")
    b = await fragrance_id(client, "Aventus")
    await client.post(
        f"{API}/collection",
        headers=h,
        json={"fragrance_id": a, "size_ml": 125, "purchase_price": 200, "currency": "EUR", "rating": 4},
    )
    await client.post(
        f"{API}/collection",
        headers=h,
        json={"fragrance_id": b, "size_ml": 50, "purchase_price": 108, "currency": "USD"},
    )
    await client.post(
        f"{API}/collection", headers=h, json={"fragrance_id": b, "status": "tried", "purchase_price": 999}
    )
    s = (await client.get(f"{API}/collection/stats", headers=h)).json()
    assert s["owned_count"] == 2 and s["tried_count"] == 1 and s["bottles_ml"] == 175
    assert s["currency"] == "EUR"
    assert abs(s["spent"] - (200 + 108 * 0.92)) < 0.01  # USD converted, 'tried' not counted
    assert s["estimated_value_usd"] and s["estimated_value_usd"] > 0


async def test_scent_dna_uses_family_axis(client, user):
    h = user["headers"]
    assert (await client.get(f"{API}/collection/scent-dna", headers=h)).json()["based_on"] == 0
    # Sauvage is 'Aromatic Fougère' + 'Fresh Spicy' — Fougère used to be missed by keyword matching.
    await client.post(
        f"{API}/collection",
        headers=h,
        json={"fragrance_id": await fragrance_id(client, "Sauvage"), "rating": 5},
    )
    dna = (await client.get(f"{API}/collection/scent-dna", headers=h)).json()
    assert dna["aromatic"] == 100 and dna["fresh"] == 100 and dna["oriental"] == 0 and dna["based_on"] == 1
