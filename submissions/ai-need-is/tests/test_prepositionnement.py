"""Tests unitaires pour crise/preparation/prepositionnement.py."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from crise.preparation.prepositionnement import (
    calculer_barycentre_incidents,
    recommander_prepositionnement,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _incidents(rows: list[dict]) -> pd.DataFrame:
    """Construit un DataFrame d'incidents minimal."""
    return pd.DataFrame(rows)


def _equipes(rows: list[dict]) -> pd.DataFrame:
    """Construit un DataFrame d'équipes minimal."""
    return pd.DataFrame(rows)


# ─── calculer_barycentre_incidents ────────────────────────────────────────────

class TestCalculerBarycentreIncidents:

    def test_dataframe_vide_retourne_nan(self):
        lat, lon = calculer_barycentre_incidents(pd.DataFrame())
        assert math.isnan(lat)
        assert math.isnan(lon)

    def test_sans_coordonnees_valides_retourne_nan(self):
        df = _incidents([{"latitude": None, "longitude": None, "nb_clients": 10}])
        lat, lon = calculer_barycentre_incidents(df)
        assert math.isnan(lat)
        assert math.isnan(lon)

    def test_deux_incidents_equiponderes_donne_point_median(self):
        """Deux incidents avec le même nb_clients → barycentre = point médian."""
        df = _incidents([
            {"latitude": 44.0, "longitude": 2.0, "nb_clients": 100},
            {"latitude": 46.0, "longitude": 4.0, "nb_clients": 100},
        ])
        lat, lon = calculer_barycentre_incidents(df)
        assert abs(lat - 45.0) < 1e-9
        assert abs(lon - 3.0) < 1e-9

    def test_poids_asymetrique_tire_vers_incident_plus_peuple(self):
        """Incident B pèse 3× plus que A → barycentre plus proche de B."""
        df = _incidents([
            {"latitude": 44.0, "longitude": 2.0, "nb_clients": 100},
            {"latitude": 48.0, "longitude": 2.0, "nb_clients": 300},
        ])
        lat, lon = calculer_barycentre_incidents(df)
        # Barycentre = (44*100 + 48*300) / 400 = (4400 + 14400)/400 = 47.0
        assert abs(lat - 47.0) < 1e-9

    def test_sans_colonne_nb_clients_utilise_poids_1(self):
        """Quand nb_clients est absent, chaque incident a poids=1 → moyenne simple."""
        df = _incidents([
            {"latitude": 44.0, "longitude": 2.0},
            {"latitude": 46.0, "longitude": 4.0},
        ])
        lat, lon = calculer_barycentre_incidents(df)
        assert abs(lat - 45.0) < 1e-9
        assert abs(lon - 3.0) < 1e-9

    def test_colonne_nb_clients_nuls_utilise_poids_1(self):
        """Si tous les nb_clients sont 0, utilise poids=1 (pas de division par zéro)."""
        df = _incidents([
            {"latitude": 44.0, "longitude": 2.0, "nb_clients": 0},
            {"latitude": 46.0, "longitude": 4.0, "nb_clients": 0},
        ])
        lat, lon = calculer_barycentre_incidents(df)
        assert abs(lat - 45.0) < 1e-9

    def test_un_seul_incident(self):
        """Un seul incident → le barycentre est ce point lui-même."""
        df = _incidents([{"latitude": 45.5, "longitude": 3.7, "nb_clients": 200}])
        lat, lon = calculer_barycentre_incidents(df)
        assert abs(lat - 45.5) < 1e-9
        assert abs(lon - 3.7) < 1e-9


# ─── recommander_prepositionnement ────────────────────────────────────────────

