"""Contract tests for the EnedisPO front-end routes (frontend/src/data/contract.ts)."""
from fastapi.testclient import TestClient

from dispatch.learning.memory import DecisionLog

INC_STATUS = {"waiting", "enroute", "repairing", "restored"}
TEAM_STATUS = {"available", "travelling", "repairing", "resting"}


def test_timeline_contract(monkeypatch):
    import dispatch.api.app as api
    import dispatch.api.frontend as front
    monkeypatch.setattr(front, "log", DecisionLog())
    monkeypatch.setattr(front, "_runs", {})
    monkeypatch.setattr(api, "_warm_up", lambda: None)
    c = TestClient(api.app)
    meta = c.get("/crises/CRISE_050/meta").json()
    assert meta["stepMinutes"] == 30 and len(meta["sites"]) == 18 and {s["id"] for s in meta["strategies"]} == {"ours", "reference"}
    tl = c.get("/crises/CRISE_050/timelines").json()
    ours, ref = tl["ours"], tl["reference"]
    assert len(ours) == len(ref) > 2
    last = ours[-1]["kpis"]
    assert last["clientsCut"] == 0 and last["score"] < last["scoreBaseline"]
    snap = next(s for s in ours if s["recommendations"])
    assert all(i["status"] in INC_STATUS for i in snap["incidents"])
    assert all(t["status"] in TEAM_STATUS and t["label"] for t in snap["teams"])
    rec = snap["recommendations"][0]
    for k in ("id", "teamId", "incidentId", "eta", "travelMinutes", "priority", "factors", "alternatives"):
        assert k in rec
    assert set(rec["factors"]) == {"clients", "sensitive", "travelMinutes", "repairHours", "shiftHoursLeftAfter"}
    alt = next(a for a in rec["alternatives"] if a["feasible"])
    step = ours.index(snap)
    body = {"step": step, "recommendationId": rec["id"], "incidentId": rec["incidentId"], "teamId": alt["teamId"],
            "recommendedTeamId": rec["teamId"], "reason": "Connaissance terrain", "kind": "overridden"}
    tl2 = c.post("/crises/CRISE_050/decisions", json=body).json()
    s2 = tl2["ours"][step]
    assert s2["decisions"][0]["teamId"] == alt["teamId"]
    nxt = tl2["ours"][step + 1]
    assert next(i for i in nxt["incidents"] if i["id"] == rec["incidentId"]).get("teamId") == alt["teamId"]
    assert front.log.stats()["rejected"] == 1                     # override logged with its reason
    tl3 = c.delete("/crises/CRISE_050/decisions").json()
    assert not tl3["ours"][step]["decisions"]


def _client(monkeypatch):
    import dispatch.api.app as api
    import dispatch.api.frontend as front
    monkeypatch.setattr(front, "log", DecisionLog())
    monkeypatch.setattr(front, "_runs", {})
    monkeypatch.setattr(api, "_warm_up", lambda: None)
    return TestClient(api.app), front


def test_phase2_explanation_and_copilot(monkeypatch):
    c, _ = _client(monkeypatch)
    ours = c.get("/crises/CRISE_050/timelines").json()["ours"]
    k = next(i for i, s in enumerate(ours) if s["recommendations"])
    rec = ours[k]["recommendations"][0]
    e = c.get("/crises/CRISE_050/explanation", params={"step": k, "incident": rec["incidentId"]}).json()
    assert e["headline"] and len(e["paragraphs"]) == 2 and e["limits"].startswith("Limites")
    for q in ("Pourquoi cette équipe ?", "Quels clients sensibles attendent ?", "Où est la saturation ?",
              "Faut-il des renforts ?"):
        a = c.post("/crises/CRISE_050/copilot", json={"question": q, "step": k, "recId": rec["id"]}).json()
        assert a["answer"], q


