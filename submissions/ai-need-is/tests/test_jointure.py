import pandas as pd

from crise.preparation.jointure import (
    annoter_pannes,
    derouler_equipes,
    filtrer_crise,
    joindre_postes,
    parser_duree,
    preparer_pannes,
    separer_pannes_localisables,
)
from crise.strategies.allocator import comparer_strategies


def test_filtrer_crise_exclut_les_autres():
    coupures = pd.DataFrame(
        [
            {"numero_crise": "CRISE_001", "id_incident": "A", "id_poste": "P1"},
            {"numero_crise": "CRISE_002", "id_incident": "B", "id_poste": "P2"},
        ]
    )

    filtre = filtrer_crise(coupures, "CRISE_001")

    assert filtre["id_incident"].tolist() == ["A"]


def test_joindre_postes_recupere_la_latitude():
    coupures = pd.DataFrame(
        [{"numero_crise": "CRISE_001", "id_incident": "A", "id_poste": "POSTE_1"}]
    )
    postes = pd.DataFrame(
        [
            {
                "id_poste": "POSTE_1",
                "latitude": 43.6,
                "longitude": 1.4,
                "nb_clients": 12,
                "poste_avec_client_sensible": 1,
            }
        ]
    )

    joint = joindre_postes(coupures, postes)

    assert joint.loc[0, "latitude"] == 43.6
    assert joint.loc[0, "nb_clients"] == 12


def test_panne_sans_poste_est_ecartee_et_non_affectee():
    coupures = pd.DataFrame(
        [
            {
                "numero_crise": "CRISE_001",
                "id_incident": "ORPHELINE",
                "id_poste": "INCONNU",
                "dureeDepannage": "4h",
                "dateHeureIncident": "09/01/2016 14:08",
            },
            {
                "numero_crise": "CRISE_001",
                "id_incident": "CONNUE",
                "id_poste": "POSTE_1",
                "dureeDepannage": "8h",
                "dateHeureIncident": "09/01/2016 15:00",
            },
        ]
    )
    postes = pd.DataFrame(
        [
            {
                "id_poste": "POSTE_1",
                "latitude": 43.6,
                "longitude": 1.4,
                "nb_clients": 20,
                "poste_avec_client_sensible": 0,
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "SITE_01_1",
                "id_site": "SITE_01",
                "commune": "Toulouse",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
            }
        ]
    )

    pannes, nb_ecartes, _ = preparer_pannes(coupures, postes, "CRISE_001")
    resultats, _ = comparer_strategies(equipes, pannes, coeff_detour=1.3, vitesse_kmh=60)

    assert nb_ecartes == 1
    assert pannes["id_incident"].tolist() == ["CONNUE"]
    assert resultats["distance"][0]["id_incident"] == "CONNUE"
    assert all(decision["id_incident"] != "ORPHELINE" for decision in resultats["distance"])


def test_site_a_cinq_equipes():
    agents = pd.DataFrame(
        [
            {
                "id_site": "SITE_01",
                "commune": "Foix",
                "latitude": 42.96,
                "longitude": 1.60,
                "nb_equipes": 5,
            }
        ]
    )

    equipes = derouler_equipes(agents)

    assert equipes["id_equipe"].tolist() == [
        "SITE_01_1",
        "SITE_01_2",
        "SITE_01_3",
        "SITE_01_4",
        "SITE_01_5",
    ]
    assert equipes["latitude"].nunique() == 1


def test_parser_duree_4h_et_valeur_inconnue():
    assert parser_duree("4h") == 4.0

    annotees, nb_illisible = annoter_pannes(
        pd.DataFrame([{"dureeDepannage": "4h"}, {"dureeDepannage": "inconnue"}])
    )

    assert annotees["duree_heures"].tolist() == [4.0, 0.0]
    assert nb_illisible == 1


def test_separer_pannes_sans_coordonnees():
    incidents = pd.DataFrame(
        [
            {"id_incident": "A", "latitude": 43.0, "longitude": 1.0},
            {"id_incident": "B", "latitude": None, "longitude": 1.0},
        ]
    )

    gardes, nb_ecartes = separer_pannes_localisables(incidents)

    assert nb_ecartes == 1
    assert gardes["id_incident"].tolist() == ["A"]
