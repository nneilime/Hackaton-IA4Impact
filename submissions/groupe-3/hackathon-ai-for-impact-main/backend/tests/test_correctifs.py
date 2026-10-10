"""Correctifs trouvés en testant des prompts réels : classe en tête de phrase, destinations sans train."""
from datetime import date

import pytest

from app.services import comprendre

AUJ = date(2026, 10, 10)


@pytest.mark.parametrize(
    ("texte", "niveau"),
    [
        ("Seconde, thème sciences et espace, 35 élèves et 3 professeurs, le 14 janvier.", "2de"),
        ("Cinquième, Moyen Âge, 24 élèves et 2 accompagnateurs.", "5e"),
        ("Bonjour. Seconde générale, 30 élèves.", "2de"),
    ],
)
def test_classe_en_tete_de_phrase(texte, niveau):
    assert comprendre.extraire(texte, AUJ)["niveau"] == niveau


def test_destinations_sans_train_ecartees(client):
    texte = ("Classe de CM2, Préhistoire, 26 élèves et 3 accompagnateurs, le jeudi 3 décembre, "
             "au départ de l'école de Pamiers.")
    demande = client.post("/api/chat", json={"messages": [{"role": "user", "content": texte}],
                                             "demande": None}).json()["demande"]
    r = client.post("/api/destinations", json={"demande": demande}).json()
    assert r["destinations"], r["message"]
    assert all(d["indice_confiance"] > 0 for d in r["destinations"])
