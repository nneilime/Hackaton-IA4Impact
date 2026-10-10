"""Robustness scenarios (fast: Smith rule as dispatcher; the optimised engine is checked on one)."""
from dispatch.engine.baselines import SmithPolicy
from dispatch.engine.planner import OptimisedPolicy
from dispatch.sim import scenarios
from dispatch.sim.simulator import Simulator


def run(scn, policy=None, **kw):
    cfg, incs, teams, mods, _ = scn(crisis="CRISE_050", **kw) if scn is not scenarios.two_crises else scn(**kw)
    sim = Simulator(cfg, incs, teams, policy or SmithPolicy(), modifiers=mods)
    return sim.run(), incs, teams, mods


def test_flood_zone_not_entered_before_reopening():
    res, incs, _, _ = run(scenarios.flood, zone="Haute-Garonne", until_h=6.0)
    hg = [i.id for i in incs if i.departement == "Haute-Garonne"]
    assert hg and all(res.started_at[i] >= 6.0 - 1e-6 for i in hg)
    assert res.kpis["unrestored"] == 0


def test_teams_lost_do_not_start_new_jobs():
    res, incs, teams, mods = run(scenarios.teams_lost, fraction=0.5, at_h=3.0)
    lost = {m.team for m in mods}
    late = [i for i, t in res.team_of.items() if t in lost and res.started_at[i] > 3.0 + 6]
    assert not late and res.kpis["unrestored"] == 0


def test_two_crises_all_restored():
    res, incs, _, _ = run(scenarios.two_crises, first="CRISE_050", second="CRISE_001", gap_h=24.0)
    assert len(incs) == len({i.id for i in incs}) and res.kpis["unrestored"] == 0


def test_stress_and_noise_run():
    for scn in (scenarios.storm, scenarios.noise):
        res, *_ = run(scn)
        assert res.kpis["unrestored"] == 0
    res, *_ = run(lambda **k: scenarios.stress(fraction=0.25, **k))
    assert res.kpis["unrestored"] == 0


def test_optimised_not_worse_than_smith_under_stress():
    smith, *_ = run(lambda **k: scenarios.stress(fraction=0.5, **k))
    opt, *_ = run(lambda **k: scenarios.stress(fraction=0.5, **k), policy=OptimisedPolicy(20))
    assert opt.kpis["customer_hours"] <= smith.kpis["customer_hours"] * 1.01