class TestRecommenderPrepositionnement:

    def test_equipes_vides_retourne_liste_vide(self):
        incidents = _incidents([{"latitude": 45.0, "longitude": 3.0, "nb_clients": 100}])
        result = recommander_prepositionnement(pd.DataFrame(), incidents)
        assert result == []

    def test_incidents_vides_retourne_liste_vide(self):
        equipes = _equipes([{
            "id_equipe": "E1", "commune": "Toulouse",
            "latitude": 43.6, "longitude": 1.4, "disponible": True,
        }])
        result = recommander_prepositionnement(equipes, pd.DataFrame())
        assert result == []

    def test_retourne_autant_dentrees_que_dequipes(self):
        incidents = _incidents([
            {"latitude": 45.0, "longitude": 3.0, "nb_clients": 100},
            {"latitude": 45.5, "longitude": 3.5, "nb_clients": 200},
        ])
        equipes = _equipes([
            {"id_equipe": "E1", "commune": "Lyon",    "latitude": 45.7, "longitude": 4.8, "disponible": True},
            {"id_equipe": "E2", "commune": "Clermont","latitude": 45.8, "longitude": 3.1, "disponible": True},
        ])
        result = recommander_prepositionnement(equipes, incidents)
        assert len(result) == 2

    def test_temps_deplacement_positif(self):
        incidents = _incidents([{"latitude": 48.8, "longitude": 2.3, "nb_clients": 50}])
        equipes = _equipes([{
            "id_equipe": "E1", "commune": "Bordeaux",
            "latitude": 44.8, "longitude": -0.6, "disponible": True,
        }])
        result = recommander_prepositionnement(equipes, incidents)
        assert len(result) == 1
        assert result[0]["temps_deplacement_h"] > 0
        assert result[0]["distance_km"] > 0

    def test_trie_par_temps_croissant(self):
        """L'équipe la plus proche du barycentre doit apparaître en premier."""
        # Barycentre ≈ (46.0, 3.0) — E2 est plus proche que E1
        incidents = _incidents([{"latitude": 46.0, "longitude": 3.0, "nb_clients": 100}])
        equipes = _equipes([
            {"id_equipe": "E1", "commune": "Brest",  "latitude": 48.4, "longitude": -4.5, "disponible": True},
            {"id_equipe": "E2", "commune": "Lyon",   "latitude": 45.7, "longitude": 4.8,  "disponible": True},
        ])
        result = recommander_prepositionnement(equipes, incidents)
        assert len(result) == 2
        assert result[0]["temps_deplacement_h"] <= result[1]["temps_deplacement_h"]

    def test_structure_des_cles_retournees(self):
        incidents = _incidents([{"latitude": 45.0, "longitude": 3.0, "nb_clients": 100}])
        equipes = _equipes([{
            "id_equipe": "E1", "commune": "Grenoble",
            "latitude": 45.2, "longitude": 5.7, "disponible": True,
        }])
        result = recommander_prepositionnement(equipes, incidents)
        assert len(result) == 1
        cles_attendues = {
            "id_equipe", "commune",
            "lat_origine", "lon_origine",
            "lat_cible", "lon_cible",
            "temps_deplacement_h", "distance_km",
        }
        assert cles_attendues == set(result[0].keys())

    def test_point_cible_est_le_barycentre(self):
        """lat_cible et lon_cible de chaque recommandation doivent être le barycentre."""
        incidents = _incidents([
            {"latitude": 44.0, "longitude": 2.0, "nb_clients": 100},
            {"latitude": 46.0, "longitude": 4.0, "nb_clients": 100},
        ])
        equipes = _equipes([{
            "id_equipe": "E1", "commune": "X",
            "latitude": 43.0, "longitude": 1.0, "disponible": True,
        }])
        result = recommander_prepositionnement(equipes, incidents)
        assert abs(result[0]["lat_cible"] - 45.0) < 1e-6
        assert abs(result[0]["lon_cible"] - 3.0) < 1e-6

    def test_equipe_sans_coordonnees_ignoree(self):
        """Une équipe dont lat/lon sont None doit être ignorée silencieusement."""
        incidents = _incidents([{"latitude": 45.0, "longitude": 3.0, "nb_clients": 100}])
        equipes = _equipes([
            {"id_equipe": "E1", "commune": "OK",   "latitude": 45.5, "longitude": 3.5, "disponible": True},
            {"id_equipe": "E2", "commune": "NOK",  "latitude": None,  "longitude": None, "disponible": True},
        ])
        result = recommander_prepositionnement(equipes, incidents)
        assert len(result) == 1
        assert result[0]["id_equipe"] == "E1"
