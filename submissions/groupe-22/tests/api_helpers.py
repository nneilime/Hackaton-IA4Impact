"""Helpers for the API tests."""

ORIGIN = {"origin": "http://testserver"}  # the TestClient's own host


def login(client, profile="camille", code="compass"):
    return client.post(
        "/api/auth/login", json={"profile": profile, "code": code}, headers=ORIGIN
    )
