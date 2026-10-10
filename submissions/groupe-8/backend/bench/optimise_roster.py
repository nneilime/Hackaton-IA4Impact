"""Stage 1: optimise the shift schedule (fixed once at initialisation) on historical crises.

Rotation work_h on / rest_h off (config). Three groups per site: A starts at H0, B at H0 + b (a few hours later, to
stagger the ends of shifts), C - the relief - at H0 + c (about 12 h later). Constraint: at every moment at least
`--min-coverage` of all teams are on duty (no "everyone asleep" window). Search: offsets b x (number of B, number of C
teams per site), coordinate descent with +-1 moves, mean customer-hours on TRAIN crises (odd ids), reported on TEST
crises (even ids, never used for tuning). The Smith rule is the dispatcher during the search (the full engine is too
slow for this loop).

Run:  python bench/optimise_roster.py --offsets 2 --train-every 2 --min-coverage 0.2
Paste the printed roster block into config/default.yaml.
"""
import argparse
import math
import statistics as S
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import list_crises, load_incidents, load_sites, load_teams  # noqa: E402
from dispatch.engine.baselines import SmithPolicy  # noqa: E402
from dispatch.engine.shifts import coverage  # noqa: E402
from dispatch.sim.simulator import Simulator  # noqa: E402


def make_teams(cfg, sites, nb, nc, b, c):
    return load_teams(cfg, sites, roster=nb, b_offset_h=b, relief=nc, c_offset_h=c)


def cover(cfg, sites, nb, nc, b, c) -> float:
    teams = make_teams(cfg, sites, nb, nc, b, c)
    return coverage([t.shift_start for t in teams], cfg.roster.work_h, cfg.roster.rest_h)[0]


def mean_nt(cfg, crises, data, sites, nb, nc, b, c):
    teams = make_teams(cfg, sites, nb, nc, b, c)
    return S.mean(Simulator(cfg, data[k], teams, SmithPolicy()).run().kpis["customer_hours"] for k in crises)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offsets", nargs="+", type=float, default=[2])
    ap.add_argument("--relief-offset", type=float, default=12.0)
    ap.add_argument("--min-coverage", type=float, default=0.2)
    ap.add_argument("--train-every", type=int, default=2, help="use every N-th train crisis (speed)")
    ap.add_argument("--passes", type=int, default=2)
    args = ap.parse_args()

    cfg = load_config(); sites = load_sites(cfg); crises = list_crises(cfg)
    data = {k: load_incidents(cfg, k)[0] for k in crises}
    train = [k for k in crises if int(k[-3:]) % 2 == 1][::args.train_every]
    test = [k for k in crises if int(k[-3:]) % 2 == 0]
    cap = {s.id: s.n_teams for s in sites}
    c = args.relief_offset
    best = None
    for b in args.offsets:
        # feasible start: a quarter of each site in relief, half of the rest in B
        nc = {s: math.ceil(cap[s] / 4) if cap[s] > 1 else 0 for s in cap}
        nb = {s: (cap[s] - nc[s]) // 2 for s in cap}
        assert cover(cfg, sites, nb, nc, b, c) >= args.min_coverage, "start roster below the coverage floor"
        cur = mean_nt(cfg, train, data, sites, nb, nc, b, c)
        print(f"b={b:g}h c={c:g}h start: train mean {cur:,.0f}, coverage {cover(cfg, sites, nb, nc, b, c):.0%}", flush=True)
        for p in range(args.passes):
            improved = False
            for s in cap:
                for grp in ("B", "C"):
                    for dv in (-1, 1):
                        tb, tc = dict(nb), dict(nc)
                        (tb if grp == "B" else tc)[s] += dv
                        if tb[s] < 0 or tc[s] < 0 or tb[s] + tc[s] > cap[s]:
                            continue
                        if cover(cfg, sites, tb, tc, b, c) < args.min_coverage:
                            continue
                        val = mean_nt(cfg, train, data, sites, tb, tc, b, c)
                        if val < cur - 1e-6:
                            cur, nb, nc, improved = val, tb, tc, True
            print(f"  pass {p + 1}: train mean {cur:,.0f}  B={sum(nb.values())} C={sum(nc.values())} "
                  f"coverage {cover(cfg, sites, nb, nc, b, c):.0%}", flush=True)
            if not improved:
                break
        if best is None or cur < best[0]:
            best = (cur, b, nb, nc)
    _, b, nb, nc = best

    old_nb = dict(vars(cfg.roster.b_per_site)); old_b = cfg.roster.b_offset_h
    zero = {s: 0 for s in cap}
    res = {
        "everyone at H0": (zero, zero, 0.0),
        "previous roster (A/B, no relief)": (old_nb, zero, old_b),
        "new roster (A/B/C relief)": (nb, nc, b),
    }
    print(f"\nTEST ({len(test)} crises never used for tuning), Smith dispatcher:")
    base = None
    for name, (xb, xc, xo) in res.items():
        m = mean_nt(cfg, test, data, sites, xb, xc, xo, c)
        base = base or m
        print(f"  {name:34s} mean {m:,.0f} customer-h ({100 * (m / base - 1):+.1f}% vs everyone at H0), "
              f"min share on duty {cover(cfg, sites, xb, xc, xo, c):.0%}")
    print("\nroster:")
    print(f"  b_offset_h: {b:g}\n  b_per_site: {nb}\n  c_offset_h: {c:g}\n  c_per_site: {nc}")


if __name__ == "__main__":
    main()
