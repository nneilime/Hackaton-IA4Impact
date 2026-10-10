"""Tests de l'API (backend/app) sur la VRAIE base, en lecture seule.

Ils nécessitent DATABASE_URL dans .env ; sans elle, tout le fichier est ignoré (skip).
Chaque appel interroge un serveur distant : comptez quelques secondes par test.
"""
import os

import pytest

try:
    from fastapi.testclient import TestClient

    from backend.app.main import app   # charge aussi le fichier .env
except Exception as error:  # pragma: no cover
    pytest.skip(f"API non importable : {error}", allow_module_level=True)

if not os.environ.get("DATABASE_URL"):
    pytest.skip("DATABASE_URL absent : tests API ignorés", allow_module_level=True)

DISCLAIMER = "Pas une source réglementaire officielle. Validation Regulatory Affairs requise."


@pytest.fixture(scope="module")
def client():
    os.environ["API_KEY"] = ""   # accès libre pour ces tests (la clé est testée à part)
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_under_api_prefix(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_gliocladium_finds_clonostachys_rosea(client):
    items = client.get("/api/products", params={"q": "gliocladium"}).json()["items"]
    assert items, "le synonyme Gliocladium doit retrouver des produits Clonostachys rosea"
    assert any((i.get("activeEntityNormalized") or "").startswith("Clonostachys rosea") for i in items)
    assert all(i.get("matchedVia", {}).get("matchedName") for i in items)   # matchedVia toujours renseigné
    assert all(not i["isSynthetic"] for i in items)                         # fictif exclu par défaut


def test_search_prestop_finds_france_and_canada(client):
    for country in ("FR", "CA"):
        items = client.get("/api/products", params={"q": "PRESTOP", "country": country}).json()["items"]
        assert any("PRESTOP" in i["commercialName"].upper() for i in items), f"PRESTOP introuvable pour {country}"


def test_synthetic_data_hidden_unless_requested(client):
    from backend.app.db import query
    # Ce test s'appuie sur les produits fictifs P-TEST-* : sans eux en base (rechargé avec --no-test), on ignore.
    if not query("SELECT 1 FROM products WHERE is_synthetic AND commercial_name ILIKE '%TEST%' LIMIT 1"):
        pytest.skip("aucun produit fictif TEST en base : rien à masquer")
    default = client.get("/api/products", params={"q": "TEST"}).json()["items"]
    assert not any(i["isSynthetic"] for i in default)
    shown = client.get("/api/products", params={"q": "TEST GLIOCLADIUM", "includeSynthetic": "true"}).json()["items"]
    assert shown and all(i["isSynthetic"] for i in shown if "TEST" in i["commercialName"])


def test_compare_country_without_data_is_not_a_negative_answer(client):
    response = client.get("/api/compare", params={"productId": "P-LPC-G46", "countries": "FR,US"})
    assert response.status_code == 200
    data = response.json()
    coverage = {c["countryCode"]: c for c in data["coverage"]}
    assert coverage["US"]["outcome"] in ("not_covered", "not_found")
    assert coverage["FR"]["outcome"] == "found"
    assert any("US" in w for w in data["warnings"])
    assert data["disclaimer"] == DISCLAIMER


def test_registrations_carry_originals_evidence_and_coverage(client):
    data = client.get("/api/products/P-LPC-G46/registrations", params={"limit": 3}).json()
    assert data["items"] and data["coverage"] and data["disclaimer"] == DISCLAIMER
    first = data["items"][0]
    assert first["evidence"]["evidenceId"].startswith("registration:")
    assert first["evidence"]["sourceRecordUrl"] and first["evidence"]["collectedAt"]
    assert first["matchedVia"]["matchedOn"]
    assert "statusOriginal" in first and "productNameOriginal" in first


def test_unknown_product_is_404_with_safe_message(client):
    response = client.get("/api/products/P-DOES-NOT-EXIST/registrations")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "No match. This is not proof of no registration."}


def test_sisters_are_hypotheses(client):
    data = client.get("/api/products/P-LPC-G46/sisters").json()
    assert data["candidates"]
    assert all(c["reviewStatus"] in ("to_verify", "validated", "confirmed", "rejected") for c in data["candidates"])
    names = [c["candidateName"].lower() for c in data["candidates"]]
    assert len(names) == len(set(names)), "dédoublonné par nom"


def test_sources_and_expirations_and_issues(client):
    sources = client.get("/api/sources").json()["items"]
    assert {"FR-EPHY", "CA-PPID"} <= {s["sourceId"] for s in sources}
    assert client.get("/api/expirations", params={"limit": 3}).status_code == 200
    issues = client.get("/api/issues", params={"productId": "P-LPC-G46", "limit": 3}).json()
    assert issues["items"] and issues["countsByType"]


def test_ask_is_implemented(client):
    """/ask répond au schéma Answer (le détail de l'agent est testé dans test_agent.py)."""
    response = client.post("/api/ask", json={"question": "Quelle est la météo à Paris ?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answerStatus"] == "out_of_scope" and body["disclaimer"] == DISCLAIMER
    assert client.post("/api/ask", json={"question": "a"}).status_code == 422


def test_api_key_required_only_when_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    assert client.get("/api/sources").status_code == 401
    assert client.get("/api/sources", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/api/health").status_code == 200   # /health reste public


def test_compare_crop_level_has_a_common_crop_and_original_units(client):
    """granularity=crop : une ligne par culture, cible ignorée pour l'alignement, doses par unité ORIGINALE."""
    data = client.get("/api/compare", params={"productId": "P-LPC-G46", "countries": "FR,CA", "granularity": "crop"}).json()
    assert data["granularity"] == "crop"
    assert data["rows"] and all(r["targetNormalized"] is None for r in data["rows"])
    common = [r for r in data["rows"] if sum(c["state"] == "present" for c in r["cells"]) >= 2]
    if not common:
        pytest.skip("aucune culture commune FR/CA dans les données actuelles")
    for cell in common[0]["cells"]:
        summary = cell["summary"]
        assert summary["useCount"] == len(cell["uses"])
        units = {u["doseUnitOriginal"] for u in cell["uses"] if u["doseValue"] is not None}
        assert {d["unitOriginal"] for d in summary["doses"]} == units   # jamais de conversion ni de mélange d'unités
        assert all(d["min"] <= d["max"] for d in summary["doses"])


def test_compare_use_level_suggests_crop_level_when_nothing_is_comparable(client):
    data = client.get("/api/compare", params={"productId": "P-LPC-G46", "countries": "FR,CA"}).json()
    assert data["granularity"] == "use"
    if not any(sum(c["state"] == "present" for c in r["cells"]) >= 2 for r in data["rows"]):
        assert any("granularity=crop" in w for w in data["warnings"])


def test_compare_rejects_unknown_granularity(client):
    assert client.get("/api/compare", params={"productId": "P-LPC-G46", "countries": "FR,CA", "granularity": "x"}).status_code == 422
