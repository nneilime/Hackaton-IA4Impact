"""Catalogue of operator rules (modifiers).

The LLM turns a manager's reason into one of these (strict JSON). The validator checks it. The engine applies it.
Safety rules (shift / rest / no interruption) are NOT modifiable from here.
See docs/RO_ENGINE_BRIEF.md §7.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Scope = Literal["incident", "crisis", "permanent"]


@dataclass(frozen=True)
class Modifier:
    reason: str = ""                 # manager's words, kept for the decision log
    scope: Scope = "crisis"


@dataclass(frozen=True)
class Force(Modifier):
    team: str = ""
    incident: str = ""


@dataclass(frozen=True)
class Forbid(Modifier):
    team_or_site: str = ""
    incident_or_zone: str = ""


@dataclass(frozen=True)
class TeamUnavailable(Modifier):
    team: str = ""
    from_h: float = 0.0
    until_h: float | None = None


@dataclass(frozen=True)
class ZoneInaccessible(Modifier):
    zone: str = ""
    until_h: float = 0.0


@dataclass(frozen=True)
class TravelFactor(Modifier):
    zone: str = ""
    factor: float = 1.0


@dataclass(frozen=True)
class DurationUpdate(Modifier):
    incident: str = ""
    hours: float = 0.0


@dataclass(frozen=True)
class Priority(Modifier):
    incident: str = ""
    factor: float = 1.0
    sensitive: bool | None = None


@dataclass(frozen=True)
class Reserve(Modifier):
    site: str = ""
    n_teams: int = 0
    until_h: float | None = None


@dataclass(frozen=True)
class Weight(Modifier):
    name: str = ""                   # beta_sensitive | lambda_stability | lambda_travel | lambda_fairness
    value: float = 0.0


CATALOGUE: dict[str, type[Modifier]] = {
    "force": Force,
    "forbid": Forbid,
    "team_unavailable": TeamUnavailable,
    "zone_inaccessible": ZoneInaccessible,
    "travel_factor": TravelFactor,
    "duration_update": DurationUpdate,
    "priority": Priority,
    "reserve": Reserve,
    "weight": Weight,
}
TYPE_OF = {cls: name for name, cls in CATALOGUE.items()}


def to_dict(m: Modifier) -> dict:
    from dataclasses import asdict
    return {"type": TYPE_OF[type(m)], **asdict(m)}


def from_dict(d: dict) -> Modifier:
    """Build a modifier from {"type": ..., fields...}. Raises KeyError / TypeError on unknown type or field."""
    d = dict(d)
    cls = CATALOGUE[d.pop("type")]
    return cls(**d)
