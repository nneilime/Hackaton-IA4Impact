"""Calibrate the offline (simulated) travel model on real road times from OSRM.

Fetches a sample of real trips (sites -> substations with incidents, and incident -> incident within a crisis) from
OSRM in a few batched `table` requests (cached in data/cache/osrm.json), then fits the simulated model's speeds,
detours and overhead by random search. Prints the error of each model and the fitted values for config/default.yaml.

Run:  python bench/calibrate_travel.py --sites-x 120 --chain 40 --trials 4000
"""
import argparse
import copy
import random
import statistics as S
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.data.loaders import list_crises, load_incidents, load_sites  # noqa: E402
from dispatch.data.travel import OsrmCache, haversine_km, travel_hours  # noqa: E402


def errors(cfg, pairs, real):
    a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
    pred = travel_hours(a[:, 0], a[:, 1], b[:, 0], b[:, 1], cfg) * 60
    err = pred - real
    return float(np.mean(np.abs(err))), float(np.mean(np.abs(err) / real) * 100), float(np.mean(err))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites-x", type=int, default=120, help="random incident substations per site")
    ap.add_argument("--chain", type=int, default=40, help="incident -> incident sample size (one crisis)")
    ap.add_argument("--trials", type=int, default=4000)
    args = ap.parse_args()
    rng = random.Random(0)
    cfg = load_config()
    sites = load_sites(cfg)
    incs = [i for c in list_crises(cfg) for i in load_incidents(cfg, c)[0]]
    dest = rng.sample([(i.lat, i.lon) for i in incs], args.sites_x)
    chain = rng.sample([(i.lat, i.lon) for i in load_incidents(cfg, "CRISE_051")[0]], args.chain)
    osrm = OsrmCache.get(load_config(travel={"mode": "osrm"}))
    so = np.array([(s.lat, s.lon) for s in sites]); de = np.array(dest); ch = np.array(chain)
    m1 = osrm.matrix(so, de, fallback=np.full((len(so), len(de)), np.nan))
    m2 = osrm.matrix(ch, ch, fallback=np.full((len(ch), len(ch)), np.nan))
    if osrm.offline:
        sys.exit("OSRM unreachable: cannot calibrate (the cached pairs, if any, are kept)")
    pairs, real = [], []
    for (pts_a, pts_b, m) in ((so, de, m1), (ch, ch, m2)):
        for i, a in enumerate(pts_a):
            for j, b in enumerate(pts_b):
                if not np.isnan(m[i, j]) and haversine_km(*a, *b) > 1:
                    pairs.append((tuple(a), tuple(b))); real.append(60 * m[i, j])
    real = np.array(real)
    print(f"{len(pairs)} real trips (median {np.median(real):.0f} min, P90 {np.percentile(real, 90):.0f} min)")
    for name, c in (("straight x1.3 @50", load_config(travel={"mode": "straight"})), ("simulated (current)", cfg)):
        mae, mape, bias = errors(c, pairs, real)
        print(f"{name:22s} MAE {mae:5.1f} min   MAPE {mape:5.1f}%   bias {bias:+5.1f} min")

    best = (errors(cfg, pairs, real)[0], cfg)
    for _ in range(args.trials):
        c = copy.deepcopy(cfg); t = c.travel
        t.overhead_min = rng.uniform(0, 15); t.local_km = rng.uniform(3, 20)
        for z, (lo, mo) in {"urban": ((20, 60), (60, 100)), "mountain": ((25, 65), (45, 90)),
                            "plain": ((35, 75), (65, 100))}.items():
            zz = getattr(t.zones, z)
            zz.local_kmh = rng.uniform(*lo); zz.main_kmh = rng.uniform(*mo); zz.detour = rng.uniform(1.05, 1.5)
        e = errors(c, pairs, real)[0]
        if e < best[0]:
            best = (e, c)
    mae, mape, bias = errors(best[1], pairs, real)
    print(f"{'simulated (fitted)':22s} MAE {mae:5.1f} min   MAPE {mape:5.1f}%   bias {bias:+5.1f} min")
    t = best[1].travel
    print("\nfitted values for config/default.yaml (travel):")
    print(f"  overhead_min: {t.overhead_min:.0f}\n  local_km: {t.local_km:.0f}")
    for z in ("urban", "mountain", "plain"):
        zz = getattr(t.zones, z)
        print(f"  {z}: local_kmh {zz.local_kmh:.0f}, main_kmh {zz.main_kmh:.0f}, detour {zz.detour:.2f}")


if __name__ == "__main__":
    main()
