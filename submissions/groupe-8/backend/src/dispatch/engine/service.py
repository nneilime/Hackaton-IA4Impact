"""Service target check (NOT part of the objective): share of incidents / customers restored by the deadline."""
from __future__ import annotations

from dispatch.engine.types import Incident


def service_share(restored_at: dict[str, float], incidents: list[Incident], deadline_h: float,
                  basis: str = "incidents") -> float:
    """Share restored by `deadline_h` (hours since H0). Unrestored incidents count as late."""
    if not incidents:
        return 1.0
    if basis == "customers":
        total = sum(i.customers for i in incidents)
        ok = sum(i.customers for i in incidents if restored_at.get(i.id, float("inf")) <= deadline_h + 1e-9)
        return ok / total
    return sum(restored_at.get(i.id, float("inf")) <= deadline_h + 1e-9 for i in incidents) / len(incidents)


def target_met(share: float, cfg) -> bool:
    return share >= cfg.service_target.share - 1e-12
