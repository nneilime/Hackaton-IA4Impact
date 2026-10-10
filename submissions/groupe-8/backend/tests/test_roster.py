"""Shift roster (stage 1): groups A / B / C (relief) and the minimum on-duty coverage."""
import pytest

from dispatch.config import load_config
from dispatch.data.loaders import load_sites, load_teams
from dispatch.engine.shifts import coverage, is_on_duty


def test_relief_group_keeps_teams_on_duty():
    cfg = load_config()
    sites = load_sites(cfg)
    cap = {s.id: s.n_teams for s in sites}
    zero = {s: 0 for s in cap}
    # two groups 2 h apart: everybody rests between H+14 and H+24
    ab = load_teams(cfg, sites, roster={s: cap[s] // 2 for s in cap}, b_offset_h=2, relief=zero, c_offset_h=12)
    worst, at = coverage([t.shift_start for t in ab], 12, 12)
    assert worst == 0 and 14 <= at < 24
    # a relief group at H+12 closes the gap
    nc = {s: cap[s] // 3 for s in cap}
    abc = load_teams(cfg, sites, roster={s: (cap[s] - nc[s]) // 2 for s in cap}, b_offset_h=2, relief=nc, c_offset_h=12)
    assert len(abc) == sum(cap.values())
    assert sum(t.shift_start == 12 for t in abc) == sum(nc.values())
    worst, _ = coverage([t.shift_start for t in abc], 12, 12)
    assert worst > 0.15
    # every team works 12 h in each 24 h (well-being rule unchanged)
    t0 = abc[0].shift_start
    assert sum(is_on_duty(t0, h / 4, 12, 12) for h in range(96)) == 48


def test_roster_larger_than_site_is_rejected():
    cfg = load_config()
    sites = load_sites(cfg)
    s = sites[0]
    with pytest.raises(ValueError):
        load_teams(cfg, sites, roster={s.id: s.n_teams}, relief={s.id: 1})


def test_configured_roster_has_no_empty_window():
    cfg = load_config()
    teams = load_teams(cfg)
    worst, at = coverage([t.shift_start for t in teams], cfg.roster.work_h, cfg.roster.rest_h)
    assert worst >= getattr(cfg.roster, "min_on_duty", 0.2) - 1e-9, f"only {worst:.0%} of teams on duty at H+{at:g}"
