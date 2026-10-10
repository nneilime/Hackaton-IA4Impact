"""Main entry point (RSLS): construction or warm start, then local search. Called at every event."""
from __future__ import annotations

from dispatch.engine.construct import insert_all, list_scheduling, warm_start
from dispatch.engine.context import build_context
from dispatch.engine.evaluate import decode, to_plan
from dispatch.engine.local_search import improve
from dispatch.engine.types import Plan, State


def plan(state: State, cfg, budget_ms: int | None = None) -> Plan:
    """Best plan for all known pending incidents. Always feasible (decoder), deterministic for a given seed."""
    budget_ms = cfg.solver.budget_ms if budget_ms is None else budget_ms
    ctx = build_context(state, cfg)
    routes, left = list_scheduling(ctx, "smith")
    left = insert_all(ctx, routes, left)
    if state.previous_plan is not None:                 # start from the better of warm start and fresh Smith plan
        w_routes, w_left = warm_start(ctx, state.previous_plan)
        if len(w_left) <= len(left) and _cost(ctx, w_routes) < _cost(ctx, routes):
            routes, left = w_routes, w_left
    routes = improve(ctx, routes, budget_ms, seed=cfg.solver.seed)
    return to_plan(ctx, routes, left)


def _cost(ctx, routes) -> float:
    return sum(decode(ctx, k, r).cost for k, r in enumerate(routes))


def should_publish(new: Plan, current: Plan | None, cfg, forced: bool = False) -> bool:
    """Publish a new plan only if it is clearly better (UI stability), or if an event forces it."""
    if forced or current is None:
        return True
    return new.score.total <= current.score.total * (1 - cfg.solver.publish_threshold)


class OptimisedPolicy:
    name = "optimised"

    def __init__(self, budget_ms: int | None = None):
        self.budget_ms = budget_ms

    def plan(self, state: State, cfg) -> Plan:
        return plan(state, cfg, self.budget_ms)
