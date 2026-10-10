"""Pilotage humain d'une crise, pas a pas.

Ce module ne change pas les strategies d'affectation. Il ajoute une couche
d'orchestration qui separe explicitement trois operations : proposer une
affectation, faire arbitrer cette proposition par un humain, puis avancer le
temps de simulation.

Le temps et les equipes sont geres par ``SimulationPasAPas`` : memes regles que la
simulation automatique (amplitude de 12 h retour compris, retours au site, repos).

A chaque pas, les recommandations sont presentees une par une, par ordre de priorite :
  - accepter : l'equipe partira sur l'incident a ce pas ;
  - refuser (motif obligatoire) : la paire (equipe, incident) est ecartee, l'incident
    revient dans la file et sera recommande a une autre equipe au meme pas. Pour
    l'equipe, le responsable choisit la suite : l'autre incident propose par le systeme,
    un incident choisi librement, ou la laisser disponible.
Les affectations retenues partent quand le responsable avance au pas suivant.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from crise.simulation.moteur import (
    SimulationPasAPas,
    _identifiant_equipe,
    lancer_simulation,
    pannes_connues,
)
from crise.strategies.allocator import est_sensible


ACTIONS_HUMAINES = ("accepter", "refuser")
SUITES_REFUS = ("autre_incident", "choix_libre", "disponible")
STATUT_SUITE = {
    "autre_incident": "AUTRE_INCIDENT_ACCEPTE",
    "choix_libre": "CHOIX_LIBRE_HUMAIN",
    "disponible": "EQUIPE_LAISSEE_DISPONIBLE",
}
HORIZON_MAX_PAS = 10_000  # le temps n'avance qu'a la demande du responsable


def creer_session_pilotage(
    pannes: pd.DataFrame,
    equipes: pd.DataFrame,
    strategie: str,
    pas_min: int,
    coeff_detour: float,
    vitesse_kmh: float,
    poids: dict[str, float] | None = None,
    duree_max_h: float = 12.0,
    repos_h: float = 11.0,
    plan_preparation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cree un etat de crise sans appliquer automatiquement de recommandation."""
    reglages = {
        "pas_min": int(pas_min),
        "coeff_detour": float(coeff_detour),
        "vitesse_kmh": float(vitesse_kmh),
        "poids": poids,
        "duree_max_h": float(duree_max_h),
        "repos_h": float(repos_h),
    }
    simulation = SimulationPasAPas(pannes, equipes, strategie, nb_pas=HORIZON_MAX_PAS, **reglages)
    reserve = set((plan_preparation or {}).get("equipes_en_reserve", []))
    for equipe in simulation.etats:
        if _identifiant_equipe(equipe) in reserve:
            equipe["etat"] = "en_reserve"
    session = {
        "simulation": simulation,
        "reglages": reglages,
        "t0": simulation.depart,
        "instant": simulation.depart,
        "instant_precedent": None,
        "pas": 0,
        "pas_min": int(pas_min),
        "strategie": strategie,
        "duree_max_h": float(duree_max_h),
        "pannes": pannes.copy(),
        "equipes_initiales": equipes.copy(),
        "pannes_par_id": simulation.pannes_par_id,
        "equipes": simulation.etats,
        "recommandation": None,
        "retenues": [],
        "equipes_decidees": set(),
        "incidents_pris": set(),
        "paires_interdites": set(),
        "journal": [],
        "plan_preparation": deepcopy(plan_preparation),
        "termine": False,
    }
    simulation.ouvrir_pas()
    return session


def _noter(session: dict[str, Any], **entree: Any) -> dict[str, Any]:
    ligne = {
        "id_decision": None,
        "pas": session["pas"] + 1,
        "instant": session["instant"],
        "id_incident": None,
        "equipe_recommandee": None,
        "equipe_retenue": None,
        "incident_retenu": None,
        "statut": "",
        "justification_humaine": "",
        **entree,
    }
    session["journal"].append(ligne)
    return ligne


def liberer_equipes_reserve(
    session: dict[str, Any], ids_equipes: list[str]
) -> list[str]:
    """Rend disponibles des equipes reservees, sur decision humaine explicite."""
    demandees = set(ids_equipes)
    liberees: list[str] = []
    for equipe in session["equipes"]:
        identifiant = _identifiant_equipe(equipe)
        if identifiant in demandees and equipe["etat"] == "en_reserve":
            equipe["etat"] = "libre"
            liberees.append(identifiant)
            _noter(
                session,
                equipe_retenue=identifiant,
                statut="EQUIPE_LIBEREE_PAR_L_HUMAIN",
                justification_humaine="Libération de la réserve opérationnelle",
            )
    if liberees and session["recommandation"] is not None:
        # Une equipe liberee peut etre plus pertinente : la recommandation est recalculee.
        session["journal"] = [
            e for e in session["journal"]
            if e["id_decision"] != session["recommandation"]["id_decision"]
        ]
        session["recommandation"] = None
    return liberees


