from __future__ import annotations

import io

from conftest import API, fragrance_id


async def test_list_is_paginated_with_brand_name(client):
    r = await client.get(f"{API}/catalog/fragrances", params={"page": 1, "size": 5, "sort": "name"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "size"}
    assert body["total"] >= 24 and len(body["items"]) == 5
    item = body["items"][0]
    for key in ("brand_name", "sizes_ml", "min_price_usd", "families", "has_embedding", "note_count"):
        assert key in item
    names = [i["name"].lower() for i in body["items"]]
    assert names == sorted(names)


async def test_search_matches_brand_too(client):
    r = await client.get(f"{API}/catalog/fragrances", params={"search": "tom ford", "size": 50})
    names = {i["name"] for i in r.json()["items"]}
    assert {"Tobacco Vanille", "Oud Wood"} <= names


async def test_filters(client):
    fam = (await client.get(f"{API}/catalog/families", params={"search": "Gourmand"})).json()["items"][0]
    r = await client.get(f"{API}/catalog/fragrances", params={"family_id": fam["id"], "size": 50})
    assert r.json()["total"] == fam["fragrance_count"] > 0
    r = await client.get(f"{API}/catalog/fragrances", params={"missing": "image", "size": 1})
    assert r.json()["total"] >= 24
    r = await client.get(f"{API}/catalog/fragrances", params={"gender": "Feminine", "size": 50})
    assert all(i["gender"] == "Feminine" for i in r.json()["items"])


async def test_detail(client):
    fid = await fragrance_id(client, "Sauvage")
    d = (await client.get(f"{API}/catalog/fragrances/{fid}")).json()
    assert d["brand"]["name"] == "Dior"
    assert [n["position"] for n in d["notes"]][:2] == ["top", "top"]
    assert {p["size_ml"] for p in d["prices"]} == {60, 100, 200}
    assert (await client.get(f"{API}/catalog/fragrances/999999")).status_code == 404


async def test_admin_fragrance_lifecycle_generates_embedding(client, admin, drain):
    h = admin["headers"]
    brands = (await client.get(f"{API}/catalog/brands", params={"search": "Guerlain"})).json()["items"]
    notes = {
        n["name"]: n["id"]
        for n in (await client.get(f"{API}/catalog/notes", params={"size": 500})).json()["items"]
    }
    payload = {
        "name": "L'Homme Idéal Test",
        "brand_id": brands[0]["id"],
        "concentration": "EDP",
        "gender": "Masculine",
        "season_fall": True,
        "notes": [
            {"note_id": notes["Almond"], "position": "top", "prominence": 5},
            {"note_id": notes["Tonka Bean"], "position": "base"},
        ],
        "prices": [{"size_ml": 50, "price_usd": 90}, {"size_ml": 100, "price_usd": 130}],
    }
    preview = await client.post(f"{API}/catalog/admin/fragrances/embedding-preview", headers=h, json=payload)
    assert preview.json()["text"].startswith("Fragrance. Top notes: Almond.")

    r = await client.post(f"{API}/catalog/admin/fragrances", headers=h, json=payload)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    await drain()
    detail = (await client.get(f"{API}/catalog/fragrances/{fid}")).json()
    assert detail["has_embedding"] is True  # the background job actually ran (old bug: ImportError)

    dup = await client.post(f"{API}/catalog/admin/fragrances", headers=h, json=payload)
    assert dup.status_code == 409

    bad = await client.post(
        f"{API}/catalog/admin/fragrances", headers=h, json={**payload, "name": "X", "family_ids": [987654]}
    )
    assert bad.status_code == 422

    payload["concentration"] = "Parfum"
    upd = await client.put(f"{API}/catalog/admin/fragrances/{fid}", headers=h, json=payload)
    assert upd.status_code == 200 and upd.json()["concentration"] == "Parfum"

    assert (await client.delete(f"{API}/catalog/admin/fragrances/{fid}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/catalog/fragrances/{fid}")).status_code == 404


async def test_lookup_crud_including_notes(client, admin):
    h = admin["headers"]
    r = await client.post(
        f"{API}/catalog/admin/notes", headers=h, json={"name": "Yuzu Peel Test", "category": "Citrus"}
    )
    assert r.status_code == 201, r.text  # notes CRUD didn't exist before
    nid = r.json()["id"]
    assert (
        await client.post(f"{API}/catalog/admin/notes", headers=h, json={"name": "yuzu peel test"})
    ).status_code == 409
    r = await client.put(f"{API}/catalog/admin/notes/{nid}", headers=h, json={"category": "Fruity"})
    assert r.json()["category"] == "Fruity" and r.json()["name"] == "Yuzu Peel Test"
    assert (await client.delete(f"{API}/catalog/admin/notes/{nid}", headers=h)).status_code == 204

    fam = await client.post(
        f"{API}/catalog/admin/families", headers=h, json={"name": "Test Family", "axis": "fresh"}
    )
    assert fam.json()["axis"] == "fresh"
    bad = await client.post(f"{API}/catalog/admin/families", headers=h, json={"name": "Bad", "axis": "salty"})
    assert bad.status_code == 422

    dior = (await client.get(f"{API}/catalog/brands", params={"search": "Dior"})).json()["items"][0]
    assert dior["fragrance_count"] >= 1
    r = await client.delete(f"{API}/catalog/admin/brands/{dior['id']}", headers=h)
    assert r.status_code == 409  # brands with fragrances are protected


async def test_notes_csv_import_and_categories(client, admin):
    csv_bytes = b"name,category\nTest Smoke Note,Smoky\nBergamot,Citrus\n,Woody\n"
    r = await client.post(
        f"{API}/catalog/admin/notes/import",
        headers=admin["headers"],
        files={"file": ("notes.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.json() == {"inserted": 1, "skipped": 1, "errors": ["Row 4: missing name"]}
    cats = (await client.get(f"{API}/catalog/notes/categories")).json()
    assert "Smoky" in cats and "Citrus" in cats


async def test_embedding_status(client, admin):
    s = (await client.get(f"{API}/catalog/admin/embeddings/status", headers=admin["headers"])).json()
    assert s["missing"] == 0 and s["coverage_pct"] == 100.0 and s["provider"] == "hashing"
