from __future__ import annotations

from conftest import API, fragrance_id


async def test_similar_ranks_the_clone_first(client):
    fid = await fragrance_id(client, "Aventus")
    sims = (await client.get(f"{API}/fragrances/{fid}/similar", params={"limit": 5})).json()
    assert sims[0]["name"] == "Club de Nuit Intense Man"
    assert all(s["fragrance_id"] != fid for s in sims)
    assert sims == sorted(sims, key=lambda s: -s["similarity_pct"])


async def test_dupes_compare_price_per_ml(client):
    fid = await fragrance_id(client, "Aventus")
    dupes = (await client.get(f"{API}/fragrances/{fid}/dupes")).json()
    assert dupes and dupes[0]["name"] == "Club de Nuit Intense Man"
    d = dupes[0]
    assert d["price_per_ml_usd"] == round(35 / 105, 4)
    assert d["original_price_per_ml_usd"] == round(445 / 100, 4)  # 100 ml is Aventus' cheapest per ml
    assert d["savings_pct"] > 90


async def test_similar_for_freshly_created_fragrance(client, admin, drain):
    """Phase 2 'done when': a new fragrance gets an embedding and appears in Similar."""
    h = admin["headers"]
    armaf = (await client.get(f"{API}/catalog/brands", params={"search": "Armaf"})).json()["items"][0]
    src = (await client.get(f"{API}/catalog/fragrances/{await fragrance_id(client, 'Aventus')}")).json()
    payload = {
        "name": "Club de Nuit Test Edition",
        "brand_id": armaf["id"],
        "concentration": "Parfum",
        "gender": "Masculine",
        "notes": [{"note_id": n["note_id"], "position": n["position"]} for n in src["notes"]],
        "family_ids": [f["id"] for f in src["families"]],
        "accord_ids": [a["id"] for a in src["accords"]],
        "season_spring": True,
        "season_summer": True,
        "season_fall": True,
    }
    new = (await client.post(f"{API}/catalog/admin/fragrances", headers=h, json=payload)).json()
    await drain()
    sims = (await client.get(f"{API}/fragrances/{new['id']}/similar", params={"limit": 3})).json()
    assert sims and sims[0]["name"] == "Aventus" and sims[0]["similarity_pct"] > 80
    await client.delete(f"{API}/catalog/admin/fragrances/{new['id']}", headers=h)


async def test_similar_404_vs_empty(client):
    assert (await client.get(f"{API}/fragrances/999999/similar")).status_code == 404


async def test_recommendations_need_liked_bottles_and_explain_themselves(client, user):
    h = user["headers"]
    assert (await client.get(f"{API}/ai/recommend", headers=h)).json() == []
    for name in ("Tobacco Vanille", "Spicebomb Extreme"):
        await client.post(
            f"{API}/collection",
            headers=h,
            json={"fragrance_id": await fragrance_id(client, name), "rating": 5},
        )
    recs = (await client.get(f"{API}/ai/recommend", headers=h, params={"limit": 5})).json()
    assert recs
    names = {r["name"] for r in recs}
    assert not names & {"Tobacco Vanille", "Spicebomb Extreme"}  # excludes what you own
    top = recs[0]
    assert top["reason"] and (top["shared_notes"] or top["shared_accords"] or top["shared_families"])


async def test_recommendations_respect_gender_preference(client, user):
    h = user["headers"]
    await client.patch(f"{API}/me/preferences", headers=h, json={"gender_preference": "Masculine"})
    await client.post(
        f"{API}/collection",
        headers=h,
        json={"fragrance_id": await fragrance_id(client, "Black Opium"), "rating": 5},
    )
    recs = (await client.get(f"{API}/ai/recommend", headers=h, params={"limit": 20})).json()
    assert recs and all(r["gender"] in ("Masculine", "Unisex") for r in recs)


async def test_ai_search_returns_results_without_llm(client, user):
    r = await client.post(
        f"{API}/ai/search",
        headers=user["headers"],
        json={"query": "warm vanilla tobacco evening scent under 400, no patchouli"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["intent"]["parsed_by"] == "rules" and d["intent"]["exclude_notes"] == ["patchouli"]
    assert d["intent"]["occasion"] == "Evening" and d["explanation"] is None
    assert d["results"] and d["results"][0]["top_notes"] is not None
    ids = [x["fragrance_id"] for x in d["results"][:3]]
    exp = await client.post(
        f"{API}/ai/explain", headers=user["headers"], json={"query": "warm vanilla", "fragrance_ids": ids}
    )
    assert exp.json()["source"] == "template" and exp.json()["explanation"]


async def test_collection_dupes(client, user):
    h = user["headers"]
    await client.post(
        f"{API}/collection",
        headers=h,
        json={"fragrance_id": await fragrance_id(client, "Aventus"), "status": "wishlist"},
    )
    dupes = (await client.get(f"{API}/deals/dupes-for-collection", headers=h)).json()
    assert (
        dupes
        and dupes[0]["original_name"] == "Aventus"
        and dupes[0]["dupe"]["name"] == "Club de Nuit Intense Man"
    )
