"""Timeline mode for the EnedisPO front-end: the whole crisis replayed in steps of `step_minutes` of crisis time
(not wall-clock time), one Snapshot per step, for our engine and for the reference strategy.

At each step: arrivals and finished repairs are processed, the engine re-plans, the recommendations of the step are
listed, the manager's decisions for this step are applied (accept / override = another team), every other
recommendation is executed automatically, and the snapshot is recorded. A checkpoint of the session is kept at
every step, so a new decision only replays the crisis from its step.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta

from dispatch.adapters import contract as C
from dispatch.engine.baselines import ReferencePolicy
from dispatch.engine.modifiers import Force
from dispatch.engine.types import ExplanationFacts
from dispatch.session import LiveSession

MAX_STEPS = 600


class TimelineRunner:
    def __init__(self, cfg, crisis_id: str, team_share: float = 1.0, reference: bool = False,
                 budget_ms: int = 100, step_minutes: int = 30, explain: bool = True, projection_budget_ms: int = 25,
                 log=None):
        self.cfg, self.crisis_id, self.team_share = cfg, crisis_id, team_share
        self.step_h = step_minutes / 60
        self.step_minutes = step_minutes
        self.explain = explain
        self.budget_ms, self.projection_budget_ms = budget_ms, projection_budget_ms
        self.base = LiveSession.start(cfg, crisis_id, budget_ms=budget_ms, teams_fraction=team_share,
                                      policy=ReferencePolicy() if reference else None, log=log)
        # snapshot 0 = the first incident (H0); snapshot k = H0 + k steps
        self.offset_h = 0.0
        self.start: datetime = self.base.t0
        self.site_names = {s.id: s.commune for s in self.base.sites}
        self.checkpoints: list[LiveSession] = []
        self.snapshots: list[dict] = []
        self.facts: dict[tuple[int, str], ExplanationFacts] = {}      # (step, incident) -> facts, for explanations

    def clock(self, k: int) -> float:
        return self.offset_h + k * self.step_h

    def run(self, decisions: dict[tuple[int, str], dict] | None = None, from_step: int = 0,
            rules: dict[int, list] | None = None) -> list[dict]:
        """Replay from `from_step` (0 = from scratch) with the manager's decisions {(step, incident): decision} and
        operator rules {step: [modifiers]} (applied from their step on)."""
        decisions, rules = decisions or {}, rules or {}
        first = from_step
        if from_step and from_step < len(self.checkpoints):
            s = self._copy(self.checkpoints[from_step])
            self.checkpoints = self.checkpoints[:from_step]
            self.snapshots = self.snapshots[:from_step]
        else:
            s, from_step = self._copy(self.base), 0
            self.checkpoints, self.snapshots = [], []
            first = None                                          # full computation: full budget everywhere
        self.facts = {key: f for key, f in self.facts.items() if key[0] < from_step}
        for k in range(from_step, MAX_STEPS):
            self.checkpoints.append(self._copy(s))
            t = self.clock(k)
            s._move_clock(max(t, s.now))
            s._facts_cache.clear()
            s.rules.extend(rules.get(k, []))
            # replaying after a decision: full search at the decision's step, lighter search for the projection
            s.replan(force=True, budget_ms=self.budget_ms if first is None or k == first else self.projection_budget_ms)
            recs = s.recommendations(with_text=self.explain) if s.plan else []
            for r in recs:
                if r.get("facts"):
                    self.facts[(k, r["incident"])] = ExplanationFacts(**r["facts"])
            step_dec = {inc: d for (st, inc), d in decisions.items() if st == k}
            self.snapshots.append(C.snapshot(s, t, C.iso(self.start, k * self.step_h),
                                             [C.recommendation(s, r, k) for r in recs],
                                             [_echo(d) for d in step_dec.values()], self.site_names))
            self._execute(s, recs, step_dec)
            if not s.pending and not s.in_progress and s._arrival_i == len(s.incidents):
                break
        return self.snapshots

    @staticmethod
    def _copy(s: LiveSession) -> LiveSession:
        """Checkpoint copy that shares everything immutable (incidents, sites, config, start time)."""
        memo = {id(s.cfg): s.cfg, id(s.incidents): s.incidents, id(s.sites): s.sites, id(s.t0): s.t0,
                id(s.permanent): s.permanent, id(s.log): s.log}
        memo.update({id(i): i for i in s.incidents})
        memo.update({id(i): i for i in s.pending.values()})
        return copy.deepcopy(s, memo)

    def _execute(self, s: LiveSession, recs: list[dict], step_dec: dict[str, dict]) -> None:
        used_teams, used_inc = set(), set()
        idle = {t.id for t in s.idle_on_duty()}
        for inc, d in step_dec.items():                          # manager's choices first
            if inc not in s.pending or d["teamId"] in used_teams:
                continue
            if d["teamId"] in idle:
                s._commit(d["teamId"], inc)
            else:                                                # busy / off duty: it takes the job next
                s.rules.append(Force(team=d["teamId"], incident=inc, reason=d.get("reason") or "", scope="incident"))
            used_teams.add(d["teamId"]); used_inc.add(inc)
        for r in recs:                                           # untouched recommendations run on their own
            if r["incident"] in used_inc or r["team"] in used_teams or r["incident"] not in s.pending:
                continue
            if s.team(r["team"]).current_job:
                continue
            s._commit(r["team"], r["incident"])
            used_teams.add(r["team"]); used_inc.add(r["incident"])


def _echo(d: dict) -> dict:
    out = {"incidentId": d["incidentId"], "teamId": d["teamId"], "kind": d["kind"],
           "recommendedTeamId": d["recommendedTeamId"]}
    if d.get("reason"):
        out["reason"] = d["reason"]
    return out


def align(ours: list[dict], reference: list[dict], step_minutes: int) -> None:
    """Same number of snapshots for both strategies (pad the shorter with its final state), and copy the
    reference score into ours as kpis.scoreBaseline."""
    def pad(snaps, n):
        while len(snaps) < n:
            last = copy.deepcopy(snaps[-1])
            last["time"] = (datetime.fromisoformat(last["time"]) + timedelta(minutes=step_minutes)).isoformat()
            last["recommendations"], last["decisions"] = [], []
            snaps.append(last)
    n = max(len(ours), len(reference))
    pad(ours, n); pad(reference, n)
    for a, b in zip(ours, reference):
        a["kpis"]["scoreBaseline"] = b["kpis"]["score"]
        b["kpis"]["scoreBaseline"] = b["kpis"]["score"]


def session_at(runner: TimelineRunner, k: int, rules: dict[int, list] | None = None) -> LiveSession:
    """A live session positioned at step k of the timeline (for refusals, reinforcement, explanations)."""
    s = runner._copy(runner.checkpoints[k])
    s._move_clock(max(runner.clock(k), s.now))
    s.rules.extend((rules or {}).get(k, []))
    s.replan(force=True, budget_ms=runner.budget_ms)
    return s
