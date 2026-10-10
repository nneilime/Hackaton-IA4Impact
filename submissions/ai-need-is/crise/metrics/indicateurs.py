"""
Indicateurs de performance et fonction objectif de la gestion de crise.

Objectif principal : maximiser le nombre de clients rétablis le plus tôt possible entre T1 et T5.
Formulation :
    Score = Σ Nbclients_rétablis(Ni) × Temps de Coupure totale (Ti)
avec :
    Temps de coupure total Ti = Temps d'attente + Temps de route + Temps de dépannage
"""

from __future__ import annotations

from typing import Any
import pandas as pd


def calculer_temps_coupure_incident(
    instant_incident: pd.Timestamp | None,
    instant_affectation: pd.Timestamp,
    temps_route_h: float,
    temps_depannage_h: float,
) -> tuple[float, float, float, float]:
    """
    Calcule la décomposition du temps de coupure pour un incident :
    (temps_attente_h, temps_route_h, temps_depannage_h, temps_coupure_total_h).
    """
    if instant_incident is not None and pd.notna(instant_incident):
        attente = max(0.0, (instant_affectation - instant_incident).total_seconds() / 3600.0)
    else:
        attente = 0.0

    route = max(0.0, float(temps_route_h))
    depannage = max(0.0, float(temps_depannage_h))
    coupure_totale = attente + route + depannage

    return round(attente, 2), round(route, 2), round(depannage, 2), round(coupure_totale, 2)


def evaluer_fonction_objectif(
    resolutions: list[dict[str, Any]],
) -> dict[str, float]:
    """
    Évalue la fonction objectif sur une liste d'incidents résolus :
    - score_objectif : Σ (Nb_clients × Ti)
    - clients_retablis : Σ Nb_clients
    - temps_moyen_coupure_h : Moyenne pondérée du temps de coupure par client rétabli
    - temps_attente_moyen_h : Moyenne du temps d'attente avant prise en charge
    - temps_route_moyen_h : Moyenne du temps de trajet
    - temps_depannage_moyen_h : Moyenne du temps de réparation
    """
    if not resolutions:
        return {
            "score_objectif": 0.0,
            "clients_retablis": 0.0,
            "temps_moyen_coupure_h": 0.0,
            "temps_attente_moyen_h": 0.0,
            "temps_route_moyen_h": 0.0,
            "temps_depannage_moyen_h": 0.0,
        }

    score_total = sum(float(r.get("produit_clients_temps", 0.0)) for r in resolutions)
    clients_total = sum(int(r.get("nb_clients", 0)) for r in resolutions)

    nb = len(resolutions)
    attente_moy = sum(float(r.get("temps_attente_h", 0.0)) for r in resolutions) / nb
    route_moy = sum(float(r.get("temps_route_h", 0.0)) for r in resolutions) / nb
    dep_moy = sum(float(r.get("temps_depannage_h", 0.0)) for r in resolutions) / nb

    temps_moyen_par_client = (score_total / clients_total) if clients_total > 0 else 0.0

    return {
        "score_objectif": round(score_total, 2),
        "clients_retablis": float(clients_total),
        "temps_moyen_coupure_h": round(temps_moyen_par_client, 2),
        "temps_attente_moyen_h": round(attente_moy, 2),
        "temps_route_moyen_h": round(route_moy, 2),
        "temps_depannage_moyen_h": round(dep_moy, 2),
    }


def evaluer_objectif_48h(
    total_clients_crise: int,
    resolutions: list[dict[str, Any]],
    instant_t0: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """
    Évalue l'engagement majeur : 90% des clients rétablis en moins de 48h.

    Retourne :
      - seuil_90_clients : nombre de clients à rétablir pour atteindre 90%
      - t90_heures : délai en heures pour atteindre les 90% (None si non atteint)
      - taux_retabli_48h_pct : pourcentage de clients rétablis en <= 48h
      - objectif_atteint : booléen (True si t90_heures <= 48h)
    """
    if total_clients_crise <= 0:
        return {
            "total_clients_crise": 0,
            "seuil_90_clients": 0,
            "t90_heures": 0.0,
            "taux_retabli_48h_pct": 100.0,
            "objectif_atteint": True,
        }

    seuil_90 = 0.90 * total_clients_crise

    resolutions_triees = sorted(
        resolutions,
        key=lambda r: r.get("instant_resolution") or pd.Timestamp.min,
    )

    cumul = 0
    t90_h = None
    clients_a_48h = 0

    for r in resolutions_triees:
        nb_cl = int(r.get("nb_clients") or 0)
        cumul += nb_cl
        inst_res = r.get("instant_resolution")
        duree_depuis_t0 = (
            max(0.0, (inst_res - instant_t0).total_seconds() / 3600.0)
            if (instant_t0 is not None and inst_res is not None)
            else float(r.get("temps_coupure_total_h") or 0.0)
        )

        if duree_depuis_t0 <= 48.0:
            clients_a_48h += nb_cl

        if cumul >= seuil_90 and t90_h is None:
            t90_h = round(duree_depuis_t0, 2)

    taux_48h = round((clients_a_48h / total_clients_crise) * 100.0, 1)
    objectif_atteint = bool(t90_h is not None and t90_h <= 48.0)

    return {
        "total_clients_crise": total_clients_crise,
        "seuil_90_clients": int(round(seuil_90)),
        "t90_heures": t90_h,
        "taux_retabli_48h_pct": taux_48h,
        "objectif_atteint": objectif_atteint,
    }

