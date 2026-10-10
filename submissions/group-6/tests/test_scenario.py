"""Tests de T1.3 (charger_scenario) et des compléments de T1.4 (zones ralenties, trajet depuis la config)."""
from pathlib import Path

import pytest

from crise.config import charger_config, chemin_projet
from crise.data import nettoyage as N
from crise.models import (
    EtatEquipe,
    EtatIncident,
    Incident,
    charger_scenario,
    creer_equipes,
    lister_crises,
    normaliser_numero_crise,
)
from crise.trajet import (
    ZONE_MONTAGNE,
    ZoneRalentie,
    calculer_trajet_min,
    faire_trajet_min,
    matrice_trajet_vectorisee,
)

BOM = "﻿"


def _ecrire(dossier: Path, nom: str, lignes: list[str]) -> None:
    (dossier / nom).write_text(BOM + "\r\n".join(lignes) + "\r\n", encoding="utf-8")


@pytest.fixture
def clean_mini(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    _ecrire(raw, "agents_v2.csv", [
        "id_site;commune;departement;longitude;latitude;nb_equipes",
        "SITE_01;Foix;Ariège;1.6060;42.9654;2",
        "SITE_02;Auch;Gers;0.5855;43.6464;1",
    ])
    _ecrire(raw, "poste_v2.csv", [
        "id_poste;code_insee;commune;code_departement;departement;region;longitude;latitude;x_l93;y_l93;"
        "nb_clients;poste_avec_client_sensible",
        "POSTE_000001;9122;Foix;9;Ariège;Occitanie;1.60;42.96;575000;6205000;100;1",
        "POSTE_000002;32013;Auch;32;Gers;Occitanie;0.58;43.64;505000;6283000;40;0",
    ])
    _ecrire(raw, "insee_v2.csv", [
        "code_insee;commune;code_departement;departement;latitude;longitude;nb_postes",
        "09122;Foix;09;Ariège;42.96;1.60;1",
        "32013;Auch;32;Gers;43.64;0.58;1",
    ])
    _ecrire(raw, "coupures_v2_100_crises.csv", [
        "numero_crise;id_incident;id_poste;causeInterruption;dateHeureIncident;dureeDepannage",
        "CRISE_001;INC_2;POSTE_000002;Chute de branche par vent;09/01/2016 15:38;2h",
        "CRISE_001;INC_1;POSTE_000001;Coup de foudre;09/01/2016 14:08;4h",
        "CRISE_002;INC_5;POSTE_000002;Usure naturelle;10/02/2016 00:30;8h",
    ])
    clean = tmp_path / "clean"
    N.nettoyer(raw, clean)
    return clean


# --------------------------------------------------------------------------- T1.3
@pytest.mark.parametrize("entree", [1, "1", "001", "crise_1", "CRISE_001"])
def test_normaliser_numero_crise(entree):
    assert normaliser_numero_crise(entree) == "CRISE_001"


def test_normaliser_numero_crise_invalide():
    with pytest.raises(ValueError):
        normaliser_numero_crise("tempête")


def test_charger_scenario_mini(clean_mini: Path):
    sites, equipes, incidents = charger_scenario(1, clean_dir=clean_mini)
    assert [s.id_site for s in sites] == ["SITE_01", "SITE_02"]
    assert [e.id_equipe for e in equipes] == ["SITE_01_E1", "SITE_01_E2", "SITE_02_E1"]
    assert all(e.etat is EtatEquipe.DISPONIBLE and e.t_libre == 0 for e in equipes)
    assert equipes[0].lat == pytest.approx(42.9654)                 # part de son site

    assert [i.id_incident for i in incidents] == ["INC_1", "INC_2"]  # triés par t_apparition
    i1, i2 = incidents
    assert isinstance(i1, Incident) and i1.etat is EtatIncident.NON_APPARU
    assert (i1.t_apparition, i2.t_apparition) == (0, 90)
    assert i1.duree_nominale == i1.duree_reelle == 240
    assert i1.nb_clients == 100 and i1.sensible is True
    assert lister_crises(clean_mini) == ["CRISE_001", "CRISE_002"]


def test_objets_neufs_a_chaque_appel(clean_mini: Path):
    _, _, a = charger_scenario(1, clean_dir=clean_mini)
    a[0].etat = EtatIncident.RESOLU
    _, _, b = charger_scenario(1, clean_dir=clean_mini)
    assert b[0].etat is EtatIncident.NON_APPARU


def test_positions_initiales_et_nb_equipes_max(clean_mini: Path):
    _, eq, _ = charger_scenario(1, {"positions_initiales": {"SITE_01_E2": (43.0, 1.0)}}, clean_dir=clean_mini)
    e2 = next(e for e in eq if e.id_equipe == "SITE_01_E2")
    assert (e2.lat, e2.lon, e2.id_site) == (43.0, 1.0, "SITE_01")   # base de rattachement inchangée

    _, eq, _ = charger_scenario(1, {"nb_equipes_max": 2}, clean_dir=clean_mini)
    assert sorted(e.id_equipe for e in eq) == ["SITE_01_E1", "SITE_02_E1"]  # tour de rôle entre sites


def test_erreurs(clean_mini: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="introuvable"):
        charger_scenario(99, clean_dir=clean_mini)
    with pytest.raises(FileNotFoundError, match="nettoyage"):
        charger_scenario(1, clean_dir=tmp_path / "vide")
    sites, _, _ = charger_scenario(1, clean_dir=clean_mini)
    with pytest.raises(ValueError, match="inconnues"):
        creer_equipes(sites, {"SITE_99_E1": (43.0, 1.0)})


CLEAN = chemin_projet("data", "clean")


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
def test_vraie_crise():
    sites, equipes, incidents = charger_scenario("CRISE_027")
    assert len(sites) == 18 and len(equipes) == 63
    assert len(incidents) == 250
    assert incidents[0].t_apparition == 0
    assert len(lister_crises()) == 100


# --------------------------------------------------------------------------- T1.4 (compléments)
class _Pt:
    def __init__(self, lat, lon):
        self.lat, self.lon = lat, lon


def test_zone_ralentie_scalaire():
    foix, ax = (42.9654, 1.6060), (42.7193, 1.8388)          # destination Ax-les-Thermes, en montagne
    normal = calculer_trajet_min(*foix, *ax)
    ralenti = calculer_trajet_min(*foix, *ax, zones=[ZONE_MONTAGNE])
    assert ralenti == pytest.approx(3 * normal)
    toulouse = (43.6369, 1.4168)                               # hors zone : pas d'effet
    assert calculer_trajet_min(*foix, *toulouse, zones=[ZONE_MONTAGNE]) == pytest.approx(
        calculer_trajet_min(*foix, *toulouse))


def test_zone_ralentie_vectorisee_coherente():
    eq = [_Pt(42.9654, 1.6060), _Pt(43.6369, 1.4168)]
    inc = [_Pt(42.7193, 1.8388), _Pt(43.6464, 0.5855)]
    zones = [ZoneRalentie(42.4, 43.05, -0.5, 2.4, 2.5)]
    m = matrice_trajet_vectorisee(eq, inc, zones=zones)
    for a, e in enumerate(eq):
        for b, i in enumerate(inc):
            assert m[a][b] == pytest.approx(calculer_trajet_min(e.lat, e.lon, i.lat, i.lon, zones=zones), rel=1e-6)


def test_faire_trajet_min_depuis_config():
    cfg = charger_config()
    trajet = faire_trajet_min(cfg)
    foix, toulouse = (42.9654, 1.6060), (43.6369, 1.4168)
    t = trajet(*foix, *toulouse)
    assert 95 <= t <= 120                                        # ≈ 76 km × 1,3 / 55 km/h ≈ 1h48
    plus_lent = faire_trajet_min({**cfg, "trajet": {**cfg["trajet"], "vitesse_plaine_kmh": 27.5}})
    assert plus_lent(*foix, *toulouse) == pytest.approx(2 * t)
