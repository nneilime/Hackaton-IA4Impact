from __future__ import annotations

import pandas as pd

from crise.factice import creer_scenario_factice, generer_sim_result_factice
from crise.instant import equipes_a, incidents_a
from crise.kpi import calculer_kpi
from crise.models import COLONNES_SIMRESULT, Equipe, Incident, SimResult, Site
from crise.policies.baselines import PlusDeClients, PlusProcheFCFS
from crise.policies.wspt_hongrois import WSPTHongroisPolicy


def test_creer_scenario_factice():
    """T4.1 — Vérifie la génération du scénario factice (30 incidents, 6 équipes)."""
    sites, equipes, incidents = creer_scenario_factice(n_incidents=30, n_equipes=6, seed=42)

    assert len(sites) == 3
    assert all(isinstance(s, Site) for s in sites)

    assert len(equipes) == 6
    assert all(isinstance(e, Equipe) for e in equipes)

    assert len(incidents) == 30
    assert all(isinstance(i, Incident) for i in incidents)

    # Vérification des propriétés des incidents
    durations = {i.duree_nominale for i in incidents}
    assert {120, 240, 480}.issubset(durations)
    assert any(i.sensible for i in incidents)
    assert any(not i.sensible for i in incidents)

    # Tri par temps d'apparition
    t_apps = [i.t_apparition for i in incidents]
    assert t_apps == sorted(t_apps)


def test_generer_sim_result_factice_structure():
    """T4.1 — Vérifie la conformité du SimResult factice avec les contrats §4.4."""
    res = generer_sim_result_factice(n_incidents=30, n_equipes=6, seed=42)

    assert isinstance(res, SimResult)
    assert isinstance(res.incidents, pd.DataFrame)
    assert isinstance(res.activites, pd.DataFrame)
    assert isinstance(res.decisions, pd.DataFrame)
    assert isinstance(res.serie, pd.DataFrame)
    assert isinstance(res.metadata, dict)

    assert len(res.incidents) == 30
    assert res.metadata.get("crise") == "CRISE_FACTICE"

    # Vérification des colonnes requises
    for col in COLONNES_SIMRESULT["incidents"]:
        assert col in res.incidents.columns, f"Colonne {col} manquante dans incidents"
    assert "commune" in res.incidents.columns
    assert "departement" in res.incidents.columns

    for col in COLONNES_SIMRESULT["activites"]:
        assert col in res.activites.columns, f"Colonne {col} manquante dans activites"

    for col in COLONNES_SIMRESULT["decisions"]:
        assert col in res.decisions.columns, f"Colonne {col} manquante dans decisions"

    for col in COLONNES_SIMRESULT["serie"]:
        assert col in res.serie.columns, f"Colonne {col} manquante dans serie"


def test_generer_sim_result_factice_kpi_and_instant():
    """T4.1 / T4.3 — Vérifie que le SimResult factice alimente sans erreur KPI et instant."""
    res = generer_sim_result_factice(n_incidents=30, n_equipes=6, seed=42)

    kpi = calculer_kpi(res)
    assert isinstance(kpi, dict)
    assert kpi["clients_heures"] > 0
    assert kpi["depassements_amplitude"] == 0
    assert 0 <= kpi["pct_clients_retablis_4h"] <= 100
    assert kpi["fin_crise_h"] > 0

    # Vérification instantanée
    inc_t = incidents_a(res, t=120)
    assert isinstance(inc_t, pd.DataFrame)
    assert len(inc_t) == 30
    assert "etat" in inc_t.columns
    assert set(inc_t["etat"].unique()).issubset({"à venir", "en attente", "en intervention", "rétabli"})

    eq_t = equipes_a(res, t=120)
    assert isinstance(eq_t, pd.DataFrame)
    assert len(eq_t) == 6
    assert "activite" in eq_t.columns
    assert "lat" in eq_t.columns
    assert "lon" in eq_t.columns


