import pandas as pd
import pytest

from crise.simulation.moteur import lancer_simulation
from crise.simulation.pilotage import (
    avancer_temps,
    bilan_session,
    creer_session_pilotage,
    enregistrer_decision_humaine,
    liberer_equipes_reserve,
    proposer_recommandation,
    tout_accepter,
)


def _pannes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_incident": "I1",
                "id_poste": "P1",
                "latitude": 43.61,
                "longitude": 1.45,
                "nb_clients": 100,
                "poste_avec_client_sensible": 0,
                "duree_heures": 1.0,
                "date_incident": pd.Timestamp("2026-01-01 08:00"),
            }
        ]
    )


def _pannes_deux() -> pd.DataFrame:
    seconde = {**_pannes().iloc[0].to_dict(), "id_incident": "I2", "id_poste": "P2",
               "latitude": 43.63, "longitude": 1.47, "nb_clients": 20}
    return pd.concat([_pannes(), pd.DataFrame([seconde])], ignore_index=True)


def _equipes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "commune": "Toulouse",
                "latitude": 43.60,
                "longitude": 1.44,
                "disponible": True,
            },
            {
                "id_equipe": "E2",
                "id_site": "S2",
                "commune": "Balma",
                "latitude": 43.62,
                "longitude": 1.46,
                "disponible": True,
            },
        ]
    )


def _session(pannes: pd.DataFrame | None = None) -> dict:
    return creer_session_pilotage(
        _pannes() if pannes is None else pannes, _equipes(), "distance", 30, 1.3, 60.0
    )


def _en_mission(session: dict) -> dict[str, str]:
    return {
        e["id_equipe"]: e["mission_id_incident"]
        for e in session["equipes"]
        if e["etat"] == "en_mission"
    }


def test_recommandation_n_est_pas_executee_automatiquement() -> None:
    session = _session()
    proposition = proposer_recommandation(session)
    assert proposition is not None
    assert all(equipe["etat"] == "libre" for equipe in session["equipes"])
    assert session["journal"][-1]["statut"] == "PROPOSEE_PAR_LE_SYSTEME"


def test_acceptation_humaine_fait_partir_l_equipe_au_pas_suivant() -> None:
    session = _session()
    proposition = proposer_recommandation(session)
    entree = enregistrer_decision_humaine(session, "accepter")
    assert entree["statut"] == "ACCEPTEE_PAR_L_HUMAIN"
    assert proposer_recommandation(session) is None  # tout le pas est arbitré

    avancer_temps(session)

    assert _en_mission(session) == {proposition["id_equipe"]: "I1"}


def test_refus_exige_une_justification() -> None:
    session = _session()
    proposer_recommandation(session)
    with pytest.raises(ValueError, match="justification"):
        enregistrer_decision_humaine(session, "refuser")


def test_incident_refuse_repropose_a_une_autre_equipe_au_meme_pas() -> None:
    session = _session()
    premiere = proposer_recommandation(session)
    enregistrer_decision_humaine(session, "refuser", "Acces dangereux", suite="disponible")
    assert all(equipe["etat"] == "libre" for equipe in session["equipes"])

    seconde = proposer_recommandation(session)

    assert seconde["id_incident"] == "I1"
    assert seconde["id_equipe"] != premiere["id_equipe"]
    statuts = [e["statut"] for e in session["journal"]]
    assert "REFUSEE_PAR_L_HUMAIN" in statuts and "EQUIPE_LAISSEE_DISPONIBLE" in statuts


def test_refus_puis_autre_incident_pour_l_equipe() -> None:
    session = _session(_pannes_deux())
    premiere = proposer_recommandation(session)
    assert premiere["id_incident"] == "I1"  # plus de clients
    equipe = premiere["id_equipe"]

    enregistrer_decision_humaine(session, "refuser", "Poste inaccessible", suite="autre_incident", id_incident="I2")
    seconde = proposer_recommandation(session)  # I1 pour l'autre équipe
    assert (seconde["id_incident"], seconde["id_equipe"]) == ("I1", "E2" if equipe == "E1" else "E1")
    enregistrer_decision_humaine(session, "accepter")
    avancer_temps(session)

    assert _en_mission(session)[equipe] == "I2"
    assert session["journal"][-3]["statut"] in {"AUTRE_INCIDENT_ACCEPTE", "ACCEPTEE_PAR_L_HUMAIN"}


def test_choix_libre_refuse_l_incident_deja_pris_ou_refuse() -> None:
    session = _session(_pannes_deux())
    premiere = proposer_recommandation(session)
    with pytest.raises(ValueError, match="meme equipe"):
        enregistrer_decision_humaine(session, "refuser", "motif", suite="choix_libre",
                                     id_incident=premiere["id_incident"])
    with pytest.raises(ValueError, match="Choisissez"):
        enregistrer_decision_humaine(session, "refuser", "motif", suite="choix_libre")


def test_tout_accepter_reproduit_la_simulation_automatique() -> None:
    session = _session(_pannes_deux())
    for _ in range(6):
        tout_accepter(session)
        avancer_temps(session)

    automatique = lancer_simulation(_pannes_deux(), _equipes(), "distance", 30, 6, 1.3, 60.0)
    def affectations(pas: list[dict]) -> list[list[tuple]]:
        return [
            [(a["id_equipe"], str(a["id_incident"]), a["temps_estime_trajet_heures"]) for a in p["affectations"]]
            for p in pas
        ]

    assert affectations(session["simulation"].historique) == affectations(automatique["pas"])
    assert session["simulation"].trajets == automatique["trajets"]

    bilan = bilan_session(session)
    assert bilan["pas_joues"] == 6
    assert bilan["pilotage"]["indicateurs"] == bilan["reference"]["indicateurs"]
    assert bilan["decisions"]["acceptees"] == bilan["decisions"]["recommandations"] == 2


def test_plan_humain_met_une_equipe_en_reserve_jusqu_a_sa_liberation() -> None:
    session = creer_session_pilotage(
        _pannes(),
        _equipes(),
        "distance",
        30,
        1.3,
        60.0,
        plan_preparation={"equipes_en_reserve": ["E1"]},
    )
    e1 = next(e for e in session["equipes"] if e["id_equipe"] == "E1")
    assert e1["etat"] == "en_reserve"
    assert proposer_recommandation(session)["id_equipe"] == "E2"
    assert liberer_equipes_reserve(session, ["E1"]) == ["E1"]
    assert e1["etat"] == "libre"
    assert session["journal"][-1]["statut"] == "EQUIPE_LIBEREE_PAR_L_HUMAIN"
