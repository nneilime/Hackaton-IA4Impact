"""Routes for the EnedisPO front-end (frontend/src/data/api/apiSource.ts), timeline mode.

  GET    /crises/{id}/meta                     -> CrisisMeta
  GET    /crises/{id}/timelines                -> {ours: Snapshot[], reference: Snapshot[]}
  POST   /crises/{id}/decisions  DecisionInput & {kind}  -> timelines (replayed from the decision's step)
  DELETE /crises/{id}/decisions                -> timelines (all decisions cancelled)
  GET    /crises/{id}/what-if?team_share=0.5   -> {score, baseline}
Every route also accepts ?team_share= (stress test: keep that share of each site's teams).
Overrides are logged in the knowledge base (learning loop) with the manager's reason.
"""
from __future__ import annotations

import copy
import itertools
import re
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dispatch.adapters.contract import describe_rule, roster, rule_names
from dispatch.adapters.timeline import TimelineRunner, align, session_at
from dispatch.copilot import answers as A
from dispatch.copilot.explain import explain_card
from dispatch.copilot.validator import InvalidModifier, validate
from dispatch.data import routes as road
from dispatch.data.loaders import list_crises, list_scenarios
from dispatch.engine.modifiers import to_dict

router = APIRouter(prefix="/crises", tags=["front-end (timeline mode)"])
_runs: dict[tuple[str, float], "CrisisRun"] = {}
_lock = threading.Lock()
cfg = None          # set by app.py
log = None


class DecisionBody(BaseModel):
    step: int
    recommendationId: str
    incidentId: str
    teamId: str
    recommendedTeamId: str
    reason: str | None = None
    kind: str = "accepted"


class CrisisRun:
    def __init__(self, crisis: str, share: float):
        t = cfg.timeline
        self.crisis, self.share = crisis, share
        self.ours = TimelineRunner(cfg, crisis, share, budget_ms=t.budget_ms, step_minutes=t.step_minutes, log=log)
        self.ref = TimelineRunner(cfg, crisis, share, reference=True, explain=False, step_minutes=t.step_minutes)
        self.decisions: dict[tuple[int, str], dict] = {}
        self.rules: dict[int, list] = {}                         # step -> operator rules applied from that step
        self.proposals: dict[int, dict] = {}
        self._pid = itertools.count(1)
        self.explanations: dict[tuple[int, str], dict] = {}
        self.ref_snaps = self.ref.run()
        self.ours.run()

    def replay(self, k: int) -> dict:
        self.modified = True                                     # the timeline now differs from the pristine run
        self.ours.run(self.decisions, from_step=k, rules=self.rules)
        self.explanations = {key: v for key, v in self.explanations.items() if key[0] < k}
        return self.timelines()

    def timelines(self) -> dict:
        align(self.ours.snapshots, self.ref_snaps, cfg.timeline.step_minutes)
        return {"ours": self.ours.snapshots, "reference": self.ref_snaps}

    def decide(self, d: dict) -> dict:
        k = d["step"]
        self.decisions.pop((k, d["incidentId"]), None)
        for key in [key for key, v in self.decisions.items() if key[0] == k and v["teamId"] == d["teamId"]]:
            del self.decisions[key]                              # a team is committed once per step
        self.decisions[(k, d["incidentId"])] = d
        if log is not None:
            _log(self, d)
        return self.replay(k)

    def decide_plan(self, k: int, overrides: dict[str, str] | None = None, replay: bool = True) -> dict:
        """Validate the whole plan of step k at once: every recommendation of the step is accepted (or, for the incidents
        in `overrides`, assigned to the team the manager chose), then the crisis is replayed once."""
        overrides = overrides or {}
        for rec in self.ours.snapshots[k]["recommendations"]:
            team = overrides.get(rec["incidentId"], rec["teamId"])
            d = {"step": k, "recommendationId": rec["id"], "incidentId": rec["incidentId"], "teamId": team,
                 "recommendedTeamId": rec["teamId"], "kind": "accepted" if team == rec["teamId"] else "overridden",
                 "reason": "Plan validé" if team == rec["teamId"] else "Ajusté dans le plan"}
            self.decisions[(k, d["incidentId"])] = d
            if log is not None:
                _log(self, d)
        # Validating the engine's own plan does not change the projection (the timeline already assumes it):
        # replay=False only records the decisions (journal, knowledge base) and answers at once.
        return self.replay(k) if replay or overrides else {"ok": True}

    def reset(self) -> dict:
        self.decisions, self.rules, self.explanations = {}, {}, {}
        if getattr(self, "modified", False):                     # only a replay (refusal, team change) changed it;
            self.ours.run()                                      # plans recorded without replay did not
            self.modified = False
        return self.timelines()


