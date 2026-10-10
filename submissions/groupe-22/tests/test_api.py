"""The HTTP API: who may see and change what. The page hides things too, but these
rules are the ones that hold when the API is called directly."""

from api_helpers import ORIGIN, login
from fastapi.testclient import TestClient

import bank_store
import server


def test_visitor_gets_a_session_but_no_private_data(client):
    assert server.COOKIE in client.cookies
    assert client.get("/api/customer").status_code == 401
    assert client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN).status_code == 401
    assert client.get("/api/demarches").json() == {"demarches": []}


def test_no_cookie_at_all_is_refused():
    with TestClient(server.app) as fresh:
        response = fresh.get("/api/customer")
    assert response.status_code == 401
    assert "Camille" not in response.text


def test_forged_cookie_is_refused(client):
    client.cookies.set(server.COOKIE, "not-a-real-token")
    assert client.get("/api/customer").status_code == 401
    assert client.get("/api/me").json() == {"kind": "visitor"}  # and a fresh visitor


def test_wrong_code_and_unknown_profile_are_refused(client):
    wrong = login(client, code="1234")
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Code de démonstration incorrect."
    assert login(client, profile="admin").status_code == 400
    assert client.get("/api/customer").status_code == 401  # still a visitor


def test_login_opens_the_customer_and_rotates_the_session(client):
    visitor_token = client.cookies[server.COOKIE]
    response = login(client)
    assert response.status_code == 200
    assert response.json()["customer"]["displayName"] == "Camille Martin"
    assert client.cookies[server.COOKIE] != visitor_token  # no session fixation
    data = client.get("/api/customer").json()
    balances = {a["label"]: a["balanceCents"] for a in data["accounts"]}
    assert balances == {"Compte courant": 124580, "Livret A": 865000}
    assert any(t["id"] == "tx_inconnu" and t["amountCents"] == -8900 for t in data["transactions"])
    # The visitor token from before the login gets nothing.
    client.cookies.set(server.COOKIE, visitor_token)
    assert client.get("/api/customer").status_code == 401


def test_session_survives_a_reload(client):
    login(client)
    assert client.get("/api/me").json()["kind"] == "customer"
    assert client.get("/api/customer").status_code == 200


def test_logout_revokes_the_old_token(client):
    login(client)
    token = client.cookies[server.COOKIE]
    assert client.post("/api/auth/logout", json={}, headers=ORIGIN).json() == {"kind": "visitor"}
    assert client.get("/api/customer").status_code == 401
    client.cookies.set(server.COOKIE, token)  # replaying the old cookie
    assert client.get("/api/customer").status_code == 401
    assert client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN).status_code == 401


def test_repeated_logins_work(client):
    for profile in ("camille", "lucas", "camille", "camille"):
        assert login(client, profile).status_code == 200
        assert client.get("/api/customer").json()["customer"]["id"] == profile


def test_card_lock_unlock_and_persistence(client):
    login(client)
    locked = client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN)
    assert locked.status_code == 200 and locked.json()["card"]["status"] == "LOCKED"
    cards = {c["id"]: c["status"] for c in client.get("/api/customer").json()["cards"]}
    assert cards == {"card_visa": "LOCKED", "card_virtual": "ACTIVE"}  # after a reload
    again = client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN)
    assert again.status_code == 409  # no double action
    unlocked = client.post("/api/cards/card_visa/unlock", json={}, headers=ORIGIN)
    assert unlocked.json()["card"]["status"] == "ACTIVE"
    assert client.post("/api/cards/card_visa/explode", json={}, headers=ORIGIN).status_code == 404
    assert client.post("/api/cards/nope/lock", json={}, headers=ORIGIN).status_code == 404


def test_customer_cannot_reach_another_customers_card(client):
    login(client, "lucas")
    response = client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN)
    assert response.status_code == 404  # same answer as a card that doesn't exist
    data = client.get("/api/customer").json()
    assert {c["id"] for c in data["cards"]} == {"card_lb_mastercard"}
    assert not any(t["id"].startswith("tx_") and not t["id"].startswith("tx_lb") for t in data["transactions"])


