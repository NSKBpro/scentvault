from __future__ import annotations

from conftest import API


async def test_health_reports_db_and_providers(client):
    r = await client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json()["database"] == "connected"
    assert r.json()["embedding_provider"] == "hashing"
    assert r.json()["job_queue"] == "inline"


async def test_register_login_me(client):
    r = await client.post(
        f"{API}/auth/register",
        json={"email": "Mihajlo@Example.com", "password": "password123", "display_name": "Mihajlo"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "mihajlo@example.com"
    assert body["refresh_token"] and body["expires_in"] > 0

    r = await client.post(
        f"{API}/auth/register", json={"email": "mihajlo@example.com", "password": "password123"}
    )
    assert r.status_code == 409

    r = await client.post(
        f"{API}/auth/login/json", json={"email": "MIHAJLO@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["display_name"] == "Mihajlo"

    form = await client.post(
        f"{API}/auth/login", data={"username": "mihajlo@example.com", "password": "password123"}
    )
    assert form.status_code == 200

    bad = await client.post(
        f"{API}/auth/login/json", json={"email": "mihajlo@example.com", "password": "nope-nope"}
    )
    assert bad.status_code == 401


async def test_refresh_rotates_and_detects_reuse(client, user):
    first = user["refresh_token"]
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": first})
    assert r.status_code == 200
    second = r.json()["refresh_token"]
    assert second != first
    # Re-using the old token is treated as theft: it fails and revokes the newer one too.
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": first})).status_code == 401
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": second})).status_code == 401


async def test_logout_revokes_refresh(client, user):
    r = await client.post(
        f"{API}/auth/logout", headers=user["headers"], json={"refresh_token": user["refresh_token"]}
    )
    assert r.status_code == 200
    assert (
        await client.post(f"{API}/auth/refresh", json={"refresh_token": user["refresh_token"]})
    ).status_code == 401


async def test_auth_required_and_admin_only(client, user):
    assert (await client.get(f"{API}/collection")).status_code == 401
    assert (
        await client.get(f"{API}/collection", headers={"Authorization": "Bearer junk"})
    ).status_code == 401
    assert (await client.get(f"{API}/admin/stats", headers=user["headers"])).status_code == 403
    # The old API leaked the whole catalog here without auth.
    assert (await client.get(f"{API}/admin/export")).status_code == 401
    assert (await client.get(f"{API}/admin/export", headers=user["headers"])).status_code == 403


async def test_change_password(client, user):
    h = user["headers"]
    wrong = await client.patch(
        f"{API}/auth/me", headers=h, json={"current_password": "x" * 8, "new_password": "newpass123"}
    )
    assert wrong.status_code == 403
    ok = await client.patch(
        f"{API}/auth/me",
        headers=h,
        json={"current_password": "password123", "new_password": "newpass123", "display_name": "New"},
    )
    assert ok.status_code == 200 and ok.json()["display_name"] == "New"
    assert (
        await client.post(f"{API}/auth/login/json", json={"email": user["email"], "password": "newpass123"})
    ).status_code == 200


async def test_preferences_and_city_geocoding(client, user):
    h = user["headers"]
    prefs = (await client.get(f"{API}/me/preferences", headers=h)).json()
    assert prefs["currency"] == "EUR" and prefs["gender_preference"] == "Any"
    r = await client.patch(
        f"{API}/me/preferences",
        headers=h,
        json={"city": "novi sad", "currency": "rsd", "gender_preference": "Masculine"},
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["city"] == "Novi Sad" and p["latitude"] == 45.25 and p["timezone"] == "Europe/Belgrade"
    assert p["currency"] == "RSD"
    assert (
        await client.patch(f"{API}/me/preferences", headers=h, json={"city": "Atlantis"})
    ).status_code == 422
    assert (
        await client.patch(f"{API}/me/preferences", headers=h, json={"currency": "XYZ"})
    ).status_code == 422


async def test_meta(client):
    m = (await client.get(f"{API}/meta")).json()
    assert "Elixir" in m["concentrations"] and "decant" in m["bottle_types"] and m["currencies"]["USD"] == 1.0
