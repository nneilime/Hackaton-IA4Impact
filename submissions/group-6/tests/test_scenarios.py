"""Tests unitaires et d'intégration des stress tests S1 à S5 (T3.6)."""
from pathlib import Path

import pytest

from crise.config import chemin_projet
from crise.kpi import depassements_amplitude
from crise.policies.baselines import PlusProcheFCFS
from crise.policies.wspt_hongrois import WSPTHongroisPolicy
from crise.scenarios import (
    construire,
    deuxieme_vague,
    evaluer_scenarios,
    normaliser_nom_scenario,
    simuler_scenario,
)

CLEAN = chemin_projet("data", "clean")
SKIP_SANS_DATA = pytest.mark.skipif(
    not (CLEAN / "incidents.parquet").exists(),
    reason="Données clean absentes : lancer python -m crise.data.nettoyage",
)


def test_normalisation_noms():
    assert normaliser_nom_scenario("S1")[0] == "S1"
    assert normaliser_nom_scenario("routes_coupees")[0] == "S1"
    assert normaliser_nom_scenario("S2")[0] == "S2"
    assert normaliser_nom_scenario("S3")[0] == "S3"
    assert normaliser_nom_scenario("S4")[0] == "S4"
    assert normaliser_nom_scenario("S5")[0] == "S5"
    assert normaliser_nom_scenario("nominal")[0] == "S0"


@SKIP_SANS_DATA
def test_deuxieme_vague():
    sites, eqs, incs = deuxieme_vague(1, decalage_min=360)
    assert len(sites) == 18
    assert len(eqs) == 63
    # Contient des incidents normaux et des incidents V2_
    v1 = [i for i in incs if not i.id_incident.startswith("V2_")]
    v2 = [i for i in incs if i.id_incident.startswith("V2_")]
    assert len(v1) > 0 and len(v2) > 0
    assert len(incs) == len(v1) + len(v2)
    # Vérification du décalage temporel
    assert min(i.t_apparition for i in v2) >= 360
    # Tous les incidents sont triés par t_apparition
    assert all(incs[j].t_apparition <= incs[j + 1].t_apparition for j in range(len(incs) - 1))


@SKIP_SANS_DATA
def test_construire_scenarios():
    # S1 : routes coupées montagne
    spec1 = construire("S1", 1)
    assert spec1["code"] == "S1"
    foix, ax = (42.9654, 1.6060), (42.7193, 1.8388)  # Ax est en montagne
    t_montagne = spec1["trajet_min"](*foix, *ax)
    t_normal = construire("nominal", 1)["trajet_min"](*foix, *ax)
    assert t_montagne == pytest.approx(3.0 * t_normal, rel=1e-3)

    # S2 : 30% indisponibilités à H+3
    spec2 = construire("S2", 1)
    assert spec2["code"] == "S2"
    indispos = spec2["options"]["indisponibilites"]
    assert len(indispos) == 21  # 63 // 3 = 21 équipes
    assert all(ind.t_debut == 180 for ind in indispos)

    # S3 : 2e vague à H+6
    spec3 = construire("S3", 1)
    assert spec3["code"] == "S3"
    assert any(i.id_incident.startswith("V2_") for i in spec3["incidents"])

    # S4 : 2 crises 48h + 50% équipes indisponibles à 48h
    spec4 = construire("S4", 1)
    assert spec4["code"] == "S4"
    assert any(i.id_incident.startswith("V2_") for i in spec4["incidents"])
    indispos4 = spec4["options"]["indisponibilites"]
    assert len(indispos4) == 32  # 63 équipes, une sur deux = 32
    assert all(ind.t_debut == 2880 for ind in indispos4)

    # S5 : 20 équipes seulement
    spec5 = construire("S5", 1)
    assert spec5["code"] == "S5"
    assert len(spec5["equipes"]) == 20


@SKIP_SANS_DATA
def test_simuler_scenarios_s1_et_s5():
    # Test S1 avec WSPT
    res_s1 = simuler_scenario("S1", 1, WSPTHongroisPolicy())
    assert res_s1.metadata["non_resolus"] == 0
    assert depassements_amplitude(res_s1) == 0
    assert res_s1.metadata["clients_heures"] > 0
    assert "commune" in res_s1.incidents.columns

    # Test S5 (20 équipes) avec R1
    res_s5 = simuler_scenario("S5", 1, PlusProcheFCFS())
    assert res_s5.metadata["non_resolus"] == 0
    assert depassements_amplitude(res_s5) == 0
    assert res_s5.metadata["nb_equipes"] == 20


@SKIP_SANS_DATA
def test_evaluer_scenarios_court(tmp_path: Path):
    df_kpi, df_resume = evaluer_scenarios(
        crises=[1],
        strategies={"R1": PlusProcheFCFS, "WSPT": WSPTHongroisPolicy},
        scenarios=["S1", "S5"],
        n_jobs=1,
        dossier_sortie=tmp_path,
    )
    assert len(df_kpi) == 4  # 1 crise × 2 strats × 2 scénarios
    assert (df_kpi["depassements_amplitude"] == 0).all()
    assert (df_kpi["non_resolus"] == 0).all()
    assert set(df_resume["strategie"]) == {"R1", "WSPT"}
    assert (tmp_path / "stress_kpi.csv").exists()