def _log(run: CrisisRun, d: dict) -> None:
    """Knowledge base entry. An override = the recommendation was refused, with the manager's reason."""
    s = run.ours.base
    inc = next((i for i in s.incidents if i.id == d["incidentId"]), None)
    team = next((t for t in s.teams if t.id == d["recommendedTeamId"]), None)
    if inc is None or team is None:
        return
    overridden = d["kind"] == "overridden"
    log.append({"crisis": s.crisis_id, "sim_time_h": d["step"] * run.ours.step_h, "team": team.id,
                "site": team.home_site, "incident": inc.id, "commune": inc.commune, "departement": inc.departement,
                "customers": inc.customers, "sensitive": bool(inc.sensitive),
                "decision": "rejected" if overridden else "accepted",
                "reason_code": "override" if overridden else None, "reason_text": d.get("reason"),
                "modifiers": [{"type": "force", "team": d["teamId"], "incident": inc.id}] if overridden else [],
                "cost_delta": None, "registry_version": getattr(cfg, "_registry_version", None), "facts": None})


def get_run(crisis: str, share: float = 1.0) -> CrisisRun:
    if crisis not in list_crises(cfg) and crisis not in list_scenarios(cfg):
        raise HTTPException(404, "crise inconnue")
    key = (crisis, round(share, 3))
    with _lock:
        if key not in _runs:
            _runs[key] = CrisisRun(crisis, share)
        return _runs[key]


def warm_up(crisis: str) -> None:
    def go():
        run = get_run(crisis)
        _prefetch_routes(run)
    threading.Thread(target=go, daemon=True).start()


def _prefetch_routes(run: "CrisisRun") -> None:
    """Fetch (and cache on disk) the road geometry of every proposed route of the crisis, in the background, so the
    map never has to wait for the routing service during the demo (same coordinates as the front's requests)."""
    import time
    pairs = []
    for snap in run.ours.snapshots:
        teams = {t["id"]: t for t in snap["teams"]}
        incs = {i["id"]: i for i in snap["incidents"]}
        for r in snap["recommendations"]:
            tm, inc = teams.get(r["teamId"]), incs.get(r["incidentId"])
            if tm and inc:
                pairs.append(((tm["lon"], tm["lat"]), (inc["lon"], inc["lat"])))
    done = 0
    for a, b in dict.fromkeys(pairs):                            # unique, in order of appearance
        known = road._key(a, b) in road._load()
        out = road.route(a, b, cfg.travel.osrm_url)
        done += out["source"] == "osrm"
        if not known:
            time.sleep(0.15)                                     # polite to the public routing service
    print(f"route prefetch {run.crisis}: {done}/{len(dict.fromkeys(pairs))} road routes cached", flush=True)


