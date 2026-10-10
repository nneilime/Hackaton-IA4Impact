"""Reference solver (offline): Google OR-Tools Routing on the same decision, to measure how far our heuristic is.

Mapping of our model:
  vehicles = teams, starting at their current position and free time; free end (dummy depot)
  time dimension in minutes: transit(i -> j) = repair(i) + travel(i, j)
  objective Σ w_i · C_i via SetCumulVarSoftUpperBound(i, 0, w_i)  (= Σ w_i (C_i - r_i) + constant)
  rest periods of the fixed roster = break intervals of each vehicle (repairs cannot overlap them)
The routes OR-Tools returns are then re-timed by OUR decoder (exact work rules), so costs are comparable.
Requires the `bench` extra (ortools).
"""
from __future__ import annotations

from dispatch.engine.context import build_context
from dispatch.engine.evaluate import to_plan
from dispatch.engine.types import Plan, State


def solve(state: State, cfg, time_limit_s: int = 60, initial_routes: list[list[int]] | None = None) -> Plan:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    ctx = build_context(state, cfg)
    n, m = len(ctx.incidents), len(ctx.teams)
    W, R = cfg.roster.work_h, cfg.roster.rest_h
    SCALE = 60                                                # minutes
    now = ctx.now
    # nodes: 0..n-1 incidents, n..n+m-1 team starts, n+m dummy end
    starts = [n + k for k in range(m)]
    end = n + m
    manager = pywrapcp.RoutingIndexManager(n + m + 1, m, starts, [end] * m)
    routing = pywrapcp.RoutingModel(manager)

    def minutes(h):
        return int(round(h * SCALE))

    service = [minutes(ctx.p[i]) for i in range(n)] + [0] * (m + 1)

    def transit(a_idx, b_idx):
        a, b = manager.IndexToNode(a_idx), manager.IndexToNode(b_idx)
        if b == end:
            return service[a] if a < n else 0
        if a >= n:                                              # from a team start
            return minutes(ctx.tt[a - n][b])
        return service[a] + minutes(ctx.ti[a][b])

    cb = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(lambda a, b: 0))
    horizon = minutes(24 * 30)
    routing.AddDimension(cb, horizon, horizon, False, "time")
    time_dim = routing.GetDimensionOrDie("time")
    for k, team in enumerate(ctx.teams):
        start_idx = routing.Start(k)
        time_dim.CumulVar(start_idx).SetMin(minutes(max(team.free_at, now) - now))
    for i in range(n):
        idx = manager.NodeToIndex(i)
        time_dim.CumulVar(idx).SetMin(minutes(max(ctx.acc[i], now) - now))
        time_dim.SetCumulVarSoftUpperBound(idx, 0, max(1, int(round(ctx.w[i]))))
        for k in range(m):
            if not ctx.allowed[k][i]:
                routing.VehicleVar(idx).RemoveValue(k)
    for k, i in ctx.forced.items():
        routing.solver().Add(routing.NextVar(routing.Start(k)) == manager.NodeToIndex(i))
    # rest periods of the fixed roster as breaks (horizon of 5 days)
    solver = routing.solver()
    node_visit_transits = [service[manager.IndexToNode(j)] if manager.IndexToNode(j) < n else 0
                           for j in range(routing.Size())]
    for k, team in enumerate(ctx.teams):
        breaks, s = [], team.shift_start
        while s + W - now < 24 * 5:
            rest_start = s + W - now
            if rest_start + R > 0:
                b0 = minutes(max(rest_start, 0))
                dur = minutes(rest_start + R) - b0
                breaks.append(solver.FixedDurationIntervalVar(b0, b0, dur, False, f"rest_{k}_{b0}"))
            s += W + R
        if team.shift_start - now > 0:                          # not yet on duty
            breaks.append(solver.FixedDurationIntervalVar(0, 0, minutes(team.shift_start - now), False, f"pre_{k}"))
        if breaks:
            time_dim.SetBreakIntervalsOfVehicle(breaks, k, node_visit_transits)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    if initial_routes:
        routing.CloseModelWithParameters(params)
        init = routing.ReadAssignmentFromRoutes(initial_routes, True)
        sol = routing.SolveFromAssignmentWithParameters(init, params) if init else routing.SolveWithParameters(params)
    else:
        sol = routing.SolveWithParameters(params)
    if sol is None:
        raise RuntimeError("OR-Tools found no solution")
    routes = []
    for k in range(m):
        idx, r = routing.Start(k), []
        idx = sol.Value(routing.NextVar(idx))
        while not routing.IsEnd(idx):
            r.append(manager.IndexToNode(idx))
            idx = sol.Value(routing.NextVar(idx))
        routes.append(r)
    return to_plan(ctx, routes)                                 # re-timed by our decoder (exact rules)
