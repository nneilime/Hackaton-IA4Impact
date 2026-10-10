"""Tests du préchauffage (backend/app/warmup.py) : lecture des requêtes de démo, sans base de données."""
from backend.app import services, warmup


def test_demo_requests_reads_get_requests_and_skips_placeholders(tmp_path):
    md = tmp_path / "demo.md"
    md.write_text(
        "- A : `GET /opportunities?country=FR&lpcOnly=true&limit=5`\n"
        "- B : `GET /products?crop=Barley&target=Rust (Puccinia)` puis `GET /compare?productId=<id>&countries=FR,DE`\n"
        "- A encore : `GET /opportunities?country=FR&lpcOnly=true&limit=5`\n"
        "- C : `GET /expirations?country=FR`\n"
        "- pas une requête : `uvicorn backend.app.main:app --port 3000`\n", encoding="utf-8")
    assert warmup.demo_requests(md) == [
        "/opportunities?country=FR&lpcOnly=true&limit=5",       # sans doublon
        "/products?crop=Barley&target=Rust+%28Puccinia%29",     # espaces et parenthèses encodés
        "/expirations?country=FR"]                              # <id> ignoré


def test_demo_requests_missing_file_gives_nothing(tmp_path):
    assert warmup.demo_requests(tmp_path / "absent.md") == []


def test_real_demo_file_contains_the_opportunities_demo_phrase():
    assert "/opportunities?country=FR&lpcOnly=true&limit=5" in warmup.demo_requests()


def test_cached_recomputes_old_values_during_a_refresh(monkeypatch):
    calls = []

    @services.cached(1000)
    def slow(x):
        calls.append(x)
        return x

    slow(1)
    slow(1)
    assert calls == [1]                                    # deuxième appel : valeur gardée
    monkeypatch.setattr(services, "REFRESH_MAX_AGE", 0)    # rafraîchissement : tout ce qui n'est pas neuf est recalculé
    slow(1)
    assert calls == [1, 1]


def test_start_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WARMUP", "0")
    assert warmup.start(object()) is None
