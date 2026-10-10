"""Tests de T1.2 — nettoyage des données.

- Tests unitaires sur de petits CSV synthétiques (toujours exécutés).
- Test d'intégration sur les vrais fichiers de data/raw/ (ignoré s'ils sont absents).
"""
from pathlib import Path

import pandas as pd
import pytest

from crise.config import chemin_projet
from crise.data import nettoyage as N

BOM = "﻿"


def _ecrire(dossier: Path, nom: str, lignes: list[str]) -> None:
    (dossier / nom).write_text(BOM + "\r\n".join(lignes) + "\r\n", encoding="utf-8")


@pytest.fixture
def raw_mini(tmp_path: Path) -> Path:
    _ecrire(tmp_path, "agents_v2.csv", [
        "id_site;commune;departement;longitude;latitude;nb_equipes",
        "SITE_01;Foix;Ariège;1.6060;42.9654;2",
        "SITE_02;Auch;Gers;0,5855;43.6464;1",          # virgule décimale tolérée
    ])
    _ecrire(tmp_path, "poste_v2.csv", [
        "id_poste;code_insee;commune;code_departement;departement;region;longitude;latitude;x_l93;y_l93;"
        "nb_clients;poste_avec_client_sensible",
        "POSTE_000001;9122;Foix;9;Ariège;Occitanie;1.60;42.96;575000;6205000;100;1",
        "POSTE_000002;32013;Auch;32;Gers;Occitanie;0.58;43.64;505000;6283000;40;0",
    ])
    _ecrire(tmp_path, "insee_v2.csv", [
        "code_insee;commune;code_departement;departement;latitude;longitude;nb_postes",
        "09122;Foix;09;Ariège;42.96;1.60;1",
        "32013;Auch;32;Gers;43.64;0.58;1",
    ])
    _ecrire(tmp_path, "coupures_v2_100_crises.csv", [
        "numero_crise;id_incident;id_poste;causeInterruption;dateHeureIncident;dureeDepannage",
        "CRISE_001;INC_1;POSTE_000001;Coup de foudre;09/01/2016 14:08;4h",
        "CRISE_001;INC_2;POSTE_000002;Chute de branche par vent;09/01/2016 15:38;2h",
        "CRISE_001;INC_3;POSTE_000001;Coup de foudre;09/01/2016 18:08;8h",   # même poste, même crise
        "CRISE_001;INC_4;POSTE_999999;Véhicule;09/01/2016 16:00;2h",         # poste inconnu → exclu
        "CRISE_002;INC_5;POSTE_000002;Usure naturelle;10/02/2016 00:30;4h",
    ])
    return tmp_path


def test_pipeline_mini(raw_mini: Path, tmp_path: Path):
    clean = tmp_path / "clean"
    r = N.nettoyer(raw_mini, clean)

    assert r["sites"] == 2 and r["equipes"] == 3
    assert r["incidents_lus"] == 5 and r["incidents_valides"] == 4
    assert [e["id_poste"] for e in r["incidents_exclus_poste_inconnu"]] == ["POSTE_999999"]
    assert r["postes_touches_plusieurs_fois"] == 1
    for f in ["sites", "postes", "communes", "incidents"]:
        assert (clean / f"{f}.parquet").exists()
    assert (clean / "rapport_nettoyage.json").exists()

    sites = pd.read_parquet(clean / "sites.parquet")
    assert sites.loc[sites.id_site == "SITE_02", "lon"].item() == pytest.approx(0.5855)

    postes = pd.read_parquet(clean / "postes.parquet")
    assert postes.loc[postes.id_poste == "POSTE_000001", "code_insee"].item() == "09122"   # zfill
    assert postes["sensible"].dtype == bool

    inc = pd.read_parquet(clean / "incidents.parquet").set_index("id_incident")
    assert inc.loc["INC_1", "t_apparition"] == 0
    assert inc.loc["INC_2", "t_apparition"] == 90            # 15:38 - 14:08
    assert inc.loc["INC_3", "duree_min"] == 480
    assert inc.loc["INC_3", "rang_sur_poste"] == 2
    assert inc.loc["INC_5", "t_apparition"] == 0             # temps relatif à SA crise
    assert inc.loc["INC_1", "nb_clients"] == 100 and bool(inc.loc["INC_1", "sensible"])


def test_duree_invalide():
    with pytest.raises(N.DonneesInvalides):
        N._duree_en_minutes(pd.Series(["3h"]))


def test_coordonnees_hors_zone(raw_mini: Path, tmp_path: Path):
    _ecrire(raw_mini, "agents_v2.csv", [
        "id_site;commune;departement;longitude;latitude;nb_equipes",
        "SITE_01;Foix;Ariège;6060;42.9654;2",        # longitude aberrante (ancien bug Excel)
    ])
    with pytest.raises(N.DonneesInvalides, match="hors zone"):
        N.nettoyer(raw_mini, tmp_path / "clean")


def test_fichier_absent(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="data/raw"):
        N.nettoyer(tmp_path, tmp_path / "clean")


RAW = chemin_projet("data", "raw")
VRAIES_DONNEES = all((RAW / f).exists() for f in N.FICHIERS_DEFAUT.values())


@pytest.mark.skipif(not VRAIES_DONNEES, reason="fichiers Enedis absents de data/raw/")
def test_vraies_donnees(tmp_path: Path):
    r = N.nettoyer(RAW, tmp_path / "clean")
    assert r["sites"] == 18
    assert r["equipes"] == 63
    assert r["postes"] == 33288
    assert r["communes"] == 1365
    assert r["crises"] == 100
    assert r["incidents_lus"] == 15681
    assert r["incidents_valides"] == 15676
    assert len(r["incidents_exclus_poste_inconnu"]) == 5
    sites = pd.read_parquet(tmp_path / "clean" / "sites.parquet").set_index("commune")
    assert sites.loc["Laurencin (Toulouse)", "lon"] == pytest.approx(1.4168)
