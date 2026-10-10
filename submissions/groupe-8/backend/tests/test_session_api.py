"""Live session, LLM fallback, knowledge base, review loop and HTTP API."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from dispatch.config import load_config
from dispatch.copilot.translate import fallback
from dispatch.copilot.validator import InvalidModifier, validate
from dispatch.learning import registry, review
from dispatch.learning.memory import DecisionLog
from dispatch.session import LiveSession

cfg = load_config()


@pytest.fixture()
def session():
    s = LiveSession.start(cfg, "CRISE_050", budget_ms=20, log=DecisionLog())
    s.advance(1.0)
    return s


def test_recommendations_have_text_and_facts(session):
    recs = session.recommendations()
    assert recs and all("text" in r and r["facts"]["factors"]["customers"] > 0 for r in recs)
    assert [r["facts"]["rank_in_plan"] for r in recs] == sorted(r["facts"]["rank_in_plan"] for r in recs)


def test_accept_dispatches_and_logs(session):
    r = session.recommendations()[0]
    session.accept(r["team"], r["incident"])
    assert r["incident"] in session.in_progress and r["incident"] not in session.pending
    assert session.log.stats()["accepted"] == 1


def test_reject_flood_creates_priced_rule(session):
    r = session.recommendations()[0]
    out = session.reject(r["team"], r["incident"], reason_text="route inondée jusqu'à 18h")
    assert out["modifiers"][0]["type"] == "zone_inaccessible" and "cost_delta" in out
    session.confirm(out["proposal_id"])
    assert session.rules and session.log.stats()["rejected"] == 1
    inc = next(i for i in session.incidents if i.id == r["incident"])
    if inc.id in session.plan.schedule:
        assert session.plan.schedule[inc.id][0] >= session.rules[0].until_h - 1e-6


def test_reject_without_info_asks_a_question(session):
    r = session.recommendations()[0]
    assert "question" in session.reject(r["team"], r["incident"], reason_code="equipe")


def test_validator_rejects_bad_rules(session):
    with pytest.raises(InvalidModifier):
        validate({"type": "zone_inaccessible", "zone": "Paris", "until_h": 5}, session)
    with pytest.raises(InvalidModifier):
        validate({"type": "duration_update", "incident": next(iter(session.pending)), "hours": 30}, session)
    with pytest.raises(InvalidModifier):
        validate({"type": "rest_rule", "hours": 2}, session)


def test_translate_fallback_parses_hours():
    ctx = {"team": "T", "incident": "I", "commune": "Muret", "now_h": 1.0, "t0": datetime(2017, 5, 28, 2, 48)}
    out = fallback(None, "véhicule en panne pendant 3 h", ctx)
    assert out["modifiers"][0]["type"] == "team_unavailable" and out["modifiers"][0]["until_h"] == pytest.approx(4.0)
    assert fallback("duree", "plutôt 8 h", ctx)["modifiers"][0]["hours"] == 8.0


def test_past_refusal_hint_and_review(session):
    r = session.recommendations()[0]
    team = session.team(r["team"]); inc = session.pending[r["incident"]]
    for _ in range(3):
        session.log.append({"crisis": "X", "team": team.id, "site": team.home_site, "incident": "Y",
                            "commune": inc.commune, "departement": inc.departement, "decision": "rejected",
                            "reason_code": "terrain", "reason_text": "mauvais accès",
                            "modifiers": [{"type": "forbid", "team_or_site": team.home_site,
                                           "incident_or_zone": inc.commune}]}, simulated=True)
    hint = session._past_refusal_hint(team.id, inc.id)
    assert hint and hint["count"] == 3 and "Appliquer la même règle" in hint["question"]
    cands = review.candidates(session.log, 3)
    # the AI proposes to adjust a variable of the calculation (travel time towards the zone), not a hard rule
    c = cands[0]
    assert c["modifier"] == {"type": "travel_factor", "zone": inc.commune, "factor": 1.3}
    assert c["variable"].startswith("Temps de trajet") and c["before"] == "×1" and c["after"] == "×1,3" and c["observed"]


def test_registry_roundtrip(tmp_path):
    p = tmp_path / "reg.yaml"
    cand = {"description": "test", "modifier": {"type": "forbid", "team_or_site": "SITE_04", "incident_or_zone": "Ariège"}}
    e = registry.activate(cand, "expert", path=p)
    assert e["registry_version"] == 1
    mods = registry.load_registry(path=p)
    assert len(mods) == 1 and mods[0].team_or_site == "SITE_04"
    registry.retire(e["id"], path=p)
    assert registry.load_registry(path=p) == []


def test_service_and_reinforcement_under_stress():
    s = LiveSession.start(cfg, "CRISE_082", budget_ms=10, log=DecisionLog(), teams_fraction=0.25)
    s.advance(6.0)
    out = s.service()
    assert 0 <= out["projected_share"] <= 1
    if not out["target_met"]:
        assert out["reinforcement"]["extra_teams"] >= 1


def test_api_flow(monkeypatch):
    import dispatch.api.app as api
    monkeypatch.setattr(api, "log", DecisionLog())
    c = TestClient(api.app)
    assert c.get("/health").json()["ok"]
    assert len(c.get("/crises").json()) == 100
    r = c.post("/sessions", json={"crisis_id": "CRISE_050", "budget_ms": 20}).json()
    sid = r["session_id"]
    snap = c.post(f"/sessions/{sid}/advance", json={"to_h": 1.0}).json()
    assert snap["kpis"]["known"] > 0 and snap["teams"] and snap["incidents"]
    recs = c.get(f"/sessions/{sid}/recommendations").json()
    assert recs and recs[0]["text"]
    a = recs[0]
    assert c.post(f"/sessions/{sid}/accept", json={"team": a["team"], "incident": a["incident"]}).status_code == 200
    b = c.get(f"/sessions/{sid}/recommendations").json()[0]
    prop = c.post(f"/sessions/{sid}/reject", json={"team": b["team"], "incident": b["incident"],
                                                   "reason_code": "competence"}).json()
    assert "proposal_id" in prop and prop["restatement"]
    snap = c.post(f"/sessions/{sid}/proposals/{prop['proposal_id']}/confirm").json()
    assert snap["rules"]
    assert "projected_share" in c.get(f"/sessions/{sid}/service").json()
    wi = c.post(f"/sessions/{sid}/what-if", json={"modifiers": [{"type": "zone_inaccessible", "zone": "Nowhere",
                                                                 "until_h": 3}]})
    assert wi.status_code == 422
    assert c.get("/learning/stats").json()["total"] == 2


def test_map_layers(session):
    r = session.recommendations()[0]
    session.accept(r["team"], r["incident"])
    gj = session.geojson()
    layers = {f["properties"]["layer"] for f in gj["features"]}
    assert {"site", "team", "incident", "route", "heat"} <= layers
    shares = [f["properties"]["score_share"] for f in gj["features"] if f["properties"]["layer"] == "incident"]
    assert abs(sum(shares) - 1) < 0.01            # the score splits per incident
    committed = [f for f in gj["features"] if f["properties"]["layer"] == "route" and f["properties"]["committed"]]
    assert committed and committed[0]["geometry"]["type"] == "LineString"


def test_business_justification_two_sentences(session):
    from dispatch.copilot.explain import check_numbers_grounded, sentence_count
    for r in session.recommendations():
        assert sentence_count(r["text"]) == 2, r["text"]
    recs = session.recommendations()
    from dispatch.engine.types import ExplanationFacts
    facts = ExplanationFacts(**recs[0]["facts"])
    assert check_numbers_grounded(recs[0]["text"], facts)
    assert not check_numbers_grounded("Cela rétablit 99999 clients.", facts)