def _propositions(session: dict[str, Any]) -> list[dict[str, Any]]:
    return session["simulation"].proposer(
        equipes_exclues=session["equipes_decidees"],
        incidents_exclus=session["incidents_pris"],
        paires_interdites=session["paires_interdites"],
    )


def _incident_sensible(session: dict[str, Any], id_incident: str) -> bool:
    incident = session["pannes_par_id"].get(str(id_incident), {})
    valeur = pd.to_numeric(incident.get("poste_avec_client_sensible"), errors="coerce")
    return bool(not pd.isna(valeur) and valeur > 0)


def _reproposition_lieu_sensible(session: dict[str, Any]) -> dict[str, Any] | None:
    """
    Apres le refus d'un lieu sensible : la meilleure autre equipe pour ce seul incident.
    ``None`` si aucune equipe disponible ne peut l'atteindre (il reste alors en alerte).
    """
    refus = session.pop("a_reproposer", None)
    if refus is None:
        return None
    pannes = session["simulation"].contexte()["pannes"]
    autres = set(pannes["id_incident"].astype(str)) - {refus["id_incident"]} if not pannes.empty else set()
    propositions = session["simulation"].proposer(
        equipes_exclues=session["equipes_decidees"],
        incidents_exclus=session["incidents_pris"] | autres,
        paires_interdites=session["paires_interdites"],
    )
    if not propositions:
        return None
    return {**propositions[0], "repropose_apres_refus": refus}


def proposer_recommandation(session: dict[str, Any]) -> dict[str, Any] | None:
    """
    Retourne la recommandation a arbitrer (la plus prioritaire selon la strategie),
    sans demarrer de mission. ``None`` quand tout le pas a ete arbitre.

    Un lieu sensible qui vient d'etre refuse est repropose aussitot a une autre equipe.
    """
    if session.get("recommandation") is not None:
        return session["recommandation"]
    reproposition = _reproposition_lieu_sensible(session)
    propositions = [reproposition] if reproposition is not None else _propositions(session)
    if not propositions:
        return None
    proposition = deepcopy(propositions[0])
    proposition["id_decision"] = f"DEC-{session['pas'] + 1:04d}-{len(session['journal']) + 1:04d}"
    proposition["statut"] = "PROPOSEE_PAR_LE_SYSTEME"
    proposition["instant"] = session["instant"]
    session["recommandation"] = proposition
    _noter(
        session,
        id_decision=proposition["id_decision"],
        id_incident=str(proposition["id_incident"]),
        equipe_recommandee=str(proposition["id_equipe"]),
        statut="PROPOSEE_PAR_LE_SYSTEME",
    )
    return proposition


def _retenir(session: dict[str, Any], decision: dict[str, Any], origine: str) -> None:
    session["retenues"].append({**decision, "origine": origine})
    session["incidents_pris"].add(str(decision["id_incident"]))


