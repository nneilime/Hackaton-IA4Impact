"""Loop 1 (within the crisis): correct duration / travel estimates from observed actuals.

Shrinkage estimate per (zone, cause): p̂ = (n · observed_mean + k · prior) / (n + k).
"""
from __future__ import annotations


class DurationCalibrator:
    def observe(self, incident_id: str, estimated_h: float, actual_h: float, context: dict) -> None:
        raise NotImplementedError

    def corrected_estimate(self, estimated_h: float, context: dict) -> float:
        raise NotImplementedError
