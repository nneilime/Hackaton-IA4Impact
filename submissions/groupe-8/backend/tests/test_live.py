"""Live mode: the engine only learns through field events, nothing moves until the manager validates."""
from fastapi.testclient import TestClient

from dispatch.config import load_config
from dispatch.data.loaders import load_incidents
from dispatch.learning.memory import DecisionLog
from dispatch.live.service import LiveCrisis

cfg = load_config()


class FakeClock:
    def __init__(self, crisis):
        self.h = 0.0
        crisis.clock.now_h = lambda: self.h


def _alerts(n=6):
    incs, _ = load_incidents(cfg, "CRISE_050")
    return [{"type": "incident_reported", "id": i.id, "poste_id": i.poste_id, "est_duration_h": i.est_duration,
             "cause": i.cause} for i in incs[:n]]


def test_live_loop_events_validation_and_field_reports():
    c = LiveCrisis(cfg, DecisionLog())
    clock = FakeClock(c)
    c.tick()
    assert c.state()["snapshot"]["recommendations"] == []                 # waiting for problems
    for a in _alerts():
        c.event(a)
    clock.h = 0.1
    c.tick()
    snap = c.state()["snapshot"]
    recs = snap["recommendations"]
    assert recs and len(snap["incidents"]) == 6
    assert all(i["reportedAt"] >= snap["incidents"][0]["reportedAt"][:10] for i in snap["incidents"])

    clock.h = 0.5                                                          # time passes, nobody validated
    c.tick()
    assert not c.dispatches_after(0)                                       # teams wait for the manager

    r = recs[0]
    out = c.accept([{"incidentId": r["incidentId"], "teamId": r["teamId"]}])
    assert out["dispatched"] == 1
    d = c.dispatches_after(0)
    assert len(d) == 1 and d[0]["team"] == r["teamId"] and d[0]["travel_h"] > 0
    assert c.history[-1]["decisions"][0]["kind"] == "accepted"
    team = next(t for t in c.state()["snapshot"]["teams"] if t["id"] == r["teamId"])
    assert team["status"] == "travelling" and team["group"] in "ABC" and team["shiftEnd"]

    clock.h = 1.0
    c.event({"type": "team_on_site", "team": r["teamId"], "incident": r["incidentId"]})
    inc = next(i for i in c.state()["snapshot"]["incidents"] if i["id"] == r["incidentId"])
    assert inc["status"] == "repairing"
    clock.h = 1.0 + d[0]["repair_h"] + 0.5                                 # the repair overran its estimate
    c.tick()
    assert c.s.team(r["teamId"]).free_at > c.s.now                         # still busy until the field says done
    c.event({"type": "repair_done", "team": r["teamId"], "incident": r["incidentId"]})
    c.tick()
    inc = next(i for i in c.state()["snapshot"]["incidents"] if i["id"] == r["incidentId"])
    assert inc["status"] == "restored" and c.s.log.stats()["accepted"] == 1


def test_live_api(monkeypatch):
    import dispatch.api.app as api
    import dispatch.api.frontend as front
    from dispatch.api import live
    monkeypatch.setattr(live, "log", DecisionLog())
    monkeypatch.setattr(live, "start_ticker", lambda: None)
    monkeypatch.setattr(front, "warm_up", lambda crisis: None)
    c = TestClient(api.app)
    clock = c.post("/live/reset", json={"speed": 60}).json()
    assert clock["speed"] == 60 and clock["start"]
    meta = c.get("/live/meta").json()
    assert meta["mode"] == "live" and {g["id"] for g in meta["roster"]["groups"]} <= {"A", "B", "C"}
    assert c.post("/live/events", json={"type": "nope"}).status_code == 422
    c.post("/live/events", json=_alerts(4))
    live.crisis().tick()
    st = c.get("/live/state").json()
    recs = st["snapshot"]["recommendations"]
    assert recs and st["historyLength"] >= 1
    e = c.get("/live/plan/explanation", params={"llm": False}).json()
    assert e["resume"].startswith("Ce plan envoie")
    assert c.get("/live/explanation", params={"incident": recs[0]["incidentId"]}).json()["paragraphs"]
    a = c.post("/live/copilot", json={"question": "Faut-il des renforts ?"}).json()
    assert "48 h" in a["answer"]
    p = c.post("/live/refusals", json={"incidentId": recs[0]["incidentId"], "teamId": recs[0]["teamId"],
                                       "reasonText": "route inondée pendant 3 h"}).json()
    assert p["restatement"].startswith("Compris")
    assert c.post(f"/live/refusals/{p['proposalId']}/confirm").json()["ok"]
    assert len(c.get("/live/rules").json()["crisis"]) == 1
    recs = c.get("/live/state").json()["snapshot"]["recommendations"]
    out = c.post("/live/plan/accept", json={"assignments": [{"incidentId": r["incidentId"], "teamId": r["teamId"]}
                                                            for r in recs]}).json()
    assert out["dispatched"] == len(recs)
    assert len(c.get("/live/dispatches").json()) == len(recs)
