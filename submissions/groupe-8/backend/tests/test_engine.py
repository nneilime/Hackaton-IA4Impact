"""Engine acceptance tests (docs/RO_ENGINE_BRIEF.md §9, docs/CURRENT_SETUP.md)."""
import pytest

from dispatch.config import load_config
from dispatch.data.loaders import load_incidents, load_teams
from dispatch.engine.baselines import BASELINES
from dispatch.engine.construct import list_scheduling
from dispatch.engine.context import build_context
from dispatch.engine.counterfactual import counterfactual
from dispatch.engine.evaluate import decode, to_plan
from dispatch.engine.explain import explain
from dispatch.engine.modifiers import Forbid, Force, ZoneInaccessible
from dispatch.engine.planner import OptimisedPolicy, plan
from dispatch.engine.service import service_share
from dispatch.engine.shifts import window
from dispatch.engine.types import Incident, State, Team
from dispatch.sim.simulator import Simulator

cfg = load_config()
LONG = load_config(roster={"work_h": 100, "rest_h": 12})      # one long shift: rules out shift effects


def _toy():
    """One team, three incidents at t0, all at the team's position (no travel)."""
    team = Team(id="T1", home_site="S1", lat=43.6, lon=1.44, free_at=0.0)
    mk = lambda i, n, p: Incident(id=i, poste_id=i, lat=43.6, lon=1.44, customers=n,  # noqa: E731
                                  sensitive=False, reported_at=0.0, est_duration=p)
    return team, mk("A", 150, 8.0), mk("B", 60, 2.0), mk("C", 100, 4.0)


def test_shift_window():
    assert window(0, 5, 12, 12) == (0, 12)
    assert window(0, 13, 12, 12) == (24, 36)       # in rest -> next shift
    assert window(2, 0, 12, 12) == (2, 14)         # before the first shift


def test_T1_decoder_toy_scores():
    team, a, b, c = _toy()
    ctx = build_context(State(now=0, teams=[team], pending=[a, b, c]), LONG)
    A, B, C = ctx.idx["A"], ctx.idx["B"], ctx.idx["C"]
    assert decode(ctx, 0, [A, C, B]).cost == pytest.approx(3240)
    assert decode(ctx, 0, [B, C, A]).cost == pytest.approx(2820)


def test_T2_smith_order_single_team():
    team, a, b, c = _toy()
    ctx = build_context(State(now=0, teams=[team], pending=[a, b, c]), LONG)
    routes, left = list_scheduling(ctx, "smith")
    assert [ctx.incidents[i].id for i in routes[0]] == ["B", "C", "A"] and not left


def test_job_never_crosses_shift_end():
    team = Team(id="T1", home_site="S1", lat=43.6, lon=1.44, free_at=10.0)
    inc = Incident(id="X", poste_id="X", lat=43.6, lon=1.44, customers=10, sensitive=False,
                   reported_at=10.0, est_duration=4.0)
    ctx = build_context(State(now=10.0, teams=[team], pending=[inc]), cfg)
    (_, go, _, C), = decode(ctx, 0, [0], trace=True).timings
    assert go == pytest.approx(24.0) and C == pytest.approx(28.0)   # 4 h job does not fit before 12 h


@pytest.fixture(scope="module")
def crisis():
    incs, _ = load_incidents(cfg, "CRISE_050")
    teams = load_teams(cfg)
    now = 3.0
    return State(now=now, teams=teams, pending=[i for i in incs if i.reported_at <= now])


def test_T3_plan_feasible_and_complete(crisis):
    p = plan(crisis, cfg, budget_ms=100)
    planned = [iid for r in p.routes.values() for iid in r]
    assert sorted(planned) == sorted(i.id for i in crisis.pending) and not p.unassigned
    W, R = cfg.roster.work_h, cfg.roster.rest_h
    teams = {t.id: t for t in crisis.teams}
    for tid, route in p.routes.items():
        for iid in route:
            go, _, C = p.schedule[iid]
            s, e = window(teams[tid].shift_start, go, W, R)
            assert s - 1e-6 <= go and C <= e + 1e-6               # the whole job fits in one shift


def test_T5_deterministic(crisis):
    a, b = plan(crisis, cfg, budget_ms=60), plan(crisis, cfg, budget_ms=60)
    assert a.routes == b.routes or a.score.total == pytest.approx(b.score.total, rel=1e-3)


def test_local_search_never_worse_than_construction(crisis):
    ctx = build_context(crisis, cfg)
    routes, left = list_scheduling(ctx, "smith")
    greedy = to_plan(ctx, routes, left).score.total
    assert plan(crisis, cfg, budget_ms=150).score.total <= greedy + 1e-6


def test_T4_force_and_forbid_respected(crisis):
    p = plan(crisis, cfg, budget_ms=50)
    tid, route = next((t, r) for t, r in p.routes.items() if len(r) >= 1)
    other = next(t.id for t in crisis.teams if t.id != tid)
    st = State(now=crisis.now, teams=crisis.teams, pending=crisis.pending,
               modifiers=[Force(team=other, incident=route[0]), Forbid(team_or_site=tid, incident_or_zone=route[0])])
    q = plan(st, cfg, budget_ms=50)
    assert q.routes[other][0] == route[0]
    assert route[0] not in q.routes.get(tid, [])


def test_zone_inaccessible_delays_departure(crisis):
    inc = crisis.pending[0]
    st = State(now=crisis.now, teams=crisis.teams, pending=crisis.pending,
               modifiers=[ZoneInaccessible(zone=inc.commune, until_h=crisis.now + 5)])
    q = plan(st, cfg, budget_ms=30)
    assert q.schedule[inc.id][0] >= crisis.now + 5 - 1e-6


def test_T8_counterfactual_zero_for_recommended(crisis):
    base = plan(crisis, cfg, budget_ms=50)
    tid, route = next((t, r) for t, r in base.routes.items() if r)
    _, delta = counterfactual(crisis, [Force(team=tid, incident=route[0])], cfg, base_plan=base)
    assert delta == 0.0


def test_explanation_facts(crisis):
    p = plan(crisis, cfg, budget_ms=50)
    facts = explain(p, crisis, cfg)
    assert facts and all(f.factors["priority_index"] > 0 for f in facts)
    assert any(f.best_alternative_team for f in facts)


def test_service_share():
    _, a, b, c = _toy()
    assert service_share({"A": 10, "B": 50}, [a, b, c], 48) == pytest.approx(1 / 3)
    assert service_share({"A": 10}, [a, b, c], 48, "customers") == pytest.approx(150 / 310)


def test_simulation_end_to_end_and_optimised_beats_smith():
    incs, _ = load_incidents(cfg, "CRISE_050")
    teams = load_teams(cfg)
    smith = Simulator(cfg, incs, teams, BASELINES["smith"]()).run()
    opt = Simulator(cfg, incs, teams, OptimisedPolicy(30)).run()
    assert smith.kpis["unrestored"] == 0 and opt.kpis["unrestored"] == 0
    assert opt.kpis["customer_hours"] < smith.kpis["customer_hours"]
