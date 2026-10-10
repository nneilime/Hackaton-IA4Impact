"""The decoder (one team's ordered list -> timetable and cost) and plan scoring.

Every solver, baseline and explanation goes through `decode`, so the work rules live in one place:
one job at a time, travel then repair, never before the incident is reported / accessible, and
travel + repair must fit entirely inside a scheduled shift (otherwise the job moves to the next shift).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dispatch.engine.context import PlanContext
from dispatch.engine.shifts import EPS, window
from dispatch.engine.types import Incident, Plan, ScoreBreakdown

INF = float("inf")


@dataclass
class RouteEval:
    feasible: bool
    cost: float = 0.0
    timings: list[tuple[int, float, float, float]] = field(default_factory=list)  # (i, depart, start repair, end)


def weight(incident: Incident, cfg) -> float:
    """w_i = customers x (1 + beta x sensitive) x priority."""
    return incident.customers * (1 + cfg.objective.beta_sensitive * incident.sensitive) * incident.priority


def incident_cost(ctx: PlanContext, i: int, C: float) -> float:
    """f_i(C_i) = w_i (C_i - r_i) + gamma n_i max(0, C_i - r_i - D)."""
    T = C - ctx.r[i]
    cost = ctx.w[i] * T
    o = ctx.cfg.objective
    if o.starvation_gamma and T > o.starvation_deadline_h:
        cost += o.starvation_gamma * ctx.n[i] * (T - o.starvation_deadline_h)
    return cost


def decode(ctx: PlanContext, k: int, route: list[int], trace: bool = False) -> RouteEval:
    """Timetable and cost of team k doing `route` in order. INF if a job can never fit in a shift."""
    team = ctx.teams[k]
    W, R = ctx.cfg.roster.work_h, ctx.cfg.roster.rest_h
    t = max(team.free_at, ctx.now)
    cost = 0.0
    lam = ctx.cfg.objective.lambda_stability
    if lam and k in ctx.prev_next and (not route or route[0] != ctx.prev_next[k]):
        cost += lam
    prev = None
    timings = [] if trace else None
    for i in route:
        d = ctx.tt[k][i] if prev is None else ctx.ti[prev][i]
        p = ctx.p[i]
        if d + p > W + EPS:
            return RouteEval(False, INF)
        go = max(t, ctx.acc[i])
        s, e = window(team.shift_start, go, W, R)
        go = max(go, s)
        if go + d + p > e + EPS:                      # does not fit: wait for the next shift
            go = max(e + R, ctx.acc[i])
            s, e = window(team.shift_start, go, W, R)
            go = max(go, s)
            if go + d + p > e + EPS:
                return RouteEval(False, INF)
        C = go + d + p
        cost += incident_cost(ctx, i, C)
        if trace:
            timings.append((i, go, go + d, C))
        t, prev = C, i
    return RouteEval(True, cost, timings or [])


def route_cost(ctx: PlanContext, k: int, route: list[int]) -> float:
    return decode(ctx, k, route).cost


# ---------------------------------------------------------------- fast incremental evaluation (local search)
def step(ctx: PlanContext, shift_start: float, t: float, d: float, i: int) -> float:
    """Completion time of job i started from time t with travel d (same rules as `decode`). INF if impossible."""
    W, R = ctx.cfg.roster.work_h, ctx.cfg.roster.rest_h
    p = ctx.p[i]
    if d + p > W + EPS:
        return INF
    go = max(t, ctx.acc[i])
    s, e = window(shift_start, go, W, R)
    go = max(go, s)
    if go + d + p > e + EPS:
        go = max(e + R, ctx.acc[i])
        s, e = window(shift_start, go, W, R)
        go = max(go, s)
        if go + d + p > e + EPS:
            return INF
    return go + d + p


def stability_cost(ctx: PlanContext, k: int, route: list[int]) -> float:
    lam = ctx.cfg.objective.lambda_stability
    return lam if lam and k in ctx.prev_next and (not route or route[0] != ctx.prev_next[k]) else 0.0


def prefix_states(ctx: PlanContext, k: int, route: list[int]) -> tuple[list, list, list]:
    """State after each prefix of the route: free time, last node, cost so far (without stability)."""
    team = ctx.teams[k]
    t, prev, cost = max(team.free_at, ctx.now), None, 0.0
    ts, prevs, costs = [t], [prev], [cost]
    for i in route:
        d = ctx.tt[k][i] if prev is None else ctx.ti[prev][i]
        C = step(ctx, team.shift_start, t, d, i)
        cost = cost + incident_cost(ctx, i, C) if C < INF else INF
        t, prev = C, i
        ts.append(t); prevs.append(prev); costs.append(cost)
    return ts, prevs, costs


def cost_from(ctx: PlanContext, k: int, t: float, prev: int | None, cost: float, nodes: list[int]) -> float:
    """Cost of finishing a route from a prefix state with `nodes` (without stability)."""
    ss = ctx.teams[k].shift_start
    for i in nodes:
        d = ctx.tt[k][i] if prev is None else ctx.ti[prev][i]
        C = step(ctx, ss, t, d, i)
        if C == INF:
            return INF
        cost += incident_cost(ctx, i, C)
        t, prev = C, i
    return cost


def to_plan(ctx: PlanContext, routes: list[list[int]], unassigned: list[int] | None = None) -> Plan:
    """Turn index routes into a Plan with ids, timetable and a full score breakdown."""
    cfg = ctx.cfg
    sched, rid = {}, {}
    weighted = cust_h = starv = stab = 0.0
    deadline = cfg.service_target.deadline_h
    on_time = n_planned = 0
    for k, route in enumerate(routes):
        tid = ctx.teams[k].id
        rid[tid] = [ctx.incidents[i].id for i in route]
        if cfg.objective.lambda_stability and k in ctx.prev_next and (not route or route[0] != ctx.prev_next[k]):
            stab += cfg.objective.lambda_stability
        for i, go, arrive, C in decode(ctx, k, route, trace=True).timings:
            sched[ctx.incidents[i].id] = (go, arrive, C)
            T = C - ctx.r[i]
            weighted += ctx.w[i] * T
            cust_h += ctx.n[i] * T
            starv += incident_cost(ctx, i, C) - ctx.w[i] * T
            n_planned += 1
            on_time += C <= deadline + EPS
    objective = weighted + starv
    score = ScoreBreakdown(total=objective + stab, objective=objective, weighted_customer_hours=weighted,
                           customer_hours=cust_h, stability_penalty=stab, starvation_penalty=starv,
                           kpis={"planned_incidents": n_planned,
                                 "planned_share_by_deadline": on_time / n_planned if n_planned else 1.0})
    un = [ctx.incidents[i].id for i in (unassigned or [])]
    return Plan(routes=rid, schedule=sched, unassigned=un, score=score)


def routes_from_plan(ctx: PlanContext, plan: Plan) -> list[list[int]]:
    """Index routes of a Plan restricted to the incidents and teams present in ctx."""
    routes = [[] for _ in ctx.teams]
    seen = set()
    for tid, ids in plan.routes.items():
        k = ctx.team_idx.get(tid)
        if k is None:
            continue
        for iid in ids:
            i = ctx.idx.get(iid)
            if i is not None and i not in seen and ctx.allowed[k][i]:
                routes[k].append(i); seen.add(i)
    return routes
