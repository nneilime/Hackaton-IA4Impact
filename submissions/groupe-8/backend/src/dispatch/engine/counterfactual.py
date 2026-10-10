"""What-if: re-plan with extra modifiers (e.g. the manager's override) and price the difference.

delta > 0 means the override costs that many (weighted) customer-hours compared with the engine's plan.
"""
from __future__ import annotations

from dataclasses import replace

from dispatch.engine.modifiers import Forbid, Force, Modifier
from dispatch.engine.planner import plan as make_plan
from dispatch.engine.types import Plan, State


def _satisfied(plan: Plan, mods: list[Modifier], state: State) -> bool:
    """True if `plan` already respects every Force / Forbid modifier (other modifiers change the data)."""
    teams = {t.id: t for t in state.teams}
    where = {iid: tid for tid, r in plan.routes.items() for iid in r}
    for m in mods:
        if isinstance(m, Force):
            if plan.routes.get(m.team, [])[:1] != [m.incident]:
                return False
        elif isinstance(m, Forbid):
            for iid, tid in where.items():
                t = teams.get(tid)
                if t and m.team_or_site in (t.id, t.home_site) and m.incident_or_zone == iid:
                    return False
        else:
            return False
    return True


def counterfactual(state: State, forced: list[Modifier], cfg, base_plan: Plan | None = None,
                   budget_ms: int | None = None) -> tuple[Plan, float]:
    base = base_plan or make_plan(state, cfg, budget_ms)
    if _satisfied(base, forced, state):
        return base, 0.0
    alt_state = replace(state, modifiers=list(state.modifiers) + list(forced), previous_plan=base)
    alt = make_plan(alt_state, cfg, budget_ms)
    return alt, alt.score.objective - base.score.objective