@router.get("/{crisis}/meta")
def meta(crisis: str, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    s = run.ours.base
    counts = {}
    for t in s.teams:
        counts[t.home_site] = counts.get(t.home_site, 0) + 1
    return {"crisisId": crisis, "mode": "replay", "roster": roster(s), "start": run.ours.snapshots[0]["time"],
            "stepMinutes": cfg.timeline.step_minutes,
            "sites": [{"id": x.id, "name": x.commune, "lon": x.lon, "lat": x.lat, "teams": counts.get(x.id, 0)}
                      for x in s.sites],
            "strategies": [{"id": "ours", "label": "Copilote",
                            "description": "Moteur optimisé : clients rétablis par heure de travail + recherche locale"},
                           {"id": "reference", "label": "Référence",
                            "description": "Premier signalé, équipe qui peut finir le plus tôt"}]}


@router.get("/{crisis}/timelines")
def timelines(crisis: str, team_share: float = 1.0):
    return get_run(crisis, team_share).timelines()


@router.post("/{crisis}/decisions")
def decide(crisis: str, body: DecisionBody, team_share: float = 1.0):
    if body.kind not in ("accepted", "overridden"):
        raise HTTPException(422, "kind must be accepted or overridden")
    run = get_run(crisis, team_share)
    if not 0 <= body.step < len(run.ours.snapshots):
        raise HTTPException(422, "step hors de la chronologie")
    with _lock:
        return run.decide(body.model_dump())


class PlanBody(BaseModel):
    step: int
    overrides: dict[str, str] = {}                               # incidentId -> teamId chosen by the manager


@router.post("/{crisis}/plan/accept")
def accept_plan(crisis: str, body: PlanBody, team_share: float = 1.0, replay: bool = True):
    """The manager validates the engine's whole plan for this step (all team -> incident assignments) in one action."""
    run = get_run(crisis, team_share)
    if not 0 <= body.step < len(run.ours.snapshots):
        raise HTTPException(422, "step hors de la chronologie")
    if not run.ours.snapshots[body.step]["recommendations"]:
        raise HTTPException(409, "aucune recommandation à ce pas de temps")
    with _lock:
        return run.decide_plan(body.step, body.overrides, replay)


@router.get("/{crisis}/plan/explanation")
def plan_explanation(crisis: str, step: int, llm: bool = True, team_share: float = 1.0):
    """'Pourquoi ce plan ?': {resume, points (≤ 4), source}. llm=false returns the instant template version."""
    from dispatch.copilot.plan_explain import explain_plan, plan_facts
    run = get_run(crisis, team_share)
    if not 0 <= step < len(run.ours.snapshots):
        raise HTTPException(422, "step hors de la chronologie")
    key = (step, "__plan__", llm)
    if key not in run.explanations:
        tl = run.timelines()
        facts = plan_facts(tl["ours"], tl["reference"], step, run.ours.start.isoformat())
        run.explanations[key] = explain_plan(facts, cfg, use_llm=llm)
    return run.explanations[key]


@router.delete("/{crisis}/decisions")
def reset(crisis: str, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    with _lock:
        return run.reset()


@router.get("/{crisis}/what-if")
def what_if(crisis: str, team_share: float = 0.5):
    ours = TimelineRunner(cfg, crisis, team_share, budget_ms=50, explain=False).run()
    ref = TimelineRunner(cfg, crisis, team_share, reference=True, explain=False).run()
    return {"score": round(ours[-1]["kpis"]["score"]), "baseline": round(ref[-1]["kpis"]["score"])}


# ---------------------------------------------------------------- phase 2: explanations and copilot
def _limits() -> str:
    return ("Limites : temps de trajet modélisés (calés sur 3 718 trajets routiers réels, ±8 min en moyenne), durées de "
            "dépannage issues de la gamme, pas de topologie réseau (un dépannage ne rétablit que son poste).")


def _explanation(run: CrisisRun, step: int, incident: str) -> dict:
    key = (step, incident)
    if key not in run.explanations:
        f = run.ours.facts.get(key)
        if f is None:
            raise HTTPException(404, "pas de recommandation pour cet incident à ce pas de temps")
        card = explain_card(f, cfg, use_llm=True)
        sentences = [x for x in re.split(r"(?<=[.!?])\s+", card["details"].strip()) if x]
        run.explanations[key] = {"headline": card["headline"], "paragraphs": sentences, "limits": _limits(),
                                 "source": card["source"]}
    return run.explanations[key]


@router.get("/{crisis}/explanation")
def explanation(crisis: str, step: int, incident: str, team_share: float = 1.0):
    """'Pourquoi ?': {headline, paragraphs (2 business sentences, LLM if compliant), limits, source}."""
    return _explanation(get_run(crisis, team_share), step, incident)


class AskBody(BaseModel):
    question: str
    step: int
    recId: str | None = None


_what_if_cache: dict[tuple[str, float], dict] = {}


def _what_if(crisis: str, share: float) -> dict:
    key = (crisis, round(share, 3))
    if key not in _what_if_cache:
        ours = TimelineRunner(cfg, crisis, share, budget_ms=50, explain=False).run()
        ref = TimelineRunner(cfg, crisis, share, reference=True, explain=False).run()
        _what_if_cache[key] = {"score": round(ours[-1]["kpis"]["score"]), "baseline": round(ref[-1]["kpis"]["score"])}
    return _what_if_cache[key]


@router.post("/{crisis}/copilot")
def copilot(crisis: str, body: AskBody, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    k = max(0, min(body.step, len(run.ours.snapshots) - 1))
    return A.answer(body.question, run.ours.snapshots[k], cfg,
                    plan_explanation=lambda: plan_explanation(crisis, k, True, team_share),
                    rec_explanation=lambda rec: _explanation(run, k, rec["incidentId"]),
                    reinforcement=lambda: _reinforcement(run, k),
                    what_if=lambda share: _what_if(crisis, share),
                    final_score=run.ours.snapshots[-1]["kpis"]["score"], rec_id=body.recId)


# ---------------------------------------------------------------- phase 3: reinforcement
def _reinforcement(run: CrisisRun, k: int) -> dict:
    s = session_at(run.ours, k, run.rules)                      # basis = config (incidents), like the header
    return s.service(with_reinforcement=True, max_extra=30)


@router.get("/{crisis}/reinforcement")
def reinforcement(crisis: str, step: int, team_share: float = 1.0):
    """Projected share of customers restored by H+48 and, if below 90 %, the extra teams needed per site."""
    run = get_run(crisis, team_share)
    return _reinforcement(run, max(0, min(step, len(run.ours.snapshots) - 1)))


# ---------------------------------------------------------------- phase 3: refusal -> rule, active rules
class RefusalBody(BaseModel):
    step: int
    incidentId: str
    teamId: str
    reasonCode: str | None = None
    reasonText: str | None = None


@router.post("/{crisis}/refusals")
def refuse(crisis: str, body: RefusalBody, team_share: float = 1.0):
    """The manager refuses a recommendation with a reason -> {question} or a priced rule proposal to confirm."""
    run = get_run(crisis, team_share)
    s = session_at(run.ours, body.step, run.rules)
    if body.incidentId not in s.pending:
        raise HTTPException(409, "incident déjà pris en charge")
    out = s.reject(body.teamId, body.incidentId, body.reasonCode, body.reasonText)
    if "proposal_id" not in out:
        return out                                               # {question} or {error}
    p = s.proposals[out["proposal_id"]]
    pid = next(run._pid)
    run.proposals[pid] = {"step": body.step, "modifiers": p.modifiers, "team": body.teamId, "incident": body.incidentId,
                          "reasonCode": body.reasonCode, "reasonText": body.reasonText, "cost": p.cost_delta}
    # The restatement is rebuilt from the validated rules (names and clock times), not the LLM's wording:
    # what the manager confirms is exactly what the engine will apply.
    rules = [describe_rule(m, _names(run)) for m in p.modifiers]
    return {"proposalId": pid, "restatement": "Compris : " + " ; ".join(rules) + ".",
            "costDelta": out["cost_delta"], "rules": rules}


def _names(run: "CrisisRun") -> dict:
    return rule_names(run.ours.base, run.ours.site_names)


@router.post("/{crisis}/refusals/{pid}/confirm")
def confirm_refusal(crisis: str, pid: int, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    p = run.proposals.pop(pid, None)
    if p is None:
        raise HTTPException(404, "proposition inconnue")
    with _lock:
        run.rules.setdefault(p["step"], []).extend(p["modifiers"])
        if log is not None:
            s = run.ours.base
            inc = next(i for i in s.incidents if i.id == p["incident"])
            team = next(t for t in s.teams if t.id == p["team"])
            log.append({"crisis": run.crisis, "sim_time_h": p["step"] * run.ours.step_h, "team": team.id,
                        "site": team.home_site, "incident": inc.id, "commune": inc.commune,
                        "departement": inc.departement, "customers": inc.customers, "sensitive": bool(inc.sensitive),
                        "decision": "rejected", "reason_code": p["reasonCode"], "reason_text": p["reasonText"],
                        "modifiers": [to_dict(m) for m in p["modifiers"]], "cost_delta": p["cost"],
                        "registry_version": getattr(cfg, "_registry_version", None), "facts": None})
        return run.replay(p["step"])


class RulesBody(BaseModel):
    step: int
    modifiers: list[dict]


@router.post("/{crisis}/rules")
def add_rules(crisis: str, body: RulesBody, team_share: float = 1.0):
    """Apply rules directly (e.g. 'Appliquer la même règle' from a past-refusal hint)."""
    run = get_run(crisis, team_share)
    s = session_at(run.ours, body.step, run.rules)
    try:
        mods = [validate(dict(m), s) for m in body.modifiers]
    except InvalidModifier as e:
        raise HTTPException(422, str(e))
    with _lock:
        run.rules.setdefault(body.step, []).extend(mods)
        return run.replay(body.step)


@router.get("/{crisis}/rules")
def list_rules(crisis: str, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    flat = [(k, m) for k in sorted(run.rules) for m in run.rules[k]]
    names = _names(run)
    crisis_rules = [{"index": i, "step": k, "label": describe_rule(m, names), "rule": to_dict(m), "reason": m.reason}
                    for i, (k, m) in enumerate(flat)]
    permanent = [{"label": describe_rule(m, names), "rule": to_dict(m), "reason": m.reason}
                 for m in run.ours.base.permanent]
    return {"crisis": crisis_rules, "permanent": permanent}


@router.delete("/{crisis}/rules/{index}")
def delete_rule(crisis: str, index: int, team_share: float = 1.0):
    run = get_run(crisis, team_share)
    flat = [(k, m) for k in sorted(run.rules) for m in run.rules[k]]
    if not 0 <= index < len(flat):
        raise HTTPException(404, "règle inconnue")
    k, m = flat[index]
    with _lock:
        run.rules[k].remove(m)
        return run.replay(k)


def invalidate_all() -> None:
    """After a change of the permanent registry: crises are recomputed on next access."""
    with _lock:
        _runs.clear()
        _what_if_cache.clear()


# ---------------------------------------------------------------- map: real road routes
routes_router = APIRouter(tags=["map"])


class RoutesBody(BaseModel):
    pairs: list[list[list[float]]]                               # [[[lon, lat], [lon, lat]], ...]


@routes_router.post("/routes")
def routes(body: RoutesBody):
    """Road geometry (OSRM, cached) for each [from, to] pair; straight line if OSRM is unreachable."""
    return road.routes(body.pairs, cfg.travel.osrm_url)
