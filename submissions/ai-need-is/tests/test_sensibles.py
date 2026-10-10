"""Priorité absolue aux lieux sensibles, pour toutes les stratégies."""

import pandas as pd
import pytest

from crise.simulation.explication import expliquer
from crise.simulation.pilotage import (
    creer_session_pilotage,
    enregistrer_decision_humaine,
    lieux_sensibles_en_attente,
    proposer_recommandation,
)
from crise.strategies.allocator import STRATEGIES, IncidentAllocator

T0 = pd.Timestamp("2016-01-09 14:00")


def _incident(identifiant: str, lat: float, lon: float, clients: int, sensible: int, minutes: int = 0) -> dict:
    return {
        "id_incident": identifiant,
        "id_poste": f"P_{identifiant}",
        "latitude": lat,
        "longitude": lon,
        "nb_clients": clients,
        "poste_avec_client_sensible": sensible,
        "duree_heures": 2.0,
        "date_incident": T0 + pd.Timedelta(minutes=minutes),
    }


def _equipe(identifiant: str, lat: float, lon: float) -> dict:
    return {"id_equipe": identifiant, "id_site": f"S_{identifiant}", "commune": "Site",
            "latitude": lat, "longitude": lon, "disponible": True}


def _ids(decisions: list[dict]) -> list[str]:
    return [str(d["id_incident"]) for d in decisions]


@pytest.mark.parametrize("strategie", STRATEGIES)
def test_une_seule_equipe_va_au_lieu_sensible(strategie: str) -> None:
    """Gros incident non sensible tout proche, petit lieu sensible plus loin et plus récent."""
    incidents = pd.DataFrame(
        [
            _incident("GROS", 43.60, 1.44, clients=500, sensible=0),
            _incident("HOPITAL", 43.80, 1.60, clients=5, sensible=1, minutes=20),
        ]
    )
    equipes = pd.DataFrame([_equipe("E1", 43.60, 1.44)])

    decisions = IncidentAllocator(1.3, 60.0).affecter_incidents(equipes, incidents, strategie)

    assert _ids(decisions) == ["HOPITAL"]


@pytest.mark.parametrize("strategie", ["distance", "premier_arrive", "score_pondere"])
def test_sensibles_servis_d_abord_dans_l_ordre_de_la_strategie(strategie: str) -> None:
    incidents = pd.DataFrame(
        [
            _incident("NORMAL", 43.60, 1.44, clients=900, sensible=0),
            _incident("EHPAD_PETIT", 43.70, 1.50, clients=10, sensible=1, minutes=0),
            _incident("EHPAD_GROS", 43.72, 1.52, clients=80, sensible=1, minutes=10),
        ]
    )
    equipes = pd.DataFrame([_equipe("E1", 43.60, 1.44), _equipe("E2", 43.61, 1.45)])

    decisions = IncidentAllocator(1.3, 60.0).affecter_incidents(equipes, incidents, strategie)

    assert set(_ids(decisions)) == {"EHPAD_PETIT", "EHPAD_GROS"}
    attendu = ["EHPAD_PETIT", "EHPAD_GROS"] if strategie == "premier_arrive" else ["EHPAD_GROS", "EHPAD_PETIT"]
    assert _ids(decisions) == attendu


def test_lieu_sensible_hors_d_atteinte_ne_bloque_pas_les_autres() -> None:
    incidents = pd.DataFrame(
        [
            _incident("NORMAL", 43.60, 1.44, clients=50, sensible=0),
            _incident("HOPITAL_PARIS", 48.85, 2.35, clients=5, sensible=1),
        ]
    )
    equipe = {**_equipe("E1", 43.60, 1.44), "heures_restantes": 12.0,
              "site_latitude": 43.60, "site_longitude": 1.44}

    decisions = IncidentAllocator(1.3, 60.0).affecter_incidents(pd.DataFrame([equipe]), incidents, "distance")

    assert _ids(decisions) == ["NORMAL"]


def test_sans_lieu_sensible_l_ordre_ne_change_pas() -> None:
    incidents = pd.DataFrame(
        [
            _incident("A", 43.60, 1.44, clients=10, sensible=0),
            _incident("B", 43.70, 1.50, clients=300, sensible=0),
            _incident("C", 43.65, 1.47, clients=100, sensible=0),
        ]
    )
    allocateur = IncidentAllocator(1.3, 60.0)

    tries = allocateur._trier(incidents, [], "distance")

    assert list(tries["id_incident"]) == ["B", "C", "A"]


