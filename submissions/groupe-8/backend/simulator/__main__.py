"""Run the field simulator against a running backend.

  python -m simulator --crisis CRISE_027                 real time (x1): alerts come as they did, starting now
  python -m simulator --crisis CRISE_027 --speed 60      demo: 1 hour of crisis per minute
  python -m simulator --crisis CRISE_051 --speed 120 --duration-noise 0.3   heavier crisis, uncertain repair times
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dispatch.config import load_config
from dispatch.data.loaders import load_incidents  # the only code that reads the CSVs
from simulator.field import Alert, Api, Field


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)                       # the log is followed while it runs
    ap = argparse.ArgumentParser(description="Simulated field for the live mode (alerts + team reports)")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--crisis", default="CRISE_027", help="past crisis to replay from now")
    ap.add_argument("--speed", type=float, default=1.0, help="clock speed: 1 = real time, 60 = 1 h per minute")
    ap.add_argument("--travel-noise", type=float, default=0.0, help="lognormal sigma on travel times")
    ap.add_argument("--duration-noise", type=float, default=0.0, help="lognormal sigma on repair times")
    ap.add_argument("--no-reset", action="store_true", help="join the crisis already open instead of opening one")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    incidents, _ = load_incidents(load_config(), args.crisis)
    alerts = [Alert(i.reported_at, i.id, i.poste_id, i.est_duration, i.cause) for i in incidents]
    api = Api(args.api)
    if not args.no_reset:
        c = api.call("/live/reset", {"speed": args.speed, "label": f"Rejeu en direct de la crise {args.crisis}"})
        print(f"Crise ouverte à {c['start']} (vitesse x{args.speed:g}) : {len(alerts)} alertes sur "
              f"{alerts[-1].at_h:.1f} h de crise.")
    Field(api, alerts, args.travel_noise, args.duration_noise, args.seed).run()


if __name__ == "__main__":
    main()
