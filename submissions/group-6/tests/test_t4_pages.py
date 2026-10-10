"""Tests TDD pour les pages annexes Streamlit (T4.8) et finitions d'accueil (T4.9)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _charger_module(nom: str, chemin: str):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_page_benchmark_chargement_et_calculs(tmp_path: Path):
    """T4.8 — Vérifie que la page 2_Benchmark dispose des fonctions de chargement et d'analyse."""
    mod = _charger_module("page_benchmark", "app/pages/2_Benchmark.py")
    assert hasattr(mod, "charger_benchmark"), "La fonction charger_benchmark doit exister"
    assert hasattr(mod, "creer_figures_benchmark"), "La fonction creer_figures_benchmark doit exister"

    # 1. Comportement robuste sans fichiers (environnement CI propre où outputs/ est vide)
    kpi_vide, resume_vide = mod.charger_benchmark(chemin_outputs=tmp_path)
    assert isinstance(kpi_vide, pd.DataFrame)
    assert isinstance(resume_vide, pd.DataFrame)
    assert mod.creer_figures_benchmark(kpi_vide) == {}

    # 2. Comportement avec fichiers (données réelles ou synthétiques)
    df_synth = pd.DataFrame([
        {"crise": "CRISE_001", "strategie": "R1", "clients_heures": 1000.0, "attente_moy_sensible_h": 3.0},
        {"crise": "CRISE_001", "strategie": "WSPT", "clients_heures": 850.0, "attente_moy_sensible_h": 1.5},
    ])
    df_synth.to_csv(tmp_path / "benchmark_kpi.csv", index=False)
    kpi, resume = mod.charger_benchmark(chemin_outputs=tmp_path)
    assert not kpi.empty, "kpi ne doit pas être vide quand un fichier existe"
    assert "strategie" in kpi.columns
    assert "clients_heures" in kpi.columns

    # Vérification des figures générées
    figs = mod.creer_figures_benchmark(kpi)
    assert isinstance(figs, dict)
    assert "boxplot_clients_heures" in figs
    assert "hist_gains" in figs


def test_page_preparation_chargement_et_donnees(tmp_path: Path):
    """T4.8 — Vérifie que la page 3_Preparation charge les données de carte et positions p-médiane."""
    mod = _charger_module("page_preparation", "app/pages/3_Preparation.py")
    assert hasattr(mod, "charger_donnees_preparation"), "La fonction charger_donnees_preparation doit exister"

    # 1. Comportement sans fichiers (environnement CI)
    z_vide, r_vide, p_vide = mod.charger_donnees_preparation(chemin_outputs=tmp_path)
    assert isinstance(z_vide, pd.DataFrame)
    assert isinstance(r_vide, pd.DataFrame)
    assert isinstance(p_vide, pd.DataFrame)

    # 2. Comportement avec données (synthétiques ou réelles)
    df_res_synth = pd.DataFrame([
        {"configuration": "Sites (base)", "clients_heures": 1000.0, "gain_vs_sites_pct": 0.0},
        {"configuration": "p-médiane (MILP)", "clients_heures": 950.0, "gain_vs_sites_pct": 5.0},
    ])
    df_res_synth.to_csv(tmp_path / "prepositionnement_resume.csv", index=False)
    _, resume, _ = mod.charger_donnees_preparation(chemin_outputs=tmp_path)
    assert not resume.empty
    assert "configuration" in resume.columns or resume.index.name == "configuration"
    assert "gain_vs_sites_pct" in resume.columns or "gain_vs_sites_pct" in resume.reset_index().columns


def test_page_stress_tests_chargement_et_scenarios():
    """T4.8 — Vérifie que la page 4_Stress_tests charge et synthétise les stress tests S1 à S5."""
    mod = _charger_module("page_stress_tests", "app/pages/4_Stress_tests.py")
    assert hasattr(mod, "charger_ou_calculer_stress"), "La fonction charger_ou_calculer_stress doit exister"

    df_stress = mod.charger_ou_calculer_stress()
    assert isinstance(df_stress, pd.DataFrame)
    assert not df_stress.empty
    assert "scenario" in df_stress.columns
    assert "strategie" in df_stress.columns
    assert "clients_heures" in df_stress.columns
    assert "depassements_amplitude" in df_stress.columns
    # 0 dépassement d'amplitude est une exigence absolue de sécurité Enedis
    assert (df_stress["depassements_amplitude"] == 0).all()


def test_accueil_chargement_rapide_t4_9():
    """T4.9 — Vérifie que la page d'accueil charge les KPIs de benchmark de manière réactive."""
    mod = _charger_module("page_accueil", "app/Accueil.py")
    assert hasattr(mod, "charger_kpi_cles_accueil"), "Accueil doit exposer charger_kpi_cles_accueil"
    kpis = mod.charger_kpi_cles_accueil()
    assert isinstance(kpis, dict)
    assert "gain_r1" in kpis
    assert "attente_sensible" in kpis
