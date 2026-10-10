import pandas as pd
import pytest

from crise.metrics.indicateurs import (
    calculer_temps_coupure_incident,
    evaluer_fonction_objectif,
    evaluer_objectif_48h,
)


def test_calculer_temps_coupure_incident() -> None:
    t_inc = pd.Timestamp("2026-01-09 10:00:00")
    t_aff = pd.Timestamp("2026-01-09 11:30:00")  # attente = 1.5h
    route = 0.75
    dep = 2.0

    attente, t_route, t_dep, total = calculer_temps_coupure_incident(
        t_inc, t_aff, route, dep
    )

    assert attente == 1.5
    assert t_route == 0.75
    assert t_dep == 2.0
    assert total == 4.25


def test_evaluer_fonction_objectif() -> None:
    resolutions = [
        {
            "id_incident": "P1",
            "nb_clients": 100,
            "temps_attente_h": 1.0,
            "temps_route_h": 0.5,
            "temps_depannage_h": 2.0,
            "temps_coupure_total_h": 3.5,
            "produit_clients_temps": 350.0,
        },
        {
            "id_incident": "P2",
            "nb_clients": 50,
            "temps_attente_h": 2.0,
            "temps_route_h": 1.0,
            "temps_depannage_h": 1.0,
            "temps_coupure_total_h": 4.0,
            "produit_clients_temps": 200.0,
        },
    ]

    res = evaluer_fonction_objectif(resolutions)

    assert res["score_objectif"] == 550.0
    assert res["clients_retablis"] == 150.0
    # Temps moyen par client rétabli : 550 / 150 = 3.67 h
    assert res["temps_moyen_coupure_h"] == 3.67
    assert res["temps_attente_moyen_h"] == 1.5
    assert res["temps_route_moyen_h"] == 0.75
    assert res["temps_depannage_moyen_h"] == 1.5


def test_evaluer_objectif_48h() -> None:
    t0 = pd.Timestamp("2026-01-09 08:00:00")
    total_clients = 1000  # seuil 90% = 900 clients

    resolutions = [
        {
            "nb_clients": 500,
            "instant_resolution": t0 + pd.Timedelta(hours=10),
        },
        {
            "nb_clients": 450,
            "instant_resolution": t0 + pd.Timedelta(hours=25),
        },
        {
            "nb_clients": 50,
            "instant_resolution": t0 + pd.Timedelta(hours=50),
        },
    ]

    res = evaluer_objectif_48h(total_clients, resolutions, instant_t0=t0)

    assert res["total_clients_crise"] == 1000
    assert res["seuil_90_clients"] == 900
    # Les 900 clients sont atteints lors de la 2e résolution à 25h
    assert res["t90_heures"] == 25.0
    assert res["objectif_atteint"] is True
    # À 48h, 500 + 450 = 950 clients ont été rétablis (95.0%)
    assert res["taux_retabli_48h_pct"] == 95.0

