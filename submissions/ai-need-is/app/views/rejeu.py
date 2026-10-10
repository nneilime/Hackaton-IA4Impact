"""Mode Rejeu : analyse comparative en lecture seule."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.components.detail import render_detail
from app.components.kpi_panel import render_kpi_panel
from app.components.timeline import render_timeline
from crise.preparation.jointure import derouler_equipes, preparer_pannes
from crise.simulation.moteur import comparer_simulations


def render_rejeu(agents_df: pd.DataFrame, postes_df: pd.DataFrame, coupures_df: pd.DataFrame, params: dict[str, Any], libelles: dict[str, str]) -> None:
    st.header("Rejeu et analyse a posteriori")
    st.caption("Espace en lecture seule : comprendre la crise et comparer les stratégies sans déclencher d'intervention.")
    crises = sorted(coupures_df["numero_crise"].dropna().unique().tolist())
    c1, c2, c3 = st.columns([2, 2, 1])
    numero = c1.selectbox("Crise à rejouer", crises, key="rejeu_crise")
    strategie = c2.selectbox("Stratégie à inspecter", list(libelles), format_func=lambda cle: libelles[cle], key="rejeu_strategie")
    nb_pas = c3.selectbox("Horizon", [24, 48, 96], index=1, format_func=lambda n: f"{n / 2:g} h")
    
    scenario = st.selectbox(
        "Scénario",
        [
            "Scénario normal",
            "50% effectifs des équipes sur un pourcentage de l'horizon défini",
            "Crises successives"
        ],
        key="rejeu_scenario"
    )
    pct_horizon = 50
    if scenario == "50% effectifs des équipes sur un pourcentage de l'horizon défini":
        pct_horizon = st.slider("Pourcentage de l'horizon (%)", 10, 90, 50, 10, key="rejeu_pct")

    lancer = st.button("Lancer le rejeu comparatif", type="primary")
    if lancer:
        pannes, nb_ecartes, nb_illisible = preparer_pannes(coupures_df, postes_df, numero)
        
        scenario_moteur = "nominal"
        if scenario == "50% effectifs des équipes sur un pourcentage de l'horizon défini":
            scenario_moteur = "perte_equipes"
        elif scenario == "Crises successives":
            if not pannes.empty and "date_incident" in pannes.columns:
                t_min = pannes["date_incident"].min()
                t_max = pannes["date_incident"].max()
                if pd.notnull(t_min) and pd.notnull(t_max):
                    delta = t_max - t_min + pd.Timedelta(minutes=1)
                    pannes_dup = pannes.copy()
                    pannes_dup["date_incident"] += delta
                    pannes_dup["id_incident"] = pannes_dup["id_incident"].astype(str) + "_dup"
                    pannes = pd.concat([pannes, pannes_dup], ignore_index=True)

        equipes = derouler_equipes(agents_df)
        with st.spinner("Calcul des stratégies de référence…"):
            resultats = comparer_simulations(
                pannes, 
                equipes, 
                30, 
                int(nb_pas) + 1, 
                float(params["geo"]["coeff_detour"]), 
                float(params["geo"]["vitesse_moyenne_kmh"]), 
                params["priorite"], 
                float(params["agents"]["duree_max_travail_h"]), 
                float(params["agents"]["duree_min_repos_h"]),
                scenario=scenario_moteur,
                alea_declenchement_pct=pct_horizon
            )
        # Les sites servent à la carte animée du déroulé (icônes 🏠).
        sites = agents_df[[c for c in ("id_site", "commune", "latitude", "longitude") if c in agents_df.columns]]
        st.session_state["rejeu"] = {"resultats_temporels": resultats, "nb_pannes": len(pannes), "nb_ecartes": nb_ecartes, "nb_illisible": nb_illisible, "pannes": pannes, "sites": sites, "numero_crise": numero}
    simulation = st.session_state.get("rejeu")
    if simulation is None:
        st.info("Choisissez une crise puis lancez le rejeu.")
        return
    st.info("Mode analyse : aucune décision affichée ici n'est exécutable.")
    render_kpi_panel(simulation, tuple(libelles), libelles)
    render_timeline(simulation, strategie, libelles, lancer)
    render_detail(simulation, strategie, libelles)
