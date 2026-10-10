"""Reference strategies required by the README, plus the Smith rule alone. All go through the same decoder.

They are team-centric list scheduling: the team that becomes available first picks, by the rule's criterion,
among the incidents that fit its current shift.
"""
from __future__ import annotations

from typing import Protocol

from dispatch.engine.construct import list_scheduling
from dispatch.engine.context import build_context
from dispatch.engine.evaluate import to_plan
from dispatch.engine.types import Plan, State


class Policy(Protocol):
    name: str

    def plan(self, state: State, cfg) -> Plan: ...


class RulePolicy:
    def __init__(self, rule: str):
        self.name = rule
        self.rule = rule

    def plan(self, state: State, cfg) -> Plan:
        ctx = build_context(state, cfg)
        routes, left = list_scheduling(ctx, self.rule)
        return to_plan(ctx, routes, left)


class ReferencePolicy:
    """The front-end's reference strategy: first reported incident first, given to the team that can finish it
    earliest (nearest feasible team). Incident-centric, no optimisation."""
    name = "reference"

    def plan(self, state: State, cfg) -> Plan:
        from dispatch.engine.evaluate import INF, step
        ctx = build_context(state, cfg)
        routes = [[] for _ in ctx.teams]
        end = [(max(t.free_at, ctx.now), None) for t in ctx.teams]       # (free time, last node) per team
        left = []
        for i in sorted(range(len(ctx.incidents)), key=lambda i: ctx.r[i]):
            best = (INF, None)
            for k, team in enumerate(ctx.teams):
                if not ctx.allowed[k][i]:
                    continue
                t, prev = end[k]
                d = ctx.tt[k][i] if prev is None else ctx.ti[prev][i]
                C = step(ctx, team.shift_start, t, d, i)
                if C < best[0]:
                    best = (C, k)
            if best[1] is None:
                left.append(i)
            else:
                routes[best[1]].append(i)
                end[best[1]] = (best[0], i)
        return to_plan(ctx, routes, left)


def FifoPolicy():
    return RulePolicy("fifo")


def NearestPolicy():
    return RulePolicy("nearest")


def MaxCustomersPolicy():
    return RulePolicy("max_customers")


def SmithPolicy():
    return RulePolicy("smith")


BASELINES = {"reference": ReferencePolicy, "fifo": FifoPolicy, "nearest": NearestPolicy, "max_customers": MaxCustomersPolicy, "smith": SmithPolicy}
