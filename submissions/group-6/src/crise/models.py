"""Contrats d'interface — FIGÉS (voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §4).

Propriétaire : P1. Toute modification est annoncée à l'équipe avant d'être poussée.
Unités : temps en MINUTES depuis le début de la crise (int), distances en km, coordonnées WGS84.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class EtatEquipe(StrEnum):
    DISPONIBLE = "disponible"
    TRAJET = "trajet"
    CHANTIER = "chantier"
    RETOUR = "retour"          # retour base avant repos
    REPOS = "repos"
    HORS_SERVICE = "hors_service"


class EtatIncident(StrEnum):
    NON_APPARU = "non_apparu"
    EN_ATTENTE = "en_attente"
    AFFECTE = "affecte"        # équipe en route
    EN_COURS = "en_cours"      # chantier
    RESOLU = "resolu"


@dataclass
class Poste:
    id_poste: str
    commune: str
    departement: str
    lat: float
    lon: float
    nb_clients: int
    sensible: bool


@dataclass
class Site:
    id_site: str
    commune: str
    lat: float
    lon: float
    nb_equipes: int


@dataclass
class Incident:
    id_incident: str
    id_poste: str
    t_apparition: int          # min depuis début de crise
    duree_nominale: int        # min (120/240/480) — ce que voit la stratégie
    duree_reelle: int          # min — ce que joue le simulateur (= nominale sans Monte Carlo)
    cause: str
    nb_clients: int
    sensible: bool
    lat: float
    lon: float
    etat: EtatIncident = EtatIncident.NON_APPARU
    id_equipe: str | None = None
    t_affectation: int | None = None
    t_arrivee: int | None = None
    t_resolution: int | None = None


@dataclass
class Equipe:
    id_equipe: str             # ex "SITE_04_E2"
    id_site: str               # base de rattachement
    lat: float                 # position courante
    lon: float
    etat: EtatEquipe = EtatEquipe.DISPONIBLE
    t_debut_service: int = 0   # début de l'amplitude en cours
    t_libre: int = 0           # date où elle redevient disponible
    id_incident: str | None = None


@dataclass
class Affectation:
    id_equipe: str
    id_incident: str
    explication: dict = field(default_factory=dict)   # format §4.3


@dataclass
class EtatSimulation:
    """Ce que reçoit une stratégie à chaque décision."""
    t: int
    equipes_disponibles: list[Equipe]
    incidents_en_attente: list[Incident]
    toutes_equipes: list[Equipe]
    params: dict               # amplitude, repos, alpha, beta, vitesses…


@dataclass
class SimResult:
    """Produit par le simulateur, utilisé par KPI et UI (§4.4)."""
    incidents: pd.DataFrame
    activites: pd.DataFrame
    decisions: pd.DataFrame
    serie: pd.DataFrame
    metadata: dict = field(default_factory=dict)


# Colonnes attendues des 4 tables de SimResult (§4.4) — utilisées par les tests et les données factices.
COLONNES_SIMRESULT = {
    "incidents": [
        "id_incident", "id_poste", "lat", "lon", "nb_clients", "sensible", "commune", "departement",
        "t_apparition", "t_affectation", "t_arrivee", "t_resolution", "id_equipe", "duree_reelle",
    ],
    "activites": [
        "id_equipe", "type", "t_debut", "t_fin", "id_incident", "lat_dep", "lon_dep", "lat_arr", "lon_arr",
    ],
    "decisions": ["t", "id_equipe", "id_incident", "explication"],
    "serie": ["t", "clients_coupes", "incidents_attente", "equipes_occupees", "equipes_repos"],
}


def normaliser_numero_crise(numero_crise: str | int) -> str:
    """27, "27", "crise_027" ou "CRISE_027" → "CRISE_027"."""
    if isinstance(numero_crise, int):
        return f"CRISE_{numero_crise:03d}"
    s = str(numero_crise).strip().upper()
    if s.isdigit():
        return f"CRISE_{int(s):03d}"
    if s.startswith("CRISE_") and s[6:].isdigit():
        return f"CRISE_{int(s[6:]):03d}"
    raise ValueError(f"numéro de crise invalide : {numero_crise!r} (attendu ex. 27 ou 'CRISE_027')")


def _dossier_clean(clean_dir: str | Path | None) -> Path:
    if clean_dir is not None:
        return Path(clean_dir)
    from crise.config import charger_config, chemin_projet

    return chemin_projet(charger_config()["chemins"]["clean"])


@lru_cache(maxsize=8)
def _lire_tables(dossier: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lit sites + incidents une seule fois par dossier (le banc d'essai appelle charger_scenario 100× et plus)."""
    import pandas as pd

    d = Path(dossier)
    manquants = [f for f in ("sites.parquet", "incidents.parquet") if not (d / f).exists()]
    if manquants:
        raise FileNotFoundError(f"{manquants} absents de {d} — lancer d'abord : python -m crise.data.nettoyage")
    return pd.read_parquet(d / "sites.parquet"), pd.read_parquet(d / "incidents.parquet")


