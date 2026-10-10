"""État de la crise à un instant t, reconstruit depuis un SimResult (sans relancer la simulation).

Sert à la carte animée (T4.2) et au point de situation (T5.3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from crise.models import SimResult

ETATS = ("à venir", "en attente", "en intervention", "rétabli")


def incidents_a(res: SimResult, t: float) -> pd.DataFrame:
    """Incidents avec une colonne `etat` à l'instant t (minutes)."""
    inc = res.incidents.copy()
    aff = inc["t_affectation"].fillna(np.inf)
    rsl = inc["t_resolution"].fillna(np.inf)
    inc["etat"] = np.select(
        [inc["t_apparition"] > t, aff > t, rsl > t],
        ["à venir", "en attente", "en intervention"],
        "rétabli",
    )
    inc["attente_h"] = ((np.minimum(aff, t) - inc["t_apparition"]).clip(lower=0) / 60).round(1)
    return inc


def equipes_a(res: SimResult, t: float) -> pd.DataFrame:
    """Position et activité de chaque équipe à l'instant t (interpolation linéaire pendant les trajets)."""
    lignes = []
    for id_eq, g in res.activites.sort_values("t_debut").groupby("id_equipe"):
        en_cours = g[(g["t_debut"] <= t) & (g["t_fin"] > t)]
        if not en_cours.empty:
            a = en_cours.iloc[-1]
            duree = max(a["t_fin"] - a["t_debut"], 1)
            f = (t - a["t_debut"]) / duree if a["type"] in ("trajet", "retour") else 1.0
            lat = a["lat_dep"] + f * (a["lat_arr"] - a["lat_dep"])
            lon = a["lon_dep"] + f * (a["lon_arr"] - a["lon_dep"])
            lignes.append({"id_equipe": id_eq, "activite": a["type"], "lat": lat, "lon": lon,
                           "id_incident": a["id_incident"], "lat_cible": a["lat_arr"], "lon_cible": a["lon_arr"]})
            continue
        passees = g[g["t_fin"] <= t]
        ref = passees.iloc[-1] if not passees.empty else g.iloc[0]
        lat, lon = (ref["lat_arr"], ref["lon_arr"]) if not passees.empty else (ref["lat_dep"], ref["lon_dep"])
        lignes.append({"id_equipe": id_eq, "activite": "disponible", "lat": lat, "lon": lon,
                       "id_incident": None, "lat_cible": lat, "lon_cible": lon})
    return pd.DataFrame(lignes)


def ligne_serie(res: SimResult, t: float) -> dict:
    """Dernier instantané de la série avant t (pour le point de situation)."""
    s = res.serie[res.serie["t"] <= t]
    return (s.iloc[-1] if not s.empty else res.serie.iloc[0]).to_dict()