def test_generer_sim_result_factice_differentes_strategies():
    """T4.1 / T4.3 — Vérifie le support des différentes stratégies sur les données factices."""
    res_wspt = generer_sim_result_factice(policy=WSPTHongroisPolicy(), seed=10)
    res_r1 = generer_sim_result_factice(policy=PlusProcheFCFS(), seed=10)
    res_r2 = generer_sim_result_factice(policy=PlusDeClients(), seed=10)

    kpi_wspt = calculer_kpi(res_wspt)
    kpi_r1 = calculer_kpi(res_r1)
    kpi_r2 = calculer_kpi(res_r2)

    assert kpi_wspt["depassements_amplitude"] == 0
    assert kpi_r1["depassements_amplitude"] == 0
    assert kpi_r2["depassements_amplitude"] == 0


def test_creer_carte_folium():
    """T4.2 — Vérifie la génération de la carte interactive Folium avec incidents, équipes et sites."""
    import folium

    from crise.carte import creer_carte_folium
    from crise.factice import creer_sites_factices

    res = generer_sim_result_factice(n_incidents=30, n_equipes=6, seed=42)
    inc_t = incidents_a(res, t=90)
    eq_t = equipes_a(res, t=90)
    sites = creer_sites_factices()

    carte = creer_carte_folium(inc_t, eq_t, sites=sites)
    assert isinstance(carte, folium.Map)
    html = carte.get_root().render()
    assert "openstreetmap" in html.lower() or "leaflet" in html.lower()
    assert "Légende de la crise" in html


def test_carte_folium_legende_couleur_texte():
    """Vérifie que la légende de la carte Folium a une couleur de texte sombre explicite (lisible sur fond blanc)."""
    from crise.carte import creer_carte_folium
    from crise.factice import creer_sites_factices

    res = generer_sim_result_factice(n_incidents=10, n_equipes=2, seed=42)
    inc_t = incidents_a(res, t=30)
    eq_t = equipes_a(res, t=30)
    sites = creer_sites_factices()

    carte = creer_carte_folium(inc_t, eq_t, sites=sites)
    html = carte.get_root().render()
    assert "Légende de la crise" in html
    assert "color: #1a1a1a" in html or "color:#1a1a1a" in html


def test_bandeau_kpi_t4_3():
    """T4.3 — Vérifie le calcul des métriques du bandeau KPI à l'instant t et au global."""
    res = generer_sim_result_factice(n_incidents=30, n_equipes=6, seed=42)
    k = calculer_kpi(res)

    # 1. Métriques globales requises par T4.3
    assert "clients_heures" in k
    assert "pct_clients_retablis_4h" in k
    assert "attente_max_sensible_h" in k
    assert "fin_crise_h" in k
    assert "depassements_amplitude" in k
    assert k["depassements_amplitude"] == 0

    # 2. Métriques instantanées à l'instant t (pas de 30 min)
    for t_test in [0, 60, 180, 360]:
        inc_t = incidents_a(res, t=t_test)
        assert set(inc_t["etat"].unique()).issubset({"à venir", "en attente", "en intervention", "rétabli"})

        nb_attente = int((inc_t["etat"] == "en attente").sum())
        nb_interv = int((inc_t["etat"] == "en intervention").sum())
        nb_retabli = int((inc_t["etat"] == "rétabli").sum())
        nb_a_venir = int((inc_t["etat"] == "à venir").sum())

        assert nb_attente + nb_interv + nb_retabli + nb_a_venir == 30

        eq_t = equipes_a(res, t=t_test)
        assert len(eq_t) == 6


def test_simulation_factice_express_helper():
    """T4.1 — Vérifie que simuler() de la salle de crise fonctionne en mode FACTICE."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "salle_crise_express",
        "app/pages/1_Salle_de_crise_express.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    # On exécute le module dans un contexte contrôlé
    spec.loader.exec_module(mod)

    res, kpi = mod.simuler(
        crise="CRISE_FACTICE (T4.1)",
        code="WSPT",
        alpha=5.0,
        beta=0.1,
        routes=False,
        nb_eq=6,
        hs_pct=0,
    )
    assert isinstance(res, SimResult)
    assert len(res.incidents) == 30
    assert kpi["depassements_amplitude"] == 0
    assert kpi["clients_heures"] > 0


