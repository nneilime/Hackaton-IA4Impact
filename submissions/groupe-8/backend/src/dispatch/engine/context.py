"""PlanContext: everything one planning call needs, with operator modifiers already applied.

Built once per call from a State. Incidents and teams are indexed 0..n-1 / 0..m-1; travel times are plain
Python lists (faster than numpy for the scalar look-ups done by the decoder).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace

import numpy as np

from dispatch.data.travel import travel_matrix
from dispatch.engine.modifiers import (DurationUpdate, Forbid, Force, Priority, Reserve, TeamUnavailable,
                                       TravelFactor, Weight, ZoneInaccessible)
from dispatch.engine.types import Incident, State, Team


@dataclass
class PlanContext:
    cfg: object
    now: float
    teams: list[Team]
    incidents: list[Incident]
    idx: dict[str, int]                         # incident id -> index
    team_idx: dict[str, int]                    # team id -> index
    w: list[float]                              # weights
    n: list[int]                                # customers
    r: list[float]                              # report times
    p: list[float]                              # estimated repair times
    acc: list[float]                            # accessible-from times
    tt: list[list[float]]                       # travel team k -> incident i (h)
    ti: list[list[float]]                       # travel incident i -> incident j (h)
    allowed: list[list[bool]]                   # allowed[k][i]
    forced: dict[int, int]                      # team -> incident that must be its next job
    prev_next: dict[int, int]                   # team -> next job in the previous plan (stability)
    near_teams: list[list[int]] = field(default_factory=list)   # per incident, closest teams first
    dmin: list[float] = field(default_factory=list)             # per incident, shortest possible travel to it


def _matches_zone(inc: Incident, zone: str) -> bool:
    z = zone.strip().lower()
    return z in (inc.commune.lower(), inc.departement.lower(), inc.poste_id.lower(), inc.id.lower())


def _effective_cfg(cfg, modifiers):
    weights = [m for m in modifiers if isinstance(m, Weight)]
    if not weights:
        return cfg
    cfg = copy.copy(cfg)
    cfg.objective = copy.copy(cfg.objective)
    for m in weights:
        setattr(cfg.objective, m.name, m.value)
    return cfg


def build_context(state: State, cfg) -> PlanContext:
    mods = state.modifiers or []
    cfg = _effective_cfg(cfg, mods)
    now = state.now

    incidents = []
    for inc in state.pending:
        for m in mods:
            if isinstance(m, DurationUpdate) and m.incident == inc.id:
                inc = replace(inc, est_duration=m.hours)
            elif isinstance(m, Priority) and m.incident == inc.id:
                inc = replace(inc, priority=inc.priority * m.factor,
                              sensitive=inc.sensitive if m.sensitive is None else m.sensitive)
            elif isinstance(m, ZoneInaccessible) and _matches_zone(inc, m.zone):
                inc = replace(inc, accessible_from=max(inc.accessible_from, m.until_h))
            elif isinstance(m, TravelFactor) and _matches_zone(inc, m.zone):
                inc = replace(inc, travel_factor=inc.travel_factor * m.factor)
        incidents.append(inc)

    teams = []
    reserved = {m.site: [m.n_teams, m.until_h] for m in mods if isinstance(m, Reserve)}
    for t in state.teams:
        t = replace(t)
        for m in mods:
            if isinstance(m, TeamUnavailable) and m.team == t.id and m.from_h <= now + 1e-9:
                if m.until_h is None:
                    t = None
                    break
                t.free_at = max(t.free_at, m.until_h)
        if t is None:
            continue
        if t.home_site in reserved and reserved[t.home_site][0] > 0 and t.free_at <= now:
            reserved[t.home_site][0] -= 1
            until = reserved[t.home_site][1]
            if until is None:
                continue
            t.free_at = max(t.free_at, until)
        teams.append(t)

    n_inc, m_team = len(incidents), len(teams)
    beta = cfg.objective.beta_sensitive
    w = [i.customers * (1 + beta * i.sensitive) * i.priority for i in incidents]
    if n_inc and m_team:
        ilat = np.array([i.lat for i in incidents]); ilon = np.array([i.lon for i in incidents])
        tlat = np.array([t.lat for t in teams]); tlon = np.array([t.lon for t in teams])
        fac = np.array([i.travel_factor for i in incidents])
        tpts = np.column_stack([tlat, tlon]); ipts = np.column_stack([ilat, ilon])
        tt_np = travel_matrix(tpts, ipts, cfg) * fac[None, :]
        ti_np = travel_matrix(ipts, ipts, cfg) * fac[None, :]
        tt, ti = tt_np.tolist(), ti_np.tolist()
        ti_off = ti_np + np.diag(np.full(n_inc, np.inf))
        dmin = np.minimum(tt_np.min(axis=0), ti_off.min(axis=0) if n_inc > 1 else np.inf).tolist()
        k_near = min(cfg.solver.neighbour_teams, m_team)
        near = np.argsort(tt_np, axis=0)[:k_near].T.tolist()
    else:
        tt, ti, near = [[] for _ in teams], [[] for _ in incidents], [[] for _ in incidents]
        dmin = [0.0] * n_inc

    idx = {inc.id: i for i, inc in enumerate(incidents)}
    team_idx = {t.id: k for k, t in enumerate(teams)}
    allowed = [[True] * n_inc for _ in teams]
    forced = {}
    for m in mods:
        if isinstance(m, Forbid):
            for k, t in enumerate(teams):
                if m.team_or_site in (t.id, t.home_site):
                    for i, inc in enumerate(incidents):
                        if m.incident_or_zone == inc.id or _matches_zone(inc, m.incident_or_zone):
                            allowed[k][i] = False
        elif isinstance(m, Force) and m.team in team_idx and m.incident in idx:
            forced[team_idx[m.team]] = idx[m.incident]

    prev_next = {}
    if state.previous_plan is not None:
        for tid, route in state.previous_plan.routes.items():
            if route and tid in team_idx and route[0] in idx:
                prev_next[team_idx[tid]] = idx[route[0]]

    return PlanContext(cfg=cfg, now=now, teams=teams, incidents=incidents, idx=idx, team_idx=team_idx, w=w,
                       n=[i.customers for i in incidents], r=[i.reported_at for i in incidents],
                       p=[i.est_duration for i in incidents], acc=[i.accessible_from for i in incidents],
                       tt=tt, ti=ti, allowed=allowed, forced=forced, prev_next=prev_next, near_teams=near,
                       dmin=dmin)
