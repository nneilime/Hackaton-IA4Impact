"""
Explication des propositions d'affectation pour le dispatcheur, et alternatives après un refus.

Fonctions pures (aucun appel Streamlit) sur un pas ouvert de ``SimulationPasAPas`` :
  - ``expliquer`` : pourquoi cette panne, pourquoi cette équipe, pourquoi pas les autres,
    et ce que la mission engage (heures d'arrivée, de fin, de retour, amplitude) ;
  - ``alternative_pour_equipe`` : la panne suivante que la stratégie confierait à l'équipe ;
  - ``options_libres`` : toutes les pannes en attente pour un choix libre, faisables ou non.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from crise.simulation.moteur import SimulationPasAPas, _trajet_h

LIBELLES_COMPOSANTES = {
    "clients": "Clients coupés",
    "sensibles": "Clients sensibles",
    "duree": "Durée de réparation",
    "proximite": "Proximité d'une équipe",
}


def _sensible(panne: Any) -> bool:
    valeur = pd.to_numeric(panne.get("poste_avec_client_sensible"), errors="coerce")
    return bool(valeur) if not pd.isna(valeur) else False


def _clients(panne: Any) -> int:
    valeur = pd.to_numeric(panne.get("nb_clients"), errors="coerce")
    return 0 if pd.isna(valeur) else int(valeur)


def ordre_priorite(simulation: SimulationPasAPas) -> pd.DataFrame:
    """
    Pannes en attente dans l'ordre où la stratégie les traite, avec leur rang (1 = la plus
    prioritaire) et, pour le score pondéré, le détail du score.
    """
    contexte = simulation.contexte()
    pannes, equipes = contexte["pannes"], contexte["equipes"]
    if pannes.empty:
        return pannes.assign(rang=pd.Series(dtype=int))
    allocateur = simulation.allocateur
    # ia_optimale n'a pas d'ordre explicite : on présente l'ordre par clients coupés.
    strategie = simulation.strategie if simulation.strategie != "ia_optimale" else "distance"
    triees = allocateur._trier(pannes, equipes, strategie)
    if simulation.strategie == "score_pondere":
        triees = triees.join(allocateur.composantes_score(triees, equipes))
    triees = triees.copy()
    triees["rang"] = range(1, len(triees) + 1)
    triees["id_incident"] = triees["id_incident"].astype(str)
    return triees


def _raison_priorite(simulation: SimulationPasAPas, ligne: pd.Series, total: int) -> str:
    raison = _raison_strategie(simulation, ligne, total)
    if _sensible(ligne):
        return "🏥 Lieu sensible : prioritaire sur tous les incidents non sensibles. " + raison
    return raison


def _raison_strategie(simulation: SimulationPasAPas, ligne: pd.Series, total: int) -> str:
    rang = f"rang {int(ligne['rang'])} sur {total} pannes en attente"
    if simulation.strategie == "premier_arrive":
        date = pd.to_datetime(ligne.get("date_incident"), errors="coerce")
        heure = f"apparue à {date:%H:%M}" if not pd.isna(date) else "date inconnue"
        return f"Stratégie « premier arrivé » : les pannes sont traitées dans l'ordre d'apparition ({heure}, {rang})."
    if simulation.strategie == "score_pondere":
        return (
            f"Stratégie « score pondéré » : score {float(ligne['score_priorite']):.2f} "
            f"sur 1 ({rang})."
        )
    if simulation.strategie == "ia_optimale":
        return f"Stratégie « IA optimale » : affectation optimisée globalement ({rang} par clients coupés)."
    return (
        f"Stratégie « distance » : les pannes sont traitées par nombre de clients décroissant "
        f"({_clients(ligne)} clients, {rang})."
    )


def expliquer(
    simulation: SimulationPasAPas,
    id_equipe: str,
    id_incident: str,
    propositions: list[dict[str, Any]] | tuple = (),
    paires_interdites: set[tuple[str, str]] | frozenset = frozenset(),
) -> dict[str, Any]:
    """Explication complète d'une affectation équipe → panne au pas ouvert."""
    id_equipe, id_incident = str(id_equipe), str(id_incident)
    contexte = simulation.contexte()
    instant = contexte["instant"]
    ordre = ordre_priorite(simulation)
    ligne = ordre.loc[ordre["id_incident"] == id_incident].iloc[0]
    equipes = {str(e["id_equipe"]): e for e in contexte["equipes"]}
    equipe = equipes[id_equipe]
    decision = simulation.decision_pour(id_equipe, id_incident)

    # Temps exact (la décision l'arrondit au centième d'heure) pour comparer les équipes.
    trajet_h = _trajet_h(
        equipe.get("latitude"), equipe.get("longitude"),
        ligne.get("latitude"), ligne.get("longitude"),
        simulation.allocateur,
    )
    reparation_h = float(ligne.get("duree_heures") or 0.0)
    retour_h = _trajet_h(
        ligne.get("latitude"), ligne.get("longitude"),
        equipe.get("site_latitude"), equipe.get("site_longitude"),
        simulation.allocateur,
    )
    amplitude_h = simulation.duree_max_h - float(equipe["heures_restantes"])
    besoin_h = trajet_h + reparation_h + retour_h
    arrivee = instant + pd.Timedelta(hours=trajet_h)
    fin = arrivee + pd.Timedelta(hours=reparation_h)

    # Équipes plus proches que celle retenue : pourquoi ne sont-elles pas envoyées ?
    autres_propositions = {
        str(p["id_equipe"]): str(p["id_incident"])
        for p in propositions
        if str(p["id_equipe"]) != id_equipe
    }
    ecartees = []
    for autre_id, autre in equipes.items():
        if autre_id == id_equipe:
            continue
        trajet_autre = _trajet_h(
            autre.get("latitude"), autre.get("longitude"),
            ligne.get("latitude"), ligne.get("longitude"),
            simulation.allocateur,
        )
        if trajet_autre >= trajet_h - 1e-9:
            continue
        retour_autre = _trajet_h(
            ligne.get("latitude"), ligne.get("longitude"),
            autre.get("site_latitude"), autre.get("site_longitude"),
            simulation.allocateur,
        )
        besoin_autre = trajet_autre + reparation_h + retour_autre
        if (autre_id, id_incident) in paires_interdites:
            raison = "refusée pour cette panne par le dispatcheur"
        elif autre_id in autres_propositions:
            raison = f"proposée sur la panne {autres_propositions[autre_id]}, plus prioritaire"
        elif besoin_autre > float(autre["heures_restantes"]) + 1e-9:
            raison = (
                f"amplitude insuffisante : {float(autre['heures_restantes']):.1f} h restantes, "
                f"il en faut {besoin_autre:.1f} (aller + réparation + retour au site)"
            )
        else:
            raison = "disponible ; non retenue par la stratégie à ce tour"
        ecartees.append({"id_equipe": autre_id, "trajet_h": round(trajet_autre, 2), "raison": raison})
    ecartees.sort(key=lambda e: e["trajet_h"])

    composantes = {}
    if simulation.strategie == "score_pondere":
        composantes = {
            LIBELLES_COMPOSANTES[cle]: round(float(ligne[cle]), 3) for cle in LIBELLES_COMPOSANTES
        }

    pourquoi_equipe = (
        f"L'équipe {id_equipe} est à {round(trajet_h * 60)} min de route. "
        + (
            "C'est la plus proche qui peut finir la mission dans son amplitude."
            if not any(e["raison"].startswith("disponible") for e in ecartees)
            else "C'est l'équipe retenue par la stratégie pour cette panne."
        )
    )
    return {
        "id_equipe": id_equipe,
        "id_incident": id_incident,
        "panne": {
            "clients": _clients(ligne),
            "sensible": _sensible(ligne),
            "reparation_h": reparation_h,
            "rang": int(ligne["rang"]),
            "nb_en_attente": len(ordre),
        },
        "pourquoi_panne": _raison_priorite(simulation, ligne, len(ordre)),
        "composantes_score": composantes,
        "pourquoi_equipe": pourquoi_equipe,
        # La proposition de la stratégie porte sa propre justification (SHAP pour l'IA).
        "explication_strategie": next(
            (
                p.get("explication", "")
                for p in propositions
                if (str(p["id_equipe"]), str(p["id_incident"])) == (id_equipe, id_incident)
            ),
            decision.get("explication", ""),
        ),
        "equipes_ecartees": ecartees[:5],
        "engagement": {
            "trajet_h": round(trajet_h, 2),
            "retour_h": round(retour_h, 2),
            "arrivee": arrivee,
            "fin_reparation": fin,
            "retour_site": fin + pd.Timedelta(hours=retour_h),
            "amplitude_avant_h": round(amplitude_h, 2),
            "amplitude_apres_h": round(amplitude_h + besoin_h, 2),
            "amplitude_max_h": simulation.duree_max_h,
        },
    }


