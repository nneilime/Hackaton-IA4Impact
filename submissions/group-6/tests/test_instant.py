"""Tests de l'état à l'instant t (carte animée)."""
import pytest

from crise.instant import equipes_a, incidents_a, ligne_serie
from crise.models import Equipe, Incident, Site
from crise.policies.baselines import PlusProcheFCFS
from crise.simulateur import parametres_simulation, simuler


def trajet(lat1, lon1, lat2, lon2):
    return abs(lat1 - lat2) * 100


@pytest.fixture
def res():
    incs = [Incident("A", "PA", 0, 120, 120, "x", 50, True, 44.0, 1.0),
            Incident("B", "PB", 60, 120, 120, "x", 30, False, 43.0, 1.0)]
    return simuler([Site("S1", "V", 43.0, 1.0, 1)], [Equipe("S1_E1", "S1", 43.0, 1.0)], incs, PlusProcheFCFS(),
                   parametres_simulation(), trajet)


def test_etats(res):
    e = incidents_a(res, 30).set_index("id_incident")["etat"]
    assert e["A"] == "en intervention" and e["B"] == "à venir"
    e = incidents_a(res, 90).set_index("id_incident")["etat"]
    assert e["B"] == "en attente"
    e = incidents_a(res, 10_000).set_index("id_incident")["etat"]
    assert (e == "rétabli").all()


def test_positions(res):
    p = equipes_a(res, 50).iloc[0]                       # à mi-trajet vers A (100 min de trajet)
    assert p["activite"] == "trajet" and p["lat"] == pytest.approx(43.5)
    p = equipes_a(res, 150).iloc[0]
    assert p["activite"] == "chantier" and p["lat"] == pytest.approx(44.0)
    assert ligne_serie(res, 45)["t"] == 30