def test_sandboxes_are_per_session():
    with TestClient(server.app) as a, TestClient(server.app) as b:
        for c in (a, b):
            c.get("/api/me")
            login(c)
        a.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN)
        statuses = {c["id"]: c["status"] for c in b.get("/api/customer").json()["cards"]}
        assert statuses["card_visa"] == "ACTIVE"  # b's demo isn't broken by a's


def test_logout_then_login_resets_the_demo(client):
    login(client)
    client.post("/api/cards/card_visa/lock", json={}, headers=ORIGIN)
    client.post("/api/auth/logout", json={}, headers=ORIGIN)
    login(client)
    statuses = {c["id"]: c["status"] for c in client.get("/api/customer").json()["cards"]}
    assert statuses["card_visa"] == "ACTIVE"


def test_cross_site_requests_are_refused(client):
    evil = {"origin": "https://evil.example"}
    assert client.post("/api/auth/login", json={"profile": "camille", "code": "compass"}, headers=evil).status_code == 403
    login(client)
    assert client.post("/api/cards/card_visa/lock", json={}, headers=evil).status_code == 403
    assert client.post("/api/auth/logout", json={}, headers=evil).status_code == 403
    # A form post (no JSON) can't do it either.
    form = client.post("/api/cards/card_visa/lock", data={"x": "1"}, headers=ORIGIN)
    assert form.status_code == 415
    assert client.delete("/api/demarches", headers=evil).status_code == 403


def test_recap_pdfs_are_only_for_their_session(client):
    login(client)
    session = bank_store.get_session(client.cookies[server.COOKIE])
    name = "A" * 22 + ".pdf"
    server.RECAPS_DIR.mkdir(parents=True, exist_ok=True)
    (server.RECAPS_DIR / name).write_bytes(b"%PDF-1.7 test")
    bank_store.add_demarche(session, "REC 00 00 01", "complaint", "t", "d", "transmitted", "text", name)
    assert client.get(f"/api/recaps/{name}").status_code == 200
    assert client.get("/api/demarches").json()["demarches"][0]["pdf"] == f"/api/recaps/{name}"
    with TestClient(server.app) as other:
        other.get("/api/me")
        login(other)
        assert other.get(f"/api/recaps/{name}").status_code == 404
    assert client.get("/api/recaps/..%2F.env").status_code == 404


def test_cookie_flags(client):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    https = client.post(
        "/api/auth/login",
        json={"profile": "camille", "code": "compass"},
        headers={**ORIGIN, "x-forwarded-proto": "https"},
    )
    assert "secure" in https.headers["set-cookie"].lower()


def test_errors_dont_leak_internals(client):
    response = client.post("/api/auth/login", content="{not json", headers={**ORIGIN, "content-type": "application/json"})
    assert response.status_code == 422
    assert "Traceback" not in response.text
    assert client.get("/api/nothing-here").status_code == 404


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"


def test_voice_speaks_at_normal_speed_and_lets_the_customer_think():
    _, session = bank_store.new_session()
    audio = server.session_config(session, push_to_talk=False)["audio"]
    assert audio["output"]["speed"] == 1.0
    assert audio["input"]["turn_detection"]["eagerness"] == "low"


def test_ratings_are_counted_and_checked(client):
    before = client.get("/api/ratings").json()
    for stars, mode in ((5, "voice"), (2, "text")):
        response = client.post("/api/ratings", json={"stars": stars, "mode": mode}, headers=ORIGIN)
        assert response.status_code == 200
    after = client.get("/api/ratings").json()
    assert after["count"] == before["count"] + 2
    assert 1 <= after["average"] <= 5
    for bad in ({"stars": 0, "mode": "text"}, {"stars": 6, "mode": "text"}, {"stars": 3, "mode": "fax"}):
        assert client.post("/api/ratings", json=bad, headers=ORIGIN).status_code == 422
    foreign = client.post("/api/ratings", json={"stars": 5, "mode": "text"}, headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403
    assert client.get("/api/ratings").json()["count"] == after["count"]


def test_rating_needs_a_session():
    with TestClient(server.app) as fresh:
        response = fresh.post("/api/ratings", json={"stars": 5, "mode": "text"}, headers=ORIGIN)
    assert response.status_code == 401
