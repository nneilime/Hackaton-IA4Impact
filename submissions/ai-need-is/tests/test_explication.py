import pandas as pd
import pytest

from crise.simulation.explication import (
    alternative_pour_equipe,
    expliquer,
    options_libres,
    ordre_priorite,
)
from crise.simulation.moteur import SimulationPasAPas
from tests.test_pas_a_pas import _equipes, _pannes


def _ouvert(strategie: str = "distance") -> tuple[SimulationPasAPas, list[dict]]:
    simulation = SimulationPasAPas(
        _pannes(), _equipes(), strategie, pas_min=30, nb_pas=4, coeff_detour=1.3, vitesse_kmh=60.0
    )
    return simulation, simulation.ouvrir_pas()


def test_explication_de_la_proposition() -> None:
    simulation, propositions = _ouvert()

    explication = expliquer(simulation, "A", "GROS", propositions)

    assert explication["panne"]["clients"] == 500
    assert explication["panne"]["rang"] == 1
    assert "clients décroissant" in explication["pourquoi_panne"]
    assert explication["equipes_ecartees"] == []  # B est plus loin de GROS que A
    engagement = explication["engagement"]
    besoin = engagement["trajet_h"] + 2.0 + engagement["retour_h"]
    assert engagement["amplitude_apres_h"] == pytest.approx(engagement["amplitude_avant_h"] + besoin, abs=0.02)
    assert engagement["fin_reparation"] == engagement["arrivee"] + pd.Timedelta(hours=2)


def test_equipe_plus_proche_refusee_est_expliquee() -> None:
    simulation, _ = _ouvert()
    refus = {("A", "GROS")}
    propositions = simulation.proposer(paires_interdites=refus)

    explication = expliquer(simulation, "B", "GROS", propositions, refus)

    (ecartee,) = explication["equipes_ecartees"]
    assert ecartee["id_equipe"] == "A"
    assert "refusée" in ecartee["raison"]


def test_options_libres_signalent_les_pannes_hors_amplitude() -> None:
    simulation, _ = _ouvert()

    options = options_libres(simulation, "A").set_index("id_incident")

    assert list(options.index) == ["GROS", "LOIN", "PETIT"]  # ordre par clients décroissant
    assert options.loc["GROS", "faisable"] and options.loc["PETIT", "faisable"]
    assert not options.loc["LOIN", "faisable"]
    assert "12 h" in options.loc["LOIN", "raison"]


def test_alternative_apres_refus() -> None:
    simulation, _ = _ouvert()

    alternative = alternative_pour_equipe(simulation, "A", incidents_exclus={"GROS"})
    assert alternative["id_incident"] == "PETIT"

    assert alternative_pour_equipe(simulation, "A", paires_interdites={("A", "GROS"), ("A", "PETIT")}) is None


def test_score_pondere_detaille() -> None:
    simulation, propositions = _ouvert("score_pondere")
    ordre = ordre_priorite(simulation)

    for _, ligne in ordre.iterrows():
        somme = ligne["clients"] + ligne["sensibles"] + ligne["duree"] + ligne["proximite"]
        assert somme == pytest.approx(ligne["score_priorite"])

    proposition = propositions[0]
    explication = expliquer(simulation, proposition["id_equipe"], proposition["id_incident"], propositions)
    assert set(explication["composantes_score"]) == {
        "Clients coupés", "Clients sensibles", "Durée de réparation", "Proximité d'une équipe",
    }