def enregistrer_decision_humaine(
    session: dict[str, Any],
    action: str,
    justification: str = "",
    suite: str = "disponible",
    id_incident: str | None = None,
) -> dict[str, Any]:
    """
    Applique l'arbitrage humain a la recommandation affichee.

    ``refuser`` exige une justification ; ``suite`` dit ce que fait l'equipe :
    ``autre_incident`` ou ``choix_libre`` (avec ``id_incident``), ou ``disponible``.
    """
    if action not in ACTIONS_HUMAINES:
        raise ValueError(f"Action inconnue : {action}")
    recommandation = session.get("recommandation")
    if recommandation is None:
        raise ValueError("Aucune recommandation en attente de decision")
    if action == "refuser" and not justification.strip():
        raise ValueError("Une justification est requise pour refuser")
    if action == "refuser" and suite not in SUITES_REFUS:
        raise ValueError(f"Suite inconnue : {suite}")

    simulation: SimulationPasAPas = session["simulation"]
    incident_id = str(recommandation["id_incident"])
    equipe_id = str(recommandation["id_equipe"])

    if action == "accepter":
        _retenir(session, recommandation, "recommandation acceptée")
        session["equipes_decidees"].add(equipe_id)
        entree = _noter(
            session,
            id_decision=recommandation["id_decision"],
            id_incident=incident_id,
            equipe_recommandee=equipe_id,
            equipe_retenue=equipe_id,
            incident_retenu=incident_id,
            statut="ACCEPTEE_PAR_L_HUMAIN",
        )
        session["recommandation"] = None
        return entree

    # Refus : l'incident reste dans la file, mais plus jamais pour cette equipe.
    choisi = None
    if suite in ("autre_incident", "choix_libre"):
        if not id_incident:
            raise ValueError("Choisissez l'incident confie a l'equipe")
        choisi = str(id_incident)
        if choisi == incident_id:
            raise ValueError("L'incident refuse ne peut pas etre redonne a la meme equipe")
        if choisi in session["incidents_pris"]:
            raise ValueError(f"L'incident {choisi} est deja attribue a ce pas")
        if not simulation.mission_faisable(equipe_id, choisi):
            raise ValueError(f"L'equipe {equipe_id} ne peut pas traiter {choisi} dans son amplitude")
    session["paires_interdites"].add((equipe_id, incident_id))
    if _incident_sensible(session, incident_id):
        # Lieu sensible refuse : il sera la toute prochaine recommandation, pour une autre equipe.
        session["a_reproposer"] = {
            "id_incident": incident_id,
            "equipe_refusee": equipe_id,
            "motif": justification.strip(),
        }
    entree = _noter(
        session,
        id_decision=recommandation["id_decision"],
        id_incident=incident_id,
        equipe_recommandee=equipe_id,
        statut="REFUSEE_PAR_L_HUMAIN",
        justification_humaine=justification.strip(),
    )
    if suite == "disponible":
        # L'equipe reste libre : elle peut recevoir une autre recommandation a ce pas.
        _noter(session, id_decision=recommandation["id_decision"], equipe_retenue=equipe_id,
               statut=STATUT_SUITE[suite], justification_humaine=justification.strip())
    else:
        _retenir(session, simulation.decision_pour(equipe_id, choisi), STATUT_SUITE[suite])
        session["equipes_decidees"].add(equipe_id)
        _noter(session, id_decision=recommandation["id_decision"], id_incident=choisi,
               equipe_retenue=equipe_id, incident_retenu=choisi, statut=STATUT_SUITE[suite],
               justification_humaine=justification.strip())
    session["recommandation"] = None
    return entree


def tout_accepter(session: dict[str, Any]) -> int:
    """Accepte toutes les recommandations restantes du pas ; renvoie leur nombre."""
    nombre = 0
    while proposer_recommandation(session) is not None:
        enregistrer_decision_humaine(session, "accepter")
        nombre += 1
    return nombre


def avancer_temps(session: dict[str, Any]) -> list[str]:
    """
    Fait partir les equipes retenues, puis avance d'un pas : missions terminees,
    retours au site, repos. Renvoie les incidents resolus a ce nouveau pas.
    """
    if session.get("recommandation") is not None:
        raise ValueError("La recommandation en attente doit etre arbitree avant d'avancer")
    simulation: SimulationPasAPas = session["simulation"]
    simulation.appliquer(session["retenues"])
    session["instant_precedent"] = session["instant"]
    simulation.ouvrir_pas()
    session["pas"] = simulation.indice
    session["instant"] = simulation.instant
    session["retenues"] = []
    session["a_reproposer"] = None
    session["equipes_decidees"] = set()
    session["incidents_pris"] = set()
    session["paires_interdites"] = set()
    terminees = simulation.contexte()["terminees"]
    for incident_id in terminees:
        _noter(session, id_incident=incident_id, statut="INCIDENT_RESOLU")
    return terminees


