"""Periodic expert review of refusals: candidates -> replay test -> (expert) activation in the registry.

  python bench/review_refusals.py --simulate CRISE_051 CRISE_046 CRISE_013 CRISE_024   # demo: synthetic refusals
  python bench/review_refusals.py                     # list candidates from the knowledge base + replay test
  python bench/review_refusals.py --activate 0 --approved-by "expert exploitation"   # add candidate #0
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import list_crises  # noqa: E402
from dispatch.learning import registry, review, simulated  # noqa: E402
from dispatch.learning.memory import DecisionLog  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", nargs="*", help="replay these crises with the simulated manager first")
    ap.add_argument("--backtest-every", type=int, default=10, help="replay every N-th crisis for the test")
    ap.add_argument("--activate", type=int, help="index of the candidate to activate")
    ap.add_argument("--approved-by", default=None)
    args = ap.parse_args()

    cfg = load_config()
    log = DecisionLog(ROOT / cfg.learning.db_path)
    if args.simulate:
        print("simulated manager:", simulated.run(cfg, args.simulate, log))
    print("knowledge base:", log.stats())
    cands = review.candidates(log, cfg.learning.review_min_refusals)
    if not cands:
        print("no candidate rule (not enough repeated refusals)")
        return
    crises = list_crises(cfg)[::args.backtest_every]
    for n, c in enumerate(cands):
        bt = review.backtest(c, cfg, crises)
        print(f"\n[{n}] {c['description']}" + ("  ⚠ ALERTE SÉCURITÉ" if c["safety_alert"] else ""))
        print(f"    preuves : {json.dumps(c['evidence'], ensure_ascii=False)}")
        print(f"    test de rejeu ({bt['crises']} crises) : coût {bt['cost_pct']:+.2f}% clients·h, "
              f"objectif 90 % à H+48 tenu dans {bt['target_still_met_in']}/{bt['crises']} crises")
    if args.activate is not None:
        if not args.approved_by:
            sys.exit("--approved-by is required (role of the expert who validates)")
        entry = registry.activate(cands[args.activate], args.approved_by)
        print(f"\nactivated {entry['id']} (registry version {entry['registry_version']})")


if __name__ == "__main__":
    main()
