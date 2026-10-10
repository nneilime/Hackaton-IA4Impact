"""
Jointure des pannes avec les postes, parsing des durées et dates, expansion des sites en équipes.

Fonctions pures : aucun appel Streamlit.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_DUREE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*h\s*$", re.IGNORECASE)
_FORMAT_DATE = "%d/%m/%Y %H:%M"

COLONNES_POSTE = (
    "id_poste",
    "latitude",
    "longitude",
    "nb_clients",
    "poste_avec_client_sensible",
)

COULEUR_PANNE = "#d62728"
COULEUR_SITE = "#1f77b4"
COULEUR_EN_COURS = "#ff7f0e"
COULEUR_RESOLUE = "#2ca02c"
COULEUR_BARYCENTRE = "#9467bd"


def filtrer_crise(coupures: pd.DataFrame, numero_crise: str) -> pd.DataFrame:
    """Garde les pannes d'une seule crise."""
    return coupures.loc[coupures["numero_crise"] == numero_crise].copy()


def joindre_postes(coupures: pd.DataFrame, postes: pd.DataFrame) -> pd.DataFrame:
    """Relie chaque panne à son poste pour récupérer position, clients et clients sensibles."""
    referentiel = postes.loc[:, list(COLONNES_POSTE)].drop_duplicates(subset=["id_poste"])
    return coupures.merge(referentiel, on="id_poste", how="left")


def separer_pannes_localisables(incidents: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Écarte les pannes sans latitude ou sans longitude. Retourne les pannes gardées et le nombre écarté."""
    if incidents.empty:
        return incidents.copy(), 0
    masque = incidents["latitude"].notna() & incidents["longitude"].notna()
    return incidents.loc[masque].copy(), int((~masque).sum())


def parser_duree(valeur: Any) -> float:
    """Convertit « 4h » en 4.0. Une valeur illisible devient 0.0."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return 0.0
    if isinstance(valeur, bool):
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    correspondance = _DUREE.match(str(valeur).strip())
    if correspondance is None:
        return 0.0
    return float(correspondance.group(1).replace(",", "."))


def est_duree_lisible(valeur: Any) -> bool:
    """Indique si la durée brute peut être lue. Un nombre déjà numérique est lisible."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return False
    if isinstance(valeur, bool):
        return False
    if isinstance(valeur, (int, float)):
        return True
    return _DUREE.match(str(valeur).strip()) is not None


def parser_date(valeur: Any) -> pd.Timestamp:
    """Convertit « 09/01/2016 14:08 » en date. Une valeur illisible devient NaT."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return pd.NaT
    if isinstance(valeur, pd.Timestamp):
        return valeur
    try:
        return pd.to_datetime(str(valeur).strip(), format=_FORMAT_DATE)
    except (ValueError, TypeError):
        return pd.NaT


def annoter_pannes(incidents: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Ajoute duree_heures et date_incident. Retourne aussi le nombre de durées illisibles."""
    annotees = incidents.copy()
    if "dureeDepannage" in annotees.columns:
        brutes = annotees["dureeDepannage"]
    else:
        brutes = pd.Series([None] * len(annotees), index=annotees.index)
    annotees["duree_heures"] = brutes.map(parser_duree)
    if "dateHeureIncident" in annotees.columns:
        annotees["date_incident"] = annotees["dateHeureIncident"].map(parser_date)
    else:
        annotees["date_incident"] = pd.NaT
    return annotees, int((~brutes.map(est_duree_lisible)).sum())


def derouler_equipes(agents: pd.DataFrame) -> pd.DataFrame:
    """Transforme chaque site en autant de lignes que nb_equipes, au même point GPS."""
    lignes: list[dict[str, Any]] = []
    for _, site in agents.iterrows():
        identifiant = str(site["id_site"])
        effectif = site.get("nb_equipes", 0)
        if pd.isna(effectif):
            continue
        for rang in range(1, int(effectif) + 1):
            lignes.append(
                {
                    "id_equipe": f"{identifiant}_{rang}",
                    "id_site": identifiant,
                    "commune": site.get("commune", ""),
                    "latitude": float(site["latitude"]),
                    "longitude": float(site["longitude"]),
                    "disponible": True,
                }
            )
    return pd.DataFrame(lignes)


def preparer_pannes(
    coupures: pd.DataFrame,
    postes: pd.DataFrame,
    numero_crise: str,
) -> tuple[pd.DataFrame, int, int]:
    """
    Filtre une crise, la relie aux postes et écarte les pannes non localisables.

    Retourne les pannes utilisables, le nombre de pannes écartées et le nombre de durées illisibles.
    """
    crise = filtrer_crise(coupures, numero_crise)
    jointes = joindre_postes(crise, postes)
    localisables, nb_ecartes = separer_pannes_localisables(jointes)
    annotees, nb_illisible = annoter_pannes(localisables)
    return annotees, nb_ecartes, nb_illisible


def construire_points_carte(incidents: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    """Assemble les pannes et les sites pour st.map, avec une couleur par type."""
    colonnes = ["latitude", "longitude", "type", "color", "libelle"]
    blocs: list[pd.DataFrame] = []
    if not incidents.empty:
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": pd.to_numeric(incidents["latitude"], errors="coerce"),
                    "longitude": pd.to_numeric(incidents["longitude"], errors="coerce"),
                    "type": "panne",
                    "color": COULEUR_PANNE,
                    "libelle": incidents["id_incident"].astype(str).to_numpy(),
                }
            )
        )
    if not sites.empty:
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": pd.to_numeric(sites["latitude"], errors="coerce"),
                    "longitude": pd.to_numeric(sites["longitude"], errors="coerce"),
                    "type": "site",
                    "color": COULEUR_SITE,
                    "libelle": sites["id_site"].astype(str).to_numpy(),
                }
            )
        )
    if not blocs:
        return pd.DataFrame(columns=colonnes)
    points = pd.concat(blocs, ignore_index=True)
    return points.dropna(subset=["latitude", "longitude"])


def construire_points_pas(
    incidents: pd.DataFrame,
    en_attente: list[str],
    en_cours: list[str],
    resolues: list[str],
    equipes: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Points de carte à un pas donné : pannes colorées selon leur statut
    (rouge en attente, orange en cours, vert résolue) et équipes à leur position.
    """
    colonnes = ["latitude", "longitude", "type", "color", "libelle"]
    statuts = (
        (en_attente, "en attente", COULEUR_PANNE),
        (en_cours, "en cours", COULEUR_EN_COURS),
        (resolues, "résolue", COULEUR_RESOLUE),
    )
    blocs: list[pd.DataFrame] = []
    if not incidents.empty:
        identifiants = incidents["id_incident"].astype(str)
        for liste, statut, couleur in statuts:
            choisies = incidents.loc[identifiants.isin(liste)]
            if choisies.empty:
                continue
            blocs.append(
                pd.DataFrame(
                    {
                        "latitude": pd.to_numeric(choisies["latitude"], errors="coerce"),
                        "longitude": pd.to_numeric(choisies["longitude"], errors="coerce"),
                        "type": statut,
                        "color": couleur,
                        "libelle": choisies["id_incident"].astype(str).to_numpy(),
                    }
                )
            )
    if equipes:
        positions = pd.DataFrame(equipes)
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": pd.to_numeric(positions["latitude"], errors="coerce"),
                    "longitude": pd.to_numeric(positions["longitude"], errors="coerce"),
                    "type": "équipe",
                    "color": COULEUR_SITE,
                    "libelle": positions["id_equipe"].astype(str).to_numpy(),
                }
            )
        )
    if not blocs:
        return pd.DataFrame(columns=colonnes)
    points = pd.concat(blocs, ignore_index=True)
    return points.dropna(subset=["latitude", "longitude"])


