"""Construction: list scheduling with a selection rule (Smith index by default), warm start, cheapest insertion."""
from __future__ import annotations

import heapq

from dispatch.engine.context import PlanContext
from dispatch.engine.evaluate import INF, decode, routes_from_plan
from dispatch.engine.shifts import EPS, window
from dispatch.engine.types import Plan

# score(ctx, team k, incident i, travel d) -> higher is better
RULES = {
    "smith": lambda ctx, k, i, d: ctx.w[i] / (d + ctx.p[i]),          # weighted customers per hour of team time
    "fifo": lambda ctx, k, i, d: -ctx.r[i],                           # oldest incident first
    "nearest": lambda ctx, k, i, d: -d,                               # closest incident first
    "max_customers": lambda ctx, k, i, d: ctx.n[i] + 1e6 * ctx.incidents[i].sensitive,  # sensitive, then biggest
}
MAX_HORIZON_H = 24 * 30


def list_scheduling(ctx: PlanContext, rule: str = "smith") -> tuple[list[list[int]], list[int]]:
    """The team that becomes available first takes the best incident (by `rule`) that fits its current shift."""
    W, R = ctx.cfg.roster.work_h, ctx.cfg.roster.rest_h
    score = RULES[rule]
    routes = [[] for _ in ctx.teams]
    remaining = set(range(len(ctx.incidents)))
    heap = []
    for k, team in enumerate(ctx.teams):
        t, prev = max(team.free_at, ctx.now), None
        if k in ctx.forced:                                   # operator-forced next job goes first
            i = ctx.forced[k]
            ev = decode(ctx, k, [i], trace=True)
            if ev.feasible:
                routes[k].append(i); remaining.discard(i)
                t, prev = ev.timings[0][3], i
        heapq.heappush(heap, (t, k, prev))
    while remaining and heap:
        t, k, prev = heapq.heappop(heap)
        if t > ctx.now + MAX_HORIZON_H:
            continue
        s, e = window(ctx.teams[k].shift_start, t, W, R)
        if t < s - EPS:
            heapq.heappush(heap, (s, k, prev)); continue
        best, best_sc, best_c = None, -INF, None
        for i in remaining:
            if not ctx.allowed[k][i]:
                continue
            d = ctx.tt[k][i] if prev is None else ctx.ti[prev][i]
            go = max(t, ctx.acc[i])
            C = go + d + ctx.p[i]
            if C > e + EPS:
                continue
            sc = score(ctx, k, i, d)
            if sc > best_sc:
                best, best_sc, best_c = i, sc, C
        if best is None:                                      # nothing fits this shift: next shift
            heapq.heappush(heap, (e + R, k, prev)); continue
        routes[k].append(best); remaining.discard(best)
        heapq.heappush(heap, (best_c, k, best))
    return routes, sorted(remaining)


def best_insertion(ctx: PlanContext, routes: list[list[int]], costs: list[float], i: int,
                   teams: list[int] | None = None) -> tuple[float, int | None, int | None]:
    """Cheapest (delta, team, position) to insert incident i. Respects forced first jobs and Forbid rules."""
    best = (INF, None, None)
    for k in (teams if teams is not None else range(len(ctx.teams))):
        if not ctx.allowed[k][i]:
            continue
        r = routes[k]
        start = 1 if (k in ctx.forced and r and r[0] == ctx.forced[k]) else 0
        for pos in range(start, len(r) + 1):
            c = decode(ctx, k, r[:pos] + [i] + r[pos:]).cost
            if c - costs[k] < best[0]:
                best = (c - costs[k], k, pos)
    return best


def insert_all(ctx: PlanContext, routes: list[list[int]], todo: list[int]) -> list[int]:
    """Insert every incident of `todo` at its cheapest position. Returns those that fit nowhere."""
    costs = [decode(ctx, k, r).cost for k, r in enumerate(routes)]
    left = []
    for i in todo:
        delta, k, pos = best_insertion(ctx, routes, costs, i)
        if k is None:
            left.append(i); continue
        routes[k].insert(pos, i)
        costs[k] += delta
    return left


def warm_start(ctx: PlanContext, previous: Plan) -> tuple[list[list[int]], list[int]]:
    """Previous plan minus finished / started jobs, forced jobs placed first, new incidents inserted cheaply."""
    routes = routes_from_plan(ctx, previous)
    for k, i in ctx.forced.items():
        for r in routes:
            if i in r:
                r.remove(i)
        routes[k].insert(0, i)
    planned = {i for r in routes for i in r}
    new = sorted((i for i in range(len(ctx.incidents)) if i not in planned), key=lambda i: ctx.r[i])
    left = insert_all(ctx, routes, new)
    return routes, left
