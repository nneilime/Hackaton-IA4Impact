"""FastAPI layer between the front-end and the engine. All decisions and numbers come from the engine.

Run:   uvicorn dispatch.api.app:app --reload --app-dir src        (docs: http://localhost:8000/docs)

Typical front-end flow
  POST /sessions {crisis_id}                       -> session_id + snapshot (map: teams, incidents, plan)
  POST /sessions/{id}/advance {to_h? | next event}  -> new snapshot
  GET  /sessions/{id}/recommendations               -> cards: text, facts, alternative cost, past-refusal hint
  POST /sessions/{id}/accept {team, incident}       -> team dispatched (if not the recommended one = modification)
  POST /sessions/{id}/reject {team, incident, reason_code?, reason_text?}
        -> {question} (ask the manager, then call reject again with more text)
        or {proposal_id, restatement, cost_delta, modifiers}  -> show "Compris : … Appliquer ? (coût …)"
  POST /sessions/{id}/proposals/{pid}/confirm | /cancel
  GET  /sessions/{id}/service                       -> projected % fixed at H+48, reinforcement if needed
  POST /sessions/{id}/what-if {modifiers:[…]}       -> cost of a hypothetical choice
  GET  /learning/candidates, POST /learning/candidates/backtest, POST /learning/registry/activate
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from dispatch.config import ROOT, load_config
from dispatch.copilot.translate import REASONS
from dispatch.copilot.validator import InvalidModifier, validate
from dispatch.data.loaders import list_crises, list_scenarios
from dispatch.engine.modifiers import to_dict
from dispatch.engine.shifts import is_on_duty, window
from dispatch.learning import registry as reg
from dispatch.learning import review
from dispatch.learning.memory import DecisionLog
from dispatch.session import LiveSession

cfg = load_config()
log = DecisionLog(ROOT / cfg.learning.db_path)
sessions: dict[str, LiveSession] = {}
_lock = threading.Lock()
_ids = itertools.count(1)

app = FastAPI(title="Pilotage de crise - moteur de dispatch", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)          # timelines: ~17 MB of JSON -> ~1-2 MB

from dispatch.api import frontend as _front  # noqa: E402  (EnedisPO front-end routes, replay of a past crisis)
from dispatch.api import live as _live  # noqa: E402  (EnedisPO front-end routes, real time)

_front.cfg, _front.log = cfg, log
_live.cfg, _live.log = cfg, log
app.include_router(_live.router)
app.include_router(_front.router)
app.include_router(_front.routes_router)


@app.on_event("startup")
def _warm_up():
    _live.start_ticker()
    _front.warm_up(cfg.timeline.default_crisis)


# ------------------------------------------------------------------ request bodies
class StartBody(BaseModel):
    crisis_id: str
    budget_ms: int | None = Field(None, description="local search budget per re-plan (default: config)")
    teams_fraction: float = Field(1.0, gt=0, le=1, description="stress test: keep this share of teams")


class AdvanceBody(BaseModel):
    to_h: float | None = Field(None, description="hours since H0; omit to jump to the next event")
    auto_accept: bool = Field(False, description="replay mode: accept every recommendation on the way")


class PairBody(BaseModel):
    team: str
    incident: str


class RejectBody(PairBody):
    reason_code: str | None = Field(None, description=f"one of {list(REASONS)}")
    reason_text: str | None = None


class ModifiersBody(BaseModel):
    modifiers: list[dict]


class CandidateBody(BaseModel):
    candidate: dict
    crises: list[str] | None = None
    budget_ms: int = 0
    approved_by: str | None = None


# ------------------------------------------------------------------ helpers
def get(sid: str) -> LiveSession:
    if sid not in sessions:
        raise HTTPException(404, "session inconnue")
    return sessions[sid]


def snapshot(s: LiveSession) -> dict:
    W, R = cfg.roster.work_h, cfg.roster.rest_h
    status = {iid: "restored" for iid in s.restored}
    status.update({iid: "in_progress" for iid in s.in_progress})
    status.update({iid: "pending" for iid in s.pending})
    eta = s.projected_restoration()
    team_of = {iid: v[0] for iid, v in s.in_progress.items()}
    if s.plan:
        team_of.update({iid: tid for tid, r in s.plan.routes.items() for iid in r})
    teams = []
    for t in s.teams:
        sh_s, sh_e = window(t.shift_start, s.now, W, R)
        teams.append({"id": t.id, "site": t.home_site, "lat": t.lat, "lon": t.lon, "status": t.status.value,
                      "on_duty": is_on_duty(t.shift_start, s.now, W, R), "current_job": t.current_job,
                      "free_at_h": t.free_at, "shift": {"start_h": sh_s, "end_h": sh_e},
                      "next_jobs": (s.plan.routes.get(t.id, []) if s.plan else [])[:3]})
    known = [i for i in s.incidents if i.reported_at <= s.now + 1e-9]
    incidents = [{"id": i.id, "poste": i.poste_id, "lat": i.lat, "lon": i.lon, "commune": i.commune,
                  "departement": i.departement, "customers": i.customers, "sensitive": bool(i.sensitive),
                  "cause": i.cause, "reported_h": i.reported_at, "repair_h": i.est_duration,
                  "status": status.get(i.id, "pending"), "team": team_of.get(i.id),
                  "restored_h": eta.get(i.id), "restored_clock": s.clock(eta[i.id]) if i.id in eta else None}
                 for i in known]
    return {"crisis": s.crisis_id, "kpis": s.kpis(), "plan_version": s.plan_version,
            "plan_score": asdict(s.plan.score) if s.plan else None, "teams": teams, "incidents": incidents,
            "rules": [to_dict(m) for m in s.rules], "permanent_rules": [to_dict(m) for m in s.permanent],
            "pending_proposals": list(s.proposals)}


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"ok": True, "llm": __import__("dispatch.copilot.client", fromlist=["x"]).llm_available()}


@app.get("/crises")
def crises():
    return list_scenarios(cfg) + list_crises(cfg)


@app.get("/reasons")
def reasons():
    """Quick reason chips for the refusal dialog."""
    return [{"code": k, "label": v} for k, v in REASONS.items()]


@app.post("/sessions")
def start(body: StartBody):
    if body.crisis_id not in list_crises(cfg) and body.crisis_id not in list_scenarios(cfg):
        raise HTTPException(404, "crise inconnue")
    s = LiveSession.start(cfg, body.crisis_id, budget_ms=body.budget_ms, log=log, teams_fraction=body.teams_fraction)
    sid = str(next(_ids))
    sessions[sid] = s
    return {"session_id": sid, **snapshot(s)}


@app.get("/sessions/{sid}")
def state(sid: str):
    return snapshot(get(sid))


@app.post("/sessions/{sid}/advance")
def advance(sid: str, body: AdvanceBody):
    s = get(sid)
    with _lock:
        n = s.advance(body.to_h, auto_accept=body.auto_accept)
    return {"dispatched": n, **snapshot(s)}


@app.get("/sessions/{sid}/map")
def map_layers(sid: str):
    """GeoJSON FeatureCollection: properties.layer in site, team, incident, route, heat, zone (see docs/API.md)."""
    return get(sid).geojson()


@app.get("/sessions/{sid}/recommendations")
def recommendations(sid: str):
    return get(sid).recommendations()


@app.get("/sessions/{sid}/recommendations/{team}/{incident}/explanation")
def explanation(sid: str, team: str, incident: str):
    """Expanded card: {headline, details (LLM if available and compliant, else template), source}."""
    return get(sid).explanation(team, incident)


@app.post("/sessions/{sid}/accept")
def accept(sid: str, body: PairBody):
    s = get(sid)
    if body.incident not in s.pending:
        raise HTTPException(409, "incident déjà pris en charge ou inconnu")
    with _lock:
        s.accept(body.team, body.incident)
    return snapshot(s)


@app.post("/sessions/{sid}/reject")
def reject(sid: str, body: RejectBody):
    s = get(sid)
    if body.incident not in s.pending:
        raise HTTPException(409, "incident déjà pris en charge ou inconnu")
    with _lock:
        return s.reject(body.team, body.incident, body.reason_code, body.reason_text)


@app.post("/sessions/{sid}/proposals/{pid}/confirm")
def confirm(sid: str, pid: int):
    s = get(sid)
    if pid not in s.proposals:
        raise HTTPException(404, "proposition inconnue")
    with _lock:
        s.confirm(pid)
    return snapshot(s)


@app.post("/sessions/{sid}/proposals/{pid}/cancel")
def cancel(sid: str, pid: int):
    get(sid).cancel(pid)
    return {"ok": True}


@app.delete("/sessions/{sid}/rules/{index}")
def remove_rule(sid: str, index: int):
    s = get(sid)
    if not 0 <= index < len(s.rules):
        raise HTTPException(404, "règle inconnue")
    s.remove_rule(index)
    return snapshot(s)


@app.post("/sessions/{sid}/what-if")
def what_if(sid: str, body: ModifiersBody):
    s = get(sid)
    try:
        mods = [validate(m, s) for m in body.modifiers]
    except InvalidModifier as e:
        raise HTTPException(422, str(e))
    return s.what_if(mods)


@app.get("/sessions/{sid}/service")
def service(sid: str, reinforcement: bool = True):
    return get(sid).service(with_reinforcement=reinforcement)


@app.get("/learning/stats")
def learning_stats():
    return log.stats()


@app.get("/learning/candidates")
def learning_candidates(min_refusals: int | None = None):
    from dispatch.data.loaders import load_sites
    names = {x.id: x.commune for x in load_sites(cfg)}
    return review.candidates(log, min_refusals or cfg.learning.review_min_refusals, names)


@app.post("/learning/candidates/backtest")
def learning_backtest(body: CandidateBody):
    crises_ = body.crises or list_crises(cfg)[::10]
    return review.backtest(body.candidate, cfg, crises_, body.budget_ms)


@app.post("/learning/registry/activate")
def learning_activate(body: CandidateBody):
    if not body.approved_by:
        raise HTTPException(422, "approved_by (rôle de l'expert) obligatoire")
    entry = reg.activate(body.candidate, body.approved_by)
    _front.invalidate_all()                       # crises are recomputed with the new permanent rule
    _live.reload_registry()
    return entry


class SimulateBody(BaseModel):
    crises: list[str] = ["CRISE_051", "CRISE_046"]


@app.post("/learning/simulate")
def learning_simulate(body: SimulateBody):
    """Demo data: replay crises with the SIMULATED manager (hidden preference), refusals logged as simulated."""
    from dispatch.learning import simulated
    return {"counts": simulated.run(cfg, body.crises, log), "stats": log.stats()}


@app.post("/learning/registry/{constraint_id}/retire")
def learning_retire(constraint_id: str):
    reg.retire(constraint_id)
    _front.invalidate_all()
    _live.reload_registry()
    return reg.read()


@app.get("/learning/remarks")
def learning_remarks(limit: int = 12):
    """The manager's remarks (refusals with their reason), most recent first: the knowledge base the AI learns from."""
    from dispatch.data.loaders import load_sites
    names = {x.id: x.commune for x in load_sites(cfg)}
    rows = log.rejections()[-limit:][::-1]
    return [{"crisis": r["crisis"], "team": r["team"], "site": names.get(r["site"], r["site"]), "commune": r["commune"],
             "departement": r["departement"], "reason_code": r["reason_code"], "reason_text": r["reason_text"],
             "simulated": bool(r["simulated"])} for r in rows]


@app.get("/learning/registry")
def learning_registry():
    return reg.read()
