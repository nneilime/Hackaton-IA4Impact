"""Tests de l'explicabilité (T2.5) et des textes modèles (T5.3)."""
import json

import pytest

from crise.copilote.templates import fiche_arbitrage, point_situation
from crise.models import Equipe, Incident, Site
from crise.policies.baselines import PlusProcheFCFS
from crise.simulateur import parametres_simulation, simuler


def trajet(a, b, c, d):
    return 0.0


def test_echange_de_smith():
    """§5.3 : A (150 clients, 8h) avant B (50 clients, 2h) coûte 100 clients·heures de plus."""
    incs = [Incident("A", "PA", 0, 480, 480, "x", 150, False, 43.0, 1.0),
            Incident("B", "PB", 0, 120, 120, "x", 50, False, 43.0, 1.0)]
    res = simuler([Site("S1", "V", 43.0, 1.0, 1)], [Equipe("S1_E1", "S1", 43.0, 1.0)], incs, PlusProcheFCFS(),
                  parametres_simulation(), trajet)
    e = json.loads(res.decisions.loc[0, "explication"])
    assert res.decisions.loc[0, "id_incident"] == "A"          # R1 prend A (arrivé en premier)
    assert e["alternative"]["id_incident"] == "B"
    assert e["alternative"]["delta_clients_heures"] == pytest.approx(-100)   # B d'abord aurait évité 100
    assert e["confiance"] < 0.5
    assert set(e["contributions_pct"]) == {"clients", "sensible", "attente", "trajet", "duree"}
    assert "à discuter" in fiche_arbitrage("S1_E1", "A", e)


def test_point_situation():
    txt = point_situation(150, {"clients_coupes": 1200, "incidents_attente": 8, "equipes_occupees": 40,
                                "equipes_repos": 5}, sensibles_attente=2, tension=["Ariège"])
    assert "1200 clients" in txt and "Ariège" in txt and "H+2h30" in txt