def test_phase3_refusal_rule_and_rules_panel(monkeypatch):
    c, front = _client(monkeypatch)
    ours = c.get("/crises/CRISE_050/timelines").json()["ours"]
    k = next(i for i, s in enumerate(ours) if s["recommendations"])
    rec = ours[k]["recommendations"][0]
    q = c.post("/crises/CRISE_050/refusals", json={"step": k, "incidentId": rec["incidentId"], "teamId": rec["teamId"],
                                                   "reasonCode": "equipe"}).json()
    assert "question" in q                                         # missing duration -> the system asks
    p = c.post("/crises/CRISE_050/refusals", json={"step": k, "incidentId": rec["incidentId"], "teamId": rec["teamId"],
                                                   "reasonText": "route inondée jusqu'à 23h"}).json()
    assert p["proposalId"] and p["restatement"] and "costDelta" in p
    tl = c.post(f"/crises/CRISE_050/refusals/{p['proposalId']}/confirm").json()
    assert len(tl["ours"]) > k and front.log.stats()["rejected"] == 1
    rules = c.get("/crises/CRISE_050/rules").json()
    assert len(rules["crisis"]) == 1 and rules["crisis"][0]["label"]
    c.delete("/crises/CRISE_050/rules/0")
    assert c.get("/crises/CRISE_050/rules").json()["crisis"] == []


def test_phase3_reinforcement_and_routes(monkeypatch):
    c, _ = _client(monkeypatch)
    r = c.get("/crises/CRISE_050/reinforcement", params={"step": 2, "team_share": 0.25}).json()
    assert 0 <= r["projected_share"] <= 1 and "target_met" in r
    import dispatch.data.routes as road
    monkeypatch.setattr(road, "_offline_until", 1e18)             # no network in tests: straight line
    monkeypatch.setattr(road, "_cache", {})
    out = c.post("/routes", json={"pairs": [[[1.44, 43.6], [1.6, 42.96]]]}).json()
    assert out[0]["coordinates"][0] == [1.44, 43.6] and out[0]["source"] == "straight"


def test_accept_whole_plan(monkeypatch):
    """'Valider le plan': every recommendation of the step is accepted in one action, one replay."""
    import dispatch.api.app as api
    import dispatch.api.frontend as front
    monkeypatch.setattr(front, "log", DecisionLog())
    monkeypatch.setattr(front, "_runs", {})
    monkeypatch.setattr(api, "_warm_up", lambda: None)
    c = TestClient(api.app)
    ours = c.get("/crises/CRISE_050/timelines").json()["ours"]
    step = next(k for k, s in enumerate(ours) if len(s["recommendations"]) >= 2)
    recs = ours[step]["recommendations"]
    tl = c.post("/crises/CRISE_050/plan/accept", json={"step": step}).json()
    decided = {d["incidentId"]: d for d in tl["ours"][step]["decisions"]}
    assert set(decided) == {r["incidentId"] for r in recs}
    assert all(decided[r["incidentId"]]["teamId"] == r["teamId"] and decided[r["incidentId"]]["kind"] == "accepted" for r in recs)
    assert front.log.stats()["total"] == len(recs)
    assert c.post("/crises/CRISE_050/plan/accept", json={"step": 10_000}).status_code == 422


def test_plan_explanation(monkeypatch):
    """'Pourquoi ce plan ?': a summary + ≤ 4 points about the whole plan, every figure grounded in the engine's facts."""
    import dispatch.api.app as api
    import dispatch.api.frontend as front
    from dispatch.copilot.plan_explain import grounded, plan_facts, plan_template
    monkeypatch.setattr(front, "log", DecisionLog())
    monkeypatch.setattr(front, "_runs", {})
    monkeypatch.setattr(api, "_warm_up", lambda: None)
    c = TestClient(api.app)
    ours = c.get("/crises/CRISE_050/timelines").json()["ours"]
    step = next(k for k, s in enumerate(ours) if len(s["recommendations"]) >= 2)
    e = c.get("/crises/CRISE_050/plan/explanation", params={"step": step, "llm": False}).json()
    assert e["source"] == "template" and e["resume"].startswith("Ce plan envoie") and 1 <= len(e["points"]) <= 4
    run = front.get_run("CRISE_050")
    tl = run.timelines()
    facts = plan_facts(tl["ours"], tl["reference"], step, run.ours.start.isoformat())
    tpl = plan_template(facts)
    assert grounded(tpl["resume"] + " ".join(tpl["points"]), facts, tpl)
    assert not grounded("Ce plan rétablit 123456 clients.", facts, tpl)        # an invented figure is rejected
