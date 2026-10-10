"""Explanation facts for each recommended next job. The LLM may only state numbers found here.

Alternatives are priced with the model itself (decoder), by local re-insertion:
  - best alternative team for the incident: move it to the front of another team's list
  - best alternative incident for the team: swap it with the front job of another team's list
delta > 0 = the alternative is worse by that many (weighted) customer-hours.
"""
from __future__ import annotations

from dispatch.engine.context import build_context
from dispatch.engine.evaluate import INF, decode, routes_from_plan
from dispatch.engine.shifts import window
from dispatch.engine.types import ExplanationFacts, Plan, State


def explain(plan: Plan, state: State, cfg, teams: list[str] | None = None) -> list[ExplanationFacts]:
    ctx = build_context(state, cfg)
    routes = routes_from_plan(ctx, plan)
    costs = [decode(ctx, k, r).cost for k, r in enumerate(routes)]
    W, R = cfg.roster.work_h, cfg.roster.rest_h
    # rank of every next job by priority index, to say "2nd highest"
    firsts = [(k, r[0]) for k, r in enumerate(routes) if r]
    idx_of = {}
    for k, i in firsts:
        ev = decode(ctx, k, [i], trace=True)
        _, go, arrive, C = ev.timings[0]
        idx_of[(k, i)] = ctx.w[i] / (arrive - go + ctx.p[i])
    ranking = sorted(idx_of.values(), reverse=True)

    facts = []
    for k, i in firsts:
        team = ctx.teams[k]
        if teams is not None and team.id not in teams:
            continue
        ev = decode(ctx, k, routes[k], trace=True)
        _, go, arrive, C = ev.timings[0]
        s, e = window(team.shift_start, go, W, R)
        rho = idx_of[(k, i)]
        # best alternative team for incident i
        r_wo = routes[k][1:]
        c_wo = decode(ctx, k, r_wo).cost
        alts = []
        firsts_of = {k2: r2[0] for k2, r2 in enumerate(routes) if r2}
        for k2 in ctx.near_teams[i]:
            if k2 == k:
                continue
            t2 = ctx.teams[k2]
            base = {"team": t2.id, "recommended_for": ctx.incidents[firsts_of[k2]].id if k2 in firsts_of else None}
            if not ctx.allowed[k2][i]:
                alts.append({**base, "feasible": False, "reason": "interdit par une règle opérateur", "delta": None})
                continue
            if k2 in ctx.forced:
                alts.append({**base, "feasible": False, "reason": "déjà imposée par l'opérateur", "delta": None})
                continue
            ev2 = decode(ctx, k2, [i] + routes[k2], trace=True)
            if not ev2.feasible:
                alts.append({**base, "feasible": False, "reason": "intervention plus longue qu'un poste", "delta": None})
                continue
            delta = (c_wo + ev2.cost) - (costs[k] + costs[k2])
            _, g2, a2, C2 = ev2.timings[0]
            s2, e2 = window(t2.shift_start, g2, W, R)
            reason = None
            if g2 > max(t2.free_at, ctx.now) + 1e-6 and s2 > max(t2.free_at, ctx.now):
                reason = "au repos : part au début de son prochain poste"
            elif t2.free_at > ctx.now + 1e-6:
                reason = "occupée : part après son intervention en cours"
            alts.append({**base, "feasible": True, "reason": reason, "delta": round(delta, 1), "depart_h": round(g2, 2),
                         "arrive_h": round(a2, 2), "restored_h": round(C2, 2), "travel_min": round(60 * (a2 - g2)),
                         "shift_left_after_h": round(max(0.0, e2 - C2), 2)})
        alts.sort(key=lambda a: (not a["feasible"], a["delta"] if a["delta"] is not None else INF))
        ok = [a for a in alts if a["feasible"]]
        alt_team = (ok[0]["delta"], ctx.team_idx[ok[0]["team"]]) if ok else (INF, None)
        # best alternative incident for team k (swap with another team's next job)
        alt_inc = (INF, None)
        for k2, j in firsts:
            if k2 == k or not ctx.allowed[k][j] or not ctx.allowed[k2][i] or k in ctx.forced or k2 in ctx.forced:
                continue
            ck = decode(ctx, k, [j] + routes[k][1:]).cost
            c2 = decode(ctx, k2, [i] + routes[k2][1:]).cost
            delta = (ck + c2) - (costs[k] + costs[k2])
            if delta < alt_inc[0]:
                alt_inc = (delta, j)
        binding = None
        if k in ctx.forced:
            binding = "forced by the operator"
        elif go > max(team.free_at, ctx.now) + 1e-6 and go >= s - 1e-6 and s > max(team.free_at, ctx.now):
            binding = "waits for the team's next shift"
        elif ctx.acc[i] > max(team.free_at, ctx.now):
            binding = "incident not accessible before departure"
        inc = ctx.incidents[i]
        facts.append(ExplanationFacts(
            team=team.id, incident=inc.id, rank_in_plan=1 + ranking.index(rho),
            factors={"customers": inc.customers, "sensitive": bool(inc.sensitive), "weight": round(ctx.w[i], 1),
                     "travel_min": round(60 * (arrive - go)), "repair_h": ctx.p[i],
                     "shift_left_h": round(e - C, 2), "priority_index": round(rho, 2),
                     "depart_h": round(go, 2), "arrive_h": round(arrive, 2), "restored_h": round(C, 2)},
            best_alternative_team=None if alt_team[1] is None else
            {"team": ctx.teams[alt_team[1]].id, "delta": round(alt_team[0], 1)},
            best_alternative_incident=None if alt_inc[1] is None else
            {"incident": ctx.incidents[alt_inc[1]].id, "delta": round(alt_inc[0], 1)},
            binding_constraint=binding, alternatives=alts[:10]))
    return facts
