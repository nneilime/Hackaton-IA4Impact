"""Reinforcement what-if: how many extra teams (from other regions / the FIRE), and at which sites, are needed
for the service target (e.g. 90 % of incidents fixed by H+48)?

Greedy: add one team at a time at the site that raises the share by the deadline the most, until the target is
met or `max_extra` is reached. Extra teams start at H0 (optimistic: real reinforcements arrive hours later).
"""
from __future__ import annotations

from collections import Counter

from dispatch.engine.baselines import SmithPolicy
from dispatch.engine.service import target_met
from dispatch.engine.types import Team
from dispatch.sim.simulator import Simulator


def _share(cfg, incidents, teams, policy_factory):
    res = Simulator(cfg, incidents, teams, policy_factory()).run()
    return res.kpis[f"share_by_deadline_{cfg.service_target.basis}"]


def teams_needed(cfg, incidents, teams, sites, policy_factory=SmithPolicy, max_extra: int = 40) -> dict:
    current = list(teams)
    share0 = share = _share(cfg, incidents, current, policy_factory)
    added = []
    while not target_met(share, cfg) and len(added) < max_extra:
        best = (-1.0, None)
        for s in sites:
            extra = Team(id=f"RENFORT_{len(added) + 1}", home_site=s.id, lat=s.lat, lon=s.lon, free_at=0.0)
            v = _share(cfg, incidents, current + [extra], policy_factory)
            if v > best[0]:
                best = (v, s)
        share, s = best
        current.append(Team(id=f"RENFORT_{len(added) + 1}", home_site=s.id, lat=s.lat, lon=s.lon, free_at=0.0))
        added.append(s.commune)
    return {"share_before": share0, "share_after": share, "target_met": target_met(share, cfg),
            "extra_teams": len(added), "by_site": dict(Counter(added))}
