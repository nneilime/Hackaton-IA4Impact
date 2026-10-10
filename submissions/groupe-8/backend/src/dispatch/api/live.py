"""Live mode routes: the crisis in real time (dispatch/live/service.py).

  The field (in the demo: the separate simulator, simulator/) talks to these:
    POST /live/reset {speed?, label?}          open a new crisis now (H0 = now); speed > 1 runs the clock faster
    POST /live/events {type, ...}              incident_reported {id, poste_id, est_duration_h, cause?}
                                               team_on_site {team, incident} · repair_done {team, incident}
                                               team_unavailable {team, until_h?, reason?}
    GET  /live/dispatches?after=seq            trips started by the manager's validations, for the field to play
  The dashboard talks to these:
    GET  /live/meta · GET /live/state?have=n   current snapshot + new history entries (poll)
    POST /live/plan/accept {assignments}       validate the plan or some lines (incidentId -> teamId)
    GET  /live/plan/explanation · GET /live/explanation?incident · POST /live/copilot
    GET  /live/reinforcement · POST /live/refusals (+ /{pid}/confirm) · GET|POST /live/rules · DELETE /live/rules/{i}
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dispatch.adapters.contract import describe_rule, rule_names
from dispatch.copilot import answers as A
from dispatch.copilot.plan_explain import explain_plan, plan_facts
from dispatch.copilot.validator import InvalidModifier, validate
from dispatch.engine.modifiers import to_dict
from dispatch.live.service import LiveCrisis, Ticker

router = APIRouter(prefix="/live", tags=["live (real time)"])
cfg = None          # set by app.py
log = None
_crisis: LiveCrisis | None = None
_ticker: Ticker | None = None
_explanations: dict = {}


def _prune(c: LiveCrisis) -> None:
    """Explanations of earlier plan versions are useless once the plan changed (a live crisis lasts days)."""
    v = c.s.plan_version
    for k in [k for k in _explanations if k[0] == id(c) and k[1] != v]:
        _explanations.pop(k, None)


def crisis() -> LiveCrisis:
    global _crisis
    if _crisis is None:
        _crisis = LiveCrisis(cfg, log)
    return _crisis


def reload_registry() -> None:
    """The expert registry changed: the live crisis applies the new permanent rules at once."""
    from dispatch.learning.registry import load_registry
    c = crisis()
    with c.lock:
        c.s.permanent = load_registry(cfg)
        c.dirty = True


def start_ticker() -> None:
    global _ticker
    if _ticker is None:
        _ticker = Ticker(crisis, cfg.live.tick_seconds)
        _ticker.start()


# ---------------------------------------------------------------- field side
class ResetBody(BaseModel):
    speed: float = 1.0
    label: str = ""


@router.post("/reset")
def reset(body: ResetBody):
    """Open a new live crisis now. Earlier live state (incidents, decisions, rules) is dropped."""
    global _crisis
    if not 0 < body.speed <= 3600:
        raise HTTPException(422, "vitesse hors plage (0 à 3600)")
    _crisis = LiveCrisis(cfg, log, speed=body.speed, label=body.label)
    _explanations.clear()
    return _crisis.clock.info()


@router.get("/clock")
def clock():
    return crisis().clock.info()


@router.post("/events")
def events(body: dict | list[dict]):
    c = crisis()
    try:
        return [c.event(e) for e in body] if isinstance(body, list) else c.event(body)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"événement invalide : {e}")


@router.get("/dispatches")
def dispatches(after: int = 0):
    return crisis().dispatches_after(after)


# ---------------------------------------------------------------- dashboard side
@router.get("/meta")
def meta():
    return crisis().meta()


@router.get("/state")
def state(have: int = 0):
    return crisis().state(have)


class Assignment(BaseModel):
    incidentId: str
    teamId: str
    reason: str | None = None


class AcceptBody(BaseModel):
    assignments: list[Assignment]
    reason: str | None = None


@router.post("/plan/accept")
def accept(body: AcceptBody):
    if not body.assignments:
        raise HTTPException(422, "aucune affectation")
    return crisis().accept([a.model_dump() for a in body.assignments], body.reason)


def _limits() -> str:
    return ("Limites : temps de trajet modélisés (calés sur 3 718 trajets routiers réels, ±8 min en moyenne), durées de "
            "dépannage issues de la gamme, pas de topologie réseau (un dépannage ne rétablit que son poste).")


@router.get("/plan/explanation")
def plan_explanation(llm: bool = True):
    """'Pourquoi ce plan ?' for the plan on screen (cached per plan version; llm=false is the instant template)."""
    c = crisis()
    _prune(c)
    key = (id(c), c.s.plan_version, "plan", llm)
    if key not in _explanations:
        with c.lock:
            snaps = c.history + [c.snapshot()]
            facts = plan_facts(snaps, None, len(snaps) - 1, c.meta()["start"])
        _explanations[key] = explain_plan(facts, cfg, use_llm=llm)   # outside the lock: the LLM takes seconds
    return _explanations[key]


@router.get("/explanation")
def explanation(incident: str):
    c = crisis()
    with c.lock:
        rec = next((r for r in c._recs() if r["incident"] == incident), None)
        if rec is None:
            raise HTTPException(404, "pas de recommandation pour cet incident")
        key = (id(c), c.s.plan_version, rec["team"], incident)
        _prune(c)
    if key not in _explanations:
        card = c.s.explanation(rec["team"], incident)
        sentences = [x for x in re.split(r"(?<=[.!?])\s+", card["details"].strip()) if x]
        _explanations[key] = {"headline": card["headline"], "paragraphs": sentences, "limits": _limits(),
                              "source": card["source"]}
    return _explanations[key]


@router.get("/reinforcement")
def reinforcement():
    c = crisis()
    with c.lock:
        c._sync()
        return c.s.service(with_reinforcement=True, max_extra=30)


class AskBody(BaseModel):
    question: str
    recId: str | None = None


@router.post("/copilot")
def copilot(body: AskBody):
    c = crisis()
    snap = c.snapshot()
    return A.answer(body.question, snap, cfg, plan_explanation=lambda: plan_explanation(True),
                    rec_explanation=lambda rec: explanation(rec["incidentId"]), reinforcement=reinforcement,
                    rec_id=body.recId)


class RefusalBody(BaseModel):
    incidentId: str
    teamId: str
    reasonCode: str | None = None
    reasonText: str | None = None


def _names(c: LiveCrisis) -> dict:
    return rule_names(c.s, c.site_names)


@router.post("/refusals")
def refuse(body: RefusalBody):
    c = crisis()
    try:
        out = c.refuse(body.incidentId, body.teamId, body.reasonCode, body.reasonText)
    except LookupError as e:
        raise HTTPException(409, str(e))
    if "proposal_id" not in out:
        return out                                               # {question} or {error}
    p = c.s.proposals[out["proposal_id"]]
    rules = [describe_rule(m, _names(c)) for m in p.modifiers]
    return {"proposalId": p.id, "restatement": "Compris : " + " ; ".join(rules) + ".", "costDelta": out["cost_delta"],
            "rules": rules}


@router.post("/refusals/{pid}/confirm")
def confirm(pid: int):
    c = crisis()
    if pid not in c.s.proposals:
        raise HTTPException(404, "proposition inconnue")
    c.confirm(pid)
    return {"ok": True}


class RulesBody(BaseModel):
    modifiers: list[dict]


@router.post("/rules")
def add_rules(body: RulesBody):
    c = crisis()
    with c.lock:
        try:
            mods = [validate(dict(m), c.s) for m in body.modifiers]
        except InvalidModifier as e:
            raise HTTPException(422, str(e))
    c.add_rules(mods)
    return {"ok": True}


@router.get("/rules")
def list_rules():
    c = crisis()
    names = _names(c)
    return {"crisis": [{"index": i, "label": describe_rule(m, names), "rule": to_dict(m), "reason": m.reason}
                       for i, m in enumerate(c.s.rules)],
            "permanent": [{"label": describe_rule(m, names), "rule": to_dict(m), "reason": m.reason}
                          for m in c.s.permanent]}


@router.delete("/rules/{index}")
def delete_rule(index: int):
    c = crisis()
    if not 0 <= index < len(c.s.rules):
        raise HTTPException(404, "règle inconnue")
    c.remove_rule(index)
    return {"ok": True}
