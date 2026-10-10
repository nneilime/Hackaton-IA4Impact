import pandas as pd
import pytest

from crise.strategies.ia_optimizer import IAOptimizer
from crise.strategies.allocator import IncidentAllocator, STRATEGIES


def test_ia_optimizer_affecte_sans_conflit() -> None:
    equipes = [
        {"id_equipe": "EQ_1", "latitude": 43.6, "longitude": 1.44, "disponible": True},
        {"id_equipe": "EQ_2", "latitude": 43.7, "longitude": 1.40, "disponible": True},
    ]
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "P_1",
                "latitude": 43.61,
                "longitude": 1.45,
                "nb_clients": 200,
                "duree_heures": 1.0,
                "poste_avec_client_sensible": False,
            },
            {
                "id_incident": "P_2",
                "latitude": 43.69,
                "longitude": 1.41,
                "nb_clients": 50,
                "duree_heures": 2.0,
                "poste_avec_client_sensible": True,
            },
        ]
    )

    optimizer = IAOptimizer(coeff_detour=1.3, vitesse_kmh=60.0)
    decisions = optimizer.affecter(equipes, pannes)

    assert len(decisions) == 2
    equipes_affectees = {d["id_equipe"] for d in decisions}
    assert len(equipes_affectees) == 2  # chaque équipe a un incident unique
    incidents_affectes = {d["id_incident"] for d in decisions}
    assert incidents_affectes == {"P_1", "P_2"}


def test_allocator_integre_ia_optimale() -> None:
    assert "ia_optimale" in STRATEGIES

    eq_df = pd.DataFrame(
        [
            {"id_equipe": "E1", "latitude": 43.6, "longitude": 1.44, "disponible": True},
        ]
    )
    inc_df = pd.DataFrame(
        [
            {"id_incident": "I1", "latitude": 43.61, "longitude": 1.45, "nb_clients": 100, "duree_heures": 1.0},
        ]
    )

    allocator = IncidentAllocator(coeff_detour=1.3, vitesse_kmh=60.0)
    decisions = allocator.affecter_incidents(eq_df, inc_df, strategie="ia_optimale")

    assert len(decisions) == 1
    assert decisions[0]["strategie"] == "ia_optimale"
    assert decisions[0]["id_incident"] == "I1"
    assert decisions[0]["id_equipe"] == "E1"


def test_ia_optimizer_shap_explications() -> None:
    optimizer = IAOptimizer()
    equipes = [{"id_equipe": "EQ_1", "latitude": 43.6, "longitude": 1.44, "disponible": True}]
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "P_SENS",
                "latitude": 43.61,
                "longitude": 1.45,
                "nb_clients": 120,
                "duree_heures": 3.0,
                "poste_avec_client_sensible": True,
            }
        ]
    )
    decisions = optimizer.affecter(equipes, pannes)
    assert len(decisions) == 1
    d = decisions[0]
    assert "shap_valeurs" in d
    shap_vals = d["shap_valeurs"]
    assert "Clients impactés" in shap_vals
    assert "Poste sensible (Hôpital/EHPAD)" in shap_vals
    assert "Temps de trajet (h)" in shap_vals
    # Pour un poste sensible, la valeur SHAP du poste sensible doit être positive
    assert shap_vals["Poste sensible (Hôpital/EHPAD)"] > 0
    # Vérification explications textuelles : le champ existe et n'est pas vide
    assert "explication_shap" in d
    assert isinstance(d["explication_shap"], str) and len(d["explication_shap"]) > 0
    # Le texte d'explication doit contenir au moins une contribution SHAP positive
    assert "pts" in d["explication"]

