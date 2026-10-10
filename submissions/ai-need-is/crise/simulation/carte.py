"""
État de la carte à un instant quelconque, y compris entre deux pas de simulation.

Fonctions pures : aucun appel Streamlit. Elles s'appuient sur les trajets et les
interventions horodatés produits par ``lancer_simulation``.

Règles d'affichage :
  - un technicien n'est visible que pendant un déplacement (vers un incident ou vers son site) ;
  - un incident est rouge tant que personne n'est sur place, orange pendant la réparation,
    et disparaît dès qu'il est résolu.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from crise.simulation.moteur import _dates_incident

COULEUR_ATTENTE = [214, 39, 40]
COULEUR_REPARATION = [255, 127, 14]


def _fraction(depart: pd.Timestamp, arrivee: pd.Timestamp, instant: pd.Timestamp) -> float:
    duree = (arrivee - depart) / pd.Timedelta(seconds=1)
    if duree <= 0:
        return 1.0
    return min(max((instant - depart) / pd.Timedelta(seconds=1) / duree, 0.0), 1.0)


def techniciens_en_route(trajets: list[dict[str, Any]], instant: pd.Timestamp) -> pd.DataFrame:
    """
    Techniciens en déplacement à ``instant``, à leur position interpolée sur le trajet.

    Un technicien apparaît à son départ et disparaît à son arrivée (incident ou site).
    """
    colonnes = [
        "id_equipe", "id_site", "destination", "id_incident", "latitude", "longitude",
        "lat_arrivee", "lon_arrivee", "arrivee", "amplitude_h",
    ]
    lignes: list[dict[str, Any]] = []
    for trajet in trajets:
        if not trajet["depart"] <= instant < trajet["arrivee"]:
            continue
        part = _fraction(trajet["depart"], trajet["arrivee"], instant)
        lignes.append(
            {
                "id_equipe": trajet["id_equipe"],
                "id_site": trajet["id_site"],
                "destination": trajet["destination"],
                "id_incident": trajet["id_incident"],
                "latitude": trajet["lat_depart"] + part * (trajet["lat_arrivee"] - trajet["lat_depart"]),
                "longitude": trajet["lon_depart"] + part * (trajet["lon_arrivee"] - trajet["lon_depart"]),
                "lat_arrivee": trajet["lat_arrivee"],
                "lon_arrivee": trajet["lon_arrivee"],
                "arrivee": trajet["arrivee"],
                "amplitude_h": trajet["amplitude_depart_h"]
                + (instant - trajet["depart"]) / pd.Timedelta(hours=1),
            }
        )
    return pd.DataFrame(lignes, columns=colonnes)


def _ms(instant: Any) -> int | None:
    """Horodatage en millisecondes (heure locale de la crise traitée comme UTC)."""
    if instant is None or pd.isna(instant):
        return None
    return int(pd.Timestamp(instant).value // 1_000_000)


def chronologie_carte(
    pannes: pd.DataFrame,
    resultat: dict[str, Any],
    sites: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Toute la chronologie de la carte en un seul objet JSON, pour l'animer dans le navigateur.

    Pour chaque incident : apparition, affectation, arrivée de l'équipe, fin de réparation.
    Pour chaque trajet : départ, arrivée, positions. Les heures sont en millisecondes.
    """
    par_incident = {i["id_incident"]: i for i in resultat.get("interventions", [])}
    affectation = {
        t["id_incident"]: t["depart"]
        for t in resultat.get("trajets", [])
        if t["destination"] == "incident"
    }

    incidents: list[dict[str, Any]] = []
    if not pannes.empty:
        for (_, panne), date in zip(pannes.iterrows(), _dates_incident(pannes)):
            if pd.isna(date) or pd.isna(panne.get("latitude")) or pd.isna(panne.get("longitude")):
                continue
            identifiant = str(panne["id_incident"])
            intervention = par_incident.get(identifiant)
            clients = pd.to_numeric(panne.get("nb_clients"), errors="coerce")
            fin = intervention["fin"] if intervention else None
            arrivee = intervention["arrivee"] if intervention else None
            incidents.append(
                {
                    "id": identifiant,
                    "lat": float(panne["latitude"]),
                    "lon": float(panne["longitude"]),
                    "clients": 0 if pd.isna(clients) else int(clients),
                    "date": _ms(date),
                    # Sans trajet (équipe déjà sur place), l'affectation se confond avec l'arrivée.
                    "aff": _ms(affectation.get(identifiant, arrivee)),
                    "arr": _ms(arrivee),
                    "fin": _ms(fin),
                }
            )

    trajets = [
        {
            "equipe": t["id_equipe"],
            "site": t["id_site"],
            "dest": t["destination"],
            "motif": t.get("motif"),
            "incident": t["id_incident"],
            "d": _ms(t["depart"]),
            "a": _ms(t["arrivee"]),
            "lat0": t["lat_depart"],
            "lon0": t["lon_depart"],
            "lat1": t["lat_arrivee"],
            "lon1": t["lon_arrivee"],
            "amp0": round(float(t["amplitude_depart_h"]), 3),
        }
        for t in resultat.get("trajets", [])
    ]

    liste_sites: list[dict[str, Any]] = []
    if sites is not None and not sites.empty:
        for site in sites.to_dict("records"):
            if pd.isna(site.get("latitude")) or pd.isna(site.get("longitude")):
                continue
            commune = site.get("commune")
            liste_sites.append(
                {
                    "id": str(site.get("id_site", "")),
                    "commune": "" if commune is None or pd.isna(commune) else str(commune),
                    "lat": float(site["latitude"]),
                    "lon": float(site["longitude"]),
                }
            )

    pas = resultat.get("pas", [])
    duree_pas = pd.Timedelta(minutes=int(resultat.get("pas_min") or 30))
    debut = resultat.get("t0") if resultat.get("t0") is not None else (pas[0]["instant"] if pas else None)
    fin = pas[-1]["instant"] + duree_pas if pas else debut
    return {
        "debut": _ms(debut),
        "fin": _ms(fin),
        "pas_min": int(resultat.get("pas_min") or 30),
        "incidents": incidents,
        "trajets": trajets,
        "sites": liste_sites,
    }