def resume_operationnel(session: dict[str, Any]) -> dict[str, Any]:
    """Produit les compteurs necessaires a l'interface Jour J."""
    simulation: SimulationPasAPas = session["simulation"]
    connues = pannes_connues(session["pannes"], session["instant"])
    connus = set(connues["id_incident"].astype(str)) if not connues.empty else set()
    en_mission = {
        str(equipe["mission_id_incident"])
        for equipe in session["equipes"]
        if equipe["etat"] == "en_mission" and equipe.get("mission_id_incident")
    }
    resolues = set(simulation.resolues)
    attente = connus - resolues - en_mission
    clients = {
        str(panne["id_incident"]): int(panne.get("nb_clients") or 0)
        for panne in session["pannes_par_id"].values()
    }
    etats = [equipe["etat"] for equipe in session["equipes"]]
    futures = set(session["pannes_par_id"]) - connus
    return {
        "connues": sorted(connus),
        "en_attente": sorted(attente),
        "en_cours": sorted(en_mission),
        "resolues": sorted(resolues),
        "acceptees_ce_pas": len(session["retenues"]),
        "clients_coupes": sum(clients.get(i, 0) for i in attente | en_mission),
        "clients_retablis": sum(clients.get(i, 0) for i in resolues),
        "equipes_libres": etats.count("libre") + etats.count("retour_base"),
        "equipes_en_mission": etats.count("en_mission"),
        "equipes_au_repos": etats.count("au_repos") + etats.count("retour_site"),
        "equipes_en_reserve": etats.count("en_reserve"),
        "crise_terminee": not attente and not en_mission and not futures,
    }


def lieux_sensibles_en_attente(session: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Lieux sensibles sans equipe partie, du plus ancien au plus recent, avec leur statut :
      - ``retenu`` : une equipe est retenue a ce pas (depart au pas suivant) ;
      - ``recommande`` : c'est la recommandation en cours ;
      - ``hors_atteinte`` : aucune equipe disponible ne peut le faire dans son amplitude ;
      - ``a_traiter`` : il sera recommande a ce pas (apres d'autres lieux sensibles).
    """
    simulation: SimulationPasAPas = session["simulation"]
    contexte = simulation.contexte()
    pannes = contexte["pannes"]
    if pannes.empty:
        return []
    sensibles = pannes.loc[est_sensible(pannes)]
    retenus = {str(d["id_incident"]): str(d["id_equipe"]) for d in session["retenues"]}
    recommande = session.get("recommandation")
    equipes = [
        str(e["id_equipe"]) for e in contexte["equipes"]
        if str(e["id_equipe"]) not in session["equipes_decidees"]
    ]
    lieux = []
    for _, panne in sensibles.iterrows():
        identifiant = str(panne["id_incident"])
        equipe = retenus.get(identifiant)
        if equipe is not None:
            statut = "retenu"
        elif recommande is not None and str(recommande["id_incident"]) == identifiant:
            statut, equipe = "recommande", str(recommande["id_equipe"])
        elif not any(
            simulation.mission_faisable(e, identifiant)
            for e in equipes
            if (e, identifiant) not in session["paires_interdites"]
        ):
            statut = "hors_atteinte"
        else:
            statut = "a_traiter"
        date = pd.to_datetime(panne.get("date_incident"), errors="coerce")
        attente = 0.0 if pd.isna(date) else max((session["instant"] - date) / pd.Timedelta(hours=1), 0.0)
        clients = pd.to_numeric(panne.get("nb_clients"), errors="coerce")
        lieux.append(
            {
                "id_incident": identifiant,
                "clients": 0 if pd.isna(clients) else int(clients),
                "attente_h": round(attente, 1),
                "statut": statut,
                "equipe": equipe,
            }
        )
    return sorted(lieux, key=lambda lieu: -lieu["attente_h"])


def bilan_session(session: dict[str, Any]) -> dict[str, Any]:
    """
    Compare le pilotage humain a la strategie automatique sur les memes pas joues,
    et resume les decisions du responsable.
    """
    simulation: SimulationPasAPas = session["simulation"]
    pilotage = simulation.resultat()
    reference = lancer_simulation(
        session["pannes"],
        session["equipes_initiales"],
        session["strategie"],
        nb_pas=max(simulation.indice, 1),
        **session["reglages"],
    )
    journal = pd.DataFrame(session["journal"])
    statuts = journal["statut"].value_counts() if not journal.empty else pd.Series(dtype=int)
    return {
        "pilotage": pilotage,
        "reference": reference,
        "pas_joues": simulation.indice,
        "decisions": {
            "recommandations": int(statuts.get("PROPOSEE_PAR_LE_SYSTEME", 0)),
            "acceptees": int(statuts.get("ACCEPTEE_PAR_L_HUMAIN", 0)),
            "refusees": int(statuts.get("REFUSEE_PAR_L_HUMAIN", 0)),
            "autre_incident": int(statuts.get("AUTRE_INCIDENT_ACCEPTE", 0)),
            "choix_libres": int(statuts.get("CHOIX_LIBRE_HUMAIN", 0)),
            "laissees_disponibles": int(statuts.get("EQUIPE_LAISSEE_DISPONIBLE", 0)),
        },
    }
