"""Events flowing on the bus. The engine only ever learns about the world through these."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    INCIDENT_REPORTED = "incident_reported"
    INCIDENT_UPDATED = "incident_updated"        # e.g. revised duration estimate
    TEAM_ON_SITE = "team_on_site"
    REPAIR_DONE = "repair_done"                  # reveals the ACTUAL duration
    TEAM_DELAYED = "team_delayed"
    TEAM_UNAVAILABLE = "team_unavailable"
    SHIFT_END = "shift_end"
    OPERATOR_DECISION = "operator_decision"      # accept / modify / reject (+ reason)


@dataclass(order=True)
class Event:
    time: float                                  # hours since t0
    type: EventType = field(compare=False)
    payload: dict = field(default_factory=dict, compare=False)