def incidents_visibles(
    pannes: pd.DataFrame,
    interventions: list[dict[str, Any]],
    instant: pd.Timestamp,
) -> pd.DataFrame:
    """
    Incidents connus et non résolus à ``instant``, avec leur statut :
    ``en attente`` (rouge, même si une équipe est en route) ou ``en réparation`` (orange).
    """
    colonnes = ["id_incident", "latitude", "longitude", "nb_clients", "statut", "couleur"]
    if pannes.empty:
        return pd.DataFrame(columns=colonnes)

    par_incident = {intervention["id_incident"]: intervention for intervention in interventions}
    dates = _dates_incident(pannes)
    lignes: list[dict[str, Any]] = []
    for (_, panne), date in zip(pannes.iterrows(), dates):
        if pd.isna(date) or date > instant:
            continue
        if pd.isna(panne.get("latitude")) or pd.isna(panne.get("longitude")):
            continue
        identifiant = str(panne["id_incident"])
        intervention = par_incident.get(identifiant)
        if intervention is not None and intervention["fin"] <= instant:
            continue
        sur_place = intervention is not None and intervention["arrivee"] <= instant
        clients = pd.to_numeric(panne.get("nb_clients"), errors="coerce")
        lignes.append(
            {
                "id_incident": identifiant,
                "latitude": float(panne["latitude"]),
                "longitude": float(panne["longitude"]),
                "nb_clients": 0 if pd.isna(clients) else int(clients),
                "statut": "en réparation" if sur_place else "en attente",
                "couleur": COULEUR_REPARATION if sur_place else COULEUR_ATTENTE,
            }
        )
    return pd.DataFrame(lignes, columns=colonnes)
