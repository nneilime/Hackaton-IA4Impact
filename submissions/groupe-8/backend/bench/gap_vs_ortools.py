"""How far is our engine from a reference solver? Same decision (a crisis frozen at H+t, all known incidents
waiting), solved by our engine with several time budgets and by OR-Tools (guided local search, long time limit).
Both plans are scored by OUR decoder, so the comparison is exact.

Run:  python bench/gap_vs_ortools.py --crises CRISE_051 CRISE_046 CRISE_066 CRISE_013 --at 4 --ortools-s 60
"""
import argparse
import statistics as S
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config  # noqa: E402
from dispatch.engine.baselines import SmithPolicy  # noqa: E402
from dispatch.engine.context import build_context  # noqa: E402
from dispatch.engine.evaluate import routes_from_plan  # noqa: E402
from dispatch.engine.planner import plan  # noqa: E402
from dispatch.engine.reference_ortools import solve  # noqa: E402
from dispatch.session import LiveSession  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crises", nargs="+", default=["CRISE_051", "CRISE_046", "CRISE_066", "CRISE_013"])
    ap.add_argument("--at", type=float, default=4.0, help="freeze the crisis at H0 + this many hours")
    ap.add_argument("--budgets", nargs="+", type=int, default=[300, 1000, 3000, 10000])
    ap.add_argument("--ortools-s", type=int, default=60)
    args = ap.parse_args()
    cfg = load_config()
    gaps = {b: [] for b in args.budgets}
    for c in args.crises:
        s = LiveSession.start(cfg, c, budget_ms=20)
        s.advance(args.at, auto_accept=True)
        st = s.state(previous=None)
        st.previous_plan = None
        smith = SmithPolicy().plan(st, cfg)
        t0 = time.perf_counter()
        ort = solve(st, cfg, args.ortools_s)
        t_ort = time.perf_counter() - t0
        ctx = build_context(st, cfg)
        ort_warm = solve(st, cfg, args.ortools_s, initial_routes=routes_from_plan(ctx, plan(st, cfg, 3000)))
        ref = min(ort.score.total, ort_warm.score.total)
        print(f"{c}: {len(st.pending)} waiting, {len(st.teams)} teams | Smith {smith.score.total:,.0f} | "
              f"OR-Tools {args.ortools_s}s {ort.score.total:,.0f} | OR-Tools from our 3s plan {ort_warm.score.total:,.0f}"
              f" ({t_ort:.0f}s)", flush=True)
        for b in args.budgets:
            ours = plan(st, cfg, b).score.total
            gaps[b].append(100 * (ours - ref) / ref)
            print(f"    ours {b:>6} ms: {ours:,.0f}  gap to OR-Tools {100 * (ours - ref) / ref:+6.2f}%", flush=True)
    print("\nmean gap to the best OR-Tools solution:")
    for b in args.budgets:
        print(f"  ours {b:>6} ms: {S.mean(gaps[b]):+6.2f}%  (worst {max(gaps[b]):+.2f}%)")


if __name__ == "__main__":
    main()
