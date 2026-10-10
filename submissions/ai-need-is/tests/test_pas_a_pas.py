import pandas as pd
import pytest

from crise.simulation.moteur import SimulationPasAPas, lancer_simulation

T0 = pd.Timestamp("2016-01-09 14:00")


def _pannes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id_incident": "GROS", "latitude": 43.60, "longitude": 1.44, "nb_clients": 500,
             "duree_heures": 2.0, "date_incident": T0},
            {"id_incident": "PETIT", "latitude": 43.70, "longitude": 1.50, "nb_clients": 10,
             "duree_heures": 2.0, "date_incident": T0},
            {"id_incident": "LOIN", "latitude": 48.85, "longitude": 2.35, "nb_clients": 50,
             "duree_heures": 8.0, "date_incident": T0},
        ]
    )


def _equipes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id_equipe": "A", "id_site": "SA", "latitude": 43.61, "longitude": 1.44, "disponible": True},
            {"id_equipe": "B", "id_site": "SB", "latitude": 43.71, "longitude": 1.50, "disponible": True},
        ]
    )


def _simulation(nb_pas: int = 4) -> SimulationPasAPas:
    return SimulationPasAPas(
        _pannes(), _equipes(), "distance", pas_min=30, nb_pas=nb_pas, coeff_detour=1.3, vitesse_kmh=60.0
    )


def _couples(decisions: list[dict]) -> set[tuple[str, str]]:
    return {(str(d["id_equipe"]), str(d["id_incident"])) for d in decisions}


def test_tout_accepter_donne_le_meme_resultat_que_le_mode_automatique() -> None:
    simulation = _simulation(nb_pas=12)
    while not simulation.termine:
        simulation.appliquer(simulation.ouvrir_pas())
    pas_a_pas = simulation.resultat()

    automatique = lancer_simulation(
        _pannes(), _equipes(), "distance", pas_min=30, nb_pas=12, coeff_detour=1.3, vitesse_kmh=60.0
    )

    assert [p["affectations"] for p in pas_a_pas["pas"]] == [p["affectations"] for p in automatique["pas"]]
    assert pas_a_pas["trajets"] == automatique["trajets"]
    assert pas_a_pas["indicateurs"] == automatique["indicateurs"]


def test_propositions_du_premier_pas() -> None:
    propositions = _simulation().ouvrir_pas()

    # « distance » traite d'abord le plus de clients, avec l'équipe la plus proche.
    # LOIN est hors d'atteinte en 12 h (aller + 8 h + retour) : personne ne la reçoit.
    assert _couples(propositions) == {("A", "GROS"), ("B", "PETIT")}


def test_paire_refusee_n_est_plus_proposee() -> None:
    simulation = _simulation()
    simulation.ouvrir_pas()

    propositions = simulation.proposer(paires_interdites={("A", "GROS")})

    assert ("A", "GROS") not in _couples(propositions)
    assert ("B", "GROS") in _couples(propositions)


def test_exclusions_d_equipes_et_de_pannes_deja_decidees() -> None:
    simulation = _simulation()
    simulation.ouvrir_pas()

    propositions = simulation.proposer(equipes_exclues={"A"}, incidents_exclus={"GROS"})

    assert _couples(propositions) == {("B", "PETIT")}


def test_choix_libre_applique_et_faisabilite() -> None:
    simulation = _simulation()
    simulation.ouvrir_pas()

    assert simulation.mission_faisable("A", "PETIT")
    assert not simulation.mission_faisable("A", "LOIN")

    choix = simulation.decision_pour("A", "PETIT")
    demarrees = simulation.appliquer([choix])

    assert _couples(demarrees) == {("A", "PETIT")}
    equipes = {e["id_equipe"]: e["etat"] for e in simulation.historique[0]["equipes"]}
    assert equipes["A"] == "en_mission"
    assert equipes["B"] == "libre"


def test_ordre_des_appels_controle() -> None:
    simulation = _simulation(nb_pas=1)
    with pytest.raises(RuntimeError):
        simulation.appliquer([])
    simulation.ouvrir_pas()
    with pytest.raises(RuntimeError):
        simulation.ouvrir_pas()
    simulation.appliquer([])
    assert simulation.termine
    with pytest.raises(RuntimeError):
        simulation.ouvrir_pas()
