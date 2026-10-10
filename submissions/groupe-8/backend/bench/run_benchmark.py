"""Benchmark: every policy on every crisis through the same simulator, same score (official N x T mode).

Run:  python bench/run_benchmark.py --policies fifo nearest max_customers smith optimised --crises all --budget-ms 50
Output: a summary table + bench/results/<timestamp>.csv (one row per crisis x policy).
"""
import argparse
import csv
import statistics as S
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import list_crises, load_incidents, load_teams  # noqa: E402
from dispatch.engine.baselines import BASELINES  # noqa: E402
from dispatch.engine.planner import OptimisedPolicy  # noqa: E402
from dispatch.sim.simulator import Simulator  # noqa: E402


def make_policy(name, budget_ms):
    return OptimisedPolicy(budget_ms) if name == "optimised" else BASELINES[name]()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policies", nargs="+", default=["fifo", "nearest", "max_customers", "smith", "optimised"])
    ap.add_argument("--crises", nargs="+", default=["all"], help="'all', 'every:N', or crisis ids")
    ap.add_argument("--budget-ms", type=int, default=50, help="local search budget per plan for 'optimised'")
    ap.add_argument("--teams-fraction", type=float, default=1.0, help="stress test: keep this share of teams")
    args = ap.parse_args()

    cfg = load_config()
    crises = list_crises(cfg)
    if args.crises[0].startswith("every:"):
        crises = crises[::int(args.crises[0].split(":")[1])]
    elif args.crises != ["all"]:
        crises = args.crises
    teams = load_teams(cfg)
    if args.teams_fraction < 1:
        step = round(1 / args.teams_fraction)
        teams = [t for k, t in enumerate(teams) if k % step == 0]

    rows, t_start = [], time.perf_counter()
    for c in crises:
        incs, _ = load_incidents(cfg, c)
        for name in args.policies:
            t0 = time.perf_counter()
            k = Simulator(cfg, incs, teams, make_policy(name, args.budget_ms)).run().kpis
            rows.append({"crisis": c, "policy": name, "seconds": round(time.perf_counter() - t0, 2), **k})
        print(f"{c} done ({time.perf_counter() - t_start:.0f}s)", flush=True)

    out = ROOT / "bench" / "results"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    by = {p: {r["crisis"]: r for r in rows if r["policy"] == p} for p in args.policies}
    target = cfg.service_target
    print(f"\n{len(crises)} crises, {len(teams)} teams. Official indicator: customer-hours (lower is better)")
    print(f"{'policy':14s} {'mean N.T':>12s} {'H+48 share':>11s} {'crises >= target':>17s} {'s/crisis':>9s}")
    for p in args.policies:
        v = by[p].values()
        ok = sum(r["share_by_deadline_" + target.basis] >= target.share for r in v)
        print(f"{p:14s} {S.mean(r['customer_hours'] for r in v):12,.0f} "
              f"{100 * S.mean(r['share_by_deadline_' + target.basis] for r in v):10.1f}% {ok:>10d}/{len(crises):<6d}"
              f"{S.mean(r['seconds'] for r in v):9.2f}")
    if "optimised" in args.policies:
        print("\noptimised vs each policy (paired, mean gain, range, crises where optimised is better):")
        for p in args.policies:
            if p == "optimised":
                continue
            g = [(by[p][c]["customer_hours"] - by["optimised"][c]["customer_hours"]) / by[p][c]["customer_hours"]
                 for c in crises]
            print(f"  vs {p:14s} {-100 * S.mean(g):+6.1f}%  ({-100 * max(g):+.1f}% .. {-100 * min(g):+.1f}%)  "
                  f"better on {sum(x > 0 for x in g)}/{len(g)}")
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
