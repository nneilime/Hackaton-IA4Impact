"""Event-driven simulator: the 'world' around the engine.

- Incidents become known only at their report time (no anticipation).
- At every event (arrival, repair done, a team's shift starting), the policy re-plans all known pending incidents;
  only the NEXT job of each idle, on-duty team is committed (the rest of the plan is a preview).
- The world holds the TRUE repair time (estimate x lognormal noise if duration_noise_sigma > 0); the engine only
  ever sees the estimate. A started repair is never interrupted, even if it overruns the shift.
"""
from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field, replace

from dispatch.engine.service import service_share
from dispatch.engine.shifts import window
from dispatch.engine.types import Incident, Plan, State, Team, TeamStatus

EPS = 1e-9


@dataclass
class Result:
    restored_at: dict[str, float] = field(default_factory=dict)     # incident id -> actual C_i
    started_at: dict[str, float] = field(default_factory=dict)      # repair start
    team_of: dict[str, str] = field(default_factory=dict)
    worked_h: dict[str, float] = field(default_factory=dict)        # team id -> hours travelling + repairing
    n_plans: int = 0
    kpis: dict[str, float] = field(default_factory=dict)


class Simulator:
    def __init__(self, cfg, incidents: list[Incident], teams: list[Team], policy, modifiers=None, seed: int = 0):
        self.cfg, self.policy = cfg, policy
        self.incidents = sorted(incidents, key=lambda i: i.reported_at)
        self.teams = [replace(t) for t in teams]
        self.modifiers = list(modifiers or [])
        self.rng = random.Random(seed)

    def _actual_duration(self, est: float) -> float:
        s = self.cfg.simulation.duration_noise_sigma
        return est if not s else est * math.exp(self.rng.gauss(-s * s / 2, s))

    def run(self, max_steps: int = 1_000_000) -> Result:
        cfg = self.cfg
        W, R = cfg.roster.work_h, cfg.roster.rest_h
        group = cfg.simulation.group_events_min / 60
        res = Result(worked_h={t.id: 0.0 for t in self.teams})
        pending: dict[str, Incident] = {}
        busy, wake = [], []                                   # heaps of (time, team index)
        for k, t in enumerate(self.teams):
            heapq.heappush(wake, (t.shift_start, k))
        ai, prev_plan = 0, None
        for _ in range(max_steps):
            nxt = [x for x in (self.incidents[ai].reported_at if ai < len(self.incidents) else None,
                               busy[0][0] if busy else None, wake[0][0] if wake else None) if x is not None]
            if not nxt:
                break
            now = min(nxt) + group
            while ai < len(self.incidents) and self.incidents[ai].reported_at <= now + EPS:
                pending[self.incidents[ai].id] = self.incidents[ai]; ai += 1
            while busy and busy[0][0] <= now + EPS:
                _, k = heapq.heappop(busy)
                self.teams[k].status, self.teams[k].current_job = TeamStatus.IDLE, None
            while wake and wake[0][0] <= now + EPS:
                heapq.heappop(wake)
            idle = [k for k, t in enumerate(self.teams)
                    if t.status == TeamStatus.IDLE and t.free_at <= now + EPS]
            if not pending or not idle:
                continue
            state = State(now=now, teams=self.teams, pending=list(pending.values()),
                          modifiers=self.modifiers, previous_plan=prev_plan)
            plan: Plan = self.policy.plan(state, cfg)
            prev_plan = plan
            res.n_plans += 1
            for k in idle:
                t = self.teams[k]
                route = plan.routes.get(t.id) or []
                if not route:
                    s, _ = window(t.shift_start, now, W, R)
                    if s > now + EPS:
                        heapq.heappush(wake, (s, k))          # off duty: look again when its shift starts
                    continue
                iid = route[0]
                go, arrive, _ = plan.schedule[iid]
                if go > now + EPS:                             # planned for later (next shift / access)
                    heapq.heappush(wake, (go, k)); continue
                inc = pending.pop(iid)
                C = arrive + self._actual_duration(inc.est_duration)
                res.started_at[iid], res.restored_at[iid], res.team_of[iid] = arrive, C, t.id
                res.worked_h[t.id] += C - go
                t.status, t.current_job, t.free_at, t.lat, t.lon = TeamStatus.REPAIRING, iid, C, inc.lat, inc.lon
                heapq.heappush(busy, (C, k))
        res.kpis = self.kpis(res)
        return res

    def kpis(self, res: Result) -> dict[str, float]:
        cfg = self.cfg
        beta = cfg.objective.beta_sensitive
        ch = wch = 0.0
        for i in self.incidents:
            C = res.restored_at.get(i.id)
            if C is None:
                continue
            ch += i.customers * (C - i.reported_at)
            wch += i.customers * (1 + beta * i.sensitive) * i.priority * (C - i.reported_at)
        st = cfg.service_target
        return {"customer_hours": ch, "weighted_customer_hours": wch,
                "restored": len(res.restored_at), "unrestored": len(self.incidents) - len(res.restored_at),
                "end_h": max(res.restored_at.values(), default=0.0),
                "share_by_deadline_incidents": service_share(res.restored_at, self.incidents, st.deadline_h, "incidents"),
                "share_by_deadline_customers": service_share(res.restored_at, self.incidents, st.deadline_h, "customers"),
                "mean_wait_per_customer_h": ch / max(1, sum(i.customers for i in self.incidents if i.id in res.restored_at)),
                "plans": res.n_plans}
