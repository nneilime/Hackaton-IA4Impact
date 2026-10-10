"""Fixed shift rotation (stage 1): work_h on / rest_h off, starting at each team's shift_start."""
from __future__ import annotations

import math

EPS = 1e-9


def window(shift_start: float, t: float, work_h: float, rest_h: float) -> tuple[float, float]:
    """The work window [s, e] that contains t, or the next one if t falls in a rest period."""
    if t < shift_start:
        return shift_start, shift_start + work_h
    cycle = work_h + rest_h
    s = shift_start + math.floor((t - shift_start) / cycle + EPS) * cycle
    if t < s + work_h - EPS:
        return s, s + work_h
    return s + cycle, s + cycle + work_h


def is_on_duty(shift_start: float, t: float, work_h: float, rest_h: float) -> bool:
    s, e = window(shift_start, t, work_h, rest_h)
    return s - EPS <= t < e - EPS


def coverage(shift_starts: list[float], work_h: float, rest_h: float, horizon_h: float = 72.0,
             step_h: float = 0.25) -> tuple[float, float]:
    """Lowest share of teams on duty over [0, horizon_h], and the first time it happens.
    Used to forbid rosters where (almost) every team rests at the same time."""
    n = len(shift_starts) or 1
    worst, at = 1.0, 0.0
    t = 0.0
    while t <= horizon_h + EPS:
        share = sum(is_on_duty(s0, t, work_h, rest_h) for s0 in shift_starts) / n
        if share < worst - EPS:
            worst, at = share, t
        t += step_h
    return worst, at
