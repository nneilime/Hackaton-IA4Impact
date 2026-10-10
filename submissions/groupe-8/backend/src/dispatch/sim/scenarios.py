"""Named scenarios for robustness tests (README criterion "Robustesse" + bonus stress tests).

Each scenario returns what the simulator needs: (cfg, incidents, teams, modifiers, description).
  normal         all teams, one crisis
  stress         only a fraction of the teams
  teams_lost     a fraction of the teams becomes unavailable for good at `at_h` (README: 50 % after 48 h)
  two_crises     a second crisis starts `gap_h` hours after the first
  flood          a zone is inaccessible until `until_h`, then slowed (travel x `slow`)
  storm          every trip slowed by `factor`
  noise          real repair times differ from the estimates (lognormal, sigma)
"""
from __future__ import annotations

import copy
from dataclasses import replace

from dispatch.config import load_config
from dispatch.data.loaders import load_incidents, load_teams
from dispatch.engine.modifiers import TeamUnavailable, TravelFactor, ZoneInaccessible


def _base(crisis: str, cfg=None):
    cfg = cfg or load_config()
    incs, _ = load_incidents(cfg, crisis)
    return cfg, incs, load_teams(cfg)


def normal(crisis="CRISE_051", cfg=None):
    cfg, incs, teams = _base(crisis, cfg)
    return cfg, incs, teams, [], f"{crisis}, all {len(teams)} teams"


def stress(crisis="CRISE_051", fraction=0.5, cfg=None):
    cfg, incs, teams = _base(crisis, cfg)
    step = round(1 / fraction)
    kept = [t for k, t in enumerate(teams) if k % step == 0]
    return cfg, incs, kept, [], f"{crisis}, only {len(kept)}/{len(teams)} teams"


def teams_lost(crisis="CRISE_051", fraction=0.5, at_h=12.0, cfg=None):
    cfg, incs, teams = _base(crisis, cfg)
    step = round(1 / fraction)
    lost = [t.id for k, t in enumerate(teams) if k % step == 0]
    mods = [TeamUnavailable(team=tid, from_h=at_h, until_h=None, reason="scenario") for tid in lost]
    return cfg, incs, teams, mods, f"{crisis}, {len(lost)} teams lost at H0+{at_h:g} h"


def two_crises(first="CRISE_046", second="CRISE_051", gap_h=24.0, cfg=None):
    cfg, a, teams = _base(first, cfg)
    b, _ = load_incidents(cfg, second)
    shifted = [replace(i, id=f"B_{i.id}", reported_at=i.reported_at + gap_h) for i in b]
    return cfg, a + shifted, teams, [], f"{first} then {second} {gap_h:g} h later ({len(a) + len(b)} incidents)"


def flood(crisis="CRISE_051", zone="Ariège", until_h=12.0, slow=1.5, cfg=None):
    cfg, incs, teams = _base(crisis, cfg)
    mods = [ZoneInaccessible(zone=zone, until_h=until_h, reason="scenario: crue"),
            TravelFactor(zone=zone, factor=slow, reason="scenario: routes dégradées")]
    return cfg, incs, teams, mods, f"{crisis}, {zone} flooded until H0+{until_h:g} h then travel x{slow:g}"


def storm(crisis="CRISE_051", factor=1.5, cfg=None):
    cfg = copy.deepcopy(cfg or load_config())
    cfg.travel.storm_factor = factor
    _, incs, teams = _base(crisis, cfg)
    return cfg, incs, teams, [], f"{crisis}, every trip x{factor:g} (storm)"


def noise(crisis="CRISE_051", sigma=0.3, cfg=None):
    cfg = copy.deepcopy(cfg or load_config())
    cfg.simulation.duration_noise_sigma = sigma
    _, incs, teams = _base(crisis, cfg)
    return cfg, incs, teams, [], f"{crisis}, real repair times = estimate x lognormal(sigma={sigma:g})"


CATALOGUE = {"normal": normal, "stress_50": lambda **k: stress(fraction=0.5, **k),
             "stress_25": lambda **k: stress(fraction=0.25, **k), "teams_lost": teams_lost,
             "two_crises": two_crises, "flood": flood, "storm": storm, "noise": noise}
