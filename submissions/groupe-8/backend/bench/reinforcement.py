"""Reinforcement what-if: extra teams (other regions / FIRE) needed to meet the service target.

Run:  python bench/reinforcement.py --crisis CRISE_082 --teams-fraction 0.5
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import load_incidents, load_sites, load_teams  # noqa: E402
from dispatch.sim.whatif import teams_needed  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crisis", required=True)
    ap.add_argument("--teams-fraction", type=float, default=1.0)
    args = ap.parse_args()
    cfg = load_config(); sites = load_sites(cfg)
    teams = load_teams(cfg, sites)
    if args.teams_fraction < 1:
        step = round(1 / args.teams_fraction)
        teams = [t for k, t in enumerate(teams) if k % step == 0]
    incs, _ = load_incidents(cfg, args.crisis)
    r = teams_needed(cfg, incs, teams, sites)
    st = cfg.service_target
    print(f"{args.crisis}, {len(teams)} teams: {100 * r['share_before']:.1f}% {st.basis} fixed by H+{st.deadline_h} "
          f"(target {100 * st.share:.0f}%)")
    if r["extra_teams"]:
        print(f"-> request +{r['extra_teams']} teams from other regions: {r['by_site']} "
              f"=> {100 * r['share_after']:.1f}% (target met: {r['target_met']})")
    else:
        print("-> target met, no reinforcement needed")


if __name__ == "__main__":
    main()
