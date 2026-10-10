from pathlib import Path

import pandas as pd
import pytest

from crise.config import chemin_projet
from crise.models import Site, charger_scenario
from crise.prepositionnement import (
    carte_risque,
    exporter_carte_chaleur_folium,
    positions_kmeans,
    positions_pmediane,
    selectionner_candidats,
)

CLEAN = chemin_projet("data", "clean")


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
def test_carte_risque_structure():
    # Test sur un petit sous-ensemble de crises d'apprentissage pour être rapide
    df = carte_risque(crises=[1, 2], n_clusters=20)
    assert isinstance(df, pd.DataFrame)
    assert set(["lat", "lon", "poids"]).issubset(df.columns)
    assert len(df) == 20
    assert (df["poids"] > 0).all()
    # Coordonnées plausibles dans la zone Enedis Occitanie / Pyrénées
    assert df["lat"].between(42.0, 45.0).all()
    assert df["lon"].between(-0.5, 4.0).all()


def test_exporter_carte_chaleur_folium(tmp_path: Path):
    df = pd.DataFrame({
        "lat": [43.1, 43.2, 43.3],
        "lon": [1.1, 1.2, 1.3],
        "poids": [100.0, 250.0, 50.0],
    })
    out = tmp_path / "carte_test.html"
    m = exporter_carte_chaleur_folium(df, chemin_sortie=out)
    assert m is not None
    assert out.exists()
    assert out.stat().st_size > 500


def test_selectionner_candidats():
    sites = [
        Site(id_site="S1", commune="C1", lat=43.0, lon=1.0, nb_equipes=3),
        Site(id_site="S2", commune="C2", lat=43.5, lon=1.5, nb_equipes=2),
    ]
    zones = pd.DataFrame({
        "lat": [43.1, 43.2, 43.6, 43.8, 43.9],
        "lon": [1.1, 1.2, 1.6, 1.8, 1.9],
        "poids": [500.0, 400.0, 300.0, 200.0, 100.0],
    })
    candidats = selectionner_candidats(zones, sites, n_avances=3)
    assert len(candidats) == 2 + 3  # 2 sites + 3 avancés = 5 candidats
    # Les 2 premiers sont les sites
    assert candidats[0] == (43.0, 1.0)
    assert candidats[1] == (43.5, 1.5)


def test_positions_pmediane_et_kmeans_synthetique():
    """Vérifie le MILP OR-Tools et K-Means sans dépendre des données réelles Enedis."""
    sites = [
        Site(id_site="SITE_01", commune="Foix", lat=42.96, lon=1.60, nb_equipes=3),
        Site(id_site="SITE_02", commune="Auch", lat=43.64, lon=0.58, nb_equipes=2),
    ]
    zones = pd.DataFrame({
        "lat": [42.97, 43.65, 43.10],
        "lon": [1.61, 0.59, 1.20],
        "poids": [300.0, 200.0, 100.0],
    })
    pos_pmed = positions_pmediane(zones, sites, n_equipes=5, n_avances=2, max_par_point=4)
    assert len(pos_pmed) == 5
    for eq_id, (lat, lon) in pos_pmed.items():
        assert eq_id.startswith("SITE_")
        assert 42.0 <= lat <= 45.0
        assert -0.5 <= lon <= 4.0

    pos_km = positions_kmeans(zones, sites, n_equipes=5)
    assert len(pos_km) == 5
    for eq_id, (lat, lon) in pos_km.items():
        assert eq_id.startswith("SITE_")
        assert 42.0 <= lat <= 45.0
        assert -0.5 <= lon <= 4.0


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
def test_positions_pmediane_et_kmeans_sur_scenario_reel():
    sites, equipes, _ = charger_scenario(1)
    # Zones réduites pour vitesse de test unitaire
    zones = pd.DataFrame({
        "lat": [s.lat + 0.05 for s in sites],
        "lon": [s.lon + 0.05 for s in sites],
        "poids": [1000.0] * len(sites),
    })

    # Test p-médiane
    pos_pmed = positions_pmediane(zones, sites, n_equipes=63, n_avances=5, max_par_point=8)
    assert isinstance(pos_pmed, dict)
    assert len(pos_pmed) == 63
    for eq_id, (lat, lon) in pos_pmed.items():
        assert eq_id.startswith("SITE_")
        assert 42.0 <= lat <= 45.0
        assert -0.5 <= lon <= 4.0

    # Test K-Means référence
    pos_km = positions_kmeans(zones, sites, n_equipes=63)
    assert isinstance(pos_km, dict)
    assert len(pos_km) == 63
    for eq_id, (lat, lon) in pos_km.items():
        assert eq_id.startswith("SITE_")
        assert 42.0 <= lat <= 45.0
        assert -0.5 <= lon <= 4.0


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
def test_evaluer_prepositionnement(tmp_path: Path):
    from crise.prepositionnement import evaluer_prepositionnement

    resume, details = evaluer_prepositionnement(
        crises_apprentissage=[1],
        crises_test=[81],
        n_clusters=20,
        n_avances=5,
        n_jobs=1,
        dossier_sortie=tmp_path,
    )
    assert isinstance(resume, pd.DataFrame)
    assert isinstance(details, pd.DataFrame)
    assert set(["Sites (base)", "K-Means (63 centres)", "p-médiane (MILP)"]).issubset(resume.index)
    assert (tmp_path / "carte_risque.csv").exists()
    assert (tmp_path / "positions_pmediane.csv").exists()
    assert (tmp_path / "prepositionnement.csv").exists()