def construire_points_preparation(
    incidents_previsionnels: pd.DataFrame,
    sites: pd.DataFrame,
    barycentre_lat: float,
    barycentre_lon: float,
) -> pd.DataFrame:
    """
    Assemble les points de la vue Préparation pour st.map / st.pydeck_chart.

    Contrairement à construire_points_carte, cette fonction affiche :
    - les incidents prévisionnels (rouge),
    - les sites d'équipes (bleu),
    - le point de repli / barycentre (violet) quand les coordonnées sont valides.

    construire_points_carte reste intacte pour Jour J et Rejeu.
    """
    import math

    colonnes = ["latitude", "longitude", "type", "color", "libelle"]
    blocs: list[pd.DataFrame] = []

    if not incidents_previsionnels.empty:
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": pd.to_numeric(incidents_previsionnels["latitude"], errors="coerce"),
                    "longitude": pd.to_numeric(incidents_previsionnels["longitude"], errors="coerce"),
                    "type": "incident_previsionnel",
                    "color": COULEUR_PANNE,
                    "libelle": incidents_previsionnels["id_incident"].astype(str).to_numpy(),
                }
            )
        )

    if not sites.empty:
        id_col = "id_site" if "id_site" in sites.columns else sites.columns[0]
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": pd.to_numeric(sites["latitude"], errors="coerce"),
                    "longitude": pd.to_numeric(sites["longitude"], errors="coerce"),
                    "type": "site",
                    "color": COULEUR_SITE,
                    "libelle": sites[id_col].astype(str).to_numpy(),
                }
            )
        )

    if not (math.isnan(barycentre_lat) or math.isnan(barycentre_lon)):
        blocs.append(
            pd.DataFrame(
                {
                    "latitude": [barycentre_lat],
                    "longitude": [barycentre_lon],
                    "type": ["point_repli"],
                    "color": [COULEUR_BARYCENTRE],
                    "libelle": ["Point de repli optimal"],
                }
            )
        )

    if not blocs:
        return pd.DataFrame(columns=colonnes)
    points = pd.concat(blocs, ignore_index=True)
    return points.dropna(subset=["latitude", "longitude"])
