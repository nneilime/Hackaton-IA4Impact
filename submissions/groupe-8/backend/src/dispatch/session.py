"""LiveSession: one crisis being managed step by step (what the front-end and the API drive).

The session holds the state of the world (clock, known incidents, teams, jobs in progress, operator rules) and
the published plan. The manager validates each recommendation:
  accept  -> the team is dispatched
  reject  -> the reason becomes a proposed rule (LLM or deterministic fallback), the engine prices it,
             the manager confirms, the rule is applied, the plan is recomputed, and the refusal is logged
             in the knowledge base for the periodic expert review.
Only incidents already reported are visible to the engine (no anticipation).
"""
from __future__ import annotations

import heapq
import itertools
import math
import random
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from dispatch.copilot.explain import explain_card
from dispatch.copilot.translate import fallback, reason_to_modifiers
from dispatch.copilot.validator import InvalidModifier, validate
from dispatch.data.loaders import load_incidents, load_sites, load_teams
from dispatch.data.travel import haversine_km
from dispatch.engine.construct import list_scheduling
from dispatch.engine.context import build_context
from dispatch.engine.counterfactual import counterfactual
from dispatch.engine.evaluate import routes_from_plan, to_plan
from dispatch.engine.explain import explain
from dispatch.engine.modifiers import Forbid, Force, Modifier, to_dict
from dispatch.engine.planner import plan as make_plan
from dispatch.engine.planner import should_publish
from dispatch.engine.service import target_met
from dispatch.engine.shifts import is_on_duty, window
from dispatch.engine.types import Incident, Plan, State, Team, TeamStatus
from dispatch.learning.memory import DecisionLog
from dispatch.learning.registry import load_registry

EPS = 1e-9


@dataclass
class Proposal:
    id: int
    team: str
    incident: str
    reason_code: str | None
    reason_text: str | None
    modifiers: list[Modifier]
    restatement: str
    cost_delta: float


