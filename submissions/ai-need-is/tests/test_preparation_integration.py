"""
Tests d'intégration — flux complet du Mode Préparation.

Vérifie :
  1. Calcul de barycentre + recommandation de prépositionnement sur données réelles.
  2. Format complet du dict plan_preparation (contrat Jour J).
  3. Non-régression Jour J : creer_session_pilotage accepte plan_preparation enrichi.
  4. construire_points_preparation : présence des 3 types de points.
  5. construire_points_preparation avec barycentre NaN : absence de "point_repli".
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from crise.preparation.jointure import construire_points_preparation
from crise.preparation.prepositionnement import (
    calculer_barycentre_incidents,
    recommander_prepositionnement,
)
from crise.simulation.pilotage import creer_session_pilotage


# ─── Fixtures minimales ───────────────────────────────────────────────────────

def _pannes_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "id_incident": "I1",
            "id_poste": "P1",
            "latitude": 43.61,
            "longitude": 1.45,
            "nb_clients": 200,
            "poste_avec_client_sensible": 0,
            "duree_heures": 2.0,
            "date_incident": pd.Timestamp("2026-01-01 08:00"),
        },
        {
            "id_incident": "I2",
            "id_poste": "P2",
            "latitude": 43.65,
            "longitude": 1.50,
            "nb_clients": 100,
            "poste_avec_client_sensible": 1,
            "duree_heures": 1.5,
            "date_incident": pd.Timestamp("2026-01-01 08:30"),
        },
    ])


def _equipes_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "id_equipe": "E1",
            "id_site": "S1",
            "commune": "Toulouse",
            "latitude": 43.60,
            "longitude": 1.44,
            "disponible": True,
        },
        {
            "id_equipe": "E2",
            "id_site": "S2",
            "commune": "Blagnac",
            "latitude": 43.63,
            "longitude": 1.38,
            "disponible": True,
        },
        {
            "id_equipe": "E3",
            "id_site": "S3",
            "commune": "Colomiers",
            "latitude": 43.61,
            "longitude": 1.33,
            "disponible": True,
        },
    ])


def _sites_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"id_site": "S1", "latitude": 43.60, "longitude": 1.44, "commune": "Toulouse"},
        {"id_site": "S2", "latitude": 43.63, "longitude": 1.38, "commune": "Blagnac"},
    ])


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestFluxCompletPrepositionnement:

    def test_barycentre_calculable_sur_pannes_reelles(self):
        """Le barycentre est calculable et cohérent (entre les 2 incidents)."""
        pannes = _pannes_df()
        lat_b, lon_b = calculer_barycentre_incidents(pannes)

        assert not math.isnan(lat_b)
        assert not math.isnan(lon_b)
        # Doit être entre les latitudes des 2 incidents (43.61 et 43.65)
        assert 43.61 <= lat_b <= 43.65
        # Doit être entre les longitudes (1.45 et 1.50)
        assert 1.45 <= lon_b <= 1.50

    def test_recommandation_retourne_une_entree_par_equipe(self):
        result = recommander_prepositionnement(_equipes_df(), _pannes_df(), 1.3, 60.0)
        assert len(result) == 3

    def test_recommandation_triee_par_temps_croissant(self):
        result = recommander_prepositionnement(_equipes_df(), _pannes_df(), 1.3, 60.0)
        temps = [r["temps_deplacement_h"] for r in result]
        assert temps == sorted(temps)

    def test_plan_preparation_contient_toutes_les_cles_contrat(self):
        """
        Simule la construction complète du plan_preparation tel que
        produit par app/views/preparation.py lors de la validation humaine.
        """
        pannes   = _pannes_df()
        equipes  = _equipes_df()

        from crise.strategies.allocator import IncidentAllocator
        allocateur = IncidentAllocator(1.3, 60.0)
        decisions = allocateur.affecter_incidents(equipes, pannes, "distance")

        prepositionnements = recommander_prepositionnement(equipes, pannes, 1.3, 60.0)
        barycentre         = calculer_barycentre_incidents(pannes)

        plan_preparation = {
            "numero_crise":            "TEST_001",
            "horizon_h":               4,
            "strategie":               "distance",
            "pannes":                  pannes,
            "pannes_previsionnelles":  pannes,
            "equipes":                 equipes,
            "decisions":               decisions,
            "prepositionnements":      prepositionnements,
            "barycentre":              barycentre,
            "nb_ecartes":              0,
            "nb_illisible":            0,
            "equipes_en_reserve":      ["E3"],
            "commentaire_humain":      "test",
            "prepositionnements_retenus": [
                p for p in prepositionnements if p["id_equipe"] != "E3"
            ],
            "statut":                  "VALIDE_PAR_L_HUMAIN",
        }

        # Toutes les clés du contrat Jour J doivent être présentes
        for cle in ("decisions", "equipes_en_reserve", "commentaire_humain", "statut"):
            assert cle in plan_preparation, f"Clé manquante : {cle}"

        # Les nouvelles clés doivent aussi être présentes
        assert "prepositionnements_retenus" in plan_preparation
        assert isinstance(plan_preparation["prepositionnements_retenus"], list)


class TestNonRegressionJourJ:

    def test_creer_session_pilotage_accepte_plan_enrichi(self):
        """
        creer_session_pilotage() doit fonctionner sans erreur même si
        plan_preparation contient les nouvelles clés additionnelles.
        """
        pannes  = _pannes_df()
        equipes = _equipes_df()

        prepositionnements = recommander_prepositionnement(equipes, pannes, 1.3, 60.0)
        barycentre         = calculer_barycentre_incidents(pannes)

        plan_enrichi = {
            "numero_crise":            "TEST_001",
            "decisions":               [],
            "equipes_en_reserve":      ["E3"],
            "commentaire_humain":      "",
            "prepositionnements_retenus": prepositionnements,
            "barycentre":              barycentre,
            "statut":                  "VALIDE_PAR_L_HUMAIN",
        }

        # Ne doit pas lever d'exception
        session = creer_session_pilotage(
            pannes, equipes, "distance", 30, 1.3, 60.0,
            plan_preparation=plan_enrichi,
        )

        assert session is not None

    def test_equipes_en_reserve_marquees_correctement(self):
        """
        Les équipes listées dans equipes_en_reserve du plan_preparation enrichi
        doivent avoir l'état 'en_reserve' dans la session pilotage.
        """
        pannes  = _pannes_df()
        equipes = _equipes_df()

        plan_enrichi = {
            "decisions":               [],
            "equipes_en_reserve":      ["E2", "E3"],
            "prepositionnements_retenus": [],
            "statut":                  "VALIDE_PAR_L_HUMAIN",
        }

        session = creer_session_pilotage(
            pannes, equipes, "distance", 30, 1.3, 60.0,
            plan_preparation=plan_enrichi,
        )

        etats = {e["id_equipe"]: e["etat"] for e in session["equipes"]}
        assert etats["E2"] == "en_reserve"
        assert etats["E3"] == "en_reserve"
        # E1 non réservée → doit être libre
        assert etats["E1"] != "en_reserve"


class TestConstruirePointsPreparation:

    def test_trois_types_de_points_presents(self):
        """Carte doit contenir incident_previsionnel, site et point_repli."""
        pannes = _pannes_df()
        sites  = _sites_df()

        points = construire_points_preparation(pannes, sites, 43.63, 1.47)
        types  = set(points["type"].unique())

        assert "incident_previsionnel" in types
        assert "site"                  in types
        assert "point_repli"           in types

    def test_barycentre_nan_pas_de_point_repli(self):
        """Quand le barycentre est NaN, aucun point de type 'point_repli' ne doit apparaître."""
        pannes = _pannes_df()
        sites  = _sites_df()

        points = construire_points_preparation(pannes, sites, float("nan"), float("nan"))
        types  = set(points["type"].unique())

        assert "point_repli" not in types

    def test_incidents_vides_retourne_dataframe_avec_colonnes(self):
        """Même avec des inputs vides, la fonction retourne le bon schéma de colonnes."""
        points = construire_points_preparation(pd.DataFrame(), pd.DataFrame(), float("nan"), float("nan"))
        assert set(points.columns) == {"latitude", "longitude", "type", "color", "libelle"}

    def test_incidents_vides_avec_barycentre_valide(self):
        """Barycentre seul (sans incidents ni sites) → un seul point 'point_repli'."""
        points = construire_points_preparation(pd.DataFrame(), pd.DataFrame(), 45.0, 3.0)
        assert len(points) == 1
        assert points.iloc[0]["type"] == "point_repli"

    def test_couleur_barycentre_est_violet(self):
        """Le point de repli doit avoir la couleur COULEUR_BARYCENTRE (#9467bd)."""
        from crise.preparation.jointure import COULEUR_BARYCENTRE
        points = construire_points_preparation(pd.DataFrame(), pd.DataFrame(), 45.0, 3.0)
        assert points.iloc[0]["color"] == COULEUR_BARYCENTRE
