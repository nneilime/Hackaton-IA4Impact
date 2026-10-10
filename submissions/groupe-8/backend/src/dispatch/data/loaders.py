"""The only code that knows the CSV format. Everything downstream works on engine types.

Files are in data/raw (semicolon-separated, UTF-8 with BOM). See data/README.md.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from dispatch.config import ROOT
from dispatch.engine.types import Incident, Site, Team

log = logging.getLogger(__name__)


def _read(cfg, key: str) -> pd.DataFrame:
    path = ROOT / cfg.data.raw_dir / getattr(cfg.data, key)
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"code_insee": str})


@lru_cache(maxsize=1)
def _postes_cached(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"code_insee": str}).set_index("id_poste")


def load_postes(cfg) -> pd.DataFrame:
    return _postes_cached(ROOT / cfg.data.raw_dir / cfg.data.postes)


def list_crises(cfg) -> list[str]:
    """The 100 historical crises (benchmarks, backtests). Demo scenarios are listed apart (list_scenarios)."""
    return sorted(_read(cfg, "incidents")["numero_crise"].unique())


SCENARIOS = Path("data/scenarios/scenarios.csv")


def _scenarios() -> pd.DataFrame | None:
    path = ROOT / SCENARIOS
    return pd.read_csv(path, sep=";", encoding="utf-8-sig") if path.exists() else None


def list_scenarios(cfg=None) -> list[str]:
    """Generated demo scenarios (bench/make_demo_scenario.py), same format as the historical crises."""
    df = _scenarios()
    return [] if df is None else sorted(df["numero_crise"].unique())


def load_sites(cfg) -> list[Site]:
    df = _read(cfg, "sites")
    return [Site(r.id_site, r.commune, r.departement, r.latitude, r.longitude, int(r.nb_equipes))
            for r in df.itertuples()]


def load_teams(cfg, sites: list[Site] | None = None, roster: dict[str, int] | None = None,
               b_offset_h: float | None = None, relief: dict[str, int] | None = None,
               c_offset_h: float | None = None) -> list[Team]:
    """One Team per unit of nb_equipes, at its site. Shift schedule (stage 1, fixed at initialisation), per site:
    the first `roster[site]` teams are group B (start at H0 + b_offset_h), the next `relief[site]` teams are group C,
    the relief (start at H0 + c_offset_h, so that some teams are always on duty), the others are group A (H0)."""
    sites = sites or load_sites(cfg)
    r = cfg.roster
    roster = dict(vars(r.b_per_site)) if roster is None else roster
    b = r.b_offset_h if b_offset_h is None else b_offset_h
    relief = (dict(vars(r.c_per_site)) if getattr(r, "c_per_site", None) else {}) if relief is None else relief
    c = getattr(r, "c_offset_h", 12.0) if c_offset_h is None else c_offset_h
    teams = []
    for s in sites:
        n_b = roster.get(s.id, 0)
        n_c = relief.get(s.id, 0)
        if n_b + n_c > s.n_teams:
            raise ValueError(f"roster for {s.id}: {n_b} B + {n_c} C teams > {s.n_teams} teams")
        for k in range(s.n_teams):
            start = float(b) if k < n_b else float(c) if k < n_b + n_c else 0.0
            teams.append(Team(id=f"{s.id}_E{k + 1}", home_site=s.id, lat=s.lat, lon=s.lon,
                              free_at=start, shift_start=start))
    return teams


def load_incidents(cfg, crisis_id: str) -> tuple[list[Incident], datetime]:
    """Incidents of one crisis, times in hours since the first incident (t0). Returns (incidents, t0)."""
    df = _read(cfg, "incidents")
    if crisis_id not in set(df["numero_crise"]):
        df = _scenarios() if _scenarios() is not None else df
    df = df[df["numero_crise"] == crisis_id].copy()
    if df.empty:
        raise ValueError(f"unknown crisis {crisis_id}")
    df["ts"] = pd.to_datetime(df["dateHeureIncident"], format="%d/%m/%Y %H:%M")
    t0 = df["ts"].min()
    postes = load_postes(cfg)

    missing = ~df["id_poste"].isin(postes.index)
    if missing.any():
        log.warning("%s: dropping %d incident(s) with unknown poste: %s",
                    crisis_id, missing.sum(), df.loc[missing, "id_incident"].tolist())
        df = df[~missing]

    incidents = []
    for r in df.sort_values("ts").itertuples():
        p = postes.loc[r.id_poste]
        incidents.append(Incident(
            id=r.id_incident, poste_id=r.id_poste, lat=float(p.latitude), lon=float(p.longitude),
            customers=int(p.nb_clients), sensitive=bool(p.poste_avec_client_sensible),
            reported_at=(r.ts - t0).total_seconds() / 3600, est_duration=float(r.dureeDepannage.rstrip("h")),
            cause=r.causeInterruption, commune=str(p.commune), departement=str(p.departement)))
    return incidents, t0.to_pydatetime()