@dataclass
class LiveSession:
    cfg: object
    crisis_id: str
    incidents: list[Incident]
    teams: list[Team]
    sites: list
    t0: datetime | None = None
    budget_ms: int | None = None
    log: DecisionLog | None = None
    now: float = 0.0
    pending: dict[str, Incident] = field(default_factory=dict)
    in_progress: dict[str, tuple[str, float, float, float]] = field(default_factory=dict)  # iid -> team, go, arrive, C
    restored: dict[str, float] = field(default_factory=dict)
    rules: list[Modifier] = field(default_factory=list)          # crisis-scoped rules confirmed by the manager
    permanent: list[Modifier] = field(default_factory=list)      # from the constraint registry (expert-validated)
    plan: Plan | None = None
    plan_version: int = 0
    proposals: dict[int, Proposal] = field(default_factory=dict)
    trip_origin: dict[str, tuple[float, float]] = field(default_factory=dict)   # iid -> where the team left from
    _facts_cache: dict = field(default_factory=dict)
    _llm_cache: dict = field(default_factory=dict)
    _arrival_i: int = 0
    _busy: list = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _rng: random.Random = field(default_factory=lambda: random.Random(0))
    policy: object | None = None                                  # None = optimised engine (RSLS)
    simulated: bool = False                                       # entries logged as synthetic (demo)
    # Live mode: the world is only known through field events (incident reported, team on site, repair done) sent
    # by an external system; nothing is simulated here. Replay mode (False): arrivals and completions are simulated.
    external_field: bool = False
    on_site: set = field(default_factory=set)                     # live: incidents whose team reported on site
    dispatches: list = field(default_factory=list)                # live: trips started, read by the field system

    # ------------------------------------------------------------------ creation
    @classmethod
    def start(cls, cfg, crisis_id: str, budget_ms: int | None = None, log: DecisionLog | None = None,
              teams_fraction: float = 1.0, policy=None) -> "LiveSession":
        incidents, t0 = load_incidents(cfg, crisis_id)
        sites = load_sites(cfg)
        teams = load_teams(cfg, sites)
        if teams_fraction < 1:
            step = round(1 / teams_fraction)
            teams = [t for k, t in enumerate(teams) if k % step == 0]
        s = cls(cfg=cfg, crisis_id=crisis_id, incidents=sorted(incidents, key=lambda i: i.reported_at),
                teams=[replace(t) for t in teams], sites=sites, t0=t0, budget_ms=budget_ms, log=log,
                permanent=load_registry(cfg), policy=policy)
        s.advance(0.0)
        return s

    @classmethod
    def empty(cls, cfg, t0: datetime, budget_ms: int | None = None, log: DecisionLog | None = None) -> "LiveSession":
        """Live crisis starting at t0 (H0) with every team at its site and no incident yet."""
        sites = load_sites(cfg)
        return cls(cfg=cfg, crisis_id="LIVE", incidents=[], teams=load_teams(cfg, sites), sites=sites, t0=t0,
                   budget_ms=budget_ms, log=log, permanent=load_registry(cfg), external_field=True)

    # ------------------------------------------------------------------ field events (live mode)
    def report(self, inc: Incident) -> None:
        """A new incident is reported by the field."""
        if any(i.id == inc.id for i in self.incidents):
            return
        self.incidents.append(inc)
        self.pending[inc.id] = inc
        self._arrival_i = len(self.incidents)

    def arrived(self, team_id: str, incident_id: str, at: float) -> None:
        """The team reports it is on site: the repair starts now, its end is re-estimated from here."""
        if incident_id not in self.in_progress:
            return
        tid, go, _, _ = self.in_progress[incident_id]
        C = at + next(i for i in self.incidents if i.id == incident_id).est_duration
        self.in_progress[incident_id] = (tid, go, at, C)
        self.on_site.add(incident_id)
        team = self.team(tid)
        team.status, team.free_at = TeamStatus.REPAIRING, C

    def repaired(self, team_id: str, incident_id: str, at: float) -> None:
        """The team reports the repair is done: customers restored, the team is free where it stands."""
        if incident_id not in self.in_progress:
            return
        tid = self.in_progress.pop(incident_id)[0]
        self.on_site.discard(incident_id)
        self.restored[incident_id] = at
        team = self.team(tid)
        team.status, team.current_job, team.free_at = TeamStatus.IDLE, None, at

    def hold_overruns(self) -> None:
        """Live: a team whose repair takes longer than estimated is still busy (never planned as free in the past)."""
        for iid, (tid, go, arrive, C) in self.in_progress.items():
            if C < self.now:
                team = self.team(tid)
                team.free_at = max(team.free_at, self.now + 1 / 60)

    # ------------------------------------------------------------------ clock
    def clock(self, h: float) -> str:
        return (self.t0 + timedelta(hours=h)).strftime("%d/%m %H:%M") if self.t0 else f"H0+{h:.2f}h"

    def next_event_time(self) -> float | None:
        cands = []
        if self._arrival_i < len(self.incidents):
            cands.append(self.incidents[self._arrival_i].reported_at)
        if self._busy:
            cands.append(self._busy[0][0])
        W, R = self.cfg.roster.work_h, self.cfg.roster.rest_h
        for t in self.teams:                                      # next shift start of an idle off-duty team
            if t.status == TeamStatus.IDLE:
                s, _ = window(t.shift_start, self.now + EPS, W, R)
                if s > self.now + EPS:
                    cands.append(s)
        if self.plan:                                             # planned departures later on
            cands += [go for go, _, _ in self.plan.schedule.values() if go > self.now + EPS]
        return min(cands) if cands else None

    def advance(self, to: float | None = None, auto_accept: bool = False, max_steps: int = 100_000) -> int:
        """Move the clock to `to` (or to the next event). With auto_accept, every recommendation is accepted on the
        way (replay mode). Returns the number of jobs dispatched."""
        dispatched = 0
        target = to if to is not None else self.next_event_time()
        if target is None:
            return 0
        for _ in range(max_steps):
            nxt = self.next_event_time()
            step_to = target if nxt is None or nxt > target else nxt
            self._move_clock(max(step_to, self.now))
            self.replan()
            if auto_accept:
                for r in self.recommendations(with_text=False):
                    self.accept(r["team"], r["incident"], log=False)
                    dispatched += 1
            if self.now >= target - EPS:
                break
        return dispatched

    def _move_clock(self, t: float) -> None:
        self.now = t
        if self.external_field:                                   # arrivals and completions come as events
            return
        while self._arrival_i < len(self.incidents) and self.incidents[self._arrival_i].reported_at <= t + EPS:
            inc = self.incidents[self._arrival_i]
            self.pending[inc.id] = inc
            self._arrival_i += 1
        while self._busy and self._busy[0][0] <= t + EPS:
            C, tid, iid = heapq.heappop(self._busy)
            team = self.team(tid)
            team.status, team.current_job = TeamStatus.IDLE, None
            self.restored[iid] = C
            self.in_progress.pop(iid, None)

    # ------------------------------------------------------------------ planning
    def team(self, tid: str) -> Team:
        return next(t for t in self.teams if t.id == tid)

    def state(self, extra: list[Modifier] | None = None, previous: Plan | None = None) -> State:
        return State(now=self.now, teams=self.teams, pending=list(self.pending.values()),
                     modifiers=self.permanent + self.rules + list(extra or []),
                     previous_plan=self.plan if previous is None else previous)

    def replan(self, force: bool = False, budget_ms: int | None = None) -> Plan | None:
        """Re-optimise. The new plan replaces the published one only if it is clearly better than the published
        routes re-timed at the current clock (publication threshold), or if the situation changed."""
        if not self.pending:
            self.plan = None
            return None
        state = self.state()
        new = (self.policy.plan(state, self.cfg) if self.policy is not None
               else make_plan(state, self.cfg, self.budget_ms if budget_ms is None else budget_ms))
        if force or self._plan_stale():
            self.plan, self.plan_version = new, self.plan_version + 1
            return self.plan
        ctx = build_context(state, self.cfg)
        kept = to_plan(ctx, routes_from_plan(ctx, self.plan))
        if should_publish(new, kept, self.cfg):
            self.plan, self.plan_version = new, self.plan_version + 1
        else:
            self.plan = kept                                      # same routes, times refreshed to now
        return self.plan

    def _plan_stale(self) -> bool:
        """The published plan no longer matches the world (incident started/new incident/team change)."""
        if self.plan is None:
            return True
        planned = {iid for r in self.plan.routes.values() for iid in r}
        return planned != set(self.pending)

    def idle_on_duty(self) -> list[Team]:
        W, R = self.cfg.roster.work_h, self.cfg.roster.rest_h
        return [t for t in self.teams if t.status == TeamStatus.IDLE and t.free_at <= self.now + EPS
                and is_on_duty(t.shift_start, self.now, W, R)]

    def recommendations(self, with_text: bool = True) -> list[dict]:
        """Next job of each idle, on-duty team that should leave now, with facts, text and past-refusal hints."""
        if not self.plan:
            return []
        out, facts_by_team = [], {}
        idle = {t.id for t in self.idle_on_duty()}
        due = [tid for tid in idle if self.plan.routes.get(tid)
               and self.plan.schedule[self.plan.routes[tid][0]][0] <= self.now + EPS]
        if not due:
            return []
        if with_text:
            for f in explain(self.plan, self.state(), self.cfg, teams=due):
                facts_by_team[f.team] = f
        for tid in sorted(due):
            iid = self.plan.routes[tid][0]
            go, arrive, C = self.plan.schedule[iid]
            rec = {"team": tid, "incident": iid, "depart_h": go, "arrive_h": arrive, "restored_h": C,
                   "restored_clock": self.clock(C)}
            if with_text and tid in facts_by_team:
                f = facts_by_team[tid]
                team = self.team(tid)
                f.factors.update({"site_commune": self._site_commune(team), "commune": self.pending[iid].commune,
                                  "restored_clock": self.clock(C)[-5:]})
                card = explain_card(f, self.cfg)
                rec.update({"headline": card["headline"], "details": card["details"], "text_source": card["source"],
                            "text": card["details"], "facts": f.__dict__, "options": self._options(f, C),
                            "past_refusals": self._past_refusal_hint(tid, iid)})
                self._facts_cache[(tid, iid, self.plan_version)] = f
            out.append(rec)
        return sorted(out, key=lambda r: (r.get("facts") or {}).get("rank_in_plan", 10**6))

    def _site_commune(self, team: Team) -> str:
        site = next((x for x in self.sites if x.id == team.home_site), None)
        return site.commune if site else team.home_site

    def _options(self, f, C: float) -> list[dict]:
        """The 3 best ways to handle this incident: recommended team (rank 1) + 2 best alternative teams.
        Each with its path (team position -> incident, [lon, lat]), restoration time and extra cost."""
        inc = self.pending[f.incident]
        out = []
        for rank, (tid, restored, travel, extra) in enumerate(
                [(f.team, C, f.factors["travel_min"], 0.0)]
                + [(a["team"], a["restored_h"], a["travel_min"], a["delta"]) for a in (f.alternatives or []) if a["feasible"]][:2],
                start=1):
            t = self.team(tid)
            out.append({"rank": rank, "team": tid, "team_site": self._site_commune(t), "travel_min": travel,
                        "restored_h": restored, "restored_clock": self.clock(restored)[-5:],
                        "extra_customer_hours": round(extra), "recommended": rank == 1,
                        "path": [[t.lon, t.lat], [inc.lon, inc.lat]]})
        return out

    def explanation(self, team_id: str, incident_id: str) -> dict:
        """Expanded card text: LLM-written details if available and compliant, else the template (cached)."""
        key = (team_id, incident_id, self.plan_version)
        if key in self._llm_cache:
            return self._llm_cache[key]
        f = self._facts_cache.get(key)
        if f is None:
            self.recommendations()
            f = self._facts_cache.get(key)
        if f is None:
            return {"error": "no current recommendation for this team and incident"}
        card = explain_card(f, self.cfg, use_llm=True)
        self._llm_cache[key] = card
        return card

    # ------------------------------------------------------------------ manager decisions
    def accept(self, team_id: str, incident_id: str, log: bool = True) -> None:
        """Dispatch team -> incident. If it differs from the recommendation, it is a manager modification."""
        recommended = self._commit(team_id, incident_id)
        if log and self.log:
            self.log.append(self._log_entry(team_id, incident_id, "accepted" if recommended else "modified"),
                            simulated=self.simulated)
        self.replan(force=True, budget_ms=self._interactive_budget())

    def _commit(self, team_id: str, incident_id: str) -> bool:
        """Start the trip now (no re-plan). Returns True if it was the engine's recommendation."""
        team = self.team(team_id)
        inc = self.pending[incident_id]
        recommended = bool(self.plan) and (self.plan.routes.get(team_id) or [None])[0] == incident_id
        timing_plan = self.plan if recommended else make_plan(
            self.state(extra=[Force(team=team_id, incident=incident_id)]), self.cfg,
            min(self._interactive_budget(), 100))
        go, arrive, _ = timing_plan.schedule[incident_id]
        go = max(go, self.now)
        if self.external_field:                                   # live: the field will report the real times
            arrive = go + (arrive - timing_plan.schedule[incident_id][0])
            C = arrive + inc.est_duration
        else:
            s = self.cfg.simulation.duration_noise_sigma
            actual = inc.est_duration if not s else inc.est_duration * math.exp(self._rng.gauss(-s * s / 2, s))
            C = arrive + actual
        del self.pending[incident_id]
        self.in_progress[incident_id] = (team_id, go, arrive, C)
        self.trip_origin[incident_id] = (team.lat, team.lon)
        team.status, team.current_job, team.free_at, team.lat, team.lon = TeamStatus.TRAVELLING, incident_id, C, inc.lat, inc.lon
        if self.external_field:
            self.dispatches.append({"seq": len(self.dispatches) + 1, "team": team_id, "incident": incident_id,
                                    "depart_h": go, "travel_h": arrive - go, "repair_h": inc.est_duration})
        else:
            heapq.heappush(self._busy, (C, team_id, incident_id))
        return recommended

    def position(self, team: Team, t: float | None = None) -> tuple[float, float]:
        """Where the team is at time t (interpolated along its trip while travelling)."""
        t = self.now if t is None else t
        if team.current_job and team.current_job in self.in_progress:
            _, go, arrive, _ = self.in_progress[team.current_job]
            o = self.trip_origin.get(team.current_job)
            if o and t < arrive and arrive > go:
                k = max(0.0, min(1.0, (t - go) / (arrive - go)))
                return o[0] + (team.lat - o[0]) * k, o[1] + (team.lon - o[1]) * k
        return team.lat, team.lon

    def reject(self, team_id: str, incident_id: str, reason_code: str | None = None,
               reason_text: str | None = None, translated: dict | None = None) -> dict:
        """Turn the refusal into a proposed rule, price it, and wait for the manager's confirmation.
        `translated`: the reason already turned into modifiers (reason_to_modifiers) by a caller that ran the LLM
        outside a lock (live mode: the dashboard must not freeze while the LLM answers)."""
        ctx_info = self._context_info(team_id, incident_id)
        out = translated or reason_to_modifiers(reason_code, reason_text, ctx_info, self.cfg)
        if out.get("question"):
            return {"question": out["question"]}
        for raw in out.get("modifiers", []):
            if not raw.get("reason"):
                raw["reason"] = reason_text or reason_code or ""       # keep the manager's own words
        try:
            mods = [validate(raw, self) for raw in out["modifiers"]]
        except InvalidModifier as e:
            if out.get("source") != "llm":
                return {"error": str(e)}
            out = fallback(reason_code, reason_text, ctx_info)          # LLM rule rejected: use the rule parser
            if out.get("question"):
                return {"question": out["question"]}
            try:
                mods = [validate(raw, self) for raw in out["modifiers"]]
            except InvalidModifier as e2:
                return {"error": str(e2)}
        if not mods:                                              # at minimum: not this team on this incident
            mods = [Forbid(team_or_site=team_id, incident_or_zone=incident_id, reason=reason_text or "", scope="incident")]
        _, delta = counterfactual(self.state(), mods, self.cfg, base_plan=self.plan, budget_ms=self.budget_ms)
        p = Proposal(id=next(self._ids), team=team_id, incident=incident_id, reason_code=reason_code,
                     reason_text=reason_text, modifiers=mods, restatement=out["restatement"], cost_delta=delta)
        self.proposals[p.id] = p
        return {"proposal_id": p.id, "restatement": p.restatement, "cost_delta": round(delta, 1),
                "modifiers": [to_dict(m) for m in mods]}

    def confirm(self, proposal_id: int) -> None:
        p = self.proposals.pop(proposal_id)
        self.rules.extend(p.modifiers)
        if self.log:
            self.log.append(self._log_entry(p.team, p.incident, "rejected", reason_code=p.reason_code,
                                            reason_text=p.reason_text, modifiers=p.modifiers, cost=p.cost_delta),
                            simulated=self.simulated)
        self.replan(force=True, budget_ms=self._interactive_budget())

    def _interactive_budget(self) -> int:
        b = self.budget_ms if self.budget_ms is not None else self.cfg.solver.budget_ms
        return min(b, self.cfg.solver.interactive_budget_ms)

    def cancel(self, proposal_id: int) -> None:
        self.proposals.pop(proposal_id, None)

    def remove_rule(self, index: int) -> None:
        del self.rules[index]
        self.replan(force=True)

    def what_if(self, modifiers: list[Modifier]) -> dict:
        alt, delta = counterfactual(self.state(), modifiers, self.cfg, base_plan=self.plan, budget_ms=self.budget_ms)
        return {"cost_delta": round(delta, 1), "routes": alt.routes}

    # ------------------------------------------------------------------ service target + reinforcement
    def projected_restoration(self, plan: Plan | None = None) -> dict[str, float]:
        plan = self.plan if plan is None else plan
        proj = dict(self.restored)
        proj.update({iid: v[3] for iid, v in self.in_progress.items()})
        if plan:
            proj.update({iid: v[2] for iid, v in plan.schedule.items()})
        return proj

    def service(self, with_reinforcement: bool = True, max_extra: int = 30) -> dict:
        """Projected share fixed by the deadline over incidents known so far; reinforcement if below target."""
        st = self.cfg.service_target
        known = [i for i in self.incidents if i.reported_at <= self.now + EPS]
        share = self._share(self.projected_restoration(), known)
        out = {"projected_share": share, "target": st.share, "deadline_h": st.deadline_h, "basis": st.basis,
               "target_met": target_met(share, self.cfg), "known_incidents": len(known)}
        if with_reinforcement and not out["target_met"] and self.pending:
            out["reinforcement"] = self._reinforcement(known, max_extra)
        return out

    def _share(self, proj: dict[str, float], known: list[Incident]) -> float:
        from dispatch.engine.service import service_share
        st = self.cfg.service_target
        return service_share(proj, known, st.deadline_h, st.basis)

    def _reinforcement(self, known: list[Incident], max_extra: int) -> dict:
        """Greedy: add teams (available now) at the site that raises the projected share most (Smith plan)."""
        extra, added, added_ids = [], [], []
        share = None
        for n in range(max_extra):
            best = (-1.0, None)
            for s in self.sites:
                cand = Team(id=f"RENFORT_{n + 1}", home_site=s.id, lat=s.lat, lon=s.lon, free_at=self.now,
                            shift_start=self.now)
                st = replace(self.state(), teams=self.teams + extra + [cand], previous_plan=None)
                ctx = build_context(st, self.cfg)
                routes, left = list_scheduling(ctx, "smith")
                v = self._share(self.projected_restoration(to_plan(ctx, routes, left)), known)
                if v > best[0]:
                    best = (v, s, cand)
            share, s, cand = best
            extra.append(cand); added.append(s.commune); added_ids.append(s.id)
            if target_met(share, self.cfg):
                break
        from collections import Counter
        by_id = Counter(added_ids)
        sites = [{"id": x.id, "name": x.commune, "lon": x.lon, "lat": x.lat, "extra": by_id[x.id]}
                 for x in self.sites if x.id in by_id]
        return {"extra_teams": len(added), "by_site": dict(Counter(added)), "sites": sites, "projected_share_after": share,
                "target_met": target_met(share, self.cfg) if share is not None else False}

    # ------------------------------------------------------------------ knowledge base helpers
    def _context_info(self, team_id: str, incident_id: str) -> dict:
        team, inc = self.team(team_id), self.pending[incident_id]
        site = next((s for s in self.sites if s.id == team.home_site), None)
        return {"team": team_id, "site": team.home_site, "site_commune": site.commune if site else "",
                "incident": incident_id, "commune": inc.commune, "departement": inc.departement,
                "now_h": self.now, "t0": self.t0}

    def _log_entry(self, team_id, incident_id, decision, reason_code=None, reason_text=None, modifiers=None,
                   cost=None) -> dict:
        inc = self.pending.get(incident_id) or next(i for i in self.incidents if i.id == incident_id)
        team = self.team(team_id)
        facts = None
        if self.plan and self.plan.routes.get(team_id, [None])[0] == incident_id:
            go, arrive, C = self.plan.schedule[incident_id]
            facts = {"travel_min": round(60 * (arrive - go)), "repair_h": inc.est_duration}
        return {"crisis": self.crisis_id, "sim_time_h": self.now, "team": team_id, "site": team.home_site,
                "incident": incident_id, "commune": inc.commune, "departement": inc.departement,
                "customers": inc.customers, "sensitive": bool(inc.sensitive), "decision": decision,
                "reason_code": reason_code, "reason_text": reason_text,
                "modifiers": [to_dict(m) for m in (modifiers or [])], "cost_delta": cost,
                "registry_version": getattr(self.cfg, "_registry_version", None), "facts": facts}

    def _past_refusal_hint(self, team_id: str, incident_id: str) -> dict | None:
        if not self.log:
            return None
        info = self._context_info(team_id, incident_id)
        similar = self.log.similar(site=info["site"], commune=info["commune"], departement=info["departement"])
        if not similar:
            return None
        last = similar[0]
        return {"count": len(similar), "last_reason": last["reason_text"] or last["reason_code"],
                "suggested_modifiers": last["modifiers"],
                "question": f"Vous avez déjà refusé {len(similar)} fois d'envoyer une équipe de {info['site_commune']} "
                            f"vers {info['commune']} (dernier motif : « {last['reason_text'] or last['reason_code']} »). "
                            f"Appliquer la même règle ?"}

    # ------------------------------------------------------------------ snapshot for the front-end
    def kpis(self) -> dict:
        ch = sum(i.customers * (self.restored[i.id] - i.reported_at) for i in self.incidents if i.id in self.restored)
        return {"now_h": self.now, "now_clock": self.clock(self.now), "known": self._arrival_i,
                "total_incidents": len(self.incidents), "pending": len(self.pending),
                "in_progress": len(self.in_progress), "restored": len(self.restored),
                "customers_restored": sum(i.customers for i in self.incidents if i.id in self.restored),
                "customer_hours_so_far": ch, "finished": not self.pending and not self.in_progress
                and self._arrival_i == len(self.incidents)}

    # ------------------------------------------------------------------ map layers (GeoJSON) for the front-end
    def geojson(self) -> dict:
        """Map layers. Every feature has properties.layer in: site, team, incident, route, heat, zone.

        The objective is a SUM over incidents (customers x hours without power), so each incident has its own
        share of the score: that is what the heat layer and the incident colours show.
        """
        feats = []
        pt = lambda lat, lon: {"type": "Point", "coordinates": [lon, lat]}  # noqa: E731
        line = lambda pts: {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in pts]}  # noqa: E731
        eta = self.projected_restoration()
        known = [i for i in self.incidents if i.reported_at <= self.now + EPS]
        impact = {i.id: i.customers * (eta[i.id] - i.reported_at) for i in known if i.id in eta}
        total = sum(impact.values()) or 1.0
        for s in self.sites:
            feats.append({"type": "Feature", "geometry": pt(s.lat, s.lon),
                          "properties": {"layer": "site", "id": s.id, "commune": s.commune, "teams": s.n_teams}})
        W, R = self.cfg.roster.work_h, self.cfg.roster.rest_h
        for t in self.teams:
            feats.append({"type": "Feature", "geometry": pt(t.lat, t.lon),
                          "properties": {"layer": "team", "id": t.id, "site": t.home_site, "status": t.status.value,
                                         "on_duty": is_on_duty(t.shift_start, self.now, W, R),
                                         "current_job": t.current_job}})
        status = {iid: "restored" for iid in self.restored}
        status.update({iid: "in_progress" for iid in self.in_progress})
        for i in known:
            st = status.get(i.id, "pending")
            remaining = i.customers * max(0.0, eta.get(i.id, self.now) - self.now) if st != "restored" else 0.0
            feats.append({"type": "Feature", "geometry": pt(i.lat, i.lon), "properties": {
                "layer": "incident", "id": i.id, "status": st, "customers": i.customers, "sensitive": bool(i.sensitive),
                "commune": i.commune, "repair_h": i.est_duration, "waiting_h": round(self.now - i.reported_at, 2),
                "eta_h": eta.get(i.id), "eta_clock": self.clock(eta[i.id]) if i.id in eta else None,
                "impact_customer_hours": round(impact.get(i.id, 0.0), 1),
                "score_share": round(impact.get(i.id, 0.0) / total, 4),
                "remaining_customer_hours": round(remaining, 1)}})
            if st != "restored" and remaining > 0:
                feats.append({"type": "Feature", "geometry": pt(i.lat, i.lon),
                              "properties": {"layer": "heat", "weight": round(remaining, 1), "incident": i.id}})
        for iid, (tid, go, arrive, C) in self.in_progress.items():
            o = self.trip_origin.get(iid)
            inc = next(x for x in self.incidents if x.id == iid)
            if o:
                feats.append({"type": "Feature", "geometry": line([o, (inc.lat, inc.lon)]), "properties": {
                    "layer": "route", "team": tid, "incidents": [iid], "committed": True,
                    "phase": "travelling" if self.now < arrive else "repairing", "depart_h": go, "arrive_h": arrive}})
        if self.plan:
            by_id = {i.id: i for i in self.incidents}
            for t in self.teams:
                r = self.plan.routes.get(t.id) or []
                if not r:
                    continue
                pts = [(t.lat, t.lon)] + [(by_id[i].lat, by_id[i].lon) for i in r[:3]]
                feats.append({"type": "Feature", "geometry": line(pts), "properties": {
                    "layer": "route", "team": t.id, "incidents": r[:3], "committed": False, "phase": "planned",
                    "depart_h": [self.plan.schedule[i][0] for i in r[:3]]}})
        colours = {1: "#2A9D8F", 2: "#E9C46A", 3: "#E76F51"}
        for rec in self.recommendations():
            for o in rec.get("options", []):
                feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": o["path"]},
                              "properties": {"layer": "option", "incident": rec["incident"], "rank": o["rank"],
                                             "team": o["team"], "recommended": o["recommended"],
                                             "restored_clock": o["restored_clock"],
                                             "extra_customer_hours": o["extra_customer_hours"],
                                             "colour": colours.get(o["rank"])}})
        for m in self.rules + self.permanent:
            zone = getattr(m, "zone", None) or getattr(m, "incident_or_zone", None)
            pts = [(i.lat, i.lon) for i in self.incidents if zone and zone.lower() in (i.commune.lower(), i.departement.lower())]
            if pts:
                lat = sum(p[0] for p in pts) / len(pts); lon = sum(p[1] for p in pts) / len(pts)
                radius = max(2.0, max(float(haversine_km(lat, lon, a, b)) for a, b in pts))
                feats.append({"type": "Feature", "geometry": pt(lat, lon), "properties": {
                    "layer": "zone", "rule": to_dict(m), "radius_km": round(radius, 1)}})
        return {"type": "FeatureCollection", "features": feats, "properties": {
            "now_h": self.now, "now_clock": self.clock(self.now), "plan_version": self.plan_version,
            "score_customer_hours_projected": round(total, 1)}}
