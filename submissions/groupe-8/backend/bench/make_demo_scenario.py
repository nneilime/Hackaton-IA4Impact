"""Demo scenario: a storm that starts small and gets worse, until there are more outages than the teams can handle.

Built from the real data (real substations, the dataset's repair durations and causes), same CSV format as the 100
historical crises, written to data/scenarios/scenarios.csv as crisis CRISE_DEMO. Seeded: always the same scenario.

  - arrivals per half hour ramp up by phase (1 -> 3 -> 8 -> 9 -> 11 ...), then calm down;
  - the storm crosses the territory from west to east: Gers first, then Haute-Garonne, then Ariège;
  - calibrated so that the 90 % within 48 h target is met at the start and missed at the end (the alert shows up
    during the replay). Check with --check.

Run:  python bench/make_demo_scenario.py [--check]
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import load_postes  # noqa: E402

CRISIS = "CRISE_DEMO"
START = datetime(2017, 1, 15, 18, 0)
# (from hour, to hour, outages per half hour, weight of each département: Gers 32, Haute-Garonne 31, Ariège 09)
PHASES = [
    (0, 2, 1, {"32": 0.8, "31": 0.2, "09": 0.0}),     # first gusts in the west: one outage at a time
    (2, 4, 3, {"32": 0.7, "31": 0.3, "09": 0.0}),
    (4, 7, 8, {"32": 0.5, "31": 0.5, "09": 0.0}),     # the storm reaches Toulouse
    (7, 11, 9, {"32": 0.2, "31": 0.6, "09": 0.2}),
    (11, 16, 11, {"32": 0.1, "31": 0.5, "09": 0.4}),  # peak, moving into the Pyrenees
    (16, 20, 6, {"32": 0.0, "31": 0.4, "09": 0.6}),
    (20, 24, 3, {"32": 0.0, "31": 0.4, "09": 0.6}),   # calming down
]


def build(seed: int = 7) -> pd.DataFrame:
    cfg = load_config()
    rng = np.random.default_rng(seed)
    postes = load_postes(cfg).reset_index()
    postes["dep"] = postes["code_departement"].astype(str).str.zfill(2).str[-2:]
    hist = pd.read_csv(ROOT / cfg.data.raw_dir / cfg.data.incidents, sep=";", encoding="utf-8-sig")
    durations = hist["dureeDepannage"].value_counts(normalize=True)
    causes = hist["causeInterruption"].value_counts(normalize=True)
    used: set[str] = set()
    rows = []
    n = 0
    for h0, h1, per_half_hour, weights in PHASES:
        for slot in range((h1 - h0) * 2):
            k = rng.poisson(per_half_hour) if per_half_hour > 1 else 1
            for _ in range(k):
                dep = rng.choice(list(weights), p=np.array(list(weights.values())) / sum(weights.values()))
                pool = postes[(postes["dep"] == dep) & ~postes["id_poste"].isin(used)]
                p = pool.iloc[rng.integers(len(pool))]
                used.add(p["id_poste"])
                minute = rng.integers(0, 30)
                ts = START + timedelta(hours=h0, minutes=slot * 30 + int(minute))
                n += 1
                rows.append({"numero_crise": CRISIS, "id_incident": f"DEMO_{n:04d}", "id_poste": p["id_poste"],
                             "causeInterruption": rng.choice(causes.index, p=causes.values),
                             "dateHeureIncident": ts.strftime("%d/%m/%Y %H:%M"),
                             "dureeDepannage": rng.choice(durations.index, p=durations.values)})
    df = pd.DataFrame(rows).sort_values("dateHeureIncident", key=lambda s: pd.to_datetime(s, format="%d/%m/%Y %H:%M"))
    return df


def check() -> None:
    """90 % within 48 h, with the engine's dispatcher rule and the configured teams."""
    from dispatch.data.loaders import load_incidents, load_teams
    from dispatch.engine.baselines import SmithPolicy
    from dispatch.sim.simulator import Simulator
    cfg = load_config()
    incs, _ = load_incidents(cfg, CRISIS)
    k = Simulator(cfg, incs, load_teams(cfg), SmithPolicy()).run().kpis
    print(f"{len(incs)} outages, {sum(i.customers for i in incs)} customers; incidents repaired within 48 h: "
          f"{k['share_by_deadline_incidents']:.0%} (target 90 %)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = ROOT / "data" / "scenarios" / "scenarios.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = build(args.seed)
    df.to_csv(out, sep=";", index=False, encoding="utf-8-sig")
    per_hour = pd.to_datetime(df["dateHeureIncident"], format="%d/%m/%Y %H:%M").dt.floor("h").value_counts().sort_index()
    print(f"{CRISIS}: {len(df)} outages written to {out.relative_to(ROOT)}; per hour: {per_hour.tolist()}")
    if args.check:
        check()


if __name__ == "__main__":
    main()
