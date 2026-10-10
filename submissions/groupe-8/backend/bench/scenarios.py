"""Robustness scenarios: every scenario x (Smith rule, optimised engine), same simulator, with the 48 h check
and the reinforcement needed when the target is missed.

Run:  python bench/scenarios.py                       (all scenarios)
      python bench/scenarios.py --only flood two_crises --budget-ms 30
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.data.loaders import load_sites  # noqa: E402
from dispatch.engine.baselines import SmithPolicy  # noqa: E402
from dispatch.engine.planner import OptimisedPolicy  # noqa: E402
from dispatch.sim.scenarios import CATALOGUE  # noqa: E402
from dispatch.sim.simulator import Simulator  # noqa: E402
from dispatch.sim.whatif import teams_needed  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=list(CATALOGUE))
    ap.add_argument("--budget-ms", type=int, default=30)
    ap.add_argument("--reinforcement", action="store_true", help="compute extra teams when the target is missed")
    args = ap.parse_args()
    print(f"{'scenario':12s} {'policy':10s} {'customer-hours':>15s} {'H+48':>7s} {'target':>7s} {'end':>7s}  description")
    for name in args.only:
        cfg, incs, teams, mods, desc = CATALOGUE[name]()
        res = {}
        for pol_name, pol in (("smith", SmithPolicy()), ("optimised", OptimisedPolicy(args.budget_ms))):
            t0 = time.perf_counter()
            k = Simulator(cfg, incs, teams, pol, modifiers=mods).run().kpis
            share = k[f"share_by_deadline_{cfg.service_target.basis}"]
            res[pol_name] = k
            print(f"{name:12s} {pol_name:10s} {k['customer_hours']:15,.0f} {100 * share:6.1f}% "
                  f"{'OK' if share >= cfg.service_target.share else 'MISSED':>7s} {k['end_h']:6.1f}h  {desc} "
                  f"({time.perf_counter() - t0:.1f}s)", flush=True)
        gain = 1 - res["optimised"]["customer_hours"] / res["smith"]["customer_hours"]
        print(f"{'':12s} {'gain':10s} {100 * gain:14.1f}%")
        k = res["optimised"]
        if args.reinforcement and k[f"share_by_deadline_{cfg.service_target.basis}"] < cfg.service_target.share and not mods:
            r = teams_needed(cfg, incs, teams, load_sites(cfg))
            print(f"{'':12s} -> reinforcement: +{r['extra_teams']} teams {r['by_site']} => {100 * r['share_after']:.1f}%")


if __name__ == "__main__":
    main()