def test_jour_j_recommande_d_abord_le_lieu_sensible_et_l_explique() -> None:
    pannes = pd.DataFrame(
        [
            _incident("GROS", 43.60, 1.44, clients=500, sensible=0),
            _incident("HOPITAL", 43.80, 1.60, clients=5, sensible=1),
        ]
    )
    equipes = pd.DataFrame([_equipe("E1", 43.60, 1.44), _equipe("E2", 43.62, 1.46)])
    session = creer_session_pilotage(pannes, equipes, "distance", 30, 1.3, 60.0)

    recommandation = proposer_recommandation(session)

    assert recommandation["id_incident"] == "HOPITAL"
    explication = expliquer(session["simulation"], recommandation["id_equipe"], "HOPITAL", [recommandation])
    assert explication["pourquoi_panne"].startswith("🏥 Lieu sensible : prioritaire")
    assert explication["panne"]["rang"] == 1


@pytest.mark.parametrize("strategie", STRATEGIES)
@pytest.mark.parametrize("suite", ["disponible", "autre_incident"])
def test_lieu_sensible_refuse_repropose_aussitot_a_une_autre_equipe(strategie: str, suite: str) -> None:
    """Deux lieux sensibles : après refus du premier, c'est encore lui qui est recommandé."""
    pannes = pd.DataFrame(
        [
            _incident("GROS", 43.60, 1.44, clients=500, sensible=0),
            _incident("HOPITAL", 43.80, 1.60, clients=200, sensible=1),
            _incident("EHPAD", 43.62, 1.46, clients=5, sensible=1),
        ]
    )
    equipes = pd.DataFrame(
        [_equipe("E1", 43.78, 1.58), _equipe("E2", 43.62, 1.46), _equipe("E3", 43.70, 1.50)]
    )
    session = creer_session_pilotage(pannes, equipes, strategie, 30, 1.3, 60.0)
    premiere = proposer_recommandation(session)
    assert premiere["id_incident"] in {"HOPITAL", "EHPAD"}
    refuse, equipe_refusee = str(premiere["id_incident"]), str(premiere["id_equipe"])
    autre = "EHPAD" if refuse == "HOPITAL" else "HOPITAL"

    enregistrer_decision_humaine(
        session, "refuser", "Accès impossible", suite=suite,
        id_incident="GROS" if suite == "autre_incident" else None,
    )
    seconde = proposer_recommandation(session)

    assert seconde["id_incident"] == refuse
    assert seconde["id_equipe"] != equipe_refusee
    assert seconde["repropose_apres_refus"]["equipe_refusee"] == equipe_refusee
    enregistrer_decision_humaine(session, "accepter")
    # Ensuite, le déroulé normal reprend (l'autre lieu sensible d'abord).
    assert proposer_recommandation(session)["id_incident"] == autre


def test_lieu_sensible_refuse_sans_autre_equipe_capable() -> None:
    pannes = pd.DataFrame(
        [
            _incident("GROS", 43.60, 1.44, clients=500, sensible=0),
            _incident("HOPITAL", 43.80, 1.60, clients=5, sensible=1),
        ]
    )
    session = creer_session_pilotage(pannes, pd.DataFrame([_equipe("E1", 43.60, 1.44)]), "distance", 30, 1.3, 60.0)
    proposer_recommandation(session)

    enregistrer_decision_humaine(session, "refuser", "Sécurité", suite="disponible")

    # Seule équipe, refusée pour l'hôpital : elle reçoit l'incident suivant, l'hôpital reste en alerte.
    assert proposer_recommandation(session)["id_incident"] == "GROS"
    assert _statuts(session) == {"HOPITAL": "hors_atteinte"}


def _statuts(session: dict) -> dict[str, str]:
    return {lieu["id_incident"]: lieu["statut"] for lieu in lieux_sensibles_en_attente(session)}


def test_statut_des_lieux_sensibles_dans_le_jour_j() -> None:
    pannes = pd.DataFrame(
        [
            _incident("GROS", 43.60, 1.44, clients=500, sensible=0),
            _incident("HOPITAL", 43.80, 1.60, clients=5, sensible=1),
            _incident("EHPAD_PARIS", 48.85, 2.35, clients=30, sensible=1),
        ]
    )
    equipes = pd.DataFrame([_equipe("E1", 43.60, 1.44), _equipe("E2", 43.62, 1.46)])
    session = creer_session_pilotage(pannes, equipes, "distance", 30, 1.3, 60.0)

    recommandation = proposer_recommandation(session)
    assert recommandation["id_incident"] == "HOPITAL"
    assert _statuts(session) == {"HOPITAL": "recommande", "EHPAD_PARIS": "hors_atteinte"}

    enregistrer_decision_humaine(session, "accepter")
    assert _statuts(session) == {"HOPITAL": "retenu", "EHPAD_PARIS": "hors_atteinte"}
    # Le lieu sensible hors d'atteinte ne bloque pas les autres incidents.
    assert proposer_recommandation(session)["id_incident"] == "GROS"
