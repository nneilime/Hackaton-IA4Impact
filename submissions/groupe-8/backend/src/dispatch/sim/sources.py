"""Interchangeable event sources. The engine never reads CSVs; a CSV is just one source."""
from __future__ import annotations

from collections.abc import Iterator

from dispatch.data.loaders import load_incidents
from dispatch.sim.events import Event, EventType


class CsvReplaySource:
    """Replays one historical crisis as INCIDENT_REPORTED events (speed is applied by the simulator clock)."""

    def __init__(self, cfg, crisis_id: str):
        self.incidents, self.t0 = load_incidents(cfg, crisis_id)

    def events(self) -> Iterator[Event]:
        for inc in self.incidents:
            yield Event(inc.reported_at, EventType.INCIDENT_REPORTED, {"incident": inc})


class ManualSource:
    """Incidents and team updates entered by the operator in the UI (click on the map)."""

    def push(self, event: Event) -> None:
        raise NotImplementedError


class StormGenerator:
    """Synthetic storms: random incidents around chosen centres, for stress tests."""

    def __init__(self, cfg, seed: int = 0):
        raise NotImplementedError
