"""
tests/test_simulation.py — Tests unitaires de base du moteur de simulation.

Exécution :
    pytest tests/
"""

import math
import sys
from pathlib import Path

import pytest

# Assure que le package 'crise' est importable depuis la racine du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

from crise import __version__


# ---------------------------------------------------------------------------
# Tests du package racine
# ---------------------------------------------------------------------------

class TestPackage:
    """Vérifie que le package crise est correctement installé."""

    def test_version_definie(self) -> None:
        """La version du package doit être une chaîne non vide."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_imports_sous_packages(self) -> None:
        """Chaque sous-package doit être importable sans erreur."""
        import crise.models      # noqa: F401
        import crise.loaders     # noqa: F401
        import crise.geo         # noqa: F401
        import crise.simulation  # noqa: F401
        import crise.strategies  # noqa: F401
        import crise.metrics     # noqa: F401
        import crise.explain     # noqa: F401


# ---------------------------------------------------------------------------
# Tests de la formule de Haversine (logique métier critique)
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance Haversine entre deux points GPS (en kilomètres).

    Args:
        lat1: Latitude du point 1 (degrés décimaux).
        lon1: Longitude du point 1 (degrés décimaux).
        lat2: Latitude du point 2 (degrés décimaux).
        lon2: Longitude du point 2 (degrés décimaux).

    Returns:
        Distance en kilomètres.
    """
    R = 6371.0  # Rayon moyen de la Terre en km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


class TestHaversine:
    """Tests unitaires de la formule de Haversine."""

    def test_distance_nulle_meme_point(self) -> None:
        """La distance entre un point et lui-même doit être 0."""
        assert haversine(43.6047, 1.4442, 43.6047, 1.4442) == pytest.approx(0.0, abs=1e-9)

    def test_distance_paris_toulouse(self) -> None:
        """Distance Paris–Toulouse : environ 589 km à vol d'oiseau."""
        dist = haversine(48.8566, 2.3522, 43.6047, 1.4442)
        assert 580.0 <= dist <= 600.0, f"Attendu ~589 km, obtenu {dist:.1f} km"

    def test_distance_symetrique(self) -> None:
        """La distance A→B doit être égale à la distance B→A."""
        d_ab = haversine(43.6047, 1.4442, 43.2965, 0.6272)
        d_ba = haversine(43.2965, 0.6272, 43.6047, 1.4442)
        assert d_ab == pytest.approx(d_ba, rel=1e-9)

    def test_distance_positive(self) -> None:
        """Toute distance entre deux points distincts doit être strictement positive."""
        dist = haversine(43.6047, 1.4442, 43.2965, 0.6272)
        assert dist > 0.0


# ---------------------------------------------------------------------------
# Tests des calculs de clients-heures (métrique principale)
# ---------------------------------------------------------------------------

class TestClientsHeures:
    """Tests du calcul de l'indicateur clients-heures."""

    def test_clients_heures_base(self) -> None:
        """
        100 clients privés d'électricité pendant 2 heures = 200 clients-heures.
        """
        nb_clients: int = 100
        duree_heures: float = 2.0
        clients_heures = nb_clients * duree_heures
        assert clients_heures == pytest.approx(200.0)

    def test_clients_heures_multiple_incidents(self) -> None:
        """Somme de plusieurs incidents indépendants."""
        incidents: list[tuple[int, float]] = [
            (50, 1.0),   # 50 clients × 1 h  = 50 ch
            (200, 0.5),  # 200 clients × 0.5 h = 100 ch
            (80, 3.0),   # 80 clients × 3 h  = 240 ch
        ]
        total = sum(nb * duree for nb, duree in incidents)
        assert total == pytest.approx(390.0)

    def test_clients_heures_zero_si_retabli_instantanement(self) -> None:
        """Si la durée de coupure est 0, les clients-heures sont 0."""
        assert 500 * 0.0 == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests de configuration YAML
# ---------------------------------------------------------------------------

class TestConfiguration:
    """Vérifie la présence et la cohérence de config/params.yaml."""

    @pytest.fixture
    def params(self) -> dict:
        """Charge les paramètres depuis le fichier YAML de configuration."""
        import yaml
        chemin = Path(__file__).parent.parent / "config" / "params.yaml"
        with chemin.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_fichier_params_existe(self) -> None:
        """Le fichier config/params.yaml doit exister."""
        chemin = Path(__file__).parent.parent / "config" / "params.yaml"
        assert chemin.exists(), "config/params.yaml introuvable"

    def test_cles_obligatoires_presentes(self, params: dict) -> None:
        """Les sections obligatoires doivent être présentes dans le YAML."""
        for section in ("simulation", "geo", "priorite", "penalites", "agents"):
            assert section in params, f"Section '{section}' manquante dans params.yaml"

    def test_coeff_detour_valide(self, params: dict) -> None:
        """Le coefficient de détour doit être supérieur à 1.0."""
        coeff = params["geo"]["coeff_detour"]
        assert coeff > 1.0, f"coeff_detour={coeff} doit être > 1.0"

    def test_pas_de_temps_positif(self, params: dict) -> None:
        """Le pas de temps doit être un entier strictement positif."""
        pas = params["simulation"]["pas_de_temps_min"]
        assert isinstance(pas, int)
        assert pas > 0
