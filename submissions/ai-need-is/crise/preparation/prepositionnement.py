"""
Calcul du prépositionnement spatial des équipes avant une crise.

Fonctions pures — aucun import Streamlit.

À partir des incidents prévisionnels (lat/lon, nb_clients), calcule le barycentre
pondéré de la zone de crise et recommande à chaque équipe un déplacement préventif
vers ce point de repli pour réduire les temps de trajet le jour J.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from crise.geo.distance import calculer_distance_haversine, estimer_temps_trajet


def calculer_barycentre_incidents(incidents_df: pd.DataFrame) -> tuple[float, float]:
    """
    Calcule le barycentre pondéré par nb_clients des incidents prévisionnels.

    Si la colonne nb_clients est absente, nulle ou zéro pour tous les incidents,
    utilise la moyenne géométrique simple (poids = 1 pour chaque incident).

    Retourne (float('nan'), float('nan')) si le DataFrame est vide ou ne contient
    aucune coordonnée valide.
    """
    if incidents_df.empty:
        return float("nan"), float("nan")

    df = incidents_df.copy()
    df["latitude"] = pd.to_numeric(df.get("latitude", pd.Series(dtype=float)), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude", pd.Series(dtype=float)), errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    if df.empty:
        return float("nan"), float("nan")

    # Poids : nb_clients si disponible et positif, sinon 1
    if "nb_clients" in df.columns:
        poids = pd.to_numeric(df["nb_clients"], errors="coerce").fillna(0.0)
        if poids.sum() <= 0:
            poids = pd.Series(1.0, index=df.index)
    else:
        poids = pd.Series(1.0, index=df.index)

    total = float(poids.sum())
    lat_b = float((df["latitude"] * poids).sum() / total)
    lon_b = float((df["longitude"] * poids).sum() / total)
    return lat_b, lon_b


def recommander_prepositionnement(
    equipes_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    coeff_detour: float = 1.3,
    vitesse_kmh: float = 60.0,
) -> list[dict[str, Any]]:
    """
    Recommande un déplacement préventif vers le barycentre de la zone de crise
    pour chaque équipe disponible.

    Paramètres
    ----------
    equipes_df : DataFrame avec colonnes id_equipe, commune, latitude, longitude.
    incidents_df : DataFrame des incidents prévisionnels (lat/lon, nb_clients).
    coeff_detour : coefficient de détour routier (par défaut 1.3).
    vitesse_kmh : vitesse moyenne des véhicules (par défaut 60 km/h).

    Retourne
    --------
    Liste de dicts triée par temps_deplacement_h croissant :
      {id_equipe, commune, lat_origine, lon_origine,
       lat_cible, lon_cible, temps_deplacement_h, distance_km}
    """
    if equipes_df.empty or incidents_df.empty:
        return []

    lat_b, lon_b = calculer_barycentre_incidents(incidents_df)
    if math.isnan(lat_b) or math.isnan(lon_b):
        return []

    recommandations: list[dict[str, Any]] = []
    for _, equipe in equipes_df.iterrows():
        try:
            lat_e = float(equipe["latitude"])
            lon_e = float(equipe["longitude"])
        except (ValueError, TypeError, KeyError):
            continue

        if math.isnan(lat_e) or math.isnan(lon_e):
            continue

        distance_km = calculer_distance_haversine(lat_e, lon_e, lat_b, lon_b)
        temps_h = estimer_temps_trajet(
            lat_e, lon_e, lat_b, lon_b,
            coeff_detour=coeff_detour,
            vitesse_moyenne_kmh=vitesse_kmh,
        )
        recommandations.append(
            {
                "id_equipe": str(equipe.get("id_equipe", "")),
                "commune": str(equipe.get("commune", "")),
                "lat_origine": lat_e,
                "lon_origine": lon_e,
                "lat_cible": lat_b,
                "lon_cible": lon_b,
                "temps_deplacement_h": round(temps_h, 3),
                "distance_km": round(distance_km, 1),
            }
        )

    recommandations.sort(key=lambda r: r["temps_deplacement_h"])
    return recommandations
