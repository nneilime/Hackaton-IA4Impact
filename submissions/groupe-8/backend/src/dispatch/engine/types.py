"""Shared contract between data, simulator, engine, copilot and app.

Proposal from docs/RO_ENGINE_BRIEF.md §5. Change it together (simulator + engine + app owners), not alone.
Time unit: hours as float since the crisis start t0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dispatch.engine.modifiers import Modifier


class TeamStatus(Enum):
    IDLE = "idle"
    TRAVELLING = "travelling"
    REPAIRING = "repairing"
    RESTING = "resting"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Incident:
    id: str
    poste_id: str
    lat: float
    lon: float
    customers: int                  # n_i
    sensitive: bool                 # s_i
    reported_at: float              # r_i (h since t0)
    est_duration: float             # p̂_i (h), an ESTIMATE; the simulator holds the truth
    cause: str = ""
    commune: str = ""
    departement: str = ""
    accessible_from: float = 0.0    # set by modifiers ("zone flooded until 18h")
    teams_required: int = 1         # C1, the MVP supports 1
    priority: float = 1.0           # weight multiplier set by modifiers
    travel_factor: float = 1.0      # travel-time multiplier into this incident (modifiers)


@dataclass
class Team:
    id: str
    home_site: str
    lat: float                      # position when it becomes free
    lon: float
    free_at: float                  # now if idle, else end of the current job
    shift_start: float = 0.0        # start of the first shift (roster); then work_h on / rest_h off
    status: TeamStatus = TeamStatus.IDLE
    current_job: str | None = None  # locked (C7)


@dataclass(frozen=True)
class Site:
    id: str
    commune: str
    departement: str
    lat: float
    lon: float
    n_teams: int


@dataclass
class ScoreBreakdown:
    total: float = 0.0                       # objective + stability penalty (what the search minimises)
    objective: float = 0.0                   # Σ f_i(C_i): weighted outage + starvation term
    weighted_customer_hours: float = 0.0     # Σ w_i (C_i - r_i)
    customer_hours: float = 0.0              # Σ n_i (C_i - r_i): the README's N×T indicator
    stability_penalty: float = 0.0
    starvation_penalty: float = 0.0
    kpis: dict[str, float] = field(default_factory=dict)


@dataclass
class Plan:
    routes: dict[str, list[str]]                                  # team_id -> ordered incident ids
    schedule: dict[str, tuple[float, float, float]] = field(default_factory=dict)  # id -> (depart, start, end)
    unassigned: list[str] = field(default_factory=list)
    score: ScoreBreakdown = field(default_factory=ScoreBreakdown)

    def next_jobs(self) -> dict[str, str]:
        return {team: route[0] for team, route in self.routes.items() if route}


@dataclass
class State:
    now: float
    teams: list[Team]
    pending: list[Incident]                                       # arrived, not yet started (C3)
    modifiers: list[Modifier] = field(default_factory=list)       # validated operator rules (C7)
    previous_plan: Plan | None = None                             # warm start + stability


@dataclass
class ExplanationFacts:
    """Everything the LLM may say about one recommendation. It may not state any number absent from here."""
    team: str
    incident: str
    rank_in_plan: int
    factors: dict[str, float | bool]
    best_alternative_team: dict | None = None        # {"team": "T04", "delta_score": 410}
    best_alternative_incident: dict | None = None    # {"incident": "INC_...", "delta_score": 180}
    alternatives: list[dict] | None = None           # next best teams: team, delta, restored_h, travel_min
    binding_constraint: str | None = None
    tipping_point: str | None = None
