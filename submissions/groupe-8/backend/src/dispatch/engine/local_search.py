"""Improvement: iterated local search within a time budget.

Moves (each re-evaluates only the 1-2 teams it touches):
  relocate  - move an incident to its best position on one of the teams closest to it (or its own team).
              Fast: insertion is evaluated from cached prefix states (only the part after the insertion point is
              recomputed), and positions are scanned in time order with a lower bound (the inserted incident's own
              cost at its earliest possible completion), so the scan stops as soon as no better move is possible.
  swap      - exchange two incidents between two teams
  ruin & recreate - after `ruin_every` non-improving moves, remove a fraction of incidents and reinsert them
                    cheapest-first; kept only if the total improves.
Incidents to relocate are picked half at random, half among the costliest (tournament).
Deterministic for a given seed. Always returns the best feasible plan found.
"""
from __future__ import annotations

import random
import time

from dispatch.engine.construct import best_insertion
from dispatch.engine.context import PlanContext
from dispatch.engine.evaluate import (INF, cost_from, decode, incident_cost, prefix_states, stability_cost)

IMPROVE = 1e-6


def improve(ctx: PlanContext, routes: list[list[int]], budget_ms: int, seed: int = 0) -> list[list[int]]:
    if budget_ms <= 0 or not ctx.incidents:
        return routes
    cfg = ctx.cfg.solver
    rng = random.Random(seed)
    routes = [list(r) for r in routes]
    costs = [decode(ctx, k, r).cost for k, r in enumerate(routes)]
    locked = {i for k, i in ctx.forced.items() if routes[k][:1] == [i]}
    where = {i: k for k, r in enumerate(routes) for i in r}
    movable = sorted(i for i in where if i not in locked)
    if not movable:
        return routes
    cache: dict[int, tuple] = {}

    def states(k):
        key = tuple(routes[k])
        hit = cache.get(k)
        if hit is None or hit[0] != key:
            hit = (key, prefix_states(ctx, k, routes[k]))
            cache[k] = hit
        return hit[1]

    def own_cost(i):
        k = where[i]
        ts, _, cs = states(k)
        pos = routes[k].index(i)
        return cs[pos + 1] - cs[pos]

    def pick():
        if rng.random() < 0.5:
            return rng.choice(movable)
        return max(rng.sample(movable, min(3, len(movable))), key=own_cost)

    def relocate(i):
        k = where[i]
        r = routes[k]
        r_wo = [x for x in r if x != i]
        c_wo = decode(ctx, k, r_wo).cost
        rem = c_wo - costs[k]
        best = (-IMPROVE, None, None)
        p_i, acc_i, dmin_i = ctx.p[i], ctx.acc[i], ctx.dmin[i]
        for k2 in set(ctx.near_teams[i]) | {k}:
            if not ctx.allowed[k2][i]:
                continue
            r2 = r_wo if k2 == k else routes[k2]
            ts, prevs, cs = prefix_states(ctx, k2, r2) if k2 == k else states(k2)
            base = c_wo if k2 == k else costs[k2]
            start = 1 if (k2 in ctx.forced and r2 and r2[0] == ctx.forced[k2]) else 0
            for pos in range(start, len(r2) + 1):
                lb = incident_cost(ctx, i, max(ts[pos], acc_i) + dmin_i + p_i)
                if (rem if k2 != k else c_wo - costs[k]) + lb >= best[0]:
                    break                                       # later positions can only be worse
                if cs[pos] == INF:
                    break
                new_r = r2[:pos] + [i] + r2[pos:]
                c = cost_from(ctx, k2, ts[pos], prevs[pos], cs[pos], new_r[pos:])
                if c == INF:
                    continue
                c += stability_cost(ctx, k2, new_r)
                delta = (c - costs[k]) if k2 == k else (rem + c - base)
                if delta < best[0]:
                    best = (delta, k2, pos)
        _, k2, pos = best
        if k2 is None:
            return False
        if k2 == k:
            routes[k] = r_wo[:pos] + [i] + r_wo[pos:]
            costs[k] = decode(ctx, k, routes[k]).cost
        else:
            routes[k], costs[k] = r_wo, c_wo
            routes[k2] = routes[k2][:pos] + [i] + routes[k2][pos:]
            costs[k2] = decode(ctx, k2, routes[k2]).cost
            where[i] = k2
        return True

    def swap(i, j):
        ki, kj = where[i], where[j]
        if ki == kj or not ctx.allowed[ki][j] or not ctx.allowed[kj][i]:
            return False
        ri = [j if x == i else x for x in routes[ki]]
        rj = [i if x == j else x for x in routes[kj]]
        ci, cj = decode(ctx, ki, ri).cost, decode(ctx, kj, rj).cost
        if ci + cj < costs[ki] + costs[kj] - IMPROVE:
            routes[ki], routes[kj], costs[ki], costs[kj] = ri, rj, ci, cj
            where[i], where[j] = kj, ki
            return True
        return False

    def ruin_and_recreate():
        nonlocal routes, costs, where
        snap = ([list(r) for r in routes], list(costs), dict(where))
        total0 = sum(costs)
        k_rm = max(1, int(len(movable) * cfg.ruin_fraction))
        removed = rng.sample(movable, k_rm)
        for i in removed:
            routes[where[i]].remove(i)
        costs = [decode(ctx, k, r).cost for k, r in enumerate(routes)]
        rng.shuffle(removed)
        for i in removed:
            delta, k, pos = best_insertion(ctx, routes, costs, i, teams=sorted(set(ctx.near_teams[i])))
            if k is None:
                delta, k, pos = best_insertion(ctx, routes, costs, i)
            if k is None:
                routes, costs, where = snap
                return False
            routes[k].insert(pos, i); costs[k] += delta; where[i] = k
        if sum(costs) < total0 - IMPROVE:
            return True
        routes, costs, where = snap
        return False

    stop = time.perf_counter() + budget_ms / 1000
    stale = 0
    while time.perf_counter() < stop:
        if rng.random() < 0.75 or len(movable) < 2:
            ok = relocate(pick())
        else:
            ok = swap(*rng.sample(movable, 2))
        stale = 0 if ok else stale + 1
        if stale >= cfg.ruin_every:
            ruin_and_recreate()
            stale = 0
    return routes