def options_libres(
    simulation: SimulationPasAPas,
    id_equipe: str,
    incidents_exclus: set[str] | frozenset = frozenset(),
) -> pd.DataFrame:
    """
    Toutes les pannes en attente pour un choix libre de l'équipe, dans l'ordre de priorité
    de la stratégie, avec trajet, clients, et si la règle des 12 h permet de les prendre.
    """
    colonnes = ["id_incident", "rang", "clients", "sensible", "reparation_h", "trajet_h", "faisable", "raison"]
    ordre = ordre_priorite(simulation)
    lignes = []
    for _, panne in ordre.iterrows():
        identifiant = str(panne["id_incident"])
        if identifiant in incidents_exclus:
            continue
        decision = simulation.decision_pour(id_equipe, identifiant)
        faisable = simulation.mission_faisable(id_equipe, identifiant)
        lignes.append(
            {
                "id_incident": identifiant,
                "rang": int(panne["rang"]),
                "clients": _clients(panne),
                "sensible": _sensible(panne),
                "reparation_h": float(panne.get("duree_heures") or 0.0),
                "trajet_h": float(decision["temps_estime_trajet_heures"]),
                "faisable": faisable,
                "raison": "" if faisable else "dépasserait les 12 h d'amplitude (retour au site compris)",
            }
        )
    return pd.DataFrame(lignes, columns=colonnes)


def alternative_pour_equipe(
    simulation: SimulationPasAPas,
    id_equipe: str,
    incidents_exclus: set[str] | frozenset = frozenset(),
    paires_interdites: set[tuple[str, str]] | frozenset = frozenset(),
) -> dict[str, Any] | None:
    """
    Après un refus : la panne la plus prioritaire (selon la stratégie) que l'équipe peut
    prendre, hors pannes déjà décidées et paires refusées. ``None`` s'il n'y en a pas.
    """
    options = options_libres(simulation, id_equipe, incidents_exclus)
    for option in options.itertuples():
        if not option.faisable or (str(id_equipe), option.id_incident) in paires_interdites:
            continue
        return simulation.decision_pour(id_equipe, option.id_incident)
    return None
