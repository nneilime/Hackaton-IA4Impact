import pandas as pd
import pytest

from crise.geo.distance import calculer_distance_haversine
from crise.simulation.carte import chronologie_carte, incidents_visibles, techniciens_en_route
from crise.simulation.moteur import lancer_simulation

SITE = (43.0, 1.0)
POSTE = (43.5, 1.0)
T0 = pd.Timestamp("2016-01-09 14:00")


def _simuler(heures_deja: float, duree_reparation_h: float) -> tuple[pd.DataFrame, dict]:
    """Une équipe au site, une panne à exactement 1 h de route."""
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "P",
                "latitude": POSTE[0],
                "longitude": POSTE[1],
                "nb_clients": 42,
                "duree_heures": duree_reparation_h,
                "date_incident": T0,
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "latitude": SITE[0],
                "longitude": SITE[1],
                "disponible": True,
                "heures_travaillees": heures_deja,
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=30,
        nb_pas=12,
        coeff_detour=1.0,
        vitesse_kmh=calculer_distance_haversine(*SITE, *POSTE),
    )
    return pannes, resultat


def _a(heures: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(hours=heures)


def test_technicien_visible_et_interpole_pendant_l_aller() -> None:
    _, resultat = _simuler(0.0, 2.0)

    milieu = techniciens_en_route(resultat["trajets"], _a(0.5))
    assert milieu["id_equipe"].tolist() == ["E1"]
    assert milieu.iloc[0]["destination"] == "incident"
    assert milieu.iloc[0]["latitude"] == pytest.approx((SITE[0] + POSTE[0]) / 2)


def test_technicien_disparait_a_l_arrivee_sur_l_incident() -> None:
    _, resultat = _simuler(0.0, 2.0)

    assert techniciens_en_route(resultat["trajets"], _a(1.0)).empty
    assert techniciens_en_route(resultat["trajets"], _a(2.0)).empty


def test_incident_rouge_en_route_orange_sur_place_puis_disparait() -> None:
    pannes, resultat = _simuler(0.0, 2.0)
    interventions = resultat["interventions"]

    assert incidents_visibles(pannes, interventions, _a(0.5)).iloc[0]["statut"] == "en attente"
    assert incidents_visibles(pannes, interventions, _a(1.5)).iloc[0]["statut"] == "en réparation"
    assert incidents_visibles(pannes, interventions, _a(3.0)).empty


def test_technicien_reapparait_sur_le_chemin_du_retour_puis_disparait_au_site() -> None:
    """8 h déjà faites + 1 h aller + 2 h réparation + 1 h retour = 12 h : retour juste après."""
    pannes, resultat = _simuler(8.0, 2.0)

    retour = techniciens_en_route(resultat["trajets"], _a(3.5))
    assert retour["destination"].tolist() == ["site"]
    assert retour.iloc[0]["latitude"] == pytest.approx((SITE[0] + POSTE[0]) / 2)
    assert incidents_visibles(pannes, resultat["interventions"], _a(3.5)).empty
    assert techniciens_en_route(resultat["trajets"], _a(4.0)).empty


def _ms(heures: float) -> int:
    return int(_a(heures).value // 1_000_000)


def test_chronologie_carte_horodate_chaque_etape_de_l_incident() -> None:
    """Le navigateur reçoit apparition, affectation, arrivée et fin, en millisecondes."""
    pannes, resultat = _simuler(8.0, 2.0)
    sites = pd.DataFrame([{"id_site": "S1", "commune": "Ici", "latitude": SITE[0], "longitude": SITE[1]}])

    chrono = chronologie_carte(pannes, resultat, sites)

    (incident,) = chrono["incidents"]
    assert incident == {
        "id": "P",
        "lat": POSTE[0],
        "lon": POSTE[1],
        "clients": 42,
        "date": _ms(0),
        "aff": _ms(0),
        "arr": _ms(1),
        "fin": _ms(3),
    }
    assert [(t["dest"], t["d"], t["a"]) for t in chrono["trajets"]] == [
        ("incident", _ms(0), _ms(1)),
        ("site", _ms(3), _ms(4)),
    ]
    assert chrono["sites"] == [{"id": "S1", "commune": "Ici", "lat": SITE[0], "lon": SITE[1]}]
    assert chrono["debut"] == _ms(0)
    assert chrono["fin"] == _ms(6)  # 12 pas de 30 min


def test_incident_jamais_affecte_reste_sans_horaires() -> None:
    pannes, resultat = _simuler(0.0, 2.0)
    pannes = pd.concat(
        [pannes, pannes.assign(id_incident="FUTUR", date_incident=_a(100))], ignore_index=True
    )

    chrono = chronologie_carte(pannes, resultat)

    futur = next(i for i in chrono["incidents"] if i["id"] == "FUTUR")
    assert (futur["aff"], futur["arr"], futur["fin"]) == (None, None, None)


def test_page_carte_identique_d_une_execution_a_l_autre() -> None:
    """Même HTML à chaque exécution : Streamlit ne recharge pas la carte quand on bouge un curseur."""
    from app.components.carte_techniciens import page_carte

    pannes, resultat = _simuler(0.0, 2.0)

    assert page_carte(pannes, resultat, None) == page_carte(pannes, resultat, None)
    assert "__DONNEES__" not in page_carte(pannes, resultat, None)


def test_incident_futur_invisible() -> None:
    pannes, resultat = _simuler(0.0, 2.0)

    assert incidents_visibles(pannes, resultat["interventions"], _a(-1.0)).empty