def lister_crises(clean_dir: str | Path | None = None) -> list[str]:
    """Liste triée des numéros de crise disponibles (ex. ["CRISE_001", …, "CRISE_100"])."""
    _, incidents = _lire_tables(str(_dossier_clean(clean_dir)))
    return sorted(incidents["numero_crise"].unique().tolist())


def creer_equipes(sites: list[Site], positions_initiales: dict[str, tuple[float, float]] | None = None) -> list[Equipe]:
    """Une Equipe par unité de nb_equipes : SITE_04_E1, SITE_04_E2, …

    positions_initiales (prépositionnement, T3.4/T1.8) : {id_equipe: (lat, lon)} ; les équipes absentes
    du dict partent de leur site. Le site reste la base de rattachement (retour pour le repos).
    """
    positions_initiales = positions_initiales or {}
    inconnues = set(positions_initiales) - {f"{s.id_site}_E{k}" for s in sites for k in range(1, s.nb_equipes + 1)}
    if inconnues:
        raise ValueError(f"positions_initiales : équipes inconnues {sorted(inconnues)[:5]}")
    equipes = []
    for s in sites:
        for k in range(1, s.nb_equipes + 1):
            id_eq = f"{s.id_site}_E{k}"
            lat, lon = positions_initiales.get(id_eq, (s.lat, s.lon))
            equipes.append(Equipe(id_equipe=id_eq, id_site=s.id_site, lat=float(lat), lon=float(lon)))
    return equipes


def charger_scenario(
    numero_crise: str | int,
    params: dict | None = None,
    clean_dir: str | Path | None = None,
) -> tuple[list[Site], list[Equipe], list[Incident]]:
    """T1.3 — renvoie (sites, equipes, incidents) pour une crise, depuis data/clean/*.parquet.

    - incidents triés par t_apparition, état NON_APPARU, duree_reelle = duree_nominale
      (le Monte Carlo du simulateur pourra modifier duree_reelle, T1.7) ;
    - t_apparition en minutes depuis le premier incident de la crise ;
    - params (optionnel) :
        "positions_initiales": {id_equipe: (lat, lon)}  → prépositionnement
        "nb_equipes_max": int                           → stress test « peu d'équipes » (S5),
                                                          on garde les premières équipes de chaque site
                                                          à tour de rôle pour rester équilibré.
    Les objets renvoyés sont NEUFS à chaque appel (le simulateur peut les modifier sans risque).
    """
    params = params or {}
    crise = normaliser_numero_crise(numero_crise)
    df_sites, df_inc = _lire_tables(str(_dossier_clean(clean_dir)))

    sites = [
        Site(id_site=r.id_site, commune=r.commune, lat=float(r.lat), lon=float(r.lon), nb_equipes=int(r.nb_equipes))
        for r in df_sites.itertuples(index=False)
    ]
    equipes = creer_equipes(sites, params.get("positions_initiales"))

    nb_max = params.get("nb_equipes_max")
    if nb_max is not None:
        # tour de rôle : E1 de chaque site, puis E2 de chaque site, …
        ordre = sorted(equipes, key=lambda e: (int(e.id_equipe.rsplit("_E", 1)[1]), e.id_site))
        garder = {e.id_equipe for e in ordre[: int(nb_max)]}
        equipes = [e for e in equipes if e.id_equipe in garder]

    sel = df_inc[df_inc["numero_crise"] == crise].sort_values(["t_apparition", "id_incident"])
    if sel.empty:
        raise ValueError(f"{crise} introuvable dans incidents.parquet")
    incidents = [
        Incident(
            id_incident=r.id_incident,
            id_poste=r.id_poste,
            t_apparition=int(r.t_apparition),
            duree_nominale=int(r.duree_min),
            duree_reelle=int(r.duree_min),
            cause=r.cause,
            nb_clients=int(r.nb_clients),
            sensible=bool(r.sensible),
            lat=float(r.lat),
            lon=float(r.lon),
        )
        for r in sel.itertuples(index=False)
    ]
    return sites, equipes, incidents
