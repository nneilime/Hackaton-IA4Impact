"""Periodic expert review of refusals (monthly, or every N refusals).

1. Expert system (deterministic rules + statistics): group refusals by (site -> commune) and (site -> departement);
   a group with >= min_refusals refusals becomes a CANDIDATE constraint. Safety reasons raise an alert at once.
2. Replay test: run historical crises with and without the candidate -> its price in customer-hours and on the
   90 %-at-48 h target, plus how many logged refusals it would have avoided.
3. Human experts decide: activate (-> learning/registry.py, new registry version), or reject.
Nothing is ever added automatically.
"""
from __future__ import annotations

import statistics as S
from collections import Counter, defaultdict

from dispatch.copilot.translate import REASONS
from dispatch.data.loaders import load_incidents, load_teams
from dispatch.engine.baselines import SmithPolicy
from dispatch.engine.modifiers import from_dict
from dispatch.engine.planner import OptimisedPolicy
from dispatch.learning.memory import DecisionLog
from dispatch.sim.simulator import Simulator


def candidates(log: DecisionLog, min_refusals: int = 3, site_names: dict | None = None) -> list[dict]:
    """site_names (site id -> commune) only changes the wording of the description."""
    rej = log.rejections()
    names = site_names or {}
    out = []
    for level, key_of in (("commune", lambda r: r["commune"]), ("departement", lambda r: r["departement"])):
        groups = defaultdict(list)
        for r in rej:
            groups[(r["site"], key_of(r))].append(r)
        for (site, zone), rows in groups.items():
            if len(rows) < min_refusals:
                continue
            if level == "departement" and len({r["commune"] for r in rows}) < 2:
                continue                                   # already covered by the commune-level candidate
            codes = Counter(r["reason_code"] or "autre" for r in rows)
            main = codes.most_common(1)[0][0]
            costs = [r["cost_delta"] for r in rows if r["cost_delta"] is not None]
            sens = sum(r["sensitive"] for r in rows) / len(rows)
            site_name = names.get(site, site)
            observed = (f"{len(rows)} refus du responsable quand le moteur envoie une équipe de {site_name} vers "
                        f"{zone} (motif le plus cité : {REASONS.get(main, main).lower()}).")
            if main in ("priorite", "securite") and sens >= 0.5:
                modifier = {"type": "weight", "name": "beta_sensitive", "value": 3.0}
                variable, before, after = "Poids des clients sensibles", "×1", "×4"
                proposal = "Compter chaque client sensible 4 fois dans le calcul, pour qu'ils passent plus tôt."
            else:
                factor = 1.5 if main == "acces" else 1.3
                modifier = {"type": "travel_factor", "zone": zone, "factor": factor}
                variable, before, after = f"Temps de trajet estimé vers {zone}", "×1", f"×{factor:g}".replace(".", ",")
                proposal = (f"Compter les trajets vers {zone} {round((factor - 1) * 100)} % plus longs dans le calcul : "
                            f"le moteur y enverra plutôt des équipes proches, comme le font les responsables.")
            out.append({
                "key": f"{site}->{zone}",
                "description": f"{variable} : {before} → {after} ({zone}).",
                "observed": observed, "proposal": proposal,
                "variable": variable, "before": before, "after": after,
                "modifier": modifier,
                "evidence": {"refusals": len(rows), "crises": len({r['crisis'] for r in rows}),
                             "main_reason": main, "reason_counts": dict(codes),
                             "examples": [r["reason_text"] for r in rows if r["reason_text"]][:3],
                             "mean_override_cost": round(S.mean(costs), 1) if costs else None,
                             "simulated_share": sum(r["simulated"] for r in rows) / len(rows)},
                "safety_alert": codes.get("securite", 0) > 0,
                "level": level,
            })
    return sorted(out, key=lambda c: -c["evidence"]["refusals"])


def backtest(candidate: dict, cfg, crises: list[str], budget_ms: int = 0) -> dict:
    """Replay crises with and without the candidate. budget_ms=0 uses the Smith rule (fast)."""
    teams = load_teams(cfg)
    mod = from_dict(candidate["modifier"])
    make = (lambda: OptimisedPolicy(budget_ms)) if budget_ms else SmithPolicy
    basis = cfg.service_target.basis
    base, alt, sb, sa = [], [], [], []
    for c in crises:
        incs, _ = load_incidents(cfg, c)
        r0 = Simulator(cfg, incs, teams, make()).run().kpis
        r1 = Simulator(cfg, incs, teams, make(), modifiers=[mod]).run().kpis
        base.append(r0["customer_hours"]); alt.append(r1["customer_hours"])
        sb.append(r0[f"share_by_deadline_{basis}"]); sa.append(r1[f"share_by_deadline_{basis}"])
    return {"crises": len(crises), "customer_hours_without": S.mean(base), "customer_hours_with": S.mean(alt),
            "cost_pct": 100 * (S.mean(alt) / S.mean(base) - 1),
            "share_by_deadline_without": S.mean(sb), "share_by_deadline_with": S.mean(sa),
            "target_still_met_in": sum(x >= cfg.service_target.share for x in sa)}
